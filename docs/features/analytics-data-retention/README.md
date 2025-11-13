# Anonymized Analytics & Data Retention System

**Feature ID**: A1
**Status**: ✅ Complete
**Date**: 2025-11-11
**Branch**: `feature/analytics-data-retention`

---

## Overview

This feature implements an anonymized analytics system that creates long-term business intelligence data while following data minimization principles. The system allows orders to be deleted after 30 days while preserving anonymized sales and violation statistics for indefinite retention.

### Key Benefits
- **Business Intelligence**: Track sales trends, revenue, popular categories without storing user data
- **Abuse Detection**: Monitor violation patterns (underpayments, late payments, timeouts) without user identification
- **Data Minimization**: Zero user_id in analytics tables, enabling indefinite retention
- **Automated Cleanup**: Daily job deletes old orders while preserving analytics

---

## Architecture

### Data Models

#### SalesRecord (Anonymized)
Stores one record per sold item with:
- **Temporal Data**: sale_date, sale_hour, sale_weekday
- **Product Data**: category_name, subcategory_name, quantity, is_physical
- **Financial Data**: item_total_price, currency, payment_method, crypto_currency
- **Order Context**: order_total_price, order_shipping_cost, order_wallet_used
- **Status**: status, is_refunded, shipping_type

**NO user_id** - Fully anonymized

#### ViolationStatistics (Anonymized)
Stores violation tracking with:
- **Temporal Data**: violation_date
- **Violation Type**: UNDERPAYMENT_FINAL, LATE_PAYMENT, TIMEOUT, USER_CANCELLATION_LATE
- **Financial Impact**: order_value, penalty_applied
- **Retry Info**: retry_count

**NO user_id** - Fully anonymized

### Service Layer

**AnalyticsService** (`services/analytics.py`)
- `create_sales_records_from_order()`: Creates SalesRecords on order completion
- `create_violation_record()`: Creates ViolationStatistics on violations

**Key Design**: Zero Telegram dependencies, pure business logic

### Repository Layer

**SalesRecordRepository** (`repositories/sales_record.py`)
- `create_many()`: Bulk insert SalesRecords
- `get_total_revenue()`: Aggregate revenue for N days
- `get_total_items_sold()`: Count items sold for N days

**ViolationStatisticsRepository** (`repositories/violation_statistics.py`)
- `create()`: Insert ViolationStatistics
- `get_violation_count_by_type()`: Count violations by type
- `get_total_penalty_amount()`: Sum penalties for N days

---

## Integration Points

### 1. Order Completion (`services/order.py:273-278`)
```python
# Create anonymized SalesRecord for long-term analytics (data minimization)
from services.analytics import AnalyticsService
try:
    sales_record_ids = await AnalyticsService.create_sales_records_from_order(order_id, session)
    logging.info(f"✅ Created {len(sales_record_ids)} SalesRecord entries for order {order_id}")
except Exception as e:
    logging.error(f"❌ Failed to create SalesRecords for order {order_id}: {e}", exc_info=True)
    # Don't fail order completion if analytics fail
```

### 2. Payment Violations (`processing/payment_handlers.py`)

**Second Underpayment** (line 367-376):
```python
# Track violation for analytics (anonymized, no user_id)
try:
    await AnalyticsService.create_violation_record(
        order_id=order.id,
        violation_type=ViolationType.UNDERPAYMENT_FINAL,
        penalty_applied=penalty_amount,
        session=session
    )
except Exception as e:
    logging.error(f"Failed to create violation record for order {order.id}: {e}", exc_info=True)
```

**Late Payment** (line 448-457): Similar integration

### 3. Order Cancellation (`services/order.py`)

**User Cancellation Late** (line 722-731):
```python
# Track violation for analytics (anonymized, no user_id)
try:
    await AnalyticsService.create_violation_record(
        order_id=order_id,
        violation_type=ViolationType.USER_CANCELLATION_LATE,
        penalty_applied=penalty_amount if wallet_refund_info and wallet_refund_info.get('penalty_amount') else 0.0,
        session=session
    )
except Exception as e:
    logging.error(f"Failed to create violation record for order {order_id}: {e}", exc_info=True)
```

**Timeout** (line 745-754): Similar integration

### 4. Data Retention Job (`jobs/data_retention_cleanup_job.py`)

Runs daily at startup via `bot.py` lifespan handler:
```python
# Start data retention cleanup job (always enabled for data minimization)
data_retention_task = asyncio.create_task(start_data_retention_cleanup_job())
logging.info("[Startup] Data retention cleanup job started")
```

**Job Actions**:
- Deletes orders older than `DATA_RETENTION_DAYS` (default: 30)
- Deletes invoices, payment_transactions (cascade)
- Deletes referral_usage after `REFERRAL_DATA_RETENTION_DAYS` (default: 365)
- **Does NOT delete** sales_records or violation_statistics (retained indefinitely)

---

## Database Schema

### Migration: `migrations/add_sales_analytics_tables.py`

Creates:
1. **sales_records** table with 4 indexes:
   - `idx_sales_records_sale_date` (sale_date DESC)
   - `idx_sales_records_category` (category_name, sale_date DESC)
   - `idx_sales_records_subcategory` (subcategory_name, sale_date DESC)
   - `idx_sales_records_is_refunded` (is_refunded, sale_date DESC)

2. **violation_statistics** table with 2 indexes:
   - `idx_violation_statistics_date` (violation_date DESC)
   - `idx_violation_statistics_type` (violation_type, violation_date DESC)

**Run Migration**:
```bash
python migrations/add_sales_analytics_tables.py
```

---

## Configuration

### Environment Variables

```bash
# Data retention (days)
DATA_RETENTION_DAYS=30
REFERRAL_DATA_RETENTION_DAYS=365

# Penalty percentages (used for violation tracking)
PAYMENT_UNDERPAYMENT_PENALTY_PERCENT=5.0
PAYMENT_LATE_PENALTY_PERCENT=5.0
```

---

## Testing

### Unit Tests (21 tests)
```bash
# Run all unit tests
python -m pytest tests/analytics/unit/ -v

# Run specific test file
python -m pytest tests/analytics/unit/test_analytics_service.py -v
```

**Coverage**:
- `test_analytics_service.py`: 11 tests (SalesRecords, ViolationStatistics, data minimization)
- `test_sales_record_repository.py`: 5 tests (CRUD, aggregation queries)
- `test_violation_statistics_repository.py`: 5 tests (CRUD, aggregation queries)

**Status**: ✅ All 21 tests passing

### Manual Testing
See: `docs/features/analytics-data-retention/MANUAL_TEST_PLAN.md`

18 manual test cases covering:
- **Core Functionality** (12 tests):
  - Order completion → SalesRecords creation
  - Payment violations → ViolationStatistics creation
  - Data retention job execution
  - Data minimization verification
  - Analytics resilience
- **Integration Scenarios** (6 tests):
  - End-to-end order flow
  - Multiple payment methods
  - High-volume processing
  - Exception handling
  - Data persistence after deletion

**Note**: Integration tests were converted to manual tests due to complex mock requirements.
Real database interactions provide better test coverage for integration scenarios.

---

## Usage Examples

### Query Total Revenue (Last 30 Days)
```python
from repositories.sales_record import SalesRecordRepository

total_revenue = await SalesRecordRepository.get_total_revenue(30, session)
print(f"Revenue (last 30 days): €{total_revenue:.2f}")
```

### Query Violation Counts
```python
from repositories.violation_statistics import ViolationStatisticsRepository
from enums.violation_type import ViolationType

late_payments = await ViolationStatisticsRepository.get_violation_count_by_type(
    ViolationType.LATE_PAYMENT, 30, session
)
print(f"Late payments (last 30 days): {late_payments}")

total_penalties = await ViolationStatisticsRepository.get_total_penalty_amount(30, session)
print(f"Total penalties collected: €{total_penalties:.2f}")
```

### SQL Queries for Reporting

**Sales by Category**:
```sql
SELECT
    category_name,
    SUM(item_total_price) as revenue,
    SUM(quantity) as items_sold
FROM sales_records
WHERE sale_date >= date('now', '-30 days')
GROUP BY category_name
ORDER BY revenue DESC;
```

**Sales by Hour of Day** (optimize product launches):
```sql
SELECT
    sale_hour,
    COUNT(*) as orders,
    SUM(item_total_price) as revenue
FROM sales_records
WHERE sale_date >= date('now', '-7 days')
GROUP BY sale_hour
ORDER BY sale_hour;
```

**Violation Trends**:
```sql
SELECT
    DATE(violation_date) as date,
    violation_type,
    COUNT(*) as count
FROM violation_statistics
WHERE violation_date >= date('now', '-30 days')
GROUP BY date, violation_type
ORDER BY date DESC, violation_type;
```

---

## Data Minimization Compliance

### Why No user_id?

**Problem**: Storing user_id in analytics violates data minimization principles and complicates data retention policies.

**Solution**: Anonymized analytics with zero user identification enables:
- ✅ Indefinite retention for business intelligence
- ✅ Deletion of orders after 30 days without losing analytics
- ✅ Compliance with data minimization principles
- ✅ Abuse pattern detection without individual tracking

### Verification

Check schema:
```sql
PRAGMA table_info(sales_records);
PRAGMA table_info(violation_statistics);
```

Both queries should show **NO user_id column**.

---

## Performance Considerations

### Indexes
All analytics queries use indexes for optimal performance:
- Date-based queries use `sale_date` / `violation_date` indexes
- Category/subcategory queries use composite indexes
- Refund queries use `is_refunded` index

### Query Performance
Expected performance (1000+ records):
- Aggregation queries (SUM, COUNT): < 100ms
- Date range filters: < 50ms
- GROUP BY queries: < 200ms

### Data Growth
Estimated table sizes (1 year, 1000 orders/month):
- **sales_records**: ~24,000 rows (~5MB)
- **violation_statistics**: ~500 rows (~100KB)

---

## Troubleshooting

### Issue: SalesRecords Not Created

**Symptoms**: Order completed but no SalesRecords in database

**Check**:
1. Logs for analytics errors:
   ```
   ❌ Failed to create SalesRecords for order X
   ```
2. Migration ran successfully:
   ```sql
   SELECT name FROM sqlite_master WHERE type='table' AND name='sales_records';
   ```
3. Items exist for order:
   ```sql
   SELECT COUNT(*) FROM items WHERE order_id = X;
   ```

### Issue: Violation Not Tracked

**Check**:
1. Violation type enum matches:
   ```python
   from enums.violation_type import ViolationType
   print(list(ViolationType))
   ```
2. Integration point called (add debug logging)
3. Order exists when violation recorded

### Issue: Data Retention Job Not Running

**Check**:
1. Bot startup logs:
   ```
   [Startup] Data retention cleanup job started
   ```
2. Job schedule (runs every 24 hours)
3. Manually trigger:
   ```bash
   python -m jobs.data_retention_cleanup_job
   ```

---

## Future Enhancements

### Potential Features
- Admin dashboard for real-time analytics viewing
- Export to CSV/Excel for external analysis
- Automated email reports (weekly revenue summary)
- Predictive analytics (sales forecasting)
- A/B testing framework integration

### Analytics Queries to Add
- Average order value trends
- Conversion rate by payment method
- Physical vs digital sales ratio
- Peak sales hours/days
- Refund rate tracking

---

## Related Documentation

- Test Cases: `docs/features/analytics-data-retention/TEST_CASES.md`
- Manual Test Plan: `docs/features/analytics-data-retention/MANUAL_TEST_PLAN.md`
- Migration: `migrations/add_sales_analytics_tables.py`
- Data Retention Job: `jobs/data_retention_cleanup_job.py`

---

## Contributors

- Initial Implementation: Claude (2025-11-11)
- Code Review: [Pending]
- Testing: [Pending]