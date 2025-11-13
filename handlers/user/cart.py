import inspect

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import CartCallback, OrderCallback
from enums.bot_entity import BotEntity
from services.cart import CartService
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator

cart_router = Router()


@cart_router.message(F.text == Localizator.get_text(BotEntity.USER, "cart"), IsUserExistFilter())
async def cart_text_message(message: types.Message, session: AsyncSession | Session):
    import logging
    logging.info("🛒 CART BUTTON HANDLER TRIGGERED")
    await show_cart(message=message, session=session)


async def show_cart(**kwargs):
    """
    Show cart contents with items and checkout button.

    Refactored to use get_cart_summary_data() - UI logic now in handler.
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from repositories.user import UserRepository
    from repositories.cart import CartRepository
    from repositories.cartItem import CartItemRepository
    from handlers.common.common import add_pagination_buttons

    message = kwargs.get("message") or kwargs.get("callback")
    session = kwargs.get("session")

    # Get user ID
    user = await UserRepository.get_by_tgid(message.from_user.id, session)

    # Get cart data from service (pure data, no UI)
    cart_data = await CartService.get_cart_summary_data(user.id, session)

    # Handle pending order redirect
    if cart_data["has_pending_order"]:
        from enums.order_status import OrderStatus
        from services.order import OrderService
        import config

        order = cart_data["order"]

        # Get order data
        order_data = await CartService.get_pending_order_data(order, session)

        kb_builder = InlineKeyboardBuilder()

        # Case 1: Expired order with invoice - auto-cancel and show message
        if order_data["is_expired"] and order_data["has_invoice"]:
            await CartService.handle_expired_order(order.id, session)
            msg = CartService.format_expired_order_message(order_data)
            # No buttons for expired order

        # Case 2: Order with invoice (payment screen)
        elif order_data["has_invoice"]:
            # Use OrderService formatter for payment screen
            msg = await OrderService._format_payment_screen(
                order_data["invoice"], order, session
            )

            # Add grace period warning if expired
            if not order_data["can_cancel_free"]:
                # Choose warning based on wallet usage
                if order_data["wallet_used"] > 0:
                    grace_warning = Localizator.get_text(BotEntity.USER, "grace_period_expired_warning_with_fee").format(
                        grace_period=config.ORDER_CANCEL_GRACE_PERIOD_MINUTES
                    )
                else:
                    grace_warning = Localizator.get_text(BotEntity.USER, "grace_period_expired_warning_no_fee").format(
                        grace_period=config.ORDER_CANCEL_GRACE_PERIOD_MINUTES
                    )
                msg += f"\n\n{grace_warning}"

            # Build cancel button
            cancel_text = Localizator.get_text(BotEntity.USER, "cancel_order_free" if order_data["can_cancel_free"] else "cancel_order_strike")
            kb_builder.button(
                text=cancel_text,
                callback_data=OrderCallback.create(level=4, order_id=order.id)
            )

        # Case 3: No invoice yet (awaiting address or payment initiation)
        else:
            # Check if order is expired without invoice
            if order_data["is_expired"]:
                # Auto-cancel expired order without invoice
                await CartService.handle_expired_order(order.id, session)
                # Show simple expiry message - order auto-cancelled
                msg = Localizator.get_text(BotEntity.USER, "order_expired_no_invoice")
                # No buttons for expired order
            else:
                # Order still active - show pending message
                msg = CartService.format_pending_order_message(order_data)

                # Build action button based on status
                if order_data["status"] == OrderStatus.PENDING_PAYMENT_AND_ADDRESS:
                    # Button: Enter shipping address
                    kb_builder.button(
                        text=Localizator.get_text(BotEntity.USER, "enter_shipping_address"),
                        callback_data=OrderCallback.create(level=2, order_id=order.id)
                    )
                else:
                    # Button: Continue to payment
                    kb_builder.button(
                        text=Localizator.get_text(BotEntity.USER, "continue_to_payment"),
                        callback_data=OrderCallback.create(level=3, order_id=order.id)
                    )

                # Add cancel button
                cancel_text = Localizator.get_text(BotEntity.USER, "cancel_order_free" if order_data["can_cancel_free"] else "cancel_order_strike")
                kb_builder.button(
                    text=cancel_text,
                    callback_data=OrderCallback.create(level=4, order_id=order.id)
                )
    else:
        # Build UI from data
        kb_builder = InlineKeyboardBuilder()

        # Get page for pagination
        page = 0 if isinstance(message, Message) else CartCallback.unpack(message.data).page

        # Build cart item buttons
        for item in cart_data["items"]:
            button_text = Localizator.get_text(BotEntity.USER, "cart_item_button").format(
                subcategory_name=item["subcategory_name"],
                qty=item["quantity"],
                total_price=item["total"],
                currency_sym=Localizator.get_currency_symbol()
            )
            kb_builder.button(
                text=button_text,
                callback_data=CartCallback.create(1, page, cart_item_id=item["cart_item_id"])
            )

        # Add checkout button if cart has items
        if cart_data["has_items"]:
            cart = await CartRepository.get_or_create(user.id, session)
            kb_builder.button(
                text=Localizator.get_text(BotEntity.USER, "checkout"),
                callback_data=CartCallback.create(2, page, cart.id)
            )
            kb_builder.adjust(1)

            # Add pagination buttons
            unpacked_cb = CartCallback.create(0) if isinstance(message, Message) else CartCallback.unpack(message.data)
            kb_builder = await add_pagination_buttons(
                kb_builder,
                unpacked_cb,
                CartItemRepository.get_maximum_page(user.id, session),
                None
            )

        # Get localized message
        msg = Localizator.get_text(BotEntity.USER, cart_data["message_key"])

    # Send response
    if isinstance(message, Message):
        await message.answer(msg, reply_markup=kb_builder.as_markup())
    elif isinstance(message, CallbackQuery):
        callback = message
        await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())


async def delete_cart_item_confirm(**kwargs):
    """
    Show confirmation dialog before deleting cart item.

    Refactored to use get_delete_confirmation_data() - UI logic in handler.
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    callback = kwargs.get("callback")
    session = kwargs.get("session")

    # Extract cart_item_id from callback
    unpacked_cb = CartCallback.unpack(callback.data)
    cart_item_id = unpacked_cb.cart_item_id

    # Get data from service (pure data, no UI)
    confirm_data = await CartService.get_delete_confirmation_data(cart_item_id, session)

    # Build confirmation message
    msg = Localizator.get_text(BotEntity.USER, confirm_data["message_key"]).format(
        subcategory_name=confirm_data["subcategory_name"],
        quantity=confirm_data["quantity"]
    )

    # Build UI in handler
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "confirm"),
        callback_data=CartCallback.create(level=4, cart_item_id=cart_item_id).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=CartCallback.create(level=0).pack()
    )
    kb_builder.adjust(2)

    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def delete_cart_item_execute(**kwargs):
    """
    Execute cart item deletion after confirmation.

    Refactored to use remove_cart_item() + show_cart().
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")

    # Extract cart_item_id from callback
    unpacked_cb = CartCallback.unpack(callback.data)
    cart_item_id = unpacked_cb.cart_item_id

    # Remove item via service
    await CartService.remove_cart_item(cart_item_id, session)

    # Show updated cart (already refactored handler)
    await show_cart(callback=callback, session=session)


async def checkout_processing(**kwargs):
    """
    Show checkout summary with price breakdown and confirmation buttons.

    Refactored to use get_checkout_summary_data() + format_checkout_message().
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from repositories.user import UserRepository

    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    # Get user ID
    user = await UserRepository.get_by_tgid(callback.from_user.id, session)

    # Get checkout data from service (pure data, no UI)
    checkout_data = await CartService.get_checkout_summary_data(user.id, session)

    # Format message from data
    msg = CartService.format_checkout_message(checkout_data)

    # Build UI in handler
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "confirm"),
        callback_data=CartCallback.create(3, confirmation=True)
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=CartCallback.create(0)
    )

    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def buy_processing(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    await callback.message.edit_reply_markup()
    msg, kb_builder = await CartService.buy_processing(callback, session)
    await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())


# ========================================
# NEW INVOICE-BASED CHECKOUT HANDLERS
# ========================================

async def create_order_handler(**kwargs):
    """
    Level 3: Checkout → Hand off to Order Domain

    Redirects to OrderCallback Level 0 (Order Creation).
    Order domain handles:
    - Stock reservation
    - Stock adjustment confirmation
    - Address collection (physical items)
    - Payment processing
    """
    callback = kwargs.get("callback")

    # Redirect to Order domain (OrderCallback level 0)
    from handlers.user.order import create_order
    await create_order(**kwargs)




@cart_router.callback_query(CartCallback.filter(), IsUserExistFilter())
async def navigate_cart_process(callback: CallbackQuery, callback_data: CartCallback, session: AsyncSession | Session, state: FSMContext):
    current_level = callback_data.level

    levels = {
        0: show_cart,
        1: delete_cart_item_confirm,
        2: checkout_processing,
        3: create_order_handler,  # Hand off to Order domain
        4: delete_cart_item_execute,
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "session": session,
        "state": state,
    }

    await current_level_function(**kwargs)
