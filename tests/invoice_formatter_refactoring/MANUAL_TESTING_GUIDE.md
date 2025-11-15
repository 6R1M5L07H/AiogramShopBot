# Manual Testing Guide: Invoice Formatter Refactoring

## Overview
Manual test cases for invoice formatter refactoring. **Goal**: Verify identical behavior before/after refactoring.

## Prerequisites
- Test environment with refactored code
- Test user account with wallet balance
- Test admin account
- Multiple products in inventory (digital + physical)

---

## Section 1: Payment Screens

### TC 1.1: Digital Product Payment Screen
- [ ] Add 2 digital products to cart → checkout
- [ ] Verify: Invoice number (INV-YYYY-XXXXXX)
- [ ] Verify: Date format (DD.MM.YYYY HH:MM)
- [ ] Verify: Items list "2x Product €XX.XX"
- [ ] Verify: Subtotal + total calculations correct
- [ ] Verify: No hardcoded emojis

### TC 1.2: Physical Product Payment Screen
- [ ] Add 2 physical products → shipping address → checkout
- [ ] Verify: Shipping cost line present
- [ ] Verify: Subtotal + shipping = total
- [ ] Verify: All text localized (German)

### TC 1.3: Mixed Cart Payment Screen
- [ ] Add 1 digital + 2 physical → checkout
- [ ] Verify: All items in unified list
- [ ] Verify: Shipping cost included
- [ ] Verify: Calculations accurate

### TC 1.4: Payment with Wallet Balance
- [ ] User with €5 balance, order €20
- [ ] Verify: Wallet usage shown (€5)
- [ ] Verify: Remaining crypto amount (€15)
- [ ] Verify: Breakdown clear

---

## Section 2: Order Completion

### TC 2.1: Wallet-Only Payment Success
- [ ] Complete order with wallet only
- [ ] Verify: Success notification received
- [ ] Verify: "Wallet Payment" header
- [ ] Verify: Items formatted correctly
- [ ] Verify: Wallet deduction shown

### TC 2.2: Crypto Payment Success
- [ ] Complete crypto payment
- [ ] Verify: "Payment Success" notification
- [ ] Verify: Invoice number present
- [ ] Verify: Digital items delivered (keys in `<code>`)

### TC 2.3: Private Data Display
- [ ] Order digital product with keys
- [ ] Verify: Keys shown in `<code>` blocks
- [ ] Verify: Multiple keys separated properly

---

## Section 3: Order History & Details

### TC 3.1: User Order History
- [ ] My Profile → Order History → click order
- [ ] Verify: Status, created/paid timestamps
- [ ] Verify: Items list with prices
- [ ] Verify: Shipping address (if physical)

### TC 3.2: Digital-Only Order Detail
- [ ] Open digital-only order
- [ ] Verify: Digital section labeled
- [ ] Verify: Private data shown
- [ ] Verify: No shipping section

### TC 3.3: Physical Order Shipped
- [ ] Open shipped order
- [ ] Verify: "Order Shipped" header
- [ ] Verify: Shipped timestamp
- [ ] Verify: Shipping address + cost

### TC 3.4: Mixed Order Detail
- [ ] Open mixed order
- [ ] Verify: Separate digital/physical sections
- [ ] Verify: Digital keys displayed
- [ ] Verify: Physical section with shipping
- [ ] Verify: Subtotals + total correct

---

## Section 4: Admin Views

### TC 4.1: Admin Order List
- [ ] Admin → Order Management → click order
- [ ] Verify: Username + User ID
- [ ] Verify: Invoice number + status
- [ ] Verify: Created/paid timestamps

### TC 4.2: Admin Order Status Views
- [ ] View PENDING order: Verify "Expires at"
- [ ] View PAID_AWAITING_SHIPMENT: Verify paid timestamp + address
- [ ] View SHIPPED: Verify all lifecycle timestamps

### TC 4.3: Admin Order with Tier Pricing
- [ ] Create bulk order (triggers tiers)
- [ ] View as admin
- [ ] Verify: Tier breakdown (qty, unit price, subtotal)
- [ ] Verify: Total matches tier calculations

---

## Section 5: Cancellations

### TC 5.1: User Cancellation (Grace Period)
- [ ] Create order → cancel within 5 min
- [ ] Verify: "Order Cancelled" header
- [ ] Verify: Refund amount shown
- [ ] Verify: Wallet updated
- [ ] Verify: No strike message

### TC 5.2: User Cancellation (Late Strike)
- [ ] Create order → wait >5 min → cancel
- [ ] Verify: Strike warning
- [ ] Verify: Grace period explanation
- [ ] Verify: Refund amount (if any)

### TC 5.3: Admin Cancellation (User View)
- [ ] Admin cancels user order
- [ ] Check user notifications
- [ ] Verify: "RECHNUNG INV-..." header line
- [ ] Verify: "Datum: ..." date line
- [ ] Verify: "Status: STORNIERT (Admin)"
- [ ] Verify: "ARTIKEL" label with separator (─────)
- [ ] Verify: Items list formatted
- [ ] Verify: "Zwischensumme" subtotal line
- [ ] Verify: "Versand" shipping line
- [ ] Verify: "GESAMT" total line
- [ ] Verify: "ERSTATTUNG" refund section
- [ ] Verify: "Erstattungsbetrag" refund amount
- [ ] Verify: "SALDO" balance line
- [ ] Verify: Admin notice + refund notice
- [ ] Verify: No strike penalty

### TC 5.4: Partial Cancellation
- [ ] Mixed order → partial cancel (refund physical)
- [ ] Verify: "Partial Cancellation" header
- [ ] Verify: "Kept" and "Refunded" sections
- [ ] Verify: Digital in kept, physical in refunded
- [ ] Verify: Refund = physical + shipping only

---

## Section 6: Localization

### TC 6.1: No Hardcoded Emojis
- [ ] Test all invoice types above
- [ ] Verify: Emojis only from l10n strings
- [ ] Verify: No standalone "📋 " or "❌ " patterns

### TC 6.2: German Localization
- [ ] Test payment/details/cancellation
- [ ] Verify: All labels in German
- [ ] Verify: Date format DD.MM.YYYY HH:MM
- [ ] Verify: Currency € symbol

---

## Section 7: Edge Cases

### TC 7.1: Missing Username (Admin View)
- [ ] View order with deleted user
- [ ] Verify: Fallback "Unknown" or "0"
- [ ] Verify: No crash

### TC 7.2: Long Item Names
- [ ] Product with 80-char name
- [ ] Verify: Truncated/wrapped properly
- [ ] Verify: Layout not broken

### TC 7.3: High Quantity (>100)
- [ ] Order 150x same product
- [ ] Verify: "150x Product" displayed
- [ ] Verify: Calculation correct

### TC 7.4: Zero Shipping Cost
- [ ] Physical order with free shipping
- [ ] Verify: "Versand €0.00" shown
- [ ] Verify: Total calculation correct

### TC 7.5: HTML in Private Data
- [ ] Digital product with `<b>License:</b> KEY`
- [ ] Verify: HTML rendered (bold preserved)
- [ ] Verify: No injection issues

---

## Regression Checklist

- [ ] No crashes/exceptions in logs
- [ ] All DB queries successful
- [ ] No N+1 query issues
- [ ] Response times < 2s
- [ ] Telegram formatting not broken
- [ ] All buttons/navigation work

---

## Test Results

**Tester**: _______________
**Date**: _______________
**Environment**: ☐ Dev ☐ Staging
**Result**: ☐ All Passed ☐ Issues Found

### Issues
| Test Case | Issue | Severity | Status |
|-----------|-------|----------|--------|
|           |       |          |        |