"""
Momentum Based Position Sizing

Adjusts position sizes based on recent price momentum and trend strength.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from freqtrade.plugins.position_sizing.iposition_sizing import IPositionSizing


logger = logging.getLogger(__name__)


class MomentumBased(IPositionSizing):
    """
    Momentum-based position sizing algorithm.
    
    Increases position size during strong trends and reduces during
    weak or choppy market conditions.
    """
    
    def __init__(self, config, dataprovider, sizing_config):
        super().__init__(config, dataprovider, sizing_config)
        
        self.momentum_lookback = sizing_config.get('momentum_lookback_periods', 10)
        self.trend_lookback = sizing_config.get('trend_lookback_periods', 20)
        self.min_momentum_multiplier = sizing_config.get('min_momentum_multiplier', 0.5)
        self.max_momentum_multiplier = sizing_config.get('max_momentum_multiplier', 2.0)
        
        logger.debug(f"MomentumBased initialized: momentum_lookback={self.momentum_lookback}, "
                    f"trend_lookback={self.trend_lookback}")
    
    def calculate(
        self,
        pair: str,
        current_rate: float,
        proposed_stake: float,
        max_stake: float,
        signal_strength: float,
        dataframe: pd.DataFrame = None,
        **kwargs
    ) -> float:
        """
        Calculate position size based on momentum.
        
        :param pair: Trading pair
        :param current_rate: Current market price
        :param proposed_stake: Base stake amount
        :param max_stake: Maximum allowed stake
        :param signal_strength: Signal strength (0.0-1.0)
        :param dataframe: OHLCV dataframe for momentum calculation
        :return: Momentum-adjusted stake amount
        """
        if dataframe is None or dataframe.empty:
            logger.debug(f"No dataframe provided for {pair}, using proposed stake")
            return self._apply_constraints(proposed_stake * signal_strength, max_stake)
        
        # Calculate momentum adjustment
        momentum_multiplier = self._calculate_momentum_multiplier(dataframe)
        
        # Apply momentum adjustment
        adjusted_stake = proposed_stake * momentum_multiplier * signal_strength
        
        # Apply constraints
        final_stake = self._apply_constraints(adjusted_stake, max_stake)
        
        logger.debug(f"MomentumBased for {pair}: {proposed_stake:.2f} -> {final_stake:.2f} "
                    f"(momentum: {momentum_multiplier:.3f}, strength: {signal_strength:.2f})")
        
        return final_stake
    
    def _calculate_momentum_multiplier(self, dataframe: pd.DataFrame) -> float:
        """
        Calculate momentum-based multiplier.
        
        :param dataframe: OHLCV dataframe
        :return: Momentum multiplier
        """
        try:
            required_length = max(self.momentum_lookback, self.trend_lookback)
            if len(dataframe) < required_length:
                return 1.0
            
            closes = dataframe['close']
            
            # Short-term momentum (price change)
            short_momentum = (closes.iloc[-1] / closes.iloc[-self.momentum_lookback]) - 1
            
            # Long-term trend strength (linear regression slope)
            trend_strength = self._calculate_trend_strength(closes)
            
            # Volatility normalization
            returns = closes.pct_change().dropna()
            if len(returns) >= self.momentum_lookback:
                volatility = returns.rolling(window=self.momentum_lookback).std().iloc[-1]
            else:
                volatility = 0.02  # Default volatility
            
            # Normalize momentum by volatility
            if volatility > 0:
                normalized_momentum = short_momentum / volatility
            else:
                normalized_momentum = 0
            
            # Combine momentum and trend
            combined_score = (normalized_momentum * 0.7) + (trend_strength * 0.3)
            
            # Convert to multiplier using tanh for smooth scaling
            momentum_multiplier = 1.0 + np.tanh(combined_score) * 0.5
            
            # Apply bounds
            momentum_multiplier = np.clip(
                momentum_multiplier,
                self.min_momentum_multiplier,
                self.max_momentum_multiplier
            )
            
            logger.debug(f"Momentum calculation: short_mom={short_momentum:.4f}, "
                        f"trend={trend_strength:.4f}, multiplier={momentum_multiplier:.3f}")
            
            return momentum_multiplier
            
        except Exception as e:
            logger.warning(f"Error calculating momentum multiplier: {e}")
            return 1.0
    
    def _calculate_trend_strength(self, prices: pd.Series) -> float:
        """
        Calculate trend strength using linear regression slope.
        
        :param prices: Price series
        :return: Normalized trend strength
        """
        try:
            if len(prices) < self.trend_lookback:
                return 0.0
            
            # Use last N periods for trend calculation
            trend_prices = prices.tail(self.trend_lookback).values
            x = np.arange(len(trend_prices))
            
            # Linear regression
            coeffs = np.polyfit(x, trend_prices, 1)
            slope = coeffs[0]
            
            # Normalize by average price
            avg_price = np.mean(trend_prices)
            if avg_price > 0:
                normalized_slope = slope / avg_price * self.trend_lookback
            else:
                normalized_slope = 0
            
            return normalized_slope
            
        except Exception as e:
            logger.debug(f"Error calculating trend strength: {e}")
            return 0.0
    
    @staticmethod
    def parameter_space() -> dict[str, Any]:
        """Define parameter space for optimization"""
        return {
            'momentum_lookback_periods': {
                'type': 'int',
                'low': 5,
                'high': 20,
                'default': 10,
                'space': 'uniform',
                'optimize': True
            },
            'trend_lookback_periods': {
                'type': 'int',
                'low': 10,
                'high': 50,
                'default': 20,
                'space': 'uniform',
                'optimize': True
            },
            'min_momentum_multiplier': {
                'type': 'real',
                'low': 0.2,
                'high': 0.8,
                'default': 0.5,
                'space': 'uniform',
                'optimize': False
            },
            'max_momentum_multiplier': {
                'type': 'real',
                'low': 1.5,
                'high': 3.0,
                'default': 2.0,
                'space': 'uniform',
                'optimize': False
            }
        }
    
    @staticmethod
    def description() -> str:
        return "Adjusts position size based on price momentum and trend strength"