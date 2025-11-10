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
from enums.order_status import OrderStatus
from utils.localizator import Localizator
from utils.html_escape import safe_html


class InvoiceFormatterService:
    """Centralized invoice formatting service"""

    @staticmethod
    def _format_private_data(private_data: str) -> str:
        """
        Format private_data based on its content type.

        Args:
            private_data: Raw private data string

        Returns:
            Formatted HTML string
        """
        # Check if private_data contains HTML tags (already formatted)
        if any(tag in private_data for tag in ['<b>', '<i>', '<a>', '<code>', '<pre>', '<u>', '<s>']):
            # Already HTML formatted - render directly with indentation on first line only
            lines = private_data.split('\n')
            result = f"   {lines[0]}\n"
            if len(lines) > 1:
                result += '\n'.join(lines[1:]) + '\n'
            return result
        # Check if private_data is a URL (for Telegram deep links)
        elif private_data.startswith(('http://', 'https://', 't.me/')):
            # Render as clickable link
            if private_data.startswith('t.me/'):
                private_data = f"https://{private_data}"
            return f"   <a href=\"{private_data}\">📱 Beratung starten</a>\n"
        else:
            # Render as code (for vouchers, keys, etc.)
            return f"   <code>{private_data}</code>\n"

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
            items: List of item dicts
            section_label: Section header (e.g., "Digital Items:")
            currency_symbol: Currency symbol
            show_private_data: Whether to show private_data
            entity: BotEntity for localization

        Returns:
            Formatted HTML string
        """
        if not items:
            return ""

        qty_unit = Localizator.get_text(BotEntity.COMMON, "quantity_unit_short")
        message = f"<b>{section_label}:</b>\n"

        for item in items:
            # Check if item has tier breakdown
            if item.get('tier_breakdown'):
                # Use tier breakdown formatting
                tier_text, _ = InvoiceFormatterService.format_items_with_tier_breakdown(
                    item_name=item['name'],
                    tier_breakdown=item['tier_breakdown'],
                    currency_symbol=currency_symbol,
                    entity=entity
                )
                message += tier_text + "\n"
            else:
                # Flat pricing (no tier breakdown)
                line_total = item['price'] * item['quantity']
                if item['quantity'] == 1:
                    message += f"{item['quantity']} {qty_unit} {item['name']} {currency_symbol}{item['price']:.2f}\n"
                else:
                    message += f"{item['quantity']} {qty_unit} {item['name']} {currency_symbol}{item['price']:.2f} = {currency_symbol}{line_total:.2f}\n"

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
            line_total = price * qty
            total += line_total

            if qty == 1 or not show_line_totals:
                items_text += f"{qty} {qty_unit} {name} {currency_symbol}{price:.2f}\n"
            else:
                items_text += f"{qty} {qty_unit} {name} {currency_symbol}{price:.2f} = {currency_symbol}{line_total:.2f}\n"

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
            digital_label = Localizator.get_text(entity, "digital_items_label")
            message += f"<b>{digital_label}:</b>\n"
            items_text, digital_total = InvoiceFormatterService.format_items_list(
                digital_items, currency_symbol, entity=entity
            )
            message += items_text
            message += "\n"

        # Physical items section
        if show_physical_section and physical_items:
            physical_label = Localizator.get_text(entity, "physical_items_label")
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
            # "Wallet-Guthaben" is in payment_wallet_line localization key
            message += f"Wallet-Guthaben -{currency_symbol}{wallet_used:.2f}\n"

        # Total
        if crypto_payment_needed > 0:
            message += f"\n<b>Zu zahlen: {currency_symbol}{crypto_payment_needed:.2f}</b>\n"
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
        header_type: str,
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
        if header_type == "admin_order":
            # Admin order view header
            header = Localizator.get_text(BotEntity.ADMIN, "order_details_header").format(
                invoice_number=invoice_number,
                username=username or "Unknown",
                user_id=user_id or 0
            )
            message += f"{header}\n\n"
            message += f"<b>Invoice #{invoice_number}</b>\n\n"

        elif header_type == "payment_screen":
            # Payment screen header with timer
            time_remaining = (expires_at - datetime.now()).total_seconds() / 60 if expires_at else 0
            expires_time = expires_at.strftime("%H:%M") if expires_at else "N/A"
            message += f"<b>Invoice #{invoice_number}</b>\n"
            message += f"{date}\n\n"

        elif header_type == "wallet_payment":
            # Wallet payment completion header
            message += f"<b>Invoice #{invoice_number}</b>\n"
            message += f"{date}\n\n"

        elif header_type == "cancellation_refund":
            # Cancellation with refund header
            message += f"❌ <b>{Localizator.get_text(entity, 'order_cancelled_title')}</b>\n\n"
            message += f"📋 {Localizator.get_text(entity, 'order_number_label')}: {invoice_number}\n\n"

        elif header_type == "partial_cancellation":
            # Partial cancellation header (mixed order: digital kept, physical refunded)
            message += f"🔄 <b>{Localizator.get_text(entity, 'order_partially_cancelled_title')}</b>\n\n"
            message += f"📋 {Localizator.get_text(entity, 'order_number_label')}: {invoice_number}\n\n"

        elif header_type == "admin_cancellation":
            # Admin cancellation header
            message += f"<b>{Localizator.get_text(entity, 'admin_cancel_invoice_header')}{invoice_number}</b>\n"
            message += f"{Localizator.get_text(entity, 'admin_cancel_invoice_date')} {date}\n"
            message += f"{Localizator.get_text(entity, 'admin_cancel_invoice_status')}\n\n"

        elif header_type == "payment_success":
            # Payment success notification header
            success_header = Localizator.get_text(entity, "payment_success").format(invoice_number=invoice_number)
            message += f"✅ <b>{success_header}</b>\n\n"
            message += f"📋 <b>{Localizator.get_text(entity, 'invoice_number_label')}: {invoice_number}</b>\n\n"

        elif header_type == "order_shipped":
            # Order shipped notification header
            shipped_header = Localizator.get_text(entity, "order_shipped_header")
            message += f"📦 <b>{shipped_header}</b>\n\n"
            message += f"📋 <b>{Localizator.get_text(entity, 'invoice_number_label')}: {invoice_number}</b>\n\n"

            # Show shipped timestamp
            if shipped_at:
                shipped_str = shipped_at.strftime("%d.%m.%Y %H:%M")
                shipped_label = Localizator.get_text(entity, "shipped_on_label")
                message += f"<b>{shipped_label}:</b> {shipped_str}\n\n"

        elif header_type == "order_detail_user" or header_type == "purchase_history":
            # User order detail / purchase history header with status
            if order_status:
                # Get status using enum value directly (UPPERCASE)
                status = Localizator.get_text(BotEntity.COMMON, f"order_status_{order_status.value}")

                created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "N/A"
                order_label = Localizator.get_text(entity, "order_label")
                message += f"<b>📋 {order_label} #{invoice_number}</b>\n\n"
                created_label = Localizator.get_text(entity, "created_on_label")
                status_label = Localizator.get_text(entity, "status_label")
                message += f"<b>{created_label}:</b> {created_str}\n"
                message += f"<b>{status_label}:</b> {status}\n"

                # Add paid timestamp if available
                if paid_at:
                    paid_str = paid_at.strftime("%d.%m.%Y %H:%M")
                    paid_info = Localizator.get_text(entity, "order_paid_on").format(paid_at=paid_str)
                    message += f"{paid_info}\n"

                # Add shipped timestamp if available
                if shipped_at:
                    shipped_str = shipped_at.strftime("%d.%m.%Y %H:%M")
                    shipped_info = Localizator.get_text(entity, "order_shipped_on").format(shipped_at=shipped_str)
                    message += f"{shipped_info}\n"

                message += "\n"

        # === ITEMS SECTION ===
        if items:
            # Auto-calculate subtotal if not provided
            if subtotal is None:
                subtotal = sum(item['price'] * item['quantity'] for item in items)

            if header_type == "partial_cancellation":
                # Partial cancellation: Show digital (kept) and physical (refunded) separately
                digital_items = [item for item in items if not item.get('is_physical', False)]
                physical_items = [item for item in items if item.get('is_physical', False)]

                if digital_items:
                    digital_title = Localizator.get_text(entity, 'partial_cancel_digital_items_title')
                    message += f"<b>{digital_title}</b>\n"
                    for item in digital_items:
                        line_total = item['price'] * item['quantity']
                        message += f"{item['quantity']}x {item['name']} {currency_symbol}{line_total:.2f}\n"
                    digital_status = Localizator.get_text(entity, 'partial_cancel_digital_status')
                    message += f"<i>{digital_status}</i>\n\n"

                if physical_items:
                    physical_title = Localizator.get_text(entity, 'partial_cancel_physical_items_title')
                    message += f"<b>{physical_title}</b>\n"
                    for item in physical_items:
                        line_total = item['price'] * item['quantity']
                        message += f"{item['quantity']}x {item['name']} {currency_symbol}{line_total:.2f}\n"
                    physical_status = Localizator.get_text(entity, 'partial_cancel_physical_status')
                    message += f"<i>{physical_status}</i>\n\n"

            elif separate_digital_physical:
                # Separate digital and physical items - used for ALL order confirmations
                digital_items = [item for item in items if not item.get('is_physical', False)]
                physical_items = [item for item in items if item.get('is_physical', False)]

                qty_unit = Localizator.get_text(BotEntity.COMMON, "quantity_unit_short")

                if digital_items:
                    digital_label = Localizator.get_text(entity, "digital_items_label")
                    message += InvoiceFormatterService._format_items_section(
                        items=digital_items,
                        section_label=digital_label,
                        currency_symbol=currency_symbol,
                        show_private_data=show_private_data,
                        entity=entity
                    )

                if physical_items:
                    physical_label = Localizator.get_text(entity, "physical_items_label")
                    message += InvoiceFormatterService._format_items_section(
                        items=physical_items,
                        section_label=physical_label,
                        currency_symbol=currency_symbol,
                        show_private_data=show_private_data,
                        entity=entity
                    )

            else:
                # Unified items list with optional spacing alignment (payment screens)
                if header_type in ["admin_cancellation"]:
                    message += f"<b>{Localizator.get_text(entity, 'admin_cancel_invoice_items')}</b>\n"
                    message += "─────────────────────────────\n"

                for item in items:
                    line_total = item['price'] * item['quantity']
                    if use_spacing_alignment:
                        # Payment screen format with spacing
                        spacing = ' ' * (20 - len(item['name']))
                        message += f"{item['quantity']}x {item['name']}\n"
                        message += f"  {currency_symbol}{item['price']:.2f} × {item['quantity']}{spacing}{currency_symbol}{line_total:.2f}\n"
                    else:
                        # Simple format
                        message += f"{item['quantity']}x {item['name']} {currency_symbol}{item['price']:.2f}\n"

                if header_type in ["admin_cancellation"]:
                    message += "─────────────────────────────\n"
                else:
                    message += "\n"

        # === PRICE BREAKDOWN ===
        if header_type not in ["cancellation_refund"]:
            # Subtotal line
            if subtotal is not None and use_spacing_alignment:
                subtotal_label = Localizator.get_text(entity, "admin_cancel_invoice_subtotal") if header_type == "admin_cancellation" else "Subtotal"
                subtotal_spacing = " " * (29 - len(subtotal_label)) if header_type == "admin_cancellation" else " " * 18
                message += f"{subtotal_label}{subtotal_spacing}{currency_symbol}{subtotal:.2f}\n"

            # Shipping line
            if shipping_cost > 0:
                if use_spacing_alignment:
                    if header_type == "admin_cancellation":
                        shipping_label = Localizator.get_text(entity, "admin_cancel_invoice_shipping")
                        shipping_spacing = " " * (29 - len(shipping_label))
                        message += f"{shipping_label}{shipping_spacing}{currency_symbol}{shipping_cost:.2f}\n"
                    else:
                        message += f"Shipping{' ' * 18}{currency_symbol}{shipping_cost:.2f}\n"
                else:
                    message += f"Versand {currency_symbol}{shipping_cost:.2f}\n"

            # Wallet line
            if wallet_used > 0:
                if use_spacing_alignment:
                    wallet_spacing = " " * 11 if header_type == "payment_screen" else " " * 20
                    wallet_line = Localizator.get_text(entity, "payment_wallet_line").format(
                        wallet_used=wallet_used,
                        wallet_spacing=wallet_spacing,
                        currency_sym=currency_symbol
                    )
                    message += wallet_line
                else:
                    message += f"Wallet-Guthaben -{currency_symbol}{wallet_used:.2f}\n"

            # Separator
            if use_spacing_alignment and header_type == "admin_cancellation":
                message += "─────────────────────────────\n"
            else:
                message += "═══════════════════════\n"

            # Total line
            if total_price is not None:
                if use_spacing_alignment:
                    if header_type == "admin_cancellation":
                        total_label = Localizator.get_text(entity, "admin_cancel_invoice_total")
                        total_spacing = " " * (29 - len(total_label))
                        message += f"<b>{total_label}{total_spacing}{currency_symbol}{total_price:.2f}</b>\n"
                    else:
                        total_spacing = " " * 23
                        if crypto_payment_needed > 0:
                            message += f"<b>Zu zahlen:{total_spacing}{currency_symbol}{crypto_payment_needed:.2f}</b>\n"
                        else:
                            message += f"<b>Total:{total_spacing}{currency_symbol}{total_price:.2f}</b>\n"
                else:
                    if crypto_payment_needed > 0:
                        message += f"<b>Zu zahlen: {currency_symbol}{crypto_payment_needed:.2f}</b>\n"
                    else:
                        message += f"<b>Total: {currency_symbol}{total_price:.2f}</b>\n"

            # Closing separator
            if not use_spacing_alignment or header_type not in ["admin_cancellation"]:
                message += "═══════════════════════\n"

        # === PAYMENT DETAILS (Payment Screen) ===
        if header_type == "payment_screen" and payment_address:
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

        # === PARTIAL CANCELLATION DETAILS ===
        if header_type == "partial_cancellation" and partial_refund_info:
            # Show refund breakdown for mixed orders
            refund_summary = Localizator.get_text(entity, 'partial_cancel_refund_summary')
            message += f"<b>{refund_summary}:</b>\n"
            message += f"{Localizator.get_text(entity, 'partial_cancel_physical_amount')}: {partial_refund_info['physical_amount']:.2f} {currency_symbol}\n"
            message += f"{Localizator.get_text(entity, 'partial_cancel_shipping')}: {partial_refund_info['shipping_cost']:.2f} {currency_symbol}\n"
            message += f"{Localizator.get_text(entity, 'partial_cancel_refundable_base')}: {partial_refund_info['refundable_base']:.2f} {currency_symbol}\n"

            if partial_refund_info['penalty_amount'] > 0:
                message += f"\n{Localizator.get_text(entity, 'partial_cancel_penalty')} ({partial_refund_info['penalty_percent']}%): -{partial_refund_info['penalty_amount']:.2f} {currency_symbol}\n"

            message += f"\n<b>{Localizator.get_text(entity, 'partial_cancel_final_refund')}: {partial_refund_info['final_refund']:.2f} {currency_symbol}</b>\n\n"

            # Footer note about digital items
            digital_note = Localizator.get_text(entity, 'partial_cancel_digital_note')
            message += f"<i>{digital_note}</i>\n\n"

            if show_strike_warning:
                strike_warning = Localizator.get_text(entity, 'strike_warning')
                message += f"⚠️ <b>{strike_warning}</b>\n\n"

        # === CANCELLATION DETAILS ===
        elif header_type == "cancellation_refund":
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
        logging.info(f"🟢 Condition evaluates to: {bool(cancellation_reason and header_type in ['admin_cancellation', 'cancellation_refund', 'partial_cancellation'])}")

        if cancellation_reason and header_type in ["admin_cancellation", "cancellation_refund", "partial_cancellation"]:
            logging.info(f"🟢 ENTERING cancellation reason block for header_type='{header_type}'")
            if header_type == "admin_cancellation":
                # Admin cancellation uses custom reason label
                logging.info(f"🟢 Adding admin cancellation reason: '{cancellation_reason}'")
                message += f"\n<b>{Localizator.get_text(entity, 'admin_cancel_reason_label')}</b>\n"
                message += f"{cancellation_reason}\n\n"
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
                    reason_text = cancellation_reason  # Fallback to raw reason

                message += f"{reason_text}\n\n"

        # === SHIPPING ADDRESS (Admin View) ===
        if shipping_address:
            message += f"\n{Localizator.get_text(entity, 'shipping_address_admin_label')}\n"
            message += f"{shipping_address}\n"

        # === FOOTER ===
        if footer_text:
            message += f"\n{footer_text}\n"

        if header_type == "admin_cancellation":
            message += f"{Localizator.get_text(entity, 'admin_cancel_notice')}\n\n"

            # Display custom reason if provided
            if cancellation_reason:
                message += f"<b>{Localizator.get_text(entity, 'admin_cancel_reason_label')}</b>\n"
                message += f"{cancellation_reason}\n\n"

            message += f"{Localizator.get_text(entity, 'admin_cancel_contact_support')}"

        # Display cancellation reason in order history detail view (for CANCELLED_BY_ADMIN status)
        if header_type in ["order_detail_admin", "order_detail_user"] and cancellation_reason:
            if order_status == OrderStatus.CANCELLED_BY_ADMIN:
                message += f"\n\n<b>{Localizator.get_text(entity, 'admin_cancel_reason_label')}</b>\n"
                message += f"{cancellation_reason}"

        if show_retention_notice:
            import config
            message += f"\n{Localizator.get_text(entity, 'purchased_items_retention_notice').format(retention_days=config.DATA_RETENTION_DAYS)}"

        return message
