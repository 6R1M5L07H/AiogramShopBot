from sqlalchemy import select

from db import session_maker
from models.item import Item
from models.subcategory import Subcategory


class SubcategoryService:
    @staticmethod
    def get_or_create_one(subcategory_name: str) -> Subcategory:
        with session_maker() as session:
            stmt = select(Subcategory).where(Subcategory.name == subcategory_name)
            subcategory = session.execute(stmt)
            subcategory = subcategory.scalar()
            if subcategory is None:
                new_category_obj = Subcategory(name=subcategory_name)
                session.add(new_category_obj)
                session.commit()
                session.refresh(new_category_obj)
                return new_category_obj
            else:
                return subcategory

    @staticmethod
    def get_all() -> list[Subcategory]:
        with session_maker() as session:
            stmt = select(Subcategory).distinct()
            subcategories = session.execute(stmt)
            subcategories = subcategories.scalars().all()
            return subcategories

    @staticmethod
    def get_by_primary_key(subcategory_id) -> Subcategory:
        with session_maker() as session:
            stmt = select(Subcategory).where(Subcategory.id == subcategory_id)
            subcategory = session.execute(stmt)
            return subcategory.scalar()

    @staticmethod
    def delete_if_not_used(subcategory_id: int):
        # TODO("Need testing")
        with session_maker() as session:
            stmt = select(Subcategory).join(Item, Item.subcategory_id == subcategory_id).where(
                Subcategory.id == subcategory_id)
            result = session.execute(stmt)
            if result.scalar() is None:
                get_stmt = select(Subcategory).where(Subcategory.id == subcategory_id)
                subcategory = session.execute(get_stmt)
                subcategory = subcategory.scalar()
                session.delete(subcategory)
                session.commit()