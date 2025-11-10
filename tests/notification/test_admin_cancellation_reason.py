"""
Admin Cancellation Reason Display Test

Tests that custom cancellation reason from admin is displayed to user
in the order cancellation notification.

Run with:
    pytest tests/notification/test_admin_cancellation_reason.py -v
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Mock config before imports
import config
config.DB_ENCRYPTION = False

from services.invoice_formatter import InvoiceFormatterService
from enums.bot_entity import BotEntity


class TestAdminCancellationReason:
    """Test that admin custom cancellation reason is displayed"""

    def test_admin_cancellation_with_custom_reason(self):
        """Test that custom reason appears in formatted message"""
        custom_reason = "Artikel nicht mehr auf Lager"

        result = InvoiceFormatterService.format_complete_order_view(
            header_type="admin_cancellation",
            invoice_number="INV-2025-000123",
            items=[
                {
                    'name': 'Test Item',
                    'price': 10.0,
                    'quantity': 2,
                    'is_physical': False,
                    'private_data': None
                }
            ],
            total_price=20.0,
            cancellation_reason=custom_reason,
            entity=BotEntity.USER
        )

        # Verify custom reason appears in message
        assert custom_reason in result, "Custom cancellation reason not found in message"

        # Verify label appears (localized)
        assert "Grund der Stornierung" in result or "Cancellation Reason" in result, \
            "Cancellation reason label not found"

    def test_admin_cancellation_without_custom_reason(self):
        """Test that message works without custom reason (None)"""
        result = InvoiceFormatterService.format_complete_order_view(
            header_type="admin_cancellation",
            invoice_number="INV-2025-000124",
            items=[
                {
                    'name': 'Test Item',
                    'price': 10.0,
                    'quantity': 1,
                    'is_physical': False,
                    'private_data': None
                }
            ],
            total_price=10.0,
            cancellation_reason=None,  # No custom reason
            entity=BotEntity.USER
        )

        # Should still generate valid message
        assert "INV-2025-000124" in result
        assert "Test Item" in result

        # Should NOT show reason label when no reason provided
        assert "Grund der Stornierung" not in result, \
            "Reason label should not appear when no reason provided"

    def test_admin_cancellation_html_escaping(self):
        """Test that custom reason is properly HTML-escaped"""
        malicious_reason = "<script>alert('xss')</script>"

        # Note: Escaping happens in NotificationService before passing to formatter
        # But we test that formatter doesn't break escaped HTML
        from utils.html_escape import safe_html
        escaped_reason = safe_html(malicious_reason)

        result = InvoiceFormatterService.format_complete_order_view(
            header_type="admin_cancellation",
            invoice_number="INV-2025-000125",
            items=[
                {
                    'name': 'Test Item',
                    'price': 10.0,
                    'quantity': 1,
                    'is_physical': False,
                    'private_data': None
                }
            ],
            total_price=10.0,
            cancellation_reason=escaped_reason,
            entity=BotEntity.USER
        )

        # Verify escaped version appears (not raw script tag)
        assert escaped_reason in result
        assert "<script>" not in result, "Raw HTML script tag found - XSS vulnerability!"

    def test_admin_cancellation_multiline_reason(self):
        """Test that multiline custom reasons are displayed correctly"""
        multiline_reason = "Artikel nicht verfügbar\nLieferant hat storniert\nKunde wird kontaktiert"

        result = InvoiceFormatterService.format_complete_order_view(
            header_type="admin_cancellation",
            invoice_number="INV-2025-000126",
            items=[
                {
                    'name': 'Test Item',
                    'price': 10.0,
                    'quantity': 1,
                    'is_physical': False,
                    'private_data': None
                }
            ],
            total_price=10.0,
            cancellation_reason=multiline_reason,
            entity=BotEntity.USER
        )

        # Verify all lines appear
        assert "Artikel nicht verfügbar" in result
        assert "Lieferant hat storniert" in result
        assert "Kunde wird kontaktiert" in result
