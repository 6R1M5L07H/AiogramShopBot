import datetime
import math

from sqlalchemy import select, update, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import StatisticsTimeDelta
from db import session_execute, session_flush
from enums.approval_status import ApprovalStatus

from models.user import UserDTO, User


class UserRepository:
    @staticmethod
    async def get_by_tgid(telegram_id: int, session: AsyncSession | Session) -> UserDTO | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        user = await session_execute(stmt, session)
        user = user.scalar()
        if user is not None:
            return UserDTO.model_validate(user, from_attributes=True)
        else:
            return user

    @staticmethod
    async def get_by_id(user_id: int, session: AsyncSession | Session) -> UserDTO | None:
        stmt = select(User).where(User.id == user_id)
        user = await session_execute(stmt, session)
        user = user.scalar()
        if user is not None:
            return UserDTO.model_validate(user, from_attributes=True)
        else:
            return user

    @staticmethod
    async def update(user_dto: UserDTO, session: Session | AsyncSession) -> None:
        user_dto_dict = user_dto.model_dump()
        none_keys = [k for k, v in user_dto_dict.items() if v is None]
        for k in none_keys:
            user_dto_dict.pop(k)

        # Update by id if available (preferred), otherwise by telegram_id
        if user_dto.id is not None:
            stmt = update(User).where(User.id == user_dto.id).values(**user_dto_dict)
        else:
            stmt = update(User).where(User.telegram_id == user_dto.telegram_id).values(**user_dto_dict)

        await session_execute(stmt, session)

    @staticmethod
    async def create(user_dto: UserDTO, session: Session | AsyncSession) -> int:
        user = User(**user_dto.model_dump())
        session.add(user)
        await session_flush(session)
        return user.id

    @staticmethod
    async def get_active(session: Session | AsyncSession) -> list[UserDTO]:
        stmt = select(User).where(User.can_receive_messages == True)
        users = await session_execute(stmt, session)
        return [UserDTO.model_validate(user, from_attributes=True) for user in users.scalars().all()]

    @staticmethod
    async def get_all_count(session: Session | AsyncSession) -> int:
        stmt = func.count(User.id)
        users_count = await session_execute(stmt, session)
        return users_count.scalar_one()

    @staticmethod
    async def get_banned_users(session: Session | AsyncSession) -> list[UserDTO]:
        """
        Get all banned users ordered by ban date (most recent first).

        Returns:
            list[UserDTO]: List of banned users with all user information
        """
        stmt = (
            select(User)
            .where(User.is_blocked == True)
            .order_by(User.blocked_at.desc())
        )
        result = await session_execute(stmt, session)
        users = result.scalars().all()
        return [UserDTO.model_validate(user, from_attributes=True) for user in users]

    @staticmethod
    async def get_user_entity(user_entity: int | str, session: Session | AsyncSession) -> UserDTO | None:
        stmt = select(User).where(or_(User.telegram_id == user_entity, User.telegram_username == user_entity,
                                      User.id == user_entity))
        user = await session_execute(stmt, session)
        user = user.scalar()
        if user is None:
            return user
        else:
            return UserDTO.model_validate(user, from_attributes=True)

    @staticmethod
    async def get_by_timedelta(timedelta: StatisticsTimeDelta, page: int, session: Session | AsyncSession) -> tuple[list[UserDTO], int]:
        current_time = datetime.datetime.now()
        timedelta = datetime.timedelta(days=timedelta.value)
        time_interval = current_time - timedelta
        users_stmt = (select(User)
                      .where(User.registered_at >= time_interval)
                      .limit(config.PAGE_ENTRIES)
                      .offset(config.PAGE_ENTRIES * page))
        users_count_stmt = select(func.count(User.id)).where(User.registered_at >= time_interval)
        users = await session_execute(users_stmt, session)
        users = [UserDTO.model_validate(user, from_attributes=True) for user in users.scalars().all()]
        users_count = await session_execute(users_count_stmt, session)
        return users, users_count.scalar_one()

    @staticmethod
    async def get_max_page_by_timedelta(timedelta: StatisticsTimeDelta, session: Session | AsyncSession) -> int:
        current_time = datetime.datetime.now()
        timedelta = datetime.timedelta(days=timedelta.value)
        time_interval = current_time - timedelta
        stmt = select(func.count(User.id)).where(User.registered_at >= time_interval)
        users = await session_execute(stmt, session)
        users = users.scalar_one()
        if users % config.PAGE_ENTRIES == 0:
            return users / config.PAGE_ENTRIES - 1
        else:
            return math.trunc(users / config.PAGE_ENTRIES)

    # === Registration Management Methods ===

    @staticmethod
    async def get_by_approval_status(
            status: ApprovalStatus,
            page: int,
            session: AsyncSession | Session
    ) -> tuple[list[UserDTO], int]:
        """
        Get users by approval status with pagination.

        Args:
            status: Approval status to filter by
            page: Page number (0-indexed)
            session: Database session

        Returns:
            Tuple of (users list, total count)
        """
        users_stmt = (
            select(User)
            .where(User.approval_status == status)
            .order_by(User.approval_requested_at.desc())
            .limit(config.PAGE_ENTRIES)
            .offset(config.PAGE_ENTRIES * page)
        )
        users_count_stmt = select(func.count(User.id)).where(User.approval_status == status)

        users = await session_execute(users_stmt, session)
        users = [UserDTO.model_validate(user, from_attributes=True) for user in users.scalars().all()]

        users_count = await session_execute(users_count_stmt, session)
        return users, users_count.scalar_one()

    @staticmethod
    async def get_max_page_by_approval_status(
            status: ApprovalStatus,
            session: AsyncSession | Session
    ) -> int:
        """
        Get max page number for approval status filter.

        Args:
            status: Approval status to filter by
            session: Database session

        Returns:
            Max page number (0-indexed)
        """
        stmt = select(func.count(User.id)).where(User.approval_status == status)
        count = await session_execute(stmt, session)
        count = count.scalar_one()

        if count % config.PAGE_ENTRIES == 0:
            return int(count / config.PAGE_ENTRIES - 1)
        else:
            return math.trunc(count / config.PAGE_ENTRIES)

    @staticmethod
    async def get_pending_users(session: AsyncSession | Session) -> list[UserDTO]:
        """
        Get all users pending approval (for batch operations).

        Returns:
            List of pending users ordered by request date
        """
        stmt = (
            select(User)
            .where(User.approval_status == ApprovalStatus.PENDING)
            .order_by(User.approval_requested_at.asc())
        )
        result = await session_execute(stmt, session)
        users = result.scalars().all()
        return [UserDTO.model_validate(user, from_attributes=True) for user in users]

    @staticmethod
    async def get_waitlist_users(session: AsyncSession | Session) -> list[UserDTO]:
        """
        Get all users on waitlist (for batch operations).

        Returns:
            List of waitlist users ordered by registration date
        """
        stmt = (
            select(User)
            .where(User.approval_status == ApprovalStatus.CLOSED_REGISTRATION)
            .order_by(User.registered_at.asc())
        )
        result = await session_execute(stmt, session)
        users = result.scalars().all()
        return [UserDTO.model_validate(user, from_attributes=True) for user in users]

    @staticmethod
    async def approve_user(
            user_id: int,
            admin_id: int,
            session: AsyncSession | Session
    ) -> None:
        """
        Approve a user (mark as approved, set approval timestamp and admin).

        Args:
            user_id: User ID to approve
            admin_id: Admin ID who approved
            session: Database session
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                approval_status=ApprovalStatus.APPROVED,
                approved_at=datetime.datetime.now(),
                approved_by_admin_id=admin_id,
                rejection_reason=None  # Clear any previous rejection reason
            )
        )
        await session_execute(stmt, session)

    @staticmethod
    async def reject_user(
            user_id: int,
            reason: str,
            session: AsyncSession | Session
    ) -> None:
        """
        Reject a user (mark as rejected with reason).

        Args:
            user_id: User ID to reject
            reason: Rejection reason to show user
            session: Database session
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                approval_status=ApprovalStatus.REJECTED,
                rejection_reason=reason
            )
        )
        await session_execute(stmt, session)

    @staticmethod
    async def batch_approve_users(
            user_ids: list[int],
            admin_id: int,
            session: AsyncSession | Session
    ) -> int:
        """
        Batch approve multiple users.

        Args:
            user_ids: List of user IDs to approve
            admin_id: Admin ID who approved
            session: Database session

        Returns:
            Number of users approved
        """
        if not user_ids:
            return 0

        stmt = (
            update(User)
            .where(User.id.in_(user_ids))
            .values(
                approval_status=ApprovalStatus.APPROVED,
                approved_at=datetime.datetime.now(),
                approved_by_admin_id=admin_id,
                rejection_reason=None
            )
        )
        result = await session_execute(stmt, session)
        return result.rowcount if hasattr(result, 'rowcount') else len(user_ids)
