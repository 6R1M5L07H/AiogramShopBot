# Quick Start - Exception Handling Tests

## Installation (einmalig)

```bash
cd tests/exception-handling
pip install -r requirements.txt
```

## Tests ausführen

### Alle Tests:
```bash
cd tests/exception-handling
python -m pytest -v
```

### Nur Item Grouping Tests (11 funktionierende Tests):
```bash
python -m pytest test_item_grouping.py -v
```

## Beispiel-Output (Alle Tests)

```
============================== 34 passed in 1.14s ==============================
```

**Test Coverage:**
-   11 Item Grouping Tests
-   7 Order Exception Tests
-   8 Item Exception Tests
-   8 Handler Exception Pattern Tests

## Was wird getestet?

### Item Grouping Tests (test_item_grouping.py)
Validieren die `OrderService._group_items_for_display()` Funktion:
-   Identische Physical Items werden gruppiert (5x Tea Plant → "5 Stk.")
-   Items mit unique private_data bleiben separat (Game Keys)
-   Items mit identical private_data werden gruppiert
-   Mixed scenarios (physical + digital + unique data)
-   Edge cases (empty list, single item, etc.)

### Order Exception Tests (test_order_exceptions.py)
Validieren Order-bezogene Exceptions:
-   OrderNotFoundException mit korrekten Attributen
-   InvalidOrderStateException für ungültige Status-Übergänge
-   Order Status Validierung (cancellable vs. non-cancellable)

### Item Exception Tests (test_item_exceptions.py)
Validieren Item-bezogene Exceptions:
-   ItemNotFoundException für nicht-existierende Items
-   InsufficientStockException bei zu wenig Lagerbestand
-   Item Validierungslogik (Menge, Preis)

### Handler Exception Tests (test_handler_exception_handling.py)
Validieren Exception Handling Patterns in Handlers:
-   OrderNotFoundException wird korrekt behandelt
-   InvalidOrderStateException mit FSM State Cleanup
-   Generic ShopBotException Handling
-   Unexpected Exception Handling
-   Exception Hierarchy (specific → broad → generic)

## Vorteile

- **Keine DB erforderlich**: Alles gemockt
- **Kein ngrok**: Telegram API gemockt
- **Schnell**: < 2 Sekunden für 11 Tests
- **Kein Bot-Token**: Läuft komplett offline
- **CI/CD ready**: Kann in GitHub Actions laufen

## Hinweise

- Alle 34 Tests sind vollständig funktionsfähig
- Tests verwenden Pattern-Testing statt vollständiger Integration-Tests (schneller und stabiler)
- Für manuelle Tests siehe MANUAL_TEST_SCENARIOS.md
- Tests können in CI/CD pipelines integriert werden
