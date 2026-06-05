from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import KardexEntryType


class InventoryLot(Base):
    """Tracks PEPS/FIFO lots — one lot per IN document line."""

    __tablename__ = "inventory_lots"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("inventory_documents.id", ondelete="RESTRICT"), nullable=False)
    quantity_initial: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantity_available: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    lot_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="inventory_lots")  # type: ignore[name-defined]


class KardexEntry(Base):
    """One entry per stock-affecting event per product. Partitioned by created_at (handled via Alembic migration)."""

    __tablename__ = "kardex_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("inventory_documents.id", ondelete="RESTRICT"), nullable=False)
    document_line_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_document_lines.id", ondelete="SET NULL"), nullable=True)
    entry_type: Mapped[KardexEntryType] = mapped_column(Enum(KardexEntryType), nullable=False)
    quantity_in: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    cost_in: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    quantity_out: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    cost_out: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    balance_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    balance_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    weighted_avg_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    product: Mapped["Product"] = relationship(back_populates="kardex_entries")  # type: ignore[name-defined]
