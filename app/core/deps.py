from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError, ValidationAppError
from app.core.redis import get_redis
from app.core.security import decode_token
from app.models.enums import UserRole
from app.models.system_param import SystemParam
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT, check blacklist, check inactivity timeout, return user."""
    try:
        payload = decode_token(token)
    except JWTError:
        raise UnauthorizedError("INVALID_TOKEN", "Token is invalid or expired")

    if payload.get("type") != "access":
        raise UnauthorizedError("INVALID_TOKEN", "Not an access token")

    # Check blacklist
    redis = await get_redis()
    if await redis.get(f"blacklist:{token}"):
        raise UnauthorizedError("TOKEN_REVOKED", "Token has been revoked")

    user_id = int(payload["sub"])

    # Check inactivity session key
    session_key = f"session:{user_id}:{token[-16:]}"
    session_value = await redis.get(session_key)
    if session_value is None:
        raise UnauthorizedError("SESSION_EXPIRED", "Session expired due to inactivity")

    # Refresh inactivity TTL on every authenticated request
    from app.core.config import settings
    result = await db.execute(select(SystemParam).where(SystemParam.key == "session_timeout_minutes"))
    param = result.scalar_one_or_none()
    session_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    if param:
        try:
            parsed = int(param.value)
            if parsed > 0:
                session_minutes = parsed
        except (TypeError, ValueError):
            pass
    session_ttl = session_minutes * 60
    await redis.expire(session_key, session_ttl)

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("ACCOUNT_INACTIVE", "Account is inactive")

    return user


def require_role(*roles: UserRole):
    """FastAPI dependency that enforces one of the given roles."""

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError()
        return user

    return _check


# Convenience shortcuts
require_admin = require_role(UserRole.admin)
require_admin_or_supervisor = require_role(UserRole.admin, UserRole.supervisor)
require_any_role = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


async def require_company_configured(db: AsyncSession = Depends(get_db)) -> None:
    from app.repositories.company_repository import CompanyRepository
    company = await CompanyRepository(db).get()
    if not company or not (company.razon_social and company.ruc and company.email):
        raise ValidationAppError("COMPANY_NOT_CONFIGURED", "Company configuration is incomplete")


async def get_stock_mode(db: AsyncSession = Depends(get_db)) -> str:
    """Return 'integer' or 'decimal' based on the stock_quantity_mode system param."""
    from sqlalchemy import select
    from app.models.system_param import SystemParam
    result = await db.execute(select(SystemParam).where(SystemParam.key == "stock_quantity_mode"))
    param = result.scalar_one_or_none()
    return param.value if param else "integer"
