from datetime import datetime, timedelta
import logging

from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import CartCallback, OrderCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.order_cancel_reason import OrderCancelReason
from enums.order_status import OrderStatus
from enums.strike_type import StrikeType
from enums.violation_type import ViolationType
from models.cart import CartDTO
from models.cartItem import CartItemDTO
from models.item import ItemDTO
from models.order import OrderDTO
from models.user import UserDTO
from repositories.cartItem import CartItemRepository
from repositories.item import ItemRepository
from repositories.order import OrderRepository
from repositories.user import UserRepository
from services.analytics import AnalyticsService
from utils.localizator import Localizator


class OrderService:

    @staticmethod
    async def orchestrate_order_creation(
        cart_dto: "CartDTO",
        session: AsyncSession | Session
    ) -> tuple[OrderDTO, list[dict], bool]:
        """
        Orchestrates order creation with stock reservation.

        This is called when user confirms checkout (after cart confirmation).
        Creates order record and reserves items. NO payment processing here!

        Flow:
        1. Calculate total price (items + MAX shipping cost)
        2. Create order record with timer
        3. Reserve items (with partial support)
        4. Handle stock adjustments if needed
        5. Determine item type (digital/physical)
        6. Set status: PENDING_PAYMENT or PENDING_PAYMENT_AND_ADDRESS

        Args:
            cart_dto: CartDTO with user_id and items
            session: Database session

        Returns:
            Tuple of (order, stock_adjustments, has_physical_items)
            - order: Created OrderDTO
            - stock_adjustments: List of items with changed quantities
              [{'subcategory_id', 'subcategory_name', 'requested', 'reserved'}, ...]
            - has_physical_items: True if order contains physical items

        Raises:
            ValueError: If all items are out of stock
        """
        from repositories.subcategory import SubcategoryRepository

        # Extract data from CartDTO
        user_id = cart_dto.user_id
        cart_items = cart_dto.items

        # 1. Calculate total price (items + MAX shipping cost) AND build tier breakdown JSON
        total_price_with_shipping, max_shipping_cost, tier_breakdown_json, shipping_type_key = await OrderService._calculate_order_totals(
            cart_items, session
        )

        # 2. Create order record with timer (NO wallet deduction yet!)
        expires_at = datetime.now() + timedelta(minutes=config.ORDER_TIMEOUT_MINUTES)

        order_dto = OrderDTO(
            user_id=user_id,
            status=OrderStatus.PENDING_PAYMENT,  # Will be updated based on item type
            total_price=total_price_with_shipping,
            shipping_cost=max_shipping_cost,
            shipping_type_key=shipping_type_key,  # Correctly determined from tiered shipping system
            currency=config.CURRENCY,
            expires_at=expires_at,
            wallet_used=0.0,  # Will be set later by orchestrate_payment_processing
            tier_breakdown_json=tier_breakdown_json  # Store tier pricing breakdown for historical accuracy
        )

        order_id = await OrderRepository.create(order_dto, session)
        logging.info(f"✅ Order {order_id} created (Status: PENDING_PAYMENT, Expires: {expires_at.strftime('%H:%M')})")

        # Reload order to get created_at (set by func.now() in DB)
        order_dto = await OrderRepository.get_by_id(order_id, session)

        # 3. Reserve items and track stock adjustments
        reserved_items, stock_adjustments = await OrderService._reserve_items_with_adjustments(
            cart_items, order_id, session
        )

        # 4. If stock adjustments: Recalculate price with tier pricing and update order
        if stock_adjustments:
            # Recalculate total with ACTUAL reserved quantities
            # CRITICAL: Use tier pricing for recalculation!
            actual_total_price = 0.0
            actual_max_shipping_cost = 0.0
            adjusted_tier_breakdown_list = []

            # Group reserved items by subcategory to recalculate tier prices
            from collections import defaultdict
            reserved_by_subcategory = defaultdict(list)
            for reserved_item in reserved_items:
                reserved_by_subcategory[reserved_item.subcategory_id].append(reserved_item)

            # Recalculate price for each subcategory with tier pricing
            from services.pricing import PricingService
            for subcategory_id, items in reserved_by_subcategory.items():
                actual_quantity = len(items)
                subcategory = await SubcategoryRepository.get_by_id(subcategory_id, session)

                # Recalculate tier price with ACTUAL quantity
                try:
                    pricing_result = await PricingService.calculate_optimal_price(
                        subcategory_id=subcategory_id,
                        quantity=actual_quantity,
                        session=session
                    )

                    # CRITICAL: If pricing returns 0, this indicates missing price configuration
                    if pricing_result.total == 0:
                        raise ValueError(f"Pricing returned 0 for subcategory {subcategory_id} - missing price tiers or item.price = 0")

                    actual_total_price += pricing_result.total

                    # Add to adjusted tier breakdown
                    adjusted_tier_breakdown_list.append({
                        'subcategory_id': subcategory_id,
                        'subcategory_name': subcategory.name if subcategory else 'Unknown',
                        'quantity': actual_quantity,
                        'total': pricing_result.total,
                        'average_unit_price': pricing_result.average_unit_price,
                        'breakdown': [
                            {
                                'quantity': item.quantity,
                                'unit_price': item.unit_price,
                                'total': item.total
                            }
                            for item in pricing_result.breakdown
                        ]
                    })

                    logging.info(f"Recalculated tier price for subcategory {subcategory_id}: {actual_quantity} items = {pricing_result.total:.2f} EUR")
                except Exception as e:
                    # CRITICAL ERROR: Cannot determine price for items
                    # This indicates missing price configuration (no tiers AND price=0)
                    logging.error(
                        f"❌ CRITICAL: Cannot calculate price for subcategory {subcategory_id} ({subcategory.name if subcategory else 'Unknown'}): {e}"
                    )
                    logging.error(f"❌ Order {order_id} MUST be cancelled - cannot proceed with unknown prices")

                    # Cancel order and release items
                    await OrderRepository.update_status(order_id, OrderStatus.CANCELLED_BY_SYSTEM, session)
                    for item in reserved_items:
                        item.order_id = None
                        item.is_sold = False
                    await ItemRepository.update(reserved_items, session)

                    # Raise exception to prevent order completion
                    raise ValueError(
                        f"Cannot create order - missing price configuration for subcategory {subcategory_id}. "
                        f"Please configure price_tiers or set item.price > 0"
                    )

                # Update shipping cost (use MAX)
                for item in items:
                    if item.is_physical:
                        actual_max_shipping_cost = max(actual_max_shipping_cost, item.shipping_cost)

            actual_total_with_shipping = actual_total_price + actual_max_shipping_cost

            # Update order with actual amounts AND adjusted tier breakdown
            import json
            order_dto.total_price = actual_total_with_shipping
            order_dto.shipping_cost = actual_max_shipping_cost
            order_dto.tier_breakdown_json = json.dumps(adjusted_tier_breakdown_list) if adjusted_tier_breakdown_list else None
            await OrderRepository.update(order_dto, session)

            logging.info(
                f"📊 Updated order {order_id} with adjusted prices: "
                f"Total={actual_total_with_shipping:.2f} EUR (was {total_price_with_shipping:.2f} EUR)"
            )

        # 5. Determine item type and set correct status
        has_physical_items = OrderService._detect_physical_items(reserved_items)

        if has_physical_items:
            await OrderRepository.update_status(order_id, OrderStatus.PENDING_PAYMENT_AND_ADDRESS, session)
            logging.info(f"📦 Order {order_id} contains physical items → Status: PENDING_PAYMENT_AND_ADDRESS")
        else:
            # Status already PENDING_PAYMENT (set at creation)
            logging.info(f"💾 Order {order_id} contains only digital items → Status: PENDING_PAYMENT")

        # Reload order after status update
        order_dto = await OrderRepository.get_by_id(order_id, session)

        # 6. Create items snapshot for historical record (before items can be released on cancel)
        items_snapshot_json = await OrderService._create_items_snapshot(order_id, session)
        order_dto.items_snapshot = items_snapshot_json
        await OrderRepository.update(order_dto, session)
        logging.info(f"💾 Saved items snapshot for order {order_id} ({len(reserved_items)} items)")

        return order_dto, stock_adjustments, has_physical_items

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
        from services.notification import NotificationService

        # Get order details
        order = await OrderRepository.get_by_id(order_id, session)
        items = await ItemRepository.get_by_order_id(order_id, session)

        if not items:
            logging.warning(f"Order {order_id} has no items - cannot complete payment")
            return

        # 1. Update order status FIRST (payment confirmed = source of truth)
        # Check if order contains physical items requiring shipment
        has_physical_items = any(item.is_physical for item in items)

        if has_physical_items:
            # Physical items → Status: PAID_AWAITING_SHIPMENT
            await OrderRepository.update_status(order_id, OrderStatus.PAID_AWAITING_SHIPMENT, session)
            logging.info(f"✅ Order {order_id} status set to PAID_AWAITING_SHIPMENT (physical items)")
        else:
            # Digital items only → Status: PAID
            await OrderRepository.update_status(order_id, OrderStatus.PAID, session)
            logging.info(f"✅ Order {order_id} status set to PAID")

        # 2. Mark items as sold (data integrity)
        for item in items:
            item.is_sold = True
        await ItemRepository.update(items, session)

        # 3. Create Buy record for purchase history (legacy - will be replaced)
        # Check if Buy record already exists (idempotency - prevent duplicates)
        existing_buy_items = await BuyItemRepository.get_by_item_ids([item.id for item in items], session)

        if not existing_buy_items:
            # No Buy record yet - create new one
            buy_dto = BuyDTO(
                buyer_id=order.user_id,
                quantity=len(items),
                total_price=order.total_price
            )
            buy_id = await BuyRepository.create(buy_dto, session)

            # Link items to buy record
            buy_item_dto_list = [BuyItemDTO(item_id=item.id, buy_id=buy_id) for item in items]
            await BuyItemRepository.create_many(buy_item_dto_list, session)
            logging.info(f"✅ Created Buy record {buy_id} for order {order_id}")
        else:
            logging.warning(f"⚠️ Buy record already exists for order {order_id} - skipping duplicate creation")

        # 3b. Create anonymized SalesRecord for long-term analytics (data minimization)
        from services.analytics import AnalyticsService
        try:
            sales_record_ids = await AnalyticsService.create_sales_records_from_order(order_id, session)
            logging.info(f"✅ Created {len(sales_record_ids)} SalesRecord entries for order {order_id}")
        except Exception as e:
            logging.error(f"❌ Failed to create SalesRecords for order {order_id}: {e}", exc_info=True)
            # Don't fail order completion if analytics fail

        # 4. Commit all changes
        await session_commit(session)
        logging.info(f"✅ Order {order_id} data committed (status=PAID, items sold, buy records created)")

        # Note: Items are now delivered via NotificationService.payment_success()
        # which sends a single combined message with invoice details + private_data
        logging.info(f"✅ Order {order_id} completed - {len(items)} items will be delivered via payment_success notification")

        # Send admin notification if order has physical items awaiting shipment
        if has_physical_items:
            from repositories.invoice import InvoiceRepository

            invoice = await InvoiceRepository.get_by_order_id(order_id, session)
            await NotificationService.order_awaiting_shipment(
                order_id=order.id,
                session=session
            )
            logging.info(f"📢 Admin notification sent: Order {order_id} awaiting shipment")

    @staticmethod
    def _calculate_partial_refund(
        items: list['ItemDTO'],
        order_total: float,
        shipping_cost: float,
        reason: 'OrderCancelReason',
        within_grace_period: bool,
        order_status: 'OrderStatus'
    ) -> dict:
        """
        Calculate refund for mixed orders (digital + physical items).

        Rules:
        1. Digital items: Refundable ONLY if NOT delivered yet (status != PAID)
        2. Physical items (not shipped): Always refundable
        3. Shipping cost: Refundable if physical items cancelled
        4. Penalty: Applied to ALL refundable amounts (digital + physical + shipping)

        Digital item delivery status:
        - PAID or PAID_AWAITING_SHIPMENT: Digital items DELIVERED → NOT refundable
        - All other statuses: Digital items NOT delivered → Refundable

        IMPORTANT: Uses order_total (with tier pricing) as source of truth,
        NOT item.price sum (which has original prices).

        Args:
            items: List of ItemDTOs in the order
            order_total: Total order amount (items + shipping) WITH TIER PRICING
            shipping_cost: Shipping cost for physical items
            reason: Cancellation reason (affects penalty)
            within_grace_period: True if within grace period (no penalty)
            order_status: Current order status (determines if digital items delivered)

        Returns:
            dict with refund breakdown:
            {
                'digital_amount': float,              # Amount for digital items (NOT refunded if delivered)
                'digital_refundable_amount': float,   # Amount for digital items (refundable if not delivered)
                'physical_amount': float,             # Amount for physical items (refundable)
                'shipping_cost': float,               # Shipping cost (refundable if physical)
                'refundable_base': float,             # Total refundable before penalty
                'penalty_percent': float,             # Penalty percentage applied
                'penalty_amount': float,              # Penalty amount (rounded down)
                'final_refund': float,                # Actual refund amount
                'has_digital_items': bool,            # True if order contains digital items
                'has_physical_items': bool,           # True if order contains physical items
                'is_mixed_order': bool,               # True if both digital and physical
                'digital_items_delivered': bool       # True if digital items were delivered
            }
        """
        from services.payment_validator import PaymentValidator
        from enums.order_status import OrderStatus

        # Check if digital items have been delivered
        # Digital items are delivered ONLY when order reaches PAID or PAID_AWAITING_SHIPMENT
        digital_items_delivered = (order_status == OrderStatus.PAID or
                                   order_status == OrderStatus.PAID_AWAITING_SHIPMENT)

        # Calculate digital item totals (digital items don't have tier pricing, use item.price)
        # Separate into delivered (non-refundable) and not-delivered (refundable)
        digital_total_non_refundable = 0.0  # Delivered digital items
        digital_total_refundable = 0.0      # Not delivered digital items
        has_digital = False
        has_physical = False

        for item in items:
            if item.is_physical:
                has_physical = True
            else:
                has_digital = True
                if digital_items_delivered:
                    # Digital item delivered → NOT refundable
                    digital_total_non_refundable += item.price
                else:
                    # Digital item NOT delivered → Refundable
                    digital_total_refundable += item.price

        is_mixed = has_digital and has_physical

        # Use order_total (with tier pricing) as source of truth
        # Calculate physical items by subtraction (preserves tier pricing)
        items_total = order_total - shipping_cost  # Subtract shipping to get items-only total

        if digital_items_delivered:
            # Digital delivered: Calculate physical as remainder after non-refundable digital
            physical_total = items_total - digital_total_non_refundable
            # Refundable base: Only physical items
            refundable_base = physical_total
        else:
            # Digital NOT delivered: Calculate physical as remainder after refundable digital
            physical_total = items_total - digital_total_refundable
            # Refundable base: Physical + Digital (both refundable)
            refundable_base = physical_total + digital_total_refundable

        # Shipping cost added to refundable base if physical items present
        if has_physical:
            refundable_base += shipping_cost

        # Determine penalty
        # NO penalty: Admin cancellation OR User within grace period
        # YES penalty: User after grace period OR Timeout
        apply_penalty = False
        penalty_percent = 0.0

        if reason == OrderCancelReason.ADMIN:
            apply_penalty = False
        elif reason == OrderCancelReason.USER:
            apply_penalty = not within_grace_period
        elif reason == OrderCancelReason.TIMEOUT:
            apply_penalty = True

        if apply_penalty:
            penalty_percent = config.PAYMENT_LATE_PENALTY_PERCENT
            penalty_amount, final_refund = PaymentValidator.calculate_penalty(
                refundable_base,
                penalty_percent
            )
        else:
            penalty_amount = 0.0
            final_refund = refundable_base

        return {
            'digital_amount': round(digital_total_non_refundable, 2),
            'digital_refundable_amount': round(digital_total_refundable, 2),
            'physical_amount': round(physical_total, 2),
            'shipping_cost': round(shipping_cost, 2),
            'refundable_base': round(refundable_base, 2),
            'penalty_percent': penalty_percent,
            'penalty_amount': round(penalty_amount, 2),
            'final_refund': round(final_refund, 2),
            'has_digital_items': has_digital,
            'has_physical_items': has_physical,
            'is_mixed_order': is_mixed,
            'digital_items_delivered': digital_items_delivered
        }

    @staticmethod
    async def cancel_order(
        order_id: int,
        reason: 'OrderCancelReason',
        session: AsyncSession | Session,
        refund_wallet: bool = True,
        custom_reason: str = None
    ) -> tuple[bool, str]:
        """
        Cancels an order with the specified reason.

        Args:
            order_id: Order ID to cancel
            reason: Reason for cancellation (USER, TIMEOUT, ADMIN)
            session: Database session
            refund_wallet: Whether to refund wallet balance (False if payment handler already credited)
            custom_reason: Optional custom reason text (used for ADMIN cancellations)

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

        # Get invoices first for logging
        from repositories.invoice import InvoiceRepository
        invoices_temp = await InvoiceRepository.get_all_by_order_id(order_id, session)
        invoice_num_log = invoices_temp[0].invoice_number if invoices_temp else "N/A"

        logging.info(f"🔄 CANCEL ORDER START: Order {order_id} (Invoice: {invoice_num_log}), Reason: {reason.value}, Refund Wallet: {refund_wallet}")

        # Get order
        order = await OrderRepository.get_by_id(order_id, session)

        logging.info(f"📋 Order {order_id} loaded: Status={order.status.value}, Total={order.total_price}€, Wallet Used={order.wallet_used}€")

        from exceptions.order import OrderNotFoundException

        if not order:
            raise OrderNotFoundException(order_id)

        # Check if order is already cancelled/completed
        already_cancelled_statuses = [
            OrderStatus.TIMEOUT,
            OrderStatus.CANCELLED_BY_USER,
            OrderStatus.CANCELLED_BY_ADMIN,
            OrderStatus.CANCELLED_BY_SYSTEM,
            OrderStatus.SHIPPED
        ]

        if order.status in already_cancelled_statuses:
            # Order is already cancelled/completed - return friendly message instead of exception
            logging.info(f"Order {order_id} is already in terminal state {order.status.value}, cannot cancel")
            from utils.localizator import Localizator
            from enums.bot_entity import BotEntity
            msg = Localizator.get_text(BotEntity.USER, "error_order_already_cancelled")
            return (True, msg)

        # Determine which statuses can be cancelled
        cancellable_statuses = [
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.PENDING_PAYMENT_AND_ADDRESS,
            OrderStatus.PENDING_PAYMENT_PARTIAL,
            OrderStatus.PAID
        ]

        # Admin can also cancel orders awaiting shipment (paid physical items)
        if reason == OrderCancelReason.ADMIN:
            cancellable_statuses.append(OrderStatus.PAID_AWAITING_SHIPMENT)

        from exceptions.order import InvalidOrderStateException

        if order.status not in cancellable_statuses:
            raise InvalidOrderStateException(
                order_id=order_id,
                current_state=order.status.value,
                required_state="PENDING_PAYMENT or PAID"
            )

        # Check grace period (only relevant for USER cancellation)
        time_elapsed = (datetime.utcnow() - order.created_at).total_seconds() / 60  # Minutes
        within_grace_period = time_elapsed <= config.ORDER_CANCEL_GRACE_PERIOD_MINUTES

        # Get ALL invoices for notification (handles partial payments with multiple invoices)
        from repositories.invoice import InvoiceRepository
        invoices = await InvoiceRepository.get_all_by_order_id(order_id, session)

        # For backward compatibility with notification methods that expect single invoice
        invoice = invoices[0] if invoices else None

        if invoices:
            # Use first invoice number for notification, or concatenate all (if multiple)
            invoice_number = invoices[0].invoice_number
            if len(invoices) > 1:
                invoice_number = " / ".join(inv.invoice_number for inv in invoices)
        else:
            # Fallback for orders without invoice (e.g., cancelled before payment)
            from datetime import datetime
            invoice_number = "N/A"

        # BUILD NOTIFICATION STRINGS FIRST (before items are released)
        # This ensures items still have order_id and can be loaded
        notification_messages = {}  # Store pre-built messages

        # Handle wallet refund/penalty logic
        # Three scenarios:
        # 1. order.wallet_used > 0: Refund wallet (with or without penalty)
        # 2. order.wallet_used = 0 BUT user has wallet balance AND penalty applies: Charge reservation fee
        # 3. order.wallet_used = 0 AND (no wallet OR no penalty): No fee
        wallet_refund_info = None
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

        # Load items to check if this is a mixed order (digital + physical)
        items = await ItemRepository.get_by_order_id(order_id, session)

        logging.info(f"📦 Order {order_id} (Invoice: {invoice_number}): Loaded {len(items)} items")

        # Calculate partial refund for mixed orders (digital items refunded if not delivered)
        partial_refund_info = OrderService._calculate_partial_refund(
            items=items,
            order_total=order.total_price,
            shipping_cost=order.shipping_cost or 0.0,
            reason=reason,
            within_grace_period=within_grace_period,
            order_status=order.status
        )

        logging.info(
            f"📊 Order {order_id} (Invoice: {invoice_number}): Partial refund calculated - "
            f"is_mixed={partial_refund_info['is_mixed_order']}, "
            f"digital_items_delivered={partial_refund_info['digital_items_delivered']}, "
            f"refundable_base={partial_refund_info['refundable_base']}€, "
            f"digital_refundable_amount={partial_refund_info['digital_refundable_amount']}€"
        )

        # Calculate total paid amount (wallet + crypto payments)
        # Wallet payments: Stored in order.wallet_used field (not in PaymentTransaction table)
        # Crypto payments: Stored in PaymentTransaction table
        from repositories.payment_transaction import PaymentTransactionRepository

        total_paid_fiat = 0.0

        # Add wallet payment (if any)
        if order.wallet_used > 0:
            total_paid_fiat += order.wallet_used

        # Add crypto payments from PaymentTransaction table (handles partial/mixed payments)
        for inv in invoices:
            # Check if this invoice has any payment transactions
            transactions = await PaymentTransactionRepository.get_by_invoice_id(inv.id, session)
            if transactions:
                # Sum up all payments for this invoice
                invoice_paid = sum(tx.fiat_amount for tx in transactions)
                total_paid_fiat += round(invoice_paid, 2)

        total_paid_fiat = round(total_paid_fiat, 2)

        # For mixed orders: Use partial refund calculation (digital items NOT refunded)
        # For non-mixed orders: Use full refund (existing behavior)
        if partial_refund_info['is_mixed_order']:
            # Mixed order: Only refund physical items + shipping
            refundable_amount = partial_refund_info['final_refund']
            logging.info(
                f"🔄 Mixed order cancellation: Digital={partial_refund_info['digital_amount']}€ (NOT refunded), "
                f"Physical={partial_refund_info['physical_amount']}€, "
                f"Shipping={partial_refund_info['shipping_cost']}€, "
                f"Refundable={refundable_amount}€"
            )
        else:
            # Non-mixed order: Use standard refund calculation based on total_paid_fiat
            refundable_amount = total_paid_fiat

        # Case 1: Payment was made (wallet or crypto) - refund with/without penalty
        logging.info(f"💰 REFUND CHECK for Order {order_id} (Invoice: {invoice_number}): refund_wallet={refund_wallet}, refundable_amount={refundable_amount}€, total_paid_fiat={total_paid_fiat}€, apply_penalty={apply_penalty}")

        # CRITICAL: Only refund if payment was actually made
        # Check total_paid_fiat instead of refundable_amount to prevent refunding unpaid orders
        if refund_wallet and total_paid_fiat > 0:
            logging.info(f"💰 ENTERING CASE 1: Refund wallet with payment made")
            # For mixed orders: Penalty already calculated in partial_refund_info
            # For non-mixed orders: Calculate penalty here
            if partial_refund_info['is_mixed_order']:
                # Mixed order: Use pre-calculated values from partial_refund_info
                # CRITICAL: Cap refund at actual amount paid (tier pricing may cause mismatch)
                penalty_amount = partial_refund_info['penalty_amount']
                refund_amount = min(partial_refund_info['final_refund'], total_paid_fiat)
                penalty_percent = partial_refund_info['penalty_percent']
                base_amount = min(partial_refund_info['refundable_base'], total_paid_fiat)

                if refund_amount < partial_refund_info['final_refund']:
                    logging.warning(
                        f"⚠️ Refund capped: calculated={partial_refund_info['final_refund']}€, "
                        f"but only {total_paid_fiat}€ was paid (tier pricing mismatch)"
                    )
            elif apply_penalty:
                # Non-mixed order with penalty: Calculate now
                from services.payment_validator import PaymentValidator
                penalty_percent = config.PAYMENT_LATE_PENALTY_PERCENT
                penalty_amount, refund_amount = PaymentValidator.calculate_penalty(
                    total_paid_fiat,
                    penalty_percent
                )
                base_amount = total_paid_fiat
            else:
                # No penalty
                penalty_amount = 0.0
                refund_amount = refundable_amount
                penalty_percent = 0.0
                base_amount = total_paid_fiat

            # Apply refund to user wallet
            old_balance = user.top_up_amount
            user.top_up_amount = round(user.top_up_amount + refund_amount, 2)
            new_balance = user.top_up_amount

            logging.info(f"💰 REFUND CALCULATION: User {user.id} wallet {old_balance}€ + {refund_amount}€ = {new_balance}€")

            await UserRepository.update(user, session)

            logging.info(f"💰 REFUND APPLIED: User {user.id} wallet updated to {new_balance}€ (awaiting commit)")

            if penalty_amount > 0:
                logging.info(
                    f"💰 Refunded {refund_amount} EUR to user {user.id} wallet "
                    f"({reason.value} cancellation, {penalty_percent}% penalty applied, "
                    f"base: {base_amount}€)"
                )
            else:
                logging.info(
                    f"💰 Refunded {refund_amount} EUR to user {user.id} wallet "
                    f"({reason.value} cancellation, no penalty)"
                )

            wallet_refund_info = {
                'original_amount': total_paid_fiat,  # Total paid (wallet + crypto)
                'base_amount': base_amount,  # Amount before penalty
                'penalty_amount': penalty_amount,
                'refund_amount': refund_amount,
                'penalty_percent': penalty_percent,
                'reason': reason.value,
                'is_mixed_order': partial_refund_info['is_mixed_order'],
                'partial_refund_info': partial_refund_info if partial_refund_info['is_mixed_order'] else None
            }

            # Add strike for late cancellation/timeout (if penalty applied)
            if apply_penalty:
                logging.info(f"⚠️ ADDING STRIKE: User {user.id}, Order {order_id}, Reason: {reason.value}")
                await OrderService._add_strike_and_check_ban(
                    user_id=user.id,
                    order_id=order_id,
                    strike_type=StrikeType.TIMEOUT if reason == OrderCancelReason.TIMEOUT else StrikeType.LATE_CANCEL,
                    session=session
                )
                logging.info(f"⚠️ STRIKE PROCESSING COMPLETE: User {user.id}")

        # Case 2: Wallet NOT used in order BUT user has balance AND penalty applies
        # Charge "reservation fee" for blocking items without payment
        elif apply_penalty and user.top_up_amount > 0:
            logging.info(f"💸 ENTERING CASE 2: Charge reservation fee (no payment made but wallet has balance)")
            from services.payment_validator import PaymentValidator
            penalty_percent = config.PAYMENT_LATE_PENALTY_PERCENT

            # Calculate fee based on order total (capped at wallet balance)
            base_amount = min(order.total_price, user.top_up_amount)
            penalty_amount, _ = PaymentValidator.calculate_penalty(base_amount, penalty_percent)

            # Deduct reservation fee from wallet
            user.top_up_amount = round(user.top_up_amount - penalty_amount, 2)
            await UserRepository.update(user, session)

            logging.info(f"💸 Charged {penalty_amount} EUR reservation fee from user {user.id} wallet ({reason.value} cancellation, no wallet used but penalty applies)")

            wallet_refund_info = {
                'original_amount': 0.0,
                'penalty_amount': penalty_amount,
                'refund_amount': 0.0,
                'penalty_percent': penalty_percent,
                'reason': f"{reason.value}_reservation_fee",
                'base_amount': base_amount
            }

        # Case 3: No wallet used AND (no wallet balance OR no penalty)
        # No financial consequence, just release items
        else:
            logging.info(f"ℹ️ ENTERING CASE 3: No wallet refund/charge (no payment made, no wallet balance, or no penalty)")

        # Set order status based on cancel reason
        if reason == OrderCancelReason.USER:
            new_status = OrderStatus.CANCELLED_BY_USER
            message = "Order successfully cancelled"
            # Add strike if cancelled outside grace period
            if not within_grace_period:
                await OrderService._add_strike_and_check_ban(
                    user_id=user.id,
                    order_id=order_id,
                    strike_type=StrikeType.LATE_CANCEL,
                    session=session
                )
                # Track violation for analytics (anonymized, no user_id)
                try:
                    await AnalyticsService.create_violation_record(
                        order_id=order_id,
                        violation_type=ViolationType.USER_CANCELLATION_LATE,
                        penalty_applied=penalty_amount if wallet_refund_info and wallet_refund_info.get('penalty_amount') else 0.0,
                        session=session
                    )
                except Exception as e:
                    logging.error(f"Failed to create violation record for order {order_id}: {e}", exc_info=True)
        elif reason == OrderCancelReason.TIMEOUT:
            new_status = OrderStatus.TIMEOUT
            within_grace_period = False  # Timeouts never count as grace period
            message = "Order cancelled due to timeout"
            # Add strike for timeout (if not already added above)
            # Check if wallet was used (strike already added in wallet refund section)
            if order.wallet_used == 0:
                await OrderService._add_strike_and_check_ban(
                    user_id=user.id,
                    order_id=order_id,
                    strike_type=StrikeType.TIMEOUT,
                    session=session
                )
            # Track violation for analytics (GDPR-compliant, no user_id)
            try:
                await AnalyticsService.create_violation_record(
                    order_id=order_id,
                    violation_type=ViolationType.TIMEOUT,
                    penalty_applied=penalty_amount if wallet_refund_info and wallet_refund_info.get('penalty_amount') else 0.0,
                    session=session
                )
            except Exception as e:
                logging.error(f"Failed to create violation record for order {order_id}: {e}", exc_info=True)
        elif reason == OrderCancelReason.ADMIN:
            new_status = OrderStatus.CANCELLED_BY_ADMIN
            within_grace_period = True  # Admin cancels don't cause strikes
            message = "Order cancelled by admin"
        else:
            raise ValueError(f"Unknown cancel reason: {reason}")

        # BUILD NOTIFICATION MESSAGES (before releasing items)
        # Items still have order_id at this point, so notifications can load them
        from services.notification import NotificationService
        from utils.localizator import Localizator

        if wallet_refund_info:
            # Wallet-based notification (includes strike info if penalty was applied)
            notification_messages['wallet_refund'] = await NotificationService.build_order_cancelled_wallet_refund_message(
                user=user,
                order=order,
                invoice=invoice,
                invoice_number=invoice_number,
                refund_info=wallet_refund_info,
                currency_sym=Localizator.get_currency_symbol(),
                session=session,
                custom_reason=custom_reason
            )
        elif not within_grace_period and reason != OrderCancelReason.ADMIN:
            # No wallet involved but strike was given
            notification_messages['strike_only'] = await NotificationService.build_order_cancelled_strike_only_message(
                user=user,
                invoice_number=invoice_number,
                reason=reason,
                custom_reason=custom_reason
            )
        elif reason == OrderCancelReason.ADMIN:
            # Admin cancellation (with or without custom reason)
            notification_messages['admin_cancel'] = await NotificationService.build_order_cancelled_by_admin_message(
                user=user,
                invoice_number=invoice_number,
                custom_reason=custom_reason,  # Can be None
                order=order,
                session=session
            )

        # UPDATE ORDER STATUS
        await OrderRepository.update_status(order_id, new_status, session)

        # UPDATE SALESRECORDS FOR REFUNDED ITEMS (only if order reached PAID status)
        # This ensures analytics accurately reflect refunded items
        if order.status == OrderStatus.PAID or order.status == OrderStatus.PAID_AWAITING_SHIPMENT:
            from services.analytics import AnalyticsService
            try:
                # Identify which items to mark as refunded based on delivery status
                refunded_items = []
                for item in items:
                    if item.is_physical:
                        # Physical items always refunded after PAID cancellation
                        refunded_items.append(item)
                    # Digital items already delivered at PAID, not refunded

                if refunded_items:
                    refunded_count = await AnalyticsService.mark_items_as_refunded(
                        order_id=order_id,
                        items=refunded_items,
                        session=session
                    )
                    logging.info(f"✅ Marked {refunded_count} SalesRecords as refunded for order {order_id}")
            except Exception as e:
                logging.error(f"❌ Failed to update SalesRecords for order {order_id}: {e}")
                # Don't fail cancellation if analytics update fails

        # STORE CANCELLATION REASON (if provided)
        if custom_reason:
            await OrderRepository.update_cancellation_reason(order_id, custom_reason, session)
            logging.info(f"📝 Stored cancellation reason for order {order_id}: '{custom_reason[:50]}...'")
            # Will be committed with transaction at the end

        # STORE REFUND BREAKDOWN (for mixed orders display)
        import json
        order_update = await OrderRepository.get_by_id(order_id, session)
        order_update.refund_breakdown_json = json.dumps(partial_refund_info)
        await OrderRepository.update(order_update, session)
        logging.info(f"💾 Stored refund breakdown for order {order_id} (is_mixed={partial_refund_info['is_mixed_order']})")

        # MARK INVOICES AS INACTIVE (soft delete for audit trail)
        if invoices:
            for invoice in invoices:
                await InvoiceRepository.mark_as_inactive(invoice.id, session)
            logging.info(f"🗑️ Marked {len(invoices)} invoice(s) as inactive for order {order_id}")

        # RELEASE ITEMS AND RESTORE STOCK
        items = await ItemRepository.get_by_order_id(order_id, session)

        # Group items by subcategory and price for stock restoration
        from collections import defaultdict
        items_by_type = defaultdict(list)
        for item in items:
            key = (item.subcategory_id, item.category_id, item.price, item.description)
            items_by_type[key].append(item)

        # For each item type, restore stock by setting is_sold=false
        for (subcategory_id, category_id, price, description), cancelled_items in items_by_type.items():
            qty_needed = len(cancelled_items)

            # First, try to restore existing sold items (is_sold=true) back to available
            sold_items = await ItemRepository.get_sold_items_by_subcategory(
                subcategory_id=subcategory_id,
                category_id=category_id,
                price=price,
                limit=qty_needed,
                session=session
            )

            # Restore sold items to available stock
            for item in sold_items:
                item.is_sold = False
                item.order_id = None

            if sold_items:
                await ItemRepository.update(sold_items, session)

            # If we couldn't find enough sold items (e.g., after DB cleanup),
            # create new items to maintain stock integrity
            shortage = qty_needed - len(sold_items)
            if shortage > 0:
                logging.warning(
                    f"Stock shortage detected for subcategory {subcategory_id}: "
                    f"needed {qty_needed}, found {len(sold_items)} sold items. "
                    f"Creating {shortage} new items."
                )
                # Note: We don't create new items automatically as we don't have private_data.
                # This should be handled manually by admin or through a separate stock management system.
                # For now, just log the shortage.

        # Clean up the cancelled order items (remove reservation AND restore to stock)
        # CRITICAL: Do NOT restore digital items if order was PAID (they were already delivered)
        items_to_restore = []
        items_kept_sold = []

        for item in items:
            item.order_id = None  # Always clear order_id

            # Only restore item to stock if:
            # 1. Physical item (always restorable) OR
            # 2. Digital item AND order was NOT yet paid (not delivered)
            if item.is_physical or order.status not in [OrderStatus.PAID, OrderStatus.PAID_AWAITING_SHIPMENT]:
                item.is_sold = False  # Restore to stock
                items_to_restore.append(item)
            else:
                # Digital item, order was PAID -> keep as sold (already delivered)
                items_kept_sold.append(item)

        await ItemRepository.update(items, session)

        logging.info(
            f"✅ Released {len(items_to_restore)} items back to stock for order {order_id} "
            f"({len(items_kept_sold)} digital items kept as sold - already delivered)"
        )

        # SEND NOTIFICATIONS (only after successful item release)
        if 'wallet_refund' in notification_messages:
            await NotificationService.send_to_user(notification_messages['wallet_refund'], user.telegram_id)
        elif 'strike_only' in notification_messages:
            await NotificationService.send_to_user(notification_messages['strike_only'], user.telegram_id)
        elif 'admin_cancel' in notification_messages:
            await NotificationService.send_to_user(notification_messages['admin_cancel'], user.telegram_id)

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

    @staticmethod
    async def reenter_shipping_address(
        callback: CallbackQuery,
        session: AsyncSession | Session,
        state=None
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Level 2: Re-enter Shipping Address

        User clicked cancel on address confirmation screen.
        Restart address input process.

        Returns:
            Tuple of (message, keyboard) with cancel button
        """
        from handlers.user.shipping_states import ShippingAddressStates

        # Get order_id from FSM
        order_id = None
        if state:
            state_data = await state.get_data()
            order_id = state_data.get("order_id")

            # Set FSM state to waiting for address
            await state.set_state(ShippingAddressStates.waiting_for_address)

        # Build keyboard with cancel button
        kb_builder = InlineKeyboardBuilder()
        if order_id:
            kb_builder.button(
                text=Localizator.get_text(BotEntity.USER, "cancel_order"),
                callback_data=OrderCallback.create(level=4, order_id=order_id)  # Level 4 = Cancel Order
            )

        # Return prompt message with keyboard
        message = Localizator.get_text(BotEntity.USER, "shipping_address_request").format(
            retention_days=config.DATA_RETENTION_DAYS
        )
        return message, kb_builder

    @staticmethod
    async def confirm_shipping_address(
        callback: CallbackQuery,
        session: AsyncSession | Session,
        state=None
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Level 6: Shipping Address Confirmation

        Saves shipping address and updates order status.
        Then redirects to Level 4 (Payment Processing).

        Flow:
        1. Get order_id from FSM
        2. Get shipping_address from FSM
        3. Save encrypted address
        4. Update status: PENDING_PAYMENT_AND_ADDRESS → PENDING_PAYMENT
        5. Clear FSM state (address collection done)
        6. Redirect to Level 4 with "Continue" button

        Args:
            callback: Callback query
            session: Database session
            state: FSM context

        Returns:
            Tuple of (message, keyboard)
        """
        from services.shipping import ShippingService

        # Get order_id and address from FSM
        if not state:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=OrderCallback.create(0)
            )
            return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

        state_data = await state.get_data()
        order_id = state_data.get("order_id")
        shipping_address = state_data.get("shipping_address")

        # Check: Order ID missing (technical error)?
        if not order_id:
            # FSM state lost - back to cart (no order to cancel)
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=OrderCallback.create(0)
            )
            return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

        # Check: Shipping address missing?
        if not shipping_address:
            # Restart address collection - user must enter text
            from handlers.user.shipping_states import ShippingAddressStates
            await state.set_state(ShippingAddressStates.waiting_for_address)

            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.USER, "cancel_order"),
                callback_data=OrderCallback.create(level=4, order_id=order_id)  # Level 4 = Cancel with strike logic
            )

            return Localizator.get_text(BotEntity.USER, "shipping_address_missing").format(
                retention_days=config.DATA_RETENTION_DAYS
            ), kb_builder

        # Get order
        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=OrderCallback.create(0)
            )
            return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

        # Save encrypted shipping address
        await ShippingService.save_shipping_address(order_id, shipping_address, session)

        # Update order status: PENDING_PAYMENT_AND_ADDRESS → PENDING_PAYMENT
        await OrderRepository.update_status(order_id, OrderStatus.PENDING_PAYMENT, session)
        await session_commit(session)

        # Keep order_id in state for payment processing
        # State will be cleared after successful payment

        # Store order_id in FSM state so process_payment can retrieve it
        if state:
            await state.update_data(order_id=order_id)

        # Check if shipping upgrade available
        from services.shipping_upsell import ShippingUpsellService
        upgrade = ShippingUpsellService.get_upgrade_for_shipping_type(order.shipping_type_key)

        if upgrade:
            # Show upsell screen directly
            return await OrderService.show_shipping_upsell_screen(order_id, session)
        else:
            # No upgrade available - directly to payment
            from handlers.user.order import process_payment
            kwargs = {"callback": callback, "session": session, "state": state}
            return await process_payment(**kwargs)

    @staticmethod
    async def show_shipping_upsell_screen(
        order_id: int,
        session: AsyncSession | Session
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Level 7: Show Shipping Upsell Screen

        Display shipping upgrade option if available for the current shipping type.

        Flow:
        1. Get order
        2. Get base shipping_type_key from order
        3. Get upgrade via ShippingUpsellService.get_upgrade_for_shipping_type()
        4. If no upgrade: Return "no upgrade" message + button to Level 8
        5. Build message with base + upgrade details
        6. Return message + keyboard

        Args:
            order_id: ID of the order
            session: Database session

        Returns:
            Tuple of (message_text, keyboard_builder)
        """
        from services.shipping_upsell import ShippingUpsellService

        # Get order
        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=OrderCallback.create(0)
            )
            return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

        # Get base shipping details
        base_shipping_key = order.shipping_type_key
        base_details = ShippingUpsellService.get_shipping_type_details(base_shipping_key)

        if not base_details:
            # Fallback if shipping type not found in config
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "continue"),
                callback_data=OrderCallback.create(level=8, order_id=order_id)
            )
            return Localizator.get_text(BotEntity.USER, "shipping_upsell_no_upgrade"), kb_builder

        # Get upgrade option
        # NOTE: Caller (show_shipping_upsell handler) checks for upgrade availability
        # before calling this method, so we can safely assume upgrade exists here
        upgrade = ShippingUpsellService.get_upgrade_for_shipping_type(base_shipping_key)

        if not upgrade:
            # This should never happen - caller checks first
            # Fallback to prevent crashes
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "continue"),
                callback_data=OrderCallback.create(level=8, order_id=order_id)
            )
            return Localizator.get_text(BotEntity.USER, "shipping_upsell_no_upgrade"), kb_builder

        # Build message with base + upgrade details
        from utils.html_escape import safe_html
        currency_sym = "€" if order.currency.value == "EUR" else order.currency.value

        message_text = Localizator.get_text(BotEntity.USER, "shipping_upsell_title")
        message_text += "\n\n"
        message_text += Localizator.get_text(BotEntity.USER, "shipping_upsell_base").format(
            shipping_name=safe_html(base_details["name"]),
            currency_sym=currency_sym,
            base_cost=base_details["charged_cost"]
        )
        message_text += Localizator.get_text(BotEntity.USER, "shipping_upsell_upgrade").format(
            upgrade_name=safe_html(upgrade["name"]),
            currency_sym=currency_sym,
            delta_cost=upgrade["delta_cost"],
            upgrade_description=safe_html(upgrade.get("description", ""))
        )

        # Build keyboard
        kb_builder = InlineKeyboardBuilder()

        # Button 1: Upgrade wählen (triggers Level 7 again with shipping_type_key)
        kb_builder.button(
            text=Localizator.get_text(BotEntity.USER, "shipping_upsell_upgrade_button").format(
                currency_sym=currency_sym,
                delta_cost=upgrade["delta_cost"]
            ),
            callback_data=OrderCallback.create(
                level=7,
                order_id=order_id,
                shipping_type_key=upgrade["target"]
            )
        )

        # Button 2: Weiter ohne Upgrade
        kb_builder.button(
            text=Localizator.get_text(BotEntity.USER, "shipping_upsell_skip_button"),
            callback_data=OrderCallback.create(level=8, order_id=order_id)
        )

        kb_builder.adjust(1)  # Stack buttons vertically

        return message_text, kb_builder

    @staticmethod
    async def show_stock_adjustment_confirmation(
        callback: CallbackQuery,
        order: OrderDTO,
        stock_adjustments: list[dict],
        session: AsyncSession | Session
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Shows confirmation screen when stock was adjusted during order creation.
        Displays complete order overview with strike-through for adjusted items.
        """
        from repositories.item import ItemRepository
        from repositories.subcategory import SubcategoryRepository

        # Get order items to build complete overview
        order_items = await ItemRepository.get_by_order_id(order.id, session)

        # Build adjustment map for quick lookup
        adjustment_map = {}
        for adj in stock_adjustments:
            adjustment_map[adj['subcategory_id']] = {
                'requested': adj['requested'],
                'reserved': adj['reserved'],
                'name': adj['subcategory_name']
            }

        # Build items list with strike-through for adjustments
        items_dict = {}
        for item in order_items:
            subcategory = await SubcategoryRepository.get_by_id(item.subcategory_id, session)
            key = (item.subcategory_id, subcategory.name, item.price)
            items_dict[key] = items_dict.get(key, 0) + 1

        items_list = ""
        subtotal = 0.0
        displayed_subcategories = set()

        # First, show all items that were reserved (including partial)
        for (subcategory_id, name, price), qty in items_dict.items():
            line_total = price * qty
            displayed_subcategories.add(subcategory_id)

            if subcategory_id in adjustment_map:
                adj = adjustment_map[subcategory_id]
                # Partial stock - show original crossed out, then actual
                items_list += f"<s>{adj['requested']}x</s> → {qty}x {name} ⚠️\n"
                items_list += f"  {Localizator.get_currency_symbol()}{price:.2f} × {qty}{' ' * (20 - len(name))}{Localizator.get_currency_symbol()}{line_total:.2f}\n"
                subtotal += line_total
            else:
                # No adjustment - normal display
                items_list += f"{qty}x {name}\n"
                items_list += f"  {Localizator.get_currency_symbol()}{price:.2f} × {qty}{' ' * (20 - len(name))}{Localizator.get_currency_symbol()}{line_total:.2f}\n"
                subtotal += line_total

        # Now add completely sold out items (reserved=0) from adjustments
        for subcategory_id, adj in adjustment_map.items():
            if adj['reserved'] == 0 and subcategory_id not in displayed_subcategories:
                # Completely sold out - strike through
                items_list += f"<s>{adj['requested']}x {adj['name']}</s> ❌\n"
                items_list += f"  <i>Ausverkauft (entfernt)</i>\n"

        # Shipping line
        shipping_line = ""
        if order.shipping_cost > 0:
            shipping_line = f"Shipping{' ' * 18}{Localizator.get_currency_symbol()}{order.shipping_cost:.2f}\n"

        # Calculate spacing
        subtotal_spacing = " " * 18
        total_spacing = " " * 23

        # Build message
        message_text = f"⚠️ <b>STOCK ADJUSTMENT</b>\n\n"
        message_text += f"Some items are no longer available in the\nrequested quantity:\n\n"
        message_text += f"<b>ITEMS</b>\n"
        message_text += f"─────────────────────────────\n"
        message_text += items_list
        message_text += f"─────────────────────────────\n"
        message_text += f"Subtotal{subtotal_spacing}{Localizator.get_currency_symbol()}{subtotal:.2f}\n"
        message_text += shipping_line
        message_text += f"─────────────────────────────\n"
        message_text += f"<b>TOTAL{total_spacing}{Localizator.get_currency_symbol()}{order.total_price:.2f}</b>\n\n"
        message_text += f"<i>Continue with adjusted order?</i>"

        # Buttons
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text="✅ Continue Payment",
            callback_data=OrderCallback.create(9, order_id=order.id)  # Level 9 = Confirm adjusted order
        )
        kb_builder.button(
            text="❌ Cancel Order",
            callback_data=OrderCallback.create(level=4, order_id=order.id)  # Level 4 = Cancel order
        )

        return message_text, kb_builder

    @staticmethod
    async def reshow_stock_adjustment(
        callback: CallbackQuery,
        session: AsyncSession | Session,
        state=None
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Level 6: Re-show Stock Adjustment Screen

        Called when user clicks Back from cancel confirmation dialog.
        Reloads stock adjustments from FSM state and displays adjustment screen again.
        """
        import json

        unpacked_cb = OrderCallback.unpack(callback.data)
        order_id = unpacked_cb.order_id

        if not order_id:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.row(CartCallback.create(0).get_back_button(0))
            return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

        # Get order
        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.row(CartCallback.create(0).get_back_button(0))
            return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

        # Get stock adjustments from FSM state
        stock_adjustments = []
        if state:
            state_data = await state.get_data()
            adjustments_json = state_data.get("stock_adjustments")
            if adjustments_json:
                stock_adjustments = json.loads(adjustments_json)

        # Show stock adjustment screen again
        return await OrderService.show_stock_adjustment_confirmation(
            callback, order, stock_adjustments, session
        )

    @staticmethod
    async def confirm_adjusted_order(
        callback: CallbackQuery,
        session: AsyncSession | Session,
        state=None
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Level 9: Stock Adjustment Confirmation

        User confirms order with adjusted quantities.
        Clears cart and redirects to next step based on order status.

        Flow:
        1. Get order from callback
        2. Clear cart (remove sold-out items, keep rest for potential reorder)
        3. Check order status
        4. Fork based on status:
           - PENDING_PAYMENT_AND_ADDRESS → Level 6 (Shipping Address)
           - PENDING_PAYMENT → Level 4 (Payment Processing)

        Args:
            callback: Callback query
            session: Database session
            state: FSM context

        Returns:
            Tuple of (message, keyboard)
        """
        unpacked_cb = OrderCallback.unpack(callback.data)
        order_id = unpacked_cb.order_id

        if not order_id:
            # No order ID - back to cart
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=OrderCallback.create(0)
            )
            return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

        # Get order
        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=OrderCallback.create(0)
            )
            return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

        # Clear cart items that were processed in this order
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)
        cart_items = await CartItemRepository.get_all_by_user_id(user.id, session)

        # Get order items to see what was actually reserved
        from repositories.item import ItemRepository
        order_items = await ItemRepository.get_by_order_id(order_id, session)

        # Build map of what was reserved per subcategory
        reserved_by_subcategory = {}
        for item in order_items:
            subcategory_id = item.subcategory_id
            reserved_by_subcategory[subcategory_id] = reserved_by_subcategory.get(subcategory_id, 0) + 1

        # Remove cart items that were fully processed or sold out
        for cart_item in cart_items:
            reserved = reserved_by_subcategory.get(cart_item.subcategory_id, 0)
            if reserved == 0:
                # Item was sold out - remove from cart
                await CartItemRepository.remove_from_cart(cart_item.id, session)
            elif reserved < cart_item.quantity:
                # Partial stock - remove from cart (user can re-add if desired)
                await CartItemRepository.remove_from_cart(cart_item.id, session)
            else:
                # Full quantity was reserved - remove from cart
                await CartItemRepository.remove_from_cart(cart_item.id, session)

        await session_commit(session)

        # Fork based on order status
        kb_builder = InlineKeyboardBuilder()

        if order.status == OrderStatus.PENDING_PAYMENT_AND_ADDRESS:
            # Physical items → Collect shipping address
            if state:
                from handlers.user.shipping_states import ShippingAddressStates
                await state.set_state(ShippingAddressStates.waiting_for_address)

            kb_builder.button(
                text=Localizator.get_text(BotEntity.USER, "cancel_order"),
                callback_data=OrderCallback.create(level=4, order_id=order_id)  # Level 4 = Cancel
            )

            message_text = Localizator.get_text(BotEntity.USER, "shipping_address_request").format(
                retention_days=config.DATA_RETENTION_DAYS
            )

        elif order.status == OrderStatus.PENDING_PAYMENT:
            # Digital items → Proceed to payment
            # Directly call process_payment to show order details or crypto selection
            return await OrderService.process_payment(callback, session, state)

        else:
            # Unexpected status - error
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=OrderCallback.create(0)
            )
            return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

        return message_text, kb_builder

    @staticmethod
    async def cancel_order_handler(
        callback: CallbackQuery,
        session: AsyncSession | Session,
        state=None
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Level 4: Show cancel confirmation dialog.
        Checks grace period and warns about penalties if applicable.
        Stores grace period status in FSM for 10 seconds to prevent race condition.
        """
        unpacked_cb = OrderCallback.unpack(callback.data)
        order_id = unpacked_cb.order_id

        kb_builder = InlineKeyboardBuilder()

        # Defensive check: Order ID must be set
        if order_id == -1:
            kb_builder.row(CartCallback.create(0).get_back_button(0))
            return "❌ <b>Error: Invalid Order ID</b>", kb_builder

        try:
            from datetime import datetime

            # Get order to check grace period
            order = await OrderRepository.get_by_id(order_id, session)

            if not order:
                kb_builder.row(CartCallback.create(0).get_back_button(0))
                return Localizator.get_text(BotEntity.USER, "order_not_found_error"), kb_builder

            # Check grace period
            time_elapsed = (datetime.utcnow() - order.created_at).total_seconds() / 60
            within_grace_period = time_elapsed <= config.ORDER_CANCEL_GRACE_PERIOD_MINUTES

            # Store grace period status and timestamp in FSM (valid for 10 seconds)
            if state:
                await state.update_data(
                    cancel_grace_status=within_grace_period,
                    cancel_grace_timestamp=datetime.utcnow().timestamp()
                )

            # Build confirmation message based on grace period and wallet usage
            if within_grace_period:
                message_text = Localizator.get_text(BotEntity.USER, "cancel_order_confirm_free").format(
                    grace_period=config.ORDER_CANCEL_GRACE_PERIOD_MINUTES
                )
            else:
                # Grace period expired - warn about penalty
                if order.wallet_used > 0:
                    # Wallet was used - warn about both strike and fee
                    message_text = Localizator.get_text(BotEntity.USER, "cancel_order_confirm_penalty_with_fee").format(
                        grace_period=config.ORDER_CANCEL_GRACE_PERIOD_MINUTES,
                        penalty_percent=config.PAYMENT_LATE_PENALTY_PERCENT,
                        currency_sym=Localizator.get_currency_symbol()
                    )
                else:
                    # No wallet used - warn about strike only
                    message_text = Localizator.get_text(BotEntity.USER, "cancel_order_confirm_penalty_no_fee").format(
                        grace_period=config.ORDER_CANCEL_GRACE_PERIOD_MINUTES
                    )

            # Buttons: Confirm or Go Back
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "confirm"),
                callback_data=OrderCallback.create(level=5, order_id=order_id)  # Level 5 = Execute cancellation
            )

            # Determine where Back button should go based on order status
            has_stock_adjustment = False
            if state:
                state_data = await state.get_data()
                has_stock_adjustment = "stock_adjustments" in state_data

            if has_stock_adjustment:
                # Back to stock adjustment screen
                kb_builder.button(
                    text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                    callback_data=OrderCallback.create(level=6, order_id=order_id)  # Level 6 = Re-show stock adjustment
                )
            elif order.status == OrderStatus.PENDING_PAYMENT_AND_ADDRESS:
                # Back to address input (don't go to payment - would finalize order without address!)
                kb_builder.button(
                    text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                    callback_data=OrderCallback.create(level=2, order_id=order_id)  # Level 2 = Re-enter address
                )
            else:
                # Back to payment screen (order already has address or no physical items)
                kb_builder.button(
                    text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                    callback_data=OrderCallback.create(level=3, order_id=order_id)  # Level 3 = Payment screen
                )

            return message_text, kb_builder

        except Exception as e:
            # Order not found or error checking status
            kb_builder.row(CartCallback.create(0).get_back_button(0))
            return f"❌ <b>Error:</b> {str(e)}", kb_builder

    @staticmethod
    async def execute_cancel_order(
        callback: CallbackQuery,
        session: AsyncSession | Session,
        state=None
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Level 5: Execute order cancellation after user confirmation.
        Uses stored grace period status if < 10 seconds old, otherwise recalculates.
        """
        from datetime import datetime

        unpacked_cb = OrderCallback.unpack(callback.data)
        order_id = unpacked_cb.order_id

        kb_builder = InlineKeyboardBuilder()

        # Defensive check: Order ID must be set
        if order_id == -1:
            kb_builder.row(CartCallback.create(0).get_back_button(0))
            return "❌ <b>Error: Invalid Order ID</b>", kb_builder

        try:
            # Get user to clear cart
            user = await UserRepository.get_by_tgid(callback.from_user.id, session)

            # Check if we have stored grace period status (from Level 4)
            use_stored_status = False
            stored_grace_status = False

            if state:
                state_data = await state.get_data()
                stored_grace_status = state_data.get("cancel_grace_status", False)
                stored_timestamp = state_data.get("cancel_grace_timestamp")

                # If stored timestamp exists and is < 10 seconds old, use stored status
                if stored_timestamp:
                    time_since_stored = datetime.utcnow().timestamp() - stored_timestamp
                    if time_since_stored < 10:  # 10 seconds grace period for confirmation
                        use_stored_status = True

            # Cancel order (will calculate grace period internally)
            within_grace_period, msg = await OrderService.cancel_order_by_user(
                order_id=order_id,
                session=session
            )

            # Override with stored status if within 10 second window
            if use_stored_status:
                within_grace_period = stored_grace_status

            # Clear cart (order was cancelled, items are back in stock)
            cart_items = await CartItemRepository.get_all_by_user_id(user.id, session)
            for cart_item in cart_items:
                await CartItemRepository.remove_from_cart(cart_item.id, session)

            # Get invoice for logging
            from repositories.invoice import InvoiceRepository
            invoices_commit = await InvoiceRepository.get_all_by_order_id(order_id, session)
            invoice_commit_log = invoices_commit[0].invoice_number if invoices_commit else "N/A"

            # Commit changes (wallet refund, order status update, item release, cart clearing)
            logging.info(f"💾 COMMITTING: Order {order_id} (Invoice: {invoice_commit_log}) cancellation, wallet refund, and cart clearing")
            await session_commit(session)
            logging.info(f"✅ COMMIT SUCCESS: Order {order_id} (Invoice: {invoice_commit_log}) cancellation complete")

            # Clear FSM state
            if state:
                await state.clear()

            # Display appropriate message
            if within_grace_period:
                message_text = Localizator.get_text(BotEntity.USER, "order_cancelled_free")
            else:
                message_text = Localizator.get_text(BotEntity.USER, "order_cancelled_with_strike").format(
                    grace_period=config.ORDER_CANCEL_GRACE_PERIOD_MINUTES
                )

            # Back to cart button
            kb_builder.row(CartCallback.create(0).get_back_button(0))

            return message_text, kb_builder

        except ValueError as e:
            # Order not found or cannot be cancelled
            kb_builder.row(CartCallback.create(0).get_back_button(0))
            return f"❌ <b>Error:</b> {str(e)}", kb_builder

    # ========================================
    # Private Helper Methods
    # ========================================

    @staticmethod
    async def _format_payment_screen(
        invoice,
        order,
        session: AsyncSession | Session
    ) -> str:
        """
        Formats payment screen with invoice details and wallet usage.

        Args:
            invoice: Invoice DTO
            order: Order DTO
            session: Database session

        Returns:
            Formatted message string
        """
        from repositories.item import ItemRepository
        from repositories.subcategory import SubcategoryRepository
        from services.invoice_formatter import InvoiceFormatterService

        # Get order items
        order_items = await ItemRepository.get_by_order_id(order.id, session)

        # Parse tier breakdown from order (NO recalculation!)
        tier_breakdown_list = OrderService._parse_tier_breakdown_from_order(order)

        # Get subcategory information
        subcategory_ids = list({item.subcategory_id for item in order_items})
        subcategories_dict = await SubcategoryRepository.get_by_ids(subcategory_ids, session)

        # Fallback: If tier_breakdown_json not available (old orders), recalculate
        if not tier_breakdown_list:
            logging.warning(f"Order {order.id} has no tier_breakdown_json, falling back to recalculation")
            tier_breakdown_list = await OrderService._group_items_with_tier_pricing(
                order_items, subcategories_dict, session
            )

        # Build items list with tier_breakdown
        items_raw = []
        for item in order_items:
            # Find corresponding tier breakdown from tier_breakdown_list
            tier_breakdown = None
            for tier_item in tier_breakdown_list:
                subcategory = subcategories_dict.get(item.subcategory_id)
                if subcategory and tier_item['subcategory_name'] == subcategory.name:
                    tier_breakdown = tier_item.get('breakdown')
                    break

            items_raw.append({
                'name': item.description,
                'price': item.price,
                'quantity': 1,  # Each item is already individual
                'is_physical': item.is_physical,
                'private_data': None,  # Don't include private_data in payment screen (not paid yet)
                'tier_breakdown': tier_breakdown
            })

        # Group items by (name, price, is_physical) - private_data excluded for aggregation
        items_list = OrderService._group_items_for_display(items_raw)

        # Format crypto amount with currency
        crypto_amount_display = f"{invoice.payment_amount_crypto} {invoice.payment_crypto_currency.value}"

        return InvoiceFormatterService.format_complete_order_view(
            header_type="payment_screen",
            invoice_number=invoice.invoice_number,
            expires_at=order.expires_at,
            items=items_list,
            shipping_cost=order.shipping_cost,
            total_price=order.total_price,
            wallet_used=order.wallet_used,
            crypto_payment_needed=invoice.fiat_amount,
            payment_address=invoice.payment_address,
            payment_amount_crypto=crypto_amount_display,
            use_spacing_alignment=True,
            separate_digital_physical=True,  # Always use separated view
            show_private_data=False,  # Don't show keys before payment
            currency_symbol=Localizator.get_currency_symbol(),
            entity=BotEntity.USER
        )

    @staticmethod
    async def _calculate_order_totals(
        cart_items: list[CartItemDTO],
        session: AsyncSession | Session
    ) -> tuple[float, float, str, str]:
        """
        Calculate order totals: item prices + max shipping cost.
        Also builds tier_breakdown_json for historical accuracy.

        Args:
            cart_items: List of cart items
            session: Database session

        Returns:
            Tuple of (total_price_with_shipping, max_shipping_cost, tier_breakdown_json, shipping_type_key)
        """
        from repositories.subcategory import SubcategoryRepository

        total_price = 0.0
        max_shipping_cost = 0.0  # Use MAX shipping cost, not SUM!
        tier_breakdown_list = []  # List of tier breakdowns for JSON

        for cart_item in cart_items:
            # Get subcategory info for tier breakdown
            subcategory = await SubcategoryRepository.get_by_id(cart_item.subcategory_id, session)

            # SECURITY: Always recompute tier pricing server-side, never trust cart data
            # This prevents price manipulation via direct database access or session tampering
            from services.pricing import PricingService

            try:
                # Attempt to calculate tier pricing
                pricing_result = await PricingService.calculate_optimal_price(
                    subcategory_id=cart_item.subcategory_id,
                    quantity=cart_item.quantity,
                    session=session
                )

                item_total = pricing_result.total

                # CRITICAL: If pricing returns 0, this indicates missing price configuration
                if item_total == 0:
                    raise ValueError(f"Pricing returned 0 for subcategory {cart_item.subcategory_id} - missing price tiers or item.price = 0")

                average_unit_price = pricing_result.average_unit_price
                breakdown = [
                    {
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                        'total': item.total
                    }
                    for item in pricing_result.breakdown
                ]

                total_price += item_total

                # Add to tier breakdown list for JSON storage
                tier_breakdown_list.append({
                    'subcategory_id': cart_item.subcategory_id,
                    'subcategory_name': subcategory.name if subcategory else 'Unknown',
                    'quantity': cart_item.quantity,
                    'total': item_total,
                    'average_unit_price': average_unit_price,
                    'breakdown': breakdown
                })

                logging.debug(f"Computed tier price for {cart_item.subcategory_id}: {item_total:.2f} EUR")

            except Exception as e:
                # CRITICAL ERROR: Cannot determine price for cart item
                logging.error(
                    f"❌ CRITICAL: Cannot calculate price for cart_item {cart_item.id} "
                    f"(subcategory {cart_item.subcategory_id}): {e}"
                )
                # Re-raise exception - order creation should FAIL if we can't determine prices
                raise ValueError(
                    f"Cannot create order - missing price configuration for subcategory {cart_item.subcategory_id}. "
                    f"Please configure price_tiers or set item.price > 0"
                ) from e

        # Calculate shipping using tiered shipping system (not legacy flat shipping_cost)
        from services.cart_shipping import CartShippingService

        max_shipping_cost = await CartShippingService.get_max_shipping_cost(cart_items, session)

        # Determine shipping_type_key from max-cost shipping method
        shipping_results = await CartShippingService.calculate_shipping_for_cart(cart_items, session)
        shipping_type_key = "paeckchen"  # Default fallback

        if shipping_results:
            # Find shipping method with priority logic:
            # 1. Highest charged_cost (what customer pays)
            # 2. If tied, highest real_cost (larger package = correct upgrades)
            max_cost_result = None
            max_charged_cost = 0.0
            for result in shipping_results.values():
                if result.charged_cost > max_charged_cost:
                    # Clear winner - higher charged cost
                    max_charged_cost = result.charged_cost
                    max_cost_result = result
                elif result.charged_cost == max_charged_cost:
                    # Tie in charged_cost - use real_cost as tiebreaker
                    if max_cost_result is None or result.real_cost > max_cost_result.real_cost:
                        max_cost_result = result

            if max_cost_result:
                shipping_type_key = max_cost_result.shipping_type_key
                logging.info(f"🚚 Selected shipping type: {shipping_type_key} (charged: €{max_cost_result.charged_cost:.2f}, real: €{max_cost_result.real_cost:.2f})")

        # Add shipping cost to total
        total_price_with_shipping = total_price + max_shipping_cost

        # Serialize tier breakdown to JSON
        import json
        tier_breakdown_json = json.dumps(tier_breakdown_list) if tier_breakdown_list else None

        logging.info(
            f"📦 Order totals: Items={total_price:.2f} EUR | "
            f"Shipping={max_shipping_cost:.2f} EUR (MAX, type={shipping_type_key}) | "
            f"Total={total_price_with_shipping:.2f} EUR"
        )

        return total_price_with_shipping, max_shipping_cost, tier_breakdown_json, shipping_type_key

    @staticmethod
    async def _reserve_items_with_adjustments(
        cart_items: list[CartItemDTO],
        order_id: int,
        session: AsyncSession | Session
    ) -> tuple[list, list[dict]]:
        """
        Reserve items for order and track stock adjustments.

        Args:
            cart_items: List of cart items
            order_id: Order ID
            session: Database session

        Returns:
            Tuple of (reserved_items, stock_adjustments)
            - reserved_items: List of reserved Item objects
            - stock_adjustments: List of adjustment dicts with subcategory info

        Raises:
            ValueError: If all items are out of stock
        """
        from repositories.subcategory import SubcategoryRepository

        reserved_items = []
        stock_adjustments = []

        for cart_item in cart_items:
            reserved, requested = await ItemRepository.reserve_items_for_order(
                cart_item.subcategory_id,
                cart_item.quantity,
                order_id,
                session
            )

            # Track if quantity changed
            if len(reserved) != requested:
                subcategory = await SubcategoryRepository.get_by_id(cart_item.subcategory_id, session)
                stock_adjustments.append({
                    'subcategory_id': cart_item.subcategory_id,
                    'subcategory_name': subcategory.name,
                    'requested': requested,
                    'reserved': len(reserved)
                })
                logging.warning(
                    f"⚠️ Stock adjustment: {subcategory.name} - "
                    f"Requested: {requested}, Reserved: {len(reserved)}"
                )

            reserved_items.extend(reserved)

        # Check: All items out of stock?
        if not reserved_items:
            await OrderRepository.update_status(order_id, OrderStatus.CANCELLED_BY_SYSTEM, session)
            logging.error(f"❌ Order {order_id} cancelled - all items out of stock")
            raise ValueError("All items are out of stock")

        return reserved_items, stock_adjustments

    @staticmethod
    def _detect_physical_items(reserved_items: list) -> bool:
        """
        Detect if order contains physical items requiring shipment.

        Args:
            reserved_items: List of reserved Item objects

        Returns:
            True if any item is physical, False otherwise
        """
        return any(item.is_physical for item in reserved_items)

    @staticmethod
    async def _format_wallet_payment_invoice(
        invoice,
        order,
        session: AsyncSession | Session
    ) -> str:
        """
        Format invoice for wallet-only payment (order completed).
        Shows different delivery status for physical vs digital items.

        Returns:
            Formatted invoice message
        """
        from repositories.item import ItemRepository
        from repositories.subcategory import SubcategoryRepository
        from services.invoice_formatter import InvoiceFormatterService

        # Get order items
        order_items = await ItemRepository.get_by_order_id(order.id, session)

        # Check if order contains physical and/or digital items
        has_physical_items = any(item.is_physical for item in order_items)
        has_digital_items = any(not item.is_physical for item in order_items)
        is_mixed_order = has_physical_items and has_digital_items

        # Parse tier breakdown from order (NO recalculation!)
        tier_breakdown_list = OrderService._parse_tier_breakdown_from_order(order)

        # Batch-load all subcategories (eliminates N+1 queries)
        subcategory_ids = list({item.subcategory_id for item in order_items})
        subcategories_dict = await SubcategoryRepository.get_by_ids(subcategory_ids, session)

        # Fallback: If tier_breakdown_json not available (old orders), recalculate
        if not tier_breakdown_list:
            logging.warning(f"Order {order.id} has no tier_breakdown_json, falling back to recalculation")
            tier_breakdown_list = await OrderService._group_items_with_tier_pricing(
                order_items, subcategories_dict, session
            )

        # Build items list with private_data (ungrouped for individual keys/codes)
        items_raw = []
        for item in order_items:
            # Find corresponding tier breakdown from tier_breakdown_list
            tier_breakdown = None
            for tier_item in tier_breakdown_list:
                subcategory = subcategories_dict.get(item.subcategory_id)
                if subcategory and tier_item['subcategory_name'] == subcategory.name:
                    tier_breakdown = tier_item.get('breakdown')
                    break

            items_raw.append({
                'name': subcategories_dict[item.subcategory_id].name if item.subcategory_id in subcategories_dict else 'Unknown',
                'price': item.price,  # Keep for fallback, but tier_breakdown takes precedence
                'quantity': 1,
                'is_physical': item.is_physical,
                'private_data': item.private_data,
                'tier_breakdown': tier_breakdown if not item.private_data else None  # Don't show tier breakdown for individual items with codes
            })

        # Group items by (name, price, is_physical, private_data) while preserving tier_breakdown
        items_list = OrderService._group_items_for_display(items_raw)

        # Choose footer based on item type
        if has_physical_items:
            footer_text = Localizator.get_text(BotEntity.USER, "order_completed_wallet_only_physical_footer")
        else:
            footer_text = Localizator.get_text(BotEntity.USER, "order_completed_wallet_only_digital_footer")

        # Get shipping type name for display
        shipping_type_name = None
        if order.shipping_type_key:
            from utils.shipping_types_loader import load_shipping_types, get_shipping_type
            try:
                shipping_types = load_shipping_types("de")
                shipping_type = get_shipping_type(shipping_types, order.shipping_type_key)
                if shipping_type:
                    shipping_type_name = shipping_type.get("name")
            except Exception:
                logging.warning(f"Failed to load shipping type for key: {order.shipping_type_key}")

        return InvoiceFormatterService.format_complete_order_view(
            header_type="wallet_payment",
            invoice_number=invoice.invoice_number,
            items=items_list,
            shipping_cost=order.shipping_cost,
            shipping_type_name=shipping_type_name,  # Pass shipping type name for display
            total_price=order.total_price,
            wallet_used=order.wallet_used,  # Use actual wallet amount from order, not invoice
            use_spacing_alignment=True,
            separate_digital_physical=True,  # Always use separated view
            show_private_data=True,  # Show keys/codes immediately after wallet payment
            show_retention_notice=True,  # Show data retention notice
            currency_symbol=Localizator.get_currency_symbol(),
            footer_text=footer_text,
            entity=BotEntity.USER
        )

    @staticmethod
    def _parse_tier_breakdown_from_order(order: OrderDTO) -> list[dict] | None:
        """
        Parse tier_breakdown_json from order.

        This eliminates redundant tier pricing recalculations by using
        the stored breakdown from order creation.

        Args:
            order: OrderDTO with tier_breakdown_json field

        Returns:
            List of tier breakdown dicts or None if not available

        Example return format:
            [
                {
                    'subcategory_id': 8,
                    'subcategory_name': 'Schwarzer Tee',
                    'quantity': 30,
                    'total': 270.0,
                    'average_unit_price': 9.0,
                    'breakdown': [
                        {'quantity': 25, 'unit_price': 9.0, 'total': 225.0},
                        {'quantity': 5, 'unit_price': 9.0, 'total': 45.0}
                    ]
                },
                ...
            ]
        """
        if not order.tier_breakdown_json:
            return None

        import json
        try:
            return json.loads(order.tier_breakdown_json)
        except (json.JSONDecodeError, TypeError) as e:
            logging.warning(f"Failed to parse tier_breakdown_json for order {order.id}: {e}")
            return None

    @staticmethod
    async def _create_items_snapshot(order_id: int, session: AsyncSession | Session) -> str:
        """
        Create JSON snapshot of all items in an order for historical record.

        This snapshot preserves complete item details (description, price, quantity,
        is_physical, private_data) even after items are released back to stock on
        order cancellation.

        Args:
            order_id: Order ID
            session: Database session

        Returns:
            JSON string with item details

        Example format:
            [
                {
                    "description": "USB Stick 32GB",
                    "price": 10.0,
                    "quantity": 1,
                    "is_physical": true,
                    "private_data": "KEY-12345-ABCDE"
                },
                ...
            ]
        """
        from repositories.item import ItemRepository
        import json

        # Get all items for this order
        items = await ItemRepository.get_by_order_id(order_id, session)

        # Build snapshot list
        snapshot = []
        for item in items:
            snapshot.append({
                'description': item.description,
                'price': item.price,
                'quantity': 1,  # Each item is individual
                'is_physical': item.is_physical,
                'private_data': item.private_data,
                'subcategory_id': item.subcategory_id
            })

        return json.dumps(snapshot)

    @staticmethod
    async def _group_items_with_tier_pricing(
        order_items: list,
        subcategories_dict: dict,
        session: AsyncSession | Session
    ) -> list[dict]:
        """
        Group order items by subcategory and calculate tier pricing.

        DEPRECATED: This is a fallback for old orders without tier_breakdown_json.
        New orders should use _parse_tier_breakdown_from_order() instead.

        Args:
            order_items: List of Item objects from order
            subcategories_dict: Dict of {subcategory_id: SubcategoryDTO}
            session: Database session

        Returns:
            List of tier breakdown dicts (same format as _parse_tier_breakdown_from_order)
        """
        from services.pricing import PricingService
        from exceptions.item import TierPricingCalculationException, ItemNotFoundException
        from collections import defaultdict

        # Group items by subcategory
        items_by_subcategory = defaultdict(list)
        for item in order_items:
            items_by_subcategory[item.subcategory_id].append(item)

        # Build result list with tier pricing (same format as JSON)
        result = []
        for subcategory_id, items in items_by_subcategory.items():
            subcategory = subcategories_dict.get(subcategory_id)
            if not subcategory:
                continue

            quantity = len(items)
            sample_item = items[0]

            # Calculate tier pricing
            try:
                pricing_result = await PricingService.calculate_optimal_price(
                    subcategory_id=subcategory_id,
                    quantity=quantity,
                    session=session
                )

                breakdown = [
                    {
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                        'total': item.total
                    }
                    for item in pricing_result.breakdown
                ]

                # Return same format as _parse_tier_breakdown_from_order
                result.append({
                    'subcategory_id': subcategory_id,
                    'subcategory_name': subcategory.name,
                    'quantity': quantity,
                    'total': pricing_result.total,
                    'average_unit_price': pricing_result.average_unit_price,
                    'breakdown': breakdown
                })
            except (ItemNotFoundException, TierPricingCalculationException) as e:
                # Fallback to flat pricing if tier calculation fails
                logging.warning(f"Tier pricing failed for subcategory {subcategory_id}: {e}")
                # Still return entry but with None breakdown (will use flat pricing)
                result.append({
                    'subcategory_id': subcategory_id,
                    'subcategory_name': subcategory.name,
                    'quantity': quantity,
                    'total': sample_item.price * quantity,
                    'average_unit_price': sample_item.price,
                    'breakdown': None
                })

        return result

    @staticmethod
    def _group_items_for_display(items: list[dict]) -> list[dict]:
        """
        Group items for display based on (name, price, is_physical, private_data).

        Items with identical attributes (including private_data) are grouped together.
        Items with unique private_data remain separate.

        Args:
            items: List of item dicts with keys: name, price, quantity, is_physical, private_data, tier_breakdown (optional)

        Returns:
            List of grouped items with updated quantities
        """
        grouped = {}
        tier_breakdown_map = {}  # Store tier_breakdown for each group

        for item in items:
            # Group by all attributes including private_data
            # This ensures items with identical private_data get grouped,
            # but items with unique private_data (keys, codes) stay separate
            key = (
                item['name'],
                item['price'],
                item['is_physical'],
                item.get('private_data')  # None or actual value
            )

            if key not in grouped:
                grouped[key] = 0
                # Store tier_breakdown for first item in group
                tier_breakdown_map[key] = item.get('tier_breakdown')
            grouped[key] += item.get('quantity', 1)

        # Build result list
        return [
            {
                'name': name,
                'price': price,
                'quantity': quantity,
                'is_physical': is_physical,
                'private_data': private_data,
                'tier_breakdown': tier_breakdown_map.get((name, price, is_physical, private_data))
            }
            for (name, price, is_physical, private_data), quantity in grouped.items()
        ]

    @staticmethod
    async def _add_strike_and_check_ban(
        user_id: int,
        order_id: int,
        strike_type: StrikeType,
        session: AsyncSession | Session
    ):
        """
        Adds a strike to user and checks if ban threshold reached.

        Args:
            user_id: User ID
            order_id: Order ID that caused the strike
            strike_type: Type of strike (TIMEOUT, LATE_CANCEL, etc.)
            session: Database session
        """
        from models.user_strike import UserStrikeDTO
        from repositories.user_strike import UserStrikeRepository

        # Check if strike for this order already exists (prevent duplicates)
        existing_strikes = await UserStrikeRepository.get_by_order_id(order_id, session)
        if existing_strikes:
            logging.warning(f"⚠️ Strike for order {order_id} already exists - skipping duplicate")
            return

        # Create strike record
        strike_dto = UserStrikeDTO(
            user_id=user_id,
            order_id=order_id,
            strike_type=strike_type,
            reason=f"{strike_type.name} for order {order_id}"
        )
        await UserStrikeRepository.create(strike_dto, session)

        # Get actual strike count from DB (single source of truth)
        user = await UserRepository.get_by_id(user_id, session)
        strikes = await UserStrikeRepository.get_by_user_id(user_id, session)
        actual_strike_count = len(strikes)

        logging.info(f"⚠️ Strike added for user {user_id}: Total strikes = {actual_strike_count}")

        # Update user strike count field for consistency
        user.strike_count = actual_strike_count

        # Check if ban threshold reached (unless admin is exempt)
        from utils.permission_utils import is_admin_user
        admin_exempt = is_admin_user(user.telegram_id) and config.EXEMPT_ADMINS_FROM_BAN

        logging.info(f"🔍 Ban check for user {user_id}: strikes={actual_strike_count}, threshold={config.MAX_STRIKES_BEFORE_BAN}, admin_exempt={admin_exempt}, already_blocked={user.is_blocked}")

        # Check if user should be banned (only if not already banned)
        if actual_strike_count >= config.MAX_STRIKES_BEFORE_BAN and not admin_exempt and not user.is_blocked:
            # User just crossed ban threshold - ban and notify
            user.is_blocked = True
            user.blocked_at = datetime.utcnow()
            user.blocked_reason = f"Automatic ban: {actual_strike_count} strikes (threshold: {config.MAX_STRIKES_BEFORE_BAN})"
            logging.warning(f"🚫 User {user_id} BANNED: {actual_strike_count} strikes reached")

            # Send ban notifications (only once when ban happens)
            from services.notification import NotificationService
            await NotificationService.notify_user_banned(user, actual_strike_count)
            await NotificationService.notify_admin_user_banned(user, actual_strike_count)
        elif admin_exempt and actual_strike_count >= config.MAX_STRIKES_BEFORE_BAN:
            logging.warning(f"⚠️ Admin {user_id} (telegram_id: {user.telegram_id}) reached ban threshold ({actual_strike_count} strikes) but is exempt from ban (EXEMPT_ADMINS_FROM_BAN={config.EXEMPT_ADMINS_FROM_BAN})")
        else:
            logging.warning(f"⚠️ User {user_id} (telegram_id: {user.telegram_id}) received strike #{actual_strike_count}/{config.MAX_STRIKES_BEFORE_BAN} (type: {strike_type.name})")

        await UserRepository.update(user, session)

    @staticmethod
    async def update_shipping_selection(
        order_id: int,
        shipping_type_key: str,
        session: AsyncSession | Session
    ) -> OrderDTO:
        """
        Update order's selected shipping type and recalculate shipping cost.

        Used when customer selects shipping upgrade (upselling flow).

        Args:
            order_id: Order ID
            shipping_type_key: Selected shipping type key (e.g., "paket_2kg")
            session: Database session

        Returns:
            OrderDTO: Updated order

        Raises:
            ValueError: If order not found or shipping type invalid

        Example:
            >>> order = await OrderService.update_shipping_selection(123, "paket_2kg", session)
            >>> order.shipping_type_key  # "paket_2kg"
            >>> order.shipping_cost  # 1.50
        """
        from services.shipping_upsell import ShippingUpsellService

        # Get order
        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            logging.error(f"[OrderService] Order {order_id} not found")
            raise ValueError(f"Order {order_id} not found")

        # Get shipping type details
        shipping_type_details = ShippingUpsellService.get_shipping_type_details(shipping_type_key)
        if not shipping_type_details:
            logging.error(f"[OrderService] Invalid shipping type: {shipping_type_key}")
            raise ValueError(f"Invalid shipping type: {shipping_type_key}")

        # Update order
        old_shipping_type = order.shipping_type_key
        old_shipping_cost = order.shipping_cost

        order.shipping_type_key = shipping_type_key
        order.shipping_cost = shipping_type_details["charged_cost"]

        # Recalculate total price
        order.total_price = (order.total_price - old_shipping_cost) + order.shipping_cost

        await OrderRepository.update(order, session)
        logging.info(f"[OrderService] Order {order_id} shipping updated: {old_shipping_type} → {shipping_type_key} (cost: {old_shipping_cost} → {order.shipping_cost})")

        return order