# Experiment 12: Reinforcement Learning Profitable Strategy

## 🎯 **Objective**

Create a profitable trading strategy using Reinforcement Learning (FreqAI RL in Freqtrade) that can:

- Learn optimal entry/exit timing from market data
- Adapt to changing market conditions
- Achieve consistent profitability over 5+ years
- Outperform traditional indicator-based strategies

## 📊 **Current Baseline Performance**

- **Traditional Strategy (ADX_OBV_Improved)**: -27.56% loss over 5 years
- **Target RL Performance**: +50% to +200% profit over 5 years
- **Risk Target**: Max drawdown < 25%

---

## 🔧 Use Freqtrade FreqAI RL (not a custom Gym from scratch)

- **Framework**: We'll use Freqtrade's built-in FreqAI RL (`ReinforcementLearner`) and override its nested `MyRLEnv.calculate_reward()` for research-grade reward design. No separate custom Gym wrapper is needed.
- **Strategy integration**: The FreqAI-enabled strategy provides raw OHLCV to the RL environment and consumes the agent's actions via the `&-action` column. We must implement:
  - `feature_engineering_standard()` to add `%-raw_open`, `%-raw_high`, `%-raw_low`, `%-raw_close`.
  - `set_freqai_targets()` to initialize a neutral `&-action` column (0).
  - `populate_entry_trend()` / `populate_exit_trend()` to map actions to entries/exits.
- **Config-first**: RL choices (algorithm, net arch, timesteps, masking, etc.) are set via `freqai.rl_config` and `freqai.model_training_parameters` in the config JSON.

Reference: See built-ins `ReinforcementLearner` and the RL docs. The environment is simplified and separate from full strategy callbacks; reward must encode risk and trading costs clearly.

## 🔬 **Phase 1: Environment Setup & Data Preparation**

### Step 1.1: Install RL Dependencies

```bash
# Recommended: use Freqtrade's installer and enable RL deps (Torch, SB3, Gymnasium)
./setup.sh -i    # Answer yes to freqai-rl when prompted

# Or with pip extras from this repo (inside your venv):
pip install -e .[freqai_rl,hyperopt,jupyter]

# Optional GPU (CUDA) - install the Torch build matching your CUDA
# Example (adjust for your CUDA):
# pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio

# TA-Lib is already pinned; ensure system deps are present if building from source
```

Notes:

- Docker users: use the image variant with RL support (suffix `_freqairl`).
- Confirm versions in `requirements-freqai-rl.txt` (Torch, Gymnasium, Stable-Baselines3, `sb3-contrib`).

### Step 1.2: Wire Strategy + FreqAI RL

Minimal FreqAI strategy requirements:

```python
# In your FreqAI strategy (e.g., user_data/strategies/RLStrategy.py)
def feature_engineering_standard(self, dataframe, **kwargs):
    dataframe["%-raw_close"] = dataframe["close"]
    dataframe["%-raw_open"] = dataframe["open"]
    dataframe["%-raw_high"] = dataframe["high"]
    dataframe["%-raw_low"] = dataframe["low"]
    return dataframe

def set_freqai_targets(self, dataframe, **kwargs):
    dataframe["&-action"] = 0  # neutral action placeholder
    return dataframe

def populate_entry_trend(self, df, metadata):
    df.loc[(df["do_predict"] == 1) & (df["&-action"] == 1), ["enter_long", "enter_tag"]] = (1, "long")
    df.loc[(df["do_predict"] == 1) & (df["&-action"] == 3), ["enter_short", "enter_tag"]] = (1, "short")
    return df

def populate_exit_trend(self, df, metadata):
    df.loc[(df["do_predict"] == 1) & (df["&-action"] == 2), "exit_long"] = 1
    df.loc[(df["do_predict"] == 1) & (df["&-action"] == 4), "exit_short"] = 1
    return df
```

Custom RL model with reward:

```python
# user_data/freqaimodels/MyCoolRLModel.py
from freqtrade.freqai.prediction_models.ReinforcementLearner import ReinforcementLearner
from freqtrade.freqai.RL.Base5ActionRLEnv import Base5ActionRLEnv, Actions, Positions

class MyCoolRLModel(ReinforcementLearner):
    class MyRLEnv(Base5ActionRLEnv):
        def calculate_reward(self, action: int) -> float:
            # Example: risk-adjusted, continuous reward (research-grade placeholder)
            if not self._is_valid(action):
                return -2.0
            pnl = self.get_unrealized_profit()  # per-step pnl in fraction
            dd = self.get_current_drawdown()    # fraction (0..1)
            cost = self.get_step_cost(action)   # fee+slippage estimate
            # Encourage valid entries/exits; discourage idle in position
            trade_open = self._position in (Positions.Long, Positions.Short)
            idle_pen = -0.001 if (trade_open and action == Actions.Neutral.value) else 0.0
            # Reward = pnl - lambda*dd - costs, scaled
            return float((pnl - 3.0*dd - cost) * 100.0 + idle_pen)
```

### Step 1.3: Data Pipeline

- **Time splits**: Use walk-forward via `train_period_days` and `backtest_period_days` to avoid leakage. RL internals disable shuffle to preserve chronology.
- **Download data**:
  - `freqtrade list-exchanges`
  - `freqtrade list-pairs --exchange binance --quote USDT`
  - `freqtrade list-timeframes --exchange binance`
  - Spot example: `freqtrade download-data -c user_data/config_binance_spot.json --timerange 20200101- --t 1h 4h`
  - Futures example: `freqtrade download-data -c user_data/config_binance_futures.json --timerange 20200101- --t 1h 4h`
- **Features**: Use FreqAI feature pipeline (train-only fit) with PCA enabled; add multi-timeframe indicators and optional correlated pairs. Avoid outlier removal methods with RL (they are disabled automatically).
- **Leakage control**: Keep `shuffle: false`; use an embargo buffer via `buffer_train_data_candles` (e.g., 50–200) to cut edges after feature generation; prefer walk-forward with non-overlapping OOS windows; avoid any future-looking features.
- **Permutation robustness (evaluation)**: Run circular block bootstrap/permutation tests on OOS predictions to estimate PBO/SPA; do not permute during training.

---

## 🧠 **Phase 2: RL Algorithm Selection & Implementation**

### Step 2.1: Algorithm Comparison

Test SB3/SB3-Contrib algorithms supported by FreqAI RL:

1. **PPO** (default baseline)
2. **A2C**
3. **DQN** (discrete)
4. **MaskablePPO** (action masking support)
5. **TRPO**, **RecurrentPPO**, **ARS** (sb3-contrib)

Tip: Prefer PPO/MaskablePPO; enable action masking if the environment supports it.

### Step 2.2: Custom Reward Function Design

```python
def calculate_reward(self, action: int) -> float:
    # Continuous, properly scaled reward inside MyRLEnv (FreqAI RL)
    if not self._is_valid(action):
        return -2.0
    pnl = self.get_unrealized_profit()      # fraction per step
    dd = self.get_current_drawdown()        # fraction 0..1
    cost = self.get_step_cost(action)       # fees+slippage
    hold_pen = 0.0
    if self._position in (Positions.Long, Positions.Short) and action == Actions.Neutral.value:
        hold_pen = -1.0 * (self._current_tick - (self._last_trade_tick or self._current_tick)) / max(1, self.rl_config.get('max_trade_duration_candles', 300))
    # Risk-adjusted pnl with transaction costs and drawdown aversion
    reward = (pnl - 3.0*dd - cost) * 100.0 + hold_pen
    return float(reward)
```

### Step 2.4: Reward shaping for extremes (pattern learning without feature leakage)

- **Goal**: Encourage entries near local lows and exits near local highs (and vice versa for shorts) while avoiding feature leakage. It's valid in RL to compute rewards using future outcomes because the environment has access to the full trajectory. Do not include future information in features/state.
- **Approach**: Combine delayed rewards using forward-looking windows for entry quality and past-looking windows for exit quality, all normalized by volatility (ATR) and costs.

Key parameters (set in `rl_config.model_reward_parameters`):

```json
"model_reward_parameters": {
  "entry_lookahead": 24,            // candles to assess forward high/low after entry
  "exit_lookback": 24,              // candles to assess past high/low at exit
  "regret_lookahead": 12,           // optional: penalize if better price shortly after exit
  "atr_period": 14,
  "atr_norm_cap": 5.0,
  "lambda_dd": 3.0,                 // drawdown penalty weight
  "lambda_cost": 1.0,               // transaction cost weight
  "lambda_entry_eff": 1.0,          // entry efficiency weight
  "lambda_exit_eff": 1.0,           // exit efficiency weight
  "lambda_regret": 0.5              // regret penalty weight
}
```

Example implementation inside `MyCoolRLModel.MyRLEnv.calculate_reward`:

```python
from freqtrade.freqai.RL.Base5ActionRLEnv import Actions, Positions

class MyCoolRLModel(ReinforcementLearner):
    class MyRLEnv(Base5ActionRLEnv):
        def _atr(self, idx: int) -> float:
            # Minimal ATR proxy (use your feature-engineered ATR if available)
            w = int(self.rl_config["model_reward_parameters"].get("atr_period", 14))
            lo = max(1, idx - w)
            h = self.prices["high"].iloc[lo:idx+1]
            l = self.prices["low"].iloc[lo:idx+1]
            c = self.prices["close"].iloc[lo:idx+1]
            tr = (h - l).abs()
            atr = tr.mean() if len(tr) else 1e-6
            cap = float(self.rl_config["model_reward_parameters"].get("atr_norm_cap", 5.0))
            return float(min(max(atr, 1e-6), cap))

        def _entry_efficiency(self, entry_idx: int, is_long: bool) -> float:
            la = int(self.rl_config["model_reward_parameters"].get("entry_lookahead", 24))
            end = min(len(self.prices) - 1, entry_idx + la)
            closes = self.prices["close"].iloc[entry_idx:end+1]
            entry_price = float(self.prices["close"].iloc[entry_idx])
            atr = self._atr(entry_idx)
            if is_long:
                fmax = float(closes.max())
                return (fmax - entry_price) / atr
            else:
                fmin = float(closes.min())
                return (entry_price - fmin) / atr

        def _exit_efficiency(self, exit_idx: int, is_long: bool) -> float:
            lb = int(self.rl_config["model_reward_parameters"].get("exit_lookback", 24))
            start = max(0, exit_idx - lb)
            closes = self.prices["close"].iloc[start:exit_idx+1]
            exit_price = float(self.prices["close"].iloc[exit_idx])
            atr = self._atr(exit_idx)
            if is_long:
                pmax = float(closes.max())
                return (exit_price - pmax) / atr  # <= 0, closer to 0 is better
            else:
                pmin = float(closes.min())
                return (pmin - exit_price) / atr  # <= 0, closer to 0 is better

        def _regret(self, exit_idx: int, is_long: bool) -> float:
            la = int(self.rl_config["model_reward_parameters"].get("regret_lookahead", 0))
            if la <= 0:
                return 0.0
            end = min(len(self.prices) - 1, exit_idx + la)
            closes = self.prices["close"].iloc[exit_idx:end+1]
            exit_price = float(self.prices["close"].iloc[exit_idx])
            atr = self._atr(exit_idx)
            if is_long:
                post_max = float(closes.max())
                return max(0.0, (post_max - exit_price) / atr)
            else:
                post_min = float(closes.min())
                return max(0.0, (exit_price - post_min) / atr)

        def calculate_reward(self, action: int) -> float:
            if not self._is_valid(action):
                return -2.0
            params = self.rl_config["model_reward_parameters"]
            lam_dd = float(params.get("lambda_dd", 3.0))
            lam_cost = float(params.get("lambda_cost", 1.0))
            lam_e = float(params.get("lambda_entry_eff", 1.0))
            lam_x = float(params.get("lambda_exit_eff", 1.0))
            lam_r = float(params.get("lambda_regret", 0.0))

            pnl = self.get_unrealized_profit()  # per-step pnl in fraction
            dd = self.get_current_drawdown()
            cost = self.get_step_cost(action)

            base = (pnl - lam_dd * dd - lam_cost * cost) * 100.0

            # Entry bonus on fresh entries
            entry_bonus = 0.0
            if action in (Actions.Long_enter.value, Actions.Short_enter.value) and self._position == Positions.Neutral:
                is_long = action == Actions.Long_enter.value
                entry_bonus = lam_e * self._entry_efficiency(self._current_tick, is_long)

            # Exit quality at exits
            exit_bonus = 0.0
            regret_pen = 0.0
            if (action == Actions.Long_exit.value and self._position == Positions.Long) or \
               (action == Actions.Short_exit.value and self._position == Positions.Short):
                is_long = self._position == Positions.Long
                exit_bonus = lam_x * self._exit_efficiency(self._current_tick, is_long)
                regret_pen = lam_r * self._regret(self._current_tick, is_long)

            return float(base + entry_bonus + exit_bonus - regret_pen)
```

Notes:

- The environment uses future prices to compute rewards for actions already taken. This is standard in RL and does not leak into features.
- Normalize by ATR to stabilize gradients and make rewards comparable across regimes/pairs.
- Tune the lambdas via Optuna; optimize on OOS equity with SPA/PBO checks to avoid overfitting.

### Step 2.3: Feature Engineering

- **Price Features**: Returns, volatility, momentum
- **Technical Indicators**: ADX, RSI, OBV, Bollinger Bands, ATR (multi-timeframe)
- **Market Regime**: Trend/sideways proxies
- **Time Features**: Cyclical encodings
- **PCA**: Enable `principal_component_analysis: true` in `feature_parameters`. FreqAI fits on train only (no leakage), then transforms validation/test. Pair with `weight_factor` and optional Gaussian `noise_standard_deviation` for regularization.

Example config block:

```json
"freqai": {
  "identifier": "RL-Exp12",
  "train_period_days": 730,
  "backtest_period_days": 90,
  "activate_tensorboard": true,
  "continual_learning": false,
  "feature_parameters": {
    "include_timeframes": ["1h", "4h"],
    "include_shifted_candles": 2,
    "principal_component_analysis": true,
    "weight_factor": 0.995,
    "noise_standard_deviation": 0.03
  },
  "data_split_parameters": {"test_size": 0.1, "shuffle": false},
  "rl_config": {
    "train_cycles": 25,
    "add_state_info": true,
    "max_trade_duration_candles": 300,
    "max_training_drawdown_pct": 0.2,
    "cpu_count": 8,
    "model_type": "PPO",
    "policy_type": "MlpPolicy",
    "net_arch": [256, 256],
    "drop_ohlc_from_features": false,
    "progress_bar": true,
    "model_reward_parameters": {"rr": 1.0, "profit_aim": 0.02, "win_reward_factor": 2}
  },
  "model_training_parameters": {
    "learning_rate": 0.0003,
    "n_steps": 2048,
    "batch_size": 64,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "ent_coef": 0.0,
    "vf_coef": 0.5,
    "n_epochs": 10
  }
}
```

---

## 🏋️ **Phase 3: Training & Hyperparameter Optimization**

### Step 3.1: Initial Training Setup

Training is driven by the JSON config (`rl_config` and `model_training_parameters`). Ensure `train_cycles * n_train_obs ≈ desired timesteps`.

### Step 3.2: Hyperparameter Optimization with Optuna

- **Learning Rate**: [1e-5, 3e-4]
- **Gamma, GAE Lambda**: gamma [0.95, 0.999]; gae_lambda [0.8, 0.98]
- **n_steps**: [512, 4096]; **batch_size**: [32, 256]
- **clip_range**: [0.1, 0.3]; **ent_coef**: [1e-4, 1e-2]
- **vf_coef**: [0.3, 1.0]; **n_epochs**: [5, 20]
- **net_arch**: [[128,128], [256,256], [256,256,128]]
- **Reward Weights**: tune drawdown penalty multiplier and profit_aim

Use pruners (Median/SuccessiveHalving), callbacks for checkpointing best models, and fixed seeding for reproducibility.

### Step 3.3: Training Monitoring

- **TensorBoard**: Enable `activate_tensorboard`; logs at `user_data/models/<identifier>/tensorboard`.
- **Validation**: Built-in eval callback saves `best_model.zip` per pair.
- **Early stopping**: Use Optuna pruners or validation gating.
- **Seeding**: Fix seeds across runs; report mean±std across 3 seeds.

---

## 📈 **Phase 4: Strategy Integration & Backtesting**

### Step 4.1: Create RL Freqtrade Strategy

Implement the minimal functions in your strategy as shown in Phase 1.2. Use:

- Run backtests with RL:
  - `freqtrade backtesting --strategy RLStrategy --freqaimodel MyCoolRLModel -c user_data/config.json`
- Live/dry-run:
  - `freqtrade trade --strategy RLStrategy --freqaimodel MyCoolRLModel -c user_data/config.json`

### Step 4.2: Comprehensive Backtesting

- **Full Period**: 2020-2025 (5 years)
- **Walk-Forward**: Configure `train_period_days` (e.g., 720) and `backtest_period_days` (e.g., 90)
- **Multiple Pairs**: SOL, BTC, ETH, ADA, DOT
- **Market Regimes**: Bull, bear, sideways

### Step 4.3: Performance Metrics

- **Profit**: Total return, CAGR, Sharpe ratio
- **Risk**: Max drawdown, volatility, VaR
- **Robustness**: Across periods/pairs, seeds
- **Stability**: Consistency of returns
- **Overfitting checks**: SPA test, PBO/CSCV style analyses (report win consistency across slices)

---

## 🔄 **Phase 5: Continuous Learning & Adaptation**

### Step 5.1: Online Learning Setup

- **Incremental Training**: Use `live_retrain_hours` for scheduled retraining
- **Concept Drift Detection**: Monitor when market conditions change
- **Model Ensemble**: Optional voting between PPO variants or seeds
- **Performance Monitoring**: Real-time tracking of live performance

### Step 5.2: Multi-Agent Approach

- **Specialist Agents**: Different agents for different market regimes
- **Meta-Agent**: Decides which specialist to use
- **Ensemble Voting**: Combine predictions from multiple agents

### Step 5.3: Advanced Features

- **Attention Mechanisms**: Feature importance-driven selection
- **Recurrent Policies**: `RecurrentPPO` for long-context tasks
- **Multi-Timeframe**: 1h, 4h, 1d via `include_timeframes`
- **Alternative Data**: Sentiment/on-chain via custom features

---

## 📊 **Phase 6: Validation & Production Deployment**

### Step 6.1: Rigorous Testing

- **Out-of-Sample**: Reserve latest year fully OOS
- **Stress Testing**: Crash windows and high-vol regimes
- **Robustness Checks**: Start-date perturbations, seeds, pairs
- **Monte Carlo**: Bootstrapped equity paths

### Step 6.2: Risk Management Integration

- **Position Sizing**: Keep discrete actions initially; add sizing later via env extension
- **Stops/TP**: Encouraged via reward shaping (profit_aim, duration penalties)
- **Portfolio Heat**: Manage via bot-level stake/risk constraints
- **Drawdown Protection**: Use protections module as guardrails

### Step 6.3: Production Monitoring

- **Real-Time Alerts**: Monitor PnL, hit rate, avg trade duration
- **Model Drift Detection**: Track reward proxies; trigger retrain when degraded
- **A/B Testing**: Compare vs indicator strategies
- **Performance Attribution**: Feature importance and policy diagnostics

---

## 🎯 **Success Criteria**

### Minimum Viable Performance

- **5-Year Return**: > +50% (vs -27.56% baseline)
- **Max Drawdown**: < 25% (vs 47% baseline)
- **Sharpe Ratio**: > 1.5
- **Win Rate**: > 55%

### Stretch Goals

- **5-Year Return**: > +200%
- **Max Drawdown**: < 15%
- **Sharpe Ratio**: > 2.0
- **Consistent Profitability**: Positive returns in 4/5 years

---

## 📝 **Implementation Timeline**

### Week 1-2: Environment & Data Setup

- [ ] Install RL dependencies (FreqAI RL, Torch, SB3/SB3-contrib)
- [ ] Implement FreqAI strategy glue (`%-raw_*`, `&-action`)
- [ ] Configure `freqai` blocks (`feature_parameters`, PCA, splits)
- [ ] Prepare walk-forward datasets and download pairs/timeframes

### Week 3-4: Model Development

- [ ] Evaluate PPO, MaskablePPO, A2C
- [ ] Design and iterate reward (risk-adjusted, cost-aware)
- [ ] Configure net_arch, conv_width, state info
- [ ] Enable TensorBoard; wire eval callback

### Week 5-6: Training & Optimization

- [ ] Train initial agents per pair and timeframe
- [ ] Optuna HPO with pruners and checkpoints
- [ ] Select models on OOS validation
- [ ] Analyze robustness across seeds/pairs

### Week 7-8: Integration & Testing

- [ ] Finalize Freqtrade integration and protections
- [ ] Comprehensive WFA backtesting
- [ ] Risk/protections guardrails in production
- [ ] Final validation and rollout plan

---

## 🔧 **Technical Architecture**

```text
Data Pipeline → Feature Engineering → RL Environment
     ↓                ↓                    ↓
Training Data → Model Training → Trained Agent
     ↓                ↓                    ↓
Validation → Hyperopt → Best Model → Freqtrade Strategy
     ↓                ↓                    ↓
Backtesting → Performance Analysis → Production Deployment
```

---

## 📈 **Expected Outcomes**

1. **Adaptive Strategy**: Learns from market patterns automatically
2. **Superior Performance**: Significantly outperforms traditional indicators
3. **Risk Management**: Built-in risk awareness through reward function
4. **Scalability**: Can be applied to multiple assets and timeframes
5. **Continuous Improvement**: Gets better with more data and experience

This RL approach should finally give us a **truly profitable strategy** that can adapt and learn, rather than relying on static indicators that fail in changing market conditions.
