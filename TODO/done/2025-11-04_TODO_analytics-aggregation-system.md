# TODO: Analytics Aggregation & Data Sanitization System

**Created**: 2025-11-04
**Priority**: High (Business Requirements)
**Status**: Planning
**Related**: 2025-11-04_TODO_eliminate-buy-model-legacy.md

## Problem Statement

After DATA_RETENTION_DAYS (30 days), all Order and Buy records are deleted for GDPR compliance. This causes:

1. **Lost Business Intelligence**: No historical revenue data, sales trends, or growth metrics
2. **No Tax Records**: May need data longer than 30 days for accounting/tax purposes
3. **Incomplete Statistics**: Admin panel shows only last 30 days of data

## Current Statistics Implementation

**Location**: `services/admin.py` - Statistics menu
**Data Source**: `BuyRepository.get_by_timedelta(days)`
**Limitation**: Only works within DATA_RETENTION_DAYS window

## Proposed Solution: Analytics Aggregation

### Architecture: Two-Tier Data Storage

```
Tier 1: Operational Data (GDPR compliant, short retention)
├─ Orders (30 days) - Full order details with PII
├─ Buys (30 days) - Purchase records with user info
└─ Items (linked to orders) - Product keys/codes

Tier 2: Analytics Data (anonymized, long retention)
├─ DailySalesStats (365+ days) - Aggregated revenue/volume
├─ ProductStats (365+ days) - Popular items, categories
└─ MonthlyRevenue (unlimited) - Historical business metrics
```

### Phase 1: Define Analytics Models

**File**: `models/analytics.py`

```python
class DailySalesStats(Base):
    """
    Daily aggregated sales data (anonymized, no PII)
    Retention: 365+ days for business intelligence
    """
    __tablename__ = 'daily_sales_stats'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)

    # Revenue metrics
    total_revenue = Column(Float, nullable=False, default=0.0)
    total_orders = Column(Integer, nullable=False, default=0)
    total_items_sold = Column(Integer, nullable=False, default=0)

    # Payment breakdown
    revenue_from_wallet = Column(Float, nullable=False, default=0.0)
    revenue_from_crypto = Column(Float, nullable=False, default=0.0)

    # Order types
    digital_orders = Column(Integer, nullable=False, default=0)
    physical_orders = Column(Integer, nullable=False, default=0)
    mixed_orders = Column(Integer, nullable=False, default=0)

    # Refund tracking
    refunds_count = Column(Integer, nullable=False, default=0)
    refunds_amount = Column(Float, nullable=False, default=0.0)

    # Cancellation tracking
    cancelled_by_user = Column(Integer, nullable=False, default=0)
    cancelled_by_admin = Column(Integer, nullable=False, default=0)
    timeout_cancelled = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=func.now())


class ProductStats(Base):
    """
    Daily product/category sales (anonymized)
    Retention: 365+ days for inventory planning
    """
    __tablename__ = 'product_stats'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    subcategory_id = Column(Integer, ForeignKey('subcategories.id'), nullable=False)

    # Sales metrics
    units_sold = Column(Integer, nullable=False, default=0)
    revenue = Column(Float, nullable=False, default=0.0)

    # Average pricing (for trend analysis)
    avg_price = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_date_category', 'date', 'category_id', 'subcategory_id'),
    )


class MonthlyRevenue(Base):
    """
    Monthly aggregated revenue (for long-term trends)
    Retention: Unlimited (or legal requirement, e.g., 7-10 years)
    """
    __tablename__ = 'monthly_revenue'

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12

    total_revenue = Column(Float, nullable=False, default=0.0)
    total_orders = Column(Integer, nullable=False, default=0)
    total_items_sold = Column(Integer, nullable=False, default=0)

    # For tax/accounting
    revenue_from_wallet = Column(Float, nullable=False, default=0.0)
    revenue_from_crypto = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_year_month', 'year', 'month', unique=True),
    )
```

### Phase 2: Aggregation Service

**File**: `services/analytics.py`

```python
class AnalyticsService:
    """
    Aggregates order data into analytics tables BEFORE deletion
    """

    @staticmethod
    async def aggregate_daily_stats(date: datetime.date, session: Session):
        """
        Aggregate all orders for a specific date into DailySalesStats.

        Should be called BEFORE order cleanup job runs.
        Idempotent: Can be re-run safely (updates existing record).
        """
        from models.analytics import DailySalesStats
        from repositories.order import OrderRepository
        from enums.order_status import OrderStatus

        # Get all orders for this date (from created_at)
        start_datetime = datetime.combine(date, datetime.min.time())
        end_datetime = datetime.combine(date, datetime.max.time())

        orders = await OrderRepository.get_by_date_range(
            start_date=start_datetime,
            end_date=end_datetime,
            session=session
        )

        # Calculate aggregates
        stats = DailySalesStats(date=date)

        for order in orders:
            if order.status in [OrderStatus.PAID, OrderStatus.SHIPPED]:
                stats.total_revenue += order.total_price
                stats.total_orders += 1
                stats.revenue_from_wallet += order.wallet_used
                stats.revenue_from_crypto += (order.total_price - order.wallet_used)

                # Count items
                items = await ItemRepository.get_by_order_id(order.id, session)
                stats.total_items_sold += len(items)

                # Classify order type
                has_physical = any(item.is_physical for item in items)
                has_digital = any(not item.is_physical for item in items)

                if has_physical and has_digital:
                    stats.mixed_orders += 1
                elif has_physical:
                    stats.physical_orders += 1
                else:
                    stats.digital_orders += 1

            elif order.status == OrderStatus.CANCELLED_BY_USER:
                stats.cancelled_by_user += 1
            elif order.status == OrderStatus.CANCELLED_BY_ADMIN:
                stats.cancelled_by_admin += 1
            elif order.status == OrderStatus.TIMEOUT:
                stats.timeout_cancelled += 1

            # Track refunds (if order has is_refunded field)
            if hasattr(order, 'is_refunded') and order.is_refunded:
                stats.refunds_count += 1
                stats.refunds_amount += order.refunded_amount or order.total_price

        # Upsert (update if exists, insert if not)
        existing = await session.execute(
            select(DailySalesStats).where(DailySalesStats.date == date)
        )
        existing_stats = existing.scalar_one_or_none()

        if existing_stats:
            # Update existing record
            for key, value in stats.__dict__.items():
                if not key.startswith('_'):
                    setattr(existing_stats, key, value)
        else:
            # Insert new record
            session.add(stats)

        await session_commit(session)
        logging.info(f"Aggregated daily stats for {date}: {stats.total_orders} orders, {stats.total_revenue:.2f} EUR")

    @staticmethod
    async def aggregate_product_stats(date: datetime.date, session: Session):
        """Aggregate product sales for a specific date"""
        # Similar to above, but grouped by category/subcategory
        pass

    @staticmethod
    async def aggregate_monthly_stats(year: int, month: int, session: Session):
        """
        Aggregate monthly revenue from DailySalesStats.

        Called at end of month or on-demand.
        """
        pass
```

### Phase 3: Data Cleanup Job (Modified)

**File**: `processing/processing.py` (existing cleanup job)

**Current behavior**: Deletes orders older than DATA_RETENTION_DAYS

**New behavior**:
```python
async def cleanup_old_data():
    """
    1. Aggregate data into analytics tables (FIRST!)
    2. Then delete operational data (Orders, Buys)
    """
    cutoff_date = datetime.now() - timedelta(days=config.DATA_RETENTION_DAYS)

    # STEP 1: Aggregate orders that will be deleted
    # Get all dates from cutoff_date to (cutoff_date - 7 days)
    # This ensures we aggregate before deletion, with 7-day safety buffer
    for days_ago in range(config.DATA_RETENTION_DAYS, config.DATA_RETENTION_DAYS + 7):
        aggregate_date = (datetime.now() - timedelta(days=days_ago)).date()

        try:
            await AnalyticsService.aggregate_daily_stats(aggregate_date, session)
            await AnalyticsService.aggregate_product_stats(aggregate_date, session)
        except Exception as e:
            logging.error(f"Failed to aggregate data for {aggregate_date}: {e}")
            # Continue with other dates (don't block cleanup)

    # STEP 2: Delete operational data (existing logic)
    await OrderRepository.delete_older_than(cutoff_date, session)
    await BuyRepository.delete_older_than(cutoff_date, session)  # If Buy still exists

    logging.info(f"Data cleanup complete: Aggregated and deleted data older than {cutoff_date}")
```

### Phase 4: Statistics Dashboard (Updated)

**File**: `services/admin.py` - Update statistics methods

**Current**: Shows only last 30 days (from Buy)
**New**: Shows historical data from analytics tables

```python
async def get_statistics(timedelta: StatisticsTimeDelta, session: Session):
    """
    Get statistics for specified time range.

    - If within DATA_RETENTION_DAYS: Use Order table (real-time)
    - If older: Use DailySalesStats (aggregated)
    """

    if timedelta.value <= config.DATA_RETENTION_DAYS:
        # Use Order table (existing logic)
        orders = await OrderRepository.get_by_status_and_date(...)
        # Calculate real-time stats
    else:
        # Use analytics table
        from repositories.analytics import AnalyticsRepository
        stats = await AnalyticsRepository.get_daily_stats_range(
            start_date=datetime.now() - timedelta(days=timedelta.value),
            end_date=datetime.now(),
            session=session
        )
        # Aggregate from DailySalesStats
```

## Configuration

**File**: `config.py` (new settings)

```python
# Analytics Retention
ANALYTICS_RETENTION_DAYS = 365  # Keep analytics for 1 year
MONTHLY_STATS_RETENTION_YEARS = 10  # Tax/legal requirement

# Aggregation Schedule
AGGREGATE_DATA_BEFORE_DAYS = 7  # Aggregate data 7 days before deletion (safety buffer)
```

## Migration Strategy

### Phase 1: Create Analytics Tables
```bash
# Create new tables (no data loss risk)
alembic revision --autogenerate -m "Add analytics tables"
alembic upgrade head
```

### Phase 2: Backfill Historical Data
```python
# Backfill last 30 days (before any data is lost)
for days_ago in range(0, 30):
    date = (datetime.now() - timedelta(days=days_ago)).date()
    await AnalyticsService.aggregate_daily_stats(date, session)
```

### Phase 3: Enable Aggregation in Cleanup Job
```python
# Modify processing/processing.py to call aggregation before deletion
```

### Phase 4: Update Statistics Dashboard
```python
# Update admin statistics to use analytics tables
```

## Benefits

- **GDPR Compliant**: PII deleted after 30 days
- **Business Intelligence**: Historical trends, revenue analysis
- **Tax Compliance**: Monthly aggregates for accounting
- **Performance**: Analytics tables are pre-aggregated (fast queries)
- **Scalability**: Aggregation runs once per day (not per query)

## Risks & Considerations

- **Data Accuracy**: Aggregation must run BEFORE deletion (safety buffer needed)
- **Idempotency**: Aggregation should be re-runnable (in case of failures)
- **Schema Evolution**: If Order model changes, aggregation logic needs update
- **Initial Backfill**: Need to aggregate existing data before enabling cleanup

## Related TODOs

- 2025-11-04_TODO_eliminate-buy-model-legacy.md (Buy migration - NOT NEEDED if both have same retention)

## Notes

- Analytics tables contain NO PII (no user IDs, no telegram usernames, no addresses)
- Only aggregated metrics: counts, sums, averages
- Product stats use category/subcategory IDs (no private_data/keys)
- Monthly stats provide long-term audit trail for tax/legal purposes
