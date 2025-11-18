-- Migration: Add PGP Encryption Support for Shipping Addresses
-- Date: 2025-11-16
--
-- Adds dual-mode encryption columns to orders table:
-- - encryption_mode: 'aes-gcm' (server-side) or 'pgp' (client-side)
-- - encrypted_payload: Binary encrypted data (BLOB)

-- Step 1: Add encryption_mode column
ALTER TABLE orders ADD COLUMN encryption_mode TEXT NULL;

-- Step 2: Add encrypted_payload column
ALTER TABLE orders ADD COLUMN encrypted_payload BLOB NULL;

-- Migration complete
-- Next steps:
-- 1. Configure PGP_PUBLIC_KEY_BASE64 in .env
-- 2. Configure BOT_DOMAIN in .env
-- 3. Generate PGP keypair: bash tools/setup_pgp_keys.sh