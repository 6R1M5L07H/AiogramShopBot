import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from repositories.price_tier import PriceTierRepository
from repositories.item import ItemRepository
from models.price_tier import TierPricingResultDTO, TierBreakdownItemDTO
from models.item import ItemDTO
from exceptions.item import ItemNotFoundException


class PricingService:
    """Service for tiered pricing calculations."""

    @staticmethod
    async def calculate_optimal_price(
        subcategory_id: int,
        quantity: int,
        session: Session | AsyncSession
    ) -> TierPricingResultDTO:
        """
        Calculate price using classic tiered pricing.

        Classic tiered pricing means all items receive the lowest unit price from the
        highest tier reached by the quantity. This is standard e-commerce behavior.

        Algorithm:
        1. Sort tiers by min_quantity ascending
        2. Find the highest tier where min_quantity <= quantity
        3. Apply that tier's unit_price to ALL items

        Example with 24 items and tiers [1→€11, 5→€10, 16→€9, 26→€8]:
            - Quantity 24 reaches tier "16→€9" (but not tier "26→€8")
            - All 24 items: 24 × €9 = €216
            - Simple and transparent for customers

        Benefits over incremental pricing:
        - Easier to understand for customers
        - Standard e-commerce behavior
        - Stronger incentive to reach next tier (clear jumps)
        - Simpler invoice display

        Args:
            subcategory_id: ID of the subcategory
            quantity: Number of items to purchase
            session: Database session

        Returns:
            TierPricingResultDTO with total, average (same as unit), and single breakdown item

        Raises:
            ItemNotFoundException: If no items exist in subcategory
        """
        # Get price tiers by subcategory (all items in same subcategory share tiers)
        tiers = await PriceTierRepository.get_by_subcategory(subcategory_id, session)

        # If no tiers, fallback to flat price from any item in subcategory
        if not tiers:
            # Get any item for flat price lookup (using direct query)
            from models.item import Item
            from sqlalchemy import select
            from db import session_execute

            stmt = (
                select(Item)
                .where(Item.subcategory_id == subcategory_id)
                .where(Item.is_sold == False)
                .limit(1)
            )
            result = await session_execute(stmt, session)
            item = result.scalar()

            if not item:
                raise ItemNotFoundException(subcategory_id=subcategory_id)

            sample_item = ItemDTO.model_validate(item, from_attributes=True)

            # Use flat pricing (no quantity discount)
            logging.warning(
                f"No price tiers for subcategory {subcategory_id}, using flat price"
            )
            return TierPricingResultDTO(
                total=round(sample_item.price * quantity, 2),
                average_unit_price=round(sample_item.price, 2),
                breakdown=[TierBreakdownItemDTO(
                    quantity=quantity,
                    unit_price=round(sample_item.price, 2),
                    total=round(sample_item.price * quantity, 2)
                )]
            )

        # Classic Tiered Pricing Algorithm
        sorted_tiers = sorted(tiers, key=lambda t: t.min_quantity)

        # Find the highest tier that applies to this quantity
        applicable_tier = sorted_tiers[0]  # Default to first tier
        for tier in sorted_tiers:
            if tier.min_quantity <= quantity:
                applicable_tier = tier
            else:
                # Tiers are sorted ascending, so we can stop here
                break

        # Apply the tier's unit price to ALL items
        unit_price = round(applicable_tier.unit_price, 2)
        total = round(unit_price * quantity, 2)

        return TierPricingResultDTO(
            total=total,
            average_unit_price=unit_price,
            breakdown=[TierBreakdownItemDTO(
                quantity=quantity,
                unit_price=unit_price,
                total=total
            )]
        )

    @staticmethod
    def format_tier_breakdown(pricing_result: TierPricingResultDTO) -> str:
        """
        Format tier breakdown for display in messages.

        With classic tiered pricing, the breakdown always contains exactly one item
        (all items at the same unit price), so we always show the simple format.

        Example output:
            ```
            24 × 9,00 € = 216,00 €
            ```

        Args:
            pricing_result: Result from calculate_optimal_price()

        Returns:
            Formatted string with quantity × unit_price = total
        """
        # Classic tiered pricing always has exactly 1 breakdown item
        item = pricing_result.breakdown[0]
        return f"{item.quantity} × {item.unit_price:.2f} € = {item.total:.2f} €"

    @staticmethod
    async def format_available_tiers(
        subcategory_id: int,
        session: Session | AsyncSession,
        unit: str = "pcs."
    ) -> str | None:
        """
        Format available tiers as a price list for display.

        Example output:
            ```
            📊 Staffelpreise:
               1-4 l:   11,00 €
              5-24 l:   10,00 €
             25-49 l:    9,00 €
                50+ l:    7,50 €
            ```

        Args:
            subcategory_id: Subcategory ID
            session: Database session
            unit: Item unit (e.g., "pcs.", "kg", "l")

        Returns:
            Formatted string with available tiers, or None if no tiers exist
        """
        # Get tiers for this subcategory
        tiers = await PriceTierRepository.get_by_subcategory(subcategory_id, session)

        # DEBUG: Log tier count
        logging.debug(f"format_available_tiers: subcategory_id={subcategory_id}, found {len(tiers)} tiers")
        for tier in tiers:
            logging.debug(f"  - {tier.min_quantity} Stk. @ {tier.unit_price} EUR")

        if not tiers:
            return None

        # Deduplicate by min_quantity (keep first occurrence)
        # This handles cases where multiple items have identical tier configs
        seen_quantities = set()
        unique_tiers = []
        for tier in sorted(tiers, key=lambda t: t.min_quantity):
            if tier.min_quantity not in seen_quantities:
                seen_quantities.add(tier.min_quantity)
                unique_tiers.append(tier)

        sorted_tiers = unique_tiers

        lines = ["<b>📊 Staffelpreise:</b>"]

        for i, tier in enumerate(sorted_tiers):
            # Determine range
            if i < len(sorted_tiers) - 1:
                # Has next tier - show range
                next_qty = sorted_tiers[i + 1].min_quantity
                range_str = f"{tier.min_quantity}-{next_qty - 1} {unit}"
            else:
                # Last tier - show "X+"
                range_str = f"{tier.min_quantity}+ {unit}"

            price_str = f"{tier.unit_price:>6.2f}"
            lines.append(f"  {range_str:>12}: {price_str} €")

        return "\n".join(lines)