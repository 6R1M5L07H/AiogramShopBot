"""
Unit tests for batch loading methods in repositories (eliminates N+1 queries).

Tests BuyItemRepository.get_by_buy_ids() and ItemRepository.get_by_ids().
"""

import pytest
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Mock config before imports
import config
config.DB_ENCRYPTION = False

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.base import Base
from models.buy import Buy
from models.buyItem import BuyItem
from models.item import Item
from models.category import Category
from models.subcategory import Subcategory
from repositories.buyItem import BuyItemRepository
from repositories.item import ItemRepository
from enums.currency import Currency


class TestBatchLoading:
    """Test batch loading methods to verify N+1 query elimination."""

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
    async def test_buy_item_get_by_buy_ids(self, session):
        """Test BuyItemRepository.get_by_buy_ids() returns dict mapping buy_id -> BuyItemDTO."""
        # Arrange: Create test data
        category = Category(name="Electronics")
        session.add(category)
        session.flush()

        subcategory = Subcategory(name="Phones")
        session.add(subcategory)
        session.flush()

        # Create 3 items
        items = []
        for i in range(3):
            item = Item(
                category_id=category.id,
                subcategory_id=subcategory.id,
                description=f"Item {i}",
                price=100.0,
                is_physical=True,
                is_sold=True,
                private_data=f"DATA-{i}"
            )
            session.add(item)
            items.append(item)
        session.flush()

        # Create 3 buys
        buys = []
        for i in range(3):
            buy = Buy(
                buyer_id=None,  # buyer_id is nullable
                quantity=1,
                buy_datetime=datetime.utcnow(),
                total_price=100.0
            )
            session.add(buy)
            buys.append(buy)
        session.flush()

        # Create 3 buy_items linking buys to items
        for i in range(3):
            buy_item = BuyItem(buy_id=buys[i].id, item_id=items[i].id)
            session.add(buy_item)
        session.commit()

        # Act: Batch load all buy_items
        buy_ids = [buy.id for buy in buys]
        result = await BuyItemRepository.get_by_buy_ids(buy_ids, session)

        # Assert: Verify result is dict with correct mappings
        assert isinstance(result, dict)
        assert len(result) == 3
        for i, buy in enumerate(buys):
            assert buy.id in result
            assert result[buy.id].buy_id == buy.id
            assert result[buy.id].item_id == items[i].id

    @pytest.mark.asyncio
    async def test_buy_item_get_by_buy_ids_empty(self, session):
        """Test BuyItemRepository.get_by_buy_ids() with empty list."""
        result = await BuyItemRepository.get_by_buy_ids([], session)
        assert result == {}

    @pytest.mark.asyncio
    async def test_item_get_by_ids(self, session):
        """Test ItemRepository.get_by_ids() returns dict mapping item_id -> ItemDTO."""
        # Arrange: Create test data
        category = Category(name="Electronics")
        session.add(category)
        session.flush()

        subcategory = Subcategory(name="Phones")
        session.add(subcategory)
        session.flush()

        # Create 5 items
        items = []
        for i in range(5):
            item = Item(
                category_id=category.id,
                subcategory_id=subcategory.id,
                description=f"Item {i}",
                price=100.0 + i,
                is_physical=True,
                is_sold=False,
                private_data=f"DATA-{i}"
            )
            session.add(item)
            items.append(item)
        session.commit()

        # Act: Batch load all items
        item_ids = [item.id for item in items]
        result = await ItemRepository.get_by_ids(item_ids, session)

        # Assert: Verify result is dict with correct mappings
        assert isinstance(result, dict)
        assert len(result) == 5
        for i, item in enumerate(items):
            assert item.id in result
            assert result[item.id].id == item.id
            assert result[item.id].description == f"Item {i}"
            assert result[item.id].price == 100.0 + i

    @pytest.mark.asyncio
    async def test_item_get_by_ids_empty(self, session):
        """Test ItemRepository.get_by_ids() with empty list."""
        result = await ItemRepository.get_by_ids([], session)
        assert result == {}

    @pytest.mark.asyncio
    async def test_item_get_by_ids_partial_match(self, session):
        """Test ItemRepository.get_by_ids() when some IDs don't exist."""
        # Arrange: Create 2 items
        category = Category(name="Electronics")
        session.add(category)
        session.flush()

        subcategory = Subcategory(name="Phones")
        session.add(subcategory)
        session.flush()

        item1 = Item(
            category_id=category.id,
            subcategory_id=subcategory.id,
            description="Item 1",
            price=100.0,
            is_physical=True,
            is_sold=False,
            private_data="DATA-1"
        )
        item2 = Item(
            category_id=category.id,
            subcategory_id=subcategory.id,
            description="Item 2",
            price=200.0,
            is_physical=True,
            is_sold=False,
            private_data="DATA-2"
        )
        session.add(item1)
        session.add(item2)
        session.commit()

        # Act: Query with some non-existent IDs
        result = await ItemRepository.get_by_ids([item1.id, 9999, item2.id, 8888], session)

        # Assert: Only existing items returned
        assert len(result) == 2
        assert item1.id in result
        assert item2.id in result
        assert 9999 not in result
        assert 8888 not in result