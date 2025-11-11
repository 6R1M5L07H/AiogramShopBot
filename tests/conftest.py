"""
Pytest configuration and fixtures for tests.

This file is automatically loaded by pytest and provides shared fixtures
and configuration for all tests.
"""

import sys
import os
from unittest.mock import Mock, MagicMock
import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Add parent directory to Python path so tests can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock config module completely before any imports
config_mock = MagicMock()
config_mock.PAYMENT_TOLERANCE_OVERPAYMENT_PERCENT = 0.1
config_mock.PAYMENT_UNDERPAYMENT_RETRY_ENABLED = True
config_mock.PAYMENT_UNDERPAYMENT_RETRY_TIMEOUT_MINUTES = 30
config_mock.PAYMENT_UNDERPAYMENT_PENALTY_PERCENT = 5.0
config_mock.PAYMENT_LATE_PENALTY_PERCENT = 5.0
config_mock.DATA_RETENTION_DAYS = 30
config_mock.REFERRAL_DATA_RETENTION_DAYS = 365
config_mock.DB_URL = "sqlite+aiosqlite:///:memory:"  # In-memory test database
config_mock.BOT_LANGUAGE = "en"  # For Localizator
config_mock.ADMIN_ID_LIST = [123456789]  # Test admin ID
config_mock.SHIPPING_ADDRESS_SECRET = "test_shipping_secret_1234567890abcdef1234567890abcdef"  # Test secret for shipping
config_mock.SHIPPING_COUNTRY = "DE"  # Test shipping country
config_mock.WEBHOOK_PATH = "/webhook/"  # Test webhook path
config_mock.MAX_STRIKES_BEFORE_BAN = 3  # Test max strikes
config_mock.TELEGRAM_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"  # Test bot token
config_mock.TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"  # Test bot token (alternative name)

# Mock Currency enum that mimics Currency enum behavior
from enum import Enum
class MockCurrency(str, Enum):
    EUR = "EUR"
    USD = "USD"

    @property
    def value(self):
        return str.__str__(self)

config_mock.CURRENCY = MockCurrency.EUR

sys.modules['config'] = config_mock

# Mock config validator to prevent validation failures during tests
validator_mock = MagicMock()
validator_mock.validate_or_exit = MagicMock(return_value=None)
validator_mock.validate_startup_config = MagicMock(return_value=None)
validator_mock.ConfigValidationError = Exception
sys.modules['utils.config_validator'] = validator_mock


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine (in-memory SQLite)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    # Import and create all tables
    from db import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


# ============================================================================
# Redis Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def redis_client():
    """Create fake Redis client for testing (no real Redis server needed)."""
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


# ============================================================================
# Aiogram Bot Fixtures
# ============================================================================

@pytest.fixture
def bot():
    """Create mocked bot instance for testing."""
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    # Use fake token for testing
    return Bot(
        token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )


@pytest.fixture
def dispatcher(redis_client):
    """Create dispatcher with fake Redis storage."""
    from aiogram import Dispatcher
    from aiogram.fsm.storage.redis import RedisStorage

    storage = RedisStorage(redis_client)
    return Dispatcher(storage=storage)
