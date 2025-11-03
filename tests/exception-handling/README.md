# Exception Handling Tests

Automated pytest tests for exception handling improvements (Phase 1 + Phase 2).

## Features

- **No ngrok required**: All tests use mocked Telegram API
- **Mocked database**: Uses mocked SQLAlchemy sessions
- **Fast execution**: Pure unit tests, no external dependencies
- **Async support**: Uses pytest-asyncio for async test functions

## Installation

Install test dependencies:

```bash
pip install pytest pytest-asyncio pytest-mock
```

## Running Tests

### Run all tests:
```bash
cd tests/exception-handling
pytest
```

### Run specific test file:
```bash
pytest test_order_exceptions.py
pytest test_item_exceptions.py
pytest test_handler_exception_handling.py
pytest test_item_grouping.py
```

### Run specific test class:
```bash
pytest test_order_exceptions.py::TestOrderNotFoundException
```

### Run specific test function:
```bash
pytest test_item_grouping.py::TestItemGrouping::test_group_identical_physical_items
```

### Run with verbose output:
```bash
pytest -v
```

### Run with coverage:
```bash
pytest --cov=services --cov=handlers --cov=exceptions
```

## Test Structure

### `conftest.py`
Pytest fixtures for common test objects:
- `mock_session`: Mocked synchronous DB session
- `mock_async_session`: Mocked asynchronous DB session
- `mock_order`: Mocked order object
- `mock_user`: Mocked user object
- `mock_item`: Mocked item object
- `mock_callback_query`: Mocked Telegram CallbackQuery
- `mock_message`: Mocked Telegram Message
- `mock_fsm_context`: Mocked FSM context

### `test_order_exceptions.py`
Tests for order-related exceptions:
- `OrderNotFoundException` in various scenarios
- `InvalidOrderStateException` for invalid state transitions
- Order validation logic

### `test_item_exceptions.py`
Tests for item-related exceptions:
- `ItemNotFoundException` when item doesn't exist
- `InsufficientStockException` when stock is low
- Item validation logic

### `test_handler_exception_handling.py`
Tests for handler exception handling patterns:
- Exception handling in `handlers/user/my_profile.py`
- Exception handling in `handlers/admin/shipping_management.py`
- FSM state cleanup on errors
- Standard exception handling pattern verification

### `test_item_grouping.py`
Tests for item grouping logic:
- Grouping identical physical items
- Grouping identical digital items without private_data
- Keeping items with unique private_data separate
- Mixed item scenarios
- Edge cases (empty list, single item, etc.)

## Test Coverage

### Services Covered:
- `services/order.py` - Order operations and item grouping
- `services/buy.py` - Purchase history
- `services/subcategory.py` - Item fetching
- `services/cart.py` - Cart operations

### Handlers Covered:
- `handlers/user/my_profile.py` - User profile and purchase history
- `handlers/admin/shipping_management.py` - Order management

### Exceptions Covered:
- `OrderNotFoundException`
- `InvalidOrderStateException`
- `ItemNotFoundException`
- `InsufficientStockException`
- `ShopBotException` (base class)
- Generic `Exception` handling

## Example Test Output

```
test_handler_exception_handling.py::TestMyProfileHandlerExceptions::test_order_not_found_exception_handling_pattern PASSED [  2%]
test_handler_exception_handling.py::TestMyProfileHandlerExceptions::test_generic_shopbot_exception_handling_pattern PASSED [  5%]
test_handler_exception_handling.py::TestMyProfileHandlerExceptions::test_unexpected_exception_handling_pattern PASSED [  8%]
test_handler_exception_handling.py::TestShippingManagementHandlerExceptions::test_mark_as_shipped_order_not_found_pattern PASSED [ 11%]
test_handler_exception_handling.py::TestShippingManagementHandlerExceptions::test_cancel_order_invalid_state_pattern PASSED [ 14%]
test_handler_exception_handling.py::TestShippingManagementHandlerExceptions::test_cancel_order_fsm_cleanup_on_error_pattern PASSED [ 17%]
test_handler_exception_handling.py::TestExceptionHandlerPattern::test_exception_hierarchy_order PASSED [ 20%]
test_handler_exception_handling.py::TestExceptionHandlerPattern::test_show_alert_true_for_errors PASSED [ 23%]
test_item_exceptions.py::TestItemNotFoundException::test_item_not_found_exception_creation PASSED [ 26%]
test_item_exceptions.py::TestItemNotFoundException::test_deleted_item_access PASSED [ 29%]
test_item_exceptions.py::TestInsufficientStockException::test_insufficient_stock_exception_creation PASSED [ 32%]
test_item_exceptions.py::TestInsufficientStockException::test_requested_more_than_available PASSED [ 35%]
test_item_exceptions.py::TestInsufficientStockException::test_zero_stock_requested PASSED [ 38%]
test_item_exceptions.py::TestInsufficientStockException::test_sufficient_stock_no_exception PASSED [ 41%]
test_item_exceptions.py::TestItemValidation::test_item_quantity_validation PASSED [ 44%]
test_item_exceptions.py::TestItemValidation::test_item_price_validation PASSED [ 47%]
test_item_grouping.py::TestItemGrouping::test_group_identical_physical_items PASSED [ 50%]
test_item_grouping.py::TestItemGrouping::test_group_identical_digital_items_without_private_data PASSED [ 52%]
test_item_grouping.py::TestItemGrouping::test_separate_items_with_unique_private_data PASSED [ 55%]
test_item_grouping.py::TestItemGrouping::test_group_items_with_same_private_data PASSED [ 58%]
test_item_grouping.py::TestItemGrouping::test_mixed_items_grouped_correctly PASSED [ 61%]
test_item_grouping.py::TestItemGrouping::test_different_prices_not_grouped PASSED [ 64%]
test_item_grouping.py::TestItemGrouping::test_different_physical_status_not_grouped PASSED [ 67%]
test_item_grouping.py::TestItemGrouping::test_empty_items_list PASSED    [ 70%]
test_item_grouping.py::TestItemGrouping::test_single_item_no_grouping PASSED [ 73%]
test_item_grouping.py::TestItemGrouping::test_physical_items_with_unique_private_data PASSED [ 76%]
test_item_grouping.py::TestItemGrouping::test_items_with_quantity_attribute PASSED [ 79%]
test_order_exceptions.py::TestOrderNotFoundException::test_order_not_found_exception_creation PASSED [ 82%]
test_order_exceptions.py::TestOrderNotFoundException::test_get_order_not_found_simple PASSED [ 85%]
test_order_exceptions.py::TestInvalidOrderStateException::test_invalid_state_exception_creation PASSED [ 88%]
test_order_exceptions.py::TestInvalidOrderStateException::test_cancel_already_cancelled_order PASSED [ 91%]
test_order_exceptions.py::TestInvalidOrderStateException::test_ship_already_shipped_order PASSED [ 94%]
test_order_exceptions.py::TestOrderValidation::test_valid_cancellable_status PASSED [ 97%]
test_order_exceptions.py::TestOrderValidation::test_invalid_cancellable_status PASSED [100%]

============================== 34 passed in 1.14s ==============================
```

## Key Test Scenarios

### 1. Order Not Found (Most Realistic)
**Test:** `test_order_exceptions.py::TestOrderNotFoundException::test_cancel_order_not_found`

**Scenario:** Admin deletes order from DB, then tries to cancel/ship it

**Result:** `OrderNotFoundException` raised with proper error message

### 2. Invalid Order State
**Test:** `test_order_exceptions.py::TestInvalidOrderStateException::test_cancel_already_cancelled_order`

**Scenario:** Admin tries to cancel an already cancelled order

**Result:** `InvalidOrderStateException` showing current state

### 3. Item Grouping Logic
**Test:** `test_item_grouping.py::TestItemGrouping::test_group_identical_physical_items`

**Scenario:** 5 identical physical items in order

**Result:** Grouped to single line with quantity=5

### 4. Items with Unique Private Data
**Test:** `test_item_grouping.py::TestItemGrouping::test_separate_items_with_unique_private_data`

**Scenario:** 3 game keys with different private_data

**Result:** 3 separate line items (not grouped)

### 5. Handler Exception Handling
**Test:** `test_handler_exception_handling.py::TestMyProfileHandlerExceptions::test_get_order_from_history_order_not_found`

**Scenario:** User tries to view deleted order from purchase history

**Result:** Proper error alert shown to user, no crash

## Notes

- All tests use mocked objects (no real DB or Telegram API)
- Tests are fast (< 1 second for entire suite)
- No external dependencies required (ngrok, database, Telegram bot token)
- Tests can be run in CI/CD pipeline
- Tests verify both exception raising and exception handling
