from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.enums import AuditAction, AttributeDataType, ProductStatus
from app.models.product import Product
from app.repositories.category_repository import CategoryRepository
from app.repositories.product_repository import ProductRepository
from app.services.audit_service import AuditService
from app.services.category_service import _validate_attribute_value


def _validate_stock_quantity(value: Decimal, mode: str, field_name: str = "stock_min") -> None:
    """Raise ValidationAppError if decimal value is provided in integer mode."""
    if mode == "integer" and value != value.to_integral_value():
        raise ValidationAppError(
            "INVALID_QUANTITY",
            f"El {field_name} debe ser un número entero.",
            field_errors={field_name: f"El {field_name} debe ser un número entero."},
        )


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ProductRepository(db)
        self.cat_repo = CategoryRepository(db)
        self.audit = AuditService(db)

    async def _validate_custom_attributes(self, category_id: int, custom_attributes: dict[str, Any] | None) -> None:
        inherited = await self.cat_repo.get_inherited_attributes(category_id)
        provided = custom_attributes or {}

        for item in inherited:
            attr = item["attr"]
            if attr.is_required and attr.name not in provided:
                raise ValidationAppError(
                    "MISSING_REQUIRED_ATTRIBUTE",
                    f"Required attribute '{attr.name}' is missing",
                )
            if attr.name in provided:
                value = provided[attr.name]
                if not _validate_attribute_value(value, attr.data_type, attr.select_options):
                    raise ValidationAppError(
                        "INVALID_ATTRIBUTE_VALUE",
                        f"Invalid value for attribute '{attr.name}' (type: {attr.data_type.value})",
                    )

    async def list_products(self, limit: int = 100, cursor: int | None = None, name: str | None = None, category_id: int | None = None, status: ProductStatus | None = None, bajo_stock: bool | None = None) -> list[Product]:
        category_ids = None
        if category_id:
            category_ids = await self.cat_repo.get_descendant_category_ids(category_id)

        products = await self.repo.list(limit=limit, cursor=cursor, name=name, category_ids=category_ids, status=status, bajo_stock=bajo_stock)
        return products

    async def create_product(self, name: str, description: str | None, category_id: int, stock_minimo: Decimal, pvp: Decimal, custom_attributes: dict | None, actor_id: int, actor_name: str, request=None, stock_mode: str = "integer") -> Product:
        cat = await self.cat_repo.get_by_id(category_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found or inactive")

        _validate_stock_quantity(stock_minimo, stock_mode, "stock_minimo")
        await self._validate_custom_attributes(category_id, custom_attributes)

        product = Product(
            name=name, description=description, category_id=category_id,
            stock_minimo=stock_minimo, stock_actual=Decimal("0"),
            pvp=pvp, status=ProductStatus.active,
            custom_attributes=custom_attributes,
        )
        p = await self.repo.create(product)

        await self.audit.log(
            AuditAction.CREATE, user_id=actor_id, username=actor_name,
            entity_type="product", entity_id=p.id,
            new={"name": name, "category_id": category_id, "pvp": float(pvp)},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(p)
        return p

    async def get_product(self, product_id: int) -> Product:
        p = await self.repo.get_by_id(product_id)
        if not p:
            raise NotFoundError("PRODUCT_NOT_FOUND", "Product not found")
        return p

    async def update_product(self, product_id: int, name: str | None, description: str | None, stock_minimo: Decimal | None, pvp: Decimal | None, custom_attributes: dict | None, actor_id: int, actor_name: str, request=None, stock_mode: str = "integer") -> Product:
        p = await self.repo.get_by_id(product_id)
        if not p:
            raise NotFoundError("PRODUCT_NOT_FOUND", "Product not found")

        if stock_minimo is not None:
            _validate_stock_quantity(stock_minimo, stock_mode, "stock_minimo")
        if custom_attributes is not None:
            await self._validate_custom_attributes(p.category_id, custom_attributes)

        previous = {"name": p.name, "pvp": float(p.pvp), "stock_minimo": float(p.stock_minimo)}
        if name is not None:
            p.name = name
        if description is not None:
            p.description = description
        if stock_minimo is not None:
            p.stock_minimo = stock_minimo
        if pvp is not None:
            p.pvp = pvp
        if custom_attributes is not None:
            p.custom_attributes = custom_attributes

        await self.audit.log(
            AuditAction.UPDATE, user_id=actor_id, username=actor_name,
            entity_type="product", entity_id=p.id,
            previous=previous, new={"name": p.name, "pvp": float(p.pvp)},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(p)
        return p

    async def update_status(self, product_id: int, status: ProductStatus, actor_id: int, actor_name: str, request=None) -> Product:
        p = await self.repo.get_by_id(product_id)
        if not p:
            raise NotFoundError("PRODUCT_NOT_FOUND", "Product not found")

        previous = {"status": p.status.value}
        p.status = status

        await self.audit.log(
            AuditAction.UPDATE, user_id=actor_id, username=actor_name,
            entity_type="product", entity_id=p.id,
            previous=previous, new={"status": status.value},
            description=f"Product status changed to {status.value}",
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(p)
        return p
