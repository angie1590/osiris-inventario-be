from datetime import date, datetime, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_role
from app.models.enums import UserRole
from app.models.kardex import KardexEntry
from app.models.system_param import SystemParam
from app.models.user import User
from app.schemas.kardex import KardexResponse

router = APIRouter()

_read_roles = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


def _parse_kardex_bound(
    value: str | None, *, end_of_day_for_date_only: bool
) -> datetime | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None

    try:
        if "T" not in raw and " " not in raw:
            d = date.fromisoformat(raw)
            local_tz = ZoneInfo(settings.APP_TIMEZONE)
            local_dt = datetime.combine(
                d,
                time.max if end_of_day_for_date_only else time.min,
                tzinfo=local_tz,
            )
            return local_dt.astimezone(timezone.utc)

        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="date_from/date_to inválidos"
        ) from exc


@router.get("/{product_id}", response_model=KardexResponse)
async def get_kardex(
    product_id: int,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    date_from_dt = _parse_kardex_bound(date_from, end_of_day_for_date_only=False)
    date_to_dt = _parse_kardex_bound(date_to, end_of_day_for_date_only=True)
    if date_from_dt and date_to_dt and date_from_dt > date_to_dt:
        raise HTTPException(
            status_code=422, detail="date_from debe ser menor o igual a date_to"
        )

    # Get kardex method
    result = await db.execute(
        select(SystemParam).where(SystemParam.key == "kardex_method")
    )
    param = result.scalar_one_or_none()
    method = param.value if param else "PEPS"

    q = (
        select(KardexEntry)
        .where(KardexEntry.product_id == product_id)
        .order_by(KardexEntry.created_at.asc(), KardexEntry.id.asc())
    )
    if date_from_dt:
        q = q.where(KardexEntry.created_at >= date_from_dt)
    if date_to_dt:
        q = q.where(KardexEntry.created_at <= date_to_dt)

    result = await db.execute(q)
    entries = list(result.scalars().all())

    # Get opening balance (last entry before date_from)
    opening_qty = Decimal("0")
    opening_val = Decimal("0")
    opening_avg = Decimal("0")
    if date_from_dt:
        prev_q = (
            select(KardexEntry)
            .where(
                KardexEntry.product_id == product_id,
                KardexEntry.created_at < date_from_dt,
            )
            .order_by(KardexEntry.created_at.desc(), KardexEntry.id.desc())
            .limit(1)
        )
        prev_result = await db.execute(prev_q)
        prev = prev_result.scalar_one_or_none()
        if prev:
            opening_qty = prev.balance_quantity
            opening_val = prev.balance_value
            opening_avg = prev.weighted_avg_cost

    total_in = sum(e.quantity_in for e in entries)
    total_out = sum(e.quantity_out for e in entries)
    closing_qty = entries[-1].balance_quantity if entries else opening_qty
    closing_val = entries[-1].balance_value if entries else opening_val
    weighted_avg = entries[-1].weighted_avg_cost if entries else opening_avg

    return KardexResponse(
        product_id=product_id,
        method=method,
        entries=entries,
        opening_balance_quantity=opening_qty,
        opening_balance_value=opening_val,
        closing_balance_quantity=closing_qty,
        closing_balance_value=closing_val,
        weighted_avg_cost=weighted_avg,
        total_in_quantity=total_in,
        total_out_quantity=total_out,
    )
