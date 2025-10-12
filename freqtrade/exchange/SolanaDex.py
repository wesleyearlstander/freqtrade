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
    Uses Bitquery GraphQL API as the data source
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
        # Initialize Bitquery credentials FIRST (before super().__init__)
        self.bitquery_api_key = os.getenv("BITQUERY_API_KEY")
        # OAuth2 Bearer access token (preferred, per Bitquery docs)
        # See: https://docs.bitquery.io/docs/authorisation/how-to-generate/
        self.bitquery_access_token = (
            os.getenv("BITQUERY_ACCESS_TOKEN")
            or os.getenv("BITQUERY_BEARER")
            or os.getenv("BITQUERY_TOKEN")
        )
        # Client credentials for programmatic token generation
        self.bitquery_client_id = os.getenv("BITQUERY_CLIENT_ID")
        self.bitquery_client_secret = os.getenv("BITQUERY_CLIENT_SECRET")
        self._bitquery_token_expiry: float | None = None

        if not (self.bitquery_access_token or self.bitquery_api_key or (self.bitquery_client_id and self.bitquery_client_secret)):
            logger.warning("Bitquery credentials not configured (need BITQUERY_ACCESS_TOKEN or BITQUERY_API_KEY or BITQUERY_CLIENT_ID/SECRET)")
        # Auto-generate access token if client credentials are present and no token provided
        if (not self.bitquery_access_token) and self.bitquery_client_id and self.bitquery_client_secret:
            try:
                self._bitquery_generate_access_token()
            except Exception as e:
                logger.warning(f"Failed to generate Bitquery access token: {e}")
        
        # Initialize caches and state before calling super().__init__
        self._markets_cache: dict[str, Any] = {}
        self._token_metadata_cache: dict[str, Any] = {}
        self._last_request_time = 0
        self._min_request_interval = 1.0  # 1 second between requests
        
        super().__init__(config, **kwargs)
        
        # Supported timeframes (aligned with Bitquery availability)
        self._timeframes = ["5m", "15m", "1h", "4h", "1d"]

    @property
    def timeframes(self) -> list[str]:
        """Return supported timeframes"""
        return self._timeframes

    @property
    def name(self) -> str:
        """Return exchange name"""
        return "Solanadex"

    @property
    def id(self) -> str:
        """Return exchange ID"""
        return "Solanadex"

    def exchange_has(self, key: str) -> bool:
        """Check if exchange supports specific functionality"""
        supported_features = {
            "fetchOHLCV": True,
            "fetchTickers": True,
            "fetchTicker": True,
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
        """Load markets from Bitquery"""
        try:
            markets = self._fetch_markets_from_bitquery()
            if markets:
                self._markets_cache = markets
                logger.info(f"Loaded {len(markets)} markets from Bitquery")
                return
        except Exception as e:
            logger.warning(f"Failed to load markets from Bitquery: {e}")
        
        # Provide minimal fallback
        logger.warning("Using fallback markets")
        self._markets_cache = self._get_fallback_markets()

    def _fetch_markets_from_bitquery(self) -> dict[str, Any]:
        """Fetch markets from Bitquery GraphQL API using v2 streaming API"""
        query = """
        query {
          Solana {
            DEXTradeByTokens(
              limit: {count: 1000}
              orderBy: {descending: Block_Time}
              where: {Block: {Time: {since: "2024-01-01T00:00:00Z"}}}
            ) {
              Trade {
                Currency {
                  Symbol
                  MintAddress
                  Name
                }
                Side {
                  Currency {
                    Symbol
                    MintAddress
                    Name
                  }
                }
                Dex {
                  ProtocolName
                }
              }
              count
            }
          }
        }
        """
        
        response = self._make_bitquery_request(query)
        
        markets = {}
        for trade in response.get("data", {}).get("Solana", {}).get("DEXTradeByTokens", []):
            base_currency = trade.get("Trade", {}).get("Currency", {})
            quote_currency = trade.get("Trade", {}).get("Side", {}).get("Currency", {})
            
            base = base_currency.get("Symbol")
            quote = quote_currency.get("Symbol")
            
            if base and quote and quote in ["SOL"]:
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

    def _get_fallback_markets(self) -> dict[str, Any]:
        """Get fallback markets for common meme coins"""
        fallback_pairs = [
            "BONK/SOL", "WIF/SOL", "PEPE/SOL", "MOODENG/SOL",
            "POPCAT/SOL", "MEW/SOL", "MUMU/SOL", "NEIRO/SOL"
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
        Fetch historical OHLCV data from Bitquery
        """
        self.validate_timeframes(timeframe)
        
        try:
            df = self._fetch_ohlcv_from_bitquery(pair, timeframe, since_ms, until_ms)
            if not df.empty:
                return self._normalize_ohlcv_dataframe(df, pair, timeframe)
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV from Bitquery for {pair}: {e}")
            return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)
        
        return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)

    def _fetch_ohlcv_from_bitquery(self, pair: str, timeframe: str, since_ms: int, until_ms: int | None) -> DataFrame:
        """Fetch OHLCV data from Bitquery v2 streaming API
        
        Fetches raw trades and aggregates them into OHLC candles manually
        because Bitquery's aggregation functions don't work well for DEX data.
        """
        if not (self.bitquery_access_token or self.bitquery_api_key or (self.bitquery_client_id and self.bitquery_client_secret)):
            raise OperationalException("Bitquery credentials not configured")
        
        base, quote = pair.split("/")
        since_dt = dt_from_ts(since_ms / 1000)
        until_dt = dt_from_ts(until_ms / 1000) if until_ms else datetime.now(UTC)
        
        # For SOL-quoted pairs, the base currency is the meme token
        # We need to find trades where meme token is Currency and SOL (WSOL) is Side.Currency
        # Note: WSOL = So11111111111111111111111111111111111111112
        
        # Query for raw trades - we'll aggregate manually
        query = f"""
        query {{
          Solana {{
            DEXTradeByTokens(
              limit: {{count: 10000}}
              orderBy: {{ascending: Block_Time}}
              where: {{
                Block: {{Time: {{since: "{since_dt.strftime('%Y-%m-%d')}T00:00:00Z", till: "{until_dt.strftime('%Y-%m-%d')}T23:59:59Z"}}}}
                Trade: {{
                  Currency: {{Symbol: {{is: "{base}"}}}}
                  Side: {{Currency: {{MintAddress: {{is: "So11111111111111111111111111111111111111112"}}}}}}
                }}
              }}
            ) {{
              Block {{
                Time
              }}
              Trade {{
                Amount
                Side {{
                  Amount
                }}
              }}
            }}
          }}
        }}
        """
        
        response = self._make_bitquery_request(query)
        trades = response.get("data", {}).get("Solana", {}).get("DEXTradeByTokens", [])
        
        if not trades:
            logger.warning(f"No trades returned for {pair} {timeframe}.")
            return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)
        
        # Convert trades to DataFrame with calculated price
        rows = []
        for trade in trades:
            time_str = trade.get("Block", {}).get("Time")
            amount = float(trade.get("Trade", {}).get("Amount", 0) or 0)
            side_amount = float(trade.get("Trade", {}).get("Side", {}).get("Amount", 0) or 0)
            
            if amount > 0 and side_amount > 0 and time_str:
                # Price in SOL = SOL amount / Token amount
                price_in_sol = side_amount / amount
                
                try:
                    dt_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    timestamp_ms = int(dt_obj.timestamp() * 1000)
                    
                    rows.append({
                        "date": timestamp_ms,
                        "price": price_in_sol,
                        "amount": amount
                    })
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Failed to parse time {time_str}: {e}")
                    continue
        
        if not rows:
            logger.warning(f"No valid trades with price data for {pair}")
            return DataFrame(columns=DEFAULT_DATAFRAME_COLUMNS)
        
        # Create DataFrame and aggregate into OHLC candles
        df = DataFrame(rows)
        df['date'] = to_datetime(df['date'], unit='ms', utc=True)
        df = df.set_index('date')
        
        # Map timeframe to pandas resample frequency
        freq_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1h",
            "2h": "2h",
            "4h": "4h",
            "1d": "1D"
        }
        resample_freq = freq_map.get(timeframe, "1h")
        
        # Aggregate into OHLC
        ohlc = df['price'].resample(resample_freq).ohlc()
        volume = df['amount'].resample(resample_freq).sum()
        
        # Combine and reset index
        result = ohlc.copy()
        result['volume'] = volume
        result = result.reset_index()
        result.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        
        # Convert date back to milliseconds timestamp
        result['date'] = (result['date'].astype('int64') / 1e6).astype('int64')
        
        # Remove rows with NaN values
        result = result.dropna()
        
        # Ensure all numeric columns are float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            result[col] = result[col].astype(float)
        
        logger.info(f"Aggregated {len(rows)} trades into {len(result)} {timeframe} candles for {pair}")
        
        return result

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
        """Make request to Bitquery GraphQL API.
        Prefer OAuth Bearer token if available (v2), else fallback to API key header (v1).
        """
        self._rate_limit()

        # Ensure Bearer token if client credentials are present (preferred)
        if (not self.bitquery_access_token) and self.bitquery_client_id and self.bitquery_client_secret:
            self._bitquery_generate_access_token()

        # Prefer v2 streaming endpoint when using Bearer tokens, otherwise fallback to v1
        if self.bitquery_access_token:
            url = "https://streaming.bitquery.io/graphql"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.bitquery_access_token}",
            }
        elif self.bitquery_api_key:
            url = "https://graphql.bitquery.io"
            headers = {
                "Content-Type": "application/json",
                "X-API-KEY": self.bitquery_api_key,
            }
        else:
            raise OperationalException("Bitquery credentials not configured (missing BITQUERY_ACCESS_TOKEN or BITQUERY_API_KEY or client credentials)")

        response = requests.post(url, json={"query": query}, headers=headers, timeout=30)
        if response.status_code == 401 and self.bitquery_client_id and self.bitquery_client_secret:
            # Attempt refresh once
            self._bitquery_generate_access_token(force=True)
            headers["Authorization"] = f"Bearer {self.bitquery_access_token}"
            response = requests.post(url, json={"query": query}, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse JSON and handle GraphQL errors explicitly
        try:
            data = response.json()
        except ValueError:
            raise OperationalException("Bitquery response is not valid JSON")

        # GraphQL may return HTTP 200 with an `errors` array
        if isinstance(data, dict) and data.get("errors"):
            try:
                messages = "; ".join(
                    [e.get("message", "") for e in data.get("errors", []) if isinstance(e, dict)]
                )
            except Exception:
                messages = ""
            raise OperationalException(f"Bitquery GraphQL errors: {messages or 'unknown error'}")

        return data

    def _bitquery_generate_access_token(self, force: bool = False) -> None:
        """Generate (or refresh) Bitquery access token using client credentials flow.
        Docs: https://docs.bitquery.io/docs/authorisation/how-to-generate/#generating-a-token-programmatically
        """
        if not (self.bitquery_client_id and self.bitquery_client_secret):
            raise OperationalException("BITQUERY_CLIENT_ID/SECRET not configured")
        if self._bitquery_token_expiry and not force:
            # If token not expired, skip
            now = datetime.now(UTC).timestamp()
            if now < self._bitquery_token_expiry - 60:
                return
        token_url = "https://oauth2.bitquery.io/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.bitquery_client_id,
            "client_secret": self.bitquery_client_secret,
            "scope": "api",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(token_url, data=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get("access_token")
        expires_in = data.get("expires_in")
        if not access_token:
            raise OperationalException("Failed to obtain Bitquery access token")
        self.bitquery_access_token = access_token
        if isinstance(expires_in, (int, float)):
            self._bitquery_token_expiry = datetime.now(UTC).timestamp() + float(expires_in)

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
        self._api_async = None
    
    def reload_markets(self, force: bool = False, load_leverage_tiers: bool = False) -> None:
        """Override reload_markets to use Bitquery instead of ccxt"""
        if not self._markets_cache or force:
            self._load_markets()
        self._markets = self._markets_cache
        self._last_markets_refresh = dt_ts()
    
    def get_tickers(self, symbols: list[str] | None = None, *, cached: bool = False) -> dict[str, Any]:
        """Get tickers for symbols.
        Returns mapping { symbol: { 'symbol': str, 'last': float, 'timestamp': int } }
        """
        tickers: dict[str, Any] = {}
        if symbols is None:
            symbols = list(self.markets.keys())
        for sym in symbols:
            try:
                base, quote = sym.split("/")
                t = self._fetch_ticker_from_bitquery(base, quote)
                if t:
                    tickers[sym] = t
            except Exception:
                continue
        return tickers

    def _fetch_ticker_from_bitquery(self, base: str, quote: str) -> dict[str, Any] | None:
        """Fetch latest price for base/quote from Bitquery v2.
        Uses most recent DEXTradeByTokens and returns last price.
        """
        if not (self.bitquery_access_token or self.bitquery_api_key or (self.bitquery_client_id and self.bitquery_client_secret)):
            return None
        # Ensure we have a bearer token if possible
        if (not self.bitquery_access_token) and self.bitquery_client_id and self.bitquery_client_secret:
            try:
                self._bitquery_generate_access_token()
            except Exception:
                pass
        today = datetime.now(UTC).strftime('%Y-%m-%d')
        query = f"""
        query {{
          Solana {{
            DEXTradeByTokens(
              limit: {{count: 1}}
              orderBy: {{descending: Block_Time}}
              where: {{
                Block: {{Time: {{since: "{today}T00:00:00Z"}}}}
                Trade: {{
                  Currency: {{Symbol: {{is: "{base}"}}}}
                  Side: {{Currency: {{Symbol: {{is: "{quote}"}}}}}}
                }}
              }}
            ) {{
              Block {{
                Time
              }}
              Trade {{
                PriceInUSD
              }}
            }}
          }}
        }}
        """
        try:
            resp = self._make_bitquery_request(query)
            trades = resp.get("data", {}).get("Solana", {}).get("DEXTradeByTokens", [])
            if trades:
                block = trades[0].get("Block", {})
                trade = trades[0].get("Trade", {})
                time_str = block.get("Time")
                price = trade.get("PriceInUSD")
                ts = int(datetime.fromisoformat(time_str.replace("Z", "+00:00")).timestamp() * 1000) if time_str else int(datetime.now(UTC).timestamp() * 1000)
                if price is not None:
                    return {"symbol": f"{base}/{quote}", "last": float(price), "timestamp": ts}
        except OperationalException:
            pass
        return None
    
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
    
    def ohlcv_candle_limit(self, timeframe: str, candle_type: CandleType = CandleType.SPOT, since_ms: int | None = None) -> int:
        """Override candle limit method"""
        # Return a reasonable limit for SolanaDex
        return 10000
    
    def additional_exchange_init(self) -> None:
        """Additional exchange initialization"""
        # No additional initialization needed for SolanaDex
        pass