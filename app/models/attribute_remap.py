from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PendingAttributeRemap(Base):
    """A product attribute value that couldn't be auto-cast when its attribute's
    data type changed, and must be re-entered by the user."""
    __tablename__ = "pending_attribute_remap"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_id: Mapped[int] = mapped_column(ForeignKey("category_attributes.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
