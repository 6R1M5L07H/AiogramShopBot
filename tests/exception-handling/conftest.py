"""
Pytest fixtures for exception handling tests.
Provides mocked database sessions and common test objects.
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

# Set required environment variables before importing app modules
# These are required for config.py to load properly
os.environ.setdefault('RUNTIME_ENVIRONMENT', 'TEST')
os.environ.setdefault('TOKEN', 'test_token_12345')
os.environ.setdefault('ADMIN_ID_LIST', '123456')
os.environ.setdefault('SUPPORT_LINK', 'https://t.me/test')
os.environ.setdefault('WEBHOOK_PATH', '/')
os.environ.setdefault('WEBAPP_HOST', 'localhost')
os.environ.setdefault('WEBAPP_PORT', '5001')
os.environ.setdefault('WEBHOOK_SECRET_TOKEN', 'test_secret')
os.environ.setdefault('DB_NAME', ':memory:')
os.environ.setdefault('DB_ENCRYPTION', 'false')
os.environ.setdefault('DB_PASS', '')
os.environ.setdefault('REDIS_HOST', 'localhost')
os.environ.setdefault('REDIS_PASSWORD', '')
os.environ.setdefault('PAGE_ENTRIES', '8')
os.environ.setdefault('BOT_LANGUAGE', 'en')
os.environ.setdefault('MULTIBOT', 'false')
os.environ.setdefault('CURRENCY', 'EUR')
os.environ.setdefault('KRYPTO_EXPRESS_API_KEY', 'test_key')
os.environ.setdefault('KRYPTO_EXPRESS_API_URL', 'https://test.example.com')
os.environ.setdefault('KRYPTO_EXPRESS_API_SECRET', 'test_api_secret')
os.environ.setdefault('ORDER_TIMEOUT_MINUTES', '30')
os.environ.setdefault('ORDER_CANCEL_GRACE_PERIOD_MINUTES', '5')
os.environ.setdefault('PAYMENT_CHECK_INTERVAL_SECONDS', '60')
os.environ.setdefault('PAYMENT_TOLERANCE_OVERPAYMENT_PERCENT', '0.1')
os.environ.setdefault('PAYMENT_UNDERPAYMENT_RETRY_ENABLED', 'true')
os.environ.setdefault('PAYMENT_UNDERPAYMENT_RETRY_TIMEOUT_MINUTES', '30')
os.environ.setdefault('PAYMENT_UNDERPAYMENT_PENALTY_PERCENT', '5')
os.environ.setdefault('PAYMENT_LATE_PENALTY_PERCENT', '5')
os.environ.setdefault('DATA_RETENTION_DAYS', '30')
os.environ.setdefault('REFERRAL_DATA_RETENTION_DAYS', '365')
os.environ.setdefault('ENCRYPTION_SECRET', 'a' * 64)  # 64 hex characters
os.environ.setdefault('MAX_STRIKES_BEFORE_BAN', '3')
os.environ.setdefault('EXEMPT_ADMINS_FROM_BAN', 'true')
os.environ.setdefault('UNBAN_TOP_UP_AMOUNT', '50.0')
os.environ.setdefault('DB_BACKUP_ENABLED', 'false')
os.environ.setdefault('DB_BACKUP_INTERVAL_HOURS', '6')
os.environ.setdefault('DB_BACKUP_RETENTION_DAYS', '7')
os.environ.setdefault('DB_BACKUP_PATH', './backups')
os.environ.setdefault('WEBHOOK_SECURITY_HEADERS_ENABLED', 'false')
os.environ.setdefault('WEBHOOK_CSP_ENABLED', 'false')
os.environ.setdefault('WEBHOOK_HSTS_ENABLED', 'false')
os.environ.setdefault('WEBHOOK_CORS_ALLOWED_ORIGINS', '')

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture
def mock_session():
    """Mock synchronous database session."""
    session = MagicMock(spec=Session)
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def mock_async_session():
    """Mock asynchronous database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def mock_order():
    """Mock order object."""
    order = MagicMock()
    order.id = 1
    order.user_id = 123
    order.invoice_number = "INV-001"
    order.status = "PAID_AWAITING_SHIPMENT"
    order.total_price = 100.0
    order.shipping_cost = 5.0
    return order


@pytest.fixture
def mock_user():
    """Mock user object."""
    user = MagicMock()
    user.id = 123
    user.telegram_id = 456789
    user.username = "testuser"
    user.is_banned = False
    user.wallet = 50.0
    return user


@pytest.fixture
def mock_item():
    """Mock item (subcategory) object."""
    item = MagicMock()
    item.id = 1
    item.name = "Test Item"
    item.price = 10.0
    item.quantity = 5
    item.is_physical = False
    return item


@pytest.fixture
def mock_callback_query():
    """Mock Telegram CallbackQuery."""
    callback = AsyncMock()
    callback.data = "test_callback_data"
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = 456789
    return callback


@pytest.fixture
def mock_message():
    """Mock Telegram Message."""
    message = AsyncMock()
    message.text = "Test message"
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    message.from_user = MagicMock()
    message.from_user.id = 456789
    return message


@pytest.fixture
def mock_fsm_context():
    """Mock FSM context."""
    context = AsyncMock()
    context.get_data = AsyncMock(return_value={})
    context.update_data = AsyncMock()
    context.set_state = AsyncMock()
    context.clear = AsyncMock()
    return context
