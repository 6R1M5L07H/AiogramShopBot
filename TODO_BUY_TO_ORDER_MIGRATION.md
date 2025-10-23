# TODO: Buy System to Order System Migration

## Current Status
The codebase has **two parallel purchase systems**:
- **OLD:** Buy/BuyItem tables (legacy, wallet-based purchases)
- **NEW:** Order/Invoice tables (current, crypto-payment based)

**Problem:** Duplication and inconsistency. Purchase history was already migrated to Order system, but Refund system still uses Buy tables.

---

## Migration Tasks

### Phase 1: Refund System Migration ✅ PRIORITY
**Files to modify:**
- [ ] `services/buy.py::refund()` - Migrate from Buy to Order
- [ ] `repositories/buy.py` - Check what's still used
- [ ] `handlers/admin/user_management.py` - Update refund UI if needed
- [ ] `models/order.py` - Add `is_refunded` field to Order?
- [ ] Database migration script for existing Buy records

**Changes needed:**
1. Add `is_refunded: bool` field to Order model
2. Rewrite `BuyService.refund()` to work with Order objects
3. Update refund queries from `BuyRepository` to `OrderRepository`
4. Ensure backward compatibility for old Buy records (if any exist in production)

### Phase 2: Cleanup Obsolete Code
**Files to remove/deprecate:**
- [ ] `models/buy.py` - Buy model (after migration)
- [ ] `models/buyItem.py` - BuyItem model (after migration)
- [ ] `repositories/buy.py` - Buy repository (after migration)
- [ ] `repositories/buyItem.py` - BuyItem repository (after migration)
- [ ] Database tables: `buys`, `buyItem` (after backup and verification)

### Phase 3: Admin Statistics Update
**Check if these use Buy system:**
- [ ] `services/admin.py` - Purchase statistics
- [ ] Admin dashboard - Revenue calculations
- [ ] Any reports that query Buy table

---

## Why This Matters

**Consistency:** All purchases should use the same system (Order/Invoice)
**Maintainability:** Eliminating duplicate code reduces bugs
**Features:** New features (shipping, invoices, payment tracking) only work with Order system
**Performance:** Eliminating unused tables reduces database complexity

---

## Migration Strategy

**Option 1: Hard Migration (Recommended)**
- Migrate all existing Buy records to Order format
- Remove Buy tables completely
- Cleaner codebase, no legacy baggage

**Option 2: Soft Migration (Conservative)**
- Keep Buy tables read-only
- New purchases → Order system only
- Refunds work for both Buy and Order
- Allows gradual migration

---

## Testing Checklist
After migration:
- [ ] Refund functionality works for Order-based purchases
- [ ] Purchase history shows all orders correctly
- [ ] Admin statistics accurate
- [ ] No references to Buy/BuyItem in active code paths
- [ ] Database backup created before dropping Buy tables

---

## Notes
- Invoice-based system introduced in PR #25 (feature/invoice-stock-management)
- Purchase history migration completed in commit 17f6193
- Refund system is the last major component using Buy tables
