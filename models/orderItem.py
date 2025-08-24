from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, DateTime, Float, func, ForeignKey

from models.base import Base


class OrderItem(Base):
    __tablename__ = 'order_items'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    price_at_purchase = Column(Float, nullable=False)
    created_at = Column(DateTime, default=func.now())


class OrderItemDTO(BaseModel):
    id: int | None = None
    order_id: int | None = None
    item_id: int | None = None
    price_at_purchase: float | None = None
    created_at: datetime | None = None