"""
Parameter optimization for options strategies.

Performs grid search over parameter ranges to find optimal strategy configurations.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from itertools import product
import copy

from ..backtester.optopsy_wrapper import OptopsyBacktester
from ..strategies.base_strategy import BaseStrategy
from ..analysis.metrics import calculate_performance_metrics


class ParameterOptimizer:
    """
    Grid search optimizer for strategy parameters.

    Supports both vertical spreads and calendar spreads with strategy-specific
    parameter ranges.

    Usage:
        # Initialize for calendar spreads
        optimizer = ParameterOptimizer(
            strategy_type='calendar',
            strategy_class=CallCalendarSpread,
            backtester=backtester,
            options_data=options_data,
            underlying_data=underlying_data,
            base_config=config
        )

        # Define parameter ranges (simplified syntax)
        optimizer.set_parameter_range('near_dte', min=20, max=35, step=5)
        optimizer.set_parameter_range('far_dte', min=45, max=75, step=10)
        optimizer.set_parameter_range('profit_target', min=0.15, max=0.35, step=0.05)
        optimizer.set_parameter_range('target_delta', min=0.40, max=0.60, step=0.05)

        # Run optimization
        results = optimizer.run_optimization()
        best_params = optimizer.get_best_parameters(metric='sharpe_ratio')
    """

    # Strategy-specific allowed parameters
    VERTICAL_PARAMETERS = {
        'entry': ['dte', 'target_delta', 'min_credit', 'max_credit',
                  'vix_min', 'vix_max'],
        'exit': ['profit_target', 'stop_loss', 'dte_min']
    }

    CALENDAR_PARAMETERS = {
        'entry': ['near_dte', 'far_dte', 'target_delta', 'min_debit', 'max_debit',
                  'vix_min', 'vix_max'],
        'exit': ['profit_target', 'stop_loss', 'dte_exit', 'max_underlying_move']
    }

    # Mapping of simplified parameters to their expanded forms
    # Used to map single parameters to multiple config keys
    PARAMETER_EXPANSION = {
        'vertical': {
            'dte': ['dte_min', 'dte_max']  # Single dte value sets both min and max (target DTE)
        },
        'calendar': {
            # Calendar spreads use single values directly, no expansion needed
        }
    }

    def __init__(
        self,
        strategy_type: str,
        strategy_class: type,
        backtester: OptopsyBacktester,
        options_data: pd.DataFrame,
        underlying_data: pd.DataFrame,
        base_config: Dict
    ):
        """
        Initialize parameter optimizer.

        Args:
            strategy_type: 'vertical' or 'calendar'
            strategy_class: Strategy class to instantiate (e.g., CallCalendarSpread)
            backtester: Backtester instance
            options_data: Historical options data
            underlying_data: Historical underlying price data
            base_config: Base configuration dictionary
        """
        if strategy_type not in ['vertical', 'calendar']:
            raise ValueError("strategy_type must be 'vertical' or 'calendar'")

        self.strategy_type = strategy_type
        self.strategy_class = strategy_class
        self.backtester = backtester
        self.options_data = options_data
        self.underlying_data = underlying_data
        self.base_config = base_config

        # Get allowed parameters for this strategy type
        if strategy_type == 'vertical':
            self.allowed_params = self.VERTICAL_PARAMETERS
        else:
            self.allowed_params = self.CALENDAR_PARAMETERS

        # Parameter ranges storage
        self.parameter_ranges: Dict[str, Dict[str, Any]] = {}

        # Results storage
        self.results: Optional[pd.DataFrame] = None
        self.best_params: Optional[Dict] = None

    def set_parameter_range(
        self,
        param_name: str,
        min: float,
        max: float,
        step: float = 1.0
    ):
        """
        Define a parameter range to test.

        Args:
            param_name: Name of parameter (e.g., 'near_dte_min', 'profit_target')
            min: Minimum value
            max: Maximum value (inclusive)
            step: Step size between values (default: 1.0)

        Raises:
            ValueError: If parameter is not valid for this strategy type
        """
        # Validate parameter name
        param_section, param_key = self._parse_parameter_name(param_name)

        if param_key not in self.allowed_params[param_section]:
            raise ValueError(
                f"Parameter '{param_name}' is not valid for {self.strategy_type} spreads. "
                f"Allowed {param_section} parameters: {self.allowed_params[param_section]}"
            )

        # Generate value range
        if step == 1.0 and isinstance(min, int) and isinstance(max, int):
            # Integer range
            values = list(range(int(min), int(max) + 1, int(step)))
        else:
            # Float range
            values = list(np.arange(min, max + step, step))
            # Round to avoid floating point errors
            values = [round(v, 4) for v in values]

        self.parameter_ranges[param_name] = {
            'min': min,
            'max': max,
            'step': step,
            'values': values,
            'section': param_section
        }

        print(f"Set parameter '{param_name}': {len(values)} values from {min} to {max} (step={step})")

    def _parse_parameter_name(self, param_name: str) -> Tuple[str, str]:
        """
        Parse parameter name to determine if it's entry or exit parameter.

        Args:
            param_name: Parameter name

        Returns:
            Tuple of (section, key) where section is 'entry' or 'exit'
        """
        # First check if it's explicitly in entry or exit parameters
        for section in ['entry', 'exit']:
            if param_name in self.allowed_params[section]:
                return section, param_name

        # If not found, raise error
        raise ValueError(
            f"Unknown parameter '{param_name}'. "
            f"Valid entry params: {self.allowed_params['entry']}, "
            f"Valid exit params: {self.allowed_params['exit']}"
        )

    def get_total_combinations(self) -> int:
        """
        Calculate total number of parameter combinations to test.

        Returns:
            Total number of combinations
        """
        if not self.parameter_ranges:
            return 0

        total = 1
        for param_info in self.parameter_ranges.values():
            total *= len(param_info['values'])

        return total

    def run_optimization(
        self,
        optimization_metric: str = 'sharpe_ratio',
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Run grid search optimization over all parameter combinations.

        Args:
            optimization_metric: Metric to optimize ('sharpe_ratio', 'total_return',
                                'profit_factor', 'calmar_ratio', etc.)
            verbose: Print progress updates

        Returns:
            DataFrame with results for all parameter combinations
        """
        if not self.parameter_ranges:
            raise ValueError("No parameter ranges defined. Use set_parameter_range() first.")

        # Generate all combinations
        param_names = list(self.parameter_ranges.keys())
        param_values_lists = [self.parameter_ranges[p]['values'] for p in param_names]

        total_combinations = self.get_total_combinations()

        if verbose:
            print(f"\n{'='*60}")
            print(f"PARAMETER OPTIMIZATION: {self.strategy_type.upper()} SPREADS")
            print(f"{'='*60}")
            print(f"Strategy: {self.strategy_class.__name__}")
            print(f"Parameters to optimize: {param_names}")
            print(f"Total combinations: {total_combinations:,}")
            print(f"Optimization metric: {optimization_metric}")
            print(f"{'='*60}\n")

        # Run backtest for each combination
        results = []

        for i, combination in enumerate(product(*param_values_lists), 1):
            # Create parameter dict
            params = dict(zip(param_names, combination))

            if verbose and i % max(1, total_combinations // 20) == 0:
                print(f"Progress: {i}/{total_combinations} ({i/total_combinations*100:.1f}%)")

            # Run backtest with these parameters
            try:
                metrics = self._run_single_backtest(params, verbose=False)

                # Store results
                result_row = params.copy()
                result_row.update(metrics)
                results.append(result_row)

            except Exception as e:
                if verbose:
                    print(f"  ⚠️  Combination {i} failed: {params}")
                    print(f"      Error: {str(e)}")

                # Store failed result
                result_row = params.copy()
                result_row['error'] = str(e)
                result_row[optimization_metric] = np.nan
                results.append(result_row)

        # Convert to DataFrame
        self.results = pd.DataFrame(results)

        # Sort by optimization metric (descending)
        if optimization_metric in self.results.columns:
            self.results = self.results.sort_values(
                optimization_metric,
                ascending=False
            ).reset_index(drop=True)

        if verbose:
            print(f"\n{'='*60}")
            print("OPTIMIZATION COMPLETE")
            print(f"{'='*60}")
            print(f"Total combinations tested: {len(results)}")
            print(f"Successful backtests: {self.results[optimization_metric].notna().sum()}")
            print(f"Failed backtests: {self.results[optimization_metric].isna().sum()}")

            if not self.results.empty and optimization_metric in self.results.columns:
                best_row = self.results.iloc[0]
                print(f"\nBest {optimization_metric}: {best_row[optimization_metric]:.4f}")
                print("\nBest parameters:")
                for param in param_names:
                    print(f"  {param}: {best_row[param]}")

        return self.results

    def _run_single_backtest(self, params: Dict, verbose: bool = False) -> Dict:
        """
        Run a single backtest with given parameters.

        Args:
            params: Dictionary of parameter values
            verbose: Print backtest details

        Returns:
            Dictionary of performance metrics
        """
        # Create a copy of base config
        config = copy.deepcopy(self.base_config)

        # Update config with new parameters
        # Need to determine which strategy config to update
        strategy_name = self.strategy_class.__name__

        # Map strategy class to config key
        config_key_map = {
            'BullPutSpread': 'bull_put',
            'BullCallSpread': 'bull_call',
            'BearPutSpread': 'bear_put',
            'BearCallSpread': 'bear_call',
            'CallCalendarSpread': 'call_calendar',
            'PutCalendarSpread': 'put_calendar'
        }

        config_key = config_key_map.get(strategy_name)
        if not config_key:
            raise ValueError(f"Unknown strategy class: {strategy_name}")

        # Update config parameters
        for param_name, param_value in params.items():
            section, key = self._parse_parameter_name(param_name)

            if config_key not in config['strategies']:
                config['strategies'][config_key] = {'entry': {}, 'exit': {}}

            if section not in config['strategies'][config_key]:
                config['strategies'][config_key][section] = {}

            # Check if this parameter needs to be expanded
            expansion_map = self.PARAMETER_EXPANSION.get(self.strategy_type, {})
            if key in expansion_map:
                # Expand to multiple config keys (e.g., 'dte' -> 'dte_min' and 'dte_max')
                for expanded_key in expansion_map[key]:
                    config['strategies'][config_key][section][expanded_key] = param_value
            else:
                # Use parameter as-is
                config['strategies'][config_key][section][key] = param_value

        # Create strategy instance with updated config
        strategy = self.strategy_class(config)

        # Run backtest
        backtest_results = self.backtester.run_backtest(
            strategy=strategy,
            options_data=self.options_data,
            underlying_data=self.underlying_data
        )

        # Calculate performance metrics
        metrics = calculate_performance_metrics(backtest_results)

        return metrics

    def get_best_parameters(
        self,
        metric: str = 'sharpe_ratio',
        top_n: int = 1
    ) -> pd.DataFrame:
        """
        Get the best parameter combinations.

        Args:
            metric: Metric to rank by
            top_n: Number of top combinations to return

        Returns:
            DataFrame with top N parameter combinations
        """
        if self.results is None:
            raise ValueError("No results available. Run run_optimization() first.")

        if metric not in self.results.columns:
            raise ValueError(f"Metric '{metric}' not found in results. Available: {self.results.columns.tolist()}")

        # Filter out failed backtests
        valid_results = self.results[self.results[metric].notna()].copy()

        # Sort by metric (descending)
        sorted_results = valid_results.sort_values(metric, ascending=False)

        return sorted_results.head(top_n)

    def save_results(self, filepath: str):
        """
        Save optimization results to CSV.

        Args:
            filepath: Path to save results
        """
        if self.results is None:
            raise ValueError("No results available. Run run_optimization() first.")

        self.results.to_csv(filepath, index=False)
        print(f"Results saved to: {filepath}")

    def plot_parameter_sensitivity(
        self,
        param_name: str,
        metric: str = 'sharpe_ratio',
        save_path: Optional[str] = None
    ):
        """
        Plot how a metric changes with a single parameter.

        Args:
            param_name: Parameter to analyze
            metric: Metric to plot
            save_path: Optional path to save plot
        """
        if self.results is None:
            raise ValueError("No results available. Run run_optimization() first.")

        import matplotlib.pyplot as plt

        # Filter valid results
        valid_results = self.results[self.results[metric].notna()].copy()

        # Group by parameter and calculate mean metric
        grouped = valid_results.groupby(param_name)[metric].agg(['mean', 'std', 'count'])

        # Plot
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.errorbar(
            grouped.index,
            grouped['mean'],
            yerr=grouped['std'],
            marker='o',
            capsize=5,
            capthick=2
        )
        ax.set_xlabel(param_name)
        ax.set_ylabel(metric)
        ax.set_title(f'{metric} vs {param_name}')
        ax.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to: {save_path}")

        plt.show()

    def plot_heatmap(
        self,
        param_x: str,
        param_y: str,
        metric: str = 'sharpe_ratio',
        save_path: Optional[str] = None
    ):
        """
        Plot 2D heatmap of metric vs two parameters.

        Args:
            param_x: First parameter (x-axis)
            param_y: Second parameter (y-axis)
            metric: Metric to plot
            save_path: Optional path to save plot
        """
        if self.results is None:
            raise ValueError("No results available. Run run_optimization() first.")

        import matplotlib.pyplot as plt
        import seaborn as sns

        # Filter valid results
        valid_results = self.results[self.results[metric].notna()].copy()

        # Create pivot table
        pivot = valid_results.pivot_table(
            values=metric,
            index=param_y,
            columns=param_x,
            aggfunc='mean'
        )

        # Plot heatmap
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.heatmap(pivot, annot=True, fmt='.3f', cmap='RdYlGn', ax=ax)
        ax.set_title(f'{metric} Heatmap: {param_x} vs {param_y}')

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to: {save_path}")

        plt.show()


def quick_optimize_vertical(
    strategy_class: type,
    backtester: OptopsyBacktester,
    options_data: pd.DataFrame,
    underlying_data: pd.DataFrame,
    config: Dict,
    dte_range: Tuple[int, int] = (30, 45),
    delta_range: Tuple[float, float] = (0.25, 0.40),
    profit_target_range: Tuple[float, float] = (0.40, 0.60)
) -> pd.DataFrame:
    """
    Quick optimization for vertical spreads with common parameters.

    Args:
        strategy_class: Strategy class (e.g., BullPutSpread)
        backtester: Backtester instance
        options_data: Options data
        underlying_data: Underlying data
        config: Base config
        dte_range: (min, max) for entry DTE
        delta_range: (min, max) for target delta
        profit_target_range: (min, max) for profit target

    Returns:
        Optimization results DataFrame
    """
    optimizer = ParameterOptimizer(
        strategy_type='vertical',
        strategy_class=strategy_class,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )

    # Simplified parameter syntax - 'dte' sets both dte_min and dte_max
    optimizer.set_parameter_range('dte', min=dte_range[0], max=dte_range[1], step=5)
    optimizer.set_parameter_range('target_delta', min=delta_range[0], max=delta_range[1], step=0.05)
    optimizer.set_parameter_range('profit_target', min=profit_target_range[0], max=profit_target_range[1], step=0.05)

    results = optimizer.run_optimization(optimization_metric='sharpe_ratio')

    return results


def quick_optimize_calendar(
    strategy_class: type,
    backtester: OptopsyBacktester,
    options_data: pd.DataFrame,
    underlying_data: pd.DataFrame,
    config: Dict,
    near_dte_range: Tuple[int, int] = (20, 35),
    far_dte_range: Tuple[int, int] = (45, 75),
    delta_range: Tuple[float, float] = (0.40, 0.60),
    profit_target_range: Tuple[float, float] = (0.15, 0.35)
) -> pd.DataFrame:
    """
    Quick optimization for calendar spreads with common parameters.

    Args:
        strategy_class: Strategy class (e.g., CallCalendarSpread)
        backtester: Backtester instance
        options_data: Options data
        underlying_data: Underlying data
        config: Base config
        near_dte_range: (min, max) for near-term DTE target
        far_dte_range: (min, max) for far-term DTE target
        delta_range: (min, max) for target delta
        profit_target_range: (min, max) for profit target

    Returns:
        Optimization results DataFrame
    """
    optimizer = ParameterOptimizer(
        strategy_type='calendar',
        strategy_class=strategy_class,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )

    # Simplified parameter syntax - single values for near_dte and far_dte
    optimizer.set_parameter_range('near_dte', min=near_dte_range[0], max=near_dte_range[1], step=5)
    optimizer.set_parameter_range('far_dte', min=far_dte_range[0], max=far_dte_range[1], step=10)
    optimizer.set_parameter_range('target_delta', min=delta_range[0], max=delta_range[1], step=0.05)
    optimizer.set_parameter_range('profit_target', min=profit_target_range[0], max=profit_target_range[1], step=0.05)

    results = optimizer.run_optimization(optimization_metric='sharpe_ratio')

    return results
