# Shipping Tiers Configuration

## Overview

Shipping tiers define quantity-based shipping type selection for physical items. Unlike `price_tiers` (which are per-item), `shipping_tiers` are defined per **subcategory** in the database.

## How It Works

1. **Subcategory-Level**: All items in a subcategory share the same shipping tier logic
2. **Quantity-Based**: As cart quantity increases, shipping type automatically upgrades
3. **Reference-Based**: `shipping_type` references keys from `shipping_types/{country}.json`

## Database Schema

```sql
CREATE TABLE shipping_tiers (
    id INTEGER PRIMARY KEY,
    subcategory_id INTEGER NOT NULL,  -- Links to subcategory
    min_quantity INTEGER NOT NULL,     -- Minimum quantity for this tier
    max_quantity INTEGER NULL,         -- Maximum quantity (NULL = unlimited)
    shipping_type TEXT NOT NULL,       -- Key from shipping_types/{country}.json
    FOREIGN KEY (subcategory_id) REFERENCES subcategories(id)
);
```

## Example Configuration

For subcategory "USB Storage Devices":

```json
[
  {
    "subcategory_id": 3,
    "min_quantity": 1,
    "max_quantity": 5,
    "shipping_type": "maxibrief"
  },
  {
    "subcategory_id": 3,
    "min_quantity": 6,
    "max_quantity": 10,
    "shipping_type": "paeckchen"
  },
  {
    "subcategory_id": 3,
    "min_quantity": 11,
    "max_quantity": null,
    "shipping_type": "paket_2kg"
  }
]
```

**Result**:
- 1-5 USB sticks → Maxibrief (free)
- 6-10 USB sticks → Päckchen (free, Packstation OK)
- 11+ USB sticks → Paket 2kg (€1.50, insured + tracking)

## Adding Shipping Tiers

### Method 1: Direct Database Insert

```sql
-- For "USB Storage Devices" (subcategory_id = 3)
INSERT INTO shipping_tiers (subcategory_id, min_quantity, max_quantity, shipping_type)
VALUES
  (3, 1, 5, 'maxibrief'),
  (3, 6, 10, 'paeckchen'),
  (3, 11, NULL, 'paket_2kg');
```

### Method 2: Python Script (Recommended)

Create `docs/generate-items/import_shipping_tiers.py`:

```python
import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import text
from db import get_db_session, session_commit


async def import_shipping_tiers():
    """Import shipping tiers from configuration."""

    # Define your shipping tiers
    tiers_config = [
        {
            "subcategory_name": "USB Storage Devices",
            "tiers": [
                {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
                {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"},
                {"min_quantity": 11, "max_quantity": None, "shipping_type": "paket_2kg"}
            ]
        },
        {
            "subcategory_name": "Hardware Accessories",
            "tiers": [
                {"min_quantity": 1, "max_quantity": None, "shipping_type": "maxibrief"}
            ]
        }
    ]

    async with get_db_session() as session:
        for config in tiers_config:
            # Get subcategory ID
            result = await session.execute(text(
                "SELECT id FROM subcategories WHERE name = :name"
            ), {"name": config["subcategory_name"]})

            subcategory_id = result.scalar()
            if not subcategory_id:
                print(f"⚠️  Subcategory '{config['subcategory_name']}' not found, skipping")
                continue

            # Delete existing tiers
            await session.execute(text(
                "DELETE FROM shipping_tiers WHERE subcategory_id = :id"
            ), {"id": subcategory_id})

            # Insert new tiers
            for tier in config["tiers"]:
                await session.execute(text("""
                    INSERT INTO shipping_tiers (subcategory_id, min_quantity, max_quantity, shipping_type)
                    VALUES (:subcategory_id, :min_quantity, :max_quantity, :shipping_type)
                """), {
                    "subcategory_id": subcategory_id,
                    "min_quantity": tier["min_quantity"],
                    "max_quantity": tier["max_quantity"],
                    "shipping_type": tier["shipping_type"]
                })

            print(f"✅ Imported {len(config['tiers'])} shipping tiers for '{config['subcategory_name']}'")

        await session_commit(session)
        print("✅ All shipping tiers imported successfully")


if __name__ == "__main__":
    asyncio.run(import_shipping_tiers())
```

## Validation Rules

1. **Coverage**: Tiers must cover 1 to ∞ (no gaps)
2. **Start**: First tier must have `min_quantity = 1`
3. **End**: At least one tier must have `max_quantity = NULL` (unlimited)
4. **No Overlaps**: Ranges must be continuous (e.g., 1-5, 6-10, 11-∞)
5. **Valid References**: `shipping_type` must exist in `shipping_types/{country}.json`

## Digital Items

Digital items (`is_physical=False`) do NOT need shipping tiers. The cart logic automatically sets `shipping_cost = 0.0` for digital subcategories.

## Migration Default

The migration script (`migrations/add_shipping_tiers.py`) creates a default tier for all physical subcategories:

```json
{
  "min_quantity": 1,
  "max_quantity": null,
  "shipping_type": "maxibrief"
}
```

**⚠️ Manual adjustment recommended** for optimal shipping configuration based on item weight/size.

## Testing

```python
# Test shipping type selection
from utils.shipping_validation import get_shipping_type_for_quantity

tiers = [
    {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
    {"min_quantity": 6, "max_quantity": None, "shipping_type": "paeckchen"}
]

print(get_shipping_type_for_quantity(tiers, 3))   # → "maxibrief"
print(get_shipping_type_for_quantity(tiers, 10))  # → "paeckchen"
```

## Related Files

- `models/shipping_tier.py` - Database model
- `utils/shipping_validation.py` - Validation functions
- `utils/shipping_types_loader.py` - Loads shipping_types/{country}.json
- `migrations/add_shipping_tiers.py` - Database migration
- `shipping_types/{country}.json` - Shipping type definitions