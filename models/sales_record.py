from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, Float, String, Date, DateTime, Boolean, Text, func
from sqlalchemy import Enum as SQLEnum

from models.base import Base
from enums.currency import Currency
from enums.cryptocurrency import Cryptocurrency
from enums.order_status import OrderStatus


class SalesRecord(Base):
    """
    Anonymized sales record per item for long-term analytics.

    NO user identification - only product, financial, and temporal data.
    Data minimization - cannot link sales to specific users.

    One record per sold item for granular analytics:
    - Trend analysis (hourly, daily, weekly patterns)
    - Product performance (category, subcategory revenue)
    - Payment method analysis (wallet vs crypto usage)
    - Shipping cost tracking
    """
    __tablename__ = 'sales_records'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # === Temporal Data ===
    sale_date = Column(Date, nullable=False, index=True)
    sale_hour = Column(Integer, nullable=False)  # 0-23
    sale_weekday = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday

    # === Item Details ===
    category_name = Column(String, nullable=False, index=True)
    subcategory_name = Column(String, nullable=False, index=True)
    quantity = Column(Integer, nullable=False)  # Always 1 for per-item records
    is_physical = Column(Boolean, nullable=False)

    # === Financial Data ===
    item_total_price = Column(Float, nullable=False)
    currency = Column(SQLEnum(Currency), nullable=False)
    average_unit_price = Column(Float, nullable=False)
    tier_breakdown_json = Column(Text, nullable=True)  # Tier pricing details

    # === Order-Level Data (Denormalized) ===
    order_hash = Column(String(64), nullable=True, index=True)  # Pseudonymized order identifier for refund tracking
    order_total_price = Column(Float, nullable=False)
    order_shipping_cost = Column(Float, nullable=False, default=0.0)
    order_wallet_used = Column(Float, nullable=False, default=0.0)

    # === Payment Details ===
    payment_method = Column(String, nullable=True)  # "wallet_only", "crypto_only", "mixed"
    crypto_currency = Column(SQLEnum(Cryptocurrency), nullable=True)

    # === Status & Lifecycle ===
    status = Column(SQLEnum(OrderStatus), nullable=False)
    is_refunded = Column(Boolean, nullable=False, default=False)

    # === Shipping Details (Anonymized) ===
    shipping_type = Column(String, nullable=True)  # e.g., "standard", "express" (NO address data)

    # === Metadata ===
    created_at = Column(DateTime, default=func.now())


class SalesRecordDTO(BaseModel):
    """DTO for SalesRecord creation"""
    id: int | None = None
    sale_date: datetime | None = None
    sale_hour: int | None = None
    sale_weekday: int | None = None
    category_name: str | None = None
    subcategory_name: str | None = None
    quantity: int | None = None
    is_physical: bool | None = None
    item_total_price: float | None = None
    currency: Currency | None = None
    average_unit_price: float | None = None
    tier_breakdown_json: str | None = None
    order_hash: str | None = None
    order_total_price: float | None = None
    order_shipping_cost: float | None = None
    order_wallet_used: float | None = None
    payment_method: str | None = None
    crypto_currency: Cryptocurrency | None = None
    status: OrderStatus | None = None
    is_refunded: bool | None = None
    shipping_type: str | None = None
    created_at: datetime | None = None