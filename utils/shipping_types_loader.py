"""
Shipping Types Loader

Loads shipping type definitions from country-specific JSON files.
Similar to localization (l10n), supports different shipping systems per country.

Usage:
    from utils.shipping_types_loader import load_shipping_types

    shipping_types = load_shipping_types("de")  # Load German shipping types
"""

import json
import os
import logging
from pathlib import Path


def load_shipping_types(country_code: str = "de") -> dict:
    """
    Load shipping types from country-specific JSON file.

    Args:
        country_code: ISO country code (e.g., "de", "pl", "us")

    Returns:
        dict: Shipping types configuration

    Raises:
        FileNotFoundError: If shipping types file doesn't exist
        json.JSONDecodeError: If JSON is malformed

    Example:
        >>> types = load_shipping_types("de")
        >>> maxibrief = types["maxibrief"]
        >>> print(maxibrief["base_cost"])
        0.0
    """
    # Build path relative to project root
    project_root = Path(__file__).parent.parent
    shipping_types_path = project_root / "shipping_types" / f"{country_code}.json"

    if not shipping_types_path.exists():
        raise FileNotFoundError(
            f"Shipping types file not found: {shipping_types_path}\n"
            f"Please create shipping_types/{country_code}.json"
        )

    try:
        with open(shipping_types_path, "r", encoding="utf-8") as f:
            shipping_types = json.load(f)

        logging.info(f"✅ Loaded {len(shipping_types)} shipping types from {country_code}.json")
        return shipping_types

    except json.JSONDecodeError as e:
        logging.error(f"❌ Failed to parse {shipping_types_path}: {e}")
        raise


def get_shipping_type(shipping_types: dict, type_key: str) -> dict | None:
    """
    Get a specific shipping type by key.

    Args:
        shipping_types: Shipping types dict from load_shipping_types()
        type_key: Key of the shipping type (e.g., "maxibrief", "paeckchen")

    Returns:
        dict: Shipping type configuration or None if not found

    Example:
        >>> types = load_shipping_types("de")
        >>> maxibrief = get_shipping_type(types, "maxibrief")
        >>> print(maxibrief["allows_packstation"])
        False
    """
    return shipping_types.get(type_key)


def get_upgrade_for_type(shipping_types: dict, type_key: str) -> dict | None:
    """
    Get the upgrade option for a shipping type.

    Args:
        shipping_types: Shipping types dict from load_shipping_types()
        type_key: Key of the base shipping type

    Returns:
        dict: Upgrade configuration or None if no upgrade available

    Example:
        >>> types = load_shipping_types("de")
        >>> upgrade = get_upgrade_for_type(types, "maxibrief")
        >>> print(upgrade["delta_cost"])
        2.35
    """
    shipping_type = shipping_types.get(type_key)
    if not shipping_type:
        return None

    return shipping_type.get("upgrade")


def validate_shipping_type_reference(shipping_types: dict, type_key: str) -> bool:
    """
    Validate that a shipping type key exists.

    Used during item import to verify shipping_tiers reference valid types.

    Args:
        shipping_types: Shipping types dict from load_shipping_types()
        type_key: Key to validate

    Returns:
        bool: True if type exists, False otherwise

    Example:
        >>> types = load_shipping_types("de")
        >>> validate_shipping_type_reference(types, "maxibrief")
        True
        >>> validate_shipping_type_reference(types, "invalid")
        False
    """
    return type_key in shipping_types