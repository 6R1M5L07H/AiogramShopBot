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
        secret: The ENCRYPTION_SECRET value from config

    Raises:
        ConfigValidationError: If secret is missing or too weak
    """
    if not secret:
        raise ConfigValidationError(
            "ENCRYPTION_SECRET is required for shipping address encryption!\n"
            "Generate a secure secret with: openssl rand -hex 32\n"
            "Add to .env: ENCRYPTION_SECRET=<your-generated-secret>"
        )

    if len(secret) < 32:
        raise ConfigValidationError(
            f"ENCRYPTION_SECRET must be at least 32 characters long (currently: {len(secret)})\n"
            "Generate a secure secret with: openssl rand -hex 32"
        )


def validate_webhook_config(
    deployment_mode: str,
    webhook_secret: Optional[str],
    webhook_path: Optional[str]
) -> None:
    """
    Validate webhook configuration for webhook deployment mode.

    Args:
        deployment_mode: DEPLOYMENT_MODE value (WEBHOOK or POLLING)
        webhook_secret: WEBHOOK_SECRET_TOKEN value
        webhook_path: WEBHOOK_PATH value

    Raises:
        ConfigValidationError: If webhook mode is configured incorrectly
    """
    if deployment_mode.upper() != "WEBHOOK":
        # Polling mode - no webhook validation needed
        return

    if not webhook_secret:
        raise ConfigValidationError(
            "WEBHOOK_SECRET_TOKEN is required when DEPLOYMENT_MODE=WEBHOOK!\n"
            "Generate a secure token with: openssl rand -hex 32\n"
            "Add to .env: WEBHOOK_SECRET_TOKEN=<your-generated-token>"
        )

    if not webhook_path:
        raise ConfigValidationError(
            "WEBHOOK_PATH is required when DEPLOYMENT_MODE=WEBHOOK!\n"
            "Add to .env: WEBHOOK_PATH=/webhook/your-secret-path"
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

    # Validate webhook config if in webhook mode
    deployment_mode = getattr(config_module, 'DEPLOYMENT_MODE', 'POLLING')
    webhook_secret = getattr(config_module, 'WEBHOOK_SECRET_TOKEN', None)
    webhook_path = getattr(config_module, 'WEBHOOK_PATH', None)
    validate_webhook_config(deployment_mode, webhook_secret, webhook_path)

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
