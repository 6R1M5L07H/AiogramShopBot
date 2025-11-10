# TODO: Data Cleanup - Orphaned Items Management

**Created:** 2025-11-09
**Status:** Discussion Phase
**Priority:** Medium
**Related:** Data Retention, Category Management

---

## Problem Statement

### Current Behavior (Bugs)

**Bug #1: Incomplete Category Deletion**
When an admin deletes a category via Admin Menu → Inventory Management:
- ✅ Unsold items in that category are deleted
- ❌ Subcategories remain in database (orphaned)
- ❌ Sold items remain in database forever (even after orders are cleaned up)

**Bug #2: Incomplete Subcategory Deletion**
When an admin deletes a subcategory:
- ✅ Unsold items in that subcategory are deleted
- ❌ Subcategory record remains in database
- ❌ Sold items remain in database forever

**Current Code Location:**
`services/admin.py:160-179` - `AdminService.delete_entity()`

### Root Cause

**Database Schema Constraints:**
```python
# models/item.py
category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
subcategory_id = Column(Integer, ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=False)
```

**Problem:**
- Items with `nullable=False` foreign keys cannot exist without category/subcategory
- Sold items are referenced by `BuyItem` table → cannot be deleted immediately
- Foreign key `ondelete="CASCADE"` prevents category deletion if sold items exist

**Database Relationships:**
```
Category
  └─ Subcategory
       └─ Item
            └─ BuyItem (links Buy ← Item)
                 └─ Buy (purchase record, retained for 30 days)
```

### Impact

**Database Pollution:**
- Test instance has 1595+ duplicate items from repeated imports
- Orphaned categories/subcategories accumulate
- Sold items from deleted categories remain forever

**User Experience:**
- Admin thinks category is deleted, but data remains
- Statistics still work (they aggregate via `Buy` table, not `Item`)

---

## Proposed Solution: Orphaned Items Cleanup

### Option 2 (Recommended)

**Approach:** Allow items to become orphaned, then cleanup after retention period

**Implementation Steps:**

#### 1. Schema Changes (Migration Required)
```python
# models/item.py
category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
subcategory_id = Column(Integer, ForeignKey("subcategories.id", ondelete="SET NULL"), nullable=True)
```

**Migration File:** `migrations/YYYY-MM-DD_allow_orphaned_items.sql`
```sql
-- Allow NULL values
ALTER TABLE items ALTER COLUMN category_id DROP NOT NULL;
ALTER TABLE items ALTER COLUMN subcategory_id DROP NOT NULL;

-- Change foreign key behavior
ALTER TABLE items DROP CONSTRAINT items_category_id_fkey;
ALTER TABLE items ADD CONSTRAINT items_category_id_fkey
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL;

ALTER TABLE items DROP CONSTRAINT items_subcategory_id_fkey;
ALTER TABLE items ADD CONSTRAINT items_subcategory_id_fkey
  FOREIGN KEY (subcategory_id) REFERENCES subcategories(id) ON DELETE SET NULL;
```

#### 2. Update Category Deletion Logic
```python
# services/admin.py - delete_entity()
case EntityType.CATEGORY:
    category = await CategoryRepository.get_by_id(unpacked_cb.entity_id, session)

    # Delete unsold items immediately
    await ItemRepository.delete_unsold_by_category_id(unpacked_cb.entity_id, session)

    # Delete all subcategories (will set subcategory_id=NULL on sold items via CASCADE)
    await SubcategoryRepository.delete_by_category_id(unpacked_cb.entity_id, session)

    # Delete category (will set category_id=NULL on sold items via CASCADE)
    await CategoryRepository.delete_by_id(unpacked_cb.entity_id, session)

    await session_commit(session)
```

#### 3. Update Subcategory Deletion Logic
```python
case EntityType.SUBCATEGORY:
    subcategory = await SubcategoryRepository.get_by_id(unpacked_cb.entity_id, session)

    # Delete unsold items immediately
    await ItemRepository.delete_unsold_by_subcategory_id(unpacked_cb.entity_id, session)

    # Delete subcategory (will set subcategory_id=NULL on sold items via CASCADE)
    await SubcategoryRepository.delete_by_id(unpacked_cb.entity_id, session)

    await session_commit(session)
```

#### 4. Data Retention Cleanup Job Extension
Add new function to `jobs/data_retention_cleanup_job.py`:

```python
async def cleanup_orphaned_items():
    """
    Deletes items with NULL category_id (orphaned items) after retention period.

    Logic:
    - Find items where category_id IS NULL
    - Check if item has associated Buys
    - If last Buy is older than DATA_RETENTION_DAYS, delete item
    - If no Buys exist, delete immediately (shouldn't happen, but safety check)
    """
    async with get_db_session() as session:
        cutoff_date = datetime.now() - timedelta(days=config.DATA_RETENTION_DAYS)

        # Find orphaned items
        orphaned_stmt = select(Item).where(Item.category_id.is_(None))
        result = await session_execute(orphaned_stmt, session)
        orphaned_items = result.scalars().all()

        if len(orphaned_items) == 0:
            logging.info("[Data Retention] No orphaned items found")
            return

        deleted_count = 0
        for item in orphaned_items:
            # Find most recent Buy for this item
            buy_stmt = (
                select(Buy)
                .join(BuyItem, BuyItem.buy_id == Buy.id)
                .where(BuyItem.item_id == item.id)
                .order_by(Buy.buy_datetime.desc())
                .limit(1)
            )
            buy_result = await session_execute(buy_stmt, session)
            last_buy = buy_result.scalar_one_or_none()

            # Delete if no buy or buy older than retention period
            if last_buy is None or last_buy.buy_datetime < cutoff_date:
                await session.delete(item)
                deleted_count += 1

        await session_commit(session)
        logging.info(f"[Data Retention] ✅ Deleted {deleted_count} orphaned items")
```

Add to main cleanup routine:
```python
async def run_data_retention_cleanup():
    # ...existing cleanup tasks...
    await cleanup_orphaned_items()  # ADD THIS
```

---

## Alternative Solutions (Not Recommended)

### Option 1: Soft Delete
- Add `deleted_at` timestamp to categories/subcategories
- Keep all relationships intact
- Hide deleted entities from UI
- **Downside:** Schema pollution, complex queries

### Option 3: Deferred Cascade Delete
- Add `pending_deletion` flag to items
- Mark items when category deleted
- Cleanup job deletes flagged items after 30 days
- **Downside:** Extra column, more complex state management

---

## Open Questions for Discussion

1. **Migration Strategy:**
   - How to handle existing data with non-null constraints?
   - Run migration on production safely?

2. **Admin UI Feedback:**
   - Should we show warning "X sold items will be orphaned and deleted after 30 days"?
   - Add confirmation step?

3. **Statistics Impact:**
   - Verify statistics don't break with NULL category_id (currently safe, uses Buy table)
   - Test refund flow with orphaned items

4. **Edge Cases:**
   - What if admin re-creates category with same name after deletion?
   - Should orphaned items be hidden from admin views immediately?

5. **Performance:**
   - Cleanup job iterates all orphaned items → optimize with bulk query?
   - Index on `category_id IS NULL` for fast lookups?

---

## Testing Checklist

- [ ] Create category → add items → delete category → verify subcategory deleted
- [ ] Buy item → delete category → verify item orphaned (category_id=NULL)
- [ ] Wait 30+ days (simulate) → run cleanup job → verify orphaned item deleted
- [ ] Check statistics still work with orphaned items
- [ ] Test refund with orphaned item
- [ ] Verify BuyItem cascade deletes when item deleted

---

## Related Files

- `models/item.py` - Item model with foreign keys
- `services/admin.py:160-179` - Category/subcategory deletion
- `jobs/data_retention_cleanup_job.py` - Daily cleanup job
- `repositories/category.py` - Category repository
- `repositories/subcategory.py` - Subcategory repository
- `repositories/item.py` - Item repository
