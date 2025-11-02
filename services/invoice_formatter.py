"""
Invoice Formatter Service

Centralized invoice/order formatting to eliminate code duplication.
Used across:
- Admin order views
- User payment screens
- Cancellation notifications
"""

from typing import Optional
from enums.bot_entity import BotEntity
from utils.localizator import Localizator


class InvoiceFormatter:
    """Centralized invoice formatting service"""

    @staticmethod
    def format_items_list(
        items_dict: dict,
        currency_symbol: str,
        show_line_totals: bool = True
    ) -> tuple[str, float]:
        """
        Format items list with optional line totals.

        Args:
            items_dict: Dict of {(name, price): quantity}
            currency_symbol: Currency symbol (e.g., "€")
            show_line_totals: Show line totals for qty > 1

        Returns:
            Tuple of (formatted_string, total_amount)
        """
        items_text = ""
        total = 0.0

        for (name, price), qty in items_dict.items():
            line_total = price * qty
            total += line_total

            if qty == 1 or not show_line_totals:
                items_text += f"{qty} Stk. {name} {currency_symbol}{price:.2f}\n"
            else:
                items_text += f"{qty} Stk. {name} {currency_symbol}{price:.2f} = {currency_symbol}{line_total:.2f}\n"

        return items_text, total

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
            message += "<b>Digital:</b>\n"
            items_text, digital_total = InvoiceFormatter.format_items_list(
                digital_items, currency_symbol
            )
            message += items_text
            message += "\n"

        # Physical items section
        if show_physical_section and physical_items:
            message += "<b>Versandartikel:</b>\n"
            items_text, physical_total = InvoiceFormatter.format_items_list(
                physical_items, currency_symbol
            )
            message += items_text
            message += "\n"

        # Price breakdown
        message += "═══════════════════════\n"

        # Shipping line
        if show_shipping and shipping_cost > 0:
            message += f"Versand {currency_symbol}{shipping_cost:.2f}\n"

        # Wallet usage line
        if show_wallet_line and wallet_used > 0:
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
        message = InvoiceFormatter.format_order_invoice(
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

        # Add shipping address
        if shipping_address:
            message += "\n<b>Adressdaten:</b>\n"
            message += f"{shipping_address}"

        return message
