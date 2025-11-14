-- Migration: Add refund_breakdown_json to orders table
-- Date: 2025-11-13
-- Purpose: Store refund calculation details for cancelled orders (especially mixed orders)
--          Allows displaying which items were refunded in order detail view

ALTER TABLE orders ADD COLUMN refund_breakdown_json TEXT NULL;

-- Index not needed - only used for display in order detail view
