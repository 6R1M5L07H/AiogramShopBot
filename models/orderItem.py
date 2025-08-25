from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, DateTime, Float, func, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship

from models.base import Base


class OrderItem(Base):
    __tablename__ = 'order_items'
    
    # Add table-level constraints and indexes
    __table_args__ = (
        # Check constraints for data integrity
        CheckConstraint('price_at_purchase > 0', name='ck_order_item_positive_price'),
        
        # Indexes for performance
        Index('ix_order_items_order_id', 'order_id'),
        Index('ix_order_items_item_id', 'item_id'),
        Index('ix_order_items_order_created', 'order_id', 'created_at'),
        
        # Unique constraint to prevent duplicate items in same order
        Index('ix_order_items_unique', 'order_id', 'item_id', unique=True),
    )

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    price_at_purchase = Column(Float, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="order_items")
    item = relationship("Item", back_populates="order_items")


class OrderItemDTO(BaseModel):
    id: int | None = None
    order_id: int | None = None
    item_id: int | None = None
    price_at_purchase: float | None = None
    created_at: datetime | None = None