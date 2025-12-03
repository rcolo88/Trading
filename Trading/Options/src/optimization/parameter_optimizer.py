"""
Parameter optimization for options strategies.

Performs grid search over parameter ranges to find optimal strategy configurations.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
import pandas as pd
import numpy as np
from itertools import product
import copy
import time
import random
import os
from pathlib import Path

# Progress bar library - shows visual progress during long operations
# Install: pip install tqdm
# Docs: https://tqdm.github.io/
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # Fallback: if tqdm not installed, we'll use text-based progress

from ..backtester.optopsy_wrapper import OptopsyBacktester
from ..strategies.base_strategy import BaseStrategy
from ..analysis.metrics import calculate_performance_metrics
from .results_compiler import get_completed_combinations


class ParameterOptimizer:
    """
    Grid search optimizer for strategy parameters.

    Supports both vertical spreads and calendar spreads with strategy-specific
    parameter ranges.

    Usage:
        # Initialize for vertical spreads
        optimizer = ParameterOptimizer(
            strategy_type='vertical',
            strategy_class=BullPutSpread,
            backtester=backtester,
            options_data=options_data,
            underlying_data=underlying_data,
            base_config=config
        )

        # Define parameter ranges for vertical spreads
        optimizer.set_parameter_range('dte', min=30, max=45, step=5)
        optimizer.set_parameter_range('short_delta', min=0.25, max=0.40, step=0.05)
        optimizer.set_parameter_range('long_delta', min=0.10, max=0.25, step=0.05)
        optimizer.set_parameter_range('profit_target', min=0.40, max=0.60, step=0.05)

        # Or for calendar spreads
        optimizer = ParameterOptimizer(
            strategy_type='calendar',
            strategy_class=CallCalendarSpread,
            backtester=backtester,
            options_data=options_data,
            underlying_data=underlying_data,
            base_config=config
        )

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
        'entry': ['dte', 'short_delta', 'long_delta', 'iv_percentile'],
        'exit': ['profit_target', 'stop_loss', 'dte_min']
    }

    CALENDAR_PARAMETERS = {
        'entry': ['near_dte', 'far_dte', 'target_delta', 'min_debit', 'max_debit',
                  'iv_percentile_min', 'iv_percentile_max'],
        'exit': ['profit_target', 'stop_loss', 'dte_exit', 'max_underlying_move']
    }

    IRON_CONDOR_PARAMETERS = {
        'entry': ['dte_min', 'dte_max', 'put_short_delta', 'put_long_delta',
                  'call_short_delta', 'call_long_delta', 'iv_percentile_min', 'iv_percentile_max',
                  'min_credit', 'max_wing_width'],
        'exit': ['profit_target', 'stop_loss', 'dte_min', 'breach_threshold']
    }

    # Mapping of simplified parameters to their expanded forms
    # Used to map single parameters to multiple config keys
    PARAMETER_EXPANSION = {
        'vertical': {
            'dte': ['dte_min', 'dte_max'],  # Single dte value sets both min and max (target DTE)
            'iv_percentile': ['iv_percentile_min', 'iv_percentile_max']  # Single IV percentile sets both min and max
        },
        'calendar': {
            # Note: Calendar spreads use explicit iv_percentile_min and iv_percentile_max
            # (not a single iv_percentile value) to avoid requiring exact match filters
        },
        'iron_condor': {
            # Iron Condor uses explicit parameters with no expansion needed
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
        if strategy_type not in ['vertical', 'calendar', 'iron_condor']:
            raise ValueError("strategy_type must be 'vertical', 'calendar', or 'iron_condor'")

        self.strategy_type = strategy_type
        self.strategy_class = strategy_class
        self.backtester = backtester
        self.options_data = options_data
        self.underlying_data = underlying_data
        self.base_config = base_config

        # Get allowed parameters for this strategy type
        if strategy_type == 'vertical':
            self.allowed_params = self.VERTICAL_PARAMETERS
        elif strategy_type == 'calendar':
            self.allowed_params = self.CALENDAR_PARAMETERS
        else:
            self.allowed_params = self.IRON_CONDOR_PARAMETERS

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

    def _estimate_runtime_and_confirm(
        self,
        param_names: List[str],
        param_values_lists: List[List],
        total_combinations: int,
        num_samples: int = 3
    ) -> bool:
        """
        Run sample backtests to estimate total runtime and ask user for confirmation.

        Args:
            param_names: List of parameter names
            param_values_lists: List of value lists for each parameter
            total_combinations: Total number of combinations to test
            num_samples: Number of sample backtests to run (default: 3)

        Returns:
            True if user confirms, False otherwise
        """
        print(f"\n{'='*60}")
        print("ESTIMATING RUNTIME...")
        print(f"{'='*60}")
        print(f"Running {num_samples} sample backtests to estimate time...\n")

        # Generate random sample combinations
        all_combinations = list(product(*param_values_lists))
        sample_size = min(num_samples, len(all_combinations))
        sample_combinations = random.sample(all_combinations, sample_size)

        # Run sample backtests and time them
        sample_times = []

        # PROGRESS BAR: Show visual progress during sampling
        # Why manual update? We want to show details for each sample
        if TQDM_AVAILABLE:
            # Create progress bar with custom description
            pbar = tqdm(
                total=sample_size,
                desc="Sampling",
                unit="backtest",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
            )
        else:
            pbar = None  # Fallback to text-based progress

        for i, combination in enumerate(sample_combinations, 1):
            params = dict(zip(param_names, combination))

            # Show what we're testing (without cluttering if using tqdm)
            if not TQDM_AVAILABLE:
                print(f"  Sample {i}/{sample_size}: Testing {params}")

            start_time = time.time()
            try:
                self._run_single_backtest(params, verbose=False)
                elapsed = time.time() - start_time
                sample_times.append(elapsed)

                # Update progress bar description to show result
                if TQDM_AVAILABLE:
                    pbar.set_postfix_str(f"✓ {elapsed:.2f}s", refresh=True)
                else:
                    print(f"    ✓ Completed in {elapsed:.2f} seconds")

            except Exception as e:
                if not TQDM_AVAILABLE:
                    print(f"    ⚠️  Sample failed: {str(e)}")
                # Still record time for failed attempts
                elapsed = time.time() - start_time
                sample_times.append(elapsed)

            # UPDATE PROGRESS BAR: Increment by 1 after each sample
            if TQDM_AVAILABLE:
                pbar.update(1)

        # CLOSE PROGRESS BAR: Always close to prevent display issues
        if TQDM_AVAILABLE:
            pbar.close()
            print()  # Add newline after progress bar

        # Calculate estimates
        if not sample_times:
            print("\n⚠️  All sample backtests failed. Cannot estimate runtime.")
            response = input("Continue anyway? (y/n): ").strip().lower()
            return response == 'y'

        avg_time = np.mean(sample_times)
        min_time = np.min(sample_times)
        max_time = np.max(sample_times)

        # Estimate total runtime
        estimated_total_seconds = avg_time * total_combinations
        estimated_min_seconds = min_time * total_combinations
        estimated_max_seconds = max_time * total_combinations

        # Format time estimates
        def format_time(seconds):
            """Convert seconds to human-readable format."""
            if seconds < 60:
                return f"{seconds:.0f} seconds"
            elif seconds < 3600:
                minutes = seconds / 60
                return f"{minutes:.1f} minutes"
            else:
                hours = seconds / 3600
                return f"{hours:.1f} hours"

        print(f"\n{'='*60}")
        print("RUNTIME ESTIMATE")
        print(f"{'='*60}")
        print(f"Sample backtests: {sample_size}")
        print(f"Average time per backtest: {avg_time:.2f} seconds")
        print(f"Time range: {min_time:.2f}s - {max_time:.2f}s")
        print(f"\nTotal combinations: {total_combinations:,}")
        print(f"\nEstimated total runtime:")
        print(f"  Best case:  {format_time(estimated_min_seconds)}")
        print(f"  Average:    {format_time(estimated_total_seconds)}")
        print(f"  Worst case: {format_time(estimated_max_seconds)}")
        print(f"{'='*60}\n")

        # Get user confirmation
        response = input("Do you want to proceed with optimization? (y/n): ").strip().lower()

        if response == 'y':
            print("\n✓ Starting optimization...\n")
            return True
        else:
            print("\n✗ Optimization cancelled by user.")
            return False

    def _params_to_key(self, params: Dict) -> Tuple:
        """
        Convert parameter dictionary to hashable key for comparison.

        Why this is needed:
        - Dicts are not hashable (can't use in sets)
        - Need to identify unique parameter combinations
        - Order shouldn't matter: {'a': 1, 'b': 2} == {'b': 2, 'a': 1}

        Args:
            params: Parameter dictionary

        Returns:
            Tuple of sorted (key, value) pairs - hashable and order-independent

        Example:
            >>> _params_to_key({'dte': 30, 'delta': 0.25})
            (('delta', 0.25), ('dte', 30))
        """
        return tuple(sorted(params.items()))

    def _get_checkpoint_path(self, strategy_name: str, timestamp: str) -> Path:
        """
        Generate checkpoint file path.

        Creates: optimization_checkpoints/<strategy>_<timestamp>.csv

        Args:
            strategy_name: Name of strategy being optimized
            timestamp: Timestamp string for unique filename

        Returns:
            Path object to checkpoint file
        """
        checkpoint_dir = Path("optimization_checkpoints")
        checkpoint_dir.mkdir(exist_ok=True)  # Create dir if doesn't exist
        filename = f"{strategy_name}_{timestamp}.csv"
        return checkpoint_dir / filename

    def _save_checkpoint(
        self,
        checkpoint_path: Path,
        results: List[Dict],
        verbose: bool = True
    ):
        """
        Save current optimization results to checkpoint file.

        WHY: If optimization is interrupted, we don't lose progress!

        Args:
            checkpoint_path: Path to save checkpoint
            results: List of result dictionaries
            verbose: Print save confirmation

        How it works:
            1. Convert results list to DataFrame
            2. Save as CSV (human-readable, easy to inspect)
            3. Print confirmation (so user knows it's saving)

        File format:
            dte,delta,sharpe_ratio,total_return,...
            30,0.25,1.52,0.24,...
            35,0.30,1.67,0.28,...
        """
        if not results:
            return  # Nothing to save

        df = pd.DataFrame(results)
        df.to_csv(checkpoint_path, index=False)

        if verbose:
            print(f"    💾 Checkpoint saved: {len(results)} results → {checkpoint_path.name}")

    def _load_checkpoint(
        self,
        checkpoint_path: Path,
        param_names: List[str]
    ) -> Tuple[List[Dict], Set[Tuple]]:
        """
        Load previous optimization results from checkpoint.

        WHY: Resume where we left off instead of starting over!

        Args:
            checkpoint_path: Path to checkpoint file
            param_names: List of parameter names being optimized

        Returns:
            Tuple of:
                - results: List of previously completed result dicts
                - completed_keys: Set of parameter combination keys already done

        How it works:
            1. Load CSV into DataFrame
            2. Extract results as list of dicts
            3. Create set of "completed keys" for fast lookup
            4. Return both so we can:
               a) Include previous results in final output
               b) Skip already-completed combinations

        Example:
            results, completed = _load_checkpoint(...)
            # completed = {(('dte', 30), ('delta', 0.25)), ...}
            # Can check: if params_key in completed: skip!
        """
        if not checkpoint_path.exists():
            return [], set()  # No checkpoint found

        print(f"\n📂 Found existing checkpoint: {checkpoint_path.name}")
        df = pd.DataFrame(pd.read_csv(checkpoint_path))

        if df.empty:
            return [], set()

        # Convert DataFrame back to list of dicts
        results = df.to_dict('records')

        # Build set of completed parameter combinations for fast lookup
        completed_keys = set()
        for result in results:
            # Extract only the parameter columns (not metrics)
            params = {k: result[k] for k in param_names if k in result}
            key = self._params_to_key(params)
            completed_keys.add(key)

        print(f"    ✓ Loaded {len(results)} previous results")
        print(f"    ✓ Will skip {len(completed_keys)} already-completed combinations")

        return results, completed_keys

    def run_optimization(
        self,
        mode: str = 'grid',
        n_trials: Optional[int] = None,
        optimization_metric: str = 'sharpe_ratio',
        verbose: bool = True,
        confirm: bool = True,
        num_samples: int = 3,
        checkpoint_every: int = 10,
        resume_from: Optional[str] = None,
        resume_from_master: bool = True,
        optuna_n_startup_trials: int = 20,
        optuna_enable_pruning: bool = True
    ) -> pd.DataFrame:
        """
        Run parameter optimization using either grid search or Optuna.

        NEW IN THIS VERSION:
        - Dual mode: 'grid' (exhaustive) or 'optuna' (Bayesian - 50-80% faster)
        - Optuna finds 92-95% optimal in 200-500 trials vs thousands for grid
        - Saves checkpoints periodically (every N combinations)
        - Can resume from previous checkpoint if interrupted
        - Automatically skips combinations already in master compiled CSV

        Args:
            mode: 'grid' for exhaustive search, 'optuna' for Bayesian optimization
            n_trials: Number of trials for Optuna mode (200-1000 recommended).
                     Ignored in grid mode. If None and mode='optuna', uses 500.
            optimization_metric: Metric to optimize ('sharpe_ratio', 'total_return',
                                'profit_factor', 'calmar_ratio', etc.)
            verbose: Print progress updates
            confirm: Ask user to confirm before starting (default: True, grid only)
            num_samples: Number of sample backtests for runtime estimation (default: 3, grid only)
            checkpoint_every: Save progress every N combinations (default: 10, grid only)
            resume_from: Path to checkpoint file to resume from (grid only)
            resume_from_master: Skip combinations already in master CSV (default: True)
            optuna_n_startup_trials: Random trials before Bayesian (optuna only)
            optuna_enable_pruning: Enable early stopping (optuna only)

        Returns:
            DataFrame with results for all parameter combinations

        Examples:
            # Optuna mode (fast - recommended for large search spaces)
            results = optimizer.run_optimization(
                mode='optuna',
                n_trials=500
            )

            # Grid search mode (exhaustive - for small search spaces)
            results = optimizer.run_optimization(
                mode='grid',
                checkpoint_every=10
            )
        """
        if not self.parameter_ranges:
            raise ValueError("No parameter ranges defined. Use set_parameter_range() first.")

        # OPTUNA MODE: Delegate to optuna_optimizer module
        if mode == 'optuna':
            from .optuna_optimizer import run_optuna_optimization

            # Set default n_trials if not specified
            if n_trials is None:
                n_trials = 500

            return run_optuna_optimization(
                parameter_optimizer=self,
                n_trials=n_trials,
                optimization_metric=optimization_metric,
                timeout=None,
                n_jobs=1,
                n_startup_trials=optuna_n_startup_trials,
                enable_pruning=optuna_enable_pruning,
                verbose=verbose
            )

        # GRID SEARCH MODE: Continue with existing logic
        elif mode != 'grid':
            raise ValueError(f"Unknown mode '{mode}'. Use 'grid' or 'optuna'.")

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

        # Estimate runtime and get user confirmation
        if confirm:
            user_confirmed = self._estimate_runtime_and_confirm(
                param_names=param_names,
                param_values_lists=param_values_lists,
                total_combinations=total_combinations,
                num_samples=num_samples
            )
            if not user_confirmed:
                raise RuntimeError("Optimization cancelled by user")

        # CHECKPOINT SETUP: Prepare for incremental saving and resume capability
        strategy_name = self.strategy_class.__name__
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if resume_from:
            # User specified checkpoint file to resume from
            checkpoint_path = Path(resume_from)
            print(f"\n🔄 RESUME MODE: Loading checkpoint from {checkpoint_path}")
        else:
            # Create new checkpoint file for this run
            checkpoint_path = self._get_checkpoint_path(strategy_name, timestamp)
            if verbose:
                print(f"\n💾 Checkpoint file: {checkpoint_path}")
                print(f"    Saving every {checkpoint_every} combinations")

        # Load previous results if resuming
        results, completed_keys = self._load_checkpoint(checkpoint_path, param_names)

        # MASTER CSV RESUME: Skip combinations already in compiled results
        # This prevents redundant computation across multiple optimization runs
        if resume_from_master:
            try:
                master_df = get_completed_combinations(strategy_name, self.base_config)
                if not master_df.empty:
                    # Count combinations from master before adding them
                    master_combinations_before = len(completed_keys)

                    # Add master CSV combinations to completed keys
                    for _, row in master_df.iterrows():
                        params = {k: row[k] for k in param_names if k in row}
                        key = self._params_to_key(params)
                        completed_keys.add(key)

                    # Report how many additional combinations were loaded from master
                    master_combinations_added = len(completed_keys) - master_combinations_before
                    if master_combinations_added > 0 and verbose:
                        print(f"    ✓ Master CSV: Skipping {master_combinations_added} already-tested combinations")
            except Exception as e:
                # Silently continue if master CSV loading fails
                # This allows optimization to work even if compilation fails
                if verbose:
                    print(f"    ⚠️  Could not load master CSV: {str(e)}")

        combinations_to_skip = len(completed_keys)
        combinations_to_run = total_combinations - combinations_to_skip

        if combinations_to_skip > 0 and verbose:
            print(f"    ✓ Total combinations to skip: {combinations_to_skip}")
            print(f"    ✓ Combinations remaining: {combinations_to_run}\n")

        # Run backtest for each combination
        start_time = time.time()
        combinations_processed = combinations_to_skip  # Start from where we left off

        # PROGRESS BAR: Create before loop
        # Why? We want a single, updating line instead of hundreds of text lines
        if TQDM_AVAILABLE and verbose:
            pbar = tqdm(
                total=total_combinations,
                desc=f"Optimizing {strategy_name}",
                unit="combo",
                initial=combinations_to_skip,  # Start from where we resumed
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
            )
        else:
            pbar = None

        try:  # Wrap in try-except to save checkpoint on Ctrl+C
            for i, combination in enumerate(product(*param_values_lists), 1):
                # Create parameter dict
                params = dict(zip(param_names, combination))
                params_key = self._params_to_key(params)

                # SKIP if already completed (resume functionality)
                if params_key in completed_keys:
                    # CRITICAL: Still update progress bar when skipping!
                    # Why? User needs to see we're making progress through the list
                    if TQDM_AVAILABLE and verbose:
                        pbar.set_postfix_str("(skipped)", refresh=False)
                        pbar.update(0)  # Trigger refresh without incrementing
                    elif verbose and i % max(1, total_combinations // 20) == 0:
                        print(f"Progress: {i}/{total_combinations} ({i/total_combinations*100:.1f}%) [Skipping completed]")
                    continue

                combinations_processed += 1

                # Text-based progress reporting (fallback if no tqdm)
                if not TQDM_AVAILABLE and verbose and combinations_processed % max(1, combinations_to_run // 20) == 0:
                    print(f"Progress: {combinations_processed}/{total_combinations} ({combinations_processed/total_combinations*100:.1f}%)")

                # Run backtest with these parameters
                try:
                    metrics = self._run_single_backtest(params, verbose=False)

                    # Store results
                    result_row = params.copy()
                    result_row.update(metrics)
                    results.append(result_row)

                    # UPDATE PROGRESS BAR: Show success
                    if TQDM_AVAILABLE and verbose:
                        pbar.set_postfix_str("✓", refresh=False)

                except Exception as e:
                    if not TQDM_AVAILABLE and verbose:
                        print(f"  ⚠️  Combination {i} failed: {params}")
                        print(f"      Error: {str(e)}")

                    # Store failed result
                    result_row = params.copy()
                    result_row['error'] = str(e)
                    result_row[optimization_metric] = np.nan
                    results.append(result_row)

                    # UPDATE PROGRESS BAR: Show failure
                    if TQDM_AVAILABLE and verbose:
                        pbar.set_postfix_str("⚠️ failed", refresh=False)

                # UPDATE PROGRESS BAR: Increment after each combination (skip or run)
                if TQDM_AVAILABLE and verbose:
                    pbar.update(1)

                # CHECKPOINT SAVE: Save progress every N combinations
                if len(results) % checkpoint_every == 0:
                    if TQDM_AVAILABLE and verbose:
                        # Show checkpoint save in progress bar
                        pbar.set_postfix_str("💾 saving...", refresh=True)
                    self._save_checkpoint(checkpoint_path, results, verbose=False if TQDM_AVAILABLE else verbose)
                    if TQDM_AVAILABLE and verbose:
                        pbar.set_postfix_str("✓", refresh=False)

        except KeyboardInterrupt:
            # User pressed Ctrl+C - close progress bar and save!
            if TQDM_AVAILABLE and verbose:
                pbar.close()

            print(f"\n\n⚠️  Interrupted by user (Ctrl+C)")
            print(f"💾 Saving checkpoint before exit...")
            self._save_checkpoint(checkpoint_path, results, verbose=True)
            print(f"\nTo resume later, use:")
            print(f"  results = optimizer.run_optimization(")
            print(f"      resume_from='{checkpoint_path}'")
            print(f"  )")
            raise  # Re-raise to actually stop execution

        finally:
            # CLOSE PROGRESS BAR: Always close, even on error
            # Why? Prevents terminal display corruption
            if TQDM_AVAILABLE and verbose and pbar is not None:
                pbar.close()

        # Final checkpoint save
        if results:
            if TQDM_AVAILABLE and verbose:
                # Don't clutter output with save message
                self._save_checkpoint(checkpoint_path, results, verbose=False)
            else:
                self._save_checkpoint(checkpoint_path, results, verbose=verbose)

        # Convert to DataFrame
        self.results = pd.DataFrame(results)

        # Sort by optimization metric (descending)
        if optimization_metric in self.results.columns:
            self.results = self.results.sort_values(
                optimization_metric,
                ascending=False
            ).reset_index(drop=True)

        # Calculate actual runtime
        actual_runtime = time.time() - start_time

        if verbose:
            print(f"\n{'='*60}")
            print("OPTIMIZATION COMPLETE")
            print(f"{'='*60}")
            print(f"Total combinations tested: {len(results)}")
            print(f"Successful backtests: {self.results[optimization_metric].notna().sum()}")
            print(f"Failed backtests: {self.results[optimization_metric].isna().sum()}")

            # Show actual runtime
            def format_time(seconds):
                if seconds < 60:
                    return f"{seconds:.0f} seconds"
                elif seconds < 3600:
                    minutes = seconds / 60
                    return f"{minutes:.1f} minutes"
                else:
                    hours = seconds / 3600
                    return f"{hours:.1f} hours"

            print(f"\nActual runtime: {format_time(actual_runtime)}")
            print(f"Average time per backtest: {actual_runtime / len(results):.2f} seconds")

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
            'BullPutSpread': 'bull_put_spread',
            'BullCallSpread': 'bull_call_spread',
            'BearPutSpread': 'bear_put_spread',
            'BearCallSpread': 'bear_call_spread',
            'CallCalendarSpread': 'call_calendar',
            'PutCalendarSpread': 'put_calendar',
            'IronCondor': 'iron_condor'
        }

        config_key = config_key_map.get(strategy_name)
        if not config_key:
            raise ValueError(f"Unknown strategy class: {strategy_name}")

        # Get existing strategy config from base_config (preserve all non-optimized params)
        if config_key not in config['strategies']:
            # Strategy config missing - this should not happen with correct key mapping
            raise ValueError(
                f"Strategy config key '{config_key}' not found in config.yaml. "
                f"Available keys: {list(config['strategies'].keys())}"
            )

        # Deep copy the existing config to preserve all parameters
        strategy_config = copy.deepcopy(config['strategies'][config_key])

        # Ensure entry and exit sections exist
        if 'entry' not in strategy_config:
            strategy_config['entry'] = {}
        if 'exit' not in strategy_config:
            strategy_config['exit'] = {}

        # Update ONLY the optimized parameters
        for param_name, param_value in params.items():
            section, key = self._parse_parameter_name(param_name)

            # Check if this parameter needs to be expanded
            expansion_map = self.PARAMETER_EXPANSION.get(self.strategy_type, {})
            if key in expansion_map:
                # Expand to multiple config keys (e.g., 'dte' -> 'dte_min' and 'dte_max')
                for expanded_key in expansion_map[key]:
                    strategy_config[section][expanded_key] = param_value
            else:
                # Use parameter as-is
                strategy_config[section][key] = param_value

        # Validate parameter formats to catch mismatches early
        if self.strategy_type == 'calendar':
            # Validate stop_loss is negative
            if 'stop_loss' in strategy_config.get('exit', {}):
                sl = strategy_config['exit']['stop_loss']
                if sl > 0:
                    raise ValueError(
                        f"stop_loss must be negative decimal (got {sl}). "
                        f"Use -0.50 for 50% loss, not 50."
                    )

            # Validate iv_percentile_max >= iv_percentile_min
            entry = strategy_config.get('entry', {})
            if 'iv_percentile_max' in entry and 'iv_percentile_min' in entry:
                if entry['iv_percentile_max'] < entry['iv_percentile_min']:
                    raise ValueError(
                        f"iv_percentile_max ({entry['iv_percentile_max']}) must be >= "
                        f"iv_percentile_min ({entry['iv_percentile_min']})"
                    )

            # Ensure iv_percentile_min has default if only max was set
            if 'iv_percentile_max' in entry and 'iv_percentile_min' not in entry:
                strategy_config['entry']['iv_percentile_min'] = 0

        elif self.strategy_type == 'vertical':
            # Validate stop_loss is between 0.0 and 1.0 (percentage of max loss)
            if 'stop_loss' in strategy_config.get('exit', {}):
                sl = strategy_config['exit']['stop_loss']
                if sl < 0.0 or sl > 1.0:
                    raise ValueError(
                        f"stop_loss must be between 0.0 and 1.0 (got {sl}). "
                        f"Use 0.50 for 50% of max loss, not 1.5 or -0.50."
                    )

        # Create strategy instance with merged config
        # CRITICAL: Pass only the strategy-specific portion of config (with 'entry'/'exit' at top level)
        # Not the full config! Strategy expects config['entry'], not config['strategies']['bull_put_spread']['entry']
        strategy = self.strategy_class(strategy_config)

        # Run backtest (verbose=False to avoid cluttering output during optimization)
        backtest_results = self.backtester.run_backtest(
            strategy=strategy,
            options_data=self.options_data,
            underlying_data=self.underlying_data,
            verbose=False  # Suppress per-backtest prints; progress bar shows overall progress
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
    short_delta_range: Tuple[float, float] = (0.25, 0.40),
    long_delta_range: Tuple[float, float] = (0.10, 0.25),
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
        short_delta_range: (min, max) for short leg delta
        long_delta_range: (min, max) for long leg delta
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
    optimizer.set_parameter_range('short_delta', min=short_delta_range[0], max=short_delta_range[1], step=0.05)
    optimizer.set_parameter_range('long_delta', min=long_delta_range[0], max=long_delta_range[1], step=0.05)
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
