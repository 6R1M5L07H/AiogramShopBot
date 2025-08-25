from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from sqlalchemy import Column, Integer, DateTime, String, Float, func, ForeignKey, Text, CheckConstraint, Index
from sqlalchemy.orm import relationship

from models.base import Base


class OrderStatus(Enum):
    CREATED = "created"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Order(Base):
    __tablename__ = 'orders'
    
    # Add table-level constraints and indexes
    __table_args__ = (
        # Check constraints for data integrity
        CheckConstraint('total_amount > 0', name='ck_order_positive_amount'),
        CheckConstraint("currency IN ('BTC', 'ETH', 'LTC', 'SOL')", name='ck_order_valid_currency'),
        CheckConstraint("status IN ('created', 'paid', 'shipped', 'cancelled', 'expired')", name='ck_order_valid_status'),
        CheckConstraint('key_access_count >= 0', name='ck_order_non_negative_access_count'),
        CheckConstraint('expires_at > created_at', name='ck_order_valid_expiry'),
        
        # Indexes for performance
        Index('ix_orders_user_status', 'user_id', 'status'),
        Index('ix_orders_payment_address', 'payment_address'),
        Index('ix_orders_status_created_at', 'status', 'created_at'),
        Index('ix_orders_expires_at', 'expires_at'),
        Index('ix_orders_user_created_at', 'user_id', 'created_at'),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    status = Column(String, nullable=False, default=OrderStatus.CREATED.value)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(4), nullable=False)  # BTC/ETH/LTC/SOL with length constraint
    payment_address = Column(String(100), unique=True, nullable=False)  # Length constraint for performance
    # Encrypted private key storage
    encrypted_private_key = Column(Text, nullable=True)  # Base64 encoded encrypted private key
    private_key_salt = Column(String(64), nullable=True)  # Base64 encoded salt for key derivation
    # Legacy plaintext private key (will be removed after migration)
    private_key = Column(String, nullable=True)
    # Audit fields for private key access
    key_accessed_at = Column(DateTime, nullable=True)
    key_accessed_by_admin = Column(Integer, ForeignKey('users.id'), nullable=True)  # FK to admin user
    key_access_count = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    paid_at = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)
    
    # Relationships with cascade delete
    user = relationship("User", foreign_keys=[user_id], back_populates="orders")
    accessed_by_admin_user = relationship("User", foreign_keys=[key_accessed_by_admin])
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    reserved_stock = relationship("ReservedStock", back_populates="order", cascade="all, delete-orphan")


class OrderDTO(BaseModel):
    id: int | None = None
    user_id: int | None = None
    status: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    payment_address: str | None = None
    # Note: private_key removed from public DTO for security
    expires_at: datetime | None = None
    created_at: datetime | None = None
    paid_at: datetime | None = None
    shipped_at: datetime | None = None
    
    
class OrderDTOWithPrivateKey(BaseModel):
    """Internal DTO that includes private key - only for admin use"""
    id: int | None = None
    user_id: int | None = None
    status: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    payment_address: str | None = None
    private_key: str | None = None  # Decrypted private key for admin access
    expires_at: datetime | None = None
    created_at: datetime | None = None
    paid_at: datetime | None = None
    shipped_at: datetime | None = None