#!/usr/bin/env python3
"""csmom — multi-strategy trade-idea engine.

PRIMARY STRATEGY (as of 2026-08-05): the 3-way BLEND —
  40% SPY (growth) / 30% macro regime tilt / 30% multi-asset rotation,
  fixed weights, MONTHLY rebalance (last trading day of each month),
  1-day execution lag. See csm/blend.py, csm/macro_regime.py,
  csm/multiasset.py and memory csm-market-neutral-macro-tests.

  `backtest` / `ideas` / `verify-book` run the BLEND. The equity
  cross-sectional momentum engine is preserved under `equity-*`.

Subcommands:
  fetch        Build (or refresh) the PIT S&P 1500 membership table and
               download price history (serves BOTH strategies).

  backtest     Walk-forward backtest of the blend + DSR, multi-fold
               consistency, per-year/crisis breakdown, rolling-window
               distribution.  (alias: blend-backtest)
  ideas        Today's target blend book + rebalance trade list. Self-gated
               on the MONTHLY cadence: safe to run every trading day (e.g.
               from cron) — it no-ops with a HOLD status until a month-end
               rebalance is actually due, so the live book only ever changes
               on the same dates the backtest changes it. --force bypasses.
               (alias: blend-ideas)
  verify-book  Assert the live blend book == the blend backtest engine.
               (alias: blend-verify)

  equity-backtest / equity-ideas / equity-verify-book
               The original equity cross-sectional residual-momentum engine
               (weekly rebalance, top-quintile stock book). Kept intact and
               fully working; no longer the default flow.

Usage:
  python csmom.py                     # interactive menu
  python csmom.py fetch
  python csmom.py backtest [--oos-frac 0.30] [--folds 5]
  python csmom.py ideas    [--capital N] [--force]
  python csmom.py verify-book
  python csmom.py equity-ideas [--capital N] [--holdings f.json] [--force]

HONEST EXPECTATIONS (blend):
  - Validated OOS Sharpe 1.316 with MaxDD -8.6% vs SPY's own -18.8% over the
    same window; DSR 0.986 across the blend's own 7-trial search space.
  - Its Sharpe edge over SPY is WINDOW-DEPENDENT (on the recent bull-market
    slice it roughly matches SPY; on the longer 2010-2026 sample it beat SPY
    with alpha t≈2.0). The drawdown reduction is the more robust claim.
  - The edge is DIVERSIFICATION across three weakly-correlated sleeves, not
    stock-picking skill. The equity engine's own alpha was tested repeatedly
    and never cleared significance — that is why SPY substitutes for it here.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yaml

# ─── ensure the package directory is on the path ─────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from csm import universe as univ_mod
from csm import data as data_mod
from csm import signals as sig_mod
from csm import portfolio as port_mod
from csm import backtest as bt_mod
from csm import validation as val_mod
from csm import report as rep_mod
from csm import blend as blend_mod


# ─────────────────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────────────────

def load_config(path: Path = _HERE / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _live_end() -> str:
    """End date for LIVE commands (`fetch`, `ideas`).

    Returns *tomorrow* (yfinance's `end` is exclusive) so the download always
    includes the most recent available close. The config `end_date` only bounds
    the *backtest* analysis window — live trade ideas must price off current
    market data, never a hard-coded historical date.
    """
    return (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _ideas_start(cfg: dict) -> str:
    """Start date for the LIVE `ideas` window — decoupled from config start_date.

    `ideas` only ever scores the *latest* row, so the window start is pure warmup,
    not analysis. The residual-momentum signal stacks two 252-day windows (a 252-day
    rolling CAPM beta must be valid before the 252-day rolling residual sum resolves),
    so today's value needs ~504 trading days (~24 months) of history. We therefore
    anchor the start to a fixed warmup measured back from *today*, NOT to
    config.start_date (which is a backtest-window knob). This keeps live ideas
    identical no matter how the backtest window is set, and prevents a short
    backtest start from silently starving the signal.

    Default warmup is 30 months — the ~24-month floor plus a ~6-month cushion to
    absorb halts / NaN gaps. Override with data.ideas_warmup_months in config.
    """
    months = int(cfg.get("data", {}).get("ideas_warmup_months", 30))
    start  = pd.Timestamp.today().normalize() - pd.DateOffset(months=months)
    return start.strftime("%Y-%m-%d")


def _backtest_window(cfg: dict) -> tuple[str, str]:
    """Resolve the backtest [start, end] window — auto-anchored to today.

    Two different knobs with two different jobs:

    START stays a FIXED, far-back analysis anchor. We do NOT roll it forward,
    because the residual-momentum signal needs ~2×signal.window (~504 trading
    days for window=252) of warmup *inside* the window before it yields a single
    valid row (see _ideas_start). A short rolling start would starve the backtest
    and collapse the OOS sample — long history also spans more market regimes,
    which is what makes the OOS Sharpe honest. `start_date: auto`/blank falls back
    to the cache floor (2010) for maximum regime coverage.

    END is AUTO-ANCHORED so the window tracks fresh data with no hand-editing:
      * `end_date: auto`/blank → today
      * a real date            → clamped to today
    The realistic weekly-rebalance simulation evaluates real forward returns at
    every rebalance, so the backtest can run right up to the latest close.
    """
    data_cfg = cfg.get("data", {})

    start = data_cfg.get("start_date")
    if start in (None, "", "auto"):
        start = data_mod._CACHE_HISTORY_START
    start = pd.Timestamp(start)

    ceiling = pd.Timestamp.today().normalize()

    end_cfg = data_cfg.get("end_date")
    if end_cfg in (None, "", "auto"):
        end = ceiling
    else:
        end = min(pd.Timestamp(end_cfg), ceiling)

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


# ─────────────────────────────────────────────────────────────────────────────
#  fetch
# ─────────────────────────────────────────────────────────────────────────────

def cmd_fetch(cfg: dict) -> None:
    """Build PIT membership + download price panel."""
    cache_dir = _HERE / cfg["data"]["cache_dir"]

    print("─── Point-in-time S&P 1500 membership ──────────────────────────────")
    pit_df = univ_mod.build_pit_membership(cache_dir)   # always builds from 2010
    ever   = univ_mod.get_all_ever_members(pit_df)
    today  = univ_mod.get_members_on(pit_df, pd.Timestamp.today())
    print(f"  Ever in S&P 1500: {len(ever)} unique tickers")
    print(f"  In index today  : {len(today)} tickers")

    print("\n─── Price panel download ─────────────────────────────────────────────")
    live_end = _live_end()   # always refresh through the latest available close
    print(f"  Refreshing prices through {live_end} (today) — config end_date is backtest-only.")
    prices = data_mod.load_price_panel(
        tickers   = ever,
        start     = cfg["data"]["start_date"],
        end       = live_end,
        cache_dir = cache_dir,
        refresh   = "full",
    )
    spy = prices.get("SPY", None)
    if spy is not None:
        print(f"  SPY price range: {spy.dropna().index[0].date()} → {spy.dropna().index[-1].date()}")
    print("  fetch complete.")


# ─────────────────────────────────────────────────────────────────────────────
#  backtest
# ─────────────────────────────────────────────────────────────────────────────

def cmd_backtest(cfg: dict, args: argparse.Namespace) -> None:
    """Walk-forward backtest with full validation suite."""
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    out_dir   = _HERE / "outputs"

    # ── Load data ────────────────────────────────────────────────────────────
    pit_df_path = cache_dir / "universe_pit.parquet"
    if pit_df_path.exists():
        pit_df = pd.read_parquet(pit_df_path)
        ever   = univ_mod.get_all_ever_members(pit_df)
    else:
        print("WARNING: PIT membership not built. Run `fetch` first for honest backtests.")
        print("  Falling back to current S&P 500 (survivorship-biased).\n")
        from io import StringIO
        import requests
        hdrs = {"User-Agent": "Mozilla/5.0"}
        r    = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers=hdrs, timeout=20
        )
        ever   = pd.read_html(StringIO(r.text))[0]["Symbol"].tolist()
        pit_df = None

    sector_map = univ_mod.get_sector_map(cache_dir)   # {} if `fetch` hasn't built it yet

    bt_start, bt_end = _backtest_window(cfg)   # fixed long start, end auto-anchored to today
    window  = int(cfg.get("signal", {}).get("window", 252))
    skip    = int(cfg.get("signal", {}).get("skip", 21))
    warmup  = 2 * window + skip                 # ~504+ days before the signal is valid
    print(f"  Backtest window: {bt_start} → {bt_end}")
    print(f"  Signal warmup: ~{warmup} trading days (2×window+skip) consumed before first valid row.")
    prices = data_mod.load_price_panel(
        tickers  = ever,
        start    = bt_start,
        end      = bt_end,
        cache_dir= cache_dir,
    )

    oos_frac = float(getattr(args, "oos_frac", 0.30))
    n_perm   = int(getattr(args, "mcpt",  0))   # 0 = skip MCPT (fast mode)

    print(f"\n─── Walk-forward backtest ({int((1-oos_frac)*100)}% IS / {int(oos_frac*100)}% OOS) ──")
    print("  Simulating the live process: rebalance every 5 trading days, hold with drift …")
    primary_res = bt_mod.walk_forward(prices, cfg, pit_df=pit_df, oos_frac=oos_frac,
                                      sector_map=sector_map)
    results = {"primary (OOS)": primary_res}

    # ── Validation suite ─────────────────────────────────────────────────────
    print("\n─── DSR (Deflated Sharpe) ───────────────────────────────────────────")
    observed_sh = val_mod.compute_metrics(primary_res.net_ret, primary_res.bench_ret)["sharpe"]
    # Deflate against EVERY configuration ever tried (config validation.trial_sharpes),
    # not just this run — otherwise the DSR forgets the selection bias of the sweep
    # that picked the current config.
    trial_grid  = [float(s) for s in
                   cfg.get("validation", {}).get("trial_sharpes", [])]
    dsr_result  = val_mod.run_dsr(primary_res.net_ret,
                                  grid_sharpes=trial_grid + [observed_sh])

    mcpt_result = None
    if n_perm > 0:
        print(f"\n─── Monte Carlo Permutation Test ({n_perm} perms) ──────────────────")
        _signals = sig_mod.primary_signal(prices, cfg)

        def _portfolio_fn(perm_sig: pd.DataFrame) -> pd.Series:
            pos = port_mod.build_positions(perm_sig, prices, cfg, pit_df=pit_df,
                                           sector_map=sector_map)
            return port_mod.portfolio_returns(pos, prices, cfg)

        mcpt_result = val_mod.run_mcpt(
            _signals, prices, observed_sh, _portfolio_fn, n_perm=n_perm
        )

    # ── alpha/beta on the strict OOS result ──────────────────────────────────
    ab = val_mod.alpha_beta(primary_res.net_ret, primary_res.bench_ret)
    print("\n─── alpha/beta vs SPY (primary OOS) ─────────────────────────────────")
    print(f"  ann. alpha {ab['ann_alpha']*100:+6.2f}%  (t={ab['alpha_tstat']:+.2f})   "
          f"beta {ab['beta']:.2f} (t={ab['beta_tstat']:.1f})   R² {ab['r_squared']:.2f}")
    if abs(ab["alpha_tstat"]) < 1.5:
        print("  NOTE: alpha is not distinguishable from zero at this sample size — "
              "the Sharpe above may be mostly beta.")

    # ── multi-fold consistency check (worst fold, not just the mean) ─────────
    n_folds = int(getattr(args, "folds", 5))
    print(f"\n─── Multi-fold walk-forward ({n_folds} folds, full history) ─────────")
    folds        = bt_mod.walk_forward_folds(prices, cfg, pit_df=pit_df, n_folds=n_folds,
                                             sector_map=sector_map)
    fold_sharpes = []
    for flabel, fres in folds.items():
        fm = val_mod.compute_metrics(fres.net_ret, fres.bench_ret)
        fold_sharpes.append(fm["sharpe"])
        print(f"  {flabel:<38} Sharpe {fm['sharpe']:+.2f}  CAGR {fm['cagr']*100:+6.1f}%  "
              f"MaxDD {fm['max_dd']*100:6.1f}%")
    if fold_sharpes:
        worst = min(fold_sharpes)
        print(f"  worst fold Sharpe: {worst:+.2f}   (bar: > 0.30)"
              + ("  *** FAILS bar ***" if worst <= 0.30 else ""))

    # ── regime-stratified breakdown across the FULL history (includes IS) ────
    # Labeled separately from the strict-OOS headline above: this walks the
    # exact same continuous-signal engine from the very first bar, so 2018/2022
    # (both in-sample under the current config.start_date) actually show up.
    print("\n─── Per-year & crisis-window breakdown (full history, includes IS) ──")
    full_res = bt_mod.simulate_live(prices, cfg, pit_df, prices.index[0],
                                    label="full-history", sector_map=sector_map)
    rb = val_mod.regime_breakdown(full_res.net_ret, full_res.bench_ret)
    with pd.option_context("display.width", 120):
        print(rb.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # ── rolling-window distribution (the actual "consistent Sharpe" metric) ──
    print("\n─── Rolling 6-month window distribution (primary OOS) ───────────────")
    rw = val_mod.rolling_window_summary(primary_res.net_ret)
    if rw.get("n_windows", 0):
        print(f"  n_windows={rw['n_windows']}   median Sharpe {rw['median_sharpe']:+.2f}   "
              f"worst window Sharpe {rw['worst_window_sharpe']:+.2f}")
        print(f"  % windows profitable: {rw['pct_profitable']*100:.0f}%   "
              f"worst window return {rw['worst_window_return']*100:+.1f}%   "
              f"median maxDD {rw['median_max_dd']*100:.1f}%")
    else:
        print("  not enough OOS history yet for a 6-month rolling window.")

    # ── Report ───────────────────────────────────────────────────────────────
    print("\n─── Report ──────────────────────────────────────────────────────────")
    rep_mod.write_backtest_report(results, dsr_result, None, mcpt_result, out_dir,
                                  has_pit=pit_df is not None)


# ─────────────────────────────────────────────────────────────────────────────
#  ideas — book persistence + weekly rebalance diff
# ─────────────────────────────────────────────────────────────────────────────

BOOK_FILE = "portfolio_book.json"


def _load_prev_book(out_dir: Path) -> dict | None:
    """Load the last persisted target book (canonical live state), or None."""
    path = out_dir / BOOK_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _save_book(out_dir: Path, payload: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / BOOK_FILE).write_text(json.dumps(payload, indent=2, default=str))


def _print_hold_status(prev: dict, gap: int, rebal_freq: int) -> None:
    """Console-only status for a non-rebalance day: report the still-current book,
    make zero trades, and don't touch outputs/ (no new report, no re-persisted book) —
    there is nothing new to record until the next scheduled rebalance."""
    header  = prev.get("header", {})
    rows    = prev.get("book", [])
    as_of   = header.get("as_of", "?")
    has_cap = header.get("capital") is not None

    print("\n" + "=" * 84)
    print("Cross-Sectional Residual Momentum — HOLD (no rebalance due)")
    print("=" * 84)
    print(f"  Last book as of: {as_of}   ({gap} trading day(s) elapsed; "
          f"rebalance every {rebal_freq})")
    print(f"  Next rebalance due in {rebal_freq - gap} trading day(s).")
    print("  No trades — continue holding the book below unchanged.")
    print("=" * 84)
    if has_cap:
        print(f"  {'Rank':<5} {'Ticker':<8} {'Weight':>8} {'Buy $':>12} {'Close':>10}")
        print("  " + "-" * 60)
        for r in rows:
            print(f"  {r['rank']:<5} {r['ticker']:<8} {r['weight_pct']:>7.2f}% "
                  f"{r.get('dollars', 0):>12,.2f} {r['last_close']:>10.2f}")
    else:
        print(f"  {'Rank':<5} {'Ticker':<8} {'Weight':>8} {'Close':>10}")
        print("  " + "-" * 40)
        for r in rows:
            print(f"  {r['rank']:<5} {r['ticker']:<8} {r['weight_pct']:>7.2f}% "
                  f"{r['last_close']:>10.2f}")
    print("=" * 84)


def _read_holdings_file(path: Path) -> dict:
    """Read an external holdings file to diff against.

    Values are the current dollar market value per ticker ({"AAPL": 250.00}),
    matching how you trade on a fractional/dollar broker like Robinhood.
    """
    raw = json.loads(Path(path).read_text())
    return {str(k).upper(): float(v) for k, v in raw.items()}


def _compute_trades(prev_rows: list[dict], new_rows: list[dict],
                    has_capital: bool, prev_dollars: dict | None = None) -> dict:
    """BUY/SELL/RESIZE diff of the new book vs the previously held one.

    Diffs on DOLLARS when capital is known (you buy/sell dollar amounts on a
    fractional broker), otherwise on weight %.  `prev_dollars` ({ticker: $market
    value}) overrides prev_rows (used by --holdings).  A $1 band suppresses noise.
    """
    buys, sells, resizes = [], [], []
    if prev_dollars is not None:
        prev_d = {k: float(v) for k, v in prev_dollars.items()}
        prev_w = {}
    else:
        prev_d = {r["ticker"]: r.get("dollars", 0.0) for r in (prev_rows or [])}
        prev_w = {r["ticker"]: r.get("weight_pct", 0.0) for r in (prev_rows or [])}
    new_d = {r["ticker"]: r.get("dollars", 0.0) for r in new_rows}
    new_w = {r["ticker"]: r.get("weight_pct", 0.0) for r in new_rows}

    for t in new_rows:
        tk = t["ticker"]
        if tk not in prev_d and tk not in prev_w:
            buys.append({"ticker": tk, "dollars": round(new_d.get(tk, 0.0), 2)
                                       if has_capital else None})
        elif has_capital:
            delta = new_d.get(tk, 0.0) - prev_d.get(tk, 0.0)
            if abs(delta) >= 1.0:
                resizes.append({"ticker": tk, "delta_dollars": round(delta, 2),
                                "from_dollars": round(prev_d.get(tk, 0.0), 2),
                                "to_dollars":   round(new_d.get(tk, 0.0), 2)})
        else:
            if abs(new_w.get(tk, 0.0) - prev_w.get(tk, 0.0)) >= 0.20:
                resizes.append({"ticker": tk, "delta_dollars": None,
                                "from_pct": prev_w.get(tk, 0.0), "to_pct": new_w.get(tk, 0.0)})

    held_now = set(new_d)
    for tk in (set(prev_d) | set(prev_w)):
        if tk not in held_now:
            sells.append({"ticker": tk, "dollars": round(prev_d.get(tk, 0.0), 2)
                                        if has_capital else None})
    return {"buys": buys, "sells": sells, "resizes": resizes}


# ─────────────────────────────────────────────────────────────────────────────
#  ideas
# ─────────────────────────────────────────────────────────────────────────────

def cmd_ideas(cfg: dict, args: argparse.Namespace) -> None:
    """Score today's universe and output ranked long ideas.

    Self-gated on the backtest's rebalance cadence: run this every trading day
    (e.g. from cron) and it will only do real work when a rebalance is actually
    due, otherwise it reports the still-held book and exits. `--force` (or
    `--holdings`, an explicit ad-hoc diff request) bypasses the gate.
    """
    cache_dir  = _HERE / cfg["data"]["cache_dir"]
    out_dir    = _HERE / "outputs"
    top_n      = int(getattr(args, "top", cfg.get("output", {}).get("top_n_ideas", 25)))
    rebal_freq = int(cfg.get("portfolio", {}).get("rebal_freq", 5))
    force      = bool(getattr(args, "force", False)) or bool(getattr(args, "holdings", None))
    prev       = _load_prev_book(out_dir)

    # ── Fast, network-free pre-check ─────────────────────────────────────────
    # A plain weekday count can only OVER-count true trading days (it counts
    # market holidays as business days too), so if it already reads under
    # rebal_freq, the real trading-day gap is guaranteed to be under it as
    # well — safe to bail before touching the price cache or network at all.
    # If it reads >= rebal_freq we can't yet be sure (a holiday may have
    # inflated it), so fall through to the exact index-based check below once
    # prices are loaded — that one is authoritative and matches the backtest's
    # rebalance grid (_rebalance_dates) exactly.
    if prev and prev.get("header", {}).get("as_of") and not force:
        prev_as_of = pd.Timestamp(prev["header"]["as_of"])
        wall_today = pd.Timestamp.today().normalize()
        quick_gap  = int(np.busday_count(prev_as_of.date(), wall_today.date()))
        if quick_gap < rebal_freq:
            _print_hold_status(prev, quick_gap, rebal_freq)
            return

    pit_df_path = cache_dir / "universe_pit.parquet"
    if pit_df_path.exists():
        pit_df = pd.read_parquet(pit_df_path)
        ever   = univ_mod.get_all_ever_members(pit_df)
    else:
        print("WARNING: PIT membership not built — run `fetch` first.")
        from io import StringIO
        import requests
        hdrs = {"User-Agent": "Mozilla/5.0"}
        r    = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers=hdrs, timeout=20
        )
        ever   = pd.read_html(StringIO(r.text))[0]["Symbol"].tolist()
        pit_df = None

    ideas_start = _ideas_start(cfg)   # fixed warmup back from today, NOT config start_date
    prices = data_mod.load_price_panel(
        tickers  = ever,
        start    = ideas_start,
        end      = _live_end(),   # live ideas price off the latest available close
        cache_dir= cache_dir,
    )

    # Use the last date where ≥50% of the panel has valid data — guards against
    # partial download failures where the newest row is mostly NaN (would otherwise
    # score signals off a near-empty universe).
    _cov_thresh  = max(50, prices.shape[1] // 2)
    today        = prices.dropna(thresh=_cov_thresh).index[-1]
    wall_today   = pd.Timestamp.today().normalize()
    panel_lag_bd = int(np.busday_count(today.date(), wall_today.date()))
    if wall_today.dayofweek < 5 and not data_mod.market_close_passed():
        panel_lag_bd -= 1   # today's session is still open — its close can't exist yet

    # ── Auto-refresh: cache is behind by ≥1 trading day → incremental update ──
    # Without this, `ideas` would silently score momentum off Friday's closes on
    # Tuesday/Wednesday/Thursday (the BDay(5) cache gate is too wide for daily
    # trading). refresh="tail" pulls only the last ~10 trading days and splices
    # them onto the cache — tiny payload, so Yahoo rate limiting is a non-issue.
    if panel_lag_bd >= 1:
        print(f"Cache is {panel_lag_bd} trading day(s) behind — refreshing prices …")
        prices = data_mod.load_price_panel(
            tickers   = ever,
            start     = ideas_start,
            end       = _live_end(),
            cache_dir = cache_dir,
            refresh   = "tail",
        )
        _cov_thresh  = max(50, prices.shape[1] // 2)
        today        = prices.dropna(thresh=_cov_thresh).index[-1]
        panel_lag_bd = int(np.busday_count(today.date(), wall_today.date()))
        if wall_today.dayofweek < 5 and not data_mod.market_close_passed():
            panel_lag_bd -= 1
        if panel_lag_bd >= 1:
            print(f"NOTE: yfinance latest close is {today.date()} — "
                  f"scoring off most recent available data.")

    stocks = prices.drop(columns=data_mod.NON_STOCK_COLS, errors="ignore")

    # ── Freshness guard #1: panel must be current vs the real calendar ───────
    # Auto-refresh above handles the 1-3 day case; this catches a genuine outage
    # where yfinance itself returned data that is still multi-days stale.
    if panel_lag_bd > 3:
        print(f"\nERROR: price panel is stale — latest close is {today.date()}, "
              f"{panel_lag_bd} trading days behind today ({wall_today.date()}).")
        print("  The book's prices and momentum would be computed off old data.")
        print("  Run `python csmom.py fetch` to refresh the price cache, then try again.")
        return

    # ── Freshness guard #2: SPY must be consistent with the rest of the panel ─
    spy_last = prices["SPY"].dropna().index.max() if "SPY" in prices.columns else None
    if spy_last is None or (today - spy_last).days > 7:
        print(f"\nERROR: SPY price data is stale (last real close: "
              f"{spy_last.date() if spy_last else 'N/A'}, panel end: {today.date()}).")
        print("  The market factor, regime filter, and residual signals are unreliable.")
        print("  Run `python csmom.py fetch` to refresh the price cache, then try again.")
        return

    # ── Drop tickers whose last real close is stale ──────────────────────────
    last_valid = stocks.apply(lambda c: c.dropna().index.max() if c.notna().any() else pd.NaT)
    stale_mask = last_valid < (today - pd.Timedelta(days=7))
    stale_cols = list(last_valid[stale_mask].index)
    if stale_cols:
        print(f"\nWARNING: {len(stale_cols)} tickers have stale prices (last close > 7 days ago).")
        print(f"  Excluded from ideas: {', '.join(stale_cols[:10])}"
              + (f" … +{len(stale_cols)-10} more" if len(stale_cols) > 10 else ""))
        stocks = stocks.drop(columns=stale_cols)

    # Stale names are excluded from the panel entirely, so the book engine can
    # never select one (target_book scores off `prices`, not just `stocks`).
    if stale_cols:
        prices = prices.drop(columns=stale_cols)
        stocks = prices.drop(columns=data_mod.NON_STOCK_COLS, errors="ignore")

    # ── Exact, trading-calendar gate ──────────────────────────────────────────
    # Authoritative version of the fast pre-check above: `today` is now the
    # real latest-available trading day (post auto-refresh), so this searchsorted
    # diff is the identical arithmetic _rebalance_dates()/simulate_live() uses to
    # place rebal dates on the price index — gap < rebal_freq here means the
    # backtest itself would not treat today as a rebalance date.
    if prev and prev.get("header", {}).get("as_of") and not force:
        prev_as_of = pd.Timestamp(prev["header"]["as_of"])
        gap = int(prices.index.searchsorted(today) - prices.index.searchsorted(prev_as_of))
        if gap < rebal_freq:
            _print_hold_status(prev, gap, rebal_freq)
            return

    # ── Build the EXACT book the backtest holds today ────────────────────────
    # target_book() is the single source of truth: top-quintile → equal-dollar
    # 1/N → vol-scaling → regime gate. Identical math to the backtest engine, so
    # trading this book reproduces the validated curve — no truncation, no
    # un-traded stop/target brackets.
    print(f"\nBuilding target book as of {today.date()} …")
    sector_map = univ_mod.get_sector_map(cache_dir)
    book = port_mod.target_book(prices, cfg, pit_df=pit_df, as_of=today, sector_map=sector_map)

    expo_ser  = sig_mod.regime_exposure(prices, cfg)
    exposure  = float(expo_ser.get(today, 1.0))
    in_regime = exposure > 0.0

    # `prev` was already loaded above for the cadence gate; reused here so the
    # rebalance $ diff always compares against what capital the book was last
    # sized at, not this run's forgotten/changed --capital flag.
    capital = getattr(args, "capital", None)
    if capital is None:
        prev_capital = (prev or {}).get("header", {}).get("capital")
        if prev_capital is not None:
            capital = float(prev_capital)
            print(f"  No --capital given — using last book's capital: ${capital:,.0f}")

    signals   = sig_mod.primary_signal(prices, cfg)
    today_sig = signals.loc[today]

    rows: list[dict] = []
    for rank, (ticker, weight) in enumerate(book.items(), start=1):
        last_close = float(stocks[ticker].dropna().iloc[-1])
        row = {
            "rank":         rank,
            "ticker":       ticker,
            "weight":       round(float(weight), 6),
            "weight_pct":   round(float(weight) * 100, 2),
            "last_close":   round(last_close, 2),
            "signal_score": round(float(today_sig.get(ticker, np.nan)), 4),
            "as_of":        str(today.date()),
        }
        if capital is not None and last_close > 0:
            dollars = float(weight) * capital
            row["dollars"] = round(dollars, 2)
            row["shares"]  = round(dollars / last_close, 4)   # fractional (Robinhood)
        rows.append(row)

    gross = float(book.sum()) if not book.empty else 0.0

    # ── Cadence note + rebalance diff vs the previously held book ─────────────
    # (rebal_freq already resolved at the top of the function, for the cadence gate)
    cadence_note = ""
    if prev and prev.get("header", {}).get("as_of"):
        prev_as_of = pd.Timestamp(prev["header"]["as_of"])
        gap = int(prices.index.searchsorted(today) - prices.index.searchsorted(prev_as_of))
        if gap <= 0:
            cadence_note = "same-day rerun — book unchanged unless data refreshed."
        elif gap < rebal_freq:
            cadence_note = (f"{gap} trading day(s) since last book; next scheduled "
                            f"rebalance in {rebal_freq - gap}. Trades below are optional drift.")
        else:
            cadence_note = f"{gap} trading days since last book — weekly rebalance due."

    holdings_path = getattr(args, "holdings", None)
    if holdings_path:
        prev_dollars = _read_holdings_file(Path(holdings_path))
        trades = _compute_trades([], rows, capital is not None, prev_dollars=prev_dollars)
    else:
        trades = _compute_trades((prev or {}).get("book", []), rows, capital is not None)

    header = {
        "as_of":      str(today.date()),
        "regime_on":  in_regime,
        "regime_exposure_pct": round(exposure * 100, 1),
        "gross_pct":  round(gross * 100, 1),
        "cash_pct":   round((1.0 - gross) * 100, 1),
        "n_names":    len(rows),
        "capital":    capital,
        "exit_rule":  "Exit any name that leaves next week's book; hold the rest. No intraday stops.",
        "cadence_note": cadence_note,
    }

    if not rows:
        if not in_regime:
            print("\nREGIME OFF (trend/vol/VIX-structure conditions failed) → no equity longs.")
            print("  The strategy takes no new longs; close existing per the exit rule.")
        else:
            print("\nNo names cleared the book today (too few candidates).")

    rep_mod.write_ideas_report(rows, header, trades, out_dir)
    # Persist the canonical live state for next run's diff (skip when diffing an
    # external --holdings file so we don't clobber the tracked book).
    if not holdings_path:
        _save_book(out_dir, {"header": header, "book": rows})


# ─────────────────────────────────────────────────────────────────────────────
#  verify-book — prove `ideas` holds exactly what the backtest engine holds
# ─────────────────────────────────────────────────────────────────────────────

def cmd_verify_book(cfg: dict, args: argparse.Namespace) -> None:
    """Assert the live book == the backtest position engine's last row.

    `ideas` has no selection logic of its own — it calls portfolio.target_book,
    which is build_positions(rebal_anchor="end").iloc[-1]. The backtest
    (simulate_live) chains that SAME per-rebalance book weekly with drift, so
    backtest and live are identical by construction. This check locks the book to
    the engine so a future edit can't silently reintroduce a divergent path.
    """
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    out_dir   = _HERE / "outputs"

    pit_df_path = cache_dir / "universe_pit.parquet"
    pit_df = pd.read_parquet(pit_df_path) if pit_df_path.exists() else None
    ever   = (univ_mod.get_all_ever_members(pit_df) if pit_df is not None
              else [])
    if not ever:
        print("ERROR: PIT universe not built — run `fetch` first.")
        return

    prices = data_mod.load_price_panel(
        tickers=ever, start=_ideas_start(cfg), end=_live_end(), cache_dir=cache_dir,
    )

    # Same coverage-guarded as-of date `ideas` uses (skip a partial last row).
    _cov_thresh = max(50, prices.shape[1] // 2)
    as_of       = prices.dropna(thresh=_cov_thresh).index[-1]

    sector_map = univ_mod.get_sector_map(cache_dir)

    # Engine path (what the backtest trades), end-anchored so the last row is fresh.
    signals = sig_mod.primary_signal(prices, cfg)
    pos     = port_mod.build_positions(signals, prices, cfg, pit_df=pit_df,
                                       rebal_anchor="end", sector_map=sector_map)
    engine  = pos.loc[as_of]
    engine  = engine[engine > 0.0].sort_values(ascending=False)

    # Live path (what `ideas` shows).
    live = port_mod.target_book(prices, cfg, pit_df=pit_df, as_of=as_of, sector_map=sector_map)

    same_names = set(engine.index) == set(live.index)
    max_w_diff = float((engine.reindex(sorted(set(engine.index) | set(live.index)))
                        .fillna(0.0)
                        - live.reindex(sorted(set(engine.index) | set(live.index)))
                        .fillna(0.0)).abs().max()) if (len(engine) or len(live)) else 0.0

    print("\n─── verify-book: live ideas book vs backtest engine ───")
    print(f"  engine names: {len(engine)}   live names: {len(live)}")
    print(f"  identical name set: {same_names}")
    print(f"  max per-name weight diff: {max_w_diff:.2e}")
    ok = same_names and max_w_diff < 1e-9
    print(f"  MATCH: {'✓ PASS' if ok else '✗ FAIL'}")
    print("  (the backtest chains this exact book weekly with drift — simulate_live)")


# ─────────────────────────────────────────────────────────────────────────────
#  blend-backtest / blend-ideas / blend-verify — 3-way SPY/macro/rotation blend
#  A SEPARATE strategy from the equity cross-sectional momentum engine above:
#  no stock universe, no PIT membership — just the small set of liquid ETFs
#  csm.blend needs. `tickers=[]` still returns them: csm.data's SIGNAL_EXCLUDE
#  union (AUX/REGIME_DETECT/DEFENSIVE_ROSTER/MACRO_SECTOR/MACRO_ASSET cols)
#  rides along in every price-panel load regardless of the stock ticker list.
# ─────────────────────────────────────────────────────────────────────────────

BLEND_BOOK_FILE = "blend_book.json"


def _load_prev_blend_book(out_dir: Path) -> dict | None:
    path = out_dir / BLEND_BOOK_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _save_blend_book(out_dir: Path, payload: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / BLEND_BOOK_FILE).write_text(json.dumps(payload, indent=2, default=str))


def _prev_blend_rebal(prev: dict | None) -> pd.Timestamp | None:
    """The rebalance date the previously saved blend book belongs to.

    Prefers `rebal_as_of` (the month-end the weights were decided on) and falls
    back to `as_of` (the price date) for books written before `rebal_as_of` was
    recorded — those two coincided whenever the old, ungated command happened to
    be run on a rebalance day, and falling back is strictly safer than treating
    an older book as having no rebalance at all.
    """
    if not prev:
        return None
    header = prev.get("header", {})
    raw = header.get("rebal_as_of") or header.get("as_of")
    return pd.Timestamp(raw) if raw else None


def _canonical_prev_month_end(ts: pd.Timestamp) -> pd.Timestamp:
    """Last canonical business-month-end on or before `ts` (no price data needed).

    The REAL rebalance date is the last *trading* day on or before this, so this
    is an upper bound on it — which is exactly what makes the network-free
    pre-check in `cmd_blend_ideas` sound: if even this upper bound hasn't moved
    past the previous book's rebalance, no new rebalance can have occurred.
    """
    return pd.offsets.BMonthEnd().rollback(ts.normalize())


def _canonical_next_month_end(ts: pd.Timestamp) -> pd.Timestamp:
    """First canonical business-month-end strictly after `ts`."""
    ts = ts.normalize()
    fwd = pd.offsets.BMonthEnd().rollforward(ts)
    return fwd if fwd > ts else ts + pd.offsets.BMonthEnd()


def _blend_rebal_status(prices: pd.DataFrame, prev: dict | None,
                        now: pd.Timestamp | None = None) -> dict:
    """Resolve the blend's MONTHLY rebalance cadence against the real trading
    calendar — the exact analogue of what `cmd_ideas` does with `rebal_freq`
    trading days, but on the month-end grid `blend.simulate_blend` actually
    trades (`multiasset.month_end_dates`, verified 2026-08-05 to be the ONLY
    dates on which blend weights change).

    Returns last_rebal / next_rebal / due / days_until_next.
    """
    from csm import multiasset as ma_mod

    rebal_dates = ma_mod.month_end_dates(prices.index)
    today       = prices.index[-1]
    past        = rebal_dates[rebal_dates <= today]
    last_rebal  = past[-1] if len(past) else None

    prev_rebal = _prev_blend_rebal(prev)
    # Due when a rebalance the previous book hasn't seen has since occurred.
    # Robust to missed runs: if you skip the month-end itself, the next run
    # still fires (unlike a check that demands today IS the rebalance day).
    due = last_rebal is not None and (prev_rebal is None or last_rebal > prev_rebal)

    # Countdown is anchored on WALL-CLOCK today (not the panel's last close) so
    # it reads as "trading days from now" — the same anchor the network-free
    # pre-check uses, keeping the two HOLD paths consistent. `now` is injectable
    # so simulations over historical panels report a sensible countdown too.
    anchor     = (now or pd.Timestamp.today()).normalize()
    next_rebal = _canonical_next_month_end(max(today, anchor))
    days_until = max(0, int(np.busday_count(anchor.date(), next_rebal.date())))

    return {
        "rebal_dates":     rebal_dates,
        "today":           today,
        "last_rebal":      last_rebal,
        "prev_rebal":      prev_rebal,
        "due":             due,
        "next_rebal":      next_rebal,
        "days_until_next": days_until,
    }


def _print_blend_hold_status(prev: dict, status: dict, capital: float | None = None) -> None:
    """Console-only HOLD status for a non-rebalance day: report the still-held
    book, make zero trades, and don't touch outputs/ — mirroring
    `_print_hold_status` for the equity engine. Nothing new is recorded until
    the next scheduled month-end rebalance.

    `capital` is resolved by the caller (explicit `--capital` this run, else
    the last save's remembered capital) and used to recompute dollar amounts
    fresh from each row's stable `weight` — NEVER from the row's stale
    `dollars` field, which was baked in at whatever capital the LAST save
    used. This is what lets the same stable book be sized correctly for
    multiple portfolios with different capital: the weights/tickers only
    change on a real month-end rebalance, but the dollar amounts always
    reflect THIS run's capital.
    """
    header       = prev.get("header", {})
    rows         = prev.get("book", [])
    prev_capital = header.get("capital")
    has_cap      = capital is not None
    last_r       = status["last_rebal"]
    nxt          = status["next_rebal"]

    print("\n" + "=" * 84)
    print("3-Way Blend — HOLD (no rebalance due)")
    print("=" * 84)
    # Books written before `rebal_as_of` existed only recorded the price date,
    # which is usually NOT a month-end — label it honestly rather than implying
    # a rebalance happened on a day that wasn't one.
    if header.get("rebal_as_of"):
        print(f"  Book decided on: {last_r.date() if last_r is not None else '?'}"
              f"   (month-end rebalance)")
    else:
        print(f"  Book last saved: {last_r.date() if last_r is not None else '?'}"
              f"   (pre-dates rebalance-date tracking)")
    print(f"  Latest close:    {status['today'].date()}")
    print(f"  Next rebalance:  {nxt.date()}  "
          f"(~{status['days_until_next']} trading day(s) away)")
    print("  No trades — the blend rebalances MONTHLY; hold the book below unchanged.")
    print("  (Weights drift with the market between rebalances by design — that is")
    print("   exactly what the backtest does, so do NOT top up to target mid-month.)")
    print("=" * 84)
    if has_cap:
        if prev_capital is not None and abs(float(capital) - float(prev_capital)) > 1e-6:
            print(f"  Sizing at THIS run's capital (${float(capital):,.0f}) — the book was last "
                  f"decided at ${float(prev_capital):,.0f}. Weights/tickers are unchanged (no "
                  f"rebalance is due); only the dollar amounts below are rescaled.")
            print("=" * 84)
        print(f"  {'Rank':<5} {'Ticker':<8} {'Sleeve':<14} {'Weight':>8} {'Buy $':>12}")
        print("  " + "-" * 56)
        for r in rows:
            dollars = float(r.get("weight", 0.0)) * float(capital)
            print(f"  {r['rank']:<5} {r['ticker']:<8} {r.get('sleeve',''):<14} "
                  f"{r['weight_pct']:>7.2f}% {dollars:>12,.2f}")
    else:
        print(f"  {'Rank':<5} {'Ticker':<8} {'Sleeve':<14} {'Weight':>8}")
        print("  " + "-" * 44)
        for r in rows:
            print(f"  {r['rank']:<5} {r['ticker']:<8} {r.get('sleeve',''):<14} "
                  f"{r['weight_pct']:>7.2f}%")
    print("=" * 84)


def cmd_blend_backtest(cfg: dict, args: argparse.Namespace) -> None:
    """Walk-forward backtest of the 3-way blend (SPY / macro tilt / rotation)."""
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    out_dir   = _HERE / "outputs"

    bt_start, bt_end = _backtest_window(cfg)
    print(f"  Backtest window: {bt_start} → {bt_end}  "
          f"(3-way blend: SPY / macro tilt / rotation, monthly rebal)")
    prices = data_mod.load_price_panel(tickers=[], start=bt_start, end=bt_end, cache_dir=cache_dir)

    oos_frac = float(getattr(args, "oos_frac", 0.30))
    n_folds  = int(getattr(args, "folds", 5))

    print(f"\n─── Walk-forward backtest ({int((1-oos_frac)*100)}% IS / {int(oos_frac*100)}% OOS) ──")
    print("  Monthly rebalance, hold with drift, fixed weights (no regime switching) …")
    primary_res = blend_mod.walk_forward_blend(prices, cfg, oos_frac=oos_frac)
    results = {"blend (OOS)": primary_res}

    observed_sh = val_mod.compute_metrics(primary_res.net_ret, primary_res.bench_ret)["sharpe"]
    trial_grid  = [float(s) for s in cfg.get("blend", {}).get("trial_sharpes", [])]
    dsr_result  = val_mod.run_dsr(primary_res.net_ret, grid_sharpes=trial_grid + [observed_sh])

    ab = val_mod.alpha_beta(primary_res.net_ret, primary_res.bench_ret)
    print("\n─── alpha/beta vs SPY (blend OOS) ────────────────────────────────────")
    print(f"  ann. alpha {ab['ann_alpha']*100:+6.2f}%  (t={ab['alpha_tstat']:+.2f})   "
          f"beta {ab['beta']:.2f} (t={ab['beta_tstat']:.1f})   R² {ab['r_squared']:.2f}")

    print(f"\n─── Multi-fold walk-forward ({n_folds} folds, full history) ──────────")
    folds = blend_mod.walk_forward_blend_folds(prices, cfg, n_folds=n_folds)
    fold_sharpes = []
    for flabel, fres in folds.items():
        fm = val_mod.compute_metrics(fres.net_ret, fres.bench_ret)
        fold_sharpes.append(fm["sharpe"])
        print(f"  {flabel:<38} Sharpe {fm['sharpe']:+.2f}  CAGR {fm['cagr']*100:+6.1f}%  "
              f"MaxDD {fm['max_dd']*100:6.1f}%")
    if fold_sharpes:
        worst = min(fold_sharpes)
        print(f"  worst fold Sharpe: {worst:+.2f}   (bar: > 0.30)"
              + ("  *** FAILS bar ***" if worst <= 0.30 else ""))

    print("\n─── Per-year & crisis-window breakdown (full history) ────────────────")
    full_res = blend_mod.simulate_blend(prices, cfg, prices.index[0], label="full-history")
    rb = val_mod.regime_breakdown(full_res.net_ret, full_res.bench_ret)
    with pd.option_context("display.width", 120):
        print(rb.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n─── Rolling 12-month window distribution (full history) ─────────────")
    rw = val_mod.rolling_window_summary(full_res.net_ret, window_months=12, step_months=3)
    if rw.get("n_windows", 0):
        print(f"  n_windows={rw['n_windows']}   median Sharpe {rw['median_sharpe']:+.2f}   "
              f"worst window Sharpe {rw['worst_window_sharpe']:+.2f}")
        print(f"  % windows profitable: {rw['pct_profitable']*100:.0f}%   "
              f"worst window return {rw['worst_window_return']*100:+.1f}%   "
              f"worst maxDD {rw['worst_max_dd']*100:.1f}%")
    else:
        print("  not enough history yet for a 12-month rolling window.")

    print("\n─── Report ──────────────────────────────────────────────────────────")
    rep_mod.write_backtest_report(results, dsr_result, None, None, out_dir,
                                  suffix="_blend", has_pit=True)


def cmd_blend_ideas(cfg: dict, args: argparse.Namespace) -> None:
    """Output today's target blend book (SPY / macro tilt / rotation weights).

    Self-gated on the backtest's MONTHLY rebalance cadence — the direct
    analogue of how `cmd_ideas` self-gates on `rebal_freq` trading days. Safe
    to run every trading day (e.g. from cron): it no-ops with a HOLD status
    until a month-end rebalance is actually due, so the live book only ever
    changes on the same dates `blend.simulate_blend` changes it. `--force`
    bypasses the gate.
    """
    from csm import multiasset as ma_mod

    cache_dir = _HERE / cfg["data"]["cache_dir"]
    out_dir   = _HERE / "outputs"
    force     = bool(getattr(args, "force", False))
    prev      = _load_prev_blend_book(out_dir)

    # Resolve capital ONCE, up front, before either gate check. An explicit
    # --capital ALWAYS wins and is used to size dollar amounts fresh this run
    # — including on a HOLD day — so managing multiple portfolios (same
    # target book, different capital each) works: run `ideas --capital A`
    # for portfolio A, then `ideas --capital B` for portfolio B, and each
    # shows correctly-scaled amounts without clobbering the other's state.
    # Falling back to the last save's remembered capital is only a
    # convenience for a single-portfolio user who omits --capital entirely.
    capital = getattr(args, "capital", None)
    if capital is None:
        prev_capital = (prev or {}).get("header", {}).get("capital")
        if prev_capital is not None:
            capital = float(prev_capital)

    # ── Fast, network-free pre-check ─────────────────────────────────────────
    # The real rebalance date is the last TRADING day on or before the
    # canonical business-month-end, so the canonical date is an upper bound on
    # it. If even that upper bound hasn't moved past the previous book's
    # rebalance, no new rebalance can have occurred — safe to bail before
    # touching the price cache or network at all. Otherwise fall through to the
    # authoritative index-based check below, which uses the exact same
    # `month_end_dates` grid `simulate_blend` trades.
    if prev and not force:
        prev_rebal = _prev_blend_rebal(prev)
        wall_today = pd.Timestamp.today().normalize()
        if prev_rebal is not None and _canonical_prev_month_end(wall_today) <= prev_rebal:
            nxt = _canonical_next_month_end(wall_today)
            _print_blend_hold_status(prev, {
                "today":           pd.Timestamp(prev.get("header", {}).get("as_of", wall_today)),
                "last_rebal":      prev_rebal,
                "next_rebal":      nxt,
                "days_until_next": int(np.busday_count(wall_today.date(), nxt.date())),
            }, capital=capital)
            return

    ideas_start = _ideas_start(cfg)   # 30mo warmup comfortably covers the
                                      # rotation's 252d absolute-momentum window
    prices = data_mod.load_price_panel(tickers=[], start=ideas_start, end=_live_end(),
                                       cache_dir=cache_dir)

    # ── Auto-refresh when the cache is behind ────────────────────────────────
    # Ported from `cmd_ideas`: without this the blend could decide a month-end
    # rebalance off a stale close. refresh="tail" pulls only the last ~10
    # trading days, so this is cheap enough to do on every real rebalance.
    wall_today   = pd.Timestamp.today().normalize()
    def _panel_lag(idx_last: pd.Timestamp) -> int:
        lag = int(np.busday_count(idx_last.date(), wall_today.date()))
        if wall_today.dayofweek < 5 and not data_mod.market_close_passed():
            lag -= 1   # today's session is still open — its close can't exist yet
        return lag

    spy_last = prices["SPY"].dropna().index.max() if "SPY" in prices.columns else None
    if spy_last is not None and _panel_lag(spy_last) >= 1:
        print(f"Cache is {_panel_lag(spy_last)} trading day(s) behind — refreshing prices …")
        prices = data_mod.load_price_panel(tickers=[], start=ideas_start, end=_live_end(),
                                           cache_dir=cache_dir, refresh="tail")
        spy_last = prices["SPY"].dropna().index.max() if "SPY" in prices.columns else None

    # ── Freshness guard: a genuine outage left the panel multi-days stale ────
    if spy_last is None or _panel_lag(spy_last) > 3:
        print(f"\nERROR: price panel is stale — latest SPY close is "
              f"{spy_last.date() if spy_last is not None else 'N/A'}, "
              f"{_panel_lag(spy_last) if spy_last is not None else '?'} trading days behind "
              f"today ({wall_today.date()}).")
        print("  The blend's regime classification and momentum ranks would be computed")
        print("  off old data. Run `python csmom.py fetch`, then try again.")
        return

    # Trim the panel to complete rows so a partially-downloaded trailing row can
    # never become the as-of date (blend needs every sleeve's tickers present).
    prices = prices.loc[:spy_last]
    today  = spy_last

    # ── Authoritative, trading-calendar rebalance gate ───────────────────────
    status = _blend_rebal_status(prices, prev)
    if prev and not force and not status["due"]:
        _print_blend_hold_status(prev, status, capital=capital)
        return

    book = blend_mod.target_book(prices, cfg, as_of=today)

    if getattr(args, "capital", None) is None and capital is not None:
        print(f"  No --capital given — using last book's capital: ${capital:,.0f}")

    growth_ticker = str(cfg.get("blend", {}).get("growth_ticker", data_mod.GROWTH_TICKER))

    def sleeve_of(t: str) -> str:
        if t == growth_ticker:
            return f"growth ({growth_ticker})"
        if t in ma_mod.DEFENSIVE_ROSTER or t == ma_mod.CASH_TICKER:
            return "rotation"
        return "macro tilt"

    rows: list[dict] = []
    for rank, (ticker, weight) in enumerate(book.items(), start=1):
        last_close = float(prices[ticker].dropna().iloc[-1])
        row = {
            "rank":         rank,
            "ticker":       ticker,
            "sleeve":       sleeve_of(ticker),
            "weight":       round(float(weight), 6),
            "weight_pct":   round(float(weight) * 100, 2),
            "last_close":   round(last_close, 2),
            "as_of":        str(today.date()),
        }
        if capital is not None and last_close > 0:
            dollars = float(weight) * capital
            row["dollars"] = round(dollars, 2)
            row["shares"]  = round(dollars / last_close, 4)
        rows.append(row)

    last_rebal = status["last_rebal"]
    print("\n" + "=" * 84)
    print("3-Way Blend (SPY / Macro Regime Tilt / Multi-Asset Rotation) — Target Book")
    print(f"Rebalance date: {last_rebal.date() if last_rebal is not None else '?'}"
          f"   |   Priced off close: {today.date()}")
    print("=" * 84)
    if capital is not None:
        print(f"  {'Rank':<5} {'Ticker':<8} {'Sleeve':<14} {'Weight':>8} {'Buy $':>12} {'Close':>10}")
        print("  " + "-" * 66)
        for r in rows:
            print(f"  {r['rank']:<5} {r['ticker']:<8} {r['sleeve']:<14} {r['weight_pct']:>7.2f}% "
                  f"{r.get('dollars', 0):>12,.2f} {r['last_close']:>10.2f}")
    else:
        print(f"  {'Rank':<5} {'Ticker':<8} {'Sleeve':<14} {'Weight':>8} {'Close':>10}")
        print("  " + "-" * 54)
        for r in rows:
            print(f"  {r['rank']:<5} {r['ticker']:<8} {r['sleeve']:<14} {r['weight_pct']:>7.2f}% "
                  f"{r['last_close']:>10.2f}")
    print("=" * 84)
    print(f"  Rebalance cadence: MONTHLY (last trading day of each month).")
    print(f"  Next rebalance:    {status['next_rebal'].date()}  "
          f"(~{status['days_until_next']} trading day(s) away)")
    print("  Execute these at the NEXT open — the backtest applies a 1-day execution")
    print("  lag, so same-day fills are not what was validated.")
    print("  Between rebalances, let the weights DRIFT (do not top up to target) —")
    print("  hold-with-drift is exactly what the backtest simulates.")
    if force and not status["due"]:
        print("  NOTE: --force used; no rebalance was actually due. Trading this book")
        print("        off-schedule departs from the validated monthly cadence.")

    # Rescale the PREVIOUS book's dollars to THIS run's capital before diffing,
    # so a capital change alone (e.g. checking a different portfolio) never
    # shows up as a phantom BUY/SELL/RESIZE — the diff should reflect only
    # real weight changes driven by the rebalance itself.
    prev_rows_prior = (prev or {}).get("book", [])
    if capital is not None:
        prev_rows_for_diff = [
            {**r, "dollars": round(float(r.get("weight", 0.0)) * capital, 2)}
            for r in prev_rows_prior
        ]
    else:
        prev_rows_for_diff = prev_rows_prior
    trades = _compute_trades(prev_rows_for_diff, rows, capital is not None)
    buys, sells, resizes = trades["buys"], trades["sells"], trades["resizes"]
    print("\n" + "-" * 84)
    print("REBALANCE — changes vs your previously held blend book")
    print("-" * 84)
    if not (buys or sells or resizes):
        print("  (no changes — book matches your last run)")
    for t in sells:
        amt = f" ${t['dollars']:,.2f}" if t.get("dollars") is not None else ""
        print(f"  SELL    {t['ticker']:<8}{amt}")
    for t in buys:
        amt = f" ${t['dollars']:,.2f}" if t.get("dollars") is not None else ""
        print(f"  BUY     {t['ticker']:<8}{amt}")
    for t in resizes:
        if t.get("delta_dollars") is not None:
            d = t["delta_dollars"]
            verb = "ADD " if d > 0 else "TRIM"
            print(f"  {verb}    {t['ticker']:<8} {'+' if d >= 0 else '−'}${abs(d):,.2f}  "
                  f"(${t['from_dollars']:,.2f} → ${t['to_dollars']:,.2f})")
        else:
            print(f"  RESIZE  {t['ticker']:<8} {t['from_pct']:.2f}% → {t['to_pct']:.2f}%")
    print("=" * 84)

    header = {
        "as_of":        str(today.date()),          # price date the closes came from
        "rebal_as_of":  str(last_rebal.date()) if last_rebal is not None else None,
        "next_rebal":   str(status["next_rebal"].date()),
        "capital":      capital,
        "n_names":      len(rows),
        "cadence":      "monthly (last trading day of month), 1-day execution lag",
        "exit_rule":    "Hold with drift until the next month-end rebalance; "
                        "do not top up to target between rebalances.",
    }
    _save_blend_book(out_dir, {"header": header, "book": rows})
    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    payload = {"generated": pd.Timestamp.now().isoformat(), "header": header,
              "book": rows, "trades": trades}
    (out_dir / f"blend_ideas_{ts}.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nBook written to: {out_dir}/blend_ideas_{ts}.json")


def cmd_blend_verify(cfg: dict, args: argparse.Namespace) -> None:
    """Assert the blend's live book == what the backtest engine would hold on
    the same date. `blend.target_book` and `blend.simulate_blend` both read
    from the SAME `blend.blend_target_weights`, so this should always PASS by
    construction — the check guards against a future edit accidentally
    diverging the two paths (same purpose as the equity engine's verify-book).
    """
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    prices = data_mod.load_price_panel(tickers=[], start=_ideas_start(cfg), end=_live_end(),
                                       cache_dir=cache_dir)
    as_of = prices["SPY"].dropna().index.max()

    live   = blend_mod.target_book(prices, cfg, as_of=as_of)
    target = blend_mod.blend_target_weights(prices, cfg)
    engine = target.loc[as_of]
    engine = engine[engine > 0.0].sort_values(ascending=False)

    same_names = set(engine.index) == set(live.index)
    all_idx = sorted(set(engine.index) | set(live.index))
    max_w_diff = (float((engine.reindex(all_idx).fillna(0.0)
                        - live.reindex(all_idx).fillna(0.0)).abs().max())
                 if all_idx else 0.0)

    print("\n─── blend-verify: live blend book vs backtest engine ───")
    print(f"  engine names: {len(engine)}   live names: {len(live)}")
    print(f"  identical name set: {same_names}")
    print(f"  max per-name weight diff: {max_w_diff:.2e}")
    ok = same_names and max_w_diff < 1e-9
    print(f"  MATCH: {'✓ PASS' if ok else '✗ FAIL'}")


# ─────────────────────────────────────────────────────────────────────────────
#  Interactive menu
# ─────────────────────────────────────────────────────────────────────────────

def _interactive_menu(cfg: dict) -> None:
    print("\n" + "=" * 64)
    print("  csmom — multi-strategy trade-idea engine")
    print("  PRIMARY: 3-way blend (SPY / macro tilt / rotation), monthly")
    print("=" * 64)
    print("  1) fetch          — build/refresh PIT universe + price cache")
    print("  2) backtest       — blend walk-forward OOS backtest + validation")
    print("  3) ideas          — today's blend book (self-gated, monthly)")
    print("  4) verify-book    — blend live book == blend engine")
    print("  5) equity-backtest— original equity momentum engine backtest")
    print("  6) equity-ideas   — original equity momentum stock book")
    print("  q) quit")
    print("=" * 64)
    choice = input("  Choice: ").strip().lower()

    class _Args:
        oos_frac = 0.30
        folds    = 5
        mcpt     = 0
        capital  = None
        holdings = None
        force    = False
        top      = cfg.get("output", {}).get("top_n_ideas", 25)

    def _ask_capital():
        cap = input("  Account capital for $ / share sizing? [blank = weights only] ").strip()
        _Args.capital = float(cap) if cap.replace(".", "", 1).isdigit() else None

    if choice in ("1", "fetch"):
        cmd_fetch(cfg)
    elif choice in ("2", "backtest"):
        cmd_blend_backtest(cfg, _Args())
    elif choice in ("3", "ideas"):
        _ask_capital()
        cmd_blend_ideas(cfg, _Args())
    elif choice in ("4", "verify-book"):
        cmd_blend_verify(cfg, _Args())
    elif choice in ("5", "equity-backtest"):
        n = input("  MCPT permutations? [0 = skip, 200 = fast, 1000 = rigorous] ").strip()
        _Args.mcpt = int(n) if n.isdigit() else 0
        cmd_backtest(cfg, _Args())
    elif choice in ("6", "equity-ideas"):
        _ask_capital()
        cmd_ideas(cfg, _Args())
    elif choice in ("q", "quit"):
        print("  Goodbye.")
    else:
        print("  Unrecognised choice.  Run `python csmom.py --help` for usage.")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg = load_config()

    parser = argparse.ArgumentParser(
        prog="csmom",
        description="Multi-strategy trade-idea engine. PRIMARY = 3-way blend "
                    "(SPY / macro regime tilt / multi-asset rotation), monthly "
                    "rebalance. Equity cross-sectional momentum under `equity-*`.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("fetch", help="Build PIT universe + download prices")

    # ── PRIMARY flow: the 3-way blend ────────────────────────────────────────
    # `ideas`/`backtest`/`verify-book` run the BLEND as of 2026-08-05, so an
    # existing cron entry switches to it with no edit. `blend-*` remain as
    # explicit aliases; the equity engine lives on under `equity-*`.
    def _add_blend_backtest(name: str, help_: str):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--oos-frac", type=float, default=0.30, dest="oos_frac",
                       help="Fraction of history held out for OOS (default 0.30)")
        p.add_argument("--folds", type=int, default=5,
                       help="Number of multi-fold walk-forward blocks (default 5)")
        return p

    def _add_blend_ideas(name: str, help_: str):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--capital", type=float, default=None,
                       help="Account capital — adds the $ to buy per name")
        p.add_argument("--force", action="store_true",
                       help="Rebuild the book even if no month-end rebalance is due "
                            "(bypasses the monthly cadence gate)")
        return p

    _add_blend_backtest("backtest",       "Walk-forward backtest of the 3-way blend (PRIMARY)")
    _add_blend_ideas   ("ideas",          "Today's target blend book + rebalance trades (PRIMARY)")
    sub.add_parser     ("verify-book",    help="Assert the live blend book == the blend engine")
    _add_blend_backtest("blend-backtest", "Alias of `backtest`")
    _add_blend_ideas   ("blend-ideas",    "Alias of `ideas`")
    sub.add_parser     ("blend-verify",   help="Alias of `verify-book`")

    # ── Equity cross-sectional momentum engine (preserved, secondary) ────────
    eb = sub.add_parser("equity-backtest",
                        help="Equity cross-sectional momentum walk-forward backtest")
    eb.add_argument("--mcpt", type=int, default=0,
                    help="MCPT permutations (0 = skip, 200 = fast, 1000 = rigorous)")
    eb.add_argument("--oos-frac", type=float, default=0.30, dest="oos_frac",
                    help="Fraction of history held out for OOS (default 0.30)")
    eb.add_argument("--folds", type=int, default=5,
                    help="Number of multi-fold walk-forward blocks (default 5)")

    ei = sub.add_parser("equity-ideas",
                        help="Equity engine's target stock book + weekly rebalance trades")
    ei.add_argument("--capital", type=float, default=None,
                    help="Account capital — adds the $ to buy per name (fractional shares)")
    ei.add_argument("--holdings", type=str, default=None,
                    help="Path to a JSON {ticker: dollar_value} of holdings to diff against")
    ei.add_argument("--force", action="store_true",
                    help="Rebuild the book even if a rebalance isn't due yet "
                         "(bypasses the rebal_freq cadence gate)")

    sub.add_parser("equity-verify-book",
                   help="Assert the live equity book == the equity backtest engine")

    args = parser.parse_args()

    if args.cmd == "fetch":
        cmd_fetch(cfg)
    elif args.cmd in ("backtest", "blend-backtest"):
        cmd_blend_backtest(cfg, args)
    elif args.cmd in ("ideas", "blend-ideas"):
        cmd_blend_ideas(cfg, args)
    elif args.cmd in ("verify-book", "blend-verify"):
        cmd_blend_verify(cfg, args)
    elif args.cmd == "equity-backtest":
        cmd_backtest(cfg, args)
    elif args.cmd == "equity-ideas":
        cmd_ideas(cfg, args)
    elif args.cmd == "equity-verify-book":
        cmd_verify_book(cfg, args)
    else:
        _interactive_menu(cfg)


if __name__ == "__main__":
    main()
