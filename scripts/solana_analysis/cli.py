"""
Command Line Interface for Solana analysis
Handles command execution and user interactions
"""

import logging
from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import AnalysisConfig
from data_fetcher import DataFetcher
from wave_detector import WaveDetector
from fibonacci import FibonacciAnalyzer
from statistics import StatisticsAnalyzer
from visualizer import Visualizer


logger = logging.getLogger(__name__)


class AnalysisCLI:
    """Main CLI class for Solana analysis"""
    
    def __init__(
        self,
        config: AnalysisConfig,
        data_fetcher: DataFetcher,
        wave_detector: WaveDetector,
        fib_analyzer: FibonacciAnalyzer,
        stats_analyzer: StatisticsAnalyzer,
        visualizer: Visualizer
    ):
        self.config = config
        self.data_fetcher = data_fetcher
        self.wave_detector = wave_detector
        self.fib_analyzer = fib_analyzer
        self.stats_analyzer = stats_analyzer
        self.visualizer = visualizer
    
    def fetch_data(
        self,
        top: int = 200,
        timeframe: str = "4h",
        days: int = 90,
        source: str = "bitquery",
        fallback: str = "dexscreener",
        output_dir: str = "data/"
    ) -> None:
        """Fetch data for analysis"""
        logger.info(f"Starting data fetch for top {top} coins")
        
        try:
            self.data_fetcher.fetch_data(
                top=top,
                timeframe=timeframe,
                days=days,
                source=source,
                fallback=fallback,
                output_dir=output_dir
            )
            logger.info("Data fetch completed successfully")
        except Exception as e:
            logger.error(f"Data fetch failed: {e}")
            raise
    
    def analyze_waves(
        self,
        timeframe: str = "4h",
        threshold: float = 10.0,
        method: str = "zigzag",
        recompute: bool = False,
        universe: str = "top200"
    ) -> None:
        """Analyze waves for all coins in universe"""
        logger.info(f"Starting wave analysis for {universe}")
        
        # Get list of coins in universe
        universe_size = self.config.get_universe_size(universe)
        coins = self._get_universe_coins(universe_size)
        
        total_waves = 0
        successful = 0
        failed = 0
        
        for coin in coins:
            try:
                symbol = coin["symbol"]
                logger.info(f"Analyzing waves for {symbol}")
                
                # Load data
                df = self.data_fetcher.load_data(symbol, timeframe)
                if df is None or df.empty:
                    logger.warning(f"No data available for {symbol}")
                    failed += 1
                    continue
                
                # Check if analysis already exists
                if not recompute:
                    existing_waves = self.wave_detector.load_waves(symbol, timeframe)
                    if existing_waves:
                        logger.info(f"Using cached waves for {symbol}")
                        total_waves += len(existing_waves)
                        successful += 1
                        continue
                
                # Detect waves
                waves = self.wave_detector.detect_waves(
                    df=df,
                    method=method,
                    threshold=threshold,
                    min_duration=self.config.wave_detection.get("min_wave_duration", 1),
                    max_duration=self.config.wave_detection.get("max_wave_duration", 1000)
                )
                
                # Save waves
                if waves:
                    self.wave_detector.save_waves(symbol, timeframe, waves)
                    total_waves += len(waves)
                    logger.info(f"Detected {len(waves)} waves for {symbol}")
                
                successful += 1
                
            except Exception as e:
                logger.error(f"Failed to analyze waves for {coin['symbol']}: {e}")
                failed += 1
        
        logger.info(f"Wave analysis completed: {successful} successful, {failed} failed, {total_waves} total waves")
    
    def execute_query(
        self,
        query_type: str,
        universe: str = "top200",
        timerange: Optional[str] = None,
        last_pumps: Optional[int] = None,
        level: Optional[float] = None,
        threshold: Optional[float] = None,
        x: Optional[str] = None,
        y: Optional[str] = None,
        bins: Optional[int] = None
    ) -> None:
        """Execute analysis queries"""
        logger.info(f"Executing query: {query_type}")
        
        # Get universe coins
        universe_size = self.config.get_universe_size(universe)
        coins = self._get_universe_coins(universe_size)
        
        if query_type == "wave_ranges":
            self._query_wave_ranges(coins, timerange)
        elif query_type == "fib_distribution":
            self._query_fib_distribution(coins, level, timerange)
        elif query_type == "avg_bottom":
            self._query_avg_bottom(coins, last_pumps)
        elif query_type == "invalidations":
            self._query_invalidations(coins, threshold, timerange)
        elif query_type == "correlations":
            self._query_correlations(coins, x, y, bins)
        else:
            logger.error(f"Unknown query type: {query_type}")
    
    def _query_wave_ranges(
        self,
        coins: List[Dict[str, Any]],
        timerange: Optional[str] = None
    ) -> None:
        """Query wave ranges for universe"""
        logger.info("Querying wave ranges...")
        
        all_waves = []
        for coin in coins:
            symbol = coin["symbol"]
            df = self.data_fetcher.load_data(symbol, "4h")
            if df is not None and not df.empty:
                waves = self.wave_detector.load_waves(symbol, "4h")
                all_waves.extend(waves)
        
        # Get wave ranges
        ranges = self.stats_analyzer.get_wave_ranges(all_waves, timerange)
        
        # Print results
        print(f"\nWave Ranges Analysis")
        print(f"Total waves: {ranges['count']}")
        if ranges['ranges']:
            print(f"Magnitude range: {ranges['ranges']['magnitude']['min']:.2f}% - {ranges['ranges']['magnitude']['max']:.2f}%")
            print(f"Duration range: {ranges['ranges']['duration']['min']} - {ranges['ranges']['duration']['max']} candles")
            print(f"Drawdown range: {ranges['ranges']['drawdown']['min']:.2f}% - {ranges['ranges']['drawdown']['max']:.2f}%")
    
    def _query_fib_distribution(
        self,
        coins: List[Dict[str, Any]],
        level: Optional[float] = None,
        timerange: Optional[str] = None
    ) -> None:
        """Query Fibonacci distribution"""
        logger.info("Querying Fibonacci distribution...")
        
        if level is None:
            level = 61.8
        
        # Analyze Fibonacci levels for all coins
        all_analyses = []
        for coin in coins:
            symbol = coin["symbol"]
            df = self.data_fetcher.load_data(symbol, "4h")
            if df is not None and not df.empty:
                waves = self.wave_detector.load_waves(symbol, "4h")
                for wave in waves:
                    analysis = self.fib_analyzer.analyze_wave_fibonacci(wave, df)
                    all_analyses.append(analysis)
        
        # Get distribution for specific level
        distribution = self.fib_analyzer.get_fibonacci_distribution(all_analyses, level)
        
        # Print results
        print(f"\nFibonacci Level {level} Distribution")
        print(f"Touch rate: {distribution['touch_rate']:.2%}")
        print(f"Invalidation rate: {distribution['invalidation_rate']:.2%}")
        print(f"Average hold time: {distribution['avg_hold_time']:.1f} candles")
        print(f"Average deepest retrace: {distribution['avg_deepest_retrace']:.2f}%")
    
    def _query_avg_bottom(
        self,
        coins: List[Dict[str, Any]],
        last_pumps: Optional[int] = None
    ) -> None:
        """Query average bottom retracement"""
        logger.info("Querying average bottom retracement...")
        
        if last_pumps is None:
            last_pumps = 5
        
        all_waves = []
        for coin in coins:
            symbol = coin["symbol"]
            df = self.data_fetcher.load_data(symbol, "4h")
            if df is not None and not df.empty:
                waves = self.wave_detector.load_waves(symbol, "4h")
                all_waves.extend(waves)
        
        # Calculate average bottom retracement
        avg_bottom = self.fib_analyzer.get_average_bottom_retracement(all_waves, last_pumps)
        
        # Print results
        print(f"\nAverage Bottom Retracement (Last {last_pumps} Pumps)")
        print(f"Average retracement: {avg_bottom:.2f}%")
    
    def _query_invalidations(
        self,
        coins: List[Dict[str, Any]],
        threshold: Optional[float] = None,
        timerange: Optional[str] = None
    ) -> None:
        """Query Fibonacci invalidations"""
        logger.info("Querying Fibonacci invalidations...")
        
        if threshold is None:
            threshold = 50.0
        
        # Analyze invalidations
        total_waves = 0
        invalidations = 0
        
        for coin in coins:
            symbol = coin["symbol"]
            df = self.data_fetcher.load_data(symbol, "4h")
            if df is not None and not df.empty:
                waves = self.wave_detector.load_waves(symbol, "4h")
                for wave in waves:
                    if wave.magnitude >= threshold:
                        total_waves += 1
                        analysis = self.fib_analyzer.analyze_wave_fibonacci(wave, df)
                        if analysis.get("invalidation_level") is not None:
                            invalidations += 1
        
        # Print results
        print(f"\nFibonacci Invalidations (Waves >= {threshold}%)")
        print(f"Total waves: {total_waves}")
        print(f"Invalidations: {invalidations}")
        if total_waves > 0:
            print(f"Invalidation rate: {invalidations/total_waves:.2%}")
    
    def _query_correlations(
        self,
        coins: List[Dict[str, Any]],
        x: Optional[str] = None,
        y: Optional[str] = None,
        bins: Optional[int] = None
    ) -> None:
        """Query correlations between variables"""
        logger.info("Querying correlations...")
        
        if x is None:
            x = "market_cap"
        if y is None:
            y = "wave_magnitude"
        
        # Collect data for correlation analysis
        all_waves = []
        for coin in coins:
            symbol = coin["symbol"]
            df = self.data_fetcher.load_data(symbol, "4h")
            if df is not None and not df.empty:
                waves = self.wave_detector.load_waves(symbol, "4h")
                all_waves.extend(waves)
        
        # Analyze correlations
        correlations = self.stats_analyzer.analyze_wave_statistics(all_waves, df)
        
        # Print results
        print(f"\nCorrelation Analysis: {y} vs {x}")
        if correlations.get("correlations"):
            corr_data = correlations["correlations"]
            if x in corr_data and y in corr_data[x]:
                correlation = corr_data[x][y]
                print(f"Correlation coefficient: {correlation:.4f}")
            else:
                print("Correlation data not available")
        else:
            print("No correlation data available")
    
    def visualize_coin(
        self,
        symbol: str,
        timeframe: str = "4h",
        show_waves: bool = True,
        show_fib: bool = True,
        output: Optional[str] = None
    ) -> None:
        """Visualize a specific coin"""
        logger.info(f"Visualizing {symbol} ({timeframe})")
        
        # Load data
        df = self.data_fetcher.load_data(symbol, timeframe)
        if df is None or df.empty:
            logger.error(f"No data available for {symbol}")
            return
        
        # Load waves
        waves = self.wave_detector.load_waves(symbol, timeframe)
        
        # Create visualization
        self.visualizer.visualize_coin(
            symbol=symbol,
            df=df,
            waves=waves,
            timeframe=timeframe,
            show_waves=show_waves,
            show_fib=show_fib,
            output=output
        )
    
    def visualize_fib_histogram(
        self,
        universe: str = "top100",
        level_grid: Optional[str] = None,
        output: Optional[str] = None
    ) -> None:
        """Visualize Fibonacci histogram"""
        logger.info(f"Creating Fibonacci histogram for {universe}")
        
        # Get universe coins
        universe_size = self.config.get_universe_size(universe)
        coins = self._get_universe_coins(universe_size)
        
        # Collect Fibonacci analyses
        all_analyses = []
        for coin in coins:
            symbol = coin["symbol"]
            df = self.data_fetcher.load_data(symbol, "4h")
            if df is not None and not df.empty:
                waves = self.wave_detector.load_waves(symbol, "4h")
                for wave in waves:
                    analysis = self.fib_analyzer.analyze_wave_fibonacci(wave, df)
                    all_analyses.append(analysis)
        
        # Create histogram
        self.visualizer.visualize_fibonacci_histogram(
            analyses=all_analyses,
            universe=universe,
            level_grid=level_grid,
            output=output
        )
    
    def visualize_heatmap(
        self,
        metric: str,
        levels: Optional[str] = None,
        universe: str = "top50",
        output: Optional[str] = None
    ) -> None:
        """Visualize heatmap"""
        logger.info(f"Creating heatmap for {metric}")
        
        self.visualizer.visualize_heatmap(
            metric=metric,
            levels=levels,
            universe=universe,
            output=output
        )
    
    def visualize_scatter(
        self,
        x: str,
        y: str,
        color: Optional[str] = None,
        output: Optional[str] = None
    ) -> None:
        """Visualize scatter plot"""
        logger.info(f"Creating scatter plot: {y} vs {x}")
        
        self.visualizer.visualize_scatter(
            x=x,
            y=y,
            color=color,
            output=output
        )
    
    def _get_universe_coins(self, universe_size: int) -> List[Dict[str, Any]]:
        """Get list of coins for universe"""
        # This would typically load from a data source
        # For now, return a placeholder list
        coins = []
        for i in range(universe_size):
            coins.append({
                "symbol": f"COIN{i+1}",
                "name": f"Coin {i+1}",
                "address": f"address_{i+1}"
            })
        return coins