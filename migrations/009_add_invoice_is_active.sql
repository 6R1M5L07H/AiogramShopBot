-- Add is_active flag to invoices table for soft-delete functionality
-- This preserves audit trail for expired/cancelled invoices

ALTER TABLE invoices ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;

-- Create index for faster queries on active invoices
CREATE INDEX idx_invoices_is_active ON invoices(is_active);

-- Mark any invoices for expired orders as inactive
UPDATE invoices 
SET is_active = 0
WHERE order_id IN (
    SELECT id FROM orders 
    WHERE status IN ('TIMEOUT', 'CANCELLED_BY_USER', 'CANCELLED_BY_ADMIN', 'CANCELLED_BY_SYSTEM')
);
