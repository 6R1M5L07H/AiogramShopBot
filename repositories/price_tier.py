from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute
from models.price_tier import PriceTier, PriceTierDTO


class PriceTierRepository:
    """Repository for price tier operations."""

    @staticmethod
    async def get_by_item_id(
        item_id: int,
        session: Session | AsyncSession
    ) -> list[PriceTierDTO]:
        """
        Get all price tiers for an item, sorted by min_quantity ASC.

        Args:
            item_id: ID of the item
            session: Database session

        Returns:
            List of PriceTierDTO sorted by min_quantity ascending
        """
        stmt = (
            select(PriceTier)
            .where(PriceTier.item_id == item_id)
            .order_by(PriceTier.min_quantity.asc())
        )
        result = await session_execute(stmt, session)
        tiers = result.scalars().all()
        return [PriceTierDTO.model_validate(tier, from_attributes=True) for tier in tiers]

    @staticmethod
    async def add_many(
        tiers: list[dict],
        session: Session | AsyncSession
    ) -> None:
        """
        Bulk insert price tiers.

        Args:
            tiers: List of tier dictionaries with keys: item_id, min_quantity, unit_price
            session: Database session

        Example:
            await PriceTierRepository.add_many([
                {"item_id": 1, "min_quantity": 1, "unit_price": 11.00},
                {"item_id": 1, "min_quantity": 5, "unit_price": 10.00},
                {"item_id": 1, "min_quantity": 10, "unit_price": 9.00},
            ], session)
        """
        for tier_data in tiers:
            tier = PriceTier(**tier_data)
            session.add(tier)

    @staticmethod
    async def delete_by_item_id(
        item_id: int,
        session: Session | AsyncSession
    ) -> int:
        """
        Delete all price tiers for an item.

        Args:
            item_id: ID of the item
            session: Database session

        Returns:
            Number of tiers deleted
        """
        stmt = delete(PriceTier).where(PriceTier.item_id == item_id)
        result = await session_execute(stmt, session)
        return result.rowcount

    @staticmethod
    async def get_by_id(
        tier_id: int,
        session: Session | AsyncSession
    ) -> PriceTierDTO | None:
        """
        Get a single price tier by ID.

        Args:
            tier_id: ID of the tier
            session: Database session

        Returns:
            PriceTierDTO if found, None otherwise
        """
        stmt = select(PriceTier).where(PriceTier.id == tier_id)
        result = await session_execute(stmt, session)
        tier = result.scalar()

        if tier is None:
            return None

        return PriceTierDTO.model_validate(tier, from_attributes=True)

    @staticmethod
    async def exists_for_item(
        item_id: int,
        session: Session | AsyncSession
    ) -> bool:
        """
        Check if price tiers exist for an item.

        Args:
            item_id: ID of the item
            session: Database session

        Returns:
            True if tiers exist, False otherwise
        """
        stmt = select(PriceTier.id).where(PriceTier.item_id == item_id).limit(1)
        result = await session_execute(stmt, session)
        return result.scalar() is not None

    @staticmethod
    async def get_by_subcategory(
        subcategory_id: int,
        session: Session | AsyncSession
    ) -> list[PriceTierDTO]:
        """
        Get price tiers for a subcategory (from any item in that subcategory).
        All items in the same subcategory share the same pricing tiers.

        Args:
            subcategory_id: ID of the subcategory
            session: Database session

        Returns:
            List of PriceTierDTO sorted by min_quantity ascending, or empty list if no tiers exist
        """
        from models.item import Item

        # Get any item that HAS price tiers (not just first item)
        # Join with price_tiers to ensure we pick an item with tiers
        item_stmt = (
            select(Item.id)
            .join(PriceTier, PriceTier.item_id == Item.id)
            .where(Item.subcategory_id == subcategory_id)
            .limit(1)
        )
        item_result = await session_execute(item_stmt, session)
        item_id = item_result.scalar()

        if item_id is None:
            return []

        # Get all tiers for that item
        return await PriceTierRepository.get_by_item_id(item_id, session)

    @staticmethod
    async def get_by_subcategories(
        subcategory_ids: list[int],
        session: Session | AsyncSession
    ) -> dict[int, list[PriceTierDTO]]:
        """
        Batch-load price tiers for multiple subcategories (prevents N+1 queries).
        All items in the same subcategory share the same pricing tiers.

        Args:
            subcategory_ids: List of subcategory IDs
            session: Database session

        Returns:
            Dict mapping subcategory_id to list of PriceTierDTO sorted by min_quantity ascending
            Example: {1: [tier1, tier2], 2: [tier1, tier2, tier3]}
        """
        from models.item import Item

        if not subcategory_ids:
            return {}

        # Get one representative item_id per subcategory that HAS tiers
        item_stmt = (
            select(Item.id, Item.subcategory_id)
            .join(PriceTier, PriceTier.item_id == Item.id)
            .where(Item.subcategory_id.in_(subcategory_ids))
            .distinct(Item.subcategory_id)
        )
        item_result = await session_execute(item_stmt, session)
        item_rows = item_result.all()

        # Map subcategory_id -> item_id
        subcategory_to_item = {row.subcategory_id: row.id for row in item_rows}

        # Get all item_ids
        item_ids = list(subcategory_to_item.values())

        if not item_ids:
            return {}

        # Batch-load all tiers for all items
        stmt = (
            select(PriceTier)
            .where(PriceTier.item_id.in_(item_ids))
            .order_by(PriceTier.item_id, PriceTier.min_quantity.asc())
        )
        result = await session_execute(stmt, session)
        all_tiers = result.scalars().all()

        # Group tiers by item_id
        tiers_by_item = {}
        for tier in all_tiers:
            if tier.item_id not in tiers_by_item:
                tiers_by_item[tier.item_id] = []
            tiers_by_item[tier.item_id].append(PriceTierDTO.model_validate(tier, from_attributes=True))

        # Remap to subcategory_id
        result_dict = {}
        for subcategory_id, item_id in subcategory_to_item.items():
            result_dict[subcategory_id] = tiers_by_item.get(item_id, [])

        return result_dict