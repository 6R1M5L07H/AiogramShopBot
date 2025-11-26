# Item Unit Field - Test Manual

This manual describes how to test the Item Unit Field feature on the test system.

## Prerequisites

- Test system running (Docker Compose or local)
- Admin access to the bot
- Clean database or ability to create test items

## Test Scope

**What we're testing:**
- Items can specify custom measurement units
- Units are validated during item creation
- Units are localized for display (text-based units only)
- Units appear in cart, checkout, invoices, and order confirmations

**What's already tested by unit tests:**
- ItemUnit enum validation (18 tests)
- Localizator unit localization (45 tests)
- Edge cases (empty strings, invalid units, whitespace)

## Test Cases

### 1. Item Generation with Unit Field

**Goal:** Verify items can be created with custom units using the generation script.

**Steps:**
```bash
cd /Users/mhasselman001/git/AiogramShopBot-gpg-key-item-unit-field
python docs/generate-items/generate_items.py --template docs/generate-items/generic_shop_template.json --admin YOUR_TELEGRAM_USERNAME
```

**Expected Result:**
- Script runs without errors
- Items are created in database with `unit` field populated
- Default unit is "pcs." for items without explicit unit in template

**Verification:**
```bash
sqlite3 data/shop.db "SELECT id, description, unit FROM items LIMIT 5;"
```

### 2. Cart Display with Units

**Goal:** Verify units are displayed in cart view.

**Steps:**
1. Add items with different units to cart:
   - Item with "pcs." (pieces)
   - Item with "kg" (kilograms)
   - Item with "l" (liters)
2. View cart via bot command

**Expected Result:**
- Cart shows quantity with localized unit for text-based units (e.g., "5 Stk." in German)
- Cart shows quantity with international unit for metric units (e.g., "2 kg")

**Screenshots Location:** `docs/testing/screenshots/cart_units_*.png`

### 3. Checkout Display with Units

**Goal:** Verify units are displayed in checkout invoice.

**Steps:**
1. Proceed to checkout with items in cart
2. View invoice before payment

**Expected Result:**
- Invoice shows each item with its unit
- Format: "Quantity x Item Description (Unit: <localized_unit>)"
- Example: "5 x Premium License (Einheit: Stk.)"

**Screenshots Location:** `docs/testing/screenshots/checkout_units_*.png`

### 4. Order Confirmation with Units

**Goal:** Verify units are displayed in order confirmation after payment.

**Steps:**
1. Complete an order (use wallet balance or test payment)
2. View order confirmation message

**Expected Result:**
- Order confirmation shows items with units
- Private data delivered with unit information

**Screenshots Location:** `docs/testing/screenshots/order_units_*.png`

### 5. Unit Localization (German/English)

**Goal:** Verify text-based units are localized, metric units pass through.

**Test Matrix:**

| Unit   | EN Display | DE Display | Type         |
|--------|------------|------------|--------------|
| pcs.   | pcs.       | Stk.       | Text (local) |
| pairs  | pairs      | Paare      | Text (local) |
| pkg.   | pkg.       | Pkg.       | Text (local) |
| g      | g          | g          | Metric       |
| kg     | kg         | kg         | Metric       |
| ml     | ml         | ml         | Metric       |
| l      | l          | l          | Metric       |
| m      | m          | m          | Metric       |
| m2     | m2         | m2         | Metric       |

**Steps:**
1. Change bot language to German (if not default)
2. Add items with each unit type to cart
3. Change bot language to English
4. Compare displays

**Expected Result:**
- Text-based units change with language
- Metric units remain unchanged across languages

### 6. Invalid Unit Handling

**Goal:** Verify invalid units are rejected with helpful error messages.

**Steps:**
1. Modify `generic_shop_template.json` with invalid unit: `"unit": "oz"`
2. Run generation script

**Expected Result:**
- Script shows error: "Invalid unit 'oz'. Valid units: pcs., pairs, pkg., g, kg, ml, l, m, m2"
- No items created
- Existing items unchanged

### 7. Missing Unit Field (Backward Compatibility)

**Goal:** Verify existing items without unit field default to "pcs."

**Steps:**
1. Check database for items created before this feature
2. View items in cart/checkout

**Expected Result:**
- Items without `unit` field show "pcs." (or localized "Stk." in German)
- No errors or crashes

### 8. Unit Field Length Validation

**Goal:** Verify unit field respects 10-character limit.

**Steps:**
1. Try to create item with 11-character unit in template
2. Run generation script

**Expected Result:**
- Validation error during generation
- Error message indicates max length (10 chars)

### 9. Tiered Pricing with Units

**Goal:** Verify units work correctly with tiered pricing.

**Steps:**
```bash
python docs/generate-items/generate_items.py --template docs/generate-items/tier_pricing_template.json --admin YOUR_TELEGRAM_USERNAME
```

**Expected Result:**
- Items with price tiers show unit in all tier displays
- Example: "1-4 Stk.: €11.00" / "5-9 Stk.: €10.00" / "10+ Stk.: €9.00"

### 10. Admin Item Management

**Goal:** Verify admins can see/edit units when managing inventory.

**Steps:**
1. Use admin interface to view item details
2. Check if unit is displayed
3. (If edit functionality exists) Try editing unit

**Expected Result:**
- Unit field visible in admin item view
- Unit can be edited if functionality exists
- Changes persist to database

## Running Unit Tests

**Quick verification before manual testing:**

```bash
cd /Users/mhasselman001/git/AiogramShopBot-gpg-key-item-unit-field

# Run ItemUnit enum tests
python -m pytest tests/enums/unit/test_item_unit.py -v

# Run Localizator unit tests
python -m pytest tests/utils/unit/test_localizator_unit.py -v

# Run all unit tests (safe, no DB mutations)
python tests/run_safe_tests.py
```

**Expected Result:**
- All 18 ItemUnit tests pass
- All 45 Localizator unit tests pass
- No errors or failures

## Test Data Cleanup

**After testing, clean up test data:**

```bash
# Remove generated test items (adjust IDs as needed)
sqlite3 data/shop.db "DELETE FROM items WHERE description LIKE '%Test%';"

# Or reset entire database (CAUTION: loses all data)
rm data/shop.db
python migrations/run_migrations.py
```

## Known Limitations

1. **No live unit editing in bot:** Units can only be set during item creation via generation script or direct DB insert
2. **No unit conversion:** 1000g ≠ 1kg in the system (they're separate units)
3. **No validation of unit-quantity combinations:** System allows "0.5 pcs." even if fractional pieces don't make sense

## Bug Reporting

If you find issues during testing:

1. Note the exact steps to reproduce
2. Take screenshots if UI-related
3. Check logs: `docker logs <container_name>` or local logs
4. Report with:
   - Test case number
   - Expected vs actual behavior
   - Error messages (if any)
   - Database state (if relevant)

## Success Criteria

✅ All 10 test cases pass without errors
✅ Units display correctly in all views (cart, checkout, order)
✅ Localization works as expected (text vs metric units)
✅ Invalid units are rejected with helpful errors
✅ Backward compatibility maintained (missing units default to "pcs.")
✅ No regressions in existing functionality (tiered pricing, admin functions)
