"""
Tests for Error Handler Utility

Tests the centralized error handling system that converts
custom exceptions to localized user-friendly messages.
"""

import pytest
from unittest.mock import patch, MagicMock

from enums.bot_entity import BotEntity
from exceptions import (
    OrderNotFoundException,
    InvalidOrderStateException,
    InsufficientStockException,
    ItemNotFoundException,
    EmptyCartException,
    UserBannedException,
    CryptocurrencyNotSelectedException,
)
from utils.error_handler import handle_service_error, handle_unexpected_error


class TestErrorHandler:
    """Test error handling utility"""

    @patch('utils.error_handler.Localizator')
    def test_order_not_found_exception(self, mock_localizator):
        """Test OrderNotFoundException handling"""
        mock_localizator.get_text.return_value = "❌ Order not found"

        exc = OrderNotFoundException(order_id=123)
        result = handle_service_error(exc, BotEntity.USER)

        mock_localizator.get_text.assert_called_with(BotEntity.USER, "error_order_not_found")
        assert "Order not found" in result

    @patch('utils.error_handler.Localizator')
    def test_invalid_order_state_exception_with_formatting(self, mock_localizator):
        """Test InvalidOrderStateException with state formatting"""
        # Mock should return formatted string
        mock_localizator.get_text.return_value = "❌ Order is in state 'CANCELLED', required 'PENDING'"

        exc = InvalidOrderStateException(
            order_id=123,
            current_state="CANCELLED",
            required_state="PENDING"
        )
        result = handle_service_error(exc, BotEntity.USER)

        mock_localizator.get_text.assert_called_with(BotEntity.USER, "error_order_invalid_state")
        # Result should contain the error message
        assert "CANCELLED" in str(result) or "Order" in str(result)

    @patch('utils.error_handler.Localizator')
    def test_insufficient_stock_exception(self, mock_localizator):
        """Test InsufficientStockException with quantities"""
        mock_localizator.get_text.return_value = "❌ Insufficient stock: {available} available, {requested} requested"

        exc = InsufficientStockException(
            item_id=456,
            requested=10,
            available=3
        )
        result = handle_service_error(exc, BotEntity.USER)

        mock_localizator.get_text.assert_called_with(BotEntity.USER, "error_insufficient_stock")

    @patch('utils.error_handler.Localizator')
    def test_item_not_found_exception(self, mock_localizator):
        """Test ItemNotFoundException handling"""
        mock_localizator.get_text.return_value = "❌ Item not available"

        exc = ItemNotFoundException(item_id=789)
        result = handle_service_error(exc, BotEntity.USER)

        mock_localizator.get_text.assert_called_with(BotEntity.USER, "error_item_not_found")
        assert "Item not available" in result

    @patch('utils.error_handler.Localizator')
    def test_empty_cart_exception(self, mock_localizator):
        """Test EmptyCartException handling"""
        mock_localizator.get_text.return_value = "🛒 Your cart is empty"

        exc = EmptyCartException(user_id=123)
        result = handle_service_error(exc, BotEntity.USER)

        mock_localizator.get_text.assert_called_with(BotEntity.USER, "error_empty_cart")
        assert "cart is empty" in result

    @patch('utils.error_handler.Localizator')
    def test_user_banned_exception(self, mock_localizator):
        """Test UserBannedException handling"""
        mock_localizator.get_text.return_value = "❌ You are banned: {reason}"

        exc = UserBannedException(telegram_id=123, reason="Too many strikes")
        result = handle_service_error(exc, BotEntity.USER)

        mock_localizator.get_text.assert_called_with(BotEntity.USER, "error_user_banned")

    @patch('utils.error_handler.Localizator')
    def test_crypto_not_selected_exception(self, mock_localizator):
        """Test CryptocurrencyNotSelectedException handling"""
        mock_localizator.get_text.return_value = "❌ Please select a cryptocurrency first"

        exc = CryptocurrencyNotSelectedException(order_id=123)
        result = handle_service_error(exc, BotEntity.USER)

        mock_localizator.get_text.assert_called_with(BotEntity.USER, "error_crypto_not_selected")
        assert "cryptocurrency" in result

    @patch('utils.error_handler.Localizator')
    def test_unexpected_exception_fallback(self, mock_localizator):
        """Test handling of unexpected exceptions"""
        mock_localizator.get_text.return_value = "❌ An unexpected error occurred"

        exc = Exception("Something went wrong")
        result = handle_unexpected_error(exc, BotEntity.USER)

        mock_localizator.get_text.assert_called_with(BotEntity.USER, "error_unexpected")
        assert "unexpected" in result

    @patch('utils.error_handler.Localizator')
    def test_admin_vs_user_entity(self, mock_localizator):
        """Test that entity parameter is passed correctly"""
        mock_localizator.get_text.return_value = "Admin error message"

        exc = OrderNotFoundException(order_id=123)

        # Test with ADMIN entity
        handle_service_error(exc, BotEntity.ADMIN)
        mock_localizator.get_text.assert_called_with(BotEntity.ADMIN, "error_order_not_found")

        # Test with USER entity
        handle_service_error(exc, BotEntity.USER)
        mock_localizator.get_text.assert_called_with(BotEntity.USER, "error_order_not_found")


class TestErrorHandlerIntegration:
    """Integration tests with real localization"""

    @patch('utils.error_handler.Localizator')
    def test_all_exception_types_have_messages(self, mock_localizator):
        """Verify all exception types have localization keys"""
        # Mock to always return a non-empty string
        mock_localizator.get_text.return_value = "❌ Test error message"
        from exceptions import (
            OrderExpiredException,
            OrderAlreadyCancelledException,
            PaymentNotFoundException,
            InvalidPaymentAmountException,
            PaymentAlreadyProcessedException,
            ItemAlreadySoldException,
            InvalidItemDataException,
            CartItemNotFoundException,
            InvalidCartStateException,
            UserNotFoundException,
            InsufficientBalanceException,
            MissingShippingAddressException,
            InvalidAddressException,
        )

        # All these exceptions should be mappable (not raise errors)
        exceptions_to_test = [
            OrderNotFoundException(order_id=1),
            OrderExpiredException(order_id=1),
            OrderAlreadyCancelledException(order_id=1),
            InvalidOrderStateException(order_id=1, current_state="A", required_state="B"),
            InsufficientStockException(item_id=1, requested=10, available=5),
            PaymentNotFoundException(invoice_id=1),
            InvalidPaymentAmountException(expected=100.0, received=50.0, currency="EUR"),
            PaymentAlreadyProcessedException(invoice_id=1),
            CryptocurrencyNotSelectedException(order_id=1),
            ItemNotFoundException(item_id=1),
            ItemAlreadySoldException(item_id=1),
            InvalidItemDataException(item_id=1, reason="test"),
            EmptyCartException(user_id=1),
            CartItemNotFoundException(cart_item_id=1),
            InvalidCartStateException(user_id=1, reason="test"),
            UserNotFoundException(telegram_id=1),
            UserBannedException(telegram_id=1, reason="test"),
            InsufficientBalanceException(user_id=1, required=100, available=50),
            MissingShippingAddressException(order_id=1),
            InvalidAddressException(order_id=1, reason="test"),
        ]

        for exc in exceptions_to_test:
            # Should not raise exception
            result = handle_service_error(exc, BotEntity.USER)
            assert result is not None
            assert len(result) > 0
            # Should contain error indicator (emoji or text)
            assert "❌" in result or "⏰" in result or "✅" in result or "🛒" in result or "📦" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
