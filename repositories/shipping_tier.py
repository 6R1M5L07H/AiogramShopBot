"""
Shipping Tier Repository

Handles database operations for shipping tiers (quantity-based shipping type selection).
"""

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from models.shipping_tier import ShippingTier, ShippingTierDTO
from db import session_execute, session_flush

logger = logging.getLogger(__name__)


class ShippingTierRepository:
    """Repository for shipping tier database operations."""

    @staticmethod
    async def get_by_subcategory_id(
        subcategory_id: int,
        session: AsyncSession | Session
    ) -> list[ShippingTier]:
        """
        Get all shipping tiers for a subcategory.

        Args:
            subcategory_id: Subcategory ID
            session: Database session

        Returns:
            list[ShippingTier]: Shipping tiers sorted by min_quantity (ascending)

        Example:
            >>> tiers = await ShippingTierRepository.get_by_subcategory_id(3, session)
            >>> for tier in tiers:
            ...     print(f"{tier.min_quantity}-{tier.max_quantity}: {tier.shipping_type}")
        """
        stmt = (
            select(ShippingTier)
            .where(ShippingTier.subcategory_id == subcategory_id)
            .order_by(ShippingTier.min_quantity.asc())
        )

        result = await session_execute(stmt, session)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_subcategory_ids(
        subcategory_ids: list[int],
        session: AsyncSession | Session
    ) -> dict[int, list[ShippingTier]]:
        """
        Get shipping tiers for multiple subcategories (batch operation).

        Args:
            subcategory_ids: List of subcategory IDs
            session: Database session

        Returns:
            dict: {subcategory_id: [ShippingTier, ...]}

        Example:
            >>> tiers_dict = await ShippingTierRepository.get_by_subcategory_ids([3, 5], session)
            >>> tiers_for_subcategory_3 = tiers_dict.get(3, [])
        """
        if not subcategory_ids:
            return {}

        stmt = (
            select(ShippingTier)
            .where(ShippingTier.subcategory_id.in_(subcategory_ids))
            .order_by(ShippingTier.subcategory_id, ShippingTier.min_quantity.asc())
        )

        result = await session_execute(stmt, session)
        tiers = result.scalars().all()

        # Group by subcategory_id
        tiers_dict = {}
        for tier in tiers:
            if tier.subcategory_id not in tiers_dict:
                tiers_dict[tier.subcategory_id] = []
            tiers_dict[tier.subcategory_id].append(tier)

        return tiers_dict

    @staticmethod
    async def create(
        tier_data: ShippingTierDTO,
        session: AsyncSession | Session
    ) -> ShippingTier:
        """
        Create a new shipping tier.

        Args:
            tier_data: ShippingTierDTO with tier information
            session: Database session

        Returns:
            ShippingTier: Created shipping tier

        Example:
            >>> tier_dto = ShippingTierDTO(
            ...     subcategory_id=3,
            ...     min_quantity=1,
            ...     max_quantity=5,
            ...     shipping_type="maxibrief"
            ... )
            >>> tier = await ShippingTierRepository.create(tier_dto, session)
        """
        tier = ShippingTier(
            subcategory_id=tier_data.subcategory_id,
            min_quantity=tier_data.min_quantity,
            max_quantity=tier_data.max_quantity,
            shipping_type=tier_data.shipping_type
        )

        session.add(tier)
        await session_flush(session)

        logger.info(f"Created shipping tier: subcategory={tier.subcategory_id}, "
                   f"qty={tier.min_quantity}-{tier.max_quantity}, type={tier.shipping_type}")

        return tier

    @staticmethod
    async def delete_by_subcategory_id(
        subcategory_id: int,
        session: AsyncSession | Session
    ) -> int:
        """
        Delete all shipping tiers for a subcategory.

        Args:
            subcategory_id: Subcategory ID
            session: Database session

        Returns:
            int: Number of tiers deleted

        Example:
            >>> deleted_count = await ShippingTierRepository.delete_by_subcategory_id(3, session)
        """
        from sqlalchemy import delete

        stmt = delete(ShippingTier).where(ShippingTier.subcategory_id == subcategory_id)
        result = await session_execute(stmt, session)

        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} shipping tiers for subcategory {subcategory_id}")

        return deleted_count

    @staticmethod
    async def bulk_create(
        subcategory_id: int,
        tiers_data: list[dict],
        session: AsyncSession | Session,
        replace_existing: bool = True
    ) -> list[ShippingTier]:
        """
        Bulk create shipping tiers for a subcategory.

        Args:
            subcategory_id: Subcategory ID
            tiers_data: List of tier dicts with min_quantity, max_quantity, shipping_type
            session: Database session
            replace_existing: If True, delete existing tiers first (default: True)

        Returns:
            list[ShippingTier]: Created shipping tiers

        Example:
            >>> tiers_data = [
            ...     {"min_quantity": 1, "max_quantity": 5, "shipping_type": "maxibrief"},
            ...     {"min_quantity": 6, "max_quantity": None, "shipping_type": "paeckchen"}
            ... ]
            >>> tiers = await ShippingTierRepository.bulk_create(3, tiers_data, session)
        """
        if replace_existing:
            await ShippingTierRepository.delete_by_subcategory_id(subcategory_id, session)

        created_tiers = []
        for tier_data in tiers_data:
            tier = ShippingTier(
                subcategory_id=subcategory_id,
                min_quantity=tier_data["min_quantity"],
                max_quantity=tier_data.get("max_quantity"),
                shipping_type=tier_data["shipping_type"]
            )
            session.add(tier)
            created_tiers.append(tier)

        await session_flush(session)

        logger.info(f"Bulk created {len(created_tiers)} shipping tiers for subcategory {subcategory_id}")

        return created_tiers