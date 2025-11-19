"""
Integration Tests: Shipping End-to-End

Tests complete shipping flow from database setup to cart checkout display:
- Item import with shipping_tiers
- Cart creation with physical items
- Shipping calculation and selection
- Summary text generation
- Max cost calculation

Uses in-memory SQLite database for isolated testing.

Run with:
    pytest tests/shipment/integration/test_shipping_end_to_end.py -v
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
from models.item import Item, ItemDTO
from models.cartItem import CartItemDTO
from models.shipping_tier import ShippingTierDTO
from repositories.shipping_tier import ShippingTierRepository
from repositories.item import ItemRepository
from services.cart_shipping import CartShippingService
from unittest.mock import patch


class TestShippingEndToEnd:
    """Test complete shipping workflow from setup to checkout."""

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
    def mock_shipping_types(self):
        """Mock shipping types configuration."""
        return {
            "maxibrief": {
                "name": "Maxibrief",
                "charged_cost": 0.0,
                "real_cost": 2.70,
                "allows_packstation": False,
                "has_tracking": False,
                "description": "Deutsche Post Maxibrief",
                "upgrade": None
            },
            "paeckchen": {
                "name": "Päckchen",
                "charged_cost": 0.0,
                "real_cost": 3.99,
                "allows_packstation": True,
                "has_tracking": False,
                "description": "DHL Päckchen",
                "upgrade": {
                    "target": "paket_2kg",
                    "upsell_button_text": "Versichert versenden"
                }
            },
            "paket_2kg": {
                "name": "Versichertes Paket (2kg)",
                "charged_cost": 1.50,
                "real_cost": 5.49,
                "allows_packstation": True,
                "has_tracking": True,
                "description": "Versichertes Paket",
                "upgrade": None
            }
        }

    @pytest.fixture
    def tea_shop_setup(self, session):
        """Set up tea shop with categories, subcategories, items, and shipping tiers."""
        # Create categories
        tea_category = Category(name="Tee")
        session.add(tea_category)
        session.commit()

        # Create subcategories
        green_tea_subcat = Subcategory(name="Grüner Tee")
        black_tea_subcat = Subcategory(name="Schwarzer Tee")
        session.add_all([green_tea_subcat, black_tea_subcat])
        session.commit()

        # Create items
        green_tea_items = [
            Item(
                category_id=tea_category.id,
                subcategory_id=green_tea_subcat.id,
                private_data="Premium green tea",
                price=12.0,
                description="Grüner Tee - Premium (10g)",
                is_physical=True,
                shipping_cost=0.0,
                allows_packstation=False,
                is_sold=False,
                is_new=True
            )
            for _ in range(150)
        ]

        black_tea_items = [
            Item(
                category_id=tea_category.id,
                subcategory_id=black_tea_subcat.id,
                private_data="Premium black tea",
                price=10.0,
                description="Schwarzer Tee - Premium (10g)",
                is_physical=True,
                shipping_cost=0.0,
                allows_packstation=False,
                is_sold=False,
                is_new=True
            )
            for _ in range(200)
        ]

        session.add_all(green_tea_items + black_tea_items)
        session.commit()

        return {
            "category": tea_category,
            "green_tea_subcat": green_tea_subcat,
            "black_tea_subcat": black_tea_subcat
        }

    @pytest.mark.asyncio
    async def test_single_subcategory_small_quantity(self, session, tea_shop_setup, mock_shipping_types):
        """Test shipping for small quantity (1-10 items) → maxibrief."""
        # Create shipping tiers for Grüner Tee
        green_tea_subcat = tea_shop_setup["green_tea_subcat"]

        tiers_data = [
            {"min_quantity": 1, "max_quantity": 10, "shipping_type": "maxibrief"},
            {"min_quantity": 11, "max_quantity": 50, "shipping_type": "paeckchen"},
            {"min_quantity": 51, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]

        await ShippingTierRepository.bulk_create(green_tea_subcat.id, tiers_data, session)

        # Create cart with 5 items
        cart_items = [
            CartItemDTO(
                category_id=tea_shop_setup["category"].id,
                id=1,
                subcategory_id=green_tea_subcat.id,
                quantity=5,
                price=12.0,
                user_id=1,
                item_id=1
            )
        ]

        # Calculate shipping
        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            result = await CartShippingService.calculate_shipping_for_cart(cart_items, session)

        assert len(result) == 1
        assert green_tea_subcat.id in result
        assert result[green_tea_subcat.id].shipping_type_key == "maxibrief"
        assert result[green_tea_subcat.id].charged_cost == 0.0

    @pytest.mark.asyncio
    async def test_single_subcategory_medium_quantity(self, session, tea_shop_setup, mock_shipping_types):
        """Test shipping for medium quantity (11-50 items) → paeckchen."""
        green_tea_subcat = tea_shop_setup["green_tea_subcat"]

        tiers_data = [
            {"min_quantity": 1, "max_quantity": 10, "shipping_type": "maxibrief"},
            {"min_quantity": 11, "max_quantity": 50, "shipping_type": "paeckchen"},
            {"min_quantity": 51, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]

        await ShippingTierRepository.bulk_create(green_tea_subcat.id, tiers_data, session)

        # Create cart with 25 items
        cart_items = [
            CartItemDTO(
                category_id=tea_shop_setup["category"].id,
                id=1,
                subcategory_id=green_tea_subcat.id,
                quantity=25,
                price=12.0,
                user_id=1,
                item_id=1
            )
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            result = await CartShippingService.calculate_shipping_for_cart(cart_items, session)

        assert result[green_tea_subcat.id].shipping_type_key == "paeckchen"
        assert result[green_tea_subcat.id].charged_cost == 0.0
        assert result[green_tea_subcat.id].upgrade is not None
        assert result[green_tea_subcat.id].upgrade["target"] == "paket_2kg"

    @pytest.mark.asyncio
    async def test_single_subcategory_large_quantity(self, session, tea_shop_setup, mock_shipping_types):
        """Test shipping for large quantity (51+ items) → paket_2kg."""
        green_tea_subcat = tea_shop_setup["green_tea_subcat"]

        tiers_data = [
            {"min_quantity": 1, "max_quantity": 10, "shipping_type": "maxibrief"},
            {"min_quantity": 11, "max_quantity": 50, "shipping_type": "paeckchen"},
            {"min_quantity": 51, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]

        await ShippingTierRepository.bulk_create(green_tea_subcat.id, tiers_data, session)

        # Create cart with 75 items
        cart_items = [
            CartItemDTO(
                category_id=tea_shop_setup["category"].id,
                id=1,
                subcategory_id=green_tea_subcat.id,
                quantity=75,
                price=12.0,
                user_id=1,
                item_id=1
            )
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            result = await CartShippingService.calculate_shipping_for_cart(cart_items, session)

        assert result[green_tea_subcat.id].shipping_type_key == "paket_2kg"
        assert result[green_tea_subcat.id].charged_cost == 1.50
        assert result[green_tea_subcat.id].upgrade is None

    @pytest.mark.asyncio
    async def test_multiple_items_same_subcategory_sum_quantities(self, session, tea_shop_setup, mock_shipping_types):
        """Test that multiple cart items from same subcategory sum quantities."""
        green_tea_subcat = tea_shop_setup["green_tea_subcat"]

        tiers_data = [
            {"min_quantity": 1, "max_quantity": 10, "shipping_type": "maxibrief"},
            {"min_quantity": 11, "max_quantity": 50, "shipping_type": "paeckchen"},
            {"min_quantity": 51, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]

        await ShippingTierRepository.bulk_create(green_tea_subcat.id, tiers_data, session)

        # Create cart with 3 items: 7 + 8 + 10 = 25 total
        cart_items = [
            CartItemDTO(category_id=tea_shop_setup["category"].id, id=1, subcategory_id=green_tea_subcat.id,
                       quantity=7, price=12.0, user_id=1, item_id=1),
            CartItemDTO(category_id=tea_shop_setup["category"].id, id=2, subcategory_id=green_tea_subcat.id,
                       quantity=8, price=12.0, user_id=1, item_id=2),
            CartItemDTO(category_id=tea_shop_setup["category"].id, id=3, subcategory_id=green_tea_subcat.id,
                       quantity=10, price=12.0, user_id=1, item_id=3)
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            result = await CartShippingService.calculate_shipping_for_cart(cart_items, session)

        # 25 items → paeckchen
        assert result[green_tea_subcat.id].shipping_type_key == "paeckchen"

    @pytest.mark.asyncio
    async def test_multiple_subcategories_separate_shipping(self, session, tea_shop_setup, mock_shipping_types):
        """Test that different subcategories get separate shipping calculations."""
        green_tea_subcat = tea_shop_setup["green_tea_subcat"]
        black_tea_subcat = tea_shop_setup["black_tea_subcat"]

        # Different tiers for each subcategory
        green_tiers = [
            {"min_quantity": 1, "max_quantity": 10, "shipping_type": "maxibrief"},
            {"min_quantity": 11, "max_quantity": None, "shipping_type": "paeckchen"}
        ]
        black_tiers = [
            {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
            {"min_quantity": 6, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]

        await ShippingTierRepository.bulk_create(green_tea_subcat.id, green_tiers, session)
        await ShippingTierRepository.bulk_create(black_tea_subcat.id, black_tiers, session)

        # Create cart with both subcategories
        cart_items = [
            CartItemDTO(category_id=tea_shop_setup["category"].id, id=1, subcategory_id=green_tea_subcat.id,
                       quantity=5, price=12.0, user_id=1, item_id=1),
            CartItemDTO(category_id=tea_shop_setup["category"].id, id=2, subcategory_id=black_tea_subcat.id,
                       quantity=10, price=10.0, user_id=1, item_id=51)
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            result = await CartShippingService.calculate_shipping_for_cart(cart_items, session)

        assert len(result) == 2
        assert result[green_tea_subcat.id].shipping_type_key == "maxibrief"
        assert result[black_tea_subcat.id].shipping_type_key == "paket_2kg"

    @pytest.mark.asyncio
    async def test_max_shipping_cost_calculation(self, session, tea_shop_setup, mock_shipping_types):
        """Test that max_shipping_cost returns highest cost among subcategories."""
        green_tea_subcat = tea_shop_setup["green_tea_subcat"]
        black_tea_subcat = tea_shop_setup["black_tea_subcat"]

        # Green: maxibrief (free), Black: paket_2kg (€1.50)
        green_tiers = [
            {"min_quantity": 1, "max_quantity": None, "shipping_type": "maxibrief"}
        ]
        black_tiers = [
            {"min_quantity": 1, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]

        await ShippingTierRepository.bulk_create(green_tea_subcat.id, green_tiers, session)
        await ShippingTierRepository.bulk_create(black_tea_subcat.id, black_tiers, session)

        cart_items = [
            CartItemDTO(category_id=tea_shop_setup["category"].id, id=1, subcategory_id=green_tea_subcat.id,
                       quantity=5, price=12.0, user_id=1, item_id=1),
            CartItemDTO(category_id=tea_shop_setup["category"].id, id=2, subcategory_id=black_tea_subcat.id,
                       quantity=10, price=10.0, user_id=1, item_id=51)
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            max_cost = await CartShippingService.get_max_shipping_cost(cart_items, session)

        assert max_cost == 1.50

    @pytest.mark.asyncio
    async def test_tier_boundary_values(self, session, tea_shop_setup, mock_shipping_types):
        """Test shipping type selection at tier boundaries."""
        green_tea_subcat = tea_shop_setup["green_tea_subcat"]

        tiers_data = [
            {"min_quantity": 1, "max_quantity": 10, "shipping_type": "maxibrief"},
            {"min_quantity": 11, "max_quantity": 50, "shipping_type": "paeckchen"},
            {"min_quantity": 51, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]

        await ShippingTierRepository.bulk_create(green_tea_subcat.id, tiers_data, session)

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            # Quantity 10 (last of tier 1)
            cart_10 = [CartItemDTO(category_id=tea_shop_setup["category"].id, id=1,
                                   subcategory_id=green_tea_subcat.id, quantity=10, price=12.0,
                                   user_id=1, item_id=1)]
            result_10 = await CartShippingService.calculate_shipping_for_cart(cart_10, session)
            assert result_10[green_tea_subcat.id].shipping_type_key == "maxibrief"

            # Quantity 11 (first of tier 2)
            cart_11 = [CartItemDTO(category_id=tea_shop_setup["category"].id, id=1,
                                   subcategory_id=green_tea_subcat.id, quantity=11, price=12.0,
                                   user_id=1, item_id=1)]
            result_11 = await CartShippingService.calculate_shipping_for_cart(cart_11, session)
            assert result_11[green_tea_subcat.id].shipping_type_key == "paeckchen"

            # Quantity 50 (last of tier 2)
            cart_50 = [CartItemDTO(category_id=tea_shop_setup["category"].id, id=1,
                                   subcategory_id=green_tea_subcat.id, quantity=50, price=12.0,
                                   user_id=1, item_id=1)]
            result_50 = await CartShippingService.calculate_shipping_for_cart(cart_50, session)
            assert result_50[green_tea_subcat.id].shipping_type_key == "paeckchen"

            # Quantity 51 (first of tier 3)
            cart_51 = [CartItemDTO(category_id=tea_shop_setup["category"].id, id=1,
                                   subcategory_id=green_tea_subcat.id, quantity=51, price=12.0,
                                   user_id=1, item_id=1)]
            result_51 = await CartShippingService.calculate_shipping_for_cart(cart_51, session)
            assert result_51[green_tea_subcat.id].shipping_type_key == "paket_2kg"

    @pytest.mark.asyncio
    async def test_no_shipping_for_digital_items(self, session, tea_shop_setup, mock_shipping_types):
        """Test that digital items return no shipping."""
        category = tea_shop_setup["category"]

        # Create digital subcategory and items
        digital_subcat = Subcategory(name="Digital Products")
        session.add(digital_subcat)
        session.commit()

        digital_item = Item(
            category_id=category.id,
            subcategory_id=digital_subcat.id,
            private_data="Digital license key",
            price=50.0,
            description="Software License",
            is_physical=False,
            shipping_cost=0.0,
            allows_packstation=False,
            is_sold=False,
            is_new=True
        )
        session.add(digital_item)
        session.commit()

        # Create cart with digital item
        cart_items = [
            CartItemDTO(category_id=category.id, id=1, subcategory_id=digital_subcat.id,
                       quantity=5, price=50.0, user_id=1, item_id=digital_item.id)
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            result = await CartShippingService.calculate_shipping_for_cart(cart_items, session)

        # Digital items should return empty result
        assert len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
