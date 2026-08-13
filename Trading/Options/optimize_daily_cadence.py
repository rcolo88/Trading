#!/usr/bin/env python3
"""
Bull Put Spread Parameter Optimization -- DAILY-CADENCE model (2026-08-10, corrected 2026-08-11)

Every prior optimization run in this project (including the 2026-08-09/10 low-delta overnight
run) sized positions off a shared risk-budget pool (max_risk_percent of current equity, spent
first-come across whatever's open) -- a model that throttles entries and rarely lets more than
2-4 positions run concurrently. That does NOT match how the user actually trades: one new spread
EVERY trading day, fixed size, regardless of what else is open, picking the expiration closest to
a DTE target and closing at a DTE floor or profit target. Every finding in this project's
CHANGELOG/README up to this point was validated against the wrong capital-allocation policy.

This script searches DTE target, DTE-min exit, profit target, and stop loss -- the four things
the user explicitly asked to re-derive for their real cadence -- jointly with short_delta and
EITHER long_delta (delta-selected wing) or strike_width (fixed-dollar wing anchored to wherever
the short-delta strike lands, i.e. "20 delta located, then subtract $5/$10/$15"). strike_width
takes precedence over long_delta in the entry logic, so the two wing types can't be searched in
one trial -- run this script twice, once per --width flag.

position_sizing.method: fixed_contracts, contracts_per_trade: 1 (config.yaml, 2026-08-10) --
always the same 1-contract size, no risk-budget gate. Uses the 2018-2026 window (the only
real-quote-grounded pricing in this project).

Also the first run since the long_delta < short_delta validation guard was added to
parameter_optimizer.py -- the 2026-08-09/10 overnight run had 363/650 trials (56%) land on an
inverted (long_delta > short_delta), degenerate structure, including its reported "best" result
(Sharpe 3.41, 100% win rate, $0 avg loss). That combination now raises during config validation
and is skipped before a backtest ever runs, instead of silently producing a fake winner.

2026-08-11 correction: two bugs fixed, both making every result before this date optimistic on
the protective (long) wing specifically. (1) The IV surface's put/call skew quadratics were
extrapolated UNBOUNDED past where skew_calibration.py actually fit them (m in [-0.20,0]/[0,0.06]),
hitting 11x by m=-0.67 on a low-spot day -- 17-50%/year of the 20-45 DTE / 0.05-0.35 delta search
space priced on this extrapolation, worst in exactly the volatile years (2018, 2020) that dominate
the IS side of the walk-forward split. Fixed: continues linearly at the quadratic's own slope at
the knot instead (synthetic_generator.py::_iv_surface). (2) The strike grid was a FIXED $5/+-$100
band -- +/-45% of spot in 2020 vs +/-13% in 2026, so a 0.10-0.20 delta long wing was literally
UNREACHABLE on crisis days (verified: 2020-03-23 minimum available |delta| was 0.105). Fixed: a
vol-adaptive delta_band grid ($1 spacing across |delta| in [0.02,0.60], reachable in every era) --
see synthetic_generator.py::generate_delta_band_strikes. Also: load_data() below used to silently
re-read config.yaml from disk (ignoring any in-memory window/grid override) and the backtester
re-copied+re-processed the entire multi-year DataFrame on every single trial -- both fixed. This
run uses the corrected data by default; pass --legacy-grid to reproduce the OLD (coarse-grid,
unbounded-skew) results for an A/B comparison. See DAILY_CADENCE_STRATEGY.md for before/after.

Usage:
    caffeinate -i opt_venv/bin/python optimize_daily_cadence.py            # delta-selected wing
    caffeinate -i opt_venv/bin/python optimize_daily_cadence.py --width    # fixed-$ wing
    # add --final to fit on the whole window with no OOS holdout (only after a --wf pass looks healthy)
    # add --legacy-grid to reproduce the pre-2026-08-11 coarse-grid/unbounded-skew results

Results saved to: optimization_results/BullPutSpreadDailyCadence[Width][_legacygrid]_YYYYMMDD_HHMMSS.csv
"""

import sys
import os
import copy
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Any
import yaml
import pandas as pd

import warnings
warnings.filterwarnings('ignore')

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization.parameter_optimizer import ParameterOptimizer, add_stability_scores, sort_results_stable
from src.optimization.results_compiler import compile_results
from src.optimization import walk_forward
from src.analysis.overfitting import summarize_overfitting
from src.analysis import regime

WIDTH_MODE = '--width' in sys.argv
STRATEGY_LABEL = 'BullPutSpreadDailyCadenceWidth' if WIDTH_MODE else 'BullPutSpreadDailyCadence'
WINDOW = ("2018-01-02", "2026-07-09")

# Purge/embargo (2026-08-11): no new IS entries in the final EMBARGO_TRADING_DAYS of the IS
# window, so no IS-scored trade is force-closed at the boundary before its own exit condition
# could fire. Sized to the worst-case trade duration this search space can produce: dte up to 45
# +/- dte_tolerance (5) = entries up to 50 calendar days out, held open until dte_min exit as low
# as 5 -> ~45 calendar days -> ~32 trading days; rounded up with margin. See run_walk_forward().
EMBARGO_TRADING_DAYS = 40


def print_header() -> None:
    print("\n" + "=" * 70)
    print(f"BULL PUT SPREAD OPTIMIZATION -- DAILY CADENCE ({'WIDTH' if WIDTH_MODE else 'DELTA'} WING)")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")


def load_configuration() -> Dict[str, Any]:
    print("Loading configuration...")
    with open('config/config.yaml', 'r') as f:
        config: Dict[str, Any] = yaml.safe_load(f)
    config['backtest']['start_date'], config['backtest']['end_date'] = WINDOW
    config['backtest']['initial_capital'] = 150000
    config['position_sizing']['method'] = 'fixed_contracts'
    config['position_sizing']['contracts_per_trade'] = 1
    # 2026-08-11: run against the corrected dataset (skew-tail fix + $1 vol-adaptive delta-band
    # grid, replacing the $5/+-$100 fixed grid every earlier run in this project used) unless
    # --legacy-grid explicitly asks for the old coarse-grid file (e.g. to A/B against prior
    # results). synthetic_data_filename() resolves this to a DIFFERENT file (grid mode is encoded
    # in the filename), so this can never silently mix pricing regimes.
    if '--legacy-grid' not in sys.argv:
        config['synthetic_data']['grid_mode'] = 'delta_band'
    print(f"  ✓ Configuration loaded (fixed_contracts=1, 2018-2026 window, $150k, "
          f"grid_mode={config['synthetic_data']['grid_mode']})\n")
    return config


def load_data(config: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("Loading market data...")
    # BUG (fixed 2026-08-11): this used to call load_sample_spy_options_data() with NO config,
    # which silently re-reads config/config.yaml from disk -- ignoring whatever load_configuration()
    # just built in memory (WINDOW override, grid_mode, etc). Any override was a no-op until this
    # threaded `config` through explicitly (run_full_span_backtest.py already did this correctly).
    options_data: pd.DataFrame = load_sample_spy_options_data(config=config)
    start_date: str = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end_date: str = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data: pd.DataFrame = fetch_spy_data(start_date, end_date)
    print(f"  ✓ Options data: {len(options_data):,} rows")
    print(f"  ✓ Underlying data: {len(underlying_data):,} rows")
    print(f"  ✓ Date range: {start_date} to {end_date}\n")
    return options_data, underlying_data


def setup_optimizer(config: Dict[str, Any], options_data: pd.DataFrame, underlying_data: pd.DataFrame,
                     entry_gate=None) -> ParameterOptimizer:
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

    # dte: TARGET, strategy pins the expiration closest to it (+/- dte_tolerance=5 default).
    optimizer.set_parameter_range('dte', min=21, max=45, step=3)
    optimizer.set_parameter_range('short_delta', min=0.15, max=0.35, step=0.02)
    if WIDTH_MODE:
        # Fixed-$ wing anchored to the short-delta strike (short_strike -/+ strike_width).
        optimizer.set_parameter_range('strike_width', min=5, max=20, step=5)
    else:
        # Lower bound widened 0.05 -> 0.03 (2026-08-11): the corrected delta_band grid's fine
        # region reaches ~0.02 abs delta by construction (see synthetic_generator.py), so a target
        # this low is now actually reachable rather than silently skipped/snapped on most days --
        # the whole point of re-running this search on corrected data.
        optimizer.set_parameter_range('long_delta', min=0.03, max=0.33, step=0.02)
        # long_delta >= short_delta is now rejected by parameter_optimizer's validation guard
        # (added 2026-08-10) before a backtest ever runs -- see module docstring.
    optimizer.set_parameter_range('profit_target', min=0.20, max=0.90, step=0.10)
    optimizer.set_parameter_range('stop_loss', min=0.10, max=0.90, step=0.10)
    optimizer.set_parameter_range('dte_min', min=5, max=25, step=2)

    total: int = optimizer.get_total_combinations()
    print(f"  ✓ Optimizer configured")
    print(f"  ✓ Total combinations: {total:,}\n")
    return optimizer


# Suffix by mode so a --final (whole-window) run never resumes from a walk-forward (IS-window-only)
# study, or vice versa -- same study_name inside each file, but the backtest window each trial was
# scored on differs, so mixing them would silently corrupt the resumed study. Also suffixed by grid
# (2026-08-11): a study whose trials were scored on the OLD $5-grid/unbounded-skew pricing must
# never be resumed into a run scored on the corrected data -- the Sharpe values aren't comparable,
# so mixing them would silently corrupt the resumed study exactly like an IS/final mismatch would.
STORAGE_PATH = str(Path('optimization_checkpoints') /
                    f"optuna_{STRATEGY_LABEL}"
                    f"_{'legacygrid' if '--legacy-grid' in sys.argv else 'db1'}"
                    f"_{'final' if '--final' in sys.argv else 'wf'}.db")


def run_optimization(optimizer: ParameterOptimizer, n_trials: int) -> pd.DataFrame:
    total_combinations: int = optimizer.get_total_combinations()
    print("Starting optimization...")
    print(f"Mode: OPTUNA")
    print(f"Trials: {n_trials:,} (out of {total_combinations:,} possible)")
    print(f"Expected speedup: ~{total_combinations / n_trials:.0f}x faster")
    print(f"Resumable storage: {STORAGE_PATH}\n")
    results: pd.DataFrame = optimizer.run_optimization(
        mode='optuna',
        n_trials=n_trials,
        optimization_metric='sharpe_ratio',
        optuna_n_startup_trials=20,
        optuna_enable_pruning=True,
        optuna_storage_path=STORAGE_PATH
    )
    return results


def save_results(results: pd.DataFrame, optimizer: ParameterOptimizer, config: Dict[str, Any]) -> None:
    results_dir: Path = Path('optimization_results')
    results_dir.mkdir(exist_ok=True)
    timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename: str = f'{STRATEGY_LABEL}_{timestamp}.csv'
    filepath: Path = results_dir / filename

    results = add_stability_scores(results, optimizer.parameter_ranges, metric='sharpe_ratio')
    results.to_csv(filepath, index=False)

    best: pd.DataFrame = results.head(5)
    param_cols: list = list(optimizer.parameter_ranges.keys())
    metric_cols: list = ['sharpe_ratio', 'stability_score', 'total_return_pct',
                          'max_drawdown_pct', 'win_rate_pct', 'total_trades']
    display_cols: list = [col for col in param_cols + metric_cols if col in best.columns]

    print("\n" + "=" * 70)
    print("OPTIMIZATION COMPLETE")
    print("=" * 70)
    print(f"Results saved to: {filepath}")
    print(f"Total combinations tested: {len(results):,}")
    print(f"\nTOP 5 PARAMETER COMBINATIONS:")
    print("-" * 70)
    print(best[display_cols].to_string(index=False))
    print("=" * 70)

    bt = config.get('backtest', {})
    n_obs = max(len(pd.bdate_range(bt.get('start_date'), bt.get('end_date'))), 2)
    try:
        diag = summarize_overfitting(results, n_obs=n_obs, metric='sharpe_ratio')
        print("OVERFITTING / SELECTION CHECK (deflated Sharpe):")
        print(f"  {diag.get('note', diag)}")
        print("=" * 70)
    except Exception as exc:
        print(f"  (deflated-Sharpe check skipped: {exc})")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    print("Compiling results into master CSV...")
    master_path: Path = compile_results(new_results=results, strategy_name=STRATEGY_LABEL, config=config)
    print(f"✓ Compiled results saved to: {master_path}\n")


def run_walk_forward(config, options_data, underlying_data, n_trials) -> int:
    """Optimize on IS only, score on untouched OOS -- same pattern as optimize_bull_put_spread.py."""
    oos_frac = 0.30
    for a in sys.argv:
        if a.startswith('--oos-frac='):
            oos_frac = float(a.split('=', 1)[1])

    is_win, oos_win = walk_forward.split_window(WINDOW[0], WINDOW[1], oos_frac)
    print("\n" + "=" * 70)
    print(f"WALK-FORWARD  in-sample {is_win[0]}..{is_win[1]}  |  out-of-sample {oos_win[0]}..{oos_win[1]}")
    print("=" * 70 + "\n")

    is_config = copy.deepcopy(config)
    is_config['backtest']['start_date'], is_config['backtest']['end_date'] = is_win

    # Purge/embargo (2026-08-11, see EMBARGO_TRADING_DAYS): block NEW entries in the final stretch
    # of the IS window so no IS-scored trade is force-closed at the boundary before its own exit
    # condition could fire -- exits still fire normally past the cutoff (entry_gate only blocks
    # entries), so a position opened before the cutoff still runs its natural course.
    is_bdays = pd.bdate_range(is_win[0], is_win[1])
    embargo_cutoff = is_bdays[-EMBARGO_TRADING_DAYS] if len(is_bdays) > EMBARGO_TRADING_DAYS else is_bdays[0]
    entry_gate = lambda d: pd.Timestamp(d) <= embargo_cutoff
    print(f"  Embargo: no new IS entries after {embargo_cutoff.date()} "
          f"(last {EMBARGO_TRADING_DAYS} trading days of the IS window)\n")

    optimizer = setup_optimizer(is_config, options_data, underlying_data, entry_gate=entry_gate)
    results = sort_results_stable(run_optimization(optimizer, n_trials), 'sharpe_ratio')

    row = results.iloc[0]
    def _cast(v):
        f = float(v)
        return int(f) if f.is_integer() else f
    best_params = {p: _cast(row[p]) for p in optimizer.parameter_ranges.keys() if p in row}

    oos = walk_forward.evaluate_oos_continuous(
        config, 'vertical', BullPutSpread, options_data, underlying_data,
        (is_win[0], oos_win[1]), oos_win[0], best_params, None,
    )
    is_sharpe = float(row['sharpe_ratio'])
    oos_sharpe = float(oos.get('sharpe_ratio', float('nan')))

    # Regime-conditional breakdown (Phase 4, 2026-08-11): calm vs. stress Sharpe/maxDD/win-rate for
    # the winning params on BOTH windows -- reported alongside, never blended into the pooled
    # Sharpe above. OOS already carries this from evaluate_oos_continuous; IS needs its own re-run
    # with return_raw=True since the search loop only kept summary metrics per trial.
    try:
        is_raw = optimizer._run_single_backtest(best_params, verbose=False, return_raw=True)
        is_regime = regime.regime_conditional_metrics(is_raw['equity_curve'], is_raw.get('trades'))
    except Exception as exc:
        is_regime = {}
        print(f"  (IS regime breakdown skipped: {exc})")

    print("\n" + "=" * 70)
    print("WALK-FORWARD RESULT (best in-sample params scored on the untouched OOS window)")
    print("=" * 70)
    print(f"  params: {best_params}")
    print(f"  IS  Sharpe: {is_sharpe:7.3f}  | IS  return: {float(row.get('total_return_pct', float('nan'))):7.2f}%")
    print(f"  OOS Sharpe: {oos_sharpe:7.3f}  | OOS return: {float(oos.get('total_return_pct', float('nan'))):7.2f}%"
          f"  | OOS trades: {oos.get('total_trades', '?')}")
    if is_regime:
        print(f"  IS  calm   Sharpe: {is_regime.get('calm_sharpe_ratio', float('nan')):7.3f}  "
              f"maxDD: {is_regime.get('calm_max_drawdown_pct', float('nan')):7.2f}%  "
              f"trades: {is_regime.get('calm_trades', '?')}  win%: {is_regime.get('calm_win_rate_pct', float('nan')):5.1f}")
        print(f"  IS  stress Sharpe: {is_regime.get('stress_sharpe_ratio', float('nan')):7.3f}  "
              f"maxDD: {is_regime.get('stress_max_drawdown_pct', float('nan')):7.2f}%  "
              f"trades: {is_regime.get('stress_trades', '?')}  win%: {is_regime.get('stress_win_rate_pct', float('nan')):5.1f}")
    if 'calm_sharpe_ratio' in oos:
        print(f"  OOS calm   Sharpe: {oos.get('calm_sharpe_ratio', float('nan')):7.3f}  "
              f"maxDD: {oos.get('calm_max_drawdown_pct', float('nan')):7.2f}%  "
              f"trades: {oos.get('calm_trades', '?')}  win%: {oos.get('calm_win_rate_pct', float('nan')):5.1f}")
        print(f"  OOS stress Sharpe: {oos.get('stress_sharpe_ratio', float('nan')):7.3f}  "
              f"maxDD: {oos.get('stress_max_drawdown_pct', float('nan')):7.2f}%  "
              f"trades: {oos.get('stress_trades', '?')}  win%: {oos.get('stress_win_rate_pct', float('nan')):5.1f}")
    if 'error' in oos:
        print(f"  OOS note: {oos['error']}")
    if oos_sharpe > 1.0 and oos_sharpe > 0.5 * is_sharpe:
        verdict = 'healthy — edge survives OOS'
    elif oos_sharpe > 0.5:
        verdict = 'edge persists but weaker — degraded, not collapsed'
    else:
        verdict = 'collapse — treat the IS optimum as overfit'
    print(f"  IS→OOS Sharpe drop: {is_sharpe - oos_sharpe:7.3f}  ({verdict})")
    worst = regime.worst_regime_sharpe(oos) if 'calm_sharpe_ratio' in oos else float('nan')
    print(f"  Worst-regime OOS Sharpe (robust ranking criterion): {worst:7.3f}")
    print("=" * 70 + "\n")

    save_results(results, optimizer, is_config)
    return 0


def main() -> int:
    try:
        print_header()
        if 'caffeinate' not in ' '.join(os.popen('ps aux | grep caffeinate').read().split()):
            print("⚠️  WARNING: Not running with caffeinate! Mac may sleep during optimization.\n")

        config = load_configuration()
        options_data, underlying_data = load_data(config)

        n_trials = 400
        for a in sys.argv:
            if a.startswith('--trials='):
                n_trials = int(a.split('=', 1)[1])

        if '--final' not in sys.argv:
            return run_walk_forward(config, options_data, underlying_data, n_trials)

        print("MODE: FINAL FIT — optimizing over the ENTIRE window with NO out-of-sample holdout.\n")
        optimizer = setup_optimizer(config, options_data, underlying_data)
        results = run_optimization(optimizer, n_trials)
        save_results(results, optimizer, config)
        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Optimization interrupted by user (Ctrl+C)")
        return 1
    except Exception as e:
        print(f"\n\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
