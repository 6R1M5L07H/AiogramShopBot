# Priorisierte TODO-Liste

**Stand:** 2025-11-22
**Sortiert nach:** Kritikalität, Impact, Aufwand

---

## 🔴 KRITISCH - Sofort

### 1. Security Fixes (BLOCKER)
**Datei:** `TODO/2025-11-13_TODO_security-architecture-findings.md`
**Priorität:** CRITICAL
**Aufwand:** 2-4 Stunden

**Issues:**
- ⚠️ Webhook Secret Token Bypass (bot.py:102)
- ⚠️ Payment Webhook Signature Bypass (processing/processing.py:20-33)
- ⚠️ Destructive Auto-Migration on Schema Drift (db.py:133-144)

**Impact:**
- Angreifer können Webhook ohne Auth nutzen
- Zahlungen ohne Signatur manipulieren
- Datenverlust bei Schema-Inkonsistenz möglich

**Blocker für:** Production Deploy

---

### 2. Test Suite Failures
**Datei:** `TODO/2025-11-21_TODO_fix-session-execute-mock-tests.md`
**Priorität:** HIGH
**Aufwand:** 1-2 Stunden

**Failing Tests:**
- `test_add_to_cart_success_exact_quantity`
- `test_add_to_cart_stock_reduced`
- `test_get_cart_summary_with_items`

**Impact:**
- CI/CD zeigt Failures auf clean develop
- Keine Regression Detection möglich
- Team-Vertrauen in Tests sinkt

**Empfohlene Lösung:** Mock PriceTierRepository statt session_execute

---

## 🟠 HOCH - Diese Woche

### 3. Message Truncation (UX Failure)
**Datei:** `TODO/2025-11-19_TODO_message-truncate-4096-chars.md`
**Priorität:** HIGH
**Aufwand:** 1-2 Stunden

**Problem:**
- Telegram 4096-Zeichen-Limit
- Große Warenkorb-Messages werden nicht angezeigt (Silent Failure)
- User sieht kein Checkout-Confirmation

**Impact:** Kritischer UX-Bug bei großen Carts

**Lösung:** Message-Splitting oder Truncation mit "Mehr anzeigen"

---

### 4. SQLCipher Backup & Data Retention
**Datei:** `TODO/2025-11-18_TODO_fix-backup-sqlcipher.md`
**Priorität:** HIGH (GDPR Risk)
**Aufwand:** 2-3 Stunden

**Failing Jobs:**
- Database Backup (sqlite3 statt sqlcipher3)
- Data Retention Cleanup (await auf sync session)

**Impact:**
- Backups schlagen fehl (Datenverlust-Risiko)
- Versandadressen werden nicht nach 30 Tagen gelöscht (GDPR-Verstoß)

---

### 5. Runtime Environment Enum Bug
**Datei:** `TODO/2025-11-13_TODO_security-architecture-findings.md` (Issue #4)
**Priorität:** HIGH
**Aufwand:** 15 Minuten

**Problem:**
```python
if RUNTIME_ENVIRONMENT == "dev":  # String-Vergleich mit Enum
```

**Impact:** Log Retention immer auf Prod-Default (5 Tage) statt DEV-Config

**Lösung:** `RuntimeEnvironment.DEV` statt `"dev"`

---

## 🟡 MITTEL - Nächster Sprint

### 6. Data Cleanup - Orphaned Items
**Datei:** `TODO/2025-11-09_TODO_data-cleanup-orphaned-items.md`
**Priorität:** MEDIUM (Bugs)
**Aufwand:** 4-6 Stunden

**Bugs:**
- Kategorie-Löschung lässt Subcategories zurück
- Verkaufte Items bleiben ewig in DB
- 1595+ Duplikate in Test-Instanz

**Lösung:** Schema-Migration (category_id nullable) + Cleanup Job

---

### 7. Cancellation Invoice Display (cancellation_refund)
**Datei:** `TODO/2025-11-05_TODO_improve-cancellation-invoice-display.md`
**Priorität:** MEDIUM
**Aufwand:** 2-3 Stunden

**Problem:** Timeout/Late Cancellation Notifications zeigen keine Item-Liste (nur Refund Info)

**Impact:** User sehen nicht, was storniert wurde → Support-Anfragen

**Note:** `partial_cancellation` wurde in PR #60 gefixt, aber `cancellation_refund` ist noch offen

---

### 8. N+1 Query Optimizations (Verbleibend)
**Datei:** `TODO/2025-11-13_TODO_security-architecture-findings.md` (Issues #5, #8, #9)
**Priorität:** MEDIUM
**Aufwand:** 3-4 Stunden

**Locations (noch offen):**
- Purchase History (services/user.py:92-126)
- Sales Record Creation (services/analytics.py:93-131)
- Analytics Aggregation (repositories/sales_record.py:226-295)

**Impact:** Performance-Degradation bei großen Datenmengen

**Note:** Admin Cancellation N+1 wurde in PR #60 gefixt (batch-loading subcategories)

---

## 🟢 NIEDRIG - Backlog

### 9. Alembic Migrations
**Datei:** `TODO/2025-01-23_TODO_alembic-migrations.md`
**Priorität:** MEDIUM (Blocker für #6)
**Aufwand:** 4-8 Stunden

**Reason:** Manuelles SQL ist fehleranfällig, keine Rollback-Strategie

---

### 10. Cart Service Split (Refactoring)
**Datei:** `TODO/2025-11-10_REFACTORING_cart-service-split.md`
**Priorität:** LOW
**Aufwand:** 8-12 Stunden

**Reason:** Code Quality, nicht urgent

---

### 11. Packstation Validation
**Datei:** `TODO/2025-10-26_TODO_packstation-validation.md`
**Priorität:** LOW
**Aufwand:** 2-3 Stunden

---

### 12. Item Unit Field
**Datei:** `TODO/2025-11-07_TODO_item-unit-field.md`
**Priorität:** LOW
**Aufwand:** 2-3 Stunden

---

### 13. README Update
**Datei:** `TODO/2025-11-07_TODO_readme-update-recent-features.md`
**Priorität:** LOW
**Aufwand:** 1 Stunde

---

## 📋 Backlog - Features

**Nicht priorisiert (Discussion/Planning Phase):**
- Separate Crypto Wallets (2025-10-19)
- Admin Payment Statistics (2025-10-19)
- GPG Public Key Display (2025-10-19)
- Referral System (2025-10-19)
- Refactor Crypto Button Generation (2025-10-24)
- Cart Cleanup Job (2025-10-26)
- Item Watchlist Notification (2025-10-26)
- Admin Notification New User (2025-11-01)
- Backup Encryption GPG (2025-11-01)
- KryptoExpress Admin Dashboard (2025-11-01)
- User Management Detail View (2025-11-01)
- Vault Integration (2025-11-01)
- Eliminate Buy Model Legacy (2025-11-04)

---

## Empfohlene Reihenfolge (Next 3 Sprints)

### Sprint 1 (Diese Woche)
1. Security Fixes (#1) - BLOCKER
2. Test Suite Failures (#2) - Blockiert Development
3. Message Truncation (#3) - Critical UX Bug

### Sprint 2 (Nächste Woche)
4. SQLCipher Backup (#4) - GDPR Risk
5. Runtime Env Bug (#5) - Quick Win
6. Cancellation Invoice (#7) - Support-Entlastung

### Sprint 3 (Übernächste Woche)
7. Data Cleanup (#6) - Requires Alembic (#9)
8. N+1 Optimizations (#8) - Performance
9. Alembic Migration Setup (#9) - Foundation

---

## Metriken

**Nach Priorität:**
- 🔴 Kritisch: 2 TODOs
- 🟠 Hoch: 3 TODOs
- 🟡 Mittel: 3 TODOs
- 🟢 Niedrig: 4 TODOs
- 📋 Backlog: 15 TODOs

**Nach Aufwand:**
- Quick Wins (<1h): 2
- Kurz (1-3h): 7
- Mittel (4-8h): 3
- Lang (>8h): 2
