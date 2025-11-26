import json
import config
from enums.bot_entity import BotEntity


class Localizator:
    localization_filename = f"./l10n/{config.BOT_LANGUAGE}.json"

    # Unit localization map (EN → localized)
    # Only text-based units that vary by language need entries
    # International units (g, kg, ml, l, oz, lb) are pass-through
    UNIT_I18N_MAP = {
        "pcs.": {"de": "Stk.", "en": "pcs."},
        "pairs": {"de": "Paar", "en": "pairs"},
        "pkg.": {"de": "Pack.", "en": "pkg."}
    }

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
    def localize_unit(unit: str) -> str:
        """
        Localize measurement unit for display.

        International units (g, kg, ml, l, oz, lb, m, m2) are pass-through (unchanged).
        Text-based units (pcs., pairs, pkg.) are translated based on BOT_LANGUAGE.

        Args:
            unit: EN-based unit string (e.g., "pcs.", "g", "kg")

        Returns:
            Localized unit string

        Examples:
            >>> # When BOT_LANGUAGE = "de"
            >>> Localizator.localize_unit("pcs.")
            'Stk.'
            >>> Localizator.localize_unit("g")
            'g'  # Pass-through (international)

            >>> # When BOT_LANGUAGE = "en"
            >>> Localizator.localize_unit("pcs.")
            'pcs.'
            >>> Localizator.localize_unit("pairs")
            'pairs'
        """
        if not unit:
            return unit

        # Normalize for lookup (strip whitespace, lowercase)
        normalized = unit.strip().lower()

        # Check if unit has localization mapping
        if normalized in Localizator.UNIT_I18N_MAP:
            translation_map = Localizator.UNIT_I18N_MAP[normalized]
            language = config.BOT_LANGUAGE.lower()

            # Return localized version, fallback to EN, fallback to original
            return translation_map.get(language, translation_map.get("en", unit))

        # International unit (no mapping) → pass-through
        return unit
