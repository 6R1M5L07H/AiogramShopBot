"""
Unit tests for InvoiceFormatterService.format_checkout_summary()

Tests the checkout formatting with tier structures, savings, and upselling.
"""

import pytest
from enums.bot_entity import BotEntity
from services.invoice_formatter import InvoiceFormatterService


class TestCheckoutFormatterSingleTieredItem:
    """Tests for single tiered item checkout formatting"""

    def test_format_checkout_single_tiered_item_tier_2(self):
        """Test formatting with single tiered item reaching tier 2 of 4"""
        items = [
            {
                'name': 'USB-Sticks 32GB',
                'quantity': 16,
                'unit_price': 9.00,
                'line_total': 144.00,
                'available_tiers': [
                    {'min_quantity': 1, 'max_quantity': 5, 'unit_price': 12.00},
                    {'min_quantity': 6, 'max_quantity': 15, 'unit_price': 10.00},
                    {'min_quantity': 16, 'max_quantity': 25, 'unit_price': 9.00},
                    {'min_quantity': 26, 'max_quantity': None, 'unit_price': 8.00},
                ],
                'current_tier_idx': 2,
                'next_tier_info': {
                    'items_needed': 10,
                    'unit_price': 8.00,
                    'extra_savings': 26.00
                },
                'savings_vs_single': 48.00
            }
        ]

        result = InvoiceFormatterService.format_checkout_summary(
            items=items,
            subtotal=144.00,
            shipping_cost=0.00,
            total=144.00,
            total_savings=48.00,
            has_physical_items=False,
            currency_symbol="€",
            entity=BotEntity.USER
        )

        # Check for tier structure
        assert "USB-Sticks 32GB" in result
        assert ("Menge: 16" in result or "Quantity: 16" in result)
        assert ("Staffelpreise:" in result or "Tier Prices:" in result)

        # Check tier prices
        assert ("1-5" in result and "12.00€" in result)
        assert ("6-15" in result and "10.00€" in result)
        assert ("16-25" in result and "9.00€" in result)
        assert ("26+" in result and "8.00€" in result)

        # Check current tier marker (language-independent)
        assert "←" in result  # Marker symbol

        # Check savings
        assert "48.00€" in result

        # Check upselling
        assert "10" in result  # 10 items needed
        assert "8.00€" in result  # Next tier price
        assert "26.00€" in result  # Extra savings

        # Check line items
        assert ("Positionen:" in result or "Line Items:" in result)
        assert "144.00€" in result

        # Check totals
        assert ("Zwischensumme:" in result or "Subtotal:" in result)
        assert ("Gesamt:" in result or "Total:" in result)

    def test_format_checkout_max_tier_reached(self):
        """Test formatting when max tier is reached (no upselling)"""
        items = [
            {
                'name': 'USB-Sticks 32GB',
                'quantity': 30,
                'unit_price': 8.00,
                'line_total': 240.00,
                'available_tiers': [
                    {'min_quantity': 1, 'max_quantity': 5, 'unit_price': 12.00},
                    {'min_quantity': 6, 'max_quantity': 15, 'unit_price': 10.00},
                    {'min_quantity': 16, 'max_quantity': 25, 'unit_price': 9.00},
                    {'min_quantity': 26, 'max_quantity': None, 'unit_price': 8.00},
                ],
                'current_tier_idx': 3,
                'next_tier_info': None,  # Max tier reached
                'savings_vs_single': 120.00
            }
        ]

        result = InvoiceFormatterService.format_checkout_summary(
            items=items,
            subtotal=240.00,
            shipping_cost=0.00,
            total=240.00,
            total_savings=120.00,
            has_physical_items=False,
            currency_symbol="€",
            entity=BotEntity.USER
        )

        # Check for max tier message instead of upselling
        assert ("Bester Preis erreicht" in result or "Best price reached" in result)
        assert ("Noch" not in result and "more" not in result)  # No upselling text
        assert "120.00€" in result


class TestCheckoutFormatterMultipleTieredItems:
    """Tests for multiple tiered items in checkout"""

    def test_format_checkout_multiple_tiered_items(self):
        """Test formatting with 2 different tiered items"""
        items = [
            {
                'name': 'USB-Sticks 32GB',
                'quantity': 16,
                'unit_price': 9.00,
                'line_total': 144.00,
                'available_tiers': [
                    {'min_quantity': 1, 'max_quantity': 5, 'unit_price': 12.00},
                    {'min_quantity': 6, 'max_quantity': 15, 'unit_price': 10.00},
                    {'min_quantity': 16, 'max_quantity': 25, 'unit_price': 9.00},
                    {'min_quantity': 26, 'max_quantity': None, 'unit_price': 8.00},
                ],
                'current_tier_idx': 2,
                'next_tier_info': {
                    'items_needed': 10,
                    'unit_price': 8.00,
                    'extra_savings': 26.00
                },
                'savings_vs_single': 48.00
            },
            {
                'name': 'Grüner Tee Bio',
                'quantity': 8,
                'unit_price': 13.00,
                'line_total': 104.00,
                'available_tiers': [
                    {'min_quantity': 1, 'max_quantity': 3, 'unit_price': 15.00},
                    {'min_quantity': 4, 'max_quantity': 10, 'unit_price': 13.00},
                    {'min_quantity': 11, 'max_quantity': None, 'unit_price': 11.00},
                ],
                'current_tier_idx': 1,
                'next_tier_info': {
                    'items_needed': 3,
                    'unit_price': 11.00,
                    'extra_savings': 22.00
                },
                'savings_vs_single': 16.00
            }
        ]

        result = InvoiceFormatterService.format_checkout_summary(
            items=items,
            subtotal=248.00,
            shipping_cost=0.00,
            total=248.00,
            total_savings=64.00,
            has_physical_items=False,
            currency_symbol="€",
            entity=BotEntity.USER
        )

        # Check both items are present
        assert "USB-Sticks 32GB" in result
        assert "Grüner Tee Bio" in result

        # Check tier structures for both
        assert ("Menge: 16" in result or "Quantity: 16" in result)
        assert ("Menge: 8" in result or "Quantity: 8" in result)

        # Check both savings
        assert "48.00€" in result
        assert "16.00€" in result

        # Check both upselling hints (items_needed values)
        assert "10" in result  # 10 more for USB sticks
        assert "3" in result   # 3 more for tea

        # Check line items section
        assert "144.00€" in result
        assert "104.00€" in result

        # Check total savings
        assert "64.00€" in result


class TestCheckoutFormatterMixedCart:
    """Tests for mixed cart with tiered and non-tiered items"""

    def test_format_checkout_mixed_tiered_and_flat(self):
        """Test formatting with both tiered and flat-pricing items"""
        items = [
            {
                'name': 'USB-Sticks 32GB',
                'quantity': 16,
                'unit_price': 9.00,
                'line_total': 144.00,
                'available_tiers': [
                    {'min_quantity': 1, 'max_quantity': 15, 'unit_price': 12.00},
                    {'min_quantity': 16, 'max_quantity': None, 'unit_price': 9.00},
                ],
                'current_tier_idx': 1,
                'next_tier_info': None,
                'savings_vs_single': 48.00
            },
            {
                'name': 'Premium Support',
                'quantity': 1,
                'unit_price': 49.99,
                'line_total': 49.99,
                'available_tiers': None,  # Flat pricing
                'current_tier_idx': 0,
                'next_tier_info': None,
                'savings_vs_single': 0.0
            }
        ]

        result = InvoiceFormatterService.format_checkout_summary(
            items=items,
            subtotal=193.99,
            shipping_cost=0.00,
            total=193.99,
            total_savings=48.00,
            has_physical_items=False,
            currency_symbol="€",
            entity=BotEntity.USER
        )

        # Tiered item should have full tier structure
        assert "USB-Sticks 32GB" in result
        assert ("Staffelpreise:" in result or "Tier Prices:" in result)

        # Flat item should only appear in line items
        assert "Premium Support" in result
        assert "49.99€" in result

        # Check totals
        assert "193.99€" in result
        assert "48.00€" in result  # Total savings


class TestCheckoutFormatterShipping:
    """Tests for shipping cost handling"""

    def test_format_checkout_with_zero_shipping(self):
        """Test that €0.00 shipping is shown for physical items"""
        items = [
            {
                'name': 'USB-Sticks 32GB',
                'quantity': 10,
                'unit_price': 10.00,
                'line_total': 100.00,
                'available_tiers': None,
                'current_tier_idx': 0,
                'next_tier_info': None,
                'savings_vs_single': 0.0
            }
        ]

        result = InvoiceFormatterService.format_checkout_summary(
            items=items,
            subtotal=100.00,
            shipping_cost=0.00,  # Promotional free shipping
            total=100.00,
            total_savings=0.00,
            has_physical_items=True,  # Has physical items
            currency_symbol="€",
            entity=BotEntity.USER
        )

        # Shipping line should be present even if 0.00
        assert ("Versand" in result or "Shipping" in result)
        assert "0.00€" in result

    def test_format_checkout_with_paid_shipping(self):
        """Test formatting with non-zero shipping cost"""
        items = [
            {
                'name': 'USB-Sticks 32GB',
                'quantity': 10,
                'unit_price': 10.00,
                'line_total': 100.00,
                'available_tiers': None,
                'current_tier_idx': 0,
                'next_tier_info': None,
                'savings_vs_single': 0.0
            }
        ]

        result = InvoiceFormatterService.format_checkout_summary(
            items=items,
            subtotal=100.00,
            shipping_cost=5.50,
            total=105.50,
            total_savings=0.00,
            has_physical_items=True,
            currency_symbol="€",
            entity=BotEntity.USER
        )

        assert ("Versand" in result or "Shipping" in result)
        assert "5.50€" in result
        assert "105.50€" in result

    def test_format_checkout_no_physical_items(self):
        """Test that shipping line is omitted for digital-only carts"""
        items = [
            {
                'name': 'Digital License Key',
                'quantity': 1,
                'unit_price': 50.00,
                'line_total': 50.00,
                'available_tiers': None,
                'current_tier_idx': 0,
                'next_tier_info': None,
                'savings_vs_single': 0.0
            }
        ]

        result = InvoiceFormatterService.format_checkout_summary(
            items=items,
            subtotal=50.00,
            shipping_cost=0.00,
            total=50.00,
            total_savings=0.00,
            has_physical_items=False,  # Digital only
            currency_symbol="€",
            entity=BotEntity.USER
        )

        # No shipping line for digital items
        assert ("Versand" not in result and "Shipping" not in result)


class TestCheckoutFormatterHTMLSafety:
    """Tests for HTML escaping and security"""

    def test_format_checkout_html_escaping(self):
        """Test that item names are properly HTML escaped"""
        items = [
            {
                'name': 'USB-Sticks <script>alert("xss")</script>',
                'quantity': 1,
                'unit_price': 10.00,
                'line_total': 10.00,
                'available_tiers': None,
                'current_tier_idx': 0,
                'next_tier_info': None,
                'savings_vs_single': 0.0
            }
        ]

        result = InvoiceFormatterService.format_checkout_summary(
            items=items,
            subtotal=10.00,
            shipping_cost=0.00,
            total=10.00,
            total_savings=0.00,
            has_physical_items=False,
            currency_symbol="€",
            entity=BotEntity.USER
        )

        # <script> tags should be escaped
        assert "<script>" not in result
        assert "&lt;script&gt;" in result or "alert" not in result


class TestCheckoutFormatterZeroSavings:
    """Tests for items with no savings"""

    def test_format_checkout_no_savings(self):
        """Test that total savings section is omitted when savings = 0"""
        items = [
            {
                'name': 'Flat Price Item',
                'quantity': 5,
                'unit_price': 20.00,
                'line_total': 100.00,
                'available_tiers': None,
                'current_tier_idx': 0,
                'next_tier_info': None,
                'savings_vs_single': 0.0
            }
        ]

        result = InvoiceFormatterService.format_checkout_summary(
            items=items,
            subtotal=100.00,
            shipping_cost=0.00,
            total=100.00,
            total_savings=0.00,
            has_physical_items=False,
            currency_symbol="€",
            entity=BotEntity.USER
        )

        # No savings section when total_savings = 0
        assert ("Gesamtersparnis" not in result and "Total Savings" not in result)
