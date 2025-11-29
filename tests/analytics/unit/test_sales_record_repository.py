"""
Unit tests for SalesRecordRepository

Tests CRUD operations for anonymized sales records using in-memory SQLite database.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Mock config before imports
import config
config.DB_ENCRYPTION = False
config.PAGE_ENTRIES = 8  # Required for pagination tests

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.base import Base
from models.sales_record import SalesRecord, SalesRecordDTO
from repositories.sales_record import SalesRecordRepository
from enums.currency import Currency
from enums.cryptocurrency import Cryptocurrency
from enums.order_status import OrderStatus


class TestSalesRecordRepository:
    """Test SalesRecordRepository CRUD operations."""

    @pytest.fixture
    def engine(self):
        """Create in-memory SQLite database."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def session(self, engine):
        """Create database session."""
        session = Session(engine)
        yield session
        session.rollback()
        session.close()

    @pytest.mark.asyncio
    async def test_create_many_success(self, session):
        """Test successful creation of multiple SalesRecords."""
        # Arrange
        now = datetime.now(timezone.utc)

        dto1 = SalesRecordDTO(
            sale_date=now,
            sale_hour=14,
            sale_weekday=1,
            category_name="Electronics",
            subcategory_name="Phones",
            quantity=1,
            is_physical=True,
            item_total_price=100.0,
            currency=Currency.EUR,
            average_unit_price=100.0,
            order_total_price=100.0,
            order_shipping_cost=5.0,
            order_wallet_used=0.0,
            payment_method="crypto_only",
            crypto_currency=Cryptocurrency.BTC,
            status=OrderStatus.PAID,
            is_refunded=False,
            shipping_type="standard"
        )

        dto2 = SalesRecordDTO(
            sale_date=now,
            sale_hour=14,
            sale_weekday=1,
            category_name="Electronics",
            subcategory_name="Accessories",
            quantity=1,
            is_physical=False,
            item_total_price=50.0,
            currency=Currency.EUR,
            average_unit_price=50.0,
            order_total_price=100.0,
            order_shipping_cost=5.0,
            order_wallet_used=0.0,
            payment_method="crypto_only",
            crypto_currency=Cryptocurrency.BTC,
            status=OrderStatus.PAID,
            is_refunded=False,
            shipping_type=None
        )

        dtos = [dto1, dto2]

        # Act
        result = await SalesRecordRepository.create_many(dtos, session)
        session.commit()

        # Assert
        assert len(result) == 2
        assert all(isinstance(id, int) for id in result)

        # Verify records were created
        records = session.query(SalesRecord).all()
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_get_total_revenue_last_30_days(self, session):
        """Test retrieval of total revenue for last 30 days."""
        # Arrange
        now = datetime.now(timezone.utc)

        # Create records within 30 days
        dto1 = SalesRecordDTO(
            sale_date=now - timedelta(days=10),
            sale_hour=14,
            sale_weekday=1,
            category_name="Electronics",
            subcategory_name="Phones",
            quantity=1,
            is_physical=True,
            item_total_price=100.0,
            currency=Currency.EUR,
            average_unit_price=100.0,
            order_total_price=100.0,
            order_shipping_cost=5.0,
            order_wallet_used=0.0,
            payment_method="crypto_only",
            crypto_currency=Cryptocurrency.BTC,
            status=OrderStatus.PAID,
            is_refunded=False,
            shipping_type="standard"
        )

        dto2 = SalesRecordDTO(
            sale_date=now - timedelta(days=5),
            sale_hour=10,
            sale_weekday=3,
            category_name="Books",
            subcategory_name="Fiction",
            quantity=1,
            is_physical=False,
            item_total_price=50.0,
            currency=Currency.EUR,
            average_unit_price=50.0,
            order_total_price=50.0,
            order_shipping_cost=0.0,
            order_wallet_used=10.0,
            payment_method="mixed",
            crypto_currency=Cryptocurrency.ETH,
            status=OrderStatus.PAID,
            is_refunded=False,
            shipping_type=None
        )

        # Create refunded record (should be excluded)
        dto3 = SalesRecordDTO(
            sale_date=now - timedelta(days=3),
            sale_hour=12,
            sale_weekday=5,
            category_name="Electronics",
            subcategory_name="Accessories",
            quantity=1,
            is_physical=True,
            item_total_price=75.0,
            currency=Currency.EUR,
            average_unit_price=75.0,
            order_total_price=75.0,
            order_shipping_cost=3.0,
            order_wallet_used=0.0,
            payment_method="crypto_only",
            crypto_currency=Cryptocurrency.BTC,
            status=OrderStatus.CANCELLED_BY_USER,
            is_refunded=True,  # Refunded - should be excluded
            shipping_type="express"
        )

        await SalesRecordRepository.create_many([dto1, dto2, dto3], session)
        session.commit()

        # Act
        result = await SalesRecordRepository.get_total_revenue(30, session)

        # Assert
        assert result == 150.0  # 100 + 50, excluding refunded 75

    @pytest.mark.asyncio
    async def test_get_total_revenue_no_sales(self, session):
        """Test total revenue with no sales records."""
        # Act
        result = await SalesRecordRepository.get_total_revenue(30, session)

        # Assert
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_get_total_items_sold_last_7_days(self, session):
        """Test retrieval of total items sold for last 7 days."""
        # Arrange
        now = datetime.now(timezone.utc)

        # Record within 7 days
        dto1 = SalesRecordDTO(
            sale_date=now - timedelta(days=2),
            sale_hour=14,
            sale_weekday=1,
            category_name="Electronics",
            subcategory_name="Phones",
            quantity=1,
            is_physical=True,
            item_total_price=100.0,
            currency=Currency.EUR,
            average_unit_price=100.0,
            order_total_price=100.0,
            order_shipping_cost=5.0,
            order_wallet_used=0.0,
            payment_method="crypto_only",
            crypto_currency=Cryptocurrency.BTC,
            status=OrderStatus.PAID,
            is_refunded=False,
            shipping_type="standard"
        )

        # Record older than 7 days (should be excluded)
        dto2 = SalesRecordDTO(
            sale_date=now - timedelta(days=10),
            sale_hour=10,
            sale_weekday=3,
            category_name="Books",
            subcategory_name="Fiction",
            quantity=1,
            is_physical=False,
            item_total_price=50.0,
            currency=Currency.EUR,
            average_unit_price=50.0,
            order_total_price=50.0,
            order_shipping_cost=0.0,
            order_wallet_used=10.0,
            payment_method="mixed",
            crypto_currency=Cryptocurrency.ETH,
            status=OrderStatus.PAID,
            is_refunded=False,
            shipping_type=None
        )

        await SalesRecordRepository.create_many([dto1, dto2], session)
        session.commit()

        # Act
        result = await SalesRecordRepository.get_total_items_sold(7, session)

        # Assert
        assert result == 1  # Only dto1 within 7 days

    @pytest.mark.asyncio
    async def test_get_total_items_sold_no_sales(self, session):
        """Test total items sold with no sales records."""
        # Act
        result = await SalesRecordRepository.get_total_items_sold(7, session)

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_subcategory_sales_grouped_basic(self, session):
        """Test get_subcategory_sales_grouped with basic data."""
        # Arrange
        now = datetime.now(timezone.utc)

        dto1 = SalesRecordDTO(
            sale_date=now,
            sale_hour=14,
            sale_weekday=1,
            category_name="Electronics",
            subcategory_name="Phones",
            quantity=1,
            is_physical=True,
            item_total_price=500.0,
            currency=Currency.EUR,
            average_unit_price=500.0,
            order_total_price=500.0,
            order_shipping_cost=5.0,
            order_wallet_used=0.0,
            payment_method="crypto_only",
            crypto_currency=Cryptocurrency.BTC,
            status=OrderStatus.PAID,
            is_refunded=False
        )

        dto2 = SalesRecordDTO(
            sale_date=now - timedelta(days=1),
            sale_hour=10,
            sale_weekday=0,
            category_name="Electronics",
            subcategory_name="Laptops",
            quantity=1,
            is_physical=True,
            item_total_price=1200.0,
            currency=Currency.EUR,
            average_unit_price=1200.0,
            order_total_price=1200.0,
            order_shipping_cost=10.0,
            order_wallet_used=0.0,
            payment_method="crypto_only",
            crypto_currency=Cryptocurrency.ETH,
            status=OrderStatus.PAID,
            is_refunded=False
        )

        await SalesRecordRepository.create_many([dto1, dto2], session)
        session.commit()

        # Act
        result = await SalesRecordRepository.get_subcategory_sales_grouped(
            start_date=now - timedelta(days=7),
            end_date=now,
            page=0,
            session=session
        )

        # Assert
        assert len(result) == 2  # 2 subcategories
        # Should be sorted by revenue DESC (Laptops 1200 > Phones 500)
        assert result[0]['subcategory'] == 'Laptops'
        assert result[0]['total_revenue'] == 1200.0
        assert result[1]['subcategory'] == 'Phones'
        assert result[1]['total_revenue'] == 500.0

    @pytest.mark.asyncio
    async def test_get_subcategory_count(self, session):
        """Test get_subcategory_count."""
        # Arrange
        now = datetime.now(timezone.utc)

        dto1 = SalesRecordDTO(
            sale_date=now,
            sale_hour=14,
            sale_weekday=1,
            category_name="Electronics",
            subcategory_name="Phones",
            quantity=1,
            is_physical=True,
            item_total_price=500.0,
            currency=Currency.EUR,
            average_unit_price=500.0,
            order_total_price=500.0,
            order_shipping_cost=5.0,
            order_wallet_used=0.0,
            payment_method="crypto_only",
            crypto_currency=Cryptocurrency.BTC,
            status=OrderStatus.PAID,
            is_refunded=False
        )

        dto2 = SalesRecordDTO(
            sale_date=now,
            sale_hour=10,
            sale_weekday=1,
            category_name="Electronics",
            subcategory_name="Laptops",
            quantity=1,
            is_physical=True,
            item_total_price=1200.0,
            currency=Currency.EUR,
            average_unit_price=1200.0,
            order_total_price=1200.0,
            order_shipping_cost=10.0,
            order_wallet_used=0.0,
            payment_method="crypto_only",
            crypto_currency=Cryptocurrency.ETH,
            status=OrderStatus.PAID,
            is_refunded=False
        )

        # Same subcategory as dto1 (should not count twice)
        dto3 = SalesRecordDTO(
            sale_date=now,
            sale_hour=15,
            sale_weekday=1,
            category_name="Electronics",
            subcategory_name="Phones",
            quantity=1,
            is_physical=True,
            item_total_price=450.0,
            currency=Currency.EUR,
            average_unit_price=450.0,
            order_total_price=450.0,
            order_shipping_cost=5.0,
            order_wallet_used=0.0,
            payment_method="wallet_only",
            status=OrderStatus.PAID,
            is_refunded=False
        )

        await SalesRecordRepository.create_many([dto1, dto2, dto3], session)
        session.commit()

        # Act
        result = await SalesRecordRepository.get_subcategory_count(
            start_date=now - timedelta(days=7),
            end_date=now,
            session=session
        )

        # Assert
        assert result == 2  # Phones and Laptops (Phones counted once despite 2 records)

    @pytest.mark.asyncio
    async def test_get_all_sales_for_csv(self, session):
        """Test get_all_sales_for_csv returns all records."""
        # Arrange
        now = datetime.now(timezone.utc)

        dtos = []
        for i in range(10):
            dtos.append(SalesRecordDTO(
                sale_date=now - timedelta(days=i),
                sale_hour=14,
                sale_weekday=i % 7,
                category_name="Category" + str(i % 3),
                subcategory_name="Subcategory" + str(i),
                quantity=1,
                is_physical=True,
                item_total_price=100.0 * (i + 1),
                currency=Currency.EUR,
                average_unit_price=100.0 * (i + 1),
                order_total_price=100.0 * (i + 1),
                order_shipping_cost=5.0,
                order_wallet_used=0.0,
                payment_method="crypto_only",
                crypto_currency=Cryptocurrency.BTC,
                status=OrderStatus.PAID,
                is_refunded=False
            ))

        await SalesRecordRepository.create_many(dtos, session)
        session.commit()

        # Act
        result = await SalesRecordRepository.get_all_sales_for_csv(session)

        # Assert
        assert len(result) == 10  # All 10 records returned
        # Should be sorted by date DESC (newest first)
        assert result[0].sale_date >= result[-1].sale_date
