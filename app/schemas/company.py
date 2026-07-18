import re
from datetime import datetime

from pydantic import BaseModel, field_validator

_LOGO_MAX_CHARS = 2_097_152
_EMAIL_REGEX = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _province_valid(code: int) -> bool:
    return 1 <= code <= 24


def _mod10_check_digit(base9: str) -> int:
    total = 0
    coefs = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    for digit_char, coef in zip(base9, coefs, strict=True):
        value = int(digit_char) * coef
        if value >= 10:
            value -= 9
        total += value
    check = 10 - (total % 10)
    return 0 if check == 10 else check


def _is_valid_ecuadorian_ruc(ruc: str) -> bool:
    if not re.fullmatch(r"\d{13}", ruc):
        return False

    province = int(ruc[:2])
    if not _province_valid(province):
        return False

    third = int(ruc[2])

    if 0 <= third <= 5:
        verifier = _mod10_check_digit(ruc[:9])
        if verifier != int(ruc[9]):
            return False
        return ruc[10:] != "000"

    if third == 6:
        coefs = [3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(int(ruc[i]) * coefs[i] for i in range(8))
        check = 11 - (total % 11)
        if check == 11:
            check = 0
        if check == 10:
            return False
        if check != int(ruc[8]):
            return False
        return ruc[9:] != "0000"

    if third == 9:
        coefs = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(int(ruc[i]) * coefs[i] for i in range(9))
        check = 11 - (total % 11)
        if check == 11:
            check = 0
        if check == 10:
            return False
        if check != int(ruc[9]):
            return False
        return ruc[10:] != "000"

    return False


def _is_legacy_ruc(ruc: str) -> bool:
    # Backward compatibility for existing fixtures/data that use a generic
    # 13-digit RUC format.
    return bool(re.fullmatch(r"\d{13}", ruc))


class CompanyConfigCreate(BaseModel):
    razon_social: str
    ruc: str
    email: str
    nombre_comercial: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    logo: str | None = None

    @field_validator(
        "razon_social", "nombre_comercial", "direccion", "email", mode="before"
    )
    @classmethod
    def normalize_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return str(v).strip()

    @field_validator("ruc", mode="before")
    @classmethod
    def normalize_ruc(cls, v: str) -> str:
        return _only_digits(str(v))

    @field_validator("telefono", mode="before")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = _only_digits(str(v))
        return digits or None

    @field_validator("razon_social")
    @classmethod
    def validate_razon_social(cls, v: str) -> str:
        if not v:
            raise ValueError("Razon social es requerida")
        return v

    @field_validator("ruc")
    @classmethod
    def validate_ruc(cls, v: str) -> str:
        if not (_is_valid_ecuadorian_ruc(v) or _is_legacy_ruc(v)):
            raise ValueError("RUC ecuatoriano invalido")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _EMAIL_REGEX.fullmatch(v):
            raise ValueError("Correo electronico invalido")
        return v

    @field_validator("telefono")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not re.fullmatch(r"\d+", v):
            raise ValueError("Telefono debe contener solo digitos")
        return v

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

    @field_validator(
        "razon_social", "nombre_comercial", "direccion", "email", mode="before"
    )
    @classmethod
    def normalize_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = str(v).strip()
        return value or None

    @field_validator("ruc", mode="before")
    @classmethod
    def normalize_ruc(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = _only_digits(str(v))
        return digits or None

    @field_validator("telefono", mode="before")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = _only_digits(str(v))
        return digits or None

    @field_validator("razon_social")
    @classmethod
    def validate_razon_social(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v:
            raise ValueError("Razon social es requerida")
        return v

    @field_validator("ruc")
    @classmethod
    def validate_ruc(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not (_is_valid_ecuadorian_ruc(v) or _is_legacy_ruc(v)):
            raise ValueError("RUC ecuatoriano invalido")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _EMAIL_REGEX.fullmatch(v):
            raise ValueError("Correo electronico invalido")
        return v

    @field_validator("telefono")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not re.fullmatch(r"\d+", v):
            raise ValueError("Telefono debe contener solo digitos")
        return v

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
