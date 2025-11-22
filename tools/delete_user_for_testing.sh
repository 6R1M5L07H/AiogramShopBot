#!/bin/bash
#
# Delete user and all related data for testing new user notifications (runs in Docker container)
#
# This script works around SQLCipher compatibility issues between host and container
# by executing the deletion directly inside the container where SQLCipher is known to work.
#
# WARNING: This deletes ALL user data including orders, buys, and deposits!
#          Only use with test accounts that have no real transaction history.
#
# Usage:
#   ./tools/delete_user_for_testing.sh <telegram_id> [container_name]
#
# Default container: shopbot-prod
#
# Example:
#   ./tools/delete_user_for_testing.sh 123456789
#   ./tools/delete_user_for_testing.sh 123456789 shopbot-dev
#

set -e

# Check arguments
if [ $# -lt 1 ]; then
    echo "❌ Error: Telegram ID required"
    echo ""
    echo "Usage: $0 <telegram_id> [container_name]"
    echo "Example: $0 123456789"
    echo "         $0 123456789 shopbot-dev"
    exit 1
fi

TELEGRAM_ID="$1"
CONTAINER_NAME="${2:-shopbot-prod}"

# Validate telegram_id is a number (POSIX-compatible)
case "$TELEGRAM_ID" in
    ''|*[!0-9]*)
        echo "❌ Error: Telegram ID must be a number"
        echo "Got: $TELEGRAM_ID"
        exit 1
        ;;
esac

echo "🧪 Test: Delete User for New User Notification Testing"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Target Telegram ID: $TELEGRAM_ID"
echo "Container: $CONTAINER_NAME"
echo ""

# Check if container exists and is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ Error: Container '$CONTAINER_NAME' is not running"
    echo "Available containers:"
    docker ps --format '  - {{.Names}}'
    exit 1
fi

# Execute deletion in container
docker exec "$CONTAINER_NAME" python3 -c "
import os
import sys
from sqlcipher3 import dbapi2 as sqlcipher

telegram_id = $TELEGRAM_ID

# Get DB_PASS and ADMIN_ID_LIST from container environment
db_pass = os.environ.get('DB_PASS')
if not db_pass:
    print('❌ Error: DB_PASS not set in container environment')
    sys.exit(1)

admin_id_list_str = os.environ.get('ADMIN_ID_LIST', '')
if admin_id_list_str:
    admin_ids = [int(aid.strip()) for aid in admin_id_list_str.split(',')]
else:
    admin_ids = []

# SAFETY CHECK: Prevent deletion of admin accounts
if telegram_id in admin_ids:
    print()
    print('🛑 ADMIN PROTECTION ACTIVATED!')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('❌ Cannot delete admin account!')
    print()
    print(f'Telegram ID {telegram_id} is in ADMIN_ID_LIST')
    print('Admin accounts are protected from deletion.')
    print()
    print('💡 Solution: Use a test account that is NOT an admin.')
    sys.exit(1)

# Connect to database
conn = sqlcipher.connect('/bot/data/database.db')
cursor = conn.cursor()
cursor.execute(f\"PRAGMA key = '{db_pass}'\")

# Find user by telegram_id
cursor.execute('SELECT id, telegram_username, top_up_amount, strike_count FROM users WHERE telegram_id = ?', (telegram_id,))
user = cursor.fetchone()

if not user:
    print(f'❌ User with Telegram ID {telegram_id} not found in database.')
    print()
    print('✅ Good news: User can register and trigger notification!')
    cursor.close()
    conn.close()
    sys.exit(0)

user_id, username, balance, strikes = user

print()
print('🔍 Found user:')
print(f'   Username: {username or \"No username\"}')
print(f'   Telegram ID: {telegram_id}')
print(f'   Internal ID: {user_id}')
print(f'   Wallet Balance: €{balance:.2f}')
print(f'   Strikes: {strikes}')
print()

# Count related data
cursor.execute('SELECT COUNT(*) FROM orders WHERE user_id = ?', (user_id,))
orders_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM buys WHERE buyer_id = ?', (user_id,))
buys_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM deposits WHERE user_id = ?', (user_id,))
deposits_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM user_strikes WHERE user_id = ?', (user_id,))
strikes_count = cursor.fetchone()[0]

print('📊 Transaction History:')
print(f'   Orders: {orders_count}')
print(f'   Buys: {buys_count}')
print(f'   Deposits: {deposits_count}')
print(f'   Strikes: {strikes_count}')
print()

total_records = orders_count + buys_count + deposits_count + strikes_count

if total_records > 0:
    print(f'⚠️  WARNING: User has {total_records} database records!')
    print('⚠️  This will delete ALL user data including transaction history!')
    print()

print('🗑️  Deleting ALL data...')

# Delete orders (CASCADE will handle order_items and invoices)
if orders_count > 0:
    cursor.execute('DELETE FROM orders WHERE user_id = ?', (user_id,))
    print(f'   ✅ {orders_count} orders deleted')

# Delete buys
if buys_count > 0:
    cursor.execute('DELETE FROM buys WHERE buyer_id = ?', (user_id,))
    print(f'   ✅ {buys_count} buys deleted')

# Delete deposits
if deposits_count > 0:
    cursor.execute('DELETE FROM deposits WHERE user_id = ?', (user_id,))
    print(f'   ✅ {deposits_count} deposits deleted')

# Delete strikes
if strikes_count > 0:
    cursor.execute('DELETE FROM user_strikes WHERE user_id = ?', (user_id,))
    print(f'   ✅ {strikes_count} strikes deleted')

# Delete cart
cursor.execute('DELETE FROM carts WHERE user_id = ?', (user_id,))
print('   ✅ Cart deleted')

# Delete payments (should CASCADE but delete explicitly to be safe)
cursor.execute('DELETE FROM payments WHERE user_id = ?', (user_id,))
print('   ✅ Payments deleted')

# Delete user
cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
print('   ✅ User deleted')

# Commit all changes
conn.commit()

print()
print(f'✅ User with Telegram ID {telegram_id} successfully deleted!')

cursor.close()
conn.close()
"

echo ""
echo "📱 Test Instructions:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Make sure bot is running with NOTIFY_ADMIN_NEW_USER=true in .env"
echo "2. Open Telegram with account $TELEGRAM_ID"
echo "3. Send /start or interact with the bot"
echo "4. Check admin chat for new user registration notification"
echo ""
echo "✨ User will be automatically re-created and admins notified!"