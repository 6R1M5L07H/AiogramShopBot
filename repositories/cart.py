from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_execute, session_flush
from models.cart import Cart, CartDTO
from models.cartItem import CartItemDTO, CartItem
from repositories.cartItem import CartItemRepository


class CartRepository:
    @staticmethod
    async def get_or_create(user_id: int, session: AsyncSession | Session):
        stmt = select(Cart).where(Cart.user_id == user_id)
        cart = await session_execute(stmt, session)
        cart = cart.scalar()
        if cart is None:
            cart = Cart(user_id=user_id)
            session.add(cart)
            await session_flush(session)
            return CartDTO.model_validate(cart, from_attributes=True)
        else:
            return CartDTO.model_validate(cart, from_attributes=True)

    @staticmethod
    async def add_to_cart(cart_item: CartItemDTO, cart: CartDTO, session: AsyncSession | Session):
        # if there exists a cart with a cart_item with the same category and subcategory, increase the quantity
        # and if not, there is either no cart_item in the cart at all or no cart_item of the same (sub-)category
        get_old_cart_content_stmt = select(Cart).join(
            CartItem, Cart.id == CartItem.cart_id).where(
            Cart.id == cart.id,
            CartItem.subcategory_id == cart_item.subcategory_id)
        old_cart_records = await session_execute(get_old_cart_content_stmt, session)
        old_cart_records = old_cart_records.scalar()

        if old_cart_records is None:
            # New item: Calculate tier breakdown for cart_item.quantity
            from services.pricing import PricingService
            import json

            pricing_result = await PricingService.calculate_optimal_price(
                subcategory_id=cart_item.subcategory_id,
                quantity=cart_item.quantity,
                session=session
            )
            cart_item.tier_breakdown = json.dumps([
                {"quantity": item.quantity, "unit_price": item.unit_price, "total": item.total}
                for item in pricing_result.breakdown
            ])

            await CartItemRepository.create(cart_item, session)
        elif old_cart_records is not None:
            # Existing item: Get current quantity and calculate new tier breakdown
            from services.pricing import PricingService
            import json

            get_cart_item_stmt = select(CartItem).where(
                CartItem.cart_id == cart.id,
                CartItem.subcategory_id == cart_item.subcategory_id
            )
            result = await session_execute(get_cart_item_stmt, session)
            existing_cart_item = result.scalar()

            new_total_quantity = existing_cart_item.quantity + cart_item.quantity

            pricing_result = await PricingService.calculate_optimal_price(
                subcategory_id=cart_item.subcategory_id,
                quantity=new_total_quantity,
                session=session
            )

            tier_breakdown_json = json.dumps([
                {"quantity": item.quantity, "unit_price": item.unit_price, "total": item.total}
                for item in pricing_result.breakdown
            ])

            quantity_update_stmt = (update(CartItem).where(
                CartItem.cart_id == cart.id,
                CartItem.subcategory_id == cart_item.subcategory_id
            ).values(
                quantity=new_total_quantity,
                tier_breakdown=tier_breakdown_json
            ))
            await session_execute(quantity_update_stmt, session)

    @staticmethod
    async def get_items_by_subcategory(
        cart_id: int,
        subcategory_id: int,
        session: AsyncSession | Session
    ) -> list[CartItemDTO]:
        """
        Get all cart items for a specific subcategory.

        Args:
            cart_id: ID of the cart
            subcategory_id: ID of the subcategory
            session: Database session

        Returns:
            List of CartItemDTO for the subcategory (usually 0 or 1 item)
        """
        stmt = select(CartItem).where(
            CartItem.cart_id == cart_id,
            CartItem.subcategory_id == subcategory_id
        )
        result = await session_execute(stmt, session)
        items = result.scalars().all()
        return [CartItemDTO.model_validate(item, from_attributes=True) for item in items]
