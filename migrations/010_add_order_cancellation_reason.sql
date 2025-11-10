-- Migration: Add cancellation_reason to orders table
-- Date: 2025-11-09
-- Purpose: Store admin custom cancellation reason for display in order history

ALTER TABLE orders ADD COLUMN cancellation_reason TEXT NULL;

-- Index not needed - rarely queried, only displayed in detail view
