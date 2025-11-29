"""Database backup utilities.

This module provides utilities for backing up and managing SQLite database backups.
"""

import gzip
import hashlib
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import config

# Dual-Mode Support: Use sqlcipher3 if DB_ENCRYPTION=true
if config.DB_ENCRYPTION:
    from sqlcipher3 import dbapi2 as sqlcipher
else:
    sqlcipher = None


logger = logging.getLogger(__name__)


class DatabaseBackup:
    """Handles database backup operations."""

    def __init__(self, db_path: str, backup_dir: str):
        """Initialize backup handler.

        Args:
            db_path: Path to the SQLite database file
            backup_dir: Directory where backups will be stored
        """
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, compress: bool = True) -> Optional[Path]:
        """Create a backup of the database.

        Supports both standard SQLite and SQLCipher encrypted databases.
        Automatically detects encryption mode from config.DB_ENCRYPTION.

        Args:
            compress: Whether to compress the backup with gzip

        Returns:
            Path to the backup file, or None if backup failed
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"db_backup_{timestamp}.db"
            backup_path = self.backup_dir / backup_filename

            # Use SQLite's backup API for safe online backup
            logger.info(f"Creating database backup: {backup_path}")

            # Dual-Mode: Use sqlcipher if DB_ENCRYPTION=true
            if config.DB_ENCRYPTION:
                if sqlcipher is None:
                    raise RuntimeError("DB_ENCRYPTION=true but sqlcipher3 module not available")

                logger.debug("Using SQLCipher for encrypted database backup")

                # Connect to encrypted source database
                source_conn = sqlcipher.connect(self.db_path)
                # SECURITY: Use parameter binding to prevent password exposure in logs
                source_conn.execute("PRAGMA key = ?", (config.DB_PASS,))

                # Connect to unencrypted backup file (backups are NOT encrypted)
                backup_conn = sqlite3.connect(str(backup_path))

                try:
                    # Perform the backup (encrypted → unencrypted)
                    source_conn.backup(backup_conn)
                    logger.info(f"Database backup created successfully (decrypted): {backup_path}")
                finally:
                    source_conn.close()
                    backup_conn.close()
            else:
                logger.debug("Using standard SQLite for database backup")

                # Standard SQLite backup (unencrypted → unencrypted)
                source_conn = sqlite3.connect(self.db_path)
                backup_conn = sqlite3.connect(str(backup_path))

                try:
                    # Perform the backup
                    source_conn.backup(backup_conn)
                    logger.info(f"Database backup created successfully: {backup_path}")
                finally:
                    source_conn.close()
                    backup_conn.close()

            # Compress backup if requested
            if compress:
                compressed_path = self._compress_backup(backup_path)
                if compressed_path:
                    backup_path.unlink()  # Remove uncompressed file
                    backup_path = compressed_path

            # Create checksum file
            self._create_checksum(backup_path)

            return backup_path

        except Exception as e:
            logger.error(f"Failed to create database backup: {e}", exc_info=True)
            return None

    def _compress_backup(self, backup_path: Path) -> Optional[Path]:
        """Compress backup file with gzip.

        Args:
            backup_path: Path to uncompressed backup

        Returns:
            Path to compressed file, or None if compression failed
        """
        try:
            compressed_path = backup_path.with_suffix(backup_path.suffix + ".gz")
            logger.info(f"Compressing backup: {compressed_path}")

            with open(backup_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            original_size = backup_path.stat().st_size
            compressed_size = compressed_path.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100
            logger.info(
                f"Backup compressed successfully: {original_size:,} -> {compressed_size:,} bytes "
                f"({ratio:.1f}% reduction)"
            )

            return compressed_path

        except Exception as e:
            logger.error(f"Failed to compress backup: {e}", exc_info=True)
            return None

    def _create_checksum(self, backup_path: Path) -> None:
        """Create SHA256 checksum file for backup verification.

        Args:
            backup_path: Path to backup file
        """
        try:
            checksum_path = backup_path.with_suffix(backup_path.suffix + ".sha256")
            logger.debug(f"Creating checksum: {checksum_path}")

            sha256_hash = hashlib.sha256()
            with open(backup_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

            checksum = sha256_hash.hexdigest()
            with open(checksum_path, "w") as f:
                f.write(f"{checksum}  {backup_path.name}\n")

            logger.debug(f"Checksum created: {checksum}")

        except Exception as e:
            logger.error(f"Failed to create checksum: {e}", exc_info=True)

    def verify_backup(self, backup_path: Path) -> bool:
        """Verify backup integrity using checksum.

        Args:
            backup_path: Path to backup file

        Returns:
            True if backup is valid, False otherwise
        """
        try:
            checksum_path = backup_path.with_suffix(backup_path.suffix + ".sha256")
            if not checksum_path.exists():
                logger.warning(f"Checksum file not found: {checksum_path}")
                return False

            # Read expected checksum
            with open(checksum_path, "r") as f:
                expected_checksum = f.read().split()[0]

            # Calculate actual checksum
            sha256_hash = hashlib.sha256()
            with open(backup_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            actual_checksum = sha256_hash.hexdigest()

            if expected_checksum == actual_checksum:
                logger.info(f"Backup verification successful: {backup_path}")
                return True
            else:
                logger.error(
                    f"Backup verification failed: {backup_path}\n"
                    f"Expected: {expected_checksum}\n"
                    f"Actual: {actual_checksum}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to verify backup: {e}", exc_info=True)
            return False

    def cleanup_old_backups(self, retention_days: int) -> int:
        """Remove backups older than retention period.

        Args:
            retention_days: Number of days to keep backups

        Returns:
            Number of backups removed
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            removed_count = 0

            logger.info(f"Cleaning up backups older than {retention_days} days (cutoff: {cutoff_date})")

            for backup_file in self.backup_dir.glob("db_backup_*.db*"):
                # Skip checksum files (they'll be removed with their backup)
                if backup_file.suffix == ".sha256":
                    continue

                file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_mtime < cutoff_date:
                    logger.info(f"Removing old backup: {backup_file} (created: {file_mtime})")

                    # Remove backup file
                    backup_file.unlink()
                    removed_count += 1

                    # Remove associated checksum file if it exists
                    checksum_file = backup_file.with_suffix(backup_file.suffix + ".sha256")
                    if checksum_file.exists():
                        checksum_file.unlink()

            logger.info(f"Removed {removed_count} old backup(s)")
            return removed_count

        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}", exc_info=True)
            return 0

    def restore_backup(self, backup_path: Path, target_path: Optional[str] = None) -> bool:
        """Restore database from backup.

        Args:
            backup_path: Path to backup file
            target_path: Path where to restore (defaults to original db_path)

        Returns:
            True if restore succeeded, False otherwise
        """
        try:
            if target_path is None:
                target_path = self.db_path

            logger.warning(f"Restoring database from backup: {backup_path} -> {target_path}")

            # Verify backup integrity first
            if not self.verify_backup(backup_path):
                logger.error("Backup verification failed, aborting restore")
                return False

            # Handle compressed backups
            if backup_path.suffix == ".gz":
                logger.info("Decompressing backup...")
                temp_path = backup_path.with_suffix("")
                with gzip.open(backup_path, "rb") as f_in:
                    with open(temp_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_path = temp_path

            # Create backup of current database before overwriting
            if os.path.exists(target_path):
                backup_current = f"{target_path}.pre-restore-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                logger.info(f"Backing up current database to: {backup_current}")
                shutil.copy2(target_path, backup_current)

            # Restore from backup
            shutil.copy2(backup_path, target_path)
            logger.info(f"Database restored successfully: {target_path}")

            # Clean up temporary decompressed file if it exists
            if backup_path.suffix == "":
                backup_path.unlink()

            return True

        except Exception as e:
            logger.error(f"Failed to restore database: {e}", exc_info=True)
            return False

    def list_backups(self) -> list[dict]:
        """List all available backups.

        Returns:
            List of backup info dictionaries
        """
        backups = []

        for backup_file in sorted(self.backup_dir.glob("db_backup_*.db*"), reverse=True):
            # Skip checksum files
            if backup_file.suffix == ".sha256":
                continue

            stat = backup_file.stat()
            backups.append({
                "path": backup_file,
                "filename": backup_file.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime),
                "compressed": backup_file.suffix == ".gz"
            })

        return backups


def get_backup_handler() -> DatabaseBackup:
    """Get configured backup handler instance.

    Returns:
        DatabaseBackup instance configured from environment
    """
    # Construct DB path from data directory and DB_NAME
    db_path = f"data/{config.DB_NAME}"
    backup_dir = config.DB_BACKUP_PATH
    return DatabaseBackup(db_path, backup_dir)
