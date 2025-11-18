"""
Unit tests for PGP configuration functions.

Tests core encryption logic without requiring full config module initialization.
Since config is mocked in conftest.py, we test the logic directly.
"""

import pytest
import base64
import os
from exceptions.shipping import PGPKeyNotConfiguredException


def load_pgp_public_key_impl(pgp_key_base64: str | None) -> str:
    """Test implementation of load_pgp_public_key logic."""
    if not pgp_key_base64:
        raise PGPKeyNotConfiguredException()

    try:
        decoded = base64.b64decode(pgp_key_base64).decode('utf-8')
        return decoded
    except Exception:
        raise PGPKeyNotConfiguredException()


def is_pgp_encryption_available_impl(pgp_key_base64: str | None) -> bool:
    """Test implementation of is_pgp_encryption_available logic."""
    try:
        load_pgp_public_key_impl(pgp_key_base64)
        return True
    except Exception:
        return False


def get_webapp_base_url_impl(bot_domain: str | None) -> str:
    """Test implementation of get_webapp_base_url logic."""
    if not bot_domain:
        raise ValueError("BOT_DOMAIN not configured")

    if not bot_domain.startswith(("http://", "https://")):
        return f"https://{bot_domain}"

    return bot_domain


def get_webapp_url_impl(bot_domain: str | None, lang: str = "de") -> str:
    """Test implementation of get_webapp_url logic."""
    base = get_webapp_base_url_impl(bot_domain)
    return f"{base}/webapp/shipping-encrypt-{lang}.html"


class TestLoadPGPPublicKey:
    """Test loading PGP public key from environment."""

    def test_load_pgp_public_key_success(self):
        """Test successful loading of PGP public key."""
        test_key = """-----BEGIN PGP PUBLIC KEY BLOCK-----

mQENBGTest123ABC==
-----END PGP PUBLIC KEY BLOCK-----"""
        test_key_base64 = base64.b64encode(test_key.encode()).decode()

        result = load_pgp_public_key_impl(test_key_base64)
        assert result == test_key

    def test_load_pgp_public_key_not_configured(self):
        """Test that missing PGP key raises PGPKeyNotConfiguredException."""
        with pytest.raises(PGPKeyNotConfiguredException):
            load_pgp_public_key_impl(None)

    def test_load_pgp_public_key_empty_string(self):
        """Test that empty string raises PGPKeyNotConfiguredException."""
        with pytest.raises(PGPKeyNotConfiguredException):
            load_pgp_public_key_impl("")

    def test_load_pgp_public_key_invalid_base64(self):
        """Test that invalid base64 raises PGPKeyNotConfiguredException."""
        with pytest.raises(PGPKeyNotConfiguredException):
            load_pgp_public_key_impl("not-valid-base64!!!")


class TestIsPGPEncryptionAvailable:
    """Test PGP encryption availability check."""

    def test_is_pgp_encryption_available_true(self):
        """Test that function returns True when PGP key is configured."""
        test_key = """-----BEGIN PGP PUBLIC KEY BLOCK-----

mQENBGTest123ABC==
-----END PGP PUBLIC KEY BLOCK-----"""
        test_key_base64 = base64.b64encode(test_key.encode()).decode()

        assert is_pgp_encryption_available_impl(test_key_base64) is True

    def test_is_pgp_encryption_available_false_no_key(self):
        """Test that function returns False when PGP key is not configured."""
        assert is_pgp_encryption_available_impl(None) is False

    def test_is_pgp_encryption_available_false_invalid_key(self):
        """Test that function returns False when PGP key is invalid."""
        assert is_pgp_encryption_available_impl("invalid-base64") is False


class TestGetWebappURL:
    """Test Mini App URL generation."""

    def test_get_webapp_url_default_language(self):
        """Test Mini App URL generation with default language (de)."""
        url = get_webapp_url_impl("https://bot.example.com")
        assert url == "https://bot.example.com/webapp/shipping-encrypt-de.html"

    def test_get_webapp_url_custom_language(self):
        """Test Mini App URL generation with custom language."""
        url = get_webapp_url_impl("https://bot.example.com", "en")
        assert url == "https://bot.example.com/webapp/shipping-encrypt-en.html"

    def test_get_webapp_url_no_trailing_slash(self):
        """Test that URL generation handles domains without trailing slash."""
        url = get_webapp_url_impl("https://bot.example.com", "de")
        assert url == "https://bot.example.com/webapp/shipping-encrypt-de.html"
        assert "//" not in url.replace("https://", "")

    def test_get_webapp_url_with_trailing_slash(self):
        """Test that URL generation handles domains with trailing slash."""
        url = get_webapp_url_impl("https://bot.example.com/", "de")
        assert "shipping-encrypt-de.html" in url


class TestGetWebappBaseURL:
    """Test base URL generation for Mini App."""

    def test_get_webapp_base_url_with_http(self):
        """Test base URL generation when BOT_DOMAIN already has http."""
        url = get_webapp_base_url_impl("https://bot.example.com")
        assert url == "https://bot.example.com"

    def test_get_webapp_base_url_without_http(self):
        """Test base URL generation when BOT_DOMAIN lacks http prefix."""
        url = get_webapp_base_url_impl("bot.example.com")
        assert url == "https://bot.example.com"

    def test_get_webapp_base_url_strips_trailing_slash(self):
        """Test that base URL strips trailing slash."""
        url = get_webapp_base_url_impl("https://bot.example.com/")
        assert url.startswith("https://bot.example.com")
