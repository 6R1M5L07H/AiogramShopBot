"""
Unit tests for ItemUnit enum.

Tests cover:
- Enum values and validation
- from_string() conversion
- Case insensitivity
- Whitespace handling
- Edge cases and error handling
"""

import pytest
from enums.item_unit import ItemUnit


class TestItemUnitEnum:
    """Test ItemUnit enum values and properties."""

    def test_all_enum_values(self):
        """Test that all expected units are defined."""
        expected_units = {
            "pcs.", "pairs", "pkg.",  # Text-based
            "g", "kg", "ml", "l", "m", "m2"  # International
        }
        actual_units = {unit.value for unit in ItemUnit}
        assert actual_units == expected_units

    def test_default_unit(self):
        """Test that default unit is PIECES."""
        assert ItemUnit.PIECES.value == "pcs."

    def test_enum_display_names(self):
        """Test display name property."""
        assert ItemUnit.PIECES.display_name == "Pieces"
        assert ItemUnit.SQUARE_METERS.display_name == "Square Meters"
        assert ItemUnit.KILOGRAMS.display_name == "Kilograms"


class TestFromString:
    """Test from_string() conversion method."""

    def test_exact_match(self):
        """Test exact string matching."""
        assert ItemUnit.from_string("pcs.") == ItemUnit.PIECES
        assert ItemUnit.from_string("g") == ItemUnit.GRAMS
        assert ItemUnit.from_string("kg") == ItemUnit.KILOGRAMS
        assert ItemUnit.from_string("ml") == ItemUnit.MILLILITERS
        assert ItemUnit.from_string("l") == ItemUnit.LITERS
        assert ItemUnit.from_string("m") == ItemUnit.METERS
        assert ItemUnit.from_string("m2") == ItemUnit.SQUARE_METERS
        assert ItemUnit.from_string("pairs") == ItemUnit.PAIRS
        assert ItemUnit.from_string("pkg.") == ItemUnit.PACKAGES

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        assert ItemUnit.from_string("PCS.") == ItemUnit.PIECES
        assert ItemUnit.from_string("G") == ItemUnit.GRAMS
        assert ItemUnit.from_string("KG") == ItemUnit.KILOGRAMS
        assert ItemUnit.from_string("ML") == ItemUnit.MILLILITERS
        assert ItemUnit.from_string("L") == ItemUnit.LITERS
        assert ItemUnit.from_string("M") == ItemUnit.METERS
        assert ItemUnit.from_string("M2") == ItemUnit.SQUARE_METERS
        assert ItemUnit.from_string("PAIRS") == ItemUnit.PAIRS
        assert ItemUnit.from_string("PKG.") == ItemUnit.PACKAGES

    def test_whitespace_trimming(self):
        """Test whitespace stripping."""
        assert ItemUnit.from_string(" pcs. ") == ItemUnit.PIECES
        assert ItemUnit.from_string("  g  ") == ItemUnit.GRAMS
        assert ItemUnit.from_string("\tkg\t") == ItemUnit.KILOGRAMS
        assert ItemUnit.from_string(" pairs ") == ItemUnit.PAIRS

    def test_mixed_case_and_whitespace(self):
        """Test combined case insensitivity and whitespace."""
        assert ItemUnit.from_string(" PCS. ") == ItemUnit.PIECES
        assert ItemUnit.from_string("  G  ") == ItemUnit.GRAMS
        assert ItemUnit.from_string(" PAIRS ") == ItemUnit.PAIRS


class TestFromStringErrors:
    """Test from_string() error handling."""

    def test_empty_string(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError, match="Unit cannot be empty"):
            ItemUnit.from_string("")

    def test_none_value(self):
        """Test None value raises ValueError."""
        with pytest.raises(ValueError, match="Unit cannot be empty"):
            ItemUnit.from_string(None)

    def test_invalid_unit(self):
        """Test invalid unit raises ValueError with suggestions."""
        with pytest.raises(ValueError, match="Invalid unit 'invalid'"):
            ItemUnit.from_string("invalid")

    def test_error_message_shows_valid_units(self):
        """Test error message includes valid units list."""
        try:
            ItemUnit.from_string("oz")  # Not yet supported
        except ValueError as e:
            error_msg = str(e)
            # Should contain list of valid units
            assert "pcs." in error_msg
            assert "g" in error_msg
            assert "kg" in error_msg

    def test_whitespace_only(self):
        """Test whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Unit cannot be empty"):
            ItemUnit.from_string("   ")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_period_handling(self):
        """Test units with periods are handled correctly."""
        assert ItemUnit.from_string("pcs.") == ItemUnit.PIECES
        assert ItemUnit.from_string("pkg.") == ItemUnit.PACKAGES

    def test_numeric_units(self):
        """Test units with numbers (m2)."""
        assert ItemUnit.from_string("m2") == ItemUnit.SQUARE_METERS
        assert ItemUnit.from_string("M2") == ItemUnit.SQUARE_METERS

    def test_single_character_units(self):
        """Test single-character units."""
        assert ItemUnit.from_string("g") == ItemUnit.GRAMS
        assert ItemUnit.from_string("l") == ItemUnit.LITERS
        assert ItemUnit.from_string("m") == ItemUnit.METERS

    def test_string_enum_behavior(self):
        """Test that ItemUnit behaves as string enum."""
        # Can compare with strings
        assert ItemUnit.PIECES == "pcs."
        assert ItemUnit.GRAMS == "g"

        # Value property gives the string value
        unit = ItemUnit.PIECES
        assert unit.value == "pcs."


class TestAllUnitsCovered:
    """Ensure all enum members are tested."""

    def test_all_units_have_from_string_test(self):
        """Verify all units can be created via from_string()."""
        for unit in ItemUnit:
            # Should not raise
            result = ItemUnit.from_string(unit.value)
            assert result == unit

    def test_all_units_have_display_name(self):
        """Verify all units have display names."""
        for unit in ItemUnit:
            # Should not raise
            display_name = unit.display_name
            assert isinstance(display_name, str)
            assert len(display_name) > 0