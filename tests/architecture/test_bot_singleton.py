"""
Unit Tests for Bot Singleton Pattern

Tests that bot_instance module follows singleton pattern and that
NotificationService no longer creates Bot instances.

NOTE: Testing actual Bot instantiation requires valid Telegram token.
These tests focus on verifying the architectural pattern is correctly implemented.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestBotSingletonPattern:
    """Test Bot Singleton Pattern Implementation"""

    def test_bot_instance_module_exists(self):
        """Test bot_instance module exists and exports required functions"""
        import bot_instance
        assert hasattr(bot_instance, 'get_bot')
        assert hasattr(bot_instance, 'close_bot')
        assert callable(bot_instance.get_bot)
        assert callable(bot_instance.close_bot)

    def test_singleton_uses_global_variable(self):
        """Test singleton pattern uses global _bot_instance variable"""
        import bot_instance
        import inspect

        source = inspect.getsource(bot_instance)

        # Should have _bot_instance global
        assert "_bot_instance = None" in source or "_bot_instance=None" in source

        # get_bot should use global keyword
        assert "global _bot_instance" in source

    def test_get_bot_creates_bot_with_html_mode(self):
        """Test get_bot() creates Bot with HTML parse mode"""
        import bot_instance
        import inspect

        source = inspect.getsource(bot_instance.get_bot)

        # Should create Bot with HTML parse mode
        assert "ParseMode.HTML" in source
        assert "Bot(" in source

    def test_close_bot_closes_session(self):
        """Test close_bot() closes bot session"""
        import bot_instance
        import inspect

        source = inspect.getsource(bot_instance.close_bot)

        # Should close session
        assert "session.close()" in source or "await" in source


class TestNotificationServiceNoBotCreation:
    """Test NotificationService no longer creates Bot instances"""

    def test_notification_service_imports_get_bot(self):
        """Test NotificationService imports get_bot instead of Bot"""
        import services.notification
        import inspect

        # Check imports
        source = inspect.getsource(services.notification)

        # Should import get_bot
        assert "from bot_instance import get_bot" in source

        # Should NOT import Bot from aiogram directly anymore
        # (may still import types from aiogram, but not Bot)
        assert "from aiogram import Bot" not in source

    def test_notification_service_no_bot_instantiation(self):
        """Test NotificationService doesn't create Bot(token=...) instances"""
        import services.notification
        import inspect

        source = inspect.getsource(services.notification)

        # Should NOT contain Bot(token=...)
        assert "Bot(token=" not in source

    def test_notification_service_no_session_close(self):
        """Test NotificationService doesn't call bot.session.close()"""
        import services.notification
        import inspect

        source = inspect.getsource(services.notification)

        # Should NOT contain session.close()
        assert "session.close()" not in source


if __name__ == "__main__":
    """
    Run tests with:
        pytest tests/architecture/test_bot_singleton.py -v
    """
    pytest.main([__file__, "-v"])
