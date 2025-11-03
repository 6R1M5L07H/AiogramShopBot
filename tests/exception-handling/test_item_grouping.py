"""
Tests for item grouping logic in services/order.py
Tests the _group_items_for_display() helper function.
"""
import pytest
from services.order import OrderService


class TestItemGrouping:
    """Test item grouping logic."""

    def test_group_identical_physical_items(self):
        """Test that identical physical items are grouped together."""
        items = [
            {'name': 'USB Flash Drive', 'price': 15.0, 'is_physical': True, 'private_data': None},
            {'name': 'USB Flash Drive', 'price': 15.0, 'is_physical': True, 'private_data': None},
            {'name': 'USB Flash Drive', 'price': 15.0, 'is_physical': True, 'private_data': None},
            {'name': 'USB Flash Drive', 'price': 15.0, 'is_physical': True, 'private_data': None},
            {'name': 'USB Flash Drive', 'price': 15.0, 'is_physical': True, 'private_data': None},
        ]

        result = OrderService._group_items_for_display(items)

        assert len(result) == 1
        assert result[0]['name'] == 'USB Flash Drive'
        assert result[0]['quantity'] == 5
        assert result[0]['price'] == 15.0
        assert result[0]['is_physical'] is True
        assert result[0]['private_data'] is None

    def test_group_identical_digital_items_without_private_data(self):
        """Test that identical digital items without private_data are grouped."""
        items = [
            {'name': 'E-Book', 'price': 10.0, 'is_physical': False, 'private_data': None},
            {'name': 'E-Book', 'price': 10.0, 'is_physical': False, 'private_data': None},
            {'name': 'E-Book', 'price': 10.0, 'is_physical': False, 'private_data': None},
        ]

        result = OrderService._group_items_for_display(items)

        assert len(result) == 1
        assert result[0]['name'] == 'E-Book'
        assert result[0]['quantity'] == 3
        assert result[0]['is_physical'] is False

    def test_separate_items_with_unique_private_data(self):
        """Test that items with unique private_data remain separate."""
        items = [
            {'name': 'Game Key', 'price': 20.0, 'is_physical': False, 'private_data': 'KEY-001'},
            {'name': 'Game Key', 'price': 20.0, 'is_physical': False, 'private_data': 'KEY-002'},
            {'name': 'Game Key', 'price': 20.0, 'is_physical': False, 'private_data': 'KEY-003'},
        ]

        result = OrderService._group_items_for_display(items)

        # Should have 3 separate items (different private_data)
        assert len(result) == 3

        # Each should have quantity 1
        for item in result:
            assert item['quantity'] == 1
            assert item['name'] == 'Game Key'
            assert item['private_data'] in ['KEY-001', 'KEY-002', 'KEY-003']

    def test_group_items_with_same_private_data(self):
        """Test that items with identical private_data are grouped."""
        items = [
            {'name': 'License', 'price': 50.0, 'is_physical': False, 'private_data': 'SHARED-KEY'},
            {'name': 'License', 'price': 50.0, 'is_physical': False, 'private_data': 'SHARED-KEY'},
        ]

        result = OrderService._group_items_for_display(items)

        # Should be grouped (same private_data)
        assert len(result) == 1
        assert result[0]['quantity'] == 2
        assert result[0]['private_data'] == 'SHARED-KEY'

    def test_mixed_items_grouped_correctly(self):
        """Test complex scenario with mixed physical/digital and private_data."""
        items = [
            # 3 identical physical items
            {'name': 'Physical Item A', 'price': 10.0, 'is_physical': True, 'private_data': None},
            {'name': 'Physical Item A', 'price': 10.0, 'is_physical': True, 'private_data': None},
            {'name': 'Physical Item A', 'price': 10.0, 'is_physical': True, 'private_data': None},
            # 2 identical digital items without private_data
            {'name': 'Digital Item B', 'price': 5.0, 'is_physical': False, 'private_data': None},
            {'name': 'Digital Item B', 'price': 5.0, 'is_physical': False, 'private_data': None},
            # 2 digital items with unique private_data
            {'name': 'Digital Item C', 'price': 15.0, 'is_physical': False, 'private_data': 'KEY123'},
            {'name': 'Digital Item C', 'price': 15.0, 'is_physical': False, 'private_data': 'KEY456'},
        ]

        result = OrderService._group_items_for_display(items)

        # Should have 4 groups: 3x Physical A, 2x Digital B, 1x Digital C (KEY123), 1x Digital C (KEY456)
        assert len(result) == 4

        # Find each group
        physical_a = [r for r in result if r['name'] == 'Physical Item A']
        digital_b = [r for r in result if r['name'] == 'Digital Item B']
        digital_c = [r for r in result if r['name'] == 'Digital Item C']

        assert len(physical_a) == 1
        assert physical_a[0]['quantity'] == 3

        assert len(digital_b) == 1
        assert digital_b[0]['quantity'] == 2

        assert len(digital_c) == 2  # Two separate items
        assert all(item['quantity'] == 1 for item in digital_c)

    def test_different_prices_not_grouped(self):
        """Test that items with different prices are not grouped."""
        items = [
            {'name': 'Item', 'price': 10.0, 'is_physical': True, 'private_data': None},
            {'name': 'Item', 'price': 15.0, 'is_physical': True, 'private_data': None},
        ]

        result = OrderService._group_items_for_display(items)

        # Should have 2 separate groups (different prices)
        assert len(result) == 2
        assert all(item['quantity'] == 1 for item in result)

    def test_different_physical_status_not_grouped(self):
        """Test that physical and digital items are not grouped together."""
        items = [
            {'name': 'Item', 'price': 10.0, 'is_physical': True, 'private_data': None},
            {'name': 'Item', 'price': 10.0, 'is_physical': False, 'private_data': None},
        ]

        result = OrderService._group_items_for_display(items)

        # Should have 2 separate groups (different is_physical)
        assert len(result) == 2
        assert all(item['quantity'] == 1 for item in result)

    def test_empty_items_list(self):
        """Test handling of empty items list."""
        items = []

        result = OrderService._group_items_for_display(items)

        assert len(result) == 0
        assert result == []

    def test_single_item_no_grouping(self):
        """Test that single item is returned as-is."""
        items = [
            {'name': 'Single Item', 'price': 10.0, 'is_physical': True, 'private_data': None},
        ]

        result = OrderService._group_items_for_display(items)

        assert len(result) == 1
        assert result[0]['quantity'] == 1
        assert result[0]['name'] == 'Single Item'

    def test_physical_items_with_unique_private_data(self):
        """Test that physical items with unique private_data remain separate."""
        items = [
            {'name': 'Collectible Card', 'price': 100.0, 'is_physical': True, 'private_data': 'SERIAL-001'},
            {'name': 'Collectible Card', 'price': 100.0, 'is_physical': True, 'private_data': 'SERIAL-002'},
        ]

        result = OrderService._group_items_for_display(items)

        # Should have 2 separate items (unique physical items with serial numbers)
        assert len(result) == 2
        assert all(item['quantity'] == 1 for item in result)
        assert result[0]['private_data'] != result[1]['private_data']

    def test_items_with_quantity_attribute(self):
        """Test that existing quantity attribute is respected."""
        items = [
            {'name': 'Item', 'price': 10.0, 'is_physical': True, 'private_data': None, 'quantity': 2},
            {'name': 'Item', 'price': 10.0, 'is_physical': True, 'private_data': None, 'quantity': 3},
        ]

        result = OrderService._group_items_for_display(items)

        # Should group and sum quantities: 2 + 3 = 5
        assert len(result) == 1
        assert result[0]['quantity'] == 5
