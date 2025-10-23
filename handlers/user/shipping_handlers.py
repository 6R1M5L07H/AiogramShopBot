from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import CartCallback
from enums.bot_entity import BotEntity
from handlers.user.shipping_states import ShippingAddressStates
from repositories.user import UserRepository
from services.cart import CartService
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator

shipping_router = Router()


@shipping_router.message(ShippingAddressStates.waiting_for_address, IsUserExistFilter())
async def process_shipping_address_input(message: Message, state: FSMContext, session: AsyncSession | Session):
    """
    Process user's shipping address input (free-text).
    Shows confirmation screen with address preview.
    """
    address_text = message.text.strip()

    if not address_text or len(address_text) < 10:
        # Address too short - ask again
        await message.answer(
            Localizator.get_text(BotEntity.USER, "shipping_address_invalid")
        )
        return

    # Store address in FSM context
    await state.update_data(shipping_address=address_text)

    # Show confirmation screen
    message_text = Localizator.get_text(BotEntity.USER, "shipping_address_confirm").format(
        address=address_text
    )

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "confirm"),
        callback_data=CartCallback.create(level=6, confirmation=True).pack()  # Level 6 = confirm address
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "cancel"),
        callback_data=CartCallback.create(level=0).pack()  # Back to cart
    )

    await message.answer(message_text, reply_markup=kb_builder.as_markup())
    await state.set_state(ShippingAddressStates.confirm_address)


@shipping_router.callback_query(F.data == CartCallback.create(level=6, confirmation=True).pack(), IsUserExistFilter())
async def confirm_shipping_address(callback: CallbackQuery, state: FSMContext, session: AsyncSession | Session):
    """
    User confirmed shipping address - proceed to crypto selection.
    """
    # Get address from FSM context
    data = await state.get_data()
    shipping_address = data.get("shipping_address")

    if not shipping_address:
        # Something went wrong - restart address collection
        await callback.message.edit_text(
            Localizator.get_text(BotEntity.USER, "shipping_address_invalid")
        )
        await state.set_state(ShippingAddressStates.waiting_for_address)
        return

    # Address confirmed - show crypto selection
    # NOTE: Address will be saved when order is created (in create_order_with_selected_crypto)
    msg, kb_builder = await CartService.show_crypto_selection_without_physical_check(callback, session)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())

    # Keep address in FSM state for later use in order creation
    # Don't clear state yet - we need it for order creation
