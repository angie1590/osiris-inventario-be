from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_isbn_required, get_stock_mode, require_role
from app.models.enums import ProductStatus, UserRole
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductStatusUpdate,
    ProductUpdate,
    RecategorizeRequest,
)
from app.services.product_service import ProductService

router = APIRouter()

_write_roles = require_role(UserRole.admin, UserRole.operator)
_read_roles = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


def _to_response(p) -> dict:
    return {
        **{
            c: getattr(p, c)
            for c in [
                "id",
                "isbn",
                "codigo_interno",
                "name",
                "description",
                "category_id",
                "stock_minimo",
                "stock_actual",
                "pvp",
                "status",
                "custom_attributes",
                "created_at",
                "updated_at",
            ]
        },
        "bajo_stock": p.stock_minimo > 0 and p.stock_actual <= p.stock_minimo,
    }


@router.get("", response_model=list[ProductResponse])
async def list_products(
    limit: int = 50,
    cursor: int | None = None,
    name: str | None = None,
    category_id: int | None = None,
    status: ProductStatus | None = None,
    bajo_stock: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    svc = ProductService(db)
    products = await svc.list_products(
        limit=limit,
        cursor=cursor,
        name=name,
        category_id=category_id,
        status=status,
        bajo_stock=bajo_stock,
    )
    return [_to_response(p) for p in products]


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_write_roles),
    stock_mode: str = Depends(get_stock_mode),
    isbn_required: bool = Depends(get_isbn_required),
):
    if isbn_required and not (body.isbn and body.isbn.strip()):
        from app.core.exceptions import ValidationAppError
        raise ValidationAppError("ISBN_REQUIRED", "El código de barras es obligatorio.")
    svc = ProductService(db)
    p = await svc.create_product(
        body.isbn,
        body.name,
        body.description,
        body.category_id,
        body.stock_minimo,
        body.pvp,
        body.custom_attributes,
        current_user.id,
        current_user.username,
        request,
        stock_mode=stock_mode,
        codigo_interno=body.codigo_interno,
    )
    return _to_response(p)


@router.get("/pending-recategorization", response_model=list[ProductResponse])
async def list_pending_recategorization(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    svc = ProductService(db)
    return [_to_response(p) for p in await svc.list_pending_recategorization()]


@router.post("/recategorize", response_model=dict)
async def recategorize_products(
    body: RecategorizeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_write_roles),
):
    svc = ProductService(db)
    count = await svc.recategorize(body.assignments, current_user.id, current_user.username, request)
    return {"recategorized": count}


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
    p = await svc.update_product(
        product_id,
        body.isbn,
        body.name,
        body.description,
        body.stock_minimo,
        body.pvp,
        body.custom_attributes,
        current_user.id,
        current_user.username,
        request,
        stock_mode=stock_mode,
        category_id=body.category_id,
        category_provided="category_id" in body.model_fields_set,
        codigo_interno=body.codigo_interno,
        codigo_interno_provided="codigo_interno" in body.model_fields_set,
    )
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
    p = await svc.update_status(
        product_id, body.status, current_user.id, current_user.username, request,
        category_id=body.category_id,
    )
    return _to_response(p)
