-- Migration: Add order_hash column to sales_records table
-- Date: 2025-11-14
-- Description: Adds order_hash column for pseudonymized order tracking in analytics

-- Add order_hash column (nullable, indexed for refund lookups)
ALTER TABLE sales_records ADD COLUMN order_hash TEXT;

-- Create index for efficient refund tracking by order_hash
CREATE INDEX IF NOT EXISTS idx_sales_records_order_hash ON sales_records(order_hash);