#!/usr/bin/env python3
"""
Disaster Recovery Test Script

This script performs comprehensive disaster recovery testing with automated reporting.

Features:
- Manual and Cron-compatible execution modes
- Automated Telegram notifications to admins
- GPG-encrypted detailed reports
- Test entity creation, backup, disaster simulation, restore, verification

Usage:
    # Manual execution (interactive, verbose output)
    python tests/disaster_recovery_test.py

    # Cron execution (silent, Telegram notifications)
    python tests/disaster_recovery_test.py --cron --notify-admins --encrypt-report

    # Custom options
    python tests/disaster_recovery_test.py --notify-admins  # Manual with Telegram
    python tests/disaster_recovery_test.py --cron           # Silent without Telegram

Report Location:
    logs/disaster_recovery/disaster_recovery_YYYYMMDD_HHMMSS.md
    logs/disaster_recovery/disaster_recovery_YYYYMMDD_HHMMSS.md.gpg (if encrypted)
"""

import argparse
import asyncio
import base64
import hashlib
import os
import shutil
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from db import get_async_session, session_execute, session_commit
from models.category import Category
from models.subcategory import Subcategory
from models.user import User
from repositories.category import CategoryRepository
from repositories.subcategory import SubcategoryRepository
from repositories.user import UserRepository
from sqlalchemy import select
from utils.db_backup import DatabaseBackup

# Only import Telegram-related modules if needed
try:
    from services.notification import NotificationService
    from aiogram.types import FSInputFile
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

# Only import GPG if needed
try:
    import gnupg
    GPG_AVAILABLE = True
except ImportError:
    GPG_AVAILABLE = False


class DisasterRecoveryTest:
    """Orchestrates disaster recovery testing with comprehensive reporting."""

    def __init__(self, cron_mode: bool = False, notify_admins: bool = False, encrypt_report: bool = False):
        """
        Initialize test environment.

        Args:
            cron_mode: Run in silent cron mode (no console output)
            notify_admins: Send Telegram notifications to admins
            encrypt_report: Encrypt report with GPG
        """
        self.cron_mode = cron_mode
        self.notify_admins = notify_admins
        self.encrypt_report = encrypt_report

        self.db_path = Path(f"data/{config.DB_NAME}")
        self.backup_dir = Path(config.DB_BACKUP_PATH)
        self.report_dir = Path("logs/disaster_recovery")
        self.report_dir.mkdir(parents=True, exist_ok=True, mode=0o700)  # Secure permissions

        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.report_path = self.report_dir / f"disaster_recovery_{self.timestamp}.md"

        self.test_entities: Dict[str, any] = {}
        self.test_results: List[Dict[str, any]] = []
        self.backup_path: Optional[Path] = None
        self.db_backup_path: Optional[Path] = None

        self.start_time = datetime.now()
        self.errors: List[str] = []

        # Initialize report
        self._init_report()

    def _init_report(self):
        """Initialize disaster recovery report file."""
        header = f"""# Disaster Recovery Test Report

**Test ID:** DR-{self.timestamp}
**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Environment:** {config.RUNTIME_ENVIRONMENT}
**Database:** {self.db_path}
**Mode:** {'Automatic (Cron)' if self.cron_mode else 'Manual'}

---

## Test Scenario

**Objective:** Verify database restore capability after total data loss

**Test Steps:**
1. Create test entities in live database
2. Execute backup procedure
3. Simulate total database file loss (catastrophic failure)
4. Execute restore from backup
5. Verify data integrity post-restore
6. Cleanup test data
7. Generate report and notify admins

---

## Test Execution Log

"""
        with open(self.report_path, 'w') as f:
            f.write(header)

        # Set secure permissions on report
        os.chmod(self.report_path, 0o600)

    def _log(self, message: str, level: str = "INFO"):
        """
        Log message to console and report.

        Args:
            message: Log message
            level: Log level (INFO, SUCCESS, WARNING, ERROR)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Console output (skip in cron mode)
        if not self.cron_mode:
            colors = {
                "INFO": "\033[94m",      # Blue
                "SUCCESS": "\033[92m",   # Green
                "WARNING": "\033[93m",   # Yellow
                "ERROR": "\033[91m",     # Red
            }
            reset = "\033[0m"

            color = colors.get(level, "")
            print(f"{color}[{timestamp}] [{level}] {message}{reset}")

        # Track errors for summary
        if level == "ERROR":
            self.errors.append(message)

        # Report output (Markdown format)
        with open(self.report_path, 'a') as f:
            emoji = {
                "INFO": "ℹ️",
                "SUCCESS": "✅",
                "WARNING": "⚠️",
                "ERROR": "❌",
            }
            f.write(f"**{timestamp}** {emoji.get(level, '')} **[{level}]** {message}\n\n")

    def _log_step(self, step_num: int, title: str):
        """Log test step header."""
        if not self.cron_mode:
            self._log(f"{'=' * 70}", "INFO")
            self._log(f"STEP {step_num}: {title}", "INFO")
            self._log(f"{'=' * 70}", "INFO")

        with open(self.report_path, 'a') as f:
            f.write(f"\n---\n\n### Step {step_num}: {title}\n\n")

    async def run(self) -> bool:
        """
        Execute complete disaster recovery test.

        Returns:
            True if all tests passed, False otherwise
        """
        try:
            if not self.cron_mode:
                self._log("DISASTER RECOVERY TEST STARTED", "INFO")
                self._log("", "INFO")

            # Step 1: Create test entities
            self._log_step(1, "Create Test Entities")
            if not await self._create_test_entities():
                self._log("Failed to create test entities", "ERROR")
                return False

            # Step 2: Execute backup
            self._log_step(2, "Execute Backup")
            if not await self._execute_backup():
                self._log("Failed to create backup", "ERROR")
                await self._cleanup_test_entities()
                return False

            # Step 3: Simulate disaster (remove DB file)
            self._log_step(3, "Simulate Total Database Loss")
            if not self._simulate_disaster():
                self._log("Failed to simulate disaster", "ERROR")
                return False

            # Step 4: Execute restore
            self._log_step(4, "Execute Database Restore")
            if not await self._execute_restore():
                self._log("Failed to restore database", "ERROR")
                return False

            # Step 5: Verify data integrity
            self._log_step(5, "Verify Data Integrity")
            if not await self._verify_data_integrity():
                self._log("Data integrity verification failed", "ERROR")
                return False

            # Step 6: Cleanup
            self._log_step(6, "Cleanup Test Entities")
            if not await self._cleanup_test_entities():
                self._log("Failed to cleanup test entities", "WARNING")

            # Success!
            if not self.cron_mode:
                self._log("", "INFO")
                self._log("=" * 70, "SUCCESS")
                self._log("DISASTER RECOVERY TEST COMPLETED SUCCESSFULLY", "SUCCESS")
                self._log("=" * 70, "SUCCESS")

            self._finalize_report(success=True)

            # Step 7: Send Telegram notification
            if self.notify_admins:
                await self._send_telegram_notification(success=True)

            return True

        except Exception as e:
            self._log(f"Unexpected error: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            self._finalize_report(success=False, error=str(e))

            if self.notify_admins:
                await self._send_telegram_notification(success=False)

            return False

    async def _create_test_entities(self) -> bool:
        """Create test entities in database."""
        try:
            async with get_async_session() as session:
                # Create test category
                test_category_name = f"DR_TEST_CATEGORY_{self.timestamp}"
                self._log(f"Creating category: {test_category_name}", "INFO")

                category = Category(
                    name=test_category_name,
                    emoji="🧪"
                )
                session.add(category)
                await session_commit(session)

                self.test_entities['category_id'] = category.id
                self.test_entities['category_name'] = test_category_name
                self._log(f"Category created with ID: {category.id}", "SUCCESS")

                # Create test subcategory
                test_subcategory_name = f"DR_TEST_SUBCATEGORY_{self.timestamp}"
                self._log(f"Creating subcategory: {test_subcategory_name}", "INFO")

                subcategory = Subcategory(
                    name=test_subcategory_name,
                    category_id=category.id,
                    emoji="🔬"
                )
                session.add(subcategory)
                await session_commit(session)

                self.test_entities['subcategory_id'] = subcategory.id
                self.test_entities['subcategory_name'] = test_subcategory_name
                self._log(f"Subcategory created with ID: {subcategory.id}", "SUCCESS")

                # Create test user with balance
                test_user_id = 999999999  # High ID to avoid conflicts
                test_username = f"dr_test_user_{self.timestamp}"
                test_balance = 100.50

                self._log(f"Creating user: {test_username}", "INFO")

                user = User(
                    telegram_id=test_user_id,
                    telegram_username=test_username,
                    wallet_balance=test_balance,
                    language="en"
                )
                session.add(user)
                await session_commit(session)

                self.test_entities['user_id'] = test_user_id
                self.test_entities['user_username'] = test_username
                self.test_entities['user_balance'] = test_balance
                self._log(f"User created: Telegram ID {test_user_id}, Balance {test_balance}", "SUCCESS")

                return True

        except Exception as e:
            self._log(f"Error creating test entities: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            return False

    async def _execute_backup(self) -> bool:
        """Execute backup procedure."""
        try:
            self._log("Initializing backup...", "INFO")

            backup_handler = DatabaseBackup(str(self.db_path), str(self.backup_dir))
            backup_path = backup_handler.create_backup(compress=True)

            if not backup_path:
                self._log("Backup creation failed", "ERROR")
                return False

            self.backup_path = backup_path

            backup_size = backup_path.stat().st_size
            backup_size_mb = backup_size / (1024 * 1024)

            self._log(f"Backup created: {backup_path.name}", "SUCCESS")
            self._log(f"Backup size: {backup_size_mb:.2f} MB", "INFO")

            return True

        except Exception as e:
            self._log(f"Error during backup: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            return False

    def _simulate_disaster(self) -> bool:
        """Simulate total database loss by moving DB file."""
        try:
            if not self.db_path.exists():
                self._log(f"Database file not found: {self.db_path}", "ERROR")
                return False

            # Move DB file to backup location
            self.db_backup_path = self.db_path.with_suffix(f".disaster_backup_{self.timestamp}")
            self._log(f"Moving database file to: {self.db_backup_path.name}", "WARNING")

            shutil.move(str(self.db_path), str(self.db_backup_path))

            if self.db_path.exists():
                self._log("Database file still exists after move!", "ERROR")
                return False

            self._log("DISASTER SIMULATED: Total database loss", "WARNING")
            return True

        except Exception as e:
            self._log(f"Error simulating disaster: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            return False

    async def _execute_restore(self) -> bool:
        """Execute restore procedure."""
        try:
            if not self.backup_path:
                self._log("No backup path available", "ERROR")
                return False

            self._log(f"Restoring from: {self.backup_path.name}", "INFO")

            backup_handler = DatabaseBackup(str(self.db_path), str(self.backup_dir))

            # Check for pre-restore backup
            pre_restore_backups = list(Path(self.db_path.parent).glob(f"{self.db_path.name}.pre-restore-*"))
            if pre_restore_backups:
                self._log(f"Pre-restore backup found (unexpected): {len(pre_restore_backups)} file(s)", "WARNING")
            else:
                self._log("No pre-restore backup (expected - DB was deleted)", "SUCCESS")

            # Execute restore
            success = backup_handler.restore_backup(self.backup_path)

            if not success:
                self._log("Restore failed", "ERROR")
                return False

            if not self.db_path.exists():
                self._log("Database file not found after restore!", "ERROR")
                return False

            self._log("Database restored successfully", "SUCCESS")
            return True

        except Exception as e:
            self._log(f"Error during restore: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            return False

    async def _verify_data_integrity(self) -> bool:
        """Verify test entities exist after restore."""
        try:
            self._log("Verifying test entities...", "INFO")

            async with get_async_session() as session:
                # Verify category
                category_id = self.test_entities['category_id']
                stmt = select(Category).where(Category.id == category_id)
                result = await session_execute(stmt, session)
                category = result.scalar_one_or_none()

                if not category or category.name != self.test_entities['category_name']:
                    self._log(f"Category verification failed", "ERROR")
                    return False

                self._log(f"Category verified: {category.name}", "SUCCESS")

                # Verify subcategory
                subcategory_id = self.test_entities['subcategory_id']
                stmt = select(Subcategory).where(Subcategory.id == subcategory_id)
                result = await session_execute(stmt, session)
                subcategory = result.scalar_one_or_none()

                if not subcategory or subcategory.name != self.test_entities['subcategory_name']:
                    self._log(f"Subcategory verification failed", "ERROR")
                    return False

                self._log(f"Subcategory verified: {subcategory.name}", "SUCCESS")

                # Verify user
                user_id = self.test_entities['user_id']
                stmt = select(User).where(User.telegram_id == user_id)
                result = await session_execute(stmt, session)
                user = result.scalar_one_or_none()

                if not user or user.wallet_balance != self.test_entities['user_balance']:
                    self._log(f"User verification failed", "ERROR")
                    return False

                self._log(f"User verified: Balance {user.wallet_balance}", "SUCCESS")

                self._log("DATA INTEGRITY VERIFIED", "SUCCESS")
                return True

        except Exception as e:
            self._log(f"Error verifying data integrity: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            return False

    async def _cleanup_test_entities(self) -> bool:
        """Remove test entities from database."""
        try:
            self._log("Removing test entities...", "INFO")

            async with get_async_session() as session:
                # Delete category (cascade deletes subcategory)
                category_id = self.test_entities.get('category_id')
                if category_id:
                    await CategoryRepository.delete(category_id, session)

                # Delete user
                user_id = self.test_entities.get('user_id')
                if user_id:
                    await UserRepository.delete_by_telegram_id(user_id, session)

                await session_commit(session)

            # Remove disaster backup file
            if self.db_backup_path and self.db_backup_path.exists():
                self.db_backup_path.unlink()

            self._log("Test entities cleaned up", "SUCCESS")
            return True

        except Exception as e:
            self._log(f"Error during cleanup: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            return False

    def _finalize_report(self, success: bool, error: Optional[str] = None):
        """Finalize disaster recovery report."""
        duration = datetime.now() - self.start_time

        with open(self.report_path, 'a') as f:
            f.write("\n---\n\n## Test Summary\n\n")

            if success:
                f.write("**Result:** ✅ **SUCCESS**\n\n")
                f.write("All test steps completed successfully.\n\n")
            else:
                f.write("**Result:** ❌ **FAILED**\n\n")
                if error:
                    f.write(f"**Error:** {error}\n\n")
                if self.errors:
                    f.write("**Errors encountered:**\n\n")
                    for err in self.errors:
                        f.write(f"- {err}\n")
                    f.write("\n")

            f.write(f"**Duration:** {duration.total_seconds():.2f} seconds\n\n")
            f.write(f"**Report Path:** {self.report_path}\n\n")

            f.write("---\n\n")
            f.write(f"*Generated by Disaster Recovery Test Script - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

        if not self.cron_mode:
            self._log(f"Report saved: {self.report_path}", "SUCCESS")

    def _encrypt_report(self) -> Optional[Path]:
        """
        Encrypt report with GPG.

        Returns:
            Path to encrypted file, or None if encryption failed
        """
        if not GPG_AVAILABLE:
            self._log("GPG not available, skipping encryption", "WARNING")
            return None

        if not hasattr(config, 'GPG_BACKUP_PUBLIC_KEY_FILE'):
            self._log("GPG_BACKUP_PUBLIC_KEY_FILE not configured", "WARNING")
            return None

        try:
            gpg = gnupg.GPG()

            # Import public key
            with open(config.GPG_BACKUP_PUBLIC_KEY_FILE, 'r') as f:
                import_result = gpg.import_keys(f.read())

            if not import_result.fingerprints:
                self._log("Failed to import GPG public key", "ERROR")
                return None

            key_id = import_result.fingerprints[0]

            # Encrypt report
            encrypted_path = self.report_path.with_suffix(self.report_path.suffix + ".gpg")

            with open(self.report_path, 'rb') as f:
                encrypted = gpg.encrypt_file(
                    f,
                    recipients=[key_id],
                    output=str(encrypted_path),
                    armor=False
                )

            if not encrypted.ok:
                self._log(f"GPG encryption failed: {encrypted.status}", "ERROR")
                return None

            os.chmod(encrypted_path, 0o600)
            self._log(f"Report encrypted: {encrypted_path.name}", "SUCCESS")

            return encrypted_path

        except Exception as e:
            self._log(f"Error encrypting report: {e}", "ERROR")
            return None

    async def _send_telegram_notification(self, success: bool):
        """
        Send Telegram notification to admins.

        Args:
            success: Whether test succeeded
        """
        if not TELEGRAM_AVAILABLE:
            self._log("Telegram not available, skipping notification", "WARNING")
            return

        try:
            duration = datetime.now() - self.start_time

            # Build compact summary message
            status_emoji = "✅" if success else "❌"
            status_text = "SUCCESS" if success else "FAILED"

            message = f"""🧪 <b>Disaster Recovery Test Report</b>

<b>Status:</b> {status_emoji} {status_text}
<b>Test ID:</b> DR-{self.timestamp}
<b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>Duration:</b> {duration.total_seconds():.2f}s
<b>Environment:</b> {config.RUNTIME_ENVIRONMENT}

<b>Test Steps:</b>
✅ Create test entities
✅ Execute backup
✅ Simulate database loss
✅ Restore from backup
{"✅ Verify data integrity" if success else "❌ Verification failed"}
✅ Cleanup test data

"""

            if not success and self.errors:
                message += f"<b>Errors ({len(self.errors)}):</b>\n"
                for err in self.errors[:3]:  # Show first 3 errors
                    message += f"• {err[:100]}\n"
                if len(self.errors) > 3:
                    message += f"• ... and {len(self.errors) - 3} more\n"
                message += "\n"

            message += f"📄 Detailed report attached"

            # Determine which file to send
            report_file = self.report_path

            if self.encrypt_report:
                encrypted_file = self._encrypt_report()
                if encrypted_file:
                    report_file = encrypted_file
                    message += " (GPG encrypted)"

            # Send message with file attachment
            if report_file.exists():
                document = FSInputFile(str(report_file))
                await NotificationService.send_to_admins(message, None, document=document)
                self._log("Telegram notification sent to admins", "SUCCESS")
            else:
                await NotificationService.send_to_admins(message, None)
                self._log("Telegram notification sent (no file attachment)", "WARNING")

        except Exception as e:
            self._log(f"Error sending Telegram notification: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")


async def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Disaster Recovery Test Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Manual execution (interactive)
  python tests/disaster_recovery_test.py

  # Cron execution with Telegram notifications
  python tests/disaster_recovery_test.py --cron --notify-admins --encrypt-report

  # Manual with Telegram notifications
  python tests/disaster_recovery_test.py --notify-admins
        """
    )

    parser.add_argument(
        "--cron",
        action="store_true",
        help="Run in silent cron mode (no console output)"
    )

    parser.add_argument(
        "--notify-admins",
        action="store_true",
        help="Send Telegram notifications to admins"
    )

    parser.add_argument(
        "--encrypt-report",
        action="store_true",
        help="Encrypt report with GPG before sending"
    )

    args = parser.parse_args()

    # Create test instance
    test = DisasterRecoveryTest(
        cron_mode=args.cron,
        notify_admins=args.notify_admins,
        encrypt_report=args.encrypt_report
    )

    success = await test.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
