# Experiment 1: Leverage & Stop Loss Optimization

## Baseline Performance

- **Strategy:** ADX_OBV_PairOptimized
- **Current Leverage:** 1x across all pairs
- **Current Stop Loss:** -25% (fixed)
- **Baseline Return:** 314.60% (3,146 USDT profit)
- **Win Rate:** 50.0% (144/288 trades)
- **Profit Factor:** 1.78
- **Max Drawdown:** 10.72%
- **Sharpe Ratio:** 3.12

## Hypothesis

Current strategy uses 1x leverage and -25% fixed stop loss across all pairs. By optimizing both parameters, we can potentially:

1. **Amplify returns** on high-confidence signals through optimal leverage
2. **Improve risk management** through dynamic stop loss levels
3. **Balance risk-reward** by finding optimal leverage/stop loss combinations
4. **Reduce drawdowns** with tighter stop losses on higher leverage trades

## Parameters to Test

### Leverage Level

- **leverage_level:** Currently fixed at 1 for all pairs
- **Test Range:** 1-5 (integer values)
- **Type:** IntParameter

### Stop Loss

- **stoploss_param:** Currently fixed at -25% for all pairs
- **Test Range:** -35% to -10% (decimal values)
- **Type:** DecimalParameter
- **Rationale:** Tighter stops (-10% to -15%) for higher leverage, wider stops (-25% to -35%) for lower leverage

### Optimization Settings

- **Method:** Hyperopt with 100+ epochs
- **Metric:** Total return with max drawdown constraint (<15%)
- **Spaces:** 'buy' (leverage) and 'sell' (stoploss)

## Expected Outcomes

### Leverage-Stop Loss Combinations

- **Conservative (1-2x leverage, -20% to -35% stop):** 400-500% returns, lower drawdown
- **Moderate (2-3x leverage, -15% to -25% stop):** 600-800% returns, balanced risk
- **Aggressive (3-5x leverage, -10% to -20% stop):** 800%+ returns, higher drawdown risk

### Stop Loss Impact

- **Tighter stops (-10% to -15%):** Higher win rate, lower profit per trade, reduced drawdown
- **Wider stops (-25% to -35%):** Lower win rate, higher profit per trade, increased drawdown
- **Optimal balance:** Expected around -18% to -22% stop loss range

## Implementation Plan

1. ✅ Add leverage_level as hyperopt parameter in strategy
2. ✅ Add stoploss_param as hyperopt parameter with property override
3. Set constraints: max_drawdown < 15%, min_trades > 200
4. Run hyperopt for 100+ epochs optimizing both parameters
5. Analyze correlation between leverage and optimal stop loss levels
6. Compare risk-adjusted metrics (Sharpe, Sortino, Calmar)
7. Document optimal parameter combinations by market conditions

## Risk Considerations

### Leverage Risks

- **Increased drawdown risk** with higher leverage
- **Margin requirements** and liquidation risk  
- **Pair-specific leverage** may be needed (volatile pairs = lower leverage)
- **Market regime sensitivity** (bull vs bear markets)

### Stop Loss Risks

- **Premature exits** with overly tight stops (-10% to -12%)
- **Excessive losses** with overly wide stops (-30% to -35%)
- **Whipsaw effect** in volatile markets with tight stops
- **Parameter overfitting** risk with too many combinations

### Combined Risks

- **High leverage + tight stops:** Frequent small losses
- **High leverage + wide stops:** Rare but catastrophic losses
- **Correlation risk:** Both parameters may optimize for same market period

## Success Criteria

- **Primary:** Beat 314.60% baseline return
- **Secondary:** Maintain drawdown < 15%
- **Tertiary:** Improve Sharpe ratio > 3.12

## Hyperopt Command

```bash
freqtrade hyperopt \
    --strategy ADX_OBV_PairOptimized \
    --timeframe 1h \
    --timerange 20240401-20250401 \
    --hyperopt-loss SharpeHyperOptLoss \
    --spaces buy sell \
    --epochs 150 \
    --config user_data/binance_futures_ADX_OBV_PairOptimized.json \
    --max-open-trades 3 \
    --timeframe-detail 5m \
    --cache none \
    --print-all
```

## Analysis Framework

### Parameter Correlation Analysis

- Plot leverage vs stop loss for top 20 epochs
- Identify optimal combinations by return/drawdown ratio
- Analyze parameter stability across different market periods

### Performance Metrics Comparison

| Metric | Baseline | Target | Best Result |
|--------|----------|---------|-------------|
| Total Return | 314.60% | >314.60% | TBD |
| Win Rate | 50.0% | >45.0% | TBD |
| Profit Factor | 1.78 | >1.78 | TBD |
| Max Drawdown | 10.72% | <15.0% | TBD |
| Sharpe Ratio | 3.12 | >3.12 | TBD |
| Leverage | 1x | 1-5x | TBD |
| Stop Loss | -25% | -35% to -10% | TBD |
