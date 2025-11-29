from enum import Enum


class InvoiceHeaderType(Enum):
    """
    Invoice header types for format_complete_order_view().

    Defines the type of invoice header to display, which determines:
    - Header text/emoji
    - Which sections to show (payment, refund, cancellation)
    - Field labels and formatting
    """

    # Admin Views
    ADMIN_ORDER = "admin_order"                     # Admin viewing pending/active order
    ORDER_DETAIL_ADMIN = "order_detail_admin"       # Admin order history detail

    # User Payment Flow
    PAYMENT_SCREEN = "payment_screen"               # Initial payment screen with crypto address
    WALLET_PAYMENT = "wallet_payment"               # Wallet-only payment (no crypto)
    PAYMENT_SUCCESS = "payment_success"             # Payment completed successfully

    # Order Completion
    ORDER_SHIPPED = "order_shipped"                 # Physical order shipped notification

    # User Order History
    ORDER_DETAIL_USER = "order_detail_user"         # User order history detail
    PURCHASE_HISTORY = "purchase_history"           # Legacy purchase history view

    # Cancellations & Refunds
    CANCELLATION_REFUND = "cancellation_refund"     # User/timeout cancellation with refund
    PARTIAL_CANCELLATION = "partial_cancellation"   # Mixed order (digital kept, physical refunded)
    ADMIN_CANCELLATION = "admin_cancellation"       # Admin-initiated cancellation