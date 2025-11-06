"""
Centralized Logging Configuration

Provides secure, production-ready logging with:
- Configurable log levels
- Automatic log rotation
- Secret masking to prevent credential leaks
- Structured output for forensic analysis
"""

import logging
import logging.handlers
import re
from pathlib import Path
from typing import Pattern

import config


class SecretMaskingFilter(logging.Filter):
    """
    Logging filter that masks sensitive data in log records.

    Prevents credential leaks by replacing sensitive values with [REDACTED].

    Masks:
    - API keys and secrets
    - Tokens and passwords
    - Private item data
    - Payment addresses
    - Transaction hashes
    - Shipping addresses
    - User personal information
    """

    # Patterns for secret masking
    PATTERNS: list[tuple[Pattern, str]] = [
        # API Keys (various formats)
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_\-]{20,})(["\']?)', re.IGNORECASE), r'\1[REDACTED_API_KEY]\3'),
        (re.compile(r'(api[_-]?secret["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_\-]{20,})(["\']?)', re.IGNORECASE), r'\1[REDACTED_API_SECRET]\3'),

        # Tokens
        (re.compile(r'(token["\']?\s*[:=]\s*["\']?)([A-Za-z0-9_\-:]{20,})(["\']?)', re.IGNORECASE), r'\1[REDACTED_TOKEN]\3'),
        (re.compile(r'(Bearer\s+)([A-Za-z0-9_\-\.]+)', re.IGNORECASE), r'\1[REDACTED_BEARER_TOKEN]'),

        # Passwords
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']+)(["\']?)', re.IGNORECASE), r'\1[REDACTED_PASSWORD]\3'),
        (re.compile(r'(pass["\']?\s*[:=]\s*["\']?)([^\s"\']{6,})(["\']?)', re.IGNORECASE), r'\1[REDACTED_PASS]\3'),

        # Crypto addresses (BTC, ETH, LTC, SOL, BNB)
        (re.compile(r'\b(bc1|ltc1|0x|[1-9A-HJ-NP-Za-km-z])[a-zA-HJ-NP-Z0-9]{25,}', re.IGNORECASE), '[REDACTED_CRYPTO_ADDRESS]'),

        # Transaction hashes (64 hex chars)
        (re.compile(r'\b([a-fA-F0-9]{64})\b'), '[REDACTED_TX_HASH]'),

        # Private data fields (item content)
        (re.compile(r'(private[_-]?data["\']?\s*[:=]\s*["\']?)([^\'"]+)(["\']?)', re.IGNORECASE), r'\1[REDACTED_PRIVATE_DATA]\3'),

        # Email addresses (PII)
        (re.compile(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'), '[REDACTED_EMAIL]'),

        # Phone numbers (various formats)
        (re.compile(r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[REDACTED_PHONE]'),

        # Shipping addresses (street + number patterns)
        (re.compile(r'(address["\']?\s*[:=]\s*["\']?)([^"\']{10,})(["\']?)', re.IGNORECASE), r'\1[REDACTED_ADDRESS]\3'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record to mask sensitive data.

        Args:
            record: LogRecord to filter

        Returns:
            True (always - we modify but don't block records)
        """
        # Mask secrets in the message
        if record.msg:
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, str(record.msg))

        # Mask secrets in arguments
        if record.args:
            masked_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in self.PATTERNS:
                        arg = pattern.sub(replacement, arg)
                masked_args.append(arg)
            record.args = tuple(masked_args)

        return True


def setup_logging():
    """
    Initialize centralized logging configuration.

    Call this function once at application startup (in run.py or main.py).

    Configuration:
    - Log level from config.LOG_LEVEL (DEBUG, INFO, WARNING, ERROR)
    - Automatic rotation every midnight
    - Keeps logs for config.LOG_ROTATION_DAYS days
    - Masks secrets if config.LOG_MASK_SECRETS is True
    - Writes to logs/bot.log
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Get log level from config (default to INFO)
    log_level_str = getattr(config, "LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Get retention days (uses environment-specific defaults)
    retention_days = getattr(config, "LOG_RETENTION_DAYS", 7)

    # Check if secret masking is enabled (default to True for security)
    mask_secrets = getattr(config, "LOG_MASK_SECRETS", True)

    # Create formatter with detailed information
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create file handler with rotation
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_dir / "bot.log",
        when="midnight",          # Rotate at midnight
        interval=1,               # Every 1 day
        backupCount=retention_days,  # Keep N days of logs
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Add secret masking filter if enabled
    if mask_secrets:
        secret_filter = SecretMaskingFilter()
        file_handler.addFilter(secret_filter)

    # Create console handler for immediate feedback
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Add secret masking to console too
    if mask_secrets:
        console_handler.addFilter(SecretMaskingFilter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add our handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Log initialization message
    logging.info("=" * 80)
    logging.info(f"Logging initialized: Level={log_level_str}, Retention={retention_days} days, Masking={'ENABLED' if mask_secrets else 'DISABLED'}")
    logging.info("=" * 80)


if __name__ == "__main__":
    # Test the logging configuration
    setup_logging()

    # Test secret masking
    logging.info("Testing secret masking:")
    logging.info("API Key: api_key=abc123def456ghi789jkl012mno345pqr678")
    logging.info("Token: TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
    logging.info("Password: password=SuperSecret123!")
    logging.info("BTC Address: bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")
    logging.info("Email: user@example.com")
    logging.info("Normal message: User 12345 created order #67890")
    logging.info("Test complete - check logs/bot.log")
