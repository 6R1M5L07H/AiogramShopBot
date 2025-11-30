"""Database backup adapters for different database types.

This module provides adapters for backing up different database types
(standard SQLite and SQLCipher) with a unified interface using the Adapter Pattern.
"""

import io
import logging
import sqlite3
from abc import ABC, abstractmethod
from typing import Iterator

import config

# Dual-Mode Support: Use sqlcipher3 if DB_ENCRYPTION=true
if config.DB_ENCRYPTION:
    from sqlcipher3 import dbapi2 as sqlcipher
else:
    sqlcipher = None


logger = logging.getLogger(__name__)


class DatabaseBackupAdapter(ABC):
    """Abstract base class for database backup adapters.

    Provides a unified interface for backing up different database types.
    All adapters must implement backup_to_buffer() to stream SQL dumps
    directly to an in-memory buffer without writing plaintext to disk.
    """

    def __init__(self, db_path: str, password: str = None):
        """Initialize backup adapter.

        Args:
            db_path: Path to the database file
            password: Database password (for encrypted databases)
        """
        self.db_path = db_path
        self.password = password

    @abstractmethod
    def backup_to_buffer(self, buffer: io.BytesIO) -> None:
        """Stream database backup as SQL dump to buffer.

        This method must never write unencrypted data to disk.
        All backup operations must be performed in-memory only.

        Args:
            buffer: BytesIO buffer to write SQL dump to

        Raises:
            RuntimeError: If backup operation fails
        """
        pass


class SQLiteBackupAdapter(DatabaseBackupAdapter):
    """Backup adapter for standard SQLite databases.

    Uses the standard sqlite3.iterdump() method to stream SQL statements
    directly to the buffer without writing to disk.
    """

    def backup_to_buffer(self, buffer: io.BytesIO) -> None:
        """Stream SQLite database as SQL dump to buffer.

        Args:
            buffer: BytesIO buffer to write SQL dump to

        Raises:
            RuntimeError: If backup operation fails
        """
        try:
            logger.debug(f"Starting SQLite backup: {self.db_path}")
            conn = sqlite3.connect(self.db_path)

            try:
                # Use built-in iterdump() to stream SQL statements
                for line in conn.iterdump():
                    buffer.write(f"{line}\n".encode('utf-8'))

                logger.debug("SQLite backup completed successfully")
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"SQLite backup failed: {e}", exc_info=True)
            raise RuntimeError(f"SQLite backup failed: {e}") from e


class SQLCipherBackupAdapter(DatabaseBackupAdapter):
    """Backup adapter for SQLCipher encrypted databases.

    Implements a custom SQL dump iterator since SQLCipher connections
    don't have the iterdump() method. Streams SQL statements directly
    to the buffer without ever writing plaintext to disk.
    """

    def backup_to_buffer(self, buffer: io.BytesIO) -> None:
        """Stream SQLCipher database as SQL dump to buffer.

        Uses custom _iterdump() implementation since sqlcipher3.Connection
        doesn't provide iterdump() method like standard sqlite3.Connection.

        Args:
            buffer: BytesIO buffer to write SQL dump to

        Raises:
            RuntimeError: If backup operation fails or sqlcipher3 not available
        """
        if sqlcipher is None:
            raise RuntimeError("DB_ENCRYPTION=true but sqlcipher3 module not available")

        try:
            logger.debug(f"Starting SQLCipher backup: {self.db_path}")
            conn = sqlcipher.connect(self.db_path)
            conn.execute(f"PRAGMA key = '{self.password}'")

            try:
                # Use custom iterdump implementation for SQLCipher
                for line in self._iterdump(conn):
                    buffer.write(line.encode('utf-8'))

                logger.debug("SQLCipher backup completed successfully")
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"SQLCipher backup failed: {e}", exc_info=True)
            raise RuntimeError(f"SQLCipher backup failed: {e}") from e

    def _iterdump(self, conn) -> Iterator[str]:
        """Generate SQL dump for SQLCipher database (like sqlite3.iterdump).

        This is a custom implementation of iterdump() for SQLCipher connections
        since they don't provide this method natively. Streams SQL statements
        one at a time without loading the entire database into memory.

        Args:
            conn: SQLCipher database connection

        Yields:
            SQL statements as strings
        """
        # Start transaction
        yield "BEGIN TRANSACTION;\n"

        # Get database schema (tables, indexes, views, triggers)
        schema_cursor = conn.execute(
            "SELECT name, type, sql FROM sqlite_master "
            "WHERE sql NOT NULL AND type IN ('table', 'index', 'view', 'trigger') "
            "ORDER BY type='table' DESC, name"
        )

        schema_items = schema_cursor.fetchall()
        table_names = []

        # First pass: Create tables and collect table names
        for name, item_type, sql in schema_items:
            if item_type == 'table':
                # Skip internal SQLite tables
                if name.startswith('sqlite_'):
                    continue

                table_names.append(name)
                yield f"{sql};\n"

        # Second pass: Dump table data
        for table_name in table_names:
            # Get column info for proper INSERT statement generation
            column_cursor = conn.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in column_cursor.fetchall()]
            column_list = ", ".join(columns)

            # Dump all rows from table
            data_cursor = conn.execute(f"SELECT * FROM {table_name}")
            for row in data_cursor:
                # Format values for SQL INSERT
                values = []
                for value in row:
                    if value is None:
                        values.append("NULL")
                    elif isinstance(value, (int, float)):
                        values.append(str(value))
                    elif isinstance(value, bytes):
                        # Binary data - encode as hex
                        values.append(f"X'{value.hex()}'")
                    else:
                        # String - escape quotes
                        escaped = str(value).replace("'", "''")
                        values.append(f"'{escaped}'")

                values_str = ", ".join(values)
                yield f"INSERT INTO {table_name} ({column_list}) VALUES ({values_str});\n"

        # Third pass: Create indexes, views, triggers
        for name, item_type, sql in schema_items:
            if item_type != 'table':
                yield f"{sql};\n"

        # Commit transaction
        yield "COMMIT;\n"


def get_backup_adapter(db_path: str, password: str = None) -> DatabaseBackupAdapter:
    """Factory function to get appropriate backup adapter.

    Automatically selects the correct adapter based on DB_ENCRYPTION config.

    Args:
        db_path: Path to the database file
        password: Database password (required if DB_ENCRYPTION=true)

    Returns:
        Appropriate DatabaseBackupAdapter instance

    Raises:
        RuntimeError: If DB_ENCRYPTION=true but password is None
    """
    if config.DB_ENCRYPTION:
        if password is None:
            raise RuntimeError("DB_ENCRYPTION=true but no password provided")
        logger.debug("Using SQLCipherBackupAdapter")
        return SQLCipherBackupAdapter(db_path, password)
    else:
        logger.debug("Using SQLiteBackupAdapter")
        return SQLiteBackupAdapter(db_path)