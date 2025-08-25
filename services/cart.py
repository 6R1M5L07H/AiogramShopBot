from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
import config
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from callbacks import AllCategoriesCallback, CartCallback
from enums.bot_entity import BotEntity
from handlers.common.common import add_pagination_buttons
from models.buy import BuyDTO
from models.buyItem import BuyItemDTO
from models.cartItem import CartItemDTO
from models.item import ItemDTO
from models.user import UserDTO
from repositories.buy import BuyRepository
from repositories.buyItem import BuyItemRepository
from repositories.cart import CartRepository
from repositories.cartItem import CartItemRepository
from repositories.item import ItemRepository
from repositories.subcategory import SubcategoryRepository
from repositories.user import UserRepository
from repositories.reservedStock import ReservedStockRepository
from services.message import MessageService
from services.notification import NotificationService
from services.order import OrderService
from utils.localizator import Localizator

logger = logging.getLogger(__name__)


class CartService:
    
    # Cart expiration time (30 minutes)
    CART_EXPIRATION_MINUTES = 30
    
    @staticmethod
    async def validate_cart_integrity(cart_items: List[CartItemDTO], user_id: int) -> Dict[str, any]:
        """
        Comprehensive cart validation before order creation
        
        Args:
            cart_items: List of cart items to validate
            user_id: User ID for validation
            
        Returns:
            Dictionary with validation results
        """
        try:
            validation_result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'total_amount': 0.0,
                'checksum': None
            }
            
            if not cart_items:
                validation_result['valid'] = False
                validation_result['errors'].append('Cart is empty')
                return validation_result
            
            # Validate item availability and prices
            total_amount = 0.0
            availability_issues = []
            price_changes = []
            
            for cart_item in cart_items:
                # Check item availability
                available = await ReservedStockRepository.check_availability(
                    cart_item.category_id,
                    cart_item.subcategory_id,
                    cart_item.quantity
                )
                
                if not available:
                    availability_issues.append({
                        'category_id': cart_item.category_id,
                        'subcategory_id': cart_item.subcategory_id,
                        'requested_quantity': cart_item.quantity
                    })
                    continue
                
                # Validate current price
                item_dto = ItemDTO(
                    category_id=cart_item.category_id, 
                    subcategory_id=cart_item.subcategory_id
                )
                current_price = await ItemRepository.get_price(item_dto)
                
                # Check for price changes
                if abs(current_price - cart_item.price) > 0.01:  # Allow 1 cent tolerance
                    price_changes.append({
                        'category_id': cart_item.category_id,
                        'subcategory_id': cart_item.subcategory_id,
                        'old_price': cart_item.price,
                        'new_price': current_price
                    })
                
                # Use current price for total calculation
                total_amount += current_price * cart_item.quantity
                
                # Validate quantity limits
                max_quantity = getattr(config, 'MAX_CART_ITEM_QUANTITY', 100)
                if cart_item.quantity > max_quantity:
                    validation_result['errors'].append(
                        f'Quantity {cart_item.quantity} exceeds maximum {max_quantity}'
                    )
                    validation_result['valid'] = False
            
            # Handle availability issues
            if availability_issues:
                validation_result['valid'] = False
                validation_result['errors'].append('Some items are no longer available')
                validation_result['availability_issues'] = availability_issues
            
            # Handle price changes
            if price_changes:
                validation_result['warnings'].append('Some prices have changed since adding to cart')
                validation_result['price_changes'] = price_changes
            
            # Validate user permissions and limits
            user_validation = await CartService._validate_user_permissions(user_id, total_amount)
            if not user_validation['valid']:
                validation_result['valid'] = False
                validation_result['errors'].extend(user_validation['errors'])
            
            validation_result['total_amount'] = total_amount
            validation_result['checksum'] = CartService._generate_cart_checksum(cart_items, total_amount)
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating cart integrity for user {user_id}: {str(e)}")
            return {
                'valid': False,
                'errors': [f'Cart validation failed: {str(e)}'],
                'warnings': [],
                'total_amount': 0.0,
                'checksum': None
            }
    
    @staticmethod
    async def _validate_user_permissions(user_id: int, total_amount: float) -> Dict[str, any]:
        """
        Validate user permissions for cart checkout
        """
        try:
            user = await UserRepository.get_user_entity(user_id)
            if not user:
                return {
                    'valid': False,
                    'errors': ['User not found']
                }
            
            # Check if user has too many timeouts
            max_timeouts = getattr(config, 'MAX_USER_TIMEOUTS', 3)
            if user.timeout_count >= max_timeouts:
                return {
                    'valid': False,
                    'errors': [f'User has exceeded maximum timeout limit ({max_timeouts})']
                }
            
            # Check minimum order amount
            min_order_amount = getattr(config, 'MIN_ORDER_AMOUNT', 1.0)
            if total_amount < min_order_amount:
                return {
                    'valid': False,
                    'errors': [f'Order amount {total_amount} is below minimum {min_order_amount}']
                }
            
            # Check maximum order amount
            max_order_amount = getattr(config, 'MAX_ORDER_AMOUNT', 10000.0)
            if total_amount > max_order_amount:
                return {
                    'valid': False,
                    'errors': [f'Order amount {total_amount} exceeds maximum {max_order_amount}']
                }
            
            return {'valid': True, 'errors': []}
            
        except Exception as e:
            logger.error(f"Error validating user permissions for user {user_id}: {str(e)}")
            return {
                'valid': False,
                'errors': [f'User validation failed: {str(e)}']
            }
    
    @staticmethod
    def _generate_cart_checksum(cart_items: List[CartItemDTO], total_amount: float) -> str:
        """
        Generate integrity checksum for cart to prevent tampering
        """
        try:
            # Create deterministic string from cart contents
            cart_data = []
            for item in sorted(cart_items, key=lambda x: (x.category_id, x.subcategory_id)):
                cart_data.append(f"{item.category_id}:{item.subcategory_id}:{item.quantity}:{item.price}")
            
            cart_string = f"{'|'.join(cart_data)}|{total_amount:.2f}"
            
            # Generate SHA-256 checksum
            return hashlib.sha256(cart_string.encode('utf-8')).hexdigest()[:16]  # First 16 chars
            
        except Exception as e:
            logger.error(f"Error generating cart checksum: {str(e)}")
            return "invalid_checksum"
    
    @staticmethod
    async def validate_cart_expiration(user_id: int) -> bool:
        """
        Check if cart has expired and should be cleared
        """
        try:
            # In a full implementation, this would check cart last_updated timestamp
            # For now, we assume carts don't expire (legacy behavior)
            return True
            
        except Exception as e:
            logger.error(f"Error validating cart expiration for user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    async def get_cart_items(user_id: int) -> List[CartItemDTO]:
        """
        Get validated cart items for user
        """
        try:
            cart_items = await CartItemRepository.get_by_user_id(user_id, 0)
            
            # Validate cart expiration
            if not await CartService.validate_cart_expiration(user_id):
                logger.info(f"Cart expired for user {user_id}, clearing cart")
                await CartService.clear_cart(user_id)
                return []
            
            return cart_items
            
        except Exception as e:
            logger.error(f"Error getting cart items for user {user_id}: {str(e)}")
            return []
    
    @staticmethod
    async def clear_cart(user_id: int) -> None:
        """
        Clear user's cart
        """
        try:
            cart = await CartRepository.get_or_create(user_id)
            await CartItemRepository.clear_cart(cart.id)
            logger.info(f"Cart cleared for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error clearing cart for user {user_id}: {str(e)}")

    @staticmethod
    async def add_to_cart(callback: CallbackQuery):
        unpacked_cb = AllCategoriesCallback.unpack(callback.data)
        user = await UserRepository.get_by_tgid(UserDTO(telegram_id=callback.from_user.id))
        cart = await CartRepository.get_or_create(user.id)
        cart_item = CartItemDTO(
            category_id=unpacked_cb.category_id,
            subcategory_id=unpacked_cb.subcategory_id,
            quantity=unpacked_cb.quantity,
            cart_id=cart.id
        )
        await CartRepository.add_to_cart(cart_item, cart)

    @staticmethod
    async def create_buttons(message: Message | CallbackQuery):
        user = await UserRepository.get_by_tgid(UserDTO(telegram_id=message.from_user.id))
        page = 0 if isinstance(message, Message) else CartCallback.unpack(message.data).page
        cart_items = await CartItemRepository.get_by_user_id(user.id, 0)
        kb_builder = InlineKeyboardBuilder()
        for cart_item in cart_items:
            item_dto = ItemDTO(category_id=cart_item.category_id, subcategory_id=cart_item.subcategory_id)
            price = await ItemRepository.get_price(item_dto)
            subcategory = await SubcategoryRepository.get_by_id(cart_item.subcategory_id)
            kb_builder.button(text=Localizator.get_text(BotEntity.USER, "cart_item_button").format(
                subcategory_name=subcategory.name,
                qty=cart_item.quantity,
                total_price=cart_item.quantity * price,
                currency_sym=Localizator.get_currency_symbol()),
                callback_data=CartCallback.create(1, page, cart_item_id=cart_item.id))
        if len(kb_builder.as_markup().inline_keyboard) > 0:
            cart = await CartRepository.get_or_create(user.id)
            unpacked_cb = CartCallback.create(0) if isinstance(message, Message) else CartCallback.unpack(message.data)
            kb_builder.button(text=Localizator.get_text(BotEntity.USER, "checkout"),
                              callback_data=CartCallback.create(2, page, cart.id))
            kb_builder.adjust(1)
            kb_builder = await add_pagination_buttons(kb_builder, unpacked_cb,
                                                      CartItemRepository.get_maximum_page(user.id),
                                                      None)
            return Localizator.get_text(BotEntity.USER, "cart"), kb_builder
        else:
            return Localizator.get_text(BotEntity.USER, "no_cart_items"), kb_builder

    @staticmethod
    async def delete_cart_item(callback: CallbackQuery):
        unpacked_cb = CartCallback.unpack(callback.data)
        cart_item_id = unpacked_cb.cart_item_id
        kb_builder = InlineKeyboardBuilder()
        if unpacked_cb.confirmation:
            await CartItemRepository.remove_from_cart(cart_item_id)
            return Localizator.get_text(BotEntity.USER, "delete_cart_item_confirmation_text"), kb_builder
        else:
            kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "confirm"),
                              callback_data=CartCallback.create(1, cart_item_id=cart_item_id,
                                                                confirmation=True))
            kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "cancel"),
                              callback_data=CartCallback.create(0))
            return Localizator.get_text(BotEntity.USER, "delete_cart_item_confirmation"), kb_builder

    @staticmethod
    async def __create_checkout_msg(cart_items: list[CartItemDTO]) -> str:
        message_text = Localizator.get_text(BotEntity.USER, "cart_confirm_checkout_process")
        message_text += "<b>\n\n"
        cart_grand_total = 0.0

        for cart_item in cart_items:
            item_dto = ItemDTO(category_id=cart_item.category_id, subcategory_id=cart_item.subcategory_id)
            price = await ItemRepository.get_price(item_dto)
            subcategory = await SubcategoryRepository.get_by_id(cart_item.subcategory_id)
            line_item_total = price * cart_item.quantity
            cart_line_item = Localizator.get_text(BotEntity.USER, "cart_item_button").format(
                subcategory_name=subcategory.name, qty=cart_item.quantity,
                total_price=line_item_total, currency_sym=Localizator.get_currency_symbol()
            )
            cart_grand_total += line_item_total
            message_text += cart_line_item
        message_text += Localizator.get_text(BotEntity.USER, "cart_grand_total_string").format(
            cart_grand_total=cart_grand_total, currency_sym=Localizator.get_currency_symbol())
        message_text += "</b>"
        return message_text

    @staticmethod
    async def checkout_processing(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        user = await UserRepository.get_by_tgid(UserDTO(telegram_id=callback.from_user.id))
        cart_items = await CartItemRepository.get_all_by_user_id(user.id)
        message_text = await CartService.__create_checkout_msg(cart_items)
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "confirm"),
                          callback_data=CartCallback.create(3,
                                                            confirmation=True))
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "cancel"),
                          callback_data=CartCallback.create(0))
        return message_text, kb_builder

    @staticmethod
    async def buy_processing(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        unpacked_cb = CartCallback.unpack(callback.data)
        user = await UserRepository.get_by_tgid(UserDTO(telegram_id=callback.from_user.id))
        cart_items = await CartItemRepository.get_all_by_user_id(user.id)
        cart_total = 0.0
        out_of_stock = []
        for cart_item in cart_items:
            item_dto = ItemDTO(category_id=cart_item.category_id, subcategory_id=cart_item.subcategory_id)
            price = await ItemRepository.get_price(item_dto)
            cart_total += price * cart_item.quantity
            is_in_stock = await ItemRepository.get_available_qty(item_dto) >= cart_item.quantity
            if is_in_stock is False:
                out_of_stock.append(cart_item)
        is_enough_money = (user.top_up_amount - user.consume_records) >= cart_total
        kb_builder = InlineKeyboardBuilder()
        if unpacked_cb.confirmation and len(out_of_stock) == 0 and is_enough_money:
            sold_items = []
            msg = ""
            for cart_item in cart_items:
                price = await ItemRepository.get_price(ItemDTO(category_id=cart_item.category_id,
                                                               subcategory_id=cart_item.subcategory_id))
                purchased_items = await ItemRepository.get_purchased_items(cart_item.category_id,
                                                                           cart_item.subcategory_id, cart_item.quantity)
                buy_dto = BuyDTO(buyer_id=user.id, quantity=cart_item.quantity, total_price=cart_item.quantity * price)
                buy_id = await BuyRepository.create(buy_dto)
                buy_item_dto_list = [BuyItemDTO(item_id=item.id, buy_id=buy_id) for item in purchased_items]
                await BuyItemRepository.create_many(buy_item_dto_list)
                for item in purchased_items:
                    item.is_sold = True
                await ItemRepository.update(purchased_items)
                await CartItemRepository.remove_from_cart(cart_item.id)
                sold_items.append(cart_item)
                msg += MessageService.create_message_with_bought_items(purchased_items)
                user.consume_records = user.consume_records + cart_total
                await UserRepository.update(user)
            await NotificationService.new_buy(sold_items, user)
            return msg, kb_builder
        elif unpacked_cb.confirmation is False:
            kb_builder.row(unpacked_cb.get_back_button(0))
            return Localizator.get_text(BotEntity.USER, "purchase_confirmation_declined"), kb_builder
        elif is_enough_money is False:
            kb_builder.row(unpacked_cb.get_back_button(0))
            return Localizator.get_text(BotEntity.USER, "insufficient_funds"), kb_builder
        elif len(out_of_stock) > 0:
            kb_builder.row(unpacked_cb.get_back_button(0))
            msg = Localizator.get_text(BotEntity.USER, "out_of_stock")
            for item in out_of_stock:
                subcategory = await SubcategoryRepository.get_by_id(item.subcategory_id)
                msg += subcategory.name + "\n"
            return msg, kb_builder

    @staticmethod
    async def get_cart_items(user_id: int) -> list[CartItemDTO]:
        """Get all cart items for a user"""
        return await CartItemRepository.get_all_by_user_id(user_id)

    @staticmethod
    async def clear_cart(user_id: int) -> None:
        """Clear all items from user's cart"""
        cart_items = await CartItemRepository.get_all_by_user_id(user_id)
        for cart_item in cart_items:
            await CartItemRepository.remove_from_cart(cart_item.id)

    @staticmethod
    async def currency_selection_processing(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        """Show currency selection for order creation"""
        user = await UserRepository.get_by_tgid(UserDTO(telegram_id=callback.from_user.id))
        
        # Check if user already has an active order
        order_details = await OrderService.get_order_details_for_user(user.id)
        if order_details['has_order']:
            kb_builder = InlineKeyboardBuilder()
            kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "back"),
                              callback_data=CartCallback.create(0))
            return Localizator.get_text(BotEntity.USER, "user_has_active_order"), kb_builder

        cart_items = await CartItemRepository.get_all_by_user_id(user.id)
        if not cart_items:
            kb_builder = InlineKeyboardBuilder()
            return Localizator.get_text(BotEntity.USER, "no_cart_items"), kb_builder

        # Show currency selection
        kb_builder = InlineKeyboardBuilder()
        currencies = ['BTC', 'ETH', 'LTC', 'SOL']
        for currency in currencies:
            kb_builder.button(text=currency, 
                              callback_data=CartCallback.create(4, currency_code=currency))
        
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "cancel"),
                          callback_data=CartCallback.create(0))
        kb_builder.adjust(2, 1)

        message_text = await CartService.__create_checkout_msg(cart_items)
        message_text += "\n\n" + Localizator.get_text(BotEntity.USER, "currency_selection_prompt")
        
        return message_text, kb_builder

    @staticmethod
    async def create_order_processing(callback: CallbackQuery) -> tuple[str, InlineKeyboardBuilder]:
        """Create order with selected currency"""
        unpacked_cb = CartCallback.unpack(callback.data)
        user = await UserRepository.get_by_tgid(UserDTO(telegram_id=callback.from_user.id))
        
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=Localizator.get_text(BotEntity.COMMON, "back"),
                          callback_data=CartCallback.create(0))

        try:
            currency = unpacked_cb.currency_code
            order = await OrderService.create_order_from_cart(user.id, currency)
            
            message_text = Localizator.get_text(BotEntity.USER, "order_created_success").format(
                order_id=order.id,
                amount=order.total_amount,
                currency=order.currency,
                address=order.payment_address,
                timeout_minutes=getattr(config, 'ORDER_TIMEOUT_MINUTES', 30)
            )
            
            return message_text, kb_builder
            
        except ValueError as e:
            error_message = Localizator.get_text(BotEntity.USER, "order_creation_failed").format(
                error=str(e)
            )
            return error_message, kb_builder
        except Exception as e:
            error_message = Localizator.get_text(BotEntity.USER, "order_creation_error")
            return error_message, kb_builder
