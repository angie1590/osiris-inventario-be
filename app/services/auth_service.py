import hashlib
import re
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ValidationAppError
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import AuditAction
from app.models.system_param import SystemParam
from app.models.user import RefreshToken, User
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.audit = AuditService(db)

    async def _get_session_timeout_minutes(self) -> int:
        result = await self.db.execute(
            select(SystemParam).where(SystemParam.key == "session_timeout_minutes")
        )
        param = result.scalar_one_or_none()
        default_value = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        if not param:
            return default_value
        try:
            value = int(param.value)
        except (TypeError, ValueError):
            return default_value
        return value if value > 0 else default_value

    async def login(
        self, username: str, password: str, request: Request | None = None
    ) -> dict:
        user = await self.user_repo.get_by_username(username)

        if not user or not verify_password(password, user.hashed_password):
            await self.audit.log(
                AuditAction.LOGIN_FAILED,
                username=username,
                entity_type="user",
                entity_id=user.id if user else None,
                new={"username_attempt": username, "reason": "invalid_credentials"},
                description=f"Intento fallido de inicio de sesión para '{username}'",
                request=request,
            )
            await self.db.commit()
            raise UnauthorizedError("INVALID_CREDENTIALS", "Invalid credentials")

        if not user.is_active:
            await self.audit.log(
                AuditAction.LOGIN_FAILED,
                user_id=user.id,
                username=user.username,
                entity_type="user",
                entity_id=user.id,
                previous={"is_active": user.is_active},
                new={"username_attempt": username, "reason": "account_inactive"},
                description=f"Intento de inicio de sesión con usuario inactivo '{user.username}'",
                request=request,
            )
            await self.db.commit()
            raise UnauthorizedError("ACCOUNT_INACTIVE", "Account is inactive")

        access_token = create_access_token(
            user.id, extra_claims={"role": user.role.value, "username": user.username}
        )
        refresh_token_str = create_refresh_token(user.id)

        rt = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(refresh_token_str),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=request.client.host if request and request.client else None,
        )
        await self.user_repo.save_refresh_token(rt)

        # Initialize inactivity key in Redis
        redis = await get_redis()
        session_timeout_minutes = await self._get_session_timeout_minutes()
        session_ttl = session_timeout_minutes * 60
        await redis.setex(f"session:{user.id}:{access_token[-16:]}", session_ttl, "1")

        await self.audit.log(
            AuditAction.LOGIN,
            user_id=user.id,
            username=user.username,
            entity_type="user",
            entity_id=user.id,
            description="Inicio de sesión exitoso",
            request=request,
        )
        await self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "bearer",
            "require_password_change": user.must_change_password,
            "session_timeout_minutes": session_timeout_minutes,
        }

    async def refresh(self, refresh_token_str: str) -> dict:
        token_hash = _hash_token(refresh_token_str)
        rt = await self.user_repo.get_refresh_token_by_hash(token_hash)

        if not rt:
            raise UnauthorizedError(
                "TOKEN_REVOKED", "Refresh token is invalid or revoked"
            )

        if rt.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedError("TOKEN_EXPIRED", "Refresh token has expired")

        user = await self.user_repo.get_by_id(rt.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("ACCOUNT_INACTIVE", "Account is inactive")

        # Rotate refresh token
        await self.user_repo.revoke_refresh_token(rt.id)
        new_refresh = create_refresh_token(user.id)
        new_rt = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(new_refresh),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.user_repo.save_refresh_token(new_rt)

        access_token = create_access_token(
            user.id, extra_claims={"role": user.role.value, "username": user.username}
        )
        redis = await get_redis()
        session_timeout_minutes = await self._get_session_timeout_minutes()
        session_ttl = session_timeout_minutes * 60
        await redis.setex(f"session:{user.id}:{access_token[-16:]}", session_ttl, "1")

        await self.db.commit()
        return {
            "access_token": access_token,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "session_timeout_minutes": session_timeout_minutes,
        }

    async def logout(
        self, user: User, access_token: str, request: Request | None = None
    ) -> None:
        # Blacklist access token in Redis
        redis = await get_redis()
        await redis.setex(
            f"blacklist:{access_token}",
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 60,
            "1",
        )
        # Revoke all refresh tokens for this user
        await self.user_repo.revoke_all_refresh_tokens(user.id)

        await self.audit.log(
            AuditAction.LOGOUT,
            user_id=user.id,
            username=user.username,
            entity_type="user",
            entity_id=user.id,
            description="Cierre de sesión",
            request=request,
        )
        await self.db.commit()

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
        access_token: str,
        request: Request | None = None,
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise ValidationAppError(
                "INVALID_CURRENT_PASSWORD", "Current password is incorrect"
            )

        user.hashed_password = hash_password(new_password)
        user.must_change_password = False

        # Invalidate all sessions
        redis = await get_redis()
        await redis.setex(
            f"blacklist:{access_token}",
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 60,
            "1",
        )
        await self.user_repo.revoke_all_refresh_tokens(user.id)

        await self.audit.log(
            AuditAction.PASSWORD_CHANGED,
            user_id=user.id,
            username=user.username,
            entity_type="user",
            entity_id=user.id,
            description="Contraseña actualizada",
            request=request,
        )
        await self.db.commit()

    async def set_approval_code(
        self, user: User, approval_code: str, request: Request | None = None
    ) -> None:
        if user.role.value not in ("admin", "supervisor"):
            raise ValidationAppError(
                "APPROVAL_CODE_ROLE_NOT_ALLOWED",
                "Only admin or supervisor users can configure an approval code",
            )

        normalized = approval_code.strip()
        if not re.fullmatch(r"\d{4}", normalized):
            raise ValidationAppError(
                "INVALID_APPROVAL_CODE_FORMAT",
                "Approval code must be exactly 4 digits",
            )

        user.approval_code_hash = hash_password(normalized)

        await self.audit.log(
            AuditAction.UPDATE,
            user_id=user.id,
            username=user.username,
            entity_type="user",
            entity_id=user.id,
            description="Approval code configured",
            request=request,
        )
        await self.db.commit()

    async def update_profile(
        self, user: User, full_name: str, request: Request | None = None
    ) -> None:
        normalized = full_name.strip()
        if not normalized:
            raise ValidationAppError("INVALID_FULL_NAME", "Full name is required")

        previous = {"full_name": user.full_name}
        user.full_name = normalized

        await self.audit.log(
            AuditAction.UPDATE,
            user_id=user.id,
            username=user.username,
            entity_type="user",
            entity_id=user.id,
            previous=previous,
            new={"full_name": user.full_name},
            description="Profile updated",
            request=request,
        )
        await self.db.commit()
