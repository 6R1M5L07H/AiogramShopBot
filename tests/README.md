# Test Suite Documentation

## Quick Start

### Run All Tests
```bash
python tests/run_all_tests.py
```

### Run Tests (Fast Mode - Skip Dependency Installation)
```bash
python tests/run_all_tests.py --fast
```

### Run Specific Tests Only
```bash
python tests/run_all_tests.py --specific payment   # Only payment tests
python tests/run_all_tests.py --specific order     # Only order tests
python tests/run_all_tests.py --specific security  # Only security tests
```

### Run with Coverage Report
```bash
python tests/run_all_tests.py --coverage
# Opens htmlcov/index.html for detailed coverage report
```

### Include Manual Test Scripts
```bash
python tests/run_all_tests.py --manual
```

### List All Available Tests
```bash
python tests/run_all_tests.py --list
```

## Test Organization

### Automated Tests (pytest)

**Architecture Tests** (`tests/architecture/`)
- `test_bot_singleton.py` - Bot instance singleton pattern
- `test_config_lazy_init.py` - Configuration lazy initialization
- `test_payment_dto_lazy_init.py` - Payment DTO lazy initialization

**Payment Tests** (`tests/payment/unit/`)
- `test_e2e_payment_flow.py` - End-to-end payment workflow
- `test_payment_validation.py` - Payment amount validation logic

**Admin Tests** (`tests/admin/`)
- `test_shipping_integration.py` - Admin shipping management integration

**Security Tests** (`tests/security/`)
- `test_html_escape.py` - HTML injection prevention

**Data Retention Tests** (`tests/data-retention/unit/`)
- `test_data_retention_cleanup.py` - GDPR data cleanup

**Exception Handling Tests** (`tests/exception-handling/`)
- `test_handler_exception_handling.py` - Handler error recovery
- `test_item_exceptions.py` - Item-related exceptions
- `test_item_grouping.py` - Item grouping logic
- `test_order_exceptions.py` - Order-related exceptions

**Configuration Tests**
- `test_config_patch.py` - Test configuration patching
- `test_config_safe.py` - Safe config operations
- `test_error_handler.py` - Error handler utilities
- `test_permission_utils.py` - Permission validation

### Manual Test Scripts

**Cart Tests** (`tests/cart/manual/`)
- `simulate_stock_race_condition.py` - Concurrent order race condition simulation

**Payment Tests** (`tests/payment/manual/`)
- `simulate_payment_webhook.py` - KryptoExpress webhook simulation

**Pricing Tests** (`tests/pricing/manual/`)
- `verify_tier_breakdown_storage.py` - Tiered pricing JSON storage verification

## Troubleshooting

**Tests fail with "Module not found"**
```bash
# Install test dependencies
python tests/run_all_tests.py  # Automatically installs deps
```

**Tests fail with "Database locked"**
```bash
# Clear test database
rm -f test_shop.db
```
