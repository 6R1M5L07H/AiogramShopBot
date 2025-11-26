"""
Unit tests for Localizator.localize_unit() method.

Tests cover:
- Text-based unit localization (pcs., pairs, pkg.)
- International unit pass-through (g, kg, ml, l, m, m2)
- Language switching (EN/DE)
- Edge cases (None, empty string, whitespace, unknown units)
- Case sensitivity and normalization
"""

import pytest
from unittest.mock import patch
from utils.localizator import Localizator
from enums.item_unit import ItemUnit


class TestLocalizeUnitTextBased:
    """Test localization of text-based units (pcs., pairs, pkg.)."""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_pieces_german(self):
        """Test pieces localized to German."""
        result = Localizator.localize_unit("pcs.")
        assert result == "Stk."

    @patch('config.BOT_LANGUAGE', 'en')
    def test_pieces_english(self):
        """Test pieces in English (unchanged)."""
        result = Localizator.localize_unit("pcs.")
        assert result == "pcs."

    @patch('config.BOT_LANGUAGE', 'de')
    def test_pairs_german(self):
        """Test pairs localized to German."""
        result = Localizator.localize_unit("pairs")
        assert result == "Paar"

    @patch('config.BOT_LANGUAGE', 'en')
    def test_pairs_english(self):
        """Test pairs in English (unchanged)."""
        result = Localizator.localize_unit("pairs")
        assert result == "pairs"

    @patch('config.BOT_LANGUAGE', 'de')
    def test_packages_german(self):
        """Test packages localized to German."""
        result = Localizator.localize_unit("pkg.")
        assert result == "Pack."

    @patch('config.BOT_LANGUAGE', 'en')
    def test_packages_english(self):
        """Test packages in English (unchanged)."""
        result = Localizator.localize_unit("pkg.")
        assert result == "pkg."


class TestLocalizeUnitInternational:
    """Test pass-through of international units (no localization)."""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_grams_passthrough_german(self):
        """Test grams unchanged in German."""
        result = Localizator.localize_unit("g")
        assert result == "g"

    @patch('config.BOT_LANGUAGE', 'en')
    def test_grams_passthrough_english(self):
        """Test grams unchanged in English."""
        result = Localizator.localize_unit("g")
        assert result == "g"

    @patch('config.BOT_LANGUAGE', 'de')
    def test_kilograms_passthrough(self):
        """Test kilograms unchanged."""
        result = Localizator.localize_unit("kg")
        assert result == "kg"

    @patch('config.BOT_LANGUAGE', 'de')
    def test_milliliters_passthrough(self):
        """Test milliliters unchanged."""
        result = Localizator.localize_unit("ml")
        assert result == "ml"

    @patch('config.BOT_LANGUAGE', 'de')
    def test_liters_passthrough(self):
        """Test liters unchanged."""
        result = Localizator.localize_unit("l")
        assert result == "l"

    @patch('config.BOT_LANGUAGE', 'de')
    def test_meters_passthrough(self):
        """Test meters unchanged."""
        result = Localizator.localize_unit("m")
        assert result == "m"

    @patch('config.BOT_LANGUAGE', 'de')
    def test_square_meters_passthrough(self):
        """Test square meters unchanged."""
        result = Localizator.localize_unit("m2")
        assert result == "m2"


class TestLocalizeUnitCaseSensitivity:
    """Test case-insensitive normalization."""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_uppercase_pieces(self):
        """Test uppercase PCS. normalized to Stk."""
        result = Localizator.localize_unit("PCS.")
        assert result == "Stk."

    @patch('config.BOT_LANGUAGE', 'de')
    def test_mixed_case_pairs(self):
        """Test mixed case PaIrS normalized to Paar."""
        result = Localizator.localize_unit("PaIrS")
        assert result == "Paar"

    @patch('config.BOT_LANGUAGE', 'de')
    def test_uppercase_international_unit(self):
        """Test uppercase G remains G (pass-through)."""
        result = Localizator.localize_unit("G")
        assert result == "G"

    @patch('config.BOT_LANGUAGE', 'en')
    def test_lowercase_packages_english(self):
        """Test lowercase pkg. remains pkg. in English."""
        result = Localizator.localize_unit("pkg.")
        assert result == "pkg."


class TestLocalizeUnitWhitespace:
    """Test whitespace handling and trimming."""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_leading_whitespace(self):
        """Test leading whitespace trimmed."""
        result = Localizator.localize_unit("  pcs.")
        assert result == "Stk."

    @patch('config.BOT_LANGUAGE', 'de')
    def test_trailing_whitespace(self):
        """Test trailing whitespace trimmed."""
        result = Localizator.localize_unit("pcs.  ")
        assert result == "Stk."

    @patch('config.BOT_LANGUAGE', 'de')
    def test_both_whitespace(self):
        """Test both leading and trailing whitespace trimmed."""
        result = Localizator.localize_unit("  pairs  ")
        assert result == "Paar"

    @patch('config.BOT_LANGUAGE', 'de')
    def test_tab_whitespace(self):
        """Test tab characters trimmed."""
        result = Localizator.localize_unit("\tpkg.\t")
        assert result == "Pack."

    @patch('config.BOT_LANGUAGE', 'de')
    def test_international_with_whitespace(self):
        """Test international unit with whitespace (pass-through)."""
        result = Localizator.localize_unit(" g ")
        assert result == " g "  # Pass-through returns original


class TestLocalizeUnitEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_none_value(self):
        """Test None value returns None (defensive programming)."""
        result = Localizator.localize_unit(None)
        assert result is None

    @patch('config.BOT_LANGUAGE', 'de')
    def test_empty_string(self):
        """Test empty string returns empty string."""
        result = Localizator.localize_unit("")
        assert result == ""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_whitespace_only(self):
        """Test whitespace-only string returns empty after normalization."""
        result = Localizator.localize_unit("   ")
        # After strip().lower(), becomes empty string -> not in map -> pass-through
        assert result == "   "

    @patch('config.BOT_LANGUAGE', 'de')
    def test_unknown_unit_passthrough(self):
        """Test unknown unit passed through unchanged."""
        result = Localizator.localize_unit("oz")  # Not yet in enum
        assert result == "oz"

    @patch('config.BOT_LANGUAGE', 'fr')
    def test_unsupported_language_fallback_to_english(self):
        """Test unsupported language falls back to English."""
        result = Localizator.localize_unit("pcs.")
        # French not in map -> fallback to "en" -> "pcs."
        assert result == "pcs."


class TestLocalizeUnitLanguageSwitching:
    """Test switching between languages."""

    def test_switch_de_to_en(self):
        """Test switching from German to English."""
        with patch('config.BOT_LANGUAGE', 'de'):
            result_de = Localizator.localize_unit("pcs.")
            assert result_de == "Stk."

        with patch('config.BOT_LANGUAGE', 'en'):
            result_en = Localizator.localize_unit("pcs.")
            assert result_en == "pcs."

    def test_switch_en_to_de(self):
        """Test switching from English to German."""
        with patch('config.BOT_LANGUAGE', 'en'):
            result_en = Localizator.localize_unit("pairs")
            assert result_en == "pairs"

        with patch('config.BOT_LANGUAGE', 'de'):
            result_de = Localizator.localize_unit("pairs")
            assert result_de == "Paar"


class TestLocalizeUnitIntegration:
    """Integration tests with ItemUnit enum."""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_all_text_based_units_have_german_translation(self):
        """Verify all text-based units have German translations."""
        text_based_units = ["pcs.", "pairs", "pkg."]
        for unit in text_based_units:
            result = Localizator.localize_unit(unit)
            # Must be different from EN value
            assert result != unit
            # Must be non-empty
            assert len(result) > 0

    @patch('config.BOT_LANGUAGE', 'de')
    def test_all_international_units_passthrough(self):
        """Verify all international units pass through unchanged."""
        international_units = ["g", "kg", "ml", "l", "m", "m2"]
        for unit in international_units:
            result = Localizator.localize_unit(unit)
            assert result == unit

    @patch('config.BOT_LANGUAGE', 'de')
    def test_all_enum_values_localizable(self):
        """Test that all ItemUnit enum values can be localized."""
        for unit_enum in ItemUnit:
            unit_value = unit_enum.value
            # Should not raise
            result = Localizator.localize_unit(unit_value)
            # Must return non-empty string
            assert isinstance(result, str)
            assert len(result) > 0


class TestLocalizeUnitNormalization:
    """Test normalization behavior in detail."""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_normalization_before_lookup(self):
        """Test that normalization (strip + lowercase) happens before lookup."""
        # All these should map to "Stk."
        test_cases = [
            "pcs.",
            "PCS.",
            " pcs. ",
            "  PCS.  ",
            "\tpcs.\t",
            "Pcs.",
            " PcS. "
        ]
        for test_input in test_cases:
            result = Localizator.localize_unit(test_input)
            assert result == "Stk.", f"Failed for input: {test_input!r}"

    @patch('config.BOT_LANGUAGE', 'en')
    def test_normalization_preserves_original_case_on_passthrough(self):
        """Test that pass-through units preserve original casing."""
        # International units not in map -> return original
        assert Localizator.localize_unit("G") == "G"
        assert Localizator.localize_unit("g") == "g"
        assert Localizator.localize_unit("ML") == "ML"

    @patch('config.BOT_LANGUAGE', 'de')
    def test_normalization_handles_period_correctly(self):
        """Test that periods in units are handled correctly."""
        # "pcs." with period
        assert Localizator.localize_unit("pcs.") == "Stk."
        # "pkg." with period
        assert Localizator.localize_unit("pkg.") == "Pack."
        # Without period (unknown) -> pass-through
        assert Localizator.localize_unit("pcs") == "pcs"


class TestLocalizeUnitI18nMap:
    """Test UNIT_I18N_MAP structure and completeness."""

    def test_i18n_map_has_de_and_en(self):
        """Test that all entries in map have both 'de' and 'en' keys."""
        for unit, translations in Localizator.UNIT_I18N_MAP.items():
            assert "de" in translations, f"Missing 'de' translation for {unit}"
            assert "en" in translations, f"Missing 'en' translation for {unit}"

    def test_i18n_map_english_matches_key(self):
        """Test that English translation matches the map key."""
        for unit, translations in Localizator.UNIT_I18N_MAP.items():
            assert translations["en"] == unit, f"EN translation mismatch for {unit}"

    def test_i18n_map_only_text_based_units(self):
        """Test that only text-based units are in the map (not international)."""
        # Expected text-based units
        expected_units = {"pcs.", "pairs", "pkg."}
        actual_units = set(Localizator.UNIT_I18N_MAP.keys())
        assert actual_units == expected_units

    def test_i18n_map_no_international_units(self):
        """Test that international units are NOT in the map."""
        international_units = ["g", "kg", "ml", "l", "m", "m2"]
        for unit in international_units:
            assert unit not in Localizator.UNIT_I18N_MAP


class TestLocalizeUnitRealWorldScenarios:
    """Test real-world usage scenarios."""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_invoice_display_scenario(self):
        """Test typical invoice display scenario."""
        # Item 1: 5 pieces of something
        quantity = 5
        unit = "pcs."
        localized_unit = Localizator.localize_unit(unit)
        display = f"{quantity} {localized_unit}"
        assert display == "5 Stk."

    @patch('config.BOT_LANGUAGE', 'de')
    def test_cart_display_scenario(self):
        """Test typical cart display scenario."""
        # Item 2: 250g of something
        quantity = 250
        unit = "g"
        localized_unit = Localizator.localize_unit(unit)
        display = f"{quantity}{localized_unit}"
        assert display == "250g"

    @patch('config.BOT_LANGUAGE', 'en')
    def test_admin_panel_scenario(self):
        """Test typical admin panel scenario (English)."""
        items = [
            ("Item A", "pcs."),
            ("Item B", "g"),
            ("Item C", "pairs"),
        ]
        results = []
        for name, unit in items:
            localized = Localizator.localize_unit(unit)
            results.append(f"{name}: {localized}")

        assert results == [
            "Item A: pcs.",
            "Item B: g",
            "Item C: pairs"
        ]

    @patch('config.BOT_LANGUAGE', 'de')
    def test_mixed_units_scenario(self):
        """Test scenario with mixed text-based and international units."""
        units = ["pcs.", "g", "pairs", "kg", "pkg.", "ml"]
        localized = [Localizator.localize_unit(u) for u in units]

        expected = ["Stk.", "g", "Paar", "kg", "Pack.", "ml"]
        assert localized == expected


class TestLocalizeUnitPerformance:
    """Test performance considerations."""

    @patch('config.BOT_LANGUAGE', 'de')
    def test_repeated_lookups(self):
        """Test that repeated lookups are efficient (no caching needed)."""
        # Call 1000 times - should be fast due to simple dict lookup
        for _ in range(1000):
            result = Localizator.localize_unit("pcs.")
            assert result == "Stk."

    @patch('config.BOT_LANGUAGE', 'de')
    def test_multiple_units_sequentially(self):
        """Test processing multiple units sequentially."""
        units = ["pcs.", "g", "pairs", "kg", "pkg.", "ml"] * 100
        for unit in units:
            # Should not raise, should be fast
            Localizator.localize_unit(unit)