# Admin Order Detail Overview

**Priority:** 🟡 Medium
**Estimated Effort:** Low-Medium (1-1.5 hours)
**Created:** 2025-10-23

## Description

Enhance the existing "Buys Statistics" section in the admin panel to show a detailed, paginated list of individual orders with all relevant information, not just aggregate totals.

## Current State

The existing statistics show only:
- Total Revenue (sum)
- Items Sold (count)
- Buys Count (number of orders)

**Missing:** Detailed list of individual orders with product names, quantities, dates, and invoice numbers.

## User Story

As a shop administrator, I want to see a detailed list of all orders from the last 30 days (or selected timeframe), so that I can monitor sales, identify trends, and provide customer support.

## Acceptance Criteria

- [ ] Extend existing `StatisticsEntity.BUYS` view to show order details
- [ ] Display format includes:
  - Invoice Number (2025-ABCDEF)
  - Date & Time (YYYY-MM-DD HH:MM)
  - Product Name (Subcategory)
  - Quantity
  - Total Price
  - Status (PAID, SHIPPED, etc.)
- [ ] Orders sorted by date (newest first)
- [ ] Paginated list (8 orders per page)
- [ ] Summary header with totals:
  - Total Revenue
  - Total Orders
  - Items Sold
- [ ] Optional: Group by day with daily subtotals
- [ ] Filter by timeframe (1 day, 7 days, 30 days) - already exists
- [ ] Privacy: NO user IDs, telegram usernames, or personal data shown
- [ ] Works with existing data retention period (only shows orders within DATA_RETENTION_DAYS)

## Display Format Example

```
📊 Sales Statistics (Last 30 Days)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Total Revenue: €1,234.56
🛍️ Total Orders: 47
📦 Items Sold: 123

📅 Recent Orders (Page 1/6):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 #2025-ABC123
🕐 2025-10-23 14:30
🛒 Green Tea | 10 pc
💵 €75.00 | ✅ PAID

📋 #2025-DEF456
🕐 2025-10-23 12:15
🛒 Premium eBook | 1 pc
💵 €9.99 | ✅ PAID

📋 #2025-GHI789
🕐 2025-10-23 10:45
🛒 Organic Coffee | 5 pc
💵 €42.50 | ✅ PAID

[< Page 1/6 >]
[🏠 Main Menu] [↩️ Back]
```

## Technical Notes

### Extend AdminService.get_statistics()

```python
# services/admin.py
case StatisticsEntity.BUYS:
    # Get paginated orders
    orders = await OrderRepository.get_by_timedelta_paginated(
        unpacked_cb.timedelta,
        unpacked_cb.page,
        session
    )

    # Calculate totals
    all_orders = await OrderRepository.get_by_timedelta(unpacked_cb.timedelta, session)
    total_revenue = sum(order.total_price for order in all_orders)
    total_orders = len(all_orders)
    items_sold = await ItemRepository.count_sold_by_timedelta(unpacked_cb.timedelta, session)

    # Build message with order details
    message = Localizator.get_text(BotEntity.ADMIN, "sales_statistics_header").format(
        timedelta=unpacked_cb.timedelta.value,
        total_revenue=total_revenue,
        total_orders=total_orders,
        items_sold=items_sold,
        currency_sym=Localizator.get_currency_symbol()
    )

    message += "\n\n📅 Recent Orders:\n" + "━" * 30 + "\n\n"

    for order in orders:
        invoice = await InvoiceRepository.get_by_order_id(order.id, session)
        items = await ItemRepository.get_by_order_id(order.id, session)

        # Get product name from first item (simplified, could be enhanced)
        first_item = items[0] if items else None
        if first_item:
            subcategory = await SubcategoryRepository.get_by_id(first_item.subcategory_id, session)
            product_name = subcategory.name
        else:
            product_name = "Unknown"

        message += Localizator.get_text(BotEntity.ADMIN, "order_detail_line").format(
            invoice_number=invoice.invoice_number if invoice else f"#{order.id}",
            date=order.created_at.strftime("%Y-%m-%d %H:%M"),
            product=product_name,
            quantity=len(items),
            total=order.total_price,
            status=order.status.value,
            currency_sym=Localizator.get_currency_symbol()
        )
        message += "\n"

    # Add pagination
    kb_builder = await add_pagination_buttons(
        kb_builder,
        unpacked_cb,
        OrderRepository.get_max_page_by_timedelta(unpacked_cb.timedelta, session),
        None
    )
    kb_builder.row(AdminConstants.back_to_main_button, unpacked_cb.get_back_button())

    return message, kb_builder
```

### New Repository Methods

```python
# repositories/order.py
@staticmethod
async def get_by_timedelta_paginated(
    timedelta: StatisticsTimeDelta,
    page: int,
    session: AsyncSession
) -> list[Order]:
    """
    Get orders within timedelta, paginated.
    """
    cutoff_date = datetime.utcnow() - datetime.timedelta(days=timedelta.value)

    stmt = (
        select(Order)
        .where(
            Order.created_at >= cutoff_date,
            Order.status.in_([OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED])
        )
        .order_by(Order.created_at.desc())
        .offset(page * config.PAGE_ENTRIES)
        .limit(config.PAGE_ENTRIES)
    )

    result = await session.execute(stmt)
    return result.scalars().all()

@staticmethod
async def get_max_page_by_timedelta(timedelta: StatisticsTimeDelta, session: AsyncSession) -> int:
    """
    Get max page number for paginated orders.
    """
    cutoff_date = datetime.utcnow() - datetime.timedelta(days=timedelta.value)

    stmt = (
        select(func.count(Order.id))
        .where(
            Order.created_at >= cutoff_date,
            Order.status.in_([OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED])
        )
    )

    result = await session.execute(stmt)
    count = result.scalar()
    return ceil(count / config.PAGE_ENTRIES)
```

### Localization Keys

```json
// de.json
{
  "sales_statistics_header": "📊 <b>Verkaufsstatistiken ({timedelta} Tage)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 Gesamtumsatz: {currency_sym}{total_revenue:.2f}\n🛍️ Bestellungen: {total_orders}\n📦 Verkaufte Artikel: {items_sold}",

  "order_detail_line": "📋 <b>{invoice_number}</b>\n🕐 {date}\n🛒 {product} | {quantity} Stk.\n💵 {currency_sym}{total:.2f} | {status}"
}

// en.json
{
  "sales_statistics_header": "📊 <b>Sales Statistics ({timedelta} days)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💰 Total Revenue: {currency_sym}{total_revenue:.2f}\n🛍️ Orders: {total_orders}\n📦 Items Sold: {items_sold}",

  "order_detail_line": "📋 <b>{invoice_number}</b>\n🕐 {date}\n🛒 {product} | {quantity} pc\n💵 {currency_sym}{total:.2f} | {status}"
}
```

## Privacy & Data Minimization

**Included:**
- ✅ Invoice numbers (for support)
- ✅ Dates
- ✅ Product names
- ✅ Quantities
- ✅ Prices
- ✅ Status

**Excluded (GDPR):**
- ❌ User IDs
- ❌ Telegram usernames
- ❌ Telegram IDs
- ❌ Shipping addresses
- ❌ Any personal identifiable information

This follows the principle of data minimization - admin only needs sales data, not customer identity.

## Optional Enhancements (Future)

- [ ] Filter by status (PAID only, SHIPPED only, etc.)
- [ ] Filter by product category
- [ ] Export to CSV
- [ ] Daily/Weekly grouping with subtotals
- [ ] Chart visualization (sales trend)

## Related

- Extends existing Statistics Section
- Uses existing `StatisticsCallback` and `StatisticsTimeDelta`
- Respects `DATA_RETENTION_DAYS` (only shows recent orders)
- Complements Data Retention Cleanup Job
