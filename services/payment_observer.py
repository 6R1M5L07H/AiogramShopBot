import logging
import asyncio
from typing import Optional, Dict
from datetime import datetime

from models.order import OrderDTO, OrderStatus
from repositories.order import OrderRepository
from services.order import OrderService

logger = logging.getLogger(__name__)


class PaymentObserverService:
    # Minimum blockchain confirmations per currency
    CONFIRMATION_REQUIREMENTS = {
        'BTC': 3,
        'ETH': 12,
        'LTC': 6,
        'SOL': 32
    }
    
    # Cache for processed transaction hashes to prevent duplicates
    _processed_tx_hashes = set()
    
    # Currency decimal precision for validation
    CURRENCY_DECIMALS = {
        'BTC': 8,
        'ETH': 18,
        'LTC': 8,
        'SOL': 9
    }
    # Locks per payment address to prevent concurrent processing
    _address_locks: Dict[str, asyncio.Lock] = {}
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
        """Process payment confirmation received from webhook or monitoring"""
        lock = PaymentObserverService._address_locks.setdefault(address, asyncio.Lock())
        async with lock:
            # Find order by payment address
            order = await OrderRepository.get_by_payment_address(address)
            if not order:
                logger.warning(f"No order found for payment address: {address}")
                return False

            # Validate payment amount
            if not await PaymentObserverService.validate_payment_amount(order.id, amount):
                logger.warning(f"Payment amount validation failed for order {order.id}")
                return False

            # Confirm payment - selectively handle known errors
            try:
                await OrderService.confirm_payment(order.id)
            except ValueError as e:
                if str(e) == "Payment already processed":
                    raise
                logger.error(f"Error confirming payment for order {order.id}: {str(e)}")
                return False

            logger.info(f"Payment confirmed for order {order.id}")
            return True
    
    @staticmethod
    async def validate_payment_amount(order_id: int, received_amount: float) -> bool:
        """
        Validate that received payment amount matches order total
        """
        try:
            order = await OrderRepository.get_by_id(order_id)
            if not order:
                return False
            
            # Allow small tolerance for transaction fees (0.1% tolerance for security)
            tolerance = 0.001
            min_amount = order.total_amount * (1 - tolerance)
            
            return received_amount >= min_amount
            
        except Exception as e:
            logger.error(f"Error validating payment amount: {str(e)}")
            return False
    
    @staticmethod
    async def validate_payment_precision(amount: float, currency: str) -> bool:
        """
        Validate payment amount precision based on currency decimal places
        """
        try:
            from decimal import Decimal, InvalidOperation

            max_decimals = PaymentObserverService.CURRENCY_DECIMALS.get(currency.upper(), 8)

            try:
                decimal_amount = Decimal(str(amount))
            except InvalidOperation:
                return False

            decimal_places = -decimal_amount.as_tuple().exponent

            return decimal_places <= max_decimals
            
        except Exception as e:
            logger.error(f"Error validating payment precision: {str(e)}")
            return False
    
    @staticmethod
    async def check_transaction_duplicate(tx_hash: str) -> bool:
        """
        Check if transaction hash has already been processed
        """
        if not tx_hash:
            return False
            
        # Check in-memory cache first
        if tx_hash in PaymentObserverService._processed_tx_hashes:
            logger.warning(f"Duplicate transaction hash detected: {tx_hash}")
            return True
        
        # TODO: In production, also check database for persistent duplicate detection
        # For now, add to memory cache
        PaymentObserverService._processed_tx_hashes.add(tx_hash)
        
        # Limit cache size to prevent memory issues
        if len(PaymentObserverService._processed_tx_hashes) > 10000:
            # Remove oldest 50% of entries (simple approach)
            PaymentObserverService._processed_tx_hashes = set(
                list(PaymentObserverService._processed_tx_hashes)[5000:]
            )
        
        return False
    
    @staticmethod
    async def validate_confirmations(currency: str, confirmations: int = 0) -> bool:
        """
        Validate that transaction has sufficient blockchain confirmations
        """
        required_confirmations = PaymentObserverService.CONFIRMATION_REQUIREMENTS.get(
            currency.upper(), 1
        )
        
        if confirmations < required_confirmations:
            logger.warning(f"Insufficient confirmations for {currency}: {confirmations} < {required_confirmations}")
            return False
        
        return True
    
    @staticmethod 
    async def handle_payment_webhook(address: str, amount: float, currency: str, tx_hash: str = None, 
                                   confirmations: int = 0) -> dict:
        """
        Handle incoming payment webhook with enhanced security validation
        """
        try:
            currency_upper = currency.upper()
            
            # 1. Check for duplicate transaction
            if tx_hash and await PaymentObserverService.check_transaction_duplicate(tx_hash):
                return {
                    'success': False,
                    'message': 'Duplicate transaction hash',
                    'address': address,
                    'amount': amount,
                    'currency': currency,
                    'tx_hash': tx_hash
                }
            
            # 2. Validate payment precision
            if not await PaymentObserverService.validate_payment_precision(amount, currency_upper):
                return {
                    'success': False,
                    'message': 'Invalid payment precision for currency',
                    'address': address,
                    'amount': amount,
                    'currency': currency,
                    'tx_hash': tx_hash
                }
            
            # 3. Validate blockchain confirmations
            if not await PaymentObserverService.validate_confirmations(currency_upper, confirmations):
                return {
                    'success': False,
                    'message': f'Insufficient confirmations ({confirmations} < {PaymentObserverService.CONFIRMATION_REQUIREMENTS.get(currency_upper, 1)})',
                    'address': address,
                    'amount': amount,
                    'currency': currency,
                    'tx_hash': tx_hash
                }
            
            # 4. Process the payment with enhanced validation
            result = await PaymentObserverService.process_payment_confirmation(address, amount, currency_upper)
            
            if result:
                logger.info(f"Payment processed successfully: {tx_hash} - {amount} {currency_upper}")
                return {
                    'success': True,
                    'message': 'Payment processed successfully',
                    'address': address,
                    'amount': amount,
                    'currency': currency,
                    'tx_hash': tx_hash,
                    'confirmations': confirmations
                }
            else:
                return {
                    'success': False,
                    'message': 'Payment processing failed - invalid amount or order not found',
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