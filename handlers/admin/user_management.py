from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import UserManagementCallback, UserManagementOperation
from handlers.admin.constants import UserManagementStates
from models.buy import BuyDTO
from services.admin import AdminService
from services.buy import BuyService
from utils.custom_filters import AdminIdFilter

user_management = Router()


async def user_management_menu(**kwargs):
    callback = kwargs.get("callback")
    state = kwargs.get("state")
    await state.clear()
    msg, kb_builder = await AdminService.get_user_management_menu()
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def credit_management(**kwargs):
    callback = kwargs.get("callback")
    state = kwargs.get("state")
    session = kwargs.get("session")
    unpacked_cb = UserManagementCallback.unpack(callback.data)

    if unpacked_cb.operation is None:
        msg, kb_builder = await AdminService.get_credit_management_menu(callback)
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
    elif unpacked_cb.operation == UserManagementOperation.UNBAN_USER:
        # Show banned users list
        msg, kb_builder = await AdminService.get_banned_users_list(callback, session)
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
    else:
        msg, kb_builder = await AdminService.request_user_entity(callback, state)
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


@user_management.message(AdminIdFilter(), F.text, StateFilter(UserManagementStates.user_entity,
                                                              UserManagementStates.balance_amount))
async def balance_management(message: Message, state: FSMContext, session: AsyncSession | Session):
    current_state = await state.get_state()
    match current_state:
        case UserManagementStates.user_entity:
            msg, kb_builder = await AdminService.request_balance_amount(message, state)
            await message.answer(text=msg, reply_markup=kb_builder.as_markup())
        case UserManagementStates.balance_amount:
            msg = await AdminService.balance_management(message, state, session)
            await message.answer(text=msg)


async def refund_buy(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    msg, kb_builder = await AdminService.get_refund_menu(callback, session)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def level_2_router(**kwargs):
    """
    Route Level 2 based on operation type.

    Level 2 is used for:
    - UNBAN_USER operation: banned users list
    - REFUND operation: refund buy list
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    unpacked_cb = UserManagementCallback.unpack(callback.data)

    if unpacked_cb.operation == UserManagementOperation.UNBAN_USER:
        # Show banned users list
        msg, kb_builder = await AdminService.get_banned_users_list(callback, session)
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
    else:
        # Show refund buy list
        await refund_buy(**kwargs)


async def level_3_router(**kwargs):
    """
    Route Level 3 based on operation type.

    Level 3 is used for:
    - UNBAN_USER operation: banned user detail view
    - REFUND operation: refund confirmation
    """
    callback = kwargs.get("callback")
    unpacked_cb = UserManagementCallback.unpack(callback.data)

    if unpacked_cb.operation == UserManagementOperation.UNBAN_USER:
        await banned_user_detail(**kwargs)
    else:
        await refund_confirmation(**kwargs)


async def refund_confirmation(**kwargs):
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    unpacked_cb = UserManagementCallback.unpack(callback.data)
    if unpacked_cb.confirmation:
        msg = await BuyService.refund(BuyDTO(id=unpacked_cb.buy_id), session)
        await callback.message.edit_text(text=msg)
    else:
        msg, kb_builder = await AdminService.refund_confirmation(callback, session)
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def banned_user_detail(**kwargs):
    """Show detailed view of a single banned user with strike history."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from utils.html_escape import safe_html
    from utils.localizator import Localizator
    from enums.bot_entity import BotEntity

    callback = kwargs.get("callback")
    session = kwargs.get("session")
    unpacked_cb = UserManagementCallback.unpack(callback.data)
    user_id = unpacked_cb.page

    # Get data from service (no Telegram objects)
    data = await AdminService.get_banned_user_detail_data(user_id, session)

    # Handle error cases
    if not data:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=UserManagementCallback.create(level=2, operation=UserManagementOperation.UNBAN_USER)
        )
        msg = Localizator.get_text(BotEntity.ADMIN, "user_not_found")
        await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())
        return

    # Format user display
    if data["telegram_username"]:
        user_display = f"@{safe_html(data['telegram_username'])}"
    else:
        user_display = f"ID: {data['telegram_id']}"

    # Build message
    message_lines = [
        Localizator.get_text(BotEntity.ADMIN, "banned_user_detail_header").format(
            user_display=user_display,
            telegram_id=data["telegram_id"],
            strike_count=data["strike_count"]
        ),
        ""
    ]

    # Add strike history
    if data["strikes"]:
        message_lines.append(Localizator.get_text(BotEntity.ADMIN, "strike_history_header"))
        message_lines.append("")

        for idx, strike in enumerate(data["strikes"], start=1):
            strike_date = strike["created_at"].strftime("%d.%m.%Y %H:%M")

            # Get localized strike type name
            strike_type_key = f"strike_type_{strike['strike_type'].lower()}"
            strike_type_name = Localizator.get_text(BotEntity.ADMIN, strike_type_key)

            # Format invoice ID
            invoice_info = strike["order_invoice_id"] if strike["order_invoice_id"] else Localizator.get_text(BotEntity.ADMIN, "no_order_id")

            # Format reason (escape HTML)
            reason_text = safe_html(strike["reason"]) if strike["reason"] else Localizator.get_text(BotEntity.ADMIN, "no_reason_given")

            message_lines.append(
                Localizator.get_text(BotEntity.ADMIN, "strike_history_item").format(
                    strike_number=idx,
                    strike_date=strike_date,
                    strike_type=strike_type_name,
                    invoice_info=invoice_info,
                    reason=reason_text
                )
            )

        if data["total_strike_count"] > 10:
            remaining_strikes = data["total_strike_count"] - len(data["strikes"])
            message_lines.append("")
            message_lines.append(
                Localizator.get_text(BotEntity.ADMIN, "strike_history_truncated").format(
                    total_strikes=remaining_strikes
                )
            )
    else:
        message_lines.append(Localizator.get_text(BotEntity.ADMIN, "no_strikes_found"))

    # Add ban information
    message_lines.append("")
    message_lines.append(Localizator.get_text(BotEntity.ADMIN, "ban_info_header"))
    ban_date = data["blocked_at"].strftime("%d.%m.%Y %H:%M") if data["blocked_at"] else Localizator.get_text(BotEntity.ADMIN, "unknown_date")
    ban_reason = safe_html(data["blocked_reason"]) if data["blocked_reason"] else Localizator.get_text(BotEntity.ADMIN, "no_reason_given")
    message_lines.append(
        Localizator.get_text(BotEntity.ADMIN, "ban_info_details").format(
            ban_date=ban_date,
            ban_reason=ban_reason
        )
    )

    # Build keyboard
    kb_builder = InlineKeyboardBuilder()

    # Unban button
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "unban_user_button_detail"),
        callback_data=UserManagementCallback.create(
            level=4,
            operation=UserManagementOperation.UNBAN_USER,
            page=user_id
        )
    )

    # Back button
    kb_builder.button(
        text=Localizator.get_text(BotEntity.COMMON, "back_button"),
        callback_data=UserManagementCallback.create(
            level=2,
            operation=UserManagementOperation.UNBAN_USER
        )
    )

    kb_builder.adjust(1)

    msg = "\n".join(message_lines)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def level_4_router(**kwargs):
    """
    Route Level 4 based on operation and confirmation status.

    Level 4 is used for:
    - UNBAN_USER with confirmation: Show unban confirmation
    - UNBAN_USER without confirmation (coming from confirmation): Execute unban
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    unpacked_cb = UserManagementCallback.unpack(callback.data)

    if unpacked_cb.operation == UserManagementOperation.UNBAN_USER:
        # Check if this is a confirmation or the actual unban action
        if unpacked_cb.confirmation:
            # This is the actual unban action
            msg = await AdminService.unban_user(callback, session)
            await callback.message.edit_text(text=msg)
        else:
            # Show confirmation dialog
            msg, kb_builder = await AdminService.unban_confirmation(callback, session)
            await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


@user_management.callback_query(AdminIdFilter(), UserManagementCallback.filter())
async def inventory_management_navigation(callback: CallbackQuery, state: FSMContext,
                                          callback_data: UserManagementCallback, session: Session | AsyncSession):
    current_level = callback_data.level

    levels = {
        0: user_management_menu,
        1: credit_management,
        2: level_2_router,  # Routes based on operation: UNBAN_USER → banned list, else → refund buy
        3: level_3_router,  # Routes based on operation: UNBAN_USER → detail, else → refund_confirmation
        4: level_4_router   # Routes based on operation: UNBAN_USER → confirmation/execute
    }
    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "state": state,
        "session": session,
    }

    await current_level_function(**kwargs)
