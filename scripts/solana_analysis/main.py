#!/usr/bin/env python3
"""
Solana Meme Coin Analysis CLI

Main entry point for the analysis CLI tool.
Provides commands for fetching data, analyzing waves, and generating visualizations.
"""

import argparse
import logging
import sys
from pathlib import Path

from cli import AnalysisCLI
from config import AnalysisConfig
from data_fetcher import DataFetcher
from wave_detector import WaveDetector
from fibonacci import FibonacciAnalyzer
from statistics import StatisticsAnalyzer
from visualizer import Visualizer


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Solana Meme Coin Analysis CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch data for top 200 coins
  python main.py fetch --top 200 --timeframe 4h --days 90

  # Analyze waves with 10% threshold
  python main.py analyze --timeframe 4h --threshold 10 --method zigzag

  # Query average bottom for last 5 pumps
  python main.py query avg_bottom --last-pumps 5 --universe top50

  # Visualize BONK with waves and Fibonacci levels
  python main.py visualize coin BONK --timeframe 4h --show-waves --show-fib
        """
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="analysis_config.json",
        help="Path to configuration file"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch data from exchanges")
    fetch_parser.add_argument("--top", type=int, default=200, help="Number of top coins to fetch")
    fetch_parser.add_argument("--timeframe", type=str, default="4h", help="Timeframe for data")
    fetch_parser.add_argument("--days", type=int, default=90, help="Number of days to fetch")
    fetch_parser.add_argument("--source", type=str, default="bitquery", choices=["bitquery", "dexscreener"], help="Data source")
    fetch_parser.add_argument("--fallback", type=str, default="dexscreener", help="Fallback data source")
    fetch_parser.add_argument("--output", type=str, default="data/", help="Output directory")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze waves and patterns")
    analyze_parser.add_argument("--timeframe", type=str, default="4h", help="Timeframe for analysis")
    analyze_parser.add_argument("--threshold", type=float, default=10.0, help="Wave detection threshold (percent)")
    analyze_parser.add_argument("--method", type=str, default="zigzag", choices=["zigzag", "pivots", "swing"], help="Wave detection method")
    analyze_parser.add_argument("--recompute", action="store_true", help="Force recomputation of waves")
    analyze_parser.add_argument("--universe", type=str, default="top200", help="Universe of coins to analyze")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query analysis results")
    query_parser.add_argument("query_type", type=str, help="Type of query to run")
    query_parser.add_argument("--universe", type=str, default="top200", help="Universe of coins")
    query_parser.add_argument("--timerange", type=str, help="Time range (e.g., last30d, 20240401-20240801)")
    query_parser.add_argument("--last-pumps", type=int, help="Number of last pumps to analyze")
    query_parser.add_argument("--level", type=float, help="Fibonacci level (e.g., 61.8)")
    query_parser.add_argument("--threshold", type=float, help="Threshold for analysis")
    query_parser.add_argument("--bins", type=int, help="Number of bins for histograms")
    query_parser.add_argument("--x", type=str, help="X-axis variable for correlations")
    query_parser.add_argument("--y", type=str, help="Y-axis variable for correlations")
    query_parser.add_argument("--color", type=str, help="Color variable for scatter plots")
    
    # Visualize command
    viz_parser = subparsers.add_parser("visualize", help="Generate visualizations")
    viz_subparsers = viz_parser.add_subparsers(dest="viz_type", help="Visualization type")
    
    # Coin visualization
    coin_viz = viz_subparsers.add_parser("coin", help="Visualize specific coin")
    coin_viz.add_argument("symbol", type=str, help="Coin symbol (e.g., BONK)")
    coin_viz.add_argument("--timeframe", type=str, default="4h", help="Timeframe")
    coin_viz.add_argument("--show-waves", action="store_true", help="Show wave annotations")
    coin_viz.add_argument("--show-fib", action="store_true", help="Show Fibonacci levels")
    coin_viz.add_argument("--output", type=str, help="Output file path")
    
    # Histogram visualization
    hist_viz = viz_subparsers.add_parser("fib_histogram", help="Fibonacci level histogram")
    hist_viz.add_argument("--universe", type=str, default="top100", help="Universe of coins")
    hist_viz.add_argument("--level-grid", type=str, help="Comma-separated Fibonacci levels")
    hist_viz.add_argument("--output", type=str, help="Output file path")
    
    # Heatmap visualization
    heatmap_viz = viz_subparsers.add_parser("heatmap", help="Heatmap visualization")
    heatmap_viz.add_argument("--metric", type=str, help="Metric to visualize")
    heatmap_viz.add_argument("--levels", type=str, help="Comma-separated levels")
    heatmap_viz.add_argument("--universe", type=str, default="top50", help="Universe of coins")
    heatmap_viz.add_argument("--output", type=str, help="Output file path")
    
    # Scatter plot visualization
    scatter_viz = viz_subparsers.add_parser("scatter", help="Scatter plot visualization")
    scatter_viz.add_argument("--x", type=str, required=True, help="X-axis variable")
    scatter_viz.add_argument("--y", type=str, required=True, help="Y-axis variable")
    scatter_viz.add_argument("--color", type=str, help="Color variable")
    scatter_viz.add_argument("--universe", type=str, default="top100", help="Universe of coins")
    scatter_viz.add_argument("--output", type=str, help="Output file path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = AnalysisConfig.load(args.config)
        
        # Initialize components
        data_fetcher = DataFetcher(config)
        wave_detector = WaveDetector(config)
        fib_analyzer = FibonacciAnalyzer(config)
        stats_analyzer = StatisticsAnalyzer(config)
        visualizer = Visualizer(config)
        
        # Create CLI instance
        cli = AnalysisCLI(
            data_fetcher=data_fetcher,
            wave_detector=wave_detector,
            fib_analyzer=fib_analyzer,
            stats_analyzer=stats_analyzer,
            visualizer=visualizer,
            config=config
        )
        
        # Execute command
        if args.command == "fetch":
            cli.fetch_data(
                top=args.top,
                timeframe=args.timeframe,
                days=args.days,
                source=args.source,
                fallback=args.fallback,
                output_dir=args.output
            )
        elif args.command == "analyze":
            cli.analyze_waves(
                timeframe=args.timeframe,
                threshold=args.threshold,
                method=args.method,
                recompute=args.recompute,
                universe=args.universe
            )
        elif args.command == "query":
            cli.run_query(
                query_type=args.query_type,
                universe=args.universe,
                timerange=args.timerange,
                last_pumps=args.last_pumps,
                level=args.level,
                threshold=args.threshold,
                bins=args.bins,
                x=args.x,
                y=args.y,
                color=args.color
            )
        elif args.command == "visualize":
            if args.viz_type == "coin":
                cli.visualize_coin(
                    symbol=args.symbol,
                    timeframe=args.timeframe,
                    show_waves=args.show_waves,
                    show_fib=args.show_fib,
                    output=args.output
                )
            elif args.viz_type == "fib_histogram":
                cli.visualize_fib_histogram(
                    universe=args.universe,
                    level_grid=args.level_grid,
                    output=args.output
                )
            elif args.viz_type == "heatmap":
                cli.visualize_heatmap(
                    metric=args.metric,
                    levels=args.levels,
                    universe=args.universe,
                    output=args.output
                )
            elif args.viz_type == "scatter":
                cli.visualize_scatter(
                    x=args.x,
                    y=args.y,
                    color=args.color,
                    universe=args.universe,
                    output=args.output
                )
            else:
                viz_parser.print_help()
        else:
            parser.print_help()
            
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()