"""
Position Sizing Mixin for Freqtrade Strategies

This mixin provides advanced position sizing capabilities that can be easily
added to any strategy by inheriting from PositionSizingMixin.
"""

import logging
from datetime import datetime
from typing import Any

import numpy as np

from freqtrade.constants import Config
from freqtrade.exceptions import OperationalException
from freqtrade.plugins.position_sizing import PositionSizingManager


logger = logging.getLogger(__name__)


class PositionSizingMixin:
    """
    Mixin class that provides advanced position sizing functionality to strategies.
    
    To use this mixin, simply inherit from it in your strategy:
    
    class MyStrategy(IStrategy, PositionSizingMixin):
        def populate_indicators(self, dataframe, metadata):
            # Enable position sizing
            self.init_position_sizing()
            return dataframe
            
        def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake, 
                               min_stake, max_stake, leverage, entry_tag, side, **kwargs):
            return self.calculate_position_size(
                pair=pair,
                current_rate=current_rate,
                proposed_stake=proposed_stake,
                max_stake=max_stake,
                **kwargs
            )
    """
    
    def init_position_sizing(self, config: Config = None) -> None:
        """
        Initialize the position sizing manager.
        Call this in your strategy's populate_indicators method.
        
        :param config: Optional config override
        """
        if not hasattr(self, '_position_sizing_manager'):
            config_to_use = config if config is not None else getattr(self, 'config', {})
            self._position_sizing_manager = PositionSizingManager(
                config=config_to_use,
                dataprovider=getattr(self, 'dp', None)
            )
            logger.info("Position sizing initialized for strategy")
    
    def calculate_position_size(
        self,
        pair: str,
        current_rate: float,
        proposed_stake: float,
        max_stake: float,
        current_time: datetime = None,
        entry_tag: str = None,
        side: str = 'long',
        signal_strength: float = None,
        method: str = None,
        **kwargs
    ) -> float:
        """
        Calculate optimal position size using configured sizing algorithm.
        
        :param pair: Trading pair
        :param current_rate: Current market price
        :param proposed_stake: Base stake amount
        :param max_stake: Maximum allowed stake
        :param current_time: Current datetime
        :param entry_tag: Entry signal tag
        :param side: Trade direction ('long' or 'short')
        :param signal_strength: Override signal strength (0.0-1.0)
        :param method: Override sizing method
        :return: Calculated stake amount
        """
        if not hasattr(self, '_position_sizing_manager'):
            logger.warning("Position sizing not initialized. Call init_position_sizing() first.")
            return proposed_stake
            
        try:
            # Calculate signal strength if not provided
            if signal_strength is None:
                signal_strength = self._calculate_signal_strength(pair, current_time)
            
            # Get the latest dataframe for this pair
            timeframe = getattr(self, 'timeframe', '1h')
            df = None
            if hasattr(self, 'dp') and self.dp is not None:
                df = self.dp.get_pair_dataframe(pair, timeframe)
            
            return self._position_sizing_manager.calculate_position_size(
                pair=pair,
                current_rate=current_rate,
                proposed_stake=proposed_stake,
                max_stake=max_stake,
                signal_strength=signal_strength,
                dataframe=df,
                method=method,
                entry_tag=entry_tag,
                side=side,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Position sizing calculation failed for {pair}: {e}")
            return proposed_stake
    
    def _calculate_signal_strength(self, pair: str, current_time: datetime = None) -> float:
        """
        Calculate signal strength based on technical indicators.
        Override this method to provide custom signal strength calculation.
        
        :param pair: Trading pair
        :param current_time: Current datetime
        :return: Signal strength (0.0 to 1.0)
        """
        try:
            # Get the latest dataframe
            timeframe = getattr(self, 'timeframe', '1h')
            if hasattr(self, 'dp') and self.dp is not None:
                df = self.dp.get_pair_dataframe(pair, timeframe)
                if df is None or df.empty:
                    return 1.0
                
                latest = df.iloc[-1]
                return self._analyze_indicators_for_strength(latest)
            
            return 1.0
            
        except Exception as e:
            logger.warning(f"Signal strength calculation failed for {pair}: {e}")
            return 1.0
    
    def _analyze_indicators_for_strength(self, latest_data: Any) -> float:
        """
        Analyze technical indicators to determine signal strength.
        Override this method to customize signal strength analysis.
        
        :param latest_data: Latest row of dataframe with indicators
        :return: Signal strength (0.0 to 1.0)
        """
        strength = 1.0
        
        try:
            # RSI-based adjustment
            if hasattr(latest_data, 'rsi') and latest_data.rsi is not None:
                rsi = latest_data.rsi
                if rsi > 70:  # Overbought - reduce strength
                    strength *= 0.7
                elif rsi < 30:  # Oversold - increase strength
                    strength *= 1.3
            
            # MACD-based adjustment
            if (hasattr(latest_data, 'macd') and hasattr(latest_data, 'macdsignal') and
                latest_data.macd is not None and latest_data.macdsignal is not None):
                macd_histogram = latest_data.macd - latest_data.macdsignal
                if abs(macd_histogram) > 0.001:  # Strong MACD signal
                    strength *= 1.2
            
            # Volume-based adjustment (if available)
            if (hasattr(latest_data, 'volume') and hasattr(latest_data, 'volume_sma') and
                latest_data.volume is not None and latest_data.volume_sma is not None):
                volume_ratio = latest_data.volume / latest_data.volume_sma
                if volume_ratio > 1.5:  # High volume confirmation
                    strength *= 1.1
                elif volume_ratio < 0.5:  # Low volume
                    strength *= 0.8
            
            # Bollinger Bands position (if available)
            if (hasattr(latest_data, 'bb_upperband') and hasattr(latest_data, 'bb_lowerband') and
                hasattr(latest_data, 'close')):
                bb_upper = latest_data.bb_upperband
                bb_lower = latest_data.bb_lowerband
                close = latest_data.close
                
                if bb_upper != bb_lower:  # Avoid division by zero
                    bb_position = (close - bb_lower) / (bb_upper - bb_lower)
                    if bb_position > 0.9 or bb_position < 0.1:  # Near extremes
                        strength *= 0.8
            
        except Exception as e:
            logger.debug(f"Error in indicator analysis: {e}")
        
        return np.clip(strength, 0.1, 2.0)
    
    def set_position_sizing_method(self, method: str) -> None:
        """
        Set the position sizing method for this strategy.
        
        :param method: Position sizing method name
        """
        if hasattr(self, '_position_sizing_manager'):
            self._position_sizing_manager.set_default_method(method)
        else:
            logger.warning("Position sizing not initialized. Call init_position_sizing() first.")
    
    def get_available_sizing_methods(self) -> list[str]:
        """
        Get list of available position sizing methods.
        
        :return: List of method names
        """
        if hasattr(self, '_position_sizing_manager'):
            return self._position_sizing_manager.get_available_methods()
        return []
    
    def add_custom_sizing_method(self, name: str, sizing_class) -> None:
        """
        Add a custom position sizing method to this strategy.
        
        :param name: Method name
        :param sizing_class: Class implementing IPositionSizing interface
        """
        if hasattr(self, '_position_sizing_manager'):
            self._position_sizing_manager.add_custom_method(name, sizing_class)
        else:
            logger.warning("Position sizing not initialized. Call init_position_sizing() first.")
    
    @property
    def position_sizing_config(self) -> dict[str, Any]:
        """Get current position sizing configuration"""
        if hasattr(self, '_position_sizing_manager'):
            return self._position_sizing_manager.get_config()
        return {}