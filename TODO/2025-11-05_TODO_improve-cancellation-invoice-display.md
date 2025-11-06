# TODO: Improve Cancellation Invoice Display

**Created**: 2025-11-05
**Priority**: Medium
**Status**: Backlog

## Problem

Cancellation notifications (timeout, late cancellation with penalty) show incomplete information:

**What's Missing:**
- ❌ No items list (user doesn't see what was cancelled)
- ❌ No structured invoice breakdown (subtotal, shipping, total)
- ❌ Only shows refund amount without full context

**What's Shown:**
- ✅ Penalty reason and explanation
- ✅ Penalty calculation (e.g. 10% fee)
- ✅ Refund amount
- ✅ Strike warning

## Current Behavior

User receives message like:
```
❌ Order Cancelled
📋 Order Number: INV-2025-000123

⏱️ Grund: Ihre Reservierungszeit ist abgelaufen.
...
💰 Guthaben-Rückerstattung:
• Verwendetes Guthaben: 50.00 €
• Bearbeitungsgebühr (10%): -5.00 €
• Zurückerstattet: 45.00 €
```

## Desired Behavior

Should show full invoice structure like successful orders:
```
❌ Order Cancelled
📋 Order Number: INV-2025-000123

📦 ITEMS
─────────────────────────────
2x Netflix Account (10.00 €)  20.00 €
1x Spotify Premium (15.00 €)  15.00 €
─────────────────────────────
Subtotal                      35.00 €
Shipping                       5.00 €
─────────────────────────────
TOTAL                         40.00 €

💳 PAYMENT
─────────────────────────────
Wallet used                   40.00 €
Status: CANCELLED

💰 REFUND
─────────────────────────────
Original amount               40.00 €
Processing fee (10%)          -4.00 €
─────────────────────────────
Refunded to wallet            36.00 €

⏱️ Grund: Ihre Reservierungszeit ist abgelaufen.
...
```

## Technical Details

**Location**: `services/notification.py:435-450`

```python
# Line 437-449: cancellation_refund header_type
return InvoiceFormatter.format_complete_order_view(
    header_type="cancellation_refund",
    invoice_number=invoice_number,
    items=None,  # ❌ NO ITEMS SHOWN
    total_price=refund_info.get('base_amount', 0),
    wallet_used=original_amount,
    refund_amount=refund_amount,
    penalty_amount=penalty_amount,
    penalty_percent=penalty_percent,
    cancellation_reason=reason,
    show_strike_warning=True,
    currency_symbol=currency_sym,
    entity=BotEntity.USER
)
```

**What Needs to Change:**

1. **Pass items to formatter**: Load order items like in `partial_cancellation` case (lines 398-417)
2. **Enhance cancellation_refund section**: In `invoice_formatter.py:574-609`, add items display + payment breakdown
3. **Show complete invoice structure**: Similar to `payment_success` or `order_shipped` formats

## Implementation Notes

- Crypto payment info not needed (all converted to Fiat after payment confirmation)
- Penalty is calculated on total Fiat amount
- User can see what they ordered before deciding if manual refund request is needed
- Better transparency = fewer support requests

## Workaround

Admin can manually refund via Credit Management if user complains about missing refund.

## Related Files

- `services/notification.py` - Line 435-450 (build_order_cancelled_wallet_refund_message)
- `services/invoice_formatter.py` - Line 574-609 (cancellation_refund section)
- `services/order.py` - `_group_items_for_display()` helper method

## Priority Justification

**Medium Priority** because:
- Workaround exists (manual refund)
- Refund logic works correctly (just display issue)
- User experience improvement, not a critical bug
- Can be done after more urgent features/fixes
