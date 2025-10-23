# 🧪 Testing Guide: Shipping Management System

## 📋 Prerequisites

### 1. Environment Setup
```bash
# Generate encryption key for shipping addresses
openssl rand -hex 32

# Add to .env file
SHIPPING_ADDRESS_ENCRYPTION_KEY=<your-generated-key>
DATA_RETENTION_DAYS=90
```

### 2. Database Migration
The new shipping fields will be auto-created by SQLAlchemy when you start the bot:
- `items` table: `is_physical`, `shipping_cost`, `packstation_allowed` columns
- `orders` table: `shipping_cost` column
- `shipping_addresses` table: Complete new table with encryption

**⚠️ Backup your database before testing!**
```bash
cp database.db database.db.backup
```

### 3. Import Test Data
```bash
# Start bot in admin mode
# Navigate to: Admin Menu → Lagerverwaltung → Artikel hinzufügen → JSON

# Upload the file: test_data_shipping.json
```

---

## 🧪 Test Scenarios

### Test 1: Digital-Only Order (No Shipping)
**Purpose:** Verify digital items skip shipping flow entirely

**Steps:**
1. As User: Browse to "Digital" → "Software-Lizenzen"
2. Add "Office Suite Premium" to cart
3. Go to cart → Checkout
4. **Expected:** Cart shows:
   ```
   Artikel: €49.99
   Gesamtsumme: €49.99
   ```
   (No shipping line!)
5. Click "Bestätigen"
6. **Expected:** Crypto selection appears immediately (NO address request)
7. Select crypto → Pay
8. **Expected:** Order status = PAID immediately (not AWAITING_SHIPMENT)

**✅ Pass Criteria:**
- No shipping cost shown
- No address collection triggered
- Order goes directly to PAID status

---

### Test 2: Physical-Only Order (With Shipping)
**Purpose:** Verify shipping address collection for physical items

**Steps:**
1. As User: Browse to "Elektronik" → "Smartphones"
2. Add "Premium Smartphone - 128GB" to cart
3. Go to cart → Checkout
4. **Expected:** Cart shows:
   ```
   Artikel: €299.99
   Versand: €5.99
   Gesamtsumme: €305.98
   ```
5. Click "Bestätigen"
6. **Expected:** Address request appears:
   ```
   📦 Lieferadresse benötigt

   Ihre Bestellung enthält physische Artikel, die versendet werden müssen.

   Bitte geben Sie Ihre vollständige Lieferadresse ein...
   ```
7. Enter address (free text):
   ```
   Max Mustermann
   Musterstraße 123
   12345 Berlin
   Deutschland
   ```
8. **Expected:** Confirmation screen with address preview
9. Click "Bestätigen"
10. **Expected:** Crypto selection appears
11. Select crypto → Pay
12. **Expected:** Order status = AWAITING_SHIPMENT (not PAID)

**✅ Pass Criteria:**
- Shipping cost calculated correctly (€5.99)
- Address collection triggered
- Address stored encrypted in database
- Order status = AWAITING_SHIPMENT after payment

---

### Test 3: Mixed Cart (Physical + Digital)
**Purpose:** Verify correct shipping calculation for mixed carts

**Steps:**
1. As User: Add multiple items:
   - "Premium Smartphone - 128GB" (€299.99, shipping €5.99)
   - "Noise-Cancelling Kopfhörer" (€149.99, shipping €4.99)
   - "Office Suite Premium" (€49.99, digital)
2. Go to cart → Checkout
3. **Expected:** Cart shows:
   ```
   Artikel: €499.97
   Versand: €5.99
   Gesamtsumme: €505.96
   ```
   (Max shipping wins: €5.99 from smartphone, NOT €4.99+€5.99)
4. Complete checkout with address
5. **Expected:** Order status = AWAITING_SHIPMENT

**✅ Pass Criteria:**
- Shipping = MAX(all physical item shipping costs)
- NOT sum of all shipping costs
- Address required because cart has physical items

---

### Test 4: Packstation Restriction Warning
**Purpose:** Verify Packstation warning for restricted items

**Steps:**
1. As User: Add "10-inch Tablet with Stylus" (packstation_allowed=false)
2. Go to cart → Checkout → Bestätigen
3. **Expected:** Address request shows additional warning:
   ```
   ⚠️ Hinweis: Ihre Bestellung enthält Artikel, die NICHT an
   eine Packstation geliefert werden können. Bitte geben Sie
   eine vollständige Hausadresse an.
   ```

**✅ Pass Criteria:**
- Warning appears for Packstation-restricted items
- No warning for Packstation-allowed items

---

### Test 5: Admin Shipping Management
**Purpose:** Verify admin can mark orders as shipped

**Steps:**
1. Complete Test 2 or Test 3 (create order with AWAITING_SHIPMENT status)
2. As Admin: Navigate to "Admin Menu" → "Versandverwaltung"
3. **Expected:** List shows pending orders:
   ```
   📦 Order #INV-12345 | @username | €305.98
   ```
4. Click on order
5. **Expected:** Order details screen shows:
   - Order ID
   - User info
   - Total price
   - Decrypted shipping address (!)
   - Items list
6. Click "Als versendet markieren"
7. **Expected:** Confirmation screen
8. Confirm
9. **Expected:** Success message, user gets Telegram notification
10. Check order status in database
11. **Expected:** Order status = SHIPPED

**✅ Pass Criteria:**
- Admin sees decrypted address
- User receives "Order shipped" notification
- Order status changes to SHIPPED

---

### Test 6: Address Encryption Verification
**Purpose:** Verify addresses are encrypted in database

**Steps:**
1. Complete Test 2 (create order with address)
2. Open database with SQLite browser:
   ```bash
   sqlite3 database.db
   SELECT * FROM shipping_addresses;
   ```
3. **Expected:** `address_encrypted` column contains binary/hex data, NOT plaintext
4. In Admin UI: View order details
5. **Expected:** Address is decrypted and readable

**✅ Pass Criteria:**
- Database stores encrypted bytes
- Admin UI shows decrypted plaintext

---

### Test 7: Address Validation
**Purpose:** Verify minimum address length validation

**Steps:**
1. Start checkout with physical item
2. Enter very short address: "Test"
3. **Expected:** Error message:
   ```
   ⚠️ Bitte geben Sie eine gültige Lieferadresse ein.
   ```
4. Enter address with 10+ characters
5. **Expected:** Confirmation screen appears

**✅ Pass Criteria:**
- Addresses < 10 chars rejected
- Addresses ≥ 10 chars accepted

---

### Test 8: Order Cancellation (With Physical Items)
**Purpose:** Verify address handling when order is cancelled

**Steps:**
1. Create order with physical items + address
2. Cancel order (within grace period)
3. **Expected:** Order cancelled, address remains in database
4. Check database: `shipping_addresses` table
5. **Expected:** Address record still exists (for audit/GDPR compliance)

**Note:** Address auto-deletion after DATA_RETENTION_DAYS is a future feature

**✅ Pass Criteria:**
- Order cancellation works normally
- Address not immediately deleted

---

### Test 9: JSON Import with Shipping Fields
**Purpose:** Verify JSON import validates shipping fields

**Test Data:**
```json
[
  {
    "category": "Test",
    "subcategory": "MissingFields",
    "price": 99.99,
    "description": "Physical item without shipping fields",
    "private_data": "DATA",
    "is_physical": true
  }
]
```

**Steps:**
1. As Admin: Try to import above JSON
2. **Expected:** Error message:
   ```
   ⚠️ Ausnahme:
   Physical item 'Physical item without shipping fields' missing required field 'shipping_cost'
   ```

**✅ Pass Criteria:**
- Import fails with clear error
- No items added to database

---

### Test 10: Purchase History Display
**Purpose:** Verify purchase history shows retention period

**Steps:**
1. As User: Navigate to "Mein Profil" → "Kaufhistorie"
2. **Expected:** Header shows:
   ```
   🧾 Ihre Käufe (letzte 90 Tage):
   ```
   (Number matches DATA_RETENTION_DAYS from .env)

**✅ Pass Criteria:**
- Retention period displayed correctly
- Matches .env config

---

## 🔍 Database Verification Queries

```sql
-- Check items have shipping fields
SELECT id, description, is_physical, shipping_cost, packstation_allowed
FROM items
LIMIT 10;

-- Check orders have shipping_cost
SELECT id, status, total_price, shipping_cost
FROM orders
WHERE status IN ('AWAITING_SHIPMENT', 'SHIPPED');

-- Check encrypted addresses exist
SELECT id, order_id, created_at, length(address_encrypted) as encrypted_bytes
FROM shipping_addresses;

-- Check order status flow
SELECT status, COUNT(*)
FROM orders
GROUP BY status;
```

---

## 🐛 Common Issues & Solutions

### Issue: "Encryption key not found"
**Solution:** Set `SHIPPING_ADDRESS_ENCRYPTION_KEY` in .env (32 bytes hex)

### Issue: "Address always shows decrypted in DB"
**Solution:** You're looking at wrong column - check `address_encrypted` not a text field

### Issue: "Shipping cost not added to order"
**Solution:** Check `ItemRepository.get_single()` returns items with shipping_cost field

### Issue: "Admin can't see shipping management button"
**Solution:** Check `ShippingManagementCallback` is imported in admin.py

### Issue: "FSM state not working"
**Solution:** Ensure Redis is running and FSMContext is passed to handlers

---

## ✅ Final Checklist

Before marking shipping feature as complete:

- [ ] All 10 test scenarios pass
- [ ] Database queries show correct data structure
- [ ] Encryption key generated and set in .env
- [ ] Test data imported successfully
- [ ] Admin can decrypt and view addresses
- [ ] Users receive shipped notifications
- [ ] Localization works in both DE and EN
- [ ] No errors in bot logs during testing
- [ ] Purchase history shows retention period
- [ ] JSON import validation catches errors

---

## 📊 Expected Test Results Summary

| Test | Scenario | Expected Result |
|------|----------|----------------|
| 1 | Digital-only | No shipping, direct to PAID |
| 2 | Physical-only | Address collected, AWAITING_SHIPMENT |
| 3 | Mixed cart | Max shipping cost, address required |
| 4 | Packstation warning | Warning shown for restricted items |
| 5 | Admin mark shipped | Status→SHIPPED, user notified |
| 6 | Encryption | DB encrypted, Admin decrypted |
| 7 | Address validation | Short addresses rejected |
| 8 | Order cancellation | Works normally, address kept |
| 9 | JSON validation | Missing fields rejected |
| 10 | Purchase history | Retention period shown |

---

## 🎯 Success Criteria

✅ **Feature is production-ready when:**
1. All 10 tests pass without errors
2. Database migration completes successfully
3. Encryption/decryption works correctly
4. Admin and user workflows are intuitive
5. No security vulnerabilities (encrypted addresses)
6. Localization complete (DE + EN)
7. Performance acceptable (encryption doesn't slow checkout)

---

**Good luck with testing! 🚀**
