"""
Analytics v2 Admin Handler

Provides admin interface for viewing anonymized sales and violation statistics.
"""

from datetime import datetime
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import AnalyticsV2Callback
from enums.bot_entity import BotEntity
from services.admin import AdminService
from services.analytics import AnalyticsService
from utils.custom_filters import AdminIdFilter
from utils.localizator import Localizator

analytics_v2 = Router()


async def analytics_v2_menu(**kwargs):
    """Display Analytics v2 main menu."""
    callback = kwargs.get("callback")
    state = kwargs.get("state")
    await state.clear()
    msg, kb_builder = await AdminService.get_analytics_v2_menu()
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def analytics_v2_timedelta_picker(**kwargs):
    """Display timedelta picker menu."""
    callback = kwargs.get("callback")
    msg, kb_builder = await AdminService.get_analytics_v2_timedelta_menu(callback)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def analytics_v2_display_data(**kwargs):
    """Display analytics data."""
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    msg, kb_builder = await AdminService.get_analytics_v2_data(callback, session)
    await callback.message.edit_text(text=msg, reply_markup=kb_builder.as_markup())


async def sales_analytics_overview(**kwargs):
    """
    Level 11: Sales Analytics time range selection.

    Shows buttons: [Last 7 Days] [Last 30 Days] [Last 90 Days] [Back]
    """
    callback = kwargs.get("callback")

    # Build keyboard (Handler responsibility!)
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text="Last 7 Days",
        callback_data=AnalyticsV2Callback.create(level=12, days=7, page=0).pack()
    )
    kb_builder.button(
        text="Last 30 Days",
        callback_data=AnalyticsV2Callback.create(level=12, days=30, page=0).pack()
    )
    kb_builder.button(
        text="Last 90 Days",
        callback_data=AnalyticsV2Callback.create(level=12, days=90, page=0).pack()
    )
    kb_builder.button(
        text=Localizator.get_text(BotEntity.ADMIN, "back_to_analytics_menu"),
        callback_data=AnalyticsV2Callback.create(level=0).pack()
    )
    kb_builder.adjust(1)

    await callback.message.edit_text(
        Localizator.get_text(BotEntity.ADMIN, "sales_analytics_overview"),
        reply_markup=kb_builder.as_markup()
    )


async def subcategory_report_view(**kwargs):
    """
    Level 12: Subcategory sales report (paginated).

    Displays subcategories sorted by revenue with daily breakdown.
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")
    callback_data = AnalyticsV2Callback.unpack(callback.data)

    # Get data from service (pure data!)
    data = await AnalyticsService.get_subcategory_sales_data(
        days=callback_data.days,
        page=callback_data.page,
        session=session
    )

    # Handler builds message text
    msg_text = _format_subcategory_report(data)

    # Handler builds keyboard
    kb_builder = _build_subcategory_keyboard(data, callback_data.days)

    await callback.message.edit_text(msg_text, reply_markup=kb_builder.as_markup())


async def export_sales_csv(**kwargs):
    """
    Level 13: Export all sales records as CSV file.

    Generates CSV and sends as Telegram Document.
    """
    callback = kwargs.get("callback")
    session = kwargs.get("session")

    # Show loading message
    await callback.message.edit_text(
        Localizator.get_text(BotEntity.ADMIN, "csv_generating")
    )

    # Get CSV content from service
    csv_content = await AnalyticsService.generate_sales_csv_content(session)

    # Convert to bytes for Telegram
    csv_file = BufferedInputFile(
        csv_content.encode('utf-8'),
        filename=f"sales_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    # Send file
    await callback.message.answer_document(
        document=csv_file,
        caption=Localizator.get_text(BotEntity.ADMIN, "csv_export_complete")
    )

    # Return to sales analytics overview
    await sales_analytics_overview(callback=callback)


# Helper functions (handler-level)

def _format_subcategory_report(data: dict) -> str:
    """Format subcategory data to message text (German)."""
    msg = f"📊 Subcategory Sales Report - Last {data['date_range']['days']} Days\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if not data['subcategories']:
        return msg + Localizator.get_text(BotEntity.ADMIN, "no_sales_found")

    for subcat in data['subcategories']:
        # Category emoji (based on category name)
        emoji = _get_category_emoji(subcat['category'])

        msg += f"{emoji} {subcat['category']} > {subcat['subcategory']}\n"

        # Daily breakdown (only days with sales!)
        for sale in subcat['sales']:
            msg += f"  {sale['date']}: {sale['quantity']} Stück ({sale['revenue']:,.2f} €)\n"

        # Subtotal
        msg += f"  Gesamt: {subcat['total_quantity']} Stück ({subcat['total_revenue']:,.2f} €)\n\n"

    # Pagination info
    msg += f"[Seite {data['current_page'] + 1} von {data['max_page'] + 1}]"

    return msg


def _build_subcategory_keyboard(data: dict, days: int) -> InlineKeyboardBuilder:
    """Build keyboard with pagination and navigation."""
    kb_builder = InlineKeyboardBuilder()

    # Pagination buttons
    pagination_row = []
    if data['current_page'] > 0:
        pagination_row.append(
            ("◀ Zurück", AnalyticsV2Callback.create(
                level=12, days=days, page=data['current_page'] - 1
            ).pack())
        )

    if data['current_page'] < data['max_page']:
        pagination_row.append(
            ("Weiter ▶", AnalyticsV2Callback.create(
                level=12, days=days, page=data['current_page'] + 1
            ).pack())
        )

    # Add pagination buttons if any
    for text, callback_data in pagination_row:
        kb_builder.button(text=text, callback_data=callback_data)

    # CSV Export button
    kb_builder.button(
        text="📄 CSV Export",
        callback_data=AnalyticsV2Callback.create(level=13).pack()
    )

    # Back to overview
    kb_builder.button(
        text="🔙 Zurück zur Übersicht",
        callback_data=AnalyticsV2Callback.create(level=11).pack()
    )

    # Adjust layout: 2 buttons in first row (pagination), rest 1 per row
    if len(pagination_row) > 0:
        kb_builder.adjust(len(pagination_row), 1, 1)
    else:
        kb_builder.adjust(1, 1)

    return kb_builder


def _get_category_emoji(category_name: str) -> str:
    """Map category name to emoji."""
    emoji_map = {
        'Electronics': '📱',
        'Clothing': '👕',
        'Books': '📚',
        'Food': '🍔',
        'Digital': '💾',
        'Gaming': '🎮',
        'Sports': '⚽',
        'Home': '🏠',
        'Beauty': '💄',
        'Toys': '🧸',
    }
    return emoji_map.get(category_name, '📦')


@analytics_v2.callback_query(AdminIdFilter(), AnalyticsV2Callback.filter())
async def analytics_v2_navigation(
    callback: CallbackQuery,
    state: FSMContext,
    callback_data: AnalyticsV2Callback,
    session: AsyncSession | Session
):
    """Route Analytics v2 navigation based on level."""
    current_level = callback_data.level

    levels = {
        0: analytics_v2_menu,
        1: analytics_v2_timedelta_picker,
        2: analytics_v2_display_data,
        11: sales_analytics_overview,
        12: subcategory_report_view,
        13: export_sales_csv,
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "state": state,
        "session": session,
    }

    await current_level_function(**kwargs)
