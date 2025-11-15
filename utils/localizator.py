import json
import config
from enums.bot_entity import BotEntity


class Localizator:
    localization_filename = f"./l10n/{config.BOT_LANGUAGE}.json"

    @staticmethod
    def get_text(entity: BotEntity, key: str) -> str:
        with open(Localizator.localization_filename, "r", encoding="UTF-8") as f:
            if entity == BotEntity.ADMIN:
                return json.loads(f.read())["admin"][key]
            elif entity == BotEntity.USER:
                return json.loads(f.read())["user"][key]
            else:
                return json.loads(f.read())["common"][key]

    @staticmethod
    def get_currency_symbol():
        return Localizator.get_text(BotEntity.COMMON, f"{config.CURRENCY.value.lower()}_symbol")

    @staticmethod
    def get_currency_text():
        return Localizator.get_text(BotEntity.COMMON, f"{config.CURRENCY.value.lower()}_text")

    @staticmethod
    def get_text_with_lang(entity: BotEntity, key: str, lang: str) -> str:
        """
        Get localized text for specific language (for Mini Apps).

        Args:
            entity: Bot entity type (USER, ADMIN, COMMON)
            key: Localization key
            lang: Language code ('de', 'en')

        Returns:
            Localized string

        Raises:
            FileNotFoundError: If language file not found
            KeyError: If key not found in localization file
        """
        localization_filename = f"./l10n/{lang}.json"
        with open(localization_filename, "r", encoding="UTF-8") as f:
            data = json.loads(f.read())
            if entity == BotEntity.ADMIN:
                return data["admin"][key]
            elif entity == BotEntity.USER:
                return data["user"][key]
            else:
                return data["common"][key]
