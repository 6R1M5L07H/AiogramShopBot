# PR#65 Test Plan: Shipping Idempotency, PGP Flow, Unit Display

**Date**: 2025-01
**PR**: #65 (fix/production-hotfixes-and-unit-display)
**Affected Areas**: Shipping address submission, PGP WebApp flow, price tier display

## Test Cases

### TC1: Shipping Address Duplicate Submission Protection

**Background**: Production crash `UNIQUE constraint failed: shipping_addresses.order_id` when users double-clicked submit.

**Fix**: services/shipping.py:180-201 - Added UPDATE logic for existing addresses.

**Test Steps**:
1. Create order with physical items (status: PENDING_PAYMENT_AND_ADDRESS)
2. Open PGP WebApp for address input
3. Submit address
4. Click submit button again immediately (simulate double-click)

**Expected Result**: No crash, address updated silently.

**Verification**: Check database - only one shipping_address record per order_id.

---

### TC2: PGP Button After Cancellation

**Background**: User cancels PGP input, returns via Cart → Checkout, PGP button disappeared.

**Fix**: services/order.py:1007-1028 - Added PGP button to reenter_shipping_address().

**Test Steps**:
1. Create order with physical items
2. Click PGP address input button (WebApp opens)
3. Close WebApp without submitting
4. Click "Cart" button in bot
5. Click "Checkout" button

**Expected Result**: PGP WebApp button appears again (not just text input).

**Verification**: Button labeled with PGP icon exists in keyboard.

---

### TC3: Item Unit Display in Price Tiers

**Background**: Price tiers showed hardcoded "Stk." regardless of actual unit (l, kg, g).

**Fix**: services/pricing.py:145 + services/subcategory.py:70,214 - Pass item.unit parameter.

**Test Steps**:
1. Create item with unit="l" (liters)
2. Create price tiers: 1→€11, 5→€10, 16→€9, 26→€8
3. View item in shop

**Expected Result**: Tier display shows "1-4 l: 11,00 €" (not "1-4 Stk:").

**Verification**: Check all units (l, kg, g, m, pairs) display correctly.

---

## Regression Tests

- [ ] Shipping address encryption/decryption still works (AES and PGP)
- [ ] Order flow completes without errors (cart → address → payment → completion)
- [ ] Price tier calculations still correct (no rounding errors)

## Success Criteria

All 3 test cases PASS + no regressions = Ready for Production
