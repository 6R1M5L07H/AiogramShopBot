"""
Cart Shipping Calculation Service

Handles shipping cost calculation for cart items based on quantity-based shipping tiers.
Uses shipping_tiers (subcategory-level) and shipping_types (country-specific).
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from bot import get_shipping_types
from enums.bot_entity import BotEntity
from models.cartItem import CartItemDTO
from models.shipping_tier import ShippingSelectionResultDTO
from repositories.item import ItemRepository
from repositories.shipping_tier import ShippingTierRepository
from utils.localizator import Localizator
from utils.shipping_validation import get_shipping_type_for_quantity

logger = logging.getLogger(__name__)


class CartShippingService:
    """Service for calculating shipping costs in cart context."""

    @staticmethod
    async def calculate_shipping_for_cart(
        cart_items: list[CartItemDTO],
        session: AsyncSession | Session
    ) -> dict[int, ShippingSelectionResultDTO]:
        """
        Calculate shipping types for all cart items.

        Groups items by subcategory and determines appropriate shipping type
        based on quantity-based shipping tiers.

        Args:
            cart_items: List of cart items
            session: Database session

        Returns:
            dict: {subcategory_id: ShippingSelectionResultDTO}
                  One shipping selection per subcategory

        Example:
            >>> cart_items = [
            ...     CartItemDTO(subcategory_id=3, quantity=7),  # USB sticks
            ...     CartItemDTO(subcategory_id=3, quantity=2)   # More USB sticks
            ... ]
            >>> result = await CartShippingService.calculate_shipping_for_cart(cart_items, session)
            >>> result[3].shipping_type_key  # "paeckchen" (7+2=9 items)
        """
        # Group items by subcategory and sum quantities (also track category_id)
        subcategory_data = {}  # {subcategory_id: {"quantity": int, "category_id": int}}
        for cart_item in cart_items:
            if cart_item.subcategory_id not in subcategory_data:
                subcategory_data[cart_item.subcategory_id] = {
                    "quantity": 0,
                    "category_id": cart_item.category_id
                }
            subcategory_data[cart_item.subcategory_id]["quantity"] += cart_item.quantity

        logger.info(f"[CartShipping] calculate_shipping_for_cart called with {len(cart_items)} items")
        logger.info(f"[CartShipping] Grouped into {len(subcategory_data)} subcategories: {subcategory_data}")

        # Load shipping types configuration
        shipping_types = get_shipping_types()
        logger.info(f"[CartShipping] Loaded shipping_types config: {list(shipping_types.keys()) if shipping_types else 'None'}")

        # Batch-load shipping tiers for all subcategories
        subcategory_ids = list(subcategory_data.keys())
        shipping_tiers_dict = await ShippingTierRepository.get_by_subcategory_ids(
            subcategory_ids, session
        )
        logger.info(f"[CartShipping] Loaded shipping_tiers for {len(shipping_tiers_dict)} subcategories")
        for subcat_id, tiers in shipping_tiers_dict.items():
            logger.info(f"[CartShipping]   Subcategory {subcat_id}: {len(tiers)} tiers")

        # Calculate shipping for each subcategory
        shipping_results = {}
        for subcategory_id, data in subcategory_data.items():
            tiers_for_subcat = shipping_tiers_dict.get(subcategory_id, [])
            logger.info(f"[CartShipping] Processing subcategory {subcategory_id}: qty={data['quantity']}, tiers={len(tiers_for_subcat)}")

            shipping_result = await CartShippingService._calculate_shipping_for_subcategory(
                category_id=data["category_id"],
                subcategory_id=subcategory_id,
                quantity=data["quantity"],
                shipping_tiers=tiers_for_subcat,
                shipping_types=shipping_types,
                session=session
            )

            if shipping_result:
                logger.info(f"[CartShipping]   Result: {shipping_result.shipping_type_key} @ {shipping_result.base_cost} EUR")
                shipping_results[subcategory_id] = shipping_result
            else:
                logger.info(f"[CartShipping]   Result: None (digital or error)")

        logger.info(f"[CartShipping] Final shipping_results: {len(shipping_results)} subcategories with shipping")
        return shipping_results

    @staticmethod
    async def _calculate_shipping_for_subcategory(
        category_id: int,
        subcategory_id: int,
        quantity: int,
        shipping_tiers: list,
        shipping_types: dict,
        session: AsyncSession | Session
    ) -> ShippingSelectionResultDTO | None:
        """
        Calculate shipping for a specific subcategory based on quantity.

        Args:
            category_id: Category ID
            subcategory_id: Subcategory ID
            quantity: Total quantity of items from this subcategory
            shipping_tiers: Shipping tiers for this subcategory
            shipping_types: Loaded shipping types configuration
            session: Database session

        Returns:
            ShippingSelectionResultDTO or None if no shipping needed (digital items)

        Example:
            >>> result = await _calculate_shipping_for_subcategory(
            ...     category_id=1,
            ...     subcategory_id=3,
            ...     quantity=7,
            ...     shipping_tiers=[...],
            ...     shipping_types={...},
            ...     session=session
            ... )
            >>> result.shipping_type_key  # "paeckchen"
            >>> result.base_cost  # 0.0
        """
        # Check if items are physical (sample check)
        sample_item = await ItemRepository.get_single(category_id, subcategory_id, session)
        logger.info(f"[CartShipping]     Sample item: is_physical={sample_item.is_physical if sample_item else 'N/A'}")

        if not sample_item or not sample_item.is_physical:
            # Digital items - no shipping
            logger.info(f"[CartShipping]     Skipping: digital item or no sample found")
            return None

        # No shipping tiers configured - fallback to legacy flat shipping_cost
        if not shipping_tiers or len(shipping_tiers) == 0:
            logger.warning(
                f"No shipping tiers configured for physical subcategory {subcategory_id}, "
                f"using legacy flat shipping_cost from item"
            )
            # Fallback: Use flat shipping_cost from item (backward compatibility)
            return ShippingSelectionResultDTO(
                shipping_type_key="legacy_flat",
                shipping_type_name=Localizator.get_text(BotEntity.USER, "shipping_legacy_flat"),
                base_cost=sample_item.shipping_cost,
                has_tracking=False,
                allows_packstation=sample_item.allows_packstation,
                upgrade=None
            )

        # Convert tiers to dict format for validation function
        tiers_list = [
            {
                "min_quantity": tier.min_quantity,
                "max_quantity": tier.max_quantity,
                "shipping_type": tier.shipping_type
            }
            for tier in shipping_tiers
        ]
        logger.info(f"[CartShipping]     Converted {len(tiers_list)} tiers: {tiers_list}")

        # Determine shipping type based on quantity
        shipping_type_key = get_shipping_type_for_quantity(tiers_list, quantity)
        logger.info(f"[CartShipping]     Selected shipping_type_key: {shipping_type_key}")

        if not shipping_type_key:
            logger.error(
                f"No shipping type found for subcategory {subcategory_id} "
                f"with quantity {quantity}"
            )
            return None

        # Get shipping type details from configuration
        shipping_type_config = shipping_types.get(shipping_type_key)
        logger.info(f"[CartShipping]     Config for '{shipping_type_key}': {shipping_type_config}")

        if not shipping_type_config:
            logger.error(
                f"Shipping type '{shipping_type_key}' not found in shipping_types configuration"
            )
            return None

        # Build result DTO
        return ShippingSelectionResultDTO(
            shipping_type_key=shipping_type_key,
            shipping_type_name=shipping_type_config["name"],
            base_cost=shipping_type_config["base_cost"],
            has_tracking=shipping_type_config["has_tracking"],
            allows_packstation=shipping_type_config["allows_packstation"],
            upgrade=shipping_type_config.get("upgrade")
        )

    @staticmethod
    async def get_max_shipping_cost(
        cart_items: list[CartItemDTO],
        session: AsyncSession | Session
    ) -> float:
        """
        Get the maximum shipping cost from all cart items.

        This is used for checkout total calculation. We charge the highest
        shipping cost among all items (not sum, as items ship together).

        Args:
            cart_items: List of cart items
            session: Database session

        Returns:
            float: Maximum shipping cost (0.0 if all digital or free shipping)

        Example:
            >>> cart_items = [
            ...     CartItemDTO(subcategory_id=3, quantity=7),   # Paeckchen (free)
            ...     CartItemDTO(subcategory_id=5, quantity=15)   # Paket 2kg (€1.50)
            ... ]
            >>> max_cost = await CartShippingService.get_max_shipping_cost(cart_items, session)
            >>> max_cost  # 1.50
        """
        shipping_results = await CartShippingService.calculate_shipping_for_cart(
            cart_items, session
        )

        if not shipping_results:
            return 0.0

        # Find maximum shipping cost
        max_cost = 0.0
        for shipping_result in shipping_results.values():
            if shipping_result.base_cost > max_cost:
                max_cost = shipping_result.base_cost

        return max_cost

    @staticmethod
    async def get_shipping_summary_text(
        cart_items: list[CartItemDTO],
        session: AsyncSession | Session
    ) -> str:
        """
        Generate human-readable shipping summary for cart.

        Args:
            cart_items: List of cart items
            session: Database session

        Returns:
            str: Formatted shipping summary (empty string if no physical items)

        Example:
            >>> text = await CartShippingService.get_shipping_summary_text(cart_items, session)
            >>> print(text)
            Shipping:
            - USB Sticks (9x): Päckchen (free)
            - Hardware Accessories (15x): Paket 2kg (€1.50)

            Max shipping cost: €1.50
        """
        from repositories.subcategory import SubcategoryRepository

        logger.info(f"[CartShipping] get_shipping_summary_text called with {len(cart_items)} items")

        shipping_results = await CartShippingService.calculate_shipping_for_cart(
            cart_items, session
        )

        logger.info(f"[CartShipping] get_shipping_summary_text: got {len(shipping_results)} shipping_results")

        if not shipping_results:
            logger.info(f"[CartShipping] get_shipping_summary_text: returning empty string (no results)")
            return ""

        # Group items by subcategory for display
        subcategory_quantities = {}
        for cart_item in cart_items:
            if cart_item.subcategory_id not in subcategory_quantities:
                subcategory_quantities[cart_item.subcategory_id] = 0
            subcategory_quantities[cart_item.subcategory_id] += cart_item.quantity

        # Load subcategory names
        subcategory_ids = list(subcategory_quantities.keys())
        subcategories_dict = await SubcategoryRepository.get_by_ids(subcategory_ids, session)

        # Build summary text
        currency_sym = Localizator.get_currency_symbol()
        summary_lines = [Localizator.get_text(BotEntity.USER, "shipping_summary_header") + ":"]
        max_cost = 0.0

        for subcategory_id, quantity in subcategory_quantities.items():
            shipping_result = shipping_results.get(subcategory_id)
            if not shipping_result:
                continue

            subcategory = subcategories_dict.get(subcategory_id)
            if not subcategory:
                continue

            # Format cost text: "free" or "€1.50"
            if shipping_result.base_cost == 0.0:
                cost_text = Localizator.get_text(BotEntity.USER, "shipping_cost_free")
            else:
                cost_text = f"{currency_sym}{shipping_result.base_cost:.2f}"

            summary_lines.append(
                f"- {subcategory.name} ({quantity}x): {shipping_result.shipping_type_name} ({cost_text})"
            )

            if shipping_result.base_cost > max_cost:
                max_cost = shipping_result.base_cost

        if max_cost > 0:
            summary_lines.append("")
            max_label = Localizator.get_text(BotEntity.USER, "shipping_max_cost_label")
            summary_lines.append(f"{max_label}: {currency_sym}{max_cost:.2f}")

        return "\n".join(summary_lines)