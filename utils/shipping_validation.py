"""
Shipping Tiers Validation Utility

Validates shipping tier configurations for:
- Reference integrity (shipping_type exists in shipping_types/{country}.json)
- Coverage completeness (quantity ranges cover 1 to ∞)
- Logical consistency (no gaps, no overlaps)
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def validate_shipping_type_reference(shipping_type: str, shipping_types: dict) -> bool:
    """
    Validate that a shipping type key exists in loaded shipping types configuration.

    Args:
        shipping_type: Key to validate (e.g., "maxibrief")
        shipping_types: Loaded shipping types dict from shipping_types_loader

    Returns:
        bool: True if type exists, False otherwise

    Example:
        >>> from bot import get_shipping_types
        >>> shipping_types = get_shipping_types()
        >>> validate_shipping_type_reference("maxibrief", shipping_types)
        True
        >>> validate_shipping_type_reference("invalid", shipping_types)
        False
    """
    is_valid = shipping_type in shipping_types

    if not is_valid:
        logger.warning(f"Invalid shipping_type reference: '{shipping_type}' not found in shipping_types configuration")

    return is_valid


def validate_tier_coverage(tiers: List[Dict[str, Any]]) -> tuple[bool, str | None]:
    """
    Validate that shipping tiers provide complete quantity coverage from 1 to ∞.

    Checks for:
    - At least one tier exists
    - First tier starts at quantity 1
    - No gaps in quantity ranges
    - No overlaps in quantity ranges
    - At least one tier with max_quantity=None (unlimited)

    Args:
        tiers: List of tier dicts with min_quantity, max_quantity, shipping_type

    Returns:
        tuple: (is_valid, error_message)
            - (True, None) if valid
            - (False, "error description") if invalid

    Example:
        >>> tiers = [
        ...     {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
        ...     {"min_quantity": 6, "max_quantity": None, "shipping_type": "paeckchen"}
        ... ]
        >>> validate_tier_coverage(tiers)
        (True, None)

        >>> bad_tiers = [
        ...     {"min_quantity": 5, "max_quantity": 10, "shipping_type": "maxibrief"}
        ... ]
        >>> validate_tier_coverage(bad_tiers)
        (False, "First tier must start at quantity 1, got 5")
    """
    if not tiers or len(tiers) == 0:
        return False, "At least one shipping tier is required"

    # Sort by min_quantity
    sorted_tiers = sorted(tiers, key=lambda t: t["min_quantity"])

    # Check: First tier starts at 1
    if sorted_tiers[0]["min_quantity"] != 1:
        return False, f"First tier must start at quantity 1, got {sorted_tiers[0]['min_quantity']}"

    # Check: Last tier has max_quantity=None (unlimited)
    has_unlimited_tier = any(t["max_quantity"] is None for t in sorted_tiers)
    if not has_unlimited_tier:
        return False, "At least one tier must have max_quantity=None (unlimited)"

    # Check for gaps and overlaps
    for i in range(len(sorted_tiers) - 1):
        current_tier = sorted_tiers[i]
        next_tier = sorted_tiers[i + 1]

        current_max = current_tier["max_quantity"]
        next_min = next_tier["min_quantity"]

        # Current tier should not be unlimited if there's a next tier
        if current_max is None:
            return False, f"Only the last tier can have max_quantity=None (found at tier {i+1})"

        # Check for gap: next_min should be current_max + 1
        if next_min != current_max + 1:
            if next_min > current_max + 1:
                return False, f"Gap detected: tier ends at {current_max}, next starts at {next_min}"
            else:
                return False, f"Overlap detected: tier ends at {current_max}, next starts at {next_min}"

    return True, None


def validate_tier_logic(tier: Dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate a single tier's internal logic.

    Args:
        tier: Single tier dict with min_quantity, max_quantity, shipping_type

    Returns:
        tuple: (is_valid, error_message)

    Example:
        >>> tier = {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"}
        >>> validate_tier_logic(tier)
        (True, None)

        >>> bad_tier = {"min_quantity": 10, "max_quantity": 5, "shipping_type": "maxibrief"}
        >>> validate_tier_logic(bad_tier)
        (False, "max_quantity (5) must be >= min_quantity (10)")
    """
    min_qty = tier.get("min_quantity")
    max_qty = tier.get("max_quantity")
    shipping_type = tier.get("shipping_type")

    # Required fields
    if min_qty is None:
        return False, "min_quantity is required"
    if shipping_type is None or shipping_type == "":
        return False, "shipping_type is required"

    # min_quantity must be positive
    if min_qty <= 0:
        return False, f"min_quantity must be > 0, got {min_qty}"

    # max_quantity validation (if not None)
    if max_qty is not None:
        if max_qty < min_qty:
            return False, f"max_quantity ({max_qty}) must be >= min_quantity ({min_qty})"

    return True, None


def get_shipping_type_for_quantity(
    tiers: List[Dict[str, Any]],
    quantity: int
) -> str | None:
    """
    Determine the appropriate shipping type for a given quantity.

    Args:
        tiers: List of shipping tier dicts (sorted by min_quantity)
        quantity: Quantity to check

    Returns:
        str: shipping_type key, or None if no matching tier

    Example:
        >>> tiers = [
        ...     {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
        ...     {"min_quantity": 6, "max_quantity": 10, "shipping_type": "paeckchen"},
        ...     {"min_quantity": 11, "max_quantity": None, "shipping_type": "paket_2kg"}
        ... ]
        >>> get_shipping_type_for_quantity(tiers, 3)
        'maxibrief'
        >>> get_shipping_type_for_quantity(tiers, 8)
        'paeckchen'
        >>> get_shipping_type_for_quantity(tiers, 100)
        'paket_2kg'
    """
    if quantity <= 0:
        logger.warning(f"Invalid quantity: {quantity} (must be > 0)")
        return None

    # Sort by min_quantity (just in case)
    sorted_tiers = sorted(tiers, key=lambda t: t["min_quantity"])

    for tier in sorted_tiers:
        min_qty = tier["min_quantity"]
        max_qty = tier["max_quantity"]

        # Check if quantity falls in this tier's range
        if quantity >= min_qty:
            if max_qty is None or quantity <= max_qty:
                return tier["shipping_type"]

    logger.warning(f"No shipping tier found for quantity {quantity}")
    return None