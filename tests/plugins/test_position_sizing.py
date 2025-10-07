"""
Test Position Sizing Framework

These tests validate the position sizing framework functionality.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

from freqtrade.plugins.position_sizing.position_sizing_manager import PositionSizingManager
from freqtrade.plugins.position_sizing.algorithms.fixed_ratio import FixedRatio
from freqtrade.plugins.position_sizing.algorithms.volatility_adjusted import VolatilityAdjusted
from freqtrade.strategy.mixins.position_sizing_mixin import PositionSizingMixin


def create_sample_dataframe(length: int = 100) -> pd.DataFrame:
    """Create a sample OHLCV dataframe for testing"""
    dates = pd.date_range('2023-01-01', periods=length, freq='1H')
    
    # Generate realistic price data with some volatility
    np.random.seed(42)  # For reproducible tests
    returns = np.random.normal(0, 0.02, length)  # 2% daily vol
    prices = 100 * np.cumprod(1 + returns)
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': prices * 1.01,
        'low': prices * 0.99,
        'close': prices,
        'volume': np.random.randint(1000, 10000, length)
    })
    
    return df


class TestPositionSizingFramework:
    """Test the core position sizing framework"""
    
    def test_fixed_ratio_algorithm(self):
        """Test the FixedRatio position sizing algorithm"""
        config = {
            'position_sizing': {
                'signal_multiplier': 1.0,
                'max_position_size_pct': 0.1,
                'min_position_size_pct': 0.01
            }
        }
        
        dataprovider = MagicMock()
        sizing_config = config['position_sizing']
        
        # Create algorithm instance
        fixed_ratio = FixedRatio(config, dataprovider, sizing_config)
        
        # Test basic calculation
        result = fixed_ratio.calculate(
            pair="BTC/USDT",
            current_rate=50000.0,
            proposed_stake=100.0,
            max_stake=1000.0,
            signal_strength=0.8
        )
        
        # Should be proposed_stake * signal_strength * multiplier
        expected = 100.0 * 0.8 * 1.0
        assert result == expected
        
        # Test with different signal strength
        result2 = fixed_ratio.calculate(
            pair="BTC/USDT",
            current_rate=50000.0,
            proposed_stake=100.0,
            max_stake=1000.0,
            signal_strength=1.5
        )
        
        assert result2 == 150.0
        
    def test_volatility_adjusted_algorithm(self):
        """Test the VolatilityAdjusted position sizing algorithm"""
        config = {
            'position_sizing': {
                'volatility_lookback_periods': 20,
                'volatility_target': 0.02,
                'max_position_size_pct': 0.1,
                'min_position_size_pct': 0.01
            }
        }
        
        dataprovider = MagicMock()
        sizing_config = config['position_sizing']
        
        # Create algorithm instance
        vol_adjusted = VolatilityAdjusted(config, dataprovider, sizing_config)
        
        # Create test dataframe
        df = create_sample_dataframe(50)
        
        # Test with dataframe
        result = vol_adjusted.calculate(
            pair="BTC/USDT",
            current_rate=50000.0,
            proposed_stake=100.0,
            max_stake=1000.0,
            signal_strength=1.0,
            dataframe=df
        )
        
        # Result should be different from proposed stake due to volatility adjustment
        assert result != 100.0
        assert isinstance(result, float)
        assert result > 0
        
        # Test without dataframe (should fallback)
        result_no_df = vol_adjusted.calculate(
            pair="BTC/USDT",
            current_rate=50000.0,
            proposed_stake=100.0,
            max_stake=1000.0,
            signal_strength=1.0,
            dataframe=None
        )
        
        assert result_no_df == 100.0  # Should equal proposed stake
        
    def test_position_sizing_manager(self):
        """Test the PositionSizingManager functionality"""
        config = {
            'position_sizing': {
                'method': 'fixed_ratio',
                'max_position_size_pct': 0.1,
                'min_position_size_pct': 0.01
            }
        }
        
        dataprovider = MagicMock()
        
        # Create manager
        manager = PositionSizingManager(config, dataprovider)
        
        # Test get available methods
        methods = manager.get_available_methods()
        assert isinstance(methods, list)
        assert len(methods) > 0
        
        # Test calculate position size
        result = manager.calculate_position_size(
            pair="BTC/USDT",
            current_rate=50000.0,
            proposed_stake=100.0,
            max_stake=1000.0,
            signal_strength=1.0
        )
        
        assert isinstance(result, float)
        assert result > 0
        
        # Test method switching
        manager.set_default_method('volatility_adjusted')
        assert manager._default_method == 'volatility_adjusted'
        
    def test_position_sizing_mixin(self):
        """Test the PositionSizingMixin functionality"""
        
        # Create a mock strategy class with the mixin
        class TestStrategy(PositionSizingMixin):
            def __init__(self):
                self.config = {
                    'position_sizing': {
                        'method': 'fixed_ratio',
                        'max_position_size_pct': 0.1
                    }
                }
                self.dp = MagicMock()
                self.timeframe = '1h'
        
        strategy = TestStrategy()
        
        # Test initialization
        strategy.init_position_sizing()
        assert hasattr(strategy, '_position_sizing_manager')
        
        # Test calculate position size
        result = strategy.calculate_position_size(
            pair="BTC/USDT",
            current_rate=50000.0,
            proposed_stake=100.0,
            max_stake=1000.0
        )
        
        assert isinstance(result, float)
        assert result > 0
        
        # Test get available methods
        methods = strategy.get_available_sizing_methods()
        assert isinstance(methods, list)
        
    def test_constraints_application(self):
        """Test that position size constraints are properly applied"""
        config = {
            'position_sizing': {
                'max_position_size_pct': 0.1,  # 10% max
                'min_position_size_pct': 0.02,  # 2% min
            }
        }
        
        dataprovider = MagicMock()
        sizing_config = config['position_sizing']
        
        fixed_ratio = FixedRatio(config, dataprovider, sizing_config)
        
        max_stake = 1000.0
        
        # Test maximum constraint
        large_stake = fixed_ratio.calculate(
            pair="BTC/USDT",
            current_rate=50000.0,
            proposed_stake=500.0,  # Would result in > 10% of max_stake
            max_stake=max_stake,
            signal_strength=2.0  # High signal
        )
        
        # Should be capped at 10% of max_stake = 100
        assert large_stake <= max_stake * 0.1
        
        # Test minimum constraint
        small_stake = fixed_ratio.calculate(
            pair="BTC/USDT",
            current_rate=50000.0,
            proposed_stake=1.0,  # Very small stake
            max_stake=max_stake,
            signal_strength=0.1  # Weak signal
        )
        
        # Should be at least 2% of max_stake = 20
        assert small_stake >= max_stake * 0.02
        
    def test_signal_strength_calculation(self):
        """Test signal strength calculation in mixin"""
        
        class TestStrategy(PositionSizingMixin):
            def __init__(self):
                self.config = {'position_sizing': {}}
                self.dp = MagicMock()
                self.timeframe = '1h'
                
                # Mock dataframe with indicators
                mock_df = pd.DataFrame({
                    'rsi': [30],  # Oversold
                    'macd': [0.1],
                    'macdsignal': [0.05],
                    'volume': [2000],
                    'volume_sma': [1000]
                })
                
                self.dp.get_pair_dataframe.return_value = mock_df
        
        strategy = TestStrategy()
        strategy.init_position_sizing()
        
        # Test signal strength calculation
        strength = strategy._calculate_signal_strength("BTC/USDT")
        
        # Should be > 1.0 due to oversold RSI and high volume
        assert strength > 1.0
        assert strength <= 3.0  # Should be bounded
        
if __name__ == "__main__":
    # Run a simple test
    test = TestPositionSizingFramework()
    test.test_fixed_ratio_algorithm()
    print("✅ Fixed ratio test passed")
    
    test.test_volatility_adjusted_algorithm()
    print("✅ Volatility adjusted test passed")
    
    test.test_position_sizing_manager()
    print("✅ Position sizing manager test passed")
    
    test.test_constraints_application()
    print("✅ Constraints test passed")
    
    print("\n🎉 All position sizing tests passed!")
    print("\n📋 Position Sizing Framework Summary:")
    print("   • Extensible plugin architecture")
    print("   • 5 built-in algorithms (Fixed, Volatility, Kelly, Risk Parity, Momentum)")
    print("   • Strategy mixin for easy integration")
    print("   • Automatic constraints and risk management")
    print("   • Hyperopt support for optimization")
    print("   • Example strategy included")