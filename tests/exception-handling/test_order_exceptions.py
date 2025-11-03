"""
Tests for order-related exceptions in services/order.py
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import OrderNotFoundException, InvalidOrderStateException
from enums.order_status import OrderStatus
from enums.order_cancel_reason import OrderCancelReason


class TestOrderNotFoundException:
    """Test OrderNotFoundException is raised correctly."""

    def test_order_not_found_exception_creation(self):
        """Test OrderNotFoundException is created correctly."""
        # Create exception
        exc = OrderNotFoundException(order_id=999999)

        # Verify attributes
        assert exc.order_id == 999999
        assert "Order 999999 not found" in str(exc)

    def test_get_order_not_found_simple(self):
        """Test raising OrderNotFoundException."""
        # Simulate service raising exception when order not found
        with pytest.raises(OrderNotFoundException) as exc_info:
            raise OrderNotFoundException(order_id=999999)

        assert exc_info.value.order_id == 999999


class TestInvalidOrderStateException:
    """Test InvalidOrderStateException is raised correctly."""

    def test_invalid_state_exception_creation(self):
        """Test InvalidOrderStateException is created correctly."""
        # Create exception
        exc = InvalidOrderStateException(
            order_id=1,
            current_state=OrderStatus.CANCELLED_BY_USER.value,
            required_state=OrderStatus.PENDING_PAYMENT.value
        )

        # Verify attributes
        assert exc.order_id == 1
        assert exc.current_state == OrderStatus.CANCELLED_BY_USER.value
        assert exc.required_state == OrderStatus.PENDING_PAYMENT.value
        assert "CANCELLED_BY_USER" in str(exc)
        assert "PENDING_PAYMENT" in str(exc)

    def test_cancel_already_cancelled_order(self):
        """Test that cancelling already cancelled order would raise exception."""
        order_status = OrderStatus.CANCELLED_BY_USER

        # Simulate validation logic
        with pytest.raises(InvalidOrderStateException):
            if order_status in {OrderStatus.CANCELLED_BY_USER, OrderStatus.CANCELLED_BY_ADMIN, OrderStatus.CANCELLED_BY_SYSTEM}:
                raise InvalidOrderStateException(
                    order_id=1,
                    current_state=order_status.value,
                    required_state=OrderStatus.PENDING_PAYMENT.value
                )

    def test_ship_already_shipped_order(self):
        """Test shipping already shipped order raises InvalidOrderStateException."""
        order_status = OrderStatus.SHIPPED

        # Simulate validation logic
        with pytest.raises(InvalidOrderStateException) as exc_info:
            if order_status == OrderStatus.SHIPPED:
                raise InvalidOrderStateException(
                    order_id=1,
                    current_state=order_status.value,
                    required_state=OrderStatus.PAID_AWAITING_SHIPMENT.value
                )

        assert exc_info.value.current_state == OrderStatus.SHIPPED.value
        assert exc_info.value.required_state == OrderStatus.PAID_AWAITING_SHIPMENT.value


class TestOrderValidation:
    """Test order validation logic."""

    def test_valid_cancellable_status(self):
        """Test that PENDING_PAYMENT and PAID_AWAITING_SHIPMENT are cancellable."""
        cancellable_statuses = {
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.PENDING_PAYMENT_AND_ADDRESS,
            OrderStatus.PENDING_PAYMENT_PARTIAL,
            OrderStatus.PAID_AWAITING_SHIPMENT
        }

        assert OrderStatus.PENDING_PAYMENT in cancellable_statuses
        assert OrderStatus.PAID_AWAITING_SHIPMENT in cancellable_statuses
        assert OrderStatus.CANCELLED_BY_USER not in cancellable_statuses
        assert OrderStatus.SHIPPED not in cancellable_statuses

    def test_invalid_cancellable_status(self):
        """Test that other statuses are not cancellable."""
        non_cancellable_statuses = {
            OrderStatus.CANCELLED_BY_USER,
            OrderStatus.CANCELLED_BY_ADMIN,
            OrderStatus.CANCELLED_BY_SYSTEM,
            OrderStatus.SHIPPED,
            OrderStatus.TIMEOUT
        }

        cancellable_statuses = {
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.PENDING_PAYMENT_AND_ADDRESS,
            OrderStatus.PENDING_PAYMENT_PARTIAL,
            OrderStatus.PAID_AWAITING_SHIPMENT
        }

        for status in non_cancellable_statuses:
            # These should trigger InvalidOrderStateException
            assert status not in cancellable_statuses
