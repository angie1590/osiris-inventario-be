from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AttributeDataType


class CategoryAttributeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    data_type: AttributeDataType
    is_required: bool = False
    select_options: list[str] | None = None

    @model_validator(mode="after")
    def validate_select_options(self):
        if self.data_type == AttributeDataType.select:
            if not self.select_options or len(self.select_options) == 0:
                raise ValueError("SELECT_REQUIRES_OPTIONS: select type must have at least one option")
        return self


class CategoryAttributeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    is_required: bool | None = None
    select_options: list[str] | None = None


class CategoryAttributeResponse(BaseModel):
    id: int
    category_id: int
    name: str
    data_type: AttributeDataType
    is_required: bool
    select_options: list[str] | None
    inherited: bool = False

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    parent_id: int | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: str | None
    parent_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
