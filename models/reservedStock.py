from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, DateTime, func, ForeignKey

from models.base import Base


class ReservedStock(Base):
    __tablename__ = 'reserved_stock'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    subcategory_id = Column(Integer, ForeignKey('subcategories.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    reserved_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)


class ReservedStockDTO(BaseModel):
    id: int | None = None
    order_id: int | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    quantity: int | None = None
    reserved_at: datetime | None = None
    expires_at: datetime | None = None