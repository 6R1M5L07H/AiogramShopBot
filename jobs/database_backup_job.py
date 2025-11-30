"""Database Backup Job

Automatically creates and manages database backups:
- Creates compressed backups at configured intervals
- Verifies backup integrity with checksums
- Cleans up old backups according to retention policy
- Notifies admins on backup failures

Runs periodically to ensure data recovery capability.
"""

import asyncio
import logging
from datetime import datetime, timedelta

import config
from utils.db_backup import get_backup_handler
from services.notification import NotificationService


logger = logging.getLogger(__name__)


class BackupJobError(Exception):
    """Raised when backup job encounters a critical error."""
    pass


async def create_backup_with_notification() -> bool:
    """Create database backup and notify admins on failure.

    Returns:
        True if backup succeeded, False otherwise
    """
    try:
        logger.info("[Database Backup] Starting scheduled backup...")

        # Initialize backup handler in thread pool (GPG initialization blocks)
        loop = asyncio.get_event_loop()
        backup_handler = await loop.run_in_executor(None, get_backup_handler)

        # Run synchronous backup in thread pool to avoid blocking event loop
        backup_path = await loop.run_in_executor(
            None,
            backup_handler.create_backup,
            True,  # compress
            True   # encrypt
        )

        if backup_path is None:
            error_msg = "Database backup creation failed - check logs for details"
            logger.error(f"[Database Backup] ❌ {error_msg}")
            await notify_admins_backup_failure(error_msg)
            return False

        # Verify backup integrity (run in thread pool)
        loop = asyncio.get_event_loop()
        is_valid = await loop.run_in_executor(
            None,
            backup_handler.verify_backup,
            backup_path
        )

        if not is_valid:
            error_msg = f"Backup verification failed: {backup_path}"
            logger.error(f"[Database Backup] ❌ {error_msg}")
            await notify_admins_backup_failure(error_msg)
            return False

        logger.info(f"[Database Backup] ✅ Backup created and verified: {backup_path}")
        return True

    except Exception as e:
        error_msg = f"Unexpected error during backup: {e}"
        logger.error(f"[Database Backup] ❌ {error_msg}", exc_info=True)
        await notify_admins_backup_failure(error_msg)
        return False


async def cleanup_old_backups_job() -> int:
    """Clean up old backups according to retention policy.

    Returns:
        Number of backups removed
    """
    try:
        logger.info("[Database Backup] Starting backup cleanup...")

        # Initialize backup handler in thread pool (GPG initialization blocks)
        loop = asyncio.get_event_loop()
        backup_handler = await loop.run_in_executor(None, get_backup_handler)

        # Run synchronous cleanup in thread pool to avoid blocking event loop
        removed_count = await loop.run_in_executor(
            None,
            backup_handler.cleanup_old_backups,
            config.DB_BACKUP_RETENTION_DAYS
        )

        logger.info(f"[Database Backup] ✅ Cleanup complete: {removed_count} backup(s) removed")
        return removed_count

    except Exception as e:
        logger.error(f"[Database Backup] ❌ Cleanup failed: {e}", exc_info=True)
        return 0


async def notify_admins_backup_failure(error_message: str):
    """Send notification to admins about backup failure.

    Args:
        error_message: Description of the backup failure
    """
    try:
        notification_text = (
            "⚠️ <b>Database Backup Failed</b>\n\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"<b>Error:</b> {error_message}\n\n"
            "<i>Please check the logs and verify backup system.</i>"
        )

        for admin_id in config.ADMIN_ID_LIST:
            try:
                await NotificationService.send_to_user(notification_text, admin_id)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id} about backup failure: {e}")

    except Exception as e:
        logger.error(f"Failed to send backup failure notifications: {e}", exc_info=True)


async def run_backup_cycle():
    """Execute a complete backup cycle: create backup + cleanup old backups."""
    if not config.DB_BACKUP_ENABLED:
        logger.info("[Database Backup] Backups disabled in configuration")
        return

    logger.info("[Database Backup] Starting backup cycle...")

    # Create new backup
    backup_success = await create_backup_with_notification()

    # Cleanup old backups (run even if current backup failed)
    await cleanup_old_backups_job()

    logger.info(
        f"[Database Backup] Backup cycle complete "
        f"(status: {'✅ SUCCESS' if backup_success else '❌ FAILED'})"
    )


async def backup_scheduler():
    """Scheduler that runs backup cycles at configured intervals.

    This function runs indefinitely and should be started as a background task.
    """
    if not config.DB_BACKUP_ENABLED:
        logger.info("[Database Backup] Backup scheduler disabled")
        return

    logger.info(
        f"[Database Backup] Scheduler started "
        f"(interval: {config.DB_BACKUP_INTERVAL_HOURS}h, "
        f"retention: {config.DB_BACKUP_RETENTION_DAYS} days)"
    )

    # Run initial backup immediately on startup
    await run_backup_cycle()

    # Schedule periodic backups
    interval_seconds = config.DB_BACKUP_INTERVAL_HOURS * 3600

    while True:
        try:
            logger.info(
                f"[Database Backup] Next backup in {config.DB_BACKUP_INTERVAL_HOURS} hour(s) "
                f"at {(datetime.now() + timedelta(seconds=interval_seconds)).strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await asyncio.sleep(interval_seconds)
            await run_backup_cycle()

        except asyncio.CancelledError:
            logger.info("[Database Backup] Scheduler stopped")
            break
        except Exception as e:
            logger.error(f"[Database Backup] Scheduler error: {e}", exc_info=True)
            # Wait before retrying on error
            await asyncio.sleep(60)


# Manual backup function for CLI/admin usage
async def manual_backup() -> bool:
    """Trigger a manual backup (can be called from admin commands).

    Returns:
        True if backup succeeded, False otherwise
    """
    logger.info("[Database Backup] Manual backup triggered")
    return await create_backup_with_notification()


# Backup verification function for testing
async def verify_latest_backup() -> bool:
    """Verify the latest backup in the backup directory.

    Returns:
        True if latest backup is valid, False otherwise
    """
    try:
        # Initialize backup handler in thread pool (GPG initialization blocks)
        loop = asyncio.get_event_loop()
        backup_handler = await loop.run_in_executor(None, get_backup_handler)

        # Run synchronous list_backups in thread pool
        backups = await loop.run_in_executor(
            None,
            backup_handler.list_backups
        )

        if not backups:
            logger.warning("[Database Backup] No backups found to verify")
            return False

        latest_backup = backups[0]
        logger.info(f"[Database Backup] Verifying latest backup: {latest_backup['filename']}")

        # Run synchronous verify_backup in thread pool
        is_valid = await loop.run_in_executor(
            None,
            backup_handler.verify_backup,
            latest_backup['path']
        )

        if is_valid:
            logger.info("[Database Backup] ✅ Latest backup verification successful")
            return True
        else:
            logger.error("[Database Backup] ❌ Latest backup verification failed")
            return False

    except Exception as e:
        logger.error(f"[Database Backup] Failed to verify latest backup: {e}", exc_info=True)
        return False
