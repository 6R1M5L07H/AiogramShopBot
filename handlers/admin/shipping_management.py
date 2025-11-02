from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import ShippingManagementCallback, AdminMenuCallback
from db import session_commit
from enums.bot_entity import BotEntity
from handlers.admin.admin_states import AdminOrderCancellationStates
from services.shipping import ShippingService
from utils.custom_filters import AdminIdFilter
from utils.localizator import Localizator

shipping_management_router = Router()


async def show_awaiting_shipment_orders(**kwargs):
    """Level 0: Shows list of orders awaiting shipment"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")

    # Get all orders with PAID_AWAITING_SHIPMENT status (via Service)
    orders = await ShippingService.get_pending_shipments(session)

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
            # Get formatted display data (via Service)
            display_data = await ShippingService.get_order_display_data(order, session)

            button_text = f"📦 {display_data['created_time']} | {display_data['invoice_display']} | {display_data['user_display']} | {order.total_price:.2f}{Localizator.get_currency_symbol()}"
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

    # Get order details (via Service with error handling)
    try:
        details = await ShippingService.get_order_details_data(order_id, session)
    except ValueError:
        # Order not found - show error and return to list
        error_text = Localizator.get_text(BotEntity.ADMIN, "error_order_not_found")
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=ShippingManagementCallback.create(level=0).pack()
        )
        await callback.message.edit_text(error_text, reply_markup=kb_builder.as_markup())
        return

    # Extract data from service response
    order = details["order"]
    invoice_number = details["invoice_number"]
    username = details["username"]
    user_id = details["user_id"]
    shipping_address = details["shipping_address"]
    digital_items = details["digital_items"]
    physical_items = details["physical_items"]

    # Build message header with invoice number and user info
    message_text = Localizator.get_text(BotEntity.ADMIN, "order_details_header").format(
        invoice_number=invoice_number,
        username=username,
        user_id=user_id
    )

    message_text += "\n\n"

    # Digital items (delivered)
    digital_total = 0.0
    if digital_items:
        message_text += "<b>Digital:</b>\n"
        for (description, price), qty in digital_items.items():
            line_total = qty * price
            digital_total += line_total
            if qty == 1:
                message_text += f"{qty} Stk. {description} {price:.2f}\n"
            else:
                message_text += f"{qty} Stk. {description} {price:.2f} = {line_total:.2f}\n"
        message_text += "\n"

    # Physical items (to be shipped)
    physical_total = 0.0
    if physical_items:
        message_text += "<b>Versandartikel:</b>\n"
        for (description, price), qty in physical_items.items():
            line_total = qty * price
            physical_total += line_total
            if qty == 1:
                message_text += f"{qty} Stk. {description} {price:.2f}\n"
            else:
                message_text += f"{qty} Stk. {description} {price:.2f} = {line_total:.2f}\n"
        message_text += "\n"

    # Price breakdown
    message_text += "═══════════════════════\n"
    if order.shipping_cost > 0:
        message_text += f"Versand {order.shipping_cost:.2f}\n\n"
    message_text += f"<b>Total: {order.total_price:.2f} {Localizator.get_currency_symbol()}</b>\n"
    message_text += "═══════════════════════\n"

    # Shipping address
    if shipping_address:
        message_text += "\n<b>Adressdaten:</b>\n"
        message_text += f"{shipping_address}"

    # Buttons
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "mark_as_shipped"),
        callback_data=ShippingManagementCallback.create(level=2, order_id=order_id).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "cancel_order_admin"),
        callback_data=ShippingManagementCallback.create(level=4, order_id=order_id).pack()
    )
    kb_builder.adjust(1)
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

    # Get invoice number for display (via Service)
    invoice_number = await ShippingService.get_invoice_number(order_id, session)

    message_text = Localizator.get_text(BotEntity.ADMIN, "confirm_mark_shipped").format(invoice_number=invoice_number)

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

    # Mark order as shipped (via Service - handles status update and notification)
    try:
        result = await ShippingService.mark_order_as_shipped(order_id, session)
        invoice_number = result["invoice_number"]
    except ValueError:
        # Order not found
        error_text = Localizator.get_text(BotEntity.ADMIN, "error_order_not_found")
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=ShippingManagementCallback.create(level=0).pack()
        )
        await callback.message.edit_text(error_text, reply_markup=kb_builder.as_markup())
        return

    # Success message
    message_text = Localizator.get_text(BotEntity.ADMIN, "order_marked_shipped").format(invoice_number=invoice_number)

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
        callback_data=ShippingManagementCallback.create(level=0).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def cancel_order_admin_confirm(**kwargs):
    """Level 4: Choose cancellation path (with or without reason)"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")

    order_id = callback_data.order_id

    # Get invoice number for display (via Service)
    invoice_number = await ShippingService.get_invoice_number(order_id, session)

    message_text = Localizator.get_text(BotEntity.ADMIN, "choose_cancel_order_path").format(
        invoice_number=invoice_number
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "cancel_with_reason"),
        callback_data=ShippingManagementCallback.create(level=5, order_id=order_id).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "cancel_without_reason"),
        callback_data=ShippingManagementCallback.create(level=7, order_id=order_id).pack()
    )
    kb_builder.adjust(1)
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "back_button"),
        callback_data=ShippingManagementCallback.create(level=1, order_id=order_id).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def cancel_order_admin_request_reason(**kwargs):
    """Level 5: Request cancellation reason from admin"""
    callback = kwargs.get("callback")
    callback_data = kwargs.get("callback_data")
    state = kwargs.get("state")

    order_id = callback_data.order_id

    # Store order_id in FSM context
    await state.update_data(order_id=order_id)

    # Set FSM state
    await state.set_state(AdminOrderCancellationStates.waiting_for_cancellation_reason)

    # Prompt for reason with cancel button
    message_text = Localizator.get_text(BotEntity.ADMIN, "enter_cancellation_reason")

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=ShippingManagementCallback.create(level=1, order_id=order_id).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


@shipping_management_router.message(AdminOrderCancellationStates.waiting_for_cancellation_reason, AdminIdFilter())
async def process_cancellation_reason(message: Message, state: FSMContext, session: AsyncSession | Session):
    """Store cancellation reason and show confirmation"""
    # Get order_id from FSM context
    data = await state.get_data()
    order_id = data.get("order_id")

    if not order_id:
        await message.answer(Localizator.get_text(BotEntity.ADMIN, "error_order_not_found"))
        await state.clear()
        return

    custom_reason = message.text

    # Store reason in FSM for confirmation step
    await state.update_data(custom_reason=custom_reason)

    # Get invoice number for display (via Service)
    invoice_number = await ShippingService.get_invoice_number(order_id, session)

    # Show confirmation with order details and reason
    message_text = Localizator.get_text(BotEntity.ADMIN, "confirm_cancel_with_reason").format(
        invoice_number=invoice_number,
        reason=custom_reason
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "confirm"),
        callback_data=ShippingManagementCallback.create(level=6, order_id=order_id, confirmation=True).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=ShippingManagementCallback.create(level=1, order_id=order_id).pack()
    )

    await message.answer(message_text, reply_markup=kb_builder.as_markup())


async def cancel_order_admin_execute(**kwargs):
    """Level 6: Execute order cancellation with custom reason"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")
    state = kwargs.get("state")

    order_id = callback_data.order_id

    # Get reason from FSM context
    data = await state.get_data()
    custom_reason = data.get("custom_reason")

    if not custom_reason:
        await callback.message.edit_text(Localizator.get_text(BotEntity.ADMIN, "error_order_not_found"))
        await state.clear()
        return

    # Get invoice number for display (via Service)
    invoice_number = await ShippingService.get_invoice_number(order_id, session)

    # Cancel order using OrderService with custom reason
    from services.order import OrderService
    from enums.order_cancel_reason import OrderCancelReason

    await OrderService.cancel_order(
        order_id=order_id,
        reason=OrderCancelReason.ADMIN,
        session=session,
        refund_wallet=True,  # Full refund, no penalty for admin cancellation
        custom_reason=custom_reason  # Pass custom reason
    )
    await session_commit(session)

    # Clear FSM state
    await state.clear()

    # Success message
    message_text = Localizator.get_text(BotEntity.ADMIN, "order_cancelled_by_admin_with_reason").format(
        invoice_number=invoice_number,
        reason=custom_reason
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
        callback_data=ShippingManagementCallback.create(level=0).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def cancel_order_admin_without_reason(**kwargs):
    """Level 7: Execute order cancellation without custom reason"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")
    state = kwargs.get("state")

    order_id = callback_data.order_id

    # Get invoice number for display (via Service)
    invoice_number = await ShippingService.get_invoice_number(order_id, session)

    # Cancel order using OrderService WITHOUT custom reason
    from services.order import OrderService
    from enums.order_cancel_reason import OrderCancelReason

    await OrderService.cancel_order(
        order_id=order_id,
        reason=OrderCancelReason.ADMIN,
        session=session,
        refund_wallet=True,
        custom_reason=None  # No custom reason
    )
    await session_commit(session)

    # Clear FSM state (in case it was set)
    await state.clear()

    # Success message
    message_text = Localizator.get_text(BotEntity.ADMIN, "order_cancelled_by_admin_no_reason").format(
        invoice_number=invoice_number
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
        callback_data=ShippingManagementCallback.create(level=0).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


@shipping_management_router.callback_query(AdminIdFilter(), ShippingManagementCallback.filter())
async def shipping_management_navigation(callback: CallbackQuery, callback_data: ShippingManagementCallback, session: AsyncSession | Session, state: FSMContext):
    # Clear FSM state when cancelling (going back to level 1), but NOT when going to level 6 (execute)
    current_state = await state.get_state()
    if current_state == AdminOrderCancellationStates.waiting_for_cancellation_reason and callback_data.level == 1:
        await state.clear()

    current_level = callback_data.level

    levels = {
        0: show_awaiting_shipment_orders,
        1: show_order_details,
        2: mark_as_shipped_confirm,
        3: mark_as_shipped_execute,
        4: cancel_order_admin_confirm,
        5: cancel_order_admin_request_reason,
        6: cancel_order_admin_execute,
        7: cancel_order_admin_without_reason,
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "session": session,
        "callback_data": callback_data,
        "state": state,
    }

    await current_level_function(**kwargs)
