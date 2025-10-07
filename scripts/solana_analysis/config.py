"""
Configuration management for Solana analysis CLI
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class AnalysisConfig:
    """Configuration class for analysis CLI"""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self.config = config_dict
        
        # Data sources
        self.bitquery_api_key = os.getenv("BITQUERY_API_KEY")
        self.dexscreener_base_url = "https://api.dexscreener.com/latest"
        
        # Data storage
        self.data_dir = Path(self.config.get("data_dir", "data/"))
        self.cache_dir = Path(self.config.get("cache_dir", "cache/"))
        
        # Analysis parameters
        self.wave_threshold = self.config.get("wave_threshold", 10.0)
        self.fib_levels = self.config.get("fib_levels", [0, 23.6, 38.2, 50, 61.8, 78.6, 100, 127.2, 161.8, 200, 261.8])
        self.timeframes = self.config.get("timeframes", ["5m", "15m", "1h", "4h", "1d"])
        
        # Universe definitions
        self.universes = self.config.get("universes", {
            "top50": 50,
            "top100": 100,
            "top200": 200,
            "top500": 500,
        })
        
        # Visualization settings
        self.viz_config = self.config.get("visualization", {
            "figure_size": [12, 8],
            "dpi": 100,
            "style": "seaborn-v0_8",
            "interactive": True,
            "save_format": "png",
        })
        
        # Cache settings
        self.cache_config = self.config.get("cache", {
            "enabled": True,
            "ttl_seconds": 3600,  # 1 hour
            "max_size": 1000,
        })
        
        # Rate limiting
        self.rate_limit = self.config.get("rate_limit", {
            "requests_per_second": 1.0,
            "burst_size": 10,
        })
    
    @classmethod
    def load(cls, config_path: str) -> "AnalysisConfig":
        """Load configuration from file"""
        config_file = Path(config_path)
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                config_dict = json.load(f)
        else:
            # Create default configuration
            config_dict = cls.get_default_config()
            # Save default config
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
        
        return cls(config_dict)
    
    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "data_dir": "data/",
            "cache_dir": "cache/",
            "wave_threshold": 10.0,
            "fib_levels": [0, 23.6, 38.2, 50, 61.8, 78.6, 100, 127.2, 161.8, 200, 261.8],
            "timeframes": ["5m", "15m", "1h", "4h", "1d"],
            "universes": {
                "top50": 50,
                "top100": 100,
                "top200": 200,
                "top500": 500,
            },
            "visualization": {
                "figure_size": [12, 8],
                "dpi": 100,
                "style": "seaborn-v0_8",
                "interactive": True,
                "save_format": "png",
            },
            "cache": {
                "enabled": True,
                "ttl_seconds": 3600,
                "max_size": 1000,
            },
            "rate_limit": {
                "requests_per_second": 1.0,
                "burst_size": 10,
            },
        }
    
    def get_universe_size(self, universe: str) -> int:
        """Get size for universe"""
        return self.universes.get(universe, 200)
    
    def get_data_path(self, symbol: str, timeframe: str) -> Path:
        """Get data path for symbol and timeframe"""
        return self.data_dir / f"{symbol}_{timeframe}.feather"
    
    def get_cache_path(self, key: str) -> Path:
        """Get cache path for key"""
        return self.cache_dir / f"{key}.json"
    
    def ensure_directories(self) -> None:
        """Ensure required directories exist"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)