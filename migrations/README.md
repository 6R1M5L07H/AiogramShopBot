# Database Migrations

## Tiered Pricing System (2025-11-06)

### Problem
Shop owners need flexible pricing based on quantity without pre-packaging items into fixed bundles. Current system only supports single price per item.

### Solution
Implement tiered pricing system where items can have multiple price tiers based on quantity (e.g., 1-4 items: €11, 5-9 items: €10, 10+ items: €9).

### Migration Options

#### Option 1: Python Script (Recommended)

```bash
# From project root
# Backup first!
cp data/shop.db data/shop.db.backup

# Run migration
python migrations/add_tiered_pricing.py
```

**Advantages:**
- Detailed logging with verification
- Safe error handling
- Shows migration progress
- Automatic verification checks

#### Option 2: SQL Script (Direct)

```bash
# Backup database first
cp data/shop.db data/shop.db.backup

# Apply SQL migration
sqlite3 data/shop.db < migrations/add_tiered_pricing.sql
```

**Advantages:**
- Faster for large databases
- No Python dependencies

### What Gets Migrated

1. **New table:** `price_tiers` with item_id, min_quantity, unit_price
2. **New column:** `cart_items.tier_breakdown` (JSON field)
3. **Data migration:** All existing items get single tier (min_quantity=1, unit_price=legacy price)

### Verification

After migration, verify the setup:

```sql
-- Check that all items have tiers
SELECT COUNT(*) FROM items
WHERE id NOT IN (SELECT DISTINCT item_id FROM price_tiers);
-- Expected: 0

-- Check tier distribution
SELECT
    COUNT(DISTINCT item_id) as items_with_tiers,
    COUNT(*) as total_tiers
FROM price_tiers;

-- View sample tiers
SELECT
    pt.item_id,
    i.description,
    pt.min_quantity,
    pt.unit_price
FROM price_tiers pt
JOIN items i ON i.id = pt.item_id
ORDER BY pt.item_id, pt.min_quantity
LIMIT 10;
```

### Rollback

If needed, restore from backup:

```bash
cp data/shop.db.backup data/shop.db
```

### Backwards Compatibility

- Legacy `items.price` field is **preserved**
- If no tiers exist for an item, system falls back to legacy price
- Existing cart/orders are unaffected (they use already-calculated prices)

---

## Wallet Rounding Fix (2025-10-24)

### Problem
Floating-point precision errors caused wallet balances to have more than 2 decimal places, leading to:
- Tiny negative balances (e.g., `-1.82e-12 EUR`)
- CHECK constraint violations when trying to update wallets
- Admin unable to completely empty wallets

### Solution
Round all wallet amounts to exactly 2 decimal places.

### Migration Options

#### Option 1: Python Script (Recommended)

```bash
# From project root
python migrations/fix_wallet_rounding.py
```

**Advantages:**
- Uses existing ORM models
- Detailed logging
- Safe error handling

#### Option 2: SQL Script (Direct)

```bash
# Backup database first
cp shop.db shop.db.backup

# Apply SQL migration
sqlite3 shop.db < migrations/fix_wallet_rounding.sql
```

**Advantages:**
- Faster for large databases
- No Python dependencies

### Verification

After migration, verify that all balances are correctly rounded:

```sql
-- Check for precision errors
SELECT telegram_id, top_up_amount
FROM users
WHERE top_up_amount != ROUND(top_up_amount, 2);

-- Should return 0 rows

-- Check for negative balances
SELECT telegram_id, top_up_amount
FROM users
WHERE top_up_amount < 0;

-- Should return 0 rows
```

### Rollback

If needed, restore from backup:

```bash
cp shop.db.backup shop.db
```

### Future Prevention

All wallet operations now use `round(amount, 2)` to prevent future precision errors.
See commits:
- 5a5a99e: fix: replace deprecated consume_records with top_up_amount
- 7bc44f9: fix: prevent negative wallet balance in REDUCE_BALANCE operation
- a7bf2e7: fix: round all wallet amounts to 2 decimal places
