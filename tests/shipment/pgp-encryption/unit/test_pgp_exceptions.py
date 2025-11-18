"""
Unit tests for PGP-related exceptions.

Tests PGPKeyNotConfiguredException.
"""

import pytest
from exceptions.shipping import PGPKeyNotConfiguredException, ShippingException


class TestPGPKeyNotConfiguredException:
    """Test PGPKeyNotConfiguredException."""

    def test_exception_is_shipping_exception(self):
        """Test that PGPKeyNotConfiguredException inherits from ShippingException."""
        exc = PGPKeyNotConfiguredException()
        assert isinstance(exc, ShippingException)

    def test_exception_message(self):
        """Test that exception has correct error message."""
        exc = PGPKeyNotConfiguredException()
        assert "PGP public key not configured" in str(exc)
        assert "PGP_PUBLIC_KEY_BASE64" in str(exc)

    def test_exception_can_be_raised(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(PGPKeyNotConfiguredException):
            raise PGPKeyNotConfiguredException()

    def test_exception_can_be_caught_as_shipping_exception(self):
        """Test that exception can be caught as ShippingException."""
        with pytest.raises(ShippingException):
            raise PGPKeyNotConfiguredException()

    def test_exception_has_details(self):
        """Test that exception has empty details dict."""
        exc = PGPKeyNotConfiguredException()
        # ShippingException should have details attribute
        assert hasattr(exc, 'details')
        assert exc.details == {}
