from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

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
        kb_builder.button(text=Localizator.get_text(BotEntity.USER, "purchase_history_button"),
                          callback_data=MyProfileCallback.create(4, "purchase_history"))
        user = await UserRepository.get_by_tgid(telegram_id, session)

        # Invoice-based system: no balance, only order history
        # TODO: Show total spent from OrderRepository.get_total_spent_by_currency()
        message = (Localizator.get_text(BotEntity.USER, "my_profile_msg")
                   .format(telegram_id=user.telegram_id,
                           fiat_balance=0.0,  # No wallet balance anymore
                           currency_text=Localizator.get_currency_text(),
                           currency_sym=Localizator.get_currency_symbol()))
        return message, kb_builder

    @staticmethod
    async def get_top_up_buttons(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = MyProfileCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "btc_top_up"),
                          callback_data=MyProfileCallback.create(unpacked_cb.level + 1,
                                                                 args_for_action=Cryptocurrency.BTC.value))
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "ltc_top_up"),
                          callback_data=MyProfileCallback.create(unpacked_cb.level + 1,
                                                                 args_for_action=Cryptocurrency.LTC.value))
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "sol_top_up"),
                          callback_data=MyProfileCallback.create(unpacked_cb.level + 1,
                                                                 args_for_action=Cryptocurrency.SOL.value))
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "eth_top_up"),
                          callback_data=MyProfileCallback.create(unpacked_cb.level + 1,
                                                                 args_for_action=Cryptocurrency.ETH.value))
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "bnb_top_up"),
                          callback_data=MyProfileCallback.create(unpacked_cb.level + 1,
                                                                 args_for_action=Cryptocurrency.BNB.value))

        kb_builder.adjust(1)
        kb_builder.row(unpacked_cb.get_back_button())
        msg_text = Localizator.get_text(BotEntity.USER, "choose_top_up_method")
        return msg_text, kb_builder

    @staticmethod
    async def get_purchase_history_buttons(callback: CallbackQuery, session: AsyncSession | Session) \
            -> tuple[str, InlineKeyboardBuilder]:
        from repositories.order import OrderRepository
        from repositories.invoice import InvoiceRepository
        import config

        unpacked_cb = MyProfileCallback.unpack(callback.data)
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)

        # Get orders from new order system
        orders = await OrderRepository.get_by_user_id(user.id, session)

        kb_builder = InlineKeyboardBuilder()
        for order in orders:
            # Get invoice for display
            invoice = await InvoiceRepository.get_by_order_id(order.id, session)

            # Get first item from order for display
            items = await ItemRepository.get_by_order_id(order.id, session)
            if items:
                first_item = items[0]
                subcategory = await SubcategoryRepository.get_by_id(first_item.subcategory_id, session)
                total_items = len(items)

                # Format button: show first item + additional items count
                # +X means "plus X additional items" (not total count)
                if total_items == 1:
                    button_text = Localizator.get_text(BotEntity.USER, "purchase_history_order_item_single").format(
                        invoice_number=invoice.invoice_number,
                        subcategory_name=subcategory.name
                    )
                else:
                    additional_count = total_items - 1
                    button_text = Localizator.get_text(BotEntity.USER, "purchase_history_order_item").format(
                        invoice_number=invoice.invoice_number,
                        subcategory_name=subcategory.name,
                        additional_count=additional_count
                    )

                kb_builder.button(text=button_text,
                    callback_data=MyProfileCallback.create(
                        unpacked_cb.level + 1,
                        args_for_action=order.id
                    ))

        kb_builder.adjust(1)
        kb_builder.row(unpacked_cb.get_back_button(0))

        if len(orders) > 0:
            retention_days = getattr(config, 'DATA_RETENTION_DAYS', 90)
            header = Localizator.get_text(BotEntity.USER, "purchases_with_retention").format(
                retention_days=retention_days
            )
            return header, kb_builder
        else:
            return Localizator.get_text(BotEntity.USER, "no_purchases"), kb_builder

    @staticmethod
    async def get_order_details(callback: CallbackQuery, session: AsyncSession | Session) \
            -> tuple[str, InlineKeyboardBuilder]:
        """Shows detailed view of a single order"""
        from repositories.order import OrderRepository
        from repositories.invoice import InvoiceRepository
        from enums.order_status import OrderStatus

        unpacked_cb = MyProfileCallback.unpack(callback.data)
        order_id = unpacked_cb.args_for_action

        # Get order details
        order = await OrderRepository.get_by_id(order_id, session)
        invoice = await InvoiceRepository.get_by_order_id(order_id, session)
        items = await ItemRepository.get_by_order_id(order_id, session)

        # Build message header
        message_text = Localizator.get_text(BotEntity.USER, "order_details_header").format(
            invoice_number=invoice.invoice_number
        ) + "\n\n"

        # Order status
        status_map = {
            OrderStatus.PAID: "✅ Bezahlt",
            OrderStatus.PAID_AWAITING_SHIPMENT: "📦 Bezahlt - Versand ausstehend",
            OrderStatus.SHIPPED: "🚚 Versendet",
        }
        status_text = status_map.get(order.status, str(order.status.value))
        message_text += f"<b>Status:</b> {status_text}\n"

        # Paid date
        if order.paid_at:
            paid_date_str = order.paid_at.strftime("%d.%m.%Y %H:%M")
            message_text += f"<b>Bezahlt am:</b> {paid_date_str}\n"

        # Shipped date (if applicable)
        if order.status == OrderStatus.SHIPPED and order.shipped_at:
            shipped_date_str = order.shipped_at.strftime("%d.%m.%Y %H:%M")
            message_text += f"<b>Versendet am:</b> {shipped_date_str}\n"

        message_text += "\n"

        # Items list
        message_text += "<b>📦 Artikel:</b>\n"
        items_total = 0.0
        for item in items:
            subcategory = await SubcategoryRepository.get_by_id(item.subcategory_id, session)
            message_text += f"- {subcategory.name}: {item.description} ({item.price:.2f}{Localizator.get_currency_symbol()})\n"
            items_total += item.price

        message_text += "\n"

        # Price breakdown
        message_text += f"<b>Artikel Gesamt:</b> {items_total:.2f}{Localizator.get_currency_symbol()}\n"
        if order.shipping_cost > 0:
            message_text += f"<b>Versandkosten:</b> {order.shipping_cost:.2f}{Localizator.get_currency_symbol()}\n"
        message_text += f"<b><u>Gesamtsumme:</u></b> {order.total_price:.2f}{Localizator.get_currency_symbol()}\n"

        # Back button
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=MyProfileCallback.create(4, "purchase_history")
        )

        return message_text, kb_builder
