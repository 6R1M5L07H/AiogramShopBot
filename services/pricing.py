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
        Calculate optimal tier combination using dynamic programming.

        The DP algorithm guarantees the minimum total cost for any quantity
        by considering all possible tier combinations, not just greedy choices.
        This prevents overcharging users when non-canonical tier structures exist.

        Algorithm:
        1. Build dp[i] = (min_cost, breakdown) for quantities 0..quantity
        2. For each quantity q, try all tier combinations
        3. Select the combination with minimum total cost
        4. Merge consecutive tiers with same unit_price for cleaner display

        Example:
            6 items with tiers [1→€10, 3→€7/item, 5→€9/item]:
            - Greedy would choose: 1×5 + 1×1 = €45 + €10 = €55
            - Optimal DP chooses: 2×3 = €21 + €21 = €42 (saves €13!)

        Args:
            subcategory_id: ID of the subcategory
            quantity: Number of items to purchase
            session: Database session

        Returns:
            TierPricingResultDTO with optimal total, average, and breakdown

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

        # Dynamic Programming: Find optimal combination
        # dp[i] = (min_cost, breakdown) for quantity i
        dp = [None] * (quantity + 1)
        dp[0] = (0.0, [])

        sorted_tiers = sorted(tiers, key=lambda t: t.min_quantity)

        for q in range(1, quantity + 1):
            best_cost = float('inf')
            best_breakdown = []

            # Try each tier
            for tier in sorted_tiers:
                if tier.min_quantity <= q:
                    # Try using this tier for different quantities
                    for tier_qty in range(tier.min_quantity, q + 1, tier.min_quantity):
                        remaining = q - tier_qty
                        if dp[remaining] is not None:
                            prev_cost, prev_breakdown = dp[remaining]
                            tier_cost = tier_qty * tier.unit_price
                            total_cost = prev_cost + tier_cost

                            if total_cost < best_cost:
                                best_cost = total_cost
                                # Deep copy breakdown to avoid mutating shared DTO instances
                                new_breakdown = [
                                    TierBreakdownItemDTO(
                                        quantity=item.quantity,
                                        unit_price=item.unit_price,
                                        total=item.total
                                    )
                                    for item in prev_breakdown
                                ]

                                # Merge with existing tier if same unit_price
                                merged = False
                                for item in new_breakdown:
                                    if abs(item.unit_price - tier.unit_price) < 0.01:
                                        item.quantity += tier_qty
                                        item.total = round(item.quantity * item.unit_price, 2)
                                        merged = True
                                        break

                                if not merged:
                                    new_breakdown.append(TierBreakdownItemDTO(
                                        quantity=tier_qty,
                                        unit_price=round(tier.unit_price, 2),
                                        total=round(tier_cost, 2)
                                    ))

                                best_breakdown = new_breakdown

            dp[q] = (best_cost, best_breakdown) if best_cost != float('inf') else None

        if dp[quantity] is None:
            # Fallback: use smallest tier for all items
            smallest_tier = sorted_tiers[0]
            breakdown = [TierBreakdownItemDTO(
                quantity=quantity,
                unit_price=round(smallest_tier.unit_price, 2),
                total=round(quantity * smallest_tier.unit_price, 2)
            )]
            total = breakdown[0].total
        else:
            total, breakdown = dp[quantity]
            total = round(total, 2)

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