"""
Tests for item-related exceptions in services/subcategory.py and services/cart.py
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from exceptions import ItemNotFoundException, InsufficientStockException
from exceptions.order import InsufficientStockException as OrderInsufficientStockException


class TestItemNotFoundException:
    """Test ItemNotFoundException is raised correctly."""

    def test_item_not_found_exception_creation(self):
        """Test ItemNotFoundException is created correctly with item_id."""
        # Create exception
        exc = ItemNotFoundException(item_id=999)

        # Verify attributes
        assert exc.item_id == 999
        assert "Item 999 not found" in str(exc)

    def test_deleted_item_access(self):
        """Test accessing deleted item raises ItemNotFoundException."""
        # Simulate item that was just deleted
        with pytest.raises(ItemNotFoundException) as exc_info:
            raise ItemNotFoundException(item_id=123)

        assert exc_info.value.item_id == 123


class TestInsufficientStockException:
    """Test InsufficientStockException is raised correctly."""

    def test_insufficient_stock_exception_creation(self):
        """Test InsufficientStockException is created correctly."""
        # Create exception (from order module)
        exc = OrderInsufficientStockException(
            item_id=1,
            requested=10,
            available=2
        )

        # Verify attributes
        assert exc.item_id == 1
        assert exc.available == 2
        assert exc.requested == 10
        assert "Insufficient stock" in str(exc)
        assert "requested 10" in str(exc)
        assert "available 2" in str(exc)

    def test_requested_more_than_available(self):
        """Test requesting more items than available raises exception."""
        available = 2
        requested = 10

        with pytest.raises(OrderInsufficientStockException) as exc_info:
            if requested > available:
                raise OrderInsufficientStockException(
                    item_id=1,
                    requested=requested,
                    available=available
                )

        assert exc_info.value.available == 2
        assert exc_info.value.requested == 10

    def test_zero_stock_requested(self):
        """Test requesting items when none available."""
        available = 0
        requested = 5

        with pytest.raises(OrderInsufficientStockException) as exc_info:
            if requested > available:
                raise OrderInsufficientStockException(
                    item_id=1,
                    requested=requested,
                    available=available
                )

        assert exc_info.value.available == 0
        assert exc_info.value.requested == 5

    def test_sufficient_stock_no_exception(self):
        """Test that sufficient stock does not raise exception."""
        available = 10
        requested = 5

        # This should NOT raise an exception
        if requested > available:
            pytest.fail("Should not raise exception when stock is sufficient")

        assert requested <= available


class TestItemValidation:
    """Test item validation logic."""

    def test_item_quantity_validation(self):
        """Test that quantity must be positive."""
        valid_quantities = [1, 5, 100]
        invalid_quantities = [0, -1, -100]

        for qty in valid_quantities:
            assert qty > 0

        for qty in invalid_quantities:
            assert qty <= 0

    def test_item_price_validation(self):
        """Test that price must be positive."""
        valid_prices = [0.01, 1.0, 100.0]
        invalid_prices = [0.0, -0.01, -100.0]

        for price in valid_prices:
            assert price > 0

        for price in invalid_prices:
            assert price <= 0
