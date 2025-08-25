#!/usr/bin/env python3
"""
Test runner for invoice-stock-management feature comprehensive test suite.

This script runs all tests with proper configuration, coverage reporting,
and performance monitoring.

Usage:
    python tests/run_tests.py [options]
    
Options:
    --security-only: Run only security tests
    --integration-only: Run only integration tests
    --performance-only: Run only performance tests
    --coverage: Generate coverage report
    --verbose: Verbose output
    --parallel: Run tests in parallel
"""

import sys
import os
import argparse
import subprocess
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def setup_test_environment():
    """Setup test environment variables and configuration."""
    # Set test environment variables
    os.environ['TESTING'] = '1'
    os.environ['ENCRYPTION_MASTER_KEY'] = 'dGVzdF9tYXN0ZXJfa2V5XzEyMzQ1Njc4OTA='  # Base64 test key
    os.environ['ORDER_TIMEOUT_MINUTES'] = '30'
    os.environ['WEBHOOK_SECRET'] = 'test_webhook_secret_key'
    
    print("✓ Test environment configured")

def run_security_tests(verbose=False, coverage=False):
    """Run security-focused tests."""
    print("\n🔒 Running Security Tests...")
    
    test_files = [
        'tests/test_security_features.py',
        'tests/test_webhook_security.py'
    ]
    
    cmd = ['python', '-m', 'pytest'] + test_files
    if verbose:
        cmd.append('-v')
    if coverage:
        cmd.extend(['--cov=services', '--cov=utils', '--cov=processing'])
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0

def run_integration_tests(verbose=False, coverage=False):
    """Run integration workflow tests."""
    print("\n🔄 Running Integration Tests...")
    
    test_files = [
        'tests/test_integration_workflows.py'
    ]
    
    cmd = ['python', '-m', 'pytest'] + test_files
    if verbose:
        cmd.append('-v')
    if coverage:
        cmd.extend(['--cov=services', '--cov=repositories'])
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0

def run_performance_tests(verbose=False):
    """Run performance and edge case tests."""
    print("\n⚡ Running Performance Tests...")
    
    test_files = [
        'tests/test_edge_cases_performance.py::TestPerformanceScenarios',
        'tests/test_edge_cases_performance.py::TestErrorRecoveryResilience'
    ]
    
    cmd = ['python', '-m', 'pytest'] + test_files + ['-s']  # -s to show print statements
    if verbose:
        cmd.append('-v')
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0

def run_edge_case_tests(verbose=False):
    """Run edge case tests."""
    print("\n🎯 Running Edge Case Tests...")
    
    test_files = [
        'tests/test_edge_cases_performance.py::TestOrderLifecycleEdgeCases'
    ]
    
    cmd = ['python', '-m', 'pytest'] + test_files
    if verbose:
        cmd.append('-v')
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0

def run_all_tests(verbose=False, coverage=False, parallel=False):
    """Run complete test suite."""
    print("\n🧪 Running Complete Test Suite...")
    
    cmd = ['python', '-m', 'pytest', 'tests/']
    
    if verbose:
        cmd.append('-v')
    if coverage:
        cmd.extend([
            '--cov=services',
            '--cov=utils', 
            '--cov=processing',
            '--cov=repositories',
            '--cov-report=html',
            '--cov-report=term-missing'
        ])
    if parallel:
        cmd.extend(['-n', 'auto'])  # Requires pytest-xdist
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0

def check_dependencies():
    """Check if required test dependencies are installed."""
    print("📋 Checking test dependencies...")
    
    required_packages = [
        'pytest',
        'pytest-asyncio',
        'aiohttp',
        'cryptography',
        'psutil'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r tests/requirements.txt")
        return False
    
    print("✓ All dependencies available")
    return True

def generate_test_report(test_results):
    """Generate a comprehensive test report."""
    print("\n📊 Test Execution Summary")
    print("=" * 50)
    
    total_tests = len(test_results)
    passed_tests = sum(test_results.values())
    failed_tests = total_tests - passed_tests
    
    for test_type, result in test_results.items():
        status = "✓ PASSED" if result else "❌ FAILED"
        print(f"{test_type:20} {status}")
    
    print("-" * 50)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if failed_tests == 0:
        print("\n🎉 All tests passed! System is ready for deployment.")
    else:
        print(f"\n⚠️  {failed_tests} test suite(s) failed. Review failures before deployment.")
    
    return failed_tests == 0

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description='Invoice-Stock-Management Test Runner')
    parser.add_argument('--security-only', action='store_true', help='Run only security tests')
    parser.add_argument('--integration-only', action='store_true', help='Run only integration tests')
    parser.add_argument('--performance-only', action='store_true', help='Run only performance tests')
    parser.add_argument('--edge-cases-only', action='store_true', help='Run only edge case tests')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--parallel', action='store_true', help='Run tests in parallel')
    
    args = parser.parse_args()
    
    print("🚀 Invoice-Stock-Management Test Suite")
    print("=" * 50)
    
    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)
    
    # Setup test environment
    setup_test_environment()
    
    start_time = time.time()
    test_results = {}
    
    try:
        if args.security_only:
            test_results['Security Tests'] = run_security_tests(args.verbose, args.coverage)
        elif args.integration_only:
            test_results['Integration Tests'] = run_integration_tests(args.verbose, args.coverage)
        elif args.performance_only:
            test_results['Performance Tests'] = run_performance_tests(args.verbose)
        elif args.edge_cases_only:
            test_results['Edge Case Tests'] = run_edge_case_tests(args.verbose)
        else:
            # Run all test categories
            test_results['Security Tests'] = run_security_tests(args.verbose, args.coverage)
            test_results['Integration Tests'] = run_integration_tests(args.verbose, args.coverage)
            test_results['Performance Tests'] = run_performance_tests(args.verbose)
            test_results['Edge Case Tests'] = run_edge_case_tests(args.verbose)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Test execution interrupted by user")
        sys.exit(1)
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    print(f"\n⏱️  Total execution time: {execution_time:.2f} seconds")
    
    # Generate final report
    all_passed = generate_test_report(test_results)
    
    if args.coverage and not any([args.security_only, args.integration_only, args.performance_only, args.edge_cases_only]):
        print("\n📈 Coverage report generated in htmlcov/index.html")
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()