# Experiment 2: Multi-Timeframe Optimization

## Baseline Performance
- **Strategy:** ADX_OBV_PairOptimized
- **Current Timeframe:** 1h across all pairs
- **Baseline Return:** 314.60% (3,146 USDT profit)
- **Total Trades:** 288 (0.79 per day)
- **Average Duration:** 1 day, 23:45:00

## Hypothesis
Current strategy uses 1h timeframe. Different timeframes may offer:
1. **Higher frequency trading** (30m) for more opportunities
2. **Better trend capture** (2h, 4h) for stronger signals
3. **Reduced noise** with longer timeframes
4. **Improved risk-reward ratios** with different time horizons

## Parameter to Test
- **timeframe:** Currently "1h" for all pairs
- **Test Options:** ["30m", "1h", "2h", "4h"]
- **Optimization Method:** Systematic testing of each timeframe
- **Detail Timeframe:** 5m for all tests (consistent execution)

## Expected Outcomes
- **30m timeframe:** More trades (~400-500), potentially higher returns but more noise
- **2h timeframe:** Fewer trades (~150-200), stronger signals, better win rate
- **4h timeframe:** Very selective trades (~100-150), highest quality signals

## Implementation Plan
1. Test each timeframe systematically with current parameters
2. For each timeframe, run separate backtest with identical conditions
3. Compare trade frequency, win rates, and total returns
4. Analyze optimal timeframe per pair (pair-specific optimization)
5. Consider hybrid approach with multiple timeframes

## Key Metrics to Compare
- **Total Return:** Absolute profit comparison
- **Trade Frequency:** Trades per day
- **Win Rate:** Percentage of profitable trades
- **Average Duration:** Time in market per trade
- **Risk-Adjusted Returns:** Sharpe, Sortino ratios
- **Drawdown Patterns:** Maximum and average drawdowns

## Risk Considerations
- **Lower timeframes:** Increased transaction costs, more noise
- **Higher timeframes:** Fewer opportunities, longer drawdown periods
- **Market regime dependency:** Some timeframes work better in trending vs ranging markets
- **Execution slippage:** Different timeframes have different execution characteristics

## Success Criteria
- **Primary:** Beat 314.60% baseline return
- **Secondary:** Maintain or improve win rate (>50%)
- **Tertiary:** Optimize trade frequency vs quality balance
