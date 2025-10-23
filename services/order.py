from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from db import session_commit
from enums.cryptocurrency import Cryptocurrency
from enums.order_status import OrderStatus
from models.cartItem import CartItemDTO
from models.item import ItemDTO
from models.order import OrderDTO
from repositories.item import ItemRepository
from repositories.order import OrderRepository
from services.invoice import InvoiceService


class OrderService:

    @staticmethod
    async def create_order_from_cart(
        user_id: int,
        cart_items: list[CartItemDTO],
        crypto_currency: Cryptocurrency,
        session: AsyncSession | Session
    ) -> OrderDTO:
        """
        Creates order from cart items with reservation and invoice.

        Args:
            user_id: User ID
            cart_items: Cart items
            crypto_currency: Selected cryptocurrency for payment
            session: DB session

        Returns:
            OrderDTO

        Raises:
            ValueError: On insufficient stock
        """

        # 1. Calculate total and check stock
        items_total = 0.0
        reserved_items = []

        for cart_item in cart_items:
            # Get price
            item_dto = ItemDTO(
                category_id=cart_item.category_id,
                subcategory_id=cart_item.subcategory_id
            )
            price = await ItemRepository.get_price(item_dto, session)
            items_total += price * cart_item.quantity

        # 2. Create order (first without shipping cost)
        expires_at = datetime.now() + timedelta(minutes=config.ORDER_TIMEOUT_MINUTES)

        order_dto = OrderDTO(
            user_id=user_id,
            status=OrderStatus.PENDING_PAYMENT,
            total_price=items_total,  # Will be updated with shipping
            shipping_cost=0.0,  # Will be updated
            currency=config.CURRENCY,
            expires_at=expires_at
        )

        order_id = await OrderRepository.create(order_dto, session)

        # Reload order from DB to get created_at (set by func.now() in DB)
        order_dto = await OrderRepository.get_by_id(order_id, session)

        # 3. Reserve items (with SELECT FOR UPDATE in repository!)
        try:
            for cart_item in cart_items:
                items = await ItemRepository.reserve_items_for_order(
                    cart_item.subcategory_id,
                    cart_item.quantity,
                    order_id,
                    session
                )
                reserved_items.extend(items)
        except ValueError as e:
            # Insufficient stock → pass exception through
            raise e

        # 4. Calculate shipping cost from reserved items
        # Max shipping cost wins (user only pays highest single shipping cost)
        max_shipping_cost = 0.0
        has_physical_items = False

        for item_dto in reserved_items:
            if item_dto.is_physical:
                has_physical_items = True
                if item_dto.shipping_cost > max_shipping_cost:
                    max_shipping_cost = item_dto.shipping_cost

        # 5. Update order with shipping cost
        total_with_shipping = items_total + max_shipping_cost

        await OrderRepository.update_order_totals(
            order_id=order_id,
            total_price=total_with_shipping,
            shipping_cost=max_shipping_cost,
            session=session
        )

        # Update DTO for return
        order_dto.total_price = total_with_shipping
        order_dto.shipping_cost = max_shipping_cost

        # 6. Create invoice with final total
        await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order_id,
            fiat_amount=total_with_shipping,
            fiat_currency=config.CURRENCY,
            crypto_currency=crypto_currency,
            session=session
        )

        return order_dto

    @staticmethod
    async def complete_order_payment(
        order_id: int,
        session: AsyncSession | Session
    ):
        """
        Completes order after successful payment.
        - Marks items as sold
        - Sets order status to PAID (digital) or PAID_AWAITING_SHIPMENT (physical)
        """

        # Get order items
        items = await ItemRepository.get_by_order_id(order_id, session)

        # Mark as sold and check if any physical items
        has_physical_items = False
        for item in items:
            item.is_sold = True
            if item.is_physical:
                has_physical_items = True

        await ItemRepository.update(items, session)

        # Update order status based on item type
        if has_physical_items:
            # Physical items require shipment
            await OrderRepository.update_status(order_id, OrderStatus.PAID_AWAITING_SHIPMENT, session)
        else:
            # Digital only → immediately PAID
            await OrderRepository.update_status(order_id, OrderStatus.PAID, session)

        await session_commit(session)

    @staticmethod
    async def cancel_order_by_user(
        order_id: int,
        session: AsyncSession | Session
    ) -> tuple[bool, str]:
        """
        Cancels an order by the user.

        Returns:
            tuple[bool, str]: (within_grace_period, message)
                - within_grace_period: True if cancelled for free (no strike)
                - message: Confirmation message

        Raises:
            ValueError: If order not found or already completed
        """
        from datetime import datetime, timezone

        # Get order
        order = await OrderRepository.get_by_id(order_id, session)

        if not order:
            raise ValueError("Order not found")

        if order.status != OrderStatus.PENDING_PAYMENT:
            raise ValueError("Order cannot be cancelled (Status: {})".format(order.status.value))

        # Check grace period
        time_elapsed = (datetime.utcnow() - order.created_at).total_seconds() / 60  # Minutes
        within_grace_period = time_elapsed <= config.ORDER_CANCEL_GRACE_PERIOD_MINUTES

        # Release reserved items
        items = await ItemRepository.get_by_order_id(order_id, session)
        for item in items:
            item.order_id = None  # Remove reservation
        await ItemRepository.update(items, session)

        # Delete shipping address (GDPR compliance - immediate deletion on cancel)
        from repositories.shipping_address import ShippingAddressRepository
        await ShippingAddressRepository.delete_by_order_id(order_id, session)

        # Set order status
        await OrderRepository.update_status(order_id, OrderStatus.CANCELLED_BY_USER, session)

        # TODO: If not within_grace_period → create strike!
        # (Strike system needs to be implemented)

        await session_commit(session)

        return within_grace_period, "Order successfully cancelled"