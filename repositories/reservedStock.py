from datetime import datetime
import logging

from sqlalchemy import select, delete, func, text

from db import get_db_session, session_commit, session_execute
from models.reservedStock import ReservedStock, ReservedStockDTO
from models.item import Item
from utils.transaction_manager import TransactionManager

logger = logging.getLogger(__name__)


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
    @TransactionManager.with_retry(max_retries=3)
    async def check_availability(category_id: int, subcategory_id: int, quantity: int) -> bool:
        """
        Check availability with atomic transaction and inventory locking to prevent race conditions
        """
        try:
            async with TransactionManager.inventory_lock_transaction(category_id, subcategory_id) as session:
                # Get total available items with lock
                available_stmt = select(func.count(Item.id)).where(
                    Item.category_id == category_id,
                    Item.subcategory_id == subcategory_id,
                    Item.is_sold == False
                )
                
                # Get total reserved items with lock
                reserved_stmt = select(func.coalesce(func.sum(ReservedStock.quantity), 0)).where(
                    ReservedStock.category_id == category_id,
                    ReservedStock.subcategory_id == subcategory_id,
                    ReservedStock.expires_at > datetime.now()
                )
                
                available_result = await session.execute(available_stmt)
                available_count = available_result.scalar_one()
                
                reserved_result = await session.execute(reserved_stmt)
                reserved_count = reserved_result.scalar_one()
                
                is_available = (available_count - reserved_count) >= quantity
                
                logger.debug(f"Stock check: category={category_id}, subcategory={subcategory_id}, "
                           f"available={available_count}, reserved={reserved_count}, "
                           f"requested={quantity}, result={is_available}")
                
                return is_available
                
        except Exception as e:
            logger.error(f"Error checking availability for category {category_id}, subcategory {subcategory_id}: {str(e)}")
            raise
    
    @staticmethod
    @TransactionManager.with_retry(max_retries=3)
    async def atomic_check_and_reserve(category_id: int, subcategory_id: int, 
                                     quantity: int, order_id: int, expires_at: datetime) -> bool:
        """
        Atomically check availability and create reservation to prevent race conditions
        """
        try:
            async with TransactionManager.inventory_lock_transaction(category_id, subcategory_id) as session:
                # First check availability with locks held
                available_stmt = select(func.count(Item.id)).where(
                    Item.category_id == category_id,
                    Item.subcategory_id == subcategory_id,
                    Item.is_sold == False
                )
                
                reserved_stmt = select(func.coalesce(func.sum(ReservedStock.quantity), 0)).where(
                    ReservedStock.category_id == category_id,
                    ReservedStock.subcategory_id == subcategory_id,
                    ReservedStock.expires_at > datetime.now()
                )
                
                available_result = await session.execute(available_stmt)
                available_count = available_result.scalar_one()
                
                reserved_result = await session.execute(reserved_stmt)
                reserved_count = reserved_result.scalar_one()
                
                if (available_count - reserved_count) < quantity:
                    logger.warning(f"Insufficient stock: available={available_count}, reserved={reserved_count}, requested={quantity}")
                    return False
                
                # Create reservation atomically
                reservation = ReservedStock(
                    order_id=order_id,
                    category_id=category_id,
                    subcategory_id=subcategory_id,
                    quantity=quantity,
                    reserved_at=datetime.now(),
                    expires_at=expires_at
                )
                
                session.add(reservation)
                await session.commit()
                
                logger.info(f"Stock reserved atomically: order={order_id}, category={category_id}, "
                          f"subcategory={subcategory_id}, quantity={quantity}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error in atomic check and reserve: {str(e)}")
            raise