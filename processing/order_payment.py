import logging
import hmac
import hashlib
from typing import Dict, Any
import time
from collections import defaultdict, deque

from aiohttp import web
from aiohttp.web_request import Request

from services.payment_observer import PaymentObserverService
import config

logger = logging.getLogger(__name__)

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # 1 minute window
RATE_LIMIT_MAX_REQUESTS = 10  # Max 10 requests per minute per IP
rate_limit_store = defaultdict(lambda: deque())


class OrderPaymentProcessor:
    # Class attribute to expose rate_limit_store for testing
    rate_limit_store = rate_limit_store
    
    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
        """
        Enhanced webhook signature verification with multiple hash algorithms
        """
        try:
            # Support multiple signature formats
            if signature.startswith('sha256='):
                expected_signature = hmac.new(
                    secret.encode('utf-8'),
                    payload,
                    hashlib.sha256
                ).hexdigest()
                return hmac.compare_digest(f"sha256={expected_signature}", signature)
            elif signature.startswith('sha1='):
                expected_signature = hmac.new(
                    secret.encode('utf-8'),
                    payload,
                    hashlib.sha1
                ).hexdigest()
                return hmac.compare_digest(f"sha1={expected_signature}", signature)
            else:
                # Default to sha256 if no prefix
                expected_signature = hmac.new(
                    secret.encode('utf-8'),
                    payload,
                    hashlib.sha256
                ).hexdigest()
                return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    @staticmethod
    def check_rate_limit(ip_address: str) -> bool:
        """
        Check if IP address has exceeded rate limit
        """
        current_time = time.time()
        requests = rate_limit_store[ip_address]
        
        # Remove old requests outside the window
        while requests and requests[0] < current_time - RATE_LIMIT_WINDOW:
            requests.popleft()
        
        # Check if rate limit exceeded
        if len(requests) >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning(f"Rate limit exceeded for IP {ip_address}: {len(requests)} requests in {RATE_LIMIT_WINDOW}s")
            return False
        
        # Add current request
        requests.append(current_time)
        return True
    
    @staticmethod
    def validate_payload_size(payload: bytes, max_size: int = 1024) -> bool:
        """
        Validate webhook payload size
        """
        if len(payload) > max_size:
            logger.warning(f"Payload size too large: {len(payload)} bytes > {max_size} bytes")
            return False
        return True
    
    @staticmethod
    def sanitize_input(data: dict) -> dict:
        """
        Sanitize and validate input data
        """
        sanitized = {}
        
        # Whitelist of allowed fields with validation
        allowed_fields = {
            'address': (str, 100),  # Max 100 chars
            'amount': (float, None),
            'currency': (str, 10),  # Max 10 chars
            'tx_hash': (str, 128),  # Max 128 chars
            'confirmations': (int, None)
        }
        
        for field, (expected_type, max_length) in allowed_fields.items():
            if field in data:
                value = data[field]
                
                # Type validation
                if expected_type == str and isinstance(value, str):
                    # String length validation
                    if max_length and len(value) > max_length:
                        logger.warning(f"Field {field} too long: {len(value)} > {max_length}")
                        continue
                    # Remove potentially dangerous characters
                    sanitized[field] = ''.join(c for c in value if c.isprintable()).strip()
                elif expected_type == float:
                    try:
                        sanitized[field] = float(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid float value for {field}: {value}")
                        continue
                elif expected_type == int:
                    try:
                        sanitized[field] = int(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid int value for {field}: {value}")
                        continue
        
        return sanitized
    
    @staticmethod
    async def process_order_payment_webhook(request: Request) -> web.Response:
        """
        Enhanced process payment confirmation webhook for orders with security hardening
        Endpoint: POST /cryptoprocessing/order_payment
        """
        client_ip = request.remote or 'unknown'
        
        try:
            # 1. Rate limiting check
            if not OrderPaymentProcessor.check_rate_limit(client_ip):
                return web.json_response(
                    {'error': 'Rate limit exceeded'}, 
                    status=429
                )
            
            # 2. Read and validate payload size
            payload = await request.read()
            if not OrderPaymentProcessor.validate_payload_size(payload, max_size=1024):
                return web.json_response(
                    {'error': 'Payload too large'}, 
                    status=413
                )
            
            # 3. Parse and validate JSON payload
            try:
                raw_data = await request.json()
            except Exception as e:
                logger.error(f"Error parsing webhook JSON from IP {client_ip}: {str(e)}")
                return web.json_response(
                    {'error': 'Invalid JSON payload'},
                    status=400
                )
            # 4. Sanitize input data
            data = OrderPaymentProcessor.sanitize_input(raw_data)


            # 5. Validate required fields
            required_fields = ['address', 'amount', 'currency']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                logger.warning(f"Missing required fields from IP {client_ip}: {missing_fields}")
                return web.json_response(
                    {'error': f'Missing required fields: {missing_fields}'},
                    status=400
                )


            # 6. Extract and validate payment data
            address = data.get('address', '').strip()
            amount = data.get('amount', 0)
            currency = data.get('currency', '').upper().strip()
            tx_hash = data.get('tx_hash', '').strip()
            confirmations = data.get('confirmations', 0)
          
            if not address or len(address) < 10:
                return web.json_response(
                    {'error': 'Invalid payment address'},
                    status=400
                )

            if amount <= 0:
                return web.json_response(
                    {'error': 'Invalid payment amount'},
                    status=400
                )

            if currency not in ['BTC', 'ETH', 'LTC', 'SOL']:
                return web.json_response(
                    {'error': 'Unsupported currency'},
                    status=400
                )


            # 7. Enhanced signature verification after basic validation
            webhook_secret = getattr(config, 'WEBHOOK_SECRET', None)
            if webhook_secret:
                signature = request.headers.get('X-Signature', '') or request.headers.get('X-Hub-Signature', '')
                if not signature:
                    logger.warning(f"Missing signature from IP {client_ip}")
                    return web.json_response(
                        {'error': 'Missing signature'},
                        status=401
                    )

                if not OrderPaymentProcessor.verify_webhook_signature(payload, signature, webhook_secret):
                    logger.warning(f"Invalid webhook signature from IP {client_ip}")
                    return web.json_response(
                        {'error': 'Invalid signature'},
                        status=401
                    )

            # 8. Process payment with enhanced validation
            result = await PaymentObserverService.handle_payment_webhook(
                address=address,
                amount=amount,
                currency=currency,
                tx_hash=tx_hash,
                confirmations=confirmations
            )
            
            if result['success']:
                logger.info(f"Payment webhook processed successfully from IP {client_ip}: {address}")
                return web.json_response(result, status=200)
            else:
                logger.warning(f"Payment webhook processing failed from IP {client_ip}: {result['message']}")
                return web.json_response(result, status=400)
                
        except Exception as e:
            logger.error(f"Error processing order payment webhook from IP {client_ip}: {str(e)}")
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