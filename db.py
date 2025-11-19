from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
import logging

from sqlalchemy import event, Engine, text, create_engine, Result, CursorResult
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

import config
from config import DB_NAME
from models.base import Base

if config.DB_ENCRYPTION:
    # Installing sqlcipher3 on windows has some difficulties,
    # so if you want to test the version with database encryption use Linux.
    from sqlcipher3 import dbapi2 as sqlcipher
"""
Imports of these models are needed to correctly create tables in the database.
For more information see https://stackoverflow.com/questions/7478403/sqlalchemy-classes-across-files
"""
from models.item import Item
from models.price_tier import PriceTier
from models.shipping_tier import ShippingTier
from models.cart import Cart
from models.cartItem import CartItem
from models.user import User
from models.buy import Buy
from models.buyItem import BuyItem
from models.category import Category
from models.subcategory import Subcategory
from models.deposit import Deposit
from models.order import Order
from models.invoice import Invoice
from models.payment_transaction import PaymentTransaction
from models.user_strike import UserStrike
from models.referral_usage import ReferralUsage
from models.referral_discount import ReferralDiscount

# SQLAlchemy logging configuration
# HARD DISABLE SQL echo - use separate SQL_DEBUG env var if needed in future
# This prevents logs from being cluttered with SQL statements
sql_echo = False

url = ""
engine = None
session_maker = None
if config.DB_ENCRYPTION:
    # DEBUG: Check if password is loaded
    db_pass = config.DB_PASS
    logging.critical(f"🔐 DB_ENCRYPTION=True, DB_PASS={'<empty>' if not db_pass else f'<{len(db_pass)} chars>'}")

    if not db_pass:
        raise ValueError("DB_ENCRYPTION=true but DB_PASS is empty! Check .env configuration.")

    # SQLCipher: Password in URL (ilyarolf's original approach)
    # Format: sqlite+pysqlcipher://:{password}@////absolute/path (4 slashes for absolute path)
    # Container path: /bot/data/ (mounted from ./data on host)
    # IMPORTANT: Relative paths (3 slashes) do NOT work with SQLAlchemy + SQLCipher
    url = f"sqlite+pysqlcipher://:{db_pass}@////bot/data/{DB_NAME}"
    engine = create_engine(
        url,
        echo=sql_echo,
        module=sqlcipher,
        connect_args={'check_same_thread': False}
    )
    session_maker = sessionmaker(engine, expire_on_commit=False)
else:
    url = f"sqlite+aiosqlite:///data/{DB_NAME}"
    engine = create_async_engine(url, echo=sql_echo)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Note: SQLAlchemy/aiosqlite logger configuration moved to utils/logging_config.py
# This ensures proper initialization order (after root logger setup)

data_folder = Path("data")
if data_folder.exists() is False:
    data_folder.mkdir()


@asynccontextmanager
async def get_db_session() -> AsyncSession | Session:
    session = None
    try:
        if config.DB_ENCRYPTION:
            with session_maker() as sync_session:
                session = sync_session
                yield session
        else:
            async with session_maker() as async_session:
                session = async_session
                yield session
    finally:
        if isinstance(session, AsyncSession):
            await session.close()
        elif isinstance(session, Session):
            session.close()


async def session_execute(stmt, session: AsyncSession | Session) -> Result[Any] | CursorResult[Any]:
    if isinstance(session, AsyncSession):
        query_result = await session.execute(stmt)
        return query_result
    else:
        query_result = session.execute(stmt)
        return query_result


async def session_flush(session: AsyncSession | Session) -> None:
    if isinstance(session, AsyncSession):
        await session.flush()
    else:
        session.flush()


async def session_commit(session: AsyncSession | Session) -> None:
    if isinstance(session, AsyncSession):
        await session.commit()
    else:
        session.commit()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    if config.DB_ENCRYPTION:
        # CRITICAL: Set cipher parameters BEFORE key
        # These must match the parameters used when the DB was created
        cursor.execute("PRAGMA cipher_page_size = 4096")
        cursor.execute("PRAGMA kdf_iter = 256000")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")

        # Set encryption key AFTER cipher parameters
        # URL password alone is not sufficient for CREATE operations
        cursor.execute(f"PRAGMA key = '{config.DB_PASS}'")
        cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def check_all_tables_exist(session: AsyncSession | Session):
    for table in Base.metadata.tables.values():
        sql_query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table.name}';"
        if isinstance(session, AsyncSession):
            result = await session.execute(text(sql_query))
            if result.scalar() is None:
                return False
        else:
            result = session.execute(text(sql_query))
            if result.scalar() is None:
                return False
    return True


async def create_db_and_tables():
    async with get_db_session() as session:
        if await check_all_tables_exist(session):
            pass
        else:
            if isinstance(session, AsyncSession):
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
                    await conn.run_sync(Base.metadata.create_all)
            else:
                Base.metadata.drop_all(bind=engine)
                Base.metadata.create_all(bind=engine)
