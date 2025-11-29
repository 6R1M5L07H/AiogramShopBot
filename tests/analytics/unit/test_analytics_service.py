"""
Unit tests for AnalyticsService

Tests the creation of anonymized SalesRecord and ViolationStatistics entries
for long-term analytics while ensuring data minimization principles.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from services.analytics import AnalyticsService
from enums.violation_type import ViolationType
from enums.order_status import OrderStatus
from enums.currency import Currency
from enums.cryptocurrency import Cryptocurrency


class TestAnalyticsServiceSalesRecords:
    """Test SalesRecord creation from orders."""

    @pytest.mark.asyncio
    async def test_create_sales_records_from_order_success(self):
        """Test successful creation of SalesRecords for a completed order."""
        # Arrange
        order_id = 1
        session = MagicMock()

        # Mock order
        mock_order = MagicMock()
        mock_order.id = order_id
        mock_order.total_price = 100.0
        mock_order.shipping_cost = 5.0
        mock_order.wallet_used = 10.0
        mock_order.currency = Currency.EUR
        mock_order.status = OrderStatus.PAID
        mock_order.tier_breakdown_json = None

        # Mock items (2 items)
        mock_item1 = MagicMock()
        mock_item1.id = 1
        mock_item1.category_id = 1
        mock_item1.subcategory_id = 1
        mock_item1.price = 50.0
        mock_item1.is_physical = True

        mock_item2 = MagicMock()
        mock_item2.id = 2
        mock_item2.category_id = 1
        mock_item2.subcategory_id = 2
        mock_item2.price = 50.0
        mock_item2.is_physical = False

        mock_items = [mock_item1, mock_item2]

        # Mock category and subcategory
        mock_category = MagicMock()
        mock_category.name = "Electronics"

        mock_subcategory1 = MagicMock()
        mock_subcategory1.name = "Phones"

        mock_subcategory2 = MagicMock()
        mock_subcategory2.name = "Accessories"

        # Mock payment transactions
        mock_transaction = MagicMock()
        mock_transaction.crypto_currency = Cryptocurrency.BTC

        mock_transactions = [mock_transaction]

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=mock_order), \
             patch('services.analytics.ItemRepository.get_by_order_id', new_callable=AsyncMock, return_value=mock_items), \
             patch('services.analytics.PaymentTransactionRepository.get_by_order_id', new_callable=AsyncMock, return_value=mock_transactions), \
             patch('services.analytics.CategoryRepository.get_by_ids', new_callable=AsyncMock, return_value={1: mock_category}), \
             patch('services.analytics.SubcategoryRepository.get_by_ids', new_callable=AsyncMock, return_value={1: mock_subcategory1, 2: mock_subcategory2}), \
             patch('services.analytics.SalesRecordRepository.create_many', new_callable=AsyncMock, return_value=[1, 2]) as mock_create_many:

            # No need to configure side_effect anymore - using batch loading now

            # Act
            result = await AnalyticsService.create_sales_records_from_order(order_id, session)

            # Assert
            assert result == [1, 2]
            assert mock_create_many.call_count == 1

            # Verify DTOs passed to create_many
            sales_record_dtos = mock_create_many.call_args[0][0]
            assert len(sales_record_dtos) == 2

            # Check first record (physical item)
            dto1 = sales_record_dtos[0]
            assert dto1.category_name == "Electronics"
            assert dto1.subcategory_name == "Phones"
            assert dto1.quantity == 1
            assert dto1.is_physical is True
            assert dto1.item_total_price == 50.0
            assert dto1.currency == Currency.EUR
            assert dto1.order_total_price == 100.0
            assert dto1.order_shipping_cost == 5.0
            assert dto1.order_wallet_used == 10.0
            assert dto1.payment_method == "mixed"
            assert dto1.crypto_currency == Cryptocurrency.BTC
            assert dto1.status == OrderStatus.PAID
            assert dto1.is_refunded is False
            assert dto1.shipping_type is None  # shipping_type not yet implemented in schema

            # Check second record (digital item)
            dto2 = sales_record_dtos[1]
            assert dto2.category_name == "Electronics"
            assert dto2.subcategory_name == "Accessories"
            assert dto2.is_physical is False
            assert dto2.shipping_type is None  # shipping_type not yet implemented in schema

    @pytest.mark.asyncio
    async def test_create_sales_records_wallet_only_payment(self):
        """Test SalesRecords creation for wallet-only payment."""
        # Arrange
        order_id = 1
        session = MagicMock()

        mock_order = MagicMock()
        mock_order.id = order_id
        mock_order.total_price = 50.0
        mock_order.shipping_cost = 0.0
        mock_order.wallet_used = 50.0
        mock_order.currency = Currency.EUR
        mock_order.status = OrderStatus.PAID
        mock_order.tier_breakdown_json = None

        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.category_id = 1
        mock_item.subcategory_id = 1
        mock_item.price = 50.0
        mock_item.is_physical = False

        mock_category = MagicMock()
        mock_category.name = "Digital"

        mock_subcategory = MagicMock()
        mock_subcategory.name = "Software"

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=mock_order), \
             patch('services.analytics.ItemRepository.get_by_order_id', new_callable=AsyncMock, return_value=[mock_item]), \
             patch('services.analytics.PaymentTransactionRepository.get_by_order_id', new_callable=AsyncMock, return_value=[]), \
             patch('services.analytics.CategoryRepository.get_by_ids', new_callable=AsyncMock, return_value={1: mock_category}), \
             patch('services.analytics.SubcategoryRepository.get_by_ids', new_callable=AsyncMock, return_value={1: mock_subcategory}), \
             patch('services.analytics.SalesRecordRepository.create_many', new_callable=AsyncMock, return_value=[1]) as mock_create_many:

            # Act
            result = await AnalyticsService.create_sales_records_from_order(order_id, session)

            # Assert
            assert result == [1]

            sales_record_dtos = mock_create_many.call_args[0][0]
            dto = sales_record_dtos[0]
            assert dto.payment_method == "wallet_only"
            assert dto.crypto_currency is None
            assert dto.order_wallet_used == 50.0

    @pytest.mark.asyncio
    async def test_create_sales_records_order_not_found(self):
        """Test handling when order is not found."""
        # Arrange
        order_id = 999
        session = MagicMock()

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=None):
            # Act
            result = await AnalyticsService.create_sales_records_from_order(order_id, session)

            # Assert
            assert result == []

    @pytest.mark.asyncio
    async def test_create_sales_records_no_items(self):
        """Test handling when order has no items."""
        # Arrange
        order_id = 1
        session = MagicMock()

        mock_order = MagicMock()
        mock_order.id = order_id

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=mock_order), \
             patch('services.analytics.ItemRepository.get_by_order_id', new_callable=AsyncMock, return_value=[]):

            # Act
            result = await AnalyticsService.create_sales_records_from_order(order_id, session)

            # Assert
            assert result == []


class TestAnalyticsServiceViolationStatistics:
    """Test ViolationStatistics creation."""

    @pytest.mark.asyncio
    async def test_create_violation_record_underpayment_final(self):
        """Test creation of UNDERPAYMENT_FINAL violation record."""
        # Arrange
        order_id = 1
        violation_type = ViolationType.UNDERPAYMENT_FINAL
        penalty_applied = 5.0
        session = MagicMock()

        mock_order = MagicMock()
        mock_order.id = order_id
        mock_order.total_price = 100.0
        mock_order.retry_count = 1

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=mock_order), \
             patch('services.analytics.ViolationStatisticsRepository.create', new_callable=AsyncMock, return_value=1) as mock_create:

            # Act
            result = await AnalyticsService.create_violation_record(
                order_id, violation_type, session, penalty_applied
            )

            # Assert
            assert result == 1
            assert mock_create.call_count == 1

            violation_dto = mock_create.call_args[0][0]
            assert violation_dto.violation_type == ViolationType.UNDERPAYMENT_FINAL
            assert violation_dto.order_value == 100.0
            assert violation_dto.penalty_applied == 5.0
            assert violation_dto.retry_count == 1

    @pytest.mark.asyncio
    async def test_create_violation_record_late_payment(self):
        """Test creation of LATE_PAYMENT violation record."""
        # Arrange
        order_id = 2
        violation_type = ViolationType.LATE_PAYMENT
        penalty_applied = 10.0
        session = MagicMock()

        mock_order = MagicMock()
        mock_order.id = order_id
        mock_order.total_price = 200.0
        mock_order.retry_count = 0

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=mock_order), \
             patch('services.analytics.ViolationStatisticsRepository.create', new_callable=AsyncMock, return_value=2) as mock_create:

            # Act
            result = await AnalyticsService.create_violation_record(
                order_id, violation_type, session, penalty_applied
            )

            # Assert
            assert result == 2

            violation_dto = mock_create.call_args[0][0]
            assert violation_dto.violation_type == ViolationType.LATE_PAYMENT
            assert violation_dto.order_value == 200.0
            assert violation_dto.penalty_applied == 10.0
            assert violation_dto.retry_count == 0

    @pytest.mark.asyncio
    async def test_create_violation_record_timeout(self):
        """Test creation of TIMEOUT violation record."""
        # Arrange
        order_id = 3
        violation_type = ViolationType.TIMEOUT
        penalty_applied = 0.0
        session = MagicMock()

        mock_order = MagicMock()
        mock_order.id = order_id
        mock_order.total_price = 75.0
        mock_order.retry_count = 0

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=mock_order), \
             patch('services.analytics.ViolationStatisticsRepository.create', new_callable=AsyncMock, return_value=3) as mock_create:

            # Act
            result = await AnalyticsService.create_violation_record(
                order_id, violation_type, session, penalty_applied
            )

            # Assert
            assert result == 3

            violation_dto = mock_create.call_args[0][0]
            assert violation_dto.violation_type == ViolationType.TIMEOUT
            assert violation_dto.penalty_applied == 0.0

    @pytest.mark.asyncio
    async def test_create_violation_record_user_cancellation_late(self):
        """Test creation of USER_CANCELLATION_LATE violation record."""
        # Arrange
        order_id = 4
        violation_type = ViolationType.USER_CANCELLATION_LATE
        penalty_applied = 7.5
        session = MagicMock()

        mock_order = MagicMock()
        mock_order.id = order_id
        mock_order.total_price = 150.0
        mock_order.retry_count = 0

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=mock_order), \
             patch('services.analytics.ViolationStatisticsRepository.create', new_callable=AsyncMock, return_value=4) as mock_create:

            # Act
            result = await AnalyticsService.create_violation_record(
                order_id, violation_type, session, penalty_applied
            )

            # Assert
            assert result == 4

            violation_dto = mock_create.call_args[0][0]
            assert violation_dto.violation_type == ViolationType.USER_CANCELLATION_LATE

    @pytest.mark.asyncio
    async def test_create_violation_record_order_not_found(self):
        """Test handling when order is not found."""
        # Arrange
        order_id = 999
        violation_type = ViolationType.TIMEOUT
        penalty_applied = 0.0
        session = MagicMock()

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=None):
            # Act
            result = await AnalyticsService.create_violation_record(
                order_id, violation_type, session, penalty_applied
            )

            # Assert
            assert result is None


class TestAnalyticsServiceDataMinimization:
    """Test that analytics service follows data minimization principles."""

    @pytest.mark.asyncio
    async def test_sales_records_contain_no_user_id(self):
        """Verify that SalesRecords do not contain user_id."""
        # Arrange
        order_id = 1
        session = MagicMock()

        mock_order = MagicMock()
        mock_order.id = order_id
        mock_order.user_id = 12345  # Should NOT appear in SalesRecord
        mock_order.total_price = 100.0
        mock_order.shipping_cost = 5.0
        mock_order.wallet_used = 0.0
        mock_order.currency = Currency.EUR
        mock_order.status = OrderStatus.PAID
        mock_order.tier_breakdown_json = None

        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.category_id = 1
        mock_item.subcategory_id = 1
        mock_item.price = 100.0
        mock_item.is_physical = False

        mock_category = MagicMock()
        mock_category.name = "Test"

        mock_subcategory = MagicMock()
        mock_subcategory.name = "Test"

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=mock_order), \
             patch('services.analytics.ItemRepository.get_by_order_id', new_callable=AsyncMock, return_value=[mock_item]), \
             patch('services.analytics.PaymentTransactionRepository.get_by_order_id', new_callable=AsyncMock, return_value=[]), \
             patch('services.analytics.CategoryRepository.get_by_ids', new_callable=AsyncMock, return_value={1: mock_category}), \
             patch('services.analytics.SubcategoryRepository.get_by_ids', new_callable=AsyncMock, return_value={1: mock_subcategory}), \
             patch('services.analytics.SalesRecordRepository.create_many', new_callable=AsyncMock, return_value=[1]) as mock_create_many:

            # Act
            await AnalyticsService.create_sales_records_from_order(order_id, session)

            # Assert
            sales_record_dtos = mock_create_many.call_args[0][0]
            dto = sales_record_dtos[0]

            # Verify no user_id field exists in DTO
            assert not hasattr(dto, 'user_id')

    @pytest.mark.asyncio
    async def test_violation_statistics_contain_no_user_id(self):
        """Verify that ViolationStatistics do not contain user_id."""
        # Arrange
        order_id = 1
        violation_type = ViolationType.TIMEOUT
        penalty_applied = 0.0
        session = MagicMock()

        mock_order = MagicMock()
        mock_order.id = order_id
        mock_order.user_id = 12345  # Should NOT appear in ViolationStatistics
        mock_order.total_price = 100.0
        mock_order.retry_count = 0

        with patch('services.analytics.OrderRepository.get_by_id', new_callable=AsyncMock, return_value=mock_order), \
             patch('services.analytics.ViolationStatisticsRepository.create', new_callable=AsyncMock, return_value=1) as mock_create:

            # Act
            await AnalyticsService.create_violation_record(
                order_id, violation_type, penalty_applied, session
            )

            # Assert
            violation_dto = mock_create.call_args[0][0]

            # Verify no user_id field exists in DTO
            assert not hasattr(violation_dto, 'user_id')
