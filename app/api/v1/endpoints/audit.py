from datetime import date, datetime, time, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.models.enums import AuditAction, UserRole
from app.models.user import User as AppUser
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.utils.export_service import ExportService

router = APIRouter()

_audit_roles = require_role(UserRole.admin, UserRole.supervisor)


def _parse_iso_datetime(value: str, *, end_of_day_for_date_only: bool) -> tuple[datetime, bool, date | None]:
    raw = value.strip()

    # Date-only values are interpreted as full day bounds in business timezone.
    if "T" not in raw and " " not in raw:
        d = date.fromisoformat(raw)
        local_tz = ZoneInfo(settings.APP_TIMEZONE)
        local_dt = datetime.combine(d, time.max if end_of_day_for_date_only else time.min, tzinfo=local_tz)
        return local_dt.astimezone(timezone.utc), True, d

    # Datetime values keep their explicit precision.
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, False, None


@router.get("/users")
async def list_audit_users(
    search: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_audit_roles),
):
    q = select(AppUser.id, AppUser.username, AppUser.full_name).order_by(AppUser.full_name, AppUser.username)
    if search:
        term = f"%{search.strip()}%"
        q = q.where(
            or_(
                AppUser.username.ilike(term),
                AppUser.full_name.ilike(term),
            )
        )
    q = q.limit(limit)
    rows = (await db.execute(q)).all()
    return [
        {
            "id": row.id,
            "username": row.username,
            "full_name": row.full_name,
        }
        for row in rows
    ]


@router.get("")
async def list_audit(
    date_from: str = Query(...),
    date_to: str = Query(...),
    user_id: int | None = None,
    action: AuditAction | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 100,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_audit_roles),
):
    try:
        date_from_dt, _, _ = _parse_iso_datetime(date_from, end_of_day_for_date_only=False)
        date_to_dt, _, _ = _parse_iso_datetime(date_to, end_of_day_for_date_only=True)
    except ValueError:
        raise ValidationAppError("INVALID_DATE_RANGE", "date_from/date_to must be valid ISO date or datetime")

    if date_from_dt > date_to_dt:
        raise ValidationAppError("INVALID_DATE_RANGE", "date_from must be before date_to")

    repo = AuditRepository(db)
    logs = await repo.list(
        date_from=date_from_dt, date_to=date_to_dt,
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
    date_from: str = Query(...),
    date_to: str = Query(...),
    user_id: int | None = None,
    action: AuditAction | None = None,
    entity_type: str | None = None,
    format: Literal["excel"] = "excel",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_audit_roles),
):
    try:
        date_from_dt, date_from_only, date_from_date = _parse_iso_datetime(date_from, end_of_day_for_date_only=False)
        date_to_dt, date_to_only, date_to_date = _parse_iso_datetime(date_to, end_of_day_for_date_only=True)
    except ValueError:
        raise ValidationAppError("INVALID_DATE_RANGE", "date_from/date_to must be valid ISO date or datetime")

    if date_from_dt > date_to_dt:
        raise ValidationAppError("INVALID_DATE_RANGE", "date_from must be before date_to")

    if date_from_only and date_to_only and date_from_date and date_to_date:
        delta_days = (date_to_date - date_from_date).days
    else:
        delta_days = (date_to_dt.date() - date_from_dt.date()).days
    if delta_days > settings.MAX_EXPORT_DATE_RANGE_DAYS:
        raise ValidationAppError(
            "DATE_RANGE_TOO_LARGE",
            f"Export date range cannot exceed {settings.MAX_EXPORT_DATE_RANGE_DAYS} days",
        )

    repo = AuditRepository(db)
    logs = await repo.list(
        date_from=date_from_dt, date_to=date_to_dt,
        user_id=user_id, action=action,
        entity_type=entity_type,
        limit=100_000,
    )

    headers = ["ID", "Timestamp", "Usuario", "IP", "Acción", "Entidad", "ID Entidad", "Descripción"]
    rows = [
        [log.id, log.timestamp.strftime("%Y-%m-%d %H:%M:%S"), log.username or "", log.ip_address or "", log.action.value, log.entity_type or "", log.entity_id or "", log.description or ""]
        for log in logs
    ]
    title = f"Log de Auditoría — {date_from_dt.date()} a {date_to_dt.date()}"
    data = ExportService.to_excel(headers, rows, title, sheet_name="Auditoría")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="auditoria.xlsx"'},
    )
