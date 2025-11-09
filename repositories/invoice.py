from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from models.invoice import Invoice, InvoiceDTO


class InvoiceRepository:

    @staticmethod
    async def create(invoice_dto: InvoiceDTO, session: Session | AsyncSession) -> int:
        """Erstellt eine neue Invoice und gibt die ID zurück"""
        invoice = Invoice(**invoice_dto.model_dump(exclude_none=True))
        session.add(invoice)
        await session_flush(session)
        return invoice.id

    @staticmethod
    async def get_by_order_id(order_id: int, session: Session | AsyncSession, include_inactive: bool = False) -> InvoiceDTO | None:
        """
        Holt erste Invoice einer Order (für Backward-Compatibility).
        Bei partial payments gibt es mehrere Invoices - gibt erste zurück.
        Für Refund-Logik use get_all_by_order_id() instead.

        Args:
            order_id: Order ID
            session: Database session
            include_inactive: If True, includes expired/cancelled invoices (for history views)

        Returns:
            First invoice for order, or None if not found
        """
        stmt = select(Invoice).where(Invoice.order_id == order_id)

        # Filter by is_active unless explicitly requesting inactive invoices
        if not include_inactive:
            stmt = stmt.where(Invoice.is_active == 1)

        stmt = stmt.order_by(Invoice.id).limit(1)
        result = await session_execute(stmt, session)
        invoice = result.scalar_one_or_none()

        if invoice:
            return InvoiceDTO.model_validate(invoice, from_attributes=True)
        return None

    @staticmethod
    async def get_all_by_order_id(order_id: int, session: Session | AsyncSession, include_inactive: bool = False) -> list[InvoiceDTO]:
        """
        Holt ALLE Invoices einer Order (für Underpayment-Fälle).
        Returns list of invoices sorted by creation time.

        Args:
            order_id: Order ID
            session: Database session
            include_inactive: If True, includes expired/cancelled invoices (for history views)

        Returns:
            List of invoices for order
        """
        stmt = select(Invoice).where(Invoice.order_id == order_id)

        # Filter by is_active unless explicitly requesting inactive invoices
        if not include_inactive:
            stmt = stmt.where(Invoice.is_active == 1)

        stmt = stmt.order_by(Invoice.id)
        result = await session_execute(stmt, session)
        invoices = result.scalars().all()

        return [InvoiceDTO.model_validate(inv, from_attributes=True) for inv in invoices]

    @staticmethod
    async def get_by_payment_processing_id(processing_id: int, session: Session | AsyncSession) -> InvoiceDTO | None:
        """Holt Invoice via KryptoExpress Payment ID (für Webhook)"""
        stmt = select(Invoice).where(Invoice.payment_processing_id == processing_id)
        result = await session_execute(stmt, session)
        invoice = result.scalar_one_or_none()

        if invoice:
            return InvoiceDTO.model_validate(invoice, from_attributes=True)
        return None

    @staticmethod
    async def get_next_invoice_number(session: Session | AsyncSession) -> str:
        """
        Generiert eindeutige Invoice-Nummer im Format: INV-YYYY-XXXXXX
        Beispiel: INV-2025-AX7D8K

        6-stelliger alphanumerischer Code (Großbuchstaben + Zahlen ohne 0/O/1/I zur Vermeidung von Verwechslungen)
        """
        import random
        import string
        from datetime import datetime

        year = datetime.now().year

        # Alphanumerische Zeichen ohne verwirrende: 0, O, 1, I, l
        chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'

        # Versuche max 10x einen eindeutigen Code zu generieren
        for _ in range(10):
            # Generiere 6-stelligen Code
            code = ''.join(random.choices(chars, k=6))
            invoice_number = f"INV-{year}-{code}"

            # Prüfe ob schon existiert
            stmt = select(Invoice.invoice_number).where(Invoice.invoice_number == invoice_number)
            result = await session_execute(stmt, session)
            existing = result.scalar_one_or_none()

            if not existing:
                return invoice_number

        # Fallback: sollte nie passieren (33^6 = ~1,3 Milliarden Möglichkeiten)
        raise RuntimeError("Could not generate unique invoice number after 10 attempts")

    @staticmethod
    async def mark_as_inactive(invoice_id: int, session: Session | AsyncSession) -> bool:
        """
        Marks an invoice as inactive (soft delete) to preserve audit trail.

        Args:
            invoice_id: Invoice ID to mark as inactive
            session: Database session

        Returns:
            True if marked as inactive, False if not found
        """
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        result = await session_execute(stmt, session)
        invoice = result.scalar_one_or_none()

        if invoice:
            invoice.is_active = 0
            await session_flush(session)
            return True
        return False