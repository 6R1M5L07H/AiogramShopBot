from datetime import datetime

from sqlalchemy import select, delete, func

from db import get_db_session, session_commit, session_execute
from models.reservedStock import ReservedStock, ReservedStockDTO
from models.item import Item


class ReservedStockRepository:
    @staticmethod
    async def create_reservations(reservations: list[ReservedStockDTO]) -> None:
        async with get_db_session() as session:
            for reservation_dto in reservations:
                reservation = ReservedStock(**reservation_dto.__dict__)
                session.add(reservation)
            await session_commit(session)

    @staticmethod
    async def get_by_order_id(order_id: int) -> list[ReservedStockDTO]:
        stmt = select(ReservedStock).where(ReservedStock.order_id == order_id)
        async with get_db_session() as session:
            reservations = await session_execute(stmt, session)
            return [ReservedStockDTO.model_validate(reservation, from_attributes=True) for reservation in reservations.scalars().all()]

    @staticmethod
    async def release_by_order_id(order_id: int) -> None:
        stmt = delete(ReservedStock).where(ReservedStock.order_id == order_id)
        async with get_db_session() as session:
            await session_execute(stmt, session)
            await session_commit(session)

    @staticmethod
    async def get_expired_reservations() -> list[ReservedStockDTO]:
        current_time = datetime.now()
        stmt = select(ReservedStock).where(ReservedStock.expires_at <= current_time)
        async with get_db_session() as session:
            reservations = await session_execute(stmt, session)
            return [ReservedStockDTO.model_validate(reservation, from_attributes=True) for reservation in reservations.scalars().all()]

    @staticmethod
    async def check_availability(category_id: int, subcategory_id: int, quantity: int) -> bool:
        # Get total available items
        available_stmt = select(func.count(Item.id)).where(
            Item.category_id == category_id,
            Item.subcategory_id == subcategory_id,
            Item.is_sold == False
        )
        
        # Get total reserved items
        reserved_stmt = select(func.coalesce(func.sum(ReservedStock.quantity), 0)).where(
            ReservedStock.category_id == category_id,
            ReservedStock.subcategory_id == subcategory_id,
            ReservedStock.expires_at > datetime.now()
        )
        
        async with get_db_session() as session:
            available_result = await session_execute(available_stmt, session)
            available_count = available_result.scalar_one()
            
            reserved_result = await session_execute(reserved_stmt, session)
            reserved_count = reserved_result.scalar_one()
            
            return (available_count - reserved_count) >= quantity