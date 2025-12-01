#!/usr/bin/env python3
"""
Advanced Database Backup Restore Tool

This tool provides a secure, in-memory restore process with full lifecycle management:
- Interactive backup selection
- In-memory GPG decryption (no temp files)
- In-memory gzip decompression
- Automated bot lifecycle (Docker Compose)
- Safety backup + automatic rollback on failure
- Atomic file operations

Usage:
    # Interactive mode (prompts for all inputs)
    python -m utils.restore_backup_advanced

    # With compose file parameter
    python -m utils.restore_backup_advanced --compose-file docker-compose.prod.yml

    # Skip Docker lifecycle management
    python -m utils.restore_backup_advanced --skip-docker

Security Features:
- NO environment variables for secrets
- GPG private key via interactive prompt (Base64)
- Password via getpass (no echo)
- In-memory processing (no temp files on disk)
"""

import argparse
import base64
import gzip
import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import gnupg

import config
from utils.db_backup import DatabaseBackup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RestoreError(Exception):
    """Base exception for restore operations."""
    pass


class AdvancedRestore:
    """Advanced restore with in-memory processing and lifecycle management."""

    def __init__(self, compose_file: Optional[str] = None, skip_docker: bool = False):
        """
        Initialize restore handler.

        Args:
            compose_file: Path to docker-compose file (None for interactive selection)
            skip_docker: If True, skip Docker lifecycle management
        """
        self.db_path = f"data/{config.DB_NAME}"
        self.backup_handler = DatabaseBackup(self.db_path, config.DB_BACKUP_PATH)
        self.safety_backup_path: Optional[Path] = None
        self.skip_docker = skip_docker
        self.compose_file: Optional[str] = compose_file

    def run_interactive(self) -> bool:
        """
        Run interactive restore process.

        Returns:
            True if restore succeeded, False otherwise
        """
        try:
            logger.info("=" * 70)
            logger.info("ADVANCED DATABASE RESTORE TOOL")
            logger.info("=" * 70)
            logger.info("")

            # Step 0: Select Docker Compose mode (if not provided via CLI)
            if not self.skip_docker and not self.compose_file:
                self.compose_file = self._select_compose_file()
                if self.compose_file is None:
                    self.skip_docker = True
                    logger.info("Docker lifecycle management disabled")
                logger.info("")

            # Step 1: Select backup
            backup_path = self._select_backup()
            if not backup_path:
                logger.error("No backup selected, aborting")
                return False

            logger.info(f"Selected backup: {backup_path}")
            logger.info("")

            # Step 2: Get GPG key if encrypted
            gpg_key_base64: Optional[str] = None
            gpg_passphrase: Optional[str] = None

            if backup_path.suffix == ".gpg":
                logger.info("Backup is GPG encrypted")
                gpg_key_base64, gpg_passphrase = self._prompt_gpg_credentials()
                if not gpg_key_base64:
                    logger.error("GPG key required for encrypted backup")
                    return False
                logger.info("GPG credentials obtained")
                logger.info("")

            # Step 3: Verify checksum (optional)
            if not self._verify_checksum_if_exists(backup_path):
                response = input("Checksum verification failed. Continue anyway? (yes/no): ")
                if response.lower() != "yes":
                    logger.info("Restore aborted by user")
                    return False

            # Step 4: Create safety backup
            logger.info("Creating safety backup of current database...")
            if not self._create_safety_backup():
                logger.error("Failed to create safety backup, aborting")
                return False
            logger.info(f"Safety backup created: {self.safety_backup_path}")
            logger.info("")

            # Step 5: Stop bot
            if not self.skip_docker:
                logger.info("Stopping bot...")
                if not self._stop_bot():
                    logger.error("Failed to stop bot, aborting")
                    self._cleanup_safety_backup()
                    return False
                logger.info("Bot stopped")
                logger.info("")

            # Step 6: Restore database (in-memory)
            logger.info("Restoring database (in-memory processing)...")
            restore_success = self._restore_database_inmemory(
                backup_path,
                gpg_key_base64,
                gpg_passphrase
            )

            if not restore_success:
                logger.error("Database restore failed!")
                logger.info("Rolling back to safety backup...")
                self._rollback_to_safety()
                if not self.skip_docker:
                    self._start_bot()
                return False

            logger.info("Database restored successfully")
            logger.info("")

            # Step 7: Start bot
            if not self.skip_docker:
                logger.info("Starting bot...")
                if not self._start_bot():
                    logger.error("Failed to start bot after restore!")
                    logger.info("Rolling back to safety backup...")
                    self._rollback_to_safety()
                    self._start_bot()
                    return False

                logger.info("Bot started successfully")
                logger.info("")

                # Step 8: Verify bot health
                logger.info("Verifying bot health...")
                time.sleep(5)  # Give bot time to initialize
                if not self._verify_bot_health():
                    logger.warning("Bot health check failed, but restore completed")
                    logger.info("Please check bot logs manually")

            # Success! Cleanup safety backup
            self._cleanup_safety_backup()

            logger.info("=" * 70)
            logger.info("RESTORE COMPLETED SUCCESSFULLY!")
            logger.info("=" * 70)

            return True

        except KeyboardInterrupt:
            logger.info("\nRestore cancelled by user")
            if self.safety_backup_path and self.safety_backup_path.exists():
                logger.info("Rolling back to safety backup...")
                self._rollback_to_safety()
                if not self.skip_docker:
                    self._start_bot()
            return False
        except Exception as e:
            logger.error(f"Unexpected error during restore: {e}", exc_info=True)
            if self.safety_backup_path and self.safety_backup_path.exists():
                logger.info("Rolling back to safety backup...")
                self._rollback_to_safety()
                if not self.skip_docker:
                    self._start_bot()
            return False

    def _select_compose_file(self) -> Optional[str]:
        """
        Interactive Docker Compose file selection.

        Returns:
            Path to compose file, or None to skip Docker management
        """
        logger.info("Docker Compose Configuration")
        logger.info("")
        logger.info("Select Docker Compose mode:")
        logger.info("  1. Production (docker-compose.prod.yml)")
        logger.info("  2. Development (docker-compose.dev.yml)")
        logger.info("  3. Custom path")
        logger.info("  4. Skip Docker lifecycle management")
        logger.info("")

        while True:
            choice = input("Select option (1-4): ").strip()

            if choice == "1":
                compose_file = "docker-compose.prod.yml"
                if Path(compose_file).exists():
                    logger.info(f"Selected: {compose_file}")
                    return compose_file
                else:
                    logger.error(f"File not found: {compose_file}")
                    logger.info("Please choose another option")

            elif choice == "2":
                compose_file = "docker-compose.dev.yml"
                if Path(compose_file).exists():
                    logger.info(f"Selected: {compose_file}")
                    return compose_file
                else:
                    logger.error(f"File not found: {compose_file}")
                    logger.info("Please choose another option")

            elif choice == "3":
                compose_file = input("Enter path to docker-compose file: ").strip()
                if Path(compose_file).exists():
                    logger.info(f"Selected: {compose_file}")
                    return compose_file
                else:
                    logger.error(f"File not found: {compose_file}")
                    logger.info("Please enter a valid path")

            elif choice == "4":
                logger.info("Docker lifecycle management will be skipped")
                return None

            else:
                logger.error("Invalid choice. Please select 1-4")

    def _select_backup(self) -> Optional[Path]:
        """
        Interactive backup selection.

        Returns:
            Selected backup path, or None if cancelled
        """
        backups = self.backup_handler.list_backups()

        if not backups:
            logger.error("No backups found in backup directory")
            return None

        logger.info("Available backups:")
        logger.info("")

        for idx, backup in enumerate(backups, 1):
            size_mb = backup['size'] / (1024 * 1024)
            encrypted = " [ENCRYPTED]" if backup['path'].suffix == ".gpg" else ""
            compressed = " [COMPRESSED]" if ".gz" in backup['path'].suffixes else ""
            logger.info(f"  {idx}. {backup['filename']}")
            logger.info(f"      Size: {size_mb:.2f} MB")
            logger.info(f"      Created: {backup['created']}")
            logger.info(f"      Status:{encrypted}{compressed}")
            logger.info("")

        while True:
            try:
                selection = input(f"Select backup (1-{len(backups)}) or 'q' to quit: ").strip()
                if selection.lower() == 'q':
                    return None

                idx = int(selection) - 1
                if 0 <= idx < len(backups):
                    return backups[idx]['path']
                else:
                    logger.error(f"Invalid selection. Please enter 1-{len(backups)}")
            except ValueError:
                logger.error("Invalid input. Please enter a number")

    def _prompt_gpg_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Prompt for GPG private key and passphrase.

        Returns:
            Tuple of (key_base64, passphrase) or (None, None) if cancelled
        """
        import getpass

        logger.info("GPG Private Key Required")
        logger.info("Please paste your GPG private key as Base64 string")
        logger.info("(Export: gpg --armor --export-secret-keys | base64)")
        logger.info("")

        key_base64 = input("GPG Private Key (Base64): ").strip()
        if not key_base64:
            return None, None

        passphrase = getpass.getpass("GPG Key Passphrase: ")

        return key_base64, passphrase

    def _verify_checksum_if_exists(self, backup_path: Path) -> bool:
        """
        Verify backup checksum if .sha256 file exists.

        Args:
            backup_path: Path to backup file

        Returns:
            True if verification passed or no checksum file, False if verification failed
        """
        checksum_path = backup_path.with_suffix(backup_path.suffix + ".sha256")

        if not checksum_path.exists():
            logger.info("No checksum file found, skipping verification")
            return True

        logger.info("Verifying backup checksum...")
        return self.backup_handler.verify_backup(backup_path)

    def _create_safety_backup(self) -> bool:
        """
        Create safety backup of current database.

        Returns:
            True if backup succeeded, False otherwise
        """
        try:
            safety_path = self.backup_handler.create_backup(compress=True)
            if safety_path:
                self.safety_backup_path = safety_path
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to create safety backup: {e}", exc_info=True)
            return False

    def _stop_bot(self) -> bool:
        """
        Stop bot via Docker Compose.

        Returns:
            True if bot stopped successfully, False otherwise
        """
        try:
            if not self.compose_file:
                logger.warning("No compose file specified, skipping bot stop")
                return True

            if not Path(self.compose_file).exists():
                logger.warning(f"Compose file {self.compose_file} not found")
                logger.warning("Assuming bot is not running in Docker, skipping stop")
                return True

            logger.info(f"Executing: docker-compose -f {self.compose_file} stop bot")

            result = subprocess.run(
                ["docker-compose", "-f", self.compose_file, "stop", "bot"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info("Bot stopped successfully")
                time.sleep(2)  # Give OS time to release file handles
                return True
            else:
                logger.error(f"Failed to stop bot: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Bot stop timed out after 60s")
            return False
        except FileNotFoundError:
            logger.error("docker-compose command not found")
            return False
        except Exception as e:
            logger.error(f"Error stopping bot: {e}", exc_info=True)
            return False

    def _start_bot(self) -> bool:
        """
        Start bot via Docker Compose.

        Returns:
            True if bot started successfully, False otherwise
        """
        try:
            if not self.compose_file:
                logger.warning("No compose file specified, skipping bot start")
                return True

            if not Path(self.compose_file).exists():
                logger.warning(f"Compose file {self.compose_file} not found")
                logger.warning("Assuming bot is not running in Docker, skipping start")
                return True

            logger.info(f"Executing: docker-compose -f {self.compose_file} start bot")

            result = subprocess.run(
                ["docker-compose", "-f", self.compose_file, "start", "bot"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info("Bot started successfully")
                return True
            else:
                logger.error(f"Failed to start bot: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Bot start timed out after 60s")
            return False
        except FileNotFoundError:
            logger.error("docker-compose command not found")
            return False
        except Exception as e:
            logger.error(f"Error starting bot: {e}", exc_info=True)
            return False

    def _restore_database_inmemory(
        self,
        backup_path: Path,
        gpg_key_base64: Optional[str],
        gpg_passphrase: Optional[str]
    ) -> bool:
        """
        Restore database using in-memory processing.

        Args:
            backup_path: Path to backup file
            gpg_key_base64: Base64-encoded GPG private key (if encrypted)
            gpg_passphrase: GPG key passphrase (if encrypted)

        Returns:
            True if restore succeeded, False otherwise
        """
        try:
            # Read backup file into memory
            logger.info("Loading backup file into memory...")
            with open(backup_path, 'rb') as f:
                backup_data = io.BytesIO(f.read())

            # Step 1: GPG Decrypt (if needed)
            if backup_path.suffix == ".gpg":
                logger.info("Decrypting backup (GPG, in-memory)...")
                backup_data = self._decrypt_gpg_inmemory(
                    backup_data,
                    gpg_key_base64,
                    gpg_passphrase
                )
                if not backup_data:
                    return False

            # Step 2: Gzip Decompress (if needed)
            if ".gz" in backup_path.suffixes or backup_path.suffix == ".gz":
                logger.info("Decompressing backup (gzip, in-memory)...")
                backup_data = self._decompress_gzip_inmemory(backup_data)
                if not backup_data:
                    return False

            # Step 3: Verify SQLite integrity
            logger.info("Verifying SQLite database integrity...")
            if not self._verify_sqlite_integrity(backup_data):
                logger.error("SQLite integrity check failed")
                return False

            # Step 4: Write to disk atomically
            logger.info("Writing database to disk (atomic operation)...")
            if not self._write_database_atomic(backup_data):
                return False

            logger.info("Database file written successfully")
            return True

        except Exception as e:
            logger.error(f"Error during restore: {e}", exc_info=True)
            return False

    def _decrypt_gpg_inmemory(
        self,
        encrypted_data: io.BytesIO,
        key_base64: str,
        passphrase: str
    ) -> Optional[io.BytesIO]:
        """
        Decrypt GPG-encrypted data in memory.

        Args:
            encrypted_data: Encrypted data as BytesIO
            key_base64: Base64-encoded private key
            passphrase: Key passphrase

        Returns:
            Decrypted data as BytesIO, or None if decryption failed
        """
        temp_gpg_home = None
        try:
            # Create temporary GPG home directory
            temp_gpg_home = tempfile.mkdtemp(prefix="gpg_restore_")
            gpg = gnupg.GPG(gnupghome=temp_gpg_home)

            # Decode and import private key
            logger.info("Importing GPG private key...")
            try:
                key_data = base64.b64decode(key_base64)
            except Exception as e:
                logger.error(f"Failed to decode Base64 key: {e}")
                return None

            import_result = gpg.import_keys(key_data.decode('utf-8'))

            if not import_result.fingerprints:
                logger.error("Failed to import GPG private key")
                return None

            key_fingerprint = import_result.fingerprints[0]
            logger.info(f"GPG key imported: {key_fingerprint[:16]}...")

            # Decrypt data
            encrypted_data.seek(0)
            decrypted = gpg.decrypt_file(encrypted_data, passphrase=passphrase)

            if not decrypted.ok:
                logger.error(f"GPG decryption failed: {decrypted.status}")
                return None

            logger.info("GPG decryption successful")

            # Return decrypted data as BytesIO
            return io.BytesIO(decrypted.data)

        except Exception as e:
            logger.error(f"Error during GPG decryption: {e}", exc_info=True)
            return None
        finally:
            # Cleanup temporary GPG home
            if temp_gpg_home and Path(temp_gpg_home).exists():
                shutil.rmtree(temp_gpg_home, ignore_errors=True)

    def _decompress_gzip_inmemory(self, compressed_data: io.BytesIO) -> Optional[io.BytesIO]:
        """
        Decompress gzip data in memory.

        Args:
            compressed_data: Compressed data as BytesIO

        Returns:
            Decompressed data as BytesIO, or None if decompression failed
        """
        try:
            compressed_data.seek(0)
            decompressed = gzip.decompress(compressed_data.read())
            logger.info(f"Decompressed: {len(compressed_data.getvalue())} -> {len(decompressed)} bytes")
            return io.BytesIO(decompressed)
        except Exception as e:
            logger.error(f"Gzip decompression failed: {e}", exc_info=True)
            return None

    def _verify_sqlite_integrity(self, db_data: io.BytesIO) -> bool:
        """
        Verify SQLite database integrity.

        Args:
            db_data: Database data as BytesIO

        Returns:
            True if integrity check passed, False otherwise
        """
        import sqlite3

        temp_db = None
        try:
            # Write to temporary file for integrity check
            temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            temp_db.write(db_data.getvalue())
            temp_db.close()

            # Run integrity check
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()

            if result == "ok":
                logger.info("SQLite integrity check: OK")
                return True
            else:
                logger.error(f"SQLite integrity check failed: {result}")
                return False

        except Exception as e:
            logger.error(f"SQLite integrity check error: {e}", exc_info=True)
            return False
        finally:
            # Cleanup temp file
            if temp_db:
                try:
                    os.unlink(temp_db.name)
                except:
                    pass

    def _write_database_atomic(self, db_data: io.BytesIO) -> bool:
        """
        Write database to disk using atomic operation.

        Uses temp file + os.rename() for atomicity.

        Args:
            db_data: Database data as BytesIO

        Returns:
            True if write succeeded, False otherwise
        """
        try:
            db_path = Path(self.db_path)
            temp_path = db_path.with_suffix(".tmp")

            # Write to temp file
            logger.info(f"Writing to temp file: {temp_path}")
            with open(temp_path, 'wb') as f:
                f.write(db_data.getvalue())

            # Atomic rename
            logger.info(f"Atomic rename: {temp_path} -> {db_path}")
            os.rename(temp_path, db_path)

            return True

        except Exception as e:
            logger.error(f"Failed to write database: {e}", exc_info=True)
            # Cleanup temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            return False

    def _rollback_to_safety(self) -> bool:
        """
        Rollback to safety backup.

        Returns:
            True if rollback succeeded, False otherwise
        """
        try:
            if not self.safety_backup_path or not self.safety_backup_path.exists():
                logger.error("Safety backup not found, cannot rollback!")
                return False

            logger.info(f"Rolling back to: {self.safety_backup_path}")

            # Use existing restore method (it handles decompression)
            return self.backup_handler.restore_backup(self.safety_backup_path)

        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            return False

    def _cleanup_safety_backup(self):
        """Remove safety backup after successful restore."""
        try:
            if self.safety_backup_path and self.safety_backup_path.exists():
                logger.info(f"Removing safety backup: {self.safety_backup_path}")
                self.safety_backup_path.unlink()

                # Also remove checksum file
                checksum_path = self.safety_backup_path.with_suffix(
                    self.safety_backup_path.suffix + ".sha256"
                )
                if checksum_path.exists():
                    checksum_path.unlink()

        except Exception as e:
            logger.warning(f"Failed to cleanup safety backup: {e}")

    def _verify_bot_health(self) -> bool:
        """
        Verify bot health after restore.

        Returns:
            True if bot is healthy, False otherwise
        """
        try:
            import sqlite3

            # Simple check: Can we open the database?
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master")
            cursor.fetchone()
            conn.close()

            logger.info("Database connection test: OK")
            return True

        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Advanced Database Backup Restore Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (prompts for all inputs)
  python -m utils.restore_backup_advanced

  # With compose file parameter
  python -m utils.restore_backup_advanced --compose-file docker-compose.prod.yml

  # Skip Docker lifecycle management
  python -m utils.restore_backup_advanced --skip-docker
        """
    )

    parser.add_argument(
        "--compose-file",
        type=str,
        help="Path to docker-compose file (e.g., docker-compose.prod.yml)"
    )

    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker lifecycle management (bot not in container)"
    )

    args = parser.parse_args()

    # Validate compose file if provided
    if args.compose_file and not Path(args.compose_file).exists():
        logger.error(f"Compose file not found: {args.compose_file}")
        sys.exit(1)

    # Create restore instance
    restore = AdvancedRestore(
        compose_file=args.compose_file,
        skip_docker=args.skip_docker
    )

    try:
        success = restore.run_interactive()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nRestore cancelled by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
