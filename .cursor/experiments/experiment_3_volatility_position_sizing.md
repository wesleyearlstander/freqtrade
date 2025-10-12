# Experiment 3: Volatility-Based Position Sizing

## Baseline Performance

- **Strategy:** ADX_OBV_PairOptimized
- **Current Position Sizing:** Fixed stake amount (666.67 USDT avg)
- **Baseline Return:** 314.60% (3,146 USDT profit)
- **Current ATR Usage:** Only for TP/SL calculation (atr_mult: 2.0-2.5)

## Hypothesis

Current strategy uses fixed position sizing. Volatility-based position sizing could:

1. **Reduce risk** during high volatility periods
2. **Increase position size** during low volatility/high confidence setups
3. **Improve risk-adjusted returns** through dynamic capital allocation
4. **Better drawdown management** by reducing exposure in volatile conditions

## Parameter to Add

- **volatility_position_multiplier:** New parameter for position sizing
- **Test Range:** 0.5 - 2.0 (decimal values)
- **Formula:** `position_size = base_stake * (avg_atr / current_atr) * volatility_position_multiplier`
- **ATR Lookback:** 14-period ATR for volatility measurement

## Implementation Details

```python
# New parameters to add
volatility_lookback = IntParameter(7, 21, default=14, space='buy')
volatility_position_multiplier = DecimalParameter(0.5, 2.0, default=1.0, space='buy')

# Position sizing logic
avg_atr = dataframe['atr'].rolling(window=volatility_lookback).mean()
current_atr = dataframe['atr']
volatility_ratio = avg_atr / current_atr
position_multiplier = volatility_ratio * volatility_position_multiplier
```

## Expected Outcomes

- **Low Volatility Periods:** Larger positions (up to 2x normal size)
- **High Volatility Periods:** Smaller positions (down to 0.5x normal size)
- **Overall Effect:** Better risk-adjusted returns, smoother equity curve
- **Target Improvement:** 350-400% returns with lower drawdown

## Implementation Plan

1. Add volatility calculation to populate_indicators()
2. Implement custom position sizing in custom_stake_amount()
3. Add hyperopt parameters for volatility_lookback and multiplier
4. Run hyperopt optimization (100+ epochs)
5. Compare results with baseline fixed position sizing

## Key Metrics to Analyze

- **Sharpe Ratio:** Should improve with better risk management
- **Maximum Drawdown:** Target <10% (vs current 10.72%)
- **Profit Factor:** Maintain >1.78 while reducing risk
- **Win Rate:** Should maintain or improve current 50%
- **Position Size Distribution:** Analyze size variations across trades

## Risk Considerations

- **Over-optimization:** Too aggressive volatility adjustments
- **Market Regime Changes:** Volatility patterns may shift
- **Execution Complexity:** More complex position sizing logic
- **Capital Utilization:** May under-utilize capital in low-vol periods

## Success Criteria

- **Primary:** Beat 314.60% baseline return
- **Secondary:** Reduce maximum drawdown to <10%
- **Tertiary:** Improve Sharpe ratio >3.5
