# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Dict, Optional, Union, Tuple
import logging
import json
from pathlib import Path

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
# Donchian Channel Strategy made 140% Profit! (Full Tutorial)
# https://youtu.be/CgYdfwrL1VQ
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
    -c user_data/binance_futures_Donchian_EMA_ADX_CHOP_PairOptimized.json \
    --timerange 20230101- \
    -t 1m 5m 15m 30m 1h 2h 4h 1d
"""

# ================================
# Backtesting
# ================================

""""
freqtrade backtesting \
    --strategy Donchian_EMA_ADX_CHOP_PairOptimized \
    --timeframe 1h \
    --timerange 20240601-20250601 \
    --breakdown month \
    -c user_data/binance_futures_Donchian_EMA_ADX_CHOP_PairOptimized.json \
    --max-open-trades 3 \
    --timeframe-detail 5m \
    --cache none
"""

# ================================
# Start FreqUI Web Interface
# ================================

"""
freqtrade webserver \
    --config user_data/binance_futures_Donchian_EMA_ADX_CHOP_PairOptimized.json
"""

class Donchian_EMA_ADX_CHOP_PairOptimized(IStrategy):

    def __init__(self, config):
        
        # Initialize the strategy with the given configuration and load pair-specific settings.   
        super().__init__(config)
        self.load_pair_settings()

    def load_pair_settings(self) -> None:
        
        # Get the class name dynamically to locate the appropriate settings file
        class_name = self.__class__.__name__
        settings_filename = Path(__file__).parent / f"{class_name}_Settings.json"
        
        try:
            # Attempt to open and load the JSON settings file
            with open(settings_filename, "r") as f:
                self.custom_info = json.load(f)
                logger.info(f"Settings successfully loaded from {settings_filename}.")
                logger.info(f"Settings: {self.custom_info}")

        except FileNotFoundError:
            # Raise an error if the settings file is missing
            raise SystemExit(f"Settings file not found at {settings_filename}. Program will exit.")
        
        except json.JSONDecodeError as e:
            # Raise an error if the JSON file contains invalid data
            raise SystemExit(f"Error decoding JSON from settings file: {e}. Program will exit.")
        
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy.
    timeframe = "1h"

    # Can this strategy go short?
    can_short: bool = True

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {}
    
    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.20

    # Trailing stoploss
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured
    
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    use_custom_stoploss = True
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200
    
    @property
    def plot_config(self):
        return {
            "main_plot": {
                'dc_upper': {"color": "#2962FF"},
                'dc_lower': {"color": "#2962FF"}
            },
            "subplots": {
                
                "ADX": {
                    "adx": {"color": "#f23645", "type": "line"
                    }
                },
                "CHOP": {
                    "chop": {"color": "#2962FF", "type": "line"
                    }
                }
            }
        }

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        
        return []

    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        pair = metadata["pair"]
        
        if pair in self.custom_info:
            
            pair_settings = self.custom_info[pair]

            dataframe['dc_upper'] = dataframe['high'].rolling(window=pair_settings["donchian_period"]).max().shift(1)
            dataframe['dc_lower'] = dataframe['low'].rolling(window=pair_settings["donchian_period"]).min().shift(1)

            dataframe["ema"] = ta.EMA(dataframe, timeperiod=pair_settings["ema_period"])
        
        dataframe['chop'] = pta.chop(
            high=dataframe['high'],
            low=dataframe['low'],
            close=dataframe['close'],
            length=14
        )
        
        # ADX
        dataframe["adx"] = ta.ADX(dataframe)
        
        # ATR
        dataframe["atr"] = ta.ATR(dataframe)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        pair = metadata["pair"]
        
        if pair in self.custom_info:
            
            pair_settings = self.custom_info[pair]
            
            dataframe.loc[
                    (
                        (qtpylib.crossed_above(dataframe["close"], dataframe['dc_upper'])) &
                        (dataframe['close'] > dataframe["ema"]) &
                        (dataframe['adx'] > pair_settings["adx_threshold"]) &
                        (dataframe['chop'] < pair_settings["chop_threshold"]) &
                        (dataframe['volume'] > 0)
                    ),
                    'enter_long'] = 1
            
            dataframe.loc[
                    (
                        (qtpylib.crossed_below(dataframe["close"], dataframe['dc_lower'])) &
                        (dataframe['close'] < dataframe[f"ema"]) &
                        (dataframe['adx'] > pair_settings["adx_threshold"]) &
                        (dataframe['chop'] < pair_settings["chop_threshold"]) &
                        (dataframe['volume'] > 0)
                    ),
                    'enter_short'] = 1

            return dataframe
    

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[:, "exit_long"] = 0
        dataframe.loc[:, "exit_short"] = 0

        return dataframe
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float | None:
        
        if pair in self.custom_info:
            
            pair_settings = self.custom_info[pair]
            
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

            candle = dataframe.iloc[-1].squeeze()
            side = 1 if trade.is_short else -1
            
            return stoploss_from_absolute(current_rate + (side * candle["atr"] * pair_settings["atr_mult"]), 
                                        current_rate=current_rate, 
                                        is_short=trade.is_short,
                                        leverage=trade.leverage)
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:

        if pair in self.custom_info:
            
            pair_settings = self.custom_info[pair]
            
            return pair_settings['leverage_level']