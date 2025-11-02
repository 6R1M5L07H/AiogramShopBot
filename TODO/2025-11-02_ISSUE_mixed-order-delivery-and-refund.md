# ISSUE: Mixed Order Delivery & Refund Problems

**Date:** 2025-11-02
**Reporter:** User Manual Testing
**Priority:** HIGH
**Type:** Bug
**Estimated Effort:** 2-3 hours

---

## Summary

Two critical issues found during manual testing of mixed orders (digital + physical items):

### Issue 1: Digital Items Not Delivered Immediately
**Expected:** Digital items should be delivered immediately upon payment
**Actual:** Digital items are NOT delivered until admin marks order as shipped
**Impact:** Users wait unnecessarily for instant delivery items

### Issue 2: Full Refund on Cancellation
**Expected:** Only unshipped physical items should be refunded
**Actual:** Full order amount (including delivered digital items) is refunded
**Impact:** Users can get digital items for free by cancelling after delivery

---

## Test Scenario

1. User creates mixed order:
   - 1x Digital Item (10€)
   - 1x Physical Item (20€)
   - Total: 30€
2. User pays with Wallet
3. **Problem 1:** Digital item NOT delivered immediately
4. User cancels order before shipment
5. **Problem 2:** Full 30€ refunded (should be 20€ only)

---

## Root Cause

### Issue 1: Delivery Logic
**Location:** `services/order.py:complete_order_payment()`

Digital items should be delivered immediately after payment, but current logic only delivers when order status = SHIPPED.

### Issue 2: Refund Logic
**Location:** `services/order.py:cancel_order()`

```python
# Current (wrong):
refund_amount = order.total_price - penalty_amount

# Should be:
refund_amount = physical_items_total + shipping_cost - penalty_amount
```

---

## Solution Plan

Full solution documented in:
**`TODO/2025-11-02_TODO_mixed-order-cancellation-fix.md`**

Key changes needed:
1. Implement immediate digital item delivery on payment
2. Add `_calculate_partial_refund()` function
3. Update cancellation logic to separate digital/physical amounts
4. Add partial refund notifications with breakdown

---

## Testing Requirements

- [ ] Digital items delivered immediately on payment (mixed orders)
- [ ] Physical items delivered on shipment confirmation
- [ ] Cancellation refunds only physical + shipping (not digital)
- [ ] Penalty applied only to refundable amount
- [ ] Notification shows correct breakdown

---

**Status:** Documented - Ready for Implementation
**Next Step:** Implement solution from TODO document
