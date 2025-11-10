import logging
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import CartCallback, OrderCallback
from db import session_commit
from enums.bot_entity import BotEntity
from enums.order_status import OrderStatus
from models.cart import CartDTO
from models.user import UserDTO
from repositories.cartItem import CartItemRepository
from repositories.item import ItemRepository
from repositories.order import OrderRepository
from repositories.user import UserRepository
from services.order import OrderService
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator

order_router = Router()


# ============================================================================
# Helper Functions for create_order()
# ============================================================================

async def _check_order_rate_limit(
    callback: CallbackQuery
) -> tuple[bool, str | None, InlineKeyboardBuilder | None]:
    """
    Check if user has exceeded order creation rate limit.

    Returns:
        tuple: (is_limited, message_text, keyboard_builder)
        - If is_limited is False: message_text and keyboard_builder are None
        - If is_limited is True: message_text and keyboard_builder contain error UI
    """
    from middleware.rate_limit import RateLimiter
    from enums.rate_limit_operation import RateLimitOperation
    from bot import redis

    limiter = RateLimiter(redis)
    is_limited, current_count, remaining = await limiter.is_rate_limited(
        RateLimitOperation.ORDER_CREATE,
        callback.from_user.id,
        max_count=config.MAX_ORDERS_PER_USER_PER_HOUR,
        window_seconds=3600
    )

    if not is_limited:
        return False, None, None

    # Rate limited - build error response
    reset_time = await limiter.get_remaining_time(RateLimitOperation.ORDER_CREATE, callback.from_user.id)
    reset_minutes = reset_time // 60

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "back_button"),
        callback_data=CartCallback.create(0)
    )

    message_text = Localizator.get_text(BotEntity.USER, "rate_limit_orders").format(
        max_count=config.MAX_ORDERS_PER_USER_PER_HOUR,
        reset_minutes=reset_minutes
    )
    logging.warning(f"Rate limit: user={callback.from_user.id}, orders={current_count}/{config.MAX_ORDERS_PER_USER_PER_HOUR}")

    return True, message_text, kb_builder


async def _get_and_validate_cart(
    callback: CallbackQuery,
    session: AsyncSession | Session
) -> tuple[UserDTO | None, list, str | None, InlineKeyboardBuilder | None]:
    """
    Get cart items and validate cart is not empty.

    Returns:
        tuple: (user, cart_items, error_message, error_keyboard)
        - If successful: user and cart_items are set, error fields are None
        - If error: error_message and error_keyboard are set
    """
    user = await UserRepository.get_by_tgid(callback.from_user.id, session)
    cart_items = await CartItemRepository.get_all_by_user_id(user.id, session)

    if cart_items:
        return user, cart_items, None, None

    # Empty cart error
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "back_button"),
        callback_data=CartCallback.create(0)
    )
    return user, [], Localizator.get_text(BotEntity.USER, "no_cart_items"), kb_builder


async def _handle_stock_adjustments(
    callback: CallbackQuery,
    order,
    stock_adjustments: list,
    state,
    session: AsyncSession | Session
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Handle UI for stock adjustments (items removed or quantity reduced).

    Returns:
        tuple: (message_text, keyboard_builder)
    """
    # Store adjustments in FSM state for potential back navigation
    if state:
        import json
        await state.update_data(
            stock_adjustments=json.dumps(stock_adjustments),
            order_id=order.id
        )

    return await OrderService.show_stock_adjustment_confirmation(
        callback, order, stock_adjustments, session
    )


async def _handle_physical_items_flow(
    order,
    state
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Handle UI flow for orders with physical items (request shipping address).

    Returns:
        tuple: (message_text, keyboard_builder)
    """
    from handlers.user.shipping_states import ShippingAddressStates
    await state.set_state(ShippingAddressStates.waiting_for_address)

    message_text = Localizator.get_text(BotEntity.USER, "shipping_address_request").format(
        retention_days=config.DATA_RETENTION_DAYS
    )
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=OrderCallback.create(level=4, order_id=order.id)
    )
    return message_text, kb_builder


async def _handle_order_creation_error(
    user,
    cart_items: list,
    session: AsyncSession | Session
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Handle error when all items are out of stock.

    Cleans up cart and returns error UI.

    Returns:
        tuple: (message_text, keyboard_builder)
    """
    # Remove all out-of-stock items from cart immediately to prevent loop
    logging.info(f"🧹 Removing all out-of-stock items from cart for user {user.id}")
    for cart_item in cart_items:
        await CartItemRepository.remove_from_cart(cart_item.id, session)
    await session_commit(session)

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.USER, "back_to_cart"),
        callback_data=CartCallback.create(0)
    )
    message_text = (
        f"❌ <b>{Localizator.get_text(BotEntity.USER, 'all_items_out_of_stock')}</b>\n\n"
        f"{Localizator.get_text(BotEntity.USER, 'all_items_out_of_stock_desc')}"
    )
    return message_text, kb_builder


# ============================================================================
# Handler: create_order
# ============================================================================

async def create_order(**kwargs):
    """
    Level 0: Create Order from Cart

    Flow:
    1. Check rate limits
    2. Get cart items and validate
    3. Create order via orchestrator with stock reservation
    4. Commit and handle UI forks:
       - Stock adjustments → Show confirmation screen
       - Physical items → Request shipping address
       - Digital items → Redirect to payment

    - Stock check & adjustment
    - User confirmation of adjustments
    - Address collection (if physical items)
    - Transition to PENDING_PAYMENT
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    # 1. Rate limiting check
    is_limited, message_text, kb_builder = await _check_order_rate_limit(callback)
    if is_limited:
        await callback.message.edit_text(text=message_text, reply_markup=kb_builder.as_markup())
        return

    # 2. Get and validate cart
    user, cart_items, error_message, error_keyboard = await _get_and_validate_cart(callback, session)
    if error_message:
        await callback.message.edit_text(text=error_message, reply_markup=error_keyboard.as_markup())
        return

    try:
        # 3. Create order via orchestrator
        cart_dto = CartDTO(user_id=user.id, items=cart_items)
        order, stock_adjustments, has_physical_items = await OrderService.orchestrate_order_creation(
            cart_dto=cart_dto,
            session=session
        )

        # Save order_id to FSM for later use
        if state:
            await state.update_data(order_id=order.id)

        # Commit order
        await session_commit(session)

        # 4. UI Fork: Stock adjustments?
        if stock_adjustments:
            msg, kb_builder = await _handle_stock_adjustments(
                callback, order, stock_adjustments, state, session
            )
            await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
            return

        # 5. Clear cart (order successfully created, no adjustments)
        for cart_item in cart_items:
            await CartItemRepository.remove_from_cart(cart_item.id, session)
        await session_commit(session)

        # 6. UI Fork: Physical items?
        if has_physical_items:
            msg, kb_builder = await _handle_physical_items_flow(order, state)
            await callback.message.edit_reply_markup()
            await callback.message.answer(msg, reply_markup=kb_builder.as_markup())
            return

        # 7. UI Fork: Digital items → Redirect directly to payment
        await process_payment(
            callback=callback,
            session=session,
            state=state,
            order_id=order.id
        )

    except ValueError as e:
        # All items out of stock
        msg, kb_builder = await _handle_order_creation_error(user, cart_items, session)
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


# ============================================================================
# Helper Functions for process_payment()
# ============================================================================

async def _resolve_order_id(
    callback: CallbackQuery,
    state,
    order_id: int = None
) -> tuple[int | None, object | None]:
    """
    Resolve order_id from parameter, callback data, or FSM state.

    Args:
        callback: The callback query containing potential order_id
        state: FSM state that might contain order_id
        order_id: Optional order_id passed directly

    Returns:
        Tuple of (order_id, unpacked_callback)
    """
    unpacked_cb = None

    if not order_id:
        # Try to unpack as OrderCallback first, fall back to CartCallback
        try:
            unpacked_cb = OrderCallback.unpack(callback.data)
            order_id = unpacked_cb.order_id
        except (ValueError, TypeError):
            # If that fails, try CartCallback (which also has order_id field)
            unpacked_cb = CartCallback.unpack(callback.data)
            order_id = unpacked_cb.order_id

        if order_id == -1 and state:
            state_data = await state.get_data()
            order_id = state_data.get("order_id")

    return order_id, unpacked_cb


async def _handle_existing_invoice(
    order_id: int,
    existing_invoice,
    session: AsyncSession | Session
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Handle case when invoice already exists for an order.
    Shows existing payment screen without new crypto selection.

    Args:
        order_id: The order ID
        existing_invoice: Existing invoice object
        session: Database session

    Returns:
        Tuple of (message, keyboard)
    """
    order = await OrderRepository.get_by_id(order_id, session)

    # Format payment screen with existing invoice
    payment_message = await OrderService._format_payment_screen(
        invoice=existing_invoice,
        order=order,
        session=session
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.USER, "cancel_order"),
        callback_data=OrderCallback.create(level=4, order_id=order_id)
    )

    return payment_message, kb_builder


async def _process_wallet_only_payment(
    order_id: int,
    order,
    state,
    session: AsyncSession | Session
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Process payment when wallet covers the entire order (Mode A).

    Args:
        order_id: The order ID
        order: Order object
        state: FSM state to clear after payment
        session: Database session

    Returns:
        Tuple of (message, keyboard) with payment confirmation or error
    """
    from services.payment import PaymentService
    from enums.cryptocurrency import Cryptocurrency

    try:
        invoice, needs_crypto_payment = await PaymentService.orchestrate_payment_processing(
            order_id=order_id,
            crypto_currency=Cryptocurrency.BTC,  # Dummy value, wallet covers all
            session=session
        )

        # Clear FSM state
        if state:
            await state.clear()

        # Show completion message with full invoice details
        kb_builder = InlineKeyboardBuilder()
        message_text = await OrderService._format_wallet_payment_invoice(
            invoice=invoice,
            order=order,
            session=session
        )
        return message_text, kb_builder

    except ValueError as e:
        # Error during payment processing
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=OrderCallback.create(0)
        )
        return Localizator.get_text(BotEntity.USER, "payment_processing_error").format(error=str(e)), kb_builder


async def _process_crypto_payment(
    order_id: int,
    cryptocurrency,
    state,
    session: AsyncSession | Session
) -> tuple[str, InlineKeyboardBuilder]:
    """
    Process payment with selected cryptocurrency (Mode C).

    Handles both scenarios:
    1. Wallet + crypto payment (shows QR code)
    2. Wallet only covers all after deduction (shows confirmation)

    Args:
        order_id: The order ID
        cryptocurrency: Selected cryptocurrency
        state: FSM state to clear after payment
        session: Database session

    Returns:
        Tuple of (message, keyboard) with payment screen or confirmation
    """
    from services.payment import PaymentService

    try:
        invoice, needs_crypto_payment = await PaymentService.orchestrate_payment_processing(
            order_id=order_id,
            crypto_currency=cryptocurrency,
            session=session
        )

        # Clear FSM state (order processing done)
        if state:
            await state.clear()

        if not needs_crypto_payment:
            # Wallet covered everything - Order PAID and completed!
            order = await OrderRepository.get_by_id(order_id, session)
            kb_builder = InlineKeyboardBuilder()
            message_text = await OrderService._format_wallet_payment_invoice(
                invoice=invoice,
                order=order,
                session=session
            )
            return message_text, kb_builder

        else:
            # Wallet insufficient - Show payment screen with QR code
            order = await OrderRepository.get_by_id(order_id, session)

            # Format payment details
            payment_message = await OrderService._format_payment_screen(
                invoice=invoice,
                order=order,
                session=session
            )

            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.USER, "cancel_order"),
                callback_data=OrderCallback.create(level=4, order_id=order_id)  # Cancel Order = Level 4
            )

            return payment_message, kb_builder

    except ValueError as e:
        # Error during payment processing
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=OrderCallback.create(0)
        )
        return Localizator.get_text(BotEntity.USER, "payment_processing_error").format(error=str(e)), kb_builder


# ============================================================================
# Handler: process_payment
# ============================================================================

async def process_payment(**kwargs):
    """
    Level 3: Process Payment

    Smart payment flow:
    1. First checks if wallet can cover everything
    2. If yes: processes payment immediately (no crypto selection needed)
    3. If no: shows crypto selection, then processes with crypto payment

    Three modes:
    A. First visit + wallet covers all: Direct wallet payment
    B. First visit + wallet insufficient: Show crypto selection
    C. Crypto selected: Process payment with crypto

    - Hand off to PaymentService
    - PaymentService handles wallet check, crypto selection, invoice creation
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")
    order_id = kwargs.get("order_id")

    from enums.cryptocurrency import Cryptocurrency
    from repositories.invoice import InvoiceRepository
    from services.cart import CartService

    # 1. Resolve order_id from various sources
    order_id, unpacked_cb = await _resolve_order_id(callback, state, order_id)

    if not order_id or order_id == -1:
        # No order found - error
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=CartCallback.create(0)  # Back to Cart (cross-domain)
        )
        msg = Localizator.get_text(BotEntity.USER, "order_not_found_error")
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
        return

    # 2. Check order status - abort if already finalized
    order = await OrderRepository.get_by_id(order_id, session)
    if order.status not in [
        OrderStatus.PENDING_PAYMENT,
        OrderStatus.PENDING_PAYMENT_AND_ADDRESS,
        OrderStatus.PENDING_PAYMENT_PARTIAL
    ]:
        # Order already finalized (TIMEOUT, CANCELLED, PAID, etc.)
        # Redirect to cart - order cannot be processed anymore
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.USER, "back_to_cart"),
            callback_data=CartCallback.create(0)
        )
        msg = Localizator.get_text(BotEntity.USER, "error_order_expired")
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
        return

    # 3. Check if active invoice already exists (excludes expired/cancelled)
    existing_invoice = await InvoiceRepository.get_by_order_id(order_id, session, include_inactive=False)
    if existing_invoice:
        # Order still valid - show existing invoice
        msg, kb_builder = await _handle_existing_invoice(order_id, existing_invoice, session)
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
        return

    # 4. Check if crypto already selected
    crypto_selected = unpacked_cb and unpacked_cb.cryptocurrency and unpacked_cb.cryptocurrency != Cryptocurrency.PENDING_SELECTION

    # 5. Mode A/B: First visit - Check wallet balance
    if not crypto_selected:
        user = await UserRepository.get_by_id(order.user_id, session)
        wallet_balance = user.top_up_amount
        order_total = order.total_price

        # Mode A: Wallet covers everything
        if wallet_balance >= order_total:
            msg, kb_builder = await _process_wallet_only_payment(order_id, order, state, session)
            await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
            return

        # Mode B: Wallet insufficient - Show crypto selection
        else:
            msg, kb_builder = await CartService._show_crypto_selection(order_id)
            await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
            return

    # 6. Mode C: Crypto selected - Process payment
    if not unpacked_cb or not unpacked_cb.cryptocurrency:
        # Should never happen (crypto_selected would be False), but safety check
        msg, kb_builder = await CartService._show_crypto_selection(order_id)
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
        return

    msg, kb_builder = await _process_crypto_payment(order_id, unpacked_cb.cryptocurrency, state, session)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def confirm_shipping_address(**kwargs):
    """
    Level 1: Confirm Shipping Address

    - Save encrypted address
    - Update status: PENDING_PAYMENT_AND_ADDRESS → PENDING_PAYMENT
    - Hand off to PaymentService
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    msg, kb_builder = await OrderService.confirm_shipping_address(callback, session, state)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def reenter_shipping_address(**kwargs):
    """
    Level 2: Re-enter Shipping Address

    - User clicked cancel on address confirmation
    - Prompts for address input again with cancel button
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    msg, kb_builder = await OrderService.reenter_shipping_address(callback, session, state)
    await callback.message.edit_reply_markup()
    await callback.message.answer(msg, reply_markup=kb_builder.as_markup())


async def cancel_order(**kwargs):
    """
    Level 4: Show Cancel Confirmation

    - Show confirmation dialog
    - Check grace period
    - Warn about penalties if applicable
    """
    import logging
    logging.info("🔴 CANCEL ORDER HANDLER TRIGGERED (Level 4)")

    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    logging.info(f"🔴 Callback data: {callback.data}")

    try:
        msg, kb_builder = await OrderService.cancel_order_handler(callback, session, state)
        logging.info(f"🔴 Message to display (first 200 chars): {msg[:200]}")
        logging.info(f"🔴 Keyboard buttons: {len(kb_builder.as_markup().inline_keyboard)} rows")

        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
        await callback.answer()  # Stop the "glowing" animation
        logging.info("✅ Cancel order confirmation displayed")
    except Exception as e:
        logging.exception(f"❌ Error in cancel_order handler: {e}")
        await callback.answer("❌ Fehler beim Laden der Stornierungsbestätigung", show_alert=True)


async def execute_cancel_order(**kwargs):
    """
    Level 5: Execute Order Cancellation

    - Cancel pending order after confirmation
    - Restore stock
    - Clear cart
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    msg, kb_builder = await OrderService.execute_cancel_order(callback, session, state)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def reshow_stock_adjustment(**kwargs):
    """
    Level 6: Re-show Stock Adjustment

    - Back navigation from cancel dialog
    - Display stock adjustment screen again
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    msg, kb_builder = await OrderService.reshow_stock_adjustment(callback, session, state)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def confirm_adjusted_order(**kwargs):
    """
    Level 9: Confirm Adjusted Order

    - User confirms order with stock adjustments
    - Continue to address collection or payment
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    msg, kb_builder = await OrderService.confirm_adjusted_order(callback, session, state)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


@order_router.callback_query(OrderCallback.filter(), IsUserExistFilter())
async def navigate_order_process(
    callback: CallbackQuery,
    callback_data: OrderCallback,
    session: AsyncSession | Session,
    state: FSMContext
):
    """
    Order process router.
    Routes callbacks to appropriate level handlers.
    """
    import logging
    logging.info(f"🔵 ORDER ROUTER TRIGGERED - Level: {callback_data.level}, Order ID: {callback_data.order_id}")

    current_level = callback_data.level

    levels = {
        0: create_order,                    # Create order from cart
        1: confirm_shipping_address,        # Confirm shipping address
        2: reenter_shipping_address,        # Re-enter address
        3: process_payment,                 # Process payment
        4: cancel_order,                    # Show cancel confirmation
        5: execute_cancel_order,            # Execute cancellation
        6: reshow_stock_adjustment,         # Re-show stock adjustment
        9: confirm_adjusted_order,          # Confirm adjusted order
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "session": session,
        "state": state,
    }

    await current_level_function(**kwargs)
