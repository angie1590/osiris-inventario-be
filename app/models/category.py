from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AttributeDataType


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Temporary "Sin clasificar" bucket auto-created when a parent with products
    # gains a subcategory. Products here must be recategorized; cannot hold new ones.
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    parent: Mapped["Category | None"] = relationship("Category", remote_side="Category.id", back_populates="children")
    children: Mapped[list["Category"]] = relationship("Category", back_populates="parent")
    attributes: Mapped[list["CategoryAttribute"]] = relationship(back_populates="category", cascade="all, delete-orphan")
    products: Mapped[list["Product"]] = relationship(back_populates="category")  # type: ignore[name-defined]


class CategoryAttribute(Base):
    __tablename__ = "category_attributes"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    data_type: Mapped[AttributeDataType] = mapped_column(Enum(AttributeDataType), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    select_options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # Set when data_type == catalog: the master list this attribute draws from.
    catalog_id: Mapped[int | None] = mapped_column(ForeignKey("catalogs.id", ondelete="RESTRICT"), nullable=True, index=True)
    # For integer/decimal attributes: whether negative values are allowed.
    allow_negative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped["Category"] = relationship(back_populates="attributes")
