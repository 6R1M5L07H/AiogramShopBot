# Manual Test Plan: Strike History Detail View

## Test Environment Setup

### Prerequisites
- Test Telegram Bot running in dev mode
- Admin account configured
- Database with test users
- Access to database for direct manipulation

### Test Data Setup

Execute the SQL file to create all test data:

```bash
sqlite3 data/database.db < docs/features/strike-history-detail-view/test_data_setup.sql
```

The SQL file creates:
- **5 Test Users** (111111-555555) with different scenarios
- **3 Orders** and **3 Invoices** for Test User 1
- **3 Strikes** for Test User 1 (linked to orders)
- **15 Strikes** for Test User 2 (truncation test)
- **2 Strikes** for Test User 3 (no username)
- **1 Strike** for Test User 4 (XSS test)
- **0 Strikes** for Test User 5 (manual ban)

See `test_data_setup.sql` in this directory for complete SQL statements.

---

## Test Cases

### TC-01: Navigation from Banned Users List

**Objective**: Verify navigation to detail view works correctly.

**Steps**:
1. Log in to bot as admin
2. Navigate to Admin Menu → User Management → Credit Management → Unban User
3. Banned users list should display
4. Click on any banned user (e.g., `@test_banned_user1`)

**Expected Result**:
- Detail view appears showing user header, strike history, and ban information
- "Unban" and "Back" buttons visible
- No errors in bot logs

**Status**: [PASS]

---

### TC-02: Strike History Display (3 Strikes)

**Objective**: Verify strikes are displayed correctly with proper formatting.

**Setup**: Use Test User 1 (3 strikes)

**Steps**:
1. Navigate to Test User 1 detail view
2. Read the strike history section

**Expected Result**:
- **Header**: Shows username, Telegram ID, strike count (3)
- **Strike History**: 3 strikes listed
- **Sorting**: Newest strike first (10.11.2025, then 09.11.2025, then 08.11.2025)
- **Each Strike Shows**:
  - Date and time (DD.MM.YYYY HH:MM format)
  - Strike type (localized: "Timeout" or "Verspätete Stornierung")
  - Order Invoice ID (e.g., `INV-1234-ABCDEF`)
  - Reason text
- **Ban Info**: Shows ban date and reason at bottom

**Status**: [PASS]

---

### TC-03: Strike Truncation (15 Strikes)

**Objective**: Verify only 10 strikes are shown with truncation message.

**Setup**: Use Test User 2 (15 strikes)

**Steps**:
1. Navigate to Test User 2 detail view
2. Count displayed strikes

**Expected Result**:
- Only 10 strikes visible
- Truncation message displayed: "... und 5 weitere" (DE) or "... and 5 more" (EN)
- Total strike count reflects all 15 strikes

**Status**: [PASS]

---

### TC-04: User Without Username

**Objective**: Verify handling of users without `telegram_username`.

**Setup**: Use Test User 3 (no username)

**Steps**:
1. Navigate to Test User 3 detail view

**Expected Result**:
- Header shows `ID: 333333` instead of `@username`
- All other information displays correctly
- No null/undefined errors

**Status**: [PASS]

---

### TC-05: HTML Injection Prevention

**Objective**: Verify HTML escaping prevents XSS attacks.

**Setup**: Use Test User 4 (malicious HTML in ban reason)

**Steps**:
1. Navigate to Test User 4 detail view
2. Check ban reason display

**Expected Result**:
- HTML tags are escaped and displayed as text
- Ban reason shows: `<script>alert("XSS")</script>Malicious ban`
- Script does NOT execute
- No broken HTML rendering

**Status**: [PASS]

---

### TC-06: User Without Strikes (Manual Ban)

**Objective**: Verify handling of banned users with no strikes.

**Setup**: Use Test User 5 (0 strikes)

**Steps**:
1. Navigate to Test User 5 detail view

**Expected Result**:
- Header shows strike count: 0
- Strike history section shows: "Keine Strikes gefunden" (DE) or "No strikes found" (EN)
- Ban information still displays correctly
- Unban button still works

**Status**: [PASS]

---

### TC-07: Invoice ID Display (With Order)

**Objective**: Verify invoice numbers are correctly resolved from orders.

**Setup**: Test User 1 strike with linked order

**Steps**:
1. Navigate to Test User 1 detail view
2. Check first two strikes (have orders)

**Expected Result**:
- Strike shows invoice number format: `INV-XXXX-XXXXXX`
- Invoice number matches order's first invoice in database

**Status**: [PASS]

---

### TC-08: Missing Order Handling

**Objective**: Verify strikes with no order show fallback text.

**Setup**: Manually create a strike without `order_id` for Test User 1 (via SQL):
```sql
INSERT INTO user_strikes (user_id, strike_type, order_id, reason, created_at)
VALUES ((SELECT id FROM users WHERE telegram_id = 111111), 'TIMEOUT', NULL, 'Admin-created test strike', '2025-11-11 12:00:00');
```

**Steps**:
1. Navigate to Test User 1 detail view
2. Check the newest strike (no order)

**Expected Result**:
- Strike shows "Keine Order" (DE) or "No Order" (EN) instead of invoice number
- No errors or null values displayed
- Other strike data displays correctly

**Status**: [PASS]

---

### TC-09: Back Button Navigation

**Objective**: Verify back button returns to banned users list.

**Steps**:
1. From any banned user detail view
2. Click "Zurück" (Back) button

**Expected Result**:
- Returns to Level 2 (Banned Users List)
- List pagination state preserved
- No errors

**Status**: [PASS]

---

### TC-10: Unban Button Navigation

**Objective**: Verify unban button leads to confirmation screen.

**Steps**:
1. From any banned user detail view
2. Click "Entsperren" (Unban) button

**Expected Result**:
- Navigates to Level 4 (Unban Confirmation)
- Confirmation message displays user information
- "Confirm" and "Cancel" buttons visible

**Status**: [PASS]

---

### TC-11: Localization (German)

**Objective**: Verify all text is properly localized in German.

**Setup**: Bot language set to German (DE)

**Steps**:
1. Navigate through banned user detail view
2. Check all labels and messages

**Expected Result**:
- Header: "Gesperrter Benutzer"
- Strike History: "Strike-Historie"
- Strike Types: "Timeout", "Verspätete Stornierung"
- Ban Info: "Sperrinfo", "Gesperrt am"
- Buttons: "Entsperren", "Zurück"
- No English text visible

**Status**: [ ]

---

### TC-12: Localization (English)

**Objective**: Verify all text is properly localized in English.

**Setup**: Bot language set to English (EN)

**Steps**:
1. Navigate through banned user detail view
2. Check all labels and messages

**Expected Result**:
- Header: "Banned User"
- Strike History: "Strike History"
- Strike Types: "Timeout", "Late Cancellation"
- Ban Info: "Ban Information", "Banned on"
- Buttons: "Unban", "Back"
- No German text visible

**Status**: [ ]

---

### TC-13: Regression - Refund Flow Still Works

**Objective**: Verify Level 3 router doesn't break existing refund functionality.

**Steps**:
1. Navigate to Admin Menu → User Management → Credit Management → Refund
2. Select a buy to refund
3. Confirm refund

**Expected Result**:
- Refund confirmation screen appears (Level 3, REFUND operation)
- Refund processes successfully
- No errors related to Level 3 routing

**Status**: [ ]

---

### TC-14: Non-Existent User Handling

**Objective**: Verify error handling for invalid user IDs.

**Setup**: Manually trigger callback with non-existent user ID (e.g., modify callback_data in database or via bot API)

**Steps**:
1. Trigger `UserManagementCallback` with `level=3, operation=UNBAN_USER, page=99999`

**Expected Result**:
- Error message: "Benutzer nicht gefunden" (User not found)
- Back button displayed
- No crash or stack trace

**Status**: [ ]

---

## Test Completion Summary

**Total Test Cases**: 14
**Passed**: 10
**Failed**: 0
**Blocked**: 4 (TC-11, TC-12, TC-13, TC-14 - not tested)

**Test Results**:
- TC-01: Navigation from Banned Users List - PASS
- TC-02: Strike History Display (3 Strikes) - PASS
- TC-03: Strike Truncation (15 Strikes) - PASS
- TC-04: User Without Username - PASS
- TC-05: HTML Injection Prevention - PASS
- TC-06: User Without Strikes (Manual Ban) - PASS
- TC-07: Invoice ID Display (With Order) - PASS
- TC-08: Missing Order Handling - PASS
- TC-09: Back Button Navigation - PASS
- TC-10: Unban Button Navigation - PASS
- TC-11: Localization (German) - NOT TESTED
- TC-12: Localization (English) - NOT TESTED
- TC-13: Regression - Refund Flow Still Works - NOT TESTED
- TC-14: Non-Existent User Handling - NOT TESTED

**Notes**:
- All core functionality tests passed (TC-01 to TC-10)
- Strike history displays correctly with proper formatting
- HTML escaping works (XSS prevention verified)
- Invoice resolution from orders works correctly
- Back button navigation fixed (previously went to REFUND menu, now correctly returns to banned users list)
- Unban confirmation dialog implemented and working (TC-10 fix)
- Localization and regression tests not executed in this test run

**Tested By**: mhasselman001
**Date**: 2025-11-12
**Bot Version**: feature/strike-history-detail-view (commit c6658e7)