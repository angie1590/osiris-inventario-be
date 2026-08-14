from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.redis import get_redis
from app.core.security import DEFAULT_USER_PASSWORD, hash_password
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService

router = APIRouter()

_admin_or_supervisor = require_role(UserRole.admin, UserRole.supervisor)


def _assert_can_manage(current_user: User, target_role: UserRole) -> None:
    """El supervisor no gestiona cuentas de administrador."""
    if current_user.role != UserRole.admin and target_role == UserRole.admin:
        raise ForbiddenError(
            detail="No tienes permiso para gestionar cuentas de administrador."
        )


@router.get("", response_model=list[UserResponse])
async def list_users(
    limit: int = 50,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_admin_or_supervisor),
):
    repo = UserRepository(db)
    users = await repo.list_users(limit=limit, cursor=cursor)
    if current_user.role != UserRole.admin:
        users = [u for u in users if u.role != UserRole.admin]
    return users


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_admin_or_supervisor),
):
    _assert_can_manage(current_user, body.role)
    repo = UserRepository(db)
    existing = await repo.get_by_username(body.username)
    if existing:
        raise ConflictError("USERNAME_TAKEN", f"Username '{body.username}' is already taken")

    new_user = User(
        username=body.username,
        hashed_password=hash_password(DEFAULT_USER_PASSWORD),
        full_name=body.full_name,
        role=body.role,
        is_active=body.is_active,
        must_change_password=True,
    )
    user = await repo.create(new_user)

    audit = AuditService(db)
    await audit.log(
        AuditAction.CREATE,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="user",
        entity_id=user.id,
        new={"username": user.username, "role": user.role.value, "full_name": user.full_name},
        description=f"Usuario '{user.username}' creado",
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_admin_or_supervisor),
):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("USER_NOT_FOUND", "User not found")
    _assert_can_manage(current_user, user.role)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_admin_or_supervisor),
):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("USER_NOT_FOUND", "User not found")
    _assert_can_manage(current_user, user.role)
    if body.role is not None:
        _assert_can_manage(current_user, body.role)

    previous = {
        "role": user.role.value,
        "is_active": user.is_active,
        "full_name": user.full_name,
        "must_change_password": user.must_change_password,
    }
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.require_password_change is not None:
        user.must_change_password = body.require_password_change

    audit = AuditService(db)
    await audit.log(
        AuditAction.UPDATE,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="user",
        entity_id=user.id,
        previous=previous,
        new={
            "role": user.role.value,
            "is_active": user.is_active,
            "full_name": user.full_name,
            "must_change_password": user.must_change_password,
        },
        description=f"Usuario '{user.username}' actualizado",
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_user_password(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_admin_or_supervisor),
):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("USER_NOT_FOUND", "User not found")
    _assert_can_manage(current_user, user.role)

    user.hashed_password = hash_password(DEFAULT_USER_PASSWORD)
    user.must_change_password = True
    await repo.revoke_all_refresh_tokens(user.id)

    # Corta las sesiones activas: sin la clave de sesión, el access token deja de servir.
    redis = await get_redis()
    async for key in redis.scan_iter(match=f"session:{user.id}:*"):
        await redis.delete(key)

    audit = AuditService(db)
    await audit.log(
        AuditAction.PASSWORD_CHANGED,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="user",
        entity_id=user.id,
        description=f"Contraseña de '{user.username}' restablecida por defecto",
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_admin_or_supervisor),
):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("USER_NOT_FOUND", "User not found")
    _assert_can_manage(current_user, user.role)
    if user.id == current_user.id:
        raise ConflictError("CANNOT_DEACTIVATE_SELF", "Cannot deactivate your own account")

    previous = {"is_active": user.is_active}
    user.is_active = False

    audit = AuditService(db)
    await audit.log(
        AuditAction.DELETE,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="user",
        entity_id=user.id,
        previous=previous,
        new={"is_active": False},
        description=f"Usuario '{user.username}' desactivado",
        request=request,
    )
    await db.commit()
