from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    require_password_change: bool = False
    session_timeout_minutes: int = 30


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    session_timeout_minutes: int = 30


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class ApprovalCodeRequest(BaseModel):
    approval_code: str = Field(..., min_length=8, max_length=8)


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)


class MeResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    require_password_change: bool
    has_approval_code: bool

    model_config = ConfigDict(from_attributes=True)
