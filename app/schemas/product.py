from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ProductStatus

_ALLOWED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/heic",
    "image/heif",
}


def _normalize_photo(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_valid_image_data_url(value: str) -> bool:
    if not value.startswith("data:"):
        return False
    prefix, _, _ = value.partition(",")
    if ";base64" not in prefix:
        return False
    mime = prefix[5:].split(";", 1)[0].lower()
    return mime in _ALLOWED_IMAGE_MIME_TYPES


def _is_valid_image_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class ProductBase(BaseModel):
    isbn: str | None = Field(None, min_length=10, max_length=32)
    codigo_interno: str | None = Field(None, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    photo: str | None = None

    @field_validator("photo", mode="before")
    @classmethod
    def normalize_photo(cls, value: str | None) -> str | None:
        return _normalize_photo(value)

    @field_validator("photo")
    @classmethod
    def validate_photo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _is_valid_image_data_url(value) or _is_valid_image_url(value):
            return value
        raise ValueError(
            "La foto debe ser PNG, JPG, JPEG o HEIC, o una URL directa a una imagen válida"
        )


class ProductCreate(ProductBase):
    name: str = Field(..., min_length=1, max_length=200)
    category_id: int
    stock_minimo: Decimal = Field(default=Decimal("0"), ge=0)
    pvp: Decimal = Field(default=Decimal("0"), ge=0)
    custom_attributes: dict[str, Any] | None = None


class ProductUpdate(ProductBase):
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
    photo: str | None = None
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
