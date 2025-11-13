"""
Analytics Service - Helper for creating anonymized sales records

This service creates SalesRecord and ViolationStatistics entries
for long-term analytics while removing user identification (data minimization).
"""

import logging
import hashlib
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from models.sales_record import SalesRecordDTO
from models.violation_statistics import ViolationStatisticsDTO
from repositories.sales_record import SalesRecordRepository
from repositories.violation_statistics import ViolationStatisticsRepository
from repositories.order import OrderRepository
from repositories.item import ItemRepository
from repositories.category import CategoryRepository
from repositories.subcategory import SubcategoryRepository
from repositories.payment_transaction import PaymentTransactionRepository
from enums.violation_type import ViolationType
from db import session_commit


class AnalyticsService:
    """Service for creating anonymized analytics records"""

    @staticmethod
    async def create_sales_records_from_order(
        order_id: int,
        session: AsyncSession | Session
    ) -> list[int]:
        """
        Create anonymized SalesRecord entries for all items in an order.

        This is called immediately when an order is completed (PAID status).
        Creates one SalesRecord per item for granular analytics.

        Args:
            order_id: Order ID
            session: Database session

        Returns:
            List of created SalesRecord IDs
        """
        # Get order data
        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            logging.warning(f"[Analytics] Order {order_id} not found, cannot create sales records")
            return []

        # Get items
        items = await ItemRepository.get_by_order_id(order_id, session)
        if not items:
            logging.warning(f"[Analytics] Order {order_id} has no items, cannot create sales records")
            return []

        # Get payment transactions to determine payment method
        transactions = await PaymentTransactionRepository.get_by_order_id(order_id, session)

        # Determine payment method
        if order.wallet_used > 0 and transactions:
            payment_method = "mixed"
            crypto_currency = transactions[0].crypto_currency if transactions else None
        elif order.wallet_used > 0 and not transactions:
            payment_method = "wallet_only"
            crypto_currency = None
        elif transactions:
            payment_method = "crypto_only"
            crypto_currency = transactions[0].crypto_currency if transactions else None
        else:
            payment_method = None
            crypto_currency = None

        # Get shipping type (if physical items)
        # NOTE: shipping_type field not yet implemented in schema, defaulting to None
        shipping_type = None

        # Current time for temporal data
        now = datetime.utcnow()

        # Generate pseudonymized order hash for refund tracking
        # Uses SHA256(order_id + created_at) to enable refund matching without storing actual order_id
        order_identifier = f"{order_id}_{order.created_at.isoformat()}"
        order_hash = hashlib.sha256(order_identifier.encode()).hexdigest()

        # Create SalesRecord for each item
        sales_record_dtos = []
        for item in items:
            # Get category and subcategory names
            category = await CategoryRepository.get_by_id(item.category_id, session)
            subcategory = await SubcategoryRepository.get_by_id(item.subcategory_id, session)

            if not category or not subcategory:
                logging.warning(f"[Analytics] Item {item.id} missing category/subcategory, skipping")
                continue

            # Calculate item total price (item.price is the unit price for this item)
            # For tier pricing, we could parse tier_breakdown_json, but for simplicity
            # we use the item's individual price
            item_total = item.price  # This is already the calculated price for this item

            sales_record_dto = SalesRecordDTO(
                # Temporal data
                sale_date=now,
                sale_hour=now.hour,
                sale_weekday=now.weekday(),
                # Item details
                category_name=category.name,
                subcategory_name=subcategory.name,
                quantity=1,  # Each item is a separate record with quantity=1
                is_physical=item.is_physical,
                # Financial data
                item_total_price=item_total,
                currency=order.currency,
                average_unit_price=item_total,  # Same as total for quantity=1
                tier_breakdown_json=order.tier_breakdown_json if order.tier_breakdown_json else None,
                # Order-level data (denormalized)
                order_hash=order_hash,  # Pseudonymized identifier for refund tracking
                order_total_price=order.total_price,
                order_shipping_cost=order.shipping_cost,
                order_wallet_used=order.wallet_used,
                # Payment details
                payment_method=payment_method,
                crypto_currency=crypto_currency,
                # Status
                status=order.status,
                is_refunded=False,  # Not refunded at creation time
                # Shipping
                shipping_type=shipping_type
            )
            sales_record_dtos.append(sales_record_dto)

        # Create all sales records
        created_ids = await SalesRecordRepository.create_many(sales_record_dtos, session)
        logging.info(f"[Analytics] ✅ Created {len(created_ids)} SalesRecord entries for order {order_id}")

        return created_ids

    @staticmethod
    async def create_violation_record(
        order_id: int,
        violation_type: 'ViolationType',
        session: AsyncSession | Session,
        penalty_applied: float = 0.0
    ) -> int | None:
        """
        Create anonymized ViolationStatistics entry for order violations.

        Args:
            order_id: Order ID
            violation_type: Type of violation (ViolationType enum)
            penalty_applied: Penalty amount (default 0.0)
            session: Database session

        Returns:
            Created ViolationStatistics ID or None if order not found
        """
        # Get order data
        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            logging.warning(f"[Analytics] Order {order_id} not found, cannot create violation record")
            return None

        # Create violation record
        violation_dto = ViolationStatisticsDTO(
            violation_date=datetime.utcnow(),
            violation_type=violation_type,
            order_value=order.total_price,
            penalty_applied=penalty_applied,
            retry_count=order.retry_count if hasattr(order, 'retry_count') else 0
        )

        violation_id = await ViolationStatisticsRepository.create(violation_dto, session)
        logging.info(f"[Analytics] ✅ Created ViolationStatistics entry (type={violation_type}, order={order_id}, penalty={penalty_applied})")

        return violation_id

    @staticmethod
    async def get_subcategory_sales_data(
        days: int,
        page: int,
        session: AsyncSession | Session
    ) -> dict:
        """
        Get subcategory sales breakdown data (pure data, no UI).

        Args:
            days: Time range (7, 30, 90)
            page: Page number (0-indexed)
            session: Database session

        Returns:
            dict with structure:
            {
                'subcategories': [
                    {
                        'category': str,
                        'subcategory': str,
                        'sales_by_date': [
                            {'date': 'DD.MM', 'quantity': int, 'revenue': float},
                            ...
                        ],
                        'total_quantity': int,
                        'total_revenue': float
                    },
                    ...
                ],
                'current_page': int,
                'max_page': int,
                'date_range': {
                    'start': datetime.date,
                    'end': datetime.date,
                    'days': int
                },
                'total_subcategories': int
            }
        """
        import config

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get grouped data from repository
        grouped_data = await SalesRecordRepository.get_subcategory_sales_grouped(
            start_date=start_date,
            end_date=end_date,
            page=page,
            session=session
        )

        # Get total count for max_page calculation
        total_count = await SalesRecordRepository.get_subcategory_count(
            start_date=start_date,
            end_date=end_date,
            session=session
        )

        # Calculate max_page
        if total_count == 0:
            max_page = 0
        elif total_count % config.PAGE_ENTRIES == 0:
            max_page = (total_count // config.PAGE_ENTRIES) - 1
        else:
            max_page = total_count // config.PAGE_ENTRIES

        # Format dates to 'DD.MM' for display
        for subcat in grouped_data:
            for sale in subcat['sales']:
                # Convert datetime.date to 'DD.MM' string
                sale['date'] = sale['date'].strftime('%d.%m')

        return {
            'subcategories': grouped_data,
            'current_page': page,
            'max_page': max_page,
            'date_range': {
                'start': start_date.date(),
                'end': end_date.date(),
                'days': days
            },
            'total_subcategories': total_count
        }

    @staticmethod
    async def generate_sales_csv_content(session: AsyncSession | Session) -> str:
        """
        Generate CSV content string for all sales records.

        Args:
            session: Database session

        Returns:
            str: CSV content (ready to write to BufferedInputFile)

        Format:
            date,hour,weekday,category,subcategory,quantity,is_physical,
            item_total_price,currency,payment_method,crypto_currency,status
        """
        import csv
        from io import StringIO

        # Get all sales records
        all_sales = await SalesRecordRepository.get_all_sales_for_csv(session)

        # Build CSV using csv module with QUOTE_ALL for security
        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)

        # Write header
        writer.writerow([
            'date', 'hour', 'weekday', 'category', 'subcategory', 'quantity',
            'is_physical', 'item_total_price', 'currency', 'payment_method',
            'crypto_currency', 'status'
        ])

        # Write data rows
        for sale in all_sales:
            writer.writerow([
                str(sale.sale_date),
                str(sale.sale_hour),
                str(sale.sale_weekday),
                sale.category_name,
                sale.subcategory_name,
                str(sale.quantity),
                str(sale.is_physical),
                str(sale.item_total_price),
                sale.currency.value if hasattr(sale.currency, 'value') else str(sale.currency),
                sale.payment_method or '',
                sale.crypto_currency or '',
                sale.status.value if hasattr(sale.status, 'value') else str(sale.status)
            ])

        return output.getvalue()

    @staticmethod
    async def mark_items_as_refunded(
        order_id: int,
        items: list,
        session: AsyncSession | Session
    ) -> int:
        """
        Mark specific items as refunded in SalesRecords for accurate analytics.

        Called when an order is cancelled after PAID status (partial refund scenario).
        Updates is_refunded flag to exclude these items from revenue calculations.

        Args:
            order_id: Order ID
            items: List of ItemDTOs to mark as refunded
            session: Database session

        Returns:
            Number of SalesRecords updated
        """
        from repositories.sales_record import SalesRecordRepository
        return await SalesRecordRepository.mark_items_as_refunded(order_id, items, session)
