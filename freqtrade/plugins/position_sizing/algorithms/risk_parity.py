"""
Risk Parity Position Sizing

Adjusts position sizes to achieve equal risk contribution across positions.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from freqtrade.plugins.position_sizing.iposition_sizing import IPositionSizing


logger = logging.getLogger(__name__)


class RiskParity(IPositionSizing):
    """
    Risk parity position sizing algorithm.
    
    Allocates capital such that each position contributes equally to portfolio risk,
    rather than equal dollar amounts.
    """
    
    def __init__(self, config, dataprovider, sizing_config):
        super().__init__(config, dataprovider, sizing_config)
        
        self.volatility_lookback = sizing_config.get('volatility_lookback_periods', 20)
        self.target_risk = sizing_config.get('target_risk_per_trade', 0.02)  # 2% risk per trade
        
        logger.debug(f"RiskParity initialized: lookback={self.volatility_lookback}, "
                    f"target_risk={self.target_risk}")
    
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
        Calculate position size for equal risk contribution.
        
        :param pair: Trading pair
        :param current_rate: Current market price
        :param proposed_stake: Base stake amount
        :param max_stake: Maximum allowed stake  
        :param signal_strength: Signal strength (0.0-1.0)
        :param dataframe: OHLCV dataframe for risk calculation
        :return: Risk-adjusted stake amount
        """
        if dataframe is None or dataframe.empty:
            logger.debug(f"No dataframe provided for {pair}, using proposed stake")
            return self._apply_constraints(proposed_stake * signal_strength, max_stake)
        
        # Calculate risk-adjusted position size
        risk_adjusted_size = self._calculate_risk_parity_size(
            dataframe, proposed_stake, max_stake, signal_strength
        )
        
        # Apply constraints
        final_stake = self._apply_constraints(risk_adjusted_size, max_stake)
        
        logger.debug(f"RiskParity for {pair}: {proposed_stake:.2f} -> {final_stake:.2f} "
                    f"(strength: {signal_strength:.2f})")
        
        return final_stake
    
    def _calculate_risk_parity_size(
        self,
        dataframe: pd.DataFrame,
        proposed_stake: float,
        max_stake: float,
        signal_strength: float
    ) -> float:
        """
        Calculate position size for target risk level.
        
        :param dataframe: OHLCV dataframe
        :param proposed_stake: Base stake amount
        :param max_stake: Maximum stake
        :param signal_strength: Signal strength
        :return: Risk-adjusted position size
        """
        try:
            if len(dataframe) < self.volatility_lookback:
                return proposed_stake * signal_strength
            
            # Calculate asset volatility
            returns = dataframe['close'].pct_change().dropna()
            
            if len(returns) < 2:
                return proposed_stake * signal_strength
            
            # Rolling volatility
            lookback_periods = min(self.volatility_lookback, len(returns))
            volatility = returns.rolling(window=lookback_periods).std().iloc[-1]
            
            if volatility <= 0 or np.isnan(volatility):
                return proposed_stake * signal_strength
            
            # Calculate position size for target risk
            # Risk = Position_Size * Volatility
            # Position_Size = Target_Risk / Volatility
            target_position_size = (self.target_risk / volatility) * max_stake
            
            # Apply signal strength
            adjusted_size = target_position_size * signal_strength
            
            logger.debug(f"Risk parity calculation: volatility={volatility:.4f}, "
                        f"target_size={target_position_size:.2f}")
            
            return adjusted_size
            
        except Exception as e:
            logger.warning(f"Error in risk parity calculation: {e}")
            return proposed_stake * signal_strength
    
    @staticmethod
    def parameter_space() -> dict[str, Any]:
        """Define parameter space for optimization"""
        return {
            'volatility_lookback_periods': {
                'type': 'int',
                'low': 10,
                'high': 50,
                'default': 20,
                'space': 'uniform',
                'optimize': True
            },
            'target_risk_per_trade': {
                'type': 'real',
                'low': 0.005,
                'high': 0.05,
                'default': 0.02,
                'space': 'uniform',
                'optimize': True
            }
        }
    
    @staticmethod
    def description() -> str:
        return "Risk parity position sizing for equal risk contribution across positions"