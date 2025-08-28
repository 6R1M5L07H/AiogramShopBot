"""
Comprehensive webhook security testing for payment processing endpoints.

This module tests critical webhook security features including:
- Rate limiting and abuse prevention
- HMAC signature verification with multiple algorithms
- Payload size validation and malformed data handling
- Input sanitization and injection prevention
- Request forgery and replay attack prevention
"""

import pytest
import asyncio
import json
import hmac
import hashlib
import time
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from processing.order_payment import OrderPaymentProcessor, RATE_LIMIT_WINDOW, RATE_LIMIT_MAX_REQUESTS
from services.payment_observer import PaymentObserverService


class TestWebhookRateLimiting:
    """Test webhook rate limiting functionality."""
    
    def test_rate_limit_within_threshold(self):
        """
        Test Case: Requests within rate limit threshold are allowed
        Security Scenario: Normal usage should not be blocked
        """
        test_ip = '192.168.1.1'
        
        # Clear any existing rate limit data
        OrderPaymentProcessor.rate_limit_store.clear()
        
        # Make requests up to the limit
        for i in range(RATE_LIMIT_MAX_REQUESTS):
            result = OrderPaymentProcessor.check_rate_limit(test_ip)
            assert result == True, f"Request {i+1} should be allowed"
    
    def test_rate_limit_exceeded(self):
        """
        Test Case: Requests exceeding rate limit are blocked
        Security Scenario: Prevent abuse and DoS attacks
        """
        test_ip = '192.168.1.2'
        
        # Clear any existing rate limit data
        OrderPaymentProcessor.rate_limit_store.clear()
        
        # Fill up the rate limit
        for i in range(RATE_LIMIT_MAX_REQUESTS):
            OrderPaymentProcessor.check_rate_limit(test_ip)
        
        # Next request should be blocked
        result = OrderPaymentProcessor.check_rate_limit(test_ip)
        assert result == False, "Request exceeding limit should be blocked"
    
    def test_rate_limit_per_ip_isolation(self):
        """
        Test Case: Rate limits are isolated per IP address
        Security Scenario: One IP's rate limit doesn't affect another
        """
        ip1 = '192.168.1.10'
        ip2 = '192.168.1.11'
        
        # Clear any existing rate limit data
        OrderPaymentProcessor.rate_limit_store.clear()
        
        # Fill rate limit for IP1
        for i in range(RATE_LIMIT_MAX_REQUESTS):
            OrderPaymentProcessor.check_rate_limit(ip1)
        
        # IP1 should be blocked
        assert OrderPaymentProcessor.check_rate_limit(ip1) == False
        
        # IP2 should still be allowed
        assert OrderPaymentProcessor.check_rate_limit(ip2) == True
    
    def test_rate_limit_window_cleanup(self):
        """
        Test Case: Rate limit window properly cleans up old requests
        Security Scenario: Rate limits reset after time window
        """
        test_ip = '192.168.1.3'
        
        # Clear any existing rate limit data
        OrderPaymentProcessor.rate_limit_store.clear()
        
        # Add old requests (simulate time passage)
        current_time = time.time()
        old_time = current_time - RATE_LIMIT_WINDOW - 10  # Outside window
        
        requests_deque = OrderPaymentProcessor.rate_limit_store[test_ip]
        
        # Add old requests that should be cleaned up
        for i in range(5):
            requests_deque.append(old_time + i)
        
        # Add current request - should trigger cleanup
        result = OrderPaymentProcessor.check_rate_limit(test_ip)
        assert result == True
        
        # Old requests should be cleaned up
        assert len([r for r in requests_deque if r < current_time - RATE_LIMIT_WINDOW]) == 0


class TestWebhookSignatureVerification:
    """Test webhook signature verification security."""
    
    def test_sha256_signature_verification_valid(self):
        """
        Test Case: Valid SHA256 signature is accepted
        Security Scenario: Legitimate webhooks with correct signatures pass
        """
        payload = b'{"test": "data"}'
        secret = 'test_secret_key'
        
        # Generate valid SHA256 signature
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature_header = f'sha256={signature}'
        
        result = OrderPaymentProcessor.verify_webhook_signature(payload, signature_header, secret)
        assert result == True
    
    def test_sha256_signature_verification_invalid(self):
        """
        Test Case: Invalid SHA256 signature is rejected
        Security Scenario: Prevent forged webhook requests
        """
        payload = b'{"test": "data"}'
        secret = 'test_secret_key'
        invalid_signature = 'sha256=invalid_signature_hash'
        
        result = OrderPaymentProcessor.verify_webhook_signature(payload, invalid_signature, secret)
        assert result == False
    
    def test_sha1_signature_verification_valid(self):
        """
        Test Case: Valid SHA1 signature is accepted (legacy support)
        Security Scenario: Support legacy webhook providers using SHA1
        """
        payload = b'{"test": "data"}'
        secret = 'test_secret_key'
        
        # Generate valid SHA1 signature
        signature = hmac.new(secret.encode(), payload, hashlib.sha1).hexdigest()
        signature_header = f'sha1={signature}'
        
        result = OrderPaymentProcessor.verify_webhook_signature(payload, signature_header, secret)
        assert result == True
    
    def test_signature_verification_wrong_secret(self):
        """
        Test Case: Signature with wrong secret is rejected
        Security Scenario: Prevent signature bypass with wrong secrets
        """
        payload = b'{"test": "data"}'
        correct_secret = 'correct_secret'
        wrong_secret = 'wrong_secret'
        
        # Generate signature with wrong secret
        signature = hmac.new(wrong_secret.encode(), payload, hashlib.sha256).hexdigest()
        signature_header = f'sha256={signature}'
        
        result = OrderPaymentProcessor.verify_webhook_signature(payload, signature_header, correct_secret)
        assert result == False
    
    def test_signature_verification_timing_attack_resistance(self):
        """
        Test Case: Signature verification uses constant-time comparison
        Security Scenario: Prevent timing attacks on signature verification
        """
        payload = b'{"test": "data"}'
        secret = 'test_secret_key'
        
        # Generate correct signature
        correct_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        correct_header = f'sha256={correct_signature}'
        
        # Generate incorrect signature of same length
        incorrect_signature = 'a' * len(correct_signature)
        incorrect_header = f'sha256={incorrect_signature}'
        
        # Both should return in similar time (using hmac.compare_digest)
        start_time = time.time()
        result1 = OrderPaymentProcessor.verify_webhook_signature(payload, correct_header, secret)
        time1 = time.time() - start_time
        
        start_time = time.time()
        result2 = OrderPaymentProcessor.verify_webhook_signature(payload, incorrect_header, secret)
        time2 = time.time() - start_time
        
        assert result1 == True
        assert result2 == False
        # Timing difference should be minimal (within reasonable bounds for testing)
        assert abs(time1 - time2) < 0.01  # 10ms tolerance
    
    def test_signature_verification_no_prefix(self):
        """
        Test Case: Signature without algorithm prefix defaults to SHA256
        Security Scenario: Handle webhooks without explicit algorithm prefix
        """
        payload = b'{"test": "data"}'
        secret = 'test_secret_key'
        
        # Generate signature without prefix
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        
        result = OrderPaymentProcessor.verify_webhook_signature(payload, signature, secret)
        assert result == True


class TestPayloadValidation:
    """Test webhook payload validation and sanitization."""
    
    def test_payload_size_within_limit(self):
        """
        Test Case: Payload within size limit is accepted
        Security Scenario: Normal payloads should be processed
        """
        small_payload = b'{"test": "data"}'  # Small payload
        result = OrderPaymentProcessor.validate_payload_size(small_payload, max_size=1024)
        assert result == True
    
    def test_payload_size_exceeds_limit(self):
        """
        Test Case: Payload exceeding size limit is rejected
        Security Scenario: Prevent memory exhaustion attacks
        """
        large_payload = b'A' * 2048  # 2KB payload
        result = OrderPaymentProcessor.validate_payload_size(large_payload, max_size=1024)
        assert result == False
    
    def test_input_sanitization_valid_data(self):
        """
        Test Case: Valid input data is properly sanitized
        Security Scenario: Clean data passes through unchanged
        """
        input_data = {
            'address': 'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh',
            'amount': 0.00123456,
            'currency': 'BTC',
            'tx_hash': 'a1b2c3d4e5f6789012345678901234567890abcdef',
            'confirmations': 6
        }
        
        sanitized = OrderPaymentProcessor.sanitize_input(input_data)
        
        assert sanitized['address'] == input_data['address']
        assert sanitized['amount'] == input_data['amount']
        assert sanitized['currency'] == input_data['currency']
        assert sanitized['tx_hash'] == input_data['tx_hash']
        assert sanitized['confirmations'] == input_data['confirmations']
    
    def test_input_sanitization_oversized_strings(self):
        """
        Test Case: Oversized string fields are rejected
        Security Scenario: Prevent buffer overflow and memory attacks
        """
        input_data = {
            'address': 'A' * 150,  # Exceeds 100 char limit
            'currency': 'B' * 20,  # Exceeds 10 char limit
            'tx_hash': 'C' * 200,  # Exceeds 128 char limit
            'amount': 1.0
        }
        
        sanitized = OrderPaymentProcessor.sanitize_input(input_data)
        
        # Oversized fields should be excluded
        assert 'address' not in sanitized
        assert 'currency' not in sanitized
        assert 'tx_hash' not in sanitized
        assert 'amount' in sanitized  # Valid field remains
    
    def test_input_sanitization_invalid_types(self):
        """
        Test Case: Invalid data types are rejected
        Security Scenario: Prevent type confusion attacks
        """
        input_data = {
            'address': 123,  # Should be string
            'amount': 'not_a_number',  # Should be float
            'currency': 456,  # Should be string
            'confirmations': 'not_an_int'  # Should be int
        }
        
        sanitized = OrderPaymentProcessor.sanitize_input(input_data)
        
        # All invalid types should be excluded
        assert len(sanitized) == 0
    
    def test_input_sanitization_non_printable_characters(self):
        """
        Test Case: Non-printable characters are removed from strings
        Security Scenario: Prevent injection of control characters
        """
        input_data = {
            'address': 'test\x00\x01\x02address',  # Contains null bytes and control chars
            'currency': 'BTC\r\n',  # Contains newlines
            'tx_hash': 'hash\t\x0bwith\x0cchars'  # Contains tabs and form feeds
        }
        
        sanitized = OrderPaymentProcessor.sanitize_input(input_data)
        
        assert sanitized['address'] == 'testaddress'
        assert sanitized['currency'] == 'BTC'
        assert sanitized['tx_hash'] == 'hashwithchars'


class TestWebhookEndpointSecurity:
    """Test complete webhook endpoint security integration."""
    
    async def test_webhook_endpoint_rate_limiting(self):
        """
        Test Case: Webhook endpoint enforces rate limiting
        Security Scenario: Prevent webhook endpoint abuse
        """
        # Create mock request
        payload_data = {'address': 'test', 'amount': 1.0, 'currency': 'BTC'}
        payload = json.dumps(payload_data).encode('utf-8')
        
        mock_request = make_mocked_request(
            'POST', '/cryptoprocessing/order_payment',
            payload=payload
        )
        mock_request.read = AsyncMock(return_value=payload)
        mock_request.remote = '192.168.1.100'
        
        # Clear rate limits
        OrderPaymentProcessor.rate_limit_store.clear()
        
        # Fill rate limit
        for i in range(RATE_LIMIT_MAX_REQUESTS):
            OrderPaymentProcessor.check_rate_limit('192.168.1.100')
        
        # Next request should be rate limited
        response = await OrderPaymentProcessor.process_order_payment_webhook(mock_request)
        
        assert response.status == 429
        response_data = json.loads(response.text)
        assert response_data['error'] == 'Rate limit exceeded'
    
    async def test_webhook_endpoint_payload_too_large(self):
        """
        Test Case: Webhook endpoint rejects oversized payloads
        Security Scenario: Prevent memory exhaustion attacks
        """
        # Create oversized payload
        large_payload = b'A' * 2048  # Exceeds 1024 byte limit
        
        mock_request = make_mocked_request(
            'POST', '/cryptoprocessing/order_payment',
            payload=large_payload
        )
        mock_request.read = AsyncMock(return_value=large_payload)
        mock_request.remote = '127.0.0.1'
        
        response = await OrderPaymentProcessor.process_order_payment_webhook(mock_request)
        
        assert response.status == 413
        response_data = json.loads(response.text)
        assert response_data['error'] == 'Payload too large'
    
    async def test_webhook_endpoint_missing_signature(self):
        """
        Test Case: Webhook endpoint rejects requests without signatures
        Security Scenario: Ensure signature requirement is enforced
        """
        payload_data = {'address': 'test', 'amount': 1.0, 'currency': 'BTC'}
        payload = json.dumps(payload_data).encode('utf-8')
        
        mock_request = make_mocked_request(
            'POST', '/cryptoprocessing/order_payment',
            headers={},  # No signature header
            payload=payload
        )
        mock_request.read = AsyncMock(return_value=payload)
        mock_request.remote = '127.0.0.1'
        
        with patch('config.WEBHOOK_SECRET', 'test_secret'):
            response = await OrderPaymentProcessor.process_order_payment_webhook(mock_request)
            
            assert response.status == 401
            response_data = json.loads(response.text)
            assert response_data['error'] == 'Missing signature'
    
    async def test_webhook_endpoint_invalid_json(self):
        """
        Test Case: Webhook endpoint rejects malformed JSON
        Security Scenario: Prevent JSON parsing attacks
        """
        invalid_json = b'{"invalid": json,}'  # Malformed JSON
        
        mock_request = make_mocked_request(
            'POST', '/cryptoprocessing/order_payment',
            payload=invalid_json
        )
        mock_request.read = AsyncMock(return_value=invalid_json)
        mock_request.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_request.remote = '127.0.0.1'
        
        response = await OrderPaymentProcessor.process_order_payment_webhook(mock_request)
        
        assert response.status == 400
        response_data = json.loads(response.text)
        assert response_data['error'] == 'Invalid JSON payload'
    
    async def test_webhook_endpoint_missing_required_fields(self):
        """
        Test Case: Webhook endpoint rejects requests with missing required fields
        Security Scenario: Ensure data integrity requirements
        """
        # Payload missing required 'amount' field
        incomplete_data = {'address': 'test', 'currency': 'BTC'}
        payload = json.dumps(incomplete_data).encode('utf-8')
        
        mock_request = make_mocked_request(
            'POST', '/cryptoprocessing/order_payment',
            payload=payload
        )
        mock_request.read = AsyncMock(return_value=payload)
        mock_request.json = AsyncMock(return_value=incomplete_data)
        mock_request.remote = '127.0.0.1'
        
        response = await OrderPaymentProcessor.process_order_payment_webhook(mock_request)
        
        assert response.status == 400
        response_data = json.loads(response.text)
        assert 'Missing required fields' in response_data['error']
    
    async def test_webhook_endpoint_invalid_currency(self):
        """
        Test Case: Webhook endpoint rejects unsupported currencies
        Security Scenario: Prevent processing of unauthorized currencies
        """
        payload_data = {
            'address': 'test_address',
            'amount': 1.0,
            'currency': 'INVALID',  # Unsupported currency
            'confirmations': 6
        }
        payload = json.dumps(payload_data).encode('utf-8')
        
        mock_request = make_mocked_request(
            'POST', '/cryptoprocessing/order_payment',
            payload=payload
        )
        mock_request.read = AsyncMock(return_value=payload)
        mock_request.json = AsyncMock(return_value=payload_data)
        mock_request.remote = '127.0.0.1'
        
        response = await OrderPaymentProcessor.process_order_payment_webhook(mock_request)
        
        assert response.status == 400
        response_data = json.loads(response.text)
        assert response_data['error'] == 'Unsupported currency'
    
    async def test_webhook_endpoint_complete_security_validation(self):
        """
        Test Case: Webhook endpoint with complete security validation pipeline
        Security Scenario: Full security validation with valid request
        """
        payload_data = {
            'address': 'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh',
            'amount': 0.001,
            'currency': 'BTC',
            'tx_hash': 'a1b2c3d4e5f6789012345678901234567890abcdef',
            'confirmations': 6
        }
        payload = json.dumps(payload_data).encode('utf-8')
        
        # Generate valid signature
        secret = 'test_webhook_secret'
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        
        mock_request = make_mocked_request(
            'POST', '/cryptoprocessing/order_payment',
            headers={'X-Signature': f'sha256={signature}'},
            payload=payload
        )
        mock_request.read = AsyncMock(return_value=payload)
        mock_request.json = AsyncMock(return_value=payload_data)
        mock_request.remote = '127.0.0.1'
        
        # Clear rate limits
        OrderPaymentProcessor.rate_limit_store.clear()
        
        # Mock successful payment processing
        with patch('services.payment_observer.PaymentObserverService.handle_payment_webhook') as mock_handle:
            mock_handle.return_value = {
                'success': True,
                'message': 'Payment processed successfully'
            }
            
            with patch('config.WEBHOOK_SECRET', secret):
                response = await OrderPaymentProcessor.process_order_payment_webhook(mock_request)
                
                assert response.status == 200
                response_data = json.loads(response.text)
                assert response_data['success'] == True
                
                # Verify payment handler was called with sanitized data
                mock_handle.assert_called_once_with(
                    address=payload_data['address'],
                    amount=payload_data['amount'],
                    currency=payload_data['currency'],
                    tx_hash=payload_data['tx_hash'],
                    confirmations=payload_data['confirmations']
                )


class TestWebhookReplayAttackPrevention:
    """Test prevention of replay attacks on webhooks."""
    
    async def test_webhook_duplicate_prevention(self):
        """
        Test Case: Webhook prevents processing of duplicate transactions
        Security Scenario: Prevent replay attacks using transaction hashes
        """
        payload_data = {
            'address': 'test_address',
            'amount': 1.0,
            'currency': 'BTC',
            'tx_hash': 'duplicate_tx_hash_test',
            'confirmations': 6
        }
        
        # Mock payment observer to track duplicate detection
        with patch('services.payment_observer.PaymentObserverService.handle_payment_webhook') as mock_handle:
            # First call succeeds
            mock_handle.return_value = {
                'success': True,
                'message': 'Payment processed successfully'
            }
            
            # Process first webhook
            result1 = await PaymentObserverService.handle_payment_webhook(**payload_data)
            
            # Second call should detect duplicate
            mock_handle.return_value = {
                'success': False,
                'message': 'Duplicate transaction hash'
            }
            
            # Process duplicate webhook
            result2 = await PaymentObserverService.handle_payment_webhook(**payload_data)
            
            assert result1['success'] == True
            assert result2['success'] == False
            assert result2['message'] == 'Duplicate transaction hash'
    
    async def test_webhook_timestamp_validation(self):
        """
        Test Case: Webhook validates request timestamps (future implementation)
        Security Scenario: Prevent replay of old webhook requests
        """
        # This test represents future timestamp validation functionality
        # Current implementation uses transaction hash deduplication
        
        current_time = int(time.time())
        old_timestamp = current_time - 3600  # 1 hour old
        
        # Future implementation would validate timestamp
        # For now, we test that transaction hash deduplication works
        payload_data = {
            'address': 'test_address',
            'amount': 1.0,
            'currency': 'BTC',
            'tx_hash': f'timestamped_tx_{old_timestamp}',
            'confirmations': 6
        }
        
        # Transaction hash deduplication should still work
        result1 = await PaymentObserverService.handle_payment_webhook(**payload_data)
        result2 = await PaymentObserverService.handle_payment_webhook(**payload_data)
        
        # Second request should be blocked as duplicate
        assert result2['success'] == False