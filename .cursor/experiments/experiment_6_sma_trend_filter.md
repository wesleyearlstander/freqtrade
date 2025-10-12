# Experiment 6: 200 SMA Trend Filter Enhancement

## Baseline Performance

- **Strategy:** ADX_OBV_PairOptimized
- **Current Trend Filter:** None (enters long/short regardless of overall trend)
- **Baseline Return:** 314.60% (3,146 USDT profit)
- **Win Rate:** 50.0% (144/288 trades)
- **Profit Factor:** 1.78
- **Max Drawdown:** 10.72%
- **Sharpe Ratio:** 3.12

## Hypothesis

Current strategy enters both long and short positions based solely on ADX/DI crossovers and OBV signals, without considering the overall market trend. By adding a 200 SMA trend filter, we can potentially:

1. **Improve win rate** by aligning trades with the dominant trend
2. **Reduce whipsaws** in sideways/choppy markets
3. **Enhance risk-adjusted returns** by avoiding counter-trend trades
4. **Maintain or improve** overall profitability while reducing drawdowns

## Parameter to Test

- **sma_trend_filter:** Boolean parameter to enable/disable 200 SMA trend filter
- **Test Values:** True/False
- **Logic:**
  - **Long entries:** Only when price > 200 SMA (uptrend)
  - **Short entries:** Only when price < 200 SMA (downtrend)
- **Optimization Method:** Hyperopt with 100+ epochs
- **Metric:** Total return with win rate and drawdown considerations

## Expected Outcomes

- **With Filter (True):**
  - Higher win rate (55-65%)
  - Potentially lower total return but better risk-adjusted returns
  - Reduced drawdown (8-12%)
  - Fewer but higher quality trades
- **Without Filter (False):**
  - Current baseline performance
  - More trades but potentially more whipsaws

## Implementation Plan

1. Add sma_trend_filter as hyperopt BooleanParameter in strategy
2. Calculate 200 SMA in populate_indicators()
3. Modify entry conditions to include trend filter logic
4. Run hyperopt to test both scenarios (True/False)
5. Analyze trade distribution and performance metrics
6. Compare risk-adjusted metrics (Sharpe, Sortino, Calmar)

## Technical Implementation

```python
# Add to hyperopt parameters
sma_trend_filter = BooleanParameter(default=False, space='buy', optimize=True, load=True)

# Add to populate_indicators
dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)

# Modify entry conditions
# Long entries: existing conditions + (not sma_trend_filter OR close > sma_200)
# Short entries: existing conditions + (not sma_trend_filter OR close < sma_200)
```

## Risk Considerations

- **Reduced trade frequency** may impact overall returns
- **Trend filter lag** - 200 SMA is a lagging indicator
- **Sideways markets** - may miss profitable opportunities
- **Market regime dependency** - effectiveness varies by market conditions
- **Parameter optimization** - risk of overfitting to historical data

## Success Criteria

- **Primary:** Improve win rate > 55% while maintaining return > 280%
- **Secondary:** Reduce max drawdown < 10%
- **Tertiary:** Improve Sharpe ratio > 3.2
- **Quaternary:** Better risk-adjusted returns (higher Calmar ratio)

## Analysis Framework

1. **Trade Quality Metrics:**
   - Win rate comparison (with/without filter)
   - Average win/loss ratio
   - Trade duration analysis

2. **Risk Metrics:**
   - Maximum drawdown
   - Sharpe ratio
   - Sortino ratio
   - Calmar ratio

3. **Market Regime Analysis:**
   - Performance in trending vs sideways markets
   - Bull vs bear market effectiveness
   - Volatility impact assessment

## Optimization Results

### Individual Pair Optimization (30 epochs each)

**SOL/USDT:USDT** (Best: Epoch 13/30)

- **sma_period**: 124 (vs 200 baseline)
- **sma_trend_filter**: False (trend filter disabled performs better)
- **Performance**: 73 trades, 58.9% win rate, 237.38% total profit
- **Other optimized params**: adx_threshold=30, di_cross_window=15, obv_ma_period=100, risk_ratio=1.5

**DOT/USDT:USDT** (Best: Epoch 20/30)  

- **sma_period**: 58 (much lower than 200!)
- **sma_trend_filter**: True (trend filter enabled is beneficial)
- **Performance**: 74 trades, 47.3% win rate, 246.53% total profit
- **Other optimized params**: atr_mult=2, obv_ma_period=120, risk_ratio=2.5

**XRP/USDT:USDT** (Best: Epoch 23/30)

- **sma_period**: 53 (very low SMA period)
- **sma_trend_filter**: True (trend filter enabled)
- **Performance**: 87 trades, 54.0% win rate, 123.93% total profit
- **Other optimized params**: adx_threshold=30, di_cross_window=20, obv_ma_period=120

## Key Findings

1. **SMA Period Varies Dramatically by Pair:**
   - SOL: 124 (medium-term trend)
   - DOT: 58 (short-term trend)
   - XRP: 53 (short-term trend)
   - **200 SMA was suboptimal for all pairs!**

2. **Trend Filter Effectiveness is Pair-Specific:**
   - SOL: Better without trend filter (False)
   - DOT: Better with trend filter (True)
   - XRP: Better with trend filter (True)

3. **Performance Impact:**
   - Each pair required different SMA periods for optimal performance
   - Generic 200 SMA approach was significantly underperforming
   - Pair-specific optimization yielded substantial improvements

## Backtest Results (Apr 2024 - Apr 2025)

### Optimized Strategy Performance

- **Total Profit**: 1,206.75 USDT (120.68% return)
- **Total Trades**: 279 trades
- **Win Rate**: 44.1% (123 wins, 156 losses)
- **Profit Factor**: 1.31
- **Sharpe Ratio**: 1.57
- **Max Drawdown**: 18.92% (479.85 USDT)
- **CAGR**: 120.68%

### Pair Performance Breakdown

- **SOL/USDT**: 98 trades, 48.0% win rate, +68.62% profit
- **DOT/USDT**: 97 trades, 43.3% win rate, +52.36% profit  
- **XRP/USDT**: 84 trades, 40.5% win rate, -0.30% profit

### Exit Reason Analysis

- **Take Profit**: 121 trades (100% win rate, +502.91% total)
- **Stop Loss**: 156 trades (0% win rate, -387.94% total)
- **Force Exit**: 2 trades (open positions, +5.7% total)

## Conclusion - EXPERIMENT FAILED ❌

**The SMA trend filter experiment FAILED to improve performance and has been reverted.**

### Key Findings:

1. **Significant Performance Degradation**: 
   - **Baseline**: 314.60% return (3,146 USDT profit), 50.0% win rate, 1.78 profit factor
   - **With SMA Filter**: 120.68% return (1,206 USDT profit), 44.1% win rate, 1.31 profit factor
   - **Loss**: -194% performance decrease

2. **SMA Trend Filter is Counterproductive**: 
   - The trend filter removed profitable trades rather than improving trade quality
   - Even with individual pair optimization, performance remained significantly worse
   - The ADX+OBV strategy works better without additional trend confirmation

3. **Lessons Learned**:
   - Not all technical indicators improve strategy performance
   - Adding complexity doesn't always yield better results
   - The original ADX+OBV combination is already well-optimized for trend detection

### Actions Taken:
- ✅ Removed all SMA trend filter code from both ADX_OBV and ADX_OBV_PairOptimized strategies
- ✅ Reverted ADX_OBV_PairOptimized_settings.json to original parameters
- ✅ Restored original strategy performance

**Recommendation**: Continue with the original ADX+OBV strategy without SMA trend filtering. Focus future experiments on other enhancement approaches that don't interfere with the core signal generation.
