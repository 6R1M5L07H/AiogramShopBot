"""
Shipping Upsell Service

Handles logic for shipping upgrade options based on shipping_types configuration.
"""

import logging
from typing import Dict, Any, Optional

from bot import get_shipping_types

logger = logging.getLogger(__name__)


class ShippingUpsellService:
    """Service for shipping upsell logic."""

    @staticmethod
    def get_upgrade_for_shipping_type(shipping_type_key: str) -> Optional[Dict[str, Any]]:
        """
        Get upgrade option for a given shipping type.

        Args:
            shipping_type_key: Key of the base shipping type (e.g., "paeckchen")

        Returns:
            dict: Upgrade details with keys: target, name, description, delta_cost
            None: If no upgrade available or shipping type not found

        Example:
            >>> upgrade = ShippingUpsellService.get_upgrade_for_shipping_type("paeckchen")
            >>> upgrade["target"]  # "paket_2kg"
            >>> upgrade["delta_cost"]  # 1.50
            >>> upgrade["name"]  # "Versichert versenden" (or target name if not set)
        """
        shipping_types = get_shipping_types()

        if not shipping_types:
            logger.warning("[ShippingUpsell] No shipping_types configuration loaded")
            return None

        if shipping_type_key not in shipping_types:
            logger.warning(f"[ShippingUpsell] Shipping type '{shipping_type_key}' not found in config")
            return None

        base_shipping_type = shipping_types[shipping_type_key]
        upgrade_ref = base_shipping_type.get("upgrade")

        if upgrade_ref is None:
            logger.info(f"[ShippingUpsell] No upgrade available for '{shipping_type_key}'")
            return None

        # Validate upgrade structure
        if not isinstance(upgrade_ref, dict) or not upgrade_ref:
            logger.warning(f"[ShippingUpsell] Invalid upgrade structure for '{shipping_type_key}'")
            return None

        # Check required field
        if "target" not in upgrade_ref:
            logger.warning(f"[ShippingUpsell] Malformed upgrade for '{shipping_type_key}', missing 'target' field")
            return None

        target_key = upgrade_ref["target"]

        # Load target shipping type
        if target_key not in shipping_types:
            logger.error(f"[ShippingUpsell] Target shipping type '{target_key}' not found in config")
            return None

        target_shipping_type = shipping_types[target_key]

        # Calculate delta_cost from target charged cost
        base_charged_cost = base_shipping_type.get("charged_cost", 0.0)
        target_charged_cost = target_shipping_type.get("charged_cost", 0.0)
        delta_cost = round(target_charged_cost - base_charged_cost, 2)

        # Use upsell_button_text if provided, otherwise fallback to target name
        button_text = upgrade_ref.get("upsell_button_text")
        if not button_text:
            button_text = target_shipping_type.get("name", target_key)
            logger.debug(f"[ShippingUpsell] No upsell_button_text, using target name: {button_text}")

        # Use target description
        description = target_shipping_type.get("description", "")

        upgrade_details = {
            "target": target_key,
            "name": button_text,
            "description": description,
            "delta_cost": delta_cost
        }

        logger.info(f"[ShippingUpsell] Found upgrade for '{shipping_type_key}': {target_key} (+{delta_cost} EUR)")
        return upgrade_details

    @staticmethod
    def calculate_total_cost_with_upgrade(charged_cost: float, upgrade_delta_cost: float) -> float:
        """
        Calculate total shipping cost including upgrade.

        Args:
            charged_cost: Base charged cost (what customer currently pays)
            upgrade_delta_cost: Additional cost for upgrade

        Returns:
            float: Total shipping cost after upgrade

        Example:
            >>> ShippingUpsellService.calculate_total_cost_with_upgrade(0.00, 1.50)
            1.50
            >>> ShippingUpsellService.calculate_total_cost_with_upgrade(2.00, 1.50)
            3.50
        """
        total = charged_cost + upgrade_delta_cost
        logger.info(f"[ShippingUpsell] Total cost: {charged_cost} + {upgrade_delta_cost} = {total}")
        return round(total, 2)

    @staticmethod
    def get_shipping_type_details(shipping_type_key: str) -> Optional[Dict[str, Any]]:
        """
        Get full details of a shipping type.

        Args:
            shipping_type_key: Key of the shipping type

        Returns:
            dict: Shipping type details (name, charged_cost, real_cost, description, etc.)
            None: If shipping type not found

        Example:
            >>> details = ShippingUpsellService.get_shipping_type_details("paeckchen")
            >>> details["name"]  # "Päckchen"
            >>> details["charged_cost"]  # 0.00
            >>> details["real_cost"]  # 3.99
        """
        shipping_types = get_shipping_types()

        if not shipping_types:
            logger.warning("[ShippingUpsell] No shipping_types configuration loaded")
            return None

        if shipping_type_key not in shipping_types:
            logger.warning(f"[ShippingUpsell] Shipping type '{shipping_type_key}' not found in config")
            return None

        return shipping_types[shipping_type_key]
