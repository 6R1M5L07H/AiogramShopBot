"""
Backup-related exceptions.
"""

from .base import ShopBotException


class BackupException(ShopBotException):
    """Base exception for backup-related errors."""
    pass


class BackupEncryptionDisabledException(BackupException):
    """Raised when attempting to create unencrypted backup."""

    def __init__(self):
        super().__init__(
            "Unencrypted backups are not allowed. "
            "Policy: Better no backups than unencrypted backups. "
            "Set PGP_PUBLIC_KEY_BASE64 in .env to enable encrypted backups.",
            details={'reason': 'encryption_disabled'}
        )


class BackupEncryptionUnavailableException(BackupException):
    """Raised when GPG encryption is not available."""

    def __init__(self, reason: str | None = None):
        message = "GPG encryption is not available. Cannot create backup."
        details = {'reason': reason or 'gpg_unavailable'}

        if reason:
            message += f" Reason: {reason}"

        message += " Ensure PGP_PUBLIC_KEY_BASE64 is properly configured in .env and python-gnupg is installed."

        super().__init__(message, details)


class BackupEncryptionFailedException(BackupException):
    """Raised when GPG encryption operation fails."""

    def __init__(self, status: str, backup_path: str | None = None):
        message = f"GPG encryption failed: {status}"
        details = {'status': status}

        if backup_path:
            details['backup_path'] = backup_path

        super().__init__(message, details)


class BackupCreationFailedException(BackupException):
    """Raised when backup creation fails for any reason."""

    def __init__(self, reason: str, db_path: str | None = None):
        message = f"Failed to create backup: {reason}"
        details = {'reason': reason}

        if db_path:
            details['db_path'] = db_path

        super().__init__(message, details)
