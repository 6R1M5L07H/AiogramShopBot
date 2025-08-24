import logging
import hmac
import hashlib
from typing import Dict, Any

from aiohttp import web
from aiohttp.web_request import Request

from services.payment_observer import PaymentObserverService
import config

logger = logging.getLogger(__name__)


class OrderPaymentProcessor:
    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
        """
        Verify webhook signature for security
        """
        try:
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures safely
            return hmac.compare_digest(f"sha256={expected_signature}", signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    @staticmethod
    async def process_order_payment_webhook(request: Request) -> web.Response:
        """
        Process payment confirmation webhook for orders
        Endpoint: POST /cryptoprocessing/order_payment
        """
        try:
            # Read request body
            payload = await request.read()
            
            # Verify signature if webhook secret is configured
            webhook_secret = getattr(config, 'WEBHOOK_SECRET', None)
            if webhook_secret:
                signature = request.headers.get('X-Signature', '')
                if not OrderPaymentProcessor.verify_webhook_signature(payload, signature, webhook_secret):
                    logger.warning("Invalid webhook signature")
                    return web.json_response(
                        {'error': 'Invalid signature'}, 
                        status=401
                    )
            
            # Parse JSON payload
            try:
                data = await request.json()
            except Exception as e:
                logger.error(f"Error parsing webhook JSON: {str(e)}")
                return web.json_response(
                    {'error': 'Invalid JSON payload'}, 
                    status=400
                )
            
            # Validate required fields
            required_fields = ['address', 'amount', 'currency']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return web.json_response(
                    {'error': f'Missing required fields: {missing_fields}'}, 
                    status=400
                )
            
            # Extract payment data
            address = data.get('address')
            amount = float(data.get('amount', 0))
            currency = data.get('currency', '').upper()
            tx_hash = data.get('tx_hash', '')
            
            # Process payment
            result = await PaymentObserverService.handle_payment_webhook(
                address=address,
                amount=amount,
                currency=currency,
                tx_hash=tx_hash
            )
            
            if result['success']:
                logger.info(f"Payment webhook processed successfully: {address}")
                return web.json_response(result, status=200)
            else:
                logger.warning(f"Payment webhook processing failed: {result['message']}")
                return web.json_response(result, status=400)
                
        except Exception as e:
            logger.error(f"Error processing order payment webhook: {str(e)}")
            return web.json_response(
                {'error': 'Internal server error'}, 
                status=500
            )
    
    @staticmethod
    async def get_order_status(request: Request) -> web.Response:
        """
        Get order status by payment address
        Endpoint: GET /cryptoprocessing/order_status?address=<payment_address>
        """
        try:
            address = request.query.get('address')
            if not address:
                return web.json_response(
                    {'error': 'Missing address parameter'}, 
                    status=400
                )
            
            from repositories.order import OrderRepository
            order = await OrderRepository.get_by_payment_address(address)
            
            if not order:
                return web.json_response(
                    {'error': 'Order not found'}, 
                    status=404
                )
            
            return web.json_response({
                'order_id': order.id,
                'status': order.status,
                'amount': order.total_amount,
                'currency': order.currency,
                'created_at': order.created_at.isoformat(),
                'expires_at': order.expires_at.isoformat(),
                'paid_at': order.paid_at.isoformat() if order.paid_at else None,
                'shipped_at': order.shipped_at.isoformat() if order.shipped_at else None
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error getting order status: {str(e)}")
            return web.json_response(
                {'error': 'Internal server error'}, 
                status=500
            )


# Route handlers for aiohttp
async def order_payment_webhook(request: Request) -> web.Response:
    """Route handler for order payment webhook"""
    return await OrderPaymentProcessor.process_order_payment_webhook(request)


async def order_status_endpoint(request: Request) -> web.Response:
    """Route handler for order status endpoint"""
    return await OrderPaymentProcessor.get_order_status(request)