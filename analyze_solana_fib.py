"""
Quick analysis of Fibonacci retracement levels for Solana meme coins
"""
import os
import sys
import logging
from datetime import datetime, timedelta, UTC
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for Windows

# Add freqtrade to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from freqtrade.configuration import Configuration
from freqtrade.exchange.SolanaDex import SolanaDex
from freqtrade.data.history import load_pair_history
from freqtrade.enums import CandleType
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_cached_ohlcv(pair: str, timeframe: str, since_ms: int, exchange, config) -> pd.DataFrame:
    """
    Get OHLCV data from cache if available, otherwise fetch from exchange
    This saves Bitquery API credits by reusing downloaded data
    """
    datadir = Path(config.get('datadir', 'user_data/data/solanadex'))
    datadir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Try to load from cache first
        logger.info(f"Checking cache for {pair}...")
        df = load_pair_history(
            pair=pair,
            timeframe=timeframe,
            datadir=datadir,
            data_format=config.get('dataformat_ohlcv', 'feather'),
            candle_type=CandleType.SPOT
        )
        
        if not df.empty:
            # Check if cached data is recent enough
            last_date = df['date'].max()
            now_ms = int(datetime.now(UTC).timestamp() * 1000)
            
            # If cache is less than 1 hour old, use it
            if (now_ms - last_date) < (3600 * 1000):
                logger.info(f"Using cached data for {pair} (last update: {pd.to_datetime(last_date, unit='ms')})")
                return df
            else:
                logger.info(f"Cache outdated for {pair}, fetching new data...")
    except (FileNotFoundError, ValueError) as e:
        logger.info(f"No cache found for {pair}, fetching from Bitquery...")
    
    # Fetch from exchange
    df = exchange.get_historic_ohlcv(
        pair=pair,
        timeframe=timeframe,
        since_ms=since_ms,
        candle_type=CandleType.SPOT
    )
    
    # Save to cache for next time
    if not df.empty:
        from freqtrade.data.history import get_datahandler
        data_handler = get_datahandler(datadir, config.get('dataformat_ohlcv', 'feather'))
        data_handler.ohlcv_store(pair, timeframe, data=df, candle_type=CandleType.SPOT)
        logger.info(f"Saved {pair} data to cache ({len(df)} candles)")
    
    return df


def plot_buy_zones_analysis(df_results: pd.DataFrame, output_file: str = 'solana_buy_zones.png'):
    """Create a visualization showing the best buy zones based on Fibonacci levels"""
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # Plot 1: Density plot of retracement levels (where to buy)
    # Adjust range to include all data points (including negative for new lows)
    min_fib = min(-10, df_results['fib_level'].min() - 5)
    max_fib = max(110, df_results['fib_level'].max() + 5)
    
    if len(df_results) > 1:
        from scipy.stats import gaussian_kde
        density = gaussian_kde(df_results['fib_level'])
        xs = np.linspace(min_fib, max_fib, 200)
        density_values = density(xs)
        
        ax1.fill_between(xs, density_values, alpha=0.5, color='steelblue')
        ax1.plot(xs, density_values, linewidth=2, color='darkblue')
    else:
        ax1.hist(df_results['fib_level'], bins=30, range=(min_fib, max_fib), 
                color='steelblue', alpha=0.7, edgecolor='black', density=True)
    
    # Mark Fibonacci levels
    fib_levels = [23.6, 38.2, 50.0, 61.8, 78.6]
    fib_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8']
    fib_names = ['23.6%', '38.2%', '50%\n(Fair)', '61.8%', '78.6%']
    
    for level, color, name in zip(fib_levels, fib_colors, fib_names):
        ax1.axvline(x=level, color=color, linestyle='--', linewidth=2, alpha=0.7)
        ax1.text(level, ax1.get_ylim()[1]*0.95, name, ha='center', 
                fontsize=9, fontweight='bold', color=color)
    
    ax1.set_xlabel('Fibonacci Level (%) - Negative = New Lows Below Start', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Density', fontsize=12, fontweight='bold')
    ax1.set_title('Buy Zone Density - Where Coins Retrace To', 
                  fontsize=13, fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
    ax1.set_xlim(min_fib, max_fib)
    
    # Add shading for different zones
    ax1.axvspan(min_fib, 0, alpha=0.15, color='red', label='New Lows (Below Start)')
    ax1.axvspan(0, 50, alpha=0.1, color='green', label='Below Fair Value')
    ax1.axvspan(50, max_fib, alpha=0.1, color='orange', label='Above Fair Value')
    ax1.axvline(x=0, color='black', linestyle='-', linewidth=2, alpha=0.5, label='Wave Start (0%)')
    ax1.legend(loc='upper right', fontsize=9)
    
    # Plot 2: Scatter plot - Wave Magnitude vs Fib Level
    scatter = ax2.scatter(df_results['fib_level'], df_results['magnitude'], 
                         c=df_results['fib_level'], cmap='RdYlGn_r', 
                         s=100, alpha=0.6, edgecolors='black', linewidth=1)
    
    ax2.axvline(x=50, color='gray', linestyle='--', linewidth=2, alpha=0.5, label='Fair Value')
    ax2.set_xlabel('Fibonacci Level (%)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Wave Magnitude (%)', fontsize=12, fontweight='bold')
    ax2.set_title('Wave Size vs Retracement Depth', fontsize=13, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
    ax2.legend(loc='upper right', fontsize=9)
    plt.colorbar(scatter, ax=ax2, label='Fib Level')
    
    # Plot 3: Average Fib Level with confidence interval
    mean_fib = df_results['fib_level'].mean()
    std_fib = df_results['fib_level'].std()
    
    zones = ['0-23.6%\n(Very Cheap)', '23.6-38.2%\n(Cheap)', '38.2-50%\n(Fair-)', 
             '50-61.8%\n(Fair+)', '61.8-78.6%\n(Expensive)', '78.6-100%\n(Very Expensive)']
    zone_ranges = [(0, 23.6), (23.6, 38.2), (38.2, 50), (50, 61.8), (61.8, 78.6), (78.6, 100)]
    zone_colors = ['#2ecc71', '#27ae60', '#f39c12', '#e67e22', '#e74c3c', '#c0392b']
    
    counts = []
    for low, high in zone_ranges:
        count = len(df_results[(df_results['fib_level'] >= low) & (df_results['fib_level'] < high)])
        counts.append(count)
    
    bars = ax3.barh(zones, counts, color=zone_colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    
    # Add percentage labels
    total = len(df_results)
    for i, (bar, count) in enumerate(zip(bars, counts)):
        if count > 0:
            pct = (count / total) * 100
            ax3.text(count + 0.1, i, f'{count} ({pct:.0f}%)', 
                    va='center', fontsize=10, fontweight='bold')
    
    ax3.set_xlabel('Number of Coins', fontsize=12, fontweight='bold')
    ax3.set_title('Distribution Across Price Zones', fontsize=13, fontweight='bold', pad=15)
    ax3.grid(True, alpha=0.3, axis='x', linestyle=':', linewidth=0.5)
    
    # Plot 4: Key Statistics and Recommendation
    ax4.axis('off')
    
    # Calculate buy zone recommendation
    if mean_fib < 30:
        recommendation = "STRONG BUY ZONE"
        rec_color = '#2ecc71'
        rec_detail = "Most coins are deeply oversold"
    elif mean_fib < 40:
        recommendation = "BUY ZONE"
        rec_color = '#27ae60'
        rec_detail = "Good entry opportunities"
    elif mean_fib < 50:
        recommendation = "FAIR VALUE"
        rec_color = '#f39c12'
        rec_detail = "Near equilibrium pricing"
    elif mean_fib < 60:
        recommendation = "NEUTRAL"
        rec_color = '#e67e22'
        rec_detail = "Slightly expensive"
    else:
        recommendation = "CAUTION"
        rec_color = '#e74c3c'
        rec_detail = "Prices near recent highs"
    
    stats_text = f"""
╔══════════════════════════════════════╗
║     FIBONACCI ANALYSIS SUMMARY       ║
╚══════════════════════════════════════╝

📊 Sample Size: {len(df_results)} waves analyzed

📈 Wave Characteristics:
   • Avg Magnitude: {df_results['magnitude'].mean():.1f}%
   • Median Magnitude: {df_results['magnitude'].median():.1f}%

🎯 Retracement Levels:
   • Average Fib Level: {mean_fib:.1f}%
   • Median Fib Level: {df_results['fib_level'].median():.1f}%
   • Std Deviation: {std_fib:.1f}%
   • Range: {df_results['fib_level'].min():.1f}% - {df_results['fib_level'].max():.1f}%

💡 Market Assessment:
   • {recommendation}
   • {rec_detail}

📍 Best Entry Zones:
   • Below 38.2%: Aggressive buy
   • 38.2% - 50%: Conservative buy
   • Above 50%: Wait for pullback

⚠️  Risk Level: {"HIGH" if df_results['magnitude'].mean() > 500 else "MODERATE" if df_results['magnitude'].mean() > 100 else "LOW"}
"""
    
    ax4.text(0.1, 0.95, stats_text, transform=ax4.transAxes,
            verticalalignment='top', fontsize=11, family='monospace',
            bbox=dict(boxstyle='round', facecolor=rec_color, alpha=0.2, 
                     edgecolor=rec_color, linewidth=3))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nBuy zones graph saved to: {output_file}")
    plt.close()


def plot_retracement_distribution(df_results: pd.DataFrame, output_file: str = 'solana_fib_distribution.png'):
    """Create a histogram showing the distribution of Fibonacci levels where price retraced to"""
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Adjust range to include all data (including negative for new lows)
    min_fib = min(-10, df_results['fib_level'].min() - 5)
    max_fib = max(110, df_results['fib_level'].max() + 5)
    
    # Plot 1: Histogram with Fibonacci levels marked
    # Using fib_level which shows where price IS (0% = low, 100% = high)
    ax1.hist(df_results['fib_level'], bins=30, range=(min_fib, max_fib), 
             color='steelblue', alpha=0.7, edgecolor='black')
    
    # Mark standard Fibonacci levels
    fib_levels = [23.6, 38.2, 50.0, 61.8, 78.6, 100.0]
    fib_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F']
    
    for level, color in zip(fib_levels, fib_colors):
        ax1.axvline(x=level, color=color, linestyle='--', linewidth=2, alpha=0.8,
                   label=f'{level}% Fib Level')
    
    ax1.set_xlabel('Fibonacci Level (Negative = New Lows)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Number of Waves', fontsize=12, fontweight='bold')
    ax1.set_title('Distribution of Fibonacci Levels Where Price Retraced To\nSolana Meme Coins\n(Negative = broke below start, 0-100 = within wave range)', 
                  fontsize=14, fontweight='bold', pad=20)
    ax1.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
    
    # Add reference line at 0%
    ax1.axvline(x=0, color='black', linestyle='-', linewidth=2, alpha=0.5, label='Wave Start (0%)')
    # Add shading
    ax1.axvspan(min_fib, 0, alpha=0.1, color='red', label='New Lows')
    ax1.axvspan(0, 50, alpha=0.1, color='green', label='Below Fair Value')
    ax1.axvspan(50, max_fib, alpha=0.1, color='orange', label='Above Fair Value')
    
    ax1.legend(loc='upper right', fontsize=9)
    ax1.set_xlim(min_fib, max_fib)
    
    # Add statistics box
    stats_text = f"""Fib Level Statistics:
    Mean: {df_results['fib_level'].mean():.1f}%
    Median: {df_results['fib_level'].median():.1f}%
    Std Dev: {df_results['fib_level'].std():.1f}%
    Min: {df_results['fib_level'].min():.1f}%
    Max: {df_results['fib_level'].max():.1f}%
    N: {len(df_results)} coins
    
    (50% = Fair Value)"""
    
    ax1.text(0.98, 0.97, stats_text, transform=ax1.transAxes,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
            fontsize=10, family='monospace')
    
    # Plot 2: Box plot by Fibonacci zones (including negative)
    fib_zones = {
        '<0%\n(New Lows)': (min_fib, 0),
        '0-23.6%\n(Deep)': (0, 23.6),
        '23.6-38.2%': (23.6, 38.2),
        '38.2-50%': (38.2, 50.0),
        '50-61.8%\n(Fair Value)': (50.0, 61.8),
        '61.8-78.6%': (61.8, 78.6),
        '78.6-100%\n(Near High)': (78.6, 100.0),
        '>100%': (100.0, max_fib)
    }
    
    zone_counts = []
    zone_labels = []
    for zone_name, (low, high) in fib_zones.items():
        count = len(df_results[(df_results['fib_level'] >= low) & 
                               (df_results['fib_level'] < high)])
        zone_counts.append(count)
        zone_labels.append(zone_name)
    
    colors_bar = ['#c0392b', '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#95a5a6']
    bars = ax2.bar(zone_labels, zone_counts, color=colors_bar, alpha=0.7, edgecolor='black')
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax2.set_xlabel('Fibonacci Zone', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Number of Coins', fontsize=12, fontweight='bold')
    ax2.set_title('Count by Fibonacci Retracement Zone', fontsize=14, fontweight='bold', pad=20)
    ax2.grid(True, alpha=0.3, axis='y', linestyle=':', linewidth=0.5)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nGraph saved to: {output_file}")
    plt.close()


def detect_all_waves(df: pd.DataFrame, min_wave_pct: float = 20.0) -> list:
    """
    Detect ALL significant waves in the data using a rolling window approach
    This finds multiple waves by looking for all local lows followed by significant highs
    """
    if df.empty or len(df) < 5:
        return []
    
    waves = []
    df_copy = df.copy().reset_index(drop=True)
    
    # Use a rolling window to find local lows (troughs)
    window = 5  # Look 5 periods before and after
    
    for i in range(window, len(df_copy) - window):
        # Check if this is a local low
        current_low = df_copy.loc[i, 'low']
        is_local_low = True
        
        # Check if it's lower than surrounding candles
        for offset in range(1, window + 1):
            if i - offset >= 0 and df_copy.loc[i - offset, 'low'] < current_low:
                is_local_low = False
                break
            if i + offset < len(df_copy) and df_copy.loc[i + offset, 'low'] < current_low:
                is_local_low = False
                break
        
        if not is_local_low:
            continue
        
        # Found a local low, now look for significant high after it
        low_idx = i
        low_price = current_low
        low_time = df_copy.loc[i, 'date']
        
        # Search for highest point after this low
        high_idx = None
        high_price = low_price
        high_time = None
        
        for j in range(i + 1, min(i + 100, len(df_copy))):  # Look up to 100 candles ahead
            if df_copy.loc[j, 'high'] > high_price:
                high_price = df_copy.loc[j, 'high']
                high_idx = j
                high_time = df_copy.loc[j, 'date']
        
        # Check if we found a significant wave
        if high_idx is not None:
            magnitude = ((high_price - low_price) / low_price) * 100
            
            if magnitude >= min_wave_pct:
                wave_data = analyze_wave_retracement(
                    low_idx, high_idx, low_price, high_price, 
                    low_time, high_time, df_copy
                )
                if wave_data:
                    waves.append(wave_data)
    
    # Remove duplicate waves (same low or high idx)
    unique_waves = []
    seen_indices = set()
    
    for wave in waves:
        key = (wave['low_idx'], wave['high_idx'])
        if key not in seen_indices:
            seen_indices.add(key)
            unique_waves.append(wave)
    
    return unique_waves


def analyze_wave_retracement(low_idx, high_idx, low_price, high_price, low_time, high_time, df):
    """Analyze a single wave's retracement"""
    
    # Calculate wave magnitude
    magnitude = ((high_price - low_price) / low_price) * 100
    
    # Filter out unrealistic data (likely bad price data)
    if magnitude > 100000 or low_price < 0.000000001:  # More than 1000x or extremely small prices
        return None
    
    # Find deepest retracement after the high
    data_after_high = df[df.index > high_idx]
    if data_after_high.empty:
        return None
    
    lowest_after_high = data_after_high['low'].min()
    
    # Calculate Fibonacci retracement level correctly:
    # When price is at the LOW (start) = 0% Fib level
    # When price is at the HIGH (top) = 100% Fib level
    # If price retraces to 38.2% Fib level = it's at 38.2% from low to high
    # Which means it has retraced 61.8% from the high (100% - 38.2%)
    
    wave_range = high_price - low_price
    current_level_from_low = lowest_after_high - low_price
    fib_level = (current_level_from_low / wave_range) * 100  # This is the Fib level (e.g., 38.2%)
    retracement_from_high = 100 - fib_level  # This is how much it retraced (e.g., 61.8%)
    
    # Validate within reasonable bounds
    if fib_level < -10 or fib_level > 110:  # Allow slight overshoot
        return None
    
    return {
        'low_idx': low_idx,
        'high_idx': high_idx,
        'low_price': low_price,
        'high_price': high_price,
        'lowest_after_high': lowest_after_high,
        'magnitude': magnitude,
        'fib_level': fib_level,  # Where price is (e.g., 38.2% = at the 38.2% Fib level)
        'retracement_pct': retracement_from_high,  # How much it retraced (e.g., 61.8%)
        'low_time': low_time,
        'high_time': high_time,
    }


def main():
    # Load configuration
    config = Configuration.from_files(['user_data/config.json'])
    config['exchange']['name'] = 'solanadex'
    config['stake_currency'] = 'SOL'  # Override to SOL for Solana meme coins
    config['trading_mode'] = 'spot'  # Solana DEX only supports spot trading
    
    # Disable orderbook pricing as it's not available on DEX
    if 'exit_pricing' in config:
        config['exit_pricing']['use_order_book'] = False
        config['exit_pricing']['price_side'] = 'same'
    if 'entry_pricing' in config:
        config['entry_pricing']['use_order_book'] = False
        config['entry_pricing']['price_side'] = 'same'
    
    # Initialize exchange directly
    exchange = SolanaDex(config)
    
    # Get list of pairs
    pairs = exchange.get_markets(quote_currencies=['SOL'], active_only=True)
    pair_list = list(pairs.keys())  # Analyze all available pairs
    
    logger.info(f"Analyzing {len(pair_list)} Solana meme coin pairs...")
    
    # Analyze each pair
    results = []
    timeframe = '1h'  # Use 1h candles for more historical data availability
    since = int((datetime.now(UTC) - timedelta(days=30)).timestamp() * 1000)  # Last 30 days for more data
    
    for pair in pair_list:
        try:
            logger.info(f"Processing {pair}...")
            
            # Use cached data if available to save API credits
            df = get_cached_ohlcv(pair, timeframe, since, exchange, config)
            
            if df.empty or len(df) < 10:
                logger.warning(f"Insufficient data for {pair}")
                continue
            
            # Detect ALL waves in this coin's history (20%+ pumps)
            waves = detect_all_waves(df, min_wave_pct=20.0)
            
            if waves:
                logger.info(f"  Found {len(waves)} waves")
                for wave in waves:
                    results.append({
                        'pair': pair,
                        'magnitude': wave['magnitude'],
                        'fib_level': wave['fib_level'],
                        'retracement_pct': wave['retracement_pct'],
                        'low_price': wave['low_price'],
                        'high_price': wave['high_price'],
                        'lowest_after_high': wave['lowest_after_high'],
                        'low_time': wave['low_time'],
                        'high_time': wave['high_time'],
                    })
            else:
                logger.info(f"  No significant waves detected")
        
        except Exception as e:
            logger.error(f"Error analyzing {pair}: {e}")
            continue
    
    # Calculate statistics
    if results:
        df_results = pd.DataFrame(results)
        
        # Generate both graphs
        plot_buy_zones_analysis(df_results)
        plot_retracement_distribution(df_results)
        
        print("\n" + "="*80)
        print("FIBONACCI RETRACEMENT ANALYSIS - SOLANA MEME COINS")
        print("="*80)
        print(f"\nFound {len(results)} waves with 20%+ magnitude")
        print(f"Timeframe: {timeframe}")
        print(f"Period: Last 30 days")
        print(f"Coins analyzed: {len(pair_list)}")
        
        print(f"\n{'Pair':<20} {'Magnitude':<12} {'Fib Level':<15} {'Meaning':<20}")
        print("-" * 80)
        
        for _, row in df_results.iterrows():
            # Determine meaning based on Fib level
            fib = row['fib_level']
            if fib < 23.6:
                meaning = "Very Cheap/Deep"
            elif fib < 38.2:
                meaning = "Cheap"
            elif fib < 50.0:
                meaning = "Below Fair Value"
            elif fib < 61.8:
                meaning = "Above Fair Value"
            elif fib < 78.6:
                meaning = "Getting Expensive"
            else:
                meaning = "Near High"
            
            print(f"{row['pair']:<20} {row['magnitude']:>10.1f}% {fib:>13.1f}% {meaning:<20}")
        
        print("\n" + "="*80)
        print("SUMMARY STATISTICS")
        print("="*80)
        print(f"Average wave magnitude:        {df_results['magnitude'].mean():>6.1f}%")
        print(f"Median wave magnitude:         {df_results['magnitude'].median():>6.1f}%")
        print(f"\nAverage Fib Level:             {df_results['fib_level'].mean():>6.1f}%")
        print(f"Median Fib Level:              {df_results['fib_level'].median():>6.1f}%")
        print(f"Min Fib Level:                 {df_results['fib_level'].min():>6.1f}%")
        print(f"Max Fib Level:                 {df_results['fib_level'].max():>6.1f}%")
        print(f"Std deviation:                 {df_results['fib_level'].std():>6.1f}%")
        print(f"\n(Remember: <50% = Below Fair Value = Cheap, >50% = Above Fair Value = Expensive)")
        
        # Fibonacci level buckets
        print("\n" + "-"*80)
        print("FIBONACCI LEVEL DISTRIBUTION")
        print("-"*80)
        
        fib_buckets = {
            '0-23.6%': (0, 23.6),
            '23.6-38.2%': (23.6, 38.2),
            '38.2-50%': (38.2, 50.0),
            '50-61.8%': (50.0, 61.8),
            '61.8-78.6%': (61.8, 78.6),
            '78.6-100%': (78.6, 100.0),
            '>100%': (100.0, float('inf'))
        }
        
        for bucket_name, (low, high) in fib_buckets.items():
            count = len(df_results[(df_results['fib_level'] >= low) & (df_results['fib_level'] < high)])
            pct = (count / len(df_results)) * 100 if len(df_results) > 0 else 0
            bar = '#' * int(pct / 2)  # Use # instead of Unicode block for Windows compatibility
            print(f"{bucket_name:<15} {count:>3} coins ({pct:>5.1f}%) {bar}")
        
        print("="*80)
        
    else:
        print("\nNo significant waves detected in the analyzed coins.")


if __name__ == "__main__":
    main()

