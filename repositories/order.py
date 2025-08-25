from datetime import datetime
import logging
from typing import Optional

from sqlalchemy import select, update

from db import get_db_session, session_commit, session_execute, session_refresh
from models.order import Order, OrderDTO, OrderDTOWithPrivateKey, OrderStatus
from services.encryption import EncryptionService

logger = logging.getLogger(__name__)


class OrderRepository:
    @staticmethod
    async def create(order_dto: OrderDTO) -> int:
        async with get_db_session() as session:
            order = Order(**order_dto.__dict__)
            session.add(order)
            await session_commit(session)
            await session_refresh(session, order)
            return order.id
    
    @staticmethod
    async def create_with_encrypted_key(order_dto: OrderDTO, private_key: str) -> int:
        """
        Create order with encrypted private key storage
        """
        try:
            async with get_db_session() as session:
                # Create order without private key first
                order_data = order_dto.__dict__.copy()
                order_data.pop('private_key', None)  # Remove if present
                
                order = Order(**order_data)
                session.add(order)
                await session_commit(session)
                await session_refresh(session, order)
                
                # Encrypt and store private key
                encrypted_key, salt = EncryptionService.encrypt_private_key(private_key, order.id)
                
                # Update order with encrypted key
                update_stmt = update(Order).where(Order.id == order.id).values(
                    encrypted_private_key=encrypted_key,
                    private_key_salt=salt
                )
                await session_execute(update_stmt, session)
                await session_commit(session)
                
                return order.id
                
        except Exception as e:
            logger.error(f"Error creating order with encrypted key: {str(e)}")
            raise

    @staticmethod
    async def get_by_id(order_id: int) -> OrderDTO | None:
        stmt = select(Order).where(Order.id == order_id)
        async with get_db_session() as session:
            order = await session_execute(stmt, session)
            order = order.scalar()
            if order is not None:
                return OrderDTO.model_validate(order, from_attributes=True)
            else:
                return None

    @staticmethod
    async def get_by_user_id(user_id: int) -> OrderDTO | None:
        stmt = select(Order).where(
            Order.user_id == user_id,
            Order.status.in_([OrderStatus.CREATED.value, OrderStatus.PAID.value])
        ).order_by(Order.created_at.desc()).limit(1)
        async with get_db_session() as session:
            order = await session_execute(stmt, session)
            order = order.scalar()
            if order is not None:
                return OrderDTO.model_validate(order, from_attributes=True)
            else:
                return None

    @staticmethod
    async def get_by_payment_address(address: str) -> OrderDTO | None:
        stmt = select(Order).where(Order.payment_address == address)
        async with get_db_session() as session:
            order = await session_execute(stmt, session)
            order = order.scalar()
            if order is not None:
                return OrderDTO.model_validate(order, from_attributes=True)
            else:
                return None

    @staticmethod
    async def update_status(order_id: int, status: OrderStatus) -> None:
        stmt = update(Order).where(Order.id == order_id).values(status=status.value)
        async with get_db_session() as session:
            await session_execute(stmt, session)
            await session_commit(session)

    @staticmethod
    async def update_payment_confirmation(order_id: int, paid_at: datetime) -> None:
        stmt = update(Order).where(Order.id == order_id).values(
            status=OrderStatus.PAID.value,
            paid_at=paid_at
        )
        async with get_db_session() as session:
            await session_execute(stmt, session)
            await session_commit(session)

    @staticmethod
    async def get_expired_orders() -> list[OrderDTO]:
        current_time = datetime.now()
        stmt = select(Order).where(
            Order.status == OrderStatus.CREATED.value,
            Order.expires_at <= current_time
        )
        async with get_db_session() as session:
            orders = await session_execute(stmt, session)
            return [OrderDTO.model_validate(order, from_attributes=True) for order in orders.scalars().all()]

    @staticmethod
    async def get_orders_ready_for_shipment() -> list[OrderDTO]:
        stmt = select(Order).where(Order.status == OrderStatus.PAID.value).order_by(Order.paid_at.desc())
        async with get_db_session() as session:
            orders = await session_execute(stmt, session)
            return [OrderDTO.model_validate(order, from_attributes=True) for order in orders.scalars().all()]

    @staticmethod
    async def update_shipped(order_id: int, shipped_at: datetime) -> None:
        stmt = update(Order).where(Order.id == order_id).values(
            status=OrderStatus.SHIPPED.value,
            shipped_at=shipped_at
        )
        async with get_db_session() as session:
            await session_execute(stmt, session)
            await session_commit(session)
    
    @staticmethod
    async def get_with_private_key(order_id: int, admin_id: int) -> Optional[OrderDTOWithPrivateKey]:
        """
        Get order with decrypted private key - ADMIN USE ONLY
        """
        try:
            stmt = select(Order).where(Order.id == order_id)
            async with get_db_session() as session:
                order = await session_execute(stmt, session)
                order = order.scalar()
                
                if order is None:
                    return None
                
                # Decrypt private key if encrypted
                private_key = None
                if order.encrypted_private_key and order.private_key_salt:
                    private_key = EncryptionService.decrypt_private_key(
                        order.encrypted_private_key,
                        order.private_key_salt,
                        order.id,
                        admin_id
                    )
                    
                    # Update audit fields
                    audit_stmt = update(Order).where(Order.id == order_id).values(
                        key_accessed_at=datetime.utcnow(),
                        key_accessed_by_admin=admin_id,
                        key_access_count=Order.key_access_count + 1
                    )
                    await session_execute(audit_stmt, session)
                    await session_commit(session)
                    
                elif order.private_key:  # Legacy plaintext key
                    private_key = order.private_key
                    logger.warning(f"Admin {admin_id} accessed legacy plaintext private key for order {order_id}")
                
                # Create DTO with private key
                order_dict = {
                    'id': order.id,
                    'user_id': order.user_id,
                    'status': order.status,
                    'total_amount': order.total_amount,
                    'currency': order.currency,
                    'payment_address': order.payment_address,
                    'private_key': private_key,
                    'expires_at': order.expires_at,
                    'created_at': order.created_at,
                    'paid_at': order.paid_at,
                    'shipped_at': order.shipped_at
                }
                
                return OrderDTOWithPrivateKey(**order_dict)
                
        except Exception as e:
            logger.error(f"Error getting order with private key for admin {admin_id}: {str(e)}")
            raise
    
    @staticmethod
    async def migrate_plaintext_keys() -> int:
        """
        Migrate existing plaintext private keys to encrypted storage
        Returns number of keys migrated
        """
        try:
            # Find orders with plaintext keys
            stmt = select(Order).where(
                Order.private_key.isnot(None),
                Order.encrypted_private_key.is_(None)
            )
            
            async with get_db_session() as session:
                orders = await session_execute(stmt, session)
                orders = orders.scalars().all()
                
                migrated_count = 0
                for order in orders:
                    try:
                        # Encrypt the plaintext key
                        encrypted_key, salt = EncryptionService.encrypt_private_key(
                            order.private_key, order.id
                        )
                        
                        # Update order with encrypted key and remove plaintext
                        update_stmt = update(Order).where(Order.id == order.id).values(
                            encrypted_private_key=encrypted_key,
                            private_key_salt=salt,
                            private_key=None  # Remove plaintext key
                        )
                        await session_execute(update_stmt, session)
                        migrated_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error migrating key for order {order.id}: {str(e)}")
                        continue
                
                await session_commit(session)
                logger.info(f"Successfully migrated {migrated_count} private keys to encrypted storage")
                return migrated_count
                
        except Exception as e:
            logger.error(f"Error during key migration: {str(e)}")
            raise