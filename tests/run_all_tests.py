#!/usr/bin/env python3
"""
Comprehensive Test Runner for AiogramShopBot

Usage:
    python tests/run_all_tests.py              # Run all automated tests
    python tests/run_all_tests.py --fast       # Run tests without installing dependencies
    python tests/run_all_tests.py --manual     # Run manual test scripts too
    python tests/run_all_tests.py --specific payment  # Run only tests matching 'payment'
    python tests/run_all_tests.py --coverage   # Run with coverage report
    python tests/run_all_tests.py --list       # List all available tests
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Ensure tests directory is in path
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text:^70}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{BLUE}ℹ {text}{RESET}")


def setup_test_environment():
    """Set up test environment variables"""
    print_info("Setting up test environment...")

    test_env = {
        "RUNTIME_ENVIRONMENT": "test",
        "NGROK_DISABLED": "true",
        "ENCRYPTION_MASTER_KEY": "dGVzdF9tYXN0ZXJfa2V5XzEyMzQ1Njc4OTA=",
        "WEBHOOK_SECRET": "test_webhook_secret_key",
        "ORDER_TIMEOUT_MINUTES": "30",
        "BACKGROUND_TASK_INTERVAL_SECONDS": "60",
        "MAX_USER_TIMEOUTS": "3",
        "PYTHONPATH": "."
    }

    for key, value in test_env.items():
        os.environ[key] = value

    print_success("Test environment configured")


def install_test_dependencies():
    """Install test dependencies from requirements.txt"""
    requirements_file = TESTS_DIR / "requirements.txt"

    if not requirements_file.exists():
        print_error("Test requirements.txt not found")
        return False

    print_info("Installing test dependencies...")

    result = subprocess.run([
        sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements_file)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print_error(f"Failed to install test dependencies:\n{result.stderr}")
        return False

    print_success("Test dependencies installed")
    return True


def list_all_tests():
    """List all available tests"""
    print_header("Available Tests")

    # Automated tests
    print(f"{BOLD}Automated Tests (pytest):{RESET}")
    test_files = sorted(TESTS_DIR.rglob("test_*.py"))
    for test_file in test_files:
        if "manual" not in str(test_file):
            rel_path = test_file.relative_to(PROJECT_ROOT)
            print(f"  • {rel_path}")

    # Manual tests
    print(f"\n{BOLD}Manual Test Scripts:{RESET}")
    manual_tests = sorted(TESTS_DIR.rglob("*/manual/*.py"))
    for manual_test in manual_tests:
        rel_path = manual_test.relative_to(PROJECT_ROOT)
        print(f"  • {rel_path}")


def run_pytest_tests(specific: str = None, coverage: bool = False):
    """Run automated pytest tests"""
    print_header("Running Automated Tests (pytest)")

    cmd = [sys.executable, "-m", "pytest"]

    # Test path
    if specific:
        cmd.append(f"tests/*{specific}*/")
        print_info(f"Running tests matching: {specific}")
    else:
        cmd.append("tests/")
        print_info("Running all automated tests")

    # Pytest options
    cmd.extend([
        "-v",
        "--tb=short",
        "--disable-warnings",
        "-x"  # Stop on first failure
    ])

    # Coverage options
    if coverage:
        cmd.extend([
            "--cov=.",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
        print_info("Coverage report will be generated")

    print(f"\n{BOLD}Command:{RESET} {' '.join(cmd)}\n")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print_success("All automated tests passed!")
        if coverage:
            print_info("Coverage report: htmlcov/index.html")
        return True
    else:
        print_error(f"Some tests failed (exit code: {result.returncode})")
        return False


def run_manual_tests():
    """Run manual test scripts"""
    print_header("Running Manual Test Scripts")

    manual_tests = sorted(TESTS_DIR.rglob("*/manual/*.py"))

    if not manual_tests:
        print_warning("No manual test scripts found")
        return True

    print_info(f"Found {len(manual_tests)} manual test scripts")

    all_passed = True
    for test_script in manual_tests:
        rel_path = test_script.relative_to(PROJECT_ROOT)
        print(f"\n{BOLD}Running:{RESET} {rel_path}")

        result = subprocess.run([sys.executable, str(test_script)])

        if result.returncode == 0:
            print_success(f"{rel_path} completed successfully")
        else:
            print_error(f"{rel_path} failed (exit code: {result.returncode})")
            all_passed = False

    return all_passed


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for AiogramShopBot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/run_all_tests.py              # Run all automated tests
  python tests/run_all_tests.py --fast       # Skip dependency installation
  python tests/run_all_tests.py --manual     # Include manual test scripts
  python tests/run_all_tests.py --specific payment  # Only payment tests
  python tests/run_all_tests.py --coverage   # Generate coverage report
  python tests/run_all_tests.py --list       # List all available tests
        """
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip dependency installation (assumes already installed)"
    )

    parser.add_argument(
        "--manual",
        action="store_true",
        help="Also run manual test scripts"
    )

    parser.add_argument(
        "--specific",
        metavar="PATTERN",
        help="Run only tests matching this pattern (e.g., 'payment', 'order')"
    )

    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate code coverage report"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available tests and exit"
    )

    args = parser.parse_args()

    # List tests and exit
    if args.list:
        list_all_tests()
        return 0

    # Setup
    print_header("AiogramShopBot Test Suite")
    setup_test_environment()

    # Install dependencies (unless --fast)
    if not args.fast:
        if not install_test_dependencies():
            return 1
    else:
        print_info("Skipping dependency installation (--fast mode)")

    # Run automated tests
    automated_passed = run_pytest_tests(
        specific=args.specific,
        coverage=args.coverage
    )

    # Run manual tests if requested
    manual_passed = True
    if args.manual:
        manual_passed = run_manual_tests()

    # Summary
    print_header("Test Summary")

    if automated_passed and manual_passed:
        print_success("All tests passed! 🎉")
        return 0
    else:
        if not automated_passed:
            print_error("Some automated tests failed")
        if not manual_passed:
            print_error("Some manual tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
