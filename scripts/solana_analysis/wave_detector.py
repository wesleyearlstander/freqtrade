"""
Wave detection algorithms for Solana meme coin analysis
Implements zigzag, pivots, and swing detection methods
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import AnalysisConfig


logger = logging.getLogger(__name__)


class Wave:
    """Represents a detected wave"""
    
    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        start_price: float,
        end_price: float,
        peak_time: datetime,
        peak_price: float,
        wave_type: str,  # "up" or "down"
        magnitude: float,
        duration: int,  # in candles
        volume_delta: float = 0.0,
        drawdown: float = 0.0
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.start_price = start_price
        self.end_price = end_price
        self.peak_time = peak_time
        self.peak_price = peak_price
        self.wave_type = wave_type
        self.magnitude = magnitude
        self.duration = duration
        self.volume_delta = volume_delta
        self.drawdown = drawdown
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "start_price": self.start_price,
            "end_price": self.end_price,
            "peak_time": self.peak_time,
            "peak_price": self.peak_price,
            "wave_type": self.wave_type,
            "magnitude": self.magnitude,
            "duration": self.duration,
            "volume_delta": self.volume_delta,
            "drawdown": self.drawdown
        }
    
    def __repr__(self) -> str:
        return f"Wave({self.wave_type}, {self.magnitude:.2f}%, {self.duration}c)"


class WaveDetector:
    """Wave detection for price data"""
    
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.cache_dir = Path("cache/waves")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def detect_waves(
        self,
        df: pd.DataFrame,
        method: str = "zigzag",
        threshold: float = 10.0,
        min_duration: int = 1,
        max_duration: int = 1000
    ) -> List[Wave]:
        """
        Detect waves in price data
        
        Args:
            df: OHLCV DataFrame with columns [date, open, high, low, close, volume]
            method: Detection method (zigzag, pivots, swing)
            threshold: Minimum percentage change for wave detection
            min_duration: Minimum wave duration in candles
            max_duration: Maximum wave duration in candles
        
        Returns:
            List of detected waves
        """
        if df.empty or len(df) < 3:
            return []
        
        # Ensure data is sorted by date
        df = df.sort_values("date").reset_index(drop=True)
        
        if method == "zigzag":
            return self._detect_zigzag_waves(df, threshold, min_duration, max_duration)
        elif method == "pivots":
            return self._detect_pivot_waves(df, threshold, min_duration, max_duration)
        elif method == "swing":
            return self._detect_swing_waves(df, threshold, min_duration, max_duration)
        else:
            raise ValueError(f"Unknown wave detection method: {method}")
    
    def _detect_zigzag_waves(
        self,
        df: pd.DataFrame,
        threshold: float,
        min_duration: int,
        max_duration: int
    ) -> List[Wave]:
        """Detect waves using zigzag algorithm"""
        waves = []
        
        # Find peaks and troughs
        highs = df["high"].values
        lows = df["low"].values
        dates = df["date"].values
        volumes = df["volume"].values
        
        # Find local maxima and minima
        peaks = self._find_peaks(highs, threshold)
        troughs = self._find_troughs(lows, threshold)
        
        # Combine and sort by time
        points = []
        for i in peaks:
            points.append((i, "peak", highs[i], dates[i]))
        for i in troughs:
            points.append((i, "trough", lows[i], dates[i]))
        
        points.sort(key=lambda x: x[0])
        
        if len(points) < 2:
            return waves
        
        # Create waves between consecutive points
        for i in range(len(points) - 1):
            curr_idx, curr_type, curr_price, curr_date = points[i]
            next_idx, next_type, next_price, next_date = points[i + 1]
            
            # Skip if same type (peak to peak or trough to trough)
            if curr_type == next_type:
                continue
            
            # Calculate magnitude
            if curr_type == "trough" and next_type == "peak":
                # Up wave
                magnitude = ((next_price - curr_price) / curr_price) * 100
                wave_type = "up"
                peak_idx = next_idx
                peak_price = next_price
                peak_time = next_date
            else:
                # Down wave
                magnitude = ((curr_price - next_price) / curr_price) * 100
                wave_type = "down"
                peak_idx = curr_idx
                peak_price = curr_price
                peak_time = curr_date
            
            # Check magnitude threshold
            if magnitude < threshold:
                continue
            
            # Check duration constraints
            duration = next_idx - curr_idx
            if duration < min_duration or duration > max_duration:
                continue
            
            # Calculate volume delta
            start_vol = volumes[curr_idx] if curr_idx < len(volumes) else 0
            end_vol = volumes[next_idx] if next_idx < len(volumes) else 0
            volume_delta = end_vol - start_vol
            
            # Calculate drawdown
            if wave_type == "up":
                # For up waves, drawdown is from peak to end
                peak_to_end = ((peak_price - next_price) / peak_price) * 100
                drawdown = peak_to_end
            else:
                # For down waves, drawdown is from start to trough
                start_to_trough = ((curr_price - next_price) / curr_price) * 100
                drawdown = start_to_trough
            
            wave = Wave(
                start_time=pd.to_datetime(curr_date, utc=True),
                end_time=pd.to_datetime(next_date, utc=True),
                start_price=curr_price,
                end_price=next_price,
                peak_time=pd.to_datetime(peak_time, utc=True),
                peak_price=peak_price,
                wave_type=wave_type,
                magnitude=magnitude,
                duration=duration,
                volume_delta=volume_delta,
                drawdown=drawdown
            )
            
            waves.append(wave)
        
        return waves
    
    def _detect_pivot_waves(
        self,
        df: pd.DataFrame,
        threshold: float,
        min_duration: int,
        max_duration: int
    ) -> List[Wave]:
        """Detect waves using pivot points"""
        waves = []
        
        # Use high and low prices for pivot detection
        highs = df["high"].values
        lows = df["low"].values
        dates = df["date"].values
        volumes = df["volume"].values
        
        # Find pivot highs and lows
        pivot_highs = self._find_pivot_highs(highs, window=5)
        pivot_lows = self._find_pivot_lows(lows, window=5)
        
        # Combine pivots
        pivots = []
        for i in pivot_highs:
            pivots.append((i, "high", highs[i], dates[i]))
        for i in pivot_lows:
            pivots.append((i, "low", lows[i], dates[i]))
        
        pivots.sort(key=lambda x: x[0])
        
        if len(pivots) < 2:
            return waves
        
        # Create waves between consecutive pivots
        for i in range(len(pivots) - 1):
            curr_idx, curr_type, curr_price, curr_date = pivots[i]
            next_idx, next_type, next_price, next_date = pivots[i + 1]
            
            # Skip if same type
            if curr_type == next_type:
                continue
            
            # Calculate magnitude
            if curr_type == "low" and next_type == "high":
                # Up wave
                magnitude = ((next_price - curr_price) / curr_price) * 100
                wave_type = "up"
                peak_idx = next_idx
                peak_price = next_price
                peak_time = next_date
            else:
                # Down wave
                magnitude = ((curr_price - next_price) / curr_price) * 100
                wave_type = "down"
                peak_idx = curr_idx
                peak_price = curr_price
                peak_time = curr_date
            
            # Check magnitude threshold
            if magnitude < threshold:
                continue
            
            # Check duration constraints
            duration = next_idx - curr_idx
            if duration < min_duration or duration > max_duration:
                continue
            
            # Calculate volume delta
            start_vol = volumes[curr_idx] if curr_idx < len(volumes) else 0
            end_vol = volumes[next_idx] if next_idx < len(volumes) else 0
            volume_delta = end_vol - start_vol
            
            # Calculate drawdown
            if wave_type == "up":
                drawdown = ((peak_price - next_price) / peak_price) * 100
            else:
                drawdown = ((curr_price - next_price) / curr_price) * 100
            
            wave = Wave(
                start_time=pd.to_datetime(curr_date, utc=True),
                end_time=pd.to_datetime(next_date, utc=True),
                start_price=curr_price,
                end_price=next_price,
                peak_time=pd.to_datetime(peak_time, utc=True),
                peak_price=peak_price,
                wave_type=wave_type,
                magnitude=magnitude,
                duration=duration,
                volume_delta=volume_delta,
                drawdown=drawdown
            )
            
            waves.append(wave)
        
        return waves
    
    def _detect_swing_waves(
        self,
        df: pd.DataFrame,
        threshold: float,
        min_duration: int,
        max_duration: int
    ) -> List[Wave]:
        """Detect waves using swing points"""
        waves = []
        
        # Use close prices for swing detection
        closes = df["close"].values
        dates = df["date"].values
        volumes = df["volume"].values
        
        # Find swing highs and lows
        swing_highs = self._find_swing_highs(closes, threshold)
        swing_lows = self._find_swing_lows(closes, threshold)
        
        # Combine swings
        swings = []
        for i in swing_highs:
            swings.append((i, "high", closes[i], dates[i]))
        for i in swing_lows:
            swings.append((i, "low", closes[i], dates[i]))
        
        swings.sort(key=lambda x: x[0])
        
        if len(swings) < 2:
            return waves
        
        # Create waves between consecutive swings
        for i in range(len(swings) - 1):
            curr_idx, curr_type, curr_price, curr_date = swings[i]
            next_idx, next_type, next_price, next_date = swings[i + 1]
            
            # Skip if same type
            if curr_type == next_type:
                continue
            
            # Calculate magnitude
            if curr_type == "low" and next_type == "high":
                # Up wave
                magnitude = ((next_price - curr_price) / curr_price) * 100
                wave_type = "up"
                peak_idx = next_idx
                peak_price = next_price
                peak_time = next_date
            else:
                # Down wave
                magnitude = ((curr_price - next_price) / curr_price) * 100
                wave_type = "down"
                peak_idx = curr_idx
                peak_price = curr_price
                peak_time = curr_date
            
            # Check magnitude threshold
            if magnitude < threshold:
                continue
            
            # Check duration constraints
            duration = next_idx - curr_idx
            if duration < min_duration or duration > max_duration:
                continue
            
            # Calculate volume delta
            start_vol = volumes[curr_idx] if curr_idx < len(volumes) else 0
            end_vol = volumes[next_idx] if next_idx < len(volumes) else 0
            volume_delta = end_vol - start_vol
            
            # Calculate drawdown
            if wave_type == "up":
                drawdown = ((peak_price - next_price) / peak_price) * 100
            else:
                drawdown = ((curr_price - next_price) / curr_price) * 100
            
            wave = Wave(
                start_time=pd.to_datetime(curr_date, utc=True),
                end_time=pd.to_datetime(next_date, utc=True),
                start_price=curr_price,
                end_price=next_price,
                peak_time=pd.to_datetime(peak_time, utc=True),
                peak_price=peak_price,
                wave_type=wave_type,
                magnitude=magnitude,
                duration=duration,
                volume_delta=volume_delta,
                drawdown=drawdown
            )
            
            waves.append(wave)
        
        return waves
    
    def _find_peaks(self, data: np.ndarray, threshold: float) -> List[int]:
        """Find local peaks in data"""
        from scipy.signal import find_peaks
        
        # Convert threshold to absolute value
        threshold_abs = np.max(data) * (threshold / 100)
        
        peaks, _ = find_peaks(data, height=threshold_abs, distance=2)
        return peaks.tolist()
    
    def _find_troughs(self, data: np.ndarray, threshold: float) -> List[int]:
        """Find local troughs in data"""
        from scipy.signal import find_peaks
        
        # Invert data to find troughs
        inverted_data = -data
        threshold_abs = np.max(data) * (threshold / 100)
        
        troughs, _ = find_peaks(inverted_data, height=threshold_abs, distance=2)
        return troughs.tolist()
    
    def _find_pivot_highs(self, data: np.ndarray, window: int = 5) -> List[int]:
        """Find pivot highs"""
        from scipy.signal import argrelextrema
        
        peaks = argrelextrema(data, np.greater, order=window)[0]
        return peaks.tolist()
    
    def _find_pivot_lows(self, data: np.ndarray, window: int = 5) -> List[int]:
        """Find pivot lows"""
        from scipy.signal import argrelextrema
        
        troughs = argrelextrema(data, np.less, order=window)[0]
        return troughs.tolist()
    
    def _find_swing_highs(self, data: np.ndarray, threshold: float) -> List[int]:
        """Find swing highs"""
        highs = []
        threshold_abs = np.max(data) * (threshold / 100)
        
        for i in range(1, len(data) - 1):
            if (data[i] > data[i-1] and data[i] > data[i+1] and 
                data[i] - np.min(data[max(0, i-5):i+6]) > threshold_abs):
                highs.append(i)
        
        return highs
    
    def _find_swing_lows(self, data: np.ndarray, threshold: float) -> List[int]:
        """Find swing lows"""
        lows = []
        threshold_abs = np.max(data) * (threshold / 100)
        
        for i in range(1, len(data) - 1):
            if (data[i] < data[i-1] and data[i] < data[i+1] and 
                np.max(data[max(0, i-5):i+6]) - data[i] > threshold_abs):
                lows.append(i)
        
        return lows
    
    def save_waves(self, symbol: str, timeframe: str, waves: List[Wave]) -> None:
        """Save waves to cache"""
        cache_file = self.cache_dir / f"{symbol}_{timeframe}_waves.json"
        
        import json
        waves_data = [wave.to_dict() for wave in waves]
        
        with open(cache_file, 'w') as f:
            json.dump(waves_data, f, default=str, indent=2)
    
    def load_waves(self, symbol: str, timeframe: str) -> List[Wave]:
        """Load waves from cache"""
        cache_file = self.cache_dir / f"{symbol}_{timeframe}_waves.json"
        
        if not cache_file.exists():
            return []
        
        import json
        with open(cache_file, 'r') as f:
            waves_data = json.load(f)
        
        waves = []
        for wave_data in waves_data:
            wave = Wave(
                start_time=pd.to_datetime(wave_data["start_time"]),
                end_time=pd.to_datetime(wave_data["end_time"]),
                start_price=wave_data["start_price"],
                end_price=wave_data["end_price"],
                peak_time=pd.to_datetime(wave_data["peak_time"]),
                peak_price=wave_data["peak_price"],
                wave_type=wave_data["wave_type"],
                magnitude=wave_data["magnitude"],
                duration=wave_data["duration"],
                volume_delta=wave_data["volume_delta"],
                drawdown=wave_data["drawdown"]
            )
            waves.append(wave)
        
        return waves