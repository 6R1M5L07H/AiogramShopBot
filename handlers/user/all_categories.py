from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import AllCategoriesCallback, QuantityDialpadCallback
from enums.bot_entity import BotEntity
from handlers.user.quantity_states import QuantityInputStates
from repositories.item import ItemRepository
from services.cart import CartService
from services.category import CategoryService
from services.subcategory import SubcategoryService
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator

all_categories_router = Router()


@all_categories_router.message(F.text == Localizator.get_text(BotEntity.USER, "all_categories"),
                               IsUserExistFilter())
async def all_categories_text_message(message: types.Message, session: AsyncSession | Session):
    import logging
    logging.info("🗂️ ALL CATEGORIES BUTTON HANDLER TRIGGERED")
    await all_categories(callback=message, session=session)


async def all_categories(**kwargs):
    message = kwargs.get("callback")
    session = kwargs.get("session")
    if isinstance(message, Message):
        msg, kb_builder = await CategoryService.get_buttons(session)
        await message.answer(msg, reply_markup=kb_builder.as_markup())
    elif isinstance(message, CallbackQuery):
        callback = message
        msg, kb_builder = await CategoryService.get_buttons(session, callback)
        await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())


async def show_subcategories_in_category(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    msg, kb_builder = await SubcategoryService.get_buttons(callback, session)
    await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())


async def select_quantity(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    state = kwargs.get("state")

    msg, kb_builder = await SubcategoryService.get_select_quantity_buttons(callback, session)
    await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())

    # Set FSM state for dialpad input
    unpacked_cb = AllCategoriesCallback.unpack(callback.data)

    # Get item data and cache in FSM state to avoid repeated DB lookups
    item = await ItemRepository.get_item_metadata(unpacked_cb.category_id, unpacked_cb.subcategory_id, session)
    available_qty = await ItemRepository.get_available_qty(item, session) if item else 0

    await state.set_state(QuantityInputStates.building_quantity)
    await state.update_data(
        item_id=item.id if item else None,
        item_name=item.description if item else "",
        available_qty=available_qty,
        category_id=unpacked_cb.category_id,
        subcategory_id=unpacked_cb.subcategory_id,
        current_quantity="",
        unit=item.unit if item else "pcs."
    )


async def add_to_cart_confirmation(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    msg, kb_builder = await SubcategoryService.get_add_to_cart_buttons(callback, session)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def add_to_cart(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    success, message_key, format_args = await CartService.add_to_cart(callback, session)

    # Show confirmation or warning message
    message = Localizator.get_text(BotEntity.USER, message_key)
    if format_args:
        message = message.format(**format_args)

    # Show alert for failures OR warnings (stock reduced)
    show_alert = (not success) or (message_key == "add_to_cart_stock_reduced")

    if success:
        # Success: Show message with Checkout + Back buttons
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from callbacks import AllCategoriesCallback, CartCallback
        from repositories.user import UserRepository
        from repositories.cart import CartRepository

        unpacked_cb = AllCategoriesCallback.unpack(callback.data)
        user = await UserRepository.get_by_tgid(callback.from_user.id, session)
        cart = await CartRepository.get_or_create(user.id, session)

        kb_builder = InlineKeyboardBuilder()

        # Row 1: Continue Shopping button
        kb_builder.button(
            text="🛍️ " + Localizator.get_text(BotEntity.USER, "continue_shopping"),
            callback_data=AllCategoriesCallback.create(
                level=1,  # Back to subcategory list
                category_id=unpacked_cb.category_id
            )
        )

        # Row 2: Go to Cart button (prominent)
        kb_builder.button(
            text="🛒 " + Localizator.get_text(BotEntity.USER, "go_to_cart"),
            callback_data=CartCallback.create(level=0, cart_id=cart.id)
        )

        # Force each button on its own row
        kb_builder.adjust(1)

        await callback.message.edit_text(text=message, reply_markup=kb_builder.as_markup())
        return  # Stop here - don't show subcategory list
    else:
        # Failure: Just show alert
        await callback.answer(text=message, show_alert=show_alert)

    # Get current context and build new callback with level 1 for subcategory list
    unpacked_cb = AllCategoriesCallback.unpack(callback.data)

    # Create a new callback query object with level 1 to avoid KeyError
    # We need to use model_copy to create a new CallbackQuery with modified data
    from aiogram.types import CallbackQuery as CQ
    from copy import copy

    # Create callback data for level 1 (subcategory list)
    new_callback_data = AllCategoriesCallback.create(
        level=1,
        category_id=unpacked_cb.category_id,
        page=unpacked_cb.page
    )

    # Create a shallow copy of callback with new data string
    modified_callback = copy(callback)
    object.__setattr__(modified_callback, 'data', new_callback_data.pack())

    # Build subcategory list message and buttons with the modified callback
    msg, kb_builder = await SubcategoryService.get_buttons(modified_callback, session)

    # Edit message to show subcategory list, preserving category context
    await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())


@all_categories_router.callback_query(AllCategoriesCallback.filter(), IsUserExistFilter())
async def navigate_categories(callback: CallbackQuery, callback_data: AllCategoriesCallback,
                              session: AsyncSession | Session, state: FSMContext):
    current_level = callback_data.level

    levels = {
        0: all_categories,
        1: show_subcategories_in_category,
        2: select_quantity,
        3: add_to_cart_confirmation,
        4: add_to_cart
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "session": session,
        "state": state,
    }

    await current_level_function(**kwargs)


@all_categories_router.callback_query(
    QuantityDialpadCallback.filter(),
    QuantityInputStates.building_quantity,
    IsUserExistFilter()
)
async def handle_dialpad_action(
    callback: CallbackQuery,
    callback_data: QuantityDialpadCallback,
    state: FSMContext,
    session: AsyncSession | Session
):
    """Handle dialpad button presses for quantity input."""
    from utils.keyboard_utils import create_quantity_dialpad

    # Get current state data
    data = await state.get_data()
    current_quantity = data.get("current_quantity", "")
    item_id = callback_data.item_id
    category_id = callback_data.category_id
    subcategory_id = callback_data.subcategory_id

    action = callback_data.action

    if action == "digit":
        # Add digit to current quantity
        digit = str(callback_data.value)
        new_quantity = current_quantity + digit

        # Validate max length (4 digits = 9999)
        if len(new_quantity) > 4:
            await callback.answer(
                Localizator.get_text(BotEntity.USER, "quantity_too_large"),
                show_alert=True
            )
            return

        await state.update_data(current_quantity=new_quantity)
        current_quantity = new_quantity
        await callback.answer()  # Ack callback to stop spinner

    elif action == "backspace":
        # Remove last digit
        if current_quantity:
            new_quantity = current_quantity[:-1]
            await state.update_data(current_quantity=new_quantity)
            current_quantity = new_quantity
        await callback.answer()  # Ack callback to stop spinner

    elif action == "clear":
        # Clear all digits
        await state.update_data(current_quantity="")
        current_quantity = ""
        await callback.answer()  # Ack callback to stop spinner

    elif action == "confirm":
        # Validate and add to cart
        if not current_quantity or current_quantity == "0":
            await callback.answer(
                Localizator.get_text(BotEntity.USER, "quantity_cannot_be_zero"),
                show_alert=True
            )
            return

        quantity = int(current_quantity)

        # Create AllCategoriesCallback to simulate add_to_cart flow
        # Pass the REQUESTED quantity (not adjusted) - add_to_cart will handle adjustment
        from copy import copy
        cart_callback = AllCategoriesCallback.create(
            level=4,  # add_to_cart level
            category_id=category_id,
            subcategory_id=subcategory_id,
            quantity=quantity,  # Pass original requested quantity
            confirmation=True
        )

        # Create modified callback with new data
        modified_callback = copy(callback)
        object.__setattr__(modified_callback, 'data', cart_callback.pack())

        # Clear FSM state
        await state.clear()

        # Call add_to_cart
        await add_to_cart(callback=modified_callback, session=session)
        return

    elif action == "back":
        # Clear FSM state and go back to subcategory list
        await state.clear()
        await callback.answer()  # Ack callback to stop spinner

        back_callback = AllCategoriesCallback.create(
            level=1,
            category_id=category_id
        )
        from copy import copy
        modified_callback = copy(callback)
        object.__setattr__(modified_callback, 'data', back_callback.pack())

        msg, kb_builder = await SubcategoryService.get_buttons(modified_callback, session)
        await callback.message.edit_text(msg, reply_markup=kb_builder.as_markup())
        return

    # Update dialpad display using cached data from FSM state
    item_name = data.get("item_name", "")
    available_qty = data.get("available_qty", 0)
    unit = data.get("unit", "pcs.")

    # Localize unit
    from utils.localizator import Localizator as LocUtil
    localized_unit = LocUtil.localize_unit(unit)

    dialpad_message = Localizator.get_text(BotEntity.USER, "quantity_dialpad_prompt").format(
        item_name=item_name,
        available=available_qty,
        unit=localized_unit,
        current_quantity=current_quantity if current_quantity else "0"
    )

    kb_builder = create_quantity_dialpad(
        item_id=item_id,
        category_id=category_id,
        subcategory_id=subcategory_id
    )

    await callback.message.edit_text(dialpad_message, reply_markup=kb_builder.as_markup())
