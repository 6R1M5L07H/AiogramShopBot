from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import MyProfileCallback
from db import session_commit
from enums.bot_entity import BotEntity
from models.buy import BuyDTO
from repositories.buy import BuyRepository
from repositories.item import ItemRepository
from repositories.user import UserRepository
from services.message import MessageService
from services.notification import NotificationService
from utils.localizator import Localizator


class BuyService:

    @staticmethod
    async def refund(buy_dto: BuyDTO, session: AsyncSession | Session) -> str:
        refund_data = await BuyRepository.get_refund_data_single(buy_dto.id, session)
        buy = await BuyRepository.get_by_id(buy_dto.id, session)
        buy.is_refunded = True
        await BuyRepository.update(buy, session)
        user = await UserRepository.get_by_tgid(refund_data.telegram_id, session)
        # Refund: Add money back to wallet (rounded to 2 decimals)
        user.top_up_amount = round(user.top_up_amount + refund_data.total_price, 2)
        await UserRepository.update(user, session)
        await session_commit(session)
        await NotificationService.refund(refund_data)
        if refund_data.telegram_username:
            return Localizator.get_text(BotEntity.ADMIN, "successfully_refunded_with_username").format(
                total_price=refund_data.total_price,
                telegram_username=refund_data.telegram_username,
                quantity=refund_data.quantity,
                subcategory=refund_data.subcategory_name,
                currency_sym=Localizator.get_currency_symbol())
        else:
            return Localizator.get_text(BotEntity.ADMIN, "successfully_refunded_with_tgid").format(
                total_price=refund_data.total_price,
                telegram_id=refund_data.telegram_id,
                quantity=refund_data.quantity,
                subcategory=refund_data.subcategory_name,
                currency_sym=Localizator.get_currency_symbol())

    @staticmethod
    async def get_purchase(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[str, InlineKeyboardBuilder]:
        from repositories.order import OrderRepository
        from repositories.invoice import InvoiceRepository
        from enums.order_status import OrderStatus

        unpacked_cb = MyProfileCallback.unpack(callback.data)
        items = await ItemRepository.get_by_buy_id(unpacked_cb.args_for_action, session)

        # Get order information via first item's order_id
        order = None
        invoice_numbers = []
        if items and items[0].order_id:
            order = await OrderRepository.get_by_id(items[0].order_id, session)

            # Get ALL invoices for this order (multiple invoices in case of underpayment)
            invoices = await InvoiceRepository.get_all_by_order_id(order.id, session)
            if invoices:
                invoice_numbers = [inv.invoice_number for inv in invoices]
            else:
                # Fallback for orders without invoice (should not happen in normal flow)
                from datetime import datetime
                fallback_ref = "N/A"
                invoice_numbers = [fallback_ref]

        # All purchases should have an order (no legacy support)
        from exceptions.order import OrderNotFoundException

        if not order:
            raise OrderNotFoundException(items[0].order_id if items and items[0].order_id else unpacked_cb.args_for_action)

        from services.invoice_formatter import InvoiceFormatter
        from services.order import OrderService

        # Build unified items list with private_data
        items_raw = []
        for item in items:
            items_raw.append({
                'name': item.description,
                'price': item.price,
                'quantity': 1,  # Each item is already individual
                'is_physical': item.is_physical,
                'private_data': item.private_data
            })

        # Group items by (name, price, is_physical, private_data)
        items_list = OrderService._group_items_for_display(items_raw)

        # Calculate subtotal (total - shipping)
        subtotal = order.total_price - order.shipping_cost

        # Format invoice numbers (one per line for multiple invoices)
        invoice_numbers_formatted = "\n".join(invoice_numbers)

        # Use InvoiceFormatter for consistent formatting
        msg = InvoiceFormatter.format_complete_order_view(
            header_type="purchase_history",
            invoice_number=invoice_numbers_formatted,
            order_status=order.status,
            created_at=order.created_at,
            paid_at=order.paid_at,
            shipped_at=order.shipped_at,
            items=items_list,
            subtotal=subtotal,
            shipping_cost=order.shipping_cost,
            total_price=order.total_price,
            separate_digital_physical=True,  # Always use separated view
            show_private_data=True,  # Show keys/codes in purchase history
            show_retention_notice=any(item.private_data for item in items),
            currency_symbol=Localizator.get_currency_symbol(),
            entity=BotEntity.USER
        )

        kb_builder = InlineKeyboardBuilder()
        kb_builder.row(unpacked_cb.get_back_button())
        return msg, kb_builder
