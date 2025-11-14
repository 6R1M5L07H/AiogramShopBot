-- Migration: Add items_snapshot to orders table
-- Date: 2025-11-13
-- Purpose: Store complete item details at order creation for historical record
--          Allows viewing cancelled order details after items are released back to stock

ALTER TABLE orders ADD COLUMN items_snapshot TEXT NULL;

-- Index not needed - only used for display in order detail view
