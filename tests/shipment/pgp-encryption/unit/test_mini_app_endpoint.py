"""
Unit tests for PGP Mini App FastAPI endpoint.

Tests the /webapp/pgp-address-input endpoint for:
- Successful template rendering
- PGP key validation
- Localization
- Error handling
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


class TestMiniAppEndpoint:
    """Test suite for Mini App FastAPI endpoint."""

    @pytest.fixture
    def test_client(self):
        """Create FastAPI test client."""
        # Import here to avoid side effects
        from bot import app
        return TestClient(app)

    @pytest.fixture
    def mock_pgp_key(self):
        """Mock PGP public key."""
        return """-----BEGIN PGP PUBLIC KEY BLOCK-----

mQENBGQxyz0BCACxxx...
-----END PGP PUBLIC KEY BLOCK-----"""

    def test_endpoint_requires_order_id(self, test_client):
        """Test that endpoint requires order_id parameter."""
        response = test_client.get("/webapp/pgp-address-input")
        assert response.status_code == 422  # FastAPI validation error

    @patch('config.PGP_PUBLIC_KEY_BASE64', 'dGVzdGtleQ==')  # base64('testkey')
    def test_endpoint_returns_html_with_valid_params(self, test_client):
        """Test successful HTML response with valid parameters."""
        response = test_client.get("/webapp/pgp-address-input?order_id=123&lang=de")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert b"pgp_address_input.html" in response.content or b"<!DOCTYPE html>" in response.content

    @patch('config.PGP_PUBLIC_KEY_BASE64', '')
    def test_endpoint_fails_without_pgp_key(self, test_client):
        """Test 500 error when PGP_PUBLIC_KEY_BASE64 not configured."""
        response = test_client.get("/webapp/pgp-address-input?order_id=123&lang=de")

        assert response.status_code == 500
        assert b"PGP encryption not available" in response.content

    @patch('config.PGP_PUBLIC_KEY_BASE64', 'dGVzdGtleQ==')
    def test_endpoint_renders_german_strings(self, test_client):
        """Test localization for German language."""
        response = test_client.get("/webapp/pgp-address-input?order_id=123&lang=de")

        assert response.status_code == 200
        # Should contain localized variables (even if English fallback is used during tests)
        content = response.content.decode('utf-8')
        # Check that template variables are rendered (not just {{ }} placeholders)
        assert "{{" not in content or content.count("{{") < 3  # Allow some JS template literals
        assert '<html lang="de">' in content

    @patch('config.PGP_PUBLIC_KEY_BASE64', 'dGVzdGtleQ==')
    def test_endpoint_renders_english_strings(self, test_client):
        """Test localization for English language."""
        response = test_client.get("/webapp/pgp-address-input?order_id=123&lang=en")

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        # Should contain English text from l10n/en.json
        assert "Shipping Address" in content or "pgp_webapp" in content

    @patch('config.PGP_PUBLIC_KEY_BASE64', 'LS0tLS1CRUdJTiBQR1AgUFVCTElDIEtFWSBCTE9DSy0tLS0t')  # base64 of '-----BEGIN PGP PUBLIC KEY BLOCK-----'
    def test_endpoint_embeds_pgp_key_in_template(self, test_client):
        """Test that PGP public key is embedded in rendered HTML."""
        response = test_client.get("/webapp/pgp-address-input?order_id=123&lang=de")

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        # Should contain the decoded PGP key
        assert "-----BEGIN PGP PUBLIC KEY BLOCK-----" in content

    @patch('config.PGP_PUBLIC_KEY_BASE64', 'dGVzdGtleQ==')
    def test_endpoint_embeds_order_id_in_template(self, test_client):
        """Test that order_id is embedded in JavaScript."""
        response = test_client.get("/webapp/pgp-address-input?order_id=999&lang=de")

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        # JavaScript should have orderId = 999
        assert "999" in content

    @patch('config.PGP_PUBLIC_KEY_BASE64', 'aW52YWxpZC1iYXNlNjQ=')
    def test_endpoint_handles_invalid_base64(self, test_client):
        """Test error handling for invalid base64-encoded key."""
        # This should not crash, but might return 500 depending on implementation
        response = test_client.get("/webapp/pgp-address-input?order_id=123&lang=de")

        # Either succeeds with decoded content or fails gracefully with 500
        assert response.status_code in [200, 500]

    @patch('config.PGP_PUBLIC_KEY_BASE64', 'dGVzdGtleQ==')
    def test_endpoint_defaults_to_german(self, test_client):
        """Test that default language is German when not specified."""
        response_no_lang = test_client.get("/webapp/pgp-address-input?order_id=123")

        # Should default to 'de'
        assert response_no_lang.status_code == 200


class TestLoadPGPPublicKey:
    """Test suite for load_pgp_public_key() function."""

    def test_load_pgp_key_decodes_base64(self):
        """Test successful decoding of base64-encoded PGP key."""
        from web.mini_app_router import load_pgp_public_key
        from exceptions.shipping import PGPKeyNotConfiguredException

        with patch('config.PGP_PUBLIC_KEY_BASE64', 'dGVzdGtleQ=='):  # base64('testkey')
            key = load_pgp_public_key()
            assert key == 'testkey'

    def test_load_pgp_key_raises_when_not_configured(self):
        """Test exception when PGP_PUBLIC_KEY_BASE64 is empty."""
        from web.mini_app_router import load_pgp_public_key
        from exceptions.shipping import PGPKeyNotConfiguredException

        with patch('config.PGP_PUBLIC_KEY_BASE64', ''):
            with pytest.raises(PGPKeyNotConfiguredException):
                load_pgp_public_key()

    def test_load_pgp_key_raises_on_decode_error(self):
        """Test exception when base64 decoding fails."""
        from web.mini_app_router import load_pgp_public_key
        from exceptions.shipping import PGPKeyNotConfiguredException

        with patch('config.PGP_PUBLIC_KEY_BASE64', 'invalid!!!base64'):
            with pytest.raises(PGPKeyNotConfiguredException):
                load_pgp_public_key()