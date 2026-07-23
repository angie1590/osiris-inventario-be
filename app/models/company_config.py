from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompanyConfig(Base):
    __tablename__ = "company_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    razon_social: Mapped[str] = mapped_column(String(200), nullable=False)
    nombre_comercial: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ruc: Mapped[str] = mapped_column(String(20), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    logo: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled_ingreso_types: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: [
            "purchase",
            "initial_inventory",
            "adjustment_positive",
            "customer_return",
            "production",
            "transfer_received",
            "other",
        ],
    )
    enabled_egreso_types: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: [
            "sale",
            "baja",
            "adjustment_negative",
            "supplier_return",
            "internal_consumption",
            "transfer_sent",
            "other",
        ],
    )
    enabled_baja_reasons: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: [
            "damage",
            "expiration",
            "loss",
            "theft",
            "donation",
            "gift",
            "destruction",
            "sample",
            "other",
        ],
    )
    sellers: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
