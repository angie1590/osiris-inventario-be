from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, oauth2_scheme, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import (
    ApprovalCodeRequest,
    ChangePasswordRequest,
    LoginResponse,
    MeResponse,
    ProfileUpdateRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()
_approver_roles = require_role(UserRole.admin, UserRole.supervisor)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.login(form_data.username, form_data.password, request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.refresh(body.refresh_token)


@router.post("/logout", status_code=200)
async def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.logout(current_user, token, request)
    return {"message": "Logged out successfully"}


@router.post("/change-password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.change_password(
        current_user, body.current_password, body.new_password, token, request
    )
    return {"message": "Password changed successfully"}


@router.get("/me", response_model=MeResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
        require_password_change=current_user.must_change_password,
        has_approval_code=bool(current_user.approval_code_hash),
    )


@router.post("/approval-code", status_code=200)
async def set_approval_code(
    body: ApprovalCodeRequest,
    request: Request,
    current_user: User = Depends(_approver_roles),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.set_approval_code(current_user, body.approval_code, request)
    return {"message": "Approval code configured"}


@router.patch("/profile", response_model=MeResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.update_profile(current_user, body.full_name, request)
    await db.refresh(current_user)
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
        require_password_change=current_user.must_change_password,
        has_approval_code=bool(current_user.approval_code_hash),
    )
