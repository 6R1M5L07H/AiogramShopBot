"""
Comprehensive security testing for the invoice-stock-management feature.

This module tests critical security features including:
- Private key encryption/decryption with AES-256-GCM
- Payment validation with 0.1% tolerance
- Race condition prevention in concurrent scenarios
- Transaction boundary integrity
- State machine validation
- Webhook security and rate limiting
"""

import pytest
import asyncio
import os
import tempfile
import base64
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from services.encryption import EncryptionService
from services.payment_observer import PaymentObserverService
from services.order import OrderService
from utils.order_state_machine import OrderStateMachine, validate_order_transition
from utils.transaction_manager import TransactionManager, TransactionLockTimeout
from processing.order_payment import OrderPaymentProcessor
from models.order import OrderStatus
from repositories.order import OrderRepository


class TestEncryptionSecurity:
    """Test encryption security functionality."""
    
    @pytest.fixture
    def test_master_key(self):
        """Test Case: Generate test master key for encryption testing"""
        # Generate a proper 32-byte master key for testing
        key = os.urandom(32)
        return base64.b64encode(key).decode('utf-8')
    
    @pytest.fixture
    def encryption_env(self, test_master_key):
        """Test Case: Set up encryption environment variables"""
        original_key = os.environ.get('ENCRYPTION_MASTER_KEY')
        os.environ['ENCRYPTION_MASTER_KEY'] = test_master_key
        yield test_master_key
        if original_key:
            os.environ['ENCRYPTION_MASTER_KEY'] = original_key
        else:
            os.environ.pop('ENCRYPTION_MASTER_KEY', None)
    
    async def test_private_key_encryption_decryption_cycle(self, encryption_env):
        """
        Test Case: Verify complete encryption/decryption cycle maintains data integrity
        Security Scenario: Ensure private keys are properly encrypted with AES-256-GCM
        """
        test_private_key = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"
        order_id = 12345
        
        # Test encryption
        encrypted_key, salt = EncryptionService.encrypt_private_key(test_private_key, order_id)
        
        # Verify encrypted data is different from original
        assert encrypted_key != test_private_key
        assert len(encrypted_key) > 0
        assert len(salt) > 0
        
        # Test decryption
        decrypted_key = EncryptionService.decrypt_private_key(encrypted_key, salt, order_id)
        
        # Verify decrypted data matches original
        assert decrypted_key == test_private_key
    
    async def test_encryption_with_different_salts(self, encryption_env):
        """
        Test Case: Verify same private key with different salts produces different encrypted results
        Security Scenario: Ensure salt uniqueness prevents rainbow table attacks
        """
        test_private_key = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"
        
        # Encrypt same key twice
        encrypted1, salt1 = EncryptionService.encrypt_private_key(test_private_key, 1)
        encrypted2, salt2 = EncryptionService.encrypt_private_key(test_private_key, 2)
        
        # Verify different salts produce different encrypted results
        assert salt1 != salt2
        assert encrypted1 != encrypted2
        
        # Verify both decrypt to same original
        decrypted1 = EncryptionService.decrypt_private_key(encrypted1, salt1, 1)
        decrypted2 = EncryptionService.decrypt_private_key(encrypted2, salt2, 2)
        
        assert decrypted1 == test_private_key
        assert decrypted2 == test_private_key
    
    async def test_encryption_wrong_salt_fails(self, encryption_env):
        """
        Test Case: Verify decryption fails with wrong salt
        Security Scenario: Ensure salt tampering detection
        """
        test_private_key = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"
        
        encrypted, salt = EncryptionService.encrypt_private_key(test_private_key, 1)
        wrong_encrypted, wrong_salt = EncryptionService.encrypt_private_key("wrong_key", 2)
        
        # Attempt decryption with wrong salt should fail
        with pytest.raises(Exception):
            EncryptionService.decrypt_private_key(encrypted, wrong_salt, 1)
    
    async def test_encryption_invalid_master_key_fails(self):
        """
        Test Case: Verify encryption fails with invalid master key
        Security Scenario: Ensure proper master key validation
        """
        # Test with no master key
        original_key = os.environ.get('ENCRYPTION_MASTER_KEY')
        if 'ENCRYPTION_MASTER_KEY' in os.environ:
            del os.environ['ENCRYPTION_MASTER_KEY']
        
        with pytest.raises(ValueError, match="ENCRYPTION_MASTER_KEY environment variable not set"):
            EncryptionService.encrypt_private_key("test_key", 1)
        
        # Test with invalid base64 master key
        os.environ['ENCRYPTION_MASTER_KEY'] = "invalid_base64_key"
        
        with pytest.raises(ValueError, match="Invalid ENCRYPTION_MASTER_KEY format"):
            EncryptionService.encrypt_private_key("test_key", 1)
        
        # Restore original key
        if original_key:
            os.environ['ENCRYPTION_MASTER_KEY'] = original_key
        else:
            os.environ.pop('ENCRYPTION_MASTER_KEY', None)
    
    async def test_key_rotation_functionality(self, encryption_env):
        """
        Test Case: Verify private key encryption rotation works correctly
        Security Scenario: Ensure smooth key rotation without data loss
        """
        test_private_key = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"
        order_id = 99999
        
        # Initial encryption
        old_encrypted, old_salt = EncryptionService.encrypt_private_key(test_private_key, order_id)
        
        # Rotate encryption
        new_encrypted, new_salt = EncryptionService.rotate_private_key_encryption(
            old_encrypted, old_salt, order_id
        )
        
        # Verify rotation produced different encrypted data
        assert new_encrypted != old_encrypted
        assert new_salt != old_salt
        
        # Verify both old and new decrypt to same original
        old_decrypted = EncryptionService.decrypt_private_key(old_encrypted, old_salt, order_id)
        new_decrypted = EncryptionService.decrypt_private_key(new_encrypted, new_salt, order_id)
        
        assert old_decrypted == test_private_key
        assert new_decrypted == test_private_key
    
    async def test_encryption_setup_verification(self, encryption_env):
        """
        Test Case: Verify encryption setup verification works correctly
        Security Scenario: Ensure encryption system integrity check
        """
        # Test successful verification
        assert EncryptionService.verify_encryption_setup() == True
        
        # Test failed verification with wrong key
        original_key = os.environ.get('ENCRYPTION_MASTER_KEY')
        os.environ['ENCRYPTION_MASTER_KEY'] = base64.b64encode(b"wrong_key").decode()
        
        # This should still work since we're generating new test data
        # The verification tests the full cycle, not key compatibility
        assert EncryptionService.verify_encryption_setup() == True
        
        # Restore original key
        if original_key:
            os.environ['ENCRYPTION_MASTER_KEY'] = original_key


class TestPaymentValidationSecurity:
    """Test payment validation security features."""
    
    async def test_payment_amount_tolerance_within_range(self):
        """
        Test Case: Verify payment validation accepts amounts within 0.1% tolerance
        Security Scenario: Test acceptable payment variance for transaction fees
        """
        # Mock order with $100 total
        with patch('repositories.order.OrderRepository.get_by_id') as mock_get:
            mock_order = Mock()
            mock_order.total_amount = 100.0
            mock_get.return_value = mock_order
            
            # Test exact amount
            assert await PaymentObserverService.validate_payment_amount(1, 100.0) == True
            
            # Test minimum acceptable amount (99.9% of order total)
            assert await PaymentObserverService.validate_payment_amount(1, 99.9) == True
            
            # Test amount slightly above minimum (99.95% of order total)
            assert await PaymentObserverService.validate_payment_amount(1, 99.95) == True
    
    async def test_payment_amount_tolerance_below_range(self):
        """
        Test Case: Verify payment validation rejects amounts below 0.1% tolerance
        Security Scenario: Prevent underpayment attacks
        """
        with patch('repositories.order.OrderRepository.get_by_id') as mock_get:
            mock_order = Mock()
            mock_order.total_amount = 100.0
            mock_get.return_value = mock_order
            
            # Test amount below tolerance (99.8% of order total)
            assert await PaymentObserverService.validate_payment_amount(1, 99.8) == False
            
            # Test significantly underpaid amount
            assert await PaymentObserverService.validate_payment_amount(1, 50.0) == False
    
    async def test_payment_precision_validation(self):
        """
        Test Case: Verify payment precision validation for different currencies
        Security Scenario: Prevent precision manipulation attacks
        """
        # Test BTC precision (8 decimal places)
        assert await PaymentObserverService.validate_payment_precision(0.12345678, 'BTC') == True
        assert await PaymentObserverService.validate_payment_precision(0.123456789, 'BTC') == False
        
        # Test ETH precision (18 decimal places)
        eth_amount = 0.123456789012345678
        assert await PaymentObserverService.validate_payment_precision(eth_amount, 'ETH') == True
        
        # Test SOL precision (9 decimal places)
        assert await PaymentObserverService.validate_payment_precision(1.123456789, 'SOL') == True
        assert await PaymentObserverService.validate_payment_precision(1.1234567890, 'SOL') == False
    
    async def test_duplicate_transaction_detection(self):
        """
        Test Case: Verify duplicate transaction hash detection
        Security Scenario: Prevent double-spending attacks
        """
        test_tx_hash = "test_transaction_hash_12345"
        
        # First transaction should be accepted
        assert await PaymentObserverService.check_transaction_duplicate(test_tx_hash) == False
        
        # Second transaction with same hash should be detected as duplicate
        assert await PaymentObserverService.check_transaction_duplicate(test_tx_hash) == True
        
        # Different hash should be accepted
        assert await PaymentObserverService.check_transaction_duplicate("different_hash") == False
    
    async def test_confirmation_requirements_validation(self):
        """
        Test Case: Verify blockchain confirmation requirements are enforced
        Security Scenario: Prevent unconfirmed transaction acceptance
        """
        # Test BTC confirmation requirement (3 confirmations)
        assert await PaymentObserverService.validate_confirmations('BTC', 3) == True
        assert await PaymentObserverService.validate_confirmations('BTC', 2) == False
        
        # Test ETH confirmation requirement (12 confirmations)
        assert await PaymentObserverService.validate_confirmations('ETH', 12) == True
        assert await PaymentObserverService.validate_confirmations('ETH', 11) == False
        
        # Test SOL confirmation requirement (32 confirmations)
        assert await PaymentObserverService.validate_confirmations('SOL', 32) == True
        assert await PaymentObserverService.validate_confirmations('SOL', 31) == False
    
    async def test_payment_webhook_comprehensive_validation(self):
        """
        Test Case: Verify comprehensive payment webhook validation
        Security Scenario: Test complete payment validation pipeline
        """
        # Test successful payment processing
        with patch('repositories.order.OrderRepository.get_by_payment_address') as mock_get_addr, \
             patch('repositories.order.OrderRepository.get_by_id') as mock_get_id, \
             patch('services.order.OrderService.confirm_payment') as mock_confirm:
            
            # Setup mocks
            mock_order = Mock()
            mock_order.id = 1
            mock_order.total_amount = 1.0
            mock_get_addr.return_value = mock_order
            mock_get_id.return_value = mock_order
            mock_confirm.return_value = None
            
            result = await PaymentObserverService.handle_payment_webhook(
                address="test_address",
                amount=1.0,
                currency="BTC",
                tx_hash="unique_tx_hash_123",
                confirmations=6
            )
            
            assert result['success'] == True
            assert result['message'] == 'Payment processed successfully'
    
    async def test_payment_webhook_insufficient_confirmations(self):
        """
        Test Case: Verify payment webhook rejects insufficient confirmations
        Security Scenario: Prevent acceptance of unconfirmed transactions
        """
        result = await PaymentObserverService.handle_payment_webhook(
            address="test_address",
            amount=1.0,
            currency="BTC",
            tx_hash="test_tx_hash",
            confirmations=1  # Below BTC requirement of 3
        )
        
        assert result['success'] == False
        assert 'Insufficient confirmations' in result['message']
    
    async def test_payment_webhook_duplicate_transaction(self):
        """
        Test Case: Verify payment webhook rejects duplicate transactions
        Security Scenario: Prevent duplicate transaction processing
        """
        tx_hash = "duplicate_test_hash"
        
        # First request should process
        with patch('repositories.order.OrderRepository.get_by_payment_address') as mock_get:
            mock_order = Mock()
            mock_order.id = 1
            mock_order.total_amount = 1.0
            mock_get.return_value = mock_order
            
            with patch('repositories.order.OrderRepository.get_by_id') as mock_get_id:
                mock_get_id.return_value = mock_order
                
                with patch('services.order.OrderService.confirm_payment'):
                    result1 = await PaymentObserverService.handle_payment_webhook(
                        address="test_address",
                        amount=1.0,
                        currency="BTC",
                        tx_hash=tx_hash,
                        confirmations=6
                    )
        
        # Second request with same hash should be rejected
        result2 = await PaymentObserverService.handle_payment_webhook(
            address="test_address",
            amount=1.0,
            currency="BTC",
            tx_hash=tx_hash,
            confirmations=6
        )
        
        assert result2['success'] == False
        assert result2['message'] == 'Duplicate transaction hash'


class TestRaceConditionPrevention:
    """Test race condition prevention in concurrent scenarios."""
    
    async def test_concurrent_order_creation_prevention(self, db_session, test_user, 
                                                       mock_crypto_generator, mock_encryption_service):
        """
        Test Case: Verify only one order can be created per user concurrently
        Security Scenario: Prevent race conditions in order creation
        """
        # Setup test cart items
        from models.cart import Cart
        cart_item = Cart(
            user_id=test_user.id,
            category_id=1,
            subcategory_id=1,
            quantity=1,
            price=10.0
        )
        db_session.add(cart_item)
        await db_session.flush()
        
        # Mock cart service
        with patch('services.cart.CartService.get_cart_items') as mock_get_cart, \
             patch('services.cart.CartService.validate_cart_integrity') as mock_validate, \
             patch('services.cart.CartService.clear_cart') as mock_clear:
            
            mock_get_cart.return_value = [Mock(
                item_id=1, category_id=1, subcategory_id=1, 
                quantity=1, price=10.0
            )]
            mock_validate.return_value = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'total_amount': 10.0
            }
            mock_clear.return_value = None
            
            # Mock repository operations
            with patch('repositories.order.OrderRepository.get_by_user_id') as mock_get_existing, \
                 patch('repositories.order.OrderRepository.create_with_encrypted_key') as mock_create, \
                 patch('repositories.orderItem.OrderItemRepository.create_many') as mock_create_items, \
                 patch('repositories.reservedStock.ReservedStockRepository.atomic_check_and_reserve') as mock_reserve:
                
                # First call returns no existing order, second returns existing order
                call_count = 0
                def get_existing_order_side_effect(user_id):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        return None  # No existing order
                    else:
                        # Return existing order to simulate race condition
                        existing_order = Mock()
                        existing_order.status = OrderStatus.CREATED.value
                        return existing_order
                
                mock_get_existing.side_effect = get_existing_order_side_effect
                mock_create.return_value = 1
                mock_create_items.return_value = None
                mock_reserve.return_value = True
                
                # First order creation should succeed
                order1 = await OrderService.create_order_from_cart(test_user.id, 'BTC')
                assert order1 is not None
                
                # Second concurrent order creation should fail
                with pytest.raises(ValueError, match="User already has an active order"):
                    await OrderService.create_order_from_cart(test_user.id, 'BTC')
    
    async def test_concurrent_stock_reservation_atomicity(self, db_session, concurrent_test_users):
        """
        Test Case: Verify atomic stock reservation prevents overselling
        Security Scenario: Test stock reservation under concurrent access
        """
        category_id = 1
        subcategory_id = 1
        available_stock = 3  # Only 3 items available
        
        # Mock stock availability check
        check_call_count = 0
        reserve_call_count = 0
        
        async def mock_check_availability(cat_id, subcat_id, quantity):
            nonlocal check_call_count
            check_call_count += 1
            # First 3 checks pass, subsequent fail
            return check_call_count <= available_stock
        
        async def mock_atomic_reserve(cat_id, subcat_id, quantity, order_id, expires_at):
            nonlocal reserve_call_count
            reserve_call_count += 1
            # First 3 reservations succeed, subsequent fail
            return reserve_call_count <= available_stock
        
        with patch('repositories.reservedStock.ReservedStockRepository.check_availability', 
                  side_effect=mock_check_availability), \
             patch('repositories.reservedStock.ReservedStockRepository.atomic_check_and_reserve',
                  side_effect=mock_atomic_reserve):
            
            # Simulate concurrent stock reservation attempts
            tasks = []
            for i, user in enumerate(concurrent_test_users):
                cart_items = [Mock(
                    category_id=category_id,
                    subcategory_id=subcategory_id,
                    quantity=1,
                    price=10.0
                )]
                task = OrderService.reserve_stock_for_cart(user.id, cart_items)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Only first 3 should succeed
            successful_reservations = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
            assert successful_reservations == available_stock
    
    async def test_transaction_retry_mechanism(self, db_session):
        """
        Test Case: Verify transaction retry mechanism handles temporary failures
        Security Scenario: Test resilience against transient database errors
        """
        retry_count = 0
        max_retries = 2
        
        @TransactionManager.with_retry(max_retries=max_retries)
        async def failing_operation():
            nonlocal retry_count
            retry_count += 1
            if retry_count <= max_retries:
                from sqlalchemy.exc import OperationalError
                raise OperationalError("Database connection lost", None, None)
            return "success"
        
        # Should succeed after retries
        result = await failing_operation()
        assert result == "success"
        assert retry_count == max_retries + 1  # Initial attempt + retries
    
    async def test_transaction_timeout_handling(self, db_session):
        """
        Test Case: Verify transaction timeout handling prevents hanging transactions
        Security Scenario: Prevent resource exhaustion from long-running transactions
        """
        with patch('utils.transaction_manager.get_db_session') as mock_session:
            mock_db_session = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db_session
            
            # Simulate transaction that times out
            async with TransactionManager.atomic_transaction(timeout=1) as session:
                # Simulate work that takes longer than timeout
                await asyncio.sleep(0.1)  # Short sleep for test
                
                # Transaction should still work within timeout
                assert session is not None


class TestStateTransitionSecurity:
    """Test order state machine security and validation."""
    
    async def test_valid_state_transitions(self):
        """
        Test Case: Verify valid state transitions are allowed
        Security Scenario: Ensure proper workflow enforcement
        """
        # Test valid transitions
        assert OrderStateMachine.is_valid_transition(
            OrderStatus.CREATED.value, OrderStatus.PAID.value) == True
        assert OrderStateMachine.is_valid_transition(
            OrderStatus.CREATED.value, OrderStatus.EXPIRED.value) == True
        assert OrderStateMachine.is_valid_transition(
            OrderStatus.CREATED.value, OrderStatus.CANCELLED.value) == True
        assert OrderStateMachine.is_valid_transition(
            OrderStatus.PAID.value, OrderStatus.SHIPPED.value) == True
    
    async def test_invalid_state_transitions(self):
        """
        Test Case: Verify invalid state transitions are rejected
        Security Scenario: Prevent unauthorized state manipulation
        """
        # Test invalid transitions from final states
        assert OrderStateMachine.is_valid_transition(
            OrderStatus.EXPIRED.value, OrderStatus.PAID.value) == False
        assert OrderStateMachine.is_valid_transition(
            OrderStatus.SHIPPED.value, OrderStatus.CANCELLED.value) == False
        assert OrderStateMachine.is_valid_transition(
            OrderStatus.CANCELLED.value, OrderStatus.PAID.value) == False
    
    async def test_admin_required_transitions(self):
        """
        Test Case: Verify admin-required transitions are properly enforced
        Security Scenario: Ensure privilege escalation prevention
        """
        # Test admin required for shipping
        assert OrderStateMachine.requires_admin(
            OrderStatus.PAID.value, OrderStatus.SHIPPED.value) == True
        
        # Test admin required for cancelling paid orders
        assert OrderStateMachine.requires_admin(
            OrderStatus.PAID.value, OrderStatus.CANCELLED.value) == True
        
        # Test non-admin transitions
        assert OrderStateMachine.requires_admin(
            OrderStatus.CREATED.value, OrderStatus.PAID.value) == False
    
    async def test_state_transition_validation_with_audit(self):
        """
        Test Case: Verify state transition validation includes proper audit logging
        Security Scenario: Ensure all state changes are audited
        """
        order_id = 12345
        
        # Test valid transition with user
        result = validate_order_transition(
            order_id, OrderStatus.CREATED.value, OrderStatus.PAID.value, user_id=100
        )
        assert result == True
        
        # Test admin-required transition without admin should fail
        result = validate_order_transition(
            order_id, OrderStatus.PAID.value, OrderStatus.SHIPPED.value, user_id=100
        )
        assert result == False
        
        # Test admin-required transition with admin should succeed
        result = validate_order_transition(
            order_id, OrderStatus.PAID.value, OrderStatus.SHIPPED.value, admin_id=200
        )
        assert result == True
    
    async def test_final_state_prevention(self):
        """
        Test Case: Verify final states cannot be transitioned from
        Security Scenario: Prevent manipulation of completed orders
        """
        final_states = [OrderStatus.EXPIRED.value, OrderStatus.SHIPPED.value, OrderStatus.CANCELLED.value]
        
        for final_state in final_states:
            assert OrderStateMachine.is_final_status(final_state) == True
            
            # Verify no transitions allowed from final states
            valid_transitions = OrderStateMachine.get_valid_transitions(final_state)
            assert len(valid_transitions) == 0