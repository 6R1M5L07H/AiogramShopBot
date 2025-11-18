"""
Configuration Validation Module

Validates critical configuration values at startup to fail-fast
with clear error messages instead of runtime failures.
"""

import sys
from typing import Optional


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


def validate_shipping_secret(secret: str) -> None:
    """
    Validate shipping address encryption secret.

    Args:
        secret: The SHIPPING_ADDRESS_SECRET value from config

    Raises:
        ConfigValidationError: If secret is missing or too weak
    """
    if not secret:
        raise ConfigValidationError(
            "SHIPPING_ADDRESS_SECRET is required for shipping address encryption!\n"
            "Generate a secure secret with: openssl rand -hex 32\n"
            "Add to .env: SHIPPING_ADDRESS_SECRET=<your-generated-secret>"
        )

    if len(secret) < 32:
        raise ConfigValidationError(
            f"SHIPPING_ADDRESS_SECRET must be at least 32 characters long (currently: {len(secret)})\n"
            "Generate a secure secret with: openssl rand -hex 32"
        )


def validate_webhook_secret(webhook_secret: Optional[str]) -> None:
    """
    Validate Telegram webhook secret token.

    Args:
        webhook_secret: WEBHOOK_SECRET_TOKEN value

    Raises:
        ConfigValidationError: If secret is missing, empty, or too weak
    """
    if not webhook_secret or len(webhook_secret.strip()) == 0:
        raise ConfigValidationError(
            "WEBHOOK_SECRET_TOKEN is required and must not be empty!\n"
            "Generate a secure token with: openssl rand -hex 32\n"
            "Add to .env: WEBHOOK_SECRET_TOKEN=<your-generated-token>"
        )

    if len(webhook_secret) < 32:
        raise ConfigValidationError(
            f"WEBHOOK_SECRET_TOKEN is too weak (length: {len(webhook_secret)}, minimum: 32)!\n"
            "Generate a secure token with: openssl rand -hex 32\n"
            "This prevents brute-force attacks on webhook authentication."
        )


def validate_payment_secret(payment_secret: Optional[str]) -> None:
    """
    Validate payment provider API secret.

    Args:
        payment_secret: KRYPTO_EXPRESS_API_SECRET value

    Raises:
        ConfigValidationError: If secret is missing, empty, or too weak
    """
    if not payment_secret or len(payment_secret.strip()) == 0:
        raise ConfigValidationError(
            "KRYPTO_EXPRESS_API_SECRET is required and must not be empty!\n"
            "This secret is used to verify payment webhook signatures.\n"
            "Get your API secret from your payment provider dashboard.\n"
            "Add to .env: KRYPTO_EXPRESS_API_SECRET=<your-api-secret>"
        )

    if len(payment_secret) < 32:
        raise ConfigValidationError(
            f"KRYPTO_EXPRESS_API_SECRET is too weak (length: {len(payment_secret)}, minimum: 32)!\n"
            "Payment webhook signatures require strong secrets to prevent HMAC bypass.\n"
            "Contact your payment provider if the provided secret is too short."
        )


def validate_required_config(value: Optional[str], name: str, example: str = "") -> None:
    """
    Validate that a required config value is set.

    Args:
        value: The config value to check
        name: Name of the config variable
        example: Optional example value to show in error message

    Raises:
        ConfigValidationError: If value is missing
    """
    if not value:
        error_msg = f"{name} is required but not set!"
        if example:
            error_msg += f"\nAdd to .env: {name}={example}"
        raise ConfigValidationError(error_msg)


def validate_startup_config(config_module) -> None:
    """
    Validate all critical configuration at startup.

    Args:
        config_module: The config module to validate

    Raises:
        ConfigValidationError: If any validation fails
    """
    # Validate shipping secret
    validate_shipping_secret(config_module.SHIPPING_ADDRESS_SECRET)

    # Validate webhook secrets (always required - system runs on webhooks)
    webhook_secret = getattr(config_module, 'WEBHOOK_SECRET_TOKEN', None)
    validate_webhook_secret(webhook_secret)

    payment_secret = getattr(config_module, 'KRYPTO_EXPRESS_API_SECRET', None)
    validate_payment_secret(payment_secret)

    # Validate bot token
    token = getattr(config_module, 'TOKEN', None)
    validate_required_config(token, 'TOKEN', '<your-telegram-bot-token>')


def validate_or_exit(config_module) -> None:
    """
    Validate configuration and exit with error code 1 if validation fails.

    This is the main entry point for startup validation.

    Args:
        config_module: The config module to validate
    """
    try:
        validate_startup_config(config_module)
    except ConfigValidationError as e:
        print(f"\n ERROR: Configuration Validation Failed\n", file=sys.stderr)
        print(str(e), file=sys.stderr)
        print("\nBot startup aborted. Please fix configuration and try again.\n", file=sys.stderr)
        sys.exit(1)
