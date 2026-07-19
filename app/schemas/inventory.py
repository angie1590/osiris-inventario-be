from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import AdjustType, DocumentStatus, DocumentType


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


class IngresoCreate(BaseModel):
    ingreso_type: Literal["purchase", "initial_inventory"] = "purchase"
    supplier_id: int | None = None
    purchase_document_type: Literal[
        "invoice", "sales_note", "receipt", "none"
    ] = "invoice"
    purchase_document_number: str | None = Field(None, max_length=100)
    purchase_document_date: datetime | None = None
    reference: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=2000)
    lines: list[DocumentLineCreate] = Field(..., min_length=1)


class EgresoCreate(BaseModel):
    reference: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=2000)
    lines: list[DocumentLineCreate] = Field(..., min_length=1)


class BajaCreate(BaseModel):
    reference: str = Field(..., min_length=1, max_length=200)
    notes: str | None = None
    lines: list[DocumentLineCreate] = Field(..., min_length=1)


class AjusteCreate(BaseModel):
    adjust_type: AdjustType
    reference: str | None = Field(None, max_length=200)
    notes: str | None = None
    lines: list[DocumentLineCreate] = Field(..., min_length=1)


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
    supplier_id: int | None
    purchase_document_type: str | None
    purchase_document_number: str | None
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
