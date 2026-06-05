from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.enums import UserRole
from app.models.kardex import KardexEntry
from app.models.system_param import SystemParam
from app.models.user import User
from app.schemas.kardex import KardexResponse

router = APIRouter()

_read_roles = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


@router.get("/{product_id}", response_model=KardexResponse)
async def get_kardex(
    product_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    # Get kardex method
    result = await db.execute(select(SystemParam).where(SystemParam.key == "kardex_method"))
    param = result.scalar_one_or_none()
    method = param.value if param else "PEPS"

    q = select(KardexEntry).where(KardexEntry.product_id == product_id).order_by(KardexEntry.created_at.asc(), KardexEntry.id.asc())
    if date_from:
        q = q.where(KardexEntry.created_at >= date_from)
    if date_to:
        q = q.where(KardexEntry.created_at <= date_to)

    result = await db.execute(q)
    entries = list(result.scalars().all())

    # Get opening balance (last entry before date_from)
    opening_qty = Decimal("0")
    opening_val = Decimal("0")
    if date_from:
        prev_q = select(KardexEntry).where(
            KardexEntry.product_id == product_id,
            KardexEntry.created_at < date_from,
        ).order_by(KardexEntry.created_at.desc(), KardexEntry.id.desc()).limit(1)
        prev_result = await db.execute(prev_q)
        prev = prev_result.scalar_one_or_none()
        if prev:
            opening_qty = prev.balance_quantity
            opening_val = prev.balance_value

    total_in = sum(e.quantity_in for e in entries)
    total_out = sum(e.quantity_out for e in entries)
    closing_qty = entries[-1].balance_quantity if entries else opening_qty
    closing_val = entries[-1].balance_value if entries else opening_val

    return KardexResponse(
        product_id=product_id,
        method=method,
        entries=entries,
        opening_balance_quantity=opening_qty,
        opening_balance_value=opening_val,
        closing_balance_quantity=closing_qty,
        closing_balance_value=closing_val,
        total_in_quantity=total_in,
        total_out_quantity=total_out,
    )
