"""
Tests for utils/localizator.py

Tests cover:
- Lang parameter functionality (request-scoped language)
- Backward compatibility (fallback to config.BOT_LANGUAGE)
- Different language codes (de, en)
- All three methods (get_text, get_currency_symbol, get_currency_text)
- Thread-safety (concurrent calls with different lang values)
- Race condition prevention (no global state mutation)
"""

import pytest
from unittest.mock import patch
import threading
import time

from utils.localizator import Localizator
from enums.bot_entity import BotEntity
from enums.currency import Currency


class TestLocalizatorLangParameter:
    """Test Localizator methods with optional lang parameter."""

    def test_get_text_with_lang_de(self):
        """Test get_text() with explicit lang='de'."""
        result = Localizator.get_text(BotEntity.USER, "all_categories", lang="de")
        assert result == "🗂️ Alle Kategorien"

    def test_get_text_with_lang_en(self):
        """Test get_text() with explicit lang='en'."""
        result = Localizator.get_text(BotEntity.USER, "all_categories", lang="en")
        assert result == "🗂️ All categories"

    def test_get_text_admin_entity(self):
        """Test get_text() with ADMIN entity."""
        result = Localizator.get_text(BotEntity.ADMIN, "menu", lang="de")
        assert result == "🔑 Admin-Menü"

        result = Localizator.get_text(BotEntity.ADMIN, "menu", lang="en")
        assert result == "🔑 Admin Menu"

    def test_get_text_common_entity(self):
        """Test get_text() with COMMON entity."""
        result = Localizator.get_text(BotEntity.COMMON, "back_button", lang="de")
        assert result == "⬅️ Zurück"

        result = Localizator.get_text(BotEntity.COMMON, "back_button", lang="en")
        assert result == "⬅️ Back"

    def test_get_currency_symbol_with_lang(self):
        """Test get_currency_symbol() with explicit lang parameter."""
        # Mock config.CURRENCY to EUR
        with patch('utils.localizator.config') as mock_config:
            mock_config.CURRENCY = Currency.EUR

            result = Localizator.get_currency_symbol(lang="de")
            assert result == "€"

            result = Localizator.get_currency_symbol(lang="en")
            assert result == "€"

    def test_get_currency_text_with_lang(self):
        """Test get_currency_text() with explicit lang parameter."""
        # Mock config.CURRENCY to EUR
        with patch('utils.localizator.config') as mock_config:
            mock_config.CURRENCY = Currency.EUR

            result = Localizator.get_currency_text(lang="de")
            assert result == "EUR"

            result = Localizator.get_currency_text(lang="en")
            assert result == "EUR"


class TestLocalizatorBackwardCompatibility:
    """Test backward compatibility when lang parameter is not provided."""

    def test_get_text_without_lang_falls_back_to_config(self):
        """Test get_text() without lang uses config.BOT_LANGUAGE (backward compatible)."""
        # Mock config.BOT_LANGUAGE to "de"
        with patch('utils.localizator.config') as mock_config:
            mock_config.BOT_LANGUAGE = "de"

            result = Localizator.get_text(BotEntity.USER, "all_categories")
            assert result == "🗂️ Alle Kategorien"

        # Mock config.BOT_LANGUAGE to "en"
        with patch('utils.localizator.config') as mock_config:
            mock_config.BOT_LANGUAGE = "en"

            result = Localizator.get_text(BotEntity.USER, "all_categories")
            assert result == "🗂️ All categories"

    def test_get_currency_symbol_without_lang_falls_back_to_config(self):
        """Test get_currency_symbol() without lang uses config.BOT_LANGUAGE."""
        with patch('utils.localizator.config') as mock_config:
            mock_config.CURRENCY = Currency.EUR
            mock_config.BOT_LANGUAGE = "de"

            result = Localizator.get_currency_symbol()
            assert result == "€"

    def test_get_currency_text_without_lang_falls_back_to_config(self):
        """Test get_currency_text() without lang uses config.BOT_LANGUAGE."""
        with patch('utils.localizator.config') as mock_config:
            mock_config.CURRENCY = Currency.EUR
            mock_config.BOT_LANGUAGE = "de"

            result = Localizator.get_currency_text()
            assert result == "EUR"


class TestLocalizatorThreadSafety:
    """Test thread-safety and race condition prevention."""

    def test_concurrent_calls_with_different_langs(self):
        """
        Test concurrent calls with different lang values don't interfere.

        This verifies the fix for the race condition where concurrent FastAPI
        requests mutated config.BOT_LANGUAGE globally.
        """
        results = []
        errors = []

        def fetch_german():
            try:
                for _ in range(10):
                    result = Localizator.get_text(BotEntity.USER, "all_categories", lang="de")
                    results.append(("de", result))
                    time.sleep(0.001)  # Small delay to increase race condition likelihood
            except Exception as e:
                errors.append(e)

        def fetch_english():
            try:
                for _ in range(10):
                    result = Localizator.get_text(BotEntity.USER, "all_categories", lang="en")
                    results.append(("en", result))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Start threads
        thread1 = threading.Thread(target=fetch_german)
        thread2 = threading.Thread(target=fetch_english)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred during concurrent execution: {errors}"

        # Verify all results are correct (no cross-contamination)
        for lang, result in results:
            if lang == "de":
                assert result == "🗂️ Alle Kategorien", \
                    f"German result contaminated: expected '🗂️ Alle Kategorien', got '{result}'"
            elif lang == "en":
                assert result == "🗂️ All categories", \
                    f"English result contaminated: expected '🗂️ All categories', got '{result}'"

    def test_no_global_state_mutation(self):
        """
        Test that calling get_text with lang parameter does NOT mutate config.BOT_LANGUAGE.

        This verifies the fix where config.BOT_LANGUAGE was mutated in mini_app_router.
        """
        with patch('utils.localizator.config') as mock_config:
            mock_config.BOT_LANGUAGE = "de"

            # Call get_text with lang='en'
            result = Localizator.get_text(BotEntity.USER, "all_categories", lang="en")
            assert result == "🗂️ All categories"

            # Verify config.BOT_LANGUAGE was NOT mutated (still 'de')
            assert mock_config.BOT_LANGUAGE == "de", \
                "config.BOT_LANGUAGE was mutated! This is a race condition vulnerability."

    def test_request_scoped_context_isolation(self):
        """
        Test that each request has its own language context (request-scoped).

        Simulates concurrent FastAPI requests with different lang query parameters.
        """
        # Simulate Request 1 (German user)
        request1_result = Localizator.get_text(BotEntity.USER, "all_categories", lang="de")

        # Simulate Request 2 (English user) - should not affect Request 1
        request2_result = Localizator.get_text(BotEntity.USER, "all_categories", lang="en")

        # Simulate Request 1 reading again - should still be German
        request1_result_again = Localizator.get_text(BotEntity.USER, "all_categories", lang="de")

        # Verify each request got correct language
        assert request1_result == "🗂️ Alle Kategorien"
        assert request2_result == "🗂️ All categories"
        assert request1_result_again == "🗂️ Alle Kategorien"


class TestLocalizatorEdgeCases:
    """Test edge cases and error handling."""

    def test_get_text_with_none_lang_uses_config(self):
        """Test get_text() with lang=None explicitly uses config.BOT_LANGUAGE."""
        with patch('utils.localizator.config') as mock_config:
            mock_config.BOT_LANGUAGE = "en"

            result = Localizator.get_text(BotEntity.USER, "all_categories", lang=None)
            assert result == "🗂️ All categories"

    def test_get_text_with_invalid_lang_raises_error(self):
        """Test get_text() with invalid language code raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            Localizator.get_text(BotEntity.USER, "all_categories", lang="invalid")

    def test_get_text_with_invalid_key_raises_error(self):
        """Test get_text() with invalid key raises KeyError."""
        with pytest.raises(KeyError):
            Localizator.get_text(BotEntity.USER, "invalid_key_that_does_not_exist", lang="de")