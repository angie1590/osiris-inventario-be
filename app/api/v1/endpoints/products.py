from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_stock_mode, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.product import ProductCreate, ProductResponse, ProductStatusUpdate, ProductUpdate
from app.services.product_service import ProductService

router = APIRouter()

_write_roles = require_role(UserRole.admin, UserRole.operator)
_read_roles = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


def _to_response(p) -> dict:
    return {
        **{c: getattr(p, c) for c in ["id", "name", "description", "category_id", "stock_minimo", "stock_actual", "pvp", "status", "custom_attributes", "created_at", "updated_at"]},
        "bajo_stock": p.stock_actual <= p.stock_minimo,
    }


@router.get("", response_model=list[ProductResponse])
async def list_products(
    limit: int = 50,
    cursor: int | None = None,
    name: str | None = None,
    category_id: int | None = None,
    bajo_stock: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    svc = ProductService(db)
    products = await svc.list_products(limit=limit, cursor=cursor, name=name, category_id=category_id, bajo_stock=bajo_stock)
    return [_to_response(p) for p in products]


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_write_roles),
    stock_mode: str = Depends(get_stock_mode),
):
    svc = ProductService(db)
    p = await svc.create_product(body.name, body.description, body.category_id, body.stock_minimo, body.pvp, body.custom_attributes, current_user.id, current_user.username, request, stock_mode=stock_mode)
    return _to_response(p)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    svc = ProductService(db)
    p = await svc.get_product(product_id)
    return _to_response(p)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    body: ProductUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_write_roles),
    stock_mode: str = Depends(get_stock_mode),
):
    svc = ProductService(db)
    p = await svc.update_product(product_id, body.name, body.description, body.stock_minimo, body.pvp, body.custom_attributes, current_user.id, current_user.username, request, stock_mode=stock_mode)
    return _to_response(p)


@router.patch("/{product_id}/status", response_model=ProductResponse)
async def update_product_status(
    product_id: int,
    body: ProductStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_write_roles),
):
    svc = ProductService(db)
    p = await svc.update_status(product_id, body.status, current_user.id, current_user.username, request)
    return _to_response(p)
