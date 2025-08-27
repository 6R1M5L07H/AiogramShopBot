from pydantic import BaseModel
from sqlalchemy import Integer, Column, String, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class Subcategory(Base):
    __tablename__ = 'subcategories'

    id = Column(Integer, primary_key=True, unique=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    
    # Relationships
    reserved_stock = relationship("ReservedStock", back_populates="subcategory")


class SubcategoryDTO(BaseModel):
    id: int | None
    name: str | None
    category_id: int | None
