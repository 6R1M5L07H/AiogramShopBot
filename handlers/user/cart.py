import inspect

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import CartCallback
from enums.bot_entity import BotEntity
from services.cart import CartService
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator

cart_router = Router()


@cart_router.message(F.text == Localizator.get_text(BotEntity.USER, "cart"), IsUserExistFilter())
async def cart_text_message(message: types.message, session: AsyncSession | Session):
    await show_cart(message=message, session=session)


async def show_cart(**kwargs):
    message = kwargs.get("message") or kwargs.get("callback")
    session = kwargs.get("session")
    msg, kb_builder = await CartService.create_buttons(message, session)
    if isinstance(message, Message):
        await message.answer(msg, reply_markup=kb_builder.as_markup())
    elif isinstance(message, CallbackQuery):
        callback = message
        await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())


async def delete_cart_item(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    msg, kb_builder = await CartService.delete_cart_item(callback, session)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def checkout_processing(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    msg, kb_builder = await CartService.checkout_processing(callback, session)
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

async def crypto_selection_for_checkout(**kwargs):
    """Level 3: Shows crypto selection after checkout confirmation (invoice flow)
    If physical items present, triggers shipping address FSM first.
    """
    from aiogram.fsm.context import FSMContext
    from handlers.user.shipping_states import ShippingAddressStates
    from services.shipping import ShippingService
    from repositories.cartItem import CartItemRepository
    from repositories.user import UserRepository

    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")  # FSMContext

    # Get user and cart items to check for physical items
    user = await UserRepository.get_by_tgid(callback.from_user.id, session)
    cart_items = await CartItemRepository.get_all_by_user_id(user.id, session)
    has_physical_items = await ShippingService.check_cart_has_physical_items(cart_items, session)

    if has_physical_items and state:
        # Set FSM state for address collection
        await state.set_state(ShippingAddressStates.waiting_for_address)

    msg, kb_builder = await CartService.get_crypto_selection_for_checkout(callback, session)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def create_order_with_crypto(**kwargs):
    """Level 4: Creates order + invoice with selected crypto"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    # Get shipping address from FSM state (if present)
    shipping_address = None
    if state:
        data = await state.get_data()
        shipping_address = data.get("shipping_address")
        # Clear FSM state after order creation
        await state.clear()

    await callback.message.edit_reply_markup()  # Remove buttons during processing
    msg, kb_builder = await CartService.create_order_with_selected_crypto(
        callback, session, shipping_address=shipping_address
    )
    await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())


async def cancel_order(**kwargs):
    """Level 5: Cancels an order (with grace period check)"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    await callback.message.edit_reply_markup()  # Remove buttons during processing
    msg, kb_builder = await CartService.cancel_order(callback, session)
    await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())


async def confirm_shipping_address_handler(**kwargs):
    """Level 6: Confirm shipping address and proceed to crypto selection"""
    from handlers.user.shipping_handlers import confirm_shipping_address
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")
    await confirm_shipping_address(callback, state, session)


@cart_router.callback_query(CartCallback.filter(), IsUserExistFilter())
async def navigate_cart_process(callback: CallbackQuery, callback_data: CartCallback, session: AsyncSession | Session, state: FSMContext):
    from aiogram.fsm.context import FSMContext

    current_level = callback_data.level

    levels = {
        0: show_cart,
        1: delete_cart_item,
        2: checkout_processing,
        3: crypto_selection_for_checkout,      # INVOICE-FLOW: Crypto selection (triggers FSM if physical items)
        4: create_order_with_crypto,           # INVOICE-FLOW: Order creation
        5: cancel_order,                       # INVOICE-FLOW: Order cancellation
        6: confirm_shipping_address_handler,   # SHIPPING: Confirm address and show crypto selection
        # 3: buy_processing  # OLD WALLET-FLOW (commented out for migration)
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "session": session,
        "state": state,
    }

    await current_level_function(**kwargs)
