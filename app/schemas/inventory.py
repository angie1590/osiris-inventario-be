from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AdjustType, DocumentStatus, DocumentType


class DocumentLineCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)


class IngresoCreate(BaseModel):
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
    authorization_code: str = Field(..., min_length=4, max_length=4)


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


class DocumentResponse(BaseModel):
    id: int
    number: str
    doc_type: DocumentType
    status: DocumentStatus
    reference: str | None
    notes: str | None
    adjust_type: AdjustType | None
    created_by: int
    authorized_by: int | None
    requested_at: datetime
    authorized_at: datetime | None
    created_at: datetime
    lines: list[DocumentLineResponse] = []

    model_config = ConfigDict(from_attributes=True)
