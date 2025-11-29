# TODO: Item Unit Field Extension

**Created:** 2025-11-07
**Priority:** Medium
**Estimated Effort:** 2-3 hours

## Overview

Add a configurable unit field to items to support different measurement types beyond "Stk." (pieces). This allows proper display of items sold by weight (g, kg), volume (ml, l), or other units.

## Current Behavior

All items display quantity as "Stk." (pieces/items):
- "5 Stk. Grüner Tee" (makes sense)
- "500 Stk. Zucker" (should be "500 g")
- "1 Stk. Olivenöl" (should be "1 l")

## Proposed Solution

### 1. Database Changes

Add `unit` column to `items` table:

```sql
ALTER TABLE items ADD COLUMN unit VARCHAR(10) DEFAULT 'Stk.' NOT NULL;
```

Create migration: `migrations/add_item_unit_field.py`

### 2. Model Changes

**models/item.py:**
```python
class Item(Base):
    # ... existing fields ...
    unit = Column(String(10), nullable=False, default='Stk.')

class ItemDTO(BaseModel):
    # ... existing fields ...
    unit: str = 'Stk.'
```

### 3. Service Changes

**services/invoice_formatter.py:**
- Replace hardcoded `qty_unit = Localizator.get_text(entity, "quantity_unit_short")` with `item.unit`
- Update all quantity displays to use item-specific unit

**services/pricing.py:**
- Update `format_tier_breakdown()` to accept unit parameter
- Update `format_available_tiers()` to use item unit

### 4. Localization Impact

Current localization keys remain for default:
- `quantity_unit_short` = "Stk." (German) / "pcs." (English)

Item-specific units bypass localization (internationally recognized: g, kg, ml, l, etc.)

### 5. Item Generator Update

**docs/generate-items/generate_items.py:**

Add unit field to template:
```json
{
  "category_id": 1,
  "subcategory_id": 1,
  "private_data": "KEY-12345",
  "price": 10.00,
  "description": "Olivenöl Extra Vergine",
  "unit": "l",
  "is_physical": true,
  "shipping_cost": 5.00,
  "price_tiers": [...]
}
```

### 6. Common Units

Suggest these standard units:
- `Stk.` - Pieces/Items (default)
- `g` - Grams
- `kg` - Kilograms
- `ml` - Milliliters
- `l` - Liters
- `m` - Meters
- `m²` - Square meters
- `Paar` - Pairs (shoes, gloves)
- `Pack.` - Packages

## Implementation Steps

1. Create and run migration
2. Update Item model and DTO
3. Update ItemRepository.add_many() to handle unit field
4. Update all display locations:
   - InvoiceFormatter (all methods using qty_unit)
   - PricingService (tier breakdown, available tiers)
   - SubcategoryService (cart preview)
   - OrderService (order confirmations)
5. Update item generator documentation
6. Test with various units
7. Update CHANGELOG.md

## Testing Checklist

- [ ] Import items with different units (Stk., g, ml)
- [ ] Verify unit display in item detail view
- [ ] Verify unit display in cart
- [ ] Verify unit display in tier breakdown
- [ ] Verify unit display in order history
- [ ] Verify unit display in admin order view
- [ ] Test that existing items default to "Stk."

## Breaking Changes

None - default value ensures backward compatibility with existing items.

## Related Files

- `models/item.py`
- `repositories/item.py`
- `services/invoice_formatter.py`
- `services/pricing.py`
- `services/subcategory.py`
- `docs/generate-items/generate_items.py`
- `migrations/add_item_unit_field.py` (new)

## Notes

- Consider validation: max 10 characters, alphanumeric + special chars (., ², ³)
- Consider enum for common units vs free text field (free text = more flexible)
- UI impact: Admin item creation would need unit field (future admin panel)
