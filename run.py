import traceback
from aiogram import types, F, Router
from aiogram.filters import Command
from aiogram.types import ErrorEvent, Message, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from config import SUPPORT_LINK
import logging
from utils.logging_config import setup_logging

# Initialize centralized logging configuration
setup_logging()

from bot import dp, main, redis

# Force-silence noisy third-party loggers AFTER Aiogram initialization
# Aiogram may reset logger levels during Bot/Dispatcher init
import logging as log_module

# Aggressively silence SQL loggers
# Must be done AFTER bot import as Aiogram/SQLAlchemy reset logger levels
for logger_name in ['aiosqlite', 'sqlalchemy', 'sqlalchemy.engine', 'sqlalchemy.pool', 'sqlalchemy.orm']:
    logger = log_module.getLogger(logger_name)
    logger.setLevel(log_module.CRITICAL)  # Only CRITICAL and above (basically nothing)
    logger.propagate = False  # Don't propagate to root logger
    logger.disabled = True  # Nuclear option: completely disable the logger
    # Remove all existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    # Add NullHandler to prevent "No handler" warnings
    logger.addHandler(log_module.NullHandler())

logging.info("🔇 SQL loggers silenced (aiosqlite, sqlalchemy.*)")
from enums.bot_entity import BotEntity
from middleware.database import DBSessionMiddleware
from middleware.throttling_middleware import ThrottlingMiddleware
from models.user import UserDTO
from multibot import main as main_multibot
from handlers.user.cart import cart_router
from handlers.user.order import order_router
from handlers.admin.admin import admin_router
from handlers.admin.shipping_management import shipping_management_router
from handlers.user.all_categories import all_categories_router
from handlers.user.my_profile import my_profile_router
from handlers.user.shipping_handlers import shipping_router
from services.notification import NotificationService
from services.user import UserService
from utils.custom_filters import IsUserExistFilter, IsUserExistFilterIncludingBanned, ButtonTextFilter
from utils.localizator import Localizator

# Logging is now configured via setup_logging() above
main_router = Router()


@main_router.message(Command(commands=["start", "help"]))
async def start(message: types.Message, session: AsyncSession | Session):
    # FIXED Issue #12: Use user-specific language from Telegram
    # Falls back to bot default if user language not supported (de/en)
    user_lang = message.from_user.language_code if message.from_user.language_code in ["de", "en"] else None

    all_categories_button = types.KeyboardButton(text=Localizator.get_text(BotEntity.USER, "all_categories", lang=user_lang))
    my_profile_button = types.KeyboardButton(text=Localizator.get_text(BotEntity.USER, "my_profile", lang=user_lang))
    faq_button = types.KeyboardButton(text=Localizator.get_text(BotEntity.USER, "faq", lang=user_lang))
    help_button = types.KeyboardButton(text=Localizator.get_text(BotEntity.USER, "help", lang=user_lang))
    gpg_button = types.KeyboardButton(text=Localizator.get_text(BotEntity.USER, "gpg_menu", lang=user_lang))
    admin_menu_button = types.KeyboardButton(text=Localizator.get_text(BotEntity.ADMIN, "menu", lang=user_lang))
    cart_button = types.KeyboardButton(text=Localizator.get_text(BotEntity.USER, "cart", lang=user_lang))
    telegram_id = message.from_user.id
    await UserService.create_if_not_exist(UserDTO(
        telegram_username=message.from_user.username,
        telegram_id=telegram_id
    ), session)
    keyboard = [[all_categories_button, my_profile_button], [faq_button, help_button],
                [cart_button, gpg_button]]
    # Check admin status using centralized permission utils
    from utils.permission_utils import is_admin_user
    if is_admin_user(telegram_id):
        keyboard.append([admin_menu_button])
    start_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, keyboard=keyboard)
    await message.answer(Localizator.get_text(BotEntity.COMMON, "start_message", lang=user_lang), reply_markup=start_markup)


@main_router.message(ButtonTextFilter("faq"), IsUserExistFilterIncludingBanned())
async def faq(message: types.Message):
    logging.info("❓ FAQ BUTTON HANDLER TRIGGERED")
    await message.answer(Localizator.get_text(BotEntity.USER, "faq_string"))


@main_router.message(ButtonTextFilter("help"), IsUserExistFilterIncludingBanned())
async def support(message: types.Message):
    logging.info("❔ HELP BUTTON HANDLER TRIGGERED")
    help_text = Localizator.get_text(BotEntity.USER, "help_string")

    # Only add button if SUPPORT_LINK is configured
    if SUPPORT_LINK:
        admin_keyboard_builder = InlineKeyboardBuilder()
        admin_keyboard_builder.button(text=Localizator.get_text(BotEntity.USER, "help_button"), url=SUPPORT_LINK)
        await message.answer(help_text, reply_markup=admin_keyboard_builder.as_markup())
    else:
        await message.answer(help_text)


@main_router.message(ButtonTextFilter("gpg_menu"), IsUserExistFilterIncludingBanned())
async def show_gpg_info(message: types.Message):
    """
    Display GPG public key information from main menu.

    Shows end-to-end encryption explanation, dual-layer security,
    shop's public PGP key, fingerprint, and expiration date.
    """
    logging.info("🔐 GPG MENU BUTTON HANDLER TRIGGERED")

    # Get GPG info view from CartService (reuses existing logic)
    from services.cart import CartService
    msg, kb_builder = await CartService.get_gpg_info_view()

    # Send response with inline keyboard
    await message.answer(msg, reply_markup=kb_builder.as_markup())


@main_router.error(F.update.message.as_("message"))
async def error_handler(event: ErrorEvent, message: Message):
    # Log the error FIRST (critical for debugging!)
    logging.error(f"Unhandled exception in handler: {event.exception}", exc_info=event.exception)

    await message.answer("Oops, something went wrong!")
    traceback_str = traceback.format_exc()
    admin_notification = (
        f"Critical error caused by {event.exception}\n\n"
        f"Stack trace:\n{traceback_str}"
    )
    if len(admin_notification) > 4096:
        byte_array = bytearray(admin_notification, 'utf-8')
        admin_notification = BufferedInputFile(byte_array, "exception.txt")
    await NotificationService.send_to_admins(admin_notification, None)


throttling_middleware = ThrottlingMiddleware(redis)
users_routers = Router()
users_routers.include_routers(
    all_categories_router,
    my_profile_router,
    cart_router,
    order_router,
    shipping_router
)
users_routers.message.middleware(throttling_middleware)
users_routers.callback_query.middleware(throttling_middleware)
main_router.message.middleware(DBSessionMiddleware())
main_router.callback_query.middleware(DBSessionMiddleware())
main_router.include_router(admin_router)
main_router.include_router(shipping_management_router)
main_router.include_router(users_routers)

# Global catch-all for web_app_data (BEFORE any routing)
@dp.message(F.web_app_data)
async def catch_all_web_app_data(message: Message):
    """Log web_app_data messages without exposing sensitive data."""
    logging.info(
        f"WebApp data received: user_id={message.from_user.id}, "
        f"data_length={len(message.web_app_data.data)}, "
        f"button_text={message.web_app_data.button_text}"
    )

# Security: Update logging middleware removed to prevent PII leakage
# Previously logged message text and callback data which may contain personal information
# For debugging, use application-level logging in specific handlers instead

# Register handlers at module level (not inside if __name__ == '__main__')
# This ensures handlers are available when uvicorn worker imports this module
try:
    logging.info("🔧 [run.py] BEFORE dp.include_router - about to register handlers")
    logging.info(f"🔧 [run.py] main_router type: {type(main_router)}")
    logging.info(f"🔧 [run.py] dp type: {type(dp)}")
    dp.include_router(main_router)
    logging.info("✅ [run.py] Handlers registered with dispatcher")
except Exception as e:
    logging.error(f"❌ [run.py] FAILED to register handlers: {e}")
    import traceback
    logging.error(traceback.format_exc())

if __name__ == '__main__':
    logging.info("🔧 [run.py] Starting bot in __main__ mode")

    if config.MULTIBOT:
        main_multibot(main_router)
    else:
        main()
