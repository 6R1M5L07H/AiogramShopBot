"""
Invoice Formatter Service

Centralized invoice/order formatting to eliminate code duplication.
Used across:
- Admin order views
- User payment screens
- Cancellation notifications
- Purchase history
"""

from typing import Optional
from datetime import datetime
from enums.bot_entity import BotEntity
from enums.invoice_header_type import InvoiceHeaderType
from enums.order_status import OrderStatus
from utils.localizator import Localizator
from utils.html_escape import safe_html, safe_url


class InvoiceFormatterService:
    """Centralized invoice formatting service"""

    @staticmethod
    def _format_private_data(private_data: str) -> str:
        """
        Format private_data based on its content type.

        Args:
            private_data: Raw private data string

        Returns:
            Formatted HTML string (always escaped to prevent XSS)
        """
        # Check if private_data is a URL (for Telegram deep links)
        if private_data.startswith(('http://', 'https://', 't.me/')):
            # Render as clickable link with URL sanitization
            if private_data.startswith('t.me/'):
                private_data = f"https://{private_data}"
            sanitized_url = safe_url(private_data)
            if not sanitized_url:
                # Invalid URL - render as escaped text
                return f"   <code>{safe_html(private_data)}</code>\n"
            return f"   <a href=\"{sanitized_url}\">📱 Beratung starten</a>\n"
        else:
            # Render as code (for vouchers, keys, etc.) with HTML escaping
            # Always escape to prevent XSS, even for admin-controlled data
            return f"   <code>{safe_html(private_data)}</code>\n"

    @staticmethod
    def _format_items_section(
        items: list,
        section_label: str,
        currency_symbol: str,
        show_private_data: bool,
        entity: BotEntity
    ) -> str:
        """
        Format a section of items (digital or physical).

        Args:
            items: List of item dicts (with optional 'unit' field)
            section_label: Section header (e.g., "Digital Items:")
            currency_symbol: Currency symbol
            show_private_data: Whether to show private_data
            entity: BotEntity for localization

        Returns:
            Formatted HTML string
        """
        if not items:
            return ""

        message = f"<b>{section_label}:</b>\n"

        for item in items:
            # Get and localize unit (fallback to "pcs." if not present)
            unit = item.get('unit', 'pcs.')
            localized_unit = Localizator.localize_unit(unit)

            # For admin view: Extract only first line (product name) from item description
            # For user view: Show full description (with HTML formatting)
            item_name = item['name']
            if entity == BotEntity.ADMIN:
                # Admin needs compact view - only first line (usually product name)
                item_name = item_name.split('\n')[0].strip()

            # Check if item has tier breakdown
            if item.get('tier_breakdown'):
                # For tiered items, show tier breakdown with proper formatting
                # Calculate total from tier breakdown
                line_total = sum(tier['total'] for tier in item['tier_breakdown'])

                # Build tier breakdown display
                tier_parts = []
                for tier in item['tier_breakdown']:
                    tier_unit_price = tier['unit_price']
                    tier_quantity = tier['quantity']
                    tier_total = tier['total']
                    tier_parts.append(f"{currency_symbol}{tier_unit_price:.2f} × {tier_quantity}")

                tier_display = " + ".join(tier_parts)

                # NOTE: Item names are admin-controlled (from database), so HTML rendering is allowed
                message += f"{item['quantity']} {localized_unit} {item_name}\n"
                message += f"  ({tier_display} = {currency_symbol}{line_total:.2f})\n"
            else:
                # Flat pricing (no tier breakdown) - item name is admin-controlled, allow HTML
                line_total = item['price'] * item['quantity']
                if item['quantity'] == 1:
                    message += f"{item['quantity']} {localized_unit} {item_name} {currency_symbol}{item['price']:.2f}\n"
                else:
                    message += f"{item['quantity']} {localized_unit} {item_name} {currency_symbol}{item['price']:.2f} = {currency_symbol}{line_total:.2f}\n"

            # Show private data if applicable
            if show_private_data and item.get('private_data'):
                message += InvoiceFormatterService._format_private_data(item['private_data'])

        message += "\n"
        return message

    @staticmethod
    def format_items_list(
        items_dict: dict,
        currency_symbol: str,
        show_line_totals: bool = True,
        entity: BotEntity = BotEntity.USER
    ) -> tuple[str, float]:
        """
        Format items list with optional line totals.

        Args:
            items_dict: Dict of {(name, price): quantity}
            currency_symbol: Currency symbol (e.g., "€")
            show_line_totals: Show line totals for qty > 1
            entity: BotEntity for localization

        Returns:
            Tuple of (formatted_string, total_amount)
        """
        items_text = ""
        total = 0.0
        qty_unit = Localizator.get_text(BotEntity.COMMON, "quantity_unit_short")

        for (name, price), qty in items_dict.items():
            # Escape item name to prevent HTML injection
            name_escaped = safe_html(name)
            line_total = price * qty
            total += line_total

            if qty == 1 or not show_line_totals:
                items_text += f"{qty} {qty_unit} {name_escaped} {currency_symbol}{price:.2f}\n"
            else:
                items_text += f"{qty} {qty_unit} {name_escaped} {currency_symbol}{price:.2f} = {currency_symbol}{line_total:.2f}\n"

        return items_text, total

    @staticmethod
    def format_items_with_tier_breakdown(
        item_name: str,
        tier_breakdown: list[dict],
        currency_symbol: str = "€",
        entity: BotEntity = BotEntity.USER
    ) -> tuple[str, float]:
        """
        Format items list with tier breakdown display.

        Args:
            item_name: Name of the item
            tier_breakdown: List of dicts with keys: quantity, unit_price, total
                           Example: [{"quantity": 10, "unit_price": 9.00, "total": 90.00}]
            currency_symbol: Currency symbol
            entity: BotEntity for localization

        Returns:
            Tuple of (formatted_string, total_amount)

        Example output:
            USB-Stick SanDisk 32GB
            Tier Pricing: (or Staffelpreise: in German)
             10 ×  9,00 € =   90,00 €
              5 × 10,00 € =   50,00 €
              2 × 11,00 € =   22,00 €
            ───────────────────────────
                       Σ  162,00 €
        """
        tier_label = Localizator.get_text(BotEntity.COMMON, "tier_breakdown_label")

        lines = [f"<b>{safe_html(item_name)}</b>"]
        lines.append(f"<b>{tier_label}:</b>")

        total = 0.0
        for item in tier_breakdown:
            qty = item["quantity"]
            unit_price = item["unit_price"]
            line_total = item["total"]
            total += line_total

            qty_str = f"{qty:>3}"
            price_str = f"{unit_price:>6.2f}"
            total_str = f"{line_total:>8.2f}"
            lines.append(f" {qty_str} × {price_str} {currency_symbol} = {total_str} {currency_symbol}")

        # Separator
        lines.append("─" * 30)

        # Total
        total_str = f"{total:>8.2f}"
        lines.append(f"{'':>17}Σ {total_str} {currency_symbol}")

        return "\n".join(lines), total

    @staticmethod
    def _format_shipping_line_with_free(
        shipping_cost: float,
        currency_symbol: str,
        entity: BotEntity = BotEntity.USER
    ) -> str:
        """
        Format shipping line with proper handling of free shipping.

        Args:
            shipping_cost: Shipping cost (can be 0)
            currency_symbol: Currency symbol
            entity: BotEntity for localization

        Returns:
            Formatted shipping line with <code> tags
        """
        qty_unit = Localizator.get_text(BotEntity.COMMON, "quantity_unit_short")
        shipping_label = Localizator.get_text(BotEntity.COMMON, "shipping_label")

        if shipping_cost == 0:
            free_label = Localizator.get_text(BotEntity.USER, "shipping_cost_free")
            return f"<code>1 {qty_unit} {shipping_label:<20}{free_label:>8}\n</code>"
        else:
            return f"<code>1 {qty_unit} {shipping_label:<20}{shipping_cost:>8.2f}{currency_symbol}\n</code>"

    @staticmethod
    def _format_subtotal_line(
        label: str,
        amount: float,
        currency_symbol: str
    ) -> str:
        """
        Format a subtotal line with separator and monospace alignment.

        Args:
            label: Label for the subtotal
            amount: Amount to display
            currency_symbol: Currency symbol

        Returns:
            Formatted subtotal section with separators
        """
        lines = []
        lines.append("─" * 30 + "\n")
        lines.append("<code>")
        lines.append(f"{label:<27}{amount:>8.2f}{currency_symbol}\n")
        lines.append("</code>")
        lines.append("─" * 30 + "\n\n")
        return "".join(lines)

    @staticmethod
    def format_order_invoice(
        invoice_number: str,
        digital_items: Optional[dict] = None,
        physical_items: Optional[dict] = None,
        shipping_cost: float = 0.0,
        total_price: float = 0.0,
        wallet_used: float = 0.0,
        crypto_payment_needed: float = 0.0,
        currency_symbol: str = "€",
        show_digital_section: bool = True,
        show_physical_section: bool = True,
        show_wallet_line: bool = True,
        show_shipping: bool = True,
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
        entity: BotEntity = BotEntity.USER
    ) -> str:
        """
        Format complete order invoice with configurable sections.

        Args:
            invoice_number: Invoice/order reference number
            digital_items: Dict of {(name, price): qty} for digital items
            physical_items: Dict of {(name, price): qty} for physical items
            shipping_cost: Shipping cost amount
            total_price: Total order price
            wallet_used: Amount paid from wallet
            crypto_payment_needed: Remaining amount for crypto payment
            currency_symbol: Currency symbol
            show_digital_section: Show digital items section
            show_physical_section: Show physical items section
            show_wallet_line: Show wallet usage line
            show_shipping: Show shipping cost line
            header_text: Custom header (default: Invoice number)
            footer_text: Custom footer text
            entity: BotEntity for localization

        Returns:
            Formatted invoice string
        """
        message = ""

        # Header
        if header_text:
            message += f"{header_text}\n\n"
        else:
            message += f"<b>Invoice #{invoice_number}</b>\n\n"

        # Digital items section
        if show_digital_section and digital_items:
            digital_label = Localizator.get_text(BotEntity.COMMON, "digital_items_label")
            message += f"<b>{digital_label}:</b>\n"
            items_text, digital_total = InvoiceFormatterService.format_items_list(
                digital_items, currency_symbol, entity=entity
            )
            message += items_text
            message += "\n"

        # Physical items section
        if show_physical_section and physical_items:
            physical_label = Localizator.get_text(BotEntity.COMMON, "physical_items_label")
            message += f"<b>{physical_label}:</b>\n"
            items_text, physical_total = InvoiceFormatterService.format_items_list(
                physical_items, currency_symbol, entity=entity
            )
            message += items_text
            message += "\n"

        # Price breakdown
        message += "═══════════════════════\n"

        # Shipping line
        if show_shipping and shipping_cost > 0:
            shipping_label = Localizator.get_text(BotEntity.COMMON, "shipping_label")
            message += f"{shipping_label} {currency_symbol}{shipping_cost:.2f}\n"

        # Wallet usage line
        if show_wallet_line and wallet_used > 0:
            wallet_label = Localizator.get_text(BotEntity.USER, "wallet_balance_label")
            message += f"{wallet_label} -{currency_symbol}{wallet_used:.2f}\n"

        # Total
        if crypto_payment_needed > 0:
            amount_due_label = Localizator.get_text(BotEntity.USER, "amount_due_label")
            message += f"\n<b>{amount_due_label}: {currency_symbol}{crypto_payment_needed:.2f}</b>\n"
        else:
            message += f"\n<b>Total: {currency_symbol}{total_price:.2f}</b>\n"

        message += "═══════════════════════\n"

        # Footer
        if footer_text:
            message += f"\n{footer_text}"

        return message

    @staticmethod
    def format_admin_order_view(
        invoice_number: str,
        username: str,
        user_id: int,
        digital_items: Optional[dict],
        physical_items: Optional[dict],
        shipping_cost: float,
        total_price: float,
        shipping_address: Optional[str],
        currency_symbol: str = "€"
    ) -> str:
        """
        Format order details for admin shipping management view.

        Args:
            invoice_number: Invoice reference
            username: User's Telegram username
            user_id: User's Telegram ID
            digital_items: Digital items dict
            physical_items: Physical items dict
            shipping_cost: Shipping cost
            total_price: Total order price
            shipping_address: Encrypted shipping address
            currency_symbol: Currency symbol

        Returns:
            Formatted admin order view
        """
        # Header with user info
        header = Localizator.get_text(BotEntity.ADMIN, "order_details_header").format(
            invoice_number=invoice_number,
            username=username,
            user_id=user_id
        )

        # Build invoice
        message = InvoiceFormatterService.format_order_invoice(
            invoice_number=invoice_number,
            digital_items=digital_items,
            physical_items=physical_items,
            shipping_cost=shipping_cost,
            total_price=total_price,
            currency_symbol=currency_symbol,
            show_wallet_line=False,
            header_text=header,
            entity=BotEntity.ADMIN
        )

        # Add shipping address (escape HTML to prevent injection)
        if shipping_address:
            message += f"\n{Localizator.get_text(BotEntity.ADMIN, 'shipping_address_admin_label')}\n"
            message += f"{safe_html(shipping_address)}"

        return message

    @staticmethod
    def format_complete_order_view(
        # === HEADER SECTION ===
        header_type: InvoiceHeaderType | str,  # str for backward compatibility during migration
        invoice_number: str,
        date: Optional[str] = None,

        # === USER INFO (Admin only) ===
        username: Optional[str] = None,
        user_id: Optional[int] = None,

        # === STATUS & TIMESTAMPS ===
        order_status: Optional[OrderStatus] = None,
        created_at: Optional[datetime] = None,
        paid_at: Optional[datetime] = None,
        shipped_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,

        # === ITEMS (unified structure) ===
        items: Optional[list[dict]] = None,

        # === PRICING ===
        subtotal: Optional[float] = None,
        shipping_cost: float = 0.0,
        shipping_type_name: Optional[str] = None,  # e.g., "Päckchen", "Paket 2kg"
        total_price: Optional[float] = None,

        # === WALLET & PAYMENT ===
        wallet_used: float = 0.0,
        crypto_payment_needed: float = 0.0,
        payment_address: Optional[str] = None,
        payment_amount_crypto: Optional[str] = None,

        # === REFUND & CANCELLATION ===
        refund_amount: Optional[float] = None,
        penalty_amount: Optional[float] = None,
        penalty_percent: Optional[int] = None,
        cancellation_reason: Optional[str] = None,
        show_strike_warning: bool = False,
        partial_refund_info: Optional[dict] = None,  # For mixed order cancellations

        # === SHIPPING ADDRESS ===
        shipping_address: Optional[str] = None,

        # === FORMATTING OPTIONS ===
        currency_symbol: str = "€",
        use_spacing_alignment: bool = False,
        show_private_data: bool = False,
        separate_digital_physical: bool = False,
        entity: BotEntity = BotEntity.USER,

        # === FOOTER ===
        footer_text: Optional[str] = None,
        show_retention_notice: bool = False,
    ) -> str:
        """
        Master template for all invoice/order formatting scenarios.

        Supports:
        - Admin order views (shipping management)
        - Payment screens (crypto + wallet)
        - Cancellation notifications (with/without penalty)
        - Purchase history (with status, timestamps, private data)

        Args:
            header_type: Type of view - "admin_order" | "payment_screen" | "wallet_payment" |
                        "cancellation_refund" | "partial_cancellation" | "admin_cancellation" | "purchase_history"
            invoice_number: Invoice reference number(s)
            date: Date string (auto-generated if None)
            username: User's Telegram username (admin views only)
            user_id: User's Telegram ID (admin views only)
            order_status: Order status enum (purchase history only)
            created_at: Order creation timestamp
            paid_at: Payment timestamp
            shipped_at: Shipping timestamp
            expires_at: Payment expiry timestamp (payment screen only)
            items: Unified items list [{'name', 'price', 'quantity', 'is_physical', 'private_data'}]
            subtotal: Order subtotal (auto-calculated if None)
            shipping_cost: Shipping cost
            total_price: Total order price
            wallet_used: Amount paid from wallet
            crypto_payment_needed: Amount to pay with crypto
            payment_address: Crypto payment address (payment screen only)
            payment_amount_crypto: Crypto amount to pay (payment screen only)
            refund_amount: Refund amount (cancellation only)
            penalty_amount: Penalty fee (cancellation only)
            penalty_percent: Penalty percentage (cancellation only)
            cancellation_reason: Reason for cancellation
            show_strike_warning: Show strike warning (cancellation only)
            shipping_address: Shipping address (admin view only)
            currency_symbol: Currency symbol
            use_spacing_alignment: Use spacing for right-aligned amounts
            show_private_data: Render private_data for items (after purchase)
            separate_digital_physical: Separate digital/physical sections (ALL order views)
            entity: BotEntity for localization
            footer_text: Custom footer text
            show_retention_notice: Show data retention notice (purchase history)

        Returns:
            Formatted invoice/order view string
        """
        message = ""

        # Auto-generate date if not provided
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d %H:%M")

        # === HEADER SECTION ===
        if header_type == InvoiceHeaderType.ADMIN_ORDER or header_type == "admin_order":
            # Admin order view header
            header = Localizator.get_text(BotEntity.ADMIN, "order_details_header").format(
                invoice_number=invoice_number,
                username=username or "Unknown",
                user_id=user_id or 0
            )
            message += f"{header}\n\n"
            message += f"<b>Invoice #{invoice_number}</b>\n\n"

        elif header_type == InvoiceHeaderType.PAYMENT_SCREEN or header_type == "payment_screen":
            # Payment screen header with timer
            time_remaining = (expires_at - datetime.now()).total_seconds() / 60 if expires_at else 0
            expires_time = expires_at.strftime("%H:%M") if expires_at else "N/A"
            message += f"<b>Invoice #{invoice_number}</b>\n"
            message += f"{date}\n\n"

        elif header_type == InvoiceHeaderType.WALLET_PAYMENT or header_type == "wallet_payment":
            # Wallet payment completion header
            message += f"<b>Invoice #{invoice_number}</b>\n"
            message += f"{date}\n\n"

        elif header_type == InvoiceHeaderType.CANCELLATION_REFUND or header_type == "cancellation_refund":
            # Cancellation with refund header
            message += f"❌ <b>{Localizator.get_text(entity, 'order_cancelled_title')}</b>\n\n"
            message += f"📋 {Localizator.get_text(entity, 'order_number_label')}: {invoice_number}\n\n"

        elif header_type == InvoiceHeaderType.PARTIAL_CANCELLATION or header_type == "partial_cancellation":
            # Partial cancellation header (mixed order: digital kept, physical refunded)
            message += f"🔄 <b>{Localizator.get_text(entity, 'order_partially_cancelled_title')}</b>\n\n"
            message += f"📋 {Localizator.get_text(entity, 'order_number_label')}: {invoice_number}\n\n"

        elif header_type == InvoiceHeaderType.ADMIN_CANCELLATION or header_type == "admin_cancellation":
            # Admin cancellation header
            message += f"<b>{Localizator.get_text(BotEntity.COMMON, 'admin_cancel_invoice_header')}{invoice_number}</b>\n"
            message += f"{Localizator.get_text(BotEntity.COMMON, 'admin_cancel_invoice_date')} {date}\n"
            message += f"{Localizator.get_text(BotEntity.COMMON, 'admin_cancel_invoice_status')}\n\n"

        elif header_type == InvoiceHeaderType.PAYMENT_SUCCESS or header_type == "payment_success":
            # Payment success notification header
            success_header = Localizator.get_text(BotEntity.COMMON, "payment_success").format(invoice_number=invoice_number)
            message += f"✅ <b>{success_header}</b>\n\n"
            message += f"📋 <b>{Localizator.get_text(entity, 'invoice_number_label')}: {invoice_number}</b>\n\n"

        elif header_type == InvoiceHeaderType.ORDER_SHIPPED or header_type == "order_shipped":
            # Order shipped notification header
            shipped_header = Localizator.get_text(entity, "order_shipped_header")
            message += f"📦 <b>{shipped_header}</b>\n\n"
            message += f"📋 <b>{Localizator.get_text(entity, 'invoice_number_label')}: {invoice_number}</b>\n\n"

            # Show shipped timestamp
            if shipped_at:
                shipped_str = shipped_at.strftime("%d.%m.%Y %H:%M")
                shipped_label = Localizator.get_text(BotEntity.COMMON, "shipped_on_label")
                message += f"<b>{shipped_label}:</b> {shipped_str}\n\n"

        elif header_type == InvoiceHeaderType.ORDER_DETAIL_ADMIN or header_type == "order_detail_admin":
            # Admin order detail header with status (no duplicate emoji)
            if order_status:
                # Get status using enum value directly (UPPERCASE)
                status = Localizator.get_text(BotEntity.COMMON, f"order_status_{order_status.value}")

                created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "N/A"
                order_label = Localizator.get_text(BotEntity.COMMON, "order_label")
                message += f"<b>{order_label} #{invoice_number}</b>\n\n"
                created_label = Localizator.get_text(BotEntity.COMMON, "created_on_label")
                status_label = Localizator.get_text(BotEntity.COMMON, "status_label")
                message += f"<b>{created_label}:</b> {created_str}\n"
                message += f"<b>{status_label}:</b> {status}\n"

                # Add paid timestamp if available
                if paid_at:
                    paid_str = paid_at.strftime("%d.%m.%Y %H:%M")
                    paid_info = Localizator.get_text(BotEntity.COMMON, "order_paid_on").format(paid_at=paid_str)
                    message += f"{paid_info}\n"

                # Add shipped timestamp if available
                if shipped_at:
                    shipped_str = shipped_at.strftime("%d.%m.%Y %H:%M")
                    shipped_info = Localizator.get_text(BotEntity.COMMON, "order_shipped_on").format(shipped_at=shipped_str)
                    message += f"{shipped_info}\n"

                message += "\n"

        elif header_type == InvoiceHeaderType.ORDER_DETAIL_USER or header_type == "order_detail_user" or header_type == InvoiceHeaderType.PURCHASE_HISTORY or header_type == InvoiceHeaderType.PURCHASE_HISTORY or header_type == "purchase_history":
            # User order detail / purchase history header with status
            if order_status:
                # Get status using enum value directly (UPPERCASE)
                status = Localizator.get_text(BotEntity.COMMON, f"order_status_{order_status.value}")

                created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "N/A"
                order_label = Localizator.get_text(BotEntity.COMMON, "order_label")
                message += f"<b>📋 {order_label} #{invoice_number}</b>\n\n"
                created_label = Localizator.get_text(BotEntity.COMMON, "created_on_label")
                status_label = Localizator.get_text(BotEntity.COMMON, "status_label")
                message += f"<b>{created_label}:</b> {created_str}\n"
                message += f"<b>{status_label}:</b> {status}\n"

                # Add paid timestamp if available
                if paid_at:
                    paid_str = paid_at.strftime("%d.%m.%Y %H:%M")
                    paid_info = Localizator.get_text(BotEntity.COMMON, "order_paid_on").format(paid_at=paid_str)
                    message += f"{paid_info}\n"

                # Add shipped timestamp if available
                if shipped_at:
                    shipped_str = shipped_at.strftime("%d.%m.%Y %H:%M")
                    shipped_info = Localizator.get_text(BotEntity.COMMON, "order_shipped_on").format(shipped_at=shipped_str)
                    message += f"{shipped_info}\n"

                message += "\n"

        # === ITEMS SECTION ===
        if items:
            # Auto-calculate subtotal if not provided
            if subtotal is None:
                subtotal = 0.0
                for item in items:
                    # Check if item has tier breakdown
                    if item.get('tier_breakdown'):
                        # Sum tier breakdown totals
                        subtotal += sum(tier['total'] for tier in item['tier_breakdown'])
                    else:
                        # Use simple price * quantity
                        subtotal += item['price'] * item['quantity']

            if header_type == InvoiceHeaderType.PARTIAL_CANCELLATION or header_type == "partial_cancellation":
                # Partial cancellation: Invoice-style formatting with clear structure
                # Structure: Non-Refundable | Refundable | Calculation | Wallet Info
                digital_items = [item for item in items if not item.get('is_physical', False)]
                physical_items = [item for item in items if item.get('is_physical', False)]

                # Calculate subtotals
                non_refundable_total = sum(
                    sum(tier['total'] for tier in item['tier_breakdown']) if item.get('tier_breakdown')
                    else item['price'] * item['quantity']
                    for item in digital_items
                )

                refundable_items_total = sum(
                    sum(tier['total'] for tier in item['tier_breakdown']) if item.get('tier_breakdown')
                    else item['price'] * item['quantity']
                    for item in physical_items
                )
                refundable_total = refundable_items_total + shipping_cost
                new_total = total_price - refundable_total

                # === NON-REFUNDABLE SECTION ===
                message += "═" * 30 + "\n"
                non_refundable_header = Localizator.get_text(BotEntity.USER, "partial_cancel_header")
                message += f"<b>{non_refundable_header}</b>\n"
                message += "─" * 30 + "\n"

                if digital_items:
                    # Format items using builder helper (without section label)
                    items_section = InvoiceFormatterService._format_items_section(
                        items=digital_items,
                        section_label="",
                        currency_symbol=currency_symbol,
                        show_private_data=show_private_data,
                        entity=entity
                    ).replace("<b>:</b>\n", "")
                    message += items_section

                # Subtotal line
                message += "─" * 30 + "\n"
                subtotal_label = Localizator.get_text(BotEntity.USER, "partial_cancel_non_refundable_subtotal")
                message += f"<code>{subtotal_label:<27}{non_refundable_total:>8.2f}{currency_symbol}\n</code>"
                message += "═" * 30 + "\n\n"

                # === REFUNDABLE SECTION ===
                refundable_header = Localizator.get_text(BotEntity.USER, "partial_cancel_refundable_header")
                message += f"<b>{refundable_header}</b>\n"
                message += "─" * 30 + "\n"

                # Physical items if present
                if physical_items:
                    items_section = InvoiceFormatterService._format_items_section(
                        items=physical_items,
                        section_label="",
                        currency_symbol=currency_symbol,
                        show_private_data=False,
                        entity=entity
                    ).replace("<b>:</b>\n", "")
                    message += items_section

                # Shipping line (always shown, uses "Free" when 0)
                message += "─" * 30 + "\n"
                message += InvoiceFormatterService._format_shipping_line_with_free(
                    shipping_cost=shipping_cost,
                    currency_symbol=currency_symbol,
                    entity=entity
                )

                # Subtotal line
                message += "─" * 30 + "\n"
                subtotal_label = Localizator.get_text(BotEntity.USER, "partial_cancel_refundable_subtotal")
                message += f"<code>{subtotal_label:<27}{refundable_total:>8.2f}{currency_symbol}\n</code>"
                message += "═" * 30 + "\n\n"

                # === ORDER TOTAL CALCULATION ===
                calculation_header = Localizator.get_text(BotEntity.USER, "partial_cancel_calculation_header")
                message += f"<b>{calculation_header}</b>\n"
                message += "─" * 30 + "\n"
                message += "<code>"
                original_label = Localizator.get_text(BotEntity.USER, "partial_cancel_original_total")
                message += f"{original_label:<27}{total_price:>8.2f}{currency_symbol}\n"
                refunded_label = Localizator.get_text(BotEntity.USER, "partial_cancel_refunded_label")
                message += f"{refunded_label:<27}{-refundable_total:>8.2f}{currency_symbol}\n"
                message += "</code>"
                message += "─" * 30 + "\n"
                message += "<code>"
                new_total_label = Localizator.get_text(BotEntity.USER, "partial_cancel_new_total")
                message += f"<b>{new_total_label:<27}{new_total:>8.2f}{currency_symbol}</b>\n"
                message += "</code>"
                message += "═" * 30 + "\n\n"

                # === WALLET INFO ===
                wallet_info = Localizator.get_text(BotEntity.USER, "partial_cancel_wallet_info")
                wallet_info = wallet_info.replace("{amount}", f"{refundable_total:.2f}{currency_symbol}")
                message += f"{wallet_info}\n\n"

                # === DIGITAL NOTE ===
                if digital_items:
                    digital_note = Localizator.get_text(BotEntity.USER, "partial_cancel_digital_note")
                    message += f"{digital_note}\n\n"

            elif separate_digital_physical:
                # Separate digital and physical items - used for ALL order confirmations
                digital_items = [item for item in items if not item.get('is_physical', False)]
                physical_items = [item for item in items if item.get('is_physical', False)]

                qty_unit = Localizator.get_text(BotEntity.COMMON, "quantity_unit_short")

                if digital_items:
                    digital_label = Localizator.get_text(BotEntity.COMMON, "digital_items_label")
                    message += InvoiceFormatterService._format_items_section(
                        items=digital_items,
                        section_label=digital_label,
                        currency_symbol=currency_symbol,
                        show_private_data=show_private_data,
                        entity=entity
                    )

                if physical_items:
                    physical_label = Localizator.get_text(BotEntity.COMMON, "physical_items_label")
                    message += InvoiceFormatterService._format_items_section(
                        items=physical_items,
                        section_label=physical_label,
                        currency_symbol=currency_symbol,
                        show_private_data=show_private_data,
                        entity=entity
                    )

                # If private_data was shown, add grouped line items summary
                if show_private_data:
                    positions_header = Localizator.get_text(BotEntity.USER, 'checkout_positions_header')
                    message += "═" * 30 + "\n"
                    message += f"<b>{positions_header}</b>\n"
                    message += "─" * 30 + "\n"
                    message += "<code>"

                    # Group items by (name, price, is_physical) for line items display
                    # This aggregates items that have the same description but different private_data
                    grouped_items = {}
                    for item in items:
                        key = (item['name'], item['price'], item.get('is_physical', False))
                        if key not in grouped_items:
                            grouped_items[key] = {
                                'name': item['name'],
                                'price': item['price'],
                                'quantity': 0,
                                'tier_breakdown': item.get('tier_breakdown')
                            }
                        grouped_items[key]['quantity'] += item['quantity']

                    # Show grouped line items (digital + physical combined)
                    for grouped_item in grouped_items.values():
                        # Calculate line total considering tier_breakdown
                        if grouped_item.get('tier_breakdown'):
                            line_total = sum(tier['total'] for tier in grouped_item['tier_breakdown'])
                        else:
                            line_total = grouped_item['price'] * grouped_item['quantity']

                        # NOTE: Item names are admin-controlled, allow HTML rendering
                        item_name = grouped_item['name']
                        # Extract only first line for compact summary
                        item_name = item_name.split('\n')[0].strip()
                        item_line = f"{item_name} × {grouped_item['quantity']}"
                        message += f"{item_line:<27}{line_total:>8.2f}{currency_symbol}\n"

                    message += "</code>"
                    message += "─" * 30 + "\n\n"

            else:
                # Unified items list with optional spacing alignment (payment screens)
                if header_type in ["admin_cancellation"]:
                    message += f"<b>{Localizator.get_text(entity, 'admin_cancel_invoice_items')}</b>\n"
                    message += "─────────────────────────────\n"

                for item in items:
                    # Calculate line total considering tier_breakdown if available
                    if item.get('tier_breakdown'):
                        line_total = sum(tier['total'] for tier in item['tier_breakdown'])
                        # For tiered items, show only "Nx Name €total" (no unit price breakdown)
                        if use_spacing_alignment:
                            spacing = ' ' * (20 - len(item['name']))
                            message += f"{item['quantity']}x {safe_html(item['name'])}{spacing}{currency_symbol}{line_total:.2f}\n"
                        else:
                            message += f"{item['quantity']}x {safe_html(item['name'])} {currency_symbol}{line_total:.2f}\n"
                    else:
                        line_total = item['price'] * item['quantity']
                        # For non-tiered items, show price breakdown
                        if use_spacing_alignment:
                            spacing = ' ' * (20 - len(item['name']))
                            message += f"{item['quantity']}x {safe_html(item['name'])}\n"
                            message += f"  {currency_symbol}{item['price']:.2f} × {item['quantity']}{spacing}{currency_symbol}{line_total:.2f}\n"
                        else:
                            message += f"{item['quantity']}x {safe_html(item['name'])} {currency_symbol}{item['price']:.2f}\n"

                if header_type in ["admin_cancellation"]:
                    message += "─────────────────────────────\n"
                else:
                    message += "\n"

        # === PRICE BREAKDOWN ===
        # Skip for: cancellation_refund (uses custom format), partial_cancellation (uses structured format)
        if header_type not in ["cancellation_refund", "partial_cancellation"]:
            # Wrap totals section in <code> for monospace alignment when use_spacing_alignment is True
            if use_spacing_alignment:
                message += "<code>"

            # Subtotal line
            if subtotal is not None:
                if use_spacing_alignment:
                    # Unified format: 27 chars left-aligned label, 8 chars right-aligned price
                    subtotal_label = Localizator.get_text(entity, "admin_cancel_invoice_subtotal") if header_type == InvoiceHeaderType.ADMIN_CANCELLATION or header_type == "admin_cancellation" else Localizator.get_text(BotEntity.USER, "cart_subtotal_label")
                    message += f"{subtotal_label:<27}{subtotal:>8.2f}{currency_symbol}\n"
                else:
                    subtotal_label = Localizator.get_text(BotEntity.USER, "cart_subtotal_label")
                    message += f"{subtotal_label} {currency_symbol}{subtotal:.2f}\n"

            # Shipping line (always show for physical items, even if €0.00)
            if shipping_cost >= 0:
                # Build shipping label with type if available
                if use_spacing_alignment:
                    shipping_label = Localizator.get_text(entity, "admin_cancel_invoice_shipping") if header_type == InvoiceHeaderType.ADMIN_CANCELLATION or header_type == "admin_cancellation" else Localizator.get_text(BotEntity.USER, "cart_shipping_max_label")
                    message += f"{shipping_label:<27}{shipping_cost:>8.2f}{currency_symbol}\n"
                    # Add shipping type as indented note if available (prevents label overflow)
                    if shipping_type_name:
                        message += f"  ({shipping_type_name})\n"
                else:
                    shipping_label = Localizator.get_text(BotEntity.USER, "cart_shipping_max_label")
                    if shipping_type_name:
                        shipping_label += f" ({shipping_type_name})"
                    message += f"{shipping_label} {currency_symbol}{shipping_cost:.2f}\n"

            # Wallet line
            if wallet_used > 0:
                if use_spacing_alignment:
                    wallet_label = Localizator.get_text(BotEntity.USER, "wallet_balance_label")
                    message += f"{wallet_label:<27}{-wallet_used:>8.2f}{currency_symbol}\n"
                else:
                    wallet_label = Localizator.get_text(BotEntity.USER, "wallet_balance_label")
                    message += f"{wallet_label} -{currency_symbol}{wallet_used:.2f}\n"

            # Close <code> block before separator
            if use_spacing_alignment:
                message += "</code>"

            # Separator (30 chars to prevent line wrapping)
            if use_spacing_alignment:
                message += "─" * 30 + "\n"
            else:
                message += "═══════════════════════\n"

            # Total line
            if total_price is not None:
                # Calculate final amount due (consider wallet usage)
                # If crypto_payment_needed is explicitly set, use it; otherwise calculate from total_price - wallet_used
                if crypto_payment_needed > 0:
                    final_amount = crypto_payment_needed
                    show_as_amount_due = True
                elif wallet_used > 0:
                    final_amount = total_price - wallet_used
                    show_as_amount_due = True
                else:
                    final_amount = total_price
                    show_as_amount_due = False

                if use_spacing_alignment:
                    message += "<code>"
                    if show_as_amount_due:
                        amount_due_label = Localizator.get_text(BotEntity.USER, "amount_due_label")
                        message += f"<b>{amount_due_label:<27}{final_amount:>8.2f}{currency_symbol}</b>\n"
                    else:
                        total_label = Localizator.get_text(entity, "admin_cancel_invoice_total") if header_type == InvoiceHeaderType.ADMIN_CANCELLATION or header_type == "admin_cancellation" else Localizator.get_text(BotEntity.USER, "cart_total_label")
                        message += f"<b>{total_label:<27}{final_amount:>8.2f}{currency_symbol}</b>\n"
                    message += "</code>"
                else:
                    if show_as_amount_due:
                        amount_due_label = Localizator.get_text(BotEntity.USER, "amount_due_label")
                        message += f"<b>{amount_due_label}: {currency_symbol}{final_amount:.2f}</b>\n"
                    else:
                        total_label = Localizator.get_text(entity, "admin_cancel_invoice_total") if header_type == InvoiceHeaderType.ADMIN_CANCELLATION or header_type == "admin_cancellation" else Localizator.get_text(BotEntity.USER, "cart_total_label")
                        message += f"<b>{total_label}: {currency_symbol}{final_amount:.2f}</b>\n"

            # Closing separator (30 chars to prevent line wrapping)
            if use_spacing_alignment:
                message += "═" * 30 + "\n"
            else:
                message += "═══════════════════════\n"

        # === PAYMENT DETAILS (Payment Screen) ===
        if header_type == InvoiceHeaderType.PAYMENT_SCREEN or header_type == "payment_screen" and payment_address:
            expires_time = expires_at.strftime("%H:%M") if expires_at else "N/A"
            time_remaining = (expires_at - datetime.now()).total_seconds() / 60 if expires_at else 0

            payment_address_label = Localizator.get_text(entity, "invoice_payment_address_label")
            payment_amount_label = Localizator.get_text(entity, "invoice_payment_amount_label")
            payment_deadline = Localizator.get_text(entity, "invoice_payment_deadline").format(expires_time=expires_time)
            time_remaining_text = Localizator.get_text(entity, "invoice_time_remaining").format(time_remaining=int(time_remaining))

            message += f"\n<b>{payment_address_label}:</b>\n"
            message += f"<code>{payment_address}</code>\n\n"
            message += f"<b>{payment_amount_label}:</b> {payment_amount_crypto}\n\n"
            message += f"⏰ <b>{payment_deadline}</b>\n"
            message += f"({time_remaining_text})\n"

        # === PARTIAL CANCELLATION / MIXED ORDER REFUND DETAILS ===
        # Show refund breakdown ONLY for order detail views with mixed items
        # For partial_cancellation header, the new structured format already includes all info
        should_show_refund = (
            header_type in ["order_detail_admin", "order_detail_user"] and
            partial_refund_info and
            partial_refund_info.get('is_mixed_order')
        )

        if should_show_refund:
            # Show refund breakdown for mixed orders in order detail views
            refund_summary = Localizator.get_text(BotEntity.COMMON, 'partial_cancel_refund_summary')
            message += f"\n<b>{refund_summary}:</b>\n"
            message += f"{Localizator.get_text(BotEntity.COMMON, 'partial_cancel_physical_amount')}: {partial_refund_info['physical_amount']:.2f} {currency_symbol}\n"
            message += f"{Localizator.get_text(BotEntity.COMMON, 'partial_cancel_shipping')}: {partial_refund_info['shipping_cost']:.2f} {currency_symbol}\n"
            message += f"{Localizator.get_text(BotEntity.COMMON, 'partial_cancel_refundable_base')}: {partial_refund_info['refundable_base']:.2f} {currency_symbol}\n"

            if partial_refund_info['penalty_amount'] > 0:
                message += f"\n{Localizator.get_text(BotEntity.COMMON, 'partial_cancel_penalty')} ({partial_refund_info['penalty_percent']}%): -{partial_refund_info['penalty_amount']:.2f} {currency_symbol}\n"

            message += f"\n<b>{Localizator.get_text(BotEntity.COMMON, 'partial_cancel_final_refund')}: {partial_refund_info['final_refund']:.2f} {currency_symbol}</b>\n\n"

            # Footer note about digital items
            digital_note = Localizator.get_text(BotEntity.COMMON, 'partial_cancel_digital_note')
            message += f"<i>{digital_note}</i>\n\n"

            if show_strike_warning:
                strike_warning = Localizator.get_text(entity, 'strike_warning')
                message += f"⚠️ <b>{strike_warning}</b>\n\n"

        # === CANCELLATION DETAILS ===
        elif header_type == InvoiceHeaderType.CANCELLATION_REFUND or header_type == "cancellation_refund":
            # Build reason-specific explanation
            if penalty_amount and penalty_amount > 0:
                if cancellation_reason and 'TIMEOUT' in cancellation_reason.upper():
                    reason_text = Localizator.get_text(entity, 'cancellation_reason_timeout')
                elif cancellation_reason and 'reservation_fee' in cancellation_reason.lower():
                    reason_text = Localizator.get_text(entity, 'cancellation_reason_reservation_fee')
                else:
                    reason_text = Localizator.get_text(entity, 'cancellation_reason_late')

                message += f"{reason_text}\n\n"

                # Wallet details section
                if wallet_used > 0:
                    wallet_section = (
                        f"{Localizator.get_text(entity, 'cancellation_wallet_refund_header')}\n"
                        f"{Localizator.get_text(entity, 'cancellation_wallet_used').format(wallet_used=f'{wallet_used:.2f}', currency_symbol=currency_symbol)}\n"
                        f"{Localizator.get_text(entity, 'cancellation_processing_fee').format(penalty_percent=penalty_percent, penalty_amount=f'{penalty_amount:.2f}', currency_symbol=currency_symbol)}\n"
                        f"{Localizator.get_text(entity, 'cancellation_amount_refunded').format(refund_amount=f'{refund_amount:.2f}', currency_symbol=currency_symbol)}"
                    )
                else:
                    base_amount = total_price or 0.0
                    wallet_section = (
                        f"{Localizator.get_text(entity, 'cancellation_reservation_fee_header')}\n"
                        f"{Localizator.get_text(entity, 'cancellation_order_value').format(base_amount=f'{base_amount:.2f}', currency_symbol=currency_symbol)}\n"
                        f"{Localizator.get_text(entity, 'cancellation_fee').format(penalty_percent=penalty_percent, penalty_amount=f'{penalty_amount:.2f}', currency_symbol=currency_symbol)}\n"
                        f"{Localizator.get_text(entity, 'cancellation_deducted_from_wallet')}"
                    )

                message += f"{wallet_section}\n\n"

                if show_strike_warning:
                    message += f"{Localizator.get_text(entity, 'cancellation_strike_received')}\n\n"
            else:
                # Full refund (no penalty)
                message += f"{Localizator.get_text(entity, 'cancellation_full_refund').format(refund_amount=f'{refund_amount:.2f}', currency_symbol=currency_symbol)}\n\n"

        # === CANCELLATION REASON ===
        import logging
        logging.info(f"🟢 Cancellation reason check: cancellation_reason='{cancellation_reason}', header_type='{header_type}'")

        # Check if header_type is one of the cancellation types (support both enum and string)
        is_cancellation_type = (
            header_type == InvoiceHeaderType.ADMIN_CANCELLATION or header_type == "admin_cancellation" or
            header_type == InvoiceHeaderType.CANCELLATION_REFUND or header_type == "cancellation_refund" or
            header_type == InvoiceHeaderType.PARTIAL_CANCELLATION or header_type == "partial_cancellation"
        )
        logging.info(f"🟢 Condition evaluates to: {bool(cancellation_reason and is_cancellation_type)}")

        if cancellation_reason and is_cancellation_type:
            logging.info(f"🟢 ENTERING cancellation reason block for header_type='{header_type}'")
            if header_type == InvoiceHeaderType.ADMIN_CANCELLATION or header_type == "admin_cancellation":
                # Admin cancellation uses custom reason label
                logging.info(f"🟢 Adding admin cancellation reason: '{cancellation_reason}'")
                message += f"\n<b>{Localizator.get_text(BotEntity.COMMON, 'admin_cancel_reason_label')}</b>\n"
                message += f"{safe_html(cancellation_reason)}\n\n"
            else:
                # User cancellation shows reason code
                reason_label = Localizator.get_text(entity, 'cancellation_reason_label')
                message += f"\n<b>{reason_label}:</b> "

                # Format reason code for display
                if 'USER' in cancellation_reason.upper():
                    reason_text = Localizator.get_text(entity, 'cancellation_reason_user')
                elif 'ADMIN' in cancellation_reason.upper():
                    reason_text = Localizator.get_text(entity, 'cancellation_reason_admin')
                elif 'TIMEOUT' in cancellation_reason.upper():
                    reason_text = Localizator.get_text(entity, 'cancellation_reason_timeout')
                else:
                    reason_text = safe_html(cancellation_reason)  # Fallback to raw reason (escaped)

                message += f"{reason_text}\n\n"

        # === SHIPPING ADDRESS (Admin View) ===
        if shipping_address:
            message += f"\n{Localizator.get_text(entity, 'shipping_address_admin_label')}\n"
            # Escape shipping address to prevent HTML injection
            message += f"{safe_html(shipping_address)}\n"

        # === FOOTER ===
        if footer_text:
            message += f"\n{footer_text}\n"

        if header_type == InvoiceHeaderType.ADMIN_CANCELLATION or header_type == "admin_cancellation":
            message += f"{Localizator.get_text(entity, 'admin_cancel_notice')}\n\n"
            message += f"{Localizator.get_text(entity, 'admin_cancel_contact_support')}"

        # Display cancellation reason in order history detail view (for CANCELLED_BY_ADMIN status)
        if header_type in ["order_detail_admin", "order_detail_user"] and cancellation_reason:
            if order_status == OrderStatus.CANCELLED_BY_ADMIN:
                message += f"\n\n<b>{Localizator.get_text(BotEntity.COMMON, 'admin_cancel_reason_label')}</b>\n"
                message += f"{safe_html(cancellation_reason)}"

        if show_retention_notice:
            import config
            message += f"\n{Localizator.get_text(entity, 'purchased_items_retention_notice').format(retention_days=config.DATA_RETENTION_DAYS)}"

        return message

    @staticmethod
    def _format_tier_item_detail(
        item: dict,
        currency_symbol: str,
        entity: BotEntity
    ) -> str:
        """
        Format a single tiered item with full tier structure, savings, and upsell.

        Args:
            item: Dict with keys:
                - name: str
                - quantity: int
                - unit_price: float
                - line_total: float
                - available_tiers: list[dict] with min_quantity, max_quantity, unit_price
                - current_tier_idx: int
                - next_tier_info: dict or None (items_needed, unit_price, extra_savings)
                - savings_vs_single: float
            currency_symbol: Currency symbol
            entity: BotEntity for localization

        Returns:
            Formatted HTML string for this item
        """
        lines = []

        # Item name and quantity
        item_name = safe_html(item['name'])
        lines.append(f"📦 <b>{item_name}</b>")
        quantity_text = Localizator.get_text(entity, 'checkout_quantity_label').format(
            quantity=item['quantity']
        )
        lines.append(f"   {quantity_text}")
        lines.append("")

        # Tier structure
        tier_label = Localizator.get_text(entity, 'checkout_tier_prices_label')
        lines.append(f"   {tier_label}")

        available_tiers = item.get('available_tiers', [])
        current_tier_idx = item.get('current_tier_idx', 0)

        # Get localized quantity unit
        qty_unit = Localizator.get_text(BotEntity.COMMON, "quantity_unit_short")

        # Build tier table with <code> to preserve space alignment in Telegram
        tier_lines = []
        for idx, tier in enumerate(available_tiers):
            # Format range with localized quantity unit
            if tier.get('max_quantity') is not None:
                range_str = f"{tier['min_quantity']}-{tier['max_quantity']} {qty_unit}"
            else:
                range_str = f"{tier['min_quantity']}+ {qty_unit}"

            # Format price
            price_str = f"{tier['unit_price']:.2f}{currency_symbol}"

            # Mark current tier (fixed width formatting for proper alignment in monospace)
            if idx == current_tier_idx:
                marker = Localizator.get_text(entity, 'checkout_tier_your_price')
                tier_lines.append(f"• {range_str:>15}: {price_str:>9}  {marker}")
            else:
                tier_lines.append(f"• {range_str:>15}: {price_str:>9}")

        # Wrap tier table in <code> to preserve alignment (Telegram collapses spaces in HTML)
        lines.append(f"   <code>\n{chr(10).join(tier_lines)}\n   </code>")

        lines.append("")

        # Savings vs single price
        savings_vs_single = item.get('savings_vs_single', 0)
        if savings_vs_single > 0:
            savings_text = Localizator.get_text(entity, 'checkout_savings').format(
                amount=f"{savings_vs_single:.2f}{currency_symbol}"
            )
            lines.append(f"   {savings_text}")

        # Upselling hint
        next_tier_info = item.get('next_tier_info')
        if next_tier_info:
            upsell_text = Localizator.get_text(entity, 'checkout_upsell').format(
                items=next_tier_info['items_needed'],
                price=f"{next_tier_info['unit_price']:.2f}{currency_symbol}",
                savings=f"{next_tier_info['extra_savings']:.2f}{currency_symbol}"
            )
            lines.append(f"   {upsell_text}")
        else:
            # Max tier reached
            max_tier_text = Localizator.get_text(entity, 'checkout_max_tier')
            lines.append(f"   {max_tier_text}")

        return "\n".join(lines)

    @staticmethod
    def format_checkout_summary(
        items: list[dict],
        subtotal: float,
        shipping_cost: float,
        total: float,
        total_savings: float,
        has_physical_items: bool,
        currency_symbol: str = "€",
        entity: BotEntity = BotEntity.USER
    ) -> str:
        """
        Format checkout summary with tier details, savings, and upselling.

        This method provides a consistent checkout view that matches the invoice
        format shown after purchase, ensuring no surprises for the user.

        Args:
            items: List of item dicts with keys:
                - name: str
                - quantity: int
                - unit_price: float
                - line_total: float
                - available_tiers: list[dict] (optional, for tiered items)
                - current_tier_idx: int (optional)
                - next_tier_info: dict or None (optional)
                - savings_vs_single: float (optional)
            subtotal: Order subtotal
            shipping_cost: Shipping cost (can be 0.00)
            total: Grand total
            total_savings: Sum of all item savings
            has_physical_items: Whether cart contains physical items
            currency_symbol: Currency symbol
            entity: BotEntity for localization

        Returns:
            Formatted HTML checkout summary string

        Example output structure:
            🛒 Warenkorb

            📦 USB-Sticks 32GB
               Menge: 16 Stück

               Staffelpreise:
               •    1-5 Stück:   12,00€
               •   6-15 Stück:   10,00€
               •  16-25 Stück:    9,00€  ← Dein Preis
               •     26+ Stück:    8,00€

               Ersparnis: 48,00€ gegenüber Einzelpreis
               Noch 10 Stück für 8,00€/Stk. (weitere 16,00€ Ersparnis möglich)

            ═══════════════════════════════════
            Positionen:
            ───────────────────────────────────
            USB-Sticks 32GB × 16      144,00€
            Grüner Tee Bio × 8        104,00€
            ───────────────────────────────────
            Zwischensumme:            428,00€
            Versandkosten:              0,00€
            ═══════════════════════════════════
            Gesamt:                   428,00€

            Gesamtersparnis: 84,00€
        """
        message = f"<b>{Localizator.get_text(entity, 'checkout_header')}</b>\n\n"

        # === SECTION 1: Detailed Tier Information ===
        # Only show for items with tier structure
        tiered_items = [item for item in items if item.get('available_tiers')]

        for item in tiered_items:
            message += InvoiceFormatterService._format_tier_item_detail(
                item, currency_symbol, entity
            )
            message += "\n\n"

        # === SECTION 2: Line Items Summary ===
        separator = Localizator.get_text(entity, 'checkout_line_separator')
        message += separator + "\n"

        positions_header = Localizator.get_text(entity, 'checkout_positions_header')
        message += f"<b>{positions_header}</b>\n"
        message += "─" * len(separator) + "\n"

        # Wrap in <code> for monospace alignment
        message += "<code>"
        for item in items:
            item_name = safe_html(item['name'])
            qty = item['quantity']
            line_total = item['line_total']
            # Use fixed width: name+qty left-aligned (27 chars), price right-aligned
            item_line = f"{item_name} × {qty}"
            message += f"{item_line:<27}{line_total:>8.2f}{currency_symbol}\n"
        message += "</code>"

        # === SECTION 3: Totals ===
        message += "─" * len(separator) + "\n"

        # Wrap totals in <code> for monospace alignment
        message += "<code>"

        subtotal_label = Localizator.get_text(entity, 'cart_subtotal_label')
        message += f"{subtotal_label:<27}{subtotal:>8.2f}{currency_symbol}\n"

        if has_physical_items:
            shipping_label = Localizator.get_text(entity, 'cart_shipping_max_label')
            message += f"{shipping_label:<27}{shipping_cost:>8.2f}{currency_symbol}\n"

        message += "</code>"
        message += separator + "\n"

        total_label = Localizator.get_text(entity, 'cart_total_label')
        message += f"<b><code>{total_label:<27}{total:>8.2f}{currency_symbol}</code></b>\n"

        # === SECTION 4: Total Savings ===
        if total_savings > 0:
            message += "\n"
            savings_text = Localizator.get_text(entity, 'checkout_total_savings').format(
                amount=f"{total_savings:.2f}{currency_symbol}"
            )
            message += f"<b>{savings_text}</b>"

        return message
