from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from models.base import Base


class ShippingTier(Base):
    """
    Shipping tier for quantity-based shipping type selection.

    Each subcategory can have multiple shipping tiers based on quantity:
    - Example: 1-5 units: Maxibrief, 6-10 units: Päckchen, 11+ units: Paket 2kg

    The cart system automatically selects the appropriate shipping type
    based on the quantity of items from the same subcategory.

    Shipping types reference keys from shipping_types/{country}.json configuration.
    """
    __tablename__ = 'shipping_tiers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    subcategory_id = Column(Integer, ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=False)
    min_quantity = Column(Integer, nullable=False)
    max_quantity = Column(Integer, nullable=True)  # NULL = unlimited
    shipping_type = Column(String, nullable=False)  # Key from shipping_types/{country}.json
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to Subcategory
    subcategory = relationship("Subcategory", backref="shipping_tiers")

    __table_args__ = (
        CheckConstraint('min_quantity > 0', name='check_shipping_min_quantity_positive'),
        CheckConstraint('max_quantity IS NULL OR max_quantity >= min_quantity',
                       name='check_shipping_max_quantity_valid'),
    )


class ShippingTierDTO(BaseModel):
    """DTO for shipping tier data transfer."""
    id: int | None = None
    subcategory_id: int
    min_quantity: int
    max_quantity: int | None = None
    shipping_type: str
    created_at: datetime | None = None


class ShippingSelectionResultDTO(BaseModel):
    """Result of shipping type selection for a cart item."""
    shipping_type_key: str  # Key from shipping_types json (e.g., "maxibrief")
    shipping_type_name: str  # Display name (e.g., "Maxibrief")
    base_cost: float
    has_tracking: bool
    allows_packstation: bool
    upgrade: dict | None = None  # Upgrade option if available