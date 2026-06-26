#!/usr/bin/env python3
"""
Call Calendar Spread Parameter Optimization

Optimizes parameters for Call Calendar Spread strategy and saves results.
Designed to run unattended in Mac terminal, even with screen closed.

Two modes:
    DEFAULT (walk-forward validation) — optimize on an in-sample window, then score the chosen
        params on a held-out out-of-sample window the search never saw. Reports IS vs OOS Sharpe.
        This is the honest "does the edge survive?" test; use it to DECIDE whether to trade.
    --final — fit on the ENTIRE window with NO out-of-sample holdout. The production fit you run
        ONLY AFTER a default run confirms the edge survives OOS, to get live params from all data.

Usage:
    # DEFAULT: walk-forward validation (honest IS-vs-OOS). caffeinate prevents Mac sleep.
    caffeinate -i python optimize_call_calendar_spread.py
    #   optional: change the holdout fraction (default 0.30 = last 30% held out)
    caffeinate -i python optimize_call_calendar_spread.py --oos-frac=0.25

    # FINAL fit on all data, no holdout (only after walk-forward passes):
    caffeinate -i python optimize_call_calendar_spread.py --final

    # --TR overlays the SPY Trend Reversal entry gate (bullish-day entries only); combinable.
    # VIX IV-Rank gate is ON by default from config (call_calendar.entry.vix_rank_max, default 30):
    #   a long calendar is long vega, so enter only when vol is cheap vs its trailing year. Override
    #   per-run with --vix-rank=N, or turn it off with --no-vix-rank. Combinable with --TR.

Results saved to: optimization_results/CallCalendarSpread_YYYYMMDD_HHMMSS.csv
"""

import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Any
import yaml
import pandas as pd

# Suppress warnings for clean output
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import copy

from src.strategies.calendar_spreads import CallCalendarSpread
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
    print("CALL CALENDAR SPREAD OPTIMIZATION")
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


def load_data(config: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load options and underlying data (dataset is the config-derived synthetic file)."""
    print("Loading market data...")

    # Load options data -- the file named by config/config.yaml -> synthetic_data
    options_data: pd.DataFrame = load_sample_spy_options_data(config=config)

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
        strategy_type='calendar',
        strategy_class=CallCalendarSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )

    # Reflective parameter ranges (Optuna samples N_TRIALS of these, so the span is free —
    # runtime is governed by N_TRIALS below, not the combination count).
    #   * The far leg can't exceed the longest DTE actually present in the data, or those
    #     trials silently find no contract. We derive that cap from the loaded data (which is
    #     governed by config/config.yaml -> synthetic_data.max_dte at generation time) and
    #     round it down to the step grid -- no more hand-coding it against the generator.
    #   * near_dte < far_dte and vix_min < vix_max by construction (DISJOINT ranges: near {7..28}
    #     vs far {30..45}; vix_min {5..20} vs vix_max {25..60}), so no trial is wasted on those
    #     invalid orderings. The near_dte {7..28} and dte_exit {2..14} ranges OVERLAP, though, so
    #     dte_exit < near_dte CANNOT be guaranteed by the ranges — it is enforced as a runtime guard
    #     in ParameterOptimizer._run_single_backtest (dte_exit >= near_dte raises and is dropped),
    #     since dte_exit >= near_dte would force the calendar to exit on entry day.
    #   * STEP is deliberately fine (3): real chains list only a few expirations/day at irregular
    #     DTEs (e.g. DoltHub clusters near ~{13, 28, 60}). A coarse step-7 grid {42,49,56,63} can
    #     straddle the actual far expiration and find NO contract (far_dte=42 lands in a gap -> 1
    #     trade), so we sample densely and let the floor (min_trades) discard the gap-landing trials.
    FAR_DTE_STEP = 3
    FAR_DTE_FLOOR = 30
    # Research ceiling: externally-sourced consensus is a 30-45 DTE far leg (3:1-4:1 over a 7-14 DTE
    # near leg); 60+ DTE pairings show overfitting risk and drift off the real expiration grid. Cap
    # the search at 45 regardless of how far the data extends, so the optimizer can't wander into a
    # longer-dated region that isn't supported by the strategy literature.
    FAR_DTE_CEIL = 45
    # Cap far_dte at the longest REAL DTE, not the combined max. In hybrid mode the data
    # carries surface-fit fill out to synthetic_data.max_dte (~90); those rows beyond the
    # real grid (~66) are quadratic IV-surface EXTRAPOLATION, not quotes. Letting far_dte
    # reach them lets the optimizer game a fabricated far leg (far_dte=87 → $10k→$356M,
    # one trade +$92M). The 'is_fill' tag (hybrid loader) marks fill rows; when present,
    # cap on real-only DTE so the search stays inside data the market actually priced.
    if 'is_fill' in options_data.columns and (~options_data['is_fill']).any():
        data_max_dte = int(options_data.loc[~options_data['is_fill'], 'dte'].max())
    else:
        data_max_dte = int(options_data['dte'].max())
    far_dte_cap = min(FAR_DTE_CEIL, max(FAR_DTE_FLOOR, (data_max_dte // FAR_DTE_STEP) * FAR_DTE_STEP))

    optimizer.set_parameter_range('near_dte', min=7, max=28, step=7)        # sell the near leg (7-28)
    optimizer.set_parameter_range('far_dte', min=FAR_DTE_FLOOR, max=far_dte_cap, step=FAR_DTE_STEP)  # buy the far leg (30-45)
    optimizer.set_parameter_range('target_delta', min=0.45, max=0.55, step=0.05)  # ATM / slightly OTM
    optimizer.set_parameter_range('profit_target', min=0.10, max=0.60, step=0.10)
    optimizer.set_parameter_range('stop_loss', min=-0.50, max=-0.10, step=0.10)
    optimizer.set_parameter_range('vix_min', min=5, max=20, step=5)
    optimizer.set_parameter_range('vix_max', min=25, max=60, step=5)
    optimizer.set_parameter_range('dte_exit', min=2, max=14, step=3)        # close the near leg early

    total: int = optimizer.get_total_combinations()
    print(f"  ✓ Optimizer configured")
    print(f"  ✓ far_dte cap from data: max DTE {data_max_dte} → far_dte ∈ [{FAR_DTE_FLOOR}, {far_dte_cap}]")
    print(f"  ✓ Total combinations: {total:,}")
    print(f"  ⏱  Estimated runtime: {total * 1.5 / 60:.1f} - {total * 2 / 60:.1f} minutes\n")

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
        # ~15.9s per full-history backtest, so 1000 trials ~= 4.4h (under the 5h budget). Raise
        # only if you shorten the date range or speed up the engine.
        N_TRIALS = 1000
    else:
        # Use grid search for small search spaces
        MODE = 'grid'
        N_TRIALS = None  # Not used in grid mode

    # Quick override: --trials=N forces Optuna with N trials (e.g. a fast first pass on a big
    # dataset). On a 5-year history each backtest is several seconds, so 1000 trials runs hours;
    # --trials=150 gives a representative walk-forward in a fraction of the time.
    for _a in sys.argv:
        if _a.startswith('--trials='):
            MODE = 'optuna'
            N_TRIALS = int(_a.split('=', 1)[1])

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
    filename: str = f'CallCalendarSpread_{timestamp}.csv'
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
        strategy_name='CallCalendarSpread',
        config=config
    )
    print(f"✓ Compiled results saved to: {master_path}\n")


def run_walk_forward(config, options_data, underlying_data, entry_gate) -> int:
    """Optimize on an in-sample window, then score the chosen params on an untouched OOS window.

    This is the honest test: a real edge keeps most of its Sharpe out-of-sample; an overfit optimum
    collapses. Enable with `--wf` (and optionally `--oos-frac=0.25`).
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

    # Score those exact params on the held-out OOS window — from the OOS slice of ONE continuous
    # IS+OOS run (standard walk-forward), NOT an isolated OOS-only backtest. An isolated short window
    # under-trades badly (an early degenerate exit + low-capital sizing starve it: ~1 trade vs ~70
    # continuous), which produced false "overfit" NaN verdicts.
    oos = walk_forward.evaluate_oos_continuous(
        config, 'calendar', CallCalendarSpread, options_data, underlying_data,
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
            print("   Recommended: caffeinate -i python optimize_call_calendar_spread.py\n")

        config = load_configuration()
        options_data, underlying_data = load_data(config)

        # Entry gates (each a causal callable(date)->bool); multiple compose by logical AND.
        start = options_data['quote_date'].min().strftime('%Y-%m-%d')
        end = options_data['quote_date'].max().strftime('%Y-%m-%d')
        gates = []

        # --TR overlays the SPY Trend Reversal signal: only open trades on 'green' (bullish) days.
        if '--TR' in sys.argv:
            from src.utils.trend_gate import spy_trend_gate
            gates.append(spy_trend_gate(end, 'bull'))
            print("  --TR ON: gating entries to SPY Trend Reversal 'green' (bullish) days only.")

        # VIX IV-Rank gate: enter only when VIX IV-Rank <= threshold (a long calendar is long vega ->
        # cheap-vol entries; the SPY-correct way to apply "IV Rank < 30"). The threshold lives in
        # config (call_calendar.entry.vix_rank_max) like every other entry filter; it's built HERE,
        # not read inside the strategy, only because the 252d rank needs warmup history absent from the
        # per-day chain -> build once as a gate vs recompute per trial. CLI overrides for one-off runs:
        #   --vix-rank=N  use threshold N    --vix-rank  use config (or 30)    --no-vix-rank  disable
        cal_entry = config['strategies']['call_calendar']['entry']
        vix_rank_max = cal_entry.get('vix_rank_max')  # config default; None/null -> off
        cli = next((a for a in sys.argv if a == '--vix-rank' or a.startswith('--vix-rank=')), None)
        if '--no-vix-rank' in sys.argv:
            vix_rank_max = None
        elif cli is not None and '=' in cli:
            vix_rank_max = float(cli.split('=', 1)[1])
        elif cli is not None:
            vix_rank_max = vix_rank_max if vix_rank_max is not None else 30.0
        if vix_rank_max is not None:
            from src.utils.vix_gate import vix_rank_gate
            gates.append(vix_rank_gate(start, end, max_rank=float(vix_rank_max)))
            print(f"  VIX IV-Rank gate ON: entries only when VIX IV-Rank <= {float(vix_rank_max):.0f} "
                  f"(config vix_rank_max; --no-vix-rank to disable).")

        if gates:
            entry_gate = gates[0] if len(gates) == 1 else (lambda d, _g=tuple(gates): all(g(d) for g in _g))
            print()
        else:
            entry_gate = None

        # Walk-forward validation is the DEFAULT: optimize on an in-sample window, then score the
        # chosen params on a held-out out-of-sample window the search never saw (the honest overfit
        # check). The bare in-sample number is optimistic by construction — you searched 1000 trials
        # and kept the max — so it must not be the default deliverable.
        #   --final  : skip the holdout and fit on the ENTIRE window (production fit; do this ONLY
        #              after a walk-forward run shows the edge survives OOS).
        #   --wf     : still accepted as an explicit alias for the (now default) walk-forward mode.
        if '--final' not in sys.argv:
            return run_walk_forward(config, options_data, underlying_data, entry_gate)

        print("MODE: FINAL FIT — optimizing over the ENTIRE window with NO out-of-sample holdout.")
        print("      The reported Sharpe is in-sample only; trust it only after a default/--wf run")
        print("      has shown the edge survives OOS. Use these params for live trading.\n")
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
