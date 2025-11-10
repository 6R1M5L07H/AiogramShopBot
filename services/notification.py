import logging
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from config import ADMIN_ID_LIST
from bot_instance import get_bot
from enums.bot_entity import BotEntity
from models.buy import RefundDTO
from models.cartItem import CartItemDTO
from models.item import ItemDTO
from models.payment import ProcessingPaymentDTO, DepositRecordDTO
from models.user import UserDTO
from repositories.category import CategoryRepository
from repositories.item import ItemRepository
from repositories.subcategory import SubcategoryRepository
from utils.localizator import Localizator
from utils.html_escape import safe_html


class NotificationService:

    @staticmethod
    async def make_user_button(username: str | None) -> InlineKeyboardMarkup:
        """
        Create inline keyboard button linking to user's Telegram profile.

        Note: This is acceptable UI creation in NotificationService because:
        - Notifications are sent from backend processes (payment processing, cart service)
        - These processes don't have access to handler/UI layer
        - The button is part of the notification, not business logic
        """
        user_button_builder = InlineKeyboardBuilder()
        if username:
            user_button_inline = types.InlineKeyboardButton(text=username, url=f"https://t.me/{username}")
            user_button_builder.add(user_button_inline)
        return user_button_builder.as_markup()

    @staticmethod
    async def send_to_admins(message: str | BufferedInputFile, reply_markup: types.InlineKeyboardMarkup | None):
        bot = get_bot()
        for admin_id in ADMIN_ID_LIST:
            try:
                if isinstance(message, str):
                    await bot.send_message(admin_id, f"<b>{message}</b>", reply_markup=reply_markup)
                else:
                    await bot.send_document(admin_id, message, reply_markup=reply_markup)
            except Exception as e:
                logging.error(e)

    @staticmethod
    async def send_to_user(message: str, telegram_id: int):
        bot = get_bot()
        try:
            await bot.send_message(telegram_id, message)
        except Exception as e:
            logging.error(e)

    @staticmethod
    async def edit_message(message: str, source_message_id: int, chat_id: int):
        bot = get_bot()
        try:
            await bot.edit_message_text(text=message, chat_id=chat_id, message_id=source_message_id)
        except Exception as e:
            logging.error(e)

    @staticmethod
    async def payment_expired(user_dto: UserDTO, payment_dto: ProcessingPaymentDTO, deposit_record: DepositRecordDTO):
        msg = Localizator.get_text(BotEntity.USER, "notification_payment_expired").format(
            payment_id=payment_dto.id
        )
        edited_payment_message = Localizator.get_text(BotEntity.USER, "top_up_balance_msg").format(
            crypto_name=payment_dto.cryptoCurrency.name,
            addr="***",
            crypto_amount=payment_dto.cryptoAmount,
            fiat_amount=payment_dto.fiatAmount,
            currency_text=Localizator.get_currency_text(),
            status=Localizator.get_text(BotEntity.USER, "status_expired"),
            topup_reference=deposit_record.topup_reference or "N/A",
            bot_name=config.BOT_NAME if hasattr(config, 'BOT_NAME') else "Bot"
        )
        await NotificationService.edit_message(edited_payment_message, deposit_record.message_id,
                                               user_dto.telegram_id)
        await NotificationService.send_to_user(msg, user_dto.telegram_id)

    @staticmethod
    async def new_deposit(payment_dto: ProcessingPaymentDTO, user_dto: UserDTO, deposit_record: DepositRecordDTO):
        user_button = await NotificationService.make_user_button(user_dto.telegram_username)
        user_notification_msg = Localizator.get_text(BotEntity.USER, "notification_new_deposit").format(
            fiat_amount=payment_dto.fiatAmount,
            currency_text=Localizator.get_currency_text(),
            payment_id=deposit_record.topup_reference or f"ID-{payment_dto.id}"
        )
        await NotificationService.send_to_user(user_notification_msg, user_dto.telegram_id)
        edited_payment_message = Localizator.get_text(BotEntity.USER, "top_up_balance_msg").format(
            crypto_name=payment_dto.cryptoCurrency.name,
            addr="***",
            crypto_amount=payment_dto.cryptoAmount,
            fiat_amount=payment_dto.fiatAmount,
            currency_text=Localizator.get_currency_text(),
            status=Localizator.get_text(BotEntity.USER, "status_paid"),
            topup_reference=deposit_record.topup_reference or "N/A",
            bot_name=config.BOT_NAME if hasattr(config, 'BOT_NAME') else "Bot"
        )
        await NotificationService.edit_message(edited_payment_message, deposit_record.message_id,
                                               user_dto.telegram_id)
        if user_dto.telegram_username:
            message = Localizator.get_text(BotEntity.ADMIN, "notification_new_deposit_username").format(
                username=safe_html(user_dto.telegram_username),
                deposit_amount_fiat=payment_dto.fiatAmount,
                currency_sym=Localizator.get_currency_symbol(),
                value=payment_dto.cryptoAmount,
                crypto_name=payment_dto.cryptoCurrency.name
            )
        else:
            message = Localizator.get_text(BotEntity.ADMIN, "notification_new_deposit_id").format(
                telegram_id=user_dto.telegram_id,
                deposit_amount_fiat=payment_dto.fiatAmount,
                currency_sym=Localizator.get_currency_symbol(),
                value=payment_dto.cryptoAmount,
                crypto_name=payment_dto.cryptoCurrency.name
            )
        await NotificationService.send_to_admins(message, user_button)

    @staticmethod
    async def new_buy(sold_items: list[CartItemDTO], user: UserDTO, session: AsyncSession | Session):
        user_button = await NotificationService.make_user_button(user.telegram_username)
        cart_grand_total = 0.0
        message = ""
        for item in sold_items:
            price = await ItemRepository.get_price(ItemDTO(subcategory_id=item.subcategory_id,
                                                           category_id=item.category_id), session)
            category = await CategoryRepository.get_by_id(item.category_id, session)
            subcategory = await SubcategoryRepository.get_by_id(item.subcategory_id, session)
            cart_item_total = price * item.quantity
            cart_grand_total += cart_item_total
            if user.telegram_username:
                message += Localizator.get_text(BotEntity.ADMIN, "notification_purchase_with_tgid").format(
                    username=safe_html(user.telegram_username),
                    total_price=cart_item_total,
                    quantity=item.quantity,
                    category_name=category.name,
                    subcategory_name=subcategory.name,
                    currency_sym=Localizator.get_currency_symbol()) + "\n"
            else:
                message += Localizator.get_text(BotEntity.ADMIN, "notification_purchase_with_username").format(
                    telegram_id=user.telegram_id,
                    total_price=cart_item_total,
                    quantity=item.quantity,
                    category_name=category.name,
                    subcategory_name=subcategory.name,
                    currency_sym=Localizator.get_currency_symbol()) + "\n"
        message += Localizator.get_text(BotEntity.USER, "cart_grand_total_string").format(
            cart_grand_total=cart_grand_total, currency_sym=Localizator.get_currency_symbol())
        await NotificationService.send_to_admins(message, user_button)

    @staticmethod
    async def refund(refund_data: RefundDTO):
        user_notification = Localizator.get_text(BotEntity.USER, "refund_notification").format(
            total_price=refund_data.total_price,
            quantity=refund_data.quantity,
            subcategory=refund_data.subcategory_name,
            currency_sym=Localizator.get_currency_symbol())
        try:
            bot = get_bot()
            await bot.send_message(refund_data.telegram_id, text=user_notification)
        except Exception as _:
            pass

    @staticmethod
    async def payment_underpayment_retry(
        user: UserDTO,
        invoice_number: str,
        paid_crypto: float,
        required_crypto: float,
        remaining_crypto: float,
        crypto_currency,
        new_invoice_number: str,
        new_payment_address: str,
        new_expires_at
    ):
        """
        Notifies user about underpayment and provides new invoice for remaining amount.

        Called after first underpayment - gives user 30 more minutes to pay remaining amount.
        """
        msg = Localizator.get_text(BotEntity.USER, "payment_underpayment_retry").format(
            invoice_number=invoice_number,
            paid_crypto=paid_crypto,
            crypto_currency=crypto_currency.value,
            required_crypto=required_crypto,
            remaining_crypto=remaining_crypto,
            new_invoice_number=new_invoice_number,
            new_payment_address=new_payment_address,
            new_expires_at=new_expires_at.strftime('%d.%m.%Y %H:%M')
        )

        await NotificationService.send_to_user(msg, user.telegram_id)

    @staticmethod
    async def payment_cancelled_underpayment(
        user: UserDTO,
        invoice_number: str,
        total_paid_fiat: float,
        penalty_amount: float,
        net_wallet_credit: float,
        currency_sym: str
    ):
        """
        Notifies user about order cancellation due to second underpayment.

        Informs about 5% penalty and wallet credit.
        """
        msg = Localizator.get_text(BotEntity.USER, "payment_cancelled_underpayment").format(
            invoice_number=invoice_number,
            total_paid_fiat=f"{total_paid_fiat:.2f}",
            penalty_amount=f"{penalty_amount:.2f}",
            net_wallet_credit=f"{net_wallet_credit:.2f}",
            currency_sym=currency_sym
        )

        await NotificationService.send_to_user(msg, user.telegram_id)

    @staticmethod
    async def payment_late(
        user: UserDTO,
        invoice_number: str,
        paid_fiat: float,
        penalty_amount: float,
        net_wallet_credit: float,
        currency_sym: str
    ):
        """
        Notifies user about late payment.

        Payment received after deadline - 5% penalty applied, wallet credited.
        """
        msg = Localizator.get_text(BotEntity.USER, "payment_late").format(
            invoice_number=invoice_number,
            paid_fiat=f"{paid_fiat:.2f}",
            penalty_amount=f"{penalty_amount:.2f}",
            net_wallet_credit=f"{net_wallet_credit:.2f}",
            currency_sym=currency_sym
        )

        await NotificationService.send_to_user(msg, user.telegram_id)

    @staticmethod
    async def payment_overpayment_wallet_credit(
        user: UserDTO,
        invoice_number: str,
        overpayment_amount: float,
        currency_sym: str
    ):
        """
        Notifies user about overpayment credited to wallet.

        Significant overpayment (>0.1%) - excess credited to wallet.
        """
        msg = Localizator.get_text(BotEntity.USER, "payment_overpayment_wallet_credit").format(
            invoice_number=invoice_number,
            overpayment_amount=f"{overpayment_amount:.2f}",
            currency_sym=currency_sym
        )

        await NotificationService.send_to_user(msg, user.telegram_id)

    @staticmethod
    async def payment_success(
        user: UserDTO,
        invoice_number: str,
        order_id: int = None,
        session = None
    ):
        """
        Notifies user about successful payment with full order details and purchased items.

        Combines payment confirmation with invoice-style formatting and private_data delivery.
        """
        # If order_id provided, use detailed invoice format with items
        if order_id and session:
            from repositories.item import ItemRepository
            from repositories.subcategory import SubcategoryRepository
            from repositories.order import OrderRepository
            from repositories.invoice import InvoiceRepository
            from services.invoice_formatter import InvoiceFormatterService
            from enums.order_status import OrderStatus

            # Get order and items
            order = await OrderRepository.get_by_id(order_id, session)
            items = await ItemRepository.get_by_order_id(order_id, session)

            if order and items:
                # Check if order contains physical and/or digital items
                has_physical_items = any(item.is_physical for item in items)
                has_digital_items = any(not item.is_physical for item in items)
                is_mixed_order = has_physical_items and has_digital_items

                # Parse tier breakdown from order (NO recalculation!)
                from services.order import OrderService
                tier_breakdown_list = OrderService._parse_tier_breakdown_from_order(order)

                # Batch-load all subcategories (eliminates N+1 queries)
                subcategory_ids = list({item.subcategory_id for item in items})
                subcategories_dict = await SubcategoryRepository.get_by_ids(subcategory_ids, session)

                # Fallback: If tier_breakdown_json not available (old orders), recalculate
                if not tier_breakdown_list:
                    logging.warning(f"Order {order_id} has no tier_breakdown_json, falling back to recalculation")
                    tier_breakdown_list = await OrderService._group_items_with_tier_pricing(
                        items, subcategories_dict, session
                    )

                # Build items list with private_data (ungrouped for individual keys/codes)
                items_raw = []
                for item in items:
                    # Find corresponding tier breakdown from tier_breakdown_list
                    tier_breakdown = None
                    for tier_item in tier_breakdown_list:
                        subcategory = subcategories_dict.get(item.subcategory_id)
                        if subcategory and tier_item['subcategory_name'] == subcategory.name:
                            tier_breakdown = tier_item.get('breakdown')
                            break

                    subcategory = subcategories_dict.get(item.subcategory_id)
                    if subcategory:
                        items_raw.append({
                            'name': subcategory.name,
                            'price': item.price,  # Keep for fallback, but tier_breakdown takes precedence
                            'quantity': 1,
                            'is_physical': item.is_physical,
                            'private_data': item.private_data,
                            'tier_breakdown': tier_breakdown  # Add tier breakdown
                        })

                # Group items by (name, price, is_physical, private_data) while preserving tier_breakdown
                items_list = OrderService._group_items_for_display(items_raw)

                # Format message with InvoiceFormatter
                msg = InvoiceFormatterService.format_complete_order_view(
                    header_type="payment_success",
                    invoice_number=invoice_number,
                    order_status=order.status,
                    created_at=order.created_at,
                    paid_at=order.paid_at,
                    items=items_list,
                    shipping_cost=order.shipping_cost,
                    total_price=order.total_price,
                    separate_digital_physical=True,  # Always use separated view
                    show_private_data=True,  # Show keys/codes after payment
                    show_retention_notice=any(item.get('private_data') for item in items_list),
                    currency_symbol=Localizator.get_currency_symbol(),
                    entity=BotEntity.USER
                )

                await NotificationService.send_to_user(msg, user.telegram_id)
                return

        # Fallback: Simple payment success message
        msg = Localizator.get_text(BotEntity.USER, "payment_success").format(
            invoice_number=invoice_number
        )
        await NotificationService.send_to_user(msg, user.telegram_id)

    @staticmethod
    async def notify_double_payment(
        user: UserDTO,
        amount: float,
        invoice_number: str
    ):
        """
        Notifies user about double payment (payment for already completed order).
        Entire amount credited to wallet.
        """
        msg = (
            f"⚠️ <b>Double Payment Detected</b>\n\n"
            f"We received a duplicate payment for order-id {invoice_number}.\n\n"
            f"💰 <b>Amount credited to wallet:</b> {amount:.2f} {Localizator.get_currency_symbol()}\n\n"
            f"Your order was already completed. The payment has been fully credited to your wallet balance."
        )

        await NotificationService.send_to_user(msg, user.telegram_id)

    @staticmethod
    async def build_order_cancelled_wallet_refund_message(
        user: UserDTO,
        order,
        invoice,
        invoice_number: str,
        refund_info: dict,
        currency_sym: str,
        session,
        custom_reason: str = None
    ) -> str:
        """
        Builds notification message about order cancellation and wallet refund.
        Shows processing fee if applicable.
        For admin cancellations, shows full invoice with refund line.

        Returns:
            Formatted message string (does NOT send)
        """
        from services.invoice_formatter import InvoiceFormatterService

        original_amount = refund_info['original_amount']
        penalty_amount = refund_info['penalty_amount']
        refund_amount = refund_info['refund_amount']
        penalty_percent = refund_info['penalty_percent']
        reason = refund_info.get('reason', 'UNKNOWN')
        is_mixed_order = refund_info.get('is_mixed_order', False)
        partial_refund_details = refund_info.get('partial_refund_info')

        # Load items for mixed order display
        items_list = None
        if is_mixed_order and order:
            from repositories.item import ItemRepository
            from repositories.subcategory import SubcategoryRepository
            from services.order import OrderService
            order_items = await ItemRepository.get_by_order_id(order.id, session)

            # Parse tier breakdown from order (NO recalculation!)
            tier_breakdown_list = OrderService._parse_tier_breakdown_from_order(order)

            # Batch-load all subcategories
            subcategory_ids = list({item.subcategory_id for item in order_items})
            subcategories_dict = await SubcategoryRepository.get_by_ids(subcategory_ids, session)

            # Fallback: If tier_breakdown_json not available (old orders), recalculate
            if not tier_breakdown_list:
                logging.warning(f"Order {order.id} has no tier_breakdown_json, falling back to recalculation")
                tier_breakdown_list = await OrderService._group_items_with_tier_pricing(
                    order_items, subcategories_dict, session
                )

            # Build items list (no private_data for cancellation messages)
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
                    'price': item.price,  # Keep for fallback, but tier_breakdown takes precedence
                    'quantity': 1,
                    'is_physical': item.is_physical,
                    'private_data': None,  # Don't show private_data in cancellation
                    'tier_breakdown': tier_breakdown  # Add tier breakdown
                })

            # Group items by (name, price, is_physical, private_data) while preserving tier_breakdown
            items_list = OrderService._group_items_for_display(items_raw)

        if is_mixed_order and partial_refund_details:
            # Mixed order cancellation - show digital items kept, physical items refunded
            return InvoiceFormatterService.format_complete_order_view(
                header_type="partial_cancellation",
                invoice_number=invoice_number,
                items=items_list,
                total_price=refund_info.get('base_amount', 0),
                refund_amount=refund_amount,
                penalty_amount=penalty_amount,
                penalty_percent=penalty_percent,
                cancellation_reason=reason,
                show_strike_warning=(penalty_amount > 0),
                partial_refund_info=partial_refund_details,
                currency_symbol=currency_sym,
                entity=BotEntity.USER
            )
        elif penalty_amount > 0:
            # Regular cancellation with processing fee and strike - use InvoiceFormatter
            return InvoiceFormatterService.format_complete_order_view(
                header_type="cancellation_refund",
                invoice_number=invoice_number,
                items=None,  # No items shown for penalty cancellations
                total_price=refund_info.get('base_amount', 0),
                wallet_used=original_amount,
                refund_amount=refund_amount,
                penalty_amount=penalty_amount,
                penalty_percent=penalty_percent,
                cancellation_reason=reason,
                show_strike_warning=True,
                currency_symbol=currency_sym,
                entity=BotEntity.USER
            )
        else:
            # Full refund (no fee)
            if 'ADMIN' in reason.upper():
                # Admin cancellation - delegate to build_order_cancelled_by_admin_message
                return await NotificationService.build_order_cancelled_by_admin_message(
                    user=user,
                    invoice_number=invoice_number,
                    custom_reason=custom_reason,
                    order=order,
                    session=session
                )
            else:
                # Simple full refund message
                return (
                    f"🔔 <b>Order Cancelled</b>\n\n"
                    f"📋 Order Number: {invoice_number}\n\n"
                    f"💰 <b>Full Refund:</b> {refund_amount:.2f} {currency_sym}\n\n"
                    f"Your wallet balance has been fully refunded and you will not receive a strike."
                )

    @staticmethod
    async def build_order_cancelled_by_admin_message(
        user: UserDTO,
        invoice_number: str,
        custom_reason: str,
        order = None,
        session = None
    ) -> str:
        """
        Builds notification message about admin order cancellation with custom reason.
        Shows full invoice with items if order and session provided.
        No wallet refund or strikes involved.

        Returns:
            Formatted message string (does NOT send)
        """
        from services.invoice_formatter import InvoiceFormatterService
        from utils.localizator import Localizator
        from enums.bot_entity import BotEntity
        import logging

        logging.info(f"🔵 build_order_cancelled_by_admin_message: custom_reason='{custom_reason}', order={order is not None}, session={session is not None}")

        # If order info available, show full invoice format
        if order and session:
            from repositories.item import ItemRepository
            from repositories.subcategory import SubcategoryRepository
            import logging

            currency_sym = Localizator.get_currency_symbol()

            # Load items (they still have order_id at this point)
            order_items = await ItemRepository.get_by_order_id(order.id, session)
            logging.info(f"notify_order_cancelled_by_admin: Found {len(order_items) if order_items else 0} items for order {order.id}")

            # Build unified items list
            items_raw = []
            for item in order_items:
                subcategory = await SubcategoryRepository.get_by_id(item.subcategory_id, session)
                if subcategory:
                    items_raw.append({
                        'name': subcategory.name,
                        'price': item.price,
                        'quantity': 1,
                        'is_physical': item.is_physical,
                        'private_data': None
                    })
                else:
                    logging.warning(f"Subcategory {item.subcategory_id} not found for item {item.id}")

            # Group items by (name, price, is_physical, private_data)
            from services.order import OrderService
            items_list = OrderService._group_items_for_display(items_raw)

            escaped_reason = safe_html(custom_reason)
            logging.info(f"🔵 Passing to formatter: cancellation_reason='{escaped_reason}' (from custom_reason='{custom_reason}')")

            return InvoiceFormatterService.format_complete_order_view(
                header_type="admin_cancellation",
                invoice_number=invoice_number,
                items=items_list,
                shipping_cost=order.shipping_cost,
                total_price=order.total_price,
                cancellation_reason=escaped_reason,
                use_spacing_alignment=True,
                currency_symbol=currency_sym,
                entity=BotEntity.USER
            )
        else:
            # Fallback: Simple message without items
            return (
                f"❌ <b>{Localizator.get_text(BotEntity.USER, 'order_cancelled_by_admin_title')}</b>\n\n"
                f"📋 {Localizator.get_text(BotEntity.USER, 'order_number')}: {invoice_number}\n\n"
                f"<b>{Localizator.get_text(BotEntity.USER, 'admin_cancel_reason_label')}</b>\n"
                f"{safe_html(custom_reason)}\n\n"
                f"{Localizator.get_text(BotEntity.USER, 'admin_cancel_contact_support')}"
            )

    @staticmethod
    async def build_order_cancelled_strike_only_message(
        user: UserDTO,
        invoice_number: str,
        reason,
        custom_reason: str = None
    ) -> str:
        """
        Builds notification message about order cancellation when no wallet was involved but strike was given.

        Returns:
            Formatted message string (does NOT send)
        """
        from enums.order_cancel_reason import OrderCancelReason

        if reason == OrderCancelReason.TIMEOUT:
            reason_text = Localizator.get_text(BotEntity.USER, "order_cancelled_strike_timeout_reason")
        else:
            reason_text = Localizator.get_text(BotEntity.USER, "order_cancelled_strike_late_cancel_reason")

        msg = Localizator.get_text(BotEntity.USER, "order_cancelled_strike_only").format(
            invoice_number=invoice_number,
            reason_text=reason_text
        )

        return msg

    @staticmethod
    async def order_shipped(user_id: int, order_id: int, invoice_number: str, session: AsyncSession | Session):
        """
        Sends notification to user when their order has been marked as shipped.
        Uses InvoiceFormatter for consistent display with items.
        """
        from repositories.user import UserRepository
        from repositories.order import OrderRepository
        from repositories.item import ItemRepository
        from repositories.subcategory import SubcategoryRepository
        from services.invoice_formatter import InvoiceFormatterService

        user = await UserRepository.get_by_id(user_id, session)
        order = await OrderRepository.get_by_id(order_id, session)
        order_items = await ItemRepository.get_by_order_id(order.id, session)

        # Batch-load subcategories
        subcategory_ids = list({item.subcategory_id for item in order_items})
        subcategories_dict = await SubcategoryRepository.get_by_ids(subcategory_ids, session)

        # Build items list with private_data
        items_raw = []
        for item in order_items:
            subcategory = subcategories_dict.get(item.subcategory_id)
            if subcategory:
                items_raw.append({
                    'name': subcategory.name,
                    'price': item.price,
                    'quantity': 1,
                    'is_physical': item.is_physical,
                    'private_data': item.private_data
                })

        # Group items by (name, price, is_physical, private_data)
        from services.order import OrderService
        items_list = OrderService._group_items_for_display(items_raw)

        # Format with InvoiceFormatter
        msg = InvoiceFormatterService.format_complete_order_view(
            header_type="order_shipped",
            invoice_number=invoice_number,
            order_status=order.status,
            created_at=order.created_at,
            shipped_at=order.shipped_at,
            items=items_list,
            shipping_cost=order.shipping_cost,
            total_price=order.total_price,
            separate_digital_physical=True,  # Always use separated view
            show_private_data=True,  # Show keys/codes (user already has them)
            currency_symbol=Localizator.get_currency_symbol(),
            entity=BotEntity.USER
        )

        await NotificationService.send_to_user(msg, user.telegram_id)

    @staticmethod
    async def order_awaiting_shipment(user_id: int, invoice_number: str, session: AsyncSession | Session):
        """
        Sends notification to admins when a new order with physical items is awaiting shipment.
        """
        from repositories.user import UserRepository

        user = await UserRepository.get_by_id(user_id, session)
        username = f"@{safe_html(user.telegram_username)}" if user.telegram_username else f"ID:{user.telegram_id}"

        msg = Localizator.get_text(BotEntity.ADMIN, "order_awaiting_shipment_notification").format(
            invoice_number=invoice_number,
            username=username
        )
        await NotificationService.send_to_admins(msg, None)

    @staticmethod
    async def notify_user_banned(user, strike_count: int):
        """
        Sends notification to user when they are banned due to strikes.

        Args:
            user: User object
            strike_count: Number of strikes that caused the ban
        """
        from utils.localizator import Localizator
        msg = Localizator.get_text(BotEntity.USER, "user_banned_notification").format(
            strike_count=strike_count,
            unban_amount=config.UNBAN_TOP_UP_AMOUNT,
            currency_sym=Localizator.get_currency_symbol()
        )
        await NotificationService.send_to_user(msg, user.telegram_id)

    @staticmethod
    async def notify_admin_user_banned(user, strike_count: int):
        """
        Sends notification to admins when a user is banned due to strikes.

        Args:
            user: User object
            strike_count: Number of strikes that caused the ban
        """
        from config import UNBAN_TOP_UP_AMOUNT

        # Format user display
        if user.telegram_username:
            user_display = f"@{safe_html(user.telegram_username)}"
        else:
            user_display = f"ID: {user.telegram_id}"

        msg = Localizator.get_text(BotEntity.ADMIN, "admin_user_banned_notification").format(
            user_display=user_display,
            telegram_id=user.telegram_id,
            strike_count=strike_count,
            ban_reason=safe_html(user.blocked_reason) if user.blocked_reason else "Unknown",
            unban_amount=UNBAN_TOP_UP_AMOUNT
        )

        user_button = await NotificationService.make_user_button(user.telegram_username)
        await NotificationService.send_to_admins(msg, user_button)

    @staticmethod
    async def notify_user_unbanned(user, top_up_amount: float, strike_count: int):
        """
        Sends notification to user when they are unbanned via wallet top-up.

        Args:
            user: User object
            top_up_amount: Amount that was topped up (EUR)
            strike_count: Current strike count (remains after unban)
        """
        msg = Localizator.get_text(BotEntity.USER, "user_unbanned_notification").format(
            top_up_amount=top_up_amount,
            currency_sym=Localizator.get_currency_symbol(),
            strike_count=strike_count
        )
        await NotificationService.send_to_user(msg, user.telegram_id)
