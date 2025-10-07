"""
Fixed Ratio Position Sizing

Simple position sizing that adjusts the proposed stake based on signal strength.
"""

import logging
from typing import Any

import pandas as pd

from freqtrade.plugins.position_sizing.iposition_sizing import IPositionSizing


logger = logging.getLogger(__name__)


class FixedRatio(IPositionSizing):
    """
    Fixed ratio position sizing with signal strength adjustment.
    
    This is the simplest form of position sizing that maintains a consistent
    ratio but adjusts based on signal strength.
    """
    
    def __init__(self, config, dataprovider, sizing_config):
        super().__init__(config, dataprovider, sizing_config)
        
        self.signal_multiplier = sizing_config.get('signal_multiplier', 1.0)
        logger.debug(f"FixedRatio initialized with multiplier: {self.signal_multiplier}")
    
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
        Calculate position size using fixed ratio method.
        
        :param pair: Trading pair
        :param current_rate: Current market price
        :param proposed_stake: Base stake amount
        :param max_stake: Maximum allowed stake
        :param signal_strength: Signal strength (0.0-1.0)
        :param dataframe: OHLCV dataframe (unused in this method)
        :return: Adjusted stake amount
        """
        # Simple multiplication by signal strength and configured multiplier
        adjusted_stake = proposed_stake * signal_strength * self.signal_multiplier
        
        # Apply constraints
        final_stake = self._apply_constraints(adjusted_stake, max_stake)
        
        logger.debug(f"FixedRatio for {pair}: {proposed_stake:.2f} -> {final_stake:.2f} "
                    f"(strength: {signal_strength:.2f})")
        
        return final_stake
    
    @staticmethod
    def parameter_space() -> dict[str, Any]:
        """Define parameter space for optimization"""
        return {
            'signal_multiplier': {
                'type': 'real',
                'low': 0.1,
                'high': 3.0,
                'default': 1.0,
                'space': 'uniform',
                'optimize': True
            },
            'max_position_size_pct': {
                'type': 'real', 
                'low': 0.01,
                'high': 0.5,
                'default': 0.1,
                'space': 'uniform',
                'optimize': False
            }
        }
    
    @staticmethod
    def description() -> str:
        return "Fixed ratio position sizing with signal strength adjustment"