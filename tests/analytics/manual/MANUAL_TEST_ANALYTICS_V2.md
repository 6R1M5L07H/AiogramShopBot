# Manual Test Guide - Analytics v2 System

**Feature**: Analytics v2 - Anonymized Sales & Violation Tracking
**Branch**: `feature/analytics-v2-admin-menu`
**Test Environment**: Development with ngrok disabled
**Prerequisites**: Bot running, Admin access, Test database

---

## Table of Contents

1. [Setup](#setup)
2. [Test Scenario 1: Order Completion → SalesRecord Creation](#test-scenario-1-order-completion--salesrecord-creation)
3. [Test Scenario 2: Payment Violations → ViolationStatistics](#test-scenario-2-payment-violations--violationstatistics)
4. [Test Scenario 3: Admin Panel - Sales Analytics](#test-scenario-3-admin-panel---sales-analytics)
5. [Test Scenario 4: Admin Panel - Violation Analytics](#test-scenario-4-admin-panel---violation-analytics)
6. [Test Scenario 5: CSV Export](#test-scenario-5-csv-export)
7. [Test Scenario 6: Data Minimization Verification](#test-scenario-6-data-minimization-verification)
8. [Test Scenario 7: Refund Handling](#test-scenario-7-refund-handling)
9. [Test Scenario 8: Mixed Orders (Physical + Digital)](#test-scenario-8-mixed-orders-physical--digital)
10. [SQL Verification Queries](#sql-verification-queries)
11. [Troubleshooting](#troubleshooting)

---

## Setup

### 1. Database Preparation

```bash
# Ensure analytics tables exist
python migrations/add_sales_analytics_tables.py

# Verify tables created
sqlite3 data/bot_database.db "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('sales_records', 'violation_statistics');"
```

Expected output:
```
sales_records
violation_statistics
```

### 2. Check Configuration

```bash
# Verify environment variables
grep -E "DATA_RETENTION_DAYS|PAYMENT_.*_PENALTY" .env
```

Expected:
```
DATA_RETENTION_DAYS=30
PAYMENT_UNDERPAYMENT_PENALTY_PERCENT=5.0
PAYMENT_LATE_PENALTY_PERCENT=5.0
```

### 3. Start Bot

```bash
# Start bot (no docker, no ngrok on this machine!)
python run.py
```

Check logs for:
```
✅ [run.py] Handlers registered with dispatcher
[Startup] Data retention cleanup job started
```

### 4. Prepare Test Data

Create test items in your catalog:
- **Category**: "Test Category"
- **Subcategory**: "Test Digital" (digital items)
- **Subcategory**: "Test Physical" (physical items with price)
- Add at least 5-10 test items to each subcategory

---

## Test Scenario 1: Order Completion → SalesRecord Creation

### Objective
Verify that SalesRecord entries are created when an order is completed (PAID status).

### Steps

#### 1.1 Create Order with Digital Items

1. Open bot as regular user
2. Navigate to "Test Digital" subcategory
3. Add 3 digital items to cart (different prices if possible)
4. Click "Create Order" → Note the **Order ID** from invoice
5. Proceed to payment screen
6. Complete payment (use wallet if balance available, or crypto)

#### 1.2 Verify SalesRecords Created

**Check Logs:**
```
✅ Created 3 SalesRecord entries for order {order_id}
```

**Check Database:**
```sql
-- Replace {order_id} with actual order ID
SELECT
    id,
    sale_date,
    sale_hour,
    category_name,
    subcategory_name,
    quantity,
    item_total_price,
    payment_method,
    is_physical,
    is_refunded
FROM sales_records
WHERE order_total_price = (
    SELECT total_price FROM orders WHERE id = {order_id}
);
```

**Expected Results:**
- ✅ 3 rows returned (one per item)
- ✅ `category_name` = "Test Category"
- ✅ `subcategory_name` = "Test Digital"
- ✅ `quantity` = 1 (for each record)
- ✅ `is_physical` = 0 (false)
- ✅ `is_refunded` = 0 (false)
- ✅ `sale_date` = today's date
- ✅ `sale_hour` = current hour (0-23)
- ✅ `payment_method` = "wallet_only" | "crypto_only" | "mixed"

#### 1.3 Verify Data Minimization

```sql
-- This query should FAIL (no user_id column exists)
SELECT user_id FROM sales_records LIMIT 1;
```

**Expected Result:**
```
Error: no such column: user_id
```

✅ **Pass Criteria**: 3 SalesRecords created, no user_id column exists

---

## Test Scenario 2: Payment Violations → ViolationStatistics

### Objective
Verify that ViolationStatistics are created for payment violations.

### 2.1 Simulate Underpayment (Final)

**Setup:**
1. Create new order (note Order ID)
2. Get payment invoice with crypto amount

**Simulate Webhook:**
```bash
# Use simulate_payment_webhook.py
# Modify to send UNDERPAYMENT twice for same order
python tests/payment/manual/simulate_payment_webhook.py
```

Follow prompts:
- Order ID: {your_order_id}
- Send first underpayment → retry allowed
- Send second underpayment → penalty applied

**Check Logs:**
```
[Analytics] ✅ Created ViolationStatistics entry (type=ViolationType.UNDERPAYMENT_FINAL, order={order_id}, penalty={amount})
```

**Verify Database:**
```sql
SELECT
    id,
    violation_date,
    violation_type,
    order_value,
    penalty_applied,
    retry_count
FROM violation_statistics
WHERE violation_type = 'UNDERPAYMENT_FINAL'
ORDER BY id DESC LIMIT 1;
```

**Expected Results:**
- ✅ 1 row created
- ✅ `violation_type` = "UNDERPAYMENT_FINAL"
- ✅ `penalty_applied` > 0 (5% of order value)
- ✅ `retry_count` = 1 (second attempt)
- ✅ `order_value` matches order total

### 2.2 Simulate Late Payment

**Note**: This requires manual timing control. For testing, you can:
1. Create order
2. Reduce `PAYMENT_LATE_THRESHOLD_SECONDS` in config temporarily (e.g., to 60 seconds)
3. Wait for grace period to expire
4. Complete payment after threshold

**Alternatively**, use database manipulation:
```sql
-- Manually set order creation time to past
UPDATE orders
SET created_at = datetime('now', '-20 minutes')
WHERE id = {order_id};
```

Then complete payment normally.

**Verify Database:**
```sql
SELECT
    violation_type,
    penalty_applied
FROM violation_statistics
WHERE violation_type = 'LATE_PAYMENT'
ORDER BY id DESC LIMIT 1;
```

**Expected**: 1 row with `LATE_PAYMENT` and penalty amount

✅ **Pass Criteria**: ViolationStatistics entries created for violations

---

## Test Scenario 3: Admin Panel - Sales Analytics

### Objective
Verify Sales Analytics admin interface displays data correctly.

### Steps

#### 3.1 Access Analytics Menu

1. Open bot as Admin user
2. Click "Admin Menu" → "📊 Analytics v2"
3. Expected: Analytics v2 menu with buttons:
   - "💰 Sales Analytics"
   - "⚠️ Violation Analytics"
   - "🔙 Back to Admin Menu"

#### 3.2 Navigate to Sales Analytics

1. Click "💰 Sales Analytics"
2. Expected: Time range selection:
   - "Last 7 Days"
   - "Last 30 Days"
   - "Last 90 Days"
   - "🔙 Zurück zu Analytics"

#### 3.3 View 7-Day Sales Report

1. Click "Last 7 Days"
2. Expected report format:

```
📊 Subcategory Sales Report - Last 7 Days
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 Test Category > Test Digital
  13.11: 3 Stück (45,00 €)
  Gesamt: 3 Stück (45,00 €)

[Seite 1 von 1]
```

**Verify:**
- ✅ Title shows correct time range
- ✅ Subcategories sorted by revenue (highest first)
- ✅ Daily breakdown shows only days WITH sales
- ✅ Date format: "DD.MM"
- ✅ Quantity and revenue displayed correctly
- ✅ Category emoji displayed (📦 or specific emoji)
- ✅ Subtotal line shows "Gesamt:"
- ✅ Pagination info at bottom

#### 3.4 Test Pagination (if >8 subcategories)

**Setup**: Create orders in 10+ different subcategories

1. Navigate to Sales Analytics → Last 30 Days
2. Expected: Page 1 shows 8 subcategories + "Weiter ▶" button
3. Click "Weiter ▶"
4. Expected: Page 2 shows remaining subcategories + "◀ Zurück" button
5. Click "◀ Zurück"
6. Expected: Back to page 1

**Verify:**
- ✅ Pagination works forward/backward
- ✅ Page indicator updates: "[Seite X von Y]"
- ✅ First page: No "◀ Zurück" button
- ✅ Last page: No "Weiter ▶" button

#### 3.5 Test Different Time Ranges

1. Go back to overview (🔙 Zurück zur Übersicht)
2. Click "Last 30 Days"
3. Verify: More data shown (if orders exist in that range)
4. Repeat for "Last 90 Days"

**Verify:**
- ✅ Time ranges filter correctly
- ✅ Revenue totals change based on range
- ✅ Navigation buttons work from all views

✅ **Pass Criteria**: Sales Analytics displays data correctly with pagination

---

## Test Scenario 4: Admin Panel - Violation Analytics

### Objective
Verify Violation Analytics displays violation statistics correctly.

### Steps

#### 4.1 Access Violation Analytics

1. Admin Menu → Analytics v2 → "⚠️ Violation Analytics"
2. Expected: Time range selection (7/30/90 days)

#### 4.2 View Violation Statistics

1. Click "Last 30 Days"
2. Expected report format:

```
⚠️ Violation Statistics - Last 30 Days
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Violation Breakdown:

Payment Timeout: 2 violations
Late Payment: 1 violations
Underpayment (Final): 1 violations
Late Cancellation: 0 violations

💰 Total Penalties Collected: 12,50 €

🔝 Top Violations:
1. Payment Timeout (2x)
2. Underpayment (Final) (1x)
3. Late Payment (1x)

[Zeitraum: 14.10 - 13.11]
```

**Verify:**
- ✅ All violation types listed (even with 0 count)
- ✅ Counts match database records
- ✅ Total penalties sum correct
- ✅ Top violations sorted by count (descending)
- ✅ Date range displayed correctly
- ✅ Currency symbol displayed

#### 4.3 Test Different Time Ranges

1. Back to overview
2. Click "Last 7 Days"
3. Verify: Only violations from last 7 days shown
4. Verify: Penalty total changes accordingly

**Verify:**
- ✅ Filters work correctly
- ✅ Empty ranges show "No violations found" (if applicable)

✅ **Pass Criteria**: Violation Analytics displays correctly

---

## Test Scenario 5: CSV Export

### Objective
Verify CSV export generates and delivers file correctly.

### Steps

#### 5.1 Generate CSV

1. Navigate to: Sales Analytics → Last 30 Days (any subcategory report)
2. Click "📄 CSV Export"
3. Expected: Loading message: "⏳ CSV wird generiert..."
4. Expected: File delivered as Telegram Document

**Verify Message:**
- ✅ Caption: "✅ CSV Export abgeschlossen!"
- ✅ Filename: `sales_export_YYYYMMDD_HHMMSS.csv`
- ✅ Automatically returns to Sales Analytics Overview

#### 5.2 Verify CSV Content

Download file and open in text editor or Excel.

**Expected Header:**
```csv
date,hour,weekday,category,subcategory,quantity,is_physical,item_total_price,currency,payment_method,crypto_currency,status
```

**Expected Data Row Example:**
```csv
2025-11-13,14,2,Test Category,Test Digital,1,False,15.0,EUR,wallet_only,,PAID
```

**Verify:**
- ✅ Header matches specification
- ✅ All sales records included (not just current time range!)
- ✅ Comma-separated format
- ✅ UTF-8 encoding (German umlauts display correctly)
- ✅ Dates in ISO format (YYYY-MM-DD)
- ✅ Boolean values as "True"/"False"
- ✅ Empty fields for nullable columns (crypto_currency if wallet_only)

#### 5.3 Test with Large Dataset

**Setup**: Create 100+ sales records (via script or manual orders)

1. Generate CSV export
2. Expected: File generates within 10 seconds
3. File size < 5 MB (Telegram limit)
4. All records included

✅ **Pass Criteria**: CSV export works correctly

---

## Test Scenario 6: Data Minimization Verification

### Objective
Ensure NO user identification exists in analytics tables.

### Steps

#### 6.1 Schema Inspection

```sql
-- Check sales_records schema
PRAGMA table_info(sales_records);
```

**Verify:**
- ✅ NO `user_id` column
- ✅ NO `telegram_id` column
- ✅ NO `telegram_username` column

```sql
-- Check violation_statistics schema
PRAGMA table_info(violation_statistics);
```

**Verify:**
- ✅ NO user-identifying columns

#### 6.2 Data Content Verification

```sql
-- Check for any PII leakage in text fields
SELECT
    category_name,
    subcategory_name,
    payment_method,
    shipping_type
FROM sales_records
LIMIT 10;
```

**Verify:**
- ✅ No usernames in any field
- ✅ No addresses in any field
- ✅ Only product/financial data

#### 6.3 Join Attempt (Should Fail)

```sql
-- Attempt to join sales_records with users (should fail)
SELECT s.*, u.telegram_username
FROM sales_records s
LEFT JOIN users u ON s.user_id = u.id
LIMIT 1;
```

**Expected Error:**
```
Error: no such column: s.user_id
```

✅ **Pass Criteria**: Zero user identification in analytics tables

---

## Test Scenario 7: Refund Handling

### Objective
Verify refunded orders are marked correctly in analytics.

### Steps

#### 7.1 Create Order and Cancel After Payment

1. Create order with 2 digital items
2. Complete payment (order status = PAID)
3. Verify SalesRecords created (2 rows, `is_refunded=0`)
4. **Admin Action**: Cancel order manually (simulate refund)

**Expected Logs:**
```
[Analytics] Marked 2 items as refunded for order {order_id}
```

#### 7.2 Verify Refund Flag

```sql
SELECT
    id,
    subcategory_name,
    item_total_price,
    is_refunded
FROM sales_records
WHERE order_total_price = (
    SELECT total_price FROM orders WHERE id = {order_id}
);
```

**Expected Results:**
- ✅ 2 rows with `is_refunded = 1` (true)

#### 7.3 Verify Revenue Calculation Excludes Refunds

```sql
SELECT
    SUM(item_total_price) as total_revenue
FROM sales_records
WHERE is_refunded = 0
AND sale_date >= date('now', '-7 days');
```

**Verify:**
- ✅ Refunded items NOT included in revenue sum
- ✅ Admin panel shows correct revenue (excluding refunds)

✅ **Pass Criteria**: Refunds marked correctly and excluded from revenue

---

## Test Scenario 8: Mixed Orders (Physical + Digital)

### Objective
Verify analytics handles mixed orders correctly.

### Steps

#### 8.1 Create Mixed Order

1. Add 2 digital items to cart
2. Add 1 physical item to cart
3. Create order → Enter shipping address
4. Complete payment

#### 8.2 Verify SalesRecords

```sql
SELECT
    subcategory_name,
    is_physical,
    item_total_price,
    order_shipping_cost
FROM sales_records
WHERE order_total_price = (
    SELECT total_price FROM orders WHERE id = {order_id}
);
```

**Expected Results:**
- ✅ 3 rows total
- ✅ 2 rows with `is_physical = 0` (digital)
- ✅ 1 row with `is_physical = 1` (physical)
- ✅ All rows have `order_shipping_cost` > 0 (denormalized from order)

#### 8.3 Verify Payment Method

**If paid with wallet only:**
- ✅ `payment_method = "wallet_only"`
- ✅ `crypto_currency = NULL`

**If paid with crypto only:**
- ✅ `payment_method = "crypto_only"`
- ✅ `crypto_currency = "BTC" | "ETH" | ...`

**If paid with both:**
- ✅ `payment_method = "mixed"`
- ✅ `crypto_currency = <used currency>`

✅ **Pass Criteria**: Mixed orders tracked correctly

---

## SQL Verification Queries

### Query 1: Total Revenue (Last 30 Days)

```sql
SELECT
    SUM(item_total_price) as total_revenue,
    COUNT(*) as items_sold,
    COUNT(DISTINCT order_total_price) as orders_count
FROM sales_records
WHERE is_refunded = 0
AND sale_date >= date('now', '-30 days');
```

### Query 2: Revenue by Category

```sql
SELECT
    category_name,
    SUM(item_total_price) as revenue,
    COUNT(*) as items_sold
FROM sales_records
WHERE is_refunded = 0
AND sale_date >= date('now', '-30 days')
GROUP BY category_name
ORDER BY revenue DESC;
```

### Query 3: Sales by Hour of Day

```sql
SELECT
    sale_hour,
    COUNT(*) as sales_count,
    SUM(item_total_price) as revenue
FROM sales_records
WHERE is_refunded = 0
AND sale_date >= date('now', '-7 days')
GROUP BY sale_hour
ORDER BY sale_hour;
```

### Query 4: Physical vs Digital Split

```sql
SELECT
    CASE WHEN is_physical = 1 THEN 'Physical' ELSE 'Digital' END as type,
    COUNT(*) as items_sold,
    SUM(item_total_price) as revenue
FROM sales_records
WHERE is_refunded = 0
AND sale_date >= date('now', '-30 days')
GROUP BY is_physical;
```

### Query 5: Payment Method Distribution

```sql
SELECT
    payment_method,
    COUNT(*) as count,
    SUM(item_total_price) as revenue
FROM sales_records
WHERE is_refunded = 0
AND sale_date >= date('now', '-30 days')
GROUP BY payment_method;
```

### Query 6: Violation Summary

```sql
SELECT
    violation_type,
    COUNT(*) as count,
    SUM(penalty_applied) as total_penalties,
    AVG(order_value) as avg_order_value
FROM violation_statistics
WHERE violation_date >= date('now', '-30 days')
GROUP BY violation_type
ORDER BY count DESC;
```

---

## Troubleshooting

### Issue: SalesRecords Not Created

**Symptoms**: Order completed but no SalesRecords in database

**Debug Steps:**

1. Check logs for errors:
```bash
grep -i "analytics" logs/bot.log | tail -20
```

2. Verify migration ran:
```sql
SELECT name FROM sqlite_master WHERE type='table' AND name='sales_records';
```

3. Verify items exist:
```sql
SELECT COUNT(*) FROM items WHERE order_id = {order_id};
```

4. Check order status:
```sql
SELECT id, status FROM orders WHERE id = {order_id};
```

**Expected**: Status should be "PAID" for SalesRecords creation

### Issue: Admin Panel Shows "No Data"

**Possible Causes:**
- No orders completed yet
- Time range filter excludes all data
- Database query error

**Debug:**
```sql
-- Check if sales_records has data
SELECT COUNT(*) FROM sales_records;

-- Check date range
SELECT MIN(sale_date), MAX(sale_date) FROM sales_records;
```

### Issue: CSV Export Fails

**Check:**
1. Logs for errors during CSV generation
2. Telegram file size limit (5 MB)
3. Permissions on temp directory

### Issue: Violation Not Tracked

**Debug:**
```python
# Check violation type enum
from enums.violation_type import ViolationType
print(list(ViolationType))
```

Expected output:
```
[<ViolationType.UNDERPAYMENT_FIRST>, <ViolationType.UNDERPAYMENT_FINAL>, ...]
```

---

## Test Results Template

### Test Execution Summary

**Date**: ___________
**Tester**: ___________
**Bot Version**: ___________
**Branch**: `feature/analytics-v2-admin-menu`

| Scenario | Status | Notes |
|----------|--------|-------|
| 1. Order Completion → SalesRecord | ⬜ Pass / ⬜ Fail | |
| 2. Payment Violations → Statistics | ⬜ Pass / ⬜ Fail | |
| 3. Admin Panel - Sales Analytics | ⬜ Pass / ⬜ Fail | |
| 4. Admin Panel - Violation Analytics | ⬜ Pass / ⬜ Fail | |
| 5. CSV Export | ⬜ Pass / ⬜ Fail | |
| 6. Data Minimization | ⬜ Pass / ⬜ Fail | |
| 7. Refund Handling | ⬜ Pass / ⬜ Fail | |
| 8. Mixed Orders | ⬜ Pass / ⬜ Fail | |

**Critical Issues Found:**
1.
2.
3.

**Minor Issues Found:**
1.
2.
3.

**Overall Assessment**: ⬜ Ready for Production / ⬜ Needs Fixes

---

## Additional Notes

- All SQL queries assume SQLite database
- For production testing, ensure real payment flow (not simulated)
- Test with multiple users for concurrent access patterns
- Monitor performance with 1000+ records
- Verify logs don't contain PII leakage

---

## Related Documentation

- Feature README: `docs/features/analytics-data-retention/README.md`
- Test Cases: `docs/features/analytics-data-retention/TEST_CASES.md`
- Unit Tests: `tests/analytics/unit/`
- Migration: `migrations/add_sales_analytics_tables.py`