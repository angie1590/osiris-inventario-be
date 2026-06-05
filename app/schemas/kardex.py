from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import KardexEntryType


class KardexEntryResponse(BaseModel):
    id: int
    product_id: int
    document_id: int
    entry_type: KardexEntryType
    quantity_in: Decimal
    cost_in: Decimal
    quantity_out: Decimal
    cost_out: Decimal
    balance_quantity: Decimal
    balance_value: Decimal
    weighted_avg_cost: Decimal
    lot_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KardexResponse(BaseModel):
    product_id: int
    method: str
    entries: list[KardexEntryResponse]
    opening_balance_quantity: Decimal
    opening_balance_value: Decimal
    closing_balance_quantity: Decimal
    closing_balance_value: Decimal
    total_in_quantity: Decimal
    total_out_quantity: Decimal
