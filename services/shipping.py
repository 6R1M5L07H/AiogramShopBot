from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from models.cartItem import CartItemDTO
from repositories.item import ItemRepository
from repositories.shipping_address import ShippingAddressRepository


class ShippingService:
    """Service for shipping-related operations"""

    @staticmethod
    async def check_cart_has_physical_items(cart_items: list[CartItemDTO], session: AsyncSession | Session) -> bool:
        """
        Check if cart contains any physical items that require shipping.

        Args:
            cart_items: List of cart items
            session: DB session

        Returns:
            True if cart has physical items, False otherwise
        """
        for cart_item in cart_items:
            try:
                sample_item = await ItemRepository.get_single(
                    cart_item.category_id, cart_item.subcategory_id, session
                )
                if sample_item and sample_item.is_physical:
                    return True
            except:
                # If no items available, continue checking other items
                continue

        return False

    @staticmethod
    async def check_cart_has_packstation_restricted_items(
        cart_items: list[CartItemDTO],
        session: AsyncSession | Session
    ) -> bool:
        """
        Check if cart contains items that cannot be delivered to Packstation.

        Args:
            cart_items: List of cart items
            session: DB session

        Returns:
            True if cart has Packstation-restricted items, False otherwise
        """
        for cart_item in cart_items:
            try:
                sample_item = await ItemRepository.get_single(
                    cart_item.category_id, cart_item.subcategory_id, session
                )
                if sample_item and sample_item.is_physical and not sample_item.packstation_allowed:
                    return True
            except:
                # If no items available, continue checking other items
                continue

        return False

    @staticmethod
    async def save_shipping_address(
        order_id: int,
        plaintext_address: str,
        session: AsyncSession | Session
    ) -> int:
        """
        Save encrypted shipping address for order.

        Args:
            order_id: Order ID
            plaintext_address: Plain text shipping address
            session: DB session

        Returns:
            Shipping address ID
        """
        return await ShippingAddressRepository.create(order_id, plaintext_address, session)

    @staticmethod
    async def get_shipping_address(order_id: int, session: AsyncSession | Session) -> str | None:
        """
        Get decrypted shipping address for order.

        Args:
            order_id: Order ID
            session: DB session

        Returns:
            Decrypted shipping address or None
        """
        return await ShippingAddressRepository.get_decrypted_address(order_id, session)
