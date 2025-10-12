# Experiment 4: Momentum Confirmation Filters

## Baseline Performance
- **Strategy:** ADX_OBV_PairOptimized
- **Current Indicators:** ADX, DI+/DI-, OBV, ATR
- **Baseline Return:** 314.60% (3,146 USDT profit)
- **Win Rate:** 50.0% (could be improved with better signal quality)

## Hypothesis
Current strategy relies on ADX/DI and OBV. Adding momentum confirmation could:
1. **Filter out false signals** during sideways markets
2. **Improve win rate** by confirming trend strength
3. **Reduce whipsaw trades** in choppy conditions
4. **Enhance signal quality** over quantity

## Parameters to Add
### RSI Confirmation
- **rsi_period:** 14-21 (RSI calculation period)
- **rsi_long_min:** 30-50 (minimum RSI for long entries)
- **rsi_long_max:** 70-85 (maximum RSI for long entries)
- **rsi_short_min:** 15-30 (minimum RSI for short entries)  
- **rsi_short_max:** 50-70 (maximum RSI for short entries)

### MACD Confirmation
- **macd_fast:** 12-15 (fast EMA period)
- **macd_slow:** 24-30 (slow EMA period)
- **macd_signal:** 8-12 (signal line period)
- **macd_confirmation:** Boolean (require MACD alignment)

## Implementation Details
```python
# New indicators
dataframe['rsi'] = ta.RSI(dataframe, timeperiod=rsi_period)
macd = ta.MACD(dataframe, fastperiod=macd_fast, slowperiod=macd_slow, signalperiod=macd_signal)
dataframe['macd'] = macd['macd']
dataframe['macd_signal'] = macd['macdsignal']
dataframe['macd_histogram'] = macd['macdhist']

# Enhanced entry conditions
long_momentum = (
    (dataframe['rsi'] >= rsi_long_min) & 
    (dataframe['rsi'] <= rsi_long_max) &
    (dataframe['macd'] > dataframe['macd_signal']) if macd_confirmation else True
)

short_momentum = (
    (dataframe['rsi'] >= rsi_short_min) & 
    (dataframe['rsi'] <= rsi_short_max) &
    (dataframe['macd'] < dataframe['macd_signal']) if macd_confirmation else True
)
```

## Expected Outcomes
- **Higher Win Rate:** Target 55-60% (vs current 50%)
- **Fewer Trades:** Expect 200-250 trades (vs current 288)
- **Better Trade Quality:** Higher average profit per trade
- **Improved Risk Metrics:** Better Sharpe and Sortino ratios

## Implementation Plan
1. Add RSI and MACD indicators to populate_indicators()
2. Create momentum confirmation functions
3. Integrate momentum filters into entry conditions
4. Add hyperopt parameters for all momentum settings
5. Run optimization focusing on win rate improvement
6. Analyze trade quality improvements

## Key Metrics to Monitor
- **Win Rate:** Primary target for improvement
- **Average Profit per Trade:** Should increase
- **Total Return:** Must exceed 314.60% baseline
- **Trade Frequency:** Acceptable reduction for quality
- **False Signal Reduction:** Compare signal-to-noise ratio

## Risk Considerations
- **Over-filtering:** May miss good opportunities
- **Parameter Sensitivity:** Multiple parameters increase complexity
- **Market Adaptation:** Momentum indicators may lag in fast markets
- **Correlation Risk:** RSI/MACD may be correlated with existing signals

## Success Criteria
- **Primary:** Beat 314.60% baseline return
- **Secondary:** Improve win rate to >55%
- **Tertiary:** Reduce total trades while maintaining profitability
