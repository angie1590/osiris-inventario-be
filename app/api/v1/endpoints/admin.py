from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.enums import AuditAction, UserRole
from app.models.kardex import KardexEntry
from app.models.system_param import SystemParam
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter()

_admin_only = require_role(UserRole.admin)
_numeric_params = {
    "session_timeout_minutes",
    "max_export_date_range_days",
    "auth_code_expire_minutes",
    "doc_number_padding",
}


class ParamUpdate(BaseModel):
    value: str


class ParamResponse(BaseModel):
    id: int
    key: str
    value: str
    description: str | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/params", response_model=list[ParamResponse])
async def list_params(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_only),
):
    result = await db.execute(select(SystemParam).order_by(SystemParam.key))
    return list(result.scalars().all())


@router.patch("/params/{key}", response_model=ParamResponse)
async def update_param(
    key: str,
    body: ParamUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_admin_only),
):
    result = await db.execute(select(SystemParam).where(SystemParam.key == key))
    param = result.scalar_one_or_none()
    if not param:
        raise NotFoundError("PARAM_NOT_FOUND", f"Parameter '{key}' not found")

    normalized_value = body.value.strip()
    if not normalized_value:
        raise ValidationAppError("EMPTY_PARAM_VALUE", f"Parameter '{key}' cannot be empty")

    if key in _numeric_params:
        if not normalized_value.isdigit():
            raise ValidationAppError("INVALID_PARAM_VALUE", f"Parameter '{key}' must be an integer")

    # Special validation for kardex_method change
    if key == "kardex_method":
        new_method = normalized_value.upper()
        if new_method not in ("PEPS", "WEIGHTED_AVERAGE"):
            from app.core.exceptions import ValidationAppError
            raise ValidationAppError("INVALID_KARDEX_METHOD", "Method must be PEPS or WEIGHTED_AVERAGE")

        current_year = datetime.now(timezone.utc).year
        year_start = datetime(current_year, 1, 1, tzinfo=timezone.utc)
        check = await db.execute(
            select(KardexEntry.id).where(KardexEntry.created_at >= year_start).limit(1)
        )
        if check.scalar_one_or_none() is not None:
            raise ConflictError("KARDEX_METHOD_LOCKED", "Cannot change kardex method with movements in the current fiscal year")

    previous = {"value": param.value}
    param.value = normalized_value
    param.updated_by = current_user.id

    audit = AuditService(db)
    await audit.log(
        AuditAction.UPDATE, user_id=current_user.id, username=current_user.username,
        entity_type="system_param", entity_id=key,
        previous=previous, new={"value": normalized_value},
        description=f"Parameter '{key}' updated",
        request=request,
    )
    await db.commit()
    await db.refresh(param)
    return param
