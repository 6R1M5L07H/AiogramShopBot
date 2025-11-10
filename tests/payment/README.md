# Payment & Invoice Testing

This directory contains tests for the payment system and invoice lifecycle.

## Quick Start

### Run All Tests (No ngrok required)
```bash
# From project root
pytest tests/payment/unit/ -v
```

### Run Specific Test Suite
```bash
# Invoice lifecycle tests
pytest tests/payment/unit/test_invoice_lifecycle.py -v

# Payment validation tests
pytest tests/payment/unit/test_payment_validation.py -v

# E2E payment flow tests
pytest tests/payment/unit/test_e2e_payment_flow.py -v
```

### Run Single Test
```bash
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_wallet_only_payment -v
```

## Test Structure

```
tests/payment/
├── README.md                           # This file
├── INVOICE_LIFECYCLE_TESTPLAN.md      # Detailed test plan
├── unit/                               # Automated tests (no ngrok)
│   ├── test_invoice_lifecycle.py      # Invoice lifecycle scenarios
│   ├── test_payment_validation.py     # Payment validation logic
│   └── test_e2e_payment_flow.py       # End-to-end payment flows
└── manual/                             # Manual integration tests
    ├── simulate_payment_webhook.py    # Webhook simulator
    └── payment-shipment-test-guide.md # Manual testing guide
```

## Test Coverage

### Automated Unit Tests (tests/payment/unit/)

**No external dependencies required** - Uses in-memory SQLite and mocked APIs

✅ **Scenario 1:** Invoice Creation (Crypto Payment)
- Invoice created with `is_active=1`
- Unique invoice number generated
- Payment address from KryptoExpress

✅ **Scenario 2:** Wallet-Only Payment
- Order paid immediately from wallet
- Invoice created for tracking (no payment address)
- Items delivered

✅ **Scenario 3:** Mixed Payment (Wallet + Crypto)
- Wallet deducted immediately
- Invoice created for remaining amount
- Correct amount calculations

✅ **Scenario 4:** Successful Payment
- Order marked as PAID
- Items marked as sold
- PaymentTransaction created

✅ **Scenario 5:** Order Timeout
- Order status → TIMEOUT
- Invoice marked inactive
- Items released back to stock

✅ **Scenario 6:** User Cancellation
- Within grace period: Full refund, no strike
- Outside grace period: Refund with penalty, strike added

✅ **Scenario 7:** Admin Cancellation
- Full refund (no penalty)
- No strike added

✅ **Scenario 8:** Underpayment
- Order cancelled
- Received amount credited to wallet

✅ **Scenario 9:** Late Payment
- Payment accepted (before timeout job)
- NO penalty applied
- Items delivered

✅ **Scenario 10:** Expired Order Access
- User redirected when accessing finalized orders
- No invoice renewal possible

✅ **Soft-Delete Queries**
- Active invoices only (default)
- All invoices including inactive (audit trail)

### Manual Integration Tests (tests/payment/manual/)

**Requires ngrok and running bot** - Tests real webhook flow

See `tests/shipment/manual/payment-shipment-test-guide.md` for detailed instructions.

## Running Tests

### Prerequisites

1. **Install test dependencies:**
   ```bash
   pip install pytest pytest-asyncio pytest-cov
   ```

2. **Ensure migration 009 is applied:**
   ```bash
   sqlite3 data/database.db < migrations/009_add_invoice_is_active.sql
   ```

### Basic Usage

```bash
# Run all unit tests
pytest tests/payment/unit/ -v

# Run with output (see print statements)
pytest tests/payment/unit/ -v -s

# Run with coverage report
pytest tests/payment/unit/ --cov=services --cov=repositories --cov-report=term-missing

# Run with HTML coverage report
pytest tests/payment/unit/ --cov=services --cov=repositories --cov-report=html
open htmlcov/index.html
```

### Advanced Usage

```bash
# Run tests matching pattern
pytest tests/payment/unit/ -k "wallet" -v

# Run tests with debugging
pytest tests/payment/unit/test_invoice_lifecycle.py -v --pdb

# Run tests with detailed logs
pytest tests/payment/unit/ -v --log-cli-level=DEBUG

# Run tests in parallel (faster)
pytest tests/payment/unit/ -v -n auto
```

### Continuous Integration

```bash
# CI-friendly command (no color, junit xml output)
pytest tests/payment/unit/ --tb=short --junitxml=test-results.xml
```

## Test Configuration

Tests use in-memory SQLite with these config overrides:

```python
config.DB_ENCRYPTION = False
config.ORDER_TIMEOUT_MINUTES = 30
config.ORDER_CANCEL_GRACE_PERIOD_MINUTES = 5
config.PAYMENT_LATE_PENALTY_PERCENT = 5.0
config.CURRENCY = "EUR"
```

To test with different values, modify `test_invoice_lifecycle.py` before running tests.

## Debugging Failed Tests

### View detailed output
```bash
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_wallet_only_payment -v -s
```

### Drop into debugger on failure
```bash
pytest tests/payment/unit/ --pdb
```

### Show local variables on failure
```bash
pytest tests/payment/unit/ -l
```

### Run last failed tests only
```bash
pytest tests/payment/unit/ --lf
```

## Manual Integration Testing

For manual testing with real bot and webhooks:

1. **Start bot:**
   ```bash
   python run.py
   ```

2. **Start ngrok:**
   ```bash
   ngrok http 8000
   ```

3. **Follow manual test guide:**
   ```bash
   cat tests/shipment/manual/payment-shipment-test-guide.md
   ```

4. **Simulate webhooks:**
   ```bash
   python tests/payment/manual/simulate_payment_webhook.py \
     --invoice-number INV-2025-ABC123 \
     --amount-paid 0.001 \
     --amount-required 0.001 \
     --crypto BTC
   ```

## Test Data

### Fixtures Available

- `engine`: In-memory SQLite database
- `session`: Database session
- `test_user`: User with ID 12345, balance 0.0
- `test_category`: Test category
- `test_subcategory`: Test subcategory
- `test_items`: 3 test items @ €10 each
- `mock_kryptoexpress_api`: Mocked KryptoExpress API responses

### Creating Custom Test Data

```python
@pytest.mark.asyncio
async def test_custom_scenario(session, test_user):
    # Create custom order
    order = Order(
        user_id=test_user.id,
        total_price=50.0,
        wallet_used=10.0,
        status=OrderStatus.PENDING_PAYMENT
    )
    session.add(order)
    session.commit()

    # Your test logic here...
```

## Troubleshooting

### Tests fail with "no such column: is_active"

**Problem:** Migration 009 not applied to test database

**Solution:** Migration is automatically applied in `engine` fixture. If issue persists, check that fixture is being used.

### Tests fail with import errors

**Problem:** Project root not in Python path

**Solution:** Tests add project root automatically. If issue persists:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/payment/unit/ -v
```

### Tests hang or timeout

**Problem:** Async tests not properly configured

**Solution:** Ensure `pytest-asyncio` is installed:
```bash
pip install pytest-asyncio
```

### Mock not working

**Problem:** Import order or patch path incorrect

**Solution:** Mock must be applied BEFORE import. Check patch path matches actual import:
```python
# Correct
with patch('crypto_api.CryptoApiWrapper.fetch_api_request'):
    ...

# Wrong
with patch('services.invoice.fetch_api_request'):
    ...
```

## Next Steps

1. ✅ Run automated tests: `pytest tests/payment/unit/ -v`
2. ✅ Verify all tests pass
3. ✅ Check coverage: `pytest tests/payment/unit/ --cov=services --cov-report=html`
4. ⏭️ Run manual integration tests (optional)
5. ⏭️ Deploy to production after all tests pass

## Support

For issues or questions:
- Check logs: `pytest -v -s --log-cli-level=DEBUG`
- Review test plan: `tests/payment/INVOICE_LIFECYCLE_TESTPLAN.md`
- Check documentation: `docs/payment/INVOICE_LIFECYCLE.md`
- Create GitHub issue with test failure details
