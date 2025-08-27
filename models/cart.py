# cart is a container for unsold items to collect items from different (sub-)categories
# to be able to checkout this cart at once together with a shipment fee. Only the
# quantity, category, subcategory is stored because the unique item is not yet sold
#
# note that the item is NOT reserved or blocked so that the availability of the item
# needs to be checked again during checkout
from pydantic import BaseModel
from sqlalchemy import Column, Integer, ForeignKey, Float
from models.base import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    subcategory_id = Column(Integer, ForeignKey('subcategories.id'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    price = Column(Float, nullable=False, default=0.0)


class CartDTO(BaseModel):
    id: int | None = None
    user_id: int | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    quantity: int | None = None
    price: float | None = None
