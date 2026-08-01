from __future__ import annotations

from decimal import Decimal

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProductStatus
from app.models.product import Product


class ProductRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, product_id: int) -> Product | None:
        result = await self.db.execute(select(Product).where(Product.id == product_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        limit: int = 100,
        cursor: int | None = None,
        name: str | None = None,
        category_ids: list[int] | None = None,
        status: ProductStatus | None = None,
        bajo_stock: bool | None = None,
        stock_desc: bool = False,
    ) -> list[Product]:
        q = select(Product)
        if stock_desc:
            q = q.order_by(Product.stock_actual.desc(), Product.id)
            if cursor:
                anchor = await self.db.get(Product, cursor)
                if anchor:
                    q = q.where(
                        or_(
                            Product.stock_actual < anchor.stock_actual,
                            and_(
                                Product.stock_actual == anchor.stock_actual,
                                Product.id > cursor,
                            ),
                        )
                    )
        else:
            q = q.order_by(Product.id)
        if cursor and not stock_desc:
            q = q.where(Product.id > cursor)
        if name:
            term = f"%{name}%"
            q = q.where(
                Product.name.ilike(term)
                | Product.isbn.ilike(term)
                | Product.codigo_interno.ilike(term)
            )
        if category_ids:
            q = q.where(Product.category_id.in_(category_ids))
        if status:
            q = q.where(Product.status == status)
        if bajo_stock is True:
            q = q.where((Product.stock_minimo > 0) & (Product.stock_actual <= Product.stock_minimo))
        q = q.limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def list_page(
        self,
        page: int,
        page_size: int,
        name: str | None = None,
        category_ids: list[int] | None = None,
        status: ProductStatus | None = None,
        bajo_stock: bool | None = None,
        stock_desc: bool = False,
    ) -> tuple[list[Product], int]:
        filters = []
        if name:
            term = f"%{name}%"
            filters.append(
                Product.name.ilike(term)
                | Product.isbn.ilike(term)
                | Product.codigo_interno.ilike(term)
            )
        if category_ids:
            filters.append(Product.category_id.in_(category_ids))
        if status:
            filters.append(Product.status == status)
        if bajo_stock is True:
            filters.append(
                (Product.stock_minimo > 0)
                & (Product.stock_actual <= Product.stock_minimo)
            )

        order = (
            (Product.stock_actual.desc(), Product.id)
            if stock_desc
            else (Product.id,)
        )
        result = await self.db.execute(
            select(Product)
            .where(*filters)
            .order_by(*order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        total = await self.db.scalar(
            select(func.count(Product.id)).where(*filters)
        )
        return list(result.scalars().all()), int(total or 0)

    async def create(self, product: Product) -> Product:
        self.db.add(product)
        await self.db.flush()
        await self.db.refresh(product)
        return product

    async def update_stock(self, product_id: int, delta: Decimal) -> None:
        """Use the PostgreSQL function to update stock safely."""
        await self.db.execute(
            text("SELECT update_product_stock(:product_id, :delta)"),
            {"product_id": product_id, "delta": float(delta)},
        )
