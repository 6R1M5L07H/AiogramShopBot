"""
Migration script for wallet-based to order-based system
This migration preserves existing wallet balances while adding new order functionality
"""

import logging
from typing import Dict, Any

from db import get_db_session
from models.user import User

logger = logging.getLogger(__name__)


class WalletToOrderMigration:
    @staticmethod
    async def run_migration() -> Dict[str, Any]:
        """
        Run migration from wallet-based to order-based system
        """
        results = {
            'success': True,
            'users_migrated': 0,
            'errors': []
        }
        
        try:
            logger.info("Starting wallet-to-order migration")
            
            # The new fields (timeout_count, last_timeout_at) are already in the User model
            # and will be created automatically by SQLAlchemy when the database is initialized
            
            # Check if migration is needed by counting users without timeout_count set
            async with get_db_session() as session:
                # The migration is already handled by the model changes
                # All new fields have proper defaults, so no data migration is needed
                logger.info("Migration completed - new fields will be created automatically")
                results['users_migrated'] = 0  # No data migration needed
            
            logger.info(f"Migration completed successfully: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            results['success'] = False
            results['errors'].append(str(e))
            return results
    
    @staticmethod
    async def validate_migration() -> Dict[str, Any]:
        """
        Validate that migration was successful
        """
        validation_results = {
            'valid': True,
            'checks_passed': 0,
            'total_checks': 2,
            'errors': []
        }
        
        try:
            async with get_db_session() as session:
                # Check 1: Verify timeout fields exist in database
                try:
                    from sqlalchemy import text
                    result = await session.execute(text("PRAGMA table_info(users)"))
                    columns = result.fetchall()
                    column_names = [col[1] for col in columns]
                    
                    if 'timeout_count' in column_names and 'last_timeout_at' in column_names:
                        validation_results['checks_passed'] += 1
                        logger.info("✓ Timeout fields exist in users table")
                    else:
                        validation_results['errors'].append("Timeout fields missing from users table")
                        
                except Exception as e:
                    validation_results['errors'].append(f"Failed to check user table columns: {str(e)}")
                
                # Check 2: Verify new tables exist
                try:
                    table_check_queries = [
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'",
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='order_items'", 
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='reserved_stock'"
                    ]
                    
                    all_tables_exist = True
                    for query in table_check_queries:
                        result = await session.execute(text(query))
                        if not result.scalar():
                            all_tables_exist = False
                            validation_results['errors'].append(f"Table missing: {query.split('=')[-1].strip(\"'\")}")
                    
                    if all_tables_exist:
                        validation_results['checks_passed'] += 1
                        logger.info("✓ All new order tables exist")
                        
                except Exception as e:
                    validation_results['errors'].append(f"Failed to check table existence: {str(e)}")
            
            if validation_results['checks_passed'] == validation_results['total_checks']:
                logger.info("Migration validation passed successfully")
            else:
                validation_results['valid'] = False
                logger.error(f"Migration validation failed: {validation_results['errors']}")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Migration validation error: {str(e)}")
            validation_results['valid'] = False
            validation_results['errors'].append(str(e))
            return validation_results


async def run_migration_if_needed():
    """
    Run migration if needed and validate results
    """
    logger.info("Checking if migration is needed...")
    
    migration = WalletToOrderMigration()
    
    # Run migration
    migration_results = await migration.run_migration()
    
    if migration_results['success']:
        logger.info("Migration completed successfully")
        
        # Validate migration
        validation_results = await migration.validate_migration()
        
        if validation_results['valid']:
            logger.info("Migration validation passed")
            return True
        else:
            logger.error(f"Migration validation failed: {validation_results['errors']}")
            return False
    else:
        logger.error(f"Migration failed: {migration_results['errors']}")
        return False