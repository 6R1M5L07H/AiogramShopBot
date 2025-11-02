# Manual Test: Shipping Management Refactoring

**Date:** 2025-11-02
**Branch:** feature/strike-system (oder technical-debt)
**Tester:** [Dein Name]
**Testsystem:** Development

---

## Testkonten

- **Admin-Konto:** [Admin Telegram Username/ID]
- **User-Konto:** [User Telegram Username/ID]

---

## Vorbereitung: Testbestellung erstellen

### Setup: Bestellung mit physischen Items erstellen

**Konto:** User-Konto

- [ ] 1. Bot starten
- [ ] 2. Kategorien durchsuchen und physisches Item finden
- [ ] 3. Item zum Warenkorb hinzufügen
- [ ] 4. Checkout starten
- [ ] 5. Versandadresse eingeben (Testadresse):
  ```
  Max Mustermann
  Musterstraße 123
  12345 Musterstadt
  Deutschland
  ```
- [ ] 6. Zahlungsart wählen (Crypto oder Wallet)
- [ ] 7. Zahlung durchführen (Test-Zahlung simulieren)
- [ ] 8. **Notiere Invoice-Nummer:** `INV-________`

**Erwartung:**
- ✅ Bestellung erfolgreich erstellt
- ✅ Status: PAID_AWAITING_SHIPMENT
- ✅ User erhält Bestellbestätigung

---

## Test 1: Empty State (Keine ausstehenden Bestellungen)

**Voraussetzung:** Keine Bestellungen in PAID_AWAITING_SHIPMENT Status

**Konto:** Admin-Konto

- [ ] 1. Bot öffnen
- [ ] 2. "Admin Menu" klicken
- [ ] 3. "Shipping Management" klicken

**Erwartetes Ergebnis:**
- [ ] ✅ Message: "Keine Bestellungen warten auf Versand" (oder EN: "No orders awaiting shipment")
- [ ] ✅ "Back to Menu" Button sichtbar
- [ ] ✅ Kein Crash, keine Fehlermeldung

**Tatsächliches Ergebnis:**
```
[Beschreibe was passiert ist]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Test 2: Bestellungsliste anzeigen (Mit Bestellungen)

**Voraussetzung:** Mindestens 1 Bestellung aus Setup vorhanden

**Konto:** Admin-Konto

- [ ] 1. Admin Menu → Shipping Management

**Erwartetes Ergebnis:**
- [ ] ✅ Liste zeigt mindestens 1 Bestellung
- [ ] ✅ Jede Zeile zeigt:
  - [ ] 📦 Icon
  - [ ] Datum/Zeit (z.B. "02.11 14:30")
  - [ ] Invoice-Nummer (z.B. "INV-12345")
  - [ ] Username + ID (z.B. "@testuser (ID:123456789)")
  - [ ] Gesamtpreis (z.B. "50.00€")
- [ ] ✅ "View Details" Button pro Bestellung
- [ ] ✅ "Back to Menu" Button am Ende

**Tatsächliches Ergebnis:**
```
[Beschreibe was angezeigt wird]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Test 3: Bestelldetails anzeigen

**Konto:** Admin-Konto

- [ ] 1. Shipping Management Liste öffnen
- [ ] 2. Auf eine Bestellung klicken ("View Details")

**Erwartetes Ergebnis:**
- [ ] ✅ Header zeigt:
  - [ ] Invoice-Nummer
  - [ ] Username
  - [ ] User ID
- [ ] ✅ Items aufgelistet:
  - [ ] Digitale Items (falls vorhanden): Unter "Digital:"
  - [ ] Physische Items: Unter "Versandartikel:"
  - [ ] Menge, Beschreibung, Preis sichtbar
- [ ] ✅ Versandkosten angezeigt (falls > 0)
- [ ] ✅ Gesamtpreis: `Total: XX.XX €`
- [ ] ✅ **Adressdaten komplett angezeigt:**
  ```
  Max Mustermann
  Musterstraße 123
  12345 Musterstadt
  Deutschland
  ```
- [ ] ✅ Buttons sichtbar:
  - [ ] "Mark as Shipped"
  - [ ] "Cancel Order"
  - [ ] "Back"

**Tatsächliches Ergebnis:**
```
[Beschreibe die Detailansicht]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Test 4: Als versendet markieren (KRITISCH!)

**Konto:** Admin-Konto (für Aktion) + User-Konto (für Notification)

### Teil A: Admin markiert als versendet

**Konto:** Admin-Konto

- [ ] 1. Shipping Management → Bestellung auswählen
- [ ] 2. "Mark as Shipped" klicken
- [ ] 3. **Bestätigung erscheint?**
  - [ ] ✅ Text: "Mark order [INV-XXX] as shipped?"
  - [ ] ✅ "Confirm" Button
  - [ ] ✅ "Cancel" Button
- [ ] 4. "Confirm" klicken

**Erwartetes Ergebnis:**
- [ ] ✅ Success-Nachricht: "Order [INV-XXX] marked as shipped"
- [ ] ✅ "Back to Menu" Button

**Tatsächliches Ergebnis:**
```
[Beschreibe was passiert ist]
```

### Teil B: User erhält Benachrichtigung

**Konto:** User-Konto (Telegram-Chat prüfen!)

- [ ] 5. **User-Chat prüfen:** Wurde Notification empfangen?

**Erwartetes Ergebnis:**
- [ ] ✅ User erhält Telegram-Nachricht:
  - [ ] Text enthält: "Your order [INV-XXX] has been shipped" (oder DE)
  - [ ] Keine Fehler

**Tatsächliches Ergebnis:**
```
[Wurde Notification empfangen? Ja/Nein]
[Text der Notification:]
```

### Teil C: Bestellung verschwindet aus Liste

**Konto:** Admin-Konto

- [ ] 6. Zurück zu "Shipping Management" navigieren
- [ ] 7. Liste neu laden

**Erwartetes Ergebnis:**
- [ ] ✅ Bestellung ist NICHT mehr in der Liste
- [ ] ✅ Falls es die letzte war: "No orders awaiting shipment"

**Tatsächliches Ergebnis:**
```
[Ist Bestellung weg? Ja/Nein]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Test 5: Navigation (Back-Buttons)

**Konto:** Admin-Konto

- [ ] 1. Admin Menu → Shipping Management (List)
- [ ] 2. Order Details öffnen
- [ ] 3. "Back" klicken → Sollte zu List zurückkehren
- [ ] 4. "Back to Menu" klicken → Sollte zu Admin Menu zurückkehren
- [ ] 5. Nochmal "Shipping Management" → "Order Details" → "Mark as Shipped" → "Cancel"
- [ ] 6. Sollte zu Details zurückkehren

**Erwartetes Ergebnis:**
- [ ] ✅ Alle Back-Buttons funktionieren
- [ ] ✅ Keine "stuck screens"
- [ ] ✅ Keine Duplikat-Messages

**Tatsächliches Ergebnis:**
```
[Beschreibe Navigation-Flow]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Test 6: Fehlerbehandlung - Nicht existierende Bestellung (NEU - Bug Fix!)

**Voraussetzung:** Eine Bestellung, die gerade als versendet markiert wurde

**Konto:** Admin-Konto

- [ ] 1. Shipping Management öffnen
- [ ] 2. Bestellung als "Shipped" markieren
- [ ] 3. **Browser/Telegram "Zurück" Button** drücken (zurück zu Details)
- [ ] 4. Versuche nochmal "Mark as Shipped" zu klicken

**Erwartetes Ergebnis (NACH Refactoring):**
- [ ] ✅ **Graceful Error-Message:** "Order not found" oder ähnlich
- [ ] ✅ "Back to Menu" Button funktioniert
- [ ] ✅ **KEIN CRASH!** (Vorher: NoResultFound Exception)

**Tatsächliches Ergebnis:**
```
[Was passiert? Fehlermeldung oder Crash?]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Test 7: Bestellung stornieren (Cancel Order)

**Voraussetzung:** Neue Bestellung erstellen (siehe Setup)

**Konto:** Admin-Konto

- [ ] 1. Shipping Management → Order Details
- [ ] 2. "Cancel Order" klicken
- [ ] 3. Wähle "Cancel without reason"
- [ ] 4. Bestätigen

**Erwartetes Ergebnis:**
- [ ] ✅ Success-Nachricht erscheint
- [ ] ✅ Bestellung verschwindet aus Shipping Management Liste
- [ ] ✅ User erhält Stornierungsbenachrichtigung (prüfe User-Chat!)
- [ ] ✅ Wallet-Guthaben wurde zurückerstattet (falls Wallet-Zahlung)

**Tatsächliches Ergebnis:**
```
[Beschreibe was passiert ist]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Test 8: Gemischte Bestellung (Digital + Physical)

**Voraussetzung:** Bestellung mit sowohl digitalen ALS AUCH physischen Items erstellen

**Setup:**
- [ ] User-Konto: 1x digitales Item + 1x physisches Item kaufen

**Konto:** Admin-Konto

- [ ] 1. Shipping Management → Order Details öffnen

**Erwartetes Ergebnis:**
- [ ] ✅ Zwei Sektionen sichtbar:
  - [ ] "Digital:" mit digitalen Items
  - [ ] "Versandartikel:" mit physischen Items
- [ ] ✅ Adresse wird angezeigt (wegen physical items)
- [ ] ✅ Beide Item-Typen korrekt gruppiert

**Tatsächliches Ergebnis:**
```
[Beschreibe Darstellung]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Test 9: Mehrere ausstehende Bestellungen

**Voraussetzung:** 3+ Bestellungen in PAID_AWAITING_SHIPMENT Status erstellen

**Konto:** Admin-Konto

- [ ] 1. Shipping Management öffnen
- [ ] 2. Alle Bestellungen durchgehen (Details öffnen)
- [ ] 3. Eine Bestellung als "Shipped" markieren
- [ ] 4. Zurück zur Liste

**Erwartetes Ergebnis:**
- [ ] ✅ Initial: Alle 3+ Bestellungen angezeigt
- [ ] ✅ Nach Markierung: Nur noch 2 Bestellungen in Liste
- [ ] ✅ Details-Navigation funktioniert für alle Bestellungen
- [ ] ✅ Keine Verwechslungen zwischen Bestellungen

**Tatsächliches Ergebnis:**
```
[Beschreibe Multi-Order Handling]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Test 10: Performance & Responsiveness

**Konto:** Admin-Konto

- [ ] 1. Shipping Management mit mehreren Bestellungen öffnen
- [ ] 2. Zwischen Bestellungen wechseln
- [ ] 3. Mehrere Aktionen schnell hintereinander ausführen

**Erwartetes Ergebnis:**
- [ ] ✅ Liste lädt schnell (< 2 Sekunden)
- [ ] ✅ Details laden schnell
- [ ] ✅ Keine verzögerten Updates
- [ ] ✅ Keine Doppel-Notifications

**Tatsächliches Ergebnis:**
```
[Beschreibe Performance]
```

**Status:** ✅ PASS / ❌ FAIL

---

## Zusammenfassung

### Test-Ergebnisse

| Test | Status | Notizen |
|------|--------|---------|
| Test 1: Empty State | ⬜ | |
| Test 2: Liste anzeigen | ⬜ | |
| Test 3: Details anzeigen | ⬜ | |
| Test 4: Als versendet markieren | ⬜ | **KRITISCH** |
| Test 5: Navigation | ⬜ | |
| Test 6: Fehlerbehandlung (Bug Fix) | ⬜ | **NEU** |
| Test 7: Bestellung stornieren | ⬜ | |
| Test 8: Gemischte Bestellung | ⬜ | |
| Test 9: Mehrere Bestellungen | ⬜ | |
| Test 10: Performance | ⬜ | |

### Gesamtergebnis

- **Alle Tests bestanden:** ✅ / ❌
- **Kritische Bugs gefunden:** [Liste hier]
- **Minor Issues gefunden:** [Liste hier]

### Empfehlung

- [ ] ✅ **SAFE TO MERGE** - Alle Tests bestanden
- [ ] ⚠️ **NEEDS FIXES** - Minor Issues, aber funktionsfähig
- [ ] ❌ **DO NOT MERGE** - Kritische Bugs gefunden

---

## Notizen & Beobachtungen

```
[Füge hier weitere Beobachtungen, Screenshots, oder Kommentare hinzu]
```

---

## Anhang: Test-Daten

### Verwendete Bestellungen

| Invoice | Items | Status | Markiert als |
|---------|-------|--------|--------------|
| INV-_____ | Physical | PAID_AWAITING_SHIPMENT | Shipped / Cancelled |
| INV-_____ | Mixed | PAID_AWAITING_SHIPMENT | - |
| INV-_____ | Physical | PAID_AWAITING_SHIPMENT | - |

---

**Test abgeschlossen am:** [Datum/Zeit]
**Tester-Signatur:** [Name]
