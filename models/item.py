from datetime import datetime

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship, backref

from models.base import Base


# Item is a unique good which can only be sold once
class Item(Base):
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True, unique=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    category = relationship("Category", backref=backref("categories", cascade="all"), passive_deletes="all",
                            lazy="joined")
    subcategory_id = Column(Integer, ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=False)
    subcategory = relationship("Subcategory", backref=backref("subcategories", cascade="all"), passive_deletes="all",
                               lazy="joined")
    private_data = Column(String, nullable=False, unique=False)
    price = Column(Float, nullable=False)
    is_sold = Column(Boolean, nullable=False, default=False)
    is_new = Column(Boolean, nullable=False, default=True)
    description = Column(String, nullable=False)

    # Shipping-related fields
    is_physical = Column(Boolean, nullable=False, default=False)
    shipping_cost = Column(Float, nullable=False, default=0.0)
    allows_packstation = Column(Boolean, nullable=False, default=False)

    # Order-Zuordnung (Reservierung + Verkauf)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=True)
    reserved_at = Column(DateTime, nullable=True)

    # Tiered Pricing
    price_tiers = relationship("PriceTier", back_populates="item", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint('price > 0', name='check_price_positive'),
        CheckConstraint('shipping_cost >= 0', name='check_shipping_cost_non_negative'),
    )


class ItemDTO(BaseModel):
    id: int | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    private_data: str | None = None
    price: float | None = None
    is_sold: bool | None = None
    is_new: bool | None = None
    description: str | None = None
    is_physical: bool | None = None
    shipping_cost: float | None = None
    allows_packstation: bool | None = None
    order_id: int | None = None
    reserved_at: datetime | None = None
    price_tiers: list[dict] | None = None

    @model_validator(mode='before')
    @classmethod
    def handle_price_tiers(cls, data):
        """Ignore price_tiers from ORM (it's a Relationship, not a column)"""
        if isinstance(data, dict):
            # Normal dict input (e.g., from JSON import) - keep price_tiers
            return data
        else:
            # ORM object input (from_attributes=True) - don't try to access price_tiers relationship
            # Create dict from ORM attributes, excluding price_tiers relationship
            result = {}
            for field_name in cls.model_fields:
                if field_name != 'price_tiers' and hasattr(data, field_name):
                    result[field_name] = getattr(data, field_name)
            return result
