from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from models.base import Base


class PriceTier(Base):
    """
    Price tier for tiered pricing system.

    Each item can have multiple tiers based on quantity:
    - Example: 1-4 units: €11, 5-9 units: €10, 10+ units: €9

    The system uses a greedy algorithm to find the optimal combination
    of tiers for any given quantity.
    """
    __tablename__ = 'price_tiers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    min_quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to Item
    item = relationship("Item", back_populates="price_tiers")

    __table_args__ = (
        CheckConstraint('min_quantity > 0', name='check_min_quantity_positive'),
        CheckConstraint('unit_price > 0', name='check_unit_price_positive'),
    )


class PriceTierDTO(BaseModel):
    """DTO for price tier data transfer."""
    id: int | None = None
    item_id: int
    min_quantity: int
    unit_price: float
    created_at: datetime | None = None


class TierBreakdownItemDTO(BaseModel):
    """Single item in a tier breakdown (e.g., "10 × €9.00 = €90.00")."""
    quantity: int
    unit_price: float
    total: float


class TierPricingResultDTO(BaseModel):
    """Complete result of tier pricing calculation."""
    total: float
    average_unit_price: float
    breakdown: list[TierBreakdownItemDTO]