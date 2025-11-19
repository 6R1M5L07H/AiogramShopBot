#!/usr/bin/env python3
"""
Simple script to reset is_new flag - works with SQLCipher

Uses the same DB setup as db.py for guaranteed compatibility.

Usage:
    python tools/reset_items_is_new_simple.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
import os
os.chdir(project_root)
load_dotenv(project_root / ".env")

# Import same setup as db.py
import config
from sqlalchemy import create_engine, text, event, Engine
from sqlalchemy.orm import sessionmaker

print("🔄 Resetting is_new flag for all items...")
print(f"📂 Working directory: {os.getcwd()}")

# Set PRAGMA key on connect (MUST be registered BEFORE engine creation)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    print(f"🔧 Event listener triggered! DB_ENCRYPTION={config.DB_ENCRYPTION}")
    if config.DB_ENCRYPTION:
        cursor = dbapi_connection.cursor()
        # CRITICAL: Set encryption key FIRST, before any other PRAGMA
        print(f"🔑 Setting PRAGMA key (length: {len(config.DB_PASS)})")
        cursor.execute(f"PRAGMA key = '{config.DB_PASS}'")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        print("✓ PRAGMA key set successfully")

# Create engine EXACTLY like db.py does
if config.DB_ENCRYPTION:
    print("🔐 Using SQLCipher encrypted mode")
    from sqlcipher3 import dbapi2 as sqlcipher

    DB_NAME = os.getenv("DB_NAME", "database.db")
    # Use absolute path (4 slashes) - relative paths don't work with SQLCipher
    db_path = str(project_root / "data" / DB_NAME)
    # Remove leading slash for URL (4 slashes + path without leading slash = absolute path)
    db_path_for_url = db_path[1:] if db_path.startswith('/') else db_path
    url = f"sqlite+pysqlcipher://:{config.DB_PASS}@////{db_path_for_url}"

    print(f"📍 Database path: {db_path}")
    print(f"📍 URL path: {db_path_for_url}")
    print(f"📍 Connection URL: sqlite+pysqlcipher://:<PASS>@////{db_path_for_url}")
    print(f"📍 File exists: {Path(db_path).exists()}")

    # Test direct connection first
    print("\n🧪 Testing direct SQLCipher connection...")
    try:
        test_conn = sqlcipher.connect(db_path)
        test_cursor = test_conn.cursor()
        test_cursor.execute(f"PRAGMA key = '{config.DB_PASS}'")
        test_cursor.execute("SELECT COUNT(*) FROM items")
        count = test_cursor.fetchone()[0]
        print(f"✓ Direct connection works! Item count: {count}")
        test_cursor.close()
        test_conn.close()
    except Exception as e:
        print(f"✗ Direct connection failed: {e}")
        sys.exit(1)

    print("\n🔧 Creating SQLAlchemy engine...")
    engine = create_engine(url, echo=False, module=sqlcipher, connect_args={'check_same_thread': False})
    SessionMaker = sessionmaker(engine, expire_on_commit=False)

    # Use synchronous session (same as bot does with DB_ENCRYPTION=True)
    with SessionMaker() as session:
        try:
            # Get count before
            result = session.execute(text("SELECT COUNT(*) FROM items WHERE is_new = 1"))
            count_before = result.scalar()
            print(f"📊 Found {count_before} items with is_new=True")

            if count_before == 0:
                print("✅ No items to reset. All items already have is_new=False")
            else:
                # Update
                session.execute(text("UPDATE items SET is_new = 0 WHERE is_new = 1"))
                session.commit()

                # Verify
                result = session.execute(text("SELECT COUNT(*) FROM items WHERE is_new = 1"))
                count_after = result.scalar()

                print(f"✅ Reset complete! {count_before} items set to is_new=False")
                print(f"📊 Remaining items with is_new=True: {count_after}")

                if count_after == 0:
                    print("✅ All items successfully reset!")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

else:
    print("ℹ️  Non-encrypted mode - use async version")
    print("This script is for SQLCipher only")
    sys.exit(1)
