-- ============================================================================
-- Strike History Detail View - Test Data Setup
-- ============================================================================
-- This file contains all SQL statements to create test data for manual testing
-- Execute with: sqlite3 data/database.db < test_data_setup.sql
-- ============================================================================

-- ============================================================================
-- Cleanup: Remove existing test data (if any)
-- ============================================================================

-- Delete in correct order (respecting foreign key constraints)
DELETE FROM user_strikes WHERE user_id IN (SELECT id FROM users WHERE telegram_id IN (111111, 222222, 333333, 444444, 555555));
DELETE FROM invoices WHERE order_id IN (SELECT id FROM orders WHERE user_id IN (SELECT id FROM users WHERE telegram_id IN (111111, 222222, 333333, 444444, 555555)));
DELETE FROM orders WHERE user_id IN (SELECT id FROM users WHERE telegram_id IN (111111, 222222, 333333, 444444, 555555));
DELETE FROM users WHERE telegram_id IN (111111, 222222, 333333, 444444, 555555);

-- ============================================================================
-- Script 1: Create Test Users
-- ============================================================================

-- Test User 1: Banned user with 3 strikes (typical case)
INSERT INTO users (telegram_id, telegram_username, strike_count, is_blocked, blocked_at, blocked_reason, top_up_amount, successful_orders_count, referral_eligible, max_referrals, successful_referrals_count)
VALUES (111111, 'test_banned_user1', 3, 1, '2025-11-10 15:30:00', '3 strikes reached (automatic ban)', 0.0, 0, 0, 10, 0);

-- Test User 2: Banned user with 15 strikes (truncation test)
INSERT INTO users (telegram_id, telegram_username, strike_count, is_blocked, blocked_at, blocked_reason, top_up_amount, successful_orders_count, referral_eligible, max_referrals, successful_referrals_count)
VALUES (222222, 'test_banned_user2', 15, 1, '2025-11-10 16:00:00', 'Multiple violations', 0.0, 0, 0, 10, 0);

-- Test User 3: Banned user without username
INSERT INTO users (telegram_id, telegram_username, strike_count, is_blocked, blocked_at, blocked_reason, top_up_amount, successful_orders_count, referral_eligible, max_referrals, successful_referrals_count)
VALUES (333333, NULL, 2, 1, '2025-11-10 17:00:00', 'Manual ban by admin', 0.0, 0, 0, 10, 0);

-- Test User 4: Banned user with HTML injection attempt in reason
INSERT INTO users (telegram_id, telegram_username, strike_count, is_blocked, blocked_at, blocked_reason, top_up_amount, successful_orders_count, referral_eligible, max_referrals, successful_referrals_count)
VALUES (444444, 'test_xss_user', 1, 1, '2025-11-10 18:00:00', '<script>alert("XSS")</script>Malicious ban', 0.0, 0, 0, 10, 0);

-- Test User 5: Banned user with no strikes (manual ban)
INSERT INTO users (telegram_id, telegram_username, strike_count, is_blocked, blocked_at, blocked_reason, top_up_amount, successful_orders_count, referral_eligible, max_referrals, successful_referrals_count)
VALUES (555555, 'test_manual_ban', 0, 1, '2025-11-10 19:00:00', 'Manual ban - no strikes', 0.0, 0, 0, 10, 0);

-- ============================================================================
-- Script 2: Create Orders and Invoices for Test User 1
-- ============================================================================

-- Create 3 orders for Test User 1
INSERT INTO orders (user_id, total_price, currency, status, expires_at, created_at, shipping_cost, total_paid_crypto, retry_count, wallet_used)
VALUES
  ((SELECT id FROM users WHERE telegram_id = 111111), 50.00, 'EUR', 'CANCELLED_BY_SYSTEM', datetime('now', '+30 minutes'), '2025-11-08 10:00:00', 0.0, 0.0, 0, 0.0),
  ((SELECT id FROM users WHERE telegram_id = 111111), 30.00, 'EUR', 'CANCELLED_BY_USER', datetime('now', '+30 minutes'), '2025-11-09 14:00:00', 0.0, 0.0, 0, 0.0),
  ((SELECT id FROM users WHERE telegram_id = 111111), 75.00, 'EUR', 'CANCELLED_BY_SYSTEM', datetime('now', '+30 minutes'), '2025-11-10 15:00:00', 0.0, 0.0, 0, 0.0);

-- Create invoices for the orders
INSERT INTO invoices (order_id, invoice_number, fiat_amount, fiat_currency, payment_address, payment_amount_crypto, payment_crypto_currency, is_partial_payment, payment_attempt, is_active)
VALUES
  ((SELECT id FROM orders WHERE user_id = (SELECT id FROM users WHERE telegram_id = 111111) AND total_price = 50.00 LIMIT 1),
   'INV-1234-ABCDEF', 50.00, 'EUR', 'bc1qtest1address', 0.0015, 'BTC', 0, 1, 1),
  ((SELECT id FROM orders WHERE user_id = (SELECT id FROM users WHERE telegram_id = 111111) AND total_price = 30.00 LIMIT 1),
   'INV-5678-GHIJKL', 30.00, 'EUR', 'bc1qtest2address', 0.0009, 'BTC', 0, 1, 1),
  ((SELECT id FROM orders WHERE user_id = (SELECT id FROM users WHERE telegram_id = 111111) AND total_price = 75.00 LIMIT 1),
   'INV-9012-MNOPQR', 75.00, 'EUR', 'bc1qtest3address', 0.0022, 'BTC', 0, 1, 1);

-- ============================================================================
-- Script 3: Create Strikes for Test User 1 (3 Strikes)
-- ============================================================================

-- Create 3 strikes for Test User 1, linked to orders
INSERT INTO user_strikes (user_id, strike_type, order_id, reason, created_at)
VALUES
  ((SELECT id FROM users WHERE telegram_id = 111111),
   'TIMEOUT',
   (SELECT id FROM orders WHERE user_id = (SELECT id FROM users WHERE telegram_id = 111111) AND total_price = 50.00 LIMIT 1),
   'Order timed out after 30 minutes',
   '2025-11-08 10:15:00'),
  ((SELECT id FROM users WHERE telegram_id = 111111),
   'LATE_CANCEL',
   (SELECT id FROM orders WHERE user_id = (SELECT id FROM users WHERE telegram_id = 111111) AND total_price = 30.00 LIMIT 1),
   'Cancelled after grace period',
   '2025-11-09 14:20:00'),
  ((SELECT id FROM users WHERE telegram_id = 111111),
   'TIMEOUT',
   (SELECT id FROM orders WHERE user_id = (SELECT id FROM users WHERE telegram_id = 111111) AND total_price = 75.00 LIMIT 1),
   'Third timeout',
   '2025-11-10 15:30:00');

-- ============================================================================
-- Script 4: Create 15 Strikes for Test User 2 (Truncation Test)
-- ============================================================================

-- Create 15 strikes for Test User 2 (no orders needed for this test)
INSERT INTO user_strikes (user_id, strike_type, order_id, reason, created_at)
VALUES
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 1', '2025-11-01 10:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 2', '2025-11-02 11:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'LATE_CANCEL', NULL, 'Strike 3', '2025-11-03 12:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 4', '2025-11-04 13:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 5', '2025-11-05 14:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'LATE_CANCEL', NULL, 'Strike 6', '2025-11-06 15:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 7', '2025-11-07 16:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 8', '2025-11-08 17:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'LATE_CANCEL', NULL, 'Strike 9', '2025-11-09 18:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 10', '2025-11-10 10:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 11', '2025-11-10 11:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'LATE_CANCEL', NULL, 'Strike 12', '2025-11-10 12:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 13', '2025-11-10 13:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 14', '2025-11-10 14:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 222222), 'TIMEOUT', NULL, 'Strike 15', '2025-11-10 15:00:00');

-- ============================================================================
-- Script 5: Create Strikes for Test Users 3 and 4
-- ============================================================================

-- Create 2 strikes for Test User 3 (no username test)
INSERT INTO user_strikes (user_id, strike_type, order_id, reason, created_at)
VALUES
  ((SELECT id FROM users WHERE telegram_id = 333333), 'TIMEOUT', NULL, 'First timeout', '2025-11-09 10:00:00'),
  ((SELECT id FROM users WHERE telegram_id = 333333), 'LATE_CANCEL', NULL, 'Late cancellation', '2025-11-10 17:00:00');

-- Create 1 strike for Test User 4 (XSS test) with HTML in reason
INSERT INTO user_strikes (user_id, strike_type, order_id, reason, created_at)
VALUES
  ((SELECT id FROM users WHERE telegram_id = 444444), 'TIMEOUT', NULL, '<b>Bold</b> and <script>alert("XSS")</script>', '2025-11-10 18:00:00');

-- ============================================================================
-- Verification Queries (Optional - for manual verification)
-- ============================================================================

-- Check created users
-- SELECT telegram_id, telegram_username, strike_count, is_blocked FROM users WHERE telegram_id IN (111111, 222222, 333333, 444444, 555555);

-- Check created orders
-- SELECT id, user_id, total_price, status FROM orders WHERE user_id IN (SELECT id FROM users WHERE telegram_id = 111111);

-- Check created invoices
-- SELECT invoice_number, order_id FROM invoices WHERE order_id IN (SELECT id FROM orders WHERE user_id IN (SELECT id FROM users WHERE telegram_id = 111111));

-- Check created strikes
-- SELECT user_id, strike_type, order_id, reason, created_at FROM user_strikes WHERE user_id IN (SELECT id FROM users WHERE telegram_id IN (111111, 222222, 333333, 444444));

-- ============================================================================
-- End of Test Data Setup
-- ============================================================================