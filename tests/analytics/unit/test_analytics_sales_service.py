"""
Unit Tests for AnalyticsService - Sales Analytics Methods

Tests:
- get_subcategory_sales_data()
- generate_sales_csv_content()
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from services.analytics import AnalyticsService
from repositories.sales_record import SalesRecordRepository
from models.sales_record import SalesRecordDTO


class TestGetSubcategorySalesData:
    """Test AnalyticsService.get_subcategory_sales_data()"""

    @pytest.mark.asyncio
    async def test_basic_structure(self, test_session):
        """Test basic data retrieval and structure."""
        data = await AnalyticsService.get_subcategory_sales_data(
            days=30, page=0, session=test_session
        )

        assert 'subcategories' in data
        assert 'current_page' in data
        assert 'max_page' in data
        assert 'date_range' in data
        assert 'total_subcategories' in data
        assert data['current_page'] == 0
        assert isinstance(data['subcategories'], list)

    @pytest.mark.asyncio
    async def test_with_test_data(self, test_session, setup_sales_data):
        """Test with actual sales data."""
        # setup_sales_data fixture creates test records
        data = await AnalyticsService.get_subcategory_sales_data(
            days=30, page=0, session=test_session
        )

        if data['subcategories']:
            subcat = data['subcategories'][0]
            assert 'category' in subcat
            assert 'subcategory' in subcat
            assert 'sales' in subcat
            assert 'total_quantity' in subcat
            assert 'total_revenue' in subcat

    @pytest.mark.asyncio
    async def test_sorting_by_revenue(self, test_session, setup_mixed_revenue):
        """Test subcategories are sorted by total revenue (DESC)."""
        data = await AnalyticsService.get_subcategory_sales_data(
            days=30, page=0, session=test_session
        )

        if len(data['subcategories']) > 1:
            revenues = [s['total_revenue'] for s in data['subcategories']]
            assert revenues == sorted(revenues, reverse=True)

    @pytest.mark.asyncio
    async def test_date_formatting(self, test_session, setup_sales_data):
        """Test dates are formatted as 'DD.MM'."""
        data = await AnalyticsService.get_subcategory_sales_data(
            days=30, page=0, session=test_session
        )

        for subcat in data['subcategories']:
            for sale in subcat['sales']:
                # Date should be string in 'DD.MM' format
                assert isinstance(sale['date'], str)
                assert '.' in sale['date']
                parts = sale['date'].split('.')
                assert len(parts) == 2
                assert len(parts[0]) == 2  # DD
                assert len(parts[1]) == 2  # MM

    @pytest.mark.asyncio
    async def test_empty_result(self, test_session):
        """Test with no sales data."""
        data = await AnalyticsService.get_subcategory_sales_data(
            days=30, page=0, session=test_session
        )

        assert data['subcategories'] == []
        assert data['current_page'] == 0
        assert data['max_page'] == 0
        assert data['total_subcategories'] == 0


class TestGenerateSalesCSV:
    """Test AnalyticsService.generate_sales_csv_content()"""

    @pytest.mark.asyncio
    async def test_csv_header(self, test_session):
        """Test CSV has correct header."""
        csv = await AnalyticsService.generate_sales_csv_content(test_session)

        lines = csv.split('\n')
        header = lines[0]
        assert 'date' in header
        assert 'category' in header
        assert 'subcategory' in header
        assert 'quantity' in header
        assert 'item_total_price' in header

    @pytest.mark.asyncio
    async def test_csv_with_data(self, test_session, setup_sales_data):
        """Test CSV with actual data."""
        csv = await AnalyticsService.generate_sales_csv_content(test_session)

        lines = csv.split('\n')
        # Should have at least header
        assert len(lines) >= 1

    @pytest.mark.asyncio
    async def test_csv_empty(self, test_session):
        """Test CSV with no data."""
        csv = await AnalyticsService.generate_sales_csv_content(test_session)

        lines = csv.split('\n')
        # Only header (and possibly empty line at end)
        assert len([l for l in lines if l]) == 1


# ==================== Fixtures ====================

@pytest_asyncio.fixture
async def setup_sales_data(test_session):
    """Create test sales data with multiple subcategories."""
    from models.sales_record import SalesRecordDTO

    now = datetime.now(timezone.utc)

    sales = [
        SalesRecordDTO(
            sale_date=now,
            sale_hour=now.hour,
            sale_weekday=now.weekday(),
            category_name='Electronics',
            subcategory_name='Smartphones',
            quantity=1,
            is_physical=True,
            item_total_price=500.0,
            currency='EUR',
            average_unit_price=500.0,
            order_total_price=500.0,
            order_shipping_cost=5.0,
            order_wallet_used=0.0,
            payment_method='crypto_only',
            crypto_currency='BTC',
            status='PAID',
            is_refunded=False
        ),
        SalesRecordDTO(
            sale_date=now - timedelta(days=1),
            sale_hour=(now - timedelta(days=1)).hour,
            sale_weekday=(now - timedelta(days=1)).weekday(),
            category_name='Electronics',
            subcategory_name='Laptops',
            quantity=1,
            is_physical=True,
            item_total_price=900.0,
            currency='EUR',
            average_unit_price=900.0,
            order_total_price=900.0,
            order_shipping_cost=10.0,
            order_wallet_used=0.0,
            payment_method='crypto_only',
            crypto_currency='ETH',
            status='PAID',
            is_refunded=False
        ),
    ]

    await SalesRecordRepository.create_many(sales, test_session)
    from db import session_commit
    await session_commit(test_session)

    yield

    # Cleanup not needed - test DB is reset after each test


@pytest_asyncio.fixture
async def setup_mixed_revenue(test_session):
    """Create sales with varying revenues for sorting test."""
    now = datetime.now(timezone.utc)

    sales = [
        # Low revenue
        SalesRecordDTO(
            sale_date=now,
            sale_hour=now.hour,
            sale_weekday=now.weekday(),
            category_name='Books',
            subcategory_name='Fiction',
            quantity=1,
            is_physical=True,
            item_total_price=15.0,
            currency='EUR',
            average_unit_price=15.0,
            order_total_price=15.0,
            order_shipping_cost=2.0,
            order_wallet_used=0.0,
            payment_method='wallet_only',
            status='PAID',
            is_refunded=False
        ),
        # High revenue
        SalesRecordDTO(
            sale_date=now,
            sale_hour=now.hour,
            sale_weekday=now.weekday(),
            category_name='Electronics',
            subcategory_name='Laptops',
            quantity=1,
            is_physical=True,
            item_total_price=1200.0,
            currency='EUR',
            average_unit_price=1200.0,
            order_total_price=1200.0,
            order_shipping_cost=10.0,
            order_wallet_used=0.0,
            payment_method='crypto_only',
            crypto_currency='BTC',
            status='PAID',
            is_refunded=False
        ),
        # Medium revenue
        SalesRecordDTO(
            sale_date=now,
            sale_hour=now.hour,
            sale_weekday=now.weekday(),
            category_name='Clothing',
            subcategory_name='T-Shirts',
            quantity=1,
            is_physical=True,
            item_total_price=30.0,
            currency='EUR',
            average_unit_price=30.0,
            order_total_price=30.0,
            order_shipping_cost=5.0,
            order_wallet_used=0.0,
            payment_method='mixed',
            crypto_currency='SOL',
            status='PAID',
            is_refunded=False
        ),
    ]

    await SalesRecordRepository.create_many(sales, test_session)
    from db import session_commit
    await session_commit(test_session)

    yield
