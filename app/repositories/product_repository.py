from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, text
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
    ) -> list[Product]:
        q = select(Product).order_by(Product.id)
        if cursor:
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
