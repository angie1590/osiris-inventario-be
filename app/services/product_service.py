import secrets
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.enums import AuditAction, AttributeDataType, ProductStatus
from app.models.product import Product
from app.repositories.category_repository import CategoryRepository
from app.repositories.product_repository import ProductRepository
from app.services.audit_service import AuditService
from app.services.category_service import CategoryService, _validate_attribute_value


def _validate_stock_quantity(
    value: Decimal, mode: str, field_name: str = "stock_min"
) -> None:
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

    @staticmethod
    def _auto_isbn() -> str:
        return f"AUTO-{secrets.token_hex(8)}"

    @staticmethod
    def _is_allowed_photo_content_type(content_type: str | None) -> bool:
        if not content_type:
            return False
        normalized = content_type.split(";", 1)[0].strip().lower()
        return normalized in {
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/heic",
            "image/heif",
        }

    async def _validate_photo_url(self, photo: str | None) -> None:
        if not photo or not photo.startswith(("http://", "https://")):
            return

        async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as client:
            responses: list[httpx.Response] = []

            try:
                responses.append(await client.head(photo))
            except httpx.HTTPError:
                pass

            needs_get = (
                not responses
                or responses[-1].status_code >= 400
                or not self._is_allowed_photo_content_type(
                    responses[-1].headers.get("content-type")
                )
            )

            if needs_get:
                try:
                    responses.append(
                        await client.get(photo, headers={"Range": "bytes=0-0"})
                    )
                except httpx.HTTPError:
                    # Some CDNs block bots/range requests; keep validation best-
                    # effort and rely on schema/url-format checks.
                    return

        if not responses or all(r.status_code >= 400 for r in responses):
            # Best-effort validation: if remote host is unreachable/forbidden,
            # don't block saving and let the URL be stored.
            return

        if not any(
            self._is_allowed_photo_content_type(r.headers.get("content-type"))
            for r in responses
            if r.status_code < 400
        ):
            raise ValidationAppError(
                "INVALID_PHOTO_URL",
                "La URL debe corresponder a una imagen PNG, JPG, JPEG o HEIC.",
                field_errors={
                    "photo": "La URL debe corresponder a una imagen PNG, JPG, JPEG o HEIC."
                },
            )

    @staticmethod
    def _normalize_gallery(
        photo: str | None,
        photos: list[dict[str, Any]] | None,
    ) -> tuple[str | None, list[dict[str, Any]] | None]:
        if photos is not None:
            if len(photos) == 0:
                return None, []
            normalized = [
                {"url": str(item.get("url", "")).strip(), "is_cover": bool(item.get("is_cover", False))}
                for item in photos
                if str(item.get("url", "")).strip()
            ]
            if len(normalized) == 0:
                return None, []

            cover_idx = next((idx for idx, item in enumerate(normalized) if item["is_cover"]), None)
            if cover_idx is None:
                normalized[0]["is_cover"] = True
                cover_idx = 0

            for idx, item in enumerate(normalized):
                item["is_cover"] = idx == cover_idx

            return normalized[cover_idx]["url"], normalized

        text = photo.strip() if photo else None
        if text:
            return text, [{"url": text, "is_cover": True}]
        return None, None

    async def _validate_gallery_urls(
        self,
        photo: str | None,
        photos: list[dict[str, Any]] | None,
    ) -> tuple[str | None, list[dict[str, Any]] | None]:
        cover, normalized = self._normalize_gallery(photo, photos)
        if normalized is None:
            return cover, None
        for item in normalized:
            await self._validate_photo_url(item["url"])
        return cover, normalized

    async def _validate_custom_attributes(
        self, category_id: int, custom_attributes: dict[str, Any] | None
    ) -> None:
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
                if attr.data_type == AttributeDataType.catalog:
                    from app.services.catalog_service import CatalogService

                    allowed = (
                        await CatalogService(self.db).active_values(attr.catalog_id)
                        if attr.catalog_id
                        else []
                    )
                    if str(value) not in allowed:
                        raise ValidationAppError(
                            "INVALID_ATTRIBUTE_VALUE",
                            f"'{value}' no es un valor válido del catálogo para el atributo '{attr.name}'.",
                        )
                elif not _validate_attribute_value(
                    value, attr.data_type, attr.select_options
                ):
                    raise ValidationAppError(
                        "INVALID_ATTRIBUTE_VALUE",
                        f"Invalid value for attribute '{attr.name}' (type: {attr.data_type.value})",
                    )
                elif (
                    attr.data_type
                    in (AttributeDataType.integer, AttributeDataType.decimal)
                    and not getattr(attr, "allow_negative", False)
                    and value not in (None, "")
                    and float(str(value)) < 0
                ):
                    raise ValidationAppError(
                        "INVALID_ATTRIBUTE_VALUE",
                        f"El atributo '{attr.name}' no admite valores negativos.",
                    )

    async def list_products(
        self,
        limit: int = 100,
        cursor: int | None = None,
        name: str | None = None,
        category_id: int | None = None,
        include_descendants: bool = True,
        status: ProductStatus | None = None,
        bajo_stock: bool | None = None,
    ) -> list[Product]:
        category_ids = None
        if category_id:
            if include_descendants:
                category_ids = await self.cat_repo.get_descendant_category_ids(
                    category_id
                )
            else:
                category_ids = [category_id]

        products = await self.repo.list(
            limit=limit,
            cursor=cursor,
            name=name,
            category_ids=category_ids,
            status=status,
            bajo_stock=bajo_stock,
        )
        return products

    async def create_product(
        self,
        isbn: str | None,
        name: str,
        description: str | None,
        photo: str | None,
        photos: list[dict[str, Any]] | None,
        category_id: int,
        stock_minimo: Decimal,
        pvp: Decimal,
        custom_attributes: dict | None,
        actor_id: int,
        actor_name: str,
        request=None,
        stock_mode: str = "integer",
        codigo_interno: str | None = None,
    ) -> Product:
        cat = await self.cat_repo.get_by_id(category_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found or inactive")
        if await self.cat_repo.has_active_children(category_id):
            raise ConflictError(
                "CATEGORY_NOT_LEAF",
                "No se pueden asignar productos a una categoría con subcategorías. Elige una categoría hoja (más específica).",
            )
        if cat.is_default:
            raise ConflictError(
                "CATEGORY_IS_DEFAULT",
                "La categoría 'Sin clasificar' es temporal. Asigna el producto a una subcategoría definitiva.",
            )

        _validate_stock_quantity(stock_minimo, stock_mode, "stock_minimo")
        photo_cover, normalized_photos = await self._validate_gallery_urls(photo, photos)
        await self._validate_custom_attributes(category_id, custom_attributes)

        product = Product(
            isbn=isbn or self._auto_isbn(),
            codigo_interno=(
                codigo_interno.strip()
                if codigo_interno and codigo_interno.strip()
                else None
            ),
            name=name,
            description=description,
            photo=photo_cover,
            photos=normalized_photos,
            category_id=category_id,
            stock_minimo=stock_minimo,
            stock_actual=Decimal("0"),
            pvp=pvp,
            status=ProductStatus.active,
            custom_attributes=custom_attributes,
        )
        p = await self.repo.create(product)

        await self.audit.log(
            AuditAction.CREATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="product",
            entity_id=p.id,
            new={
                "isbn": p.isbn,
                "name": name,
                "category_id": category_id,
                "pvp": float(pvp),
            },
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

    async def update_product(
        self,
        product_id: int,
        isbn: str | None,
        name: str | None,
        description: str | None,
        photo: str | None,
        photos: list[dict[str, Any]] | None,
        stock_minimo: Decimal | None,
        pvp: Decimal | None,
        custom_attributes: dict | None,
        actor_id: int,
        actor_name: str,
        request=None,
        stock_mode: str = "integer",
        category_id: int | None = None,
        category_provided: bool = False,
        codigo_interno: str | None = None,
        codigo_interno_provided: bool = False,
        photo_provided: bool = False,
        photos_provided: bool = False,
    ) -> Product:
        p = await self.repo.get_by_id(product_id)
        if not p:
            raise NotFoundError("PRODUCT_NOT_FOUND", "Product not found")

        # Resolve the target category (may be reassigned) and validate it.
        old_category_id = p.category_id
        target_category_id = p.category_id
        if (
            category_provided
            and category_id is not None
            and category_id != p.category_id
        ):
            cat = await self.cat_repo.get_by_id(category_id)
            if not cat or not cat.is_active:
                raise NotFoundError(
                    "CATEGORY_NOT_FOUND",
                    "La categoría seleccionada no existe o está inactiva.",
                )
            if await self.cat_repo.has_active_children(category_id):
                raise ConflictError(
                    "CATEGORY_NOT_LEAF",
                    "No se pueden asignar productos a una categoría con subcategorías. Elige una categoría hoja.",
                )
            if cat.is_default:
                raise ConflictError(
                    "CATEGORY_IS_DEFAULT",
                    "La categoría 'Sin clasificar' es temporal. Asigna el producto a una subcategoría definitiva.",
                )
            target_category_id = category_id

        if stock_minimo is not None:
            _validate_stock_quantity(stock_minimo, stock_mode, "stock_minimo")
        photo_cover: str | None = None
        normalized_photos: list[dict[str, Any]] | None = None
        if photos_provided:
            photo_cover, normalized_photos = await self._validate_gallery_urls(photo, photos)
        elif photo_provided:
            photo_cover, normalized_photos = await self._validate_gallery_urls(photo, None)
        if custom_attributes is not None:
            await self._validate_custom_attributes(
                target_category_id, custom_attributes
            )

        previous = {
            "isbn": p.isbn,
            "name": p.name,
            "pvp": float(p.pvp),
            "stock_minimo": float(p.stock_minimo),
            "category_id": p.category_id,
            "photo": p.photo,
            "photos": p.photos,
        }
        if isbn is not None:
            p.isbn = isbn
        if codigo_interno_provided:
            p.codigo_interno = (
                codigo_interno.strip()
                if codigo_interno and codigo_interno.strip()
                else None
            )
        if name is not None:
            p.name = name
        if description is not None:
            p.description = description
        if photos_provided or photo_provided:
            p.photo = photo_cover
            p.photos = normalized_photos
        p.category_id = target_category_id
        if stock_minimo is not None:
            p.stock_minimo = stock_minimo
        if pvp is not None:
            p.pvp = pvp
        if custom_attributes is not None:
            p.custom_attributes = custom_attributes

        # If the product left a "Sin clasificar" default bucket, drop the bucket
        # once it no longer holds active products.
        if target_category_id != old_category_id:
            await CategoryService(self.db).cleanup_default_if_empty(old_category_id)

        await self.audit.log(
            AuditAction.UPDATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="product",
            entity_id=p.id,
            previous=previous,
            new={"isbn": p.isbn, "name": p.name, "pvp": float(p.pvp)},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(p)
        return p

    async def update_status(
        self,
        product_id: int,
        status: ProductStatus,
        actor_id: int,
        actor_name: str,
        request=None,
        category_id: int | None = None,
    ) -> Product:
        p = await self.repo.get_by_id(product_id)
        if not p:
            raise NotFoundError("PRODUCT_NOT_FOUND", "Product not found")

        previous = {"status": p.status.value, "category_id": p.category_id}

        # Reactivating: the product's category must be active. If it was deleted
        # (e.g. via category cascade), a new active category must be supplied to
        # avoid a dangling reference.
        if status == ProductStatus.active:
            cat = await self.cat_repo.get_by_id(p.category_id)
            if not cat or not cat.is_active:
                if category_id is None:
                    raise ConflictError(
                        "PRODUCT_CATEGORY_INACTIVE",
                        "El producto pertenece a una categoría eliminada. Asígnale una categoría activa para reactivarlo.",
                    )
                newcat = await self.cat_repo.get_by_id(category_id)
                if not newcat or not newcat.is_active:
                    raise NotFoundError(
                        "CATEGORY_NOT_FOUND",
                        "La categoría seleccionada no existe o está inactiva.",
                    )
                if await self.cat_repo.has_active_children(category_id):
                    raise ConflictError(
                        "CATEGORY_NOT_LEAF",
                        "No se pueden asignar productos a una categoría con subcategorías. Elige una categoría hoja.",
                    )
                if newcat.is_default:
                    raise ConflictError(
                        "CATEGORY_IS_DEFAULT",
                        "La categoría 'Sin clasificar' es temporal. Asigna el producto a una subcategoría definitiva.",
                    )
                p.category_id = category_id

        p.status = status

        await self.audit.log(
            AuditAction.UPDATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="product",
            entity_id=p.id,
            previous=previous,
            new={"status": status.value},
            description=f"Product status changed to {status.value}",
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(p)
        return p

    async def list_pending_recategorization(self) -> list[Product]:
        """Active products sitting in a 'Sin clasificar' default category."""
        from app.models.category import Category

        result = await self.db.execute(
            select(Product)
            .join(Category, Category.id == Product.category_id)
            .where(
                Category.is_default == True,
                Category.is_active == True,
                Product.status == ProductStatus.active,
            )
            .order_by(Product.category_id, Product.id)
        )
        return list(result.scalars().all())

    async def recategorize(
        self, assignments, actor_id: int, actor_name: str, request=None
    ) -> int:
        """Bulk-reassign products out of default buckets into final leaf
        categories, then drop emptied default buckets."""
        affected_defaults: set[int] = set()
        count = 0
        for a in assignments:
            p = await self.repo.get_by_id(a.product_id)
            if not p:
                raise NotFoundError(
                    "PRODUCT_NOT_FOUND", f"El producto {a.product_id} no existe."
                )
            cat = await self.cat_repo.get_by_id(a.category_id)
            if not cat or not cat.is_active:
                raise NotFoundError(
                    "CATEGORY_NOT_FOUND",
                    "La categoría seleccionada no existe o está inactiva.",
                )
            if await self.cat_repo.has_active_children(a.category_id):
                raise ConflictError(
                    "CATEGORY_NOT_LEAF",
                    "No se pueden asignar productos a una categoría con subcategorías. Elige una categoría hoja.",
                )
            if cat.is_default:
                raise ConflictError(
                    "CATEGORY_IS_DEFAULT",
                    "La categoría 'Sin clasificar' es temporal. Asigna el producto a una subcategoría definitiva.",
                )
            old = p.category_id
            if old == a.category_id:
                continue
            p.category_id = a.category_id
            affected_defaults.add(old)
            count += 1
            await self.audit.log(
                AuditAction.UPDATE,
                user_id=actor_id,
                username=actor_name,
                entity_type="product",
                entity_id=p.id,
                previous={"category_id": old},
                new={"category_id": a.category_id},
                description="Recategorize product",
                request=request,
            )

        cat_svc = CategoryService(self.db)
        for cid in affected_defaults:
            await cat_svc.cleanup_default_if_empty(cid)
        await self.db.commit()
        return count
