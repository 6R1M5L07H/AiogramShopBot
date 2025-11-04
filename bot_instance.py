"""
Bot Instance Singleton

Provides a single shared Bot instance for the entire application.
This prevents creating multiple Bot instances which wastes resources (new HTTP session each time).

Usage:
    from bot_instance import get_bot
    bot = get_bot()
    await bot.send_message(chat_id, text)

Note: Bot instance is automatically initialized when first accessed.
"""

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config

_bot_instance = None


def get_bot() -> Bot:
    """
    Get the singleton Bot instance.

    Returns:
        Bot: The shared Bot instance
    """
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = Bot(
            token=config.TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
    return _bot_instance


async def close_bot():
    """
    Close the Bot instance session.

    Should be called during application shutdown.
    """
    global _bot_instance
    if _bot_instance is not None:
        await _bot_instance.session.close()
        _bot_instance = None
