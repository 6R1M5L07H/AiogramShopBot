from aiogram import types, F, Router
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import dp, main
from config import SUPPORT_LINK
import logging

from handlers.admin.admin import admin_router
from handlers.user.all_categories import all_categories_router
from handlers.user.my_profile import my_profile_router
from services.user import UserService
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator

logging.basicConfig(level=logging.INFO)


@dp.message(Command(commands=["start", "help"]))
async def start(message: types.message):
    all_categories_button = types.KeyboardButton(text=Localizator.get_text_from_key("all_categories"))
    my_profile_button = types.KeyboardButton(text=Localizator.get_text_from_key("my_profile"))
    faq_button = types.KeyboardButton(text=Localizator.get_text_from_key("faq"))
    help_button = types.KeyboardButton(text=Localizator.get_text_from_key("help"))
    keyboard = [[all_categories_button, my_profile_button], [faq_button, help_button]]
    start_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, keyboard=keyboard)
    user_telegram_id = message.chat.id
    user_telegram_username = message.from_user.username
    is_exist = UserService.is_exist(user_telegram_id)
    if is_exist is False:
        UserService.update_receive_messages(user_telegram_id, True)
        UserService.create(user_telegram_id, user_telegram_username)
    else:
        UserService.update_username(user_telegram_id, user_telegram_username)
    await message.answer(Localizator.get_text_from_key("start_message"), reply_markup=start_markup)


@dp.message(F.text == Localizator.get_text_from_key("faq"), IsUserExistFilter())
async def faq(message: types.message):
    faq_string = Localizator.get_text_from_key("faq_string")
    await message.answer(faq_string, parse_mode='html')


@dp.message(F.text == Localizator.get_text_from_key("help"), IsUserExistFilter())
async def support(message: types.message):
    admin_keyboard_builder = InlineKeyboardBuilder()

    admin_keyboard_builder.button(text=Localizator.get_text_from_key("help_button"), url=SUPPORT_LINK)
    await message.answer(Localizator.get_text_from_key("help_string"), reply_markup=admin_keyboard_builder.as_markup())


main_router = Router()
main_router.include_router(admin_router)
main_router.include_router(my_profile_router)
main_router.include_router(all_categories_router)
dp.include_router(main_router)

if __name__ == '__main__':
    main()
