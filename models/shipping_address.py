from sqlalchemy import Column, Integer, String, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship

from models.base import Base


class ShippingAddress(Base):
    """
    Stores encrypted shipping addresses for orders with physical items.
    Supports two encryption modes:
    - AES-256-GCM: Server-side encryption (nonce + tag required)
    - PGP: Client-side encryption (nonce + tag not used)
    """
    __tablename__ = 'shipping_addresses'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False, unique=True)

    # Encrypted address data
    encrypted_address = Column(LargeBinary, nullable=False)  # Encrypted address
    nonce = Column(LargeBinary, nullable=False)  # GCM nonce (12 bytes) - only for AES mode
    tag = Column(LargeBinary, nullable=False)  # GCM tag (16 bytes) - only for AES mode
    encryption_mode = Column(String, nullable=False, default='aes')  # 'aes' or 'pgp'

    # Relation
    order = relationship('Order', back_populates='shipping_address')
