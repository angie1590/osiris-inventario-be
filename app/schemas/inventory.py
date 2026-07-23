from datetime import datetime
from decimal import Decimal
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import AdjustType, DocumentStatus, DocumentType

PurchaseDocumentType = Literal[
    "invoice",
    "sales_note",
    "liquidation_purchase",
    "receipt",
    "other",
    "inventory_act",
    "adjustment_act",
    "credit_note",
    "production_act",
    "transfer_note",
    "delivery_note",
    "disposal_act",
    "donation_act",
    "internal_consumption_act",
    "supplier_return",
    "transfer_act",
    "none",
]

EgresoType = Literal[
    "sale",
    "baja",
    "adjustment_negative",
    "supplier_return",
    "internal_consumption",
    "transfer_sent",
    "other",
]

BajaReason = Literal[
    "damage",
    "expiration",
    "loss",
    "theft",
    "donation",
    "gift",
    "destruction",
    "sample",
    "other",
]

AdjustmentReason = Literal[
    "physical_count",
    "record_error",
    "administrative_correction",
    "other",
]

DiscountType = Literal["percent", "fixed"]
CountStatus = Literal["draft", "applied", "cancelled"]
AdjustmentIncrementCostMode = Literal["auto", "suggested", "required_manual"]


def _is_valid_ecuador_ruc(value: str) -> bool:
    if len(value) != 13 or not value.isdigit():
        return False

    province = int(value[:2])
    if province < 1 or province > 24:
        return False

    third = int(value[2])

    if third < 6:
        coefs = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        total = 0
        for i, coef in enumerate(coefs):
            p = int(value[i]) * coef
            if p >= 10:
                p -= 9
            total += p
        check = (10 - (total % 10)) % 10
        if check != int(value[9]):
            return False
        return value[10:] != "000"

    if third == 6:
        coefs = [3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(int(value[i]) * coefs[i] for i in range(8))
        check = 11 - (total % 11)
        if check == 11:
            check = 0
        if check == 10 or check != int(value[8]):
            return False
        return value[9:] != "0000"

    if third == 9:
        coefs = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(int(value[i]) * coefs[i] for i in range(9))
        check = 11 - (total % 11)
        if check == 11:
            check = 0
        if check == 10 or check != int(value[9]):
            return False
        return value[10:] != "000"

    return False


def _is_valid_ecuador_cedula(value: str) -> bool:
    if len(value) != 10 or not value.isdigit():
        return False

    province = int(value[:2])
    if province < 1 or province > 24:
        return False

    third = int(value[2])
    if third >= 6:
        return False

    coefs = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for i, coef in enumerate(coefs):
        p = int(value[i]) * coef
        if p >= 10:
            p -= 9
        total += p

    check = (10 - (total % 10)) % 10
    return check == int(value[9])


class DocumentLineCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    unit_price_base: Decimal | None = Field(default=None, ge=0)
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(default=None, ge=0)


class IngresoCreate(BaseModel):
    ingreso_type: Literal[
        "purchase",
        "initial_inventory",
        "adjustment_positive",
        "customer_return",
        "production",
        "transfer_received",
        "other",
    ] = "purchase"
    supplier_id: int | None = None
    purchase_document_type: PurchaseDocumentType = "invoice"
    purchase_document_number: str | None = Field(None, max_length=100)
    purchase_document_date: datetime | None = None
    reference: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=2000)
    lines: list[DocumentLineCreate] = Field(..., min_length=1)

    @field_validator("purchase_document_date", mode="before")
    @classmethod
    def _normalize_purchase_document_date(cls, value):
        if value is None or isinstance(value, datetime):
            return value

        raw = str(value).strip()
        if not raw:
            return None

        # Accept browser-localized values such as: "19/07/2026, 10:46 a.m."
        m = re.match(
            r"^(\d{2})/(\d{2})/(\d{4}),?\s+(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?$",
            raw,
            flags=re.IGNORECASE,
        )
        if not m:
            return value

        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))
        ampm = m.group(6).lower()

        if ampm == "p" and hour < 12:
            hour += 12
        if ampm == "a" and hour == 12:
            hour = 0

        return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"


class EgresoCreate(BaseModel):
    egreso_type: EgresoType = "sale"
    purchase_document_type: PurchaseDocumentType = "sales_note"
    purchase_document_number: str | None = Field(None, max_length=100)
    seller_name: str | None = Field(None, max_length=200)
    purchase_document_date: datetime | None = None
    baja_reason: BajaReason | None = None
    adjustment_reason: AdjustmentReason | None = None
    reference: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=2000)
    lines: list[DocumentLineCreate] = Field(..., min_length=1)

    @field_validator("seller_name", mode="before")
    @classmethod
    def _normalize_seller_name(cls, value):
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    @field_validator("purchase_document_date", mode="before")
    @classmethod
    def _normalize_purchase_document_date(cls, value):
        if value is None or isinstance(value, datetime):
            return value

        raw = str(value).strip()
        if not raw:
            return None

        m = re.match(
            r"^(\d{2})/(\d{2})/(\d{4}),?\s+(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?$",
            raw,
            flags=re.IGNORECASE,
        )
        if not m:
            return value

        day = int(m.group(1))
        month = int(m.group(2))
        year = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))
        ampm = m.group(6).lower()

        if ampm == "p" and hour < 12:
            hour += 12
        if ampm == "a" and hour == 12:
            hour = 0

        return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"

    @model_validator(mode="after")
    def _validate_baja_reason(self):
        if self.egreso_type == "baja" and not self.baja_reason:
            raise ValueError("Motivo de la baja es obligatorio")
        if self.egreso_type == "adjustment_negative" and not self.adjustment_reason:
            raise ValueError("Motivo del ajuste es obligatorio")
        if self.egreso_type != "baja":
            self.baja_reason = None
        if self.egreso_type != "adjustment_negative":
            self.adjustment_reason = None
        return self


class BajaCreate(BaseModel):
    reference: str = Field(..., min_length=1, max_length=200)
    notes: str | None = None
    lines: list[DocumentLineCreate] = Field(..., min_length=1)


class AjusteCreate(BaseModel):
    adjust_type: AdjustType
    reference: str | None = Field(None, max_length=200)
    notes: str | None = None
    lines: list[DocumentLineCreate] = Field(..., min_length=1)


class CountLineCreate(BaseModel):
    product_id: int
    physical_quantity: Decimal = Field(..., gt=0)


class InventoryCountCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    lines: list[CountLineCreate] = Field(..., min_length=1)


class InventoryCountUpdate(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    lines: list[CountLineCreate] = Field(..., min_length=1)


class CountApplyLineCost(BaseModel):
    product_id: int
    unit_cost: Decimal = Field(..., gt=0)


class InventoryCountApply(BaseModel):
    line_costs: list[CountApplyLineCost] = Field(default_factory=list)


class AdjustmentIncrementCostPreview(BaseModel):
    product_id: int
    mode: AdjustmentIncrementCostMode
    unit_cost: Decimal | None = None


class AuthCodeRequest(BaseModel):
    pass


class ApproveRequest(BaseModel):
    authorization_code: str = Field(..., min_length=8, max_length=8)


class VoidRequest(BaseModel):
    # Required only when an operator voids; admin/supervisor void without a PIN.
    authorizer_pin: str | None = None


class DocumentLineResponse(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    product_isbn: str | None = None
    quantity: Decimal
    unit_cost: Decimal
    unit_price: Decimal
    unit_price_base: Decimal | None = None
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = None
    lot_id: int | None

    model_config = ConfigDict(from_attributes=True)


class SupplierCreate(BaseModel):
    identification_type: Literal["ruc", "cedula", "passport"] = "ruc"
    identification_number: str = Field(..., min_length=1, max_length=20)
    trade_name: str = Field(..., min_length=1, max_length=200)
    legal_name: str = Field(..., min_length=1, max_length=200)
    address: str | None = Field(None, max_length=300)
    phone: str | None = Field(None, min_length=7, max_length=15, pattern=r"^\d*$")

    @field_validator("identification_number", mode="before")
    @classmethod
    def _normalize_identification_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().upper()

    @field_validator("identification_type", mode="before")
    @classmethod
    def _normalize_identification_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().lower()

    @field_validator("identification_number")
    @classmethod
    def _validate_identification_number(cls, value: str, info) -> str:
        doc_type = info.data.get("identification_type")
        if doc_type == "ruc":
            if not _is_valid_ecuador_ruc(value):
                raise ValueError("RUC inválido")
        elif doc_type == "cedula":
            if not _is_valid_ecuador_cedula(value):
                raise ValueError("Cédula inválida")
        return value

    @field_validator("trade_name", "legal_name", "address", mode="before")
    @classmethod
    def _uppercase_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().upper()

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().upper()


class SupplierUpdate(BaseModel):
    identification_type: Literal["ruc", "cedula", "passport"] | None = None
    identification_number: str | None = Field(None, min_length=1, max_length=20)
    trade_name: str | None = Field(None, min_length=1, max_length=200)
    legal_name: str | None = Field(None, min_length=1, max_length=200)
    address: str | None = Field(None, max_length=300)
    phone: str | None = Field(None, min_length=7, max_length=15, pattern=r"^\d*$")
    is_active: bool | None = None

    @field_validator("identification_number", mode="before")
    @classmethod
    def _normalize_identification_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().upper()

    @field_validator("identification_type", mode="before")
    @classmethod
    def _normalize_identification_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().lower()

    @field_validator("identification_number")
    @classmethod
    def _validate_identification_number(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        doc_type = info.data.get("identification_type")
        if doc_type == "ruc":
            if not _is_valid_ecuador_ruc(value):
                raise ValueError("RUC inválido")
        elif doc_type == "cedula":
            if not _is_valid_ecuador_cedula(value):
                raise ValueError("Cédula inválida")
        return value

    @field_validator("trade_name", "legal_name", "address", mode="before")
    @classmethod
    def _uppercase_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().upper()

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().upper()


class SupplierResponse(BaseModel):
    id: int
    identification_type: Literal["ruc", "cedula", "passport"]
    identification_number: str
    trade_name: str
    legal_name: str
    address: str | None
    phone: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class DocumentAttachmentResponse(BaseModel):
    id: int
    original_name: str
    mime_type: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: int
    number: str
    doc_type: DocumentType
    status: DocumentStatus
    ingreso_type: str | None
    egreso_type: str | None = None
    baja_reason: str | None = None
    adjustment_reason: str | None = None
    supplier_id: int | None
    purchase_document_type: PurchaseDocumentType | None
    purchase_document_number: str | None
    seller_name: str | None
    purchase_document_date: datetime | None
    reference: str | None
    notes: str | None
    adjust_type: AdjustType | None
    created_by: int
    authorized_by: int | None
    requested_at: datetime
    authorized_at: datetime | None
    created_at: datetime
    supplier: SupplierResponse | None = None
    attachments: list[DocumentAttachmentResponse] = []
    lines: list[DocumentLineResponse] = []

    model_config = ConfigDict(from_attributes=True)


class InventoryCountLineResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    product_isbn: str | None = None
    product_codigo_interno: str | None = None
    system_quantity: Decimal
    physical_quantity: Decimal
    difference_quantity: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryCountResponse(BaseModel):
    id: int
    number: str
    status: CountStatus
    description: str
    created_by: int
    positive_adjustment_document_id: int | None = None
    negative_adjustment_document_id: int | None = None
    positive_adjustment_document_number: str | None = None
    negative_adjustment_document_number: str | None = None
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[InventoryCountLineResponse]

    model_config = ConfigDict(from_attributes=True)
