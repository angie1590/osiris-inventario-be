from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.catalog import (
    CatalogCreate, CatalogResponse, CatalogUpdate,
    CatalogValueCreate, CatalogValueResponse, CatalogValueUpdate,
)
from app.services.catalog_service import CatalogService

router = APIRouter()

_write_roles = require_role(UserRole.admin, UserRole.supervisor)
_read_roles = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


def _catalog_response(cat, value_count: int = 0) -> CatalogResponse:
    resp = CatalogResponse.model_validate(cat)
    resp.value_count = value_count
    return resp


@router.get("", response_model=list[CatalogResponse])
async def list_catalogs(db: AsyncSession = Depends(get_db), _: User = Depends(_read_roles)):
    svc = CatalogService(db)
    return [_catalog_response(cat, count) for cat, count in await svc.list_catalogs()]


@router.post("", response_model=CatalogResponse, status_code=status.HTTP_201_CREATED)
async def create_catalog(body: CatalogCreate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(_write_roles)):
    svc = CatalogService(db)
    cat = await svc.create_catalog(body.name, body.description, current_user.id, current_user.username, request)
    return _catalog_response(cat, 0)


@router.patch("/{catalog_id}", response_model=CatalogResponse)
async def update_catalog(catalog_id: int, body: CatalogUpdate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(_write_roles)):
    svc = CatalogService(db)
    cat = await svc.update_catalog(catalog_id, body.name, body.description, current_user.id, current_user.username, request)
    return _catalog_response(cat, len(await svc.active_values(catalog_id)))


@router.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_catalog(catalog_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(_write_roles)):
    svc = CatalogService(db)
    await svc.delete_catalog(catalog_id, current_user.id, current_user.username, request)


@router.get("/{catalog_id}/values", response_model=list[CatalogValueResponse])
async def list_values(catalog_id: int, include_inactive: bool = True, db: AsyncSession = Depends(get_db), _: User = Depends(_read_roles)):
    svc = CatalogService(db)
    return await svc.list_values(catalog_id, include_inactive=include_inactive)


@router.post("/{catalog_id}/values", response_model=CatalogValueResponse, status_code=status.HTTP_201_CREATED)
async def add_value(catalog_id: int, body: CatalogValueCreate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(_write_roles)):
    svc = CatalogService(db)
    return await svc.add_value(catalog_id, body.value, current_user.id, current_user.username, request)


@router.patch("/{catalog_id}/values/{value_id}", response_model=CatalogValueResponse)
async def update_value(catalog_id: int, value_id: int, body: CatalogValueUpdate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(_write_roles)):
    svc = CatalogService(db)
    return await svc.update_value(catalog_id, value_id, body.value, current_user.id, current_user.username, request)


@router.post("/{catalog_id}/values/{value_id}/deactivate", response_model=CatalogValueResponse)
async def deactivate_value(catalog_id: int, value_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(_write_roles)):
    svc = CatalogService(db)
    return await svc.set_value_active(catalog_id, value_id, False, current_user.id, current_user.username, request)


@router.post("/{catalog_id}/values/{value_id}/reactivate", response_model=CatalogValueResponse)
async def reactivate_value(catalog_id: int, value_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(_write_roles)):
    svc = CatalogService(db)
    return await svc.set_value_active(catalog_id, value_id, True, current_user.id, current_user.username, request)
