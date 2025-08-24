import logging
from typing import Optional
from datetime import datetime

from models.order import OrderDTO, OrderStatus
from repositories.order import OrderRepository
from services.order import OrderService

logger = logging.getLogger(__name__)


class PaymentObserverService:
    @staticmethod
    async def monitor_order_payments() -> None:
        """
        Monitor order payments and process confirmations
        This would typically integrate with blockchain APIs or webhook services
        """
        try:
            # In a real implementation, this would monitor blockchain transactions
            # For now, this is a placeholder for the monitoring logic
            logger.info("Payment monitoring cycle completed")
            
        except Exception as e:
            logger.error(f"Error monitoring order payments: {str(e)}")
    
    @staticmethod
    async def process_payment_confirmation(address: str, amount: float, currency: str) -> bool:
        """
        Process payment confirmation received from webhook or monitoring
        """
        try:
            # Find order by payment address
            order = await OrderRepository.get_by_payment_address(address)
            if not order:
                logger.warning(f"No order found for payment address: {address}")
                return False
            
            # Validate payment amount
            if not await PaymentObserverService.validate_payment_amount(order.id, amount):
                logger.warning(f"Payment amount validation failed for order {order.id}")
                return False
            
            # Confirm payment
            await OrderService.confirm_payment(order.id)
            logger.info(f"Payment confirmed for order {order.id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing payment confirmation: {str(e)}")
            return False
    
    @staticmethod
    async def validate_payment_amount(order_id: int, received_amount: float) -> bool:
        """
        Validate that received payment amount matches order total
        """
        try:
            order = await OrderRepository.get_by_id(order_id)
            if not order:
                return False
            
            # Allow small tolerance for transaction fees (1% tolerance)
            tolerance = 0.01
            min_amount = order.total_amount * (1 - tolerance)
            
            return received_amount >= min_amount
            
        except Exception as e:
            logger.error(f"Error validating payment amount: {str(e)}")
            return False
    
    @staticmethod 
    async def handle_payment_webhook(address: str, amount: float, currency: str, tx_hash: str = None) -> dict:
        """
        Handle incoming payment webhook with transaction details
        """
        try:
            result = await PaymentObserverService.process_payment_confirmation(address, amount, currency.upper())
            
            if result:
                return {
                    'success': True,
                    'message': 'Payment processed successfully',
                    'address': address,
                    'amount': amount,
                    'currency': currency,
                    'tx_hash': tx_hash
                }
            else:
                return {
                    'success': False,
                    'message': 'Payment processing failed',
                    'address': address,
                    'amount': amount,
                    'currency': currency,
                    'tx_hash': tx_hash
                }
                
        except Exception as e:
            logger.error(f"Error handling payment webhook: {str(e)}")
            return {
                'success': False,
                'message': f'Webhook processing error: {str(e)}',
                'address': address,
                'amount': amount,
                'currency': currency,
                'tx_hash': tx_hash
            }