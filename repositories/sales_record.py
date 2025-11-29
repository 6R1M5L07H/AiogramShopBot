from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from db import session_execute, session_flush
from models.sales_record import SalesRecord, SalesRecordDTO


class SalesRecordRepository:
    """Repository for SalesRecord model - anonymized sales analytics"""

    @staticmethod
    async def create(sales_record_dto: SalesRecordDTO, session: AsyncSession | Session) -> int:
        """
        Create new sales record.

        Args:
            sales_record_dto: SalesRecord data
            session: Database session

        Returns:
            ID of created sales record
        """
        sales_record = SalesRecord(
            sale_date=sales_record_dto.sale_date.date() if sales_record_dto.sale_date else datetime.now(timezone.utc).date(),
            sale_hour=sales_record_dto.sale_hour,
            sale_weekday=sales_record_dto.sale_weekday,
            category_name=sales_record_dto.category_name,
            subcategory_name=sales_record_dto.subcategory_name,
            quantity=sales_record_dto.quantity,
            is_physical=sales_record_dto.is_physical,
            item_total_price=sales_record_dto.item_total_price,
            currency=sales_record_dto.currency,
            average_unit_price=sales_record_dto.average_unit_price,
            tier_breakdown_json=sales_record_dto.tier_breakdown_json,
            order_hash=sales_record_dto.order_hash,
            order_total_price=sales_record_dto.order_total_price,
            order_shipping_cost=sales_record_dto.order_shipping_cost,
            order_wallet_used=sales_record_dto.order_wallet_used,
            payment_method=sales_record_dto.payment_method,
            crypto_currency=sales_record_dto.crypto_currency,
            status=sales_record_dto.status,
            is_refunded=sales_record_dto.is_refunded if sales_record_dto.is_refunded is not None else False,
            shipping_type=sales_record_dto.shipping_type
        )
        session.add(sales_record)
        await session_flush(session)
        return sales_record.id

    @staticmethod
    async def create_many(sales_record_dtos: list[SalesRecordDTO], session: AsyncSession | Session) -> list[int]:
        """
        Create multiple sales records (for bulk operations).

        Args:
            sales_record_dtos: List of SalesRecord data
            session: Database session

        Returns:
            List of created IDs
        """
        records = []
        for dto in sales_record_dtos:
            record = SalesRecord(
                sale_date=dto.sale_date.date() if dto.sale_date else datetime.now(timezone.utc).date(),
                sale_hour=dto.sale_hour,
                sale_weekday=dto.sale_weekday,
                category_name=dto.category_name,
                subcategory_name=dto.subcategory_name,
                quantity=dto.quantity,
                is_physical=dto.is_physical,
                item_total_price=dto.item_total_price,
                currency=dto.currency,
                average_unit_price=dto.average_unit_price,
                tier_breakdown_json=dto.tier_breakdown_json,
                order_hash=dto.order_hash,
                order_total_price=dto.order_total_price,
                order_shipping_cost=dto.order_shipping_cost,
                order_wallet_used=dto.order_wallet_used,
                payment_method=dto.payment_method,
                crypto_currency=dto.crypto_currency,
                status=dto.status,
                is_refunded=dto.is_refunded if dto.is_refunded is not None else False,
                shipping_type=dto.shipping_type
            )
            session.add(record)
            records.append(record)

        await session_flush(session)
        return [record.id for record in records]

    @staticmethod
    async def get_by_date_range(
        start_date: datetime,
        end_date: datetime,
        session: AsyncSession | Session
    ) -> list[SalesRecord]:
        """
        Get sales records within date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            session: Database session

        Returns:
            List of SalesRecord objects
        """
        stmt = select(SalesRecord).where(
            SalesRecord.sale_date >= start_date.date(),
            SalesRecord.sale_date <= end_date.date()
        ).order_by(SalesRecord.sale_date.desc())

        result = await session_execute(stmt, session)
        return result.scalars().all()

    @staticmethod
    async def get_by_category(
        category_name: str,
        days: int,
        session: AsyncSession | Session
    ) -> list[SalesRecord]:
        """
        Get sales records for specific category within last N days.

        Args:
            category_name: Category name
            days: Number of days to look back
            session: Database session

        Returns:
            List of SalesRecord objects
        """
        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)

        stmt = select(SalesRecord).where(
            SalesRecord.category_name == category_name,
            SalesRecord.sale_date >= cutoff_date
        ).order_by(SalesRecord.sale_date.desc())

        result = await session_execute(stmt, session)
        return result.scalars().all()

    @staticmethod
    async def get_total_revenue(
        days: int,
        session: AsyncSession | Session
    ) -> float:
        """
        Get total revenue for last N days.

        Args:
            days: Number of days to look back
            session: Database session

        Returns:
            Total revenue (sum of item_total_price)
        """
        from sqlalchemy import func

        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)

        stmt = select(func.sum(SalesRecord.item_total_price)).where(
            SalesRecord.sale_date >= cutoff_date,
            SalesRecord.is_refunded == False  # Exclude refunds
        )

        result = await session_execute(stmt, session)
        total = result.scalar()

        return total if total is not None else 0.0

    @staticmethod
    async def get_total_items_sold(
        days: int,
        session: AsyncSession | Session
    ) -> int:
        """
        Get total items sold for last N days.

        Args:
            days: Number of days to look back
            session: Database session

        Returns:
            Total quantity sold
        """
        from sqlalchemy import func

        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)

        stmt = select(func.sum(SalesRecord.quantity)).where(
            SalesRecord.sale_date >= cutoff_date,
            SalesRecord.is_refunded == False  # Exclude refunds
        )

        result = await session_execute(stmt, session)
        total = result.scalar()

        return int(total) if total is not None else 0

    @staticmethod
    async def get_subcategory_sales_grouped(
        start_date: datetime,
        end_date: datetime,
        page: int,
        session: AsyncSession | Session
    ) -> list[dict]:
        """
        Get sales records grouped by subcategory with daily breakdown.

        Aggregates sales by (category, subcategory), then groups daily sales within each.
        Sorted by total revenue DESC (highest revenue first).
        Paginated using config.PAGE_ENTRIES.

        Uses two-query approach for optimal performance:
        1. Query paginated list of subcategories with totals (SQL GROUP BY + LIMIT)
        2. Query daily breakdowns for only those specific subcategories

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            page: Page number (0-indexed)
            session: Database session

        Returns:
            List of dicts with structure:
            [
                {
                    'category': str,
                    'subcategory': str,
                    'sales': [  # Only days with sales!
                        {'date': datetime.date, 'quantity': int, 'revenue': float},
                        ...
                    ],
                    'total_quantity': int,
                    'total_revenue': float
                },
                ...
            ]
        """
        import config
        from sqlalchemy import func, tuple_

        # Query 1: Get paginated list of subcategories with totals (SQL aggregation)
        stmt_subcategories = (
            select(
                SalesRecord.category_name,
                SalesRecord.subcategory_name,
                func.sum(SalesRecord.quantity).label('total_quantity'),
                func.sum(SalesRecord.item_total_price).label('total_revenue')
            )
            .where(
                SalesRecord.sale_date >= start_date.date(),
                SalesRecord.sale_date <= end_date.date(),
                SalesRecord.is_refunded == False
            )
            .group_by(SalesRecord.category_name, SalesRecord.subcategory_name)
            .order_by(func.sum(SalesRecord.item_total_price).desc())
            .limit(config.PAGE_ENTRIES)
            .offset(page * config.PAGE_ENTRIES)
        )

        result_subcategories = await session_execute(stmt_subcategories, session)
        subcategories = result_subcategories.all()

        if not subcategories:
            return []

        # Build result structure with totals
        subcategory_list = []
        subcategory_keys = []

        for row in subcategories:
            subcategory_list.append({
                'category': row.category_name,
                'subcategory': row.subcategory_name,
                'total_quantity': int(row.total_quantity),
                'total_revenue': float(row.total_revenue),
                'sales': []  # Will be populated from Query 2
            })
            subcategory_keys.append((row.category_name, row.subcategory_name))

        # Query 2: Get daily breakdown for only these specific subcategories
        stmt_daily = (
            select(
                SalesRecord.category_name,
                SalesRecord.subcategory_name,
                SalesRecord.sale_date,
                func.sum(SalesRecord.quantity).label('quantity'),
                func.sum(SalesRecord.item_total_price).label('revenue')
            )
            .where(
                SalesRecord.sale_date >= start_date.date(),
                SalesRecord.sale_date <= end_date.date(),
                SalesRecord.is_refunded == False,
                tuple_(SalesRecord.category_name, SalesRecord.subcategory_name).in_(subcategory_keys)
            )
            .group_by(SalesRecord.category_name, SalesRecord.subcategory_name, SalesRecord.sale_date)
            .order_by(SalesRecord.sale_date.desc())
        )

        result_daily = await session_execute(stmt_daily, session)
        daily_sales = result_daily.all()

        # Map daily sales to subcategories
        daily_by_subcategory = {}
        for row in daily_sales:
            key = (row.category_name, row.subcategory_name)
            if key not in daily_by_subcategory:
                daily_by_subcategory[key] = []
            daily_by_subcategory[key].append({
                'date': row.sale_date,
                'quantity': int(row.quantity),
                'revenue': float(row.revenue)
            })

        # Populate 'sales' field in result structure
        for subcat_data in subcategory_list:
            key = (subcat_data['category'], subcat_data['subcategory'])
            subcat_data['sales'] = daily_by_subcategory.get(key, [])

        return subcategory_list

    @staticmethod
    async def get_subcategory_count(
        start_date: datetime,
        end_date: datetime,
        session: AsyncSession | Session
    ) -> int:
        """
        Get count of distinct subcategories with sales in date range.

        Uses subquery approach for database-agnostic DISTINCT counting
        (works on SQLite, PostgreSQL, MySQL).

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            session: Database session

        Returns:
            Count of distinct (category_name, subcategory_name) combinations
        """
        from sqlalchemy import func

        # Subquery: Get all distinct (category_name, subcategory_name) combinations
        distinct_subquery = (
            select(
                SalesRecord.category_name,
                SalesRecord.subcategory_name
            )
            .where(
                SalesRecord.sale_date >= start_date.date(),
                SalesRecord.sale_date <= end_date.date(),
                SalesRecord.is_refunded == False
            )
            .distinct()
            .subquery()
        )

        # Count rows in subquery (DB-agnostic)
        stmt = select(func.count()).select_from(distinct_subquery)

        result = await session_execute(stmt, session)
        return result.scalar() or 0

    @staticmethod
    async def get_all_sales_for_csv(session: AsyncSession | Session) -> list[SalesRecord]:
        """
        Get ALL sales records for CSV export (no pagination, no date filter).

        Args:
            session: Database session

        Returns:
            List of all SalesRecord objects, sorted by sale_date DESC
        """
        stmt = select(SalesRecord).order_by(SalesRecord.sale_date.desc())

        result = await session_execute(stmt, session)
        return result.scalars().all()

    @staticmethod
    async def mark_items_as_refunded(
        order_id: int,
        items: list,
        session: AsyncSession | Session
    ) -> int:
        """
        Update is_refunded flag for specific items in an order.

        Uses order_hash to precisely identify records belonging to this order,
        preventing incorrect refund marking of other orders on the same day.

        Args:
            order_id: Order ID (used to generate order_hash)
            items: List of ItemDTOs to mark as refunded
            session: Database session

        Returns:
            Number of SalesRecords updated
        """
        import hashlib
        from repositories.order import OrderRepository
        from repositories.subcategory import SubcategoryRepository
        from repositories.category import CategoryRepository

        # Get order to generate order_hash
        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            return 0

        # Generate same order_hash as when records were created
        order_identifier = f"{order_id}_{order.created_at.isoformat()}"
        order_hash = hashlib.sha256(order_identifier.encode()).hexdigest()

        # Build list of (category_name, subcategory_name) tuples for this order
        items_to_refund = []
        for item in items:
            subcategory = await SubcategoryRepository.get_by_id(item.subcategory_id, session)
            if subcategory:
                category = await CategoryRepository.get_by_id(subcategory.category_id, session)
                if category:
                    items_to_refund.append({
                        'category_name': category.name,
                        'subcategory_name': subcategory.name,
                        'quantity': 1
                    })

        # Update SalesRecords using order_hash for precise targeting
        updated_count = 0
        for item_info in items_to_refund:
            stmt = (
                update(SalesRecord)
                .where(
                    SalesRecord.order_hash == order_hash,
                    SalesRecord.category_name == item_info['category_name'],
                    SalesRecord.subcategory_name == item_info['subcategory_name'],
                    SalesRecord.is_refunded == False
                )
                .values(is_refunded=True)
                .execution_options(synchronize_session="fetch")
            )
            result = await session_execute(stmt, session)
            updated_count += result.rowcount

        return updated_count