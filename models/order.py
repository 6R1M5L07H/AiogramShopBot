from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from sqlalchemy import Column, Integer, DateTime, String, Float, func, ForeignKey

from models.base import Base


class OrderStatus(Enum):
    CREATED = "created"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(String, nullable=False, default=OrderStatus.CREATED.value)
    total_amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)  # BTC/ETH/LTC/SOL
    payment_address = Column(String, unique=True, nullable=False)
    private_key = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    paid_at = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)


class OrderDTO(BaseModel):
    id: int | None = None
    user_id: int | None = None
    status: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    payment_address: str | None = None
    private_key: str | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    paid_at: datetime | None = None
    shipped_at: datetime | None = None