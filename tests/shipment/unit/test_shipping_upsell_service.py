"""
Unit Tests for ShippingUpsellService

Tests shipping upsell logic with various scenarios and edge cases.
Follows strict Service/UI separation (no Telegram objects).
"""

import pytest
from unittest.mock import patch

from services.shipping_upsell import ShippingUpsellService


class TestGetUpgradeForShippingType:
    """Test get_upgrade_for_shipping_type() method."""

    @patch('services.shipping_upsell.get_shipping_types')
    def test_get_upgrade_success(self, mock_get_shipping_types):
        """Test successful retrieval of upgrade option."""
        # Arrange
        mock_get_shipping_types.return_value = {
            "paeckchen": {
                "name": "Päckchen",
                "base_cost": 0.00,
                "upgrade": {
                    "type": "paket_2kg",
                    "delta_cost": 1.50,
                    "name": "Versichert versenden",
                    "description": "Versichertes Paket bis 500€"
                }
            }
        }

        # Act
        result = ShippingUpsellService.get_upgrade_for_shipping_type("paeckchen")

        # Assert
        assert result is not None
        assert result["type"] == "paket_2kg"
        assert result["delta_cost"] == 1.50
        assert result["name"] == "Versichert versenden"
        assert result["description"] == "Versichertes Paket bis 500€"

    @patch('services.shipping_upsell.get_shipping_types')
    def test_get_upgrade_no_upgrade_available(self, mock_get_shipping_types):
        """Test when shipping type has no upgrade."""
        # Arrange
        mock_get_shipping_types.return_value = {
            "paket_5kg": {
                "name": "Paket 5kg",
                "base_cost": 0.00,
                "upgrade": None
            }
        }

        # Act
        result = ShippingUpsellService.get_upgrade_for_shipping_type("paket_5kg")

        # Assert
        assert result is None

    @patch('services.shipping_upsell.get_shipping_types')
    def test_get_upgrade_shipping_type_not_found(self, mock_get_shipping_types):
        """Test with non-existent shipping type."""
        # Arrange
        mock_get_shipping_types.return_value = {
            "paeckchen": {
                "name": "Päckchen",
                "base_cost": 0.00,
                "upgrade": None
            }
        }

        # Act
        result = ShippingUpsellService.get_upgrade_for_shipping_type("invalid_key")

        # Assert
        assert result is None

    @patch('services.shipping_upsell.get_shipping_types')
    def test_get_upgrade_no_config_loaded(self, mock_get_shipping_types):
        """Test when shipping_types config is not loaded."""
        # Arrange
        mock_get_shipping_types.return_value = None

        # Act
        result = ShippingUpsellService.get_upgrade_for_shipping_type("paeckchen")

        # Assert
        assert result is None

    @patch('services.shipping_upsell.get_shipping_types')
    def test_get_upgrade_empty_config(self, mock_get_shipping_types):
        """Test with empty shipping_types config."""
        # Arrange
        mock_get_shipping_types.return_value = {}

        # Act
        result = ShippingUpsellService.get_upgrade_for_shipping_type("paeckchen")

        # Assert
        assert result is None


class TestCalculateTotalCostWithUpgrade:
    """Test calculate_total_cost_with_upgrade() method."""

    def test_calculate_zero_base_cost(self):
        """Test calculation with zero base cost."""
        # Act
        result = ShippingUpsellService.calculate_total_cost_with_upgrade(0.00, 1.50)

        # Assert
        assert result == 1.50

    def test_calculate_non_zero_base_cost(self):
        """Test calculation with non-zero base cost."""
        # Act
        result = ShippingUpsellService.calculate_total_cost_with_upgrade(2.00, 1.50)

        # Assert
        assert result == 3.50

    def test_calculate_zero_upgrade_cost(self):
        """Test calculation with zero upgrade cost (edge case)."""
        # Act
        result = ShippingUpsellService.calculate_total_cost_with_upgrade(2.00, 0.00)

        # Assert
        assert result == 2.00

    def test_calculate_both_zero(self):
        """Test calculation with both costs zero."""
        # Act
        result = ShippingUpsellService.calculate_total_cost_with_upgrade(0.00, 0.00)

        # Assert
        assert result == 0.00

    def test_calculate_precision(self):
        """Test calculation handles floating-point precision."""
        # Act
        result = ShippingUpsellService.calculate_total_cost_with_upgrade(0.10, 0.20)

        # Assert
        assert result == 0.30
        assert isinstance(result, float)

    def test_calculate_large_values(self):
        """Test calculation with large values."""
        # Act
        result = ShippingUpsellService.calculate_total_cost_with_upgrade(100.50, 50.25)

        # Assert
        assert result == 150.75


class TestGetShippingTypeDetails:
    """Test get_shipping_type_details() method."""

    @patch('services.shipping_upsell.get_shipping_types')
    def test_get_details_success(self, mock_get_shipping_types):
        """Test successful retrieval of shipping type details."""
        # Arrange
        mock_get_shipping_types.return_value = {
            "paeckchen": {
                "name": "Päckchen",
                "base_cost": 0.00,
                "allows_packstation": True,
                "has_tracking": False,
                "description": "DHL Päckchen"
            }
        }

        # Act
        result = ShippingUpsellService.get_shipping_type_details("paeckchen")

        # Assert
        assert result is not None
        assert result["name"] == "Päckchen"
        assert result["base_cost"] == 0.00
        assert result["allows_packstation"] is True
        assert result["has_tracking"] is False
        assert result["description"] == "DHL Päckchen"

    @patch('services.shipping_upsell.get_shipping_types')
    def test_get_details_not_found(self, mock_get_shipping_types):
        """Test with non-existent shipping type."""
        # Arrange
        mock_get_shipping_types.return_value = {
            "paeckchen": {
                "name": "Päckchen",
                "base_cost": 0.00
            }
        }

        # Act
        result = ShippingUpsellService.get_shipping_type_details("invalid_key")

        # Assert
        assert result is None

    @patch('services.shipping_upsell.get_shipping_types')
    def test_get_details_no_config(self, mock_get_shipping_types):
        """Test when config is not loaded."""
        # Arrange
        mock_get_shipping_types.return_value = None

        # Act
        result = ShippingUpsellService.get_shipping_type_details("paeckchen")

        # Assert
        assert result is None


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('services.shipping_upsell.get_shipping_types')
    def test_malformed_upgrade_structure(self, mock_get_shipping_types):
        """Test with malformed upgrade structure."""
        # Arrange
        mock_get_shipping_types.return_value = {
            "paeckchen": {
                "name": "Päckchen",
                "upgrade": {}  # Empty dict instead of None or proper structure
            }
        }

        # Act
        result = ShippingUpsellService.get_upgrade_for_shipping_type("paeckchen")

        # Assert - Should handle gracefully and return None
        assert result is None

    @patch('services.shipping_upsell.get_shipping_types')
    def test_missing_upgrade_key(self, mock_get_shipping_types):
        """Test shipping type without upgrade key."""
        # Arrange
        mock_get_shipping_types.return_value = {
            "paeckchen": {
                "name": "Päckchen",
                "base_cost": 0.00
                # No "upgrade" key
            }
        }

        # Act
        result = ShippingUpsellService.get_upgrade_for_shipping_type("paeckchen")

        # Assert
        assert result is None

    def test_calculate_negative_costs(self):
        """Test calculation with negative costs (edge case)."""
        # Act
        result = ShippingUpsellService.calculate_total_cost_with_upgrade(-1.00, 2.00)

        # Assert
        assert result == 1.00  # Should still calculate

    @patch('services.shipping_upsell.get_shipping_types')
    def test_unicode_in_shipping_names(self, mock_get_shipping_types):
        """Test handling of unicode characters in names."""
        # Arrange
        mock_get_shipping_types.return_value = {
            "paeckchen": {
                "name": "Päckchen mit Ümläüten",
                "base_cost": 0.00,
                "upgrade": {
                    "type": "paket",
                    "name": "Versichért",
                    "delta_cost": 1.50,
                    "description": "Beschreibüng"
                }
            }
        }

        # Act
        result = ShippingUpsellService.get_upgrade_for_shipping_type("paeckchen")

        # Assert
        assert result is not None
        assert "Versichért" in result["name"]
        assert "Beschreibüng" in result["description"]
