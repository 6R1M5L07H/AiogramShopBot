import logging
from aiogram import types, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import config
from config import ADMIN_ID_LIST, TOKEN
from enums.bot_entity import BotEntity
from enums.cryptocurrency import Cryptocurrency
from models.buy import RefundDTO
from models.cartItem import CartItemDTO
from models.item import ItemDTO
from models.user import UserDTO
from models.order import OrderDTO
from repositories.category import CategoryRepository
from repositories.item import ItemRepository
from repositories.subcategory import SubcategoryRepository
from utils.localizator import Localizator


class NotificationService:

    @staticmethod
    async def make_user_button(username: str | None) -> InlineKeyboardMarkup:
        user_button_builder = InlineKeyboardBuilder()
        if username:
            user_button_inline = types.InlineKeyboardButton(text=username, url=f"https://t.me/{username}")
            user_button_builder.add(user_button_inline)
        return user_button_builder.as_markup()

    @staticmethod
    async def send_to_admins(message: str, reply_markup: types.InlineKeyboardMarkup):
        bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        for admin_id in ADMIN_ID_LIST:
            try:
                await bot.send_message(admin_id, f"<b>{message}</b>", reply_markup=reply_markup)
            except Exception as e:
                logging.error(e)

    @staticmethod
    async def new_deposit(deposit_amount: float, cryptocurrency: Cryptocurrency, fiat_amount: float, user_dto: UserDTO):
        deposit_amount_fiat = round(fiat_amount, 2)
        user_button = await NotificationService.make_user_button(user_dto.telegram_username)
        if user_dto.telegram_username:
            message = Localizator.get_text(BotEntity.ADMIN, "notification_new_deposit_username").format(
                username=user_dto.telegram_username,
                deposit_amount_fiat=deposit_amount_fiat,
                currency_sym=Localizator.get_currency_symbol()
            )
        else:
            message = Localizator.get_text(BotEntity.ADMIN, "notification_new_deposit_id").format(
                telegram_id=user_dto.telegram_id,
                deposit_amount_fiat=deposit_amount_fiat,
                currency_sym=Localizator.get_currency_symbol()
            )
        addr = getattr(user_dto, cryptocurrency.get_address_field())
        message += Localizator.get_text(BotEntity.ADMIN, "notification_crypto_deposit").format(
            value=deposit_amount,
            crypto_name=cryptocurrency.value.replace('_', ' '),
            crypto_address=addr
        )
        message += Localizator.get_text(BotEntity.ADMIN, "notification_seed").format(seed=user_dto.seed)
        await NotificationService.send_to_admins(message, user_button)

    @staticmethod
    async def new_buy(sold_items: list[CartItemDTO], user: UserDTO):
        user_button = await NotificationService.make_user_button(user.telegram_username)
        cart_grand_total = 0.0
        message = ""
        for item in sold_items:
            price = await ItemRepository.get_price(ItemDTO(subcategory_id=item.subcategory_id,
                                                           category_id=item.category_id))
            category = await CategoryRepository.get_by_id(item.category_id)
            subcategory = await SubcategoryRepository.get_by_id(item.subcategory_id)
            cart_item_total = price * item.quantity
            cart_grand_total += cart_item_total
            if user.telegram_username:
                message += Localizator.get_text(BotEntity.ADMIN, "notification_purchase_with_tgid").format(
                    username=user.telegram_username,
                    total_price=cart_item_total,
                    quantity=item.quantity,
                    category_name=category.name,
                    subcategory_name=subcategory.name,
                    currency_sym=Localizator.get_currency_symbol()) + "\n"
            else:
                message += Localizator.get_text(BotEntity.ADMIN, "notification_purchase_with_username").format(
                    telegram_id=user.telegram_id,
                    total_price=cart_item_total,
                    quantity=item.quantity,
                    category_name=category.name,
                    subcategory_name=subcategory.name,
                    currency_sym=Localizator.get_currency_symbol()) + "\n"
        message += Localizator.get_text(BotEntity.USER, "cart_grand_total_string").format(
            cart_grand_total=cart_grand_total, currency_sym=Localizator.get_currency_symbol())
        await NotificationService.send_to_admins(message, user_button)

    @staticmethod
    async def refund(refund_data: RefundDTO):
        user_notification = Localizator.get_text(BotEntity.USER, "refund_notification").format(
            total_price=refund_data.total_price,
            quantity=refund_data.quantity,
            subcategory=refund_data.subcategory_name,
            currency_sym=Localizator.get_currency_symbol())
        try:
            bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            await bot.send_message(refund_data.telegram_id, text=user_notification)
        except Exception as _:
            pass

    @staticmethod
    async def order_created(order: OrderDTO, user: UserDTO) -> None:
        """Send notification when order is created"""
        bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        
        # User notification with payment instructions
        timeout_minutes = getattr(config, 'ORDER_TIMEOUT_MINUTES', 30)
        user_message = Localizator.get_text(BotEntity.USER, "order_created_instructions").format(
            order_id=order.id,
            amount=order.total_amount,
            currency=order.currency,
            address=order.payment_address,
            timeout_minutes=timeout_minutes
        )
        
        try:
            await bot.send_message(user.telegram_id, user_message)
        except Exception as e:
            logging.error(f"Failed to send order created notification to user {user.telegram_id}: {e}")
        
        # Admin notification
        user_button = await NotificationService.make_user_button(user.telegram_username)
        if user.telegram_username:
            admin_message = f"New Order #{order.id}\nUser: @{user.telegram_username}\nAmount: {order.total_amount} {order.currency}\nPayment Address: {order.payment_address}"
        else:
            admin_message = f"New Order #{order.id}\nUser ID: {user.telegram_id}\nAmount: {order.total_amount} {order.currency}\nPayment Address: {order.payment_address}"
        
        await NotificationService.send_to_admins(admin_message, user_button)

    @staticmethod
    async def payment_received(order: OrderDTO, user: UserDTO, private_key: str) -> None:
        """Send notification when payment is received"""
        bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        
        # User notification
        user_message = Localizator.get_text(BotEntity.USER, "payment_received_notification").format(
            order_id=order.id,
            amount=order.total_amount,
            currency=order.currency
        )
        
        try:
            await bot.send_message(user.telegram_id, user_message)
        except Exception as e:
            logging.error(f"Failed to send payment received notification to user {user.telegram_id}: {e}")
        
        # Admin notification with private key
        user_button = await NotificationService.make_user_button(user.telegram_username)
        if user.telegram_username:
            admin_message = f"Payment Received for Order #{order.id}\nUser: @{user.telegram_username}\nAmount: {order.total_amount} {order.currency}\nPrivate Key: {private_key}\n\nOrder ready for shipment!"
        else:
            admin_message = f"Payment Received for Order #{order.id}\nUser ID: {user.telegram_id}\nAmount: {order.total_amount} {order.currency}\nPrivate Key: {private_key}\n\nOrder ready for shipment!"
        
        await NotificationService.send_to_admins(admin_message, user_button)

    @staticmethod
    async def order_expired(order: OrderDTO, user: UserDTO) -> None:
        """Send notification when order expires"""
        bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        
        # User notification
        user_message = Localizator.get_text(BotEntity.USER, "order_expired_notification").format(
            order_id=order.id
        )
        
        try:
            await bot.send_message(user.telegram_id, user_message)
        except Exception as e:
            logging.error(f"Failed to send order expired notification to user {user.telegram_id}: {e}")

    @staticmethod
    async def order_cancelled(order: OrderDTO, user: UserDTO, admin_initiated: bool = False) -> None:
        """Send notification when order is cancelled"""
        bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        
        # User notification
        if admin_initiated:
            user_message = Localizator.get_text(BotEntity.USER, "order_cancelled_admin").format(
                order_id=order.id
            )
        else:
            user_message = Localizator.get_text(BotEntity.USER, "order_cancelled_user").format(
                order_id=order.id
            )
        
        try:
            await bot.send_message(user.telegram_id, user_message)
        except Exception as e:
            logging.error(f"Failed to send order cancelled notification to user {user.telegram_id}: {e}")

    @staticmethod
    async def order_shipped(order: OrderDTO, user: UserDTO) -> None:
        """Send notification when order is shipped"""
        bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        
        # User notification
        user_message = Localizator.get_text(BotEntity.USER, "order_shipped_notification").format(
            order_id=order.id
        )
        
        try:
            await bot.send_message(user.telegram_id, user_message)
        except Exception as e:
            logging.error(f"Failed to send order shipped notification to user {user.telegram_id}: {e}")
        
        # Admin confirmation
        user_button = await NotificationService.make_user_button(user.telegram_username)
        if user.telegram_username:
            admin_message = f"Order #{order.id} marked as shipped\nUser: @{user.telegram_username}"
        else:
            admin_message = f"Order #{order.id} marked as shipped\nUser ID: {user.telegram_id}"
        
        await NotificationService.send_to_admins(admin_message, user_button)
