from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, DateTime, func, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship

from models.base import Base


class ReservedStock(Base):
    __tablename__ = 'reserved_stock'
    
    # Add table-level constraints and indexes
    __table_args__ = (
        # Check constraints for data integrity
        CheckConstraint('quantity > 0', name='ck_reserved_stock_positive_quantity'),
        CheckConstraint('expires_at > reserved_at', name='ck_reserved_stock_valid_expiry'),
        
        # Indexes for performance
        Index('ix_reserved_stock_order_id', 'order_id'),
        Index('ix_reserved_stock_category_subcategory', 'category_id', 'subcategory_id'),
        Index('ix_reserved_stock_expires_at', 'expires_at'),
        Index('ix_reserved_stock_category_subcategory_expires', 'category_id', 'subcategory_id', 'expires_at'),
        
        # Unique constraint per order and category/subcategory combination
        Index('ix_reserved_stock_unique', 'order_id', 'category_id', 'subcategory_id', unique=True),
    )

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id', ondelete='CASCADE'), nullable=False)
    subcategory_id = Column(Integer, ForeignKey('subcategories.id', ondelete='CASCADE'), nullable=False)
    quantity = Column(Integer, nullable=False)
    reserved_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="reserved_stock")
    category = relationship("Category", back_populates="reserved_stock")
    subcategory = relationship("Subcategory", back_populates="reserved_stock")


class ReservedStockDTO(BaseModel):
    id: int | None = None
    order_id: int | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    quantity: int | None = None
    reserved_at: datetime | None = None
    expires_at: datetime | None = None