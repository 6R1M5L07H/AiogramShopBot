from datetime import datetime

from sqlalchemy import select, update

from db import get_db_session, session_commit, session_execute, session_refresh
from models.order import Order, OrderDTO, OrderStatus


class OrderRepository:
    @staticmethod
    async def create(order_dto: OrderDTO) -> int:
        async with get_db_session() as session:
            order = Order(**order_dto.__dict__)
            session.add(order)
            await session_commit(session)
            await session_refresh(session, order)
            return order.id

    @staticmethod
    async def get_by_id(order_id: int) -> OrderDTO | None:
        stmt = select(Order).where(Order.id == order_id)
        async with get_db_session() as session:
            order = await session_execute(stmt, session)
            order = order.scalar()
            if order is not None:
                return OrderDTO.model_validate(order, from_attributes=True)
            else:
                return None

    @staticmethod
    async def get_by_user_id(user_id: int) -> OrderDTO | None:
        stmt = select(Order).where(
            Order.user_id == user_id,
            Order.status.in_([OrderStatus.CREATED.value, OrderStatus.PAID.value])
        ).order_by(Order.created_at.desc()).limit(1)
        async with get_db_session() as session:
            order = await session_execute(stmt, session)
            order = order.scalar()
            if order is not None:
                return OrderDTO.model_validate(order, from_attributes=True)
            else:
                return None

    @staticmethod
    async def get_by_payment_address(address: str) -> OrderDTO | None:
        stmt = select(Order).where(Order.payment_address == address)
        async with get_db_session() as session:
            order = await session_execute(stmt, session)
            order = order.scalar()
            if order is not None:
                return OrderDTO.model_validate(order, from_attributes=True)
            else:
                return None

    @staticmethod
    async def update_status(order_id: int, status: OrderStatus) -> None:
        stmt = update(Order).where(Order.id == order_id).values(status=status.value)
        async with get_db_session() as session:
            await session_execute(stmt, session)
            await session_commit(session)

    @staticmethod
    async def update_payment_confirmation(order_id: int, paid_at: datetime) -> None:
        stmt = update(Order).where(Order.id == order_id).values(
            status=OrderStatus.PAID.value,
            paid_at=paid_at
        )
        async with get_db_session() as session:
            await session_execute(stmt, session)
            await session_commit(session)

    @staticmethod
    async def get_expired_orders() -> list[OrderDTO]:
        current_time = datetime.now()
        stmt = select(Order).where(
            Order.status == OrderStatus.CREATED.value,
            Order.expires_at <= current_time
        )
        async with get_db_session() as session:
            orders = await session_execute(stmt, session)
            return [OrderDTO.model_validate(order, from_attributes=True) for order in orders.scalars().all()]

    @staticmethod
    async def get_orders_ready_for_shipment() -> list[OrderDTO]:
        stmt = select(Order).where(Order.status == OrderStatus.PAID.value).order_by(Order.paid_at.desc())
        async with get_db_session() as session:
            orders = await session_execute(stmt, session)
            return [OrderDTO.model_validate(order, from_attributes=True) for order in orders.scalars().all()]

    @staticmethod
    async def update_shipped(order_id: int, shipped_at: datetime) -> None:
        stmt = update(Order).where(Order.id == order_id).values(
            status=OrderStatus.SHIPPED.value,
            shipped_at=shipped_at
        )
        async with get_db_session() as session:
            await session_execute(stmt, session)
            await session_commit(session)