import math
from sqlalchemy import select, func
import config
from models.category import Category
from models.item import Item
from db import session_commit, session_execute, session_refresh, get_db_session


class CategoryService:

    @staticmethod
    async def get_or_create_one(category_name: str) -> Category:
        async with get_db_session() as session:
            stmt = select(Category).where(Category.name == category_name)
            category = await session_execute(stmt, session)
            category = category.scalar()
            if category is None:
                new_category_obj = Category(name=category_name)
                session.add(new_category_obj)
                await session_commit(session)
                await session_refresh(session, new_category_obj)
                return new_category_obj
            else:
                return category

    @staticmethod
    async def get_by_primary_key(primary_key: int) -> Category:
        async with get_db_session() as session:
            stmt = select(Category).where(Category.id == primary_key)
            category = await session_execute(stmt, session)
            return category.scalar()

    @staticmethod
    async def get_to_delete(page: int = 0):
        async with get_db_session() as session:
            stmt = select(Category).join(Item, Item.category_id == Category.id
                                         ).where(Item.is_sold == 0).distinct().limit(config.PAGE_ENTRIES).offset(
                page * config.PAGE_ENTRIES).group_by(Category.name)
            categories = await session_execute(stmt, session)
            return categories.scalars().all()

    @staticmethod
    async def get_unsold(page) -> list[Category]:
        async with get_db_session() as session:
            stmt = select(Category).join(Item, Item.category_id == Category.id).where(
                Item.is_sold == 0).distinct().limit(config.PAGE_ENTRIES).offset(
                page * config.PAGE_ENTRIES).group_by(Category.name)
            category_names = await session_execute(stmt, session)
            return category_names.scalars().all()

    @staticmethod
    async def get_maximum_page() -> int:
        async with get_db_session() as session:
            unique_categories_subquery = (
                select(Category.id)
                .join(Item, Item.category_id == Category.id)
                .filter(Item.is_sold == 0)
                .distinct()
            ).alias('unique_categories')
            stmt = select(func.count()).select_from(unique_categories_subquery)
            max_page = await session_execute(stmt, session)
            max_page = max_page.scalar_one()
            if max_page % config.PAGE_ENTRIES == 0:
                return max_page / config.PAGE_ENTRIES - 1
            else:
                return math.trunc(max_page / config.PAGE_ENTRIES)

    @staticmethod
    async def get_name(category_id) -> str:
        async with get_db_session() as session:
            stmt = select(Category.name).where(Category.id == category_id)
            category_name = await session.execute(stmt)
            category_name = category_name.scalar()
            if category_name is None:
                return ""
        return category_name