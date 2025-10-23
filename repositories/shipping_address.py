from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models.shipping_address import ShippingAddress
from utils.encryption import AddressEncryption


class ShippingAddressRepository:
    """Repository for shipping address CRUD operations with encryption"""

    @staticmethod
    async def create(order_id: int, plaintext_address: str, session: AsyncSession | Session) -> int:
        """
        Create encrypted shipping address for order.

        Args:
            order_id: Order ID
            plaintext_address: Plain text address (multi-line)
            session: DB session

        Returns:
            Shipping address ID
        """
        # Encrypt address
        encrypted = AddressEncryption.encrypt(plaintext_address)

        shipping_address = ShippingAddress(
            order_id=order_id,
            address_encrypted=encrypted
        )

        session.add(shipping_address)
        await session.flush()
        return shipping_address.id

    @staticmethod
    async def get_by_order_id(order_id: int, session: AsyncSession | Session) -> ShippingAddress | None:
        """Get shipping address by order ID"""
        stmt = select(ShippingAddress).where(ShippingAddress.order_id == order_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_decrypted_address(order_id: int, session: AsyncSession | Session) -> str | None:
        """
        Get decrypted shipping address for order.

        Args:
            order_id: Order ID
            session: DB session

        Returns:
            Decrypted address string, or None if not found
        """
        shipping_address = await ShippingAddressRepository.get_by_order_id(order_id, session)

        if not shipping_address:
            return None

        # Decrypt address
        return AddressEncryption.decrypt(shipping_address.address_encrypted)

    @staticmethod
    async def delete_by_order_id(order_id: int, session: AsyncSession | Session):
        """Delete shipping address by order ID"""
        shipping_address = await ShippingAddressRepository.get_by_order_id(order_id, session)
        if shipping_address:
            await session.delete(shipping_address)
