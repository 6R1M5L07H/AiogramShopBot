# TODO: Fix session_execute Mock Configuration in Unit Tests

**Priority:** HIGH
**Status:** Open
**Created:** 2025-11-21
**Affects:** Test Suite Reliability

## Problem Summary

Three unit tests fail consistently on `develop` branch due to incorrect mock configuration for the `session_execute()` wrapper function. The tests attempt to call `.scalar()` on a coroutine object instead of an awaited result.

## Failing Tests

1. `tests/cart/unit/test_cart_service_crud.py::TestAddToCart::test_add_to_cart_success_exact_quantity`
2. `tests/cart/unit/test_cart_service_crud.py::TestAddToCart::test_add_to_cart_stock_reduced`
3. `tests/cart/unit/test_cart_service_crud.py::TestGetCartSummaryData::test_get_cart_summary_with_items`

## Error Details

```
AttributeError: 'coroutine' object has no attribute 'scalar'
  File "repositories/price_tier.py", line 148, in get_by_subcategory
    item_result = await session_execute(item_stmt, session)
    item_id = item_result.scalar()
```

## Root Cause

The `session_execute()` wrapper in `db.py` is designed to support both:
- `AsyncSession` (returns awaited result)
- `Session` (returns synchronous result)

However, when tests mock the session as `AsyncMock`, the `session_execute()` function's `isinstance()` check treats it as `AsyncSession` and attempts to await `session.execute()`, which returns a coroutine instead of the expected `Result` object.

### Problematic Code Flow

```python
# db.py:100-106
async def session_execute(stmt, session: AsyncSession | Session) -> Result[Any] | CursorResult[Any]:
    if isinstance(session, AsyncSession):
        query_result = await session.execute(stmt)  # When session is AsyncMock, this is a coroutine
        return query_result
    else:
        query_result = session.execute(stmt)
        return query_result
```

When `session` is an `AsyncMock`:
- `isinstance(session, AsyncSession)` → `True` (incorrect)
- `await session.execute(stmt)` → Returns a coroutine (not a Result)
- Calling `.scalar()` on coroutine → `AttributeError`

## Impact

- **Test Coverage:** 3 critical cart service tests are failing
- **CI/CD:** Test suite shows failures on clean `develop` branch
- **Development:** Developers cannot rely on these tests for regression detection
- **Scope:** Affects all tests that use `CartService.add_to_cart()` and `CartService.get_cart_summary_data()`

## Solution Approaches

### Option 1: Patch session_execute in Tests (Quick Fix)

Patch `db.session_execute` to return a properly configured mock:

```python
# In test setup
mock_result = AsyncMock()
mock_result.scalar.return_value = 1  # or appropriate value
mock_result.all.return_value = []

with patch('db.session_execute', return_value=mock_result):
    # Test code
```

**Pros:**
- Quick fix
- Minimal code changes

**Cons:**
- Needs patching in every affected test
- Doesn't address fundamental mock configuration issue

### Option 2: Mock PriceTierRepository (Cleaner)

Instead of letting tests reach `session_execute()`, mock at the repository level:

```python
with patch('repositories.price_tier.PriceTierRepository.get_by_subcategory', return_value=[]):
    # Test code
```

**Pros:**
- Cleaner test isolation
- Avoids deep mocking of database layer
- Follows repository pattern correctly

**Cons:**
- Requires identifying all repository calls in test paths
- May need multiple patches per test

### Option 3: Use Real Session with In-Memory DB (Most Robust)

Convert affected tests to integration tests using SQLite in-memory:

```python
@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
```

**Pros:**
- Tests actual database behavior
- No mock configuration issues
- Catches real SQL errors

**Cons:**
- Slower test execution
- More setup code required
- Blurs line between unit and integration tests

## Recommended Approach

**Option 2** (Mock PriceTierRepository) is recommended:

1. It maintains unit test isolation
2. Respects the service/repository layer separation
3. Avoids brittle low-level mocking
4. Aligns with existing test patterns in the codebase

## Implementation Checklist

- [ ] Identify all repository calls in failing test paths:
  - `PriceTierRepository.get_by_subcategory()`
  - `ItemRepository.get_item_metadata()`
  - Other repository methods called during cart operations
- [ ] Add repository-level mocks to test setup
- [ ] Verify all 3 tests pass with new mocking approach
- [ ] Run full test suite to ensure no regressions
- [ ] Document mock patterns in test documentation
- [ ] Consider applying same pattern to other brittle tests

## Related Files

- `db.py:100-106` - `session_execute()` wrapper
- `repositories/price_tier.py:147-148` - Failing line
- `tests/cart/unit/test_cart_service_crud.py` - Affected tests
- `services/cart.py` - Calls PricingService which triggers the issue
- `services/pricing.py:55` - Calls PriceTierRepository.get_by_subcategory()

## Testing After Fix

```bash
# Run specific failing tests
pytest tests/cart/unit/test_cart_service_crud.py::TestAddToCart::test_add_to_cart_success_exact_quantity -v
pytest tests/cart/unit/test_cart_service_crud.py::TestAddToCart::test_add_to_cart_stock_reduced -v
pytest tests/cart/unit/test_cart_service_crud.py::TestGetCartSummaryData::test_get_cart_summary_with_items -v

# Run entire test suite
pytest tests/cart/unit/test_cart_service_crud.py -v

# Verify no regressions
pytest tests/ -v
```

## Notes

- This issue was discovered during security patch testing (2025-11-20_security_patches branch)
- The security patches (HTML escaping + Decimal refactoring) are NOT the cause of these failures
- Tests fail consistently on clean `develop` branch (commit 1e770bc)
- 14 other tests in the same file pass successfully
- Issue likely introduced during recent cart service refactoring (#58)
