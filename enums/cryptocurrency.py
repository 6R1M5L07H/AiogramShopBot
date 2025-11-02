from enum import Enum

import config


class Cryptocurrency(str, Enum):
    BNB = "BNB"
    BTC = "BTC"
    LTC = "LTC"
    ETH = "ETH"
    SOL = "SOL"
    USDT_TRC20 = "USDT_TRC20"
    USDT_ERC20 = "USDT_ERC20"
    USDC_ERC20 = "USDC_ERC20"
    PENDING_SELECTION = "PENDING_SELECTION"  # Placeholder when order created before crypto selected

    def get_divider(self):
        """
        Returns the number of decimal places for this cryptocurrency.

        Values are read from config.CRYPTO_DECIMAL_PLACES, which can be
        overridden via environment variables (CRYPTO_DECIMALS_BTC, etc.)

        Returns:
            int: Number of decimal places (e.g., 8 for BTC = satoshi precision)
        """
        # Import here to avoid circular dependency
        import config

        # Use config value, with fallback to historical defaults
        return config.CRYPTO_DECIMAL_PLACES.get(self.value, 8)

    def get_coingecko_name(self) -> str:
        match self:
            case Cryptocurrency.BTC:
                return "bitcoin"
            case Cryptocurrency.LTC:
                return "litecoin"
            case Cryptocurrency.ETH:
                return "ethereum"
            case Cryptocurrency.BNB:
                return "binancecoin"
            case Cryptocurrency.SOL:
                return "solana"
            case Cryptocurrency.USDT_TRC20 | Cryptocurrency.USDT_ERC20:
                return "tether"
            case Cryptocurrency.USDC_ERC20:
                return "usd-coin"

    def get_localization_key(self) -> tuple:
        """
        Returns (BotEntity, localization_key) for payment button text.

        Returns:
            Tuple of (BotEntity enum value, localization key string)
        """
        from enums.bot_entity import BotEntity

        mapping = {
            Cryptocurrency.BTC: (BotEntity.COMMON, "btc_top_up"),
            Cryptocurrency.ETH: (BotEntity.COMMON, "eth_top_up"),
            Cryptocurrency.LTC: (BotEntity.COMMON, "ltc_top_up"),
            Cryptocurrency.SOL: (BotEntity.COMMON, "sol_top_up"),
            Cryptocurrency.BNB: (BotEntity.COMMON, "bnb_top_up"),
            Cryptocurrency.USDT_TRC20: (BotEntity.USER, "usdt_trc20_top_up"),
            Cryptocurrency.USDT_ERC20: (BotEntity.USER, "usdt_erc20_top_up"),
            Cryptocurrency.USDC_ERC20: (BotEntity.USER, "usdc_erc20_top_up"),
        }
        return mapping[self]

    @staticmethod
    def get_payment_options() -> list['Cryptocurrency']:
        """
        Returns list of cryptocurrencies available for payments and wallet top-up.
        Single source of truth for crypto selection across entire application.
        Based on ilyarolf's original wallet top-up implementation.
        Order defines button display order.

        Returns:
            List of Cryptocurrency enum values in display order
        """
        return [
            Cryptocurrency.BTC,
            Cryptocurrency.LTC,
            Cryptocurrency.SOL,
            Cryptocurrency.ETH,
            Cryptocurrency.BNB,
        ]
