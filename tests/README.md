# Tests

This directory contains tests for the AiogramShopBot payment validation system.

## Test Files

### `test_payment_validation.py`
Tests for the core payment validation logic (Phase 2):
- Exact payment detection
- Overpayment handling (minor vs significant)
- Underpayment detection (zero tolerance)
- Late payment handling
- Currency mismatch detection
- PaymentTransaction record creation

**Status:** Test stubs created, implement during Phase 2

### `test_e2e_payment_flow.py`
End-to-end payment flow tests with mocked KryptoExpress API:
- Full wallet payment (no invoice needed)
- Partial wallet payment + crypto invoice
- Exact crypto payment webhook processing
- Overpayment → wallet credit
- First underpayment → retry with new invoice
- Second underpayment → penalty
- Late payment → penalty
- Wallet checkout scenarios
- Payment validation edge cases (tolerance boundaries, satoshi-level amounts)

**Status:** ✅ Test structure implemented, edge case tests fully functional

**Run with:**
```bash
pytest tests/test_e2e_payment_flow.py -v -s
```

### `test_data_retention_cleanup.py`
Tests for the data retention cleanup job:
- Old order deletion (30 days)
- Cascade deletion of invoices and payment transactions
- Referral usage deletion (365 days)
- Expired referral discount deletion (90 days)
- Edge case handling

**Status:** Test stubs created, implement after Phase 1 database is ready

### `manual/`
Manual testing scripts for realistic payment webhook simulation:

#### `manual/simulate_payment_webhook.py`
Python script to simulate KryptoExpress payment webhooks with realistic payloads:
- HMAC-SHA512 signature generation
- Realistic crypto address generation
- Support for all cryptocurrencies (BTC, ETH, LTC, SOL, BNB, USDT, USDC)
- Configurable payment scenarios (exact, overpayment, underpayment, late payment)
- Command-line interface with full argument support

**Usage:**
```bash
# Exact payment
python tests/manual/simulate_payment_webhook.py \
  --payment-id 123456 \
  --amount-paid 0.001 \
  --url http://localhost:8000/webhook/cryptoprocessing/event

# Overpayment (10%)
python tests/manual/simulate_payment_webhook.py \
  --payment-id 123456 \
  --amount-paid 0.0011 \
  --amount-required 0.001 \
  --fiat-amount 55.0

# Underpayment (90%)
python tests/manual/simulate_payment_webhook.py \
  --payment-id 123456 \
  --amount-paid 0.0009 \
  --amount-required 0.001

# Currency mismatch
python tests/manual/simulate_payment_webhook.py \
  --payment-id 123456 \
  --crypto LTC \
  --amount-paid 0.05 \
  --amount-required 0.001

# Payment expired
python tests/manual/simulate_payment_webhook.py \
  --payment-id 123456 \
  --amount-paid 0.001 \
  --not-paid
```

**Environment Variables:**
- `WEBHOOK_URL` - Webhook endpoint (default: http://localhost:8000/webhook/cryptoprocessing/event)
- `KRYPTO_EXPRESS_API_SECRET` - API secret for HMAC signature

#### `manual/run_payment_scenarios.sh`
Bash script to run all payment validation scenarios automatically:
- 6 predefined test scenarios (exact, minor overpayment, significant overpayment, underpayment, currency mismatch, expired)
- Colored output (green/red for pass/fail)
- Automatic payment ID incrementing
- Test results summary

**Usage:**
```bash
# Run all scenarios
export WEBHOOK_URL="http://localhost:8000/webhook/cryptoprocessing/event"
export KRYPTO_EXPRESS_API_SECRET="your-secret-key"
./tests/manual/run_payment_scenarios.sh

# Custom payment ID
PAYMENT_ID=999999 ./tests/manual/run_payment_scenarios.sh
```

**Status:** ✅ Fully implemented and ready for testing

### `webhook/` (Legacy)
Old webhook simulation scripts (kept for reference):
- `test_payment_webhook.py` - Python script to simulate KryptoExpress webhooks
- `test_payment_webhook.sh` - Bash alternative
- `README.md` - Instructions for webhook testing

## Running Tests

### Run all tests:
```bash
pytest tests/ -v
```

### Run specific test file:
```bash
pytest tests/test_payment_validation.py -v
```

### Run specific test class:
```bash
pytest tests/test_payment_validation.py::TestPaymentValidation -v
```

### Run specific test:
```bash
pytest tests/test_payment_validation.py::TestPaymentValidation::test_exact_payment_is_accepted -v
```

### Run with coverage:
```bash
pytest tests/ --cov=services --cov=models --cov-report=html
```

## Test Implementation Status

| Test File | Status | Phase |
|-----------|--------|-------|
| `test_payment_validation.py` | 📝 Stubs only | Phase 2 |
| `test_e2e_payment_flow.py` | ✅ Implemented (edge cases) | Phase 4 |
| `test_data_retention_cleanup.py` | 📝 Stubs only | After Phase 1 DB |
| `manual/simulate_payment_webhook.py` | ✅ Fully implemented | Phase 4 |
| `manual/run_payment_scenarios.sh` | ✅ Fully implemented | Phase 4 |
| `webhook/test_payment_webhook.py` | ✅ Implemented (legacy) | Complete |

## Writing New Tests

### Test Structure
```python
import pytest

class TestFeatureName:
    """Test suite for Feature."""

    def test_specific_behavior(self):
        """Test that specific behavior works correctly."""
        # Arrange
        input_data = prepare_test_data()

        # Act
        result = function_under_test(input_data)

        # Assert
        assert result == expected_output
```

### Async Tests
For async functions, use `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function()
    assert result is not None
```

### Database Tests
For tests requiring database:

```python
from db import get_db_session, session_commit

@pytest.mark.asyncio
async def test_database_operation():
    """Test database operation."""
    async with get_db_session() as session:
        # Create test data
        # Perform operation
        # Verify results
        await session_commit(session)
```

## Test Data

### Creating Test Orders
```python
from datetime import datetime, timedelta
from models.order import Order, OrderDTO
from enums.order_status import OrderStatus

old_order = OrderDTO(
    user_id=1,
    status=OrderStatus.PAID,
    total_price=50.0,
    currency=Currency.EUR,
    created_at=datetime.now() - timedelta(days=35),  # 35 days old
    expires_at=datetime.now() - timedelta(days=35, minutes=-15)
)
```

### Creating Test Payment Transactions
```python
from models.payment_transaction import PaymentTransactionDTO
from enums.cryptocurrency import Cryptocurrency

transaction = PaymentTransactionDTO(
    order_id=123,
    invoice_id=456,
    crypto_amount=0.001,
    crypto_currency=Cryptocurrency.BTC,
    fiat_amount=50.0,
    fiat_currency=Currency.EUR,
    is_underpayment=True,
    penalty_applied=False
)
```

## Continuous Integration

Tests should be run in CI/CD pipeline:
- On every pull request
- Before merging to main branch
- Daily for integration tests

## Test Coverage Goals

- **Unit Tests:** 80%+ coverage
- **Integration Tests:** Critical paths covered
- **Edge Cases:** All validation edge cases tested

## Troubleshooting

### Tests won't run
```bash
# Install pytest if missing
pip install pytest pytest-asyncio

# Check Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database errors in tests
```bash
# Ensure test database is clean
rm test_database.db

# Or use in-memory database for tests
# Set DB_NAME=:memory: in test config
```

### Import errors
```bash
# Run from project root
cd /path/to/AiogramShopBot
pytest tests/
```

## Future Tests

Additional tests to implement:
- [ ] Webhook signature validation tests
- [ ] Invoice generation tests
- [ ] Order timeout job tests
- [ ] Referral code generation tests
- [ ] User wallet balance tests
- [ ] Exchange rate locking tests
- [ ] Multi-currency payment tests
- [ ] Penalty calculation tests
- [ ] Notification delivery tests

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy testing best practices](https://docs.sqlalchemy.org/en/14/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
