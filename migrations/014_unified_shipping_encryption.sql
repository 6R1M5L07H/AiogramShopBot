-- Migration: Unified Shipping Address Encryption Storage
-- Date: 2025-01-15
-- Description: Add unified encryption fields to orders table for both PGP and AES-GCM

-- Add encryption_mode column (enum-like constraint)
ALTER TABLE orders ADD COLUMN encryption_mode TEXT CHECK(encryption_mode IN ('aes-gcm', 'pgp'));

-- Add encrypted_payload column (binary storage)
ALTER TABLE orders ADD COLUMN encrypted_payload BLOB;

-- Index for performance
CREATE INDEX idx_orders_encryption_mode ON orders(encryption_mode)
WHERE encryption_mode IS NOT NULL;

-- Note: shipping_addresses table will be deprecated after migration
-- Old data will be migrated via Python script: 014_unified_shipping_encryption.py
