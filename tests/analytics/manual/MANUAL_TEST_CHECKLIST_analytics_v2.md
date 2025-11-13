# Manual Test Checklist - Analytics v2 Feature

**Feature Branch:** `feature/analytics-v2-admin-menu`
**Test Date:** _________
**Tester:** _________

---

## 1. Analytics v2 Admin Menu Tests

### Test 1.1: Admin Menu Button erscheint
- [x] Als Admin einloggen
- [x] Verifizieren: "Admin Menü" Button ist sichtbar
- [x] Button klicken → Admin Menu öffnet sich

### Test 1.2: Analytics v2 Navigation
- [x] Im Admin Menu: "📊 Violation Analytics" Button klicken
- [x] Verifizieren: Level 10 View öffnet sich mit Übersicht
- [x] Buttons vorhanden: "Last 7 Days", "Last 30 Days", "Last 90 Days", "🔙 Back to Admin Menu"

### Test 1.3: 7-Tage-Statistik
- [x] "Last 7 Days" Button klicken
- [x] Verifizieren: Statistik wird angezeigt mit:
  - [x] Zeitraum (letzten 7 Tage)
  - [x] Violation Counts nach Typ (payment_timeout, late_cancellation, etc.)
  - [x] Total Penalties Amount
  - [unbekannt, da alle Werte 0 sind] Top Violation Types
- [x] "🔙 Back to Overview" Button funktioniert

### Test 1.4: 30-Tage-Statistik
- [x] "Last 30 Days" Button klicken
- [x] Gleiche Verifikation wie Test 1.3:
  - [x] Zeitraum korrekt
  - [x] Violation Counts angezeigt
  - [x] Total Penalties Amount
  - [unbekannt, da alle Werte 0 sind] Top Violation Types
- [x] "🔙 Back to Overview" Button funktioniert

### Test 1.5: 90-Tage-Statistik
- [x] "Last 90 Days" Button klicken
- [x] Gleiche Verifikation wie Test 1.3:
  - [x] Zeitraum korrekt
  - [x] Violation Counts angezeigt
  - [x] Total Penalties Amount
  - [unbekannt, da alle Werte 0 sind] Top Violation Types
- [x] "🔙 Back to Overview" Button funktioniert

### Test 1.6: Navigation zurück zu Admin Menu
- [x] Von Overview: "🔙 Back to Admin Menu" klicken
- [x] Verifizieren: Zurück im Admin Menu (Level 0)

---

## 2. User Button Handler Tests

### Test 2.1: My Profile Button
- [x] Als regulärer User einloggen (nicht Admin)
- [x] "👤 My Profile" Button klicken
- [x] Verifizieren: My Profile Ansicht öffnet sich
- [x] Log-Check: "👤 MY PROFILE BUTTON HANDLER TRIGGERED" erscheint

### Test 2.2: Cart Button
- [x] "🛒 Cart" Button klicken
- [x] Verifizieren: Cart Ansicht öffnet sich

### Test 2.3: FAQ Button
- [x] "❓ FAQ" Button klicken
- [x] Verifizieren: FAQ Text wird angezeigt
- [x] Log-Check: "❓ FAQ BUTTON HANDLER TRIGGERED" erscheint

### Test 2.4: Help Button
- [x] "❔ Help" Button klicken
- [x] Verifizieren: Help Text wird angezeigt
- [x] Verifizieren: Support Link Button erscheint (wenn SUPPORT_LINK konfiguriert)
- [x] Log-Check: "❔ HELP BUTTON HANDLER TRIGGERED" erscheint

### Test 2.5: All Categories Button
- [x] "📦 All Categories" Button klicken
- [x] Verifizieren: Categories Ansicht öffnet sich

---

## 3. Filter Tests

### Test 3.1: IsUserExistFilterIncludingBanned - Existierender User
- [x] Als existierender User My Profile öffnen
- [ ] Log-Check:
  - [Suche nach diesem String ergab keinen Treffer (grep -E)] "🔍 IsUserExistFilterIncludingBanned called for user {id}"
  - [Suche nach diesem String ergab keinen Treffer (grep -E)] "🔍 IsUserExistFilterIncludingBanned result: True"

### Test 3.2: IsUserExistFilterIncludingBanned - Gebannter User
- [feature "Admin-Ban" nicht implementiert] User bannen (3 Strikes vergeben)
- [ ] Als gebannter User My Profile öffnen
- [ ] Verifizieren: My Profile öffnet sich (gebannte User dürfen Wallet top-up machen!)
- [ ] FAQ Button klicken → sollte auch funktionieren
- [ ] Help Button klicken → sollte auch funktionieren

### Test 3.3: IsUserExistFilter - Gebannter User
- [ ] Als gebannter User "All Categories" klicken
- [ ] Verifizieren: Ban-Nachricht erscheint mit:
  - [ ] Strike count
  - [ ] Unban amount
  - [ ] Currency symbol
- [ ] Verifizieren: Kein Zugriff auf Shopping/Cart

### Test 3.4: Non-Existent User Filter
- [x] Neuen Telegram-Account erstellen (oder DB User löschen)
- [x] Versuche "My Profile" zu klicken (ohne /start)
- [x] Verifizieren: Handler wird nicht getriggert
- [String nicht gefunden in den logs] Log-Check: "🔍 IsUserExistFilterIncludingBanned result: False"

---

## 4. Handler Registration Tests

### Test 4.1: Startup Logs
- [x] Bot neu starten
- [x] Log-Check für Handler Registration:
  - [x] "🔧 [run.py] BEFORE dp.include_router - about to register handlers"
  - [x] "✅ [run.py] Handlers registered with dispatcher"
- [x] Keine Fehler in Logs

### Test 4.2: Webhook Processing
- [x] Button-Klick durchführen (beliebiger Button)
- [x] Log-Check:
  - [x] "📥 Webhook received update: ..."
  - [x] "✅ Webhook processed successfully"

---

## 5. Database Persistence Tests

### Test 5.1: Violation Statistics gespeichert
- [ ] Payment Timeout simulieren (via `simulate_payment_webhook.py` mit underpayment)
- [ ] Admin Menu → Analytics v2 öffnen
- [ ] Verifizieren: Neue Violation erscheint in Statistik
- [ ] DB-Check: `violation_statistics` Tabelle hat neuen Eintrag

### Test 5.2: User Persistence nach /start
- [x] `/start` Command senden
- [x] User in DB vorhanden prüfen
- [x] Bot neu starten
- [x] My Profile öffnen → sollte funktionieren ohne erneuten `/start`

---

## 6. Edge Cases & Error Handling

### Test 6.1: Keine Violation Data vorhanden
- [x] Frische DB (keine Violations)
- [x] Admin Menu → Analytics v2 öffnen
- [diese Meldung gibt es nicht, aber alle Zahlen sind auf 0] Verifizieren: "No violations found" oder ähnliche Nachricht
- [x] Keine Exceptions in Logs

### Test 6.2: Admin + Banned User
- [ ] Admin-User bannen (falls EXEMPT_ADMINS_FROM_BAN=false)
- [ ] Als gebannter Admin "All Categories" klicken
- [ ] Verifizieren: Verhalten gemäß EXEMPT_ADMINS_FROM_BAN Config

### Test 6.3: Concurrent Button Clicks
- [x] Schnell mehrfach denselben Button klicken
- [x] Verifizieren: Throttling Middleware greift
- [x] Keine Race Conditions in Logs

### Test 6.4: Invalid Callback Data
- [N/A] Manipulierte Callback Data senden (via Debug-Tool)
- [Unklar] Verifizieren: Graceful Error Handling
- [Unklar] User bekommt sinnvolle Fehlermeldung

---

## 7. Localization Tests

### Test 7.1: German Localization
- [auf englisch getestet] Alle Analytics v2 Texte sind auf Deutsch
- [auf englisch getestet] Button Labels korrekt übersetzt
- [auf englisch getestet] Violation Type Namen lesbar (z.B. "Zahlungs-Timeout" statt "payment_timeout")

### Test 7.2: Currency Display
- [Kein Symbol, aber "EUR"] Total Penalties Amount zeigt korrektes Currency Symbol (€)
- [Auf Englisch getestet, da sieht die Darstellung gut aus] Beträge korrekt formatiert (z.B. "12,50 €" statt "12.5")

---

## Test Results Summary

**Total Tests:** 50+
**Passed:** _____
**Failed:** _____
**Blocked:** _____

### Critical Issues Found:
1.
2.
3.

### Minor Issues Found:
1.
2.
3.

### Notes:
