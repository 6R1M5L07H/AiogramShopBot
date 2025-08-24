from datetime import datetime, timedelta
from typing import Dict, Any

from models.order import OrderDTO, OrderStatus
from models.orderItem import OrderItemDTO
from models.reservedStock import ReservedStockDTO
from models.cart import CartItemDTO
from models.user import UserDTO
from repositories.order import OrderRepository
from repositories.orderItem import OrderItemRepository
from repositories.reservedStock import ReservedStockRepository
from repositories.item import ItemRepository
from repositories.user import UserRepository
from utils.CryptoAddressGenerator import CryptoAddressGenerator
from services.notification import NotificationService
import config


class OrderService:
    @staticmethod
    async def create_order_from_cart(user_id: int, currency: str) -> OrderDTO:
        """
        Create order from user's cart with temporary stock reservation
        """
        # Check if user already has an active order
        existing_order = await OrderRepository.get_by_user_id(user_id)
        if existing_order and existing_order.status in [OrderStatus.CREATED.value, OrderStatus.PAID.value]:
            raise ValueError("User already has an active order")
        
        # Get cart items (assuming CartService.get_cart_items exists)
        from services.cart import CartService
        cart_items = await CartService.get_cart_items(user_id)
        
        if not cart_items:
            raise ValueError("Cart is empty")
        
        # Check stock availability and calculate total
        stock_check_result = await OrderService.reserve_stock_for_cart(user_id, cart_items)
        if not stock_check_result['success']:
            raise ValueError(f"Insufficient stock: {stock_check_result['message']}")
        
        # Generate one-time crypto address
        crypto_gen = CryptoAddressGenerator()
        address_data = crypto_gen.generate_one_time_address(currency, user_id)
        
        # Calculate order timeout
        timeout_minutes = getattr(config, 'ORDER_TIMEOUT_MINUTES', 30)
        expires_at = datetime.now() + timedelta(minutes=timeout_minutes)
        
        # Create order
        order_dto = OrderDTO(
            user_id=user_id,
            status=OrderStatus.CREATED.value,
            total_amount=stock_check_result['total_amount'],
            currency=currency,
            payment_address=address_data['address'],
            private_key=address_data['private_key'],
            expires_at=expires_at,
            created_at=datetime.now()
        )
        
        order_id = await OrderRepository.create(order_dto)
        order_dto.id = order_id
        
        # Create order items
        order_items = []
        for cart_item in cart_items:
            order_item = OrderItemDTO(
                order_id=order_id,
                item_id=cart_item.item_id,
                price_at_purchase=cart_item.price,
                created_at=datetime.now()
            )
            order_items.append(order_item)
        
        await OrderItemRepository.create_many(order_items)
        
        # Create stock reservations
        reservations = []
        for cart_item in cart_items:
            reservation = ReservedStockDTO(
                order_id=order_id,
                category_id=cart_item.category_id,
                subcategory_id=cart_item.subcategory_id,
                quantity=cart_item.quantity,
                reserved_at=datetime.now(),
                expires_at=expires_at
            )
            reservations.append(reservation)
        
        await ReservedStockRepository.create_reservations(reservations)
        
        # Clear cart after order creation
        await CartService.clear_cart(user_id)
        
        # Send notifications
        user_dto = await UserRepository.get_user_entity(user_id)
        await NotificationService.order_created(order_dto, user_dto)
        
        return order_dto
    
    @staticmethod
    async def reserve_stock_for_cart(user_id: int, cart_items: list[CartItemDTO]) -> Dict[str, Any]:
        """
        Check stock availability and calculate total amount for cart items
        """
        total_amount = 0.0
        insufficient_items = []
        
        for cart_item in cart_items:
            # Check availability with existing reservations
            available = await ReservedStockRepository.check_availability(
                cart_item.category_id,
                cart_item.subcategory_id,
                cart_item.quantity
            )
            
            if not available:
                insufficient_items.append({
                    'category_id': cart_item.category_id,
                    'subcategory_id': cart_item.subcategory_id,
                    'requested': cart_item.quantity
                })
            else:
                total_amount += cart_item.price * cart_item.quantity
        
        if insufficient_items:
            return {
                'success': False,
                'message': f"Insufficient stock for {len(insufficient_items)} items",
                'insufficient_items': insufficient_items
            }
        
        return {
            'success': True,
            'total_amount': total_amount,
            'message': 'Stock available'
        }
    
    @staticmethod
    async def cancel_order(order_id: int, user_initiated: bool = True) -> None:
        """
        Cancel order and release reserved stock
        """
        order = await OrderRepository.get_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        
        if order.status not in [OrderStatus.CREATED.value]:
            raise ValueError("Order cannot be cancelled")
        
        # Update order status
        await OrderRepository.update_status(order_id, OrderStatus.CANCELLED)
        
        # Release reserved stock
        await ReservedStockRepository.release_by_order_id(order_id)
        
        # Increment timeout count if not user initiated
        if not user_initiated:
            await UserRepository.increment_timeout_count(order.user_id)
        
        # Send notification
        user_dto = await UserRepository.get_user_entity(order.user_id)
        await NotificationService.order_cancelled(order, user_dto, not user_initiated)
    
    @staticmethod
    async def confirm_payment(order_id: int) -> None:
        """
        Confirm payment received and mark items as sold
        """
        order = await OrderRepository.get_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        
        if order.status != OrderStatus.CREATED.value:
            raise ValueError("Order is not in created status")
        
        # Update order status to paid
        await OrderRepository.update_payment_confirmation(order_id, datetime.now())
        
        # Mark items as sold
        await ItemRepository.mark_items_as_sold_from_order(order_id)
        
        # Release reservations (items are now sold)
        await ReservedStockRepository.release_by_order_id(order_id)
        
        # Send notifications
        user_dto = await UserRepository.get_user_entity(order.user_id)
        await NotificationService.payment_received(order, user_dto, order.private_key)
    
    @staticmethod
    async def expire_order(order_id: int) -> None:
        """
        Expire order due to timeout
        """
        order = await OrderRepository.get_by_id(order_id)
        if not order:
            return  # Order already processed or doesn't exist
        
        if order.status != OrderStatus.CREATED.value:
            return  # Order already processed
        
        # Update order status
        await OrderRepository.update_status(order_id, OrderStatus.EXPIRED)
        
        # Release reserved stock
        await ReservedStockRepository.release_by_order_id(order_id)
        
        # Increment user timeout count
        await UserRepository.increment_timeout_count(order.user_id)
        
        # Send notification
        user_dto = await UserRepository.get_user_entity(order.user_id)
        await NotificationService.order_expired(order, user_dto)
    
    @staticmethod
    async def ship_order(order_id: int) -> None:
        """
        Mark order as shipped
        """
        order = await OrderRepository.get_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        
        if order.status != OrderStatus.PAID.value:
            raise ValueError("Order is not paid")
        
        # Update order status
        await OrderRepository.update_shipped(order_id, datetime.now())
        
        # Send notification
        user_dto = await UserRepository.get_user_entity(order.user_id)
        await NotificationService.order_shipped(order, user_dto)
    
    @staticmethod
    async def get_order_details_for_user(user_id: int) -> Dict[str, Any]:
        """
        Get order details and status for user
        """
        order = await OrderRepository.get_by_user_id(user_id)
        if not order:
            return {'has_order': False}
        
        order_items = await OrderItemRepository.get_by_order_id(order.id)
        
        return {
            'has_order': True,
            'order': order,
            'items': order_items,
            'time_remaining': (order.expires_at - datetime.now()).total_seconds() if order.status == OrderStatus.CREATED.value else 0
        }