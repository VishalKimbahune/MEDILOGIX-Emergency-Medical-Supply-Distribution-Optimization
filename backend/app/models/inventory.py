"""Inventory ORM model tracking stock quantities per warehouse and product."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Inventory(Base, TimestampMixin):
    """Product-wise stock record at a medical distribution warehouse."""

    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", name="uq_inventory_warehouse_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventory_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    data_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Relationships
    warehouse = relationship("Warehouse", back_populates="inventory_items")
    product = relationship("Product", back_populates="inventory_items")
