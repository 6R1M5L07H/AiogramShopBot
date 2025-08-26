import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional
from functools import wraps
from datetime import datetime, timedelta

from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy import text
from db import get_db_session, session_commit, session_rollback

logger = logging.getLogger(__name__)


class TransactionManager:
    """
    Utility class for managing database transactions with proper locking,
    rollback mechanisms, and retry logic for race condition prevention.
    """
    
    # Transaction timeout in seconds
    TRANSACTION_TIMEOUT = 30
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 0.1  # Base delay in seconds
    
    @staticmethod
    @asynccontextmanager
    async def atomic_transaction(timeout: Optional[int] = None) -> AsyncGenerator[Any, None]:
        """
        Context manager for atomic database transactions with timeout protection.
        
        Usage:
            async with TransactionManager.atomic_transaction() as session:
                # Database operations here
                await session.execute(...)
                await session.commit()
        """
        timeout = timeout or TransactionManager.TRANSACTION_TIMEOUT
        session = None
        
        try:
            async with get_db_session() as session:
                bind = session.bind
                if bind and bind.dialect.name != "sqlite":
                    # Set transaction timeout for databases that support it
                    await session.execute(text(f"SET SESSION innodb_lock_wait_timeout = {timeout}"))

                    # Start transaction with proper isolation level
                    await session.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))

                transaction_start = datetime.utcnow()
                logger.debug(f"Transaction started at {transaction_start}")

                yield session

                # Check transaction duration
                duration = (datetime.utcnow() - transaction_start).total_seconds()
                if duration > timeout:
                    logger.warning(f"Transaction exceeded timeout: {duration}s > {timeout}s")

                await session_commit(session)
                logger.debug(f"Transaction committed successfully in {duration:.2f}s")
                
        except Exception as e:
            if session:
                try:
                    await session_rollback(session)
                    logger.info(f"Transaction rolled back due to error: {str(e)}")
                except Exception as rollback_error:
                    logger.critical(f"Failed to rollback transaction: {str(rollback_error)}")
            raise
    
    @staticmethod
    @asynccontextmanager
    async def row_lock_transaction(table_name: str, row_id: int, 
                                 timeout: Optional[int] = None) -> AsyncGenerator[Any, None]:
        """
        Context manager for transactions with row-level locking.
        
        Args:
            table_name: Name of the table to lock
            row_id: ID of the row to lock
            timeout: Transaction timeout in seconds
        """
        timeout = timeout or TransactionManager.TRANSACTION_TIMEOUT
        
        try:
            async with TransactionManager.atomic_transaction(timeout) as session:
                # Acquire row-level lock using SELECT ... FOR UPDATE
                lock_query = text(f"""
                    SELECT id FROM {table_name}
                    WHERE id = :row_id
                    FOR UPDATE NOWAIT
                """)
                
                try:
                    await session.execute(lock_query, {"row_id": row_id})
                    logger.debug(f"Row lock acquired for {table_name}.id = {row_id}")
                except OperationalError as e:
                    if "Lock wait timeout" in str(e) or "try restarting transaction" in str(e):
                        raise TransactionLockTimeout(f"Could not acquire lock for {table_name}.id = {row_id}")
                    raise
                
                yield session
                
        except Exception as e:
            logger.error(f"Row lock transaction failed for {table_name}.id = {row_id}: {str(e)}")
            raise
    
    @staticmethod
    @asynccontextmanager 
    async def inventory_lock_transaction(category_id: int, subcategory_id: int,
                                       timeout: Optional[int] = None) -> AsyncGenerator[Any, None]:
        """
        Context manager for transactions with inventory-level locking to prevent stock conflicts.
        
        Args:
            category_id: Category ID for inventory lock
            subcategory_id: Subcategory ID for inventory lock  
            timeout: Transaction timeout in seconds
        """
        timeout = timeout or TransactionManager.TRANSACTION_TIMEOUT
        
        try:
            async with TransactionManager.atomic_transaction(timeout) as session:
                # Acquire inventory locks for both items and reservations
                items_lock_query = text("""
                    SELECT COUNT(*) FROM items 
                    WHERE category_id = :category_id AND subcategory_id = :subcategory_id
                    FOR UPDATE
                """)
                
                reservations_lock_query = text("""
                    SELECT COUNT(*) FROM reserved_stock
                    WHERE category_id = :category_id AND subcategory_id = :subcategory_id
                    FOR UPDATE
                """)
                
                params = {"category_id": category_id, "subcategory_id": subcategory_id}
                
                try:
                    await session.execute(items_lock_query, params)
                    await session.execute(reservations_lock_query, params)
                    logger.debug(f"Inventory lock acquired for category {category_id}, subcategory {subcategory_id}")
                except OperationalError as e:
                    if "Lock wait timeout" in str(e) or "try restarting transaction" in str(e):
                        raise TransactionLockTimeout(f"Could not acquire inventory lock for category {category_id}, subcategory {subcategory_id}")
                    raise
                
                yield session
                
        except Exception as e:
            logger.error(f"Inventory lock transaction failed for category {category_id}, subcategory {subcategory_id}: {str(e)}")
            raise
    
    @staticmethod
    def with_retry(max_retries: Optional[int] = None, delay_base: Optional[float] = None):
        """
        Decorator for automatic retry of database operations with exponential backoff.
        
        Args:
            max_retries: Maximum number of retry attempts
            delay_base: Base delay for exponential backoff
        """
        max_retries = max_retries or TransactionManager.MAX_RETRIES
        delay_base = delay_base or TransactionManager.RETRY_DELAY_BASE
        
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except (OperationalError, IntegrityError, TransactionLockTimeout) as e:
                        last_exception = e
                        
                        if attempt == max_retries:
                            logger.error(f"Function {func.__name__} failed after {max_retries} retries: {str(e)}")
                            break
                        
                        # Exponential backoff with jitter
                        delay = delay_base * (2 ** attempt) + (delay_base * 0.1 * attempt)
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay:.2f}s: {str(e)}")
                        await asyncio.sleep(delay)
                    except Exception as e:
                        # Don't retry non-transient errors
                        logger.error(f"Non-retryable error in {func.__name__}: {str(e)}")
                        raise
                
                raise last_exception
            
            return wrapper
        return decorator
    
    @staticmethod
    async def execute_with_savepoint(session, operations: list, savepoint_name: str = "sp1"):
        """
        Execute multiple operations with savepoint for partial rollback capability.
        
        Args:
            session: Database session
            operations: List of async functions to execute
            savepoint_name: Name for the savepoint
        """
        try:
            # Create savepoint
            await session.execute(text(f"SAVEPOINT {savepoint_name}"))
            logger.debug(f"Savepoint {savepoint_name} created")
            
            # Execute operations
            results = []
            for operation in operations:
                result = await operation(session)
                results.append(result)
            
            # Release savepoint if all operations succeeded
            await session.execute(text(f"RELEASE SAVEPOINT {savepoint_name}"))
            logger.debug(f"Savepoint {savepoint_name} released")
            
            return results
            
        except Exception as e:
            # Rollback to savepoint
            try:
                await session.execute(text(f"ROLLBACK TO SAVEPOINT {savepoint_name}"))
                logger.info(f"Rolled back to savepoint {savepoint_name}: {str(e)}")
            except Exception as rollback_error:
                logger.critical(f"Failed to rollback to savepoint {savepoint_name}: {str(rollback_error)}")
            raise
    
    @staticmethod
    async def check_transaction_health(session) -> dict:
        """
        Check the health and status of the current transaction.
        
        Returns:
            Dictionary with transaction status information
        """
        try:
            # Check transaction status
            result = await session.execute(text("SELECT @@tx_isolation, @@autocommit, CONNECTION_ID()"))
            isolation, autocommit, connection_id = result.fetchone()
            
            # Check for deadlocks
            deadlock_result = await session.execute(text("SHOW ENGINE INNODB STATUS"))
            innodb_status = deadlock_result.fetchone()[2]
            
            has_deadlock = "LATEST DETECTED DEADLOCK" in innodb_status
            has_lock_waits = "LOCK WAIT" in innodb_status
            
            return {
                'isolation_level': isolation,
                'autocommit': bool(autocommit),
                'connection_id': connection_id,
                'has_deadlock': has_deadlock,
                'has_lock_waits': has_lock_waits,
                'status': 'healthy' if not (has_deadlock or has_lock_waits) else 'warning'
            }
            
        except Exception as e:
            logger.error(f"Error checking transaction health: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }


class TransactionLockTimeout(Exception):
    """Exception raised when database lock acquisition times out"""
    pass


class TransactionRetryExhausted(Exception):
    """Exception raised when maximum retry attempts are exhausted"""
    pass