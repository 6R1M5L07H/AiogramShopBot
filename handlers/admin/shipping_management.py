from aiogram import Router, types
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import ShippingManagementCallback, AdminMenuCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.order_status import OrderStatus
from handlers.admin.admin_states import AdminOrderCancellationStates
from services.shipping import ShippingService
from utils.custom_filters import AdminIdFilter
from utils.localizator import Localizator

shipping_management_router = Router()


async def show_order_filters(**kwargs):
    """Level 0: Shows filter selection for order management"""
    callback = kwargs.get("callback")
    callback_data = kwargs.get("callback_data")

    # Get current filter (if any) to highlight it
    current_filter = callback_data.filter_type if callback_data else None

    message_text = Localizator.get_text(BotEntity.ADMIN, "order_management_title") + "\n\n"
    message_text += "🔍 <b>Filter wählen:</b>"

    kb_builder = InlineKeyboardBuilder()

    # Import filter types
    from enums.order_filter import OrderFilterType

    # Main filter groups (most important at top)
    filter_buttons = [
        (OrderFilterType.REQUIRES_ACTION, "order_filter_requires_action", "⚠️"),
        (OrderFilterType.ALL, "order_filter_all", "📋"),
        (OrderFilterType.ACTIVE, "order_filter_active", "🔄"),
        (OrderFilterType.COMPLETED, "order_filter_completed", "✅"),
        (OrderFilterType.CANCELLED, "order_filter_cancelled", "❌"),
    ]

    for filter_type, localization_key, icon in filter_buttons:
        button_text = Localizator.get_text(BotEntity.ADMIN, localization_key)

        # Highlight current filter
        if current_filter == filter_type or (current_filter is None and filter_type == OrderFilterType.REQUIRES_ACTION):
            button_text = f"• {button_text} •"

        kb_builder.button(
            text=button_text,
            callback_data=ShippingManagementCallback.create(level=1, filter_type=filter_type, page=0).pack()
        )

    kb_builder.adjust(1)  # One button per row

    # Back to admin menu
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
        callback_data=AdminMenuCallback.create(level=0).pack()
    )

    if isinstance(callback, CallbackQuery):
        await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def show_awaiting_shipment_orders(**kwargs):
    """
    Level 1: Shows list of orders with pagination and filters.

    Wrapper around unified OrderManagementService.
    """
    from services.order_management import OrderManagementService

    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")

    filter_type = callback_data.filter_type if callback_data else None
    page = callback_data.page if callback_data else 0

    message_text, kb_builder = await OrderManagementService.get_order_list_view(
        session=session,
        page=page,
        filter_type=filter_type,
        user_id=None,  # Admin sees all users
        entity=BotEntity.ADMIN,
        callback_factory=ShippingManagementCallback
    )

    if isinstance(callback, CallbackQuery):
        await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def show_order_details(**kwargs):
    """Level 2: Shows order details with shipping address"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")

    order_id = callback_data.order_id
    filter_type = callback_data.filter_type if callback_data else None
    page = callback_data.page if callback_data else 0

    # Get order details (via Service with error handling)
    try:
        details = await ShippingService.get_order_details_data(order_id, session)
    except ValueError:
        # Order not found - show error and return to list
        error_text = Localizator.get_text(BotEntity.ADMIN, "error_order_not_found")
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=ShippingManagementCallback.create(level=1, filter_type=filter_type, page=page).pack()
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

    # Format order details using InvoiceFormatter
    from services.invoice_formatter import InvoiceFormatter

    message_text = InvoiceFormatter.format_admin_order_view(
        invoice_number=invoice_number,
        username=username,
        user_id=user_id,
        digital_items=digital_items if digital_items else None,
        physical_items=physical_items if physical_items else None,
        shipping_cost=order.shipping_cost,
        total_price=order.total_price,
        shipping_address=shipping_address,
        currency_symbol=Localizator.get_currency_symbol()
    )

    # Add Order Status section
    message_text += "\n\n─────────────────────\n"
    message_text += "📊 <b>BESTELLSTATUS</b>\n\n"

    # Map OrderStatus to localized string (UPPERCASE keys)
    status_map = {
        OrderStatus.PENDING_PAYMENT: "order_status_PENDING_PAYMENT",
        OrderStatus.PENDING_PAYMENT_AND_ADDRESS: "order_status_PENDING_PAYMENT_AND_ADDRESS",
        OrderStatus.PENDING_PAYMENT_PARTIAL: "order_status_PENDING_PAYMENT_PARTIAL",
        OrderStatus.PAID: "order_status_PAID",
        OrderStatus.PAID_AWAITING_SHIPMENT: "order_status_PAID_AWAITING_SHIPMENT",
        OrderStatus.SHIPPED: "order_status_SHIPPED",
        OrderStatus.CANCELLED_BY_USER: "order_status_CANCELLED_BY_USER",
        OrderStatus.CANCELLED_BY_ADMIN: "order_status_CANCELLED_BY_ADMIN",
        OrderStatus.CANCELLED_BY_SYSTEM: "order_status_CANCELLED_BY_SYSTEM",
        OrderStatus.TIMEOUT: "order_status_TIMEOUT",
    }

    status_key = status_map.get(order.status, "order_status_PENDING_PAYMENT")
    status_text = Localizator.get_text(BotEntity.COMMON, status_key)
    message_text += f"<b>Status:</b> {status_text}\n"

    # Add timestamps based on status
    if order.paid_at:
        paid_at_str = order.paid_at.strftime("%d.%m.%Y %H:%M:%S")
        message_text += f"<b>Bezahlt am:</b> {paid_at_str}\n"
    if order.shipped_at:
        shipped_at_str = order.shipped_at.strftime("%d.%m.%Y %H:%M:%S")
        message_text += f"<b>Versendet am:</b> {shipped_at_str}\n"
    if order.cancelled_at:
        cancelled_at_str = order.cancelled_at.strftime("%d.%m.%Y %H:%M:%S")
        message_text += f"<b>Storniert am:</b> {cancelled_at_str}\n"

    # Add Payment History section (if order is paid)
    if order.status in [OrderStatus.PAID, OrderStatus.PAID_AWAITING_SHIPMENT, OrderStatus.SHIPPED]:
        try:
            from services.payment import PaymentService
            payment_history = await PaymentService.get_payment_history_details(order_id, session)

            message_text += "\n\n─────────────────────\n"
            message_text += f"💳 <b>{Localizator.get_text(BotEntity.ADMIN, 'order_payment_history_title')}</b>\n\n"

            # Order timestamps
            created_at_str = payment_history['order_created_at'].strftime("%d.%m.%Y %H:%M:%S")
            message_text += f"{Localizator.get_text(BotEntity.ADMIN, 'order_created_at')}: {created_at_str}\n"

            if payment_history['payment_received_at']:
                paid_at_str = payment_history['payment_received_at'].strftime("%d.%m.%Y %H:%M:%S")
                message_text += f"{Localizator.get_text(BotEntity.ADMIN, 'order_paid_at')}: {paid_at_str}\n"

            message_text += "\n"

            # Payment method
            wallet_used = payment_history['wallet_amount_used']
            crypto_payments = payment_history['crypto_payments']

            if wallet_used > 0 and len(crypto_payments) > 0:
                payment_method = "Gemischt (Guthaben + Krypto)"
            elif wallet_used > 0:
                payment_method = "Guthaben"
            elif len(crypto_payments) > 0:
                payment_method = "Kryptowährung"
            else:
                payment_method = "Unbekannt"

            message_text += f"<b>{Localizator.get_text(BotEntity.ADMIN, 'order_payment_method')}:</b> {payment_method}\n\n"

            # Wallet amount
            if wallet_used > 0:
                message_text += f"{Localizator.get_text(BotEntity.ADMIN, 'order_wallet_used')}: {wallet_used:.2f} {Localizator.get_currency_symbol()}\n"

            # Crypto payments
            for idx, crypto_payment in enumerate(crypto_payments, 1):
                message_text += f"\n<b>{Localizator.get_text(BotEntity.ADMIN, 'order_crypto_payment').format(currency=crypto_payment['currency'])}</b>\n"
                message_text += f"  Betrag: {crypto_payment['crypto_amount']} {crypto_payment['currency']} (≈ {crypto_payment['fiat_amount']:.2f} {Localizator.get_currency_symbol()})\n"
                message_text += f"  {Localizator.get_text(BotEntity.ADMIN, 'order_kryptoexpress_tx_id')}: <code>{crypto_payment['kryptoexpress_transaction_id']}</code>\n"
                message_text += f"  {Localizator.get_text(BotEntity.ADMIN, 'order_kryptoexpress_order_id')}: {crypto_payment['kryptoexpress_order_id']}\n"
                message_text += f"  {Localizator.get_text(BotEntity.ADMIN, 'order_payment_address')}: <code>{crypto_payment['payment_address'][:20]}...</code>\n"

                if crypto_payment['transaction_hash']:
                    message_text += f"  {Localizator.get_text(BotEntity.ADMIN, 'order_transaction_hash')}: <code>{crypto_payment['transaction_hash'][:16]}...</code>\n"

                confirmed_at_str = crypto_payment['confirmed_at'].strftime("%d.%m.%Y %H:%M:%S")
                message_text += f"  {Localizator.get_text(BotEntity.ADMIN, 'order_confirmed_at')}: {confirmed_at_str}\n"

                # Payment flags
                if crypto_payment['is_overpayment']:
                    message_text += f"  {Localizator.get_text(BotEntity.ADMIN, 'order_overpayment_note').format(amount=crypto_payment['wallet_credit_amount'] or 0, currency_sym=Localizator.get_currency_symbol())}\n"
                if crypto_payment['is_underpayment']:
                    message_text += f"  {Localizator.get_text(BotEntity.ADMIN, 'order_underpayment_note')}\n"
                if crypto_payment['is_late_payment']:
                    message_text += f"  {Localizator.get_text(BotEntity.ADMIN, 'order_late_payment_note').format(penalty_percent=crypto_payment['penalty_percent'])}\n"

            # Summary
            message_text += "\n"
            message_text += f"{Localizator.get_text(BotEntity.ADMIN, 'order_underpayment_retries')}: {payment_history['underpayment_retries']}\n"

            if payment_history['late_payment_penalty'] > 0:
                message_text += f"{Localizator.get_text(BotEntity.ADMIN, 'order_late_penalty')}: {payment_history['late_payment_penalty']:.2f} {Localizator.get_currency_symbol()}\n"

            message_text += f"<b>{Localizator.get_text(BotEntity.ADMIN, 'order_total_paid')}: {payment_history['total_paid']:.2f} {Localizator.get_currency_symbol()}</b>\n"

        except Exception as e:
            # If payment history fails, just skip it (don't break the whole view)
            import logging
            logging.warning(f"Failed to load payment history for order {order_id}: {e}")

    # Determine item types
    has_physical_items = bool(physical_items)
    has_digital_items = bool(digital_items)

    # Build action buttons based on order type and status
    kb_builder = InlineKeyboardBuilder()

    # "Mark as Shipped" button: Only for physical items awaiting shipment
    if has_physical_items and order.status == OrderStatus.PAID_AWAITING_SHIPMENT:
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "mark_as_shipped"),
            callback_data=ShippingManagementCallback.create(level=3, order_id=order_id).pack()
        )

    # "Cancel Order" button: Logic based on status and item types
    # - Always show for PENDING_* statuses (not yet paid/delivered)
    # - For PAID/PAID_AWAITING_SHIPMENT: Only if NO digital items (digital = already delivered, non-refundable)
    pending_statuses = [
        OrderStatus.PENDING_PAYMENT,
        OrderStatus.PENDING_PAYMENT_AND_ADDRESS,
        OrderStatus.PENDING_PAYMENT_PARTIAL
    ]

    show_cancel = False
    if order.status in pending_statuses:
        show_cancel = True  # Not paid yet, can always cancel
    elif order.status == OrderStatus.PAID_AWAITING_SHIPMENT and not has_digital_items:
        show_cancel = True  # Only physical items, not yet shipped, can cancel

    if show_cancel:
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "cancel_order_admin"),
            callback_data=ShippingManagementCallback.create(level=5, order_id=order_id).pack()
        )

    kb_builder.adjust(1)
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "back_button"),
        callback_data=ShippingManagementCallback.create(level=1, filter_type=filter_type, page=page).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def mark_as_shipped_confirm(**kwargs):
    """Level 3: Confirmation before marking as shipped"""
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
        callback_data=ShippingManagementCallback.create(level=4, order_id=order_id, confirmation=True).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=ShippingManagementCallback.create(level=2, order_id=order_id).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def mark_as_shipped_execute(**kwargs):
    """Level 4: Execute mark as shipped"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = kwargs.get("callback_data")

    order_id = callback_data.order_id

    # Mark order as shipped (via Service - handles status update and notification)
    from exceptions import OrderNotFoundException, ShopBotException

    try:
        result = await ShippingService.mark_order_as_shipped(order_id, session)
        invoice_number = result["invoice_number"]

    except OrderNotFoundException:
        # Order not found
        error_text = Localizator.get_text(BotEntity.ADMIN, "error_order_not_found")
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=ShippingManagementCallback.create(level=1).pack()
        )
        await callback.message.edit_text(error_text, reply_markup=kb_builder.as_markup())
        return

    except ShopBotException as e:
        error_text = f"❌ Error: {str(e)}"
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=ShippingManagementCallback.create(level=1).pack()
        )
        await callback.message.edit_text(error_text, reply_markup=kb_builder.as_markup())
        return

    except Exception as e:
        logging.exception(f"Unexpected error marking order as shipped: {e}")
        error_text = "❌ An unexpected error occurred"
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
            callback_data=ShippingManagementCallback.create(level=1).pack()
        )
        await callback.message.edit_text(error_text, reply_markup=kb_builder.as_markup())
        return

    # Success message
    message_text = Localizator.get_text(BotEntity.ADMIN, "order_marked_shipped").format(invoice_number=invoice_number)

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
        callback_data=ShippingManagementCallback.create(level=1).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def cancel_order_admin_confirm(**kwargs):
    """Level 5: Choose cancellation path (with or without reason)"""
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
        callback_data=ShippingManagementCallback.create(level=6, order_id=order_id).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "cancel_without_reason"),
        callback_data=ShippingManagementCallback.create(level=8, order_id=order_id).pack()
    )
    kb_builder.adjust(1)
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "back_button"),
        callback_data=ShippingManagementCallback.create(level=2, order_id=order_id).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def cancel_order_admin_request_reason(**kwargs):
    """Level 6: Request cancellation reason from admin"""
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
        callback_data=ShippingManagementCallback.create(level=2, order_id=order_id).pack()
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
        callback_data=ShippingManagementCallback.create(level=7, order_id=order_id, confirmation=True).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=ShippingManagementCallback.create(level=2, order_id=order_id).pack()
    )

    await message.answer(message_text, reply_markup=kb_builder.as_markup())


async def cancel_order_admin_execute(**kwargs):
    """Level 7: Execute order cancellation with custom reason"""
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
    from exceptions import OrderNotFoundException, InvalidOrderStateException, ShopBotException

    try:
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

    except OrderNotFoundException:
        await state.clear()
        message_text = "❌ Order not found"

    except InvalidOrderStateException as e:
        await state.clear()
        message_text = f"❌ Cannot cancel order: Order is {e.current_state}"

    except ShopBotException as e:
        await state.clear()
        message_text = f"❌ Error: {str(e)}"

    except Exception as e:
        logging.exception(f"Unexpected error cancelling order: {e}")
        await state.clear()
        message_text = "❌ An unexpected error occurred"

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
        callback_data=ShippingManagementCallback.create(level=1).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def cancel_order_admin_without_reason(**kwargs):
    """Level 8: Execute order cancellation without custom reason"""
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
    from exceptions import OrderNotFoundException, InvalidOrderStateException, ShopBotException

    try:
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

    except OrderNotFoundException:
        await state.clear()
        message_text = "❌ Order not found"

    except InvalidOrderStateException as e:
        await state.clear()
        message_text = f"❌ Cannot cancel order: Order is {e.current_state}"

    except ShopBotException as e:
        await state.clear()
        message_text = f"❌ Error: {str(e)}"

    except Exception as e:
        logging.exception(f"Unexpected error cancelling order: {e}")
        await state.clear()
        message_text = "❌ An unexpected error occurred"

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "back_to_menu"),
        callback_data=ShippingManagementCallback.create(level=1).pack()
    )

    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


@shipping_management_router.callback_query(AdminIdFilter(), ShippingManagementCallback.filter())
async def shipping_management_navigation(callback: CallbackQuery, callback_data: ShippingManagementCallback, session: AsyncSession | Session, state: FSMContext):
    # Clear FSM state when cancelling (going back to level 2), but NOT when going to level 7 (execute)
    current_state = await state.get_state()
    if current_state == AdminOrderCancellationStates.waiting_for_cancellation_reason and callback_data.level == 2:
        await state.clear()

    current_level = callback_data.level

    levels = {
        0: show_order_filters,              # NEW: Filter selection
        1: show_awaiting_shipment_orders,   # Was Level 0
        2: show_order_details,              # Was Level 1
        3: mark_as_shipped_confirm,         # Was Level 2
        4: mark_as_shipped_execute,         # Was Level 3
        5: cancel_order_admin_confirm,      # Was Level 4
        6: cancel_order_admin_request_reason,  # Was Level 5
        7: cancel_order_admin_execute,      # Was Level 6
        8: cancel_order_admin_without_reason,  # Was Level 7
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "session": session,
        "callback_data": callback_data,
        "state": state,
    }

    await current_level_function(**kwargs)
