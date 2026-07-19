from datetime import datetime
from decimal import Decimal
import secrets
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ProductStatus


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    isbn: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: f"AUTO-{secrets.token_hex(8)}",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # Optional human-facing alphanumeric internal code (e.g. L010263). Whether it
    # is used is controlled by the 'internal_code_enabled' system param.
    codigo_interno: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    photo: Mapped[str | None] = mapped_column(Text, nullable=True)
    photos: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    stock_minimo: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=0
    )
    stock_actual: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=0
    )
    pvp: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus), nullable=False, default=ProductStatus.active, index=True
    )
    custom_attributes: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category: Mapped["Category"] = relationship(back_populates="products")  # type: ignore[name-defined]
    document_lines: Mapped[list["InventoryDocumentLine"]] = relationship(back_populates="product")  # type: ignore[name-defined]
    kardex_entries: Mapped[list["KardexEntry"]] = relationship(back_populates="product")  # type: ignore[name-defined]
    inventory_lots: Mapped[list["InventoryLot"]] = relationship(back_populates="product")  # type: ignore[name-defined]
