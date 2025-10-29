from aiogram import types
from aiogram.filters import BaseFilter
from aiogram.types import Message

import config
from db import get_db_session
from models.user import UserDTO
from services.user import UserService


class AdminIdFilter(BaseFilter):

    async def __call__(self, message: types.Message):
        return message.from_user.id in config.ADMIN_ID_LIST


class IsUserExistFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        async with get_db_session() as session:
            user = await UserService.get(UserDTO(telegram_id=message.from_user.id), session)

            if user is None:
                return False

            # Check if user is banned (unless admin is exempt)
            if user.is_blocked:
                is_admin = message.from_user.id in config.ADMIN_ID_LIST
                admin_exempt = is_admin and config.EXEMPT_ADMINS_FROM_BAN

                if not admin_exempt:
                    # User is banned and not exempt - block access
                    return False

            return True
