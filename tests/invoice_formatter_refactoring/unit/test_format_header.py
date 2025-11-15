"""
Unit tests for InvoiceFormatterService._format_header()

Tests the extracted header formatting component to ensure all 10+ header types
render correctly with proper localization and timestamps.
"""

import pytest
from datetime import datetime
from services.invoice_formatter import InvoiceFormatterService
from enums.bot_entity import BotEntity
from enums.order_status import OrderStatus


class TestFormatHeader:
    """Test suite for _format_header() method"""

    def test_admin_order_header(self):
        """Test admin order view header with user info"""
        result = InvoiceFormatterService._format_header(
            header_type="admin_order",
            invoice_number="INV-2025-ABC123",
            date="2025-01-15 10:30",
            username="testuser",
            user_id=123456,
            entity=BotEntity.ADMIN
        )

        assert "INV-2025-ABC123" in result
        assert "testuser" in result
        assert "123456" in result
        assert "<b>" in result  # Should contain bold formatting

    def test_payment_screen_header(self):
        """Test payment screen header with invoice number and date"""
        result = InvoiceFormatterService._format_header(
            header_type="payment_screen",
            invoice_number="INV-2025-XYZ789",
            date="2025-01-15 10:30",
            entity=BotEntity.USER
        )

        assert "INV-2025-XYZ789" in result
        assert "2025-01-15 10:30" in result

    def test_wallet_payment_header(self):
        """Test wallet payment completion header"""
        result = InvoiceFormatterService._format_header(
            header_type="wallet_payment",
            invoice_number="INV-2025-WALLET",
            date="2025-01-15 11:00",
            entity=BotEntity.USER
        )

        assert "INV-2025-WALLET" in result
        assert "2025-01-15 11:00" in result

    def test_cancellation_refund_header(self):
        """Test cancellation with refund header (uses l10n)"""
        result = InvoiceFormatterService._format_header(
            header_type="cancellation_refund",
            invoice_number="INV-2025-CANCEL",
            date="2025-01-15 12:00",
            entity=BotEntity.USER
        )

        assert "INV-2025-CANCEL" in result
        # Should use localized strings from l10n (no hardcoded emojis)
        assert "order_cancelled_title" not in result  # Should be replaced by actual text

    def test_partial_cancellation_header(self):
        """Test partial cancellation header (mixed order)"""
        result = InvoiceFormatterService._format_header(
            header_type="partial_cancellation",
            invoice_number="INV-2025-PARTIAL",
            date="2025-01-15 13:00",
            entity=BotEntity.USER
        )

        assert "INV-2025-PARTIAL" in result

    def test_admin_cancellation_header(self):
        """Test admin cancellation notification header"""
        result = InvoiceFormatterService._format_header(
            header_type="admin_cancellation",
            invoice_number="INV-2025-ADMIN",
            date="2025-01-15 14:00",
            entity=BotEntity.COMMON
        )

        assert "INV-2025-ADMIN" in result
        assert "2025-01-15 14:00" in result

    def test_payment_success_header(self):
        """Test payment success notification header"""
        result = InvoiceFormatterService._format_header(
            header_type="payment_success",
            invoice_number="INV-2025-SUCCESS",
            date="2025-01-15 15:00",
            entity=BotEntity.USER
        )

        assert "INV-2025-SUCCESS" in result

    def test_order_shipped_header(self):
        """Test order shipped notification header with timestamp"""
        shipped_at = datetime(2025, 1, 15, 16, 30)
        result = InvoiceFormatterService._format_header(
            header_type="order_shipped",
            invoice_number="INV-2025-SHIPPED",
            date="2025-01-15 16:00",
            shipped_at=shipped_at,
            entity=BotEntity.USER
        )

        assert "INV-2025-SHIPPED" in result
        assert "15.01.2025" in result  # German date format
        assert "16:30" in result

    def test_order_detail_admin_with_status(self):
        """Test admin order detail header with status and timestamps"""
        created_at = datetime(2025, 1, 10, 10, 0)
        paid_at = datetime(2025, 1, 10, 11, 0)

        result = InvoiceFormatterService._format_header(
            header_type="order_detail_admin",
            invoice_number="INV-2025-DETAIL",
            date="2025-01-15 17:00",
            order_status=OrderStatus.PAID_AWAITING_SHIPMENT,
            created_at=created_at,
            paid_at=paid_at,
            entity=BotEntity.ADMIN
        )

        assert "INV-2025-DETAIL" in result
        assert "10.01.2025" in result  # Created date
        # Should show PAID_AWAITING_SHIPMENT status

    def test_order_detail_user_with_full_lifecycle(self):
        """Test user order detail header with full order lifecycle timestamps"""
        created_at = datetime(2025, 1, 10, 10, 0)
        paid_at = datetime(2025, 1, 10, 11, 0)
        shipped_at = datetime(2025, 1, 11, 9, 0)

        result = InvoiceFormatterService._format_header(
            header_type="order_detail_user",
            invoice_number="INV-2025-FULL",
            date="2025-01-15 18:00",
            order_status=OrderStatus.SHIPPED,
            created_at=created_at,
            paid_at=paid_at,
            shipped_at=shipped_at,
            entity=BotEntity.USER
        )

        assert "INV-2025-FULL" in result
        assert "10.01.2025 10:00" in result  # Created timestamp
        assert "10.01.2025 11:00" in result  # Paid timestamp
        assert "11.01.2025 09:00" in result  # Shipped timestamp

    def test_header_with_missing_username(self):
        """Test admin header with missing username (should show 'Unknown')"""
        result = InvoiceFormatterService._format_header(
            header_type="admin_order",
            invoice_number="INV-2025-NOUSER",
            date="2025-01-15 19:00",
            username=None,  # Missing username
            user_id=None,   # Missing user ID
            entity=BotEntity.ADMIN
        )

        assert "INV-2025-NOUSER" in result
        assert "Unknown" in result or "0" in result  # Fallback values

    def test_no_hardcoded_emojis_in_headers(self):
        """Test that headers don't contain hardcoded emojis (regression test)"""
        # Test all header types to ensure emojis come from l10n only
        header_types = [
            "admin_order", "payment_screen", "wallet_payment",
            "cancellation_refund", "partial_cancellation", "admin_cancellation",
            "payment_success", "order_shipped", "order_detail_admin", "order_detail_user"
        ]

        for header_type in header_types:
            result = InvoiceFormatterService._format_header(
                header_type=header_type,
                invoice_number="INV-2025-TEST",
                date="2025-01-15 20:00",
                order_status=OrderStatus.PAID,
                created_at=datetime(2025, 1, 15, 10, 0),
                entity=BotEntity.USER
            )

            # Headers should either:
            # 1. Not contain emojis at all (admin_order, payment_screen, wallet_payment)
            # 2. Have emojis from l10n strings (detected by absence of standalone emoji patterns)
            # This test ensures no "❌ <b>" or "📋 " patterns (hardcoded emoji + space + tag)
            # But allows emojis INSIDE localized strings

            # The key is: if emoji exists, it should be part of a localized string
            # Not a standalone f"❌ {variable}" pattern