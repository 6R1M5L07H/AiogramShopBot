# How to Add New Measurement Units

This guide explains how to extend the item unit system with new measurement units.

## Overview

The system uses a strict enum-based approach for measurement units:
- **EN-based** values are stored in the database (e.g., `"pcs."`, `"g"`, `"ml"`)
- **Localized** for display in user's language (e.g., `"pcs."` → `"Stk."` in German)
- **Type-safe** through Python enums with validation

## Current Supported Units

### Text-based Units (Localized)
- `pcs.` (Pieces) → `"Stk."` in German
- `pairs` → `"Paar"` in German
- `pkg.` (Packages) → `"Pack."` in German

### Metric Units (International, Not Localized)
- `g` (Grams)
- `kg` (Kilograms)
- `ml` (Milliliters)
- `l` (Liters)
- `m` (Meters)
- `m2` (Square Meters - note: `m2` not `m²` for security/ASCII-only)

## Understanding the Two-Step Process

**Important:** EVERY unit must be added to the `ItemUnit` enum. The distinction between "localized" and "international" units only affects whether you need to add a translation mapping.

### Why must international units be added to the enum?

**Reason:** We use a **strict enum** validation system. Only predefined units are accepted. Even though "g" and "kg" are universally recognized, they must still be explicitly added to the enum for validation and type safety.

### What does "international" mean then?

**"International" = No translation needed**

- The unit is written the same way in all languages (e.g., "g", "kg", "oz", "lb")
- You skip the localization mapping step
- The `Localizator.localize_unit()` method will pass them through unchanged

### The Two Steps Explained

#### For International Units (g, kg, oz, lb, ml, l)

**Step 1:** Add to `ItemUnit` enum ✅ **REQUIRED**
```python
# enums/item_unit.py
class ItemUnit(str, Enum):
    OUNCES = "oz"  # Must be added!
```

**Step 2:** Add to localization map ❌ **SKIP THIS**
```python
# utils/localizator.py
# NO ENTRY NEEDED - "oz" stays "oz" in all languages
```

**Why:** Internationally recognized units are pass-through. The localization service returns them unchanged.

#### For Text-based Units (pcs., pairs, boxes)

**Step 1:** Add to `ItemUnit` enum ✅ **REQUIRED**
```python
# enums/item_unit.py
class ItemUnit(str, Enum):
    BOXES = "boxes"  # Must be added!
```

**Step 2:** Add to localization map ✅ **REQUIRED**
```python
# utils/localizator.py
UNIT_I18N_MAP = {
    "boxes": {"de": "Kartons", "en": "boxes"}  # Translation needed!
}
```

**Why:** These units vary by language and need explicit translations.

## Adding a New Unit (Step-by-Step)

### Step 1: Add to ItemUnit Enum (ALWAYS REQUIRED)

**File:** `enums/item_unit.py`

```python
class ItemUnit(str, Enum):
    # Existing units...

    # Add your new unit here (ALWAYS, regardless of localization)
    OUNCES = "oz"  # Example: adding ounces (international)
    BOXES = "boxes"  # Example: adding boxes (needs translation)
```

**Naming Convention:**
- Enum name: `UPPERCASE_SNAKE_CASE` (e.g., `SQUARE_METERS`)
- Enum value: EN-based abbreviation (e.g., `"oz"`, `"lb"`, `"boxes"`)
- Keep values short (max 10 characters)
- Use lowercase for metric units (`"g"`, `"ml"`)
- Use periods for abbreviated text units (`"pcs."`, `"pkg."`)

### Step 2: Add Localization Mapping (ONLY for text-based units)

**File:** `utils/localizator.py`

**Decision matrix:**
- ❓ Is the unit written the same in all languages? (e.g., "g", "kg", "oz")
  - ✅ YES → **Skip this step** (pass-through)
  - ❌ NO → **Add translation below**

```python
UNIT_I18N_MAP = {
    "pcs.": {"de": "Stk.", "en": "pcs."},
    "pairs": {"de": "Paar", "en": "pairs"},
    "pkg.": {"de": "Pack.", "en": "pkg."},

    # Add translation ONLY if unit varies by language
    "boxes": {"de": "Kartons", "en": "boxes"}  # Needs translation

    # NO ENTRY for international units:
    # "oz", "lb", "g", "kg" → automatically pass-through
}
```

**When to add localization:**
- ✅ Text-based units that vary by language (`"pcs."` → `"Stk."`)
- ❌ Metric units (internationally recognized: `"g"`, `"kg"`, `"ml"`, `"l"`)
- ❌ Imperial units (internationally recognized: `"oz"`, `"lb"`, `"ft"`)

### Step 3: Update Documentation

**File:** `docs/generate-items/generate_items.py` (docstring)

Add your new unit to the examples:

```python
"""
## Supported Units (EN-based)

### Localized (text-based):
- `pcs.` (pieces) → "Stk." (DE)
- `pairs` → "Paar" (DE)
- `pkg.` (packages) → "Pack." (DE)
- `boxes` → "Kartons" (DE)  # NEW

### International (metric - no localization):
- `g` (grams)
- `kg` (kilograms)
- `ml` (milliliters)
- `l` (liters)
- `m` (meters)
- `m2` (square meters)
- `oz` (ounces)  # NEW
"""
```

### Step 4: Write Tests

**File:** `tests/enums/unit/test_item_unit.py` (create if doesn't exist)

```python
def test_new_unit_validation():
    """Test that new unit is recognized and validated."""
    # Test enum value
    assert ItemUnit.OUNCES.value == "oz"

    # Test from_string conversion
    unit = ItemUnit.from_string("oz")
    assert unit == ItemUnit.OUNCES

    # Test case insensitivity
    unit = ItemUnit.from_string(" OZ ")
    assert unit == ItemUnit.OUNCES


def test_new_unit_localization():
    """Test localization of new unit (if applicable)."""
    from utils.localizator import Localizator

    # If unit has translation (text-based)
    localized = Localizator.localize_unit("boxes")
    assert localized == "Kartons"  # When LANGUAGE=de

    # If unit is international (no translation)
    localized = Localizator.localize_unit("oz")
    assert localized == "oz"  # Pass-through (unchanged)
```

### Step 5: Migration (Optional)

If you need to update existing items to use the new unit:

**File:** `migrations/update_items_to_new_unit.py`

```python
#!/usr/bin/env python3
"""
Migration: Update specific items to new unit
"""
import asyncio
from sqlalchemy import text
from db import get_db_session, session_commit, session_execute

async def run_migration():
    async with get_db_session() as session:
        # Example: Update all items in subcategory #5 to use "oz"
        await session_execute(
            text("""
                UPDATE items
                SET unit = 'oz'
                WHERE subcategory_id = 5
                  AND unit = 'pcs.'
            """),
            session
        )
        await session_commit(session)

if __name__ == "__main__":
    asyncio.run(run_migration())
```

## Example: Adding "Pounds" Unit (International)

### 1. Add enum value ✅ REQUIRED

```python
# enums/item_unit.py
class ItemUnit(str, Enum):
    # ...
    POUNDS = "lb"
```

### 2. Skip localization ❌ NOT NEEDED

```python
# utils/localizator.py - NO CHANGES needed
# "lb" is internationally recognized (pass-through)
```

**Why skip?** "lb" is written the same way worldwide. No translation exists.

### 3. Update docs

```python
# docs/generate-items/generate_items.py
"""
- `lb` (pounds)  # Added to International section
"""
```

### 4. Use in item import

```json
{
  "category": "Food",
  "subcategory": "Meat",
  "private_data": "BEEF-001",
  "price": 15.00,
  "description": "Premium Beef",
  "unit": "lb",
  "is_physical": true,
  "shipping_cost": 5.00
}
```

### 5. Verify

```bash
# Run unit tests
python -m pytest tests/enums/unit/test_item_unit.py -v

# Import items with new unit
python repositories/item_parser.py import_items.json
```

## Example: Adding "Boxes" Unit (Text-based)

### 1. Add enum value ✅ REQUIRED

```python
# enums/item_unit.py
class ItemUnit(str, Enum):
    # ...
    BOXES = "boxes"
```

### 2. Add localization ✅ REQUIRED

```python
# utils/localizator.py
UNIT_I18N_MAP = {
    # ...
    "boxes": {"de": "Kartons", "en": "boxes"}
}
```

**Why add?** "Boxes" is translated differently in German (Kartons). Needs mapping.

### 3. Update docs, test, use (same as pounds example)

## Common Pitfalls

### ❌ Forgetting to add international unit to enum
```python
# DON'T: Assume "g" works without enum entry
# It WILL fail validation!

# DO: Always add to enum first
class ItemUnit(str, Enum):
    GRAMS = "g"  # Required even though international
```

### ❌ Adding international unit to localization map
```python
# DON'T: Add unnecessary translation
UNIT_I18N_MAP = {
    "g": {"de": "g", "en": "g"}  # Redundant!
}

# DO: Skip it - pass-through is automatic
# (no entry needed)
```

### ❌ Using Unicode characters
```python
# DON'T: Security risk, escaping issues
SQUARE_METERS = "m²"

# DO: ASCII-safe alternative
SQUARE_METERS = "m2"
```

### ❌ Too long unit values
```python
# DON'T: Exceeds 10 char limit
TABLESPOONS = "tablespoons"

# DO: Use abbreviation
TABLESPOONS = "tbsp"
```

### ❌ Inconsistent casing
```python
# DON'T: Mixed case for metric units
GRAMS = "G"
MILLILITERS = "ML"

# DO: Lowercase for metric units
GRAMS = "g"
MILLILITERS = "ml"
```

### ❌ Forgetting validation tests
```python
# DON'T: Add unit without tests

# DO: Always write validation tests
def test_new_unit():
    assert ItemUnit.from_string("lb") == ItemUnit.POUNDS
```

## Validation Rules

The system enforces these rules automatically:
- ✅ Max 10 characters
- ✅ Alphanumeric + period only (`[a-zA-Z0-9.]+`)
- ✅ Case-insensitive matching (`"G"` → `"g"`)
- ✅ Whitespace trimming (`" ml "` → `"ml"`)
- ❌ Special characters rejected (`"m²"`, `"m³"`)
- ❌ Empty strings rejected
- ❌ Unknown units rejected with helpful error

## Decision Flowchart

```
Need to add a new unit?
    ↓
Step 1: Add to ItemUnit enum
    ↓ (ALWAYS)
    ↓
Step 2: Does the unit vary by language?
    ↓
    ├─ YES (e.g., "pcs." vs "Stk.") → Add to UNIT_I18N_MAP
    │                                  ↓
    │                                  Done
    │
    └─ NO (e.g., "g", "kg", "oz") → Skip localization
                                     ↓ (Pass-through)
                                     Done
```

## Need Help?

If you're unsure whether your unit needs localization:

1. Check existing similar units in `enums/item_unit.py`
2. Review test cases in `tests/enums/unit/test_item_unit.py`
3. Consult the localization map in `utils/localizator.py`
4. Ask: "Is this unit written identically worldwide?"
   - YES → No localization (e.g., "g", "oz")
   - NO → Add localization (e.g., "pcs.", "pairs")

## Checklist

Before deploying a new unit, verify:

- [ ] Added to `ItemUnit` enum with correct naming convention
- [ ] Added to localization map (ONLY if text-based unit)
- [ ] Updated documentation in item generator
- [ ] Written unit tests for validation
- [ ] Written unit tests for localization (if applicable)
- [ ] Tested import with sample items
- [ ] Verified display in all views (cart, checkout, orders)
- [ ] No Unicode characters used
- [ ] Value length ≤ 10 characters
- [ ] Follows casing convention (lowercase for metric, periods for abbreviated text)
