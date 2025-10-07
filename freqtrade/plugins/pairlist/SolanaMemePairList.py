"""
Solana Meme Coin PairList provider

Provides dynamic pair list based on Solana meme coin market cap and volume
"""

import logging
from typing import Any, Literal

from cachetools import TTLCache

from freqtrade.constants import ListPairsWithTimeframes
from freqtrade.exceptions import OperationalException
from freqtrade.plugins.pairlist.IPairList import IPairList, PairlistParameter, SupportsBacktesting


logger = logging.getLogger(__name__)


class SolanaMemePairList(IPairList):
    """
    PairList provider for Solana meme coins
    Fetches top meme coins by market cap and volume from Bitquery/DexScreener
    """
    
    is_pairlist_generator = True
    supports_backtesting = SupportsBacktesting.NO

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        
        # Configuration parameters
        self._number_assets = self._pairlistconfig.get("number_assets", 200)
        self._refresh_period = self._pairlistconfig.get("refresh_period", 1800)
        self._sort_by = self._pairlistconfig.get("sort_by", "market_cap")  # market_cap, volume, liquidity
        self._min_market_cap = self._pairlistconfig.get("min_market_cap", 1000000)  # $1M
        self._min_volume_24h = self._pairlistconfig.get("min_volume_24h", 100000)  # $100K
        self._quote_currencies = self._pairlistconfig.get("quote_currencies", ["USDC", "USDT"])
        self._exclude_stablecoins = self._pairlistconfig.get("exclude_stablecoins", True)
        self._exclude_wrapped = self._pairlistconfig.get("exclude_wrapped", True)
        
        # Cache for pair list
        self._pair_cache: TTLCache = TTLCache(maxsize=1, ttl=self._refresh_period)
        
        # Validate configuration
        if self._number_assets <= 0:
            raise OperationalException("number_assets must be greater than 0")
        
        if self._sort_by not in ["market_cap", "volume", "liquidity"]:
            raise OperationalException("sort_by must be one of: market_cap, volume, liquidity")

    def gen_pairlist(
        self, 
        tickers: dict[str, Any], 
        min_vol: float | None = None
    ) -> list[str]:
        """
        Generate pair list for Solana meme coins
        """
        # Check cache first
        if "pairs" in self._pair_cache:
            return self._pair_cache["pairs"]
        
        try:
            # Fetch meme coin data
            meme_coins = self._fetch_meme_coins()
            
            # Filter and sort
            filtered_coins = self._filter_coins(meme_coins)
            sorted_coins = self._sort_coins(filtered_coins)
            
            # Generate pairs
            pairs = []
            for coin in sorted_coins[:self._number_assets]:
                for quote in self._quote_currencies:
                    pair = f"{coin['symbol']}/{quote}"
                    pairs.append(pair)
            
            # Cache the result
            self._pair_cache["pairs"] = pairs
            
            logger.info(f"Generated {len(pairs)} pairs from {len(sorted_coins)} meme coins")
            return pairs
            
        except Exception as e:
            logger.error(f"Failed to generate meme coin pair list: {e}")
            # Return fallback pairs
            return self._get_fallback_pairs()

    def _fetch_meme_coins(self) -> list[dict[str, Any]]:
        """Fetch meme coin data from Bitquery and DexScreener"""
        try:
            # Try Bitquery first
            coins = self._fetch_from_bitquery()
            if coins:
                return coins
        except Exception as e:
            logger.warning(f"Failed to fetch from Bitquery: {e}")
        
        # Fallback to DexScreener
        try:
            coins = self._fetch_from_dexscreener()
            return coins
        except Exception as e:
            logger.error(f"Failed to fetch from DexScreener: {e}")
            return []

    def _fetch_from_bitquery(self) -> list[dict[str, Any]]:
        """Fetch meme coin data from Bitquery"""
        # This would implement the actual Bitquery GraphQL query
        # For now, return empty list to trigger fallback
        return []

    def _fetch_from_dexscreener(self) -> list[dict[str, Any]]:
        """Fetch meme coin data from DexScreener"""
        import requests
        
        url = "https://api.dexscreener.com/latest/dex/tokens/solana"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        pairs = data.get("pairs", [])
        
        # Convert to coin format
        coins = []
        seen_symbols = set()
        
        for pair in pairs:
            base_token = pair.get("baseToken", {})
            quote_token = pair.get("quoteToken", {})
            
            symbol = base_token.get("symbol")
            if not symbol or symbol in seen_symbols:
                continue
            
            # Skip if not a quote currency we want
            if quote_token.get("symbol") not in self._quote_currencies:
                continue
            
            # Skip stablecoins if configured
            if self._exclude_stablecoins and self._is_stablecoin(symbol):
                continue
            
            # Skip wrapped tokens if configured
            if self._exclude_wrapped and self._is_wrapped_token(symbol):
                continue
            
            coin_data = {
                "symbol": symbol,
                "name": base_token.get("name", symbol),
                "address": base_token.get("address"),
                "market_cap": pair.get("marketCap", 0),
                "volume_24h": pair.get("volume", {}).get("h24", 0),
                "liquidity": pair.get("liquidity", {}).get("usd", 0),
                "price_change_24h": pair.get("priceChange", {}).get("h24", 0),
                "fdv": pair.get("fdv", 0),
                "info": pair,
            }
            
            coins.append(coin_data)
            seen_symbols.add(symbol)
        
        return coins

    def _filter_coins(self, coins: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter coins based on criteria"""
        filtered = []
        
        for coin in coins:
            # Check market cap
            if coin.get("market_cap", 0) < self._min_market_cap:
                continue
            
            # Check volume
            if coin.get("volume_24h", 0) < self._min_volume_24h:
                continue
            
            # Additional filters
            if self._exclude_stablecoins and self._is_stablecoin(coin["symbol"]):
                continue
            
            if self._exclude_wrapped and self._is_wrapped_token(coin["symbol"]):
                continue
            
            filtered.append(coin)
        
        return filtered

    def _sort_coins(self, coins: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort coins by specified criteria"""
        if self._sort_by == "market_cap":
            return sorted(coins, key=lambda x: x.get("market_cap", 0), reverse=True)
        elif self._sort_by == "volume":
            return sorted(coins, key=lambda x: x.get("volume_24h", 0), reverse=True)
        elif self._sort_by == "liquidity":
            return sorted(coins, key=lambda x: x.get("liquidity", 0), reverse=True)
        else:
            return coins

    def _is_stablecoin(self, symbol: str) -> bool:
        """Check if symbol is a stablecoin"""
        stablecoins = {
            "USDC", "USDT", "USDD", "TUSD", "BUSD", "DAI", "FRAX", "LUSD", "SUSD",
            "GUSD", "HUSD", "USDK", "USDN", "UST", "USTC", "USDP", "USDS", "USDX"
        }
        return symbol.upper() in stablecoins

    def _is_wrapped_token(self, symbol: str) -> bool:
        """Check if symbol is a wrapped token"""
        wrapped_prefixes = {"W", "WETH", "WBTC", "WBNB", "WMATIC", "WAVAX"}
        return symbol.upper() in wrapped_prefixes or symbol.upper().startswith("W")

    def _get_fallback_pairs(self) -> list[str]:
        """Get fallback pairs when API calls fail"""
        fallback_coins = [
            "BONK", "WIF", "PEPE", "DOGE", "SHIB", "FLOKI", "BABYDOGE",
            "BOME", "MYRO", "POPCAT", "MEW", "GOAT", "PNUT", "ACT"
        ]
        
        pairs = []
        for coin in fallback_coins:
            for quote in self._quote_currencies:
                pairs.append(f"{coin}/{quote}")
        
        return pairs

    @staticmethod
    def available_parameters() -> dict[str, PairlistParameter]:
        """Return available parameters for this pairlist"""
        return {
            "number_assets": {
                "type": "number",
                "default": 200,
                "description": "Number of assets to include in the pairlist",
                "help": "Maximum number of meme coin pairs to include",
            },
            "refresh_period": {
                "type": "number", 
                "default": 1800,
                "description": "Refresh period in seconds",
                "help": "How often to refresh the pair list (in seconds)",
            },
            "sort_by": {
                "type": "option",
                "default": "market_cap",
                "options": ["market_cap", "volume", "liquidity"],
                "description": "Sort criteria for meme coins",
                "help": "How to sort the meme coins (by market cap, volume, or liquidity)",
            },
            "min_market_cap": {
                "type": "number",
                "default": 1000000,
                "description": "Minimum market cap in USD",
                "help": "Minimum market cap required for inclusion (in USD)",
            },
            "min_volume_24h": {
                "type": "number",
                "default": 100000,
                "description": "Minimum 24h volume in USD",
                "help": "Minimum 24-hour volume required for inclusion (in USD)",
            },
            "quote_currencies": {
                "type": "list",
                "default": ["USDC", "USDT"],
                "description": "Quote currencies to use",
                "help": "List of quote currencies to create pairs with",
            },
            "exclude_stablecoins": {
                "type": "boolean",
                "default": True,
                "description": "Exclude stablecoins",
                "help": "Whether to exclude stablecoins from the pair list",
            },
            "exclude_wrapped": {
                "type": "boolean", 
                "default": True,
                "description": "Exclude wrapped tokens",
                "help": "Whether to exclude wrapped tokens from the pair list",
            },
        }