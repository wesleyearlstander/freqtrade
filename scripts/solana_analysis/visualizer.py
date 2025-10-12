"""
Visualization components for Solana meme coin analysis
Provides interactive charts and visualizations for wave analysis
"""

import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo

from config import AnalysisConfig
from wave_detector import Wave
from fibonacci import FibonacciAnalyzer


logger = logging.getLogger(__name__)


class Visualizer:
    """Visualization components for analysis results"""
    
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.fib_analyzer = FibonacciAnalyzer(config)
        
        # Set matplotlib style
        plt.style.use(config.visualization.get("style", "seaborn-v0_8"))
        
        # Set default figure size
        self.default_figure_size = config.visualization.get("default_figure_size", (12, 8))
        self.dpi = config.visualization.get("dpi", 100)
    
    def visualize_coin(
        self,
        symbol: str,
        df: pd.DataFrame,
        waves: List[Wave],
        timeframe: str,
        show_waves: bool = True,
        show_fib: bool = True,
        output: Optional[str] = None
    ) -> None:
        """
        Visualize a specific coin with price chart, waves, and Fibonacci levels
        
        Args:
            symbol: Coin symbol
            df: OHLCV DataFrame
            waves: List of detected waves
            timeframe: Timeframe for the chart
            show_waves: Whether to show wave annotations
            show_fib: Whether to show Fibonacci levels
            output: Output file path (optional)
        """
        # Create figure with subplots
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=(f"{symbol} Price Chart ({timeframe})", "Volume"),
            row_heights=[0.7, 0.3]
        )
        
        # Add candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=df["date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="Price",
                increasing_line_color="green",
                decreasing_line_color="red"
            ),
            row=1, col=1
        )
        
        # Add volume chart
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["volume"],
                name="Volume",
                marker_color="lightblue",
                opacity=0.7
            ),
            row=2, col=1
        )
        
        # Add wave annotations
        if show_waves and waves:
            self._add_wave_annotations(fig, waves, df)
        
        # Add Fibonacci levels
        if show_fib and waves:
            self._add_fibonacci_levels(fig, waves, df)
        
        # Update layout
        fig.update_layout(
            title=f"{symbol} Analysis - {timeframe}",
            xaxis_title="Date",
            yaxis_title="Price (USDC)",
            height=800,
            showlegend=True,
            template="plotly_white"
        )
        
        # Update x-axis
        fig.update_xaxes(
            type="date",
            tickformat="%Y-%m-%d %H:%M",
            row=1, col=1
        )
        fig.update_xaxes(
            type="date",
            tickformat="%Y-%m-%d %H:%M",
            row=2, col=1
        )
        
        # Update y-axis
        fig.update_yaxes(title="Price (USDC)", row=1, col=1)
        fig.update_yaxes(title="Volume", row=2, col=1)
        
        # Save or show
        if output:
            fig.write_html(output)
            logger.info(f"Chart saved to {output}")
        else:
            fig.show()
    
    def _add_wave_annotations(
        self,
        fig: go.Figure,
        waves: List[Wave],
        df: pd.DataFrame
    ) -> None:
        """Add wave annotations to the chart"""
        for i, wave in enumerate(waves):
            # Determine color based on wave type
            color = "green" if wave.wave_type == "up" else "red"
            
            # Add wave line
            fig.add_trace(
                go.Scatter(
                    x=[wave.start_time, wave.end_time],
                    y=[wave.start_price, wave.end_price],
                    mode="lines+markers",
                    line=dict(color=color, width=3),
                    marker=dict(size=8),
                    name=f"Wave {i+1} ({wave.wave_type})",
                    showlegend=True
                ),
                row=1, col=1
            )
            
            # Add magnitude annotation
            mid_time = wave.start_time + (wave.end_time - wave.start_time) / 2
            mid_price = (wave.start_price + wave.end_price) / 2
            
            fig.add_annotation(
                x=mid_time,
                y=mid_price,
                text=f"{wave.magnitude:.1f}%",
                showarrow=True,
                arrowhead=2,
                arrowcolor=color,
                font=dict(color=color, size=10),
                row=1, col=1
            )
    
    def _add_fibonacci_levels(
        self,
        fig: go.Figure,
        waves: List[Wave],
        df: pd.DataFrame
    ) -> None:
        """Add Fibonacci retracement levels to the chart"""
        if not waves:
            return
        
        # Get the most recent significant wave
        recent_wave = max(waves, key=lambda w: w.start_time)
        
        # Calculate Fibonacci levels
        if recent_wave.wave_type == "up":
            high_price = recent_wave.peak_price
            low_price = recent_wave.start_price
        else:
            high_price = recent_wave.start_price
            low_price = recent_wave.peak_price
        
        range_size = high_price - low_price
        
        # Add Fibonacci levels
        fib_levels = self.config.get_fibonacci_levels()
        colors = ["red", "orange", "yellow", "green", "blue", "purple", "pink"]
        
        for i, level in enumerate(fib_levels):
            if level <= 100:
                # Retracement levels
                fib_price = high_price - (range_size * (level / 100))
                color = colors[i % len(colors)]
                
                fig.add_hline(
                    y=fib_price,
                    line_dash="dash",
                    line_color=color,
                    annotation_text=f"F{level}",
                    annotation_position="right",
                    row=1, col=1
                )
    
    def visualize_fibonacci_histogram(
        self,
        analyses: List[Dict[str, Any]],
        universe: str = "top100",
        level_grid: Optional[str] = None,
        output: Optional[str] = None
    ) -> None:
        """
        Create histogram of Fibonacci level distributions
        
        Args:
            analyses: List of Fibonacci analyses
            universe: Universe identifier
            level_grid: Comma-separated Fibonacci levels
            output: Output file path (optional)
        """
        if not analyses:
            logger.warning("No analyses provided for histogram")
            return
        
        # Parse level grid
        if level_grid:
            levels = [float(x.strip()) for x in level_grid.split(",")]
        else:
            levels = self.config.get_fibonacci_levels()
        
        # Prepare data for histogram
        level_data = {}
        for level in levels:
            level_data[level] = []
        
        # Collect data for each level
        for analysis in analyses:
            level_analysis = analysis.get("level_analysis", {})
            for level in levels:
                if level in level_analysis:
                    level_info = level_analysis[level]
                    if level_info.get("touched", False):
                        level_data[level].append({
                            "hold_time": level_info.get("hold_time", 0),
                            "deepest_retrace": level_info.get("deepest_retrace", 0),
                            "invalidation": level_info.get("invalidation", False)
                        })
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Hold Time Distribution",
                "Deepest Retracement Distribution",
                "Invalidation Rate by Level",
                "Touch Rate by Level"
            )
        )
        
        # Hold time histogram
        hold_times = []
        level_labels = []
        for level, data in level_data.items():
            if data:
                hold_times.extend([d["hold_time"] for d in data])
                level_labels.extend([f"F{level}" for _ in data])
        
        if hold_times:
            fig.add_trace(
                go.Histogram(
                    x=hold_times,
                    name="Hold Time",
                    nbinsx=20,
                    marker_color="lightblue"
                ),
                row=1, col=1
            )
        
        # Deepest retracement histogram
        retraces = []
        for level, data in level_data.items():
            if data:
                retraces.extend([d["deepest_retrace"] for d in data])
        
        if retraces:
            fig.add_trace(
                go.Histogram(
                    x=retraces,
                    name="Deepest Retracement",
                    nbinsx=20,
                    marker_color="lightgreen"
                ),
                row=1, col=2
            )
        
        # Invalidation rate by level
        invalidation_rates = []
        level_names = []
        for level, data in level_data.items():
            if data:
                invalidation_count = sum(1 for d in data if d["invalidation"])
                invalidation_rate = invalidation_count / len(data)
                invalidation_rates.append(invalidation_rate)
                level_names.append(f"F{level}")
        
        if invalidation_rates:
            fig.add_trace(
                go.Bar(
                    x=level_names,
                    y=invalidation_rates,
                    name="Invalidation Rate",
                    marker_color="red"
                ),
                row=2, col=1
            )
        
        # Touch rate by level
        touch_rates = []
        for level, data in level_data.items():
            total_analyses = len(analyses)
            touch_rate = len(data) / total_analyses if total_analyses > 0 else 0
            touch_rates.append(touch_rate)
        
        if touch_rates:
            fig.add_trace(
                go.Bar(
                    x=level_names,
                    y=touch_rates,
                    name="Touch Rate",
                    marker_color="blue"
                ),
                row=2, col=2
            )
        
        # Update layout
        fig.update_layout(
            title=f"Fibonacci Analysis - {universe}",
            height=800,
            showlegend=True,
            template="plotly_white"
        )
        
        # Update axes
        fig.update_xaxes(title="Hold Time (candles)", row=1, col=1)
        fig.update_xaxes(title="Deepest Retracement (%)", row=1, col=2)
        fig.update_xaxes(title="Fibonacci Level", row=2, col=1)
        fig.update_xaxes(title="Fibonacci Level", row=2, col=2)
        
        fig.update_yaxes(title="Count", row=1, col=1)
        fig.update_yaxes(title="Count", row=1, col=2)
        fig.update_yaxes(title="Rate", row=2, col=1)
        fig.update_yaxes(title="Rate", row=2, col=2)
        
        # Save or show
        if output:
            fig.write_html(output)
            logger.info(f"Histogram saved to {output}")
        else:
            fig.show()
    
    def visualize_heatmap(
        self,
        metric: str,
        levels: Optional[str] = None,
        universe: str = "top50",
        output: Optional[str] = None
    ) -> None:
        """
        Create heatmap visualization for Fibonacci levels
        
        Args:
            metric: Metric to visualize (e.g., "fib_hold_time")
            levels: Comma-separated Fibonacci levels
            universe: Universe identifier
            output: Output file path (optional)
        """
        # This would be implemented based on the specific metric
        # For now, create a placeholder heatmap
        if levels:
            level_list = [float(x.strip()) for x in levels.split(",")]
        else:
            level_list = [23.6, 38.2, 50, 61.8, 78.6]
        
        # Create sample data (in real implementation, this would come from analysis)
        data = np.random.rand(len(level_list), len(level_list))
        
        fig = go.Figure(data=go.Heatmap(
            z=data,
            x=[f"F{level}" for level in level_list],
            y=[f"F{level}" for level in level_list],
            colorscale="Viridis"
        ))
        
        fig.update_layout(
            title=f"Fibonacci {metric} Heatmap - {universe}",
            xaxis_title="Level 1",
            yaxis_title="Level 2",
            template="plotly_white"
        )
        
        if output:
            fig.write_html(output)
            logger.info(f"Heatmap saved to {output}")
        else:
            fig.show()
    
    def visualize_scatter(
        self,
        x: str,
        y: str,
        color: Optional[str] = None,
        output: Optional[str] = None
    ) -> None:
        """
        Create scatter plot visualization
        
        Args:
            x: X-axis variable
            y: Y-axis variable
            color: Color variable (optional)
            output: Output file path (optional)
        """
        # This would be implemented based on the specific variables
        # For now, create a placeholder scatter plot
        n_points = 100
        x_data = np.random.randn(n_points)
        y_data = np.random.randn(n_points)
        
        if color:
            color_data = np.random.randn(n_points)
            fig = go.Figure(data=go.Scatter(
                x=x_data,
                y=y_data,
                mode="markers",
                marker=dict(
                    size=10,
                    color=color_data,
                    colorscale="Viridis",
                    showscale=True
                ),
                text=[f"Point {i}" for i in range(n_points)],
                hovertemplate=f"{x}: %{{x}}<br>{y}: %{{y}}<br>{color}: %{{marker.color}}<extra></extra>"
            ))
        else:
            fig = go.Figure(data=go.Scatter(
                x=x_data,
                y=y_data,
                mode="markers",
                marker=dict(size=10, color="blue"),
                text=[f"Point {i}" for i in range(n_points)],
                hovertemplate=f"{x}: %{{x}}<br>{y}: %{{y}}<extra></extra>"
            ))
        
        fig.update_layout(
            title=f"{y} vs {x}",
            xaxis_title=x,
            yaxis_title=y,
            template="plotly_white"
        )
        
        if output:
            fig.write_html(output)
            logger.info(f"Scatter plot saved to {output}")
        else:
            fig.show()
    
    def create_wave_timeline(
        self,
        waves: List[Wave],
        output: Optional[str] = None
    ) -> None:
        """
        Create timeline visualization of waves
        
        Args:
            waves: List of waves to visualize
            output: Output file path (optional)
        """
        if not waves:
            logger.warning("No waves provided for timeline")
            return
        
        # Sort waves by start time
        sorted_waves = sorted(waves, key=lambda w: w.start_time)
        
        # Create timeline data
        y_positions = []
        start_times = []
        end_times = []
        magnitudes = []
        colors = []
        labels = []
        
        for i, wave in enumerate(sorted_waves):
            y_positions.append(i)
            start_times.append(wave.start_time)
            end_times.append(wave.end_time)
            magnitudes.append(abs(wave.magnitude))
            colors.append("green" if wave.wave_type == "up" else "red")
            labels.append(f"Wave {i+1}: {wave.magnitude:.1f}%")
        
        # Create timeline chart
        fig = go.Figure()
        
        for i, wave in enumerate(sorted_waves):
            fig.add_trace(go.Scatter(
                x=[wave.start_time, wave.end_time],
                y=[i, i],
                mode="lines+markers",
                line=dict(color=colors[i], width=5),
                marker=dict(size=10),
                name=labels[i],
                hovertemplate=f"Start: {wave.start_time}<br>End: {wave.end_time}<br>Magnitude: {wave.magnitude:.1f}%<br>Duration: {wave.duration} candles<extra></extra>"
            ))
        
        fig.update_layout(
            title="Wave Timeline",
            xaxis_title="Time",
            yaxis_title="Wave Index",
            height=600,
            template="plotly_white"
        )
        
        if output:
            fig.write_html(output)
            logger.info(f"Timeline saved to {output}")
        else:
            fig.show()
    
    def create_correlation_matrix(
        self,
        correlation_data: Dict[str, Any],
        output: Optional[str] = None
    ) -> None:
        """
        Create correlation matrix heatmap
        
        Args:
            correlation_data: Correlation data dictionary
            output: Output file path (optional)
        """
        # This would be implemented based on the correlation data structure
        # For now, create a placeholder correlation matrix
        variables = ["magnitude", "duration", "drawdown", "volume_delta"]
        n_vars = len(variables)
        
        # Create sample correlation matrix
        corr_matrix = np.random.rand(n_vars, n_vars)
        corr_matrix = (corr_matrix + corr_matrix.T) / 2  # Make symmetric
        np.fill_diagonal(corr_matrix, 1)  # Diagonal should be 1
        
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix,
            x=variables,
            y=variables,
            colorscale="RdBu",
            zmid=0,
            text=np.round(corr_matrix, 2),
            texttemplate="%{text}",
            textfont={"size": 10}
        ))
        
        fig.update_layout(
            title="Correlation Matrix",
            template="plotly_white"
        )
        
        if output:
            fig.write_html(output)
            logger.info(f"Correlation matrix saved to {output}")
        else:
            fig.show()