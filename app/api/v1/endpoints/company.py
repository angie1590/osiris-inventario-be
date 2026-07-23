from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_any_role
from app.core.exceptions import NotFoundError
from app.models.company_config import CompanyConfig
from app.models.user import User
from app.schemas.company import (
    CompanyConfigCreate,
    CompanyConfigResponse,
    CompanyConfigUpdate,
    DEFAULT_EGRESO_TYPES,
    DEFAULT_BAJA_REASONS,
    DEFAULT_INGRESO_TYPES,
)
from app.services.company_service import CompanyService, _is_complete

router = APIRouter()


def _normalize_egreso_types(types: list[str] | None) -> list[str]:
    legacy_baja_types = {
        "damage_disposal",
        "expiration_disposal",
        "loss_theft_disposal",
        "donation",
    }
    values: list[str] = []
    for item in types or []:
        normalized = "baja" if item in legacy_baja_types else item
        if normalized not in values:
            values.append(normalized)
    return values or DEFAULT_EGRESO_TYPES


def _to_response(company: CompanyConfig) -> CompanyConfigResponse:
    enabled_ingreso_types = company.enabled_ingreso_types or DEFAULT_INGRESO_TYPES
    enabled_egreso_types = _normalize_egreso_types(company.enabled_egreso_types)
    enabled_baja_reasons = company.enabled_baja_reasons or DEFAULT_BAJA_REASONS
    sellers = company.sellers or []
    return CompanyConfigResponse(
        id=company.id,
        razon_social=company.razon_social,
        nombre_comercial=company.nombre_comercial,
        ruc=company.ruc,
        direccion=company.direccion,
        telefono=company.telefono,
        email=company.email,
        logo=company.logo,
        enabled_ingreso_types=enabled_ingreso_types,
        enabled_egreso_types=enabled_egreso_types,
        enabled_baja_reasons=enabled_baja_reasons,
        sellers=sellers,
        is_complete=_is_complete(company),
        created_at=company.created_at,
        updated_at=company.updated_at,
        updated_by=company.updated_by,
    )


@router.get("", response_model=CompanyConfigResponse)
async def get_company(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_any_role),
):
    svc = CompanyService(db)
    company = await svc.get_or_none()
    if not company:
        raise NotFoundError("COMPANY_NOT_FOUND", "Company configuration not found")
    return _to_response(company)


@router.post("", response_model=CompanyConfigResponse, status_code=201)
async def create_company(
    body: CompanyConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    svc = CompanyService(db)
    company = await svc.create(body, current_user, request)
    return _to_response(company)


@router.patch("", response_model=CompanyConfigResponse)
async def update_company(
    body: CompanyConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    svc = CompanyService(db)
    company = await svc.update(body, current_user, request)
    return _to_response(company)
