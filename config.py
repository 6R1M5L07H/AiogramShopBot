import os
import logging

from dotenv import load_dotenv

from enums.currency import Currency
from enums.runtime_environment import RuntimeEnvironment
from external_ip import get_sslipio_external_url
from ngrok_executor import start_ngrok

# Load .env but don't override existing environment variables
# This allows test scripts to set RUNTIME_ENVIRONMENT=TEST before import
load_dotenv(".env", override=False)

# Parse RUNTIME_ENVIRONMENT with clear error message on misconfiguration
try:
    _runtime_env_str = os.environ.get("RUNTIME_ENVIRONMENT")
    if not _runtime_env_str:
        raise ValueError("RUNTIME_ENVIRONMENT environment variable is not set")
    RUNTIME_ENVIRONMENT = RuntimeEnvironment(_runtime_env_str)
except ValueError as e:
    valid_values = [env.value for env in RuntimeEnvironment]
    import sys
    print(f"\n ERROR: Invalid RUNTIME_ENVIRONMENT configuration\n", file=sys.stderr)
    print(f"Reason: {e}", file=sys.stderr)
    print(f"Valid values: {', '.join(valid_values)}", file=sys.stderr)
    print(f"Current value: {os.environ.get('RUNTIME_ENVIRONMENT', '(not set)')}", file=sys.stderr)
    print(f"\nAdd to .env: RUNTIME_ENVIRONMENT={valid_values[0]}\n", file=sys.stderr)
    sys.exit(1)

# Webhook configuration (initialized lazily at startup to avoid side-effects)
WEBHOOK_HOST = None
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH")
WEBHOOK_URL = None


def initialize_webhook_config():
    """
    Initialize webhook configuration with side effects.

    This function must be called explicitly during bot startup.
    It performs side effects (starting ngrok, HTTP requests) that should NOT
    happen during module import.

    Side effects:
    - DEV mode: Starts ngrok tunnel (subprocess)
    - PROD mode: Makes HTTP request to sslipio.com
    - Sets BOT_DOMAIN automatically from WEBHOOK_HOST if not configured

    Returns:
        str: The webhook URL
    """
    global WEBHOOK_HOST, WEBHOOK_URL, BOT_DOMAIN

    # TEST mode: No webhook needed
    if RUNTIME_ENVIRONMENT == RuntimeEnvironment.TEST:
        WEBHOOK_HOST = None
        WEBHOOK_URL = None
        return None

    # DEV mode: Start ngrok tunnel
    elif RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
        WEBHOOK_HOST = start_ngrok()
        WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

        # Auto-set BOT_DOMAIN from ngrok URL if not configured
        if not BOT_DOMAIN:
            BOT_DOMAIN = WEBHOOK_HOST
            logging.info(f"[Init] BOT_DOMAIN auto-configured from ngrok: {BOT_DOMAIN}")

        return WEBHOOK_URL

    # PROD mode: Get external IP
    else:
        WEBHOOK_HOST = get_sslipio_external_url()
        WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

        # Auto-set BOT_DOMAIN from external IP if not configured
        if not BOT_DOMAIN:
            BOT_DOMAIN = WEBHOOK_HOST
            logging.info(f"[Init] BOT_DOMAIN auto-configured from external IP: {BOT_DOMAIN}")

        return WEBHOOK_URL

WEBAPP_HOST = os.environ.get("WEBAPP_HOST")
WEBAPP_PORT = int(os.environ.get("WEBAPP_PORT")) if os.environ.get("WEBAPP_PORT") else None
TOKEN = os.environ.get("TOKEN")

# Admin Authentication - ALWAYS use plaintext IDs for functionality
# Admin IDs are needed for:
# - Sending notifications (new orders, errors, system events)
# - Startup messages
# - Admin-specific features
try:
    _admin_id_list_str = os.environ.get("ADMIN_ID_LIST")
    if not _admin_id_list_str or len(_admin_id_list_str.strip()) == 0:
        raise ValueError("ADMIN_ID_LIST environment variable is not set or empty")
    ADMIN_ID_LIST = _admin_id_list_str.split(',')
    ADMIN_ID_LIST = [int(admin_id.strip()) for admin_id in ADMIN_ID_LIST]
    if len(ADMIN_ID_LIST) == 0:
        raise ValueError("ADMIN_ID_LIST must contain at least one admin ID")
except ValueError as e:
    import sys
    print(f"\n ERROR: Invalid ADMIN_ID_LIST configuration\n", file=sys.stderr)
    print(f"Reason: {e}", file=sys.stderr)
    print(f"Expected format: comma-separated list of Telegram user IDs", file=sys.stderr)
    print(f"Example: ADMIN_ID_LIST=123456789,987654321", file=sys.stderr)
    print(f"Current value: {os.environ.get('ADMIN_ID_LIST', '(not set)')}\n", file=sys.stderr)
    sys.exit(1)

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

# Admin Notifications
NOTIFY_ADMINS_NEW_USER = os.environ.get("NOTIFY_ADMINS_NEW_USER", "true") == "true"  # Default: enabled

SUPPORT_LINK = os.environ.get("SUPPORT_LINK")
DB_ENCRYPTION = os.environ.get("DB_ENCRYPTION", False) == 'true'
DB_NAME = os.environ.get("DB_NAME")
DB_PASS = os.environ.get("DB_PASS")

# Parse PAGE_ENTRIES with error handling
try:
    _page_entries_str = os.environ.get("PAGE_ENTRIES")
    if not _page_entries_str:
        raise ValueError("PAGE_ENTRIES environment variable is not set")
    PAGE_ENTRIES = int(_page_entries_str)
    if PAGE_ENTRIES <= 0:
        raise ValueError(f"PAGE_ENTRIES must be positive (got: {PAGE_ENTRIES})")
except ValueError as e:
    import sys
    print(f"\n ERROR: Invalid PAGE_ENTRIES configuration\n", file=sys.stderr)
    print(f"Reason: {e}", file=sys.stderr)
    print(f"Expected: Positive integer (e.g., 10, 20, 50)", file=sys.stderr)
    print(f"Current value: {os.environ.get('PAGE_ENTRIES', '(not set)')}\n", file=sys.stderr)
    sys.exit(1)

BOT_LANGUAGE = os.environ.get("BOT_LANGUAGE", "en")  # Default to English
SHIPPING_COUNTRY = os.environ.get("SHIPPING_COUNTRY", "de")  # Default to Germany
MULTIBOT = os.environ.get("MULTIBOT", False) == 'true'

# Parse CURRENCY with error handling
try:
    _currency_str = os.environ.get("CURRENCY")
    if not _currency_str:
        raise ValueError("CURRENCY environment variable is not set")
    CURRENCY = Currency(_currency_str)
except ValueError as e:
    valid_currencies = [c.value for c in Currency]
    import sys
    print(f"\n ERROR: Invalid CURRENCY configuration\n", file=sys.stderr)
    print(f"Reason: {e}", file=sys.stderr)
    print(f"Valid values: {', '.join(valid_currencies)}", file=sys.stderr)
    print(f"Current value: {os.environ.get('CURRENCY', '(not set)')}", file=sys.stderr)
    print(f"\nAdd to .env: CURRENCY={valid_currencies[0]}\n", file=sys.stderr)
    sys.exit(1)
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

# Cryptocurrency Decimal Precision Configuration
# Defines the number of decimal places for each cryptocurrency (smallest unit precision)
# BTC: 8 decimals = satoshi (1 BTC = 100,000,000 satoshi)
# ETH: 18 decimals = wei (1 ETH = 1,000,000,000,000,000,000 wei)
# LTC: 8 decimals = litoshi (1 LTC = 100,000,000 litoshi)
# SOL: 9 decimals = lamport (1 SOL = 1,000,000,000 lamport)
# BNB: 18 decimals (1 BNB = 1,000,000,000,000,000,000 smallest units)
# USDT/USDC: 6 decimals (1 USDT = 1,000,000 smallest units)
CRYPTO_DECIMAL_PLACES = {
    "BTC": int(os.environ.get("CRYPTO_DECIMALS_BTC", "8")),
    "LTC": int(os.environ.get("CRYPTO_DECIMALS_LTC", "8")),
    "ETH": int(os.environ.get("CRYPTO_DECIMALS_ETH", "18")),
    "SOL": int(os.environ.get("CRYPTO_DECIMALS_SOL", "9")),
    "BNB": int(os.environ.get("CRYPTO_DECIMALS_BNB", "18")),
    "USDT_TRC20": int(os.environ.get("CRYPTO_DECIMALS_USDT_TRC20", "6")),
    "USDT_ERC20": int(os.environ.get("CRYPTO_DECIMALS_USDT_ERC20", "6")),
    "USDC_ERC20": int(os.environ.get("CRYPTO_DECIMALS_USDC_ERC20", "6")),
}

# Data Retention Configuration
DATA_RETENTION_DAYS = int(os.environ.get("DATA_RETENTION_DAYS", "30"))
REFERRAL_DATA_RETENTION_DAYS = int(os.environ.get("REFERRAL_DATA_RETENTION_DAYS", "365"))

# Shipping Management Configuration
SHIPPING_ADDRESS_SECRET = os.environ.get("SHIPPING_ADDRESS_SECRET", "")  # Validated at startup

# PGP Encryption Configuration
BOT_DOMAIN = os.environ.get("BOT_DOMAIN", "")  # Base domain for webapp URLs (e.g., "example.com" or "https://example.com")
PGP_PUBLIC_KEY_BASE64 = os.environ.get("PGP_PUBLIC_KEY_BASE64", "")  # Base64-encoded PGP public key for client-side encryption

# Strike System Configuration
MAX_STRIKES_BEFORE_BAN = int(os.environ.get("MAX_STRIKES_BEFORE_BAN", "3"))  # Default: 3 strikes = ban
EXEMPT_ADMINS_FROM_BAN = os.environ.get("EXEMPT_ADMINS_FROM_BAN", "true") == "true"  # Default: admins exempt from bans
UNBAN_TOP_UP_AMOUNT = float(os.environ.get("UNBAN_TOP_UP_AMOUNT", "50.0"))  # Minimum top-up amount to unban (EUR)

# Logging Configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_MASK_SECRETS = os.environ.get("LOG_MASK_SECRETS", "true") == "true"  # Mask sensitive data in logs

# Log Retention: Environment-specific defaults
# Dev: Use DATA_RETENTION_DAYS (30 days default) for debugging
# Prod: Use 5 days default to save disk space
if RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
    LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", str(DATA_RETENTION_DAYS)))
else:
    LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "5"))

# Backward compatibility alias
LOG_ROTATION_DAYS = LOG_RETENTION_DAYS

# Rate Limiting Configuration
MAX_ORDERS_PER_USER_PER_HOUR = int(os.environ.get("MAX_ORDERS_PER_USER_PER_HOUR", "5"))  # Prevent order spam
MAX_PAYMENT_CHECKS_PER_MINUTE = int(os.environ.get("MAX_PAYMENT_CHECKS_PER_MINUTE", "10"))  # Prevent payment status spam

# Database Backup Configuration
DB_BACKUP_ENABLED = os.environ.get("DB_BACKUP_ENABLED", "true") == "true"  # Enable automated backups
DB_BACKUP_INTERVAL_HOURS = int(os.environ.get("DB_BACKUP_INTERVAL_HOURS", "6"))  # Backup every N hours
DB_BACKUP_RETENTION_DAYS = int(os.environ.get("DB_BACKUP_RETENTION_DAYS", "7"))  # Keep backups for N days
DB_BACKUP_PATH = os.environ.get("DB_BACKUP_PATH", "./backups")  # Backup directory path

# Webhook Security Configuration
# Disabled by default for pure API/webhook bots (no browser UI)
# Enable when adding web-based admin dashboard or public pages
WEBHOOK_SECURITY_HEADERS_ENABLED = os.environ.get("WEBHOOK_SECURITY_HEADERS_ENABLED", "false") == "true"  # Enable security headers
WEBHOOK_CSP_ENABLED = os.environ.get("WEBHOOK_CSP_ENABLED", "false") == "true"  # Enable Content Security Policy
WEBHOOK_HSTS_ENABLED = os.environ.get("WEBHOOK_HSTS_ENABLED", "false") == "true"  # Enable HSTS (only for HTTPS)
WEBHOOK_CORS_ALLOWED_ORIGINS = os.environ.get("WEBHOOK_CORS_ALLOWED_ORIGINS", "").split(",") if os.environ.get("WEBHOOK_CORS_ALLOWED_ORIGINS") else []  # CORS allowed origins
