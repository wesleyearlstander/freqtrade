# Solana Meme Coin Analysis CLI

A comprehensive analysis tool for Solana meme coins, providing wave detection, Fibonacci analysis, and statistical insights.

## Features

- **Data Fetching**: Download OHLCV data from Bitquery and DexScreener APIs
- **Wave Detection**: Multiple algorithms (zigzag, pivots, swing) for identifying price waves
- **Fibonacci Analysis**: Retracement and extension level analysis
- **Statistical Analysis**: Correlations, distributions, and rolling statistics
- **Interactive Visualizations**: Charts, histograms, heatmaps, and scatter plots
- **CLI Interface**: Easy-to-use command-line interface

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export BITQUERY_API_KEY="your_bitquery_api_key"
```

3. Create configuration file:
```bash
python main.py  # This will create a default config file
```

## Usage

### Data Fetching

Fetch data for top 200 coins over 90 days:
```bash
python main.py fetch --top 200 --timeframe 4h --days 90 --source bitquery --fallback dexscreener
```

### Wave Analysis

Analyze waves with 10% threshold using zigzag method:
```bash
python main.py analyze --timeframe 4h --threshold 10 --method zigzag --universe top200
```

### Queries

#### Wave Ranges
Get wave ranges for a specific time period:
```bash
python main.py query wave_ranges --universe top200 --timerange 20240401-20240801
```

#### Fibonacci Distribution
Analyze Fibonacci level distribution:
```bash
python main.py query fib_distribution --level 61.8 --timerange last90d
```

#### Average Bottom Retracement
Calculate average bottom retracement for last 5 pumps:
```bash
python main.py query avg_bottom --last-pumps 5 --universe top50
```

#### Invalidations
Find Fibonacci invalidations after 50% waves:
```bash
python main.py query invalidations --after-pump-threshold 50 --timerange last30d
```

#### Correlations
Analyze correlations between variables:
```bash
python main.py query correlations --x market_cap --y wave_magnitude --bins 5
```

### Visualizations

#### Coin Chart
Visualize specific coin with waves and Fibonacci levels:
```bash
python main.py visualize coin BONK --timeframe 4h --show-waves --show-fib --output bonk_analysis.html
```

#### Fibonacci Histogram
Create histogram of Fibonacci level distributions:
```bash
python main.py visualize fib_histogram --universe top100 --level-grid 23.6,38.2,50,61.8,78.6
```

#### Heatmap
Create heatmap visualization:
```bash
python main.py visualize heatmap --metric fib_hold_time --levels 38.2,50,61.8 --universe top50
```

#### Scatter Plot
Create scatter plot:
```bash
python main.py visualize scatter --x wave_magnitude --y retracement --color volume_delta
```

## Configuration

The tool uses a JSON configuration file (`analysis_config.json`) with the following structure:

```json
{
  "bitquery_api_key": null,
  "dexscreener_base_url": "https://api.dexscreener.com/latest",
  "data_dir": "data",
  "cache_dir": "cache",
  "output_dir": "output",
  "supported_timeframes": ["5m", "15m", "1h", "4h", "1d"],
  "default_timeframe": "4h",
  "max_candles": 10000,
  "wave_detection": {
    "default_threshold": 10.0,
    "min_wave_duration": 1,
    "max_wave_duration": 1000,
    "fibonacci_levels": [0, 23.6, 38.2, 50, 61.8, 78.6, 100, 127.2, 161.8, 200, 261.8]
  },
  "universes": {
    "top50": 50,
    "top100": 100,
    "top200": 200,
    "top500": 500
  },
  "visualization": {
    "default_figure_size": [12, 8],
    "dpi": 100,
    "style": "seaborn-v0_8"
  },
  "rate_limiting": {
    "min_request_interval": 1.0,
    "max_requests_per_minute": 60
  },
  "cache": {
    "ttl": 3600,
    "max_size": 1000
  }
}
```

## Data Sources

### Bitquery (Primary)
- GraphQL API for historical OHLCV data
- Requires API key
- High-quality data with good coverage

### DexScreener (Fallback)
- REST API for token and pair data
- No API key required
- Good coverage of Solana tokens

## Wave Detection Methods

### Zigzag
- Identifies peaks and troughs based on percentage threshold
- Good for trend-following analysis
- Configurable sensitivity

### Pivots
- Uses pivot points to identify reversals
- More conservative than zigzag
- Good for swing trading

### Swing
- Identifies swing highs and lows
- Based on local extrema
- Good for short-term analysis

## Fibonacci Analysis

The tool analyzes Fibonacci retracement and extension levels:

- **Retracement Levels**: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
- **Extension Levels**: 127.2%, 161.8%, 200%, 261.8%

For each level, it calculates:
- Touch rate
- Hold time
- Invalidation rate
- Deepest retracement

## Statistical Analysis

### Basic Statistics
- Mean, median, standard deviation
- Percentiles (25th, 75th, 90th, 95th, 99th)
- Skewness and kurtosis

### Correlations
- Wave magnitude vs market cap
- Duration vs volume
- Drawdown vs volatility

### Distributions
- Magnitude distribution
- Duration distribution
- Drawdown distribution

## Examples

### Example 1: Complete Analysis Pipeline

```bash
# 1. Fetch data
python main.py fetch --top 100 --timeframe 4h --days 60

# 2. Analyze waves
python main.py analyze --timeframe 4h --threshold 15 --method zigzag --universe top100

# 3. Query results
python main.py query wave_ranges --universe top100 --timerange last30d
python main.py query fib_distribution --level 61.8 --timerange last30d

# 4. Visualize
python main.py visualize coin BONK --timeframe 4h --show-waves --show-fib
```

### Example 2: Fibonacci Analysis

```bash
# Analyze Fibonacci levels for top 50 coins
python main.py analyze --universe top50 --threshold 10
python main.py query fib_distribution --level 38.2
python main.py visualize fib_histogram --universe top50 --level-grid 23.6,38.2,50,61.8,78.6
```

### Example 3: Correlation Analysis

```bash
# Analyze correlations between wave properties
python main.py query correlations --x market_cap --y wave_magnitude
python main.py visualize scatter --x wave_magnitude --y retracement --color volume_delta
```

## Troubleshooting

### Common Issues

1. **No data available**: Check API keys and network connectivity
2. **Rate limiting**: Increase `min_request_interval` in config
3. **Memory issues**: Reduce `max_candles` or use smaller universes
4. **Visualization errors**: Check matplotlib/plotly installation

### Debug Mode

Run with verbose logging:
```bash
python main.py -v analyze --timeframe 4h --threshold 10
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.