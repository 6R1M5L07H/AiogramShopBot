from datetime import datetime, timedelta
from typing import Dict, Any
import logging

from models.order import OrderDTO, OrderStatus
from models.orderItem import OrderItemDTO
from models.reservedStock import ReservedStockDTO
from models.cartItem import CartItemDTO
from models.user import UserDTO
from repositories.order import OrderRepository
from repositories.orderItem import OrderItemRepository
from repositories.reservedStock import ReservedStockRepository
from repositories.item import ItemRepository
from repositories.user import UserRepository
from utils.CryptoAddressGenerator import CryptoAddressGenerator
from utils.transaction_manager import TransactionManager
from utils.order_state_machine import validate_order_transition
from services.notification import NotificationService
import config

logger = logging.getLogger(__name__)


class OrderService:
    @staticmethod
    @TransactionManager.with_retry(max_retries=3)
    async def create_order_from_cart(user_id: int, currency: str) -> OrderDTO:
        """
        Create order from user's cart with atomic transaction and stock reservation
        """
        try:
            async with TransactionManager.atomic_transaction() as session:
                # Check if user already has an active order
                existing_order = await OrderRepository.get_by_user_id(user_id)
                if existing_order and existing_order.status in [OrderStatus.CREATED.value, OrderStatus.PAID.value]:
                    raise ValueError("User already has an active order")
                
                # Get and validate cart items
                from services.cart import CartService
                cart_items = await CartService.get_cart_items(user_id)
                
                if not cart_items:
                    raise ValueError("Cart is empty")
                
                # Comprehensive cart validation
                cart_validation = await CartService.validate_cart_integrity(cart_items, user_id)
                if not cart_validation['valid']:
                    error_messages = '; '.join(cart_validation['errors'])
                    raise ValueError(f"Cart validation failed: {error_messages}")
                
                # Log any warnings
                if cart_validation['warnings']:
                    warning_messages = '; '.join(cart_validation['warnings'])
                    logger.warning(f"Cart validation warnings for user {user_id}: {warning_messages}")
                
                # Use validated total amount
                total_amount = cart_validation['total_amount']
                
                # Calculate order timeout
                timeout_minutes = getattr(config, 'ORDER_TIMEOUT_MINUTES', 30)
                expires_at = datetime.now() + timedelta(minutes=timeout_minutes)
                
                # Stock reservation operations - total_amount already calculated from cart validation
                reservation_operations = []
                
                async def create_order_operation(session):
                    # Generate one-time crypto address
                    crypto_gen = CryptoAddressGenerator()
                    address_data = crypto_gen.generate_one_time_address(currency, user_id)
                    
                    # Create order with encrypted private key
                    order_dto = OrderDTO(
                        user_id=user_id,
                        status=OrderStatus.CREATED.value,  
                        total_amount=total_amount,
                        currency=currency,
                        payment_address=address_data['address'],
                        expires_at=expires_at,
                        created_at=datetime.now()
                    )
                    
                    order_id = await OrderRepository.create_with_encrypted_key(order_dto, address_data['private_key'])
                    order_dto.id = order_id
                    return order_dto, order_id
                
                async def create_order_items_operation(session, order_id):
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
                    return order_items
                
                async def reserve_stock_operation(session, order_id):
                    # Reserve stock atomically for each item
                    reservation_results = []
                    for cart_item in cart_items:
                        success = await ReservedStockRepository.atomic_check_and_reserve(
                            cart_item.category_id,
                            cart_item.subcategory_id,
                            cart_item.quantity,
                            order_id,
                            expires_at
                        )
                        if not success:
                            raise ValueError(f"Insufficient stock for category {cart_item.category_id}, subcategory {cart_item.subcategory_id}")
                        reservation_results.append(success)
                    return reservation_results
                
                async def clear_cart_operation(session):
                    await CartService.clear_cart(user_id)
                
                # Total amount already calculated and validated from cart validation
                
                # Execute all operations in savepoints for partial rollback capability
                operations = [
                    create_order_operation,
                    lambda s: create_order_items_operation(s, None),  # Will be updated with actual order_id
                    lambda s: reserve_stock_operation(s, None),       # Will be updated with actual order_id
                    clear_cart_operation
                ]
                
                # Execute order creation first
                order_dto, order_id = await create_order_operation(session)
                
                # Update operations with actual order_id
                operations[1] = lambda s: create_order_items_operation(s, order_id)
                operations[2] = lambda s: reserve_stock_operation(s, order_id)
                
                # Execute remaining operations with savepoints
                await TransactionManager.execute_with_savepoint(
                    session, 
                    [operations[1], operations[2], operations[3]], 
                    "order_creation"
                )
                
                # Commit the transaction
                await session.commit()
                
                logger.info(f"Order {order_id} created successfully for user {user_id} with {len(cart_items)} items")
                
                # Send notifications (outside transaction to avoid blocking)
                try:
                    user_dto = await UserRepository.get_user_entity(user_id)
                    await NotificationService.order_created(order_dto, user_dto)
                except Exception as e:
                    logger.error(f"Failed to send order creation notification: {str(e)}")
                
                return order_dto
                
        except Exception as e:
            logger.error(f"Error creating order for user {user_id}: {str(e)}")
            raise
    
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
    async def cancel_order(order_id: int, user_initiated: bool = True, admin_id: int = None) -> None:
        """
        Cancel order and release reserved stock with state machine validation
        """
        order = await OrderRepository.get_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        
        # Validate state transition using state machine
        if not validate_order_transition(
            order_id, 
            order.status, 
            OrderStatus.CANCELLED.value,
            admin_id=admin_id if not user_initiated else None,
            user_id=order.user_id if user_initiated else None
        ):
            raise ValueError(f"Invalid status transition: {order.status} -> {OrderStatus.CANCELLED.value}")
        
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
    @TransactionManager.with_retry(max_retries=3)
    async def confirm_payment(order_id: int) -> None:
        """
        Confirm payment received and mark items as sold with atomic transaction
        """
        try:
            async with TransactionManager.atomic_transaction() as session:
                order = await OrderRepository.get_by_id(order_id)
                if not order:
                    raise ValueError("Order not found")
                
                # Validate state transition using state machine
                if not validate_order_transition(
                    order_id, 
                    order.status, 
                    OrderStatus.PAID.value
                ):
                    raise ValueError(f"Invalid status transition: {order.status} -> {OrderStatus.PAID.value}")
                
                async def update_payment_status_operation(session):
                    await OrderRepository.update_payment_confirmation(order_id, datetime.now())
                
                async def mark_items_sold_operation(session):
                    await ItemRepository.mark_items_as_sold_from_order(order_id)
                
                async def release_reservations_operation(session):
                    await ReservedStockRepository.release_by_order_id(order_id)
                
                # Execute all operations with savepoints for atomicity
                operations = [
                    update_payment_status_operation,
                    mark_items_sold_operation,
                    release_reservations_operation
                ]
                
                await TransactionManager.execute_with_savepoint(
                    session,
                    operations,
                    "payment_confirmation"
                )
                
                await session.commit()
                
                logger.info(f"Payment confirmed successfully for order {order_id}")
                
                # Send notifications (outside transaction)
                try:
                    user_dto = await UserRepository.get_user_entity(order.user_id)
                    await NotificationService.payment_received(order, user_dto)
                except Exception as e:
                    logger.error(f"Failed to send payment confirmation notification: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error confirming payment for order {order_id}: {str(e)}")
            raise
    
    @staticmethod
    async def expire_order(order_id: int) -> None:
        """
        Expire order due to timeout with state machine validation
        """
        order = await OrderRepository.get_by_id(order_id)
        if not order:
            return  # Order already processed or doesn't exist
        
        # Validate state transition using state machine
        if not validate_order_transition(
            order_id, 
            order.status, 
            OrderStatus.EXPIRED.value
        ):
            logger.warning(f"Cannot expire order {order_id}: invalid transition from {order.status}")
            return  # Order already processed or in invalid state
        
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
    async def ship_order(order_id: int, admin_id: int) -> None:
        """
        Mark order as shipped with state machine validation (admin only)
        """
        order = await OrderRepository.get_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        
        # Validate state transition using state machine (requires admin)
        if not validate_order_transition(
            order_id, 
            order.status, 
            OrderStatus.SHIPPED.value,
            admin_id=admin_id
        ):
            raise ValueError(f"Invalid status transition: {order.status} -> {OrderStatus.SHIPPED.value} (admin required)")
        
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