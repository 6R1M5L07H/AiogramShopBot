"""
Integration testing for the invoice-stock-management feature workflows.

This module tests complete end-to-end workflows including:
- Cart-to-order flow with stock management
- Payment processing webhooks with validation
- Background task scheduler for order expiration
- Admin order management workflows
- Cross-service integration points
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, call
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
import json
import hmac
import hashlib
import time

from services.order import OrderService
from services.cart import CartService
from services.background_tasks import BackgroundTaskService
from processing.order_payment import OrderPaymentProcessor
from repositories.order import OrderRepository
from repositories.cart import CartRepository
from repositories.item import ItemRepository
from models.order import OrderStatus, OrderDTO
from models.cart import CartItemDTO
from models.item import ItemDTO


class TestCartToOrderIntegration:
    """Test complete cart-to-order workflow integration."""
    
    async def test_complete_cart_to_order_workflow(self, db_session, test_user, test_category, 
                                                 test_subcategory, test_items, 
                                                 mock_crypto_generator, mock_encryption_service,
                                                 mock_notification_service):
        """
        Test Case: Complete cart-to-order workflow with stock reservation
        Integration Scenario: User adds items to cart, creates order, stock is reserved
        """
        # Step 1: Add items to cart
        with patch('repositories.cart.CartRepository.create') as mock_cart_create, \
             patch('repositories.cart.CartRepository.get_by_user_id') as mock_get_cart:
            
            # Mock cart items
            cart_items = [
                CartItemDTO(
                    id=1,
                    user_id=test_user.id,
                    category_id=test_category.id,
                    subcategory_id=test_subcategory.id,
                    quantity=2,
                    price=20.0
                ),
                CartItemDTO(
                    id=2,
                    user_id=test_user.id,
                    category_id=test_category.id,
                    subcategory_id=test_subcategory.id,
                    quantity=1,
                    price=15.0
                )
            ]
            
            mock_get_cart.return_value = cart_items
            
            # Step 2: Mock cart validation
            with patch('services.cart.CartService.validate_cart_integrity') as mock_validate, \
                 patch('services.cart.CartService.clear_cart') as mock_clear_cart:
                
                mock_validate.return_value = {
                    'valid': True,
                    'errors': [],
                    'warnings': [],
                    'total_amount': 55.0  # 2*20 + 1*15
                }
                mock_clear_cart.return_value = None
                
                # Step 3: Mock order creation components
                with patch('repositories.order.OrderRepository.get_by_user_id') as mock_get_existing, \
                     patch('repositories.order.OrderRepository.create_with_encrypted_key') as mock_create_order, \
                     patch('repositories.orderItem.OrderItemRepository.create_many') as mock_create_items, \
                     patch('repositories.reservedStock.ReservedStockRepository.atomic_check_and_reserve') as mock_reserve:
                    
                    mock_get_existing.return_value = None  # No existing order
                    mock_create_order.return_value = 123  # Order ID
                    mock_create_items.return_value = None
                    mock_reserve.return_value = True  # Stock available
                    
                    # Step 4: Create order from cart
                    order = await OrderService.create_order_from_cart(test_user.id, 'BTC')
                    
                    # Verify order creation
                    assert order is not None
                    assert order.user_id == test_user.id
                    assert order.total_amount == 55.0
                    assert order.currency == 'BTC'
                    assert order.status == OrderStatus.CREATED.value
                    
                    # Verify workflow calls
                    mock_validate.assert_called_once()
                    mock_create_order.assert_called_once()
                    mock_create_items.assert_called_once()
                    mock_clear_cart.assert_called_once()
                    assert mock_reserve.call_count == 2  # One for each cart item
                    
                    # Verify notifications
                    mock_notification_service.order_created.assert_called_once()
    
    async def test_cart_to_order_insufficient_stock(self, db_session, test_user, test_category,
                                                   test_subcategory, mock_crypto_generator):
        """
        Test Case: Cart-to-order workflow fails with insufficient stock
        Integration Scenario: Stock validation prevents order creation
        """
        # Mock cart with items
        cart_items = [
            CartItemDTO(
                id=1,
                user_id=test_user.id,
                category_id=test_category.id,
                subcategory_id=test_subcategory.id,
                quantity=10,  # More than available
                price=20.0
            )
        ]
        
        with patch('services.cart.CartService.get_cart_items', return_value=cart_items), \
             patch('services.cart.CartService.validate_cart_integrity') as mock_validate:
            
            # Mock insufficient stock scenario
            mock_validate.return_value = {
                'valid': False,
                'errors': ['Insufficient stock for category 1, subcategory 1'],
                'warnings': [],
                'total_amount': 0
            }
            
            # Order creation should fail
            with pytest.raises(ValueError, match="Cart validation failed"):
                await OrderService.create_order_from_cart(test_user.id, 'BTC')
    
    async def test_cart_to_order_with_existing_active_order(self, db_session, test_user):
        """
        Test Case: Cart-to-order fails when user has existing active order
        Integration Scenario: Prevent multiple active orders per user
        """
        # Mock existing active order
        existing_order = Mock()
        existing_order.status = OrderStatus.CREATED.value
        
        with patch('repositories.order.OrderRepository.get_by_user_id', return_value=existing_order):
            
            # Order creation should fail
            with pytest.raises(ValueError, match="User already has an active order"):
                await OrderService.create_order_from_cart(test_user.id, 'BTC')


class TestPaymentWebhookIntegration:
    """Test payment webhook processing integration."""
    
    async def test_complete_payment_webhook_workflow(self, test_order, mock_notification_service):
        """
        Test Case: Complete payment webhook processing workflow
        Integration Scenario: Webhook validates payment and confirms order
        """
        # Mock webhook payload
        webhook_data = {
            'address': test_order.payment_address,
            'amount': test_order.total_amount,
            'currency': test_order.currency,
            'tx_hash': 'test_tx_hash_12345',
            'confirmations': 6
        }
        
        # Mock order repository calls
        with patch('repositories.order.OrderRepository.get_by_payment_address') as mock_get_by_addr, \
             patch('repositories.order.OrderRepository.get_by_id') as mock_get_by_id, \
             patch('repositories.order.OrderRepository.update_payment_confirmation') as mock_update, \
             patch('repositories.item.ItemRepository.mark_items_as_sold_from_order') as mock_mark_sold, \
             patch('repositories.reservedStock.ReservedStockRepository.release_by_order_id') as mock_release, \
             patch('repositories.user.UserRepository.get_user_entity') as mock_get_user:
            
            # Setup mocks
            mock_order = Mock()
            mock_order.id = test_order.id
            mock_order.user_id = test_order.user_id
            mock_order.total_amount = test_order.total_amount
            mock_order.status = OrderStatus.CREATED.value
            
            mock_get_by_addr.return_value = mock_order
            mock_get_by_id.return_value = mock_order
            mock_update.return_value = None
            mock_mark_sold.return_value = None
            mock_release.return_value = None
            mock_get_user.return_value = Mock(id=test_order.user_id)
            
            # Process webhook
            result = await PaymentObserverService.handle_payment_webhook(**webhook_data)
            
            # Verify successful processing
            assert result['success'] == True
            assert result['message'] == 'Payment processed successfully'
            
            # Verify workflow execution
            mock_get_by_addr.assert_called_once_with(webhook_data['address'])
            mock_update.assert_called_once()
            mock_mark_sold.assert_called_once()
            mock_release.assert_called_once()
            mock_notification_service.payment_received.assert_called_once()
    
    async def test_payment_webhook_security_validation(self):
        """
        Test Case: Payment webhook with comprehensive security validation
        Integration Scenario: Full security pipeline validation
        """
        # Create mock request with proper signature
        payload_data = {
            'address': 'test_address_12345',
            'amount': 1.0,
            'currency': 'BTC',
            'tx_hash': 'valid_tx_hash',
            'confirmations': 6
        }
        payload = json.dumps(payload_data).encode('utf-8')
        
        # Generate valid signature
        secret = 'test_webhook_secret_key'
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        
        # Create mock request
        mock_request = make_mocked_request(
            'POST', '/cryptoprocessing/order_payment',
            headers={'X-Signature': f'sha256={signature}'},
            payload=payload
        )
        mock_request.read = AsyncMock(return_value=payload)
        mock_request.json = AsyncMock(return_value=payload_data)
        mock_request.remote = '127.0.0.1'
        
        # Mock successful payment processing
        with patch('services.payment_observer.PaymentObserverService.handle_payment_webhook') as mock_handle:
            mock_handle.return_value = {
                'success': True,
                'message': 'Payment processed successfully'
            }
            
            with patch('config.WEBHOOK_SECRET', secret):
                # Process webhook
                response = await OrderPaymentProcessor.process_order_payment_webhook(mock_request)
                
                # Verify successful processing
                assert response.status == 200
                response_data = json.loads(response.text)
                assert response_data['success'] == True
    
    async def test_payment_webhook_rate_limiting(self):
        """
        Test Case: Payment webhook rate limiting functionality
        Integration Scenario: Rate limiting prevents abuse
        """
        test_ip = '192.168.1.100'
        
        # Make requests up to limit
        for i in range(10):  # Max requests per minute
            assert OrderPaymentProcessor.check_rate_limit(test_ip) == True
        
        # Next request should be rate limited
        assert OrderPaymentProcessor.check_rate_limit(test_ip) == False
        
        # Verify rate limit window reset
        time.sleep(0.1)  # Small delay for test
        # After window, should allow again (mocked in real implementation)
    
    async def test_payment_webhook_invalid_signature(self):
        """
        Test Case: Payment webhook rejects invalid signatures
        Integration Scenario: Signature validation prevents tampering
        """
        payload_data = {'address': 'test', 'amount': 1.0, 'currency': 'BTC'}
        payload = json.dumps(payload_data).encode('utf-8')
        
        mock_request = make_mocked_request(
            'POST', '/cryptoprocessing/order_payment',
            headers={'X-Signature': 'invalid_signature'},
            payload=payload
        )
        mock_request.read = AsyncMock(return_value=payload)
        mock_request.remote = '127.0.0.1'
        
        with patch('config.WEBHOOK_SECRET', 'test_secret'):
            response = await OrderPaymentProcessor.process_order_payment_webhook(mock_request)
            
            assert response.status == 401
            response_data = json.loads(response.text)
            assert response_data['error'] == 'Invalid signature'


class TestBackgroundTaskIntegration:
    """Test background task processing integration."""
    
    async def test_order_expiration_background_task(self, db_session, expired_order, 
                                                   mock_notification_service):
        """
        Test Case: Background task processes expired orders correctly
        Integration Scenario: Expired orders are automatically handled
        """
        # Mock repository calls for expiration processing
        with patch('repositories.order.OrderRepository.get_expired_orders') as mock_get_expired, \
             patch('repositories.order.OrderRepository.update_status') as mock_update_status, \
             patch('repositories.reservedStock.ReservedStockRepository.release_by_order_id') as mock_release, \
             patch('repositories.user.UserRepository.increment_timeout_count') as mock_increment, \
             patch('repositories.user.UserRepository.get_user_entity') as mock_get_user:
            
            # Setup mocks
            mock_get_expired.return_value = [expired_order]
            mock_update_status.return_value = None
            mock_release.return_value = None
            mock_increment.return_value = None
            mock_get_user.return_value = Mock(id=expired_order.user_id)
            
            # Process expired orders
            await BackgroundTaskService.process_expired_orders()
            
            # Verify expiration workflow
            mock_get_expired.assert_called_once()
            mock_update_status.assert_called_once_with(expired_order.id, OrderStatus.EXPIRED)
            mock_release.assert_called_once_with(expired_order.id)
            mock_increment.assert_called_once_with(expired_order.user_id)
            mock_notification_service.order_expired.assert_called_once()
    
    async def test_background_task_scheduler_integration(self):
        """
        Test Case: Background task scheduler runs periodic tasks
        Integration Scenario: Scheduler processes tasks at intervals
        """
        task_executed = False
        
        async def mock_task():
            nonlocal task_executed
            task_executed = True
        
        # Mock background service methods
        with patch('services.background_tasks.BackgroundTaskService.process_expired_orders', 
                  side_effect=mock_task):
            
            # Run background task cycle
            await BackgroundTaskService.run_background_tasks()
            
            # Verify task execution
            assert task_executed == True
    
    async def test_background_task_error_handling(self):
        """
        Test Case: Background tasks handle errors gracefully
        Integration Scenario: Individual task failures don't crash scheduler
        """
        error_occurred = False
        
        async def failing_task():
            nonlocal error_occurred
            error_occurred = True
            raise Exception("Test error")
        
        with patch('services.background_tasks.BackgroundTaskService.process_expired_orders',
                  side_effect=failing_task):
            
            # Background task should handle error gracefully
            try:
                await BackgroundTaskService.run_background_tasks()
            except Exception:
                pytest.fail("Background task should handle errors gracefully")
            
            assert error_occurred == True


class TestAdminOrderManagementIntegration:
    """Test admin order management workflow integration."""
    
    async def test_admin_order_shipment_workflow(self, db_session, paid_order, test_admin_user,
                                                mock_notification_service):
        """
        Test Case: Admin order shipment workflow with state validation
        Integration Scenario: Admin ships paid order through complete workflow
        """
        # Mock repository calls
        with patch('repositories.order.OrderRepository.get_by_id') as mock_get_order, \
             patch('repositories.order.OrderRepository.update_shipped') as mock_update_shipped, \
             patch('repositories.user.UserRepository.get_user_entity') as mock_get_user:
            
            # Setup mocks
            mock_order = Mock()
            mock_order.id = paid_order.id
            mock_order.user_id = paid_order.user_id
            mock_order.status = OrderStatus.PAID.value
            
            mock_get_order.return_value = mock_order
            mock_update_shipped.return_value = None
            mock_get_user.return_value = Mock(id=paid_order.user_id)
            
            # Ship order as admin
            await OrderService.ship_order(paid_order.id, test_admin_user.id)
            
            # Verify shipment workflow
            mock_get_order.assert_called_once_with(paid_order.id)
            mock_update_shipped.assert_called_once()
            mock_notification_service.order_shipped.assert_called_once()
    
    async def test_admin_order_shipment_invalid_state(self, db_session, test_order, test_admin_user):
        """
        Test Case: Admin cannot ship order in invalid state
        Integration Scenario: State machine prevents invalid transitions
        """
        # Mock order in CREATED state (not PAID)
        with patch('repositories.order.OrderRepository.get_by_id') as mock_get_order:
            mock_order = Mock()
            mock_order.id = test_order.id
            mock_order.status = OrderStatus.CREATED.value  # Not paid yet
            mock_get_order.return_value = mock_order
            
            # Shipment should fail due to invalid state
            with pytest.raises(ValueError, match="Invalid status transition"):
                await OrderService.ship_order(test_order.id, test_admin_user.id)
    
    async def test_admin_private_key_access_audit(self, db_session, test_order, test_admin_user):
        """
        Test Case: Admin private key access is properly audited
        Integration Scenario: Private key access creates audit trail
        """
        encrypted_key = "encrypted_test_key"
        salt = "test_salt"
        
        # Mock repository and encryption service
        with patch('repositories.order.OrderRepository.get_private_key_data') as mock_get_key, \
             patch('repositories.order.OrderRepository.update_key_access_audit') as mock_audit, \
             patch('services.encryption.EncryptionService.decrypt_private_key') as mock_decrypt:
            
            mock_get_key.return_value = (encrypted_key, salt)
            mock_decrypt.return_value = "decrypted_private_key"
            mock_audit.return_value = None
            
            # Access private key as admin
            result = await OrderRepository.get_decrypted_private_key(
                test_order.id, test_admin_user.id
            )
            
            # Verify audit logging
            mock_audit.assert_called_once_with(
                test_order.id, test_admin_user.id, datetime
            )
            assert result == "decrypted_private_key"


class TestCrossServiceIntegration:
    """Test integration between different services."""
    
    async def test_order_notification_integration(self, db_session, test_user, test_order,
                                                 mock_notification_service):
        """
        Test Case: Order lifecycle events trigger appropriate notifications
        Integration Scenario: All order state changes send notifications
        """
        # Mock user repository
        with patch('repositories.user.UserRepository.get_user_entity') as mock_get_user:
            mock_get_user.return_value = test_user
            
            # Test order creation notification
            await NotificationService.order_created(test_order, test_user)
            mock_notification_service.order_created.assert_called_once_with(test_order, test_user)
            
            # Test payment received notification
            await NotificationService.payment_received(test_order, test_user)
            mock_notification_service.payment_received.assert_called_once_with(test_order, test_user)
            
            # Test order shipped notification
            await NotificationService.order_shipped(test_order, test_user)
            mock_notification_service.order_shipped.assert_called_once_with(test_order, test_user)
    
    async def test_stock_item_integration(self, db_session, test_items, test_order):
        """
        Test Case: Stock management integrates with item inventory
        Integration Scenario: Order confirmation marks items as sold
        """
        # Mock item repository
        with patch('repositories.item.ItemRepository.mark_items_as_sold_from_order') as mock_mark_sold, \
             patch('repositories.item.ItemRepository.get_available_items') as mock_get_available:
            
            mock_mark_sold.return_value = None
            mock_get_available.return_value = test_items[:3]  # 3 available items
            
            # Confirm payment (should mark items as sold)
            with patch('repositories.order.OrderRepository.get_by_id') as mock_get_order, \
                 patch('repositories.order.OrderRepository.update_payment_confirmation') as mock_update:
                
                mock_order = Mock()
                mock_order.id = test_order.id
                mock_order.status = OrderStatus.CREATED.value
                mock_get_order.return_value = mock_order
                mock_update.return_value = None
                
                await OrderService.confirm_payment(test_order.id)
                
                # Verify items marked as sold
                mock_mark_sold.assert_called_once_with(test_order.id)
    
    async def test_encryption_repository_integration(self, db_session, test_order):
        """
        Test Case: Encryption service integrates with repository layer
        Integration Scenario: Encrypted private keys are stored and retrieved correctly
        """
        test_private_key = "test_private_key_12345"
        
        # Mock encryption service
        with patch('services.encryption.EncryptionService.encrypt_private_key') as mock_encrypt, \
             patch('services.encryption.EncryptionService.decrypt_private_key') as mock_decrypt:
            
            mock_encrypt.return_value = ("encrypted_key", "salt")
            mock_decrypt.return_value = test_private_key
            
            # Mock repository storage
            with patch('repositories.order.OrderRepository.store_encrypted_private_key') as mock_store, \
                 patch('repositories.order.OrderRepository.get_private_key_data') as mock_get:
                
                mock_store.return_value = None
                mock_get.return_value = ("encrypted_key", "salt")
                
                # Store encrypted key
                await OrderRepository.create_with_encrypted_key(test_order, test_private_key)
                
                # Retrieve and decrypt key
                result = await OrderRepository.get_decrypted_private_key(test_order.id)
                
                # Verify integration
                mock_encrypt.assert_called_once_with(test_private_key, test_order.id)
                mock_store.assert_called_once()
                mock_decrypt.assert_called_once_with("encrypted_key", "salt", test_order.id)
                assert result == test_private_key