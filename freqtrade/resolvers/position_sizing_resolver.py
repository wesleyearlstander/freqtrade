"""
Position Sizing Resolver

Dynamically loads position sizing algorithms, similar to how other Freqtrade resolvers work.
"""

import logging
from pathlib import Path
from typing import Any

from freqtrade.constants import Config, USERPATH_STRATEGIES
from freqtrade.data.dataprovider import DataProvider
from freqtrade.exceptions import OperationalException
from freqtrade.plugins.position_sizing.iposition_sizing import IPositionSizing
from freqtrade.resolvers import IResolver


logger = logging.getLogger(__name__)


class PositionSizingResolver(IResolver):
    """
    This class contains the logic to load position sizing algorithms dynamically.
    """
    
    object_type = IPositionSizing
    object_type_str = "PositionSizing"
    user_subdir = "position_sizing"
    initial_search_path = Path(__file__).parent.parent / "plugins" / "position_sizing" / "algorithms"
    
    @staticmethod
    def load_position_sizing(
        position_sizing_name: str,
        config: Config,
        dataprovider: DataProvider,
        sizing_config: dict[str, Any],
        **kwargs
    ) -> IPositionSizing:
        """
        Load the position sizing algorithm with the given name.
        
        :param position_sizing_name: Name of the position sizing algorithm
        :param config: Configuration dictionary
        :param dataprovider: DataProvider instance
        :param sizing_config: Position sizing configuration
        :return: PositionSizing instance
        """
        
        kwargs.update({
            'config': config,
            'dataprovider': dataprovider,
            'sizing_config': sizing_config
        })
        
        return PositionSizingResolver.load_object(
            position_sizing_name,
            kwargs,
            extra_dirs=config.get('position_sizing_path', [])
        )
    
    @staticmethod
    def search_all_objects(
        config: Config, 
        enum_failed: bool, 
        recursive: bool = True
    ) -> list[dict[str, Any]]:
        """
        Search for all available position sizing algorithms.
        
        :param config: Configuration dictionary
        :param enum_failed: Flag to include failed imports
        :param recursive: Flag for recursive search
        :return: List of available position sizing algorithms
        """
        extra_dirs = config.get('position_sizing_path', [])
        
        if extra_dirs:
            extra_dirs = [Path(d) for d in extra_dirs]
        
        return PositionSizingResolver._search_all_objects(
            directory=PositionSizingResolver.initial_search_path,
            enum_failed=enum_failed,
            recursive=recursive,
            extra_dirs=extra_dirs
        )
    
    @staticmethod
    def _validate_position_sizing(position_sizing: IPositionSizing) -> None:
        """
        Validate a position sizing algorithm.
        
        :param position_sizing: PositionSizing instance
        """
        if not hasattr(position_sizing, 'calculate'):
            raise OperationalException(
                f"Position sizing algorithm {position_sizing.name} must implement calculate() method"
            )
        
        if not position_sizing.validate_config():
            raise OperationalException(
                f"Position sizing algorithm {position_sizing.name} has invalid configuration"
            )