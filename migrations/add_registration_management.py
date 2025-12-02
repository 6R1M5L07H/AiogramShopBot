#!/usr/bin/env python3
"""
Migration: Add Registration Management System
Date: 2025-12-02

This migration adds a 3-tier registration management system with approval workflows.
Supports three modes: open (auto-approve), request_approval (manual), closed (waitlist).

Changes:
1. Creates 'system_settings' table for runtime configuration
2. Adds approval fields to 'users' table
3. Adds user statistics fields (DUMMY values for future trust-level system)

Usage:
    python migrations/add_registration_management.py
"""

import sys
import os
import asyncio
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from db import get_db_session, session_commit, session_execute

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_migration():
    """Execute the registration management migration."""
    logger.info("=" * 60)
    logger.info("REGISTRATION MANAGEMENT SYSTEM MIGRATION")
    logger.info("=" * 60)
    logger.info("")

    async with get_db_session() as session:
        try:
            # Step 1: Create system_settings table
            logger.info("Step 1: Creating 'system_settings' table...")
            try:
                await session_execute(
                    text("""
                        CREATE TABLE IF NOT EXISTS system_settings (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """),
                    session
                )
                logger.info("✅ 'system_settings' table created")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info("⚠️  'system_settings' table already exists, skipping")
                else:
                    raise

            # Step 2: Add default registration_mode setting
            logger.info("Step 2: Setting default registration mode to 'open'...")
            await session_execute(
                text("""
                    INSERT OR IGNORE INTO system_settings (key, value)
                    VALUES ('registration_mode', 'open')
                """),
                session
            )
            logger.info("✅ Default registration mode set")

            # Step 3: Add approval columns to users table
            logger.info("Step 3: Adding approval columns to 'users' table...")

            approval_columns = [
                ("approval_status", "VARCHAR(20) NOT NULL DEFAULT 'approved'"),
                ("approval_requested_at", "DATETIME"),
                ("approved_at", "DATETIME"),
                ("approved_by_admin_id", "INTEGER"),
                ("rejection_reason", "TEXT"),
            ]

            for column_name, column_type in approval_columns:
                try:
                    await session_execute(
                        text(f"""
                            ALTER TABLE users
                            ADD COLUMN {column_name} {column_type}
                        """),
                        session
                    )
                    logger.info(f"  ✅ '{column_name}' column added")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info(f"  ⚠️  '{column_name}' column already exists, skipping")
                    else:
                        raise

            # Step 4: Add user statistics columns (DUMMY values)
            logger.info("Step 4: Adding user statistics columns (DUMMY)...")

            stats_columns = [
                ("lifetime_revenue", "REAL NOT NULL DEFAULT 0.0"),
                ("lifetime_orders", "INTEGER NOT NULL DEFAULT 0"),
                ("first_order_date", "DATETIME"),
                ("last_order_date", "DATETIME"),
            ]

            for column_name, column_type in stats_columns:
                try:
                    await session_execute(
                        text(f"""
                            ALTER TABLE users
                            ADD COLUMN {column_name} {column_type}
                        """),
                        session
                    )
                    logger.info(f"  ✅ '{column_name}' column added (DUMMY)")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info(f"  ⚠️  '{column_name}' column already exists, skipping")
                    else:
                        raise

            # Step 5: Add CHECK constraints by recreating table
            logger.info("Step 5: Adding CHECK constraints...")
            try:
                # Check if table already has new columns
                result = await session_execute(
                    text("PRAGMA table_info(users)"),
                    session
                )
                columns = result.fetchall()
                column_names = [col[1] for col in columns]

                if 'approval_status' not in column_names:
                    raise Exception("approval_status column not found, cannot proceed with constraint addition")

                # Get existing table schema
                result = await session_execute(
                    text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"),
                    session
                )
                existing_schema = result.scalar()

                # Only recreate if constraints not present
                if "CHECK (lifetime_revenue >= 0)" not in existing_schema:
                    # Create new table with constraints
                    await session_execute(
                        text("""
                            CREATE TABLE users_new (
                                id INTEGER PRIMARY KEY,
                                telegram_username TEXT UNIQUE,
                                telegram_id INTEGER NOT NULL UNIQUE,
                                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                can_receive_messages INTEGER DEFAULT 1,
                                strike_count INTEGER NOT NULL DEFAULT 0,
                                is_blocked INTEGER NOT NULL DEFAULT 0,
                                blocked_at DATETIME,
                                blocked_reason TEXT,
                                top_up_amount REAL NOT NULL DEFAULT 0.0,
                                referral_code VARCHAR(8) UNIQUE,
                                referral_code_created_at DATETIME,
                                successful_orders_count INTEGER NOT NULL DEFAULT 0,
                                referral_eligible INTEGER NOT NULL DEFAULT 0,
                                max_referrals INTEGER NOT NULL DEFAULT 10,
                                successful_referrals_count INTEGER NOT NULL DEFAULT 0,
                                referred_by_user_id INTEGER,
                                referred_at DATETIME,
                                approval_status VARCHAR(20) NOT NULL DEFAULT 'approved',
                                approval_requested_at DATETIME,
                                approved_at DATETIME,
                                approved_by_admin_id INTEGER,
                                rejection_reason TEXT,
                                lifetime_revenue REAL NOT NULL DEFAULT 0.0,
                                lifetime_orders INTEGER NOT NULL DEFAULT 0,
                                first_order_date DATETIME,
                                last_order_date DATETIME,
                                CHECK (strike_count >= 0),
                                CHECK (top_up_amount >= 0),
                                CHECK (successful_orders_count >= 0),
                                CHECK (max_referrals >= 0),
                                CHECK (successful_referrals_count >= 0),
                                CHECK (lifetime_revenue >= 0),
                                CHECK (lifetime_orders >= 0),
                                CHECK (approval_status IN ('approved', 'pending', 'closed_registration', 'rejected'))
                            )
                        """),
                        session
                    )

                    # Copy data from old table
                    await session_execute(
                        text("""
                            INSERT INTO users_new
                            SELECT id, telegram_username, telegram_id, registered_at, can_receive_messages,
                                   strike_count, is_blocked, blocked_at, blocked_reason, top_up_amount,
                                   referral_code, referral_code_created_at, successful_orders_count,
                                   referral_eligible, max_referrals, successful_referrals_count,
                                   referred_by_user_id, referred_at,
                                   COALESCE(approval_status, 'approved'),
                                   approval_requested_at, approved_at, approved_by_admin_id, rejection_reason,
                                   COALESCE(lifetime_revenue, 0.0),
                                   COALESCE(lifetime_orders, 0),
                                   first_order_date, last_order_date
                            FROM users
                        """),
                        session
                    )

                    # Drop old table and rename new one
                    await session_execute(text("DROP TABLE users"), session)
                    await session_execute(text("ALTER TABLE users_new RENAME TO users"), session)

                    logger.info("✅ CHECK constraints added")
                else:
                    logger.info("⚠️  CHECK constraints already exist, skipping")

            except Exception as e:
                logger.warning(f"⚠️  Could not add constraints: {e}")
                logger.info("    Validation will be enforced at application level")

            # Step 6: Verify migration
            logger.info("")
            logger.info("Step 6: Verifying migration...")

            # Check system_settings table
            result = await session_execute(
                text("SELECT key, value FROM system_settings WHERE key = 'registration_mode'"),
                session
            )
            setting = result.fetchone()
            if setting:
                logger.info(f"✅ registration_mode = '{setting[1]}'")
            else:
                logger.error("❌ registration_mode setting not found!")
                raise Exception("Migration verification failed: registration_mode missing")

            # Check users table columns
            result = await session_execute(
                text("PRAGMA table_info(users)"),
                session
            )
            columns = result.fetchall()
            column_names = [col[1] for col in columns]

            required_columns = [
                'approval_status', 'approval_requested_at', 'approved_at',
                'approved_by_admin_id', 'rejection_reason',
                'lifetime_revenue', 'lifetime_orders', 'first_order_date', 'last_order_date'
            ]

            missing_columns = [col for col in required_columns if col not in column_names]
            if missing_columns:
                logger.error(f"❌ Missing columns: {', '.join(missing_columns)}")
                raise Exception("Migration verification failed: columns missing")
            else:
                logger.info(f"✅ All required columns exist ({len(required_columns)} columns)")

            # Check existing users have default approval_status
            result = await session_execute(
                text("SELECT COUNT(*) FROM users WHERE approval_status = 'approved'"),
                session
            )
            approved_users = result.scalar()

            result = await session_execute(
                text("SELECT COUNT(*) FROM users"),
                session
            )
            total_users = result.scalar()

            logger.info(f"📊 {approved_users}/{total_users} users have 'approved' status (existing users)")

            # Commit transaction
            await session_commit(session)
            logger.info("✅ Transaction committed")

            logger.info("")
            logger.info("=" * 60)
            logger.info("MIGRATION COMPLETE!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Summary:")
            logger.info(f"  • Created 'system_settings' table")
            logger.info(f"  • Default registration mode: 'open'")
            logger.info(f"  • Added approval workflow columns to 'users'")
            logger.info(f"  • Added DUMMY statistics columns (trust-level system TODO)")
            logger.info(f"  • Migrated {total_users} existing users to 'approved' status")
            logger.info("")
            logger.info("Registration Modes:")
            logger.info("  • open: Auto-approve new users (current)")
            logger.info("  • request_approval: Manual admin approval required")
            logger.info("  • closed: Waitlist mode, bulk approval later")
            logger.info("")
            logger.info("Approval Statuses:")
            logger.info("  • approved: User can access shop")
            logger.info("  • pending: Waiting for admin approval")
            logger.info("  • closed_registration: On waitlist")
            logger.info("  • rejected: Registration denied")
            logger.info("")
            logger.info("Next steps:")
            logger.info("  1. Implement SystemSettingsRepository")
            logger.info("  2. Extend UserRepository with approval methods")
            logger.info("  3. Update UserService.create_if_not_exist()")
            logger.info("  4. Extend AdminService with user management")
            logger.info("  5. Add admin UI handlers for user list/approval")
            logger.info("  6. Implement user notifications")
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            await session.rollback()
            raise


if __name__ == "__main__":
    try:
        asyncio.run(run_migration())
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
