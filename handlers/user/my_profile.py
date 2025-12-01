from aiogram import types, Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import MyProfileCallback
from enums.bot_entity import BotEntity
from enums.cryptocurrency import Cryptocurrency
from services.buy import BuyService
from services.payment import PaymentService
from services.user import UserService
from utils.custom_filters import IsUserExistFilter, IsUserExistFilterIncludingBanned, ButtonTextFilter
from utils.localizator import Localizator

my_profile_router = Router()


@my_profile_router.message(ButtonTextFilter("my_profile"), IsUserExistFilterIncludingBanned())
async def my_profile_text_message(message: types.Message, session: Session | AsyncSession):
    import logging
    logging.info("👤 MY PROFILE BUTTON HANDLER TRIGGERED")
    await my_profile(message=message, session=session)


class MyProfileConstants:
    back_to_main_menu = types.InlineKeyboardButton(
        text=Localizator.get_text(BotEntity.USER, "back_to_my_profile"),
        callback_data=MyProfileCallback.create(level=0).pack())


async def my_profile(**kwargs):
    message: Message | CallbackQuery = kwargs.get("message") or kwargs.get("callback")
    session: Session | AsyncSession = kwargs.get("session")
    msg_text, kb_builder = await UserService.get_my_profile_buttons(message.from_user.id, session)
    if isinstance(message, Message):
        await message.answer(msg_text, reply_markup=kb_builder.as_markup())
    elif isinstance(message, CallbackQuery):
        callback = message
        await callback.message.edit_text(msg_text, reply_markup=kb_builder.as_markup())


async def top_up_balance(**kwargs):
    callback = kwargs.get("callback")
    msg_text, kb_builder = await UserService.get_top_up_buttons(callback)
    await callback.message.edit_text(text=msg_text, reply_markup=kb_builder.as_markup())


async def purchase_history(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    msg_text, kb_builder = await UserService.get_purchase_history_buttons(callback, session)
    await callback.message.edit_text(text=msg_text, reply_markup=kb_builder.as_markup())


async def strike_statistics(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    msg_text, kb_builder = await UserService.get_strike_statistics_buttons(callback, session)
    await callback.message.edit_text(text=msg_text, reply_markup=kb_builder.as_markup())


async def get_order_from_history(**kwargs):
    from exceptions import OrderNotFoundException, ShopBotException
    import logging

    callback = kwargs.get("callback")
    session = kwargs.get("session")

    try:
        msg, kb_builder = await BuyService.get_purchase(callback, session)
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())

    except OrderNotFoundException:
        await callback.answer("❌ Order not found", show_alert=True)

    except ShopBotException as e:
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

    except Exception as e:
        logging.exception(f"Unexpected error getting order from history: {e}")
        await callback.answer("❌ An unexpected error occurred", show_alert=True)


async def my_orders_overview(**kwargs):
    """Level 7: Order history - default to All Orders list (filter selection via button)"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")

    # Directly show All Orders list (filter_type=None, page=0)
    msg_text, kb_builder = await UserService.get_my_orders_list(
        callback.from_user.id,
        filter_type=None,  # All Orders
        page=0,
        session=session
    )
    await callback.message.edit_text(msg_text, reply_markup=kb_builder.as_markup())


async def my_orders_list(**kwargs):
    """Level 8: Paginated order list with filter"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = MyProfileCallback.unpack(callback.data)

    msg_text, kb_builder = await UserService.get_my_orders_list(
        callback.from_user.id,
        callback_data.filter_type,
        callback_data.page,
        session
    )
    await callback.message.edit_text(msg_text, reply_markup=kb_builder.as_markup())


async def my_order_detail(**kwargs):
    """Level 9: Order detail view"""
    from exceptions import OrderNotFoundException
    import logging

    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = MyProfileCallback.unpack(callback.data)

    try:
        msg_text, kb_builder = await UserService.get_order_detail_for_user(
            callback_data.args_for_action,
            callback.from_user.id,  # Pass telegram_id for ownership check
            session,
            filter_type=callback_data.filter_type
        )
        await callback.message.edit_text(msg_text, reply_markup=kb_builder.as_markup())

    except OrderNotFoundException:
        await callback.answer("❌ Bestellung nicht gefunden", show_alert=True)

    except Exception as e:
        logging.exception(f"Unexpected error getting order detail: {e}")
        await callback.answer("❌ Ein unerwarteter Fehler ist aufgetreten", show_alert=True)


async def my_orders_filter_selection(**kwargs):
    """Level 10: Filter selection for order history"""
    callback = kwargs.get("callback")
    session = kwargs.get("session")

    msg_text, kb_builder = await UserService.get_my_orders_overview(
        callback.from_user.id,
        session
    )
    await callback.message.edit_text(msg_text, reply_markup=kb_builder.as_markup())


async def create_payment(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    session: AsyncSession | Session = kwargs.get("session")
    unpacked_cb = MyProfileCallback.unpack(callback.data)
    msg = await callback.message.edit_text(Localizator.get_text(BotEntity.USER, "loading"))
    text = await PaymentService.create(Cryptocurrency(unpacked_cb.args_for_action), msg, session)
    await msg.edit_text(text=text)


@my_profile_router.callback_query(MyProfileCallback.filter(), IsUserExistFilterIncludingBanned())
async def navigate(callback: CallbackQuery, callback_data: MyProfileCallback, session: AsyncSession | Session):
    import logging
    logging.info(f"🟣 MY PROFILE ROUTER TRIGGERED - Level: {callback_data.level}, Callback data: {callback.data}")

    current_level = callback_data.level

    levels = {
        0: my_profile,
        1: top_up_balance,
        2: create_payment,
        4: purchase_history,
        5: get_order_from_history,
        6: strike_statistics,
        7: my_orders_overview,
        8: my_orders_list,
        9: my_order_detail,
        10: my_orders_filter_selection
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "session": session,
    }

    await current_level_function(**kwargs)
