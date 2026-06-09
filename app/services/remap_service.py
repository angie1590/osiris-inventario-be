from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.models.attribute_remap import PendingAttributeRemap
from app.models.catalog import CatalogValue
from app.models.enums import AttributeDataType, AuditAction
from app.models.product import Product
from app.repositories.category_repository import CategoryRepository
from app.repositories.product_repository import ProductRepository
from app.services.audit_service import AuditService
from app.services.category_service import _cast_attribute_value


class RemapService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cat_repo = CategoryRepository(db)
        self.prod_repo = ProductRepository(db)
        self.audit = AuditService(db)

    async def _allowed_values(self, attr) -> list[str] | None:
        if attr.data_type == AttributeDataType.select:
            return attr.select_options
        if attr.data_type == AttributeDataType.catalog and attr.catalog_id:
            return list((await self.db.execute(
                select(CatalogValue.value).where(
                    CatalogValue.catalog_id == attr.catalog_id, CatalogValue.is_active == True
                )
            )).scalars().all())
        return None

    async def list_pending(self) -> dict:
        rows = list((await self.db.execute(
            select(PendingAttributeRemap).order_by(PendingAttributeRemap.attribute_id, PendingAttributeRemap.id)
        )).scalars().all())

        by_attr: dict[int, list[PendingAttributeRemap]] = {}
        for r in rows:
            by_attr.setdefault(r.attribute_id, []).append(r)

        groups = []
        total = 0
        for attr_id, items in by_attr.items():
            attr = await self.cat_repo.get_attribute_by_id(attr_id)
            if not attr:
                # attribute removed → orphan pending rows; drop them
                for it in items:
                    await self.db.delete(it)
                continue
            allowed = await self._allowed_values(attr)
            prod_names = dict((await self.db.execute(
                select(Product.id, Product.name).where(Product.id.in_([i.product_id for i in items]))
            )).all())
            groups.append({
                "attribute_id": attr_id,
                "attribute_name": attr.name,
                "target_type": attr.data_type.value,
                "is_required": attr.is_required,
                "catalog_id": attr.catalog_id,
                "allowed_values": allowed,
                "items": [
                    {"id": i.id, "product_id": i.product_id, "product_name": prod_names.get(i.product_id, ""), "old_value": i.old_value}
                    for i in items
                ],
            })
            total += len(items)
        await self.db.commit()
        return {"total": total, "groups": groups}

    async def resolve(self, assignments, actor_id: int, actor_name: str, request=None) -> int:
        count = 0
        for a in assignments:
            row = await self.db.get(PendingAttributeRemap, a.id)
            if not row:
                continue
            attr = await self.cat_repo.get_attribute_by_id(row.attribute_id)
            product = await self.prod_repo.get_by_id(row.product_id)
            if not attr or not product:
                await self.db.delete(row)
                continue

            value = a.value
            if value is None or (isinstance(value, str) and value.strip() == ""):
                if attr.is_required:
                    raise ValidationAppError(
                        "REQUIRED_VALUE_MISSING",
                        f"El producto '{product.name}' requiere un valor para '{attr.name}'.",
                    )
                # non-required: leave the value unset
            else:
                allowed = await self._allowed_values(attr)
                ok, casted = _cast_attribute_value(
                    value, attr.data_type,
                    options=allowed if attr.data_type == AttributeDataType.select else None,
                    catalog_values=allowed if attr.data_type == AttributeDataType.catalog else None,
                )
                if not ok:
                    raise ValidationAppError(
                        "INVALID_ATTRIBUTE_VALUE",
                        f"'{value}' no es un valor válido para '{attr.name}'.",
                    )
                ca = dict(product.custom_attributes or {})
                ca[attr.name] = casted
                product.custom_attributes = ca

            await self.db.delete(row)
            count += 1

        if count:
            await self.audit.log(
                AuditAction.UPDATE, user_id=actor_id, username=actor_name,
                entity_type="attribute_remap", entity_id=0,
                new={"resolved": count}, description="Resolve attribute remap", request=request,
            )
        await self.db.commit()
        return count
