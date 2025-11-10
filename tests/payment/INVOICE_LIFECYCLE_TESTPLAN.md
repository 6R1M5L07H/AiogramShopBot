# Invoice Lifecycle - Test Plan

This test plan covers all invoice lifecycle scenarios documented in `docs/payment/INVOICE_LIFECYCLE.md`.

## Test Execution Modes

### 1. Automated Unit Tests (Recommended)
**No ngrok required** - Uses mocked database and services

```bash
# Run all invoice lifecycle tests
pytest tests/payment/unit/test_invoice_lifecycle.py -v

# Run specific test
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_wallet_only_payment -v

# Run with coverage
pytest tests/payment/unit/test_invoice_lifecycle.py --cov=services --cov=repositories --cov-report=html
```

### 2. Manual Integration Tests
**Requires ngrok** - Tests with real bot and webhook simulator

Follow the detailed guide in `tests/shipment/manual/payment-shipment-test-guide.md`

---

## Test Scenarios

### ✅ Scenario 1: Invoice Creation (Crypto Payment)

**Trigger:** User selects cryptocurrency for order payment

**Preconditions:**
- Order exists with status `PENDING_PAYMENT` or `PENDING_PAYMENT_AND_ADDRESS`
- No active invoice exists for order
- Wallet balance insufficient to cover full order amount

**Expected Results:**
- Invoice created with `is_active = 1`
- Invoice has unique invoice number (format: `INV-YYYY-XXXXXX`)
- Order `expires_at` set to `now() + 30 minutes` (configurable)
- Invoice has payment address from KryptoExpress
- Invoice `fiat_amount` = remaining amount after wallet deduction

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_invoice_creation -v

# Manual
# 1. Add items to cart
# 2. Click checkout
# 3. Select BTC
# 4. Verify invoice details in bot message
```

**Database Verification:**
```sql
SELECT id, order_id, invoice_number, payment_address, fiat_amount, is_active
FROM invoices
WHERE order_id = ?;
-- Expected: 1 row, is_active=1, payment_address NOT NULL
```

---

### ✅ Scenario 2: Wallet-Only Payment

**Trigger:** Wallet balance covers full order amount

**Preconditions:**
- User wallet balance >= order total price
- User navigates to payment step

**Expected Results:**
- Order marked as `PAID` immediately
- Invoice created with `payment_address = NULL` (tracking only)
- Invoice `is_active = 1` (for audit trail)
- Items delivered immediately
- No crypto payment required

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_wallet_only_payment -v
```

**Database Verification:**
```sql
SELECT i.invoice_number, i.payment_address, i.fiat_amount, o.status, o.wallet_used
FROM invoices i
JOIN orders o ON i.order_id = o.id
WHERE o.id = ?;
-- Expected: payment_address=NULL, status='PAID', wallet_used=order.total_price
```

---

### ✅ Scenario 3: Mixed Payment (Wallet + Crypto)

**Trigger:** Wallet balance partially covers order amount

**Preconditions:**
- 0 < wallet balance < order total price
- User navigates to payment step

**Expected Results:**
- Wallet balance deducted immediately
- Invoice created for REMAINING amount only
- Invoice `fiat_amount` = `order.total_price - wallet_used`
- Order stays `PENDING_PAYMENT` until crypto received
- User pays remaining amount via crypto

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_mixed_payment -v
```

**Database Verification:**
```sql
SELECT o.total_price, o.wallet_used, i.fiat_amount
FROM orders o
JOIN invoices i ON i.order_id = o.id
WHERE o.id = ?;
-- Expected: fiat_amount = total_price - wallet_used
```

---

### ✅ Scenario 4: Successful Payment

**Trigger:** KryptoExpress webhook with status PAID

**Preconditions:**
- Invoice exists with `is_active = 1`
- Payment received matches expected amount (within tolerance)

**Expected Results:**
- `PaymentTransaction` record created
- Order status updated to `PAID`
- Items marked as sold
- Buy records created
- Digital items delivered immediately
- User notified of successful payment

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_successful_payment -v

# Manual
python tests/payment/manual/simulate_payment_webhook.py \
  --invoice-number INV-2025-ABC123 \
  --amount-paid 0.001 \
  --amount-required 0.001 \
  --crypto BTC
```

**Database Verification:**
```sql
SELECT o.status, COUNT(i.id) as item_count, COUNT(b.id) as buy_count
FROM orders o
LEFT JOIN items i ON i.order_id = o.id
LEFT JOIN buys b ON b.item_id = i.id
WHERE o.id = ?
GROUP BY o.id;
-- Expected: status='PAID', item_count=buy_count (all items have buy records)
```

---

### ✅ Scenario 5: Order Timeout

**Trigger:** Background job runs after `order.expires_at`

**Preconditions:**
- Order status: `PENDING_PAYMENT*`
- Current time > `order.expires_at`
- No payment received

**Expected Results:**
- Order status updated to `TIMEOUT`
- All invoices marked as inactive: `is_active = 0`
- Reserved items released (stock restored)
- Strike added to user (if outside grace period)
- User notified of timeout

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_order_timeout -v

# Manual - wait for timeout or trigger job manually
python jobs/order_timeout_job.py
```

**Database Verification:**
```sql
SELECT o.status, i.is_active, COUNT(items.id) as released_items
FROM orders o
LEFT JOIN invoices i ON i.order_id = o.id
LEFT JOIN items ON items.order_id = o.id AND items.is_sold = 0
WHERE o.id = ?
GROUP BY o.id;
-- Expected: status='TIMEOUT', is_active=0, released_items > 0 (items no longer reserved)
```

---

### ✅ Scenario 6: User Cancellation

**Trigger:** User clicks "Cancel Order" button

**Preconditions:**
- Order status: `PENDING_PAYMENT*`
- Order not yet paid

**Expected Results:**
- Order status updated to `CANCELLED_BY_USER`
- All invoices marked as inactive: `is_active = 0`
- Wallet refunded (may include penalty if late)
- Reserved items released
- Strike added if outside grace period (5 minutes default)

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_user_cancellation -v

# Automated (with penalty)
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_user_cancellation_with_penalty -v
```

**Database Verification:**
```sql
SELECT o.status, i.is_active, u.top_up_amount as wallet, u.strike_count
FROM orders o
LEFT JOIN invoices i ON i.order_id = o.id
LEFT JOIN users u ON u.id = o.user_id
WHERE o.id = ?;
-- Expected: status='CANCELLED_BY_USER', is_active=0
-- If cancelled within grace period: strike_count unchanged
-- If cancelled late: strike_count += 1, wallet refunded with penalty
```

---

### ✅ Scenario 7: Admin Cancellation

**Trigger:** Admin clicks "Cancel Order" (with or without reason)

**Preconditions:**
- Order status: `PENDING_PAYMENT*` or `PAID_AWAITING_SHIPMENT`
- Admin has cancellation permission

**Expected Results:**
- Order status updated to `CANCELLED_BY_ADMIN`
- All invoices marked as inactive: `is_active = 0`
- Full wallet refund (NO penalty)
- Reserved items released
- User notified with custom reason (if provided)

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_admin_cancellation -v

# Manual
# 1. Navigate to Admin > Order Management > Shipping Required
# 2. Select order
# 3. Click "Cancel Order"
# 4. Optionally enter custom reason
# 5. Verify user receives notification with reason
```

**Database Verification:**
```sql
SELECT o.status, i.is_active, u.top_up_amount as wallet, u.strike_count
FROM orders o
LEFT JOIN invoices i ON i.order_id = o.id
LEFT JOIN users u ON u.id = o.user_id
WHERE o.id = ?;
-- Expected: status='CANCELLED_BY_ADMIN', is_active=0, NO strike added
```

---

### ✅ Scenario 8: Underpayment

**Trigger:** KryptoExpress webhook with UNDERPAYMENT status

**Preconditions:**
- Payment received < expected amount (outside tolerance)
- Invoice exists with `is_active = 1`

**Expected Results:**
- `PaymentTransaction` record created (for audit)
- Order status updated to `CANCELLED_BY_SYSTEM`
- Invoice marked as inactive: `is_active = 0`
- Reserved items released
- Received amount credited to user wallet
- User notified of cancellation and wallet credit

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_underpayment -v

# Manual
python tests/payment/manual/simulate_payment_webhook.py \
  --invoice-number INV-2025-ABC123 \
  --amount-paid 0.0009 \
  --amount-required 0.001 \
  --crypto BTC
```

**Database Verification:**
```sql
SELECT o.status, i.is_active, u.top_up_amount as wallet_credited, pt.is_underpayment
FROM orders o
LEFT JOIN invoices i ON i.order_id = o.id
LEFT JOIN users u ON u.id = o.user_id
LEFT JOIN payment_transactions pt ON pt.invoice_id = i.id
WHERE o.id = ?;
-- Expected: status='CANCELLED_BY_SYSTEM', is_active=0, is_underpayment=1, wallet credited
```

---

### ✅ Scenario 9: Late Payment (Before Timeout Job)

**Trigger:** KryptoExpress webhook AFTER `order.expires_at` but BEFORE timeout job runs

**Preconditions:**
- Payment received after expiration timestamp
- Order not yet cancelled by timeout job (race condition window)
- Payment amount correct

**Expected Results:**
- `PaymentTransaction` record created (NO penalty flag)
- Order status updated to `PAID`
- Items marked as sold
- Items delivered immediately
- User notified of successful payment
- **NO penalty applied** (purchase completed = no opportunity cost)

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_late_payment_accepted -v

# Manual
python tests/payment/manual/simulate_payment_webhook.py \
  --invoice-number INV-2025-ABC123 \
  --amount-paid 0.001 \
  --amount-required 0.001 \
  --crypto BTC \
  --late
```

**Database Verification:**
```sql
SELECT o.status, pt.is_late_payment, pt.penalty_applied, o.expires_at, pt.received_at
FROM orders o
JOIN invoices i ON i.order_id = o.id
JOIN payment_transactions pt ON pt.invoice_id = i.id
WHERE o.id = ?;
-- Expected: status='PAID', is_late_payment=1, penalty_applied=0
-- received_at > expires_at (payment late but accepted)
```

---

### ✅ Scenario 10: Expired Order Access

**Trigger:** User navigates to payment page for expired/finalized order

**Preconditions:**
- Order status: `TIMEOUT`, `CANCELLED_BY_USER`, `CANCELLED_BY_ADMIN`, `CANCELLED_BY_SYSTEM`, or `PAID`
- User tries to access order payment screen

**Expected Results:**
- User redirected to cart
- Error message: "This order has expired and can no longer be processed"
- No invoice renewal possible
- User must create new order

**Test Commands:**
```bash
# Automated
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_expired_order_access -v

# Manual
# 1. Create order and let it timeout (or cancel it)
# 2. Try to navigate back to order payment screen
# 3. Verify error message and redirect to cart
```

**Code Verification:**
```python
# handlers/user/order.py:process_payment()
# Lines 514-529: Check order status before processing
assert order.status not in [
    OrderStatus.TIMEOUT,
    OrderStatus.CANCELLED_BY_USER,
    OrderStatus.CANCELLED_BY_ADMIN,
    OrderStatus.CANCELLED_BY_SYSTEM,
    OrderStatus.PAID
]
```

---

## Soft-Delete Verification

### Test: Active Invoices Only

**Query:**
```python
invoice = await InvoiceRepository.get_by_order_id(
    order_id,
    session,
    include_inactive=False  # Default
)
```

**Expected:** Returns `None` for cancelled/expired orders

### Test: All Invoices (Audit Trail)

**Query:**
```python
invoices = await InvoiceRepository.get_all_by_order_id(
    order_id,
    session,
    include_inactive=True
)
```

**Expected:** Returns ALL invoices including inactive ones for complete history

---

## Configuration Testing

Test with different config values:

```bash
# Test with short timeout (faster testing)
export ORDER_TIMEOUT_MINUTES=2
export ORDER_CANCEL_GRACE_PERIOD_MINUTES=1
pytest tests/payment/unit/test_invoice_lifecycle.py -v

# Test with no grace period
export ORDER_CANCEL_GRACE_PERIOD_MINUTES=0
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_user_cancellation_with_penalty -v

# Test with high penalty
export PAYMENT_LATE_PENALTY_PERCENT=10.0
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_user_cancellation_with_penalty -v
```

---

## Regression Testing

After code changes, run full suite:

```bash
# Run all invoice lifecycle tests
pytest tests/payment/unit/test_invoice_lifecycle.py -v

# Run with coverage
pytest tests/payment/unit/test_invoice_lifecycle.py --cov=services --cov=repositories --cov-report=term-missing

# Check for untested scenarios
pytest tests/payment/unit/test_invoice_lifecycle.py --cov=services --cov-report=html
open htmlcov/index.html
```

---

## Migration Testing

Before running tests, ensure migration is applied:

```bash
# Check if migration 009 is applied
sqlite3 data/database.db "PRAGMA table_info(invoices);" | grep is_active

# If not found, run migration
sqlite3 data/database.db < migrations/009_add_invoice_is_active.sql

# Verify migration
sqlite3 data/database.db "SELECT COUNT(*) FROM invoices WHERE is_active = 0;"
```

---

## Debugging Failed Tests

### View test logs
```bash
pytest tests/payment/unit/test_invoice_lifecycle.py -v -s --log-cli-level=DEBUG
```

### Run single test with debugging
```bash
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_wallet_only_payment -v -s --pdb
```

### Check database state after test
```python
# In test file, add breakpoint:
import pdb; pdb.set_trace()

# Then query database:
result = await session.execute(select(Invoice).where(Invoice.order_id == order_id))
invoice = result.scalar_one_or_none()
print(f"Invoice: {invoice}")
```

---

## Performance Testing

Test with large datasets:

```bash
# Test with 100 concurrent orders
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_concurrent_orders -v

# Test timeout job with 1000 expired orders
pytest tests/payment/unit/test_invoice_lifecycle.py::TestInvoiceLifecycle::test_timeout_job_performance -v
```

---

## Next Steps

1. ✅ Run migration 009
2. ✅ Run automated tests: `pytest tests/payment/unit/test_invoice_lifecycle.py -v`
3. ✅ Verify all tests pass
4. ✅ Run manual integration tests (optional)
5. ✅ Update KryptoExpress API key
6. ✅ Test in production with small real payment
