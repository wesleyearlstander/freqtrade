"""
Statistical analysis for Solana meme coin waves
Provides correlation analysis, distributions, and statistical metrics
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config import AnalysisConfig
from wave_detector import Wave


logger = logging.getLogger(__name__)


class StatisticsAnalyzer:
    """Statistical analysis for wave patterns"""
    
    def __init__(self, config: AnalysisConfig):
        self.config = config
    
    def analyze_wave_statistics(
        self,
        waves: List[Wave],
        df: pd.DataFrame,
        universe: str = "top200"
    ) -> Dict[str, Any]:
        """
        Analyze statistical properties of waves
        
        Args:
            waves: List of detected waves
            df: OHLCV DataFrame
            universe: Universe identifier for context
        
        Returns:
            Dictionary with statistical analysis results
        """
        if not waves:
            return {
                "total_waves": 0,
                "up_waves": 0,
                "down_waves": 0,
                "statistics": {},
                "distributions": {},
                "correlations": {}
            }
        
        # Basic counts
        up_waves = [w for w in waves if w.wave_type == "up"]
        down_waves = [w for w in waves if w.wave_type == "down"]
        
        # Calculate statistics
        stats = self._calculate_basic_statistics(waves, up_waves, down_waves)
        
        # Calculate distributions
        distributions = self._calculate_distributions(waves, up_waves, down_waves)
        
        # Calculate correlations
        correlations = self._calculate_correlations(waves, df)
        
        return {
            "total_waves": len(waves),
            "up_waves": len(up_waves),
            "down_waves": len(down_waves),
            "statistics": stats,
            "distributions": distributions,
            "correlations": correlations,
            "universe": universe
        }
    
    def _calculate_basic_statistics(
        self,
        all_waves: List[Wave],
        up_waves: List[Wave],
        down_waves: List[Wave]
    ) -> Dict[str, Any]:
        """Calculate basic statistical metrics"""
        stats = {}
        
        # Magnitude statistics
        if all_waves:
            magnitudes = [w.magnitude for w in all_waves]
            stats["magnitude"] = {
                "mean": np.mean(magnitudes),
                "median": np.median(magnitudes),
                "std": np.std(magnitudes),
                "min": np.min(magnitudes),
                "max": np.max(magnitudes),
                "q25": np.percentile(magnitudes, 25),
                "q75": np.percentile(magnitudes, 75)
            }
        
        # Duration statistics
        if all_waves:
            durations = [w.duration for w in all_waves]
            stats["duration"] = {
                "mean": np.mean(durations),
                "median": np.median(durations),
                "std": np.std(durations),
                "min": np.min(durations),
                "max": np.max(durations),
                "q25": np.percentile(durations, 25),
                "q75": np.percentile(durations, 75)
            }
        
        # Drawdown statistics
        if all_waves:
            drawdowns = [w.drawdown for w in all_waves]
            stats["drawdown"] = {
                "mean": np.mean(drawdowns),
                "median": np.median(drawdowns),
                "std": np.std(drawdowns),
                "min": np.min(drawdowns),
                "max": np.max(drawdowns),
                "q25": np.percentile(drawdowns, 25),
                "q75": np.percentile(drawdowns, 75)
            }
        
        # Volume delta statistics
        if all_waves:
            volume_deltas = [w.volume_delta for w in all_waves]
            stats["volume_delta"] = {
                "mean": np.mean(volume_deltas),
                "median": np.median(volume_deltas),
                "std": np.std(volume_deltas),
                "min": np.min(volume_deltas),
                "max": np.max(volume_deltas),
                "q25": np.percentile(volume_deltas, 25),
                "q75": np.percentile(volume_deltas, 75)
            }
        
        # Up vs down wave statistics
        if up_waves:
            up_magnitudes = [w.magnitude for w in up_waves]
            stats["up_waves"] = {
                "count": len(up_waves),
                "avg_magnitude": np.mean(up_magnitudes),
                "avg_duration": np.mean([w.duration for w in up_waves]),
                "avg_drawdown": np.mean([w.drawdown for w in up_waves])
            }
        
        if down_waves:
            down_magnitudes = [w.magnitude for w in down_waves]
            stats["down_waves"] = {
                "count": len(down_waves),
                "avg_magnitude": np.mean(down_magnitudes),
                "avg_duration": np.mean([w.duration for w in down_waves]),
                "avg_drawdown": np.mean([w.drawdown for w in down_waves])
            }
        
        return stats
    
    def _calculate_distributions(
        self,
        all_waves: List[Wave],
        up_waves: List[Wave],
        down_waves: List[Wave]
    ) -> Dict[str, Any]:
        """Calculate distribution properties"""
        distributions = {}
        
        # Magnitude distribution
        if all_waves:
            magnitudes = [w.magnitude for w in all_waves]
            distributions["magnitude"] = self._calculate_distribution_properties(magnitudes)
        
        # Duration distribution
        if all_waves:
            durations = [w.duration for w in all_waves]
            distributions["duration"] = self._calculate_distribution_properties(durations)
        
        # Drawdown distribution
        if all_waves:
            drawdowns = [w.drawdown for w in all_waves]
            distributions["drawdown"] = self._calculate_distribution_properties(drawdowns)
        
        # Wave type distribution
        if all_waves:
            up_count = len(up_waves)
            down_count = len(down_waves)
            total = len(all_waves)
            
            distributions["wave_types"] = {
                "up_percentage": (up_count / total) * 100,
                "down_percentage": (down_count / total) * 100,
                "up_count": up_count,
                "down_count": down_count
            }
        
        return distributions
    
    def _calculate_distribution_properties(self, data: List[float]) -> Dict[str, Any]:
        """Calculate distribution properties for a dataset"""
        if not data:
            return {}
        
        data_array = np.array(data)
        
        # Basic statistics
        mean = np.mean(data_array)
        std = np.std(data_array)
        skewness = self._calculate_skewness(data_array)
        kurtosis = self._calculate_kurtosis(data_array)
        
        # Percentiles
        percentiles = {
            "p10": np.percentile(data_array, 10),
            "p25": np.percentile(data_array, 25),
            "p50": np.percentile(data_array, 50),
            "p75": np.percentile(data_array, 75),
            "p90": np.percentile(data_array, 90),
            "p95": np.percentile(data_array, 95),
            "p99": np.percentile(data_array, 99)
        }
        
        # Histogram bins
        hist, bin_edges = np.histogram(data_array, bins=20)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        return {
            "mean": mean,
            "std": std,
            "skewness": skewness,
            "kurtosis": kurtosis,
            "percentiles": percentiles,
            "histogram": {
                "counts": hist.tolist(),
                "bin_centers": bin_centers.tolist(),
                "bin_edges": bin_edges.tolist()
            }
        }
    
    def _calculate_skewness(self, data: np.ndarray) -> float:
        """Calculate skewness of data"""
        if len(data) < 3:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return 0.0
        
        skewness = np.mean(((data - mean) / std) ** 3)
        return skewness
    
    def _calculate_kurtosis(self, data: np.ndarray) -> float:
        """Calculate kurtosis of data"""
        if len(data) < 4:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return 0.0
        
        kurtosis = np.mean(((data - mean) / std) ** 4) - 3
        return kurtosis
    
    def _calculate_correlations(
        self,
        waves: List[Wave],
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate correlations between wave properties and market data"""
        if not waves or df.empty:
            return {}
        
        # Prepare data for correlation analysis
        wave_data = []
        
        for wave in waves:
            # Get market data for the wave period
            wave_df = df[(df["date"] >= wave.start_time) & (df["date"] <= wave.end_time)]
            
            if wave_df.empty:
                continue
            
            # Calculate market metrics
            avg_volume = wave_df["volume"].mean()
            price_volatility = wave_df["close"].std() / wave_df["close"].mean()
            volume_volatility = wave_df["volume"].std() / wave_df["volume"].mean() if wave_df["volume"].mean() > 0 else 0
            
            wave_data.append({
                "magnitude": wave.magnitude,
                "duration": wave.duration,
                "drawdown": wave.drawdown,
                "volume_delta": wave.volume_delta,
                "avg_volume": avg_volume,
                "price_volatility": price_volatility,
                "volume_volatility": volume_volatility,
                "wave_type": 1 if wave.wave_type == "up" else 0
            })
        
        if not wave_data:
            return {}
        
        # Create DataFrame for correlation analysis
        corr_df = pd.DataFrame(wave_data)
        
        # Calculate correlation matrix
        numeric_cols = corr_df.select_dtypes(include=[np.number]).columns
        corr_matrix = corr_df[numeric_cols].corr()
        
        # Extract specific correlations
        correlations = {}
        
        # Magnitude correlations
        if "magnitude" in corr_matrix.columns:
            magnitude_corr = corr_matrix["magnitude"].drop("magnitude")
            correlations["magnitude"] = magnitude_corr.to_dict()
        
        # Duration correlations
        if "duration" in corr_matrix.columns:
            duration_corr = corr_matrix["duration"].drop("duration")
            correlations["duration"] = duration_corr.to_dict()
        
        # Drawdown correlations
        if "drawdown" in corr_matrix.columns:
            drawdown_corr = corr_matrix["drawdown"].drop("drawdown")
            correlations["drawdown"] = drawdown_corr.to_dict()
        
        return correlations
    
    def analyze_rolling_statistics(
        self,
        waves: List[Wave],
        window_size: int = 10
    ) -> Dict[str, Any]:
        """Analyze rolling statistics for waves"""
        if not waves or len(waves) < window_size:
            return {}
        
        # Sort waves by start time
        sorted_waves = sorted(waves, key=lambda x: x.start_time)
        
        # Calculate rolling statistics
        rolling_stats = {
            "magnitude": [],
            "duration": [],
            "drawdown": [],
            "volume_delta": []
        }
        
        for i in range(window_size - 1, len(sorted_waves)):
            window_waves = sorted_waves[i - window_size + 1:i + 1]
            
            rolling_stats["magnitude"].append(np.mean([w.magnitude for w in window_waves]))
            rolling_stats["duration"].append(np.mean([w.duration for w in window_waves]))
            rolling_stats["drawdown"].append(np.mean([w.drawdown for w in window_waves]))
            rolling_stats["volume_delta"].append(np.mean([w.volume_delta for w in window_waves]))
        
        return {
            "window_size": window_size,
            "rolling_stats": rolling_stats,
            "trends": self._calculate_trends(rolling_stats)
        }
    
    def _calculate_trends(self, rolling_stats: Dict[str, List[float]]) -> Dict[str, Any]:
        """Calculate trends in rolling statistics"""
        trends = {}
        
        for metric, values in rolling_stats.items():
            if len(values) < 2:
                continue
            
            # Calculate linear trend
            x = np.arange(len(values))
            slope, intercept = np.polyfit(x, values, 1)
            
            # Calculate trend strength (R-squared)
            y_pred = slope * x + intercept
            ss_res = np.sum((values - y_pred) ** 2)
            ss_tot = np.sum((values - np.mean(values)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            trends[metric] = {
                "slope": slope,
                "intercept": intercept,
                "r_squared": r_squared,
                "trend_direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
            }
        
        return trends
    
    def get_wave_ranges(
        self,
        waves: List[Wave],
        timerange: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get wave ranges for a specific time period"""
        if not waves:
            return {"waves": [], "count": 0}
        
        # Filter by timerange if specified
        if timerange:
            start_date, end_date = self._parse_timerange(timerange)
            filtered_waves = [
                w for w in waves
                if start_date <= w.start_time <= end_date
            ]
        else:
            filtered_waves = waves
        
        # Sort by start time
        filtered_waves.sort(key=lambda x: x.start_time)
        
        # Calculate ranges
        if filtered_waves:
            magnitudes = [w.magnitude for w in filtered_waves]
            durations = [w.duration for w in filtered_waves]
            drawdowns = [w.drawdown for w in filtered_waves]
            
            ranges = {
                "magnitude": {
                    "min": min(magnitudes),
                    "max": max(magnitudes),
                    "range": max(magnitudes) - min(magnitudes)
                },
                "duration": {
                    "min": min(durations),
                    "max": max(durations),
                    "range": max(durations) - min(durations)
                },
                "drawdown": {
                    "min": min(drawdowns),
                    "max": max(drawdowns),
                    "range": max(drawdowns) - min(drawdowns)
                }
            }
        else:
            ranges = {}
        
        return {
            "waves": [w.to_dict() for w in filtered_waves],
            "count": len(filtered_waves),
            "ranges": ranges,
            "timerange": timerange
        }
    
    def _parse_timerange(self, timerange: str) -> Tuple[datetime, datetime]:
        """Parse timerange string into start and end dates"""
        if timerange.startswith("last"):
            # Parse relative timerange (e.g., "last30d", "last7d")
            days = int(timerange[4:-1])
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=days)
        elif "-" in timerange:
            # Parse absolute timerange (e.g., "20240401-20240801")
            start_str, end_str = timerange.split("-")
            start_date = datetime.strptime(start_str, "%Y%m%d").replace(tzinfo=UTC)
            end_date = datetime.strptime(end_str, "%Y%m%d").replace(tzinfo=UTC)
        else:
            # Single date
            date = datetime.strptime(timerange, "%Y%m%d").replace(tzinfo=UTC)
            start_date = date
            end_date = date + timedelta(days=1)
        
        return start_date, end_date