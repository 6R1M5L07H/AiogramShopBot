"""
Automated tests for shipping_management handler refactoring.

These tests ensure that moving logic from handlers to services
doesn't break existing functionality.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from aiogram.types import CallbackQuery, Message, User, Chat
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Mock config before importing any modules that use it
import sys
sys.modules['config'] = MagicMock()

from enums.order_status import OrderStatus
from models.order import Order
from models.invoice import Invoice
from models.user import User as UserModel


# Fixtures

@pytest.fixture
def mock_session():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_callback():
    """Mock Telegram callback query."""
    callback = Mock(spec=CallbackQuery)
    callback.from_user = Mock(spec=User)
    callback.from_user.id = 12345
    callback.message = Mock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def sample_order():
    """Sample order for testing."""
    order = Mock(spec=Order)
    order.id = 1
    order.user_id = 12345
    order.total_price_eur = 100.0
    order.status = OrderStatus.PENDING_SHIPMENT
    order.shipping_address = "Test Address 123"
    order.created_at = "2025-11-01 10:00:00"
    order.items = []
    return order


@pytest.fixture
def sample_invoice():
    """Sample invoice for testing."""
    invoice = Mock(spec=Invoice)
    invoice.id = "INV-001"
    invoice.order_id = 1
    invoice.amount_eur = 100.0
    invoice.cryptocurrency = "BTC"
    invoice.crypto_address = "bc1q..."
    return invoice


@pytest.fixture
def sample_user():
    """Sample user for testing."""
    user = Mock(spec=UserModel)
    user.telegram_id = 12345
    user.telegram_username = "testuser"
    user.wallet_balance = 50.0
    return user


# Test: Get Pending Orders

@pytest.mark.asyncio
async def test_get_pending_orders_empty(mock_session):
    """Test getting pending orders when list is empty."""
    from handlers.admin.shipping_management import show_pending_orders

    # Mock repository call
    with patch('repositories.order.OrderRepository.get_orders_awaiting_shipment') as mock_repo:
        mock_repo.return_value = []

        # Create mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock(spec=Message)
        callback.message.edit_text = AsyncMock()

        # Call function
        await show_pending_orders(callback=callback, session=mock_session)

        # Verify repository was called
        mock_repo.assert_called_once_with(mock_session)

        # Verify message was sent
        callback.message.edit_text.assert_called_once()
        call_args = callback.message.edit_text.call_args
        message_text = call_args[1]['text']

        # Should contain "no orders" message
        assert "keine" in message_text.lower() or "no orders" in message_text.lower()


@pytest.mark.asyncio
async def test_get_pending_orders_with_data(mock_session, sample_order, sample_invoice, sample_user):
    """Test getting pending orders with actual data."""
    from handlers.admin.shipping_management import show_pending_orders

    # Mock repository calls
    with patch('repositories.order.OrderRepository.get_orders_awaiting_shipment') as mock_order_repo, \
         patch('repositories.invoice.InvoiceRepository.get_by_order_id') as mock_invoice_repo, \
         patch('repositories.user.UserRepository.get_by_id') as mock_user_repo:

        mock_order_repo.return_value = [sample_order]
        mock_invoice_repo.return_value = sample_invoice
        mock_user_repo.return_value = sample_user

        # Create mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock(spec=Message)
        callback.message.edit_text = AsyncMock()

        # Call function
        await show_pending_orders(callback=callback, session=mock_session)

        # Verify repositories were called
        mock_order_repo.assert_called_once_with(mock_session)
        assert mock_invoice_repo.called
        assert mock_user_repo.called

        # Verify message was sent
        callback.message.edit_text.assert_called_once()
        call_args = callback.message.edit_text.call_args
        message_text = call_args[1]['text']

        # Should contain order info
        assert sample_invoice.id in message_text
        assert sample_user.telegram_username in message_text


# Test: Show Order Details

@pytest.mark.asyncio
async def test_show_order_details(mock_session, sample_order, sample_invoice, sample_user):
    """Test showing order details."""
    from handlers.admin.shipping_management import show_order_details

    # Mock repository calls
    with patch('repositories.order.OrderRepository.get_by_id_with_items') as mock_order_repo, \
         patch('repositories.invoice.InvoiceRepository.get_by_order_id') as mock_invoice_repo, \
         patch('repositories.user.UserRepository.get_by_id') as mock_user_repo:

        mock_order_repo.return_value = sample_order
        mock_invoice_repo.return_value = sample_invoice
        mock_user_repo.return_value = sample_user

        # Create mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock(spec=Message)
        callback.message.edit_text = AsyncMock()

        # Call function
        await show_order_details(callback=callback, session=mock_session, order_id=1)

        # Verify repositories were called
        mock_order_repo.assert_called_once_with(1, mock_session)
        mock_invoice_repo.assert_called_once_with(1, mock_session)
        mock_user_repo.assert_called_once_with(sample_order.user_id, mock_session)

        # Verify message was sent
        callback.message.edit_text.assert_called_once()
        call_args = callback.message.edit_text.call_args
        message_text = call_args[1]['text']

        # Should contain key order details
        assert sample_invoice.id in message_text
        assert sample_order.shipping_address in message_text


@pytest.mark.asyncio
async def test_show_order_details_not_found(mock_session):
    """Test showing order details when order doesn't exist."""
    from handlers.admin.shipping_management import show_order_details

    # Mock repository call returning None
    with patch('repositories.order.OrderRepository.get_by_id_with_items') as mock_repo:
        mock_repo.return_value = None

        # Create mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        # Call function
        await show_order_details(callback=callback, session=mock_session, order_id=999)

        # Verify repository was called
        mock_repo.assert_called_once_with(999, mock_session)

        # Should show error message (either via edit_text or answer)
        assert callback.message.edit_text.called or callback.answer.called


# Test: Mark as Shipped

@pytest.mark.asyncio
async def test_mark_as_shipped_success(mock_session, sample_order, sample_invoice):
    """Test marking order as shipped successfully."""
    from handlers.admin.shipping_management import mark_as_shipped

    # Mock repository calls
    with patch('repositories.order.OrderRepository.get_by_id') as mock_get_order, \
         patch('repositories.order.OrderRepository.update_status') as mock_update_status, \
         patch('repositories.invoice.InvoiceRepository.get_by_order_id') as mock_get_invoice, \
         patch('services.notification.NotificationService.send_to_user') as mock_notify:

        mock_get_order.return_value = sample_order
        mock_update_status.return_value = None
        mock_get_invoice.return_value = sample_invoice
        mock_notify.return_value = None

        # Create mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        # Call function
        await mark_as_shipped(callback=callback, session=mock_session, order_id=1)

        # Verify status was updated
        mock_update_status.assert_called_once_with(1, OrderStatus.SHIPPED, mock_session)

        # Verify user was notified
        mock_notify.assert_called_once()

        # Verify confirmation message
        callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_mark_as_shipped_order_not_found(mock_session):
    """Test marking non-existent order as shipped."""
    from handlers.admin.shipping_management import mark_as_shipped

    # Mock repository call returning None
    with patch('repositories.order.OrderRepository.get_by_id') as mock_repo:
        mock_repo.return_value = None

        # Create mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        # Call function
        await mark_as_shipped(callback=callback, session=mock_session, order_id=999)

        # Should show error (either via answer or edit_text)
        assert callback.answer.called or callback.message.edit_text.called


# Test: Integration - Full Flow

@pytest.mark.asyncio
async def test_full_shipping_flow(mock_session, sample_order, sample_invoice, sample_user):
    """Test complete shipping management flow."""
    from handlers.admin.shipping_management import show_pending_orders, show_order_details, mark_as_shipped

    with patch('repositories.order.OrderRepository.get_orders_awaiting_shipment') as mock_list, \
         patch('repositories.order.OrderRepository.get_by_id_with_items') as mock_get_order, \
         patch('repositories.order.OrderRepository.get_by_id') as mock_get_order_simple, \
         patch('repositories.order.OrderRepository.update_status') as mock_update, \
         patch('repositories.invoice.InvoiceRepository.get_by_order_id') as mock_get_invoice, \
         patch('repositories.user.UserRepository.get_by_id') as mock_get_user, \
         patch('services.notification.NotificationService.send_to_user') as mock_notify:

        # Setup mocks
        mock_list.return_value = [sample_order]
        mock_get_order.return_value = sample_order
        mock_get_order_simple.return_value = sample_order
        mock_get_invoice.return_value = sample_invoice
        mock_get_user.return_value = sample_user
        mock_notify.return_value = None

        # Create mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        # Step 1: Show pending orders
        await show_pending_orders(callback=callback, session=mock_session)
        assert callback.message.edit_text.called

        # Step 2: Show order details
        await show_order_details(callback=callback, session=mock_session, order_id=1)
        assert callback.message.edit_text.call_count >= 2

        # Step 3: Mark as shipped
        await mark_as_shipped(callback=callback, session=mock_session, order_id=1)
        mock_update.assert_called_once_with(1, OrderStatus.SHIPPED, mock_session)
        mock_notify.assert_called_once()


# Test: Error Handling

@pytest.mark.asyncio
async def test_database_error_handling(mock_session):
    """Test that database errors are handled gracefully."""
    from handlers.admin.shipping_management import show_pending_orders

    # Mock repository raising exception
    with patch('repositories.order.OrderRepository.get_orders_awaiting_shipment') as mock_repo:
        mock_repo.side_effect = Exception("Database connection error")

        # Create mock callback
        callback = Mock(spec=CallbackQuery)
        callback.message = Mock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        # Call should not crash, but handle error
        try:
            await show_pending_orders(callback=callback, session=mock_session)
            # If it doesn't crash, that's good
            assert True
        except Exception as e:
            # If it does crash, fail the test
            pytest.fail(f"Handler should handle database errors gracefully, but got: {e}")


# Parametrized Tests

@pytest.mark.parametrize("order_count", [0, 1, 5, 10])
@pytest.mark.asyncio
async def test_pending_orders_various_counts(mock_session, sample_order, order_count):
    """Test pending orders display with various order counts."""
    from handlers.admin.shipping_management import show_pending_orders

    orders = [sample_order] * order_count

    with patch('repositories.order.OrderRepository.get_orders_awaiting_shipment') as mock_repo, \
         patch('repositories.invoice.InvoiceRepository.get_by_order_id'), \
         patch('repositories.user.UserRepository.get_by_id'):

        mock_repo.return_value = orders

        callback = Mock(spec=CallbackQuery)
        callback.message = Mock(spec=Message)
        callback.message.edit_text = AsyncMock()

        await show_pending_orders(callback=callback, session=mock_session)

        # Verify function completed
        callback.message.edit_text.assert_called_once()
