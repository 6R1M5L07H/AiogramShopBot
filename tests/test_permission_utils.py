"""
Tests for utils/permission_utils.py

Tests cover:
- Admin user verification (hash-based and legacy)
- Banned user checking with admin exemption
- User existence checks
- Edge cases and error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from utils.permission_utils import (
    is_admin_user,
    is_banned_user,
    get_user_or_none,
    is_user_exists
)
from models.user import UserDTO


class TestIsAdminUser:
    """Test is_admin_user() function."""

    def test_admin_user_with_hashes(self):
        """Test admin verification using hash-based method."""
        # Mock config with hashes
        with patch('utils.permission_utils.config') as mock_config:
            mock_config.ADMIN_ID_HASHES = ['hash1', 'hash2']
            mock_config.ADMIN_ID_LIST = [123456]

            # Mock verify_admin_id to return True (imported inside function)
            with patch('utils.admin_hash_generator.verify_admin_id', return_value=True):
                result = is_admin_user(123456)
                assert result is True

    def test_non_admin_user_with_hashes(self):
        """Test non-admin verification using hash-based method."""
        with patch('utils.permission_utils.config') as mock_config:
            mock_config.ADMIN_ID_HASHES = ['hash1', 'hash2']
            mock_config.ADMIN_ID_LIST = [123456]

            # Mock verify_admin_id to return False (imported inside function)
            with patch('utils.admin_hash_generator.verify_admin_id', return_value=False):
                result = is_admin_user(999999)
                assert result is False

    def test_admin_user_legacy_list(self):
        """Test admin verification using legacy ADMIN_ID_LIST."""
        with patch('utils.permission_utils.config') as mock_config:
            mock_config.ADMIN_ID_HASHES = None  # No hashes - use legacy
            mock_config.ADMIN_ID_LIST = [123456, 789012]

            # Should check ADMIN_ID_LIST
            result = is_admin_user(123456)
            assert result is True

            result = is_admin_user(789012)
            assert result is True

    def test_non_admin_user_legacy_list(self):
        """Test non-admin verification using legacy ADMIN_ID_LIST."""
        with patch('utils.permission_utils.config') as mock_config:
            mock_config.ADMIN_ID_HASHES = None
            mock_config.ADMIN_ID_LIST = [123456, 789012]

            result = is_admin_user(999999)
            assert result is False

    def test_empty_admin_list(self):
        """Test behavior with empty admin list."""
        with patch('utils.permission_utils.config') as mock_config:
            mock_config.ADMIN_ID_HASHES = None
            mock_config.ADMIN_ID_LIST = []

            result = is_admin_user(123456)
            assert result is False


class TestIsBannedUser:
    """Test is_banned_user() function."""

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """Test banned check when user doesn't exist."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock UserService.get to return None (user not found)
        with patch('utils.permission_utils.UserService.get', return_value=None):
            result = await is_banned_user(999999, mock_session)
            assert result is False

    @pytest.mark.asyncio
    async def test_user_not_banned(self):
        """Test banned check when user exists and is not banned."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock user that is not blocked
        mock_user = MagicMock()
        mock_user.is_blocked = False
        mock_user.telegram_id = 123456

        with patch('utils.permission_utils.UserService.get', return_value=mock_user):
            result = await is_banned_user(123456, mock_session)
            assert result is False

    @pytest.mark.asyncio
    async def test_user_banned_regular_user(self):
        """Test banned check when regular user is banned."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock banned user (not admin)
        mock_user = MagicMock()
        mock_user.is_blocked = True
        mock_user.telegram_id = 123456

        with patch('utils.permission_utils.UserService.get', return_value=mock_user):
            with patch('utils.permission_utils.config') as mock_config:
                mock_config.EXEMPT_ADMINS_FROM_BAN = False

                result = await is_banned_user(123456, mock_session)
                assert result is True

    @pytest.mark.asyncio
    async def test_admin_banned_but_exempt(self):
        """Test banned admin with exemption enabled."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock banned admin
        mock_user = MagicMock()
        mock_user.is_blocked = True
        mock_user.telegram_id = 123456

        with patch('utils.permission_utils.UserService.get', return_value=mock_user):
            with patch('utils.permission_utils.config') as mock_config:
                mock_config.EXEMPT_ADMINS_FROM_BAN = True
                mock_config.ADMIN_ID_HASHES = None
                mock_config.ADMIN_ID_LIST = [123456]

                # Admin is banned but exempt
                result = await is_banned_user(123456, mock_session)
                assert result is False

    @pytest.mark.asyncio
    async def test_admin_banned_no_exemption(self):
        """Test banned admin with exemption disabled."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock banned admin
        mock_user = MagicMock()
        mock_user.is_blocked = True
        mock_user.telegram_id = 123456

        with patch('utils.permission_utils.UserService.get', return_value=mock_user):
            with patch('utils.permission_utils.config') as mock_config:
                mock_config.EXEMPT_ADMINS_FROM_BAN = False  # No exemption
                mock_config.ADMIN_ID_HASHES = None
                mock_config.ADMIN_ID_LIST = [123456]

                # Admin is banned and not exempt
                result = await is_banned_user(123456, mock_session)
                assert result is True

    @pytest.mark.asyncio
    async def test_banned_check_with_hashes(self):
        """Test banned admin check uses hash-based verification."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock banned admin
        mock_user = MagicMock()
        mock_user.is_blocked = True
        mock_user.telegram_id = 123456

        with patch('utils.permission_utils.UserService.get', return_value=mock_user):
            with patch('utils.permission_utils.config') as mock_config:
                mock_config.EXEMPT_ADMINS_FROM_BAN = True
                mock_config.ADMIN_ID_HASHES = ['hash1', 'hash2']
                mock_config.ADMIN_ID_LIST = [123456]

                # Mock verify_admin_id to return True (imported inside function)
                with patch('utils.admin_hash_generator.verify_admin_id', return_value=True):
                    result = await is_banned_user(123456, mock_session)
                    assert result is False  # Admin exempt from ban


class TestGetUserOrNone:
    """Test get_user_or_none() function."""

    @pytest.mark.asyncio
    async def test_get_existing_user(self):
        """Test getting an existing user."""
        mock_session = AsyncMock(spec=AsyncSession)

        mock_user = MagicMock()
        mock_user.telegram_id = 123456
        mock_user.username = "testuser"

        with patch('utils.permission_utils.UserService.get', return_value=mock_user):
            result = await get_user_or_none(123456, mock_session)
            assert result is not None
            assert result.telegram_id == 123456
            assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self):
        """Test getting a non-existent user returns None."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch('utils.permission_utils.UserService.get', return_value=None):
            result = await get_user_or_none(999999, mock_session)
            assert result is None


class TestIsUserExists:
    """Test is_user_exists() function."""

    @pytest.mark.asyncio
    async def test_user_exists(self):
        """Test checking if user exists (positive case)."""
        mock_session = AsyncMock(spec=AsyncSession)

        mock_user = MagicMock()
        mock_user.telegram_id = 123456

        with patch('utils.permission_utils.UserService.get', return_value=mock_user):
            result = await is_user_exists(123456, mock_session)
            assert result is True

    @pytest.mark.asyncio
    async def test_user_not_exists(self):
        """Test checking if user exists (negative case)."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch('utils.permission_utils.UserService.get', return_value=None):
            result = await is_user_exists(999999, mock_session)
            assert result is False


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    @pytest.mark.asyncio
    async def test_banned_user_workflow(self):
        """Test complete banned user workflow."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Setup: Banned regular user
        mock_user = MagicMock()
        mock_user.is_blocked = True
        mock_user.telegram_id = 123456

        with patch('utils.permission_utils.UserService.get', return_value=mock_user):
            with patch('utils.permission_utils.config') as mock_config:
                mock_config.EXEMPT_ADMINS_FROM_BAN = True
                mock_config.ADMIN_ID_HASHES = None
                mock_config.ADMIN_ID_LIST = [999999]  # Different admin

                # 1. Check if user exists
                exists = await is_user_exists(123456, mock_session)
                assert exists is True

                # 2. Check if user is admin
                is_admin = is_admin_user(123456)
                assert is_admin is False

                # 3. Check if user is banned
                is_banned = await is_banned_user(123456, mock_session)
                assert is_banned is True  # Regular banned user

    @pytest.mark.asyncio
    async def test_admin_workflow(self):
        """Test complete admin workflow."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Setup: Admin user
        mock_user = MagicMock()
        mock_user.is_blocked = False
        mock_user.telegram_id = 123456

        with patch('utils.permission_utils.UserService.get', return_value=mock_user):
            with patch('utils.permission_utils.config') as mock_config:
                mock_config.EXEMPT_ADMINS_FROM_BAN = True
                mock_config.ADMIN_ID_HASHES = None
                mock_config.ADMIN_ID_LIST = [123456]

                # 1. Check if user is admin
                is_admin = is_admin_user(123456)
                assert is_admin is True

                # 2. Check if admin is banned
                is_banned = await is_banned_user(123456, mock_session)
                assert is_banned is False

    @pytest.mark.asyncio
    async def test_new_user_workflow(self):
        """Test workflow for new user that doesn't exist yet."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch('utils.permission_utils.UserService.get', return_value=None):
            # 1. Check if user exists
            exists = await is_user_exists(999999, mock_session)
            assert exists is False

            # 2. Get user or none
            user = await get_user_or_none(999999, mock_session)
            assert user is None

            # 3. Check if banned (should return False for non-existent user)
            is_banned = await is_banned_user(999999, mock_session)
            assert is_banned is False
