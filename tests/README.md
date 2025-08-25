# Invoice-Stock-Management Test Suite

This comprehensive test suite validates the complete invoice-stock-management feature implementation with security fixes. The tests cover all critical functionality, edge cases, and security scenarios.

## Test Coverage Areas

### 🔒 Security Testing (`test_security_features.py`)
- **Private Key Encryption/Decryption**: AES-256-GCM encryption with unique salts
- **Payment Validation**: 0.1% tolerance validation and precision checks
- **Race Condition Prevention**: Concurrent operation safety and atomicity
- **Transaction Boundary Integrity**: ACID properties and rollback scenarios
- **State Machine Validation**: Order status transition security
- **Key Rotation**: Encryption key rotation without data loss

### 🌐 Webhook Security Testing (`test_webhook_security.py`)
- **Rate Limiting**: IP-based request throttling and abuse prevention
- **HMAC Signature Verification**: SHA256/SHA1 signature validation
- **Payload Validation**: Size limits, malformed data handling, input sanitization
- **Injection Prevention**: SQL injection, XSS, and command injection protection
- **Replay Attack Prevention**: Transaction hash deduplication
- **Timing Attack Resistance**: Constant-time signature comparison

### 🔄 Integration Testing (`test_integration_workflows.py`)
- **Cart-to-Order Flow**: Complete workflow from cart to confirmed order
- **Payment Processing**: Webhook validation and order confirmation
- **Background Task Scheduler**: Automated order expiration handling
- **Admin Order Management**: Order shipment and private key access workflows
- **Cross-Service Integration**: Service interaction and data consistency
- **Notification Integration**: Event-driven notification system

### 🎯 Edge Cases & Performance (`test_edge_cases_performance.py`)
- **Boundary Conditions**: Timing edge cases and precision limits
- **Concurrent Operations**: Race condition handling under load
- **Performance Benchmarks**: Response time and memory usage validation
- **Error Recovery**: Database failure recovery and retry mechanisms
- **Resource Management**: Memory leak prevention and cleanup validation

## Test Infrastructure

### Fixtures (`conftest.py`)
- **Database Session Management**: Isolated test transactions with rollback
- **Test Data Creation**: Users, orders, cart items, and payment scenarios
- **Mock Services**: Crypto generation, encryption, and notifications
- **Performance Monitoring**: CPU, memory, and timing metrics
- **Error Simulation**: Database failure and network error scenarios

### Test Environment Setup
```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Set required environment variables
export TESTING=1
export ENCRYPTION_MASTER_KEY="dGVzdF9tYXN0ZXJfa2V5XzEyMzQ1Njc4OTA="
export WEBHOOK_SECRET="test_webhook_secret_key"
```

## Running Tests

### Quick Start
```bash
# Run all tests
python tests/run_tests.py

# Run with coverage report
python tests/run_tests.py --coverage

# Run specific test categories
python tests/run_tests.py --security-only
python tests/run_tests.py --integration-only
python tests/run_tests.py --performance-only
```

### Manual Test Execution
```bash
# Security tests only
pytest tests/test_security_features.py -v

# Integration tests with coverage
pytest tests/test_integration_workflows.py --cov=services

# Performance tests with output
pytest tests/test_edge_cases_performance.py::TestPerformanceScenarios -s

# All tests with detailed output
pytest tests/ -v --cov=services --cov=utils --cov-report=html
```

### Parallel Execution
```bash
# Install pytest-xdist for parallel execution
pip install pytest-xdist

# Run tests in parallel
python tests/run_tests.py --parallel
```

## Test Scenarios Covered

### Critical Security Scenarios
1. **Private Key Protection**: Encryption at rest with proper key derivation
2. **Payment Manipulation**: Amount validation with precise tolerance checking
3. **Race Condition Attacks**: Concurrent order creation and stock reservation
4. **State Transition Attacks**: Invalid order status manipulation prevention
5. **Webhook Forgery**: HMAC signature verification and replay protection
6. **Resource Exhaustion**: Rate limiting and payload size validation

### Business Logic Scenarios
1. **Order Lifecycle**: Creation → Payment → Shipment → Completion
2. **Stock Management**: Atomic reservation and race condition handling
3. **Payment Processing**: Multi-currency validation and confirmation
4. **Error Handling**: Graceful degradation and recovery mechanisms
5. **Admin Operations**: Privileged actions with proper authorization
6. **Background Processing**: Automated order expiration and cleanup

### Performance Scenarios
1. **Concurrent Users**: Multiple simultaneous order creations
2. **High-Volume Payments**: Rapid payment validation processing
3. **Bulk Encryption**: Large-scale private key encryption/decryption
4. **Memory Management**: Sustained load without memory leaks
5. **Database Performance**: Transaction handling under stress

## Test Data and Mocking Strategy

### Mock Services
- **CryptoAddressGenerator**: Deterministic address generation for testing
- **EncryptionService**: Controlled encryption/decryption for security tests
- **NotificationService**: Captured notifications for verification
- **DatabaseSessions**: Isolated transactions with automatic rollback

### Test Data Patterns
- **Valid Orders**: Standard order creation and processing flows
- **Edge Cases**: Boundary conditions and timing scenarios  
- **Invalid Data**: Malformed input and error condition testing
- **Concurrent Data**: Multi-user and race condition scenarios

## Coverage Requirements

### Minimum Coverage Thresholds
- **Overall Code Coverage**: >90%
- **Security Functions**: 100%
- **Payment Processing**: 100%
- **Order Management**: >95%
- **State Machine Logic**: 100%

### Coverage Exclusions
- External API calls (mocked in tests)
- Telegram bot integration (separate test suite)
- Database migration scripts (tested separately)
- Configuration and environment setup

## Test Performance Benchmarks

### Response Time Requirements
- **Order Creation**: <200ms per order
- **Payment Validation**: <50ms per validation
- **Webhook Processing**: <100ms per webhook
- **Encryption Operations**: <10ms per key

### Memory Usage Limits
- **Peak Memory**: <100MB increase during tests
- **Memory Leaks**: <5MB growth over sustained operations
- **Concurrent Load**: <80% memory utilization peak

### Throughput Targets
- **Concurrent Orders**: 50+ simultaneous order creations
- **Payment Validations**: 1000+ validations per second
- **Webhook Requests**: 100+ requests per minute (after rate limiting)

## Security Test Compliance

### Encryption Standards
- **Algorithm**: AES-256-GCM (authenticated encryption)
- **Key Derivation**: PBKDF2 with SHA-256 (120,000 iterations)
- **Salt Generation**: Cryptographically secure random salts
- **Key Storage**: Environment variable with base64 encoding

### Webhook Security Standards
- **Signature Algorithm**: HMAC-SHA256 primary, HMAC-SHA1 legacy support
- **Rate Limiting**: 10 requests per minute per IP address
- **Payload Limits**: 1KB maximum payload size
- **Input Validation**: Whitelist-based field validation

### Access Control Standards
- **Admin Operations**: Privilege verification for sensitive actions
- **State Transitions**: State machine enforcement for all changes
- **Audit Logging**: Comprehensive logging of security-relevant events
- **Error Handling**: No sensitive data exposure in error messages

## Continuous Integration Integration

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run all tests before commit
pre-commit run --all-files
```

### CI/CD Pipeline Integration
```yaml
# Example GitHub Actions workflow
- name: Run Security Tests
  run: python tests/run_tests.py --security-only --coverage

- name: Run Integration Tests  
  run: python tests/run_tests.py --integration-only

- name: Performance Benchmarks
  run: python tests/run_tests.py --performance-only
```

## Troubleshooting

### Common Issues
1. **Database Connection Errors**: Ensure test database is properly configured
2. **Encryption Key Errors**: Verify ENCRYPTION_MASTER_KEY environment variable
3. **Import Errors**: Check Python path includes project root
4. **Timeout Errors**: Increase test timeouts for slower systems

### Debug Mode
```bash
# Run tests with debug output
pytest tests/ -v -s --tb=long

# Run specific failing test
pytest tests/test_security_features.py::TestEncryptionSecurity::test_private_key_encryption_decryption_cycle -v -s
```

### Performance Debugging
```bash
# Run with memory profiling
python -m memory_profiler tests/run_tests.py --performance-only

# Run with timing analysis
pytest tests/test_edge_cases_performance.py --durations=10
```

## Test Maintenance

### Adding New Tests
1. Follow existing test patterns and naming conventions
2. Use appropriate fixtures from `conftest.py`
3. Include comprehensive docstrings with test scenarios
4. Add performance benchmarks for new critical paths
5. Update this README with new test coverage areas

### Updating Test Data
1. Maintain test data consistency across all test files
2. Use factory patterns for complex test object creation
3. Keep mock data realistic but deterministic
4. Update fixtures when adding new model fields or relationships

This test suite provides comprehensive coverage of the invoice-stock-management feature with a focus on security, reliability, and performance validation.