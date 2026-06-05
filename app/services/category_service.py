from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.category import Category, CategoryAttribute
from app.models.enums import AuditAction, AttributeDataType
from app.repositories.category_repository import CategoryRepository
from app.services.audit_service import AuditService


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


class CategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CategoryRepository(db)
        self.audit = AuditService(db)

    async def list_categories(self, limit: int = 100, cursor: int | None = None) -> list[Category]:
        return await self.repo.list(limit=limit, cursor=cursor)

    async def create_category(self, name: str, description: str | None, parent_id: int | None, actor_id: int, actor_name: str, request=None) -> Category:
        if parent_id:
            parent = await self.repo.get_by_id(parent_id)
            if not parent or not parent.is_active:
                raise NotFoundError("PARENT_CATEGORY_NOT_FOUND", "Parent category not found or inactive")

        cat = Category(name=name, description=description, parent_id=parent_id)
        self.db.add(cat)
        await self.db.flush()

        await self.audit.log(
            AuditAction.CREATE, user_id=actor_id, username=actor_name,
            entity_type="category", entity_id=cat.id,
            new={"name": name, "parent_id": parent_id},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(cat)
        return cat

    async def update_category(self, category_id: int, name: str | None, description: str | None, actor_id: int, actor_name: str, request=None) -> Category:
        cat = await self.repo.get_by_id(category_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found")

        previous = {"name": cat.name, "description": cat.description}
        if name is not None:
            cat.name = name
        if description is not None:
            cat.description = description

        await self.audit.log(
            AuditAction.UPDATE, user_id=actor_id, username=actor_name,
            entity_type="category", entity_id=cat.id,
            previous=previous, new={"name": cat.name, "description": cat.description},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(cat)
        return cat

    async def delete_category(self, category_id: int, actor_id: int, actor_name: str, request=None) -> None:
        cat = await self.repo.get_by_id(category_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found")

        if await self.repo.has_active_children(category_id):
            raise ConflictError("CATEGORY_HAS_CHILDREN", "Category has active subcategories")
        if await self.repo.has_products(category_id):
            raise ConflictError("CATEGORY_HAS_PRODUCTS", "Category has assigned products")

        cat.is_active = False
        await self.audit.log(
            AuditAction.DELETE, user_id=actor_id, username=actor_name,
            entity_type="category", entity_id=cat.id,
            previous={"is_active": True}, new={"is_active": False},
            request=request,
        )
        await self.db.commit()

    async def get_inherited_attributes(self, category_id: int) -> list[dict]:
        cat = await self.repo.get_by_id(category_id)
        if not cat:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found")
        return await self.repo.get_inherited_attributes(category_id)

    async def add_attribute(self, category_id: int, name: str, data_type: AttributeDataType, is_required: bool, select_options: list[str] | None, actor_id: int, actor_name: str, request=None) -> CategoryAttribute:
        cat = await self.repo.get_by_id(category_id)
        if not cat or not cat.is_active:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Category not found")

        if await self.repo.attribute_name_exists_in_hierarchy(category_id, name):
            raise ConflictError("DUPLICATE_ATTRIBUTE_IN_HIERARCHY", f"Attribute '{name}' already exists in the category hierarchy")

        if data_type == AttributeDataType.select and (not select_options or len(select_options) == 0):
            raise ValidationAppError("SELECT_REQUIRES_OPTIONS", "Select type must have at least one option")

        attr = CategoryAttribute(
            category_id=category_id, name=name, data_type=data_type,
            is_required=is_required, select_options=select_options,
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

    async def update_attribute(self, category_id: int, attr_id: int, name: str | None, is_required: bool | None, select_options: list[str] | None, actor_id: int, actor_name: str, request=None) -> CategoryAttribute:
        attr = await self.repo.get_attribute_by_id(attr_id)
        if not attr or attr.category_id != category_id:
            raise NotFoundError("ATTRIBUTE_NOT_FOUND", "Attribute not found in this category")

        if name and await self.repo.attribute_name_exists_in_hierarchy(category_id, name, exclude_id=attr_id):
            raise ConflictError("DUPLICATE_ATTRIBUTE_IN_HIERARCHY", f"Attribute '{name}' already exists in the hierarchy")

        previous = {"name": attr.name, "is_required": attr.is_required}
        if name is not None:
            attr.name = name
        if is_required is not None:
            attr.is_required = is_required
        if select_options is not None:
            attr.select_options = select_options

        await self.audit.log(
            AuditAction.UPDATE, user_id=actor_id, username=actor_name,
            entity_type="category_attribute", entity_id=attr.id,
            previous=previous, new={"name": attr.name, "is_required": attr.is_required},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(attr)
        return attr

    async def delete_attribute(self, category_id: int, attr_id: int, actor_id: int, actor_name: str, request=None) -> None:
        attr = await self.repo.get_attribute_by_id(attr_id)
        if not attr or attr.category_id != category_id:
            raise NotFoundError("ATTRIBUTE_NOT_FOUND", "Attribute not found in this category")

        await self.db.delete(attr)
        await self.audit.log(
            AuditAction.DELETE, user_id=actor_id, username=actor_name,
            entity_type="category_attribute", entity_id=attr_id,
            previous={"name": attr.name, "category_id": category_id},
            request=request,
        )
        await self.db.commit()
