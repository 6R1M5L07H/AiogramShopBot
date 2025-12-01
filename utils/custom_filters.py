from aiogram import types
from aiogram.filters import BaseFilter
from aiogram.types import Message

import config
from db import get_db_session
from enums.bot_entity import BotEntity
from models.user import UserDTO
from services.user import UserService
from utils.localizator import Localizator
from utils.permission_utils import is_admin_user, is_banned_user


class ButtonTextFilter(BaseFilter):
    """
    Filter that matches button text at runtime instead of import time.

    Solves the issue where F.text == Localizator.get_text(...) is evaluated
    at import time, which can cause mismatches if BOT_LANGUAGE changes or
    localization is initialized differently between import and runtime.

    Usage:
        @router.message(ButtonTextFilter("all_categories"), IsUserExistFilter())
        async def handler(message: Message, session: AsyncSession | Session):
            ...
    """

    def __init__(self, localization_key: str, entity: BotEntity = BotEntity.USER):
        self.localization_key = localization_key
        self.entity = entity

    async def __call__(self, message: Message) -> bool:
        # Evaluate text match at runtime, not import time
        expected_text = Localizator.get_text(self.entity, self.localization_key)
        return message.text == expected_text


class AdminIdFilter(BaseFilter):
    """
    Filter that checks if user is an admin using secure hash-based verification.

    Security:
    - Verifies admin status by hashing the user's Telegram ID and comparing with stored hashes
    - Prevents admin identification if environment variables are compromised
    - Backward compatible with legacy ADMIN_ID_LIST (with deprecation warning)
    """

    async def __call__(self, message: types.Message):
        return is_admin_user(message.from_user.id)


class IsUserExistFilter(BaseFilter):
    """
    Filter that checks if user exists and is not banned.
    Blocks banned users from accessing protected routes (shopping, cart, etc.).
    Admins with EXEMPT_ADMINS_FROM_BAN=true can bypass ban.

    If user is banned, shows informative message with unban instructions.
    If user doesn't exist, auto-creates profile with welcome message for seamless UX.
    """
    async def __call__(self, message: Message) -> bool:
        import logging
        async with get_db_session() as session:
            user = await UserService.get(UserDTO(telegram_id=message.from_user.id), session)

            if user is None:
                logging.info(
                    f"🆕 AUTO-CREATING USER: Telegram ID {message.from_user.id} "
                    f"(username: @{message.from_user.username}) accessed handler without profile. "
                    f"Creating profile automatically for seamless UX."
                )

                # Auto-create user profile for seamless UX
                await UserService.create_if_not_exist(
                    UserDTO(
                        telegram_username=message.from_user.username,
                        telegram_id=message.from_user.id
                    ),
                    session
                )

                # Show friendly welcome message
                from utils.localizator import Localizator
                from enums.bot_entity import BotEntity
                await message.answer(Localizator.get_text(BotEntity.COMMON, "welcome_auto_created"))

                # Re-fetch user to continue processing
                user = await UserService.get(UserDTO(telegram_id=message.from_user.id), session)

                if user is None:
                    # Unlikely - but handle gracefully
                    logging.error(f"❌ Failed to create user profile for {message.from_user.id}")
                    return False

            # Check if user is banned using centralized function
            if await is_banned_user(message.from_user.id, session):
                # User is banned - show informative message
                from utils.localizator import Localizator
                from enums.bot_entity import BotEntity
                from repositories.user_strike import UserStrikeRepository

                # Get actual strike count from DB
                strikes = await UserStrikeRepository.get_by_user_id(user.id, session)
                strike_count = len(strikes)

                ban_message = Localizator.get_text(BotEntity.USER, "account_banned_access_denied").format(
                    strike_count=strike_count,
                    unban_amount=config.UNBAN_TOP_UP_AMOUNT,
                    currency_sym=Localizator.get_currency_symbol()
                )

                await message.answer(ban_message)
                return False

            return True


class IsUserExistFilterIncludingBanned(BaseFilter):
    """
    Filter that checks if user exists, but allows banned users.
    Used for protected routes that banned users should still access:
    - My Profile (for wallet top-up)
    - Support
    - FAQ/Terms

    If user doesn't exist, auto-creates profile with welcome message for seamless UX.
    """
    async def __call__(self, message: Message) -> bool:
        import logging
        logging.info(f"🔍 IsUserExistFilterIncludingBanned called for user {message.from_user.id}")
        async with get_db_session() as session:
            user = await UserService.get(UserDTO(telegram_id=message.from_user.id), session)

            if user is None:
                logging.info(
                    f"🆕 AUTO-CREATING USER: Telegram ID {message.from_user.id} "
                    f"(username: @{message.from_user.username}) accessed handler without profile. "
                    f"Creating profile automatically for seamless UX."
                )

                # Auto-create user profile for seamless UX
                await UserService.create_if_not_exist(
                    UserDTO(
                        telegram_username=message.from_user.username,
                        telegram_id=message.from_user.id
                    ),
                    session
                )

                # Show friendly welcome message
                from utils.localizator import Localizator
                from enums.bot_entity import BotEntity
                await message.answer(Localizator.get_text(BotEntity.COMMON, "welcome_auto_created"))

                # Re-fetch user to continue processing
                user = await UserService.get(UserDTO(telegram_id=message.from_user.id), session)

                if user is None:
                    # Unlikely - but handle gracefully
                    logging.error(f"❌ Failed to create user profile for {message.from_user.id}")
                    logging.info(f"🔍 IsUserExistFilterIncludingBanned result: False (user=None after create)")
                    return False

                logging.info(f"🔍 IsUserExistFilterIncludingBanned result: True (user_id={user.id}, auto-created)")
                return True

            logging.info(f"🔍 IsUserExistFilterIncludingBanned result: True (user_id={user.id})")
            return True
