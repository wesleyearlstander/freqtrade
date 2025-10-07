"""
Interface for position sizing algorithms

All position sizing algorithms must implement this interface to be used
within the Freqtrade position sizing framework.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from freqtrade.constants import Config
from freqtrade.data.dataprovider import DataProvider


logger = logging.getLogger(__name__)


class IPositionSizing(ABC):
    """
    Interface for position sizing algorithms.
    
    All position sizing methods must inherit from this class and implement the calculate method.
    """
    
    def __init__(
        self,
        config: Config,
        dataprovider: DataProvider,
        sizing_config: dict[str, Any]
    ) -> None:
        """
        Initialize the position sizing algorithm.
        
        :param config: Freqtrade configuration
        :param dataprovider: DataProvider instance
        :param sizing_config: Position sizing specific configuration
        """
        self._config = config
        self._dataprovider = dataprovider
        self._sizing_config = sizing_config
        
        # Common configuration with defaults
        self.max_position_size_pct = sizing_config.get('max_position_size_pct', 0.1)
        self.min_position_size_pct = sizing_config.get('min_position_size_pct', 0.01)
    
    @property
    def name(self) -> str:
        """
        Returns the name of the position sizing algorithm
        """
        return self.__class__.__name__
    
    @abstractmethod
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
        Calculate the position size for a trade.
        
        :param pair: Trading pair
        :param current_rate: Current market price
        :param proposed_stake: Base stake amount from strategy
        :param max_stake: Maximum allowed stake
        :param signal_strength: Signal strength (0.0-1.0)
        :param dataframe: OHLCV dataframe for the pair (optional)
        :return: Calculated stake amount
        """
        pass
    
    @staticmethod
    @abstractmethod
    def parameter_space() -> dict[str, Any]:
        """
        Define the parameter space for this position sizing method.
        Used for optimization and configuration validation.
        
        :return: Dictionary defining parameter space
        """
        pass
    
    @staticmethod
    def description() -> str:
        """
        Return a description of this position sizing method.
        """
        return "Position sizing algorithm"
    
    def validate_config(self) -> bool:
        """
        Validate the configuration for this position sizing method.
        
        :return: True if configuration is valid
        """
        try:
            if not 0 < self.min_position_size_pct <= self.max_position_size_pct <= 1.0:
                logger.error(f"Invalid position size percentages: "
                           f"min={self.min_position_size_pct}, max={self.max_position_size_pct}")
                return False
            return True
        except Exception as e:
            logger.error(f"Configuration validation failed for {self.name}: {e}")
            return False
    
    def log_once(self, logmethod, message: str) -> None:
        """
        Send a log message, but only once per running instance.
        """
        if not hasattr(self, '_log_cache'):
            self._log_cache = set()
        
        if message not in self._log_cache:
            logmethod(f"{self.name}: {message}")
            self._log_cache.add(message)
    
    def _apply_constraints(self, position_size: float, max_stake: float) -> float:
        """
        Apply safety constraints to position size
        
        :param position_size: Calculated position size
        :param max_stake: Maximum allowed stake
        :return: Constrained position size
        """
        # Apply percentage-based limits
        max_allowed = max_stake * self.max_position_size_pct
        min_allowed = max_stake * self.min_position_size_pct
        
        # Ensure position is within bounds
        constrained_size = max(min_allowed, min(position_size, max_allowed))
        
        # Final safety check - never exceed max_stake
        constrained_size = min(constrained_size, max_stake)
        
        return constrained_size