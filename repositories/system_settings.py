from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from enums.registration_mode import RegistrationMode
from models.system_settings import SystemSettings


class SystemSettingsRepository:
    """
    Repository for system-wide runtime configuration.

    Provides CRUD operations for the key-value SystemSettings store.
    Used for configuration that can change without bot restart.
    """

    @staticmethod
    async def get(key: str, session: AsyncSession | Session) -> str | None:
        """
        Get a setting value by key.

        Args:
            key: Setting key (e.g., "registration_mode")
            session: Database session (async or sync)

        Returns:
            Setting value as string, or None if not found
        """
        stmt = select(SystemSettings).where(SystemSettings.key == key)
        result = await session_execute(stmt, session)
        setting = result.scalar()
        return setting.value if setting else None

    @staticmethod
    async def set(key: str, value: str, session: AsyncSession | Session) -> None:
        """
        Set a setting value (insert or update).

        Args:
            key: Setting key
            value: Setting value (stored as string)
            session: Database session (async or sync)
        """
        # Check if exists
        existing = await SystemSettingsRepository.get(key, session)

        if existing is not None:
            # Update existing
            stmt = update(SystemSettings).where(SystemSettings.key == key).values(value=value)
            await session_execute(stmt, session)
        else:
            # Insert new
            setting = SystemSettings(key=key, value=value)
            session.add(setting)
            await session_flush(session)

    @staticmethod
    async def delete(key: str, session: AsyncSession | Session) -> None:
        """
        Delete a setting by key.

        Args:
            key: Setting key to delete
            session: Database session (async or sync)
        """
        stmt = delete(SystemSettings).where(SystemSettings.key == key)
        await session_execute(stmt, session)

    @staticmethod
    async def get_all(session: AsyncSession | Session) -> dict[str, str]:
        """
        Get all settings as a dictionary.

        Args:
            session: Database session (async or sync)

        Returns:
            Dictionary mapping keys to values
        """
        stmt = select(SystemSettings)
        result = await session_execute(stmt, session)
        settings = result.scalars().all()
        return {setting.key: setting.value for setting in settings}

    @staticmethod
    async def get_registration_mode(session: AsyncSession | Session) -> RegistrationMode:
        """
        Get current registration mode.

        Args:
            session: Database session (async or sync)

        Returns:
            Registration mode enum (defaults to OPEN if not set or invalid)
        """
        mode_str = await SystemSettingsRepository.get("registration_mode", session)

        if not mode_str:
            return RegistrationMode.OPEN

        # Parse string to enum (fallback to OPEN if invalid)
        try:
            return RegistrationMode(mode_str)
        except ValueError:
            return RegistrationMode.OPEN
