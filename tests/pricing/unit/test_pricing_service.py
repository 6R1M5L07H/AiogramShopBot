"""
PricingService Unit Tests

Tests the tiered pricing calculation logic without requiring ngrok or external services.
Uses in-memory SQLite database for testing.

Run with:
    pytest tests/pricing/unit/test_pricing_service.py -v
    pytest tests/pricing/unit/test_pricing_service.py -v -s  # with output
    pytest tests/pricing/unit/test_pricing_service.py --cov=services.pricing  # with coverage
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Mock config before imports
import config
config.DB_ENCRYPTION = False

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from models.base import Base
from models.item import Item
from models.category import Category
from models.subcategory import Subcategory
from models.price_tier import PriceTier
from services.pricing import PricingService
from exceptions.item import ItemNotFoundException


class TestPricingService:
    """Test PricingService.calculate_optimal_price()"""

    @pytest.fixture
    def engine(self):
        """Create in-memory SQLite database"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def session(self, engine):
        """Create database session"""
        session = Session(engine)
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def test_category(self, session):
        """Create test category"""
        category = Category(name="Test Category")
        session.add(category)
        session.commit()
        return category

    @pytest.fixture
    def test_subcategory(self, session, test_category):
        """Create test subcategory"""
        subcategory = Subcategory(name="Test Subcategory")
        session.add(subcategory)
        session.commit()
        return subcategory

    @pytest.fixture
    def test_item_with_tiers(self, session, test_category, test_subcategory):
        """Create test item with price tiers"""
        item = Item(
            category_id=test_category.id,
            subcategory_id=test_subcategory.id,
            private_data="Test item data",
            price=11.0,  # Fallback flat price
            description="Test item",
            is_physical=False,
            shipping_cost=0.0,
            allows_packstation=False,
            is_sold=False,
            is_new=True
        )
        session.add(item)
        session.commit()

        # Add price tiers
        tiers = [
            PriceTier(item_id=item.id, min_quantity=1, unit_price=11.0),
            PriceTier(item_id=item.id, min_quantity=5, unit_price=10.0),
            PriceTier(item_id=item.id, min_quantity=10, unit_price=9.0),
        ]
        session.add_all(tiers)
        session.commit()

        return item

    @pytest.mark.asyncio
    async def test_single_tier_quantity(self, session, test_subcategory, test_item_with_tiers):
        """Test pricing for quantity within first tier (1-4 items)"""
        result = await PricingService.calculate_optimal_price(
            subcategory_id=test_subcategory.id,
            quantity=3,
            session=session
        )

        # Classic tiered pricing: 3 items at tier 1 price (11.0 EUR/item)
        assert result.total == 33.0  # 3 × 11.0
        assert result.average_unit_price == 11.0
        assert len(result.breakdown) == 1
        assert result.breakdown[0].quantity == 3
        assert result.breakdown[0].unit_price == 11.0
        assert result.breakdown[0].total == 33.0

    @pytest.mark.asyncio
    async def test_exact_tier_boundary(self, session, test_subcategory, test_item_with_tiers):
        """Test pricing at exact tier boundary (5 items)"""
        result = await PricingService.calculate_optimal_price(
            subcategory_id=test_subcategory.id,
            quantity=5,
            session=session
        )

        assert result.total == 50.0  # 5 × 10.0
        assert result.average_unit_price == 10.0
        assert len(result.breakdown) == 1
        assert result.breakdown[0].quantity == 5
        assert result.breakdown[0].unit_price == 10.0

    @pytest.mark.asyncio
    async def test_multiple_tiers(self, session, test_subcategory, test_item_with_tiers):
        """Test pricing spanning multiple tiers (12 items)"""
        result = await PricingService.calculate_optimal_price(
            subcategory_id=test_subcategory.id,
            quantity=12,
            session=session
        )

        # Classic tiered pricing: 12 items reach tier 3 (10+ items @ 9.0 EUR)
        # All 12 items: 12 × 9.0 = 108.0 EUR
        assert result.total == 108.0
        assert result.average_unit_price == 9.0

        # Classic tiered pricing always has exactly 1 breakdown entry
        assert len(result.breakdown) == 1
        assert result.breakdown[0].quantity == 12
        assert result.breakdown[0].unit_price == 9.0

    @pytest.mark.asyncio
    async def test_large_quantity(self, session, test_subcategory, test_item_with_tiers):
        """Test pricing for large quantity (100 items)"""
        result = await PricingService.calculate_optimal_price(
            subcategory_id=test_subcategory.id,
            quantity=100,
            session=session
        )

        # Should use largest tier (10+ items @ 9.0 EUR)
        assert result.total == 900.0  # 100 × 9.0
        assert result.average_unit_price == 9.0
        assert len(result.breakdown) == 1
        assert result.breakdown[0].quantity == 100
        assert result.breakdown[0].unit_price == 9.0

    @pytest.mark.asyncio
    async def test_non_canonical_tiers(self, session, test_category, test_subcategory):
        """
        Test non-canonical tier structure with classic tiered pricing.

        With classic tiered pricing, quantity 6 items with tiers [1→€10, 3→€7, 5→€9]
        reaches tier "5→€9", so all 6 items are priced at 9 EUR each.

        Result: 6 × €9 = €54

        Note: This differs from incremental/DP pricing which could optimize to €42.
        Classic pricing is simpler and standard in e-commerce.
        """
        # Create new subcategory for this test
        subcat = Subcategory(name="Non-canonical Test")
        session.add(subcat)
        session.commit()

        # Create item with non-canonical tiers
        item = Item(
            category_id=test_category.id,
            subcategory_id=subcat.id,
            private_data="Non-canonical tier test",
            price=10.0,
            description="Test item",
            is_physical=False,
            shipping_cost=0.0,
            allows_packstation=False,
            is_sold=False,
            is_new=True
        )
        session.add(item)
        session.commit()

        # Non-canonical tiers (5-item tier is more expensive than 3-item tier)
        tiers = [
            PriceTier(item_id=item.id, min_quantity=1, unit_price=10.0),
            PriceTier(item_id=item.id, min_quantity=3, unit_price=7.0),
            PriceTier(item_id=item.id, min_quantity=5, unit_price=9.0),
        ]
        session.add_all(tiers)
        session.commit()

        result = await PricingService.calculate_optimal_price(
            subcategory_id=subcat.id,
            quantity=6,
            session=session
        )

        # Classic tiered pricing: 6 items reach tier "5→€9"
        # All 6 items: 6 × 9.0 = 54.0 EUR
        assert result.total == 54.0, f"Expected 54.0 EUR (6×9), got {result.total}"
        assert result.average_unit_price == 9.0
        assert len(result.breakdown) == 1
        assert result.breakdown[0].quantity == 6
        assert result.breakdown[0].unit_price == 9.0

    @pytest.mark.asyncio
    async def test_no_tiers_flat_pricing(self, session, test_category):
        """Test fallback to flat pricing when no tiers exist"""
        # Create subcategory without tiers
        subcategory = Subcategory(name="Flat Pricing Subcategory")
        session.add(subcategory)
        session.commit()

        # Create item without price tiers
        item = Item(
            category_id=test_category.id,
            subcategory_id=subcategory.id,
            private_data="Flat price item",
            price=25.0,
            description="Flat price test",
            is_physical=False,
            shipping_cost=0.0,
            allows_packstation=False,
            is_sold=False,
            is_new=True
        )
        session.add(item)
        session.commit()

        result = await PricingService.calculate_optimal_price(
            subcategory_id=subcategory.id,
            quantity=5,
            session=session
        )

        # Should use flat price
        assert result.total == 125.0  # 5 × 25.0
        assert result.average_unit_price == 25.0
        assert len(result.breakdown) == 1

    @pytest.mark.asyncio
    async def test_no_items_raises_exception(self, session, test_category):
        """Test that ItemNotFoundException is raised when no items exist"""
        subcategory = Subcategory(name="Empty Subcategory")
        session.add(subcategory)
        session.commit()

        with pytest.raises(ItemNotFoundException):
            await PricingService.calculate_optimal_price(
                subcategory_id=subcategory.id,
                quantity=5,
                session=session
            )

    @pytest.mark.asyncio
    async def test_tier_merging(self, session, test_subcategory, test_item_with_tiers):
        """Test that consecutive tiers with same unit_price are merged"""
        result = await PricingService.calculate_optimal_price(
            subcategory_id=test_subcategory.id,
            quantity=10,
            session=session
        )

        # Should merge all 10 items at 9.0 EUR
        assert len(result.breakdown) == 1
        assert result.breakdown[0].quantity == 10
        assert result.breakdown[0].unit_price == 9.0

    @pytest.mark.asyncio
    async def test_rounding_precision(self, session, test_category):
        """Test that prices are rounded correctly to 2 decimal places"""
        subcat = Subcategory(name="Rounding Test")
        session.add(subcat)
        session.commit()

        item = Item(
            category_id=test_category.id,
            subcategory_id=subcat.id,
            private_data="Rounding test",
            price=10.999,
            description="Rounding test",
            is_physical=False,
            shipping_cost=0.0,
            allows_packstation=False,
            is_sold=False,
            is_new=True
        )
        session.add(item)
        session.commit()

        tiers = [
            PriceTier(item_id=item.id, min_quantity=1, unit_price=10.999),
        ]
        session.add_all(tiers)
        session.commit()

        result = await PricingService.calculate_optimal_price(
            subcategory_id=subcat.id,
            quantity=3,
            session=session
        )

        # All prices should be rounded to 2 decimals
        assert result.breakdown[0].unit_price == 11.0  # rounded
        assert result.breakdown[0].total == 33.0
        assert result.total == 33.0
        assert result.average_unit_price == 11.0

    @pytest.mark.asyncio
    async def test_single_item_quantity(self, session, test_subcategory, test_item_with_tiers):
        """Test pricing for quantity = 1"""
        result = await PricingService.calculate_optimal_price(
            subcategory_id=test_subcategory.id,
            quantity=1,
            session=session
        )

        assert result.total == 11.0
        assert result.average_unit_price == 11.0
        assert len(result.breakdown) == 1

    @pytest.mark.asyncio
    async def test_calculation_idempotence(self, session, test_category, test_subcategory, test_item_with_tiers):
        """
        Test that calculation is idempotent (repeated calls produce identical results).

        Regression test to ensure calculations are consistent and don't have
        hidden state or mutation bugs.
        """
        # Calculate for quantity 10
        result_10 = await PricingService.calculate_optimal_price(
            subcategory_id=test_subcategory.id,
            quantity=10,
            session=session
        )

        # Calculate for quantity 12
        result_12 = await PricingService.calculate_optimal_price(
            subcategory_id=test_subcategory.id,
            quantity=12,
            session=session
        )

        # Now re-calculate for quantity 10 - should get SAME result
        result_10_again = await PricingService.calculate_optimal_price(
            subcategory_id=test_subcategory.id,
            quantity=10,
            session=session
        )

        # Verify results are identical (idempotent)
        assert result_10.total == result_10_again.total
        assert result_10.average_unit_price == result_10_again.average_unit_price
        assert len(result_10.breakdown) == len(result_10_again.breakdown)

        for orig, again in zip(result_10.breakdown, result_10_again.breakdown):
            assert orig.quantity == again.quantity
            assert orig.unit_price == again.unit_price
            assert orig.total == again.total

    @pytest.mark.asyncio
    async def test_format_tier_breakdown(self):
        """Test formatting for classic tiered pricing (always single breakdown entry)"""
        from models.price_tier import TierPricingResultDTO, TierBreakdownItemDTO

        pricing_result = TierPricingResultDTO(
            total=55.0,
            average_unit_price=11.0,
            breakdown=[
                TierBreakdownItemDTO(quantity=5, unit_price=11.0, total=55.0)
            ]
        )

        formatted = PricingService.format_tier_breakdown(pricing_result)

        assert "5 × 11.00 € = 55.00 €" in formatted
        assert "Staffelpreise:" not in formatted  # Simple format, no header
