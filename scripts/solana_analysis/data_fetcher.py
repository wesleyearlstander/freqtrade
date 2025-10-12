"""
Data fetcher for Solana meme coin analysis
Handles fetching data from Bitquery and DexScreener APIs
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from cachetools import TTLCache

from config import AnalysisConfig


logger = logging.getLogger(__name__)


class DataFetcher:
    """Data fetcher for Solana meme coin data"""
    
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.bitquery_api_key = config.bitquery_api_key
        self.dexscreener_base_url = config.dexscreener_base_url
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0 / config.rate_limit["requests_per_second"]
        
        # Cache for API responses
        self.cache = TTLCache(
            maxsize=config.cache_config["max_size"],
            ttl=config.cache_config["ttl_seconds"]
        )
        
        # Ensure directories exist
        config.ensure_directories()
    
    def fetch_data(
        self,
        symbols: List[str],
        timeframe: str,
        days: int,
        source: str = "bitquery",
        fallback: str = "dexscreener"
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for multiple symbols
        
        Args:
            symbols: List of symbol pairs (e.g., ["BONK/USDC", "WIF/USDC"])
            timeframe: Timeframe for data (e.g., "4h")
            days: Number of days to fetch
            source: Primary data source ("bitquery" or "dexscreener")
            fallback: Fallback data source
            
        Returns:
            Dictionary mapping symbols to DataFrames
        """
        logger.info(f"Fetching data for {len(symbols)} symbols over {days} days")
        
        data = {}
        for symbol in symbols:
            try:
                df = self.fetch_symbol_data(symbol, timeframe, days, source, fallback)
                if not df.empty:
                    data[symbol] = df
                    logger.info(f"Fetched {len(df)} candles for {symbol}")
                else:
                    logger.warning(f"No data available for {symbol}")
            except Exception as e:
                logger.error(f"Failed to fetch data for {symbol}: {e}")
        
        return data
    
    def fetch_symbol_data(
        self,
        symbol: str,
        timeframe: str,
        days: int,
        source: str = "bitquery",
        fallback: str = "dexscreener"
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a single symbol"""
        # Check cache first
        cache_key = f"{symbol}_{timeframe}_{days}_{source}"
        if cache_key in self.cache:
            logger.debug(f"Using cached data for {symbol}")
            return self.cache[cache_key]
        
        # Try primary source
        try:
            if source == "bitquery":
                df = self._fetch_from_bitquery(symbol, timeframe, days)
            elif source == "dexscreener":
                df = self._fetch_from_dexscreener(symbol, timeframe, days)
            else:
                raise ValueError(f"Unknown source: {source}")
            
            if not df.empty:
                self.cache[cache_key] = df
                return df
        except Exception as e:
            logger.warning(f"Failed to fetch from {source} for {symbol}: {e}")
        
        # Try fallback source
        if fallback != source:
            try:
                if fallback == "bitquery":
                    df = self._fetch_from_bitquery(symbol, timeframe, days)
                elif fallback == "dexscreener":
                    df = self._fetch_from_dexscreener(symbol, timeframe, days)
                else:
                    raise ValueError(f"Unknown fallback source: {fallback}")
                
                if not df.empty:
                    self.cache[cache_key] = df
                    return df
            except Exception as e:
                logger.error(f"Failed to fetch from fallback {fallback} for {symbol}: {e}")
        
        # Return empty DataFrame if all sources fail
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    
    def _fetch_from_bitquery(self, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
        """Fetch data from Bitquery GraphQL API"""
        if not self.bitquery_api_key:
            raise ValueError("Bitquery API key not configured")
        
        base, quote = symbol.split("/")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
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
                since: "{start_date.strftime('%Y-%m-%d')}"
                till: "{end_date.strftime('%Y-%m-%d')}"
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
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        
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
        
        df = pd.DataFrame(data)
        return self._normalize_dataframe(df)
    
    def _fetch_from_dexscreener(self, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
        """Fetch data from DexScreener API"""
        base, quote = symbol.split("/")
        
        # Get token address for base currency
        token_address = self._get_token_address(base)
        if not token_address:
            raise ValueError(f"Token address not found for {base}")
        
        url = f"{self.dexscreener_base_url}/dex/tokens/{token_address}"
        response = self._make_request(url)
        
        pairs = response.get("pairs", [])
        if not pairs:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        
        # Find the specific pair
        target_pair = None
        for pair in pairs:
            if pair.get("quoteToken", {}).get("symbol") == quote:
                target_pair = pair
                break
        
        if not target_pair:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        
        # Get OHLCV data
        ohlcv = target_pair.get("ohlcv", [])
        if not ohlcv:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        
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
        
        df = pd.DataFrame(data)
        return self._normalize_dataframe(df)
    
    def _get_token_address(self, symbol: str) -> Optional[str]:
        """Get token address for symbol"""
        # This would typically be a mapping or API call
        # For now, return None to trigger fallback
        return None
    
    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize DataFrame to standard format"""
        if df.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        
        # Ensure proper column names
        df = df.rename(columns={
            "date": "date",
            "open": "open",
            "high": "high", 
            "low": "low",
            "close": "close",
            "volume": "volume"
        })
        
        # Convert date to datetime
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
        
        # Sort by date
        df = df.sort_values("date").reset_index(drop=True)
        
        # Remove duplicates
        df = df.drop_duplicates(subset=["date"]).reset_index(drop=True)
        
        # Ensure all required columns exist
        required_columns = ["date", "open", "high", "low", "close", "volume"]
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0.0
        
        # Select only required columns
        df = df[required_columns]
        
        return df
    
    def _make_bitquery_request(self, query: str) -> Dict[str, Any]:
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
    
    def _make_request(self, url: str) -> Dict[str, Any]:
        """Make HTTP request with rate limiting"""
        self._rate_limit()
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        return response.json()
    
    def _rate_limit(self) -> None:
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def save_data(self, data: Dict[str, pd.DataFrame], output_dir: str) -> None:
        """Save data to files"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for symbol, df in data.items():
            if not df.empty:
                filename = f"{symbol.replace('/', '_')}.feather"
                filepath = output_path / filename
                df.to_feather(filepath)
                logger.info(f"Saved data for {symbol} to {filepath}")
    
    def load_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load data from file"""
        filepath = self.config.get_data_path(symbol, timeframe)
        
        if filepath.exists():
            try:
                df = pd.read_feather(filepath)
                logger.info(f"Loaded data for {symbol} from {filepath}")
                return df
            except Exception as e:
                logger.error(f"Failed to load data for {symbol}: {e}")
        
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])