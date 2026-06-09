from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AttributeDataType


class CategoryAttributeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    data_type: AttributeDataType
    is_required: bool = False
    select_options: list[str] | None = None
    catalog_id: int | None = None
    allow_negative: bool = False

    @model_validator(mode="after")
    def validate_type_requirements(self):
        if self.data_type == AttributeDataType.select:
            if not self.select_options or len(self.select_options) == 0:
                raise ValueError("SELECT_REQUIRES_OPTIONS: select type must have at least one option")
        # catalog_id is optional: if absent, the service auto-creates/reuses a
        # catalog named after the attribute (plural).
        return self


class CategoryAttributeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    data_type: AttributeDataType | None = None
    is_required: bool | None = None
    select_options: list[str] | None = None
    catalog_id: int | None = None
    allow_negative: bool | None = None


class CategoryAttributeResponse(BaseModel):
    id: int
    category_id: int
    name: str
    data_type: AttributeDataType
    is_required: bool
    select_options: list[str] | None
    catalog_id: int | None = None
    allow_negative: bool = False
    is_active: bool = True
    inherited: bool = False
    # How many product values were queued for manual re-map by the last type change.
    remap_pending: int = 0

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    parent_id: int | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    parent_id: int | None = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: str | None
    parent_id: int | None
    is_active: bool
    is_default: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryCreateResponse(CategoryResponse):
    # How many products were moved to an auto-created "Sin clasificar" bucket
    # because this category turned its parent into a non-leaf.
    products_moved: int = 0
