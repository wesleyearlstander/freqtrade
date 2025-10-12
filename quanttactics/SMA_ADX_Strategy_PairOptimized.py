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
# ADX & Moving Averages: Freqtrade Crypto Strategy That Actually Works!
# YouTube Link: https://youtu.be/S6l3nZ3YkWw
# ==========================================

# ================================
# Freqtrade Version
# ================================

"""
freqtrade -V

Operating System:       Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.36
Python Version:         Python 3.12.9
CCXT Version:           4.4.62

Freqtrade Version:      freqtrade 2025.2
"""

# ================================
# Download Historical Data
# ================================

"""

freqtrade list-data -c user_data/config_binance_futures.json --show-timerange

freqtrade download-data \
    -c user_data/config_binance_futures.json \
    --timerange 20230101- \
    -t 1m 5m 15m 30m 1h 2h 4h 1d
"""

# ================================
# Backtesting
# ================================

"""
freqtrade backtesting \
    --strategy SMA_ADX_Strategy_PairOptimized \
    --timeframe 4h \
    --timerange 20240201-20250201 \
    --breakdown month \
    -c user_data/binance_futures_SMA_ADX_Strategy_PairOptimized.json \
    --max-open-trades 3 \
    --cache none \
    --timeframe-detail 15m
"""

# ================================
# Start FreqUI Web Interface
# ================================

"""
freqtrade webserver \
    --config user_data/config_binance_futures.json
"""

class SMA_ADX_Strategy_PairOptimized(IStrategy):
    
    def __init__(self, config):
        
        # Initialize the strategy with the given configuration and load pair-specific settings.   
        super().__init__(config)
        self.load_pair_settings()

    def load_pair_settings(self) -> None:
        
        # Get the class name dynamically to locate the appropriate settings file
        class_name = self.__class__.__name__
        settings_filename = Path(__file__).parent / f'{class_name}_Settings.json'
        
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
    timeframe = "4h"
    informative_timeframe = '1d'

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
    startup_candle_count: int = 200
    
    @property
    def plot_config(self):
        return {
            # Main plot indicators (Moving averages, ...)
            "main_plot": {
                "sma_high": {"color": "#4CAF50"},
                "sma_low": {"color": "#f23645"},
                "sma_long": {"color": "#ffeb3b"}
                
            },
            "subplots": {
                # Subplots - each dict defines one additional plot 
                "ADX": {
                    "adx": {"color": "#2962ff"},
                },
                "ATR": {
                    "atr_1d": {"color": "#ff9800"}
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
        # get access to all pairs available in whitelist.
        pairs = self.dp.current_whitelist()

        # Assign tf to each pair so they can be downloaded and cached for strategy.
        informative_pairs = [(pair, self.informative_timeframe) for pair in pairs]

        return informative_pairs
    
    @informative('1d')
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        return dataframe
    

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        pair = metadata['pair']
        
        if pair in self.custom_info:
            
            pair_settings = self.custom_info[pair]
            
            dataframe["sma_high"] = ta.SMA(dataframe["high"], timeperiod=pair_settings["short_sma_period"])
            dataframe["sma_low"] = ta.SMA(dataframe["low"], timeperiod=pair_settings["short_sma_period"])
            
            dataframe["sma_long"] = ta.SMA(dataframe["close"], timeperiod=pair_settings["long_sma_period"])

            dataframe["adx"] = ta.ADX(dataframe, timeperiod=pair_settings["adx_period"])
            
            dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
            
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # Retrieve the trading pair from metadata
        pair = metadata['pair']

        # Check if the pair has custom settings defined in self.custom_info
        if pair in self.custom_info:
            
            # Retrieve custom parameter settings for the specific trading pair
            pair_settings = self.custom_info[pair]
            
            # Define entry conditions for Long Position
            dataframe.loc[
                (
                    # Price is above the long-term SMA (indicating an uptrend)
                    (dataframe['close'] > dataframe["sma_long"]) &
                    
                    # Check if the price crossed above the high SMA within the specified rolling window
                    (dataframe['close'].rolling(window=pair_settings["cross_rolling_window"]).apply(
                        lambda x: any(qtpylib.crossed_above(
                            x, dataframe["sma_high"].iloc[x.index[0]:x.index[-1]+1]
                        )) 
                    )) &

                    # ADX is above the threshold (confirming strong trend momentum)
                    (dataframe["adx"] > pair_settings["adx_threshold"]) &
                    
                    # ATR is greater than a threshold percentage of the current price 
                    # (ensuring sufficient volatility for a meaningful trade)
                    (dataframe["atr_1d"] > dataframe["close"] * pair_settings["atr_price_threshold"]) &
                                    
                    # Ensure there is trading volume to avoid illiquid market conditions
                    (dataframe["volume"] > 0)  
                ),
                "enter_long"] = 1

            # Define entry conditions for Short Position
            dataframe.loc[
                (
                    # Price is below the long-term SMA (indicating a downtrend)
                    (dataframe['close'] < dataframe["sma_long"]) &
                    
                    # Check if the price crossed below the low SMA within the specified rolling window
                    (dataframe['close'].rolling(window=pair_settings["cross_rolling_window"]).apply(
                        lambda x: any(qtpylib.crossed_below(
                            x, dataframe["sma_low"].iloc[x.index[0]:x.index[-1]+1]
                        )) 
                    )) &

                    # ADX is above the threshold (confirming strong trend momentum)
                    (dataframe["adx"] > pair_settings["adx_threshold"]) &
                    
                    # ATR is greater than a threshold percentage of the current price 
                    # (ensuring sufficient volatility for a meaningful trade)
                    (dataframe["atr_1d"] > dataframe["close"] * pair_settings["atr_price_threshold"]) &
                                    
                    # Ensure there is trading volume to avoid illiquid market conditions
                    (dataframe["volume"] > 0)  
                ),
                "enter_short"] = 1


            return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        # Retrieve the trading pair from metadata
        pair = metadata['pair']

        # Check if the pair has custom settings defined in self.custom_info
        if pair in self.custom_info:
            
            # Retrieve custom parameter settings for the specific trading pair
            pair_settings = self.custom_info[pair]
            
            # Define exit conditions for Long Position
            dataframe.loc[
                (
                    # Price crosses below the adjusted lower SMA (stop-loss level)
                    # This level is determined by subtracting ATR * atr_mult from the lower SMA
                    (qtpylib.crossed_below(
                        dataframe['close'], 
                        dataframe["sma_low"] - (pair_settings["atr_mult"] * dataframe["atr"])
                    )) & 
                    
                    # Ensure there is trading volume to confirm the market is active
                    (dataframe["volume"] > 0)
                ),
                "exit_long"] = 1  # Signal to exit long trades
            
            # Define exit conditions for Short Position
            dataframe.loc[
                (
                    # Price crosses above the adjusted upper SMA (stop-loss level)
                    # This level is determined by adding ATR * atr_mult to the upper SMA
                    (qtpylib.crossed_above(
                        dataframe['close'], 
                        dataframe["sma_high"] + (pair_settings["atr_mult"] * dataframe['atr'])
                    )) & 
                    
                    # Ensure there is trading volume to confirm the market is active
                    (dataframe["volume"] > 0)
                ),
                "exit_short"] = 1  # Signal to exit short trades

        
        
        return dataframe
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:

        if pair in self.custom_info:
            
            pair_settings = self.custom_info[pair]
            
            return pair_settings["leverage_level"]