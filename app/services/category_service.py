from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.category import Category, CategoryAttribute
from app.models.enums import AuditAction, AttributeDataType
from app.repositories.category_repository import CategoryRepository
from app.services.audit_service import AuditService


def _pluralize_es(name: str) -> str:
    """Best-effort Spanish pluralization of the last word of a catalog name
    (Marca→Marcas, Color→Colores, Material→Materiales, Luz→Luces)."""
    name = name.strip()
    if not name:
        return name
    parts = name.split(" ")
    w = parts[-1]
    low = w.lower()
    if low.endswith(("s", "x")) and len(w) > 1:
        plural = w  # leave likely-invariant words as-is
    elif low.endswith(("a", "e", "i", "o", "u", "á", "é", "í", "ó", "ú")):
        plural = w + "s"
    elif low.endswith("z"):
        plural = w[:-1] + "ces"
    else:
        plural = w + "es"
    parts[-1] = plural
    return " ".join(parts)


def _validate_attribute_value(value: Any, data_type: AttributeDataType, options: list[str] | None) -> bool:
    if data_type == AttributeDataType.integer:
        try:
            int(str(value))
        except (ValueError, TypeError):
            return False
    elif data_type == AttributeDataType.decimal:
        try:
            float(str(value))
        except (ValueError, TypeError):
            return False
    elif data_type == AttributeDataType.boolean:
        if not isinstance(value, bool):
            return False
    elif data_type == AttributeDataType.select:
        if options and str(value) not in options:
            return False
    return True


def _cast_attribute_value(
    value: Any,
    to_type: AttributeDataType,
    options: list[str] | None = None,
    catalog_values: list[str] | None = None,
) -> tuple[bool, Any]:
    """Try to convert a stored value to the new data type. Returns (ok, casted)."""
    if value is None or value == "":
        return True, None
    s = str(value)
    if to_type == AttributeDataType.text:
        return True, s
    if to_type == AttributeDataType.integer:
        try:
            return True, int(str(value).strip())
        except (ValueError, TypeError):
            return False, None
    if to_type == AttributeDataType.decimal:
        try:
            return True, float(str(value).strip())
        except (ValueError, TypeError):
            return False, None
    if to_type == AttributeDataType.boolean:
        if isinstance(value, bool):
            return True, value
        low = s.strip().lower()
        if low in ("true", "1", "si", "sí", "yes"):
            return True, True
        if low in ("false", "0", "no"):
            return True, False
        return False, None
    if to_type == AttributeDataType.date:
        from datetime import date
        try:
            date.fromisoformat(s[:10])
            return True, s[:10]
        except ValueError:
            return False, None
    if to_type == AttributeDataType.select:
        return (s in (options or [])), s
    if to_type == AttributeDataType.catalog:
        return (s in (catalog_values or [])), s
    return False, None


class CategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CategoryRepository(db)
        self.audit = AuditService(db)

    async def list_categories(self, limit: int = 100, cursor: int | None = None) -> list[Category]:
        return await self.repo.list(limit=limit, cursor=cursor)

    async def create_category(self, name: str, description: str | None, parent_id: int | None, actor_id: int, actor_name: str, request=None) -> tuple[Category, int]:
        if parent_id:
            parent = await self.repo.get_by_id(parent_id)
            if not parent or not parent.is_active:
                raise NotFoundError("PARENT_CATEGORY_NOT_FOUND", "Parent category not found or inactive")

        cat = Category(name=name.strip(), description=description, parent_id=parent_id)
        self.db.add(cat)
        await self.db.flush()

        await self.audit.log(
            AuditAction.CREATE, user_id=actor_id, username=actor_name,
            entity_type="category", entity_id=cat.id,
            new={"name": name, "parent_id": parent_id},
            request=request,
        )

        # A parent that had direct products becomes non-leaf when it gains a child;
        # its products must move to an auto-created "Sin clasificar" default bucket
        # for later recategorization.
        products_moved = 0
        if parent_id:
            products_moved = await self._ensure_default_bucket(parent_id, actor_id, actor_name, request)

        await self.db.commit()
        await self.db.refresh(cat)
        return cat, products_moved

    DEFAULT_CATEGORY_NAME = "Sin clasificar"

    async def _ensure_default_bucket(self, parent_id: int, actor_id: int, actor_name: str, request=None) -> int:
        """If the parent holds direct active products, move them into a (possibly
        new) 'Sin clasificar' default subcategory. Returns the number moved."""
        direct = await self.repo.count_active_products(parent_id)
        if direct == 0:
            return 0
        default = await self.repo.get_default_child(parent_id)
        if default is None:
            default = Category(name=self.DEFAULT_CATEGORY_NAME, parent_id=parent_id, is_default=True)
            self.db.add(default)
            await self.db.flush()
            await self.audit.log(
                AuditAction.CREATE, user_id=actor_id, username=actor_name,
                entity_type="category", entity_id=default.id,
                new={"name": self.DEFAULT_CATEGORY_NAME, "parent_id": parent_id, "is_default": True},
                request=request,
            )
        return await self.repo.reassign_active_products(parent_id, default.id)

    async def cleanup_default_if_empty(self, category_id: int) -> None:
        """Soft-delete a default category once it no longer holds active products."""
        cat = await self.repo.get_by_id(category_id)
        if cat and cat.is_default and cat.is_active:
            if await self.repo.count_active_products(category_id) == 0:
                cat.is_active = False

    async def update_category(
        self,
        category_id: int,
        name: str | None,
        description: str | None,
        actor_id: int,
        actor_name: str,
        request=None,
        parent_id: int | None = None,
        parent_provided: bool = False,
    ) -> Category:
        cat = await self.repo.get_by_id(category_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found")

        previous = {"name": cat.name, "description": cat.description, "parent_id": cat.parent_id}

        if parent_provided and parent_id != cat.parent_id:
            await self._validate_move(cat, parent_id)
            cat.parent_id = parent_id

        if name is not None:
            cat.name = name.strip()
        if description is not None:
            cat.description = description

        await self.audit.log(
            AuditAction.UPDATE, user_id=actor_id, username=actor_name,
            entity_type="category", entity_id=cat.id,
            previous=previous,
            new={"name": cat.name, "description": cat.description, "parent_id": cat.parent_id},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(cat)
        return cat

    async def _validate_move(self, cat: Category, new_parent_id: int | None) -> None:
        """Validate re-parenting a category: no cycles, valid parent, and no
        duplicate attributes introduced into the inheritance chain."""
        if new_parent_id is None:
            return  # moving to root never introduces inherited duplicates

        if new_parent_id == cat.id:
            raise ConflictError("CATEGORY_INVALID_PARENT", "Una categoría no puede ser su propio padre.")

        # The new parent cannot be the category itself or one of its descendants.
        descendant_ids = await self.repo.get_descendant_category_ids(cat.id)
        if new_parent_id in descendant_ids:
            raise ConflictError(
                "CATEGORY_INVALID_PARENT",
                "No se puede mover la categoría dentro de su propia rama (crearía un ciclo).",
            )

        parent = await self.repo.get_by_id(new_parent_id)
        if not parent or not parent.is_active:
            raise NotFoundError("PARENT_CATEGORY_NOT_FOUND", "La categoría padre no existe o está inactiva.")

        # After the move, the whole subtree inherits the new parent's chain.
        # Block if any attribute name collides between the two.
        subtree = await self.repo.active_attribute_names_in_subtree(cat.id)
        chain = {
            item["attr"].name.strip().lower()
            for item in await self.repo.get_inherited_attributes(new_parent_id)
        }
        duplicates = sorted(subtree[n] for n in subtree.keys() & chain)
        if duplicates:
            raise ConflictError(
                "CATEGORY_MOVE_DUPLICATE_ATTRIBUTES",
                f"No se puede mover la categoría porque generaría atributos duplicados en la cadena de herencia: {', '.join(duplicates)}.",
            )

    async def delete_category(
        self,
        category_id: int,
        actor_id: int,
        actor_name: str,
        request=None,
        delete_products: bool = False,
    ) -> None:
        cat = await self.repo.get_by_id(category_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATEGORY_NOT_FOUND", "La categoría no existe o ya fue eliminada.")

        if await self.repo.has_active_children(category_id):
            raise ConflictError(
                "CATEGORY_HAS_CHILDREN",
                "No se puede eliminar: la categoría tiene subcategorías activas. Elimínalas o muévelas primero.",
            )

        # Products with available stock would leave inventory inconsistencies if
        # their category were removed — block entirely (even with delete_products).
        with_stock = await self.repo.count_active_products_with_stock(category_id)
        if with_stock > 0:
            raise ConflictError(
                "CATEGORY_HAS_PRODUCTS_WITH_STOCK",
                f"No se puede eliminar: la categoría tiene {with_stock} producto(s) con stock disponible. Da de baja o egresa ese stock antes de eliminar la categoría.",
            )

        product_count = await self.repo.count_active_products(category_id)
        if product_count > 0 and not delete_products:
            raise ConflictError(
                "CATEGORY_HAS_PRODUCTS",
                f"La categoría tiene {product_count} producto(s) activo(s) asociado(s).",
            )

        deactivated = 0
        if product_count > 0 and delete_products:
            deactivated = await self.repo.deactivate_products_in_category(category_id)

        cat.is_active = False
        await self.audit.log(
            AuditAction.DELETE, user_id=actor_id, username=actor_name,
            entity_type="category", entity_id=cat.id,
            previous={"is_active": True},
            new={"is_active": False, "products_deactivated": deactivated},
            request=request,
        )
        await self.db.commit()

    async def get_inherited_attributes(self, category_id: int) -> list[dict]:
        cat = await self.repo.get_by_id(category_id)
        if not cat:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found")
        return await self.repo.get_inherited_attributes(category_id)

    async def add_attribute(self, category_id: int, name: str, data_type: AttributeDataType, is_required: bool, select_options: list[str] | None, actor_id: int, actor_name: str, request=None, catalog_id: int | None = None, allow_negative: bool = False) -> CategoryAttribute:
        cat = await self.repo.get_by_id(category_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found")

        name = name.strip()  # normalize: trim leading/trailing spaces (Rule 9)
        # An attribute name must be unique across the whole branch (ancestors and
        # descendants) so it lives at a single level and is inherited without
        # duplicates.
        if await self.repo.attribute_name_exists_in_hierarchy(category_id, name):
            raise ConflictError(
                "DUPLICATE_ATTRIBUTE_IN_HIERARCHY",
                f"El atributo '{name}' ya existe en una categoría superior y se hereda en esta. No es necesario crearlo aquí.",
            )
        if await self.repo.attribute_name_exists_in_descendants(category_id, name):
            raise ConflictError(
                "DUPLICATE_ATTRIBUTE_IN_DESCENDANTS",
                f"El atributo '{name}' ya existe en una o más subcategorías de esta rama. Elimínalo de las subcategorías para colocarlo en este nivel y que se herede.",
            )

        if data_type == AttributeDataType.select and (not select_options or len(select_options) == 0):
            raise ValidationAppError("SELECT_REQUIRES_OPTIONS", "Select type must have at least one option")
        resolved_catalog_id = None
        if data_type == AttributeDataType.catalog:
            if catalog_id is not None:
                await self._validate_catalog_ref(catalog_id)
                resolved_catalog_id = catalog_id
            else:
                # Auto-create (or reuse) a catalog named after the attribute (plural).
                resolved_catalog_id = await self._resolve_or_create_catalog(name, actor_id, actor_name, request)

        attr = CategoryAttribute(
            category_id=category_id, name=name, data_type=data_type,
            is_required=is_required, select_options=select_options,
            catalog_id=resolved_catalog_id,
            allow_negative=allow_negative if data_type in (AttributeDataType.integer, AttributeDataType.decimal) else False,
        )
        self.db.add(attr)
        await self.db.flush()

        await self.audit.log(
            AuditAction.CREATE, user_id=actor_id, username=actor_name,
            entity_type="category_attribute", entity_id=attr.id,
            new={"name": name, "data_type": data_type.value, "category_id": category_id},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(attr)
        return attr

    async def _resolve_or_create_catalog(self, base_name: str, actor_id: int, actor_name: str, request=None, seed_values: list[str] | None = None) -> int:
        """Find (by plural name) or create the catalog that backs this attribute.
        Reusing by name keeps the same canonical list across categories."""
        from app.models.catalog import Catalog, CatalogValue
        name = _pluralize_es(base_name.strip())
        catalog = (await self.db.execute(
            select(Catalog).where(
                func.lower(func.trim(Catalog.name)) == name.lower(),
                Catalog.is_active == True,
            )
        )).scalar_one_or_none()
        if catalog is None:
            catalog = Catalog(name=name)
            self.db.add(catalog)
            await self.db.flush()
            await self.audit.log(
                AuditAction.CREATE, user_id=actor_id, username=actor_name,
                entity_type="catalog", entity_id=catalog.id,
                new={"name": name, "auto_from_attribute": base_name}, request=request,
            )
        if seed_values:
            present = {
                v.value.strip().lower()
                for v in (await self.db.execute(select(CatalogValue).where(CatalogValue.catalog_id == catalog.id))).scalars().all()
            }
            for opt in seed_values:
                o = (opt or "").strip()
                if o and o.lower() not in present:
                    self.db.add(CatalogValue(catalog_id=catalog.id, value=o))
                    present.add(o.lower())
            await self.db.flush()
        return catalog.id

    async def _validate_catalog_ref(self, catalog_id: int | None) -> None:
        from app.models.catalog import Catalog
        if not catalog_id:
            raise ValidationAppError("CATALOG_REQUIRED", "Un atributo de tipo catálogo debe referenciar un catálogo.")
        cat = await self.db.get(Catalog, catalog_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATALOG_NOT_FOUND", "El catálogo seleccionado no existe.")

    async def update_attribute(self, category_id: int, attr_id: int, name: str | None, data_type: "AttributeDataType | None", is_required: bool | None, select_options: list[str] | None, actor_id: int, actor_name: str, request=None, catalog_id: int | None = None, allow_negative: bool | None = None) -> CategoryAttribute:
        attr = await self.repo.get_attribute_by_id(attr_id)
        if not attr or attr.category_id != category_id:
            raise NotFoundError("ATTRIBUTE_NOT_FOUND", "Attribute not found in this category")

        if name is not None:
            name = name.strip()  # normalize (Rule 9)
        if name and await self.repo.attribute_name_exists_in_hierarchy(category_id, name, exclude_id=attr_id):
            raise ConflictError(
                "DUPLICATE_ATTRIBUTE_IN_HIERARCHY",
                f"El atributo '{name}' ya existe en una categoría superior y se hereda en esta.",
            )
        if name and await self.repo.attribute_name_exists_in_descendants(category_id, name, exclude_id=attr_id):
            raise ConflictError(
                "DUPLICATE_ATTRIBUTE_IN_DESCENDANTS",
                f"El atributo '{name}' ya existe en una o más subcategorías de esta rama.",
            )

        effective_type = data_type if data_type is not None else attr.data_type
        effective_catalog_id = catalog_id if catalog_id is not None else attr.catalog_id
        pending_count = 0

        # Changing the data type migrates existing product values: auto-cast what
        # we can, and queue the rest for manual re-mapping (no destructive block).
        if data_type is not None and data_type != attr.data_type:
            effective_catalog_id, pending_count = await self._migrate_attribute_type(
                attr, data_type, select_options, catalog_id, actor_id, actor_name, request
            )

        if effective_type == AttributeDataType.catalog:
            await self._validate_catalog_ref(effective_catalog_id)

        previous = {"name": attr.name, "is_required": attr.is_required, "data_type": attr.data_type.value}
        if name is not None:
            attr.name = name
        if data_type is not None:
            attr.data_type = data_type
        if is_required is not None:
            attr.is_required = is_required
        if select_options is not None:
            attr.select_options = select_options
        if allow_negative is not None:
            attr.allow_negative = allow_negative
        if effective_type not in (AttributeDataType.integer, AttributeDataType.decimal):
            attr.allow_negative = False
        if effective_type == AttributeDataType.catalog:
            attr.catalog_id = effective_catalog_id
            attr.select_options = None
        else:
            attr.catalog_id = None

        await self.audit.log(
            AuditAction.UPDATE, user_id=actor_id, username=actor_name,
            entity_type="category_attribute", entity_id=attr.id,
            previous=previous, new={"name": attr.name, "is_required": attr.is_required, "data_type": attr.data_type.value},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(attr)
        return attr, pending_count

    async def _migrate_attribute_type(self, attr, new_type, new_options, provided_catalog_id, actor_id, actor_name, request=None) -> tuple[int | None, int]:
        from app.models.catalog import CatalogValue
        from app.models.attribute_remap import PendingAttributeRemap

        effective_catalog_id = provided_catalog_id if provided_catalog_id is not None else attr.catalog_id

        # Changing to catalog without choosing one → auto-create/reuse a catalog
        # named after the attribute (plural). If coming from select, seed its values.
        if new_type == AttributeDataType.catalog and provided_catalog_id is None:
            seed = attr.select_options if attr.data_type == AttributeDataType.select else None
            effective_catalog_id = await self._resolve_or_create_catalog(
                attr.name, actor_id, actor_name, request, seed_values=seed
            )

        # Validation context for the new type.
        options = new_options if new_options is not None else attr.select_options
        catalog_values: list[str] | None = None
        if new_type == AttributeDataType.catalog and effective_catalog_id:
            catalog_values = list((await self.db.execute(
                select(CatalogValue.value).where(
                    CatalogValue.catalog_id == effective_catalog_id, CatalogValue.is_active == True
                )
            )).scalars().all())

        subtree_ids = await self.repo.get_descendant_category_ids(attr.category_id)
        products = await self.repo.products_with_attribute(subtree_ids, attr.name)
        pending = 0
        for p in products:
            ca = dict(p.custom_attributes or {})
            if attr.name not in ca:
                continue
            ok, casted = _cast_attribute_value(ca[attr.name], new_type, options=options, catalog_values=catalog_values)
            if ok:
                if casted is None:
                    ca.pop(attr.name, None)
                else:
                    ca[attr.name] = casted
            else:
                self.db.add(PendingAttributeRemap(
                    product_id=p.id, attribute_id=attr.id, attribute_name=attr.name,
                    target_type=new_type.value, old_value=str(ca[attr.name]),
                ))
                ca.pop(attr.name, None)
                pending += 1
            p.custom_attributes = ca

        return effective_catalog_id, pending

    async def deactivate_attribute(self, category_id: int, attr_id: int, actor_id: int, actor_name: str, request=None) -> CategoryAttribute:
        attr = await self.repo.get_attribute_by_id(attr_id)
        if not attr or attr.category_id != category_id:
            raise NotFoundError("ATTRIBUTE_NOT_FOUND", "Attribute not found in this category")

        attr.is_active = False
        await self.audit.log(
            AuditAction.UPDATE, user_id=actor_id, username=actor_name,
            entity_type="category_attribute", entity_id=attr.id,
            previous={"is_active": True}, new={"is_active": False},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(attr)
        return attr

    async def reactivate_attribute(self, category_id: int, attr_id: int, actor_id: int, actor_name: str, request=None) -> CategoryAttribute:
        attr = await self.repo.get_attribute_by_id(attr_id)
        if not attr or attr.category_id != category_id:
            raise NotFoundError("ATTRIBUTE_NOT_FOUND", "Attribute not found in this category")

        attr.is_active = True
        await self.audit.log(
            AuditAction.UPDATE, user_id=actor_id, username=actor_name,
            entity_type="category_attribute", entity_id=attr.id,
            previous={"is_active": False}, new={"is_active": True},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(attr)
        return attr

    async def delete_attribute(self, category_id: int, attr_id: int, actor_id: int, actor_name: str, request=None) -> None:
        attr = await self.repo.get_attribute_by_id(attr_id)
        if not attr or attr.category_id != category_id:
            raise NotFoundError("ATTRIBUTE_NOT_FOUND", "Attribute not found in this category")

        has_values = await self.repo.attribute_has_product_values(attr_id)
        if has_values:
            raise ConflictError(
                "ATTRIBUTE_IN_USE",
                f"Cannot delete attribute '{attr.name}': it has product values. Deactivate it instead.",
            )

        await self.db.delete(attr)
        await self.audit.log(
            AuditAction.DELETE, user_id=actor_id, username=actor_name,
            entity_type="category_attribute", entity_id=attr_id,
            previous={"name": attr.name, "category_id": category_id},
            request=request,
        )
        await self.db.commit()
