-- Migration: Add encryption_mode to shipping_addresses table
-- Date: 2025-11-18
--
-- Adds encryption_mode column to shipping_addresses to support both:
-- - 'aes': Server-side AES-256-GCM encryption
-- - 'pgp': Client-side PGP encryption (zero-knowledge)

ALTER TABLE shipping_addresses ADD COLUMN encryption_mode TEXT NOT NULL DEFAULT 'aes';