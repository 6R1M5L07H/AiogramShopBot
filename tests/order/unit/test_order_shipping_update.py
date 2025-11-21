"""
Unit Tests for OrderService.update_shipping_selection()

Tests order shipping update logic with various scenarios and edge cases.
Follows strict Service/UI separation (no Telegram objects).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from services.order import OrderService
from models.order import OrderDTO
from enums.order_status import OrderStatus
from enums.currency import Currency


class TestUpdateShippingSelection:
    """Test update_shipping_selection() method."""

    @pytest.mark.asyncio
    @patch('services.order.OrderRepository.get_by_id')
    @patch('services.order.OrderRepository.update')
    @patch('services.shipping_upsell.ShippingUpsellService.get_shipping_type_details')
    async def test_update_shipping_success(
        self,
        mock_get_shipping_details,
        mock_order_update,
        mock_order_get
    ):
        """Test successful shipping type update."""
        # Arrange
        session = AsyncMock()
        order_id = 123

        # Existing order with base shipping
        existing_order = OrderDTO(
            id=order_id,
            user_id=1,
            status=OrderStatus.PENDING_PAYMENT,
            total_price=50.00,
            shipping_cost=0.00,
            shipping_type_key="paeckchen",
            currency=Currency.EUR
        )
        mock_order_get.return_value = existing_order

        # Upgrade shipping type details
        mock_get_shipping_details.return_value = {
            "name": "Paket 2kg Versichert",
            "charged_cost": 1.50,
            "has_tracking": True
        }

        # Act
        result = await OrderService.update_shipping_selection(
            order_id=order_id,
            shipping_type_key="paket_2kg",
            session=session
        )

        # Assert
        assert result.shipping_type_key == "paket_2kg"
        assert result.shipping_cost == 1.50
        assert result.total_price == 51.50  # 50.00 + 1.50
        mock_order_update.assert_called_once()

    @pytest.mark.asyncio
    @patch('services.order.OrderRepository.get_by_id')
    @patch('services.order.OrderRepository.update')
    @patch('services.shipping_upsell.ShippingUpsellService.get_shipping_type_details')
    async def test_update_shipping_replace_existing_cost(
        self,
        mock_get_shipping_details,
        mock_order_update,
        mock_order_get
    ):
        """Test update when order already has shipping cost."""
        # Arrange
        session = AsyncMock()
        order_id = 123

        # Existing order with non-zero shipping
        existing_order = OrderDTO(
            id=order_id,
            user_id=1,
            status=OrderStatus.PENDING_PAYMENT,
            total_price=52.00,  # 50 + 2
            shipping_cost=2.00,
            shipping_type_key="paket_5kg",
            currency=Currency.EUR
        )
        mock_order_get.return_value = existing_order

        # Downgrade to cheaper shipping
        mock_get_shipping_details.return_value = {
            "name": "Paket 2kg",
            "charged_cost": 1.50
        }

        # Act
        result = await OrderService.update_shipping_selection(
            order_id=order_id,
            shipping_type_key="paket_2kg",
            session=session
        )

        # Assert
        assert result.shipping_type_key == "paket_2kg"
        assert result.shipping_cost == 1.50
        assert result.total_price == 51.50  # (52.00 - 2.00) + 1.50
        mock_order_update.assert_called_once()

    @pytest.mark.asyncio
    @patch('services.order.OrderRepository.get_by_id')
    async def test_update_shipping_order_not_found(self, mock_order_get):
        """Test with non-existent order."""
        # Arrange
        session = AsyncMock()
        mock_order_get.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Order .* not found"):
            await OrderService.update_shipping_selection(
                order_id=999,
                shipping_type_key="paket_2kg",
                session=session
            )

    @pytest.mark.asyncio
    @patch('services.order.OrderRepository.get_by_id')
    @patch('services.shipping_upsell.ShippingUpsellService.get_shipping_type_details')
    async def test_update_shipping_invalid_shipping_type(
        self,
        mock_get_shipping_details,
        mock_order_get
    ):
        """Test with invalid shipping type key."""
        # Arrange
        session = AsyncMock()

        existing_order = OrderDTO(
            id=123,
            user_id=1,
            status=OrderStatus.PENDING_PAYMENT,
            total_price=50.00,
            shipping_cost=0.00,
            shipping_type_key="paeckchen",
            currency=Currency.EUR
        )
        mock_order_get.return_value = existing_order
        mock_get_shipping_details.return_value = None  # Invalid type

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid shipping type"):
            await OrderService.update_shipping_selection(
                order_id=123,
                shipping_type_key="invalid_key",
                session=session
            )

    @pytest.mark.asyncio
    @patch('services.order.OrderRepository.get_by_id')
    @patch('services.order.OrderRepository.update')
    @patch('services.shipping_upsell.ShippingUpsellService.get_shipping_type_details')
    async def test_update_shipping_zero_to_zero(
        self,
        mock_get_shipping_details,
        mock_order_update,
        mock_order_get
    ):
        """Test edge case: update from free shipping to another free shipping."""
        # Arrange
        session = AsyncMock()

        existing_order = OrderDTO(
            id=123,
            user_id=1,
            status=OrderStatus.PENDING_PAYMENT,
            total_price=50.00,
            shipping_cost=0.00,
            shipping_type_key="paeckchen",
            currency=Currency.EUR
        )
        mock_order_get.return_value = existing_order

        mock_get_shipping_details.return_value = {
            "name": "Maxibrief",
            "charged_cost": 0.00
        }

        # Act
        result = await OrderService.update_shipping_selection(
            order_id=123,
            shipping_type_key="maxibrief",
            session=session
        )

        # Assert
        assert result.shipping_type_key == "maxibrief"
        assert result.shipping_cost == 0.00
        assert result.total_price == 50.00  # Unchanged
        mock_order_update.assert_called_once()

    @pytest.mark.asyncio
    @patch('services.order.OrderRepository.get_by_id')
    @patch('services.order.OrderRepository.update')
    @patch('services.shipping_upsell.ShippingUpsellService.get_shipping_type_details')
    async def test_update_shipping_precision(
        self,
        mock_get_shipping_details,
        mock_order_update,
        mock_order_get
    ):
        """Test floating-point precision in price calculation."""
        # Arrange
        session = AsyncMock()

        existing_order = OrderDTO(
            id=123,
            user_id=1,
            status=OrderStatus.PENDING_PAYMENT,
            total_price=50.10,
            shipping_cost=0.10,
            shipping_type_key="paeckchen",
            currency=Currency.EUR
        )
        mock_order_get.return_value = existing_order

        mock_get_shipping_details.return_value = {
            "name": "Paket",
            "charged_cost": 0.20
        }

        # Act
        result = await OrderService.update_shipping_selection(
            order_id=123,
            shipping_type_key="paket",
            session=session
        )

        # Assert
        assert result.total_price == 50.20  # (50.10 - 0.10) + 0.20
        assert isinstance(result.total_price, float)

    @pytest.mark.asyncio
    @patch('services.order.OrderRepository.get_by_id')
    @patch('services.order.OrderRepository.update')
    @patch('services.shipping_upsell.ShippingUpsellService.get_shipping_type_details')
    async def test_update_shipping_preserves_other_fields(
        self,
        mock_get_shipping_details,
        mock_order_update,
        mock_order_get
    ):
        """Test that update doesn't modify unrelated order fields."""
        # Arrange
        session = AsyncMock()

        existing_order = OrderDTO(
            id=123,
            user_id=1,
            status=OrderStatus.PENDING_PAYMENT,
            total_price=50.00,
            shipping_cost=0.00,
            shipping_type_key="paeckchen",
            currency=Currency.EUR,
            wallet_used=5.00,
            tier_breakdown_json='{"some": "data"}'
        )
        mock_order_get.return_value = existing_order

        mock_get_shipping_details.return_value = {
            "name": "Paket",
            "charged_cost": 1.50
        }

        # Act
        result = await OrderService.update_shipping_selection(
            order_id=123,
            shipping_type_key="paket",
            session=session
        )

        # Assert - Other fields unchanged
        assert result.user_id == 1
        assert result.status == OrderStatus.PENDING_PAYMENT
        assert result.currency == Currency.EUR
        assert result.wallet_used == 5.00
        assert result.tier_breakdown_json == '{"some": "data"}'


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    @patch('services.order.OrderRepository.get_by_id')
    @patch('services.order.OrderRepository.update')
    @patch('services.shipping_upsell.ShippingUpsellService.get_shipping_type_details')
    async def test_update_with_none_shipping_type_key(
        self,
        mock_get_shipping_details,
        mock_order_update,
        mock_order_get
    ):
        """Test update when order initially has None as shipping_type_key."""
        # Arrange
        session = AsyncMock()

        existing_order = OrderDTO(
            id=123,
            user_id=1,
            status=OrderStatus.PENDING_PAYMENT,
            total_price=50.00,
            shipping_cost=0.00,
            shipping_type_key=None,  # No shipping type set
            currency=Currency.EUR
        )
        mock_order_get.return_value = existing_order

        mock_get_shipping_details.return_value = {
            "name": "Paket",
            "charged_cost": 1.50
        }

        # Act
        result = await OrderService.update_shipping_selection(
            order_id=123,
            shipping_type_key="paket",
            session=session
        )

        # Assert
        assert result.shipping_type_key == "paket"
        assert result.shipping_cost == 1.50
        assert result.total_price == 51.50

    @pytest.mark.asyncio
    @patch('services.order.OrderRepository.get_by_id')
    @patch('services.order.OrderRepository.update')
    @patch('services.shipping_upsell.ShippingUpsellService.get_shipping_type_details')
    async def test_update_with_large_shipping_cost(
        self,
        mock_get_shipping_details,
        mock_order_update,
        mock_order_get
    ):
        """Test update with unusually large shipping cost."""
        # Arrange
        session = AsyncMock()

        existing_order = OrderDTO(
            id=123,
            user_id=1,
            status=OrderStatus.PENDING_PAYMENT,
            total_price=100.00,
            shipping_cost=0.00,
            shipping_type_key="paeckchen",
            currency=Currency.EUR
        )
        mock_order_get.return_value = existing_order

        mock_get_shipping_details.return_value = {
            "name": "Express International",
            "charged_cost": 50.00  # Expensive shipping
        }

        # Act
        result = await OrderService.update_shipping_selection(
            order_id=123,
            shipping_type_key="express_intl",
            session=session
        )

        # Assert
        assert result.shipping_cost == 50.00
        assert result.total_price == 150.00  # 100 + 50
