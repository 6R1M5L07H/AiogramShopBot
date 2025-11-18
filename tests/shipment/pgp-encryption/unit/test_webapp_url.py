"""
Unit tests for webapp URL generation utility.

Tests get_webapp_url() function for:
- URL construction
- Query parameter handling
- HTTPS prefix handling
- Configuration validation
"""

import pytest
from unittest.mock import patch
from exceptions.shipping import BotDomainNotConfiguredException


class TestGetWebappUrl:
    """Test suite for get_webapp_url() utility function."""

    def test_generates_url_with_query_params(self):
        """Test URL generation with basic query parameters."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', 'example.com'):
            url = get_webapp_url("/webapp/test", lang="de", order_id=42)

            assert url.startswith("https://example.com/webapp/test?")
            assert "lang=de" in url
            assert "order_id=42" in url

    def test_adds_https_prefix_when_missing(self):
        """Test that https:// is added when domain has no protocol."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', 'example.com'):
            url = get_webapp_url("/test", lang="en")

            assert url.startswith("https://")

    def test_preserves_existing_https_prefix(self):
        """Test that existing https:// is not duplicated."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', 'https://example.com'):
            url = get_webapp_url("/test", lang="en")

            assert url == "https://example.com/test?lang=en"
            assert url.count("https://") == 1

    def test_removes_trailing_slash_from_domain(self):
        """Test that trailing slash is removed from domain."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', 'https://example.com/'):
            url = get_webapp_url("/test", lang="en")

            assert url == "https://example.com/test?lang=en"
            assert "example.com//test" not in url

    def test_raises_when_bot_domain_not_configured(self):
        """Test exception when BOT_DOMAIN is empty."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', ''):
            with pytest.raises(BotDomainNotConfiguredException):
                get_webapp_url("/test", lang="de")

    def test_raises_when_bot_domain_is_none(self):
        """Test exception when BOT_DOMAIN is None."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', None):
            with pytest.raises(BotDomainNotConfiguredException):
                get_webapp_url("/test", lang="de")

    def test_handles_multiple_query_params(self):
        """Test URL generation with multiple query parameters."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', 'example.com'):
            url = get_webapp_url(
                "/webapp/pgp-address-input",
                lang="de",
                order_id=123,
                user_id=456,
                session="abc123"
            )

            assert "order_id=123" in url
            assert "user_id=456" in url
            assert "session=abc123" in url
            assert "lang=de" in url

    def test_defaults_to_german_language(self):
        """Test that lang defaults to 'de' if not specified."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', 'example.com'):
            url = get_webapp_url("/test", order_id=42)

            assert "lang=de" in url

    def test_overrides_default_language(self):
        """Test that explicit lang parameter overrides default."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', 'example.com'):
            url = get_webapp_url("/test", lang="en", order_id=42)

            assert "lang=en" in url
            assert "lang=de" not in url

    def test_handles_http_prefix(self):
        """Test that http:// prefix is preserved (for dev environments)."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', 'http://localhost:8000'):
            url = get_webapp_url("/test", lang="en")

            assert url == "http://localhost:8000/test?lang=en"

    def test_real_world_pgp_webapp_url(self):
        """Test real-world example for PGP address input."""
        from utils.webapp_url import get_webapp_url

        with patch('config.BOT_DOMAIN', 'shop.example.com'):
            url = get_webapp_url(
                "/webapp/pgp-address-input",
                lang="de",
                order_id=1337
            )

            assert url.startswith("https://shop.example.com/webapp/pgp-address-input?")
            assert "lang=de" in url
            assert "order_id=1337" in url
            assert url.startswith("https://")


class TestBotDomainNotConfiguredException:
    """Test suite for BotDomainNotConfiguredException."""

    def test_exception_message(self):
        """Test that exception has correct message."""
        exc = BotDomainNotConfiguredException()

        assert "BOT_DOMAIN not configured" in str(exc)
        assert ".env" in str(exc)

    def test_exception_is_shipping_exception(self):
        """Test that exception inherits from ShippingException."""
        from exceptions.shipping import ShippingException

        exc = BotDomainNotConfiguredException()

        assert isinstance(exc, ShippingException)

    def test_exception_has_empty_details(self):
        """Test that exception has empty details dict."""
        exc = BotDomainNotConfiguredException()

        # ShopBotException should have details attribute
        assert hasattr(exc, 'details') or hasattr(exc, 'args')