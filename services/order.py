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
from repositories.user import UserRepository
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
        Automatically uses wallet balance if available.

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
        from repositories.user import UserRepository
        import logging

        # 1. Calculate total and check stock
        total_price = 0.0
        reserved_items = []

        for cart_item in cart_items:
            # Get price
            item_dto = ItemDTO(
                category_id=cart_item.category_id,
                subcategory_id=cart_item.subcategory_id
            )
            price = await ItemRepository.get_price(item_dto, session)
            total_price += price * cart_item.quantity

        # 2. Check wallet balance and calculate remaining amount
        user = await UserRepository.get_by_id(user_id, session)
        wallet_balance = user.top_up_amount

        # Calculate how much wallet balance to use (max: total_price)
        wallet_used = min(wallet_balance, total_price)
        remaining_amount = total_price - wallet_used

        logging.info(f"💰 Order creation: Total={total_price:.2f} EUR | Wallet={wallet_used:.2f} EUR | Remaining={remaining_amount:.2f} EUR")

        # 3. Deduct wallet balance if used
        if wallet_used > 0:
            user.top_up_amount -= wallet_used
            await UserRepository.update(user, session)
            logging.info(f"✅ Deducted {wallet_used:.2f} EUR from wallet (new balance: {user.top_up_amount:.2f} EUR)")

        # 4. Create order
        expires_at = datetime.now() + timedelta(minutes=config.ORDER_TIMEOUT_MINUTES)

        order_dto = OrderDTO(
            user_id=user_id,
            status=OrderStatus.PENDING_PAYMENT if remaining_amount > 0 else OrderStatus.PAID,
            total_price=total_price,
            currency=config.CURRENCY,
            expires_at=expires_at,
            wallet_used=wallet_used  # Track wallet usage
        )

        order_id = await OrderRepository.create(order_dto, session)

        # Reload order from DB to get created_at (set by func.now() in DB)
        order_dto = await OrderRepository.get_by_id(order_id, session)

        # 5. Reserve items (with SELECT FOR UPDATE in repository!)
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
            # Insufficient stock → rollback wallet deduction
            if wallet_used > 0:
                user.top_up_amount += wallet_used
                await UserRepository.update(user, session)
                logging.warning(f"⚠️ Rolled back wallet deduction: {wallet_used:.2f} EUR")
            raise e

        # 6. Create invoice ONLY if remaining amount > 0
        if remaining_amount > 0:
            await InvoiceService.create_invoice_with_kryptoexpress(
                order_id=order_id,
                fiat_amount=remaining_amount,  # Invoice for remaining amount only!
                fiat_currency=config.CURRENCY,
                crypto_currency=crypto_currency,
                session=session
            )
            logging.info(f"📋 Created invoice for remaining amount: {remaining_amount:.2f} EUR")
        else:
            # Order fully paid by wallet → status already set to PAID (line 81)
            logging.info(f"✅ Order fully paid by wallet ({wallet_used:.2f} EUR)")

        # 7. If order is fully paid (wallet-only), complete it immediately
        # Reload order to check final status
        order_dto = await OrderRepository.get_by_id(order_id, session)
        if order_dto.status == OrderStatus.PAID:
            # Commit reservation before completing order
            await session_commit(session)

            # Complete order: mark items sold, create Buy records, deliver items
            await OrderService.complete_order_payment(order_id, session)
            logging.info(f"✅ Order {order_id} completed immediately (paid by wallet)")

        return order_dto

    @staticmethod
    async def complete_order_payment(
        order_id: int,
        session: AsyncSession | Session
    ):
        """
        Completes order after successful payment.

        Order of operations (status FIRST for consistency):
        1. Set status to PAID (payment confirmed - source of truth)
        2. Mark items as sold (data integrity)
        3. Create Buy records (purchase history)
        4. Commit all changes
        5. Deliver items to user (send private_data via DM)

        Rationale: Status represents business truth (payment received).
        If item marking fails, status=PAID allows recovery jobs to detect
        and fix incomplete orders. Status should be set immediately after
        payment confirmation, not after data operations.
        """
        import logging
        from models.buy import BuyDTO
        from models.buyItem import BuyItemDTO
        from repositories.buy import BuyRepository
        from repositories.buyItem import BuyItemRepository
        from services.message import MessageService
        from services.notification import NotificationService

        # Get order details
        order = await OrderRepository.get_by_id(order_id, session)
        items = await ItemRepository.get_by_order_id(order_id, session)

        if not items:
            logging.warning(f"Order {order_id} has no items - cannot complete payment")
            return

        # 1. Update order status FIRST (payment confirmed = source of truth)
        await OrderRepository.update_status(order_id, OrderStatus.PAID, session)
        logging.info(f"✅ Order {order_id} status set to PAID")

        # 2. Mark items as sold (data integrity)
        for item in items:
            item.is_sold = True
        await ItemRepository.update(items, session)

        # 3. Create Buy record for purchase history (same as old system)
        buy_dto = BuyDTO(
            buyer_id=order.user_id,
            quantity=len(items),
            total_price=order.total_price
        )
        buy_id = await BuyRepository.create(buy_dto, session)

        # Link items to buy record
        buy_item_dto_list = [BuyItemDTO(item_id=item.id, buy_id=buy_id) for item in items]
        await BuyItemRepository.create_many(buy_item_dto_list, session)

        # 4. Commit all changes
        await session_commit(session)
        logging.info(f"✅ Order {order_id} data committed (status=PAID, items sold, buy records created)")

        # 5. Deliver items to user
        user = await UserRepository.get_by_id(order.user_id, session)

        # Create message with bought items (same format as old system)
        items_message = MessageService.create_message_with_bought_items(items)

        # Send items to user via DM (user receives their purchased items)
        await NotificationService.send_to_user(items_message, user.telegram_id)

        logging.info(f"✅ Order {order_id} completed - {len(items)} items delivered to user {user.id}")

        # Send admin notification (same as old system)
        # Note: new_buy expects cart_items, but we can reconstruct from order
        # For now, just log - admin notification can be enhanced later
        logging.info(f"📢 TODO: Send admin notification for order {order_id}")

    @staticmethod
    async def cancel_order(
        order_id: int,
        reason: 'OrderCancelReason',
        session: AsyncSession | Session,
        refund_wallet: bool = True
    ) -> tuple[bool, str]:
        """
        Cancels an order with the specified reason.

        Args:
            order_id: Order ID to cancel
            reason: Reason for cancellation (USER, TIMEOUT, ADMIN)
            session: Database session
            refund_wallet: Whether to refund wallet balance (False if payment handler already credited)

        Returns:
            tuple[bool, str]: (within_grace_period, message)
                - within_grace_period: True if cancelled for free (no strike)
                - message: Confirmation message

        Raises:
            ValueError: If order not found or cannot be cancelled
        """
        from datetime import datetime
        from enums.order_cancel_reason import OrderCancelReason
        import logging

        # Get order
        order = await OrderRepository.get_by_id(order_id, session)

        if not order:
            raise ValueError("Order not found")

        # Only pending orders can be cancelled
        if order.status not in [OrderStatus.PENDING_PAYMENT, OrderStatus.PENDING_PAYMENT_PARTIAL]:
            raise ValueError("Order cannot be cancelled (Status: {})".format(order.status.value))

        # Check grace period (only relevant for USER cancellation)
        time_elapsed = (datetime.utcnow() - order.created_at).total_seconds() / 60  # Minutes
        within_grace_period = time_elapsed <= config.ORDER_CANCEL_GRACE_PERIOD_MINUTES

        # Release reserved items
        items = await ItemRepository.get_by_order_id(order_id, session)
        for item in items:
            item.order_id = None  # Remove reservation
        await ItemRepository.update(items, session)

        # Refund wallet balance if any was used (and if not already refunded by payment handler)
        wallet_refund_info = None
        if refund_wallet and order.wallet_used > 0:
            user = await UserRepository.get_by_id(order.user_id, session)

            # Determine if penalty should be applied
            # NO penalty: Admin cancellation OR User within grace period
            # YES penalty: User after grace period OR Timeout
            apply_penalty = False
            if reason == OrderCancelReason.ADMIN:
                apply_penalty = False  # Admin cancels never have penalty
            elif reason == OrderCancelReason.USER:
                apply_penalty = not within_grace_period  # User penalty only outside grace period
            elif reason == OrderCancelReason.TIMEOUT:
                apply_penalty = True  # Timeout always has penalty (strike)

            if apply_penalty:
                # Apply penalty (configurable percentage)
                # Use calculate_penalty() to ensure correct rounding (penalty rounded DOWN)
                from services.payment_validator import PaymentValidator
                penalty_percent = config.PAYMENT_LATE_PENALTY_PERCENT
                penalty_amount, refund_amount = PaymentValidator.calculate_penalty(
                    order.wallet_used,
                    penalty_percent
                )

                user.top_up_amount += refund_amount
                await UserRepository.update(user, session)

                logging.info(f"💰 Refunded {refund_amount} EUR to user {user.id} wallet ({reason.value} cancellation, {penalty_percent}% penalty applied)")

                wallet_refund_info = {
                    'original_amount': order.wallet_used,
                    'penalty_amount': penalty_amount,
                    'refund_amount': refund_amount,
                    'penalty_percent': penalty_percent,
                    'reason': reason.value
                }
                # TODO: Create strike for late cancellation/timeout
            else:
                # Full refund for: ADMIN or USER within grace period
                user.top_up_amount += order.wallet_used
                await UserRepository.update(user, session)

                logging.info(f"💰 Refunded {order.wallet_used} EUR to user {user.id} wallet ({reason.value} cancellation, no penalty)")

                wallet_refund_info = {
                    'original_amount': order.wallet_used,
                    'penalty_amount': 0.0,
                    'refund_amount': order.wallet_used,
                    'penalty_percent': 0,
                    'reason': reason.value
                }

        # Set order status based on cancel reason
        if reason == OrderCancelReason.USER:
            new_status = OrderStatus.CANCELLED_BY_USER
            message = "Order successfully cancelled"
            # TODO: If not within_grace_period → create strike!
        elif reason == OrderCancelReason.TIMEOUT:
            new_status = OrderStatus.TIMEOUT
            within_grace_period = False  # Timeouts never count as grace period
            message = "Order cancelled due to timeout"
        elif reason == OrderCancelReason.ADMIN:
            new_status = OrderStatus.CANCELLED_BY_ADMIN
            within_grace_period = True  # Admin cancels don't cause strikes
            message = "Order cancelled by admin"
        else:
            raise ValueError(f"Unknown cancel reason: {reason}")

        await OrderRepository.update_status(order_id, new_status, session)

        # Send notification to user about wallet refund if applicable
        if wallet_refund_info:
            from services.notification import NotificationService
            from utils.localizator import Localizator
            from repositories.invoice import InvoiceRepository

            # Get invoice number for notification
            invoice = await InvoiceRepository.get_by_order_id(order_id, session)
            invoice_number = invoice.invoice_number if invoice else str(order_id)

            await NotificationService.notify_order_cancelled_wallet_refund(
                user=user,
                invoice_number=invoice_number,
                refund_info=wallet_refund_info,
                currency_sym=Localizator.get_currency_symbol()
            )

        return within_grace_period, message

    @staticmethod
    async def cancel_order_by_user(
        order_id: int,
        session: AsyncSession | Session
    ) -> tuple[bool, str]:
        """
        Cancels an order by the user (convenience wrapper).

        Returns:
            tuple[bool, str]: (within_grace_period, message)
        """
        from enums.order_cancel_reason import OrderCancelReason
        return await OrderService.cancel_order(order_id, OrderCancelReason.USER, session)