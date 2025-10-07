"""
Position Sizing Plugin Framework

This module provides extensible position sizing algorithms that can be used
independently or through the PositionSizingMixin in strategies.
"""

from freqtrade.plugins.position_sizing.position_sizing_manager import PositionSizingManager
from freqtrade.plugins.position_sizing.iposition_sizing import IPositionSizing

__all__ = ["PositionSizingManager", "IPositionSizing"]