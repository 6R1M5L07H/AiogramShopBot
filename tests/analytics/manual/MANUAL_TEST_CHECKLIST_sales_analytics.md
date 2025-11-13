# Manual Test Checklist - Sales Analytics (Subcategory Report)

**Feature:** Sales Analytics v2 - Subcategory Sales Report + CSV Export
**Branch:** `feature/sales-analytics-subcategory-report`
**Test Date:** _________
**Tester:** _________

---

## 1. Navigation Tests

### Test 1.1: Access Sales Analytics from Analytics v2 Menu
- [ ] Admin Menu öffnen → "📊 Analytics v2"
- [ ] Analytics v2 Menu zeigt "💰 Sales Analytics" Button
- [ ] Button klicken → Sales Analytics Overview (Level 11)

### Test 1.2: Time Range Selection
- [ ] Buttons vorhanden: "Last 7 Days", "Last 30 Days", "Last 90 Days"
- [ ] "🔙 Zurück zu Analytics" Button vorhanden

---

## 2. Subcategory Report Display

### Test 2.1: 7-Tage Report
- [ ] "Last 7 Days" klicken
- [ ] Titel: "📊 Subcategory Sales Report - Last 7 Days"
- [ ] Subcategories nach Umsatz sortiert (höchster zuerst)
- [ ] Format pro Subcategory:
  - [ ] Emoji + Category > Subcategory Name
  - [ ] Tägliche Verkäufe: "DD.MM: X Stück (XXX,XX €)"
  - [ ] Nur Tage MIT Verkäufen angezeigt
  - [ ] Gesamt-Zeile: "Gesamt: X Stück (XXX,XX €)"
- [ ] Pagination Info: "[Seite X von Y]"

### Test 2.2: 30-Tage Report
- [ ] "Last 30 Days" → Report mit 30-Tage Zeitraum
- [ ] Mehr Daten als 7-Tage Report (falls vorhanden)

### Test 2.3: 90-Tage Report
- [ ] "Last 90 Days" → Report mit 90-Tage Zeitraum

### Test 2.4: Sortierung Verifizieren
- [ ] Erste Subcategory hat höchsten Umsatz
- [ ] Letzte Subcategory hat niedrigsten Umsatz
- [ ] Manuelle Stichprobe: Summen korrekt?

---

## 3. Pagination

### Test 3.1: Next Button (bei >8 Subcategories)
- [ ] "Weiter ▶" Button vorhanden (wenn mehr als PAGE_ENTRIES=8)
- [ ] Klick → Seite 2 mit neuen Subcategories
- [ ] Pagination Info updated: "[Seite 2 von Y]"

### Test 3.2: Previous Button
- [ ] Auf Seite 2: "◀ Zurück" Button vorhanden
- [ ] Klick → Zurück zu Seite 1

### Test 3.3: Edge Cases
- [ ] Seite 1: Kein "◀ Zurück" Button
- [ ] Letzte Seite: Kein "Weiter ▶" Button
- [ ] Weniger als 8 Subcategories: Keine Pagination Buttons

---

## 4. CSV Export

### Test 4.1: Export Button & Generation
- [ ] "📄 CSV Export" Button vorhanden
- [ ] Klick → Loading: "⏳ CSV wird generiert..."
- [ ] CSV als Telegram Document empfangen
- [ ] Caption: "✅ CSV Export abgeschlossen!"
- [ ] Filename: `sales_export_YYYYMMDD_HHMMSS.csv`

### Test 4.2: CSV Content Validation
- [ ] Header Spalten: date, hour, weekday, category, subcategory, quantity, is_physical, item_total_price, currency, payment_method, crypto_currency, status
- [ ] Daten: ALLE Sales Records (nicht nur aktueller Zeitraum!)
- [ ] Format: Komma-separiert, UTF-8
- [ ] Excel-kompatibel (Umlaute, Zahlen)

### Test 4.3: Nach Export Navigation
- [ ] Automatisch zurück zu Sales Analytics Overview
- [ ] Alle Buttons weiterhin funktionsfähig

---

## 5. Edge Cases

### Test 5.1: Keine Sales Data
- [ ] Leere DB → Report zeigt "Keine Verkäufe im gewählten Zeitraum gefunden."
- [ ] Nur "🔙 Zurück" Button

### Test 5.2: Nur 1 Subcategory
- [ ] 1 Subcategory in DB
- [ ] Report zeigt 1 Eintrag
- [ ] "[Seite 1 von 1]"
- [ ] Keine Pagination Buttons

### Test 5.3: Genau 8 Subcategories
- [ ] Alle 8 auf Seite 1
- [ ] "[Seite 1 von 1]"
- [ ] Keine Pagination Buttons

### Test 5.4: 9 Subcategories (2 Pages)
- [ ] Seite 1: 8 Subcategories
- [ ] "Weiter ▶" vorhanden
- [ ] Seite 2: 1 Subcategory
- [ ] "◀ Zurück" vorhanden

### Test 5.5: Refunded Orders
- [ ] Sales mit `is_refunded=True` in DB
- [ ] Report: Refunded Sales NICHT im Umsatz enthalten

### Test 5.6: CSV Export - Leere DB
- [ ] Leere DB → CSV nur mit Header (keine Daten-Zeilen)

---

## 6. Localization & Formatting

### Test 6.1: Deutsche Texte
- [ ] Alle Nachrichten auf Deutsch
- [ ] Button Labels auf Deutsch

### Test 6.2: Zahlenformat
- [ ] Deutsch: "1.234,56 €" (Punkt als Tausender, Komma als Dezimal)
- [ ] Currency Symbol "€" nach Betrag

### Test 6.3: Category Emojis
- [ ] Electronics: 📱
- [ ] Clothing: 👕
- [ ] Books: 📚
- [ ] Unknown Categories: 📦 (Default)

---

## 7. Performance

### Test 7.1: Große Datenmenge
- [ ] 100+ Subcategories → Report lädt < 3 Sekunden
- [ ] Pagination smooth ohne Delay

### Test 7.2: CSV Export Performance
- [ ] 1000+ SalesRecords → CSV generiert < 10 Sekunden
- [ ] File Size < 5 MB (Telegram Limit)

---

## 8. Integration

### Test 8.1: Analytics v2 Menu Navigation
- [ ] Von Sales Analytics zurück zu Analytics v2 Overview
- [ ] Violation Analytics öffnen → Zurück → Sales Analytics öffnen
- [ ] Keine Navigation Fehler

### Test 8.2: Order → Sales Record Integration
- [ ] Neue Order erstellen und bezahlen
- [ ] Sales Analytics öffnen
- [ ] Neue Order erscheint in Report
- [ ] Umsatz korrekt addiert

---

## Test Results Summary

**Total Tests:** 60+
**Passed:** _____
**Failed:** _____
**Blocked:** _____

### Critical Issues:
1.
2.

### Minor Issues:
1.
2.

### Notes:
