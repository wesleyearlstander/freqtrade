"""
Volatility Adjusted Position Sizing

Adjusts position sizes based on market volatility to maintain consistent risk exposure.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from freqtrade.plugins.position_sizing.iposition_sizing import IPositionSizing


logger = logging.getLogger(__name__)


class VolatilityAdjusted(IPositionSizing):
    """
    Volatility-adjusted position sizing.
    
    Reduces position size during high volatility periods and increases during
    low volatility to maintain consistent risk exposure.
    """
    
    def __init__(self, config, dataprovider, sizing_config):
        super().__init__(config, dataprovider, sizing_config)
        
        self.volatility_lookback = sizing_config.get('volatility_lookback_periods', 20)
        self.volatility_target = sizing_config.get('volatility_target', 0.02)  # 2% daily
        self.min_volatility_adjustment = sizing_config.get('min_volatility_adjustment', 0.2)
        self.max_volatility_adjustment = sizing_config.get('max_volatility_adjustment', 3.0)
        
        logger.debug(f"VolatilityAdjusted initialized: lookback={self.volatility_lookback}, "
                    f"target={self.volatility_target}")
    
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
        Calculate position size adjusted for volatility.
        
        :param pair: Trading pair
        :param current_rate: Current market price  
        :param proposed_stake: Base stake amount
        :param max_stake: Maximum allowed stake
        :param signal_strength: Signal strength (0.0-1.0)
        :param dataframe: OHLCV dataframe for volatility calculation
        :return: Volatility-adjusted stake amount
        """
        if dataframe is None or dataframe.empty:
            logger.debug(f"No dataframe provided for {pair}, using proposed stake")
            return self._apply_constraints(proposed_stake * signal_strength, max_stake)
        
        # Calculate realized volatility
        volatility_adjustment = self._calculate_volatility_adjustment(dataframe)
        
        # Apply volatility adjustment
        adjusted_stake = proposed_stake * volatility_adjustment * signal_strength
        
        # Apply constraints
        final_stake = self._apply_constraints(adjusted_stake, max_stake)
        
        logger.debug(f"VolatilityAdjusted for {pair}: {proposed_stake:.2f} -> {final_stake:.2f} "
                    f"(vol_adj: {volatility_adjustment:.3f}, strength: {signal_strength:.2f})")
        
        return final_stake
    
    def _calculate_volatility_adjustment(self, dataframe: pd.DataFrame) -> float:
        """
        Calculate volatility adjustment factor.
        
        :param dataframe: OHLCV dataframe
        :return: Volatility adjustment factor
        """
        try:
            if len(dataframe) < self.volatility_lookback:
                return 1.0
            
            # Calculate returns
            returns = dataframe['close'].pct_change().dropna()
            
            if len(returns) < 2:
                return 1.0
            
            # Calculate rolling volatility
            lookback_periods = min(self.volatility_lookback, len(returns))
            volatility = returns.rolling(window=lookback_periods).std().iloc[-1]
            
            if volatility <= 0 or np.isnan(volatility):
                return 1.0
            
            # Calculate adjustment: target_vol / actual_vol
            adjustment = self.volatility_target / volatility
            
            # Apply bounds to prevent extreme adjustments
            adjustment = np.clip(
                adjustment,
                self.min_volatility_adjustment,
                self.max_volatility_adjustment
            )
            
            return adjustment
            
        except Exception as e:
            logger.warning(f"Error calculating volatility adjustment: {e}")
            return 1.0
    
    @staticmethod
    def parameter_space() -> dict[str, Any]:
        """Define parameter space for optimization"""
        return {
            'volatility_lookback_periods': {
                'type': 'int',
                'low': 5,
                'high': 50,
                'default': 20,
                'space': 'uniform',
                'optimize': True
            },
            'volatility_target': {
                'type': 'real',
                'low': 0.005,
                'high': 0.05,
                'default': 0.02,
                'space': 'uniform', 
                'optimize': True
            },
            'min_volatility_adjustment': {
                'type': 'real',
                'low': 0.1,
                'high': 0.5,
                'default': 0.2,
                'space': 'uniform',
                'optimize': False
            },
            'max_volatility_adjustment': {
                'type': 'real',
                'low': 2.0,
                'high': 5.0,
                'default': 3.0,
                'space': 'uniform',
                'optimize': False
            }
        }
    
    @staticmethod
    def description() -> str:
        return "Adjusts position size inversely to market volatility for consistent risk exposure"