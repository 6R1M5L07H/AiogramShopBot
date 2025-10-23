from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import ShippingManagementCallback, AdminMenuCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.order_status import OrderStatus
from repositories.invoice import InvoiceRepository
from repositories.order import OrderRepository
from repositories.user import UserRepository
from services.notification import NotificationService
from services.shipping import ShippingService
from utils.custom_filters import AdminIdFilter
from utils.localizator import Localizator

shipping_management_router = Router()


async def show_awaiting_shipment_orders(**kwargs):
    """Level 0: Shows list of orders awaiting shipment"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")

    # Get all orders with PAID_AWAITING_SHIPMENT status
    orders = await OrderRepository.get_orders_awaiting_shipment(session)

    if not orders:
        # No orders awaiting shipment
        message_text = Localizator.get_text(BotEntity.ADMIN, "no_orders_awaiting_shipment")
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=AdminMenuCallback.create(level=0).pack()
        )
    else:
        # Show list of orders
        message_text = Localizator.get_text(BotEntity.ADMIN, "awaiting_shipment_orders") + "\n\n"

        kb_builder = InlineKeyboardBuilder()

        for order in orders:
            # Get invoice number for display
            invoice = await InvoiceRepository.get_by_order_id(order.id, session)
            user = await UserRepository.get_by_id(order.user_id, session)
            username = f"@{user.telegram_username}" if user.telegram_username else f"ID:{user.telegram_id}"

            button_text = f"📦 Order #{invoice.invoice_number} | {username} | {order.total_price:.2f}{Localizator.get_currency_symbol()}"
            kb_builder.button(
                text=button_text,
                callback_data=ShippingManagementCallback.create(level=1, order_id=order.id).pack()
            )

        kb_builder.adjust(1)  # One button per row
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=AdminMenuCallback.create(level=0).pack()
        )

    if isinstance(callback, CallbackQuery):
        await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def show_order_details(**kwargs):
    """Level 1: Shows order details with shipping address"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")

    order_id = callback_data.order_id

    # Get order details
    order = await OrderRepository.get_by_id_with_items(order_id, session)
    invoice = await InvoiceRepository.get_by_order_id(order_id, session)
    user = await UserRepository.get_by_id(order.user_id, session)
    shipping_address = await ShippingService.get_shipping_address(order_id, session)

    username = f"@{user.telegram_username}" if user.telegram_username else str(user.telegram_id)

    # Build message
    message_text = Localizator.get_text(BotEntity.ADMIN, "order_details_header").format(order_id=order_id) + "\n\n"
    message_text += Localizator.get_text(BotEntity.ADMIN, "order_user").format(
        username=username, user_id=user.telegram_id
    ) + "\n\n"

    # Calculate items total
    items_total = sum(item.price for item in order.items)

    # Show price breakdown
    message_text += f"<b>Artikel:</b> {items_total:.2f}{Localizator.get_currency_symbol()}\n"
    if order.shipping_cost > 0:
        message_text += f"<b>Versand:</b> {order.shipping_cost:.2f}{Localizator.get_currency_symbol()}\n"
    message_text += f"<b><u>Gesamtsumme:</u></b> {order.total_price:.2f}{Localizator.get_currency_symbol()}\n\n"

    # Shipping address
    if shipping_address:
        message_text += Localizator.get_text(BotEntity.ADMIN, "order_shipping_address").format(
            address=shipping_address
        ) + "\n\n"

    # Items list (only physical items need shipping)
    items_text = ""
    for item in order.items:
        if item.is_physical:
            items_text += f"- {item.description} ({item.price:.2f}{Localizator.get_currency_symbol()})\n"

    message_text += Localizator.get_text(BotEntity.ADMIN, "order_items_list").format(items=items_text)

    # Buttons
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "mark_as_shipped"),
        callback_data=ShippingManagementCallback.create(level=2, order_id=order_id).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "back_button"),
        callback_data=ShippingManagementCallback.create(level=0).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def mark_as_shipped_confirm(**kwargs):
    """Level 2: Confirmation before marking as shipped"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")

    order_id = callback_data.order_id

    # Get invoice number for display
    invoice = await InvoiceRepository.get_by_order_id(order_id, session)

    message_text = Localizator.get_text(BotEntity.ADMIN, "confirm_mark_shipped").format(order_id=invoice.invoice_number)

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "confirm"),
        callback_data=ShippingManagementCallback.create(level=3, order_id=order_id, confirmation=True).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=ShippingManagementCallback.create(level=1, order_id=order_id).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def mark_as_shipped_execute(**kwargs):
    """Level 3: Execute mark as shipped"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")

    order_id = callback_data.order_id

    # Update order status to SHIPPED
    await OrderRepository.update_status(order_id, OrderStatus.SHIPPED, session)
    await session_commit(session)

    # Send notification to user
    order = await OrderRepository.get_by_id(order_id, session)
    invoice = await InvoiceRepository.get_by_order_id(order_id, session)
    await NotificationService.order_shipped(order.user_id, invoice.invoice_number, session)

    # Success message
    message_text = Localizator.get_text(BotEntity.ADMIN, "order_marked_shipped").format(order_id=order_id)

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
        callback_data=ShippingManagementCallback.create(level=0).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


@shipping_management_router.callback_query(AdminIdFilter(), ShippingManagementCallback.filter())
async def shipping_management_navigation(callback: CallbackQuery, callback_data: ShippingManagementCallback, session: AsyncSession | Session):
    current_level = callback_data.level

    levels = {
        0: show_awaiting_shipment_orders,
        1: show_order_details,
        2: mark_as_shipped_confirm,
        3: mark_as_shipped_execute,
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "session": session,
        "callback_data": callback_data,
    }

    await current_level_function(**kwargs)
