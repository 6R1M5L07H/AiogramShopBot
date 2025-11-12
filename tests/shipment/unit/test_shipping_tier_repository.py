"""
Unit Tests: ShippingTierRepository

Tests for repositories/shipping_tier.py covering:
- CRUD operations for shipping tiers
- Batch operations (get_by_subcategory_ids, bulk_create)
- Tier retrieval and sorting
- Delete operations

Uses in-memory SQLite database for isolated testing.

Run with:
    pytest tests/shipment/unit/test_shipping_tier_repository.py -v
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Mock config before imports
import config
config.DB_ENCRYPTION = False

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.base import Base
from models.category import Category
from models.subcategory import Subcategory
from models.shipping_tier import ShippingTier, ShippingTierDTO
from repositories.shipping_tier import ShippingTierRepository


class TestShippingTierRepository:
    """Test ShippingTierRepository database operations."""

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

    @pytest.fixture
    def test_category(self, session):
        """Create test category."""
        category = Category(name="Test Category")
        session.add(category)
        session.commit()
        return category

    @pytest.fixture
    def test_subcategories(self, session, test_category):
        """Create multiple test subcategories."""
        subcategories = [
            Subcategory(name="USB Sticks"),
            Subcategory(name="Tea Products"),
            Subcategory(name="Digital Products")
        ]
        session.add_all(subcategories)
        session.commit()
        return subcategories

    @pytest.mark.asyncio
    async def test_create_shipping_tier(self, session, test_subcategories):
        """Test creating a single shipping tier."""
        subcategory = test_subcategories[0]

        tier_dto = ShippingTierDTO(
            subcategory_id=subcategory.id,
            min_quantity=1,
            max_quantity=5,
            shipping_type="maxibrief"
        )

        tier = await ShippingTierRepository.create(tier_dto, session)

        assert tier.id is not None
        assert tier.subcategory_id == subcategory.id
        assert tier.min_quantity == 1
        assert tier.max_quantity == 5
        assert tier.shipping_type == "maxibrief"

    @pytest.mark.asyncio
    async def test_create_shipping_tier_unlimited(self, session, test_subcategories):
        """Test creating tier with unlimited max_quantity (None)."""
        subcategory = test_subcategories[0]

        tier_dto = ShippingTierDTO(
            subcategory_id=subcategory.id,
            min_quantity=11,
            max_quantity=None,
            shipping_type="paket_2kg"
        )

        tier = await ShippingTierRepository.create(tier_dto, session)

        assert tier.max_quantity is None
        assert tier.shipping_type == "paket_2kg"

    @pytest.mark.asyncio
    async def test_get_by_subcategory_id(self, session, test_subcategories):
        """Test retrieving tiers for a specific subcategory."""
        subcategory = test_subcategories[0]

        # Create multiple tiers
        tiers_data = [
            ShippingTierDTO(subcategory_id=subcategory.id, min_quantity=1, max_quantity=5, shipping_type="maxibrief"),
            ShippingTierDTO(subcategory_id=subcategory.id, min_quantity=6, max_quantity=10, shipping_type="paeckchen"),
            ShippingTierDTO(subcategory_id=subcategory.id, min_quantity=11, max_quantity=None, shipping_type="paket_2kg")
        ]

        for tier_dto in tiers_data:
            await ShippingTierRepository.create(tier_dto, session)

        # Retrieve tiers
        tiers = await ShippingTierRepository.get_by_subcategory_id(subcategory.id, session)

        assert len(tiers) == 3
        # Verify sorting by min_quantity ascending
        assert tiers[0].min_quantity == 1
        assert tiers[1].min_quantity == 6
        assert tiers[2].min_quantity == 11

    @pytest.mark.asyncio
    async def test_get_by_subcategory_id_empty(self, session, test_subcategories):
        """Test retrieving tiers for subcategory with no tiers."""
        subcategory = test_subcategories[0]

        tiers = await ShippingTierRepository.get_by_subcategory_id(subcategory.id, session)

        assert len(tiers) == 0

    @pytest.mark.asyncio
    async def test_get_by_subcategory_ids_batch(self, session, test_subcategories):
        """Test batch retrieval of tiers for multiple subcategories."""
        subcat1, subcat2, subcat3 = test_subcategories

        # Create tiers for subcat1
        await ShippingTierRepository.create(
            ShippingTierDTO(subcategory_id=subcat1.id, min_quantity=1, max_quantity=5, shipping_type="maxibrief"),
            session
        )
        await ShippingTierRepository.create(
            ShippingTierDTO(subcategory_id=subcat1.id, min_quantity=6, max_quantity=None, shipping_type="paeckchen"),
            session
        )

        # Create tiers for subcat2
        await ShippingTierRepository.create(
            ShippingTierDTO(subcategory_id=subcat2.id, min_quantity=1, max_quantity=10, shipping_type="maxibrief"),
            session
        )

        # subcat3 has no tiers

        # Batch retrieve
        tiers_dict = await ShippingTierRepository.get_by_subcategory_ids(
            [subcat1.id, subcat2.id, subcat3.id],
            session
        )

        assert len(tiers_dict) == 2  # Only subcat1 and subcat2 have tiers
        assert subcat1.id in tiers_dict
        assert subcat2.id in tiers_dict
        assert subcat3.id not in tiers_dict
        assert len(tiers_dict[subcat1.id]) == 2
        assert len(tiers_dict[subcat2.id]) == 1

    @pytest.mark.asyncio
    async def test_get_by_subcategory_ids_empty_list(self, session):
        """Test batch retrieval with empty subcategory list."""
        tiers_dict = await ShippingTierRepository.get_by_subcategory_ids([], session)

        assert tiers_dict == {}

    @pytest.mark.asyncio
    async def test_delete_by_subcategory_id(self, session, test_subcategories):
        """Test deleting all tiers for a subcategory."""
        subcategory = test_subcategories[0]

        # Create tiers
        await ShippingTierRepository.create(
            ShippingTierDTO(subcategory_id=subcategory.id, min_quantity=1, max_quantity=5, shipping_type="maxibrief"),
            session
        )
        await ShippingTierRepository.create(
            ShippingTierDTO(subcategory_id=subcategory.id, min_quantity=6, max_quantity=None, shipping_type="paeckchen"),
            session
        )

        # Verify tiers exist
        tiers_before = await ShippingTierRepository.get_by_subcategory_id(subcategory.id, session)
        assert len(tiers_before) == 2

        # Delete
        deleted_count = await ShippingTierRepository.delete_by_subcategory_id(subcategory.id, session)

        assert deleted_count == 2

        # Verify tiers deleted
        tiers_after = await ShippingTierRepository.get_by_subcategory_id(subcategory.id, session)
        assert len(tiers_after) == 0

    @pytest.mark.asyncio
    async def test_delete_by_subcategory_id_no_tiers(self, session, test_subcategories):
        """Test deleting from subcategory with no tiers."""
        subcategory = test_subcategories[0]

        deleted_count = await ShippingTierRepository.delete_by_subcategory_id(subcategory.id, session)

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_bulk_create(self, session, test_subcategories):
        """Test bulk creation of tiers."""
        subcategory = test_subcategories[0]

        tiers_data = [
            {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
            {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"},
            {"min_quantity": 11, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]

        created_tiers = await ShippingTierRepository.bulk_create(
            subcategory.id,
            tiers_data,
            session,
            replace_existing=False
        )

        assert len(created_tiers) == 3
        assert all(tier.id is not None for tier in created_tiers)
        assert created_tiers[0].shipping_type == "maxibrief"
        assert created_tiers[2].max_quantity is None

    @pytest.mark.asyncio
    async def test_bulk_create_replace_existing(self, session, test_subcategories):
        """Test bulk creation with replace_existing=True."""
        subcategory = test_subcategories[0]

        # Create initial tiers
        initial_tiers = [
            {"min_quantity": 1, "max_quantity": None, "shipping_type": "maxibrief"}
        ]
        await ShippingTierRepository.bulk_create(
            subcategory.id,
            initial_tiers,
            session,
            replace_existing=False
        )

        # Verify initial tier exists
        tiers_before = await ShippingTierRepository.get_by_subcategory_id(subcategory.id, session)
        assert len(tiers_before) == 1

        # Replace with new tiers
        new_tiers = [
            {"min_quantity": 1, "max_quantity": 10, "shipping_type": "paeckchen"},
            {"min_quantity": 11, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]
        created_tiers = await ShippingTierRepository.bulk_create(
            subcategory.id,
            new_tiers,
            session,
            replace_existing=True
        )

        # Verify old tiers deleted, new tiers created
        tiers_after = await ShippingTierRepository.get_by_subcategory_id(subcategory.id, session)
        assert len(tiers_after) == 2
        assert tiers_after[0].shipping_type == "paeckchen"
        assert tiers_after[1].shipping_type == "paket_2kg"

    @pytest.mark.asyncio
    async def test_tier_sorting_by_min_quantity(self, session, test_subcategories):
        """Test that tiers are always sorted by min_quantity ascending."""
        subcategory = test_subcategories[0]

        # Create tiers in random order
        tiers_data = [
            ShippingTierDTO(subcategory_id=subcategory.id, min_quantity=11, max_quantity=None, shipping_type="paket_2kg"),
            ShippingTierDTO(subcategory_id=subcategory.id, min_quantity=1, max_quantity=5, shipping_type="maxibrief"),
            ShippingTierDTO(subcategory_id=subcategory.id, min_quantity=6, max_quantity=10, shipping_type="paeckchen")
        ]

        for tier_dto in tiers_data:
            await ShippingTierRepository.create(tier_dto, session)

        # Retrieve and verify sorting
        tiers = await ShippingTierRepository.get_by_subcategory_id(subcategory.id, session)

        assert len(tiers) == 3
        assert tiers[0].min_quantity == 1
        assert tiers[1].min_quantity == 6
        assert tiers[2].min_quantity == 11

    @pytest.mark.asyncio
    async def test_multiple_subcategories_isolation(self, session, test_subcategories):
        """Test that tiers are isolated per subcategory."""
        subcat1, subcat2 = test_subcategories[:2]

        # Create tiers for subcat1
        await ShippingTierRepository.create(
            ShippingTierDTO(subcategory_id=subcat1.id, min_quantity=1, max_quantity=None, shipping_type="maxibrief"),
            session
        )

        # Create tiers for subcat2
        await ShippingTierRepository.create(
            ShippingTierDTO(subcategory_id=subcat2.id, min_quantity=1, max_quantity=None, shipping_type="paeckchen"),
            session
        )

        # Verify isolation
        tiers1 = await ShippingTierRepository.get_by_subcategory_id(subcat1.id, session)
        tiers2 = await ShippingTierRepository.get_by_subcategory_id(subcat2.id, session)

        assert len(tiers1) == 1
        assert len(tiers2) == 1
        assert tiers1[0].shipping_type == "maxibrief"
        assert tiers2[0].shipping_type == "paeckchen"

    @pytest.mark.asyncio
    async def test_delete_only_affects_target_subcategory(self, session, test_subcategories):
        """Test that delete only removes tiers for target subcategory."""
        subcat1, subcat2 = test_subcategories[:2]

        # Create tiers for both subcategories
        await ShippingTierRepository.create(
            ShippingTierDTO(subcategory_id=subcat1.id, min_quantity=1, max_quantity=None, shipping_type="maxibrief"),
            session
        )
        await ShippingTierRepository.create(
            ShippingTierDTO(subcategory_id=subcat2.id, min_quantity=1, max_quantity=None, shipping_type="paeckchen"),
            session
        )

        # Delete tiers for subcat1
        await ShippingTierRepository.delete_by_subcategory_id(subcat1.id, session)

        # Verify subcat1 tiers deleted, subcat2 tiers remain
        tiers1 = await ShippingTierRepository.get_by_subcategory_id(subcat1.id, session)
        tiers2 = await ShippingTierRepository.get_by_subcategory_id(subcat2.id, session)

        assert len(tiers1) == 0
        assert len(tiers2) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
