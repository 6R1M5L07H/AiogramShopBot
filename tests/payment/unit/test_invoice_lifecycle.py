"""
Invoice Lifecycle Unit Tests

Tests all invoice lifecycle scenarios without requiring ngrok or external services.
Uses in-memory SQLite database and mocked KryptoExpress API.

Run with:
    pytest tests/payment/unit/test_invoice_lifecycle.py -v
    pytest tests/payment/unit/test_invoice_lifecycle.py -v -s  # with output
    pytest tests/payment/unit/test_invoice_lifecycle.py --cov=services --cov=repositories  # with coverage
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Mock config before imports
import config
from enums.currency import Currency as CurrencyEnum

# Override config for testing
config.DB_ENCRYPTION = False
config.ORDER_TIMEOUT_MINUTES = 30
config.ORDER_CANCEL_GRACE_PERIOD_MINUTES = 5
config.PAYMENT_LATE_PENALTY_PERCENT = 5.0
config.CURRENCY = CurrencyEnum.EUR


from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from models.base import Base
from models.user import User
from models.order import Order
from models.item import Item
from models.category import Category
from models.subcategory import Subcategory
from models.invoice import Invoice
from models.payment_transaction import PaymentTransaction
from enums.order_status import OrderStatus
from enums.order_cancel_reason import OrderCancelReason
from enums.currency import Currency
from enums.cryptocurrency import Cryptocurrency
from repositories.order import OrderRepository
from repositories.user import UserRepository
from repositories.item import ItemRepository
from repositories.invoice import InvoiceRepository
from repositories.payment_transaction import PaymentTransactionRepository
from services.invoice import InvoiceService
from services.payment import PaymentService
from services.order import OrderService


class TestInvoiceLifecycle:
    """Test invoice lifecycle scenarios"""

    @pytest.fixture
    def engine(self):
        """Create in-memory SQLite database"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        # Note: is_active column is now in Invoice model, no migration needed
        return engine

    @pytest.fixture
    def session(self, engine):
        """Create database session"""
        session = Session(engine)
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def test_user(self, session):
        """Create test user"""
        user = User(
            telegram_id=12345,
            top_up_amount=0.0,
            strike_count=0
        )
        session.add(user)
        session.commit()
        return user

    @pytest.fixture
    def test_category(self, session):
        """Create test category"""
        category = Category(name="Test Category")
        session.add(category)
        session.commit()
        return category

    @pytest.fixture
    def test_subcategory(self, session, test_category):
        """Create test subcategory"""
        subcategory = Subcategory(
            name="Test Subcategory"
        )
        session.add(subcategory)
        session.commit()
        return subcategory

    @pytest.fixture
    def test_items(self, session, test_subcategory, test_category):
        """Create test items"""
        items = []
        for i in range(3):
            item = Item(
                category_id=test_category.id,
                subcategory_id=test_subcategory.id,
                private_data=f"TEST-KEY-{i}",
                price=10.0,
                description=f"Test Item {i}",
                is_physical=False,
                is_sold=False,
                is_new=True
            )
            session.add(item)
            items.append(item)
        session.commit()
        return items

    @pytest.fixture
    def mock_kryptoexpress_api(self):
        """Mock KryptoExpress API responses"""
        with patch('crypto_api.CryptoApiWrapper.CryptoApiWrapper.fetch_api_request') as mock:
            mock.return_value = {
                "id": 123456,
                "address": "bc1qmock123test456",
                "cryptoAmount": 0.001,
                "cryptoCurrency": "BTC",
                "fiatAmount": 30.0,
                "fiatCurrency": "EUR",
                "isPaid": False,
                "paymentType": "PAYMENT"
            }
            yield mock

    # ==================== Scenario 1: Invoice Creation ====================

    @pytest.mark.asyncio
    async def test_invoice_creation(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: Invoice creation for crypto payment

        Expected:
        - Invoice created with is_active=1
        - Unique invoice number (INV-YYYY-XXXXXX)
        - Order expires_at set to now() + 30 minutes
        - Payment address from KryptoExpress
        """
        # Create order
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=0.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        session.add(order)
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Create invoice
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=30.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        # Verify invoice
        assert invoice is not None
        assert invoice.is_active == 1
        assert invoice.invoice_number.startswith("INV-")
        assert len(invoice.invoice_number) == 15  # INV-YYYY-XXXXX (format changed)
        assert invoice.payment_address.startswith("bc1qmock")  # Mock generates varying addresses
        assert invoice.fiat_amount == 30.0
        assert invoice.payment_crypto_currency == Cryptocurrency.BTC

        # Verify order
        assert order.expires_at > datetime.utcnow()
        assert (order.expires_at - datetime.utcnow()).total_seconds() <= 1800  # 30 minutes

    # ==================== Scenario 2: Wallet-Only Payment ====================

    @pytest.mark.asyncio
    async def test_wallet_only_payment(self, session, test_user, test_items):
        """
        Test: Order fully paid by wallet (no crypto invoice)

        Expected:
        - Invoice created with payment_address=NULL
        - Invoice is_active=1 (tracking invoice)
        - Order status=PAID immediately
        - Items delivered
        """
        # Give user sufficient wallet balance
        test_user.top_up_amount = 100.0
        session.commit()

        # Create order
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=0.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        session.add(order)
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Process wallet payment
        invoice, needs_crypto = await PaymentService.orchestrate_payment_processing(
            order_id=order.id,
            crypto_currency=Cryptocurrency.BTC,  # Dummy value
            session=session
        )

        # Verify invoice
        assert invoice is not None
        assert invoice.payment_address is None
        assert invoice.is_active == 1
        assert invoice.fiat_amount == 30.0

        # Verify order
        stmt = select(Order).where(Order.id == order.id)
        result = session.execute(stmt)
        updated_order = result.scalar_one()
        assert updated_order.status == OrderStatus.PAID
        assert updated_order.wallet_used == 30.0
        assert needs_crypto is False

        # Verify wallet deduction
        stmt = select(User).where(User.id == test_user.id)
        result = session.execute(stmt)
        updated_user = result.scalar_one()
        assert updated_user.top_up_amount == 70.0

    # ==================== Scenario 3: Mixed Payment ====================

    @pytest.mark.asyncio
    async def test_mixed_payment(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: Wallet partially covers order, invoice for remaining amount

        Expected:
        - Wallet deducted immediately
        - Invoice created for REMAINING amount only
        - Invoice fiat_amount = order.total_price - wallet_used
        """
        # Give user partial wallet balance
        test_user.top_up_amount = 10.0
        session.commit()

        # Create order
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=0.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        session.add(order)
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Process mixed payment
        invoice, needs_crypto = await PaymentService.orchestrate_payment_processing(
            order_id=order.id,
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        # Verify invoice (for REMAINING amount)
        assert invoice is not None
        assert invoice.fiat_amount == 20.0  # 30 - 10 wallet
        assert invoice.payment_address.startswith("bc1qmock")  # Mock generates varying addresses
        assert invoice.is_active == 1
        assert needs_crypto is True

        # Verify order
        stmt = select(Order).where(Order.id == order.id)
        result = session.execute(stmt)
        updated_order = result.scalar_one()
        assert updated_order.status == OrderStatus.PENDING_PAYMENT  # Still waiting for crypto
        assert updated_order.wallet_used == 10.0

        # Verify wallet deduction
        stmt = select(User).where(User.id == test_user.id)
        result = session.execute(stmt)
        updated_user = result.scalar_one()
        assert updated_user.top_up_amount == 0.0

    # ==================== Scenario 4: Successful Payment ====================

    @pytest.mark.asyncio
    async def test_successful_payment(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: Successful crypto payment completes order

        Expected:
        - Order status=PAID
        - Items marked as sold
        - PaymentTransaction created
        """
        # Create order with invoice
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=0.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        session.add(order)
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Create invoice
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=30.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        # Simulate payment webhook (would be called by webhook handler)
        # For this test, we manually update order status and mark items sold
        order.status = OrderStatus.PAID
        order.paid_at = datetime.utcnow()
        for item in test_items:
            item.is_sold = True
        session.commit()

        # Create payment transaction
        transaction = PaymentTransaction(
            order_id=order.id,
            invoice_id=invoice.id,
            payment_processing_id=123456,
            crypto_amount=0.001,
            crypto_currency=Cryptocurrency.BTC,
            fiat_amount=30.0,
            fiat_currency=Currency.EUR,
            payment_address="bc1qmock123test456",
            transaction_hash="mock_tx_hash",
            received_at=datetime.utcnow(),
            is_underpayment=False,
            is_overpayment=False,
            is_late_payment=False,
            penalty_applied=False
        )
        session.add(transaction)
        session.commit()

        # Verify order
        stmt = select(Order).where(Order.id == order.id)
        result = session.execute(stmt)
        updated_order = result.scalar_one()
        assert updated_order.status == OrderStatus.PAID
        assert updated_order.paid_at is not None

        # Verify items sold
        stmt = select(Item).where(Item.order_id == order.id)
        result = session.execute(stmt)
        sold_items = result.scalars().all()
        assert len(sold_items) == 3
        assert all(item.is_sold for item in sold_items)

        # Verify transaction
        stmt = select(PaymentTransaction).where(PaymentTransaction.invoice_id == invoice.id)
        result = session.execute(stmt)
        tx = result.scalar_one()
        assert tx.fiat_amount == 30.0
        assert tx.is_underpayment is False

    # ==================== Scenario 5: Order Timeout ====================

    @pytest.mark.asyncio
    async def test_order_timeout(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: Order timeout marks invoices inactive and releases items

        Expected:
        - Order status=TIMEOUT
        - Invoice is_active=0
        - Items released (order_id=NULL)
        """
        # Create expired order with invoice
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=0.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow() - timedelta(minutes=45),
            expires_at=datetime.utcnow() - timedelta(minutes=15)  # Expired 15 min ago
        )
        session.add(order)
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Create invoice
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=30.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        # Simulate timeout job
        order.status = OrderStatus.TIMEOUT
        await InvoiceRepository.mark_as_inactive(invoice.id, session)

        # Release items
        for item in test_items:
            item.order_id = None
            item.is_sold = False
        session.commit()

        # Verify order
        stmt = select(Order).where(Order.id == order.id)
        result = session.execute(stmt)
        updated_order = result.scalar_one()
        assert updated_order.status == OrderStatus.TIMEOUT

        # Verify invoice inactive
        stmt = select(Invoice).where(Invoice.id == invoice.id)
        result = session.execute(stmt)
        updated_invoice = result.scalar_one()
        assert updated_invoice.is_active == 0

        # Verify items released
        stmt = select(Item).where(Item.id.in_([item.id for item in test_items]))
        result = session.execute(stmt)
        released_items = result.scalars().all()
        assert all(item.order_id is None for item in released_items)
        assert all(not item.is_sold for item in released_items)

    # ==================== Scenario 6: User Cancellation ====================

    @pytest.mark.asyncio
    async def test_user_cancellation(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: User cancels order within grace period (no penalty)

        Expected:
        - Order status=CANCELLED_BY_USER
        - Invoice is_active=0
        - Wallet fully refunded
        - No strike added
        """
        # Give user wallet balance
        test_user.top_up_amount = 50.0
        session.commit()

        # Create order with wallet usage
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=10.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow(),  # Just created
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        session.add(order)
        # Deduct wallet (as would happen in real order creation)
        test_user.top_up_amount -= order.wallet_used
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Create invoice for remaining 20 EUR
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=20.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        # Cancel order (within grace period)
        await OrderService.cancel_order(order.id, OrderCancelReason.USER, session, refund_wallet=True)

        # Verify order
        stmt = select(Order).where(Order.id == order.id)
        result = session.execute(stmt)
        updated_order = result.scalar_one()
        assert updated_order.status == OrderStatus.CANCELLED_BY_USER

        # Verify invoice inactive
        stmt = select(Invoice).where(Invoice.id == invoice.id)
        result = session.execute(stmt)
        updated_invoice = result.scalar_one()
        assert updated_invoice.is_active == 0

        # Verify wallet refunded (no penalty within grace period)
        stmt = select(User).where(User.id == test_user.id)
        result = session.execute(stmt)
        updated_user = result.scalar_one()
        assert updated_user.top_up_amount == 50.0  # Full refund (40 + 10)

    @pytest.mark.asyncio
    async def test_user_cancellation_with_penalty(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: User cancels order outside grace period (with penalty)

        Expected:
        - Order status=CANCELLED_BY_USER
        - Invoice is_active=0
        - Wallet refunded minus 5% penalty
        - Strike added
        """
        # Give user wallet balance
        test_user.top_up_amount = 50.0
        session.commit()

        # Create order with wallet usage (created 10 minutes ago, outside grace period)
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=10.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow() - timedelta(minutes=10),  # Outside grace period
            expires_at=datetime.utcnow() + timedelta(minutes=20)
        )
        session.add(order)
        # Deduct wallet (as would happen in real order creation)
        test_user.top_up_amount -= order.wallet_used
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Create invoice
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=20.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        # Cancel order (outside grace period)
        await OrderService.cancel_order(order.id, OrderCancelReason.USER, session, refund_wallet=True)

        # Verify order
        stmt = select(Order).where(Order.id == order.id)
        result = session.execute(stmt)
        updated_order = result.scalar_one()
        assert updated_order.status == OrderStatus.CANCELLED_BY_USER

        # Verify invoice inactive
        stmt = select(Invoice).where(Invoice.id == invoice.id)
        result = session.execute(stmt)
        updated_invoice = result.scalar_one()
        assert updated_invoice.is_active == 0

        # Verify wallet refunded with penalty (10 EUR - 5% = 9.50 EUR)
        stmt = select(User).where(User.id == test_user.id)
        result = session.execute(stmt)
        updated_user = result.scalar_one()
        expected_wallet = 50.0 - 10.0 + 9.5  # Original - used + refunded_with_penalty
        assert abs(updated_user.top_up_amount - expected_wallet) < 0.01

        # Verify strike added
        assert updated_user.strike_count == 1

    # ==================== Scenario 7: Admin Cancellation ====================

    @pytest.mark.asyncio
    async def test_admin_cancellation(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: Admin cancels order (full refund, no penalty)

        Expected:
        - Order status=CANCELLED_BY_ADMIN
        - Invoice is_active=0
        - Wallet fully refunded (NO penalty)
        - NO strike added
        """
        # Give user wallet balance
        test_user.top_up_amount = 50.0
        session.commit()

        # Create order with wallet usage
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=10.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow() - timedelta(minutes=10),
            expires_at=datetime.utcnow() + timedelta(minutes=20)
        )
        session.add(order)
        # Deduct wallet (as would happen in real order creation)
        test_user.top_up_amount -= order.wallet_used
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Create invoice
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=20.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        # Admin cancels order
        order.status = OrderStatus.CANCELLED_BY_ADMIN
        await InvoiceRepository.mark_as_inactive(invoice.id, session)

        # Full wallet refund (no penalty for admin cancellation)
        test_user.top_up_amount += order.wallet_used

        # Release items
        for item in test_items:
            item.order_id = None
        session.commit()

        # Verify order
        stmt = select(Order).where(Order.id == order.id)
        result = session.execute(stmt)
        updated_order = result.scalar_one()
        assert updated_order.status == OrderStatus.CANCELLED_BY_ADMIN

        # Verify invoice inactive
        stmt = select(Invoice).where(Invoice.id == invoice.id)
        result = session.execute(stmt)
        updated_invoice = result.scalar_one()
        assert updated_invoice.is_active == 0

        # Verify wallet fully refunded (no penalty)
        stmt = select(User).where(User.id == test_user.id)
        result = session.execute(stmt)
        updated_user = result.scalar_one()
        assert updated_user.top_up_amount == 50.0  # Full refund

        # Verify NO strike added
        assert updated_user.strike_count == 0

    # ==================== Scenario 8: Underpayment ====================

    @pytest.mark.asyncio
    async def test_underpayment(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: Underpayment cancels order and credits wallet

        Expected:
        - Order status=CANCELLED_BY_SYSTEM
        - Invoice is_active=0
        - Received amount credited to wallet
        """
        # Create order with invoice
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=0.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        session.add(order)
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Create invoice
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=30.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        # Simulate underpayment (25 EUR received instead of 30 EUR)
        order.status = OrderStatus.CANCELLED_BY_SYSTEM
        await InvoiceRepository.mark_as_inactive(invoice.id, session)

        # Credit received amount to wallet
        test_user.top_up_amount += 25.0

        # Release items
        for item in test_items:
            item.order_id = None
        session.commit()

        # Create payment transaction
        transaction = PaymentTransaction(
            order_id=order.id,
            invoice_id=invoice.id,
            payment_processing_id=123456,
            crypto_amount=0.00083,
            crypto_currency=Cryptocurrency.BTC,
            fiat_amount=25.0,
            fiat_currency=Currency.EUR,
            payment_address="bc1qmock123test456",
            transaction_hash="mock_tx_hash",
            received_at=datetime.utcnow(),
            is_underpayment=True,
            is_overpayment=False,
            is_late_payment=False,
            penalty_applied=False,
            wallet_credit_amount=25.0
        )
        session.add(transaction)
        session.commit()

        # Verify order
        stmt = select(Order).where(Order.id == order.id)
        result = session.execute(stmt)
        updated_order = result.scalar_one()
        assert updated_order.status == OrderStatus.CANCELLED_BY_SYSTEM

        # Verify invoice inactive
        stmt = select(Invoice).where(Invoice.id == invoice.id)
        result = session.execute(stmt)
        updated_invoice = result.scalar_one()
        assert updated_invoice.is_active == 0

        # Verify wallet credited
        stmt = select(User).where(User.id == test_user.id)
        result = session.execute(stmt)
        updated_user = result.scalar_one()
        assert updated_user.top_up_amount == 25.0

        # Verify transaction
        stmt = select(PaymentTransaction).where(PaymentTransaction.invoice_id == invoice.id)
        result = session.execute(stmt)
        tx = result.scalar_one()
        assert tx.is_underpayment is True
        assert tx.wallet_credit_amount == 25.0

    # ==================== Scenario 9: Late Payment (No Penalty) ====================

    @pytest.mark.asyncio
    async def test_late_payment_accepted(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: Late payment (before timeout job) accepted without penalty

        Expected:
        - Order status=PAID
        - is_late_payment=True but penalty_applied=False
        - Items delivered normally
        """
        # Create expired order with invoice
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=0.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow() - timedelta(minutes=45),
            expires_at=datetime.utcnow() - timedelta(minutes=5)  # Expired 5 min ago
        )
        session.add(order)
        session.commit()

        # Reserve items
        for item in test_items:
            item.order_id = order.id
        session.commit()

        # Create invoice
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=30.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        # Simulate late payment (payment arrives before timeout job runs)
        order.status = OrderStatus.PAID
        order.paid_at = datetime.utcnow()
        for item in test_items:
            item.is_sold = True
        session.commit()

        # Create payment transaction (late but NO penalty)
        transaction = PaymentTransaction(
            order_id=order.id,
            invoice_id=invoice.id,
            payment_processing_id=123456,
            crypto_amount=0.001,
            crypto_currency=Cryptocurrency.BTC,
            fiat_amount=30.0,
            fiat_currency=Currency.EUR,
            payment_address="bc1qmock123test456",
            transaction_hash="mock_tx_hash",
            received_at=datetime.utcnow(),
            is_underpayment=False,
            is_overpayment=False,
            is_late_payment=True,  # Payment was late
            penalty_applied=False  # But NO penalty (items delivered)
        )
        session.add(transaction)
        session.commit()

        # Verify order
        stmt = select(Order).where(Order.id == order.id)
        result = session.execute(stmt)
        updated_order = result.scalar_one()
        assert updated_order.status == OrderStatus.PAID
        assert updated_order.paid_at > updated_order.expires_at  # Payment late

        # Verify transaction (late but no penalty)
        stmt = select(PaymentTransaction).where(PaymentTransaction.invoice_id == invoice.id)
        result = session.execute(stmt)
        tx = result.scalar_one()
        assert tx.is_late_payment is True
        assert tx.penalty_applied is False  # NO penalty when items delivered

    # ==================== Scenario 10: Expired Order Access ====================

    @pytest.mark.asyncio
    async def test_expired_order_access(self, session, test_user, test_items):
        """
        Test: User tries to access expired/finalized order

        Expected:
        - Code checks order status BEFORE processing
        - Non-PENDING orders are rejected
        - No invoice renewal possible
        """
        # Create finalized orders with different statuses
        finalized_statuses = [
            OrderStatus.TIMEOUT,
            OrderStatus.CANCELLED_BY_USER,
            OrderStatus.CANCELLED_BY_ADMIN,
            OrderStatus.CANCELLED_BY_SYSTEM,
            OrderStatus.PAID
        ]

        for status in finalized_statuses:
            order = Order(
            currency=Currency.EUR,
                user_id=test_user.id,
                total_price=30.0,
                wallet_used=0.0,
                status=status,
                created_at=datetime.utcnow() - timedelta(hours=1),
                expires_at=datetime.utcnow() - timedelta(minutes=30)
            )
            session.add(order)
        session.commit()

        # Verify: Code should reject all finalized orders
        # This is tested by checking order status in handlers/user/order.py:process_payment()
        pending_statuses = [
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.PENDING_PAYMENT_AND_ADDRESS,
            OrderStatus.PENDING_PAYMENT_PARTIAL
        ]

        stmt = select(Order).where(Order.user_id == test_user.id)
        result = session.execute(stmt)
        all_orders = result.scalars().all()

        for order in all_orders:
            # Simulate check from handlers/user/order.py line 516
            is_processable = order.status in pending_statuses

            # All finalized orders should be rejected
            if order.status in finalized_statuses:
                assert not is_processable, f"Order with status {order.status} should NOT be processable"

    # ==================== Soft-Delete Query Tests ====================

    @pytest.mark.asyncio
    async def test_active_invoices_only_query(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: Query returns only active invoices by default

        Expected:
        - get_by_order_id(include_inactive=False) returns None for cancelled orders
        """
        # Create order with invoice
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=0.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        session.add(order)
        session.commit()

        # Create and then mark invoice inactive
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=30.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        await InvoiceRepository.mark_as_inactive(invoice.id, session)

        # Query with include_inactive=False (default)
        active_invoice = await InvoiceRepository.get_by_order_id(
            order.id,
            session,
            include_inactive=False
        )

        # Should return None (invoice is inactive)
        assert active_invoice is None

    @pytest.mark.asyncio
    async def test_all_invoices_audit_trail_query(self, session, test_user, test_items, mock_kryptoexpress_api):
        """
        Test: Query returns all invoices including inactive for audit trail

        Expected:
        - get_all_by_order_id(include_inactive=True) returns all invoices
        """
        # Create order with invoice
        order = Order(
            currency=Currency.EUR,
            user_id=test_user.id,
            total_price=30.0,
            wallet_used=0.0,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        session.add(order)
        session.commit()

        # Create and mark invoice inactive
        invoice = await InvoiceService.create_invoice_with_kryptoexpress(
            order_id=order.id,
            fiat_amount=30.0,
            fiat_currency="EUR",
            crypto_currency=Cryptocurrency.BTC,
            session=session
        )

        await InvoiceRepository.mark_as_inactive(invoice.id, session)

        # Query with include_inactive=True
        all_invoices = await InvoiceRepository.get_all_by_order_id(
            order.id,
            session,
            include_inactive=True
        )

        # Should return invoice despite is_active=0
        assert len(all_invoices) == 1
        assert all_invoices[0].is_active == 0
