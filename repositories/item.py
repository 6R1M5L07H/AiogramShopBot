from datetime import datetime

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute
from models.buyItem import BuyItem
from models.item import Item, ItemDTO


class ItemRepository:

    @staticmethod
    async def get_price(item_dto: ItemDTO, session: Session | AsyncSession) -> float:
        stmt = (select(Item.price)
                .where(Item.category_id == item_dto.category_id,
                       Item.subcategory_id == item_dto.subcategory_id)
                .limit(1))
        price = await session_execute(stmt, session)
        return price.scalar()

    @staticmethod
    async def get_prices_batch(
        items: list[tuple[int, int]],
        session: Session | AsyncSession
    ) -> dict[tuple[int, int], float]:
        """
        Batch load prices for multiple (category_id, subcategory_id) pairs.

        Prevents N+1 queries by loading all prices in a single query.

        Args:
            items: List of (category_id, subcategory_id) tuples
            session: Database session

        Returns:
            Dict mapping (category_id, subcategory_id) -> price

        Example:
            >>> prices = await get_prices_batch([(1, 2), (1, 3), (2, 1)], session)
            >>> prices[(1, 2)]  # 9.99
        """
        if not items:
            return {}

        # Build query with OR conditions for each (category_id, subcategory_id) pair
        from sqlalchemy import or_, and_

        conditions = [
            and_(Item.category_id == cat_id, Item.subcategory_id == sub_id)
            for cat_id, sub_id in items
        ]

        stmt = (
            select(Item.category_id, Item.subcategory_id, Item.price)
            .where(or_(*conditions))
            .distinct()
        )

        result = await session_execute(stmt, session)
        rows = result.all()

        # Build dict mapping (category_id, subcategory_id) -> price
        return {(row[0], row[1]): row[2] for row in rows}

    @staticmethod
    async def get_available_qty(item_dto: ItemDTO, session: Session | AsyncSession) -> int:
        sub_stmt = (select(Item)
                    .where(Item.category_id == item_dto.category_id,
                           Item.subcategory_id == item_dto.subcategory_id,
                           Item.is_sold == False,
                           Item.order_id == None))  # Only count unreserved items
        stmt = select(func.count()).select_from(sub_stmt)
        available_qty = await session_execute(stmt, session)
        return available_qty.scalar()

    @staticmethod
    async def get_item_metadata(category_id: int, subcategory_id: int, session: Session | AsyncSession) -> ItemDTO | None:
        """
        Get item metadata for display purposes (price, description, is_physical, shipping_cost).
        Returns ANY item (sold or not) since we only need metadata, not availability.
        For availability check, use get_available_qty().

        Returns:
            ItemDTO if found, None if no items exist for this category/subcategory
        """
        stmt = (select(Item)
                .where(Item.category_id == category_id,
                       Item.subcategory_id == subcategory_id)
                .limit(1))
        item = await session_execute(stmt, session)
        result = item.scalar()

        if result is None:
            return None

        return ItemDTO.model_validate(result, from_attributes=True)

    @staticmethod
    async def get_by_id(item_id: int, session: Session | AsyncSession) -> ItemDTO:
        stmt = select(Item).where(Item.id == item_id)
        item = await session_execute(stmt, session)
        return ItemDTO.model_validate(item.scalar(), from_attributes=True)

    @staticmethod
    async def get_by_ids(item_ids: list[int], session: Session | AsyncSession) -> dict[int, ItemDTO]:
        """
        Batch load Items for multiple item_ids (eliminates N+1 queries).

        Args:
            item_ids: List of item IDs
            session: Database session

        Returns:
            Dict mapping item_id -> ItemDTO
        """
        if not item_ids:
            return {}

        stmt = select(Item).where(Item.id.in_(item_ids))
        result = await session_execute(stmt, session)
        items = result.scalars().all()

        return {item.id: ItemDTO.model_validate(item, from_attributes=True) for item in items}

    @staticmethod
    async def get_purchased_items(category_id: int, subcategory_id: int, quantity: int, session: Session | AsyncSession) -> list[ItemDTO]:
        stmt = (select(Item)
                .where(Item.category_id == category_id, Item.subcategory_id == subcategory_id,
                       Item.is_sold == False,
                       Item.order_id == None)  # Only get unreserved items
                .limit(quantity))
        items = await session_execute(stmt, session)
        return [ItemDTO.model_validate(item, from_attributes=True) for item in items.scalars().all()]

    @staticmethod
    async def update(item_dto_list: list[ItemDTO], session: Session | AsyncSession):
        for item in item_dto_list:
            # Exclude price_tiers (relationship) and only dump set fields
            stmt = update(Item).where(Item.id == item.id).values(**item.model_dump(exclude={'price_tiers'}, exclude_unset=True))
            await session_execute(stmt, session)

    @staticmethod
    async def get_by_buy_id(buy_id: int, session: Session | AsyncSession) -> list[ItemDTO]:
        stmt = (
            select(Item)
            .join(BuyItem, BuyItem.item_id == Item.id)
            .where(BuyItem.buy_id == buy_id)
        )
        result = await session_execute(stmt, session)
        return [ItemDTO.model_validate(item, from_attributes=True) for item in result.scalars().all()]

    @staticmethod
    async def set_not_new(session: Session | AsyncSession):
        stmt = update(Item).values(is_new=False)
        await session_execute(stmt, session)

    @staticmethod
    async def delete_unsold_by_category_id(entity_id: int, session: Session | AsyncSession):
        stmt = delete(Item).where(Item.category_id == entity_id, Item.is_sold == False)
        await session_execute(stmt, session)

    @staticmethod
    async def delete_unsold_by_subcategory_id(entity_id: int, session: Session | AsyncSession):
        stmt = delete(Item).where(Item.subcategory_id == entity_id, Item.is_sold == False)
        await session_execute(stmt, session)

    @staticmethod
    async def add_many(items: list[ItemDTO], session: Session | AsyncSession):
        from db import session_flush
        from repositories.price_tier import PriceTierRepository

        # Convert DTOs to ORM models and add to session
        # Track which models have price_tiers
        tiers_to_add = []
        for item_dto in items:
            # Extract and remove price_tiers before creating ORM model
            price_tiers = None
            if hasattr(item_dto, 'price_tiers') and item_dto.price_tiers:
                price_tiers = item_dto.price_tiers

            # Exclude price_tiers from model_dump (it's not a database column)
            item_dict = item_dto.model_dump(exclude={'price_tiers'})
            item_model = Item(**item_dict)
            session.add(item_model)

            # Store model and tiers together for later
            if price_tiers:
                tiers_to_add.append((item_model, price_tiers))

        # Flush to get item IDs if any items have tiers
        if tiers_to_add:
            await session_flush(session)

            # Now add price tiers with correct item_id
            for item_model, tiers in tiers_to_add:
                tier_dicts = [
                    {
                        'item_id': item_model.id,
                        'min_quantity': tier['min_quantity'],
                        'unit_price': tier['unit_price']
                    }
                    for tier in tiers
                ]
                await PriceTierRepository.add_many(tier_dicts, session)

    @staticmethod
    async def get_new(session: Session | AsyncSession) -> list[ItemDTO]:
        stmt = select(Item).where(Item.is_new == True)
        items = await session_execute(stmt, session)
        return [ItemDTO.model_validate(item, from_attributes=True) for item in items.scalars().all()]

    @staticmethod
    async def get_in_stock(session: Session | AsyncSession) -> list[ItemDTO]:
        stmt = select(Item).where(Item.is_sold == False)
        items = await session_execute(stmt, session)
        return [ItemDTO.model_validate(item, from_attributes=True) for item in items.scalars().all()]

    @staticmethod
    async def get_available_quantity_for_subcategory(
        subcategory_id: int,
        session: Session | AsyncSession
    ) -> int:
        """
        Returns the number of available items for a subcategory (not sold, not reserved).

        Args:
            subcategory_id: Subcategory ID
            session: Database session

        Returns:
            Number of available items
        """
        stmt = select(func.count()).select_from(
            select(Item)
            .where(Item.subcategory_id == subcategory_id)
            .where(Item.is_sold == False)
            .where(Item.order_id == None)
        )
        result = await session_execute(stmt, session)
        return result.scalar()

    @staticmethod
    async def reserve_items_for_order(
        subcategory_id: int,
        quantity: int,
        order_id: int,
        session: Session | AsyncSession
    ) -> tuple[list[ItemDTO], int]:
        """
        Reserves items for an order, taking what's available (partial reservation allowed).
        Uses SELECT FOR UPDATE for race-condition safety.

        Args:
            subcategory_id: Subcategory ID
            quantity: Requested quantity
            order_id: Order ID
            session: Database session

        Returns:
            Tuple of (reserved_items, requested_quantity)
            - reserved_items: List of reserved ItemDTOs (may be less than requested)
            - requested_quantity: Original requested quantity for tracking
        """
        # SELECT FOR UPDATE: Lock available items atomically
        stmt = (
            select(Item)
            .where(Item.subcategory_id == subcategory_id)
            .where(Item.is_sold == False)
            .where(Item.order_id == None)  # Only unreserved items
            .limit(quantity)
            .with_for_update()  # 🔒 Row-Level Lock!
        )

        result = await session_execute(stmt, session)
        items = result.scalars().all()

        # Reserve whatever is available (no error if less than requested)
        for item in items:
            item.order_id = order_id
            item.reserved_at = datetime.now()

        return [ItemDTO.model_validate(item, from_attributes=True) for item in items], quantity

    @staticmethod
    async def get_by_order_id(order_id: int, session: Session | AsyncSession) -> list[ItemDTO]:
        """
        Holt alle Items einer Order mit eager loading für Subcategories.
        Eliminiert N+1 Queries durch selectinload(Item.subcategory).
        """
        from sqlalchemy.orm import selectinload

        stmt = select(Item).where(Item.order_id == order_id).options(
            selectinload(Item.subcategory)
        )
        result = await session_execute(stmt, session)
        return [ItemDTO.model_validate(item, from_attributes=True) for item in result.scalars().all()]

    @staticmethod
    async def get_sold_items_by_subcategory(
        subcategory_id: int,
        category_id: int,
        price: float,
        limit: int,
        session: Session | AsyncSession
    ) -> list[ItemDTO]:
        """
        Get sold items (is_sold=true) for a specific subcategory/category/price combination.
        Used for stock restoration when orders are cancelled.

        Args:
            subcategory_id: Subcategory ID
            category_id: Category ID
            price: Item price
            limit: Maximum number of items to return
            session: Database session

        Returns:
            List of sold ItemDTOs matching the criteria
        """
        stmt = (
            select(Item)
            .where(Item.subcategory_id == subcategory_id)
            .where(Item.category_id == category_id)
            .where(Item.price == price)
            .where(Item.is_sold == True)
            .where(Item.order_id == None)  # Not currently reserved
            .limit(limit)
        )
        result = await session_execute(stmt, session)
        return [ItemDTO.model_validate(item, from_attributes=True) for item in result.scalars().all()]


