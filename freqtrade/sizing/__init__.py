"""
Advanced Position Sizing Framework for Freqtrade

This module provides sophisticated position sizing algorithms that can be easily
integrated into trading strategies for better risk management and performance optimization.
"""

from freqtrade.sizing.position_sizer import PositionSizer
from freqtrade.sizing.risk_manager import RiskManager
from freqtrade.sizing.market_regime import MarketRegimeDetector

__all__ = ["PositionSizer", "RiskManager", "MarketRegimeDetector"]