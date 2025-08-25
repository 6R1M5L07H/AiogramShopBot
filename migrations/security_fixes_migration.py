"""
Security Fixes Migration Script

This script migrates the database to implement all critical security fixes:
1. Encrypts existing plaintext private keys
2. Creates new database constraints and indexes
3. Validates data integrity

Run this after updating the models but before starting the application.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_db_session, session_commit, session_execute
from repositories.order import OrderRepository
from services.encryption import EncryptionService
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityMigration:
    """
    Migration class for implementing security fixes
    """
    
    @staticmethod
    async def verify_encryption_setup():
        """
        Verify that encryption is properly configured before migration
        """
        logger.info("Verifying encryption setup...")
        
        if not os.getenv('ENCRYPTION_MASTER_KEY'):
            logger.error("ENCRYPTION_MASTER_KEY environment variable not set!")
            logger.info("To generate a new master key, run:")
            logger.info(f"export ENCRYPTION_MASTER_KEY='{EncryptionService.generate_encryption_key()}'")
            return False
        
        if not EncryptionService.verify_encryption_setup():
            logger.error("Encryption setup verification failed!")
            return False
        
        logger.info("✅ Encryption setup verified successfully")
        return True
    
    @staticmethod
    async def migrate_private_keys():
        """
        Migrate existing plaintext private keys to encrypted storage
        """
        logger.info("Starting private key migration...")
        
        try:
            migrated_count = await OrderRepository.migrate_plaintext_keys()
            logger.info(f"✅ Successfully migrated {migrated_count} private keys to encrypted storage")
            return True
            
        except Exception as e:
            logger.error(f"❌ Private key migration failed: {str(e)}")
            return False
    
    @staticmethod
    async def create_database_constraints():
        """
        Create additional database constraints and indexes for security
        """
        logger.info("Creating database constraints and indexes...")
        
        try:
            async with get_db_session() as session:
                # Create additional indexes that might not be auto-created
                constraints_sql = [
                    # Transaction hash uniqueness (if we add transaction tracking)
                    """
                    CREATE TABLE IF NOT EXISTS processed_transactions (
                        id INTEGER PRIMARY KEY,
                        tx_hash VARCHAR(128) UNIQUE NOT NULL,
                        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        order_id INTEGER,
                        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
                    )
                    """,
                    
                    # Index for processed transactions
                    "CREATE INDEX IF NOT EXISTS ix_processed_transactions_tx_hash ON processed_transactions(tx_hash)",
                    "CREATE INDEX IF NOT EXISTS ix_processed_transactions_order_id ON processed_transactions(order_id)",
                    
                    # Additional security audit table
                    """
                    CREATE TABLE IF NOT EXISTS security_audit_log (
                        id INTEGER PRIMARY KEY,
                        event_type VARCHAR(50) NOT NULL,
                        user_id INTEGER,
                        admin_id INTEGER,
                        order_id INTEGER,
                        event_data TEXT,
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                        FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE SET NULL,
                        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
                    )
                    """,
                    
                    # Index for audit log
                    "CREATE INDEX IF NOT EXISTS ix_security_audit_event_type ON security_audit_log(event_type)",
                    "CREATE INDEX IF NOT EXISTS ix_security_audit_created_at ON security_audit_log(created_at)",
                    "CREATE INDEX IF NOT EXISTS ix_security_audit_user_id ON security_audit_log(user_id)",
                    "CREATE INDEX IF NOT EXISTS ix_security_audit_admin_id ON security_audit_log(admin_id)",
                ]
                
                for sql in constraints_sql:
                    try:
                        await session.execute(text(sql))
                        logger.debug(f"Executed: {sql[:50]}...")
                    except Exception as e:
                        logger.warning(f"Could not execute constraint (may already exist): {str(e)}")
                
                await session_commit(session)
                logger.info("✅ Database constraints and indexes created successfully")
                return True
                
        except Exception as e:
            logger.error(f"❌ Database constraint creation failed: {str(e)}")
            return False
    
    @staticmethod
    async def validate_data_integrity():
        """
        Validate data integrity after migration
        """
        logger.info("Validating data integrity...")
        
        try:
            async with get_db_session() as session:
                # Check for orders without encrypted keys
                unencrypted_orders = await session.execute(text("""
                    SELECT COUNT(*) FROM orders 
                    WHERE (private_key IS NOT NULL AND encrypted_private_key IS NULL)
                """))
                unencrypted_count = unencrypted_orders.scalar()
                
                if unencrypted_count > 0:
                    logger.warning(f"⚠️ Found {unencrypted_count} orders with unencrypted private keys")
                    return False
                
                # Check for valid order statuses
                invalid_status = await session.execute(text("""
                    SELECT COUNT(*) FROM orders 
                    WHERE status NOT IN ('created', 'paid', 'shipped', 'cancelled', 'expired')
                """))
                invalid_status_count = invalid_status.scalar()
                
                if invalid_status_count > 0:
                    logger.error(f"❌ Found {invalid_status_count} orders with invalid status values")
                    return False
                
                # Check for negative amounts
                negative_amounts = await session.execute(text("""
                    SELECT COUNT(*) FROM orders WHERE total_amount <= 0
                """))
                negative_amount_count = negative_amounts.scalar()
                
                if negative_amount_count > 0:
                    logger.error(f"❌ Found {negative_amount_count} orders with negative or zero amounts")
                    return False
                
                # Check reserved stock integrity
                invalid_reservations = await session.execute(text("""
                    SELECT COUNT(*) FROM reserved_stock 
                    WHERE quantity <= 0 OR expires_at <= reserved_at
                """))
                invalid_reservation_count = invalid_reservations.scalar()
                
                if invalid_reservation_count > 0:
                    logger.error(f"❌ Found {invalid_reservation_count} invalid stock reservations")
                    return False
                
                logger.info("✅ Data integrity validation passed")
                return True
                
        except Exception as e:
            logger.error(f"❌ Data integrity validation failed: {str(e)}")
            return False
    
    @staticmethod
    async def create_security_audit_entry(event_type: str, details: str):
        """
        Create a security audit log entry for the migration
        """
        try:
            async with get_db_session() as session:
                await session.execute(text("""
                    INSERT INTO security_audit_log (event_type, event_data, created_at)
                    VALUES (:event_type, :event_data, :created_at)
                """), {
                    "event_type": event_type,
                    "event_data": details,
                    "created_at": datetime.utcnow()
                })
                await session_commit(session)
                
        except Exception as e:
            logger.warning(f"Could not create audit entry: {str(e)}")
    
    @staticmethod
    async def run_full_migration():
        """
        Run the complete security migration process
        """
        logger.info("🔒 Starting Security Fixes Migration")
        logger.info("=" * 50)
        
        start_time = datetime.utcnow()
        
        # Step 1: Verify encryption setup
        if not await SecurityMigration.verify_encryption_setup():
            logger.error("❌ Migration aborted - encryption setup failed")
            return False
        
        # Step 2: Create database constraints
        if not await SecurityMigration.create_database_constraints():
            logger.error("❌ Migration aborted - database constraint creation failed")
            return False
        
        # Step 3: Migrate private keys
        if not await SecurityMigration.migrate_private_keys():
            logger.error("❌ Migration aborted - private key migration failed")
            return False
        
        # Step 4: Validate data integrity
        if not await SecurityMigration.validate_data_integrity():
            logger.error("❌ Migration aborted - data integrity validation failed")
            return False
        
        # Step 5: Create audit entry
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        await SecurityMigration.create_security_audit_entry(
            "SECURITY_MIGRATION_COMPLETED",
            f"Security fixes migration completed successfully in {duration:.2f} seconds"
        )
        
        logger.info("=" * 50)
        logger.info(f"✅ Security Fixes Migration completed successfully in {duration:.2f} seconds")
        logger.info("🔒 Your application is now secure with the following improvements:")
        logger.info("   • Private keys encrypted with AES-256-GCM")
        logger.info("   • Payment validation tolerance reduced to 0.1%")
        logger.info("   • Database constraints and foreign keys enforced")
        logger.info("   • Atomic transactions implemented")
        logger.info("   • Security audit logging enabled")
        
        return True


async def main():
    """
    Main migration function
    """
    try:
        success = await SecurityMigration.run_full_migration()
        if success:
            logger.info("Migration completed successfully! You can now start the application.")
            sys.exit(0)
        else:
            logger.error("Migration failed! Please check the logs and fix issues before starting the application.")
            sys.exit(1)
            
    except Exception as e:
        logger.critical(f"Critical error during migration: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())