from sqlalchemy import select, delete

from db import get_db_session, session_commit, session_execute
from models.orderItem import OrderItem, OrderItemDTO


class OrderItemRepository:
    @staticmethod
    async def create_many(order_items: list[OrderItemDTO]) -> None:
        async with get_db_session() as session:
            for order_item_dto in order_items:
                order_item = OrderItem(**order_item_dto.__dict__)
                session.add(order_item)
            await session_commit(session)

    @staticmethod
    async def get_by_order_id(order_id: int) -> list[OrderItemDTO]:
        stmt = select(OrderItem).where(OrderItem.order_id == order_id)
        async with get_db_session() as session:
            order_items = await session_execute(stmt, session)
            return [OrderItemDTO.model_validate(order_item, from_attributes=True) for order_item in order_items.scalars().all()]

    @staticmethod
    async def delete_by_order_id(order_id: int) -> None:
        stmt = delete(OrderItem).where(OrderItem.order_id == order_id)
        async with get_db_session() as session:
            await session_execute(stmt, session)
            await session_commit(session)