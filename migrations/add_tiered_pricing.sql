-- Migration: Add Tiered Pricing Support
-- Date: 2025-11-06
-- Description: Creates price_tiers table and adds tier_breakdown column to cart_items

-- ============================================
-- 1. Create price_tiers table
-- ============================================
CREATE TABLE IF NOT EXISTS price_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    min_quantity INTEGER NOT NULL CHECK (min_quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price > 0),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_price_tiers_item_id ON price_tiers(item_id);
CREATE INDEX IF NOT EXISTS idx_price_tiers_min_quantity ON price_tiers(item_id, min_quantity);

-- ============================================
-- 2. Extend cart_items table
-- ============================================
ALTER TABLE cart_items ADD COLUMN tier_breakdown TEXT NULL;
-- Format: JSON array [{"quantity": 10, "unit_price": 9.00, "total": 90.00}, ...]

-- ============================================
-- 3. Migrate existing items to single-tier system
-- ============================================
-- For each item, create a single tier with min_quantity=1 and unit_price=item.price
INSERT INTO price_tiers (item_id, min_quantity, unit_price)
SELECT id, 1, price
FROM items
WHERE price IS NOT NULL AND price > 0;

-- ============================================
-- Verification queries
-- ============================================
-- Check that all items have at least one tier:
-- SELECT COUNT(*) FROM items WHERE id NOT IN (SELECT DISTINCT item_id FROM price_tiers);
-- Expected: 0

-- Check tier counts:
-- SELECT item_id, COUNT(*) as tier_count FROM price_tiers GROUP BY item_id;