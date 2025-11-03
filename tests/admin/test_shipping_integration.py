"""
Integration tests for shipping management module.

Uses aiogram-tests for proper Telegram bot testing.
Manual testing checklist: SHIPPING_MANAGEMENT_TEST_GUIDE.md
"""

import pytest
from unittest.mock import AsyncMock, Mock
from aiogram.types import CallbackQuery, User, Message, Chat
from aiogram import Bot
from exceptions import OrderNotFoundException


# ============================================================================
# Smoke Tests (Module Structure)
# ============================================================================

def test_shipping_management_module_imports():
    """Test that shipping_management module can be imported."""
    try:
        from handlers.admin import shipping_management
        assert shipping_management is not None
        assert hasattr(shipping_management, 'show_awaiting_shipment_orders')
        assert hasattr(shipping_management, 'show_order_details')
        assert hasattr(shipping_management, 'mark_as_shipped_execute')
    except ImportError as e:
        pytest.fail(f"Failed to import shipping_management: {e}")


def test_required_functions_exist():
    """Test that all required functions exist in module."""
    from handlers.admin import shipping_management

    required_functions = [
        'show_awaiting_shipment_orders',
        'show_order_details',
        'mark_as_shipped_confirm',
        'mark_as_shipped_execute',
    ]

    for func_name in required_functions:
        assert hasattr(shipping_management, func_name), f"Missing function: {func_name}"


# ============================================================================
# Integration Tests (With Aiogram)
# ============================================================================

@pytest.mark.asyncio
async def test_show_awaiting_shipment_orders_empty(test_session):
    """Test showing empty pending shipments list."""
    from handlers.admin.shipping_management import show_awaiting_shipment_orders
    from callbacks import ShippingManagementCallback

    # Create mock callback query
    user = User(id=123456789, is_bot=False, first_name="Admin")
    message = Mock(spec=Message)
    message.edit_text = AsyncMock()
    message.chat = Chat(id=123456789, type="private")

    callback = Mock(spec=CallbackQuery)
    callback.from_user = user
    callback.message = message
    callback.data = ShippingManagementCallback(
        level=0,
        order_id=0,
        confirmation=False,
        page=1
    ).pack()

    # Mock bot
    bot = Mock(spec=Bot)

    try:
        await show_awaiting_shipment_orders(
            callback=callback,
            bot=bot,
            session=test_session,
            callback_data=ShippingManagementCallback(
                level=0,
                order_id=0,
                confirmation=False,
                page=1
            )
        )

        # Verify message was sent
        message.edit_text.assert_called_once()
        call_args = message.edit_text.call_args

        # Should show "no orders" message
        assert call_args is not None
        message_text = call_args[0][0] if call_args[0] else call_args.kwargs.get('text', '')
        assert len(message_text) > 0  # Some message was sent

    except Exception as e:
        pytest.fail(f"Handler raised unexpected exception: {e}")


@pytest.mark.asyncio
async def test_show_order_details_not_found(test_session):
    """Test showing order details for non-existent order.

    After refactoring: Handler should gracefully handle missing orders.
    """
    from handlers.admin.shipping_management import show_order_details
    from callbacks import ShippingManagementCallback

    # Create mock callback query
    user = User(id=123456789, is_bot=False, first_name="Admin")
    message = Mock(spec=Message)
    message.edit_text = AsyncMock()
    message.answer = AsyncMock()
    message.chat = Chat(id=123456789, type="private")

    callback = Mock(spec=CallbackQuery)
    callback.from_user = user
    callback.message = message
    callback.data = ShippingManagementCallback(
        level=1,
        order_id=99999,
        confirmation=False,
        page=1
    ).pack()
    callback.answer = AsyncMock()

    # Mock bot
    bot = Mock(spec=Bot)

    # Should raise OrderNotFoundException for non-existent order
    with pytest.raises(OrderNotFoundException) as exc_info:
        await show_order_details(
            callback=callback,
            bot=bot,
            session=test_session,
            callback_data=ShippingManagementCallback(
                level=1,
                order_id=99999,
                confirmation=False,
                page=1
            )
        )

    # Verify exception has correct order_id
    assert exc_info.value.order_id == 99999


# ============================================================================
# Service Layer Tests (To be added after refactoring)
# ============================================================================

# TODO: After creating services/shipping.py, add tests like:
#
# @pytest.mark.asyncio
# async def test_shipping_service_get_pending_orders(test_session):
#     """Test ShippingService.get_pending_orders_view()"""
#     from services.shipping import ShippingService
#
#     message_text, keyboard = await ShippingService.get_pending_orders_view(test_session)
#     assert isinstance(message_text, str)
#     assert keyboard is not None
