"""
Unit Tests for HTML Escaping Utilities

Tests HTML injection prevention for user-controllable data.
"""

import pytest
from utils.html_escape import safe_html, safe_url


class TestSafeHtml:
    """Test safe_html() function"""

    def test_escape_script_injection(self):
        """Test blocking script tag injection"""
        malicious = "User</b><script>alert('XSS')</script>"
        result = safe_html(malicious)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "</b>" not in result  # Closing tag also escaped

    def test_escape_tag_injection(self):
        """Test escaping HTML tag injection"""
        malicious = "Admin<b>Bold</b>"
        result = safe_html(malicious)
        assert "<b>" not in result
        assert "&lt;b&gt;" in result

    def test_escape_link_injection(self):
        """Test escaping link injection"""
        malicious = 'User<a href="http://evil.com">Click</a>'
        result = safe_html(malicious)
        assert "<a href" not in result
        assert "&lt;a href=" in result

    def test_escape_quote_injection(self):
        """Test escaping quote injection (attribute breakout)"""
        malicious = 'User" onclick="alert(1)'
        result = safe_html(malicious)
        assert '&quot;' in result or '&#x27;' in result

    def test_preserve_normal_text(self):
        """Test normal text is preserved"""
        normal = "Normal Username 123"
        result = safe_html(normal)
        assert result == "Normal Username 123"

    def test_handle_none(self):
        """Test None input returns empty string"""
        result = safe_html(None)
        assert result == ""

    def test_handle_empty_string(self):
        """Test empty string returns empty string"""
        result = safe_html("")
        assert result == ""

    def test_escape_ampersand(self):
        """Test ampersand escaping"""
        text = "Tom & Jerry"
        result = safe_html(text)
        assert "&amp;" in result

    def test_escape_less_than_greater_than(self):
        """Test < and > escaping"""
        text = "User<123>"
        result = safe_html(text)
        assert "&lt;" in result
        assert "&gt;" in result


class TestSafeUrl:
    """Test safe_url() function"""

    def test_allow_https(self):
        """Test HTTPS URLs are allowed"""
        url = "https://t.me/user123"
        result = safe_url(url)
        assert "https://t.me/user123" in result

    def test_allow_http(self):
        """Test HTTP URLs are allowed"""
        url = "http://example.com"
        result = safe_url(url)
        assert "http://example.com" in result

    def test_block_javascript_protocol(self):
        """Test javascript: protocol is blocked"""
        malicious = "javascript:alert(1)"
        result = safe_url(malicious)
        assert result == ""

    def test_block_data_protocol(self):
        """Test data: protocol is blocked"""
        malicious = "data:text/html,<script>alert(1)</script>"
        result = safe_url(malicious)
        assert result == ""

    def test_handle_none(self):
        """Test None input returns empty string"""
        result = safe_url(None)
        assert result == ""

    def test_handle_empty_string(self):
        """Test empty string returns empty string"""
        result = safe_url("")
        assert result == ""

    def test_allow_telegram_protocol(self):
        """Test tg:// protocol is allowed"""
        url = "tg://user?id=123"
        result = safe_url(url)
        assert "tg://" in result


class TestHtmlInjectionScenarios:
    """Test real-world HTML injection scenarios"""

    def test_username_with_html(self):
        """Test malicious username with HTML tags"""
        username = "Hacker</b><a href='http://evil.com'>Click here</a>"
        safe_username = safe_html(username)

        # Simulate notification
        message = f"<b>New order from @{safe_username}</b>"

        # Verify HTML is escaped
        assert "<a href" not in message
        assert "&lt;a href" in message

    def test_shipping_address_with_script(self):
        """Test malicious shipping address"""
        address = "123 Main St</b><script>alert('XSS')</script>"
        safe_address = safe_html(address)

        # Simulate admin view
        message = f"<b>Shipping Address:</b>\n{safe_address}"

        # Verify script is escaped
        assert "<script>" not in message
        assert "&lt;script&gt;" in message

    def test_custom_cancel_reason_injection(self):
        """Test admin custom reason with injection attempt"""
        reason = "Out of stock</b>\n<b>FAKE ADMIN MESSAGE"
        safe_reason = safe_html(reason)

        # Simulate cancellation message
        message = f"<b>Cancellation Reason:</b>\n{safe_reason}"

        # Verify injection is escaped
        assert "</b>" not in safe_reason
        assert "&lt;/b&gt;" in safe_reason

    def test_ban_reason_with_quotes(self):
        """Test ban reason with quote injection"""
        ban_reason = 'Fraud attempt" onclick="alert(1)'
        safe_ban_reason = safe_html(ban_reason)

        # Simulate ban notification
        message = f"<b>Ban Reason:</b> {safe_ban_reason}"

        # Verify quotes are escaped
        assert '&quot;' in safe_ban_reason or '&#x27;' in safe_ban_reason


if __name__ == "__main__":
    """
    Run tests with:
        pytest tests/security/test_html_escape.py -v
    """
    pytest.main([__file__, "-v"])
