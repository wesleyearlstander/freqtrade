"""
Fibonacci analysis for Solana meme coin waves
Analyzes retracements, extensions, and hold times at Fibonacci levels
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config import AnalysisConfig
from wave_detector import Wave


logger = logging.getLogger(__name__)


class FibonacciLevel:
    """Represents a Fibonacci level analysis"""
    
    def __init__(
        self,
        level: float,
        price: float,
        hold_time: int,  # in candles
        invalidation: bool = False,
        deepest_retrace: float = 0.0,
        time_spent: int = 0
    ):
        self.level = level
        self.price = price
        self.hold_time = hold_time
        self.invalidation = invalidation
        self.deepest_retrace = deepest_retrace
        self.time_spent = time_spent
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "level": self.level,
            "price": self.price,
            "hold_time": self.hold_time,
            "invalidation": self.invalidation,
            "deepest_retrace": self.deepest_retrace,
            "time_spent": self.time_spent
        }


class FibonacciAnalyzer:
    """Fibonacci analysis for wave patterns"""
    
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.fibonacci_levels = config.get_fibonacci_levels()
    
    def analyze_wave_fibonacci(
        self,
        wave: Wave,
        df: pd.DataFrame,
        lookback_candles: int = 100
    ) -> Dict[str, Any]:
        """
        Analyze Fibonacci levels for a single wave
        
        Args:
            wave: Wave object to analyze
            df: OHLCV DataFrame
            lookback_candles: Number of candles to look back for analysis
        
        Returns:
            Dictionary with Fibonacci analysis results
        """
        # Get price range for the wave
        start_price = wave.start_price
        end_price = wave.end_price
        peak_price = wave.peak_price
        
        # Calculate Fibonacci levels
        if wave.wave_type == "up":
            # Up wave: retracement from peak
            high_price = peak_price
            low_price = start_price
            range_size = high_price - low_price
        else:
            # Down wave: retracement from trough
            high_price = start_price
            low_price = peak_price
            range_size = high_price - low_price
        
        # Calculate Fibonacci retracement levels
        fib_levels = {}
        for level in self.fibonacci_levels:
            if level <= 100:
                # Retracement levels
                fib_price = high_price - (range_size * (level / 100))
                fib_levels[level] = fib_price
            else:
                # Extension levels
                fib_price = high_price + (range_size * ((level - 100) / 100))
                fib_levels[level] = fib_price
        
        # Analyze price action at each level
        level_analysis = {}
        for level, price in fib_levels.items():
            analysis = self._analyze_level_price_action(
                df, price, wave.start_time, wave.end_time, level
            )
            level_analysis[level] = analysis
        
        # Calculate overall metrics
        deepest_retrace = self._calculate_deepest_retrace(df, wave, fib_levels)
        invalidation_level = self._check_invalidation(df, wave, fib_levels)
        
        return {
            "wave_id": f"{wave.start_time}_{wave.end_time}",
            "wave_type": wave.wave_type,
            "fibonacci_levels": fib_levels,
            "level_analysis": level_analysis,
            "deepest_retrace": deepest_retrace,
            "invalidation_level": invalidation_level,
            "range_size": range_size,
            "high_price": high_price,
            "low_price": low_price
        }
    
    def _analyze_level_price_action(
        self,
        df: pd.DataFrame,
        level_price: float,
        start_time: datetime,
        end_time: datetime,
        level: float
    ) -> Dict[str, Any]:
        """Analyze price action at a specific Fibonacci level"""
        # Filter data to wave timeframe
        wave_data = df[(df["date"] >= start_time) & (df["date"] <= end_time)]
        
        if wave_data.empty:
            return {
                "level": level,
                "price": level_price,
                "hold_time": 0,
                "invalidation": False,
                "deepest_retrace": 0.0,
                "time_spent": 0
            }
        
        # Check if price touched the level
        touched = False
        hold_candles = 0
        max_hold_candles = 0
        invalidation = False
        
        for _, row in wave_data.iterrows():
            high = row["high"]
            low = row["low"]
            close = row["close"]
            
            # Check if price touched the level
            if low <= level_price <= high:
                touched = True
                hold_candles += 1
                max_hold_candles = max(max_hold_candles, hold_candles)
            else:
                hold_candles = 0
            
            # Check for invalidation (price closes below level for retracements)
            if level <= 100 and close < level_price:
                invalidation = True
        
        # Calculate deepest retracement
        deepest_retrace = 0.0
        if touched:
            price_diff = abs(level_price - wave_data["close"].iloc[-1])
            deepest_retrace = (price_diff / level_price) * 100
        
        return {
            "level": level,
            "price": level_price,
            "touched": touched,
            "hold_time": max_hold_candles,
            "invalidation": invalidation,
            "deepest_retrace": deepest_retrace,
            "time_spent": hold_candles
        }
    
    def _calculate_deepest_retrace(
        self,
        df: pd.DataFrame,
        wave: Wave,
        fib_levels: Dict[float, float]
    ) -> float:
        """Calculate the deepest retracement level reached"""
        wave_data = df[(df["date"] >= wave.start_time) & (df["date"] <= wave.end_time)]
        
        if wave_data.empty:
            return 0.0
        
        if wave.wave_type == "up":
            # For up waves, find lowest point after peak
            peak_idx = wave_data[wave_data["date"] == wave.peak_time].index
            if len(peak_idx) > 0:
                after_peak = wave_data[wave_data.index >= peak_idx[0]]
                if not after_peak.empty:
                    lowest_price = after_peak["low"].min()
                    retrace = ((wave.peak_price - lowest_price) / wave.peak_price) * 100
                    return retrace
        else:
            # For down waves, find highest point after trough
            trough_idx = wave_data[wave_data["date"] == wave.peak_time].index
            if len(trough_idx) > 0:
                after_trough = wave_data[wave_data.index >= trough_idx[0]]
                if not after_trough.empty:
                    highest_price = after_trough["high"].max()
                    retrace = ((highest_price - wave.peak_price) / wave.peak_price) * 100
                    return retrace
        
        return 0.0
    
    def _check_invalidation(
        self,
        df: pd.DataFrame,
        wave: Wave,
        fib_levels: Dict[float, float]
    ) -> Optional[float]:
        """Check if any Fibonacci level was invalidated"""
        wave_data = df[(df["date"] >= wave.start_time) & (df["date"] <= wave.end_time)]
        
        if wave_data.empty:
            return None
        
        if wave.wave_type == "up":
            # For up waves, check if price closed below retracement levels
            for level, price in fib_levels.items():
                if level <= 100:  # Only retracement levels
                    if wave_data["close"].min() < price:
                        return level
        else:
            # For down waves, check if price closed above retracement levels
            for level, price in fib_levels.items():
                if level <= 100:  # Only retracement levels
                    if wave_data["close"].max() > price:
                        return level
        
        return None
    
    def analyze_multiple_waves(
        self,
        waves: List[Wave],
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Analyze Fibonacci levels for multiple waves"""
        results = []
        
        for wave in waves:
            analysis = self.analyze_wave_fibonacci(wave, df)
            results.append(analysis)
        
        # Aggregate statistics
        stats = self._calculate_fibonacci_statistics(results)
        
        return {
            "individual_analyses": results,
            "statistics": stats
        }
    
    def _calculate_fibonacci_statistics(
        self,
        analyses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate aggregated Fibonacci statistics"""
        if not analyses:
            return {}
        
        # Collect data for each level
        level_stats = {}
        
        for level in self.fibonacci_levels:
            level_data = {
                "touched_count": 0,
                "invalidation_count": 0,
                "hold_times": [],
                "deepest_retraces": [],
                "time_spent": []
            }
            
            for analysis in analyses:
                level_analysis = analysis["level_analysis"].get(level, {})
                
                if level_analysis.get("touched", False):
                    level_data["touched_count"] += 1
                
                if level_analysis.get("invalidation", False):
                    level_data["invalidation_count"] += 1
                
                level_data["hold_times"].append(level_analysis.get("hold_time", 0))
                level_data["deepest_retraces"].append(level_analysis.get("deepest_retrace", 0))
                level_data["time_spent"].append(level_analysis.get("time_spent", 0))
            
            # Calculate statistics
            if level_data["touched_count"] > 0:
                level_stats[level] = {
                    "touch_rate": level_data["touched_count"] / len(analyses),
                    "invalidation_rate": level_data["invalidation_count"] / level_data["touched_count"],
                    "avg_hold_time": np.mean(level_data["hold_times"]),
                    "max_hold_time": np.max(level_data["hold_times"]),
                    "avg_deepest_retrace": np.mean(level_data["deepest_retraces"]),
                    "avg_time_spent": np.mean(level_data["time_spent"])
                }
            else:
                level_stats[level] = {
                    "touch_rate": 0.0,
                    "invalidation_rate": 0.0,
                    "avg_hold_time": 0.0,
                    "max_hold_time": 0.0,
                    "avg_deepest_retrace": 0.0,
                    "avg_time_spent": 0.0
                }
        
        # Overall statistics
        total_waves = len(analyses)
        up_waves = sum(1 for a in analyses if a["wave_type"] == "up")
        down_waves = total_waves - up_waves
        
        return {
            "total_waves": total_waves,
            "up_waves": up_waves,
            "down_waves": down_waves,
            "level_statistics": level_stats
        }
    
    def get_average_bottom_retracement(
        self,
        waves: List[Wave],
        last_pumps: int = 5
    ) -> float:
        """Calculate average bottom retracement for last N pumps"""
        up_waves = [w for w in waves if w.wave_type == "up"]
        
        if not up_waves:
            return 0.0
        
        # Sort by start time and get last N pumps
        up_waves.sort(key=lambda x: x.start_time)
        last_pumps_waves = up_waves[-last_pumps:]
        
        # Calculate average retracement
        retracements = []
        for wave in last_pumps_waves:
            # Calculate retracement from peak to end
            retracement = ((wave.peak_price - wave.end_price) / wave.peak_price) * 100
            retracements.append(retracement)
        
        return np.mean(retracements) if retracements else 0.0
    
    def get_fibonacci_distribution(
        self,
        analyses: List[Dict[str, Any]],
        level: float
    ) -> Dict[str, Any]:
        """Get distribution statistics for a specific Fibonacci level"""
        level_data = []
        
        for analysis in analyses:
            level_analysis = analysis["level_analysis"].get(level, {})
            if level_analysis.get("touched", False):
                level_data.append(level_analysis)
        
        if not level_data:
            return {
                "level": level,
                "count": 0,
                "touch_rate": 0.0,
                "invalidation_rate": 0.0,
                "avg_hold_time": 0.0,
                "avg_deepest_retrace": 0.0
            }
        
        return {
            "level": level,
            "count": len(level_data),
            "touch_rate": len(level_data) / len(analyses),
            "invalidation_rate": sum(1 for d in level_data if d.get("invalidation", False)) / len(level_data),
            "avg_hold_time": np.mean([d.get("hold_time", 0) for d in level_data]),
            "avg_deepest_retrace": np.mean([d.get("deepest_retrace", 0) for d in level_data])
        }