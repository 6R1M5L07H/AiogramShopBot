from sqlalchemy import Column, Integer, LargeBinary, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from models.base import Base


class ShippingAddress(Base):
    """
    Stores encrypted shipping addresses for physical product orders.

    All address fields are encrypted using AES-256 to protect customer PII.
    Encryption key is stored in environment variable SHIPPING_ADDRESS_ENCRYPTION_KEY.
    """
    __tablename__ = 'shipping_addresses'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), unique=True, nullable=False)

    # Encrypted address text (single field, user enters free-form)
    # Format example:
    # John Doe
    # Main Street 42
    # Apt 5B
    # 10115 Berlin
    # Germany
    address_encrypted = Column(LargeBinary, nullable=False)

    created_at = Column(DateTime, default=func.now())

    # Relationship
    order = relationship("Order", back_populates="shipping_address")
