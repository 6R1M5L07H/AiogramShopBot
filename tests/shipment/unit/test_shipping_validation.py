"""
Unit Tests: Shipping Validation Utilities

Tests for shipping_validation.py covering:
- Shipping type reference validation
- Tier coverage validation (gaps, overlaps, start/end)
- Individual tier logic validation
- Quantity-based shipping type selection
"""

import pytest
from utils.shipping_validation import (
    validate_shipping_type_reference,
    validate_tier_coverage,
    validate_tier_logic,
    get_shipping_type_for_quantity
)


class TestShippingTypeReferenceValidation:
    """Test validation of shipping type references against configuration."""

    def test_valid_shipping_type_reference(self):
        """Valid shipping type exists in configuration."""
        shipping_types = {
            "maxibrief": {"name": "Maxibrief", "base_cost": 0.0},
            "paeckchen": {"name": "Päckchen", "base_cost": 0.0}
        }
        assert validate_shipping_type_reference("maxibrief", shipping_types) is True

    def test_invalid_shipping_type_reference(self):
        """Invalid shipping type does not exist in configuration."""
        shipping_types = {
            "maxibrief": {"name": "Maxibrief", "base_cost": 0.0}
        }
        assert validate_shipping_type_reference("invalid_type", shipping_types) is False

    def test_empty_shipping_types_dict(self):
        """Empty shipping types configuration."""
        assert validate_shipping_type_reference("maxibrief", {}) is False


class TestTierCoverageValidation:
    """Test validation of tier coverage completeness."""

    def test_valid_tier_coverage(self):
        """Valid tier coverage: 1 to infinity, no gaps."""
        tiers = [
            {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
            {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"},
            {"min_quantity": 11, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]
        is_valid, error = validate_tier_coverage(tiers)
        assert is_valid is True
        assert error is None

    def test_tier_coverage_does_not_start_at_one(self):
        """Tier coverage must start at quantity 1."""
        tiers = [
            {"min_quantity": 5, "max_quantity": 10, "shipping_type": "maxibrief"},
            {"min_quantity": 11, "max_quantity": None, "shipping_type": "paeckchen"}
        ]
        is_valid, error = validate_tier_coverage(tiers)
        assert is_valid is False
        assert "must start at quantity 1" in error

    def test_tier_coverage_missing_unlimited_tier(self):
        """At least one tier must have max_quantity=None."""
        tiers = [
            {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
            {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"}
        ]
        is_valid, error = validate_tier_coverage(tiers)
        assert is_valid is False
        assert "unlimited" in error.lower()

    def test_tier_coverage_gap_detected(self):
        """Gap between tiers should be detected."""
        tiers = [
            {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
            {"min_quantity": 8, "max_quantity": None, "shipping_type": "paeckchen"}  # Gap 6-7
        ]
        is_valid, error = validate_tier_coverage(tiers)
        assert is_valid is False
        assert "gap" in error.lower()

    def test_tier_coverage_overlap_detected(self):
        """Overlap between tiers should be detected."""
        tiers = [
            {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
            {"min_quantity": 4, "max_quantity": None, "shipping_type": "paeckchen"}  # Overlap at 4-5
        ]
        is_valid, error = validate_tier_coverage(tiers)
        assert is_valid is False
        assert "overlap" in error.lower()

    def test_tier_coverage_unlimited_in_middle(self):
        """Only the last tier can have max_quantity=None."""
        tiers = [
            {"min_quantity": 1, "max_quantity": None, "shipping_type": "maxibrief"},  # Unlimited in middle
            {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"}
        ]
        is_valid, error = validate_tier_coverage(tiers)
        assert is_valid is False
        assert "only the last tier" in error.lower()

    def test_tier_coverage_empty_list(self):
        """Empty tier list is invalid."""
        is_valid, error = validate_tier_coverage([])
        assert is_valid is False
        assert "at least one" in error.lower()


class TestIndividualTierLogicValidation:
    """Test validation of individual tier logic."""

    def test_valid_tier_logic(self):
        """Valid tier with all required fields."""
        tier = {
            "min_quantity": 1,
            "max_quantity": 5,
            "shipping_type": "maxibrief"
        }
        is_valid, error = validate_tier_logic(tier)
        assert is_valid is True
        assert error is None

    def test_valid_tier_logic_unlimited(self):
        """Valid tier with unlimited max_quantity."""
        tier = {
            "min_quantity": 1,
            "max_quantity": None,
            "shipping_type": "maxibrief"
        }
        is_valid, error = validate_tier_logic(tier)
        assert is_valid is True
        assert error is None

    def test_tier_logic_missing_min_quantity(self):
        """Tier must have min_quantity."""
        tier = {
            "max_quantity": 5,
            "shipping_type": "maxibrief"
        }
        is_valid, error = validate_tier_logic(tier)
        assert is_valid is False
        assert "min_quantity" in error

    def test_tier_logic_missing_shipping_type(self):
        """Tier must have shipping_type."""
        tier = {
            "min_quantity": 1,
            "max_quantity": 5
        }
        is_valid, error = validate_tier_logic(tier)
        assert is_valid is False
        assert "shipping_type" in error

    def test_tier_logic_zero_min_quantity(self):
        """min_quantity must be positive."""
        tier = {
            "min_quantity": 0,
            "max_quantity": 5,
            "shipping_type": "maxibrief"
        }
        is_valid, error = validate_tier_logic(tier)
        assert is_valid is False
        assert "must be > 0" in error

    def test_tier_logic_max_less_than_min(self):
        """max_quantity must be >= min_quantity."""
        tier = {
            "min_quantity": 10,
            "max_quantity": 5,
            "shipping_type": "maxibrief"
        }
        is_valid, error = validate_tier_logic(tier)
        assert is_valid is False
        assert "must be >=" in error


class TestQuantityBasedShippingTypeSelection:
    """Test shipping type selection based on quantity."""

    def setup_method(self):
        """Set up common test data."""
        self.tiers = [
            {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
            {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"},
            {"min_quantity": 11, "max_quantity": None, "shipping_type": "paket_2kg"}
        ]

    def test_select_first_tier(self):
        """Quantity 1-5 should select maxibrief."""
        assert get_shipping_type_for_quantity(self.tiers, 1) == "maxibrief"
        assert get_shipping_type_for_quantity(self.tiers, 3) == "maxibrief"
        assert get_shipping_type_for_quantity(self.tiers, 5) == "maxibrief"

    def test_select_second_tier(self):
        """Quantity 6-10 should select paeckchen."""
        assert get_shipping_type_for_quantity(self.tiers, 6) == "paeckchen"
        assert get_shipping_type_for_quantity(self.tiers, 8) == "paeckchen"
        assert get_shipping_type_for_quantity(self.tiers, 10) == "paeckchen"

    def test_select_unlimited_tier(self):
        """Quantity 11+ should select paket_2kg."""
        assert get_shipping_type_for_quantity(self.tiers, 11) == "paket_2kg"
        assert get_shipping_type_for_quantity(self.tiers, 50) == "paket_2kg"
        assert get_shipping_type_for_quantity(self.tiers, 1000) == "paket_2kg"

    def test_select_boundary_values(self):
        """Test boundary values between tiers."""
        assert get_shipping_type_for_quantity(self.tiers, 5) == "maxibrief"  # Last of tier 1
        assert get_shipping_type_for_quantity(self.tiers, 6) == "paeckchen"  # First of tier 2
        assert get_shipping_type_for_quantity(self.tiers, 10) == "paeckchen"  # Last of tier 2
        assert get_shipping_type_for_quantity(self.tiers, 11) == "paket_2kg"  # First of tier 3

    def test_select_invalid_quantity_zero(self):
        """Quantity 0 is invalid."""
        assert get_shipping_type_for_quantity(self.tiers, 0) is None

    def test_select_invalid_quantity_negative(self):
        """Negative quantity is invalid."""
        assert get_shipping_type_for_quantity(self.tiers, -5) is None

    def test_select_empty_tiers(self):
        """Empty tier list returns None."""
        assert get_shipping_type_for_quantity([], 5) is None

    def test_select_unsorted_tiers(self):
        """Function should handle unsorted tiers."""
        unsorted_tiers = [
            {"min_quantity": 11, "max_quantity": None, "shipping_type": "paket_2kg"},
            {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
            {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"}
        ]
        assert get_shipping_type_for_quantity(unsorted_tiers, 3) == "maxibrief"
        assert get_shipping_type_for_quantity(unsorted_tiers, 8) == "paeckchen"
        assert get_shipping_type_for_quantity(unsorted_tiers, 20) == "paket_2kg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])