"""SolanaDex exchange subclass for meme coin analysis"""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
from pandas import DataFrame, to_datetime

from freqtrade.constants import DEFAULT_DATAFRAME_COLUMNS
from freqtrade.enums import CandleType, MarginMode, TradingMode
from freqtrade.exceptions import OperationalException, TemporaryError
from freqtrade.exchange import Exchange
from freqtrade.exchange.exchange_types import FtHas
from freqtrade.util.datetime_helpers import dt_from_ts, dt_ts

logger = logging.getLogger(__name__)


class SolanaDex(Exchange):
    """
    SolanaDex exchange implementation for meme coin analysis
    Uses Bitquery GraphQL API as primary data source with DexScreener fallback
    """

    _ft_has: FtHas = {
        "stoploss_on_exchange": False,
        "trades_pagination": "id",
        "trades_pagination_arg": "fromId",
        "trades_has_history": False,
        "fetch_orders_limit_minutes": None,
        "l2_limit_range": [5, 10, 20, 50, 100, 500, 1000],
        "ws_enabled": False,
    }

    _supported_trading_mode_margin_pairs: list[tuple[TradingMode, Any]] = [
        (TradingMode.SPOT, MarginMode.NONE),
    ]

    def __init__(self, config: dict[str, Any], **kwargs) -> None:
        super().__init__(config, **kwargs)
        
        # Initialize Bitquery API key
        self.bitquery_api_key = os.getenv("BITQUERY_API_KEY")
        if not self.bitquery_api_key:
            logger.warning("BITQUERY_API_KEY not found in environment variables")
        
        # Initialize DexScreener API
        self.dexscreener_base_url = "https://api.dexscreener.com/latest"
        
        # Cache for markets and token metadata
        self._markets_cache: dict[str, Any] = {}
        self._token_metadata_cache: dict[str, Any] = {}
        
        # Supported timeframes (aligned with Bitquery availability)
        self._timeframes = ["5m", "15m", "1h", "4h", "1d"]
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 1.0  # 1 second between requests

    @property
    def timeframes(self) -> list[str]:
        """Return supported timeframes"""
        return self._timeframes

    @property
    def name(self) -> str:
        """Return exchange name"""
        return "solanadex"

    @property
    def id(self) -> str:
        """Return exchange ID"""
        return "solanadex"

    def exchange_has(self, key: str) -> bool:
        """Check if exchange supports specific functionality"""
        supported_features = {
            "fetchOHLCV": True,
            "fetchTickers": True,
            "fetchMarkets": True,
        }
        return supported_features.get(key, False)

    def validate_timeframes(self, timeframe: str | None) -> None:
        """Validate timeframe against supported timeframes"""
        if not timeframe:
            return
        
        if timeframe not in self._timeframes:
            raise OperationalException(
                f"Invalid timeframe '{timeframe}'. This exchange supports: {self._timeframes}"
            )

    def get_markets(
        self, 
        symbols: list[str] | None = None, 
        *, 
        tradable_only: bool = True, 
        active_only: bool = True,
        quote_currencies: list[str] | None = None,
        base_currencies: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Get available markets (meme coin pairs)
        Returns dict in ccxt format with BASE/USDC pairs
        """
        if not self._markets_cache:
            self._load_markets()
        
        markets = self._markets_cache.copy()
        
        # Filter by symbols if provided
        if symbols:
            markets = {k: v for k, v in markets.items() if k in symbols}
        
        # Filter by quote currencies if provided
        if quote_currencies:
            filtered_markets = {}
            for symbol, market in markets.items():
                if market.get("quote") in quote_currencies:
                    filtered_markets[symbol] = market
            markets = filtered_markets
        
        return markets

    def _load_markets(self) -> None:
        """Load markets from Bitquery and DexScreener"""
        try:
            # Try Bitquery first
            markets = self._fetch_markets_from_bitquery()
            if markets:
                self._markets_cache = markets
                logger.info(f"Loaded {len(markets)} markets from Bitquery")
                return
        except Exception as e:
            logger.warning(f"Failed to load markets from Bitquery: {e}")
        
        # Fallback to DexScreener
        try:
            markets = self._fetch_markets_from_dexscreener()
            if markets:
                self._markets_cache = markets
                logger.info(f"Loaded {len(markets)} markets from DexScreener")
            else:
                logger.warning("No markets returned from DexScreener, using fallback")
                self._markets_cache = self._get_fallback_markets()
        except Exception as e:
            logger.error(f"Failed to load markets from DexScreener: {e}")
            # Provide minimal fallback
            self._markets_cache = self._get_fallback_markets()

    def _fetch_markets_from_bitquery(self) -> dict[str, Any]:
        """Fetch markets from Bitquery GraphQL API"""
        if not self.bitquery_api_key:
            raise OperationalException("Bitquery API key not configured")
        
        query = """
        query {
          ethereum(network: solana) {
            dexTrades(
              options: {limit: 1000, desc: "count"}
              date: {since: "2024-01-01"}
            ) {
              baseCurrency {
                symbol
                address
                name
              }
              quoteCurrency {
                symbol
                address
                name
              }
              count
              tradeAmount(in: USD)
            }
          }
        }
        """
        
        response = self._make_bitquery_request(query)
        
        markets = {}
        for trade in response.get("data", {}).get("ethereum", {}).get("dexTrades", []):
            base = trade["baseCurrency"]["symbol"]
            quote = trade["quoteCurrency"]["symbol"]
            
            # Only include USDC and USDT pairs
            if quote in ["USDC", "USDT"]:
                symbol = f"{base}/{quote}"
                markets[symbol] = {
                    "id": symbol,
                    "symbol": symbol,
                    "base": base,
                    "quote": quote,
                    "active": True,
                    "precision": {
                        "amount": 8,
                        "price": 8,
                    },
                    "limits": {
                        "amount": {"min": 0.00000001, "max": None},
                        "price": {"min": 0.00000001, "max": None},
                        "cost": {"min": 1.0, "max": None},
                    },
                    "info": trade,
                }
        
        return markets

    def _fetch_markets_from_dexscreener(self) -> dict[str, Any]:
        """Fetch markets from DexScreener API"""
        url = f"{self.dexscreener_base_url}/dex/tokens/solana"
        response = self._make_request(url)
        
        markets = {}
        pairs = response.get("pairs", [])
        if not pairs:
            logger.warning("No pairs returned from DexScreener")
            return markets
            
        for token in pairs:
            if not isinstance(token, dict):
                continue
                
            base_token = token.get("baseToken", {})
            quote_token = token.get("quoteToken", {})
            
            if not base_token or not quote_token:
                continue
                
            base = base_token.get("symbol")
            quote = quote_token.get("symbol")
            
            if not base or not quote:
                continue
                
            if quote in ["USDC", "USDT"]:
                symbol = f"{base}/{quote}"
                
                markets[symbol] = {
                    "id": symbol,
                    "symbol": symbol,
                    "base": base,
                    "quote": quote,
                    "active": True,
                    "precision": {
                        "amount": 8,
                        "price": 8,
                    },
                    "limits": {
                        "amount": {"min": 0.00000001, "max": None},
                        "price": {"min": 0.00000001, "max": None},
                        "cost": {"min": 1.0, "max": None},
                    },
                    "info": token,
                }
        
        return markets

    def _get_fallback_markets(self) -> dict[str, Any]:
        """Get fallback markets for common meme coins"""
        fallback_pairs = [
            "BONK/USDC", "WIF/USDC", "PEPE/USDC", "DOGE/USDC", 
            "SHIB/USDC", "FLOKI/USDC", "BABYDOGE/USDC"
        ]
        
        markets = {}
        for symbol in fallback_pairs:
            base, quote = symbol.split("/")
            markets[symbol] = {
                "id": symbol,
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "active": True,
                "precision": {
                    "amount": 8,
                    "price": 8,
                },
                "limits": {
                    "amount": {"min": 0.00000001, "max": None},
                    "price": {"min": 0.00000001, "max": None},
                    "cost": {"min": 1.0, "max": None},
                },
                "info": {},
            }
        
        return markets

    def get_historic_ohlcv(
        self,
        pair: str,
        timeframe: str,
        since_ms: int,
        candle_type: CandleType,
        is_new_pair: bool = False,
        until_ms: int | None = None,
    ) -> DataFrame:
        """
        Fetch historical OHLCV data from Bitquery or DexScreener
        """
        self.validate_timeframes(timeframe)
        
        try:
            # Try Bitquery first
            df = self._fetch_ohlcv_from_bitquery(pair, timeframe, since_ms, until_ms)
            if not df.empty:
                return self._normalize_ohlcv_dataframe(df, pair, timeframe)
        except Exception as e:
            logger.warning(f"Failed to fetch OHLCV from Bitquery for {pair}: {e}")
        
        # Fallback to DexScreener
        try:
            df = self._fetch_ohlcv_from_dexscreener(pair, timeframe, since_ms, until_ms)
            return self._normalize_ohlcv_dataframe(df, pair, timeframe)
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV from DexScreener for {pair}: {e}")
            return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)

    def _fetch_ohlcv_from_bitquery(self, pair: str, timeframe: str, since_ms: int, until_ms: int | None) -> DataFrame:
        """Fetch OHLCV data from Bitquery"""
        if not self.bitquery_api_key:
            raise OperationalException("Bitquery API key not configured")
        
        base, quote = pair.split("/")
        since_dt = dt_from_ts(since_ms / 1000)
        until_dt = dt_from_ts(until_ms / 1000) if until_ms else datetime.now(UTC)
        
        # Map timeframe to Bitquery interval
        interval_map = {
            "5m": "5m",
            "15m": "15m", 
            "1h": "1h",
            "4h": "4h",
            "1d": "1d"
        }
        interval = interval_map.get(timeframe, "1h")
        
        query = f"""
        query {{
          ethereum(network: solana) {{
            dexTrades(
              options: {{limit: 1000, desc: "timeInterval.minute"}}
              date: {{
                since: "{since_dt.strftime('%Y-%m-%d')}"
                till: "{until_dt.strftime('%Y-%m-%d')}"
              }}
              baseCurrency: {{is: "{base}"}}
              quoteCurrency: {{is: "{quote}"}}
            ) {{
              timeInterval {{
                minute
              }}
              count
              tradeAmount(in: USD)
              maximum_price: price(calculate: maximum)
              minimum_price: price(calculate: minimum)
              first_price: price(calculate: first)
              last_price: price(calculate: last)
            }}
          }}
        }}
        """
        
        response = self._make_bitquery_request(query)
        trades = response.get("data", {}).get("ethereum", {}).get("dexTrades", [])
        
        if not trades:
            return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)
        
        # Convert to OHLCV format
        data = []
        for trade in trades:
            time_interval = trade["timeInterval"]
            minute = time_interval["minute"]
            
            # Convert to timestamp
            dt = datetime.fromisoformat(minute.replace("Z", "+00:00"))
            timestamp = int(dt.timestamp() * 1000)
            
            data.append({
                "date": timestamp,
                "open": trade["first_price"],
                "high": trade["maximum_price"],
                "low": trade["minimum_price"],
                "close": trade["last_price"],
                "volume": trade["tradeAmount"],
            })
        
        return DataFrame(data)

    def _fetch_ohlcv_from_dexscreener(self, pair: str, timeframe: str, since_ms: int, until_ms: int | None) -> DataFrame:
        """Fetch OHLCV data from DexScreener"""
        base, quote = pair.split("/")
        
        # Get token address from pair
        token_address = self._get_token_address(base)
        if not token_address:
            raise OperationalException(f"Token address not found for {base}")
        
        url = f"{self.dexscreener_base_url}/dex/tokens/{token_address}"
        response = self._make_request(url)
        
        pair_data = response.get("pairs", [])
        if not pair_data:
            return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)
        
        # Find the specific pair
        target_pair = None
        for p in pair_data:
            if p.get("quoteToken", {}).get("symbol") == quote:
                target_pair = p
                break
        
        if not target_pair:
            return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)
        
        # Get OHLCV data
        ohlcv = target_pair.get("ohlcv", [])
        if not ohlcv:
            return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)
        
        # Convert to DataFrame
        data = []
        for candle in ohlcv:
            data.append({
                "date": int(candle["t"]),
                "open": float(candle["o"]),
                "high": float(candle["h"]),
                "low": float(candle["l"]),
                "close": float(candle["c"]),
                "volume": float(candle["v"]),
            })
        
        return DataFrame(data)

    def _get_token_address(self, symbol: str) -> str | None:
        """Get token address for symbol"""
        # This would typically be a mapping or API call
        # For now, return None to trigger fallback
        return None

    def _normalize_ohlcv_dataframe(self, df: DataFrame, pair: str, timeframe: str) -> DataFrame:
        """Normalize OHLCV DataFrame to Freqtrade format"""
        if df.empty:
            return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)
        
        # Ensure proper column names
        df = df.rename(columns={
            "date": "date",
            "open": "open", 
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume"
        })
        
        # Ensure date column is datetime
        if "date" in df.columns:
            df["date"] = to_datetime(df["date"], unit="ms", utc=True)
        
        # Sort by date
        df = df.sort_values("date").reset_index(drop=True)
        
        # Remove duplicates
        df = df.drop_duplicates(subset=["date"]).reset_index(drop=True)
        
        # Ensure all required columns exist
        for col in DEFAULT_DATAFRAME_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0
        
        # Select only required columns
        df = df[DEFAULT_DATAFRAME_COLUMNS]
        
        return df

    def _make_bitquery_request(self, query: str) -> dict[str, Any]:
        """Make request to Bitquery GraphQL API"""
        self._rate_limit()
        
        url = "https://graphql.bitquery.io"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.bitquery_api_key,
        }
        
        response = requests.post(url, json={"query": query}, headers=headers, timeout=30)
        response.raise_for_status()
        
        return response.json()

    def _make_request(self, url: str) -> dict[str, Any]:
        """Make HTTP request with rate limiting"""
        self._rate_limit()
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        return response.json()

    def _rate_limit(self) -> None:
        """Implement rate limiting"""
        current_time = datetime.now().timestamp()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            import time
            time.sleep(sleep_time)
        
        self._last_request_time = datetime.now().timestamp()

    def _init_ccxt(self, exchange_conf: dict, validate: bool, ccxt_config: dict) -> None:
        """Override ccxt initialization since we don't use ccxt"""
        # SolanaDex doesn't use ccxt, so we set _api to None
        self._api = None
    
    def get_tickers(self, symbols: list[str] | None = None, *, cached: bool = False) -> dict[str, Any]:
        """Get tickers for symbols"""
        # For now, return empty tickers since we don't have real-time data
        # In a real implementation, this would fetch from Bitquery/DexScreener
        return {}
    
    def reload_markets(self, reload: bool = False) -> None:
        """Override to prevent ccxt market reloading"""
        # Markets are already loaded in get_markets()
        pass
    
    def _load_async_markets(self, reload: bool = False) -> None:
        """Override to prevent async market loading"""
        # Markets are already loaded in get_markets()
        pass
    
    @property
    def markets(self) -> dict[str, Any]:
        """Override markets property to use our custom markets"""
        if not hasattr(self, '_markets_cache') or not self._markets_cache:
            self._load_markets()
        return self._markets_cache
    
    def features(self, trading_mode: str, feature: str, default: Any = None) -> Any:
        """Override features method since we don't use ccxt"""
        # Return default values for common features
        if feature == "limit":
            return 1000  # Default candle limit
        return default
    
    def ohlcv_candle_limit(self, timeframe: str, candle_type: CandleType) -> int:
        """Override candle limit method"""
        # Return a reasonable limit for SolanaDex
        return 1000
    
    def additional_exchange_init(self) -> None:
        """Additional exchange initialization"""
        # No additional initialization needed for SolanaDex
        pass