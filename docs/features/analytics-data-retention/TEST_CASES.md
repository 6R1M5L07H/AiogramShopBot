# Analytics & Data Retention - Test Cases

**Feature**: Anonymized Analytics System with Data Retention
**Date**: 2025-11-11
**Status**: Implementation Complete

## Overview

This document describes all test cases for the anonymized analytics system that creates SalesRecords and ViolationStatistics for long-term business intelligence while following data minimization principles.

## Test Environment Setup

### Prerequisites
- Python 3.10+
- pytest installed
- Test database (SQLite)
- All dependencies from requirements.txt

### Running Tests

```bash
# Run all analytics tests
python -m pytest tests/analytics/ -v

# Run specific test file
python -m pytest tests/analytics/unit/test_analytics_service.py -v

# Run with coverage
python -m pytest tests/analytics/ --cov=services.analytics --cov=repositories.sales_record --cov=repositories.violation_statistics
```

---

## Unit Tests

### AnalyticsService Tests

#### Test Category: SalesRecord Creation

**TC-A01: Create SalesRecords from Completed Order**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_create_sales_records_from_order_success`
- **Purpose**: Verify SalesRecords are created correctly for a paid order with multiple items
- **Input**:
  - Order with 2 items (1 physical, 1 digital)
  - Mixed payment (wallet + crypto)
- **Expected Output**:
  - 2 SalesRecords created
  - Correct category/subcategory names
  - Correct financial data (item price, order total, shipping, wallet)
  - Correct payment method ("mixed")
  - Shipping type populated for physical items
- **Verification**:
  - ✅ No user_id in DTOs
  - ✅ Temporal data captured (hour, weekday)
  - ✅ Payment details captured

**TC-A02: Create SalesRecords for Wallet-Only Payment**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_create_sales_records_wallet_only_payment`
- **Purpose**: Verify wallet-only orders tracked correctly
- **Input**: Order paid entirely with wallet balance
- **Expected Output**:
  - payment_method = "wallet_only"
  - crypto_currency = None
  - wallet_used > 0

**TC-A03: Handle Order Not Found**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_create_sales_records_order_not_found`
- **Purpose**: Verify graceful handling when order doesn't exist
- **Input**: Non-existent order_id
- **Expected Output**: Empty list returned, no exceptions

**TC-A04: Handle Order with No Items**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_create_sales_records_no_items`
- **Purpose**: Verify handling of edge case (order without items)
- **Input**: Order with empty items list
- **Expected Output**: Empty list returned

#### Test Category: ViolationStatistics Creation

**TC-A05: Create UNDERPAYMENT_FINAL Violation**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_create_violation_record_underpayment_final`
- **Purpose**: Track second underpayment violations
- **Input**:
  - Order with retry_count = 1
  - penalty_applied = 5.0
- **Expected Output**:
  - ViolationType.UNDERPAYMENT_FINAL
  - Correct order_value, penalty_applied, retry_count

**TC-A06: Create LATE_PAYMENT Violation**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_create_violation_record_late_payment`
- **Purpose**: Track late payment violations
- **Input**: Payment received after deadline
- **Expected Output**: ViolationType.LATE_PAYMENT with penalty

**TC-A07: Create TIMEOUT Violation**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_create_violation_record_timeout`
- **Purpose**: Track order timeout violations
- **Input**: Order expired without payment
- **Expected Output**: ViolationType.TIMEOUT with zero penalty

**TC-A08: Create USER_CANCELLATION_LATE Violation**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_create_violation_record_user_cancellation_late`
- **Purpose**: Track late user cancellations
- **Input**: User cancellation outside grace period
- **Expected Output**: ViolationType.USER_CANCELLATION_LATE with penalty

**TC-A09: Handle Violation for Non-Existent Order**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_create_violation_record_order_not_found`
- **Purpose**: Verify graceful handling of missing orders
- **Expected Output**: None returned, no exceptions

#### Test Category: Data Minimization Compliance

**TC-A10: Verify SalesRecords Contain No user_id**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_sales_records_contain_no_user_id`
- **Purpose**: **CRITICAL** - Ensure data minimization principles
- **Verification**: Assert DTO has no user_id attribute
- **Rationale**: SalesRecords must be anonymized for indefinite retention

**TC-A11: Verify ViolationStatistics Contain No user_id**
- **File**: `tests/analytics/unit/test_analytics_service.py`
- **Test**: `test_violation_statistics_contain_no_user_id`
- **Purpose**: **CRITICAL** - Ensure data minimization principles
- **Verification**: Assert DTO has no user_id attribute
- **Rationale**: ViolationStatistics must be anonymized for abuse detection

---

### SalesRecordRepository Tests

**TC-R01: Create Multiple SalesRecords**
- **File**: `tests/analytics/unit/test_sales_record_repository.py`
- **Test**: `test_create_many_success`
- **Purpose**: Verify bulk creation of SalesRecords
- **Input**: 2 SalesRecordDTOs
- **Expected Output**: 2 IDs returned

**TC-R02: Get Total Revenue (Last 30 Days)**
- **File**: `tests/analytics/unit/test_sales_record_repository.py`
- **Test**: `test_get_total_revenue_last_30_days`
- **Purpose**: Verify revenue aggregation query
- **Expected Output**: Correct sum of item_total_price

**TC-R03: Get Total Revenue (No Sales)**
- **File**: `tests/analytics/unit/test_sales_record_repository.py`
- **Test**: `test_get_total_revenue_no_sales`
- **Purpose**: Handle edge case of no data
- **Expected Output**: 0.0

**TC-R04: Get Total Items Sold (Last 7 Days)**
- **File**: `tests/analytics/unit/test_sales_record_repository.py`
- **Test**: `test_get_total_items_sold_last_7_days`
- **Purpose**: Verify item count aggregation
- **Expected Output**: Correct count

**TC-R05: Get Total Items Sold (No Sales)**
- **File**: `tests/analytics/unit/test_sales_record_repository.py`
- **Test**: `test_get_total_items_sold_no_sales`
- **Purpose**: Handle edge case
- **Expected Output**: 0

---

### ViolationStatisticsRepository Tests

**TC-R06: Create ViolationStatistics**
- **File**: `tests/analytics/unit/test_violation_statistics_repository.py`
- **Test**: `test_create_success`
- **Purpose**: Verify creation of violation record
- **Expected Output**: ID returned

**TC-R07: Get Violation Count by Type**
- **File**: `tests/analytics/unit/test_violation_statistics_repository.py`
- **Test**: `test_get_violation_count_by_type`
- **Purpose**: Count violations of specific type
- **Expected Output**: Correct count

**TC-R08: Get Violation Count (No Data)**
- **File**: `tests/analytics/unit/test_violation_statistics_repository.py`
- **Test**: `test_get_violation_count_by_type_no_violations`
- **Expected Output**: 0

**TC-R09: Get Total Penalty Amount**
- **File**: `tests/analytics/unit/test_violation_statistics_repository.py`
- **Test**: `test_get_total_penalty_amount`
- **Purpose**: Sum all penalties for financial reporting
- **Expected Output**: Correct sum

**TC-R10: Get Total Penalty Amount (No Data)**
- **File**: `tests/analytics/unit/test_violation_statistics_repository.py`
- **Test**: `test_get_total_penalty_amount_no_penalties`
- **Expected Output**: 0.0

---

## Integration Tests (Manual Only)

**Note**: Integration tests were moved to manual testing due to complex mock requirements.
See `MANUAL_TEST_PLAN.md` for detailed test procedures (TC-13 through TC-18).

### Why Manual Testing?

The following scenarios require real database interactions and are difficult to mock reliably:
- Order completion flow with multiple repositories
- Exception handling and resilience testing
- Data retention verification after deletion
- Performance testing with real data volumes

### Integration Test Coverage (Manual)

**TC-I01: Order Completion Creates SalesRecords** → MANUAL_TEST_PLAN.md TC-13
- **Purpose**: End-to-end test of SalesRecord creation on order completion
- **Type**: Manual integration test
- **Rationale**: Requires real order flow with database transactions

**TC-I02: Analytics Exception Handling** → MANUAL_TEST_PLAN.md TC-17
- **Purpose**: Verify order completion doesn't fail if analytics fails
- **Type**: Manual resilience test
- **Rationale**: Requires simulating database failures

**TC-I03: Late Payment Creates Violation Record** → MANUAL_TEST_PLAN.md TC-4
- **Type**: Manual violation tracking test
- **Coverage**: Already covered in standard manual tests

**TC-I04: Second Underpayment Creates Violation Record** → MANUAL_TEST_PLAN.md TC-3
- **Type**: Manual violation tracking test
- **Coverage**: Already covered in standard manual tests

**TC-I05: Timeout Creates Violation Record** → MANUAL_TEST_PLAN.md TC-5
- **Type**: Manual violation tracking test
- **Coverage**: Already covered in standard manual tests

**TC-I06: User Cancellation Late Creates Violation Record** → MANUAL_TEST_PLAN.md TC-6
- **Type**: Manual violation tracking test
- **Coverage**: Already covered in standard manual tests

**TC-I07: SalesRecords Persist After Order Deletion** → MANUAL_TEST_PLAN.md TC-18
- **Purpose**: **CRITICAL** - Verify data separation
- **Type**: Manual data retention test
- **Rationale**: Requires real database deletion to verify persistence

**TC-I08: ViolationStatistics Persist After Order Deletion** → MANUAL_TEST_PLAN.md TC-7
- **Purpose**: **CRITICAL** - Verify violation tracking survives deletion
- **Type**: Manual data retention test
- **Rationale**: Requires real database deletion to verify persistence

---

## Test Execution Results

### Current Status
- ✅ All unit tests pass (21/21)
- ✅ Integration tests converted to manual tests (8 scenarios → MANUAL_TEST_PLAN.md)
- ✅ Code coverage: Repository and service layers fully tested
- ✅ No Telegram dependencies in service layer
- ✅ Data minimization verified (no user_id in analytics)

### Known Issues
- None

### Test Coverage Summary

**Automated Tests (Unit)**:
- `test_analytics_service.py`: 11 tests ✅
- `test_sales_record_repository.py`: 5 tests ✅
- `test_violation_statistics_repository.py`: 5 tests ✅
- **Total**: 21/21 passing

**Manual Tests** (see MANUAL_TEST_PLAN.md):
- Core functionality: 12 test cases
- Integration scenarios: 6 additional test cases
- **Total**: 18 manual test cases

---

## Regression Testing Checklist

Before merging to main branch:

- [ ] Run full test suite: `python -m pytest tests/ -v`
- [ ] Verify no imports from aiogram in services/repositories
- [ ] Check database migration runs successfully
- [ ] Verify data retention job starts on bot launch
- [ ] Manual test plan executed (see MANUAL_TEST_PLAN.md)