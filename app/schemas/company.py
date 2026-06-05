from datetime import datetime

from pydantic import BaseModel, field_validator

_LOGO_MAX_CHARS = 2_097_152


class CompanyConfigCreate(BaseModel):
    razon_social: str
    ruc: str
    email: str
    nombre_comercial: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    logo: str | None = None

    @field_validator("logo")
    @classmethod
    def logo_size(cls, v: str | None) -> str | None:
        if v is not None and len(v) > _LOGO_MAX_CHARS:
            raise ValueError("logo must not exceed 2 MB")
        return v


class CompanyConfigUpdate(BaseModel):
    razon_social: str | None = None
    ruc: str | None = None
    email: str | None = None
    nombre_comercial: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    logo: str | None = None

    @field_validator("logo")
    @classmethod
    def logo_size(cls, v: str | None) -> str | None:
        if v is not None and len(v) > _LOGO_MAX_CHARS:
            raise ValueError("logo must not exceed 2 MB")
        return v


class CompanyConfigResponse(BaseModel):
    id: int
    razon_social: str
    nombre_comercial: str | None
    ruc: str
    direccion: str | None
    telefono: str | None
    email: str
    logo: str | None
    is_complete: bool
    created_at: datetime
    updated_at: datetime
    updated_by: int | None

    model_config = {"from_attributes": True}
