from typing import Any

from pydantic import BaseModel, Field


class RemapItem(BaseModel):
    id: int
    product_id: int
    product_name: str
    old_value: str | None


class RemapGroup(BaseModel):
    attribute_id: int
    attribute_name: str
    target_type: str
    is_required: bool
    catalog_id: int | None = None
    allowed_values: list[str] | None = None
    items: list[RemapItem]


class RemapPendingResponse(BaseModel):
    total: int
    groups: list[RemapGroup]


class RemapAssignment(BaseModel):
    id: int
    value: Any | None = None


class RemapResolveRequest(BaseModel):
    assignments: list[RemapAssignment] = Field(..., min_length=1)
