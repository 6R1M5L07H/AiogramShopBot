"""
Pytest configuration and fixtures for comprehensive test suite.

This module provides shared fixtures and configuration for testing the
invoice-stock-management feature with security fixes.
"""

import pytest
import asyncio
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, AsyncGenerator
from unittest.mock import Mock, patch, AsyncMock

import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import models and services for testing
from models.base import Base
from models.user import User, UserDTO
from models.order import Order, OrderDTO, OrderStatus
from models.cart import Cart, CartDTO
from models.cartItem import CartItem, CartItemDTO
from models.item import Item, ItemDTO
from models.category import Category, CategoryDTO
from models.subcategory import Subcategory, SubcategoryDTO
from models.orderItem import OrderItem
from models.reservedStock import ReservedStock
from db import get_db_session
import config


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_engine():
    """Create a test database engine with in-memory SQLite."""
    # Create temporary database file for testing
    test_db_fd, test_db_path = tempfile.mkstemp(suffix='.db')
    os.close(test_db_fd)
    
    database_url = f"sqlite+aiosqlite:///{test_db_path}"
    engine = create_async_engine(database_url, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()
    try:
        os.unlink(test_db_path)
    except OSError:
        pass


@pytest.fixture
async def db_session(test_db_engine):
    """Create a test database session with transaction rollback."""
    async_session_maker = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        # Start a transaction
        async with session.begin():
            yield session
            # Transaction will be rolled back automatically


@pytest.fixture
async def test_user(db_session) -> UserDTO:
    """Create a test user for order testing."""
    # Test Case: Create standard test user with initialized timeout count
    user = User(
        telegram_id=12345,
        telegram_username="test_user",
        language="en",
        timeout_count=0,
        created_at=datetime.now()
    )
    db_session.add(user)
    await db_session.flush()
    
    return UserDTO(
        id=user.id,
        telegram_id=user.telegram_id,
        telegram_username=user.telegram_username,
        language=user.language,
        timeout_count=user.timeout_count
    )


@pytest.fixture
async def test_admin_user(db_session) -> UserDTO:
    """Create a test admin user."""
    # Test Case: Create admin user for privilege testing
    admin = User(
        telegram_id=67890,
        telegram_username="test_admin",
        language="en",
        timeout_count=0,
        is_admin=True,
        created_at=datetime.now()
    )
    db_session.add(admin)
    await db_session.flush()
    
    return UserDTO(
        id=admin.id,
        telegram_id=admin.telegram_id,
        telegram_username=admin.telegram_username,
        language=admin.language,
        timeout_count=admin.timeout_count
    )


@pytest.fixture
async def test_category(db_session) -> CategoryDTO:
    """Create a test category."""
    # Test Case: Create category for item organization testing
    category = Category(
        name="Test Category",
        created_at=datetime.now()
    )
    db_session.add(category)
    await db_session.flush()
    
    return CategoryDTO(
        id=category.id,
        name=category.name
    )


@pytest.fixture
async def test_subcategory(db_session, test_category) -> SubcategoryDTO:
    """Create a test subcategory."""
    # Test Case: Create subcategory for item organization testing
    subcategory = Subcategory(
        name="Test Subcategory",
        category_id=test_category.id,
        created_at=datetime.now()
    )
    db_session.add(subcategory)
    await db_session.flush()
    
    return SubcategoryDTO(
        id=subcategory.id,
        name=subcategory.name,
        category_id=subcategory.category_id
    )


@pytest.fixture
async def test_items(db_session, test_category, test_subcategory) -> list[ItemDTO]:
    """Create test items for stock management testing."""
    # Test Case: Create multiple items for stock reservation and race condition testing
    items = []
    for i in range(5):
        item = Item(
            name=f"Test Item {i+1}",
            price=10.0 + i,
            category_id=test_category.id,
            subcategory_id=test_subcategory.id,
            is_sold=False,
            created_at=datetime.now()
        )
        db_session.add(item)
        items.append(item)
    
    await db_session.flush()
    
    return [
        ItemDTO(
            id=item.id,
            name=item.name,
            price=item.price,
            category_id=item.category_id,
            subcategory_id=item.subcategory_id,
            is_sold=item.is_sold
        )
        for item in items
    ]


@pytest.fixture
async def test_cart_items(db_session, test_user, test_category, test_subcategory) -> list[CartItemDTO]:
    """Create test cart items."""
    # Test Case: Create cart items for order creation testing
    cart_items = []
    
    # Add 2 items to cart
    for i in range(2):
        cart_item = Cart(
            user_id=test_user.id,
            category_id=test_category.id,
            subcategory_id=test_subcategory.id,
            quantity=1,
            price=15.0 + i,
            created_at=datetime.now()
        )
        db_session.add(cart_item)
        cart_items.append(cart_item)
    
    await db_session.flush()
    
    return [
        CartItemDTO(
            id=cart_item.id,
            user_id=cart_item.user_id,
            category_id=cart_item.category_id,
            subcategory_id=cart_item.subcategory_id,
            quantity=cart_item.quantity,
            price=cart_item.price
        )
        for cart_item in cart_items
    ]


@pytest.fixture
async def test_order(db_session, test_user) -> OrderDTO:
    """Create a test order."""
    # Test Case: Create standard order for status transition testing
    expires_at = datetime.now() + timedelta(minutes=30)
    order = Order(
        user_id=test_user.id,
        status=OrderStatus.CREATED.value,
        total_amount=25.0,
        currency="BTC",
        payment_address="test_address_12345",
        expires_at=expires_at,
        created_at=datetime.now()
    )
    db_session.add(order)
    await db_session.flush()
    
    return OrderDTO(
        id=order.id,
        user_id=order.user_id,
        status=order.status,
        total_amount=order.total_amount,
        currency=order.currency,
        payment_address=order.payment_address,
        expires_at=order.expires_at,
        created_at=order.created_at
    )


@pytest.fixture
def mock_crypto_generator():
    """Mock crypto address generator for testing."""
    # Test Case: Mock crypto address generation to avoid external dependencies
    with patch('utils.CryptoAddressGenerator.CryptoAddressGenerator') as mock:
        mock_instance = Mock()
        mock_instance.generate_one_time_address.return_value = {
            'address': 'test_crypto_address_12345',
            'private_key': 'test_private_key_12345'
        }
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_encryption_service():
    """Mock encryption service for testing."""
    # Test Case: Mock encryption to test security functionality without real keys
    with patch('services.encryption.EncryptionService') as mock:
        mock.encrypt_private_key.return_value = (
            'encrypted_key_base64',
            'salt_base64'
        )
        mock.decrypt_private_key.return_value = 'decrypted_private_key_12345'
        mock.verify_encryption_setup.return_value = True
        yield mock


@pytest.fixture
def mock_notification_service():
    """Mock notification service to prevent actual notifications during testing."""
    # Test Case: Mock notifications to avoid side effects during testing
    with patch('services.notification.NotificationService') as mock:
        mock.order_created = AsyncMock()
        mock.payment_received = AsyncMock()
        mock.order_shipped = AsyncMock()
        mock.order_expired = AsyncMock()
        mock.order_cancelled = AsyncMock()
        yield mock


@pytest.fixture
async def expired_order(db_session, test_user) -> OrderDTO:
    """Create an expired test order."""
    # Test Case: Create expired order for expiration workflow testing
    expires_at = datetime.now() - timedelta(minutes=10)  # Already expired
    order = Order(
        user_id=test_user.id,
        status=OrderStatus.CREATED.value,
        total_amount=30.0,
        currency="ETH",
        payment_address="expired_address_12345",
        expires_at=expires_at,
        created_at=datetime.now() - timedelta(minutes=40)
    )
    db_session.add(order)
    await db_session.flush()
    
    return OrderDTO(
        id=order.id,
        user_id=order.user_id,
        status=order.status,
        total_amount=order.total_amount,
        currency=order.currency,
        payment_address=order.payment_address,
        expires_at=order.expires_at,
        created_at=order.created_at
    )


@pytest.fixture
async def paid_order(db_session, test_user) -> OrderDTO:
    """Create a paid test order for shipping tests."""
    # Test Case: Create paid order for shipment workflow testing
    order = Order(
        user_id=test_user.id,
        status=OrderStatus.PAID.value,
        total_amount=50.0,
        currency="LTC",
        payment_address="paid_address_12345",
        expires_at=datetime.now() + timedelta(minutes=30),
        created_at=datetime.now() - timedelta(minutes=5),
        paid_at=datetime.now() - timedelta(minutes=2)
    )
    db_session.add(order)
    await db_session.flush()
    
    return OrderDTO(
        id=order.id,
        user_id=order.user_id,
        status=order.status,
        total_amount=order.total_amount,
        currency=order.currency,
        payment_address=order.payment_address,
        expires_at=order.expires_at,
        created_at=order.created_at,
        paid_at=order.paid_at
    )


@pytest.fixture
def test_webhook_payload():
    """Create test webhook payload for payment processing."""
    # Test Case: Standard webhook payload for payment confirmation testing
    return {
        'address': 'test_crypto_address_12345',
        'amount': 25.0,
        'currency': 'BTC',
        'tx_hash': 'test_transaction_hash_12345',
        'confirmations': 6
    }


@pytest.fixture
def test_config():
    """Override configuration for testing."""
    # Test Case: Configure test environment settings
    original_values = {}
    test_values = {
        'ORDER_TIMEOUT_MINUTES': 30,
        'WEBHOOK_SECRET': 'test_webhook_secret_key',
        'ENCRYPTION_MASTER_KEY': 'dGVzdF9tYXN0ZXJfa2V5XzEyMzQ1Njc4OTA='  # base64 encoded test key
    }
    
    # Store original values and set test values
    for key, value in test_values.items():
        if hasattr(config, key):
            original_values[key] = getattr(config, key)
        setattr(config, key, value)
    
    yield test_values
    
    # Restore original values
    for key, value in original_values.items():
        setattr(config, key, value)


@pytest.fixture
async def concurrent_test_users(db_session) -> list[UserDTO]:
    """Create multiple test users for race condition testing."""
    # Test Case: Create multiple users for concurrent operation testing
    users = []
    for i in range(5):
        user = User(
            telegram_id=20000 + i,
            telegram_username=f"concurrent_user_{i}",
            language="en",
            timeout_count=0,
            created_at=datetime.now()
        )
        db_session.add(user)
        users.append(user)
    
    await db_session.flush()
    
    return [
        UserDTO(
            id=user.id,
            telegram_id=user.telegram_id,
            telegram_username=user.telegram_username,
            language=user.language,
            timeout_count=user.timeout_count
        )
        for user in users
    ]


# Performance testing utilities
@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during testing."""
    # Test Case: Performance monitoring for optimization testing
    import time
    import psutil
    import threading
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.memory_usage = []
            self.cpu_usage = []
            self.monitoring = False
            self.monitor_thread = None
        
        def start_monitoring(self):
            self.start_time = time.time()
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_resources)
            self.monitor_thread.start()
        
        def stop_monitoring(self):
            self.end_time = time.time()
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join()
        
        def _monitor_resources(self):
            while self.monitoring:
                self.memory_usage.append(psutil.virtual_memory().percent)
                self.cpu_usage.append(psutil.cpu_percent(interval=0.1))
                time.sleep(0.1)
        
        def get_metrics(self):
            duration = self.end_time - self.start_time if self.end_time else 0
            return {
                'duration': duration,
                'avg_memory_usage': sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0,
                'max_memory_usage': max(self.memory_usage) if self.memory_usage else 0,
                'avg_cpu_usage': sum(self.cpu_usage) / len(self.cpu_usage) if self.cpu_usage else 0,
                'max_cpu_usage': max(self.cpu_usage) if self.cpu_usage else 0
            }
    
    return PerformanceMonitor()


# Error simulation fixtures
@pytest.fixture
def database_error_simulator():
    """Simulate database errors for error handling testing."""
    # Test Case: Database error simulation for resilience testing
    from sqlalchemy.exc import OperationalError, IntegrityError
    
    class DatabaseErrorSimulator:
        def __init__(self):
            self.error_count = 0
            self.max_errors = 0
        
        def set_error_scenario(self, error_type, max_errors=1):
            self.error_type = error_type
            self.max_errors = max_errors
            self.error_count = 0
        
        def maybe_raise_error(self):
            if self.error_count < self.max_errors:
                self.error_count += 1
                if self.error_type == 'operational':
                    raise OperationalError("Database connection lost", None, None)
                elif self.error_type == 'integrity':
                    raise IntegrityError("Constraint violation", None, None)
                elif self.error_type == 'timeout':
                    raise OperationalError("Lock wait timeout exceeded", None, None)
    
    return DatabaseErrorSimulator()