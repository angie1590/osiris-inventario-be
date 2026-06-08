from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.category import (
    CategoryAttributeCreate, CategoryAttributeResponse, CategoryAttributeUpdate,
    CategoryCreate, CategoryResponse, CategoryUpdate,
)
from app.services.category_service import CategoryService

router = APIRouter()

_write_roles = require_role(UserRole.admin, UserRole.operator)
_read_roles = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    limit: int = 50,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    svc = CategoryService(db)
    return await svc.list_categories(limit=limit, cursor=cursor)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_write_roles),
):
    svc = CategoryService(db)
    return await svc.create_category(body.name, body.description, body.parent_id, current_user.id, current_user.username, request)


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    from app.core.exceptions import NotFoundError
    from app.repositories.category_repository import CategoryRepository
    repo = CategoryRepository(db)
    cat = await repo.get_by_id(category_id)
    if not cat or not cat.is_active:
        raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found")
    return cat


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    body: CategoryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_write_roles),
):
    svc = CategoryService(db)
    return await svc.update_category(category_id, body.name, body.description, current_user.id, current_user.username, request)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    request: Request,
    delete_products: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    svc = CategoryService(db)
    await svc.delete_category(
        category_id,
        current_user.id,
        current_user.username,
        request,
        delete_products=delete_products,
    )


@router.get("/{category_id}/attributes", response_model=list[CategoryAttributeResponse])
async def get_category_attributes(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    svc = CategoryService(db)
    items = await svc.get_inherited_attributes(category_id)
    return [
        CategoryAttributeResponse(
            id=item["attr"].id,
            category_id=item["attr"].category_id,
            name=item["attr"].name,
            data_type=item["attr"].data_type,
            is_required=item["attr"].is_required,
            select_options=item["attr"].select_options,
            is_active=item["attr"].is_active,
            inherited=item["inherited"],
        )
        for item in items
    ]


@router.post("/{category_id}/attributes", response_model=CategoryAttributeResponse, status_code=status.HTTP_201_CREATED)
async def add_attribute(
    category_id: int,
    body: CategoryAttributeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    svc = CategoryService(db)
    attr = await svc.add_attribute(category_id, body.name, body.data_type, body.is_required, body.select_options, current_user.id, current_user.username, request)
    return CategoryAttributeResponse(
        id=attr.id, category_id=attr.category_id, name=attr.name,
        data_type=attr.data_type, is_required=attr.is_required,
        select_options=attr.select_options, is_active=attr.is_active, inherited=False,
    )


@router.patch("/{category_id}/attributes/{attr_id}", response_model=CategoryAttributeResponse)
async def update_attribute(
    category_id: int,
    attr_id: int,
    body: CategoryAttributeUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    svc = CategoryService(db)
    attr = await svc.update_attribute(category_id, attr_id, body.name, body.data_type, body.is_required, body.select_options, current_user.id, current_user.username, request)
    return CategoryAttributeResponse(
        id=attr.id, category_id=attr.category_id, name=attr.name,
        data_type=attr.data_type, is_required=attr.is_required,
        select_options=attr.select_options, is_active=attr.is_active, inherited=False,
    )


@router.post("/{category_id}/attributes/{attr_id}/deactivate", response_model=CategoryAttributeResponse)
async def deactivate_attribute(
    category_id: int,
    attr_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    svc = CategoryService(db)
    attr = await svc.deactivate_attribute(category_id, attr_id, current_user.id, current_user.username, request)
    return CategoryAttributeResponse(
        id=attr.id, category_id=attr.category_id, name=attr.name,
        data_type=attr.data_type, is_required=attr.is_required,
        select_options=attr.select_options, is_active=attr.is_active, inherited=False,
    )


@router.post("/{category_id}/attributes/{attr_id}/reactivate", response_model=CategoryAttributeResponse)
async def reactivate_attribute(
    category_id: int,
    attr_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    svc = CategoryService(db)
    attr = await svc.reactivate_attribute(category_id, attr_id, current_user.id, current_user.username, request)
    return CategoryAttributeResponse(
        id=attr.id, category_id=attr.category_id, name=attr.name,
        data_type=attr.data_type, is_required=attr.is_required,
        select_options=attr.select_options, is_active=attr.is_active, inherited=False,
    )


@router.delete("/{category_id}/attributes/{attr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attribute(
    category_id: int,
    attr_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    svc = CategoryService(db)
    await svc.delete_attribute(category_id, attr_id, current_user.id, current_user.username, request)
