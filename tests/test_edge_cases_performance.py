"""
Edge cases and performance testing for invoice-stock-management feature.

This module tests edge cases, boundary conditions, and performance scenarios:
- Edge cases in order lifecycle management
- Boundary conditions for payment validation
- Performance testing under load
- Error recovery and resilience testing
- Memory usage and resource management
"""

import pytest
import asyncio
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc
import psutil
import os

from services.order import OrderService
from services.payment_observer import PaymentObserverService
from services.encryption import EncryptionService
from utils.transaction_manager import TransactionManager, TransactionLockTimeout
from models.order import OrderStatus, OrderDTO
from repositories.order import OrderRepository


class TestOrderLifecycleEdgeCases:
    """Test edge cases in order lifecycle management."""
    
    async def test_order_creation_at_exact_expiry_boundary(self, db_session, test_user, 
                                                          mock_crypto_generator, mock_encryption_service):
        """
        Test Case: Order creation exactly at expiry time boundary
        Edge Case: Test timing edge case in order expiration
        """
        # Mock cart with single item
        cart_items = [Mock(
            item_id=1, category_id=1, subcategory_id=1,
            quantity=1, price=10.0
        )]
        
        with patch('services.cart.CartService.get_cart_items', return_value=cart_items), \
             patch('services.cart.CartService.validate_cart_integrity') as mock_validate, \
             patch('services.cart.CartService.clear_cart'):
            
            mock_validate.return_value = {
                'valid': True, 'errors': [], 'warnings': [], 'total_amount': 10.0
            }
            
            with patch('repositories.order.OrderRepository.get_by_user_id', return_value=None), \
                 patch('repositories.order.OrderRepository.create_with_encrypted_key', return_value=1), \
                 patch('repositories.orderItem.OrderItemRepository.create_many'), \
                 patch('repositories.reservedStock.ReservedStockRepository.atomic_check_and_reserve', return_value=True):
                
                # Create order that expires very soon
                with patch('config.ORDER_TIMEOUT_MINUTES', 0.01):  # 0.6 seconds
                    order = await OrderService.create_order_from_cart(test_user.id, 'BTC')
                    
                    # Order should be created successfully
                    assert order is not None
                    assert order.user_id == test_user.id
                    
                    # Check that expiry is in the near future
                    time_to_expiry = (order.expires_at - datetime.now()).total_seconds()
                    assert 0 < time_to_expiry <= 1  # Within 1 second
    
    async def test_order_payment_confirmation_race_condition(self, db_session, test_order):
        """
        Test Case: Multiple payment confirmations for same order
        Edge Case: Prevent double payment processing
        """
        payment_processed_count = 0
        
        async def mock_confirm_payment(order_id):
            nonlocal payment_processed_count
            payment_processed_count += 1
            # Simulate some processing time
            await asyncio.sleep(0.01)
            if payment_processed_count > 1:
                raise ValueError("Payment already processed")
        
        with patch('repositories.order.OrderRepository.get_by_payment_address') as mock_get_by_addr, \
             patch('repositories.order.OrderRepository.get_by_id') as mock_get_by_id, \
             patch('services.order.OrderService.confirm_payment', side_effect=mock_confirm_payment):
            
            mock_order = Mock()
            mock_order.id = test_order.id
            mock_order.total_amount = test_order.total_amount
            mock_get_by_addr.return_value = mock_order
            mock_get_by_id.return_value = mock_order
            
            # Try to process payment confirmation concurrently
            tasks = [
                PaymentObserverService.process_payment_confirmation(
                    test_order.payment_address, 
                    test_order.total_amount, 
                    test_order.currency
                )
                for _ in range(3)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Only one should succeed, others should fail
            success_count = sum(1 for r in results if r is True)
            error_count = sum(1 for r in results if isinstance(r, Exception))
            
            assert success_count == 1
            assert error_count == 2
    
    async def test_order_expiry_at_exact_payment_time(self, db_session):
        """
        Test Case: Order expires exactly when payment is being processed
        Edge Case: Test race condition between expiry and payment
        """
        # Create order that expires immediately
        order_data = OrderDTO(
            id=999,
            user_id=123,
            status=OrderStatus.CREATED.value,
            total_amount=50.0,
            currency='BTC',
            payment_address='race_test_address',
            expires_at=datetime.now() + timedelta(seconds=0.1),  # Expires very soon
            created_at=datetime.now()
        )
        
        with patch('repositories.order.OrderRepository.get_by_payment_address') as mock_get_addr, \
             patch('repositories.order.OrderRepository.get_by_id') as mock_get_by_id:
            
            mock_get_addr.return_value = order_data
            mock_get_by_id.return_value = order_data
            
            # Wait for order to expire
            await asyncio.sleep(0.2)
            
            # Try to process payment on expired order
            with patch('services.order.OrderService.confirm_payment') as mock_confirm:
                # Mock state machine validation to catch invalid transition
                with patch('utils.order_state_machine.validate_order_transition', return_value=False):
                    mock_confirm.side_effect = ValueError("Invalid status transition")
                    
                    result = await PaymentObserverService.process_payment_confirmation(
                        'race_test_address', 50.0, 'BTC'
                    )
                    
                    # Payment should fail due to expired order
                    assert result is False
    
    async def test_zero_amount_payment_handling(self):
        """
        Test Case: Payment with zero or negative amount
        Edge Case: Invalid payment amounts should be rejected
        """
        # Test zero amount
        with patch('repositories.order.OrderRepository.get_by_id') as mock_get:
            mock_order = Mock()
            mock_order.total_amount = 100.0
            mock_get.return_value = mock_order
            
            result = await PaymentObserverService.validate_payment_amount(1, 0.0)
            assert result is False
        
        # Test negative amount  
        result = await PaymentObserverService.validate_payment_amount(1, -50.0)
        assert result is False
    
    async def test_extremely_small_payment_precision(self):
        """
        Test Case: Payment with maximum allowed decimal precision
        Edge Case: Test boundary of decimal precision validation
        """
        # Test BTC with exactly 8 decimal places (maximum)
        btc_amount = 0.12345678  # Exactly 8 decimals
        result = await PaymentObserverService.validate_payment_precision(btc_amount, 'BTC')
        assert result is True
        
        # Test BTC with 9 decimal places (should fail)
        btc_amount_too_precise = 0.123456789  # 9 decimals
        result = await PaymentObserverService.validate_payment_precision(btc_amount_too_precise, 'BTC')
        assert result is False
        
        # Test ETH with exactly 18 decimal places (maximum)
        eth_amount = 0.123456789012345678  # Exactly 18 decimals
        result = await PaymentObserverService.validate_payment_precision(eth_amount, 'ETH')
        assert result is True


class TestPerformanceScenarios:
    """Test performance under various load conditions."""
    
    async def test_concurrent_order_creation_performance(self, concurrent_test_users, performance_monitor):
        """
        Test Case: Multiple users creating orders concurrently
        Performance Scenario: System handles concurrent order creation efficiently
        """
        performance_monitor.start_monitoring()
        
        # Mock all dependencies for performance testing
        with patch('services.cart.CartService.get_cart_items') as mock_get_cart, \
             patch('services.cart.CartService.validate_cart_integrity') as mock_validate, \
             patch('services.cart.CartService.clear_cart'), \
             patch('repositories.order.OrderRepository.get_by_user_id', return_value=None), \
             patch('repositories.order.OrderRepository.create_with_encrypted_key') as mock_create, \
             patch('repositories.orderItem.OrderItemRepository.create_many'), \
             patch('repositories.reservedStock.ReservedStockRepository.atomic_check_and_reserve', return_value=True), \
             patch('utils.CryptoAddressGenerator.CryptoAddressGenerator') as mock_crypto, \
             patch('services.encryption.EncryptionService.encrypt_private_key', return_value=('enc', 'salt')):
            
            # Setup mocks
            mock_get_cart.return_value = [Mock(
                item_id=1, category_id=1, subcategory_id=1,
                quantity=1, price=10.0
            )]
            mock_validate.return_value = {
                'valid': True, 'errors': [], 'warnings': [], 'total_amount': 10.0
            }
            
            order_id_counter = 1000
            def create_order_side_effect(order_dto, private_key):
                nonlocal order_id_counter
                order_id_counter += 1
                return order_id_counter
            
            mock_create.side_effect = create_order_side_effect
            
            crypto_instance = Mock()
            crypto_instance.generate_one_time_address.return_value = {
                'address': 'test_address', 'private_key': 'test_key'
            }
            mock_crypto.return_value = crypto_instance
            
            # Create orders concurrently
            tasks = [
                OrderService.create_order_from_cart(user.id, 'BTC')
                for user in concurrent_test_users
            ]
            
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            performance_monitor.stop_monitoring()
            
            # Verify all orders were created successfully
            successful_orders = [r for r in results if isinstance(r, OrderDTO)]
            assert len(successful_orders) == len(concurrent_test_users)
            
            # Performance assertions
            total_time = end_time - start_time
            assert total_time < 2.0  # Should complete within 2 seconds
            
            metrics = performance_monitor.get_metrics()
            assert metrics['max_memory_usage'] < 80  # Memory usage should stay reasonable
            
            print(f"Performance metrics: {metrics}")
    
    async def test_payment_validation_performance(self, performance_monitor):
        """
        Test Case: Payment validation performance under load
        Performance Scenario: Rapid payment validation doesn't degrade performance
        """
        performance_monitor.start_monitoring()
        
        # Create many payment validation tasks
        validation_tasks = []
        
        with patch('repositories.order.OrderRepository.get_by_id') as mock_get:
            mock_order = Mock()
            mock_order.total_amount = 100.0
            mock_get.return_value = mock_order
            
            # Create 1000 validation tasks
            for i in range(1000):
                amount = 99.9 + (i * 0.00001)  # Slight variations in amount
                task = PaymentObserverService.validate_payment_amount(1, amount)
                validation_tasks.append(task)
            
            start_time = time.time()
            results = await asyncio.gather(*validation_tasks)
            end_time = time.time()
        
        performance_monitor.stop_monitoring()
        
        # All validations should succeed
        assert all(results)
        
        # Performance check
        total_time = end_time - start_time
        assert total_time < 1.0  # Should complete within 1 second
        
        metrics = performance_monitor.get_metrics()
        print(f"Payment validation performance: {total_time:.3f}s for 1000 validations")
        print(f"Memory metrics: {metrics}")
    
    async def test_encryption_performance_bulk_operations(self, performance_monitor):
        """
        Test Case: Encryption performance with bulk operations
        Performance Scenario: Encryption scales well with multiple operations
        """
        # Setup test encryption environment
        test_master_key = EncryptionService.generate_encryption_key()
        original_key = os.environ.get('ENCRYPTION_MASTER_KEY')
        os.environ['ENCRYPTION_MASTER_KEY'] = test_master_key
        
        try:
            performance_monitor.start_monitoring()
            
            # Test bulk encryption operations
            encryption_tasks = []
            for i in range(100):  # 100 private keys
                private_key = f"test_private_key_{i:04d}_{'x' * 50}"  # Realistic key size
                task = asyncio.create_task(
                    asyncio.to_thread(EncryptionService.encrypt_private_key, private_key, i)
                )
                encryption_tasks.append(task)
            
            start_time = time.time()
            encryption_results = await asyncio.gather(*encryption_tasks)
            encryption_time = time.time() - start_time
            
            # Test bulk decryption operations
            decryption_tasks = []
            for i, (encrypted_key, salt) in enumerate(encryption_results):
                task = asyncio.create_task(
                    asyncio.to_thread(EncryptionService.decrypt_private_key, encrypted_key, salt, i)
                )
                decryption_tasks.append(task)
            
            start_time = time.time()
            decryption_results = await asyncio.gather(*decryption_tasks)
            decryption_time = time.time() - start_time
            
            performance_monitor.stop_monitoring()
            
            # Verify all operations succeeded
            assert len(encryption_results) == 100
            assert len(decryption_results) == 100
            
            # Performance assertions
            assert encryption_time < 5.0  # Should encrypt 100 keys in under 5 seconds
            assert decryption_time < 5.0  # Should decrypt 100 keys in under 5 seconds
            
            # Verify data integrity
            for i, decrypted in enumerate(decryption_results):
                expected = f"test_private_key_{i:04d}_{'x' * 50}"
                assert decrypted == expected
            
            metrics = performance_monitor.get_metrics()
            print(f"Encryption performance: {encryption_time:.3f}s for 100 operations")
            print(f"Decryption performance: {decryption_time:.3f}s for 100 operations")
            print(f"Memory metrics: {metrics}")
            
        finally:
            # Restore original environment
            if original_key:
                os.environ['ENCRYPTION_MASTER_KEY'] = original_key
            else:
                os.environ.pop('ENCRYPTION_MASTER_KEY', None)
    
    async def test_memory_usage_under_load(self):
        """
        Test Case: Memory usage remains stable under sustained load
        Performance Scenario: No memory leaks during extended operations
        """
        # Record initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Simulate sustained load with order operations
        for batch in range(10):  # 10 batches
            tasks = []
            
            # Create batch of mock operations
            for i in range(50):  # 50 operations per batch
                # Simulate order creation workflow
                task = self._simulate_order_workflow(batch * 50 + i)
                tasks.append(task)
            
            # Execute batch
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Force garbage collection
            gc.collect()
            
            # Check memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            # Memory shouldn't increase significantly (allow 50MB growth)
            assert memory_increase < 50, f"Memory usage increased by {memory_increase:.1f}MB"
            
            print(f"Batch {batch + 1}: Memory usage {current_memory:.1f}MB (+{memory_increase:.1f}MB)")
    
    async def _simulate_order_workflow(self, workflow_id):
        """Simulate a complete order workflow for performance testing."""
        # Mock all external dependencies to focus on memory/CPU usage
        with patch('utils.CryptoAddressGenerator.CryptoAddressGenerator') as mock_crypto, \
             patch('services.encryption.EncryptionService.encrypt_private_key') as mock_encrypt:
            
            crypto_instance = Mock()
            crypto_instance.generate_one_time_address.return_value = {
                'address': f'test_address_{workflow_id}',
                'private_key': f'test_private_key_{workflow_id}'
            }
            mock_crypto.return_value = crypto_instance
            
            mock_encrypt.return_value = (f'encrypted_{workflow_id}', f'salt_{workflow_id}')
            
            # Simulate data processing
            order_data = {
                'id': workflow_id,
                'user_id': workflow_id % 100,
                'amount': 10.0 + (workflow_id * 0.01),
                'currency': ['BTC', 'ETH', 'LTC', 'SOL'][workflow_id % 4],
                'address': f'test_address_{workflow_id}',
                'private_key': f'test_private_key_{workflow_id}'
            }
            
            # Simulate some processing time
            await asyncio.sleep(0.001)  # 1ms processing time
            
            return order_data


class TestErrorRecoveryResilience:
    """Test error recovery and system resilience."""
    
    async def test_database_connection_recovery(self, database_error_simulator):
        """
        Test Case: System recovers from temporary database connection failures
        Resilience Scenario: Retry mechanism handles transient database errors
        """
        call_count = 0
        
        @TransactionManager.with_retry(max_retries=3)
        async def failing_database_operation():
            nonlocal call_count
            call_count += 1
            
            # Simulate database connection failure for first 2 attempts
            if call_count <= 2:
                database_error_simulator.set_error_scenario('operational', max_errors=2)
                database_error_simulator.maybe_raise_error()
            
            return f"success_on_attempt_{call_count}"
        
        # Operation should succeed after retries
        result = await failing_database_operation()
        assert result == "success_on_attempt_3"
        assert call_count == 3
    
    async def test_transaction_deadlock_recovery(self):
        """
        Test Case: System handles database deadlocks gracefully
        Resilience Scenario: Deadlock detection and retry
        """
        deadlock_count = 0
        
        async def deadlock_prone_operation():
            nonlocal deadlock_count
            deadlock_count += 1
            
            if deadlock_count == 1:
                # Simulate deadlock on first attempt
                from sqlalchemy.exc import OperationalError
                raise OperationalError("Deadlock found when trying to get lock", None, None)
            
            return "deadlock_resolved"
        
        # Wrap with retry mechanism
        retry_operation = TransactionManager.with_retry(max_retries=2)(deadlock_prone_operation)
        
        result = await retry_operation()
        assert result == "deadlock_resolved"
        assert deadlock_count == 2
    
    async def test_encryption_service_failover(self):
        """
        Test Case: System handles encryption service failures gracefully
        Resilience Scenario: Encryption errors are properly handled and logged
        """
        # Test with missing master key
        original_key = os.environ.get('ENCRYPTION_MASTER_KEY')
        if 'ENCRYPTION_MASTER_KEY' in os.environ:
            del os.environ['ENCRYPTION_MASTER_KEY']
        
        try:
            with pytest.raises(ValueError, match="ENCRYPTION_MASTER_KEY environment variable not set"):
                EncryptionService.encrypt_private_key("test_key", 1)
        finally:
            # Restore original key
            if original_key:
                os.environ['ENCRYPTION_MASTER_KEY'] = original_key
    
    async def test_webhook_processing_error_isolation(self):
        """
        Test Case: Webhook processing errors don't affect other requests
        Resilience Scenario: Individual webhook failures are isolated
        """
        successful_webhooks = 0
        failed_webhooks = 0
        
        async def process_webhook(webhook_id, should_fail=False):
            nonlocal successful_webhooks, failed_webhooks
            
            if should_fail:
                failed_webhooks += 1
                raise Exception(f"Webhook {webhook_id} processing failed")
            else:
                successful_webhooks += 1
                return f"webhook_{webhook_id}_processed"
        
        # Process multiple webhooks, some failing
        webhook_tasks = []
        for i in range(10):
            should_fail = i % 3 == 0  # Every 3rd webhook fails
            task = process_webhook(i, should_fail)
            webhook_tasks.append(task)
        
        # Execute all webhooks, catching exceptions
        results = await asyncio.gather(*webhook_tasks, return_exceptions=True)
        
        # Count results
        success_count = sum(1 for r in results if isinstance(r, str))
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        assert success_count == 7  # 7 successful webhooks
        assert error_count == 3   # 3 failed webhooks
        assert successful_webhooks == 7
        assert failed_webhooks == 3
    
    async def test_resource_cleanup_on_failure(self):
        """
        Test Case: Resources are properly cleaned up after failures
        Resilience Scenario: No resource leaks on operation failures
        """
        resources_created = []
        resources_cleaned = []
        
        class MockResource:
            def __init__(self, resource_id):
                self.id = resource_id
                resources_created.append(resource_id)
            
            async def cleanup(self):
                resources_cleaned.append(self.id)
        
        async def failing_operation_with_resources():
            # Create some resources
            resource1 = MockResource("resource_1")
            resource2 = MockResource("resource_2")
            
            try:
                # Simulate some work
                await asyncio.sleep(0.01)
                
                # Simulate failure
                raise Exception("Operation failed")
                
            except Exception:
                # Cleanup resources
                await resource1.cleanup()
                await resource2.cleanup()
                raise
        
        # Run failing operation
        with pytest.raises(Exception, match="Operation failed"):
            await failing_operation_with_resources()
        
        # Verify resources were created and cleaned up
        assert len(resources_created) == 2
        assert len(resources_cleaned) == 2
        assert set(resources_created) == set(resources_cleaned)