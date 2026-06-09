from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.catalog import Catalog, CatalogValue
from app.models.category import CategoryAttribute
from app.models.enums import AuditAction
from app.services.audit_service import AuditService


class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # ── Catalogs ──────────────────────────────────────────────────────────
    async def list_catalogs(self) -> list[tuple[Catalog, int]]:
        result = await self.db.execute(
            select(Catalog, func.count(CatalogValue.id))
            .outerjoin(
                CatalogValue,
                (CatalogValue.catalog_id == Catalog.id) & (CatalogValue.is_active == True),
            )
            .where(Catalog.is_active == True)
            .group_by(Catalog.id)
            .order_by(Catalog.name)
        )
        return [(row[0], int(row[1])) for row in result.all()]

    async def get_catalog(self, catalog_id: int) -> Catalog:
        cat = await self.db.get(Catalog, catalog_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATALOG_NOT_FOUND", "El catálogo no existe.")
        return cat

    async def create_catalog(self, name: str, description: str | None, actor_id, actor_name, request=None) -> Catalog:
        name = name.strip()
        await self._ensure_catalog_name_free(name)
        cat = Catalog(name=name, description=description)
        self.db.add(cat)
        await self.db.flush()
        await self.audit.log(AuditAction.CREATE, user_id=actor_id, username=actor_name,
                             entity_type="catalog", entity_id=cat.id, new={"name": name}, request=request)
        await self.db.commit()
        await self.db.refresh(cat)
        return cat

    async def update_catalog(self, catalog_id: int, name: str | None, description: str | None, actor_id, actor_name, request=None) -> Catalog:
        cat = await self.get_catalog(catalog_id)
        previous = {"name": cat.name, "description": cat.description}
        if name is not None:
            name = name.strip()
            await self._ensure_catalog_name_free(name, exclude_id=catalog_id)
            cat.name = name
        if description is not None:
            cat.description = description
        await self.audit.log(AuditAction.UPDATE, user_id=actor_id, username=actor_name,
                             entity_type="catalog", entity_id=cat.id, previous=previous,
                             new={"name": cat.name, "description": cat.description}, request=request)
        await self.db.commit()
        await self.db.refresh(cat)
        return cat

    async def delete_catalog(self, catalog_id: int, actor_id, actor_name, request=None) -> None:
        cat = await self.get_catalog(catalog_id)
        in_use = await self.db.execute(
            select(func.count()).select_from(CategoryAttribute).where(
                CategoryAttribute.catalog_id == catalog_id,
                CategoryAttribute.is_active == True,
            )
        )
        if int(in_use.scalar_one()) > 0:
            raise ConflictError(
                "CATALOG_IN_USE",
                "No se puede eliminar: el catálogo está siendo usado por atributos de categorías.",
            )
        cat.is_active = False
        await self.audit.log(AuditAction.DELETE, user_id=actor_id, username=actor_name,
                             entity_type="catalog", entity_id=cat.id, previous={"is_active": True},
                             new={"is_active": False}, request=request)
        await self.db.commit()

    async def _ensure_catalog_name_free(self, name: str, exclude_id: int | None = None) -> None:
        q = select(Catalog.id).where(
            func.lower(func.trim(Catalog.name)) == name.strip().lower(),
            Catalog.is_active == True,
        )
        if exclude_id:
            q = q.where(Catalog.id != exclude_id)
        if (await self.db.execute(q.limit(1))).scalar_one_or_none() is not None:
            raise ConflictError("CATALOG_NAME_EXISTS", f"Ya existe un catálogo llamado '{name}'.")

    # ── Values ────────────────────────────────────────────────────────────
    async def list_values(self, catalog_id: int, include_inactive: bool = True) -> list[CatalogValue]:
        await self.get_catalog(catalog_id)
        q = select(CatalogValue).where(CatalogValue.catalog_id == catalog_id)
        if not include_inactive:
            q = q.where(CatalogValue.is_active == True)
        q = q.order_by(CatalogValue.value)
        return list((await self.db.execute(q)).scalars().all())

    async def active_values(self, catalog_id: int) -> list[str]:
        result = await self.db.execute(
            select(CatalogValue.value).where(
                CatalogValue.catalog_id == catalog_id, CatalogValue.is_active == True
            )
        )
        return list(result.scalars().all())

    async def add_value(self, catalog_id: int, value: str, actor_id, actor_name, request=None) -> CatalogValue:
        await self.get_catalog(catalog_id)
        value = value.strip()
        await self._ensure_value_free(catalog_id, value)
        cv = CatalogValue(catalog_id=catalog_id, value=value)
        self.db.add(cv)
        await self.db.flush()
        await self.audit.log(AuditAction.CREATE, user_id=actor_id, username=actor_name,
                             entity_type="catalog_value", entity_id=cv.id,
                             new={"catalog_id": catalog_id, "value": value}, request=request)
        await self.db.commit()
        await self.db.refresh(cv)
        return cv

    async def update_value(self, catalog_id: int, value_id: int, value: str, actor_id, actor_name, request=None) -> CatalogValue:
        cv = await self._get_value(catalog_id, value_id)
        value = value.strip()
        await self._ensure_value_free(catalog_id, value, exclude_id=value_id)
        previous = {"value": cv.value}
        cv.value = value
        await self.audit.log(AuditAction.UPDATE, user_id=actor_id, username=actor_name,
                             entity_type="catalog_value", entity_id=cv.id, previous=previous,
                             new={"value": value}, request=request)
        await self.db.commit()
        await self.db.refresh(cv)
        return cv

    async def set_value_active(self, catalog_id: int, value_id: int, active: bool, actor_id, actor_name, request=None) -> CatalogValue:
        cv = await self._get_value(catalog_id, value_id)
        cv.is_active = active
        await self.audit.log(AuditAction.UPDATE, user_id=actor_id, username=actor_name,
                             entity_type="catalog_value", entity_id=cv.id,
                             new={"is_active": active}, request=request)
        await self.db.commit()
        await self.db.refresh(cv)
        return cv

    async def _get_value(self, catalog_id: int, value_id: int) -> CatalogValue:
        cv = await self.db.get(CatalogValue, value_id)
        if not cv or cv.catalog_id != catalog_id:
            raise NotFoundError("CATALOG_VALUE_NOT_FOUND", "El valor no existe en este catálogo.")
        return cv

    async def _ensure_value_free(self, catalog_id: int, value: str, exclude_id: int | None = None) -> None:
        q = select(CatalogValue.id).where(
            CatalogValue.catalog_id == catalog_id,
            CatalogValue.is_active == True,
            func.lower(func.trim(CatalogValue.value)) == value.strip().lower(),
        )
        if exclude_id:
            q = q.where(CatalogValue.id != exclude_id)
        if (await self.db.execute(q.limit(1))).scalar_one_or_none() is not None:
            raise ConflictError("CATALOG_VALUE_EXISTS", f"El valor '{value}' ya existe en este catálogo.")
