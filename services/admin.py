import asyncio
import datetime
import logging
import re

from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import AdminAnnouncementCallback, AnnouncementType, AdminInventoryManagementCallback, EntityType, \
    AddType, UserManagementCallback, UserManagementOperation, StatisticsCallback, StatisticsEntity, StatisticsTimeDelta, \
    WalletCallback, AnalyticsV2Callback, AnalyticsV2Entity, AnalyticsV2TimeDelta
from crypto_api.CryptoApiWrapper import CryptoApiWrapper
from db import session_commit
from enums.bot_entity import BotEntity
from enums.cryptocurrency import Cryptocurrency
from aiogram.types import InlineKeyboardButton
from handlers.admin.constants import AdminConstants, AdminInventoryManagementStates, UserManagementStates, WalletStates
from handlers.common.common import add_pagination_buttons
from models.withdrawal import WithdrawalDTO
from repositories.buy import BuyRepository
from repositories.category import CategoryRepository
from repositories.deposit import DepositRepository
from repositories.item import ItemRepository
from repositories.subcategory import SubcategoryRepository
from repositories.user import UserRepository
from utils.localizator import Localizator
from utils.html_escape import safe_html


class AdminService:

    @staticmethod
    async def get_announcement_menu() -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "send_everyone"),
                          callback_data=AdminAnnouncementCallback.create(1))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "restocking"),
                          callback_data=AdminAnnouncementCallback.create(2, AnnouncementType.RESTOCKING))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "stock"),
                          callback_data=AdminAnnouncementCallback.create(2, AnnouncementType.CURRENT_STOCK))
        kb_builder.row(AdminConstants.back_to_main_button)
        kb_builder.adjust(1)
        return Localizator.get_text(BotEntity.ADMIN, "announcements"), kb_builder

    @staticmethod
    async def send_announcement(callback: CallbackQuery, session: AsyncSession | Session):
        unpacked_cb = AdminAnnouncementCallback.unpack(callback.data)
        await callback.message.edit_reply_markup()
        active_users = await UserRepository.get_active(session)
        all_users_count = await UserRepository.get_all_count(session)
        counter = 0
        for user in active_users:
            try:
                await callback.message.copy_to(user.telegram_id, reply_markup=None)
                counter += 1
                await asyncio.sleep(1.5)
            except TelegramForbiddenError as e:
                logging.error(f"TelegramForbiddenError: {e.message}")
                if "user is deactivated" in e.message.lower():
                    user.can_receive_messages = False
                elif "bot was blocked by the user" in e.message.lower():
                    user.can_receive_messages = False
                    await UserRepository.update(user, session)
            except Exception as e:
                logging.error(e)
            finally:
                if unpacked_cb.announcement_type == AnnouncementType.RESTOCKING:
                    await ItemRepository.set_not_new(session)
                await session_commit(session)
        return Localizator.get_text(BotEntity.ADMIN, "sending_result").format(counter=counter,
                                                                              len=len(active_users),
                                                                              users_count=all_users_count)

    @staticmethod
    async def get_inventory_management_menu() -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "add_items"),
                          callback_data=AdminInventoryManagementCallback.create(level=1, entity_type=EntityType.ITEM))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "delete_category"),
                          callback_data=AdminInventoryManagementCallback.create(level=2,
                                                                                entity_type=EntityType.CATEGORY))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "delete_subcategory"),
                          callback_data=AdminInventoryManagementCallback.create(level=2,
                                                                                entity_type=EntityType.SUBCATEGORY))
        kb_builder.adjust(1)
        kb_builder.row(AdminConstants.back_to_main_button)
        return Localizator.get_text(BotEntity.ADMIN, "inventory_management"), kb_builder

    @staticmethod
    async def get_add_items_type(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = AdminInventoryManagementCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "add_items_json"),
                          callback_data=AdminInventoryManagementCallback.create(1, AddType.JSON, EntityType.ITEM))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "add_items_txt"),
                          callback_data=AdminInventoryManagementCallback.create(1, AddType.TXT, EntityType.ITEM))
        kb_builder.adjust(1)
        kb_builder.row(unpacked_cb.get_back_button())
        return Localizator.get_text(BotEntity.ADMIN, "add_items_msg"), kb_builder

    @staticmethod
    async def get_delete_entity_menu(callback: CallbackQuery, session: AsyncSession | Session):
        unpacked_cb = AdminInventoryManagementCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()
        match unpacked_cb.entity_type:
            case EntityType.CATEGORY:
                categories = await CategoryRepository.get_to_delete(unpacked_cb.page, session)
                [kb_builder.button(text=category.name, callback_data=AdminInventoryManagementCallback.create(
                    level=3,
                    entity_type=unpacked_cb.entity_type,
                    entity_id=category.id
                )) for category in categories]
                kb_builder.adjust(1)
                kb_builder = await add_pagination_buttons(kb_builder, unpacked_cb,
                                                          CategoryRepository.get_maximum_page(session),
                                                          unpacked_cb.get_back_button(0))
                return Localizator.get_text(BotEntity.ADMIN, "delete_category"), kb_builder
            case EntityType.SUBCATEGORY:
                subcategories = await SubcategoryRepository.get_to_delete(unpacked_cb.page, session)
                [kb_builder.button(text=subcategory.name, callback_data=AdminInventoryManagementCallback.create(
                    level=3,
                    entity_type=unpacked_cb.entity_type,
                    entity_id=subcategory.id
                )) for subcategory in subcategories]
                kb_builder.adjust(1)
                kb_builder = await add_pagination_buttons(kb_builder, unpacked_cb,
                                                          SubcategoryRepository.get_maximum_page_to_delete(session),
                                                          unpacked_cb.get_back_button(0))
                return Localizator.get_text(BotEntity.ADMIN, "delete_subcategory"), kb_builder

    @staticmethod
    async def delete_confirmation(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[
        str, InlineKeyboardBuilder]:
        unpacked_cb = AdminInventoryManagementCallback.unpack(callback.data)
        unpacked_cb.confirmation = True
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "confirm"),
                          callback_data=unpacked_cb)
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "cancel"),
                          callback_data=AdminInventoryManagementCallback.create(0))
        match unpacked_cb.entity_type:
            case EntityType.CATEGORY:
                category = await CategoryRepository.get_by_id(unpacked_cb.entity_id, session)
                return Localizator.get_text(BotEntity.ADMIN, "delete_entity_confirmation").format(
                    entity=unpacked_cb.entity_type.name.capitalize(),
                    entity_name=category.name
                ), kb_builder
            case EntityType.SUBCATEGORY:
                subcategory = await SubcategoryRepository.get_by_id(unpacked_cb.entity_id, session)
                return Localizator.get_text(BotEntity.ADMIN, "delete_entity_confirmation").format(
                    entity=unpacked_cb.entity_type.name.capitalize(),
                    entity_name=subcategory.name
                ), kb_builder

    @staticmethod
    async def delete_entity(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[
        str, InlineKeyboardBuilder]:
        unpacked_cb = AdminInventoryManagementCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()
        kb_builder.row(AdminConstants.back_to_main_button)
        match unpacked_cb.entity_type:
            case EntityType.CATEGORY:
                category = await CategoryRepository.get_by_id(unpacked_cb.entity_id, session)
                await ItemRepository.delete_unsold_by_category_id(unpacked_cb.entity_id, session)
                await session_commit(session)
                return Localizator.get_text(BotEntity.ADMIN, "successfully_deleted").format(
                    entity_name=category.name,
                    entity_to_delete=unpacked_cb.entity_type.name.capitalize()), kb_builder
            case EntityType.SUBCATEGORY:
                subcategory = await SubcategoryRepository.get_by_id(unpacked_cb.entity_id, session)
                await ItemRepository.delete_unsold_by_subcategory_id(unpacked_cb.entity_id, session)
                await session_commit(session)
                return Localizator.get_text(BotEntity.ADMIN, "successfully_deleted").format(
                    entity_name=subcategory.name,
                    entity_to_delete=unpacked_cb.entity_type.name.capitalize()), kb_builder

    @staticmethod
    async def get_add_item_msg(callback: CallbackQuery, state: FSMContext):
        unpacked_cb = AdminInventoryManagementCallback.unpack(callback.data)
        kb_markup = InlineKeyboardBuilder()
        kb_markup.button(text=Localizator.get_text(BotEntity.COMMON, 'cancel'),
                         callback_data=AdminInventoryManagementCallback.create(0))
        await state.update_data(add_type=unpacked_cb.add_type.value)
        await state.set_state()
        match unpacked_cb.add_type:
            case AddType.JSON:
                await state.set_state(AdminInventoryManagementStates.document)
                return Localizator.get_text(BotEntity.ADMIN, "add_items_json_msg"), kb_markup
            case AddType.TXT:
                await state.set_state(AdminInventoryManagementStates.document)
                return Localizator.get_text(BotEntity.ADMIN, "add_items_txt_msg"), kb_markup

    @staticmethod
    async def get_user_management_menu() -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "credit_management"),
                          callback_data=UserManagementCallback.create(1))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "make_refund"),
                          callback_data=UserManagementCallback.create(2))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "unban_user"),
                          callback_data=UserManagementCallback.create(1, UserManagementOperation.UNBAN_USER))
        kb_builder.adjust(1)
        kb_builder.row(AdminConstants.back_to_main_button)
        return Localizator.get_text(BotEntity.ADMIN, "user_management"), kb_builder

    @staticmethod
    async def get_credit_management_menu(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = UserManagementCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "credit_management_add_balance"),
                          callback_data=UserManagementCallback.create(1, UserManagementOperation.ADD_BALANCE))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "credit_management_reduce_balance"),
                          callback_data=UserManagementCallback.create(1, UserManagementOperation.REDUCE_BALANCE))
        kb_builder.row(unpacked_cb.get_back_button())
        return Localizator.get_text(BotEntity.ADMIN, "credit_management"), kb_builder

    @staticmethod
    async def get_banned_users_list(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[str, InlineKeyboardBuilder]:
        """
        Display list of all banned users with unban buttons.

        Shows:
        - Username/ID
        - Strike count
        - Ban date
        - Ban reason
        - Unban button for each user
        """
        from repositories.user import UserRepository
        from repositories.user_strike import UserStrikeRepository

        unpacked_cb = UserManagementCallback.unpack(callback.data)
        banned_users = await UserRepository.get_banned_users(session)

        kb_builder = InlineKeyboardBuilder()

        if not banned_users:
            message = Localizator.get_text(BotEntity.ADMIN, "no_banned_users")
        else:
            message = Localizator.get_text(BotEntity.ADMIN, "banned_users_list_header").format(
                count=len(banned_users)
            )

            for user in banned_users:
                # Get actual strike count from DB
                strikes = await UserStrikeRepository.get_by_user_id(user.id, session)
                strike_count = len(strikes)

                # Format username display
                if user.telegram_username:
                    user_display = f"@{safe_html(user.telegram_username)}"
                else:
                    user_display = f"ID: {user.telegram_id}"

                # Format ban date
                ban_date = user.blocked_at.strftime("%d.%m.%Y") if user.blocked_at else "Unknown"

                # Build user info text
                user_info = Localizator.get_text(BotEntity.ADMIN, "banned_user_item").format(
                    user_display=user_display,
                    telegram_id=user.telegram_id,
                    strike_count=strike_count,
                    ban_date=ban_date,
                    ban_reason=safe_html(user.blocked_reason) if user.blocked_reason else "Unknown"
                )
                message += user_info

                # Add detail view button for this user
                kb_builder.button(
                    text=Localizator.get_text(BotEntity.ADMIN, "unban_user_button").format(user_display=user_display),
                    callback_data=UserManagementCallback.create(
                        level=3,  # Level 3: banned user detail view
                        operation=UserManagementOperation.UNBAN_USER,
                        page=user.id  # Store user_id in page field
                    )
                )

        kb_builder.adjust(1)
        kb_builder.row(unpacked_cb.get_back_button())
        return message, kb_builder

    @staticmethod
    async def unban_confirmation(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[str, InlineKeyboardBuilder]:
        """
        Show confirmation dialog before unbanning a user.

        Args:
            callback: Callback with user_id in page field
            session: Database session

        Returns:
            tuple: (confirmation message, keyboard builder)
        """
        from repositories.user import UserRepository

        unpacked_cb = UserManagementCallback.unpack(callback.data)
        user_id = unpacked_cb.page

        # Get user data
        user = await UserRepository.get_by_id(user_id, session)

        if not user:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(
                text=Localizator.get_text(BotEntity.COMMON, "back_button"),
                callback_data=UserManagementCallback.create(level=2, operation=UserManagementOperation.UNBAN_USER)
            )
            return Localizator.get_text(BotEntity.ADMIN, "user_not_found"), kb_builder

        # Build confirmation message
        if user.telegram_username:
            user_display = f"@{safe_html(user.telegram_username)}"
        else:
            user_display = f"ID: {user.telegram_id}"

        msg = Localizator.get_text(BotEntity.ADMIN, "unban_confirmation").format(
            user_display=user_display,
            telegram_id=user.telegram_id,
            strike_count=user.strike_count
        )

        # Build keyboard with confirmation
        unpacked_cb.confirmation = True
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "confirm"),
            callback_data=unpacked_cb
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, "cancel"),
            callback_data=UserManagementCallback.create(level=3, operation=UserManagementOperation.UNBAN_USER, page=user_id)
        )
        kb_builder.adjust(1)

        return msg, kb_builder

    @staticmethod
    async def unban_user(callback: CallbackQuery, session: AsyncSession | Session) -> str:
        """
        Unban a user by setting is_blocked = False.

        Args:
            callback: Callback with user_id in page field
            session: Database session

        Returns:
            str: Success or error message
        """
        from repositories.user import UserRepository

        unpacked_cb = UserManagementCallback.unpack(callback.data)
        user_id = unpacked_cb.page  # user_id is stored in page field

        # Get user
        user = await UserRepository.get_by_id(user_id, session)

        if not user:
            return Localizator.get_text(BotEntity.ADMIN, "user_not_found")

        if not user.is_blocked:
            return Localizator.get_text(BotEntity.ADMIN, "user_not_banned").format(
                user_display=safe_html(user.telegram_username) if user.telegram_username else user.telegram_id
            )

        # Unban user
        user.is_blocked = False
        user.blocked_at = None
        user.blocked_reason = f"Unbanned by admin at {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"

        await UserRepository.update(user, session)
        from db import session_commit
        await session_commit(session)

        # Format user display
        if user.telegram_username:
            user_display = f"@{safe_html(user.telegram_username)}"
        else:
            user_display = f"ID: {user.telegram_id}"

        # Send notification to unbanned user
        from services.notification import NotificationService
        user_message = Localizator.get_text(BotEntity.USER, "user_unbanned_by_admin_notification").format(
            strike_count=user.strike_count
        )
        await NotificationService.send_to_user(user_message, user.telegram_id)

        return Localizator.get_text(BotEntity.ADMIN, "user_unbanned_success").format(
            user_display=user_display,
            strike_count=user.strike_count
        )

    @staticmethod
    async def get_banned_user_detail_data(user_id: int, session: AsyncSession | Session) -> dict | None:
        """
        Get data for banned user detail view.

        Business logic: Fetch user, strikes, format data for display.
        No Telegram objects, no keyboard building - pure data preparation.

        Args:
            user_id: User ID to fetch details for
            session: Database session

        Returns:
            dict with user data and strikes, or None if user not found/not banned
            {
                "user_id": int,
                "telegram_id": int,
                "telegram_username": str | None,
                "strike_count": int,
                "blocked_at": datetime | None,
                "blocked_reason": str | None,
                "strikes": list[dict]  # [{created_at, strike_type, order_invoice_id, reason}]
            }
        """
        from repositories.user_strike import UserStrikeRepository

        # Get user
        user = await UserRepository.get_by_id(user_id, session)

        if not user or not user.is_blocked:
            return None

        # Get all strikes for this user (with eager loading to avoid lazy loading issues)
        strikes = await UserStrikeRepository.get_by_user_id(user_id, session, eager_load_order=True)
        strikes_sorted = sorted(strikes, key=lambda s: s.created_at, reverse=True)

        # Build strikes list (max 10 to avoid message length issues)
        strikes_data = []
        for strike in strikes_sorted[:10]:
            # Get order invoice number if available (from first invoice)
            invoice_number = None
            if strike.order_id and strike.order and strike.order.invoices:
                # Get first invoice (main invoice for the order)
                invoice_number = strike.order.invoices[0].invoice_number

            strikes_data.append({
                "created_at": strike.created_at,
                "strike_type": strike.strike_type.value,  # Convert enum to string
                "order_invoice_id": invoice_number,
                "reason": strike.reason
            })

        return {
            "user_id": user.id,
            "telegram_id": user.telegram_id,
            "telegram_username": user.telegram_username,
            "strike_count": user.strike_count,
            "blocked_at": user.blocked_at,
            "blocked_reason": user.blocked_reason,
            "strikes": strikes_data,
            "total_strike_count": len(strikes_sorted)  # For truncation message
        }

    @staticmethod
    async def request_user_entity(callback: CallbackQuery, state: FSMContext):
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "cancel"),
                          callback_data=UserManagementCallback.create(0))
        await state.set_state(UserManagementStates.user_entity)
        unpacked_cb = UserManagementCallback.unpack(callback.data)
        await state.update_data(operation=unpacked_cb.operation.value)
        return Localizator.get_text(BotEntity.ADMIN, "credit_management_request_user_entity"), kb_builder

    @staticmethod
    async def request_balance_amount(message: Message, state: FSMContext) -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "cancel"),
                          callback_data=UserManagementCallback.create(0))
        await state.update_data(user_entity=message.text)
        await state.set_state(UserManagementStates.balance_amount)
        data = await state.get_data()
        operation = UserManagementOperation(int(data['operation']))
        match operation:
            case UserManagementOperation.ADD_BALANCE:
                return Localizator.get_text(BotEntity.ADMIN, "credit_management_plus_operation").format(
                    currency_text=Localizator.get_currency_text()), kb_builder
            case UserManagementOperation.REDUCE_BALANCE:
                return Localizator.get_text(BotEntity.ADMIN, "credit_management_minus_operation").format(
                    currency_text=Localizator.get_currency_text()), kb_builder

    @staticmethod
    async def balance_management(message: Message, state: FSMContext, session: AsyncSession | Session) -> str:
        data = await state.get_data()
        await state.clear()
        user = await UserRepository.get_user_entity(data['user_entity'], session)
        operation = UserManagementOperation(int(data['operation']))
        if user is None:
            return Localizator.get_text(BotEntity.ADMIN, "credit_management_user_not_found")
        elif operation == UserManagementOperation.ADD_BALANCE:
            user.top_up_amount = round(user.top_up_amount + float(message.text), 2)
            await UserRepository.update(user, session)
            await session_commit(session)
            return Localizator.get_text(BotEntity.ADMIN, "credit_management_added_success").format(
                amount=message.text,
                telegram_id=user.telegram_id,
                currency_text=Localizator.get_currency_text())
        else:
            # REDUCE_BALANCE: Subtract from wallet
            amount_to_reduce = float(message.text)

            # Round amounts for comparison (avoid floating-point errors)
            current_balance = round(user.top_up_amount, 2)
            amount_to_reduce = round(amount_to_reduce, 2)

            # Check if user has enough balance
            if current_balance < amount_to_reduce:
                return Localizator.get_text(BotEntity.ADMIN, "credit_management_insufficient_balance").format(
                    current_balance=current_balance,
                    amount=amount_to_reduce,
                    telegram_id=user.telegram_id,
                    currency_text=Localizator.get_currency_text())

            # Subtract and round to 2 decimals
            user.top_up_amount = round(max(0.0, user.top_up_amount - amount_to_reduce), 2)
            await UserRepository.update(user, session)
            await session_commit(session)
            return Localizator.get_text(BotEntity.ADMIN, "credit_management_reduced_success").format(
                amount=message.text,
                telegram_id=user.telegram_id,
                currency_text=Localizator.get_currency_text())

    @staticmethod
    async def get_refund_menu(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[
        str, InlineKeyboardBuilder]:
        unpacked_cb = UserManagementCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()
        refund_data = await BuyRepository.get_refund_data(unpacked_cb.page, session)
        for refund_item in refund_data:
            callback = UserManagementCallback.create(
                unpacked_cb.level + 1,
                UserManagementOperation.REFUND,
                buy_id=refund_item.buy_id)
            if refund_item.telegram_username:
                kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "refund_by_username").format(
                    telegram_username=safe_html(refund_item.telegram_username),
                    total_price=refund_item.total_price,
                    subcategory=refund_item.subcategory_name,
                    currency_sym=Localizator.get_currency_symbol()),
                    callback_data=callback)
            else:
                kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "refund_by_tgid").format(
                    telegram_id=refund_item.telegram_id,
                    total_price=refund_item.total_price,
                    subcategory=refund_item.subcategory_name,
                    currency_sym=Localizator.get_currency_symbol()),
                    callback_data=callback)
        kb_builder.adjust(1)
        kb_builder = await add_pagination_buttons(kb_builder, unpacked_cb,
                                                  BuyRepository.get_max_refund_page(session),
                                                  unpacked_cb.get_back_button(0))
        return Localizator.get_text(BotEntity.ADMIN, "refund_menu"), kb_builder

    @staticmethod
    async def refund_confirmation(callback: CallbackQuery, session: AsyncSession | Session):
        unpacked_cb = UserManagementCallback.unpack(callback.data)
        unpacked_cb.confirmation = True
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "confirm"),
                          callback_data=unpacked_cb)
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "cancel"),
                          callback_data=UserManagementCallback.create(0))
        refund_data = await BuyRepository.get_refund_data_single(unpacked_cb.buy_id, session)
        if refund_data.telegram_username:
            return Localizator.get_text(BotEntity.ADMIN, "refund_confirmation_by_username").format(
                telegram_username=safe_html(refund_data.telegram_username),
                quantity=refund_data.quantity,
                subcategory=refund_data.subcategory_name,
                total_price=refund_data.total_price,
                currency_sym=Localizator.get_currency_symbol()), kb_builder
        else:
            return Localizator.get_text(BotEntity.ADMIN, "refund_confirmation_by_tgid").format(
                telegram_id=refund_data.telegram_id,
                quantity=refund_data.quantity,
                subcategory=refund_data.subcategory_name,
                total_price=refund_data.total_price,
                currency_sym=Localizator.get_currency_symbol()), kb_builder

    @staticmethod
    async def get_statistics_menu() -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "users_statistics"),
                          callback_data=StatisticsCallback.create(1, StatisticsEntity.USERS))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "buys_statistics"),
                          callback_data=StatisticsCallback.create(1, StatisticsEntity.BUYS))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "deposits_statistics"),
                          callback_data=StatisticsCallback.create(1, StatisticsEntity.DEPOSITS))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "get_database_file"),
                          callback_data=StatisticsCallback.create(3))
        kb_builder.adjust(1)
        kb_builder.row(AdminConstants.back_to_main_button)
        return Localizator.get_text(BotEntity.ADMIN, "pick_statistics_entity"), kb_builder

    @staticmethod
    async def get_timedelta_menu(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        unpacked_cb = StatisticsCallback.unpack(callback.data)
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "1_day"),
                          callback_data=StatisticsCallback.create(unpacked_cb.level + 1,
                                                                  unpacked_cb.statistics_entity,
                                                                  StatisticsTimeDelta.DAY))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "7_day"),
                          callback_data=StatisticsCallback.create(unpacked_cb.level + 1,
                                                                  unpacked_cb.statistics_entity,
                                                                  StatisticsTimeDelta.WEEK))
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "30_day"),
                          callback_data=StatisticsCallback.create(unpacked_cb.level + 1,
                                                                  unpacked_cb.statistics_entity,
                                                                  StatisticsTimeDelta.MONTH))
        kb_builder.row(unpacked_cb.get_back_button(0))
        return Localizator.get_text(BotEntity.ADMIN, "statistics_timedelta"), kb_builder

    @staticmethod
    async def get_statistics(callback: CallbackQuery, session: AsyncSession | Session):
        unpacked_cb = StatisticsCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()
        match unpacked_cb.statistics_entity:
            case StatisticsEntity.USERS:
                users, users_count = await UserRepository.get_by_timedelta(unpacked_cb.timedelta, unpacked_cb.page,
                                                                           session)
                # Build user list for message text
                user_list = []
                for user in users:
                    if user.telegram_username:
                        # Add as clickable button
                        kb_builder.button(text=f"@{user.telegram_username}", url=f't.me/{user.telegram_username}')
                    else:
                        # Add to text list (no button due to privacy restrictions)
                        user_list.append(f"• User {user.telegram_id}")

                kb_builder.adjust(1)
                kb_builder = await add_pagination_buttons(
                    kb_builder,
                    unpacked_cb,
                    UserRepository.get_max_page_by_timedelta(unpacked_cb.timedelta, session),
                    None)
                kb_builder.row(AdminConstants.back_to_main_button, unpacked_cb.get_back_button())

                # Build message with user list if any users without username
                msg = Localizator.get_text(BotEntity.ADMIN, "new_users_msg").format(
                    users_count=users_count,
                    timedelta=unpacked_cb.timedelta.value
                )
                if user_list:
                    msg += "\n\n<b>Users without username:</b>\n" + "\n".join(user_list)

                return msg, kb_builder
            case StatisticsEntity.BUYS:
                buys = await BuyRepository.get_by_timedelta(unpacked_cb.timedelta, session)
                total_profit = 0.0
                items_sold = 0
                for buy in buys:
                    total_profit += buy.total_price
                    items_sold += buy.quantity
                kb_builder.row(AdminConstants.back_to_main_button, unpacked_cb.get_back_button())
                return Localizator.get_text(BotEntity.ADMIN, "sales_statistics").format(
                    timedelta=unpacked_cb.timedelta,
                    total_profit=total_profit, items_sold=items_sold,
                    buys_count=len(buys), currency_sym=Localizator.get_currency_symbol()), kb_builder
            case StatisticsEntity.DEPOSITS:
                deposits = await DepositRepository.get_by_timedelta(unpacked_cb.timedelta, session)
                fiat_amount = 0.0
                btc_amount = 0.0
                ltc_amount = 0.0
                sol_amount = 0.0
                eth_amount = 0.0
                bnb_amount = 0.0
                for deposit in deposits:
                    match deposit.network:
                        case "BTC":
                            btc_amount += deposit.amount / pow(10, deposit.network.get_divider())
                        case "LTC":
                            ltc_amount += deposit.amount / pow(10, deposit.network.get_divider())
                        case "SOL":
                            sol_amount += deposit.amount / pow(10, deposit.network.get_divider())
                        case "ETH":
                            eth_amount += deposit.amount / pow(10, deposit.network.get_divider())
                        case "BNB":
                            bnb_amount += deposit.amount / pow(10, deposit.network.get_divider())
                prices = await CryptoApiWrapper.get_crypto_prices()
                btc_price = prices[Cryptocurrency.BTC.get_coingecko_name()][config.CURRENCY.value.lower()]
                ltc_price = prices[Cryptocurrency.LTC.get_coingecko_name()][config.CURRENCY.value.lower()]
                sol_price = prices[Cryptocurrency.SOL.get_coingecko_name()][config.CURRENCY.value.lower()]
                eth_price = prices[Cryptocurrency.ETH.get_coingecko_name()][config.CURRENCY.value.lower()]
                bnb_price = prices[Cryptocurrency.BNB.get_coingecko_name()][config.CURRENCY.value.lower()]
                fiat_amount += ((btc_amount * btc_price) + (ltc_amount * ltc_price) + (sol_amount * sol_price)
                                + (eth_amount * eth_price) + (bnb_amount * bnb_price))
                kb_builder.row(AdminConstants.back_to_main_button, unpacked_cb.get_back_button())
                return Localizator.get_text(BotEntity.ADMIN, "deposits_statistics_msg").format(
                    timedelta=unpacked_cb.timedelta, deposits_count=len(deposits),
                    btc_amount=btc_amount, ltc_amount=ltc_amount,
                    sol_amount=sol_amount, eth_amount=eth_amount,
                    bnb_amount=bnb_amount,
                    fiat_amount=fiat_amount, currency_text=Localizator.get_currency_text()), kb_builder

    @staticmethod
    async def get_wallet_menu() -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "withdraw_funds"),
                          callback_data=WalletCallback.create(1))
        kb_builder.row(AdminConstants.back_to_main_button)
        return Localizator.get_text(BotEntity.ADMIN, "crypto_withdraw"), kb_builder

    @staticmethod
    async def get_withdraw_menu() -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        wallet_balance = await CryptoApiWrapper.get_wallet_balance()
        [kb_builder.button(
            text=Localizator.get_text(BotEntity.COMMON, f"{key.lower()}_top_up"),
            callback_data=WalletCallback.create(1, Cryptocurrency(key))
        ) for key in wallet_balance.keys()]
        kb_builder.adjust(1)
        kb_builder.row(AdminConstants.back_to_main_button)
        msg_text = Localizator.get_text(BotEntity.ADMIN, "crypto_wallet").format(
            btc_balance=wallet_balance.get('BTC') or 0.0,
            ltc_balance=wallet_balance.get('LTC') or 0.0,
            sol_balance=wallet_balance.get('SOL') or 0.0,
            eth_balance=wallet_balance.get('ETH') or 0.0,
            bnb_balance=wallet_balance.get('BNB') or 0.0
        )
        if sum(wallet_balance.values()) > 0:
            msg_text += Localizator.get_text(BotEntity.ADMIN, "choose_crypto_to_withdraw")
        return msg_text, kb_builder

    @staticmethod
    async def request_crypto_address(callback: CallbackQuery, state: FSMContext) -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = WalletCallback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()
        kb_builder.row(AdminConstants.back_to_main_button)
        await state.update_data(cryptocurrency=unpacked_cb.cryptocurrency)
        await state.set_state(WalletStates.crypto_address)
        return Localizator.get_text(BotEntity.ADMIN, "send_addr_request").format(
            crypto_name=unpacked_cb.cryptocurrency.value), kb_builder

    @staticmethod
    async def calculate_withdrawal(message: Message, state: FSMContext) -> tuple[str, InlineKeyboardBuilder]:
        kb_builder = InlineKeyboardBuilder()
        if message.text and message.text.lower() == "cancel":
            await state.clear()
            return Localizator.get_text(BotEntity.COMMON, "cancelled"), kb_builder
        to_address = message.text
        state_data = await state.get_data()
        await state.update_data(to_address=to_address)
        cryptocurrency = Cryptocurrency(state_data['cryptocurrency'])
        prices = await CryptoApiWrapper.get_crypto_prices()
        price = prices[cryptocurrency.get_coingecko_name()][config.CURRENCY.value.lower()]

        withdraw_dto = await CryptoApiWrapper.withdrawal(
            cryptocurrency,
            to_address,
            True
        )
        withdraw_dto: WithdrawalDTO = WithdrawalDTO.model_validate(withdraw_dto, from_attributes=True)
        if withdraw_dto.receivingAmount > 0:
            kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "confirm"),
                              callback_data=WalletCallback.create(2, cryptocurrency))
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "cancel"),
                          callback_data=WalletCallback.create(0))
        return Localizator.get_text(BotEntity.ADMIN, "crypto_withdrawal_info").format(
            address=withdraw_dto.toAddress,
            crypto_name=cryptocurrency.value,
            withdrawal_amount=withdraw_dto.totalWithdrawalAmount,
            withdrawal_amount_fiat=withdraw_dto.totalWithdrawalAmount * price,
            currency_text=Localizator.get_currency_text(),
            blockchain_fee_amount=withdraw_dto.blockchainFeeAmount,
            blockchain_fee_fiat=withdraw_dto.blockchainFeeAmount * price,
            service_fee_amount=withdraw_dto.serviceFeeAmount,
            service_fee_fiat=withdraw_dto.serviceFeeAmount * price,
            receiving_amount=withdraw_dto.receivingAmount,
            receiving_amount_fiat=withdraw_dto.receivingAmount * price,
        ), kb_builder

    @staticmethod
    async def withdraw_transaction(callback: CallbackQuery, state: FSMContext) -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = WalletCallback.unpack(callback.data)
        state_data = await state.get_data()
        kb_builder = InlineKeyboardBuilder()
        withdraw_dto = await CryptoApiWrapper.withdrawal(
            unpacked_cb.cryptocurrency,
            state_data['to_address'],
            False
        )
        withdraw_dto = WithdrawalDTO.model_validate(withdraw_dto, from_attributes=True)
        match unpacked_cb.cryptocurrency:
            case Cryptocurrency.LTC:
                [kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "transaction"),
                                   url=f"{CryptoApiWrapper.LTC_API_BASENAME_TX}{tx_id}") for tx_id in
                 withdraw_dto.txIdList]
            case Cryptocurrency.BTC:
                [kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "transaction"),
                                   url=f"{CryptoApiWrapper.BTC_API_BASENAME_TX}{tx_id}") for tx_id in
                 withdraw_dto.txIdList]
            case Cryptocurrency.SOL:
                [kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "transaction"),
                                   url=f"{CryptoApiWrapper.SOL_API_BASENAME_TX}{tx_id}") for tx_id in
                 withdraw_dto.txIdList]
            case Cryptocurrency.ETH:
                [kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "transaction"),
                                   url=f"{CryptoApiWrapper.ETH_API_BASENAME_TX}{tx_id}") for tx_id in
                 withdraw_dto.txIdList]
            case Cryptocurrency.BNB:
                [kb_builder.button(text=Localizator.get_text(BotEntity.ADMIN, "transaction"),
                                   url=f"{CryptoApiWrapper.BNB_API_BASENAME_TX}{tx_id}") for tx_id in
                 withdraw_dto.txIdList]
        kb_builder.adjust(1)
        await state.clear()
        return Localizator.get_text(BotEntity.ADMIN, "transaction_broadcasted"), kb_builder

    @staticmethod
    async def validate_withdrawal_address(message: Message, state: FSMContext) -> bool:
        address_regex = {
            Cryptocurrency.BTC: re.compile(r'^bc1[a-zA-HJ-NP-Z0-9]{25,39}$'),
            Cryptocurrency.LTC: re.compile(r'^ltc1[a-zA-HJ-NP-Z0-9]{26,}$'),
            Cryptocurrency.ETH: re.compile(r'^0x[a-fA-F0-9]{40}$'),
            Cryptocurrency.BNB: re.compile(r'^0x[a-fA-F0-9]{40}$'),
            Cryptocurrency.SOL: re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'),
        }
        state_data = await state.get_data()
        cryptocurrency = Cryptocurrency(state_data['cryptocurrency'])
        regex = address_regex[cryptocurrency]
        return bool(regex.match(message.text))

    # ==================== Analytics v2 Methods ====================

    @staticmethod
    async def get_analytics_v2_menu() -> tuple[str, InlineKeyboardBuilder]:
        """Build Analytics v2 main menu."""
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "analytics_v2_sales"),
            callback_data=AnalyticsV2Callback.create(1, AnalyticsV2Entity.SALES)
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "analytics_v2_violations"),
            callback_data=AnalyticsV2Callback.create(1, AnalyticsV2Entity.VIOLATIONS)
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "analytics_v2_revenue"),
            callback_data=AnalyticsV2Callback.create(1, AnalyticsV2Entity.REVENUE)
        )
        # NEW: Sales Analytics (Subcategory Report)
        kb_builder.button(
            text="💰 Sales Analytics",
            callback_data=AnalyticsV2Callback.create(level=11).pack()
        )
        kb_builder.adjust(1)
        kb_builder.row(AdminConstants.back_to_main_button)
        return Localizator.get_text(BotEntity.ADMIN, "analytics_v2_menu"), kb_builder

    @staticmethod
    async def get_analytics_v2_timedelta_menu(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        """Build timedelta picker menu."""
        kb_builder = InlineKeyboardBuilder()
        unpacked_cb = AnalyticsV2Callback.unpack(callback.data)

        # Get entity name for display
        entity_names = {
            AnalyticsV2Entity.SALES: Localizator.get_text(BotEntity.ADMIN, "analytics_v2_sales"),
            AnalyticsV2Entity.VIOLATIONS: Localizator.get_text(BotEntity.ADMIN, "analytics_v2_violations"),
            AnalyticsV2Entity.REVENUE: Localizator.get_text(BotEntity.ADMIN, "analytics_v2_revenue"),
        }
        entity_name = entity_names.get(unpacked_cb.entity, "")

        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "analytics_v2_7_days"),
            callback_data=AnalyticsV2Callback.create(2, unpacked_cb.entity, AnalyticsV2TimeDelta.WEEK)
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "analytics_v2_30_days"),
            callback_data=AnalyticsV2Callback.create(2, unpacked_cb.entity, AnalyticsV2TimeDelta.MONTH)
        )
        kb_builder.button(
            text=Localizator.get_text(BotEntity.ADMIN, "analytics_v2_90_days"),
            callback_data=AnalyticsV2Callback.create(2, unpacked_cb.entity, AnalyticsV2TimeDelta.QUARTER)
        )
        kb_builder.adjust(1)
        kb_builder.row(InlineKeyboardButton(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=AnalyticsV2Callback.create(0).pack()
        ))
        msg = Localizator.get_text(BotEntity.ADMIN, "analytics_v2_timedelta_menu").format(entity=entity_name)
        return msg, kb_builder

    @staticmethod
    async def get_analytics_v2_data(callback: CallbackQuery, session: AsyncSession | Session) -> tuple[str, InlineKeyboardBuilder]:
        """Display analytics data based on entity and timedelta."""
        unpacked_cb = AnalyticsV2Callback.unpack(callback.data)
        kb_builder = InlineKeyboardBuilder()

        from repositories.sales_record import SalesRecordRepository
        from repositories.violation_statistics import ViolationStatisticsRepository
        from enums.violation_type import ViolationType

        days = unpacked_cb.timedelta
        currency_text = Localizator.get_currency_text()

        match unpacked_cb.entity:
            case AnalyticsV2Entity.SALES:
                # Get sales data
                total_revenue = await SalesRecordRepository.get_total_revenue(days, session)
                total_items = await SalesRecordRepository.get_total_items_sold(days, session)

                msg = Localizator.get_text(BotEntity.ADMIN, 'analytics_v2_sales_data').format(
                    days=days,
                    items_sold=total_items,
                    total_revenue=total_revenue,
                    currency_text=currency_text
                )

            case AnalyticsV2Entity.VIOLATIONS:
                # Get violation data
                underpayment_count = await ViolationStatisticsRepository.get_violation_count_by_type(ViolationType.UNDERPAYMENT_FINAL, days, session)
                late_payment_count = await ViolationStatisticsRepository.get_violation_count_by_type(ViolationType.LATE_PAYMENT, days, session)
                timeout_count = await ViolationStatisticsRepository.get_violation_count_by_type(ViolationType.TIMEOUT, days, session)
                cancellation_count = await ViolationStatisticsRepository.get_violation_count_by_type(ViolationType.USER_CANCELLATION_LATE, days, session)
                total_penalty = await ViolationStatisticsRepository.get_total_penalty_amount(days, session)

                msg = Localizator.get_text(BotEntity.ADMIN, 'analytics_v2_violations_data').format(
                    days=days,
                    underpayment_count=underpayment_count,
                    late_payment_count=late_payment_count,
                    timeout_count=timeout_count,
                    cancellation_count=cancellation_count,
                    total_penalty=total_penalty,
                    currency_text=currency_text
                )

            case AnalyticsV2Entity.REVENUE:
                # Revenue overview
                total_revenue = await SalesRecordRepository.get_total_revenue(days, session)
                total_items = await SalesRecordRepository.get_total_items_sold(days, session)
                avg_per_item = total_revenue / total_items if total_items > 0 else 0.0

                msg = Localizator.get_text(BotEntity.ADMIN, 'analytics_v2_revenue_data').format(
                    days=days,
                    total_revenue=total_revenue,
                    items_sold=total_items,
                    avg_per_item=avg_per_item,
                    currency_text=currency_text
                )

        # Back button
        kb_builder.row(InlineKeyboardButton(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=AnalyticsV2Callback.create(1, unpacked_cb.entity).pack()
        ))
        kb_builder.row(AdminConstants.back_to_main_button)

        return msg, kb_builder

    # === Registration Management Methods ===

    @staticmethod
    async def get_user_list_view(
            callback: CallbackQuery,
            session: AsyncSession | Session
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Show paginated user list filtered by approval status.

        Shows user list with filters: Pending, Waitlist, Banned.
        Each user entry shows: username/ID, registration date, status.
        """
        from repositories.user import UserRepository
        from enums.approval_status import ApprovalStatus
        from utils.html_escape import safe_html

        unpacked_cb = UserManagementCallback.unpack(callback.data)

        # Map filter_type to ApprovalStatus
        if unpacked_cb.filter_type == ApprovalStatus.PENDING.value:
            status_filter = ApprovalStatus.PENDING
            title_key = "user_list_title_pending"
        elif unpacked_cb.filter_type == ApprovalStatus.CLOSED_REGISTRATION.value:
            status_filter = ApprovalStatus.CLOSED_REGISTRATION
            title_key = "user_list_title_waitlist"
        else:  # Banned users (is_blocked=True, not approval_status)
            # Special case: Banned users use existing method
            return await AdminService.get_banned_users_list(callback, session)

        # Get paginated users
        users, total_count = await UserRepository.get_by_approval_status(
            status_filter,
            unpacked_cb.page,
            session
        )

        kb_builder = InlineKeyboardBuilder()

        if not users:
            message = Localizator.get_text(BotEntity.ADMIN, "user_list_empty")
        else:
            message = Localizator.get_text(BotEntity.ADMIN, title_key).format(count=total_count)
            message += "\n\n"

            # Build user list buttons
            for user in users:
                username_display = safe_html(user.telegram_username) if user.telegram_username else f"ID: {user.telegram_id}"
                date_str = user.registered_at.strftime("%d.%m.%Y") if user.registered_at else "N/A"

                button_text = f"{date_str} - {username_display}"

                kb_builder.button(
                    text=button_text,
                    callback_data=UserManagementCallback.create(
                        level=6,  # User detail view
                        operation=UserManagementOperation.USER_DETAIL,
                        user_id=user.id,
                        filter_type=unpacked_cb.filter_type
                    ).pack()
                )

            kb_builder.adjust(1)

            # Add batch approve button for pending/waitlist
            if status_filter in [ApprovalStatus.PENDING, ApprovalStatus.CLOSED_REGISTRATION]:
                kb_builder.row(InlineKeyboardButton(
                    text=Localizator.get_text(BotEntity.ADMIN, "batch_approve_all"),
                    callback_data=UserManagementCallback.create(
                        level=7,  # Batch approve confirmation
                        operation=UserManagementOperation.BATCH_APPROVE,
                        filter_type=unpacked_cb.filter_type
                    ).pack()
                ))

            # Pagination
            max_page = await UserRepository.get_max_page_by_approval_status(status_filter, session)
            kb_builder = await add_pagination_buttons(
                kb_builder,
                unpacked_cb,
                max_page,
                unpacked_cb.get_back_button(0)  # Back to user management menu
            )

        return message, kb_builder

    @staticmethod
    async def get_user_detail_view(
            callback: CallbackQuery,
            session: AsyncSession | Session
    ) -> tuple[str, InlineKeyboardBuilder]:
        """
        Show detailed user information with approve/reject actions.

        Shows:
        - Username/ID, Telegram ID
        - Registration date, status
        - Lifetime revenue, orders (DUMMY for now)
        - Contact button
        - Approve/Reject buttons
        """
        from repositories.user import UserRepository
        from enums.approval_status import ApprovalStatus
        from utils.html_escape import safe_html

        unpacked_cb = UserManagementCallback.unpack(callback.data)
        user = await UserRepository.get_by_id(unpacked_cb.user_id, session)

        if not user:
            return Localizator.get_text(BotEntity.ADMIN, "user_not_found"), InlineKeyboardBuilder()

        kb_builder = InlineKeyboardBuilder()

        # Build message
        username_display = safe_html(user.telegram_username) if user.telegram_username else "N/A"
        status_key = f"approval_status_{user.approval_status.value}"

        message = Localizator.get_text(BotEntity.ADMIN, "user_detail_header")
        message += "\n\n"
        message += Localizator.get_text(BotEntity.ADMIN, "user_detail_username").format(username=username_display)
        message += Localizator.get_text(BotEntity.ADMIN, "user_detail_telegram_id").format(telegram_id=user.telegram_id)
        message += Localizator.get_text(BotEntity.ADMIN, "user_detail_status").format(
            status=Localizator.get_text(BotEntity.ADMIN, status_key)
        )

        if user.registered_at:
            date_str = user.registered_at.strftime("%d.%m.%Y %H:%M")
            message += Localizator.get_text(BotEntity.ADMIN, "user_detail_registered").format(date=date_str)

        # DUMMY statistics
        message += "\n"
        message += Localizator.get_text(BotEntity.ADMIN, "user_detail_stats_header")
        message += Localizator.get_text(BotEntity.ADMIN, "user_detail_lifetime_revenue").format(
            revenue=f"{user.lifetime_revenue:.2f}",
            currency=Localizator.get_currency_symbol()
        )
        message += Localizator.get_text(BotEntity.ADMIN, "user_detail_lifetime_orders").format(orders=user.lifetime_orders)

        # Contact button (using telegram_id)
        kb_builder.row(InlineKeyboardButton(
            text=Localizator.get_text(BotEntity.ADMIN, "contact_user"),
            url=f"tg://user?id={user.telegram_id}"
        ))

        # Action buttons based on status
        if user.approval_status == ApprovalStatus.PENDING or user.approval_status == ApprovalStatus.CLOSED_REGISTRATION:
            kb_builder.button(
                text=Localizator.get_text(BotEntity.ADMIN, "approve_user_button"),
                callback_data=UserManagementCallback.create(
                    level=8,  # Approve confirmation
                    operation=UserManagementOperation.APPROVE_USER,
                    user_id=user.id,
                    filter_type=unpacked_cb.filter_type
                ).pack()
            )
            kb_builder.button(
                text=Localizator.get_text(BotEntity.ADMIN, "reject_user_button"),
                callback_data=UserManagementCallback.create(
                    level=9,  # Rejection reason input (FSM)
                    operation=UserManagementOperation.REJECT_USER,
                    user_id=user.id,
                    filter_type=unpacked_cb.filter_type
                ).pack()
            )
            kb_builder.adjust(2)

        # Back button
        kb_builder.row(InlineKeyboardButton(
            text=Localizator.get_text(BotEntity.COMMON, "back_button"),
            callback_data=UserManagementCallback.create(
                level=5,  # Back to user list
                operation=UserManagementOperation.USER_LIST,
                page=unpacked_cb.page,
                filter_type=unpacked_cb.filter_type
            ).pack()
        ))

        return message, kb_builder
