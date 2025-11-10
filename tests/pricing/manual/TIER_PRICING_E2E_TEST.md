# Tier Pricing End-to-End Test Checklist

## Overview
This document provides a comprehensive manual test plan for the tiered pricing feature implementation.

## Prerequisites
- Bot running locally or in production
- Test user account registered
- Admin account configured
- Test data: Categories/Subcategories with items that have price tiers configured
- Access to both user and admin interfaces

## Test Data Setup

### Required: Subcategory with Tiered Pricing
Example configuration (adjust to your data):
```
Category: Electronics
Subcategory: iPhone 15 Pro
Price Tiers:
  - 1-4 items: 11.00 EUR/each
  - 5-9 items: 10.00 EUR/each
  - 10+ items: 9.00 EUR/each
Stock: At least 20 items available
```

## Phase 1: Cart Display Tests

### Test 1.1: Single Tier (Below First Threshold)
**Setup**: Empty cart
**Steps**:
1. Browse to iPhone 15 Pro subcategory
2. Set quantity: 3
3. Tap "In den Warenkorb"

**Expected Result**:
```
Warenkorb

iPhone 15 Pro
 Anzahl: 3 Stk.
 Stückpreis: 11,00 €

Staffelpreise:
  3 × 11,00 € =   33,00 €
──────────────────────────
               Σ   33,00 €
               Ø   11,00 €/Stk.

Gesamtsumme: 33,00 €
```

**Verification**:
- [ ] Tier breakdown section displays
- [ ] Correct tier applied (1x tier at 11.00 EUR)
- [ ] Total matches: 3 × 11.00 = 33.00 EUR
- [ ] Average unit price: 11.00 EUR/item
- [ ] No hardcoded strings (all localized)

---

### Test 1.2: Single Tier (Second Threshold)
**Steps**:
1. Empty cart
2. Add 7 items to cart

**Expected Result**:
```
Staffelpreise:
  7 × 10,00 € =   70,00 €
──────────────────────────
               Σ   70,00 €
               Ø   10,00 €/Stk.
```

**Verification**:
- [ ] Second tier applied (10.00 EUR/item)
- [ ] Total: 70.00 EUR
- [ ] Average: 10.00 EUR/item

---

### Test 1.3: Multiple Tiers (Mixed)
**Steps**:
1. Empty cart
2. Add 17 items to cart

**Expected Result**:
```
Staffelpreise:
 10 ×  9,00 € =   90,00 €
  5 × 10,00 € =   50,00 €
  2 × 11,00 € =   22,00 €
──────────────────────────
               Σ  162,00 €
               Ø    9,53 €/Stk.
```

**Verification**:
- [ ] Greedy algorithm applied (largest tier first)
- [ ] Breakdown: 10 at 9.00, 5 at 10.00, 2 at 11.00
- [ ] Total: 162.00 EUR
- [ ] Average: 9.53 EUR/item
- [ ] Alignment correct (numbers right-aligned)

---

### Test 1.4: Edit Quantity in Cart
**Steps**:
1. Have 7 items in cart (single tier: 70.00 EUR)
2. Tap "Menge ändern"
3. Change quantity to 17
4. Confirm

**Expected Result**:
- [ ] Tier breakdown recalculates immediately
- [ ] Shows multiple tiers (10+5+2)
- [ ] Total updates to 162.00 EUR
- [ ] Average updates to 9.53 EUR/item

---

### Test 1.5: Multiple Subcategories (Different Tiers)
**Setup**:
- Subcategory A: 17 items (tiers: 11/10/9)
- Subcategory B: 5 items (different tiers)

**Steps**:
1. Add Subcategory A (17 items)
2. Add Subcategory B (5 items)
3. View cart

**Expected Result**:
```
Warenkorb

iPhone 15 Pro
 Anzahl: 17 Stk.
 Stückpreis: 9,53 €

Staffelpreise:
 10 ×  9,00 € =   90,00 €
  5 × 10,00 € =   50,00 €
  2 × 11,00 € =   22,00 €
──────────────────────────
               Σ  162,00 €
               Ø    9,53 €/Stk.

Samsung Galaxy S24
 Anzahl: 5 Stk.
 Stückpreis: [calculated]

Staffelpreise:
 [tier breakdown for subcategory B]

Gesamtsumme: [total of both]
```

**Verification**:
- [ ] Each subcategory has separate tier breakdown
- [ ] Tier calculations independent per subcategory
- [ ] Total sums both subcategories correctly

---

### Test 1.6: Physical + Digital Items Mix
**Steps**:
1. Add physical items (17 items with shipping)
2. Add digital items (no shipping)
3. View cart

**Expected Result**:
```
Digitale Produkte:
[Digital items with tier breakdown]

Physische Produkte:
[Physical items with tier breakdown]

Versand: 4,99 €
──────────────────────────
Gesamtsumme: [subtotal + shipping]
```

**Verification**:
- [ ] Tier breakdown shown for both digital and physical
- [ ] Shipping cost separate line
- [ ] Total includes shipping only for physical items

---

## Phase 2: Order Payment Screen Tests

### Test 2.1: Order Creation (Multiple Tiers)
**Steps**:
1. Have 17 items in cart (multiple tiers)
2. Tap "Zur Kasse"
3. Enter shipping address (if physical)
4. View payment screen

**Expected Result**:
```
Rechnung #XXXXX

Status: Warte auf Zahlung ⏳
Erstellt: [timestamp]

iPhone 15 Pro
 Anzahl: 17 Stk.
 Stückpreis: 9,53 €

Staffelpreise:
 10 ×  9,00 € =   90,00 €
  5 × 10,00 € =   50,00 €
  2 × 11,00 € =   22,00 €
──────────────────────────
               Σ  162,00 €
               Ø    9,53 €/Stk.

Zwischensumme: 162,00 €
Versand: 4,99 €
──────────────────────────
Gesamtsumme: 166,99 €

Guthaben: [wallet balance]
Zu zahlen: [remaining amount]
```

**Verification**:
- [ ] Tier breakdown matches cart display
- [ ] Stock reserved (items no longer available in shop)
- [ ] Subtotal + shipping = total
- [ ] Wallet balance deducted if applicable
- [ ] Payment buttons available

---

### Test 2.2: Payment Confirmation
**Steps**:
1. Complete payment for order from Test 2.1
2. View order confirmation

**Expected Result**:
- [ ] Order status changes to PAID
- [ ] Items marked as sold
- [ ] Invoice still shows tier breakdown
- [ ] All prices match pre-payment values

---

## Phase 3: Order History Tests (User)

### Test 3.1: User Order Detail View
**Steps**:
1. Open "Mein Profil" → "Bestellungen"
2. Select order from Test 2.2
3. View order details

**Expected Result**:
```
Bestellung #XXXXX

Status: Bezahlt ✅
Erstellt: [timestamp]
Bezahlt: [timestamp]

iPhone 15 Pro
 Anzahl: 17 Stk.
 Stückpreis: 9,53 €

Staffelpreise:
 10 ×  9,00 € =   90,00 €
  5 × 10,00 € =   50,00 €
  2 × 11,00 € =   22,00 €
──────────────────────────
               Σ  162,00 €
               Ø    9,53 €/Stk.

Zwischensumme: 162,00 €
Versand: 4,99 €
──────────────────────────
Gesamtsumme: 166,99 €

📬 Lieferadresse:
[Encrypted notice - not shown to user]
```

**Verification**:
- [ ] Tier breakdown preserved in history
- [ ] Individual items with private_data shown (if digital with keys)
- [ ] Shipping address shows encryption notice (not actual address)
- [ ] All timestamps present
- [ ] Status emoji correct

---

### Test 3.2: Order History List View
**Steps**:
1. Open "Mein Profil" → "Bestellungen"
2. View order list

**Expected Result**:
```
Meine Bestellungen
Filter: Alle

✅ DD.MM • SHORT_ID • Bezahlt
⏳ DD.MM • SHORT_ID • Warte auf Zahlung
🚚 DD.MM • SHORT_ID • Versandt

[Pagination if >10 orders]
[Filter ändern]
[Zurück]
```

**Verification**:
- [ ] Order list shows status emojis
- [ ] Short invoice ID (last 6 chars)
- [ ] Date format: DD.MM
- [ ] Filter works (ALL, ACTIVE, COMPLETED, CANCELLED)

---

### Test 3.3: Order with Individual Items (Digital Keys)
**Setup**: Order digital items with unique keys/codes (e.g., game keys)

**Steps**:
1. Create order with 5 digital items (each has unique key)
2. View order in history

**Expected Result**:
```
Steam Key
 Anzahl: 5 Stk.
 Stückpreis: 10,00 €

Staffelpreise:
  5 × 10,00 € =   50,00 €
──────────────────────────
               Σ   50,00 €
               Ø   10,00 €/Stk.

🔑 Ihre Keys:
KEY-XXXXX-XXXXX
KEY-YYYYY-YYYYY
KEY-ZZZZZ-ZZZZZ
KEY-AAAAA-AAAAA
KEY-BBBBB-BBBBB

⚠️ Diese Daten werden nach 30 Tagen automatisch gelöscht.
```

**Verification**:
- [ ] Tier breakdown shown for grouped view
- [ ] Individual keys listed separately
- [ ] Retention notice displayed
- [ ] Keys remain unique (not grouped)

---

## Phase 4: Admin Order Management Tests

### Test 4.1: Admin Order List
**Steps**:
1. Login as admin
2. Open "Bestellungen verwalten"
3. View order list

**Expected Result**:
```
Bestellungsverwaltung
Filter: Erfordert Aktion

📦 DD.MM • SHORT_ID • Warte auf Versand
✅ DD.MM • SHORT_ID • Bezahlt
⏳ DD.MM • SHORT_ID • Warte auf Zahlung

[Pagination]
[Filter ändern]
[Zurück]
```

**Verification**:
- [ ] Admin sees all orders (not just own)
- [ ] Default filter: REQUIRES_ACTION
- [ ] Status emojis consistent with user view

---

### Test 4.2: Admin Order Detail View
**Steps**:
1. Select order with multiple tiers from admin list
2. View order details

**Expected Result**:
```
Bestellung #XXXXX
Kunde: @username

Status: Bezahlt - Warte auf Versand 📦
Erstellt: [timestamp]
Bezahlt: [timestamp]

iPhone 15 Pro
 Anzahl: 17 Stk.
 Stückpreis: 9,53 €

Staffelpreise:
 10 ×  9,00 € =   90,00 €
  5 × 10,00 € =   50,00 €
  2 × 11,00 € =   22,00 €
──────────────────────────
               Σ  162,00 €
               Ø    9,53 €/Stk.

Zwischensumme: 162,00 €
Versand: 4,99 €
──────────────────────────
Gesamtsumme: 166,99 €

📬 Lieferadresse:
[ACTUAL DECRYPTED ADDRESS FOR ADMIN]

[Als versandt markieren]
[Bestellung stornieren]
[Zurück]
```

**Verification**:
- [ ] Tier breakdown visible to admin
- [ ] Admin sees actual decrypted shipping address
- [ ] Customer username shown
- [ ] Action buttons context-aware (based on status)
- [ ] All prices match order creation

---

### Test 4.3: Admin Action Buttons
**Steps**:
1. View order with status PAID_AWAITING_SHIPMENT
2. Tap "Als versandt markieren"
3. Confirm

**Expected Result**:
- [ ] Order status changes to SHIPPED
- [ ] "Als versandt markieren" button disappears
- [ ] Tier breakdown still visible
- [ ] User receives notification

---

## Phase 5: Edge Cases & Error Handling

### Test 5.1: Fallback to Legacy Pricing
**Setup**: Item with NO price tiers configured

**Steps**:
1. Add item to cart (no tiers)
2. View cart

**Expected Result**:
```
Product Without Tiers
 Anzahl: 5 Stk.
 Stückpreis: 11,00 €

[NO TIER BREAKDOWN SECTION]

Zwischensumme: 55,00 €
```

**Verification**:
- [ ] No tier breakdown displayed
- [ ] Legacy price used (item.price)
- [ ] No errors or crashes
- [ ] Total calculated correctly

---

### Test 5.2: Mixed: Some Items Have Tiers, Some Don't
**Steps**:
1. Add Subcategory A (with tiers) - 10 items
2. Add Subcategory B (no tiers) - 5 items
3. View cart

**Expected Result**:
```
Product A (with tiers)
 Anzahl: 10 Stk.
 Stückpreis: 9,00 €

Staffelpreise:
 10 ×  9,00 € =   90,00 €
──────────────────────────
               Σ   90,00 €
               Ø    9,00 €/Stk.

Product B (no tiers)
 Anzahl: 5 Stk.
 Stückpreis: 11,00 €

[NO TIER BREAKDOWN]

Gesamtsumme: 145,00 €
```

**Verification**:
- [ ] Tier breakdown only for products with tiers
- [ ] No breakdown for legacy pricing items
- [ ] Both types coexist without errors

---

### Test 5.3: Quantity = 1 (Single Item)
**Steps**:
1. Add 1 item to cart (lowest tier)

**Expected Result**:
```
iPhone 15 Pro
 Anzahl: 1 Stk.
 Stückpreis: 11,00 €

Staffelpreise:
  1 × 11,00 € =   11,00 €
──────────────────────────
               Σ   11,00 €
               Ø   11,00 €/Stk.
```

**Verification**:
- [ ] Tier breakdown shown even for single item
- [ ] Correct tier applied (highest unit price)
- [ ] No calculation errors

---

### Test 5.4: Very Large Quantity
**Steps**:
1. Add 100 items to cart

**Expected Result**:
- [ ] Tier breakdown calculates correctly
- [ ] No overflow errors
- [ ] Alignment remains correct with large numbers
- [ ] Average price calculated correctly

**Example**:
```
Staffelpreise:
100 ×  9,00 € =  900,00 €
──────────────────────────
               Σ  900,00 €
               Ø    9,00 €/Stk.
```

---

### Test 5.5: Stock Adjustment During Checkout
**Steps**:
1. Add 17 items to cart (multiple tiers)
2. Use `simulate_stock_race_condition.py` to steal 10 items
3. Press "Zur Kasse"
4. View stock adjustment screen

**Expected Result**:
```
⚠️ Lagerbestand angepasst

iPhone 15 Pro
 Angefragt: 17 Stk.
 Verfügbar: 7 Stk.

Neue Berechnung:
  7 × 10,00 € =   70,00 €
──────────────────────────
               Σ   70,00 €
               Ø   10,00 €/Stk.

Gesamtsumme: 70,00 €

[Bestätigen]
[Abbrechen]
```

**Verification**:
- [ ] Tier breakdown recalculates with new quantity
- [ ] Correct tier applied (7 items = second tier)
- [ ] Total matches adjusted quantity
- [ ] User can confirm or cancel

---

## Phase 6: Localization Tests

### Test 6.1: German Locale (Default)
**Verification**:
- [ ] "Stk." for quantity unit
- [ ] "Staffelpreise:" for tier breakdown label
- [ ] "Versand:" for shipping label
- [ ] No hardcoded English strings

### Test 6.2: English Locale (if implemented)
**Steps**:
1. Change locale to English (if supported)
2. View cart with tier breakdown

**Expected Strings**:
- [ ] "pcs." for quantity unit
- [ ] "Tier Pricing:" for label
- [ ] "Shipping:" for shipping label

---

## Phase 7: Performance & Database Tests

### Test 7.1: No N+1 Queries in Order History
**Steps**:
1. Create 10 orders with tier pricing
2. Enable SQL query logging (`LOG_LEVEL=DEBUG`)
3. Open order history list
4. Count queries

**Expected Result**:
- [ ] Single query for orders with `selectinload()`
- [ ] No additional queries per order
- [ ] Query count < 10 (not 100+)

---

### Test 7.2: Tier Breakdown Not Stored in Order Table
**Steps**:
1. Create order with tier breakdown
2. Check database: `SELECT * FROM orders WHERE id = ?`

**Verification**:
- [ ] No `tier_breakdown` column in orders table
- [ ] Tier breakdown calculated dynamically at display time
- [ ] Legacy `total_price` still stored

---

### Test 7.3: Cart Item Stores Tier Breakdown
**Steps**:
1. Add items to cart (multiple tiers)
2. Check database: `SELECT tier_breakdown FROM cart_items WHERE id = ?`

**Expected Result**:
- [ ] `tier_breakdown` column exists
- [ ] Contains JSON string with breakdown
- [ ] JSON format matches `TierBreakdownItemDTO` structure

Example JSON:
```json
[
  {"quantity": 10, "unit_price": 9.00, "total": 90.00},
  {"quantity": 5, "unit_price": 10.00, "total": 50.00},
  {"quantity": 2, "unit_price": 11.00, "total": 22.00}
]
```

---

## Test Results Summary

### Cart Display
- [ ] Test 1.1: Single tier (below threshold)
- [ ] Test 1.2: Single tier (second threshold)
- [ ] Test 1.3: Multiple tiers (mixed)
- [ ] Test 1.4: Edit quantity in cart
- [ ] Test 1.5: Multiple subcategories
- [ ] Test 1.6: Physical + digital mix

### Order Payment Screen
- [ ] Test 2.1: Order creation
- [ ] Test 2.2: Payment confirmation

### User Order History
- [ ] Test 3.1: Order detail view
- [ ] Test 3.2: Order list view
- [ ] Test 3.3: Individual items with keys

### Admin Order Management
- [ ] Test 4.1: Admin order list
- [ ] Test 4.2: Admin order detail
- [ ] Test 4.3: Admin action buttons

### Edge Cases
- [ ] Test 5.1: Fallback to legacy pricing
- [ ] Test 5.2: Mixed tiers and no tiers
- [ ] Test 5.3: Single item
- [ ] Test 5.4: Large quantity
- [ ] Test 5.5: Stock adjustment

### Localization
- [ ] Test 6.1: German locale
- [ ] Test 6.2: English locale

### Performance
- [ ] Test 7.1: No N+1 queries
- [ ] Test 7.2: Tier breakdown not stored
- [ ] Test 7.3: Cart stores tier breakdown

---

## Notes for Tester

### Known Limitations
- Tier breakdown calculated dynamically (slight performance cost)
- Fallback to legacy pricing if calculation fails (graceful degradation)
- Individual items with unique keys show tier breakdown but remain ungrouped

### Testing Tips
1. Use real Telegram bot UI for accurate testing
2. Check SQL logs for N+1 queries (`LOG_LEVEL=DEBUG`)
3. Verify alignment with different number lengths
4. Test with different subcategories (different tier configurations)
5. Test both user and admin contexts for each scenario

### Bug Reporting
When reporting bugs, include:
- Test number and name
- Steps to reproduce
- Expected vs. actual result
- Screenshots if UI issue
- SQL logs if database issue
- Error logs if crash