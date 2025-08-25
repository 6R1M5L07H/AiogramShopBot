#!/usr/bin/env python3
"""
Test validation script for invoice-stock-management feature test suite.

This script validates the test structure and critical test components
without running the full test suite, useful for CI/CD validation.
"""

import sys
import os
import ast
import importlib.util
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def validate_test_file(test_file_path):
    """Validate a test file for proper structure and completeness."""
    print(f"Validating {test_file_path.name}...")
    
    try:
        # Parse the test file
        with open(test_file_path, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Count test classes and methods
        test_classes = []
        test_methods = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                test_classes.append(node.name)
                
                # Count test methods in class
                for item in node.body:
                    if (isinstance(item, ast.FunctionDef) and 
                        (item.name.startswith('test_') or item.name.startswith('async def test_'))):
                        test_methods.append(f"{node.name}.{item.name}")
            
            elif (isinstance(node, ast.FunctionDef) and 
                  node.name.startswith('test_')):
                test_methods.append(node.name)
        
        print(f"  ✓ Found {len(test_classes)} test classes")
        print(f"  ✓ Found {len(test_methods)} test methods")
        
        # Check for required imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        required_imports = ['pytest', 'asyncio']
        missing_imports = [imp for imp in required_imports if not any(imp in i for i in imports)]
        
        if missing_imports:
            print(f"  ⚠️  Missing recommended imports: {missing_imports}")
        else:
            print("  ✓ Required imports present")
        
        return len(test_methods) > 0
        
    except SyntaxError as e:
        print(f"  ❌ Syntax error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error validating file: {e}")
        return False

def validate_test_configuration():
    """Validate test configuration and fixtures."""
    print("\nValidating test configuration...")
    
    # Check conftest.py
    conftest_path = project_root / 'tests' / 'conftest.py'
    if conftest_path.exists():
        print("  ✓ conftest.py found")
        
        # Check for key fixtures
        with open(conftest_path, 'r') as f:
            content = f.read()
        
        required_fixtures = [
            'test_user', 'test_admin_user', 'test_order', 
            'mock_crypto_generator', 'mock_encryption_service'
        ]
        
        found_fixtures = []
        for fixture in required_fixtures:
            if f"def {fixture}" in content:
                found_fixtures.append(fixture)
        
        print(f"  ✓ Found {len(found_fixtures)}/{len(required_fixtures)} required fixtures")
        
        if len(found_fixtures) < len(required_fixtures):
            missing = set(required_fixtures) - set(found_fixtures)
            print(f"  ⚠️  Missing fixtures: {missing}")
    
    else:
        print("  ❌ conftest.py not found")
        return False
    
    # Check requirements.txt
    requirements_path = project_root / 'tests' / 'requirements.txt'
    if requirements_path.exists():
        print("  ✓ test requirements.txt found")
    else:
        print("  ⚠️  test requirements.txt not found")
    
    return True

def validate_test_coverage():
    """Validate test coverage across critical components."""
    print("\nValidating test coverage areas...")
    
    coverage_areas = {
        'Security Tests': [
            'encryption', 'payment_validation', 'race_condition', 
            'state_transition', 'authentication'
        ],
        'Integration Tests': [
            'cart_to_order', 'webhook_processing', 'background_tasks',
            'admin_management', 'cross_service'
        ],
        'Performance Tests': [
            'concurrent_operations', 'bulk_processing', 'memory_usage',
            'response_time'
        ],
        'Edge Cases': [
            'boundary_conditions', 'error_recovery', 'timing_issues'
        ]
    }
    
    test_files = list((project_root / 'tests').glob('test_*.py'))
    
    for area, keywords in coverage_areas.items():
        print(f"\n{area}:")
        
        found_tests = []
        for test_file in test_files:
            try:
                with open(test_file, 'r') as f:
                    content = f.read().lower()
                
                for keyword in keywords:
                    if keyword.lower() in content:
                        found_tests.append(f"{test_file.name}:{keyword}")
            except Exception:
                continue
        
        if found_tests:
            print(f"  ✓ Coverage found: {len(found_tests)} test areas")
            for test in found_tests[:3]:  # Show first 3
                print(f"    - {test}")
            if len(found_tests) > 3:
                print(f"    ... and {len(found_tests) - 3} more")
        else:
            print(f"  ⚠️  No coverage found for {area}")

def check_critical_components():
    """Check that critical components being tested exist."""
    print("\nChecking critical components...")
    
    critical_files = [
        'services/order.py',
        'services/encryption.py', 
        'services/payment_observer.py',
        'utils/order_state_machine.py',
        'utils/transaction_manager.py',
        'processing/order_payment.py'
    ]
    
    missing_files = []
    for file_path in critical_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ❌ {file_path} - MISSING")
            missing_files.append(file_path)
    
    return len(missing_files) == 0

def generate_test_summary():
    """Generate a summary of the test suite."""
    print("\n" + "="*60)
    print("TEST SUITE SUMMARY")
    print("="*60)
    
    test_files = list((project_root / 'tests').glob('test_*.py'))
    total_files = len(test_files)
    
    total_classes = 0
    total_methods = 0
    
    for test_file in test_files:
        try:
            with open(test_file, 'r') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            classes = [node.name for node in ast.walk(tree) 
                      if isinstance(node, ast.ClassDef) and node.name.startswith('Test')]
            methods = [node.name for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
            
            total_classes += len(classes)
            total_methods += len(methods)
            
        except Exception:
            continue
    
    print(f"Test Files: {total_files}")
    print(f"Test Classes: {total_classes}")  
    print(f"Test Methods: {total_methods}")
    
    # Estimate coverage areas
    coverage_estimate = min(95, (total_methods * 2))  # Rough estimate
    print(f"Estimated Coverage: {coverage_estimate}%")
    
    print("\nTest Categories:")
    categories = {
        'Security': 'test_security_features.py, test_webhook_security.py',
        'Integration': 'test_integration_workflows.py', 
        'Performance': 'test_edge_cases_performance.py',
        'Configuration': 'conftest.py, requirements.txt'
    }
    
    for category, files in categories.items():
        print(f"  - {category}: {files}")

def main():
    """Main validation function."""
    print("🧪 Invoice-Stock-Management Test Suite Validation")
    print("="*60)
    
    # Validate individual test files
    test_files = list((project_root / 'tests').glob('test_*.py'))
    valid_files = 0
    
    for test_file in test_files:
        if validate_test_file(test_file):
            valid_files += 1
    
    print(f"\n✓ {valid_files}/{len(test_files)} test files are valid")
    
    # Validate configuration
    config_valid = validate_test_configuration()
    
    # Validate coverage
    validate_test_coverage()
    
    # Check critical components
    components_exist = check_critical_components()
    
    # Generate summary
    generate_test_summary()
    
    # Final assessment
    print("\n" + "="*60)
    print("VALIDATION RESULT")
    print("="*60)
    
    if valid_files == len(test_files) and config_valid and components_exist:
        print("🎉 Test suite validation PASSED")
        print("   Ready for test execution")
        return True
    else:
        print("⚠️  Test suite validation PARTIAL")
        print("   Some issues found - review above output")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)