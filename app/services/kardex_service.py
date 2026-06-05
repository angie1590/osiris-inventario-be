from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryDocument, InventoryDocumentLine
from app.models.enums import DocumentType, KardexEntryType
from app.models.kardex import InventoryLot, KardexEntry


class KardexService:
    def __init__(self, db: AsyncSession, method: str = "PEPS"):
        self.db = db
        self.method = method  # "PEPS" or "WEIGHTED_AVERAGE"

    async def _get_current_balance(self, product_id: int) -> tuple[Decimal, Decimal, Decimal]:
        """Returns (balance_quantity, balance_value, weighted_avg_cost)."""
        result = await self.db.execute(
            select(KardexEntry)
            .where(KardexEntry.product_id == product_id)
            .order_by(KardexEntry.created_at.desc(), KardexEntry.id.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        if not last:
            return Decimal("0"), Decimal("0"), Decimal("0")
        return last.balance_quantity, last.balance_value, last.weighted_avg_cost

    async def record_entry(self, document: InventoryDocument, lines: list[InventoryDocumentLine]) -> None:
        """Create Kardex entries for an approved document."""
        if self.method == "PEPS":
            await self._record_peps(document, lines)
        else:
            await self._record_weighted_average(document, lines)

    async def _record_peps(self, document: InventoryDocument, lines: list[InventoryDocumentLine]) -> None:
        for line in lines:
            balance_qty, balance_val, avg_cost = await self._get_current_balance(line.product_id)

            if document.doc_type == DocumentType.IN:
                # Create lot
                lot = InventoryLot(
                    product_id=line.product_id,
                    document_id=document.id,
                    quantity_initial=line.quantity,
                    quantity_available=line.quantity,
                    unit_cost=line.unit_cost,
                    lot_date=document.created_at,
                )
                self.db.add(lot)
                await self.db.flush()

                new_balance_qty = balance_qty + line.quantity
                new_balance_val = balance_val + (line.quantity * line.unit_cost)
                new_avg = new_balance_val / new_balance_qty if new_balance_qty > 0 else Decimal("0")

                entry = KardexEntry(
                    product_id=line.product_id,
                    document_id=document.id,
                    document_line_id=line.id,
                    entry_type=KardexEntryType.IN,
                    quantity_in=line.quantity,
                    cost_in=line.unit_cost,
                    quantity_out=Decimal("0"),
                    cost_out=Decimal("0"),
                    balance_quantity=new_balance_qty,
                    balance_value=new_balance_val,
                    weighted_avg_cost=new_avg,
                    lot_id=lot.id,
                )
                self.db.add(entry)

            else:
                # OUT: consume lots FIFO
                remaining = line.quantity
                await self._consume_lots_peps(line, document, remaining, balance_qty, balance_val)

    async def _consume_lots_peps(self, line: InventoryDocumentLine, document: InventoryDocument, qty_to_consume: Decimal, balance_qty: Decimal, balance_val: Decimal) -> None:
        result = await self.db.execute(
            select(InventoryLot)
            .where(InventoryLot.product_id == line.product_id, InventoryLot.quantity_available > 0)
            .order_by(InventoryLot.lot_date.asc(), InventoryLot.id.asc())
        )
        lots = list(result.scalars().all())

        remaining = qty_to_consume
        current_balance_qty = balance_qty
        current_balance_val = balance_val

        for lot in lots:
            if remaining <= 0:
                break
            consumed = min(lot.quantity_available, remaining)
            lot.quantity_available -= consumed
            remaining -= consumed
            cost_out = consumed * lot.unit_cost
            current_balance_qty -= consumed
            current_balance_val -= cost_out
            new_avg = current_balance_val / current_balance_qty if current_balance_qty > 0 else Decimal("0")

            entry = KardexEntry(
                product_id=line.product_id,
                document_id=document.id,
                document_line_id=line.id,
                entry_type=KardexEntryType.OUT if document.doc_type in (DocumentType.EG,) else KardexEntryType.ADJUST,
                quantity_in=Decimal("0"),
                cost_in=Decimal("0"),
                quantity_out=consumed,
                cost_out=lot.unit_cost,
                balance_quantity=current_balance_qty,
                balance_value=current_balance_val,
                weighted_avg_cost=new_avg,
                lot_id=lot.id,
            )
            self.db.add(entry)

    async def _record_weighted_average(self, document: InventoryDocument, lines: list[InventoryDocumentLine]) -> None:
        for line in lines:
            balance_qty, balance_val, avg_cost = await self._get_current_balance(line.product_id)

            if document.doc_type == DocumentType.IN:
                new_balance_qty = balance_qty + line.quantity
                new_balance_val = balance_val + (line.quantity * line.unit_cost)
                new_avg = (new_balance_val / new_balance_qty).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if new_balance_qty > 0 else Decimal("0")

                entry = KardexEntry(
                    product_id=line.product_id,
                    document_id=document.id,
                    document_line_id=line.id,
                    entry_type=KardexEntryType.IN,
                    quantity_in=line.quantity,
                    cost_in=line.unit_cost,
                    quantity_out=Decimal("0"),
                    cost_out=Decimal("0"),
                    balance_quantity=new_balance_qty,
                    balance_value=new_balance_val,
                    weighted_avg_cost=new_avg,
                )
                self.db.add(entry)

            else:
                cost_out_total = line.quantity * avg_cost
                new_balance_qty = balance_qty - line.quantity
                new_balance_val = balance_val - cost_out_total
                new_avg = avg_cost if new_balance_qty > 0 else Decimal("0")

                entry = KardexEntry(
                    product_id=line.product_id,
                    document_id=document.id,
                    document_line_id=line.id,
                    entry_type=KardexEntryType.OUT if document.doc_type == DocumentType.EG else KardexEntryType.ADJUST,
                    quantity_in=Decimal("0"),
                    cost_in=Decimal("0"),
                    quantity_out=line.quantity,
                    cost_out=avg_cost,
                    balance_quantity=new_balance_qty,
                    balance_value=new_balance_val,
                    weighted_avg_cost=new_avg,
                )
                self.db.add(entry)
