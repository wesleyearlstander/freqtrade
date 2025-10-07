"""
Position Sizing Manager

Manages and coordinates different position sizing algorithms, providing a unified
interface for calculating optimal position sizes.
"""

import logging
from typing import Any

import pandas as pd

from freqtrade.constants import Config
from freqtrade.data.dataprovider import DataProvider
from freqtrade.exceptions import OperationalException
from freqtrade.plugins.position_sizing.iposition_sizing import IPositionSizing
from freqtrade.resolvers.position_sizing_resolver import PositionSizingResolver


logger = logging.getLogger(__name__)


class PositionSizingManager:
    """
    Manages position sizing algorithms and provides a unified interface for calculating position sizes.
    """
    
    def __init__(self, config: Config, dataprovider: DataProvider = None) -> None:
        """
        Initialize the position sizing manager.
        
        :param config: Freqtrade configuration
        :param dataprovider: DataProvider instance
        """
        self._config = config
        self._dataprovider = dataprovider
        
        # Position sizing configuration
        self._sizing_config = config.get('position_sizing', {})
        self._default_method = self._sizing_config.get('method', 'fixed_ratio')
        
        # Initialize sizing algorithms
        self._sizing_methods: dict[str, IPositionSizing] = {}
        self._custom_methods: dict[str, IPositionSizing] = {}
        
        self._initialize_default_methods()
        
        logger.info(f"PositionSizingManager initialized with default method: {self._default_method}")
    
    def _initialize_default_methods(self) -> None:
        """Initialize default position sizing methods"""
        try:
            # Load built-in methods
            built_in_methods = [
                'FixedRatio',
                'VolatilityAdjusted', 
                'KellyCriterion',
                'RiskParity',
                'MomentumBased'
            ]
            
            for method_name in built_in_methods:
                try:
                    sizing_class = PositionSizingResolver.load_position_sizing(
                        method_name, 
                        config=self._config,
                        dataprovider=self._dataprovider,
                        sizing_config=self._sizing_config
                    )
                    self._sizing_methods[method_name.lower()] = sizing_class
                    logger.debug(f"Loaded position sizing method: {method_name}")
                    
                except Exception as e:
                    logger.warning(f"Failed to load position sizing method {method_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error initializing position sizing methods: {e}")
            # Fallback to ensure we always have at least one method
            self._create_fallback_method()
    
    def _create_fallback_method(self) -> None:
        """Create a fallback method if none could be loaded"""
        from freqtrade.plugins.position_sizing.algorithms.fixed_ratio import FixedRatio
        
        try:
            self._sizing_methods['fixed_ratio'] = FixedRatio(
                self._config, self._dataprovider, self._sizing_config
            )
            logger.info("Created fallback fixed_ratio position sizing method")
        except Exception as e:
            logger.error(f"Failed to create fallback method: {e}")
    
    def calculate_position_size(
        self,
        pair: str,
        current_rate: float,
        proposed_stake: float,
        max_stake: float,
        signal_strength: float = 1.0,
        method: str = None,
        dataframe: pd.DataFrame = None,
        **kwargs
    ) -> float:
        """
        Calculate optimal position size using specified method.
        
        :param pair: Trading pair
        :param current_rate: Current market price  
        :param proposed_stake: Base stake amount
        :param max_stake: Maximum allowed stake
        :param signal_strength: Signal strength (0.0-1.0)
        :param method: Position sizing method to use (optional)
        :param dataframe: OHLCV dataframe for the pair (optional)
        :return: Calculated stake amount
        """
        if method is None:
            method = self._default_method
        
        method_key = method.lower()
        
        try:
            # Check custom methods first
            if method_key in self._custom_methods:
                sizing_algo = self._custom_methods[method_key]
            elif method_key in self._sizing_methods:
                sizing_algo = self._sizing_methods[method_key]
            else:
                logger.warning(f"Unknown position sizing method: {method}, using fixed_ratio")
                method_key = 'fixed_ratio'
                sizing_algo = self._sizing_methods.get(method_key)
                
                if not sizing_algo:
                    logger.error("No position sizing methods available!")
                    return proposed_stake
            
            # Calculate position size
            calculated_size = sizing_algo.calculate(
                pair=pair,
                current_rate=current_rate,
                proposed_stake=proposed_stake,
                max_stake=max_stake,
                signal_strength=signal_strength,
                dataframe=dataframe,
                **kwargs
            )
            
            logger.debug(f"Position size calculated for {pair}: {proposed_stake:.2f} -> "
                        f"{calculated_size:.2f} (method: {method})")
            
            return calculated_size
            
        except Exception as e:
            logger.error(f"Error calculating position size for {pair} using {method}: {e}")
            return proposed_stake
    
    def set_default_method(self, method: str) -> None:
        """
        Set the default position sizing method.
        
        :param method: Method name
        """
        method_key = method.lower()
        
        if method_key in self._sizing_methods or method_key in self._custom_methods:
            self._default_method = method_key
            logger.info(f"Default position sizing method set to: {method}")
        else:
            raise OperationalException(f"Position sizing method '{method}' not found")
    
    def get_available_methods(self) -> list[str]:
        """
        Get list of available position sizing methods.
        
        :return: List of method names
        """
        methods = list(self._sizing_methods.keys()) + list(self._custom_methods.keys())
        return sorted(methods)
    
    def add_custom_method(self, name: str, sizing_class) -> None:
        """
        Add a custom position sizing method.
        
        :param name: Method name
        :param sizing_class: Instance of IPositionSizing
        """
        if not isinstance(sizing_class, IPositionSizing):
            raise OperationalException(f"Custom sizing method must implement IPositionSizing interface")
        
        method_key = name.lower()
        self._custom_methods[method_key] = sizing_class
        logger.info(f"Added custom position sizing method: {name}")
    
    def get_method_info(self, method: str = None) -> dict[str, Any]:
        """
        Get information about a position sizing method.
        
        :param method: Method name (optional, uses default if not provided)
        :return: Method information dictionary
        """
        if method is None:
            method = self._default_method
            
        method_key = method.lower()
        
        # Find the method
        sizing_algo = None
        if method_key in self._custom_methods:
            sizing_algo = self._custom_methods[method_key]
        elif method_key in self._sizing_methods:
            sizing_algo = self._sizing_methods[method_key]
        
        if not sizing_algo:
            return {}
        
        return {
            'name': sizing_algo.name,
            'description': sizing_algo.description(),
            'parameter_space': sizing_algo.parameter_space(),
            'is_custom': method_key in self._custom_methods
        }
    
    def get_config(self) -> dict[str, Any]:
        """
        Get current configuration.
        
        :return: Configuration dictionary
        """
        return {
            'default_method': self._default_method,
            'available_methods': self.get_available_methods(),
            'sizing_config': self._sizing_config.copy()
        }