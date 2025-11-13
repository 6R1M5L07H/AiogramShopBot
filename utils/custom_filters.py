from aiogram import types
from aiogram.filters import BaseFilter
from aiogram.types import Message

import config
from db import get_db_session
from models.user import UserDTO
from services.user import UserService
from utils.permission_utils import is_admin_user, is_banned_user


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
    """
    async def __call__(self, message: Message) -> bool:
        import logging
        async with get_db_session() as session:
            user = await UserService.get(UserDTO(telegram_id=message.from_user.id), session)

            if user is None:
                logging.error(
                    f"❌ USER NOT FOUND: Telegram ID {message.from_user.id} "
                    f"(username: @{message.from_user.username}) tried to access protected route but user profile doesn't exist in database. "
                    f"User needs to send /start command first to create profile. "
                    f"This may indicate: (1) User was deleted from DB, (2) DB was reset, (3) New user without /start."
                )
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
    """
    async def __call__(self, message: Message) -> bool:
        import logging
        logging.info(f"🔍 IsUserExistFilterIncludingBanned called for user {message.from_user.id}")
        async with get_db_session() as session:
            user = await UserService.get(UserDTO(telegram_id=message.from_user.id), session)

            if user is None:
                logging.error(
                    f"❌ USER NOT FOUND: Telegram ID {message.from_user.id} "
                    f"(username: @{message.from_user.username}) tried to access handler but user profile doesn't exist in database. "
                    f"User needs to send /start command first to create profile. "
                    f"This may indicate: (1) User was deleted from DB, (2) DB was reset, (3) New user without /start."
                )
                logging.info(f"🔍 IsUserExistFilterIncludingBanned result: False (user=None)")
                return False

            logging.info(f"🔍 IsUserExistFilterIncludingBanned result: True (user_id={user.id})")
            return True
