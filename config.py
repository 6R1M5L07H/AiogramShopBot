import os

from dotenv import load_dotenv

from enums.currency import Currency
from enums.runtime_environment import RuntimeEnvironment
from external_ip import get_sslipio_external_url
from ngrok_executor import start_ngrok

# Load .env but don't override existing environment variables
# This allows test scripts to set RUNTIME_ENVIRONMENT=TEST before import
load_dotenv(".env", override=False)
RUNTIME_ENVIRONMENT = RuntimeEnvironment(os.environ.get("RUNTIME_ENVIRONMENT"))

# Webhook setup - skip for TEST mode (used by test scripts)
if RUNTIME_ENVIRONMENT == RuntimeEnvironment.TEST:
    WEBHOOK_HOST = None
    WEBHOOK_PATH = None
    WEBHOOK_URL = None
elif RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
    WEBHOOK_HOST = start_ngrok()
    WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH")
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
else:  # PROD
    WEBHOOK_HOST = get_sslipio_external_url()
    WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH")
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBAPP_HOST = os.environ.get("WEBAPP_HOST")
WEBAPP_PORT = int(os.environ.get("WEBAPP_PORT")) if os.environ.get("WEBAPP_PORT") else None
TOKEN = os.environ.get("TOKEN")

# Admin Authentication - ALWAYS use plaintext IDs for functionality
# Admin IDs are needed for:
# - Sending notifications (new orders, errors, system events)
# - Startup messages
# - Admin-specific features
ADMIN_ID_LIST = os.environ.get("ADMIN_ID_LIST").split(',')
ADMIN_ID_LIST = [int(admin_id) for admin_id in ADMIN_ID_LIST]

# Generate hashes for secure verification (computed at runtime)
# These are used for permission checks without storing hashes in env
from utils.admin_hash_generator import generate_admin_id_hash
ADMIN_ID_HASHES = [generate_admin_id_hash(admin_id) for admin_id in ADMIN_ID_LIST]

# Security Note: ADMIN_ID_LIST must be in .env for notifications to work.
# The hashes provide defense-in-depth but don't eliminate the need for IDs.
# Recommended security measures:
# - Restrict .env file permissions (chmod 600)
# - Use environment-specific secrets management (Vault, AWS Secrets Manager)
# - Never commit .env to version control
# - Rotate admin IDs if env file is compromised

SUPPORT_LINK = os.environ.get("SUPPORT_LINK")
DB_ENCRYPTION = os.environ.get("DB_ENCRYPTION", False) == 'true'
DB_NAME = os.environ.get("DB_NAME")
DB_PASS = os.environ.get("DB_PASS")
PAGE_ENTRIES = int(os.environ.get("PAGE_ENTRIES"))
BOT_LANGUAGE = os.environ.get("BOT_LANGUAGE")
MULTIBOT = os.environ.get("MULTIBOT", False) == 'true'
CURRENCY = Currency(os.environ.get("CURRENCY"))
KRYPTO_EXPRESS_API_KEY = os.environ.get("KRYPTO_EXPRESS_API_KEY")
KRYPTO_EXPRESS_API_URL = os.environ.get("KRYPTO_EXPRESS_API_URL")
KRYPTO_EXPRESS_API_SECRET = os.environ.get("KRYPTO_EXPRESS_API_SECRET")
WEBHOOK_SECRET_TOKEN = os.environ.get("WEBHOOK_SECRET_TOKEN")
REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")

# Invoice/Order System Configuration
ORDER_TIMEOUT_MINUTES = int(os.environ.get("ORDER_TIMEOUT_MINUTES", "30"))  # Default: 30 minutes
ORDER_CANCEL_GRACE_PERIOD_MINUTES = int(os.environ.get("ORDER_CANCEL_GRACE_PERIOD_MINUTES", "5"))  # Grace period for free cancellation

# Payment Validation Configuration
PAYMENT_TOLERANCE_OVERPAYMENT_PERCENT = float(os.environ.get("PAYMENT_TOLERANCE_OVERPAYMENT_PERCENT", "0.1"))
PAYMENT_UNDERPAYMENT_RETRY_ENABLED = os.environ.get("PAYMENT_UNDERPAYMENT_RETRY_ENABLED", "true") == "true"
PAYMENT_UNDERPAYMENT_RETRY_TIMEOUT_MINUTES = int(os.environ.get("PAYMENT_UNDERPAYMENT_RETRY_TIMEOUT_MINUTES", "30"))
PAYMENT_UNDERPAYMENT_PENALTY_PERCENT = float(os.environ.get("PAYMENT_UNDERPAYMENT_PENALTY_PERCENT", "5"))
PAYMENT_LATE_PENALTY_PERCENT = float(os.environ.get("PAYMENT_LATE_PENALTY_PERCENT", "5"))

# Data Retention Configuration
DATA_RETENTION_DAYS = int(os.environ.get("DATA_RETENTION_DAYS", "30"))
REFERRAL_DATA_RETENTION_DAYS = int(os.environ.get("REFERRAL_DATA_RETENTION_DAYS", "365"))

# Shipping Management Configuration
SHIPPING_ADDRESS_SECRET = os.environ.get("ENCRYPTION_SECRET", "")

# Strike System Configuration
MAX_STRIKES_BEFORE_BAN = int(os.environ.get("MAX_STRIKES_BEFORE_BAN", "3"))  # Default: 3 strikes = ban
EXEMPT_ADMINS_FROM_BAN = os.environ.get("EXEMPT_ADMINS_FROM_BAN", "true") == "true"  # Default: admins exempt from bans
UNBAN_TOP_UP_AMOUNT = float(os.environ.get("UNBAN_TOP_UP_AMOUNT", "50.0"))  # Minimum top-up amount to unban (EUR)

# Logging Configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_MASK_SECRETS = os.environ.get("LOG_MASK_SECRETS", "true") == "true"  # Mask sensitive data in logs
LOG_ROTATION_DAYS = int(os.environ.get("LOG_ROTATION_DAYS", "7"))  # Keep logs for N days

# Rate Limiting Configuration
MAX_ORDERS_PER_USER_PER_HOUR = int(os.environ.get("MAX_ORDERS_PER_USER_PER_HOUR", "5"))  # Prevent order spam
MAX_PAYMENT_CHECKS_PER_MINUTE = int(os.environ.get("MAX_PAYMENT_CHECKS_PER_MINUTE", "10"))  # Prevent payment status spam

# Database Backup Configuration
DB_BACKUP_ENABLED = os.environ.get("DB_BACKUP_ENABLED", "true") == "true"  # Enable automated backups
DB_BACKUP_INTERVAL_HOURS = int(os.environ.get("DB_BACKUP_INTERVAL_HOURS", "6"))  # Backup every N hours
DB_BACKUP_RETENTION_DAYS = int(os.environ.get("DB_BACKUP_RETENTION_DAYS", "7"))  # Keep backups for N days
DB_BACKUP_PATH = os.environ.get("DB_BACKUP_PATH", "./backups")  # Backup directory path
