# Experiment 7: 4-Year Parameter Optimization with 6-Month Validation

## Objective

Optimize ADX_OBV strategy parameters using 4 years of historical data (2021-2025) and validate performance on the last 6 months as an out-of-sample test to ensure robust parameter selection and avoid overfitting.

## Baseline Performance

- **Strategy:** ADX_OBV (Original without leverage optimization)
- **Baseline Return:** 314.60% (3,146 USDT profit)
- **Baseline Win Rate:** 50.0% (144/288 trades)

## Methodology

### Training Period: 4 Years (2021-01-01 to 2025-01-01)

- **Purpose:** Find robust parameters across multiple market cycles
- **Benefits:**
  - Captures bull markets, bear markets, and sideways periods
  - Reduces overfitting to specific market conditions
  - More statistically significant sample size
  - Better parameter stability

### Validation Period: 6 Months (2024-10-01 to 2025-04-01)

- **Purpose:** Out-of-sample performance validation
- **Benefits:**
  - Tests parameter robustness on unseen data
  - Validates strategy performance in recent market conditions
  - Prevents data snooping bias

## Parameters to Optimize

### Core Strategy Parameters

- **leverage_level:** 1-10 (expanded from 1-5)
- **stoploss_param:** -0.50 to -0.05 (expanded from -0.35 to -0.10)
- **adx_threshold:** 20, 25, 30, 35, 40
- **atr_mult:** 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0
- **di_cross_window:** 5, 10, 15, 20, 25, 30
- **obv_ma_period:** 60, 80, 100, 120, 140
- **risk_ratio:** 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0

### Optimization Settings

- **Method:** Hyperopt with 200+ epochs per pair
- **Loss Function:** SharpeHyperOptLoss for risk-adjusted returns
- **Spaces:** 'buy' and 'sell'
- **Constraints:**
  - Min trades > 100 (over 4 years)
  - Max drawdown < 25%
  - Profit factor > 1.1

## Expected Benefits of 4-Year Optimization

### Market Cycle Coverage

- **2021:** Bull market recovery
- **2022:** Bear market crash
- **2023:** Recovery and consolidation
- **2024:** Mixed conditions
- **2025:** Current conditions

### Statistical Robustness

- **Sample Size:** ~1,460 days vs 365 days (4x larger)
- **Trade Count:** Expected 800-1,200+ trades per pair
- **Market Conditions:** Multiple cycles for better generalization

## Implementation Plan

### Phase 1: Data Preparation

1. ✅ Ensure 4-year data availability for all pairs
2. Download missing data if needed
3. Verify data quality and completeness

### Phase 2: Individual Pair Optimization (4-Year Training)

1. SOL/USDT:USDT hyperopt (2021-2025)
2. DOT/USDT:USDT hyperopt (2021-2025)
3. XRP/USDT:USDT hyperopt (2021-2025)

### Phase 3: Parameter Selection

1. Select best parameters from each pair optimization
2. Update ADX_OBV_PairOptimized_settings.json
3. Document parameter changes and rationale

### Phase 4: Validation Testing (6-Month Out-of-Sample)

1. Backtest with optimized parameters on 2024-10-01 to 2025-04-01
2. Compare against baseline performance
3. Analyze parameter stability and robustness

### Phase 5: Final Comparison (Full Year Test)

1. Backtest with 4-year optimized parameters on 2024-04-01 to 2025-04-01
2. Compare directly against baseline 314.60% return (original without leverage)
3. Document performance improvement and parameter effectiveness vs both baseline and current optimized version

## Success Criteria

### Training Performance (4-Year Period)

- **Primary:** Consistent profitability across all 4 years
- **Secondary:** Sharpe ratio > 1.0
- **Tertiary:** Max drawdown < 25%

### Validation Performance (6-Month Period)

- **Primary:** Beat previous 120.814% annualized return
- **Secondary:** Maintain win rate > 40%
- **Tertiary:** Demonstrate parameter stability

## Risk Considerations

### Overfitting Risks

- **Mitigation:** Use out-of-sample validation period
- **Monitor:** Parameter stability across different periods
- **Validate:** Performance consistency in validation period

### Market Regime Changes

- **Consider:** Recent market structure changes
- **Account for:** Volatility regime shifts
- **Validate:** Parameter robustness across conditions

## Hyperopt Commands

### SOL/USDT:USDT Optimization

```bash
freqtrade hyperopt \
    --strategy ADX_OBV \
    --timeframe 1h \
    --timerange 20210101-20250101 \
    --hyperopt-loss SharpeHyperOptLoss \
    --spaces buy sell \
    --epochs 200 \
    --config user_data/binance_futures_ADX_OBV.json \
    --max-open-trades 1 \
    --timeframe-detail 5m \
    --cache none \
    -p SOL/USDT:USDT \
    --random-state 42
```

### Validation Backtest (6-Month Out-of-Sample)

```bash
freqtrade backtesting \
    --strategy ADX_OBV_PairOptimized \
    --timeframe 1h \
    --timerange 20241001-20250401 \
    --config user_data/binance_futures_ADX_OBV_PairOptimized.json \
    --max-open-trades 3 \
    --timeframe-detail 5m \
    --cache none
```

### Final Comparison Backtest (Full Year)

```bash
freqtrade backtesting \
    --strategy ADX_OBV_PairOptimized \
    --timeframe 1h \
    --timerange 20240401-20250401 \
    --config user_data/binance_futures_ADX_OBV_PairOptimized.json \
    --max-open-trades 3 \
    --timeframe-detail 5m \
    --cache none
```

## Expected Results

### Improved Parameter Robustness

- More stable parameters across market cycles
- Better risk-adjusted returns
- Reduced overfitting to specific periods

### Enhanced Performance Metrics

- **Target Return:** 400%+ annualized (vs 314.60% baseline, 120.814% current)
- **Target Sharpe:** 2.0+ (improved risk-adjusted returns)
- **Target Win Rate:** 50%+ (match or beat baseline 50.0%)
- **Target Drawdown:** <15% (improved risk management)

### Validation Success

- Consistent performance on out-of-sample data
- Parameter stability across different market conditions
- Robust performance in recent market environment

## Results Documentation

Results will be documented in this file with:

- Optimal parameters for each pair
- Training period performance metrics
- Validation period performance comparison
- Parameter stability analysis
- Recommendations for production use

---

**Status:** In Progress
**Created:** 2025-09-23
**Training Period:** 2021-01-01 to 2025-01-01 (4 years)
**Validation Period:** 2024-10-01 to 2025-04-01 (6 months)
