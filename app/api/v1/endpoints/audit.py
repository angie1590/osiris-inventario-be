from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.core.exceptions import ValidationAppError
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.utils.export_service import ExportService

router = APIRouter()

_audit_roles = require_role(UserRole.admin, UserRole.supervisor)


@router.get("")
async def list_audit(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    user_id: int | None = None,
    action: AuditAction | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 100,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_audit_roles),
):
    if date_from > date_to:
        raise ValidationAppError("INVALID_DATE_RANGE", "date_from must be before date_to")

    repo = AuditRepository(db)
    logs = await repo.list(
        date_from=date_from, date_to=date_to,
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        limit=limit, cursor=cursor,
    )
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "user_id": log.user_id,
            "username": log.username,
            "ip_address": log.ip_address,
            "action": log.action.value,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "previous_values": log.previous_values,
            "new_values": log.new_values,
            "description": log.description,
        }
        for log in logs
    ]


@router.get("/export")
async def export_audit(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    user_id: int | None = None,
    action: AuditAction | None = None,
    entity_type: str | None = None,
    format: Literal["excel"] = "excel",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_audit_roles),
):
    from app.core.config import settings
    if date_from > date_to:
        raise ValidationAppError("INVALID_DATE_RANGE", "date_from must be before date_to")

    delta_days = (date_to - date_from).days
    if delta_days > settings.MAX_EXPORT_DATE_RANGE_DAYS:
        raise ValidationAppError(
            "DATE_RANGE_TOO_LARGE",
            f"Export date range cannot exceed {settings.MAX_EXPORT_DATE_RANGE_DAYS} days",
        )

    repo = AuditRepository(db)
    logs = await repo.list(
        date_from=date_from, date_to=date_to,
        user_id=user_id, action=action,
        entity_type=entity_type,
        limit=100_000,
    )

    headers = ["ID", "Timestamp", "Usuario", "IP", "Acción", "Entidad", "ID Entidad", "Descripción"]
    rows = [
        [log.id, log.timestamp.strftime("%Y-%m-%d %H:%M:%S"), log.username or "", log.ip_address or "", log.action.value, log.entity_type or "", log.entity_id or "", log.description or ""]
        for log in logs
    ]
    title = f"Log de Auditoría — {date_from.date()} a {date_to.date()}"
    data = ExportService.to_excel(headers, rows, title, sheet_name="Auditoría")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="auditoria.xlsx"'},
    )
