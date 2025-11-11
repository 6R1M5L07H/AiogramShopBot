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
        Calculate price using incremental tiered pricing.

        Incremental pricing means each tier applies only to items within its quantity range,
        not to all items retroactively. This is the original design.

        Algorithm:
        1. Sort tiers by min_quantity ascending
        2. For each tier, calculate how many items fall into that tier
        3. Apply tier's unit_price only to items in that tier's range
        4. Sum up all tier costs

        Example with 17 items and tiers [1→€11, 5→€10, 10→€9]:
            - Items 1-4:   4 × €11 = €44  (Tier 1)
            - Items 5-9:   5 × €10 = €50  (Tier 2)
            - Items 10-17: 8 × €9  = €72  (Tier 3)
            - Total: €166, Average: €9.76/item

        Contrast with "classic" staffelpreise (all 17 × €9 = €153):
            Incremental rewards bulk buyers while charging full price for initial items.

        Args:
            subcategory_id: ID of the subcategory
            quantity: Number of items to purchase
            session: Database session

        Returns:
            TierPricingResultDTO with total, average, and breakdown per tier

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

        # Incremental Tiered Pricing Algorithm
        sorted_tiers = sorted(tiers, key=lambda t: t.min_quantity)

        breakdown = []
        total_cost = 0.0
        remaining_qty = quantity
        current_item_index = 1  # Track which item number we're on

        for i, tier in enumerate(sorted_tiers):
            # Determine how many items fall into this tier
            tier_start = tier.min_quantity

            # Find tier end (next tier's start - 1, or infinity for last tier)
            if i < len(sorted_tiers) - 1:
                tier_end = sorted_tiers[i + 1].min_quantity - 1
            else:
                # Last tier - takes all remaining items
                tier_end = None  # Unbounded

            # Calculate items in this tier
            if current_item_index < tier_start:
                # We haven't reached this tier yet, skip to it
                current_item_index = tier_start

            # How many items are priced at this tier?
            if tier_end is None:
                # Last tier - all remaining items
                items_in_tier = quantity - current_item_index + 1
            else:
                # Limited tier - don't exceed tier_end
                items_in_tier = min(quantity - current_item_index + 1, tier_end - current_item_index + 1)

            # Stop if no more items to process
            if items_in_tier <= 0:
                break

            # Calculate cost for this tier
            tier_cost = items_in_tier * tier.unit_price
            total_cost += tier_cost

            # Add to breakdown
            breakdown.append(TierBreakdownItemDTO(
                quantity=items_in_tier,
                unit_price=round(tier.unit_price, 2),
                total=round(tier_cost, 2)
            ))

            # Move to next items
            current_item_index += items_in_tier

            # Stop if we've processed all items
            if current_item_index > quantity:
                break

        total = round(total_cost, 2)
        average_unit_price = round(total / quantity, 2)

        return TierPricingResultDTO(
            total=total,
            average_unit_price=average_unit_price,
            breakdown=breakdown
        )

    @staticmethod
    def format_tier_breakdown(pricing_result: TierPricingResultDTO) -> str:
        """
        Format tier breakdown for display in messages.

        If only 1 tier exists, shows simple fixed price format.
        If multiple tiers exist, shows tiered pricing breakdown.

        Example output (multiple tiers):
            ```
            Staffelpreise:
             10 ×  9,00 € =   90,00 €
              5 × 10,00 € =   50,00 €
              2 × 11,00 € =   22,00 €
            ───────────────────────────
                       Σ  162,00 €
                       Ø    9,53 €/Stk.
            ```

        Example output (single tier/fixed price):
            ```
            5 × 11,00 € = 55,00 €
            ```

        Args:
            pricing_result: Result from calculate_optimal_price()

        Returns:
            Formatted string with aligned columns
        """
        # If only 1 tier, show simple line item without tier header/footer
        if len(pricing_result.breakdown) == 1:
            item = pricing_result.breakdown[0]
            return f"{item.quantity} × {item.unit_price:.2f} € = {item.total:.2f} €"

        # Multiple tiers - show full breakdown
        lines = ["<b>Staffelpreise:</b>"]

        # Build breakdown lines with aligned formatting
        for item in pricing_result.breakdown:
            qty_str = f"{item.quantity:>3}"
            price_str = f"{item.unit_price:>6.2f}"
            total_str = f"{item.total:>8.2f}"
            lines.append(f" {qty_str} × {price_str} € = {total_str} €")

        # Separator line
        lines.append("─" * 30)

        # Total and average
        total_str = f"{pricing_result.total:>8.2f}"
        avg_str = f"{pricing_result.average_unit_price:>6.2f}"
        lines.append(f"{'':>17}Σ {total_str} €")
        lines.append(f"{'':>17}Ø {avg_str} €/Stk.")

        return "\n".join(lines)

    @staticmethod
    async def format_available_tiers(
        subcategory_id: int,
        session: Session | AsyncSession
    ) -> str | None:
        """
        Format available tiers as a price list for display.

        Example output:
            ```
            📊 Staffelpreise:
               1-4 Stk.:   11,00 €
              5-24 Stk.:   10,00 €
             25-49 Stk.:    9,00 €
                50+ Stk.:    7,50 €
            ```

        Args:
            subcategory_id: Subcategory ID
            session: Database session

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
                range_str = f"{tier.min_quantity}-{next_qty - 1} Stk."
            else:
                # Last tier - show "X+"
                range_str = f"{tier.min_quantity}+ Stk."

            price_str = f"{tier.unit_price:>6.2f}"
            lines.append(f"  {range_str:>12}: {price_str} €")

        return "\n".join(lines)