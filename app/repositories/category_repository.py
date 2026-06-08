from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category import Category, CategoryAttribute


class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, category_id: int) -> Category | None:
        result = await self.db.execute(
            select(Category).where(Category.id == category_id).options(selectinload(Category.attributes))
        )
        return result.scalar_one_or_none()

    async def list(self, limit: int = 100, cursor: int | None = None) -> list[Category]:
        q = select(Category).where(Category.is_active == True).order_by(Category.id)
        if cursor:
            q = q.where(Category.id > cursor)
        q = q.limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def has_active_children(self, category_id: int) -> bool:
        result = await self.db.execute(
            select(Category.id).where(Category.parent_id == category_id, Category.is_active == True).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def has_products(self, category_id: int) -> bool:
        from app.models.product import Product
        result = await self.db.execute(
            select(Product.id).where(Product.category_id == category_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def count_active_products(self, category_id: int) -> int:
        from app.models.enums import ProductStatus
        from app.models.product import Product
        result = await self.db.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.category_id == category_id, Product.status == ProductStatus.active)
        )
        return int(result.scalar_one())

    async def deactivate_products_in_category(self, category_id: int) -> int:
        """Soft-delete (deactivate) all active products of a category. Returns the count."""
        from app.models.enums import ProductStatus
        from app.models.product import Product
        result = await self.db.execute(
            update(Product)
            .where(Product.category_id == category_id, Product.status == ProductStatus.active)
            .values(status=ProductStatus.inactive)
        )
        return result.rowcount or 0

    async def get_ancestor_ids(self, category_id: int) -> list[int]:
        """Return list of ancestor category IDs from root to parent."""
        ids = []
        current = await self.get_by_id(category_id)
        while current and current.parent_id:
            ids.insert(0, current.parent_id)
            current = await self.get_by_id(current.parent_id)
        return ids

    async def get_inherited_attributes(self, category_id: int) -> list[dict]:
        """Return all attributes from category + all ancestors. Each includes 'inherited' flag."""
        category = await self.get_by_id(category_id)
        if not category:
            return []

        # Collect all category IDs in hierarchy (root first, then current)
        hierarchy_ids = await self.get_ancestor_ids(category_id)
        hierarchy_ids.append(category_id)

        all_attrs = []
        seen_names: set[str] = set()

        for cat_id in hierarchy_ids:
            result = await self.db.execute(
                select(CategoryAttribute).where(
                    CategoryAttribute.category_id == cat_id,
                    CategoryAttribute.is_active == True,
                )
            )
            for attr in result.scalars().all():
                if attr.name.lower() not in seen_names:
                    seen_names.add(attr.name.lower())
                    all_attrs.append({
                        "attr": attr,
                        "inherited": cat_id != category_id,
                    })

        return all_attrs

    async def attribute_name_exists_in_hierarchy(self, category_id: int, name: str, exclude_id: int | None = None) -> bool:
        existing = await self.get_inherited_attributes(category_id)
        for item in existing:
            if item["attr"].name.lower() == name.lower():
                if exclude_id and item["attr"].id == exclude_id:
                    continue
                return True
        return False

    async def attribute_name_exists_in_descendants(
        self, category_id: int, name: str, exclude_id: int | None = None
    ) -> bool:
        """True if any strict descendant category already has an active attribute
        with this name (case-insensitive)."""
        descendant_ids = [
            cid for cid in await self.get_descendant_category_ids(category_id) if cid != category_id
        ]
        if not descendant_ids:
            return False
        q = select(CategoryAttribute.id).where(
            CategoryAttribute.category_id.in_(descendant_ids),
            CategoryAttribute.is_active == True,
            func.lower(CategoryAttribute.name) == name.lower(),
        )
        if exclude_id:
            q = q.where(CategoryAttribute.id != exclude_id)
        result = await self.db.execute(q.limit(1))
        return result.scalar_one_or_none() is not None

    async def get_descendant_category_ids(self, category_id: int) -> list[int]:
        """Return all descendant category IDs (recursive)."""
        ids = [category_id]
        result = await self.db.execute(select(Category.id).where(Category.parent_id == category_id))
        children = list(result.scalars().all())
        for child_id in children:
            ids.extend(await self.get_descendant_category_ids(child_id))
        return ids

    async def get_attribute_by_id(self, attr_id: int) -> CategoryAttribute | None:
        result = await self.db.execute(select(CategoryAttribute).where(CategoryAttribute.id == attr_id))
        return result.scalar_one_or_none()

    async def attribute_has_product_values(self, attr_id: int) -> bool:
        from app.models.product import Product
        attr = await self.get_attribute_by_id(attr_id)
        if not attr:
            return False
        result = await self.db.execute(
            select(Product.id).where(
                Product.custom_attributes.has_key(attr.name)  # type: ignore[attr-defined]
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_active_attributes(self, category_id: int) -> list[CategoryAttribute]:
        result = await self.db.execute(
            select(CategoryAttribute).where(
                CategoryAttribute.category_id == category_id,
                CategoryAttribute.is_active == True,
            )
        )
        return list(result.scalars().all())
