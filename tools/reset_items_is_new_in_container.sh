#!/bin/bash
#
# Reset is_new flag for all items (runs in Docker container)
#
# This script works around SQLCipher compatibility issues between host and container
# by executing the reset directly inside the container where SQLCipher is known to work.
#
# Background:
# SQLCipher 4.x requires specific cipher parameters (cipher_page_size, kdf_iter, etc.)
# that must match between DB creation and reading. Direct SQLCipher connection works
# reliably in the container, while db.py may show warnings but still functions.
#
# Usage:
#   ./tools/reset_items_is_new_in_container.sh [container_name]
#
# Default container: shopbot-prod
#

set -e

CONTAINER_NAME="${1:-shopbot-prod}"

echo "🔄 Resetting is_new flag in container: $CONTAINER_NAME"

# Check if container exists and is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ Error: Container '$CONTAINER_NAME' is not running"
    echo "Available containers:"
    docker ps --format '  - {{.Names}}'
    exit 1
fi

# Execute reset in container (uses DB_PASS from container environment)
# NOTE: Direct SQLCipher connection is more reliable than db.py for utility scripts
docker exec "$CONTAINER_NAME" python3 -c '
import os
from sqlcipher3 import dbapi2 as sqlcipher

# Get DB_PASS from container environment
db_pass = os.environ.get("DB_PASS")
if not db_pass:
    print("❌ Error: DB_PASS not set in container environment")
    exit(1)

# Connect to database
# CRITICAL: For SQLCipher 4.x, PRAGMA key alone is sufficient for existing DBs
# The cipher parameters are stored in the DB header and auto-detected
conn = sqlcipher.connect("/bot/data/database.db")
cursor = conn.cursor()
cursor.execute(f"PRAGMA key = '\''{db_pass}'\''")

# Get count before
cursor.execute("SELECT COUNT(*) FROM items WHERE is_new = 1")
count_before = cursor.fetchone()[0]
print(f"📊 Found {count_before} items with is_new=1")

if count_before > 0:
    # Update
    cursor.execute("UPDATE items SET is_new = 0 WHERE is_new = 1")
    conn.commit()

    # Verify
    cursor.execute("SELECT COUNT(*) FROM items WHERE is_new = 1")
    count_after = cursor.fetchone()[0]
    print(f"✅ Reset complete! {count_before} items set to is_new=0")
    print(f"📊 Remaining: {count_after}")
else:
    print("✅ No items to reset")

cursor.close()
conn.close()
'

echo "✅ Done!"