# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Dict, Optional, Union, Tuple, List
from freqtrade.optimize.space import Categorical, Dimension, Integer, SKDecimal
import logging
from functools import reduce

logger = logging.getLogger(__name__)

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,  # @informative decorator
    # Hyperopt Parameters
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    # timeframe helpers
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    # Strategy helper functions
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)


# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta
from technical import qtpylib


# ==========================================
# QuantumTactics Synthesis Strategy - 1-Minute High Frequency Trading
# Combines the most profitable elements from all quanttactics strategies
# Optimized for 1-minute timeframe with multi-timeframe trend confirmation
# ==========================================

# ================================
# Freqtrade Version
# ================================

"""
freqtrade -V

Operating System:       Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.36
Python Version:         Python 3.13.5
CCXT Version:           4.4.96

Freqtrade Version:      freqtrade 2025.7
"""

# ================================
# Download Historical Data
# ================================

"""
freqtrade download-data \
    -c user_data/binance_futures_QuantumTactics_Synthesis.json \
    --timerange 20230101- \
    -t 1m 5m 15m 30m 1h 2h 4h 1d
"""

# ================================
# Hyperopt Optimization
# ================================

"""
freqtrade hyperopt \
    --strategy QuantumTactics_Synthesis \
    --config user_data/binance_futures_QuantumTactics_Synthesis.json \
    --timeframe 1h \
    --timerange 20240101-20240801 \
    --hyperopt-loss MultiMetricHyperOptLoss \
    --spaces buy sell roi stoploss\
    -e 100 \
    --j -2 \
    --random-state 9319 \
    --min-trades 30 \
    --max-open-trades 3 \
    -p SOL/USDT:USDT DOT/USDT:USDT AVAX/USDT:USDT
"""

# ================================
# Backtesting
# ================================

"""
freqtrade backtesting \
    --strategy QuantumTactics_Synthesis \
    --timeframe 1h \
    --timerange 20240101-20240801 \
    --breakdown month \
    -c user_data/binance_futures_QuantumTactics_Synthesis.json \
    --max-open-trades 3 \
    --cache none \
    --timeframe-detail 5m
"""

# ================================
# Start FreqUI Web Interface
# ================================

"""
freqtrade webserver \
    --config user_data/binance_futures_QuantumTactics_Synthesis.json
"""


class QuantumTactics_Synthesis(IStrategy):

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy - 1m for high frequency trading
    timeframe = "1m"

    # Can this strategy go short?
    can_short: bool = True

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {}

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.25

    # Trailing stoploss
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 1000  # Increased for multiple timeframes

    # ================================
    # Core Strategy Parameters - Optimized for 1m timeframe
    # ================================

    # ADX for trend strength (from TemaAdxCmo, ADX_OBV, etc.)
    adx_period = CategoricalParameter([5, 7, 10], default=7, space="buy")  # Shorter for 1m
    adx_threshold = CategoricalParameter([20, 25, 30], default=25, space="buy")  # Lower threshold

    # TEMA for fast trend (from TemaAdxCmo)
    tema_period = CategoricalParameter([5, 8, 13], default=8, space="buy")  # Faster for 1m
    tema_rolling_window = CategoricalParameter([2, 3, 4], default=3, space="buy")  # Shorter window

    # EMA for medium trend (from most strategies)
    ema_period = CategoricalParameter([20, 50, 100], default=50, space="buy")  # Shorter for 1m

    # OBV for volume confirmation (from ADX_OBV)
    obv_ma_period = CategoricalParameter([20, 30, 50], default=30, space="buy")  # Shorter for 1m

    # MACD for momentum (from most strategies)
    macd_rolling_window = CategoricalParameter([3, 5, 8], default=5, space="buy")  # Shorter for 1m

    # RSI for momentum (from RSI strategies)
    rsi_period = CategoricalParameter([7, 10, 14], default=10, space="buy")  # Shorter for 1m
    rsi_threshold = CategoricalParameter([45, 50, 55], default=50, space="buy")  # Lower threshold

    # SuperTrend for trend direction (from SuperTrend strategies)
    supertrend_period = CategoricalParameter([7, 10, 13], default=10, space="buy")  # Shorter for 1m
    supertrend_multiplier = CategoricalParameter([1.5, 2, 2.5], default=2, space="buy")  # Lower multiplier

    # Exit parameters - tighter for 1m trading
    atr_mult = CategoricalParameter([1.5, 2, 2.5], default=2, space="sell")
    risk_ratio = CategoricalParameter([1, 1.5, 2], default=1.5, space="sell")  # Lower risk ratio
    stop_loss_buffer = DecimalParameter(0.001, 0.005, decimals=3, default=0.003, space="sell")

    leverage_level = IntParameter(1, 3, default=1, space='buy', optimize=False, load=False)

    @property
    def plot_config(self):

        plot_config = {
            "main_plot": {
                f"tema_{self.tema_period.value}": {"color": "#f50057", "type": "line"},
                f"ema_{self.ema_period.value}": {"color": "#2962ff", "type": "line"},
                f"supertrend_{self.supertrend_period.value}_{self.supertrend_multiplier.value}": {
                    "color": "#4caf50",
                    "type": "line",
                    "fill_to": "close"
                }
            },
            "subplots": {
                "ADX": {
                    f"adx_{self.adx_period.value}": {"color": "#f23645", "type": "line"}
                },
                "OBV": {
                    "obv": {"color": "#2962ff", "type": "line"},
                    f"obv_ma_{self.obv_ma_period.value}": {"color": "#fdd835", "type": "line"}
                },
                "MACD": {
                    "macd": {"color": "#2962ff", "fill_to": "macdhist"},
                    "macdsignal": {"color": "#ff6d00"},
                    "macdhist": {"type": "bar", "plotly": {"opacity": 0.9}}
                },
                "RSI": {
                    f"rsi_{self.rsi_period.value}": {"color": "#9e57c2", "type": "line"}
                }
            }
        }

        return plot_config

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ================================
        # Core Trend Indicators (ADX + TEMA + EMA)
        # ================================

        # ADX for trend strength
        dataframe[f"adx_{self.adx_period.value}"] = ta.ADX(dataframe, timeperiod=self.adx_period.value)

        # TEMA for fast trend
        dataframe[f"tema_{self.tema_period.value}"] = ta.TEMA(dataframe, timeperiod=self.tema_period.value)

        # EMA for medium trend
        dataframe[f"ema_{self.ema_period.value}"] = ta.EMA(dataframe, timeperiod=self.ema_period.value)

        # ================================
        # Volume Confirmation (OBV)
        # ================================

        # OBV for volume confirmation
        dataframe["obv"] = ta.OBV(dataframe)
        dataframe[f"obv_ma_{self.obv_ma_period.value}"] = dataframe["obv"].rolling(window=self.obv_ma_period.value).mean()

        # ================================
        # Momentum Indicators (MACD + RSI)
        # ================================

        # MACD for momentum
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        # RSI for momentum confirmation
        dataframe[f"rsi_{self.rsi_period.value}"] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)

        # ================================
        # SuperTrend for trend direction
        # ================================

        # SuperTrend for clear trend direction
        superTrend = pta.supertrend(
            dataframe['high'],
            dataframe['low'],
            dataframe['close'],
            length=self.supertrend_period.value,
            multiplier=self.supertrend_multiplier.value
        )
        dataframe[f'supertrend_{self.supertrend_period.value}_{self.supertrend_multiplier.value}'] = superTrend[f'SUPERT_{self.supertrend_period.value}_{self.supertrend_multiplier.value}.0']
        dataframe[f'supertrend_direction_{self.supertrend_period.value}_{self.supertrend_multiplier.value}'] = superTrend[f'SUPERTd_{self.supertrend_period.value}_{self.supertrend_multiplier.value}.0']

        # ================================
        # ATR for exits
        # ================================

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ================================
        # Multi-Condition Entry Logic
        # ================================

        # Use current parameter values for column names
        adx_col = f"adx_{self.adx_period.value}"
        tema_col = f"tema_{self.tema_period.value}"
        ema_col = f"ema_{self.ema_period.value}"
        obv_ma_col = f"obv_ma_{self.obv_ma_period.value}"
        rsi_col = f"rsi_{self.rsi_period.value}"
        supertrend_col = f'supertrend_direction_{self.supertrend_period.value}_{self.supertrend_multiplier.value}'

        # ================================
        # Long Entry Conditions (Synthesized from best performers)
        # ================================

        long_conditions = []

        # 1. ADX trend strength (from TemaAdxCmo, ADX_OBV)
        long_conditions.append(dataframe[adx_col] > self.adx_threshold.value)

        # 2. TEMA trend (from TemaAdxCmo)
        long_conditions.append(dataframe[tema_col] > dataframe[tema_col].shift(1))

        # 3. EMA alignment (from most strategies)
        long_conditions.append(dataframe[tema_col] > dataframe[ema_col])

        # 4. 1m timeframe trend confirmation (200 EMA)
        long_conditions.append(dataframe[f"ema_{self.ema_period.value}"] > dataframe[f"ema_{self.ema_period.value}"].shift(1))

        # 5. Volume confirmation (from ADX_OBV)
        long_conditions.append(dataframe["obv"] > dataframe[obv_ma_col])

        # 6. MACD momentum (from MACD strategies)
        long_conditions.append(dataframe["macd"] > dataframe["macdsignal"])
        long_conditions.append(
            dataframe["macd"].rolling(window=self.macd_rolling_window.value).apply(
                lambda x: any(qtpylib.crossed_above(x, dataframe["macdsignal"].iloc[x.index[0]:x.index[-1]+1]))
            )
        )

        # 7. RSI confirmation (from RSI strategies)
        long_conditions.append(dataframe[rsi_col] > self.rsi_threshold.value)

        # 8. SuperTrend direction (from SuperTrend strategies)
        long_conditions.append(dataframe[supertrend_col] == 1)

        # 9. Volume filter
        long_conditions.append(dataframe["volume"] > 0)

        # Apply all long conditions
        if long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, long_conditions),
                'enter_long'] = 1

        # ================================
        # Short Entry Conditions
        # ================================

        short_conditions = []

        # 1. ADX trend strength
        short_conditions.append(dataframe[adx_col] > self.adx_threshold.value)

        # 2. TEMA trend
        short_conditions.append(dataframe[tema_col] < dataframe[tema_col].shift(1))

        # 3. EMA alignment
        short_conditions.append(dataframe[tema_col] < dataframe[ema_col])

        # 4. 1m timeframe trend confirmation (200 EMA)
        short_conditions.append(dataframe[f"ema_{self.ema_period.value}"] < dataframe[f"ema_{self.ema_period.value}"].shift(1))

        # 5. Volume confirmation
        short_conditions.append(dataframe["obv"] < dataframe[obv_ma_col])

        # 6. MACD momentum
        short_conditions.append(dataframe["macd"] < dataframe["macdsignal"])
        short_conditions.append(
            dataframe["macd"].rolling(window=self.macd_rolling_window.value).apply(
                lambda x: any(qtpylib.crossed_below(x, dataframe["macdsignal"].iloc[x.index[0]:x.index[-1]+1]))
            )
        )

        # 7. RSI confirmation
        short_conditions.append(dataframe[rsi_col] < (100 - self.rsi_threshold.value))

        # 8. SuperTrend direction
        short_conditions.append(dataframe[supertrend_col] == -1)

        # 9. Volume filter
        short_conditions.append(dataframe["volume"] > 0)

        # Apply all short conditions
        if short_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, short_conditions),
                'enter_short'] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ================================
        # Exit Logic (ATR-based from all strategies)
        # ================================

        supertrend_col = f'supertrend_direction_{self.supertrend_period.value}_{self.supertrend_multiplier.value}'
        ema_col = f"ema_{self.ema_period.value}"

        # Exit long when SuperTrend turns bearish or price drops below EMA
        dataframe.loc[
            (
                (dataframe[supertrend_col] == -1) |
                (dataframe["close"] < dataframe[ema_col] - (dataframe["atr"] * self.atr_mult.value))
            ) &
            (dataframe["volume"] > 0)
            ,
            "exit_long"] = 1

        # Exit short when SuperTrend turns bullish or price rises above EMA
        dataframe.loc[
            (
                (dataframe[supertrend_col] == 1) |
                (dataframe["close"] > dataframe[ema_col] + (dataframe["atr"] * self.atr_mult.value))
            ) &
            (dataframe["volume"] > 0)
            ,
            "exit_short"] = 1

        return dataframe


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                current_profit: float, **kwargs):

        side = -1 if trade.is_short else 1

        # Retrieve TP and SL from custom data
        take_profit = trade.get_custom_data('take_profit')
        stop_loss = trade.get_custom_data('stop_loss')

        # If TP or SL is not set, initialize them
        if take_profit is None or stop_loss is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

            # Get the date just before trade opened
            trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)

            # Filter dataframe to candles before the trade opened
            signal_data = dataframe.loc[dataframe["date"] < trade_date]

            if signal_data.empty:
                logger.warning(f"[{pair}] No signal candle found. Skip setting TP/SL.")
                return None

            signal_candle = signal_data.iloc[-1]

            if not trade.is_short:
                # Calculate the lowest price over the last x candles (swing low)
                swing_low = signal_data["low"].rolling(5).min().iloc[-1]
                stop_loss = swing_low * (1 - self.stop_loss_buffer.value)
                risk_amount = abs(signal_candle["close"] - stop_loss)
                take_profit = signal_candle["close"] + (self.risk_ratio.value * risk_amount)

            elif trade.is_short:
                # Calculate the highest price over the last x candles (swing high)
                swing_high = signal_data["high"].rolling(5).max().iloc[-1]
                stop_loss = swing_high * (1 + self.stop_loss_buffer.value)
                risk_amount = abs(signal_candle["close"] - stop_loss)
                take_profit = signal_candle["close"] - (self.risk_ratio.value * risk_amount)

            # Save to trade's custom data
            trade.set_custom_data('take_profit', take_profit)
            trade.set_custom_data('stop_loss', stop_loss)

            # logger.info(f"[{pair}] TP/SL set. TP: {take_profit:.2f}, SL: {stop_loss:.2f}")


        # Get the current close price
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        current_close = dataframe.iloc[-1]['close']

        # Check exit conditions
        if (trade.is_short and current_close <= take_profit) or \
        (not trade.is_short and current_close >= take_profit):
            # logger.info(f"[{pair}] Take Profit hit! Close: {current_close:.2f}, TP: {take_profit:.2f}")
            return "take_profit_achieved"

        if (trade.is_short and current_close >= stop_loss) or \
        (not trade.is_short and current_close <= stop_loss):
            # logger.info(f"[{pair}] Stop Loss hit! Close: {current_close:.2f}, SL: {stop_loss:.2f}")
            return "stop_loss_achieved"

        return None


    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:

        return self.leverage_level.value
