"""
Centralized permission utilities for user authorization.

This module provides centralized functions for checking user permissions
to eliminate duplicate admin verification logic across the codebase.

Security:
- Uses hash-based admin verification when ADMIN_ID_HASHES is configured
- Falls back to ADMIN_ID_LIST for backward compatibility
- Prevents admin identification if environment variables are compromised
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from models.user import UserDTO
from services.user import UserService


def is_admin_user(telegram_id: int) -> bool:
    """
    Check if a user is an admin using secure hash-based verification.

    This function centralizes admin verification logic to eliminate
    duplicate code patterns across the codebase.

    Security:
    - Prefers hash-based verification (ADMIN_ID_HASHES) for security
    - Falls back to plaintext list (ADMIN_ID_LIST) for compatibility

    Args:
        telegram_id: The Telegram user ID to check

    Returns:
        True if user is an admin, False otherwise

    Example:
        >>> is_admin_user(123456789)
        True
        >>> is_admin_user(999999999)
        False
    """
    # Hash-based verification (secure, preferred)
    if config.ADMIN_ID_HASHES:
        from utils.admin_hash_generator import verify_admin_id
        return verify_admin_id(telegram_id, config.ADMIN_ID_HASHES)

    # Plaintext list fallback (legacy, deprecated)
    return telegram_id in config.ADMIN_ID_LIST


async def is_banned_user(telegram_id: int, session: AsyncSession | Session) -> bool:
    """
    Check if a user is banned (blocked).

    This function centralizes ban checking logic and respects admin exemption
    settings when EXEMPT_ADMINS_FROM_BAN is enabled.

    Args:
        telegram_id: The Telegram user ID to check
        session: Database session (async or sync)

    Returns:
        True if user is banned and not exempt, False otherwise

    Example:
        >>> await is_banned_user(123456789, session)
        False  # User not banned
        >>> await is_banned_user(999999999, session)
        True   # User banned
    """
    # Get user from database
    user = await UserService.get(UserDTO(telegram_id=telegram_id), session)

    if user is None:
        # User doesn't exist - not banned, but probably will fail other checks
        return False

    # User not blocked - not banned
    if not user.is_blocked:
        return False

    # User is blocked - check admin exemption
    if config.EXEMPT_ADMINS_FROM_BAN:
        # Check if user is admin (admins are exempt from bans)
        if is_admin_user(telegram_id):
            return False

    # User is banned and not exempt
    return True


async def get_user_or_none(telegram_id: int, session: AsyncSession | Session) -> Optional[UserDTO]:
    """
    Get user from database or return None if not found.

    Convenience function for getting user data with None-safe returns.

    Args:
        telegram_id: The Telegram user ID to fetch
        session: Database session (async or sync)

    Returns:
        UserDTO if user exists, None otherwise

    Example:
        >>> user = await get_user_or_none(123456789, session)
        >>> if user:
        ...     print(f"User: {user.username}")
    """
    return await UserService.get(UserDTO(telegram_id=telegram_id), session)


async def is_user_exists(telegram_id: int, session: AsyncSession | Session) -> bool:
    """
    Check if a user exists in the database.

    Args:
        telegram_id: The Telegram user ID to check
        session: Database session (async or sync)

    Returns:
        True if user exists, False otherwise

    Example:
        >>> await is_user_exists(123456789, session)
        True
    """
    user = await UserService.get(UserDTO(telegram_id=telegram_id), session)
    return user is not None
