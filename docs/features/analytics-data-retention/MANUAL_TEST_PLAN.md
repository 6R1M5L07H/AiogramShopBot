# Analytics & Data Retention - Manual Test Plan

**Feature**: Anonymized Analytics System with Data Retention
**Date**: 2025-11-11
**Version**: 1.0
**Tester**: [Name]
**Test Date**: [Date]
**Environment**: [Dev/Staging/Production]

---

## Pre-Test Setup

### Database Setup
1. Backup production database before testing
2. Run migration: `python migrations/add_sales_analytics_tables.py`
3. Verify tables created:
   ```sql
   SELECT name FROM sqlite_master WHERE type='table' AND name IN ('sales_records', 'violation_statistics');
   ```
4. Verify indexes created (6 total: 4 for sales_records, 2 for violation_statistics)

### Bot Configuration
1. Verify `DATA_RETENTION_DAYS` configured in config (default: 30)
2. Verify `REFERRAL_DATA_RETENTION_DAYS` configured (default: 365)
3. Check bot.py startup logs for: `[Startup] Data retention cleanup job started`

---

## Test Case 1: Order Completion Creates SalesRecords

**Objective**: Verify that completing an order creates anonymized SalesRecords

### Steps:
1. Create new test user (record user_id for verification)
2. Add 2 items to cart (1 physical, 1 digital)
3. Create order
4. Complete payment (crypto or wallet)
5. Wait for order to reach PAID status

### Verification:
1. Check database:
   ```sql
   SELECT COUNT(*) FROM sales_records;
   ```
   **Expected**: 2 new records

2. Verify SalesRecord data:
   ```sql
   SELECT
     category_name, subcategory_name, quantity, is_physical,
     item_total_price, currency, payment_method, crypto_currency,
     status, is_refunded, shipping_type
   FROM sales_records
   ORDER BY created_at DESC
   LIMIT 2;
   ```
   **Expected**:
   - ✅ No user_id column exists
   - ✅ category_name and subcategory_name populated
   - ✅ quantity = 1 for each record
   - ✅ is_physical correct for each item
   - ✅ payment_method = "wallet_only", "crypto_only", or "mixed"
   - ✅ status = "PAID"
   - ✅ is_refunded = 0
   - ✅ shipping_type populated for physical items

3. Verify temporal data:
   ```sql
   SELECT sale_date, sale_hour, sale_weekday FROM sales_records ORDER BY created_at DESC LIMIT 1;
   ```
   **Expected**:
   - ✅ sale_date matches today
   - ✅ sale_hour between 0-23
   - ✅ sale_weekday between 0-6 (0=Monday)

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 2: Wallet-Only Payment Tracking

**Objective**: Verify wallet-only orders tracked correctly

### Steps:
1. Create test user with wallet balance
2. Add item to cart (price ≤ wallet balance)
3. Create order
4. Complete payment using only wallet

### Verification:
```sql
SELECT payment_method, crypto_currency, order_wallet_used
FROM sales_records
ORDER BY created_at DESC
LIMIT 1;
```
**Expected**:
- ✅ payment_method = "wallet_only"
- ✅ crypto_currency = NULL
- ✅ order_wallet_used > 0

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 3: Second Underpayment Creates Violation

**Objective**: Verify UNDERPAYMENT_FINAL violation is tracked

### Steps:
1. Create order with crypto payment
2. Send partial payment (underpayment #1)
3. Wait for retry deadline extension
4. Send partial payment again (underpayment #2)
5. Order should be cancelled with penalty

### Verification:
```sql
SELECT violation_type, order_value, penalty_applied, retry_count
FROM violation_statistics
ORDER BY created_at DESC
LIMIT 1;
```
**Expected**:
- ✅ violation_type = "underpayment_final"
- ✅ order_value matches order total
- ✅ penalty_applied = 5% of total paid
- ✅ retry_count = 1

**Check no user_id**:
```sql
PRAGMA table_info(violation_statistics);
```
**Expected**: No user_id column

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 4: Late Payment Creates Violation

**Objective**: Verify LATE_PAYMENT violation is tracked

### Steps:
1. Create order with 5-minute timeout (adjust config for testing)
2. Wait for order to expire (status = TIMEOUT)
3. Send payment after expiry

### Verification:
```sql
SELECT violation_type, order_value, penalty_applied
FROM violation_statistics
WHERE violation_type = 'late_payment'
ORDER BY created_at DESC
LIMIT 1;
```
**Expected**:
- ✅ violation_type = "late_payment"
- ✅ penalty_applied = 5% of payment amount

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 5: Order Timeout Creates Violation

**Objective**: Verify TIMEOUT violation is tracked

### Steps:
1. Create order
2. Do NOT send payment
3. Wait for order to expire automatically

### Verification:
```sql
SELECT violation_type, order_value, penalty_applied
FROM violation_statistics
WHERE violation_type = 'timeout'
ORDER BY created_at DESC
LIMIT 1;
```
**Expected**:
- ✅ violation_type = "timeout"
- ✅ penalty_applied = 0.0

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 6: User Cancellation Late Creates Violation

**Objective**: Verify USER_CANCELLATION_LATE violation is tracked

### Steps:
1. Create order
2. Wait for grace period to expire (default: 5 minutes)
3. User cancels order via bot

### Verification:
```sql
SELECT violation_type, order_value, penalty_applied
FROM violation_statistics
WHERE violation_type = 'user_cancellation_late'
ORDER BY created_at DESC
LIMIT 1;
```
**Expected**:
- ✅ violation_type = "user_cancellation_late"
- ✅ penalty_applied > 0 (if wallet used)

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 7: Data Retention Job Execution

**Objective**: Verify data retention job runs and deletes old data correctly

### Steps:
1. Create test orders with modified created_at (31+ days old)
2. Create SalesRecords for those orders
3. Manually trigger data retention job:
   ```bash
   python -m jobs.data_retention_cleanup_job
   ```

### Verification:
1. Check logs for successful execution:
   ```
   [Data Retention] Starting daily cleanup job
   [Data Retention] Order retention: 30 days
   [Data Retention] ✅ Deleted X orders older than 30 days
   [Data Retention] ✅ Daily cleanup completed successfully
   ```

2. Verify orders deleted:
   ```sql
   SELECT COUNT(*) FROM orders WHERE created_at < date('now', '-30 days');
   ```
   **Expected**: 0

3. **CRITICAL** - Verify SalesRecords NOT deleted:
   ```sql
   SELECT COUNT(*) FROM sales_records WHERE sale_date < date('now', '-30 days');
   ```
   **Expected**: > 0 (sales records remain)

4. **CRITICAL** - Verify ViolationStatistics NOT deleted:
   ```sql
   SELECT COUNT(*) FROM violation_statistics WHERE violation_date < date('now', '-30 days');
   ```
   **Expected**: > 0 (violation stats remain)

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 8: Analytics Query Performance

**Objective**: Verify analytics queries perform acceptably

### Steps:
1. Populate database with 1000+ SalesRecords
2. Run analytics queries:

```sql
-- Total revenue last 30 days
SELECT SUM(item_total_price) FROM sales_records
WHERE sale_date >= date('now', '-30 days');

-- Total items sold last 7 days
SELECT SUM(quantity) FROM sales_records
WHERE sale_date >= date('now', '-7 days');

-- Revenue by category (last 30 days)
SELECT category_name, SUM(item_total_price) as revenue
FROM sales_records
WHERE sale_date >= date('now', '-30 days')
GROUP BY category_name
ORDER BY revenue DESC;

-- Violation count by type (last 30 days)
SELECT violation_type, COUNT(*) as count
FROM violation_statistics
WHERE violation_date >= date('now', '-30 days')
GROUP BY violation_type;
```

### Verification:
- ✅ Each query completes in < 1 second
- ✅ Results are accurate
- ✅ Indexes are being used (check EXPLAIN QUERY PLAN)

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 9: Bot Startup with Data Retention Job

**Objective**: Verify data retention job starts automatically on bot startup

### Steps:
1. Stop bot if running
2. Start bot: `python run.py`
3. Monitor startup logs

### Verification:
Check for log messages:
```
[Startup] Data retention cleanup job started
```

Verify job is running:
```bash
# Check bot process logs
tail -f logs/bot.log | grep "Data Retention"
```

Wait 24 hours or check job runs at midnight (if scheduled).

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 10: Service Layer Isolation

**Objective**: Verify AnalyticsService has no Telegram dependencies

### Steps:
1. Inspect source code:
   ```bash
   grep -r "from aiogram\|from telegram\|bot\.\|dp\." services/analytics.py
   grep -r "from aiogram\|from telegram\|bot\.\|dp\." repositories/sales_record.py
   grep -r "from aiogram\|from telegram\|bot\.\|dp\." repositories/violation_statistics.py
   ```

### Verification:
**Expected**: No matches (exit code 1)

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 11: Analytics Failure Doesn't Break Order Flow

**Objective**: Verify order completion succeeds even if analytics fails

### Steps:
1. Temporarily break analytics (e.g., rename sales_records table)
2. Create and complete an order
3. Verify order reaches PAID status despite analytics failure

### Verification:
1. Check order status:
   ```sql
   SELECT status FROM orders ORDER BY created_at DESC LIMIT 1;
   ```
   **Expected**: status = "PAID"

2. Check logs for analytics error (should be logged but not propagate):
   ```
   ❌ Failed to create SalesRecords for order X: [error]
   ```

3. Restore analytics table

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 12: Data Minimization Verification

**Objective**: **CRITICAL** - Verify no user_id in analytics tables

### Steps:
1. Complete 10 orders with different users
2. Inspect database schema and data

### Verification:
```sql
-- Check table structure
PRAGMA table_info(sales_records);
PRAGMA table_info(violation_statistics);

-- Verify no user_id column exists
SELECT COUNT(*) FROM pragma_table_info('sales_records') WHERE name='user_id';
SELECT COUNT(*) FROM pragma_table_info('violation_statistics') WHERE name='user_id';
```
**Expected**: Both queries return 0

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 13: Order Completion Creates SalesRecords (Integration)

**Objective**: Verify end-to-end flow from order completion to SalesRecord creation

### Steps:
1. Create test user and add 2 items to cart (1 physical, 1 digital)
2. Complete order with mixed payment (wallet + crypto)
3. Wait for order to reach PAID status
4. Check logs for analytics service execution

### Verification:
```sql
-- Check SalesRecords created
SELECT COUNT(*) FROM sales_records
WHERE created_at >= datetime('now', '-5 minutes');
```
**Expected**: 2 records (one per item)

```sql
-- Verify item details
SELECT
    category_name,
    subcategory_name,
    is_physical,
    payment_method,
    crypto_currency,
    order_wallet_used
FROM sales_records
WHERE created_at >= datetime('now', '-5 minutes')
ORDER BY id DESC
LIMIT 2;
```
**Expected**:
- ✅ Both records have correct category/subcategory
- ✅ is_physical matches item types (True, False)
- ✅ payment_method = "mixed"
- ✅ crypto_currency populated
- ✅ order_wallet_used > 0

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 14: Multiple Payment Methods Tracking

**Objective**: Verify correct payment_method detection for different scenarios

### Steps:
1. **Scenario A**: Create order, pay 100% with wallet
   - Verify: payment_method = "wallet_only", crypto_currency = NULL
2. **Scenario B**: Create order, pay 100% with crypto
   - Verify: payment_method = "crypto_only", crypto_currency = BTC/ETH/etc
3. **Scenario C**: Create order, pay 50% wallet + 50% crypto
   - Verify: payment_method = "mixed", crypto_currency populated

### Verification:
```sql
SELECT
    payment_method,
    crypto_currency,
    order_wallet_used,
    order_total_price
FROM sales_records
WHERE created_at >= datetime('now', '-10 minutes')
ORDER BY id DESC;
```

**Expected**:
- ✅ Wallet-only: payment_method="wallet_only", crypto_currency=NULL
- ✅ Crypto-only: payment_method="crypto_only", crypto_currency set
- ✅ Mixed: payment_method="mixed", both fields populated

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 15: Refund Handling and Analytics Update

**Objective**: Verify is_refunded flag updates when orders are refunded

### Steps:
1. Create and complete order (status = PAID)
2. Verify SalesRecords created with is_refunded = 0
3. Refund the order (admin cancellation or user refund)
4. **Manual Update Required**: Update SalesRecords manually or via refund job
   ```sql
   UPDATE sales_records
   SET is_refunded = 1
   WHERE id IN (SELECT id FROM sales_records WHERE ...);
   ```
5. Verify refunded records excluded from revenue queries

### Verification:
```sql
-- Check is_refunded flag
SELECT id, is_refunded, status FROM sales_records
WHERE created_at >= datetime('now', '-10 minutes');
```

```sql
-- Verify revenue query excludes refunds
SELECT SUM(item_total_price) as revenue
FROM sales_records
WHERE sale_date >= date('now', '-7 days')
  AND is_refunded = 0;
```

**Expected**:
- ✅ is_refunded updated to 1
- ✅ Revenue queries exclude refunded records

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 16: High-Volume Order Processing (Performance)

**Objective**: Verify analytics can handle multiple concurrent orders

### Steps:
1. Create 10-20 orders simultaneously (use test script if available)
2. Complete all orders within 1 minute
3. Monitor logs for any errors or delays
4. Check database for all SalesRecords created

### Verification:
```sql
-- Count records created in test window
SELECT
    COUNT(*) as total_records,
    COUNT(DISTINCT category_name) as unique_categories,
    SUM(item_total_price) as total_revenue
FROM sales_records
WHERE created_at >= datetime('now', '-5 minutes');
```

**Expected**:
- ✅ All orders create SalesRecords (no missing records)
- ✅ No errors in logs
- ✅ Query performance remains acceptable (<1s)
- ✅ No duplicate records

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 17: Analytics Resilience (Exception Handling)

**Objective**: Verify analytics failures don't break order completion

### Steps:
1. **Simulate analytics failure** (e.g., temporarily rename sales_records table):
   ```sql
   ALTER TABLE sales_records RENAME TO sales_records_backup;
   ```
2. Create and complete an order
3. Check order reaches PAID status despite analytics failure
4. Check logs for error messages
5. Restore table:
   ```sql
   ALTER TABLE sales_records_backup RENAME TO sales_records;
   ```

### Verification:
```sql
-- Verify order completed successfully
SELECT id, status FROM orders
WHERE created_at >= datetime('now', '-5 minutes')
ORDER BY id DESC LIMIT 1;
```
**Expected**: status = "PAID"

**Logs Expected**:
```
❌ Failed to create SalesRecords for order X: [error message]
```

**Expected**:
- ✅ Order completes successfully
- ✅ Error logged but not propagated
- ✅ User sees no error message

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Test Case 18: Data Retention Verification (Integration)

**Objective**: **CRITICAL** - Verify SalesRecords persist after order deletion

### Steps:
1. Create and complete order (note order_id)
2. Verify SalesRecords created:
   ```sql
   SELECT COUNT(*) FROM sales_records
   WHERE order_total_price = <order_total>;
   ```
3. Wait for data retention period (or manually delete order):
   ```sql
   DELETE FROM orders WHERE id = <order_id>;
   ```
4. **CRITICAL**: Verify SalesRecords still exist:
   ```sql
   SELECT * FROM sales_records
   WHERE order_total_price = <order_total>;
   ```

### Verification:
**Expected**:
- ✅ Orders deleted after retention period
- ✅ SalesRecords remain in database (NO CASCADE DELETE)
- ✅ ViolationStatistics remain in database
- ✅ Revenue queries still work with old data

**Result**: ☐ PASS ☐ FAIL
**Notes**: _______________________

---

## Acceptance Criteria Summary

For feature to be considered production-ready:

### Core Functionality (Must Pass)
- ☐ All 18 manual test cases pass
- ☐ **CRITICAL**: No user_id in analytics tables (TC-12)
- ☐ **CRITICAL**: SalesRecords persist after order deletion (TC-7, TC-18)
- ☐ **CRITICAL**: ViolationStatistics persist after order deletion (TC-7)
- ☐ Data retention job runs automatically (TC-9)
- ☐ Analytics failures don't break orders (TC-11, TC-17)
- ☐ All 4 violation types tracked correctly (TC-3, TC-4, TC-5, TC-6)

### Integration & Performance (Must Pass)
- ☐ End-to-end order completion flow works (TC-13)
- ☐ All payment methods tracked correctly (TC-14)
- ☐ High-volume processing without errors (TC-16)
- ☐ Query performance acceptable (<1s for 1000+ records) (TC-8)

### Code Quality (Must Pass)
- ☐ Service layer has no Telegram dependencies (TC-10)
- ☐ All 21 unit tests pass (pytest tests/analytics/unit/)

### Optional (Nice to Have)
- ☐ Refund handling implemented (TC-15)

---

## Test Results

**Overall Status**: ☐ PASS ☐ FAIL

**Tester Signature**: _______________________

**Date**: _______________________

**Additional Notes**:
_____________________________________________
_____________________________________________
_____________________________________________