# Data Retention Cleanup Job (GDPR Critical)

**Priority:** 🔴 **CRITICAL** - GDPR Compliance Required
**Estimated Effort:** Medium (1-2 hours)
**Created:** 2025-10-23

## Problem

Currently, orders and related data are stored **indefinitely** in the database, violating GDPR data minimization principles. There is no automatic cleanup mechanism for old orders.

## Description

Implement a background job that automatically deletes old orders and related data after a configurable retention period (default: 30 days). This ensures GDPR compliance and prevents database bloat.

## User Story

As a shop administrator, I want old order data to be automatically deleted after 30 days, so that I comply with GDPR data minimization requirements and keep the database clean.

## Acceptance Criteria

- [ ] Background job runs every 24 hours (configurable interval)
- [ ] Deletes orders older than `DATA_RETENTION_DAYS` (default: 30)
- [ ] Only deletes completed orders (status: PAID, SHIPPED, DELIVERED, CANCELLED, TIMEOUT)
- [ ] Does NOT delete pending orders (PENDING_PAYMENT, AWAITING_SHIPMENT)
- [ ] Cascade deletes related data:
  - Invoice records
  - Payment transaction records
  - Buy records (BuyItem junction table)
  - Reserved items (mark as available again if order was cancelled)
- [ ] Logs deleted order count and details
- [ ] Job can be manually triggered via admin command (optional)
- [ ] Dry-run mode for testing (optional)

## Technical Notes

### Configuration

```python
# config.py
DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "30"))
DATA_RETENTION_CHECK_INTERVAL_HOURS = int(os.getenv("DATA_RETENTION_CHECK_INTERVAL_HOURS", "24"))
```

### Job Structure

```python
# jobs/data_retention_cleanup_job.py
import asyncio
from datetime import datetime, timedelta
import logging

from db import get_db_session
from repositories.order import OrderRepository
from repositories.invoice import InvoiceRepository
from repositories.payment_transaction import PaymentTransactionRepository
from repositories.buy import BuyRepository
from repositories.buyItem import BuyItemRepository
import config

async def cleanup_old_orders():
    """
    Deletes orders and related data older than DATA_RETENTION_DAYS.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=config.DATA_RETENTION_DAYS)

    async with get_db_session() as session:
        # Get orders to delete (only completed/cancelled orders)
        old_orders = await OrderRepository.get_completed_before(cutoff_date, session)

        if not old_orders:
            logging.info(f"✅ Data retention cleanup: No orders older than {config.DATA_RETENTION_DAYS} days")
            return

        deleted_count = 0
        for order in old_orders:
            # Delete cascade: invoices, payment_transactions, buy records
            await InvoiceRepository.delete_by_order_id(order.id, session)
            await PaymentTransactionRepository.delete_by_order_id(order.id, session)

            # Delete buy records
            buy_records = await BuyRepository.get_by_order_id(order.id, session)
            for buy in buy_records:
                await BuyItemRepository.delete_by_buy_id(buy.id, session)
                await BuyRepository.delete(buy.id, session)

            # Delete order
            await OrderRepository.delete(order.id, session)
            deleted_count += 1

        await session.commit()

        logging.info(f"🗑️ Data retention cleanup: Deleted {deleted_count} orders older than {config.DATA_RETENTION_DAYS} days")

async def data_retention_cleanup_job():
    """
    Background job that runs every DATA_RETENTION_CHECK_INTERVAL_HOURS hours.
    """
    while True:
        try:
            await cleanup_old_orders()
        except Exception as e:
            logging.error(f"❌ Data retention cleanup job failed: {e}")

        # Wait until next run
        await asyncio.sleep(config.DATA_RETENTION_CHECK_INTERVAL_HOURS * 3600)
```

### Integration in run.py

```python
# run.py
from jobs.data_retention_cleanup_job import data_retention_cleanup_job

async def on_startup(bot: Bot):
    # ... existing startup code ...

    # Start data retention cleanup job
    asyncio.create_task(data_retention_cleanup_job())
    logging.info("✅ Data retention cleanup job started")
```

### Repository Methods Needed

```python
# repositories/order.py
@staticmethod
async def get_completed_before(cutoff_date: datetime, session: AsyncSession) -> list[Order]:
    """
    Get all completed/cancelled orders created before cutoff_date.
    """
    stmt = select(Order).where(
        Order.created_at < cutoff_date,
        Order.status.in_([
            OrderStatus.PAID,
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
            OrderStatus.CANCELLED_BY_USER,
            OrderStatus.CANCELLED_BY_ADMIN,
            OrderStatus.TIMEOUT
        ])
    )
    result = await session.execute(stmt)
    return result.scalars().all()
```

## GDPR Compliance

This feature implements **Article 5(1)(e) - Storage Limitation** of GDPR:
> Personal data shall be kept in a form which permits identification of data subjects for no longer than is necessary for the purposes for which the personal data are processed.

**Data Retention Justification:**
- 30 days allows time for:
  - Customer support inquiries
  - Dispute resolution
  - Financial reconciliation
- After 30 days, data is no longer necessary for business purposes

## Testing Checklist

- [ ] Create test orders with different dates
- [ ] Run job manually and verify old orders are deleted
- [ ] Verify pending orders are NOT deleted
- [ ] Verify cascade deletion (invoices, buy records)
- [ ] Verify job logs correctly
- [ ] Test with DATA_RETENTION_DAYS=1 (accelerated testing)

## Related

- Payment Validation System already has `DATA_RETENTION_DAYS` config
- Purchase History display shows "(last X days)" based on this config
- TODO: Admin Order Overview will also use this timeframe
