from enum import Enum


class ItemUnit(str, Enum):
    """
    Measurement units for items.

    EN-based values are stored in the database and localized for display.
    Examples:
    - PIECES ("pcs.") → "Stk." in German
    - GRAMS ("g") → remains "g" (international)
    """

    # Text-based units (localized)
    PIECES = "pcs."
    PAIRS = "pairs"
    PACKAGES = "pkg."

    # Weight units (international, not localized)
    GRAMS = "g"
    KILOGRAMS = "kg"

    # Volume units (international, not localized)
    MILLILITERS = "ml"
    LITERS = "l"

    # Length/Area units (international, not localized)
    METERS = "m"
    SQUARE_METERS = "m2"

    @classmethod
    def from_string(cls, value: str) -> 'ItemUnit':
        """
        Convert string to ItemUnit enum.

        Handles case-insensitive matching and whitespace.

        Args:
            value: String value to convert

        Returns:
            ItemUnit enum member

        Raises:
            ValueError: If value is not a valid unit

        Examples:
            >>> ItemUnit.from_string("pcs.")
            ItemUnit.PIECES
            >>> ItemUnit.from_string(" G ")
            ItemUnit.GRAMS
        """
        if not value:
            raise ValueError("Unit cannot be empty")

        # Normalize: strip whitespace, lowercase for lookup
        normalized = value.strip().lower()

        # Check if empty after stripping
        if not normalized:
            raise ValueError("Unit cannot be empty")

        # Try exact match first (case-insensitive)
        for unit in cls:
            if unit.value.lower() == normalized:
                return unit

        # If no match, raise error with suggestions
        valid_units = [u.value for u in cls]
        raise ValueError(
            f"Invalid unit '{value}'. Valid units: {', '.join(valid_units)}"
        )

    @property
    def display_name(self) -> str:
        """
        Get display name for documentation/errors.

        Returns:
            Human-readable name

        Examples:
            >>> ItemUnit.PIECES.display_name
            'Pieces'
            >>> ItemUnit.SQUARE_METERS.display_name
            'Square Meters'
        """
        return self.name.replace('_', ' ').title()