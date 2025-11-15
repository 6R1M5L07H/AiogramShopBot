"""
Unit tests for InvoiceFormatterService._format_items()

Tests the extracted items formatting component for:
- Digital/physical item separation
- Partial cancellation formatting
- Unified item lists
- Spacing alignment
- Private data display
- Tier pricing integration
"""

import pytest
from services.invoice_formatter import InvoiceFormatterService
from enums.bot_entity import BotEntity


class TestFormatItems:
    """Test suite for _format_items() method"""

    def test_empty_items_list(self):
        """Test handling of empty items list"""
        message, subtotal = InvoiceFormatterService._format_items(
            items=None,
            header_type="payment_screen",
            currency_symbol="€",
            show_private_data=False,
            separate_digital_physical=False,
            use_spacing_alignment=False,
            entity=BotEntity.USER
        )

        assert message == ""
        assert subtotal == 0.0

    def test_unified_items_simple_format(self):
        """Test unified items list without spacing alignment"""
        items = [
            {'name': 'Digital Product A', 'price': 10.00, 'quantity': 2, 'is_physical': False},
            {'name': 'Digital Product B', 'price': 15.50, 'quantity': 1, 'is_physical': False}
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="payment_screen",
            currency_symbol="€",
            show_private_data=False,
            separate_digital_physical=False,
            use_spacing_alignment=False,
            entity=BotEntity.USER
        )

        assert "2x Digital Product A" in message
        assert "1x Digital Product B" in message
        assert "€10.00" in message
        assert "€15.50" in message
        assert subtotal == 35.50  # 2*10 + 1*15.5

    def test_unified_items_with_spacing_alignment(self):
        """Test unified items with spacing alignment (payment screen format)"""
        items = [
            {'name': 'Product', 'price': 25.00, 'quantity': 1, 'is_physical': False}
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="payment_screen",
            currency_symbol="€",
            show_private_data=False,
            separate_digital_physical=False,
            use_spacing_alignment=True,
            entity=BotEntity.USER
        )

        assert "1x Product" in message
        assert "€25.00" in message
        # Should have spacing for alignment
        assert " " * 5 in message or "\n" in message  # Spacing present
        assert subtotal == 25.00

    def test_separate_digital_physical_items(self):
        """Test digital/physical item separation"""
        items = [
            {'name': 'Steam Key', 'price': 20.00, 'quantity': 1, 'is_physical': False},
            {'name': 'USB Stick', 'price': 15.00, 'quantity': 2, 'is_physical': True},
            {'name': 'Netflix Voucher', 'price': 10.00, 'quantity': 1, 'is_physical': False}
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="order_detail_user",
            currency_symbol="€",
            show_private_data=False,
            separate_digital_physical=True,
            use_spacing_alignment=False,
            entity=BotEntity.USER
        )

        # Should have separate sections
        assert "Steam Key" in message
        assert "Netflix Voucher" in message
        assert "USB Stick" in message

        # Check subtotal calculation
        assert subtotal == 60.00  # 20 + 2*15 + 10 = 20 + 30 + 10

    def test_partial_cancellation_format(self):
        """Test partial cancellation items formatting (digital kept, physical refunded)"""
        items = [
            {'name': 'Digital Game', 'price': 30.00, 'quantity': 1, 'is_physical': False},
            {'name': 'Physical Merch', 'price': 25.00, 'quantity': 1, 'is_physical': True}
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="partial_cancellation",
            currency_symbol="€",
            show_private_data=False,
            separate_digital_physical=False,
            use_spacing_alignment=False,
            entity=BotEntity.USER
        )

        assert "Digital Game" in message
        assert "Physical Merch" in message
        # Should show partial cancellation structure
        assert subtotal == 55.00  # 30 + 25

    def test_admin_cancellation_format_with_separators(self):
        """Test admin cancellation format with section separators"""
        items = [
            {'name': 'Product X', 'price': 100.00, 'quantity': 1, 'is_physical': False}
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="admin_cancellation",
            currency_symbol="€",
            show_private_data=False,
            separate_digital_physical=False,
            use_spacing_alignment=False,
            entity=BotEntity.USER  # Admin cancellation messages are shown to users
        )

        assert "Product X" in message
        assert "€100.00" in message
        # Should have separators for admin cancellation
        assert "─" in message  # Section separator
        assert subtotal == 100.00

    def test_items_with_private_data(self):
        """Test items rendering with private data (keys/codes)"""
        items = [
            {
                'name': 'Steam Key',
                'price': 20.00,
                'quantity': 1,
                'is_physical': False,
                'private_data': 'XXXX-YYYY-ZZZZ-AAAA'
            }
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="order_detail_user",
            currency_symbol="€",
            show_private_data=True,  # Show private data
            separate_digital_physical=True,
            use_spacing_alignment=False,
            entity=BotEntity.USER
        )

        assert "Steam Key" in message
        assert "€20.00" in message
        assert "XXXX-YYYY-ZZZZ-AAAA" in message  # Private data shown
        assert "<code>" in message  # Formatted as code
        assert subtotal == 20.00

    def test_items_without_showing_private_data(self):
        """Test that private data is hidden when show_private_data=False"""
        items = [
            {
                'name': 'Secret Code',
                'price': 15.00,
                'quantity': 1,
                'is_physical': False,
                'private_data': 'SECRET-KEY-12345'
            }
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="payment_screen",
            currency_symbol="€",
            show_private_data=False,  # Don't show private data
            separate_digital_physical=False,
            use_spacing_alignment=False,
            entity=BotEntity.USER
        )

        assert "Secret Code" in message
        assert "€15.00" in message
        assert "SECRET-KEY-12345" not in message  # Private data hidden
        assert subtotal == 15.00

    def test_items_with_tier_breakdown(self):
        """Test items with tier pricing breakdown integration"""
        items = [
            {
                'name': 'USB Stick 32GB',
                'price': 10.00,
                'quantity': 17,
                'is_physical': True,
                'tier_breakdown': [
                    {'quantity': 10, 'unit_price': 9.00, 'total': 90.00},
                    {'quantity': 5, 'unit_price': 10.00, 'total': 50.00},
                    {'quantity': 2, 'unit_price': 11.00, 'total': 22.00}
                ]
            }
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="order_detail_user",
            currency_symbol="€",
            show_private_data=False,
            separate_digital_physical=True,
            use_spacing_alignment=False,
            entity=BotEntity.USER
        )

        assert "USB Stick 32GB" in message
        # Should contain tier breakdown
        assert "9.00" in message or "9,00" in message
        assert "10.00" in message or "10,00" in message
        assert "11.00" in message or "11,00" in message
        # Subtotal should use tier breakdown total
        assert subtotal == 170.00  # 10*9 + 5*10 + 2*11 = 162 (item total)

    def test_subtotal_calculation_accuracy(self):
        """Test that subtotal calculation is accurate for various quantities"""
        items = [
            {'name': 'Item A', 'price': 12.99, 'quantity': 3, 'is_physical': False},
            {'name': 'Item B', 'price': 7.50, 'quantity': 2, 'is_physical': False},
            {'name': 'Item C', 'price': 100.00, 'quantity': 1, 'is_physical': True}
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="payment_screen",
            currency_symbol="€",
            show_private_data=False,
            separate_digital_physical=False,
            use_spacing_alignment=False,
            entity=BotEntity.USER
        )

        # 3*12.99 + 2*7.50 + 1*100.00 = 38.97 + 15.00 + 100.00 = 153.97
        assert subtotal == pytest.approx(153.97, rel=0.01)

    def test_items_with_html_in_private_data(self):
        """Test items with HTML-formatted private data"""
        items = [
            {
                'name': 'Consultation',
                'price': 50.00,
                'quantity': 1,
                'is_physical': False,
                'private_data': '<b>Zoom Link:</b> https://zoom.us/j/123456'
            }
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="order_detail_user",
            currency_symbol="€",
            show_private_data=True,
            separate_digital_physical=True,
            use_spacing_alignment=False,
            entity=BotEntity.USER
        )

        assert "Consultation" in message
        assert "<b>Zoom Link:</b>" in message  # HTML preserved
        assert "https://zoom.us/j/123456" in message
        assert subtotal == 50.00

    def test_mixed_items_return_correct_subtotal(self):
        """Test that mixed digital/physical items return correct subtotal"""
        items = [
            {'name': 'Digital A', 'price': 10.00, 'quantity': 1, 'is_physical': False},
            {'name': 'Physical B', 'price': 20.00, 'quantity': 2, 'is_physical': True},
            {'name': 'Digital C', 'price': 15.00, 'quantity': 1, 'is_physical': False}
        ]

        message, subtotal = InvoiceFormatterService._format_items(
            items=items,
            header_type="order_detail_admin",
            currency_symbol="€",
            show_private_data=False,
            separate_digital_physical=True,
            use_spacing_alignment=False,
            entity=BotEntity.ADMIN
        )

        assert subtotal == 65.00  # 10 + 2*20 + 15