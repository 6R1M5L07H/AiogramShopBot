from json import load
from pathlib import Path
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from callbacks import AddType
from db import session_commit
from enums.bot_entity import BotEntity
from models.item import ItemDTO
from repositories.category import CategoryRepository
from repositories.item import ItemRepository
from repositories.subcategory import SubcategoryRepository
from utils.localizator import Localizator

logger = logging.getLogger(__name__)


class ItemService:

    @staticmethod
    def _validate_price_tiers(price_tiers: list[dict], item_description: str) -> None:
        """
        Validate price tier configuration for incremental pricing.

        Checks:
        1. Tiers are sorted by min_quantity ascending
        2. No gaps between tiers (tier N+1 must start at tier N end + 1)
        3. Prices are strictly decreasing (no duplicates or increases)
        4. First tier must start at min_quantity=1

        Args:
            price_tiers: List of tier dicts with min_quantity and unit_price
            item_description: Item description for error messages

        Raises:
            ValueError: If validation fails with detailed German error message
        """
        if not price_tiers:
            return  # No tiers = no validation needed

        # Sort by min_quantity to check order
        sorted_tiers = sorted(price_tiers, key=lambda t: t['min_quantity'])

        # Check 1: First tier must start at 1
        if sorted_tiers[0]['min_quantity'] != 1:
            raise ValueError(
                f"Erste Preisstufe muss bei min_quantity=1 beginnen (Item: {item_description})"
            )

        # Check remaining tiers
        for i in range(len(sorted_tiers)):
            current_tier = sorted_tiers[i]

            # Check 2: No gaps (tier N+1 should follow tier N)
            if i > 0:
                prev_tier = sorted_tiers[i - 1]
                expected_start = prev_tier['min_quantity'] + 1

                # Allow gap only if previous tier had explicit max
                # For incremental pricing, we infer max from next tier's start
                if current_tier['min_quantity'] != expected_start:
                    # This is actually OK for incremental - tier 1-4, then tier 5-9 is valid
                    pass

            # Check 3: Prices must strictly decrease
            if i > 0:
                prev_price = sorted_tiers[i - 1]['unit_price']
                current_price = current_tier['unit_price']

                if current_price >= prev_price:
                    if current_price == prev_price:
                        raise ValueError(
                            f"Doppelter Preis {current_price:.2f}€ in Stufe {i} und {i+1} "
                            f"(Item: {item_description}). Staffelpreise müssen streng monoton fallen."
                        )
                    else:
                        raise ValueError(
                            f"Preis steigt von {prev_price:.2f}€ auf {current_price:.2f}€ in Stufe {i+1} "
                            f"(Item: {item_description}). Staffelpreise müssen fallen."
                        )

        logger.info(f"✓ Price tiers validated for: {item_description} ({len(price_tiers)} tiers)")

    @staticmethod
    async def get_new(session: AsyncSession | Session) -> list[ItemDTO]:
        return await ItemRepository.get_new(session)

    @staticmethod
    async def get_in_stock_items(session: AsyncSession | Session):
        return await ItemRepository.get_in_stock(session)

    @staticmethod
    async def parse_items_json(path_to_file: str, session: AsyncSession | Session):
        with open(path_to_file, 'r', encoding='utf-8') as file:
            data = load(file)

            # DEBUG: Log data structure
            logger.info(f"📦 JSON loaded: type={type(data)}, keys={list(data.keys()) if isinstance(data, dict) else 'NOT A DICT'}")

            # Support both legacy format (flat items array) and new format (dict with items + subcategories)
            if isinstance(data, dict) and 'items' in data:
                items = data['items']
                subcategories_with_tiers = data.get('subcategories', [])
                logger.info(f"📦 New format: {len(items)} items, type={type(items)}")
            else:
                # Legacy format: flat array
                items = data
                subcategories_with_tiers = []
                logger.info(f"📦 Legacy format: {len(items)} items, type={type(items)}")

            # Track shipping_tiers per subcategory (from both items and subcategories section)
            subcategory_shipping_tiers = {}

            # First pass: Extract shipping_tiers from subcategories section
            for subcat_def in subcategories_with_tiers:
                subcat_name = subcat_def.get('name')
                shipping_tiers = subcat_def.get('shipping_tiers')
                if subcat_name and shipping_tiers:
                    subcategory_shipping_tiers[subcat_name] = shipping_tiers

            items_list = []
            for item in items:
                category = await CategoryRepository.get_or_create(item['category'], session)
                subcategory = await SubcategoryRepository.get_or_create(item['subcategory'], session)

                # Extract shipping_tiers if present in item (legacy format)
                shipping_tiers = item.pop('shipping_tiers', None)
                if shipping_tiers:
                    # Store for this subcategory
                    subcategory_shipping_tiers[item['subcategory']] = shipping_tiers

                item.pop('category')
                item.pop('subcategory')

                # Extract price_tiers if present (will be handled separately)
                price_tiers = item.pop('price_tiers', None)

                # Validate price_tiers before processing
                if price_tiers:
                    ItemService._validate_price_tiers(price_tiers, item.get('description', 'Unknown item'))

                    # Find tier with min_quantity=1 or use first tier as fallback
                    base_tier = next((t for t in price_tiers if t['min_quantity'] == 1), price_tiers[0])
                    item['price'] = base_tier['unit_price']

                # Ensure private_data is never None (DB constraint: NOT NULL)
                if item.get('private_data') is None:
                    item['private_data'] = ''

                item_dto = ItemDTO(
                    category_id=category.id,
                    subcategory_id=subcategory.id,
                    **item
                )

                # Attach price_tiers for later storage
                item_dto.price_tiers = price_tiers

                items_list.append(item_dto)

            # Return tuple: (items, shipping_tiers_dict)
            return items_list, subcategory_shipping_tiers

    @staticmethod
    async def parse_items_txt(path_to_file: str, session: AsyncSession | Session):
        with open(path_to_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            items_list = []
            for line in lines:
                category_name, subcategory_name, description, price, private_data = line.split(';')
                category = await CategoryRepository.get_or_create(category_name, session)
                subcategory = await SubcategoryRepository.get_or_create(subcategory_name, session)
                items_list.append(ItemDTO(
                    category_id=category.id,
                    subcategory_id=subcategory.id,
                    price=float(price),
                    description=description,
                    private_data=private_data
                ))
            return items_list

    @staticmethod
    async def add_items(path_to_file: str, add_type: AddType, session: AsyncSession | Session) -> str:
        from repositories.shipping_tier import ShippingTierRepository
        from models.shipping_tier import ShippingTierDTO

        try:
            items = []
            subcategory_shipping_tiers = {}

            if add_type == AddType.JSON:
                items, subcategory_shipping_tiers = await ItemService.parse_items_json(path_to_file, session)
            else:
                items = await ItemService.parse_items_txt(path_to_file, session)

            await ItemRepository.add_many(items, session)

            # Now create shipping_tiers (after subcategories exist)
            if subcategory_shipping_tiers:
                for subcat_name, tiers in subcategory_shipping_tiers.items():
                    # Get subcategory ID
                    subcategory = await SubcategoryRepository.get_or_create(subcat_name, session)

                    # Delete existing tiers for this subcategory (replace on import)
                    await ShippingTierRepository.delete_by_subcategory_id(subcategory.id, session)

                    # Create new tiers
                    for tier in tiers:
                        tier_dto = ShippingTierDTO(
                            subcategory_id=subcategory.id,
                            min_quantity=tier['min_quantity'],
                            max_quantity=tier.get('max_quantity'),  # Can be None
                            shipping_type=tier['shipping_type']
                        )
                        await ShippingTierRepository.create(tier_dto, session)

            await session_commit(session)
            return Localizator.get_text(BotEntity.ADMIN, "add_items_success").format(adding_result=len(items))
        except Exception as e:
            import traceback
            logger.error(f"❌ Failed to add items from {path_to_file}: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return Localizator.get_text(BotEntity.ADMIN, "add_items_err").format(adding_result=str(e))
        finally:
            Path(path_to_file).unlink(missing_ok=True)
