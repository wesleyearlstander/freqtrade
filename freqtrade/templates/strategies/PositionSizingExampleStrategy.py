"""
Example Strategy demonstrating Advanced Position Sizing Framework

This strategy shows how to integrate the position sizing framework into your
trading strategies for better risk management and performance optimization.
"""

import logging
from datetime import datetime
from functools import reduce
from typing import Optional

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IStrategy
from freqtrade.strategy.mixins import PositionSizingMixin


logger = logging.getLogger(__name__)


class PositionSizingExampleStrategy(IStrategy, PositionSizingMixin):
    """
    Example strategy demonstrating the Position Sizing Framework
    
    This strategy:
    1. Uses standard technical indicators for entry/exit signals
    2. Implements advanced position sizing via the PositionSizingMixin
    3. Dynamically adjusts position sizes based on market conditions
    4. Shows how to customize signal strength calculation
    """
    
    # Strategy interface version
    INTERFACE_VERSION = 3
    
    # Strategy parameters
    timeframe = '1h'
    
    # ROI table
    minimal_roi = {
        "0": 0.10,
        "30": 0.05,
        "60": 0.02,
        "120": 0.01
    }
    
    # Stoploss
    stoploss = -0.10
    
    # Trailing stoploss
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = False
    
    # Optional order types
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False,
        'stoploss_on_exchange_interval': 60,
    }
    
    # Hyperoptable parameters for position sizing
    pos_sizing_method = DecimalParameter(
        0, 4, default=1, decimals=0, space="buy", optimize=True,
        load=True
    )
    
    # Strategy-specific parameters
    rsi_oversold = DecimalParameter(20, 40, default=30, space="buy", optimize=True)
    rsi_overbought = DecimalParameter(60, 80, default=70, space="sell", optimize=True)
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        
        # Position sizing method mapping
        self.sizing_methods = [
            'fixed_ratio',
            'volatility_adjusted', 
            'kelly_criterion',
            'risk_parity',
            'momentum_based'
        ]
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators and initialize position sizing
        """
        # Initialize position sizing framework
        self.init_position_sizing()
        
        # Set position sizing method based on hyperopt parameter
        method_index = int(self.pos_sizing_method.value)
        if 0 <= method_index < len(self.sizing_methods):
            method = self.sizing_methods[method_index]
            self.set_position_sizing_method(method)
            logger.info(f"Using position sizing method: {method}")
        
        # Standard technical indicators
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['macd'], dataframe['macdsignal'], dataframe['macdhist'] = ta.MACD(dataframe)
        
        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        
        # ATR for volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # Moving averages for trend
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate buy trend indicators
        """
        conditions = []
        
        # RSI oversold
        conditions.append(dataframe['rsi'] < self.rsi_oversold.value)
        
        # MACD bullish crossover
        conditions.append(
            (dataframe['macd'] > dataframe['macdsignal']) &
            (dataframe['macd'].shift(1) <= dataframe['macdsignal'].shift(1))
        )
        
        # Price above short-term SMA
        conditions.append(dataframe['close'] > dataframe['sma_20'])
        
        # Volume confirmation
        conditions.append(dataframe['volume'] > dataframe['volume_sma'] * 0.8)
        
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'
            ] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate sell trend indicators
        """
        conditions = []
        
        # RSI overbought
        conditions.append(dataframe['rsi'] > self.rsi_overbought.value)
        
        # MACD bearish crossover
        conditions.append(
            (dataframe['macd'] < dataframe['macdsignal']) &
            (dataframe['macd'].shift(1) >= dataframe['macdsignal'].shift(1))
        )
        
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'exit_long'
            ] = 1
        
        return dataframe
    
    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """
        Custom stake amount calculation using position sizing framework
        """
        try:
            # Calculate advanced position size
            optimal_stake = self.calculate_position_size(
                pair=pair,
                current_rate=current_rate,
                proposed_stake=proposed_stake,
                max_stake=max_stake,
                current_time=current_time,
                entry_tag=entry_tag,
                side=side,
                **kwargs
            )
            
            # Ensure we respect min_stake requirements
            if min_stake is not None and optimal_stake < min_stake:
                logger.debug(f"Adjusting stake from {optimal_stake:.2f} to min_stake {min_stake:.2f}")
                return min_stake
            
            return optimal_stake
            
        except Exception as e:
            logger.error(f"Error in custom_stake_amount for {pair}: {e}")
            return proposed_stake
    
    def _analyze_indicators_for_strength(self, latest_data) -> float:
        """
        Custom signal strength calculation based on multiple indicators
        
        Override the mixin's method to provide strategy-specific logic
        """
        try:
            strength = 1.0
            
            # RSI strength - stronger signals at extremes
            if hasattr(latest_data, 'rsi') and latest_data.rsi is not None:
                rsi = latest_data.rsi
                if rsi < 25:  # Very oversold
                    strength *= 1.5
                elif rsi < 35:  # Oversold
                    strength *= 1.2
                elif rsi > 75:  # Very overbought (for shorts)
                    strength *= 1.3
                elif rsi > 65:  # Overbought
                    strength *= 1.1
            
            # MACD histogram strength
            if hasattr(latest_data, 'macdhist') and latest_data.macdhist is not None:
                macd_hist = abs(latest_data.macdhist)
                # Stronger histogram = stronger signal
                if macd_hist > 0.002:
                    strength *= 1.3
                elif macd_hist > 0.001:
                    strength *= 1.1
            
            # Volume confirmation
            if (hasattr(latest_data, 'volume') and hasattr(latest_data, 'volume_sma') and
                latest_data.volume is not None and latest_data.volume_sma is not None):
                volume_ratio = latest_data.volume / latest_data.volume_sma
                if volume_ratio > 2.0:  # Very high volume
                    strength *= 1.4
                elif volume_ratio > 1.5:  # High volume
                    strength *= 1.2
                elif volume_ratio < 0.5:  # Low volume
                    strength *= 0.7
            
            # Bollinger Band position
            if (hasattr(latest_data, 'bb_upperband') and hasattr(latest_data, 'bb_lowerband') and
                hasattr(latest_data, 'close')):
                bb_upper = latest_data.bb_upperband
                bb_lower = latest_data.bb_lowerband
                close = latest_data.close
                
                if bb_upper != bb_lower:
                    bb_width = bb_upper - bb_lower
                    bb_position = (close - bb_lower) / bb_width
                    
                    # Squeeze detection (narrow bands = potential breakout)
                    if hasattr(latest_data, 'atr') and latest_data.atr is not None:
                        bb_width_norm = bb_width / close  # Normalize by price
                        atr_norm = latest_data.atr / close
                        
                        if bb_width_norm < atr_norm * 0.8:  # Squeeze condition
                            strength *= 1.2
            
            return max(0.1, min(strength, 3.0))  # Bound between 0.1 and 3.0
            
        except Exception as e:
            logger.warning(f"Error calculating signal strength: {e}")
            return 1.0
    
    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> bool:
        """
        Confirm trade entry with additional position sizing checks
        """
        try:
            # Get current position sizing info
            sizing_info = self.position_sizing_config
            
            # Log position sizing decision
            logger.info(f"Position sizing for {pair}: method={sizing_info.get('default_method', 'unknown')}, "
                       f"amount={amount:.6f}, rate={rate:.8f}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in confirm_trade_entry: {e}")
            return True