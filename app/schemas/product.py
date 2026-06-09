from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ProductStatus


class ProductCreate(BaseModel):
    isbn: str | None = Field(None, min_length=10, max_length=32)
    codigo_interno: str | None = Field(None, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    category_id: int
    stock_minimo: Decimal = Field(default=Decimal("0"), ge=0)
    pvp: Decimal = Field(default=Decimal("0"), ge=0)
    custom_attributes: dict[str, Any] | None = None


class ProductUpdate(BaseModel):
    isbn: str | None = Field(None, min_length=10, max_length=32)
    codigo_interno: str | None = Field(None, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    category_id: int | None = None
    stock_minimo: Decimal | None = Field(None, ge=0)
    pvp: Decimal | None = Field(None, ge=0)
    custom_attributes: dict[str, Any] | None = None


class ProductStatusUpdate(BaseModel):
    status: ProductStatus
    # Optional: when reactivating a product whose category was deleted, a new
    # active category must be supplied to avoid dangling references.
    category_id: int | None = None


class RecategorizeAssignment(BaseModel):
    product_id: int
    category_id: int


class RecategorizeRequest(BaseModel):
    assignments: list[RecategorizeAssignment] = Field(..., min_length=1)


class ProductResponse(BaseModel):
    id: int
    isbn: str
    codigo_interno: str | None = None
    name: str
    description: str | None
    category_id: int
    stock_minimo: Decimal
    stock_actual: Decimal
    pvp: Decimal
    status: ProductStatus
    custom_attributes: dict[str, Any] | None
    bajo_stock: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
