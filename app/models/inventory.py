from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AdjustType, DocumentStatus, DocumentType


class DocumentSequence(Base):
    __tablename__ = "document_sequences"
    __table_args__ = (UniqueConstraint("doc_type", "year", name="uq_doc_sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    last_number: Mapped[int] = mapped_column(nullable=False, default=0)


class CountSequence(Base):
    __tablename__ = "count_sequences"
    __table_args__ = (UniqueConstraint("prefix", "year", name="uq_count_sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    last_number: Mapped[int] = mapped_column(nullable=False, default=0)


class InventoryDocument(Base):
    __tablename__ = "inventory_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType), nullable=False, index=True
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), nullable=False, default=DocumentStatus.pending, index=True
    )
    ingreso_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    purchase_document_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    purchase_document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    purchase_document_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    baja_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    adjustment_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjust_type: Mapped[AdjustType | None] = mapped_column(
        Enum(AdjustType), nullable=True
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    authorized_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    authorized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # type: ignore[name-defined]
    authorizer: Mapped["User | None"] = relationship("User", foreign_keys=[authorized_by])  # type: ignore[name-defined]
    supplier: Mapped["InventorySupplier | None"] = relationship("InventorySupplier")
    lines: Mapped[list["InventoryDocumentLine"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["InventoryDocumentAttachment"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    authorization_codes: Mapped[list["AuthorizationCode"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    @property
    def egreso_type(self) -> str | None:
        if self.doc_type != DocumentType.EG:
            return None
        legacy_baja_types = {
            "damage_disposal",
            "expiration_disposal",
            "loss_theft_disposal",
            "donation",
        }
        if self.ingreso_type in legacy_baja_types:
            return "baja"
        return self.ingreso_type


class InventorySupplier(Base):
    __tablename__ = "inventory_suppliers"
    __table_args__ = (
        UniqueConstraint(
            "identification_type",
            "ruc",
            name="uq_inventory_supplier_identification",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    identification_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ruc", index=True
    )
    ruc: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def identification_number(self) -> str:
        return self.ruc

    @identification_number.setter
    def identification_number(self, value: str) -> None:
        self.ruc = value


class InventoryCount(Base):
    __tablename__ = "inventory_counts"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    positive_adjustment_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_documents.id", ondelete="SET NULL"), nullable=True
    )
    negative_adjustment_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_documents.id", ondelete="SET NULL"), nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # type: ignore[name-defined]
    positive_adjustment_document: Mapped["InventoryDocument | None"] = relationship(
        "InventoryDocument", foreign_keys=[positive_adjustment_document_id]
    )
    negative_adjustment_document: Mapped["InventoryDocument | None"] = relationship(
        "InventoryDocument", foreign_keys=[negative_adjustment_document_id]
    )
    lines: Mapped[list["InventoryCountLine"]] = relationship(
        back_populates="count", cascade="all, delete-orphan"
    )

    @property
    def positive_adjustment_document_number(self) -> str | None:
        return (
            self.positive_adjustment_document.number
            if self.positive_adjustment_document
            else None
        )

    @property
    def negative_adjustment_document_number(self) -> str | None:
        return (
            self.negative_adjustment_document.number
            if self.negative_adjustment_document
            else None
        )


class InventoryCountLine(Base):
    __tablename__ = "inventory_count_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    count_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_counts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    product_isbn_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_codigo_interno_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    physical_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    difference_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    count: Mapped["InventoryCount"] = relationship(back_populates="lines")

    @property
    def product_name(self) -> str:
        return self.product_name_snapshot

    @property
    def product_isbn(self) -> str | None:
        return self.product_isbn_snapshot

    @property
    def product_codigo_interno(self) -> str | None:
        return self.product_codigo_interno_snapshot


class InventoryDocumentAttachment(Base):
    __tablename__ = "inventory_document_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["InventoryDocument"] = relationship(back_populates="attachments")


class InventoryDocumentLine(Base):
    __tablename__ = "inventory_document_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=0
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=0
    )
    unit_price_base: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    discount_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    discount_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_lots.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["InventoryDocument"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship(back_populates="document_lines")  # type: ignore[name-defined]

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def product_isbn(self) -> str | None:
        return self.product.isbn if self.product else None


class AuthorizationCode(Base):
    __tablename__ = "authorization_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["InventoryDocument"] = relationship(
        back_populates="authorization_codes"
    )
