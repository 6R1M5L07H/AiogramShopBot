from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import MyProfileCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.cryptocurrency import Cryptocurrency
from handlers.common.common import add_pagination_buttons
from models.user import User, UserDTO
from repositories.buy import BuyRepository
from repositories.buyItem import BuyItemRepository
from repositories.cart import CartRepository
from repositories.item import ItemRepository
from repositories.subcategory import SubcategoryRepository
from repositories.user import UserRepository
from utils.localizator import Localizator


class UserService:

    @staticmethod
    async def create_if_not_exist(user_dto: UserDTO, session: AsyncSession | Session) -> None:
        user = await UserRepository.get_by_tgid(user_dto.telegram_id, session)
        match user:
            case None:
                user_id = await UserRepository.create(user_dto, session)
                await CartRepository.get_or_create(user_id, session)
                await session_commit(session)
            case _:
                update_user_dto = UserDTO(**user.model_dump())
                update_user_dto.can_receive_messages = True
                update_user_dto.telegram_username = user_dto.telegram_username
                await UserRepository.update(update_user_dto, session)
                await session_commit(session)

    @staticmethod
    async def get(user_dto: UserDTO, session: AsyncSession | Session) -> User | None:
        return await UserRepository.get_by_tgid(user_dto.telegram_id, session)

    @staticmethod
    async def get_my_profile_buttons(telegram_id: int, session: Session | AsyncSession) -> tuple[
        str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.USER, "order_history_button"),
                          callback_data=MyProfileCallback.create(7))
        kb_builder.button(text=Localizator.get_text(BotEntity.USER, "top_up_balance_button"),
                          callback_data=MyProfileCallback.create(1, "top_up_balance"))
        kb_builder.button(text=Localizator.get_text(BotEntity.USER, "strike_statistics"),
                          callback_data=MyProfileCallback.create(6, "strike_statistics"))
        kb_builder.adjust(1)

        user = await UserRepository.get_by_tgid(telegram_id, session)

        # Show wallet balance (top_up_amount = overpayments + penalties credited)
        # Format balance to 2 decimal places
        message = (Localizator.get_text(BotEntity.USER, "my_profile_msg")
                   .format(telegram_id=user.telegram_id,
                           fiat_balance=f"{user.top_up_amount:.2f}",
                           currency_text=Localizator.get_currency_text(),
                           currency_sym=Localizator.get_currency_symbol()))
        return message, kb_builder

    @staticmethod
    async def get_top_up_buttons(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = MyProfileCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()

        # Generate crypto buttons from enum (same 5 cryptos for payment and top-up)
        for crypto in Cryptocurrency.get_payment_options():
            entity, key = crypto.get_localization_key()
            kb_builder.button(
                text=Localizator.get_text(entity, key),
                callback_data=MyProfileCallback.create(unpacked_cb.level + 1, args_for_action=crypto.value)
            )

        kb_builder.adjust(1)
        kb_builder.row(unpacked_cb.get_back_button())
        msg_text = Localizator.get_text(BotEntity.USER, "choose_top_up_method")
        return msg_text, kb_builder

    @staticmethod
    async def get_purchase_history_buttons(callback: CallbackQuery, session: AsyncSession | Session) \
            -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = MyProfileCallback.unpack(callback.data)
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)
        buys = await BuyRepository.get_by_buyer_id(user.id, unpacked_cb.page, session)
        kb_builder = InlineKeyboardBuilder()

        # Batch-load all items and subcategories (eliminates N+1 queries)
        item_ids = []
        for buy in buys:
            buy_item = await BuyItemRepository.get_single_by_buy_id(buy.id, session)
            item_ids.append(buy_item.item_id)

        # Get all items in one query
        items_dict = {}
        for item_id in item_ids:
            item = await ItemRepository.get_by_id(item_id, session)
            items_dict[item_id] = item

        # Batch-load subcategories
        subcategory_ids = list({item.subcategory_id for item in items_dict.values()})
        subcategories_dict = await SubcategoryRepository.get_by_ids(subcategory_ids, session)

        # Build buttons with batch-loaded data
        for buy in buys:
            buy_item = await BuyItemRepository.get_single_by_buy_id(buy.id, session)
            item = items_dict.get(buy_item.item_id)
            if not item:
                continue
            subcategory = subcategories_dict.get(item.subcategory_id)
            if not subcategory:
                continue

            # Format date only for list view (keep it short)
            date_str = buy.buy_datetime.strftime("%d.%m.%Y") if buy.buy_datetime else "N/A"

            kb_builder.button(text=f"{date_str} - {subcategory.name} (x{buy.quantity})",
                callback_data=MyProfileCallback.create(
                    unpacked_cb.level + 1,
                    args_for_action=buy.id
                ))
        kb_builder.adjust(1)
        kb_builder = await add_pagination_buttons(kb_builder, unpacked_cb,
                                                  BuyRepository.get_max_page_purchase_history(user.id, session),
                                                  unpacked_cb.get_back_button(0))
        if len(kb_builder.as_markup().inline_keyboard) > 1:
            return Localizator.get_text(BotEntity.USER, "purchases").format(
                retention_days=config.DATA_RETENTION_DAYS
            ), kb_builder
        else:
            return Localizator.get_text(BotEntity.USER, "no_purchases"), kb_builder

    @staticmethod
    async def get_strike_statistics_buttons(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[str, InlineKeyboardBuilder]:
        """
        Shows user's strike statistics and history.
        Uses DB count as single source of truth (not user.strike_count field).
        """
        from repositories.user_strike import UserStrikeRepository
        import config

        unpacked_cb = MyProfileCallback.unpack(callback.data)
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)

        # Get user's strikes - use DB count as single source of truth
        strikes = await UserStrikeRepository.get_by_user_id(user.id, session)
        actual_strike_count = len(strikes)

        # Determine status based on actual DB count
        # Use max(0, ...) to prevent negative remaining strikes
        remaining_strikes = max(0, config.MAX_STRIKES_BEFORE_BAN - actual_strike_count)
        if user.is_blocked:
            status = Localizator.get_text(BotEntity.USER, "strike_status_banned")
        elif actual_strike_count >= config.MAX_STRIKES_BEFORE_BAN - 1:
            status = Localizator.get_text(BotEntity.USER, "strike_status_warning").format(remaining=remaining_strikes)
        else:
            status = Localizator.get_text(BotEntity.USER, "strike_status_ok")

        # Build strike list (show last 5)
        strikes_list = ""
        for strike in strikes[:5]:
            date_str = strike.created_at.strftime("%d.%m.%Y")

            # Get invoice number for this order
            from repositories.invoice import InvoiceRepository
            invoice = await InvoiceRepository.get_by_order_id(strike.order_id, session)
            if invoice:
                invoice_number = invoice.invoice_number
            else:
                # Fallback for strikes on orders without invoice (legacy data)
                from datetime import datetime
                invoice_number = f"ORDER-{datetime.now().year}-{strike.order_id:06d}"

            strikes_list += Localizator.get_text(BotEntity.USER, "strike_list_item").format(
                date=date_str,
                strike_type=strike.strike_type.name,
                order_id=invoice_number
            )

        if not strikes_list:
            strikes_list = "No strikes\n"

        # Build message using actual DB count
        message = Localizator.get_text(BotEntity.USER, "strike_statistics_msg").format(
            strike_count=actual_strike_count,
            max_strikes=config.MAX_STRIKES_BEFORE_BAN,
            status=status,
            strikes_list=strikes_list,
            grace_period=config.ORDER_CANCEL_GRACE_PERIOD_MINUTES
        )

        # Build keyboard
        kb_builder = InlineKeyboardBuilder()
        kb_builder.row(unpacked_cb.get_back_button(0))

        return message, kb_builder

    @staticmethod
    async def get_my_orders_overview(
        telegram_id: int,
        session: Session | AsyncSession
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Get user order history overview with pending order banner if exists.

        Shows:
        - Pending order banner (if exists) with link to payment
        - Filter selection (ALL, COMPLETED, CANCELLED)

        Args:
            telegram_id: Telegram user ID
            session: Database session

        Returns:
            Tuple of (message_text, keyboard_builder)
        """
        from enums.order_filter import OrderFilterType
        from repositories.order import OrderRepository
        from repositories.invoice import InvoiceRepository
        from datetime import datetime

        user = await UserRepository.get_by_tgid(telegram_id, session)
        kb_builder = InlineKeyboardBuilder()

        # Check for pending order
        pending_order = await OrderRepository.get_pending_order_by_user(user.id, session)

        # Build message
        message_text = Localizator.get_text(BotEntity.USER, "my_orders_title") + "\n\n"

        # Add pending order banner if exists
        if pending_order:
            # Get invoice number
            invoices = await InvoiceRepository.get_all_by_order_id(pending_order.id, session)
            invoice_number = invoices[0].invoice_number if invoices else f"ORDER-{datetime.now().year}-{pending_order.id:06d}"

            # Calculate remaining time
            if pending_order.expires_at:
                remaining_seconds = (pending_order.expires_at - datetime.now()).total_seconds()
                remaining_minutes = max(0, int(remaining_seconds / 60))
            else:
                remaining_minutes = 0

            message_text += Localizator.get_text(BotEntity.USER, "pending_order_banner").format(
                invoice_number=invoice_number,
                remaining_minutes=remaining_minutes
            ) + "\n\n"

            # Button to go to pending order
            from callbacks import CartCallback
            kb_builder.button(
                text=Localizator.get_text(BotEntity.USER, "go_to_payment"),
                callback_data=CartCallback.create(level=0).pack()
            )

        message_text += "─────────────\n\n"
        message_text += Localizator.get_text(BotEntity.USER, "order_history_label")

        # Filter buttons (redirect to list view with selected filter)
        filter_buttons = [
            (None, "order_filter_all"),
            (OrderFilterType.COMPLETED, "order_filter_completed_user"),
            (OrderFilterType.CANCELLED, "order_filter_cancelled_user"),
        ]

        for f_type, localization_key in filter_buttons:
            button_text = Localizator.get_text(BotEntity.USER, localization_key)
            kb_builder.button(
                text=button_text,
                callback_data=MyProfileCallback.create(level=8, filter_type=f_type, page=0).pack()
            )

        kb_builder.adjust(1)

        # Back to profile
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=MyProfileCallback.create(level=0).pack()
        )

        return message_text, kb_builder

    @staticmethod
    async def get_my_orders_list(
        telegram_id: int,
        filter_type: int | None,
        page: int,
        session: Session | AsyncSession
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Get paginated list of user's orders with filter.

        Args:
            telegram_id: Telegram user ID
            filter_type: OrderFilterType enum value (None = ALL)
            page: Page number (0-indexed)
            session: Database session

        Returns:
            Tuple of (message_text, keyboard_builder)
        """
        from enums.order_filter import OrderFilterType
        from enums.order_status import OrderStatus
        from utils.order_filters import get_status_filter_for_user
        from repositories.order import OrderRepository
        from datetime import datetime

        user = await UserRepository.get_by_tgid(telegram_id, session)

        # Get status filter using user-specific logic
        status_filter = get_status_filter_for_user(filter_type)

        # Get orders with pagination
        orders = await OrderRepository.get_by_user_id_with_filter(
            user_id=user.id,
            status_filter=status_filter,
            page=page,
            session=session
        )

        # Get max page for pagination
        max_page = await OrderRepository.get_max_page_by_user_id(
            user_id=user.id,
            status_filter=status_filter,
            session=session
        )

        # Determine filter name for display
        if filter_type is None:
            filter_name = Localizator.get_text(BotEntity.USER, "order_filter_all")
        elif filter_type == OrderFilterType.COMPLETED:
            filter_name = Localizator.get_text(BotEntity.USER, "order_filter_completed_user")
        elif filter_type == OrderFilterType.CANCELLED:
            filter_name = Localizator.get_text(BotEntity.USER, "order_filter_cancelled_user")
        else:
            filter_name = Localizator.get_text(BotEntity.USER, "order_filter_all")

        # Build message
        message_text = Localizator.get_text(BotEntity.USER, "my_orders_title") + "\n"
        message_text += Localizator.get_text(BotEntity.USER, "order_filter_current").format(filter_name=filter_name) + "\n\n"

        kb_builder = InlineKeyboardBuilder()

        if not orders:
            message_text += Localizator.get_text(BotEntity.USER, "order_no_orders")
        else:
            # Add order buttons with compact single-line layout
            for order in orders:
                # Short date: DD.MM (without year)
                created_time = order.created_at.strftime("%d.%m")

                # Short invoice: last 6 chars (e.g., "85TQ2A" from "INV-2025-85TQ2A")
                full_invoice = order.invoices[0].invoice_number if order.invoices else f"ORDER-{datetime.now().year}-{order.id:06d}"
                short_invoice = full_invoice[-6:]  # Last 6 characters

                # Get status text (l10n keys have no emojis for clean layout)
                status_text = Localizator.get_text(BotEntity.COMMON, f"order_status_{order.status.value}")

                # Button layout: Compact single line - DD.MM • SHORT_ID • Status
                # Add trailing spaces to make text appear left-aligned (Telegram centers by default)
                button_text = f"{created_time} • {short_invoice} • {status_text}".ljust(40)
                
                kb_builder.button(
                    text=button_text,
                    callback_data=MyProfileCallback.create(level=9, filter_type=filter_type, args_for_action=order.id).pack()
                )

            # Ensure single column layout (full width buttons)
            kb_builder.adjust(1)

        # Add pagination (wrap max_page in async lambda for add_pagination_buttons)
        unpacked_cb = MyProfileCallback.create(level=8, filter_type=filter_type, page=page)

        async def get_max_page_async():
            return max_page

        # Add pagination buttons (without back button, we'll add custom buttons below)
        kb_builder = await add_pagination_buttons(
            kb_builder,
            unpacked_cb,
            get_max_page_async(),
            None  # No back button here, we add custom buttons below
        )

        # Re-apply single column layout after pagination (which may have changed it)
        # Note: This doesn't affect pagination buttons themselves, just future buttons

        # Add "Change Filter" button (level=10 for filter selection)
        from aiogram.types import InlineKeyboardButton
        kb_builder.row(
            InlineKeyboardButton(
                text=Localizator.get_text(BotEntity.USER, "order_filter_change_button"),
                callback_data=MyProfileCallback.create(level=10).pack()
            )
        )

        # Back to My Profile
        kb_builder.row(unpacked_cb.get_back_button(0))

        return message_text, kb_builder

    @staticmethod
    async def get_order_detail_for_user(
        order_id: int,
        telegram_id: int,
        session: Session | AsyncSession,
        filter_type: int | None = None
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Get detailed order view for user.

        Reuses ShippingService.get_order_details_data() for consistency.

        Args:
            order_id: Order ID
            telegram_id: Telegram user ID (for ownership verification)
            session: Database session
            filter_type: Filter type to return to (for back button)

        Returns:
            Tuple of (message_text, keyboard_builder)

        Raises:
            OrderNotFoundException: If order not found or doesn't belong to user
        """
        from services.shipping import ShippingService
        from services.invoice_formatter import InvoiceFormatter
        from exceptions.order import OrderNotFoundException

        try:
            order_data = await ShippingService.get_order_details_data(order_id, session)
        except Exception:
            raise OrderNotFoundException(order_id)

        order = order_data["order"]

        # SECURITY: Verify order belongs to requesting user
        user = await UserRepository.get_by_tgid(telegram_id, session)
        if order.user_id != user.id:
            raise OrderNotFoundException(order_id)  # Hide existence of other users' orders

        # Build items list for InvoiceFormatter
        items_list = []
        
        # Digital items
        for (description, price), quantity in order_data["digital_items"].items():
            items_list.append({
                'name': description,
                'price': price,
                'quantity': quantity,
                'is_physical': False,
            })

        # Physical items
        for (description, price), quantity in order_data["physical_items"].items():
            items_list.append({
                'name': description,
                'price': price,
                'quantity': quantity,
                'is_physical': True,
            })

        # Calculate subtotal
        subtotal = order.total_price - order.shipping_cost

        # Format message
        msg = InvoiceFormatter.format_complete_order_view(
            header_type="order_detail_user",
            invoice_number=order_data["invoice_number"],
            order_status=order.status,
            created_at=order.created_at,
            paid_at=order.paid_at,
            shipped_at=order.shipped_at,
            items=items_list,
            subtotal=subtotal,
            shipping_cost=order.shipping_cost,
            total_price=order.total_price,
            separate_digital_physical=True,
            show_private_data=False,
            show_retention_notice=False,
            currency_symbol=Localizator.get_currency_symbol(),
            entity=BotEntity.USER
        )

        # Add shipping address if exists (hide decryption failures from users)
        if order_data["shipping_address"] and not order_data["shipping_address"].startswith("[DECRYPTION FAILED"):
            import config
            msg += f"\n\n📬 <b>{Localizator.get_text(BotEntity.USER, 'shipping_address_label')}:</b>\n"
            msg += f"<code>{order_data['shipping_address']}</code>\n"
            msg += f"<i>{Localizator.get_text(BotEntity.USER, 'shipping_address_encrypted_notice').format(retention_days=config.DATA_RETENTION_DAYS)}</i>"
        elif order_data["shipping_address"]:
            # Shipping address exists but decryption failed - show only notice
            import config
            msg += f"\n\n📬 <b>{Localizator.get_text(BotEntity.USER, 'shipping_address_label')}:</b>\n"
            msg += f"<i>{Localizator.get_text(BotEntity.USER, 'shipping_address_encrypted_notice').format(retention_days=config.DATA_RETENTION_DAYS)}</i>"

        # Keyboard
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=MyProfileCallback.create(level=8, filter_type=filter_type, page=0).pack()
        )

        return msg, kb_builder
