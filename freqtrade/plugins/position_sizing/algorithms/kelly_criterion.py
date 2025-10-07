"""
Kelly Criterion Position Sizing

Optimal position sizing based on the Kelly Criterion using historical trade performance.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from freqtrade.persistence import Trade
from freqtrade.plugins.position_sizing.iposition_sizing import IPositionSizing


logger = logging.getLogger(__name__)


class KellyCriterion(IPositionSizing):
    """
    Kelly Criterion position sizing algorithm.
    
    Calculates optimal position size based on historical win rate and 
    average win/loss ratios for the specific pair.
    """
    
    def __init__(self, config, dataprovider, sizing_config):
        super().__init__(config, dataprovider, sizing_config)
        
        self.min_trades_required = sizing_config.get('min_trades_required', 10)
        self.max_lookback_trades = sizing_config.get('max_lookback_trades', 50)
        self.kelly_fraction = sizing_config.get('kelly_fraction', 0.25)  # Conservative
        self.min_kelly_fraction = sizing_config.get('min_kelly_fraction', 0.01)
        self.max_kelly_fraction = sizing_config.get('max_kelly_fraction', 0.5)
        
        logger.debug(f"KellyCriterion initialized: min_trades={self.min_trades_required}, "
                    f"kelly_fraction={self.kelly_fraction}")
    
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
        Calculate position size using Kelly Criterion.
        
        :param pair: Trading pair
        :param current_rate: Current market price
        :param proposed_stake: Base stake amount  
        :param max_stake: Maximum allowed stake
        :param signal_strength: Signal strength (0.0-1.0)
        :param dataframe: OHLCV dataframe (unused in this method)
        :return: Kelly-optimized stake amount
        """
        try:
            # Get recent trade history for this pair
            kelly_fraction = self._calculate_kelly_fraction(pair)
            
            if kelly_fraction <= 0:
                # No profitable edge detected, use minimal position
                adjusted_stake = proposed_stake * 0.5 * signal_strength
            else:
                # Apply Kelly fraction to max stake
                adjusted_stake = max_stake * kelly_fraction * signal_strength
            
            # Apply constraints
            final_stake = self._apply_constraints(adjusted_stake, max_stake)
            
            logger.debug(f"KellyCriterion for {pair}: kelly_fraction={kelly_fraction:.3f}, "
                        f"stake: {proposed_stake:.2f} -> {final_stake:.2f}")
            
            return final_stake
            
        except Exception as e:
            logger.warning(f"Error in Kelly criterion calculation for {pair}: {e}")
            return self._apply_constraints(proposed_stake * signal_strength, max_stake)
    
    def _calculate_kelly_fraction(self, pair: str) -> float:
        """
        Calculate Kelly fraction based on historical trades for the pair.
        
        :param pair: Trading pair
        :return: Kelly fraction (0.0 to 1.0)
        """
        try:
            # Get recent closed trades for this pair
            recent_trades = Trade.get_trades_proxy(pair=pair, is_open=False)
            
            if len(recent_trades) < self.min_trades_required:
                logger.debug(f"Insufficient trade history for {pair}: {len(recent_trades)} trades "
                           f"(minimum: {self.min_trades_required})")
                return 0.0
            
            # Use only the most recent trades
            trades_to_analyze = recent_trades[-self.max_lookback_trades:]
            
            # Extract profit ratios
            profit_ratios = []
            for trade in trades_to_analyze:
                if trade.profit_ratio is not None:
                    profit_ratios.append(trade.profit_ratio)
            
            if len(profit_ratios) < self.min_trades_required:
                return 0.0
            
            returns = np.array(profit_ratios)
            
            # Calculate win rate and average returns
            winning_trades = returns[returns > 0]
            losing_trades = returns[returns < 0]
            
            if len(winning_trades) == 0 or len(losing_trades) == 0:
                # Need both wins and losses for Kelly calculation
                return 0.0
            
            win_rate = len(winning_trades) / len(returns)
            avg_win = np.mean(winning_trades)
            avg_loss = abs(np.mean(losing_trades))  # Make positive
            
            # Kelly formula: f = (bp - q) / b
            # where b = odds received on the winning bet (avg_win/avg_loss)
            #       p = probability of winning (win_rate)
            #       q = probability of losing (1 - win_rate)
            
            if avg_loss == 0:
                return 0.0
            
            b = avg_win / avg_loss  # Win/loss ratio
            p = win_rate
            q = 1 - win_rate
            
            kelly_fraction = (b * p - q) / b
            
            # Apply conservative scaling
            kelly_fraction = kelly_fraction * self.kelly_fraction
            
            # Apply bounds
            kelly_fraction = np.clip(
                kelly_fraction,
                self.min_kelly_fraction,
                self.max_kelly_fraction
            )
            
            logger.debug(f"Kelly calculation for {pair}: win_rate={win_rate:.3f}, "
                        f"win/loss_ratio={b:.3f}, kelly_fraction={kelly_fraction:.3f}")
            
            return max(0.0, kelly_fraction)
            
        except Exception as e:
            logger.warning(f"Error calculating Kelly fraction for {pair}: {e}")
            return 0.0
    
    @staticmethod
    def parameter_space() -> dict[str, Any]:
        """Define parameter space for optimization"""
        return {
            'min_trades_required': {
                'type': 'int',
                'low': 5,
                'high': 30,
                'default': 10,
                'space': 'uniform',
                'optimize': False
            },
            'max_lookback_trades': {
                'type': 'int',
                'low': 20,
                'high': 100,
                'default': 50,
                'space': 'uniform',
                'optimize': True
            },
            'kelly_fraction': {
                'type': 'real',
                'low': 0.1,
                'high': 0.5,
                'default': 0.25,
                'space': 'uniform',
                'optimize': True
            },
            'max_kelly_fraction': {
                'type': 'real',
                'low': 0.3,
                'high': 0.8,
                'default': 0.5,
                'space': 'uniform',
                'optimize': False
            }
        }
    
    @staticmethod
    def description() -> str:
        return "Optimal position sizing using Kelly Criterion based on historical trade performance"