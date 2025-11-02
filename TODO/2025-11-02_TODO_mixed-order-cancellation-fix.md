# Fix: Gemischte Order-Stornierung (Digital + Physical)

**Date:** 2025-11-02
**Priority:** HIGH
**Status:** Planning
**Estimated Effort:** 2-3 hours
**Type:** Bug Fix + Feature Enhancement

---

## Problem

Bei Stornierung einer gemischten Bestellung (digitale + physische Items) wird der **GESAMTBETRAG** erstattet, obwohl digitale Items bereits ausgeliefert wurden.

**Aktuelles Verhalten:**
```
Order: 1x Digital (10€) + 1x Physical (20€) = 30€
User zahlt: 30€ Wallet
Digital wird sofort ausgeliefert ✅
User storniert vor Versand
Erstattung: 30€ ❌ (falsch - digital schon erhalten!)
```

**Erwartetes Verhalten:**
```
Order: 1x Digital (10€) + 1x Physical (20€) = 30€
User zahlt: 30€ Wallet
Digital wird sofort ausgeliefert ✅
User storniert vor Versand
Erstattung: 20€ ✅ (nur physical, digital behalten)
```

---

## Root Cause Analysis

### Code Location: `services/order.py:cancel_order()`

```python
# Line 280-350 (ungefähr)
async def cancel_order(
    order_id: int,
    reason: OrderCancelReason,
    session: AsyncSession | Session,
    refund_wallet: bool = True,
    custom_reason: str = None
):
    # ...
    # Aktuell: Erstattet GESAMTBETRAG
    refund_amount = order.total_price - penalty_amount

    # Problem: Keine Unterscheidung zwischen digital/physical
```

### Betroffene Szenarien

1. **User storniert gemischte Order** (vor Versand)
   - Digital bereits erhalten
   - Physical noch nicht versendet
   - ❌ User bekommt Geld für digitale Items zurück

2. **Admin storniert gemischte Order** (vor Versand)
   - Digital bereits erhalten
   - Physical noch nicht versendet
   - ❌ User bekommt Geld für digitale Items zurück

3. **Timeout Cancellation** (gemischte Order)
   - Digital bereits erhalten
   - ❌ User bekommt Geld für digitale Items zurück (minus Strafe)

---

## Solution Design

### Phase 1: Refund Calculation (Kernlogik)

**Neue Funktion:** `_calculate_partial_refund()`

```python
@staticmethod
def _calculate_partial_refund(
    order_id: int,
    items: list,
    original_amount: float,
    reason: OrderCancelReason
) -> dict:
    """
    Calculate refund for mixed orders.

    Rules:
    1. Digital items (already delivered): NOT refundable
    2. Physical items (not shipped): Refundable
    3. Shipping cost: Refundable if physical items cancelled

    Returns:
        {
            'digital_amount': 10.00,      # Not refunded
            'physical_amount': 20.00,     # Refundable
            'shipping_cost': 5.00,        # Refundable
            'refundable_amount': 25.00,   # physical + shipping
            'penalty_amount': 1.25,       # 5% of refundable
            'final_refund': 23.75         # refundable - penalty
        }
    """
    digital_total = 0.0
    physical_total = 0.0

    for item in items:
        if item.is_physical:
            physical_total += item.price
        else:
            digital_total += item.price

    # Shipping cost only refunded if physical items present
    refundable_base = physical_total
    if physical_total > 0:
        refundable_base += order.shipping_cost

    # Calculate penalty on refundable amount only
    penalty_percent = _get_penalty_percent(reason)
    penalty_amount = refundable_base * (penalty_percent / 100)

    final_refund = refundable_base - penalty_amount

    return {
        'digital_amount': digital_total,
        'physical_amount': physical_total,
        'shipping_cost': order.shipping_cost,
        'refundable_amount': refundable_base,
        'penalty_percent': penalty_percent,
        'penalty_amount': penalty_amount,
        'final_refund': final_refund,
        'non_refundable_reason': 'digital_already_delivered'
    }
```

---

### Phase 2: Update cancel_order()

```python
async def cancel_order(
    order_id: int,
    reason: OrderCancelReason,
    session: AsyncSession | Session,
    refund_wallet: bool = True,
    custom_reason: str = None
):
    order = await OrderRepository.get_by_id(order_id, session)
    items = await ItemRepository.get_by_order_id(order_id, session)

    # Check if mixed order
    has_digital = any(not item.is_physical for item in items)
    has_physical = any(item.is_physical for item in items)
    is_mixed = has_digital and has_physical

    if is_mixed:
        # Use partial refund calculation
        refund_info = OrderService._calculate_partial_refund(
            order_id, items, order.total_price, reason
        )
    else:
        # Use full refund calculation (existing logic)
        refund_info = OrderService._calculate_full_refund(
            order.total_price, reason
        )

    # Process refund
    if refund_wallet and refund_info['final_refund'] > 0:
        await WalletService.add_balance(
            order.user_id,
            refund_info['final_refund'],
            session
        )

    # Update order status
    await OrderRepository.update_status(order_id, OrderStatus.CANCELLED, session)

    # Send notification (with partial refund details)
    await NotificationService.order_cancelled_partial_refund(
        user, order, invoice, refund_info, session, custom_reason
    )
```

---

### Phase 3: Update Notifications

**Neue Notification:** `order_cancelled_partial_refund()`

```python
@staticmethod
async def order_cancelled_partial_refund(
    user: UserDTO,
    order,
    invoice,
    refund_info: dict,
    session,
    custom_reason: str = None
):
    """
    Notification for mixed order cancellation with partial refund.

    Shows breakdown:
    - Digital items: Already delivered (NOT refunded)
    - Physical items: Cancelled (refunded)
    - Shipping: Refunded
    - Penalty: Applied to refundable amount only
    """
    msg = (
        f"🔄 <b>Bestellung teilweise storniert</b>\n\n"
        f"<b>Order-ID:</b> {invoice.invoice_number}\n\n"
        f"<b>DIGITALE ARTIKEL</b> (bereits geliefert):\n"
        f"Betrag: {refund_info['digital_amount']:.2f}€\n"
        f"Status: ✅ Behalten (nicht erstattungsfähig)\n\n"
        f"<b>PHYSISCHE ARTIKEL</b> (storniert):\n"
        f"Betrag: {refund_info['physical_amount']:.2f}€\n"
        f"Versandkosten: {refund_info['shipping_cost']:.2f}€\n"
        f"Erstattungsfähig: {refund_info['refundable_amount']:.2f}€\n\n"
    )

    if refund_info['penalty_amount'] > 0:
        msg += (
            f"⚠️ <b>Bearbeitungsgebühr:</b>\n"
            f"{refund_info['penalty_percent']:.0f}% von {refund_info['refundable_amount']:.2f}€ "
            f"= {refund_info['penalty_amount']:.2f}€\n\n"
        )

    msg += (
        f"💰 <b>Erstattung:</b>\n"
        f"Wallet-Guthaben: +{refund_info['final_refund']:.2f}€\n\n"
        f"<i>Die digitalen Artikel wurden bereits an dich geliefert und "
        f"können daher nicht erstattet werden.</i>"
    )

    await NotificationService.send_to_user(msg, user.telegram_id)
```

---

### Phase 4: Localization (DE/EN)

**l10n/de.json:**
```json
{
    "order_cancelled_partial_refund_digital_kept": "🔄 <b>Bestellung teilweise storniert</b>\n\n<b>Order-ID:</b> {invoice_number}\n\n<b>DIGITALE ARTIKEL</b> (bereits geliefert):\nBetrag: {digital_amount}€\nStatus: ✅ Behalten\n\n<b>PHYSISCHE ARTIKEL</b> (storniert):\nBetrag: {physical_amount}€\nVersandkosten: {shipping_cost}€\n\n💰 <b>Erstattung: {final_refund}€</b>\n\n<i>Die digitalen Artikel wurden bereits geliefert und können nicht erstattet werden.</i>"
}
```

---

## Implementation Tasks

### Step 1: Core Logic (1 hour)
- [ ] Add `_calculate_partial_refund()` to `services/order.py`
- [ ] Add `_calculate_full_refund()` (extract existing logic)
- [ ] Update `cancel_order()` to use mixed-order detection
- [ ] Add unit tests for refund calculation

### Step 2: Notifications (30 min)
- [ ] Add `order_cancelled_partial_refund()` to `services/notification.py`
- [ ] Add localization strings (DE/EN)
- [ ] Test notification formatting

### Step 3: Edge Cases (30 min)
- [ ] Handle digital-only orders (existing behavior)
- [ ] Handle physical-only orders (existing behavior)
- [ ] Handle mixed orders with 0€ digital items
- [ ] Handle mixed orders with penalties

### Step 4: Testing (1 hour)
- [ ] Manual test: Cancel mixed order (digital + physical)
- [ ] Manual test: Cancel digital-only order
- [ ] Manual test: Cancel physical-only order
- [ ] Manual test: Timeout cancellation of mixed order
- [ ] Manual test: Admin cancellation of mixed order
- [ ] Verify refund amounts are correct
- [ ] Verify notifications are correct

---

## Test Cases

### Test 1: Mixed Order Cancellation (User)
**Setup:**
- 1x Digital (10€)
- 1x Physical (20€)
- Shipping: 5€
- Total: 35€
- Payment: Wallet

**Steps:**
1. User completes payment
2. Digital item delivered immediately
3. User cancels before shipment (within grace period)

**Expected Result:**
- Digital: 10€ NOT refunded (already delivered)
- Physical: 20€ refunded
- Shipping: 5€ refunded
- Penalty: 0€ (grace period)
- **Total Refund: 25€**

---

### Test 2: Mixed Order Timeout Cancellation
**Setup:**
- 1x Digital (15€)
- 1x Physical (30€)
- Shipping: 5€
- Total: 50€
- Payment: Wallet

**Steps:**
1. User completes payment
2. Digital item delivered immediately
3. Order times out (no action)
4. System cancels order

**Expected Result:**
- Digital: 15€ NOT refunded (already delivered)
- Physical: 30€ refundable
- Shipping: 5€ refundable
- Refundable base: 35€
- Penalty: 5% of 35€ = 1.75€
- **Total Refund: 33.25€**

---

### Test 3: Digital-Only Order (Regression Test)
**Setup:**
- 2x Digital (10€ each)
- Total: 20€

**Steps:**
1. User completes payment
2. Items delivered
3. User tries to cancel

**Expected Result:**
- Cancellation NOT allowed (items already delivered)
- OR: 0€ refund with message "Items already delivered"

---

## Related Issues

- Mixed order handling in shipping management
- Item delivery timing
- Refund calculation consistency

---

## Security Considerations

- Prevent double-refund exploits
- Verify item delivery status before refund
- Log all refund calculations for audit

---

## Rollback Plan

If issues arise:
1. Revert `cancel_order()` changes
2. Keep existing full-refund logic
3. Add warning message about mixed orders

---

**Status:** Ready for Implementation
**Next Step:** Implement Phase 1 (Core Logic)
