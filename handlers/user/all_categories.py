from aiogram import types, Router, F
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, CallbackQuery

from callbacks import AllCategoriesCallback
from services.cart import CartService
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from handlers.common.common import add_pagination_buttons
# from models.cartItem import CartItem
# from services.cart import CartService
from services.category import CategoryService
# from services.item import ItemService
from services.subcategory import SubcategoryService
# from services.user import UserService
from utils.custom_filters import IsUserExistFilter
from utils.localizator import Localizator, BotEntity

all_categories_router = Router()


@all_categories_router.message(F.text == Localizator.get_text(BotEntity.USER, "all_categories"),
                               IsUserExistFilter())
async def all_categories_text_message(message: types.message):
    await all_categories(message)


# async def create_category_buttons(page: int):
#     categories = await CategoryService.get_unsold(page)
#     if categories:
#         categories_builder = InlineKeyboardBuilder()
#         for category in categories:
#             categories_builder.button(text=category.name,
#                                       callback_data=create_callback_all_categories(level=1, category_id=category.id))
#         categories_builder.adjust(2)
#         return categories_builder


# async def create_subcategory_buttons(category_id: int, page: int = 0):
#     current_level = 1
#     items = await ItemService.get_unsold_subcategories_by_category(category_id, page)
#     subcategories_builder = InlineKeyboardBuilder()
#     for item in items:
#         subcategory_price = await ItemService.get_price_by_subcategory(item.subcategory_id, category_id)
#         available_quantity = await ItemService.get_available_quantity(item.subcategory_id, category_id)
#         subcategory_inline_button = create_callback_all_categories(level=current_level + 1,
#                                                                    category_id=category_id,
#                                                                    subcategory_id=item.subcategory_id,
#                                                                    price=subcategory_price)
#         subcategories_builder.button(
#             text=Localizator.get_text(BotEntity.USER, "subcategory_button").format(
#                 subcategory_name=item.subcategory.name,
#                 subcategory_price=subcategory_price,
#                 available_quantity=available_quantity,
#                 currency_sym=Localizator.get_currency_symbol()),
#             callback_data=subcategory_inline_button)
#     subcategories_builder.adjust(1)
#     return subcategories_builder


async def all_categories(message: Message | CallbackQuery):
    if isinstance(message, Message):
        category_buttons = await CategoryService.get_buttons(AllCategoriesCallback.create(0))
        if len(category_buttons.as_markup().inline_keyboard) > 0:
            await message.answer(Localizator.get_text(BotEntity.USER, "all_categories"),
                                 reply_markup=category_buttons.as_markup())
        else:
            await message.answer(Localizator.get_text(BotEntity.USER, "no_categories"))
    elif isinstance(message, CallbackQuery):
        callback = message
        unpacked_callback = AllCategoriesCallback.unpack(callback.data)
        category_buttons = await CategoryService.get_buttons(unpacked_callback)
        if len(category_buttons.as_markup().inline_keyboard) > 0:
            await callback.message.edit_text(Localizator.get_text(BotEntity.USER, "all_categories"),
                                             reply_markup=category_buttons.as_markup())
        else:
            await callback.message.edit_text(Localizator.get_text(BotEntity.USER, "no_categories"))


async def show_subcategories_in_category(callback: CallbackQuery):
    unpacked_callback = AllCategoriesCallback.unpack(callback.data)
    subcategory_buttons = await SubcategoryService.get_buttons(unpacked_callback)
    await callback.message.edit_text(Localizator.get_text(BotEntity.USER, "subcategories"),
                                     reply_markup=subcategory_buttons.as_markup())


async def select_quantity(callback: CallbackQuery):
    unpacked_callback = AllCategoriesCallback.unpack(callback.data)
    message_text, kb_builder = await SubcategoryService.get_select_quantity_buttons(unpacked_callback)
    await callback.message.edit_text(message_text, reply_markup=kb_builder.as_markup())


async def add_to_cart_confirmation(callback: CallbackQuery):
    unpacked_callback = AllCategoriesCallback.unpack(callback.data)
    message_text, kb_builder = await SubcategoryService.get_add_to_cart_buttons(unpacked_callback)
    await callback.message.edit_text(text=message_text, reply_markup=kb_builder.as_markup())


async def add_to_cart(callback: CallbackQuery):
    unpacked_callback = AllCategoriesCallback.unpack(callback.data)
    await CartService.add_to_cart(unpacked_callback, callback.from_user.id)
    await callback.message.edit_text(text=Localizator.get_text(BotEntity.USER, "item_added_to_cart"))


@all_categories_router.callback_query(AllCategoriesCallback.filter(), IsUserExistFilter())
async def navigate_categories(call: CallbackQuery, callback_data: AllCategoriesCallback):
    current_level = callback_data.level

    levels = {
        0: all_categories,
        1: show_subcategories_in_category,
        2: select_quantity,
        3: add_to_cart_confirmation,
        4: add_to_cart
    }

    current_level_function = levels[current_level]

    await current_level_function(call)
