"""
Results Compiler for Optimization Runs

Automatically compiles optimization results from multiple runs into a single
master CSV per strategy and date range. Handles deduplication by keeping the
most recent result for each unique parameter combination.

Usage:
    from src.optimization.results_compiler import compile_results

    master_path = compile_results(
        new_results=results_df,
        strategy_name='BullPutSpread',
        config=config
    )
"""

from pathlib import Path
from typing import Dict, Tuple, List, Any
import pandas as pd


def get_date_range_from_config(config: Dict[str, Any]) -> Tuple[str, str]:
    """
    Extract backtest date range from config.

    Args:
        config: Configuration dictionary with backtest section

    Returns:
        Tuple of (start_date, end_date) formatted as YYYYMMDD strings

    Example:
        >>> config = {'backtest': {'start_date': '2025-01-03', 'end_date': '2025-11-17'}}
        >>> get_date_range_from_config(config)
        ('20250103', '20251117')
    """
    start_date: str = config['backtest']['start_date']
    end_date: str = config['backtest']['end_date']

    # Convert from YYYY-MM-DD to YYYYMMDD for filename
    start_formatted: str = start_date.replace('-', '')
    end_formatted: str = end_date.replace('-', '')

    return start_formatted, end_formatted


def get_master_csv_path(strategy_name: str, date_start: str, date_end: str) -> Path:
    """
    Generate path for master compiled CSV file.

    Args:
        strategy_name: Name of strategy (e.g., 'BullPutSpread')
        date_start: Start date as YYYYMMDD string
        date_end: End date as YYYYMMDD string

    Returns:
        Path to master CSV file

    Example:
        >>> get_master_csv_path('BullPutSpread', '20250103', '20251117')
        PosixPath('optimization_results/compiled/BullPutSpread_compiled_20250103_20251117.csv')
    """
    # Create compiled directory if it doesn't exist
    compiled_dir: Path = Path('optimization_results/compiled')
    compiled_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with strategy name and date range
    filename: str = f'{strategy_name}_compiled_{date_start}_{date_end}.csv'
    filepath: Path = compiled_dir / filename

    return filepath


def identify_parameter_columns(df: pd.DataFrame) -> List[str]:
    """
    Identify which columns are parameters vs metrics.

    Parameter columns come first in the DataFrame and have specific types.
    Metric columns include things like sharpe_ratio, total_return_pct, etc.

    Args:
        df: Results DataFrame

    Returns:
        List of parameter column names

    Note:
        This uses exact matching against known metric column names from
        calculate_performance_metrics(). Everything else is a parameter.
    """
    # Known metric columns from calculate_performance_metrics()
    # These are the exact column names produced by the metrics calculation
    known_metrics: List[str] = [
        'initial_capital',
        'final_value',
        'total_pnl',
        'total_return_pct',
        'annualized_return_pct',
        'sharpe_ratio',
        'sortino_ratio',
        'max_drawdown_pct',
        'calmar_ratio',
        'volatility_pct',
        'total_trades',
        'winning_trades',
        'losing_trades',
        'win_rate_pct',
        'avg_win',
        'avg_loss',
        'largest_win',
        'largest_loss',
        'profit_factor',
        'avg_days_in_trade',
        'positive_months',
        'total_months',
        'positive_months_pct',
        'best_month_pct',
        'worst_month_pct',
        'avg_monthly_return_pct'
    ]

    # Identify parameter columns: those that are NOT in known metrics list
    param_columns: List[str] = []

    for col in df.columns:
        if col not in known_metrics:
            param_columns.append(col)

    return param_columns


def compile_results(
    new_results: pd.DataFrame,
    strategy_name: str,
    config: Dict[str, Any]
) -> Path:
    """
    Compile optimization results into master CSV.

    This function:
    1. Loads existing master CSV if it exists
    2. Identifies parameter columns (for deduplication key)
    3. Merges new results with existing results
    4. For duplicate parameter combinations, keeps the newest result
    5. Sorts by sharpe_ratio descending
    6. Saves to master CSV

    Args:
        new_results: DataFrame with new optimization results
        strategy_name: Name of strategy (e.g., 'BullPutSpread')
        config: Configuration dictionary with backtest date range

    Returns:
        Path to saved master CSV file

    Example:
        >>> master_path = compile_results(
        ...     new_results=optimizer_results_df,
        ...     strategy_name='BullPutSpread',
        ...     config=config_dict
        ... )
        >>> print(f"Compiled results saved to: {master_path}")
    """
    # Get date range for filename
    date_start, date_end = get_date_range_from_config(config)

    # Get master CSV path
    master_path: Path = get_master_csv_path(strategy_name, date_start, date_end)

    # Identify parameter columns for deduplication
    param_columns: List[str] = identify_parameter_columns(new_results)

    # Load existing master CSV if it exists
    if master_path.exists():
        existing_results: pd.DataFrame = pd.read_csv(master_path)

        # Combine new and existing results
        combined: pd.DataFrame = pd.concat([existing_results, new_results], ignore_index=True)

        # Remove duplicates: keep last (most recent) for each parameter combination
        # This means new results overwrite old results for same parameters
        combined = combined.drop_duplicates(subset=param_columns, keep='last')

    else:
        # No existing results, use new results as-is
        combined = new_results.copy()

    # Sort by sharpe_ratio descending (best results first)
    if 'sharpe_ratio' in combined.columns:
        combined = combined.sort_values('sharpe_ratio', ascending=False)

    # Reset index for clean sequential numbering
    combined = combined.reset_index(drop=True)

    # Save to master CSV
    combined.to_csv(master_path, index=False)

    return master_path


def get_completed_combinations(
    strategy_name: str,
    config: Dict[str, Any]
) -> pd.DataFrame:
    """
    Load previously completed parameter combinations from master CSV.

    This is used by the optimizer to skip already-tested combinations
    and avoid redundant computation.

    Args:
        strategy_name: Name of strategy (e.g., 'BullPutSpread')
        config: Configuration dictionary with backtest date range

    Returns:
        DataFrame with completed results, or empty DataFrame if no master exists

    Example:
        >>> completed = get_completed_combinations('BullPutSpread', config)
        >>> if not completed.empty:
        ...     print(f"Found {len(completed)} previously tested combinations")
    """
    # Get date range for filename
    date_start, date_end = get_date_range_from_config(config)

    # Get master CSV path
    master_path: Path = get_master_csv_path(strategy_name, date_start, date_end)

    # Load if exists, otherwise return empty DataFrame
    if master_path.exists():
        return pd.read_csv(master_path)
    else:
        return pd.DataFrame()
