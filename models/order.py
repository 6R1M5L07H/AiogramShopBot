from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String, func, CheckConstraint, Enum as SQLEnum, Text, LargeBinary
from sqlalchemy.orm import relationship

from enums.currency import Currency
from enums.order_status import OrderStatus
from models.base import Base


class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, unique=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING_PAYMENT)
    total_price = Column(Float, nullable=False)
    currency = Column(SQLEnum(Currency), nullable=False)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)

    # Shipping Fields
    shipping_cost = Column(Float, nullable=False, default=0.0)
    shipping_type_key = Column(String(100), nullable=True)  # Key referencing shipping_types config (e.g., "paeckchen", "paket_2kg")

    # Note: Shipping addresses are stored in shipping_addresses table (encrypted with AES-256-GCM or PGP)

    # Legacy Shipping Address Encryption (for backwards compatibility)
    # These columns are deprecated and only used for reading old data
    # New orders use the shipping_addresses table
    encryption_mode = Column(Text, nullable=True)  # 'aes-gcm' | 'pgp'
    encrypted_payload = Column(LargeBinary, nullable=True)  # Combined ciphertext+nonce+tag (AES) or PGP message

    # Payment Validation Fields
    total_paid_crypto = Column(Float, nullable=False, default=0.0)  # Sum of all partial payments
    retry_count = Column(Integer, nullable=False, default=0)  # Underpayment retry counter (0 or 1)
    original_expires_at = Column(DateTime, nullable=True)  # Original deadline (before extension)
    wallet_used = Column(Float, nullable=False, default=0.0)  # Wallet balance used for this order

    # Tier Pricing Breakdown (JSON)
    # Stores complete tier calculation for historical accuracy and audit trail
    # Format: [{"subcategory_id": 8, "subcategory_name": "Tea", "quantity": 30, "total": 270.0,
    #           "average_unit_price": 9.0, "breakdown": [{"quantity": 25, "unit_price": 9.0, "total": 225.0}, ...]}]
    tier_breakdown_json = Column(Text, nullable=True)

    # Cancellation Reason (for admin cancellations)
    # Stores custom reason text provided by admin when cancelling order
    # Displayed in order history detail view
    cancellation_reason = Column(Text, nullable=True)

    # Items Snapshot (JSON)
    # Stores complete item details at order creation time for historical record
    # Format: [{"description": "Item Name", "price": 10.0, "quantity": 2, "is_physical": true,
    #           "private_data": "KEY-123", "tier_breakdown": {...}, "unit": "pcs."}]
    # Allows viewing order details after items are released back to stock (cancelled orders)
    items_snapshot = Column(Text, nullable=True)

    # Refund Breakdown (JSON)
    # Stores refund calculation details for cancelled orders (especially mixed orders)
    # Format: {"digital_amount": 10.0, "physical_amount": 20.0, "shipping_cost": 1.5,
    #          "refundable_base": 21.5, "penalty_percent": 5, "penalty_amount": 1.08,
    #          "final_refund": 20.42, "is_mixed_order": true}
    # Allows displaying which items were refunded vs. kept in cancelled order view
    refund_breakdown_json = Column(Text, nullable=True)

    # Relations
    user = relationship('User', backref='orders')
    items = relationship('Item', backref='order')
    invoices = relationship('Invoice', back_populates='order', cascade='all, delete-orphan')  # Changed to plural, removed uselist=False to allow multiple invoices (partial payments)
    payment_transactions = relationship('PaymentTransaction', back_populates='order', cascade='all, delete-orphan')
    shipping_address = relationship('ShippingAddress', back_populates='order', uselist=False, cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('total_price > 0', name='check_order_total_price_positive'),
    )


class OrderDTO(BaseModel):
    id: int | None = None
    user_id: int | None = None
    status: OrderStatus | None = None
    total_price: float | None = None
    currency: Currency | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    paid_at: datetime | None = None
    cancelled_at: datetime | None = None
    shipped_at: datetime | None = None
    shipping_cost: float | None = 0.0
    shipping_type_key: str | None = None  # Key referencing shipping_types config
    total_paid_crypto: float | None = None
    retry_count: int | None = None
    original_expires_at: datetime | None = None
    wallet_used: float | None = None
    tier_breakdown_json: str | None = None  # JSON string with tier pricing breakdown
    cancellation_reason: str | None = None  # Custom reason for admin cancellations
    items_snapshot: str | None = None  # JSON string with complete item details at order creation
    refund_breakdown_json: str | None = None  # JSON string with refund calculation for cancelled orders