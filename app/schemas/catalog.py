from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CatalogCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class CatalogUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class CatalogValueResponse(BaseModel):
    id: int
    catalog_id: int
    value: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CatalogResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    value_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CatalogValueCreate(BaseModel):
    value: str = Field(..., min_length=1, max_length=150)


class CatalogValueUpdate(BaseModel):
    value: str = Field(..., min_length=1, max_length=150)
