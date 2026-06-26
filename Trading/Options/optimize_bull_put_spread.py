#!/usr/bin/env python3
"""
Bull Put Spread Parameter Optimization

Optimizes parameters for Bull Put Spread strategy and saves results.
Designed to run unattended in Mac terminal, even with screen closed.

Two modes:
    DEFAULT (walk-forward validation) — optimize on an in-sample window, then score the chosen
        params on a held-out out-of-sample window the search never saw. Reports IS vs OOS Sharpe.
        The honest "does the edge survive?" test; use it to DECIDE whether to trade.
    --final — fit on the ENTIRE window with NO out-of-sample holdout. The production fit you run
        ONLY AFTER a default run confirms the edge survives OOS, to get live params from all data.

Usage:
    # DEFAULT: walk-forward validation (honest IS-vs-OOS). caffeinate prevents Mac sleep.
    caffeinate -i python optimize_bull_put_spread.py
    #   optional: change the holdout fraction (default 0.30 = last 30% held out)
    caffeinate -i python optimize_bull_put_spread.py --oos-frac=0.25

    # FINAL fit on all data, no holdout (only after walk-forward passes):
    caffeinate -i python optimize_bull_put_spread.py --final

Results saved to: optimization_results/BullPutSpread_YYYYMMDD_HHMMSS.csv
"""

import sys
import os
import copy
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Any
import yaml
import pandas as pd

# Suppress warnings for clean output
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
# This line is not necessary if code is run in correct directory
# sys.path.insert(0, str(Path(__file__).parent))

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization.parameter_optimizer import ParameterOptimizer, add_stability_scores
from src.optimization.results_compiler import compile_results
from src.optimization import walk_forward
from src.analysis.overfitting import summarize_overfitting


def print_header() -> None:
    """Print script header."""
    print("\n" + "="*70)
    print("BULL PUT SPREAD OPTIMIZATION")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")


def load_configuration() -> Dict[str, Any]:
    """Load configuration from config.yaml."""
    print("Loading configuration...")
    with open('config/config.yaml', 'r') as f:
        config: Dict[str, Any] = yaml.safe_load(f)
    print("  ✓ Configuration loaded\n")
    return config


def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load options and underlying data."""
    print("Loading market data...")

    # Load options data
    options_data: pd.DataFrame = load_sample_spy_options_data()

    # Load underlying data
    start_date: str = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end_date: str = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data: pd.DataFrame = fetch_spy_data(start_date, end_date)

    print(f"  ✓ Options data: {len(options_data):,} rows")
    print(f"  ✓ Underlying data: {len(underlying_data):,} rows")
    print(f"  ✓ Date range: {start_date} to {end_date}\n")

    return options_data, underlying_data


def setup_optimizer(config: Dict[str, Any], options_data: pd.DataFrame, underlying_data: pd.DataFrame,
                    entry_gate=None) -> ParameterOptimizer:
    """Create and configure parameter optimizer (optionally with a SPY Trend Reversal entry gate)."""
    print("Setting up optimizer...")

    backtester: OptopsyBacktester = OptopsyBacktester(config, entry_gate=entry_gate)

    optimizer: ParameterOptimizer = ParameterOptimizer(
        strategy_type='vertical',
        strategy_class=BullPutSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )

    # Reflective credit-vertical ranges (tastytrade's ~200k-trade study: 30-45 DTE entry, 16-30 delta
    # short, manage at ~50% profit / ~21 DTE, in elevated IV). short_delta > long_delta = real credit.
    optimizer.set_parameter_range('dte', min=30, max=45, step=5)                  # 30-45 DTE
    optimizer.set_parameter_range('short_delta', min=0.16, max=0.30, step=0.02)   # sell 16-30 delta
    optimizer.set_parameter_range('long_delta', min=0.08, max=0.16, step=0.02)    # protective wing
    optimizer.set_parameter_range('profit_target', min=0.40, max=0.60, step=0.05) # manage ~50%
    optimizer.set_parameter_range('stop_loss', min=-0.60, max=-0.30, step=0.10)   # % of max loss
    optimizer.set_parameter_range('dte_min', min=18, max=24, step=2)              # exit near 21 DTE
    optimizer.set_parameter_range('vix', min=15, max=40, step=5)                  # premium-rich IV

    total: int = optimizer.get_total_combinations()
    print(f"  ✓ Optimizer configured")
    print(f"  ✓ Total combinations: {total:,}\n")

    return optimizer


def run_optimization(optimizer: ParameterOptimizer) -> pd.DataFrame:
    """Run the parameter optimization."""

    # ========================================================================
    # OPTIMIZATION MODE CONFIGURATION
    # ========================================================================
    # Choose optimization mode based on search space size
    total_combinations: int = optimizer.get_total_combinations()

    # RECOMMENDED: Use Optuna for large search spaces (>1000 combinations)
    if total_combinations > 1000:
        MODE = 'optuna'
        N_TRIALS = 1500  # 200-1000 recommended
    else:
        # Use grid search for small search spaces
        MODE = 'grid'
        N_TRIALS = None  # Not used in grid mode

    # OVERRIDE: Uncomment to force a specific mode
    # MODE = 'optuna'
    # N_TRIALS = 500

    # MODE = 'grid'
    # ========================================================================

    print("Starting optimization...")
    print(f"Mode: {MODE.upper()}")

    if MODE == 'optuna':
        print(f"Trials: {N_TRIALS:,} (out of {total_combinations:,} possible)")
        print(f"Expected speedup: ~{total_combinations / N_TRIALS:.0f}x faster")
        print("(Progress bar will appear below - this may take several minutes)\n")

        # Run Optuna optimization
        results: pd.DataFrame = optimizer.run_optimization(
            mode='optuna',
            n_trials=N_TRIALS,
            optimization_metric='sharpe_ratio',
            optuna_n_startup_trials=20,  # Random exploration first
            optuna_enable_pruning=True   # Stop unpromising trials early
        )
    else:
        print(f"Total combinations: {total_combinations:,}")
        print("(Progress bar will appear below - this may take a while)\n")

        # Run grid search optimization
        results: pd.DataFrame = optimizer.run_optimization(
            mode='grid',
            optimization_metric='sharpe_ratio',
            confirm=False,  # No user input needed for unattended run
            num_samples=3,
            checkpoint_every=10  # Save progress every 10 combinations
        )

    return results


def save_results(results: pd.DataFrame, optimizer: ParameterOptimizer, config: Dict[str, Any]) -> None:
    """Save optimization results to CSV and compile into master."""
    # Create results directory if it doesn't exist
    results_dir: Path = Path('optimization_results')
    results_dir.mkdir(exist_ok=True)

    # Generate filename with timestamp
    timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename: str = f'BullPutSpread_{timestamp}.csv'
    filepath: Path = results_dir / filename

    # Add neighborhood-stability scores so robust plateaus are visible next to lucky spikes.
    results = add_stability_scores(results, optimizer.parameter_ranges, metric='sharpe_ratio')

    # Save full results
    results.to_csv(filepath, index=False)

    # Get best parameters (top 5 from already-sorted results)
    best: pd.DataFrame = results.head(5)

    # Determine which columns to display (parameters + key metrics)
    param_cols: list = list(optimizer.parameter_ranges.keys())
    metric_cols: list = ['sharpe_ratio', 'stability_score', 'total_return_pct',
                         'max_drawdown_pct', 'win_rate_pct']
    display_cols: list = [col for col in param_cols + metric_cols if col in best.columns]

    # Print summary
    print("\n" + "="*70)
    print("OPTIMIZATION COMPLETE")
    print("="*70)
    print(f"Results saved to: {filepath}")
    print(f"Total combinations tested: {len(results):,}")
    print(f"\nTOP 5 PARAMETER COMBINATIONS:")
    print("-"*70)
    print(best[display_cols].to_string(index=False))
    print("="*70)

    # Overfitting check: deflate the best Sharpe for the number of trials searched.
    bt = config.get('backtest', {})
    n_obs = max(len(pd.bdate_range(bt.get('start_date'), bt.get('end_date'))), 2)
    try:
        diag = summarize_overfitting(results, n_obs=n_obs, metric='sharpe_ratio')
        print("OVERFITTING / SELECTION CHECK (deflated Sharpe):")
        print(f"  {diag.get('note', diag)}")
        print("="*70)
    except Exception as exc:  # never let reporting break a completed run
        print(f"  (deflated-Sharpe check skipped: {exc})")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    # Compile results into master CSV
    print("Compiling results into master CSV...")
    master_path: Path = compile_results(
        new_results=results,
        strategy_name='BullPutSpread',
        config=config
    )
    print(f"✓ Compiled results saved to: {master_path}\n")


def run_walk_forward(config, options_data, underlying_data, entry_gate) -> int:
    """Optimize on an in-sample window, then score the chosen params on an untouched OOS window.

    The honest test: a real edge keeps most of its Sharpe out-of-sample; an overfit optimum
    collapses. This is the DEFAULT mode (--final fits on the whole window instead). Tune the split
    with --oos-frac=0.25.
    """
    from src.optimization.parameter_optimizer import sort_results_stable

    bt = config['backtest']
    oos_frac = 0.30
    for a in sys.argv:
        if a.startswith('--oos-frac='):
            oos_frac = float(a.split('=', 1)[1])

    is_win, oos_win = walk_forward.split_window(bt['start_date'], bt['end_date'], oos_frac)
    print("\n" + "=" * 70)
    print(f"WALK-FORWARD  in-sample {is_win[0]}..{is_win[1]}  |  out-of-sample {oos_win[0]}..{oos_win[1]}")
    print("=" * 70 + "\n")

    # Optimize on IS only.
    is_config = copy.deepcopy(config)
    is_config['backtest']['start_date'], is_config['backtest']['end_date'] = is_win
    optimizer = setup_optimizer(is_config, options_data, underlying_data, entry_gate)
    results = sort_results_stable(run_optimization(optimizer), 'sharpe_ratio')

    # Pull the chosen (best IS) parameters, casting integral grid values back to int.
    row = results.iloc[0]
    def _cast(v):
        f = float(v)
        return int(f) if f.is_integer() else f
    best_params = {p: _cast(row[p]) for p in optimizer.parameter_ranges.keys() if p in row}

    # Score on the held-out OOS window from the OOS slice of ONE continuous IS+OOS run (standard
    # walk-forward), not an isolated OOS-only backtest (which under-trades short windows).
    oos = walk_forward.evaluate_oos_continuous(
        config, 'vertical', BullPutSpread, options_data, underlying_data,
        (is_win[0], oos_win[1]), oos_win[0], best_params, entry_gate,
    )
    is_sharpe = float(row['sharpe_ratio'])
    oos_sharpe = float(oos.get('sharpe_ratio', float('nan')))

    print("\n" + "=" * 70)
    print("WALK-FORWARD RESULT (best in-sample params scored on the untouched OOS window)")
    print("=" * 70)
    print(f"  params: {best_params}")
    print(f"  IS  Sharpe: {is_sharpe:7.3f}  | IS  return: {float(row.get('total_return_pct', float('nan'))):7.2f}%")
    print(f"  OOS Sharpe: {oos_sharpe:7.3f}  | OOS return: {float(oos.get('total_return_pct', float('nan'))):7.2f}%"
          f"  | OOS trades: {oos.get('total_trades', '?')}")
    if 'error' in oos:
        print(f"  OOS note: {oos['error']}")
    if oos_sharpe > 1.0 and oos_sharpe > 0.5 * is_sharpe:
        verdict = 'healthy — edge survives OOS'
    elif oos_sharpe > 0.5:
        verdict = 'edge persists but weaker — degraded, not collapsed'
    else:
        verdict = 'collapse — treat the IS optimum as overfit'
    print(f"  IS→OOS Sharpe drop: {is_sharpe - oos_sharpe:7.3f}  ({verdict})")
    print("=" * 70 + "\n")

    save_results(results, optimizer, is_config)
    return 0


def main() -> int:
    """Main execution function."""
    try:
        print_header()

        # Check if running with caffeinate
        if 'caffeinate' not in ' '.join(os.popen('ps aux | grep caffeinate').read().split()):
            print("⚠️  WARNING: Not running with caffeinate!")
            print("   Mac may sleep during optimization (especially on battery)")
            print("   Recommended: caffeinate -i python optimize_bull_put_spread.py\n")

        config = load_configuration()
        options_data, underlying_data = load_data()

        # --TR overlays the SPY Trend Reversal signal: only open trades on 'green' (bullish) days.
        entry_gate = None
        if '--TR' in sys.argv:
            from src.utils.trend_gate import spy_trend_gate
            end = options_data['quote_date'].max().strftime('%Y-%m-%d')
            entry_gate = spy_trend_gate(end, 'bull')
            print("  --TR ON: gating entries to SPY Trend Reversal 'green' (bullish) days only.\n")

        # Walk-forward validation is the DEFAULT (optimize in-sample, score out-of-sample). The bare
        # in-sample Sharpe is optimistic by construction, so it must not be the default deliverable.
        #   --final : skip the holdout, fit on the ENTIRE window (production fit — only after a
        #             default run shows the edge survives OOS). --wf is an alias for the default.
        if '--final' not in sys.argv:
            return run_walk_forward(config, options_data, underlying_data, entry_gate)

        print("MODE: FINAL FIT — optimizing over the ENTIRE window with NO out-of-sample holdout.")
        print("      Trust this Sharpe only after a default/--wf run has shown the edge survives OOS.\n")
        optimizer = setup_optimizer(config, options_data, underlying_data, entry_gate)
        results = run_optimization(optimizer)
        save_results(results, optimizer, config)

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Optimization interrupted by user (Ctrl+C)")
        print("Partial results saved in optimization_checkpoints/ directory")
        return 1

    except Exception as e:
        print(f"\n\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
