# Advanced Position Sizing Framework

The Advanced Position Sizing Framework is an extensible system that allows strategies to dynamically adjust position sizes based on market conditions, signal strength, and risk management principles.

## Overview

Traditional position sizing in Freqtrade uses fixed amounts or simple percentage-based calculations. This framework provides sophisticated algorithms that can:

- **Adjust for Market Volatility**: Reduce position sizes during high volatility periods
- **Optimize Based on Historical Performance**: Use Kelly Criterion for optimal capital allocation
- **Balance Portfolio Risk**: Ensure equal risk contribution across positions
- **Respond to Market Momentum**: Increase position sizes during strong trends
- **Integrate Signal Strength**: Scale positions based on technical indicator confidence

## Quick Start

### 1. Enable Position Sizing in Your Strategy

```python
from freqtrade.strategy import IStrategy
from freqtrade.strategy.mixins import PositionSizingMixin

class MyStrategy(IStrategy, PositionSizingMixin):
    def populate_indicators(self, dataframe, metadata):
        # Initialize position sizing
        self.init_position_sizing()
        
        # Your indicators here
        return dataframe
    
    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake, 
                           min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        return self.calculate_position_size(
            pair=pair,
            current_rate=current_rate,
            proposed_stake=proposed_stake,
            max_stake=max_stake,
            **kwargs
        )
```

### 2. Configure Position Sizing

Add to your `config.json`:

```json
{
  "position_sizing": {
    "method": "volatility_adjusted",
    "max_position_size_pct": 0.1,
    "min_position_size_pct": 0.01,
    "volatility_lookback_periods": 20,
    "volatility_target": 0.02
  }
}
```

## Available Algorithms

### 1. Fixed Ratio (`fixed_ratio`)
Simple position sizing with signal strength adjustment.

**Configuration:**
```json
{
  "method": "fixed_ratio",
  "signal_multiplier": 1.0
}
```

### 2. Volatility Adjusted (`volatility_adjusted`)
Adjusts position size based on market volatility.

**Configuration:**
```json
{
  "method": "volatility_adjusted",
  "volatility_lookback_periods": 20,
  "volatility_target": 0.02,
  "min_volatility_adjustment": 0.2,
  "max_volatility_adjustment": 3.0
}
```

### 3. Kelly Criterion (`kelly_criterion`)
Optimal position sizing based on historical win rate and returns.

**Configuration:**
```json
{
  "method": "kelly_criterion",
  "min_trades_required": 10,
  "max_lookback_trades": 50,
  "kelly_fraction": 0.25
}
```

### 4. Risk Parity (`risk_parity`)
Equal risk contribution across positions.

**Configuration:**
```json
{
  "method": "risk_parity",
  "volatility_lookback_periods": 20,
  "target_risk_per_trade": 0.02
}
```

### 5. Momentum Based (`momentum_based`)
Adjusts based on price momentum and trend strength.

**Configuration:**
```json
{
  "method": "momentum_based",
  "momentum_lookback_periods": 10,
  "trend_lookback_periods": 20,
  "min_momentum_multiplier": 0.5,
  "max_momentum_multiplier": 2.0
}
```

## Advanced Usage

### Custom Signal Strength

Override the signal strength calculation for your specific strategy:

```python
def _analyze_indicators_for_strength(self, latest_data) -> float:
    strength = 1.0
    
    # RSI based adjustment
    if hasattr(latest_data, 'rsi'):
        rsi = latest_data.rsi
        if rsi < 30:
            strength *= 1.3  # Oversold - stronger signal
        elif rsi > 70:
            strength *= 0.7  # Overbought - weaker signal
    
    # Volume confirmation
    if hasattr(latest_data, 'volume') and hasattr(latest_data, 'volume_sma'):
        volume_ratio = latest_data.volume / latest_data.volume_sma
        if volume_ratio > 1.5:
            strength *= 1.2  # High volume confirmation
    
    return np.clip(strength, 0.1, 2.0)
```

### Dynamic Method Switching

```python
def populate_indicators(self, dataframe, metadata):
    self.init_position_sizing()
    
    # Switch methods based on market conditions
    volatility = dataframe['atr'].iloc[-1] / dataframe['close'].iloc[-1]
    
    if volatility > 0.03:  # High volatility
        self.set_position_sizing_method('risk_parity')
    else:  # Normal volatility
        self.set_position_sizing_method('kelly_criterion')
```

### Custom Position Sizing Algorithm

Create your own position sizing algorithm:

```python
from freqtrade.plugins.position_sizing.iposition_sizing import IPositionSizing

class CustomSizing(IPositionSizing):
    def calculate(self, pair, current_rate, proposed_stake, max_stake, 
                 signal_strength, dataframe=None, **kwargs):
        # Your custom logic here
        adjusted_stake = proposed_stake * signal_strength
        return self._apply_constraints(adjusted_stake, max_stake)
    
    @staticmethod
    def parameter_space():
        return {
            'custom_param': {
                'type': 'real',
                'low': 0.1,
                'high': 2.0,
                'default': 1.0,
                'space': 'uniform',
                'optimize': True
            }
        }
    
    @staticmethod
    def description():
        return "My custom position sizing algorithm"

# Use in strategy
def populate_indicators(self, dataframe, metadata):
    self.init_position_sizing()
    custom_sizer = CustomSizing(self.config, self.dp, self.config.get('position_sizing', {}))
    self.add_custom_sizing_method('custom', custom_sizer)
    self.set_position_sizing_method('custom')
```

## Hyperopt Integration

Position sizing parameters can be optimized using Hyperopt:

```python
from freqtrade.strategy import DecimalParameter

class OptimizedStrategy(IStrategy, PositionSizingMixin):
    # Optimize position sizing method
    pos_sizing_method = DecimalParameter(0, 4, default=1, decimals=0, space="buy")
    
    # Optimize volatility target
    volatility_target = DecimalParameter(0.01, 0.05, default=0.02, space="buy")
    
    def populate_indicators(self, dataframe, metadata):
        self.init_position_sizing()
        
        # Update config based on hyperopt parameters
        sizing_config = self.config.get('position_sizing', {})
        sizing_config['volatility_target'] = self.volatility_target.value
        
        # Set method based on hyperopt
        methods = ['fixed_ratio', 'volatility_adjusted', 'kelly_criterion', 'risk_parity', 'momentum_based']
        method = methods[int(self.pos_sizing_method.value)]
        self.set_position_sizing_method(method)
```

## Risk Management

The framework includes built-in risk management:

- **Maximum Position Size**: Never exceed configured percentage of available capital
- **Minimum Position Size**: Ensure positions meet exchange minimums
- **Constraint Validation**: Automatic bounds checking on all calculations
- **Error Handling**: Graceful fallback to proposed stake on calculation errors

## Performance Considerations

- **Caching**: Indicator calculations are cached when possible
- **Efficient Calculations**: Algorithms use vectorized operations where applicable
- **Memory Management**: Only necessary data is retained for calculations
- **Lazy Loading**: Position sizing algorithms are loaded on-demand

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **Configuration Errors**: Validate position sizing configuration
3. **Data Issues**: Check that dataframes contain required columns
4. **Performance Issues**: Consider reducing lookback periods for faster execution

### Debug Information

Enable debug logging for detailed position sizing information:

```json
{
  "logging": {
    "level": "DEBUG",
    "formatters": {
      "default": {
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
      }
    }
  }
}
```

## Examples

See `freqtrade/templates/strategies/PositionSizingExampleStrategy.py` for a complete example strategy that demonstrates all features of the position sizing framework.

## Architecture

The position sizing framework follows Freqtrade's plugin architecture:

- **IPositionSizing**: Abstract base class for all position sizing algorithms
- **PositionSizingManager**: Coordinates multiple algorithms and provides unified interface
- **PositionSizingMixin**: Strategy mixin for easy integration
- **PositionSizingResolver**: Dynamic loading of position sizing algorithms
- **Built-in Algorithms**: Five sophisticated algorithms ready to use

This extensible design allows users to easily add custom position sizing methods while maintaining compatibility with existing Freqtrade features.