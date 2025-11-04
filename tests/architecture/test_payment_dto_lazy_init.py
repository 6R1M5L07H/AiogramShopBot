"""
Unit Tests for Payment DTO Lazy Initialization

Tests that ProcessingPaymentDTO uses lazy evaluation for callbackUrl
to avoid computing it at import time when config.WEBHOOK_URL might be None.
"""

import pytest


class TestPaymentDTOLazyInit:
    """Test Payment DTO Lazy Initialization"""

    def test_payment_dto_import_safe(self):
        """Test that importing models.payment doesn't evaluate WEBHOOK_URL"""
        # This test verifies the import is safe even when config not initialized
        # The actual DTO creation will happen after bot.py calls initialize_webhook_config()
        from models.payment import ProcessingPaymentDTO

        # Import should succeed (no immediate evaluation of default_factory)
        assert ProcessingPaymentDTO is not None

    def test_callback_url_uses_default_factory(self):
        """Test that callbackUrl uses Field(default_factory=...) pattern"""
        from models.payment import ProcessingPaymentDTO
        import inspect

        # Get the field definition
        fields = ProcessingPaymentDTO.model_fields
        callback_field = fields.get('callbackUrl')

        assert callback_field is not None, "callbackUrl field should exist"

        # Check that it uses default_factory (lazy evaluation)
        # This ensures the URL is computed when DTO is created, not at import time
        assert callback_field.default_factory is not None, \
            "callbackUrl should use default_factory for lazy evaluation"

    def test_get_callback_url_function_exists(self):
        """Test that _get_callback_url() helper function exists"""
        from models import payment

        assert hasattr(payment, '_get_callback_url')
        assert callable(payment._get_callback_url)

    def test_get_callback_url_validates_webhook_url(self):
        """Test that _get_callback_url() validates WEBHOOK_URL is initialized"""
        from models.payment import _get_callback_url
        import config

        # Save original value
        original_webhook_url = config.WEBHOOK_URL

        try:
            # Set to None (simulates not initialized)
            config.WEBHOOK_URL = None

            # Should raise ValueError when WEBHOOK_URL is None
            with pytest.raises(ValueError) as exc_info:
                _get_callback_url()

            assert "WEBHOOK_URL is not initialized" in str(exc_info.value)
        finally:
            # Restore original value
            config.WEBHOOK_URL = original_webhook_url

    def test_callback_secret_uses_default_factory(self):
        """Test that callbackSecret also uses Field(default_factory=...)"""
        from models.payment import ProcessingPaymentDTO

        fields = ProcessingPaymentDTO.model_fields
        secret_field = fields.get('callbackSecret')

        assert secret_field is not None, "callbackSecret field should exist"
        assert secret_field.default_factory is not None, \
            "callbackSecret should use default_factory for lazy evaluation"


if __name__ == "__main__":
    """
    Run tests with:
        pytest tests/architecture/test_payment_dto_lazy_init.py -v
    """
    pytest.main([__file__, "-v"])
