"""
Unit Tests: CartShippingService

Tests for services/cart_shipping.py covering:
- Shipping calculation for cart (grouping, quantity summation)
- Shipping type selection per subcategory
- Max shipping cost calculation
- Upgrade option loading (Feature A3 backend)
- Legacy fallback for items without tiers
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from models.cartItem import CartItemDTO
from models.shipping_tier import ShippingSelectionResultDTO
from models.item import Item
from services.cart_shipping import CartShippingService


@pytest.fixture
def mock_shipping_types():
    """Mock shipping types configuration."""
    return {
        "maxibrief": {
            "name": "Maxibrief",
            "base_cost": 0.0,
            "allows_packstation": False,
            "has_tracking": False,
            "upgrade": {
                "type": "maxibrief_einwurf",
                "delta_cost": 2.35,
                "name": "Mit Sendungsverfolgung absichern",
                "description": "Einwurfeinschreiben mit Sendungsverfolgung"
            }
        },
        "maxibrief_einwurf": {
            "name": "Maxibrief + Einwurfeinschreiben",
            "base_cost": 2.35,
            "allows_packstation": False,
            "has_tracking": True,
            "upgrade": None
        },
        "paeckchen": {
            "name": "Päckchen",
            "base_cost": 0.0,
            "allows_packstation": True,
            "has_tracking": False,
            "upgrade": {
                "type": "paket_2kg",
                "delta_cost": 1.50,
                "name": "Versichert versenden",
                "description": "Versichertes Paket bis 500€"
            }
        },
        "paket_2kg": {
            "name": "Versichertes Paket (2kg)",
            "base_cost": 1.50,
            "allows_packstation": True,
            "has_tracking": True,
            "upgrade": None
        }
    }


@pytest.fixture
def mock_shipping_tiers():
    """Mock shipping tiers from database."""
    return {
        3: [  # Subcategory 3 (USB Sticks)
            MagicMock(min_quantity=1, max_quantity=5, shipping_type="maxibrief"),
            MagicMock(min_quantity=6, max_quantity=10, shipping_type="paeckchen"),
            MagicMock(min_quantity=11, max_quantity=None, shipping_type="paket_2kg")
        ],
        5: [  # Subcategory 5 (Hardware)
            MagicMock(min_quantity=1, max_quantity=None, shipping_type="maxibrief")
        ]
    }


class TestCalculateShippingForCart:
    """Test shipping calculation for entire cart."""

    @pytest.mark.asyncio
    async def test_single_subcategory_single_item(self, mock_shipping_types, mock_shipping_tiers):
        """Single item from one subcategory."""
        cart_items = [
            CartItemDTO(category_id=1, id=1, subcategory_id=3, quantity=3, price=10.0, user_id=1, item_id=1)
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            with patch('services.cart_shipping.ShippingTierRepository.get_by_subcategory_ids',
                      return_value=mock_shipping_tiers):
                with patch('services.cart_shipping.ItemRepository.get_single',
                          return_value=MagicMock(is_physical=True, shipping_cost=0.0, allows_packstation=False)):

                    mock_session = AsyncMock()
                    result = await CartShippingService.calculate_shipping_for_cart(cart_items, mock_session)

                    assert len(result) == 1
                    assert 3 in result
                    assert result[3].shipping_type_key == "maxibrief"
                    assert result[3].base_cost == 0.0

    @pytest.mark.asyncio
    async def test_multiple_items_same_subcategory_sum_quantities(self, mock_shipping_types, mock_shipping_tiers):
        """Multiple items from same subcategory should sum quantities."""
        cart_items = [
            CartItemDTO(category_id=1, id=1, subcategory_id=3, quantity=3, price=10.0, user_id=1, item_id=1),
            CartItemDTO(category_id=1, id=2, subcategory_id=3, quantity=4, price=10.0, user_id=1, item_id=2)
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            with patch('services.cart_shipping.ShippingTierRepository.get_by_subcategory_ids',
                      return_value=mock_shipping_tiers):
                with patch('services.cart_shipping.ItemRepository.get_single',
                          return_value=MagicMock(is_physical=True, shipping_cost=0.0, allows_packstation=True)):

                    mock_session = AsyncMock()
                    result = await CartShippingService.calculate_shipping_for_cart(cart_items, mock_session)

                    # 3 + 4 = 7 items → should select paeckchen (6-10 range)
                    assert result[3].shipping_type_key == "paeckchen"

    @pytest.mark.asyncio
    async def test_multiple_subcategories_separate_shipping(self, mock_shipping_types, mock_shipping_tiers):
        """Multiple subcategories should each get separate shipping calculation."""
        cart_items = [
            CartItemDTO(category_id=1, id=1, subcategory_id=3, quantity=3, price=10.0, user_id=1, item_id=1),
            CartItemDTO(category_id=1, id=2, subcategory_id=5, quantity=2, price=15.0, user_id=1, item_id=2)
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            with patch('services.cart_shipping.ShippingTierRepository.get_by_subcategory_ids',
                      return_value=mock_shipping_tiers):
                with patch('services.cart_shipping.ItemRepository.get_single',
                          return_value=MagicMock(is_physical=True, shipping_cost=0.0, allows_packstation=False)):

                    mock_session = AsyncMock()
                    result = await CartShippingService.calculate_shipping_for_cart(cart_items, mock_session)

                    assert len(result) == 2
                    assert 3 in result
                    assert 5 in result


class TestCalculateShippingForSubcategory:
    """Test shipping calculation for single subcategory."""

    @pytest.mark.asyncio
    async def test_digital_items_return_none(self, mock_shipping_types):
        """Digital items should return None (no shipping)."""
        with patch('services.cart_shipping.ItemRepository.get_single',
                  return_value=MagicMock(is_physical=False)):

            mock_session = AsyncMock()
            result = await CartShippingService._calculate_shipping_for_subcategory(
                category_id=1,
                subcategory_id=1,
                quantity=5,
                shipping_tiers=[],
                shipping_types=mock_shipping_types,
                session=mock_session
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_no_tiers_fallback_to_legacy_shipping_cost(self, mock_shipping_types):
        """Items without shipping tiers should fallback to flat shipping_cost."""
        mock_item = MagicMock(
            is_physical=True,
            shipping_cost=5.0,
            allows_packstation=True
        )

        with patch('services.cart_shipping.ItemRepository.get_single',
                  return_value=mock_item):

            mock_session = AsyncMock()
            result = await CartShippingService._calculate_shipping_for_subcategory(
                category_id=1,
                subcategory_id=1,
                quantity=5,
                shipping_tiers=[],  # No tiers configured
                shipping_types=mock_shipping_types,
                session=mock_session
            )

            assert result is not None
            assert result.shipping_type_key == "legacy_flat"
            assert result.base_cost == 5.0
            assert result.allows_packstation is True

    @pytest.mark.asyncio
    async def test_valid_tier_selection(self, mock_shipping_types):
        """Valid tier selection based on quantity."""
        mock_tiers = [
            MagicMock(min_quantity=1, max_quantity=5, shipping_type="maxibrief"),
            MagicMock(min_quantity=6, max_quantity=None, shipping_type="paeckchen")
        ]

        with patch('services.cart_shipping.ItemRepository.get_single',
                  return_value=MagicMock(is_physical=True)):

            mock_session = AsyncMock()
            result = await CartShippingService._calculate_shipping_for_subcategory(
                category_id=1,
                subcategory_id=1,
                quantity=7,
                shipping_tiers=mock_tiers,
                shipping_types=mock_shipping_types,
                session=mock_session
            )

            assert result.shipping_type_key == "paeckchen"
            assert result.shipping_type_name == "Päckchen"

    @pytest.mark.asyncio
    async def test_shipping_type_not_found_in_config(self, mock_shipping_types):
        """Invalid shipping_type reference should return None."""
        mock_tiers = [
            MagicMock(min_quantity=1, max_quantity=None, shipping_type="invalid_type")
        ]

        with patch('services.cart_shipping.ItemRepository.get_single',
                  return_value=MagicMock(is_physical=True)):

            mock_session = AsyncMock()
            result = await CartShippingService._calculate_shipping_for_subcategory(
                category_id=1,
                subcategory_id=1,
                quantity=5,
                shipping_tiers=mock_tiers,
                shipping_types=mock_shipping_types,
                session=mock_session
            )

            assert result is None


class TestUpgradeOptionLoading:
    """Test upgrade option loading (Feature A3 backend)."""

    @pytest.mark.asyncio
    async def test_upgrade_option_loaded_when_available(self, mock_shipping_types):
        """Upgrade option should be loaded for base shipping types."""
        mock_tiers = [
            MagicMock(min_quantity=1, max_quantity=None, shipping_type="maxibrief")
        ]

        with patch('services.cart_shipping.ItemRepository.get_single',
                  return_value=MagicMock(is_physical=True)):

            mock_session = AsyncMock()
            result = await CartShippingService._calculate_shipping_for_subcategory(
                category_id=1,
                subcategory_id=1,
                quantity=5,
                shipping_tiers=mock_tiers,
                shipping_types=mock_shipping_types,
                session=mock_session
            )

            assert result.upgrade is not None
            assert result.upgrade["type"] == "maxibrief_einwurf"
            assert result.upgrade["delta_cost"] == 2.35
            assert "Sendungsverfolgung" in result.upgrade["name"]

    @pytest.mark.asyncio
    async def test_upgrade_option_none_for_top_tier(self, mock_shipping_types):
        """Top-tier shipping types should have no upgrade option."""
        mock_tiers = [
            MagicMock(min_quantity=1, max_quantity=None, shipping_type="paket_2kg")
        ]

        with patch('services.cart_shipping.ItemRepository.get_single',
                  return_value=MagicMock(is_physical=True)):

            mock_session = AsyncMock()
            result = await CartShippingService._calculate_shipping_for_subcategory(
                category_id=1,
                subcategory_id=1,
                quantity=5,
                shipping_tiers=mock_tiers,
                shipping_types=mock_shipping_types,
                session=mock_session
            )

            assert result.upgrade is None

    @pytest.mark.asyncio
    async def test_upgrade_chain_maxibrief_to_einwurf(self, mock_shipping_types):
        """Verify upgrade chain: maxibrief → maxibrief_einwurf."""
        mock_tiers = [
            MagicMock(min_quantity=1, max_quantity=None, shipping_type="maxibrief")
        ]

        with patch('services.cart_shipping.ItemRepository.get_single',
                  return_value=MagicMock(is_physical=True)):

            mock_session = AsyncMock()
            result = await CartShippingService._calculate_shipping_for_subcategory(
                category_id=1,
                subcategory_id=1,
                quantity=3,
                shipping_tiers=mock_tiers,
                shipping_types=mock_shipping_types,
                session=mock_session
            )

            # Base option
            assert result.shipping_type_key == "maxibrief"
            assert result.base_cost == 0.0
            assert result.has_tracking is False

            # Upgrade option
            assert result.upgrade["type"] == "maxibrief_einwurf"
            assert result.upgrade["delta_cost"] == 2.35

    @pytest.mark.asyncio
    async def test_upgrade_chain_paeckchen_to_paket(self, mock_shipping_types):
        """Verify upgrade chain: paeckchen → paket_2kg."""
        mock_tiers = [
            MagicMock(min_quantity=1, max_quantity=None, shipping_type="paeckchen")
        ]

        with patch('services.cart_shipping.ItemRepository.get_single',
                  return_value=MagicMock(is_physical=True)):

            mock_session = AsyncMock()
            result = await CartShippingService._calculate_shipping_for_subcategory(
                category_id=1,
                subcategory_id=1,
                quantity=3,
                shipping_tiers=mock_tiers,
                shipping_types=mock_shipping_types,
                session=mock_session
            )

            # Base option
            assert result.shipping_type_key == "paeckchen"
            assert result.base_cost == 0.0
            assert result.has_tracking is False

            # Upgrade option
            assert result.upgrade["type"] == "paket_2kg"
            assert result.upgrade["delta_cost"] == 1.50


class TestMaxShippingCost:
    """Test maximum shipping cost calculation."""

    @pytest.mark.asyncio
    async def test_max_cost_from_multiple_subcategories(self, mock_shipping_types, mock_shipping_tiers):
        """Should return highest shipping cost among subcategories."""
        cart_items = [
            CartItemDTO(category_id=1, id=1, subcategory_id=3, quantity=3, price=10.0, user_id=1, item_id=1),  # maxibrief (0.0)
            CartItemDTO(category_id=1, id=2, subcategory_id=3, quantity=10, price=10.0, user_id=1, item_id=2)  # paket_2kg (1.50)
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            with patch('services.cart_shipping.ShippingTierRepository.get_by_subcategory_ids',
                      return_value=mock_shipping_tiers):
                with patch('services.cart_shipping.ItemRepository.get_single',
                          return_value=MagicMock(is_physical=True, shipping_cost=0.0, allows_packstation=True)):

                    mock_session = AsyncMock()
                    max_cost = await CartShippingService.get_max_shipping_cost(cart_items, mock_session)

                    # 3 + 10 = 13 items → paket_2kg (€1.50)
                    assert max_cost == 1.50

    @pytest.mark.asyncio
    async def test_max_cost_all_free_shipping(self, mock_shipping_types, mock_shipping_tiers):
        """All free shipping should return 0.0."""
        cart_items = [
            CartItemDTO(category_id=1, id=1, subcategory_id=3, quantity=3, price=10.0, user_id=1, item_id=1)
        ]

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            with patch('services.cart_shipping.ShippingTierRepository.get_by_subcategory_ids',
                      return_value=mock_shipping_tiers):
                with patch('services.cart_shipping.ItemRepository.get_single',
                          return_value=MagicMock(is_physical=True, shipping_cost=0.0, allows_packstation=False)):

                    mock_session = AsyncMock()
                    max_cost = await CartShippingService.get_max_shipping_cost(cart_items, mock_session)

                    assert max_cost == 0.0

    @pytest.mark.asyncio
    async def test_max_cost_only_digital_items(self):
        """Only digital items should return 0.0."""
        cart_items = [
            CartItemDTO(category_id=1, id=1, subcategory_id=1, quantity=5, price=10.0, user_id=1, item_id=1)
        ]

        with patch('services.cart_shipping.CartShippingService.calculate_shipping_for_cart',
                  return_value={}):  # No physical items

            mock_session = AsyncMock()
            max_cost = await CartShippingService.get_max_shipping_cost(cart_items, mock_session)

            assert max_cost == 0.0


class TestShippingSummaryText:
    """Test shipping summary text generation."""

    @pytest.mark.asyncio
    async def test_summary_text_format(self, mock_shipping_types, mock_shipping_tiers):
        """Summary text should contain subcategory names, quantities, and costs."""
        cart_items = [
            CartItemDTO(category_id=1, id=1, subcategory_id=3, quantity=7, price=10.0, user_id=1, item_id=1)
        ]

        mock_subcategories = {
            3: MagicMock(id=3, name="USB Sticks")
        }

        with patch('services.cart_shipping.get_shipping_types', return_value=mock_shipping_types):
            with patch('services.cart_shipping.ShippingTierRepository.get_by_subcategory_ids',
                      return_value=mock_shipping_tiers):
                with patch('services.cart_shipping.ItemRepository.get_single',
                          return_value=MagicMock(is_physical=True, shipping_cost=0.0, allows_packstation=True)):
                    with patch('repositories.subcategory.SubcategoryRepository.get_by_ids',
                              return_value=mock_subcategories):

                        mock_session = AsyncMock()
                        summary = await CartShippingService.get_shipping_summary_text(cart_items, mock_session)

                        assert "USB Sticks" in summary
                        assert "(7x)" in summary
                        assert "Päckchen" in summary

    @pytest.mark.asyncio
    async def test_summary_text_empty_for_digital_cart(self):
        """Empty cart or only digital items should return empty string."""
        with patch('services.cart_shipping.CartShippingService.calculate_shipping_for_cart',
                  return_value={}):

            mock_session = AsyncMock()
            summary = await CartShippingService.get_shipping_summary_text([], mock_session)

            assert summary == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])