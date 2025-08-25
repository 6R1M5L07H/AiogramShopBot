from pydantic import BaseModel
from sqlalchemy import Integer, Column, String
from sqlalchemy.orm import relationship

from models.base import Base


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True, unique=True)
    name = Column(String, nullable=False, unique=True)
    
    # Relationships
    reserved_stock = relationship("ReservedStock", back_populates="category")


class CategoryDTO(BaseModel):
    id: int | None = None
    name: str | None = None
