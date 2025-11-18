"""
Telegram WebApp initData validation utility.

Validates HMAC-SHA256 signature from Telegram WebApp to ensure requests
are authentic and haven't been tampered with.

Security features:
- HMAC-SHA256 signature verification
- Replay attack protection (timestamp validation)
- User ID extraction and verification
"""

import hmac
import hashlib
import time
from urllib.parse import parse_qsl
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class WebAppValidationError(Exception):
    """Raised when WebApp initData validation fails."""
    pass


def validate_telegram_webapp_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 3600
) -> Dict[str, str]:
    """
    Validates Telegram WebApp initData HMAC signature.

    Args:
        init_data: Raw initData string from Telegram.WebApp.initData
        bot_token: Bot token for HMAC validation
        max_age_seconds: Maximum age of initData (default: 1 hour)

    Returns:
        Dict containing validated data (user, auth_date, query_id, etc.)

    Raises:
        WebAppValidationError: If validation fails

    Example:
        >>> data = validate_telegram_webapp_init_data(
        ...     init_data=request.headers['X-Telegram-Init-Data'],
        ...     bot_token=config.BOT_TOKEN
        ... )
        >>> user_id = json.loads(data['user'])['id']
    """
    if not init_data:
        raise WebAppValidationError("No initData provided")

    if not bot_token:
        raise WebAppValidationError("Bot token not configured")

    # Parse initData into key-value pairs
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception as e:
        raise WebAppValidationError(f"Failed to parse initData: {e}")

    # Extract hash (this is the signature we need to verify)
    received_hash = parsed.pop('hash', None)
    if not received_hash:
        raise WebAppValidationError("No hash in initData")

    # Check timestamp to prevent replay attacks
    try:
        auth_date = int(parsed.get('auth_date', 0))
    except (ValueError, TypeError):
        raise WebAppValidationError("Invalid auth_date")

    age_seconds = time.time() - auth_date
    if age_seconds > max_age_seconds:
        raise WebAppValidationError(
            f"InitData too old ({int(age_seconds)}s > {max_age_seconds}s max)"
        )

    if age_seconds < -60:  # Allow 60s clock skew
        raise WebAppValidationError("InitData timestamp is in the future")

    # Build data-check-string (alphabetically sorted key=value pairs)
    data_check_string = '\n'.join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    # Calculate secret key from bot token
    # Secret = HMAC_SHA256(bot_token, "WebAppData")
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()

    # Calculate expected hash
    # Hash = HMAC_SHA256(data_check_string, secret_key)
    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_hash, received_hash):
        logger.warning(
            f"WebApp signature mismatch | "
            f"Expected: {expected_hash[:16]}... | "
            f"Received: {received_hash[:16]}..."
        )
        raise WebAppValidationError("Invalid signature")

    logger.info(f"✅ WebApp initData validated successfully (user_id from parsed data)")
    return parsed


def extract_user_id(validated_data: Dict[str, str]) -> int:
    """
    Extracts user ID from validated initData.

    Args:
        validated_data: Dict returned by validate_telegram_webapp_init_data()

    Returns:
        Telegram user ID

    Raises:
        WebAppValidationError: If user data is invalid
    """
    import json

    user_json = validated_data.get('user')
    if not user_json:
        raise WebAppValidationError("No user data in initData")

    try:
        user_data = json.loads(user_json)
        user_id = user_data.get('id')
        if not user_id:
            raise WebAppValidationError("No user ID in user data")
        return int(user_id)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        raise WebAppValidationError(f"Invalid user data: {e}")