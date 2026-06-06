from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.enums import UserRole


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-z0-9_]+$")
    full_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole
    password: str = Field(..., min_length=8)
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=100)
    role: UserRole | None = None
    is_active: bool | None = None
    require_password_change: bool | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    # The model stores this as `must_change_password`; the API exposes it as
    # `require_password_change` to match the auth endpoints and the frontend.
    require_password_change: bool = Field(
        validation_alias=AliasChoices("must_change_password", "require_password_change")
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
