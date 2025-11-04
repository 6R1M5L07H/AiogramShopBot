import logging
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from crypto_api.CryptoApiWrapper import CryptoApiWrapper
from db import get_db_session, session_commit
from enums.bot_entity import BotEntity
from enums.cryptocurrency import Cryptocurrency
from enums.order_status import OrderStatus
from enums.payment import PaymentType
from models.invoice import InvoiceDTO
from models.payment import ProcessingPaymentDTO
from repositories.order import OrderRepository
from repositories.payment import PaymentRepository
from repositories.user import UserRepository
from services.invoice import InvoiceService
from utils.localizator import Localizator


class PaymentService:
    @staticmethod
    async def create(cryptocurrency: Cryptocurrency, message: Message, session: AsyncSession | Session) -> str:
        user = await UserRepository.get_by_tgid(message.chat.id, session)
        unexpired_payments_count = await PaymentRepository.get_unexpired_unpaid_payments(user.id, session)
        if unexpired_payments_count >= 5:
            return Localizator.get_text(BotEntity.USER, "too_many_payment_request")
        else:
            payment_dto = ProcessingPaymentDTO(
                paymentType=PaymentType.DEPOSIT,
                fiatCurrency=config.CURRENCY,
                cryptoCurrency=cryptocurrency
            )
            headers = {
                "X-Api-Key": config.KRYPTO_EXPRESS_API_KEY,
                "Content-Type": "application/json"
            }
            payment_dto = await CryptoApiWrapper.fetch_api_request(
                f"{config.KRYPTO_EXPRESS_API_URL}/payment",
                method="POST",
                data=payment_dto.model_dump_json(exclude_none=True),
                headers=headers
            )
            payment_dto = ProcessingPaymentDTO.model_validate(payment_dto, from_attributes=True)
            if payment_dto:
                topup_ref = await PaymentRepository.create(payment_dto.id, user.id, message.message_id, session)
                await session_commit(session)
                return Localizator.get_text(BotEntity.USER, "top_up_balance_msg").format(
                    topup_reference=topup_ref,
                    crypto_name=payment_dto.cryptoCurrency.name,
                    addr=payment_dto.address,
                    crypto_amount=payment_dto.cryptoAmount,
                    fiat_amount=payment_dto.fiatAmount,
                    currency_text=Localizator.get_currency_text(),
                    status=Localizator.get_text(BotEntity.USER, "status_pending")
                )

    @staticmethod
    async def orchestrate_payment_processing(
        order_id: int,
        crypto_currency: Cryptocurrency,
        session: AsyncSession | Session
    ) -> tuple[InvoiceDTO, bool]:
        """
        Orchestrates payment processing with invoice creation and wallet handling.

        This is called AFTER order creation and (for physical items) address collection.

        Flow:
        1. Get order details
        2. Check wallet balance
        3. Deduct wallet (full/partial/none)
        4. Calculate remaining amount
        5. Create invoice:
           - remaining > 0: crypto invoice for REST amount
           - remaining = 0: wallet-only invoice (tracking)
        6. Update order status (PAID or PENDING_PAYMENT)
        7. If PAID: complete order (mark sold, deliver items)

        Args:
            order_id: Order ID
            crypto_currency: Selected cryptocurrency (or PENDING_SELECTION)
            session: Database session

        Returns:
            Tuple of (invoice, needs_crypto_payment)
            - invoice: Created InvoiceDTO
            - needs_crypto_payment: True if crypto payment needed, False if fully paid by wallet

        Raises:
            ValueError: If order not found or crypto not selected when needed
        """
        from services.order import OrderService

        # 1. Get order details
        from exceptions.order import OrderNotFoundException

        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            raise OrderNotFoundException(order_id)

        order_total = order.total_price
        logging.info(f"💳 Processing payment for order {order_id}: Total={order_total:.2f} EUR")

        # 2. Check wallet balance
        user = await UserRepository.get_by_id(order.user_id, session)
        wallet_balance = user.top_up_amount
        logging.info(f"💰 User {user.id} wallet balance: {wallet_balance:.2f} EUR")

        # 3. Calculate wallet usage (full/partial/none)
        wallet_used = round(min(wallet_balance, order_total), 2)
        remaining_amount = round(order_total - wallet_used, 2)

        logging.info(f"💵 Wallet breakdown: Used={wallet_used:.2f} EUR | Remaining={remaining_amount:.2f} EUR")

        # 4. Deduct wallet balance if any used
        if wallet_used > 0:
            user.top_up_amount = round(user.top_up_amount - wallet_used, 2)
            await UserRepository.update(user, session)
            logging.info(f"✅ Deducted {wallet_used:.2f} EUR from wallet (new balance: {user.top_up_amount:.2f} EUR)")

        # 5. Update order with wallet usage
        order.wallet_used = wallet_used
        await OrderRepository.update(order, session)

        # 6. Create invoice
        if remaining_amount > 0:
            # Crypto payment needed - create invoice with KryptoExpress
            from exceptions.payment import CryptocurrencyNotSelectedException

            if crypto_currency == Cryptocurrency.PENDING_SELECTION:
                raise CryptocurrencyNotSelectedException(order_id)

            invoice = await InvoiceService.create_invoice_with_kryptoexpress(
                order_id=order_id,
                fiat_amount=remaining_amount,  # Invoice for REST amount only!
                fiat_currency=config.CURRENCY,
                crypto_currency=crypto_currency,
                session=session
            )
            logging.info(f"📋 Created crypto invoice for remaining amount: {remaining_amount:.2f} EUR")

            # Order stays PENDING_PAYMENT (waiting for crypto)
            await OrderRepository.update_status(order_id, OrderStatus.PENDING_PAYMENT, session)
            needs_crypto_payment = True

            # Commit invoice and order status to database
            await session_commit(session)

        else:
            # Wallet covered everything - create tracking invoice
            invoice = await InvoiceService.create_wallet_only_invoice(
                order_id=order_id,
                fiat_amount=order_total,  # Total order amount
                fiat_currency=config.CURRENCY,
                session=session
            )
            logging.info(f"✅ Order fully paid by wallet ({wallet_used:.2f} EUR) - created tracking invoice")

            # Order is now PAID
            await OrderRepository.update_status(order_id, OrderStatus.PAID, session)
            needs_crypto_payment = False

            # Commit before completing order
            await session_commit(session)

            # Complete order: mark items sold, create buy records, deliver items
            await OrderService.complete_order_payment(order_id, session)
            logging.info(f"✅ Order {order_id} completed (paid by wallet)")

        return invoice, needs_crypto_payment

    @staticmethod
    async def get_payment_history_details(order_id: int, session: AsyncSession | Session) -> dict:
        """
        Gets comprehensive payment history details for an order.

        Aggregates data from Order, Invoice(s), and PaymentTransaction(s) tables.
        Used for admin order detail view to show complete payment information.

        Args:
            order_id: Order ID

        Returns:
            Dictionary with payment history:
            {
                "order_created_at": datetime,
                "payment_received_at": datetime | None,
                "wallet_amount_used": float,
                "crypto_payments": [
                    {
                        "currency": str,
                        "crypto_amount": float,
                        "fiat_amount": float,
                        "kryptoexpress_transaction_id": int,
                        "kryptoexpress_order_id": str (invoice_number),
                        "payment_address": str,
                        "transaction_hash": str | None,
                        "confirmed_at": datetime,
                        "is_overpayment": bool,
                        "is_underpayment": bool,
                        "is_late_payment": bool,
                        "penalty_applied": bool,
                        "penalty_percent": float,
                        "wallet_credit_amount": float | None
                    }
                ],
                "underpayment_retries": int,
                "late_payment_penalty": float,
                "total_paid": float
            }

        Raises:
            OrderNotFoundException: If order not found
        """
        from repositories.invoice import InvoiceRepository
        from repositories.payment_transaction import PaymentTransactionRepository
        from exceptions.order import OrderNotFoundException

        # Get order
        order = await OrderRepository.get_by_id(order_id, session)
        if not order:
            raise OrderNotFoundException(order_id)

        # Get all invoices for this order (may have multiple for partial payments)
        invoices = await InvoiceRepository.get_by_order_id(order_id, session)

        # Get all payment transactions for this order
        transactions = await PaymentTransactionRepository.get_by_order_id(order_id, session)

        # Build crypto payments list
        crypto_payments = []
        for transaction in transactions:
            # Find corresponding invoice for this transaction
            invoice = next((inv for inv in invoices if inv.id == transaction.invoice_id), None)

            crypto_payments.append({
                "currency": transaction.crypto_currency.name,
                "crypto_amount": transaction.crypto_amount,
                "fiat_amount": transaction.fiat_amount,
                "kryptoexpress_transaction_id": transaction.payment_processing_id,
                "kryptoexpress_order_id": invoice.invoice_number if invoice else "N/A",
                "payment_address": transaction.payment_address,
                "transaction_hash": transaction.transaction_hash,
                "confirmed_at": transaction.received_at,
                "is_overpayment": transaction.is_overpayment,
                "is_underpayment": transaction.is_underpayment,
                "is_late_payment": transaction.is_late_payment,
                "penalty_applied": transaction.penalty_applied,
                "penalty_percent": transaction.penalty_percent,
                "wallet_credit_amount": transaction.wallet_credit_amount
            })

        # Calculate late payment penalty (if any transaction has penalty)
        late_payment_penalty = 0.0
        for transaction in transactions:
            if transaction.penalty_applied and transaction.is_late_payment:
                # Calculate penalty amount from percentage
                late_payment_penalty += transaction.fiat_amount * (transaction.penalty_percent / 100)

        # Calculate total paid (wallet + all crypto transactions)
        total_paid = order.wallet_used + sum(t.fiat_amount for t in transactions)

        return {
            "order_created_at": order.created_at,
            "payment_received_at": order.paid_at,
            "wallet_amount_used": order.wallet_used,
            "crypto_payments": crypto_payments,
            "underpayment_retries": order.retry_count,
            "late_payment_penalty": late_payment_penalty,
            "total_paid": total_paid
        }
