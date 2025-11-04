# TODO: Eliminate Buy Model (Legacy System)

**Created**: 2025-11-04
**Priority**: Medium (Technical Debt)
**Status**: Planning

## Problem Analysis

The `Buy` model is a legacy purchase tracking system that duplicates data from the `Order` model. Analysis shows that:

1. **Purchase History** already uses Order (via `buy_id → items → order_id` chain)
2. **Refund System** uses Buy but could work better with Order (has wallet_used, shipping_cost, invoice, payment history)
3. **Statistics** uses Buy but could easily use Order
4. **Order Management** (shipping_management.py) is already 100% Buy-free

### Current Architecture (Problematic)

```
Order (30 days retention)
  └─ Items (order_id FK, NO CASCADE)
       └─ BuyItem (item_id FK)
            └─ Buy (NO order_id link!)

Problem: When Order is deleted (SQL DELETE), Buy becomes orphaned
```

### Buy Usage

| Feature | Current Implementation | Why Order is Better |
|---------|----------------------|-------------------|
| Purchase History | Uses Buy → Items → Order | Already fetches Order for all data! |
| Refund System | `Buy.is_refunded`, `Buy.total_price` | Order has wallet_used, shipping_cost, invoice |
| Statistics | `BuyRepository.get_by_timedelta()` | `OrderRepository` can filter by status + date |
| Order Management | **Already Buy-free** | N/A |

## Migration Plan

### Phase 1: Extend Order Model
```python
# models/order.py
class Order(Base):
    # Add refund tracking (move from Buy)
    is_refunded = Column(Boolean, default=False, nullable=False)
    refunded_at = Column(DateTime, nullable=True)
    refunded_amount = Column(Float, nullable=True)  # May differ from total_price (partial refunds)
```

### Phase 2: Migrate Refund System
**Files to change:**
- `services/admin.py` - AdminService.get_refund_menu()
- `services/buy.py` - BuyService.refund()
- `repositories/order.py` - Add get_refundable_orders()

**New implementation:**
```python
# Replace: BuyRepository.get_refund_data()
# With: OrderRepository.get_refundable_orders(status_filter=[PAID, SHIPPED], is_refunded=False)

# Refund logic:
order.is_refunded = True
order.refunded_at = datetime.now()
order.refunded_amount = calculate_refund(order)  # Consider wallet_used, shipping, partial refunds
user.top_up_amount += order.refunded_amount
```

### Phase 3: Migrate Purchase History
**Files to change:**
- `services/buy.py` - BuyService.get_purchase()
- `repositories/item.py` - Remove get_by_buy_id() or keep as alias

**Current chain:**
```python
buy_id → ItemRepository.get_by_buy_id() → items → order_id → OrderRepository.get_by_id()
```

**New (direct):**
```python
order_id → OrderRepository.get_by_id() → order.items
```

### Phase 4: Migrate Statistics
**Files to change:**
- `services/admin.py` - Statistics calculations
- `repositories/order.py` - Add date range queries

**Replace:**
```python
# OLD: BuyRepository.get_by_timedelta(days)
# NEW: OrderRepository.get_by_status_and_date(
#        status=[OrderStatus.PAID, OrderStatus.SHIPPED],
#        start_date=...,
#        end_date=...
#      )
```

### Phase 5: Data Migration Script
```python
# migrations/migrate_buy_to_order.py
"""
1. For each Buy record:
   - Find corresponding Order via: Buy → BuyItem → Item → order_id
   - Copy Buy.is_refunded → Order.is_refunded
   - Set Order.refunded_at = Buy.buy_datetime (if refunded)

2. Verify data integrity:
   - Count Buy records: SELECT COUNT(*) FROM buys
   - Count Order records with corresponding Buy: SELECT COUNT(DISTINCT order_id) FROM items WHERE order_id IN (...)
   - Report orphaned Buys (no matching Order)

3. Create backup before dropping tables:
   - Dump Buy + BuyItem tables to SQL file
"""
```

### Phase 6: Drop Buy Tables
```sql
-- After successful migration and testing
DROP TABLE IF EXISTS buyItem CASCADE;
DROP TABLE IF EXISTS buys CASCADE;

-- Remove references in code:
-- - models/buy.py (delete file)
-- - models/buyItem.py (delete file)
-- - repositories/buy.py (delete file)
-- - services/buy.py (refactor to services/order.py or delete)
```

## Benefits

- **Single Source of Truth** - No more Order/Buy duplication
- **Better Refunds** - Access to wallet_used, shipping_cost, invoice, payment history
- **Simpler Code** - No `buy_id → items → order_id` indirection
- **Correct CASCADE** - Order deletion cleanly removes all related data
- **Already Working** - Order Management is already Buy-free
- **Unified Data Retention** - All purchase data follows same lifecycle (DATA_RETENTION_DAYS)

## Risks & Considerations

- **Breaking Changes**: Existing code depends on Buy model
- **Data Loss**: If migration fails, purchase history could be lost (mitigated by backup)
- **Refund History**: Need to preserve refund timestamps and amounts
- **Testing**: Refund system needs thorough testing after migration

## Decision (REVISED)

**Key Insight**: Both Buy and Order are deleted after DATA_RETENTION_DAYS (30 days) for GDPR compliance. Therefore:

1. **Skip Buy→Order Migration** - Both tables will be cleaned up anyway
2. **Real Problem**: Statistics/Analytics lost after data retention cleanup
3. **Better Solution**: Implement **Analytics Aggregation System** (separate TODO)

**Current Status**: Order Management (shipping_management.py) is already Buy-free
**Next Step**:
- Continue using Order-only approach for all new features (no new Buy dependencies)
- Create separate TODO for Analytics/Data Sanitization system

**Migration**: NOT NEEDED - Both Buy and Order follow same retention policy

## Related Files

### Currently Buy-dependent:
- `services/admin.py` (refund menu)
- `services/buy.py` (refund logic, purchase history)
- `repositories/buy.py`
- `models/buy.py`
- `models/buyItem.py`

### Already Buy-free:
- `handlers/admin/shipping_management.py`
- `repositories/order.py`
- `services/order.py`

## Notes

- The Order Management feature (PR #XX) deliberately avoids Buy dependency
- All order data is accessible via Order model + relationships (items, invoices, payment_transactions, shipping_address)
- Buy was likely created before Order model existed (legacy from simpler cart → buy flow)
- Modern flow: Cart → Order → Payment → Delivery (Buy is redundant)
