from pydantic import BaseModel
from sqlalchemy import Column, Integer, ForeignKey, CheckConstraint, Text

from models.base import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    subcategory_id = Column(Integer, ForeignKey('subcategories.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    # JSON-encoded tier pricing breakdown for UX performance
    # NOTE: This is a display cache only. Server ALWAYS recomputes pricing
    # at order creation (services/order.py) to prevent price manipulation.
    # Accepted risk: Historic pricing data visible in DB backups.
    tier_breakdown = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
    )


class CartItemDTO(BaseModel):
    id: int | None = None
    cart_id: int | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    quantity: int | None = None
    tier_breakdown: str | None = None  # JSON-encoded tier pricing breakdown
