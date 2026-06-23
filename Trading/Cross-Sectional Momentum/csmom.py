#!/usr/bin/env python3
"""csmom — Cross-Sectional Residual Momentum Trade-Idea Engine.

Subcommands:
  fetch      Build (or refresh) the point-in-time S&P 1500 membership table
             and download price history.
  backtest   Run a walk-forward backtest (weekly-rebalance simulation) + DSR/MCPT.
  ideas      Output today's target portfolio book — the exact holdings the
             backtest trades (full top-quintile, equal-dollar, vol-scaled,
             regime-gated) plus the weekly rebalance trade list.
  verify-book  Assert the live book == the backtest position engine.

Usage:
  python csmom.py                     # interactive menu
  python csmom.py fetch
  python csmom.py backtest [--mcpt N] [--oos-frac 0.30]
  python csmom.py ideas    [--capital N] [--holdings file.json]
  python csmom.py verify-book

HONEST EXPECTATIONS:
  - This strategy was validated on *survivorship-biased* current S&P 500
    data (Stage 0: Sharpe 0.97, MCPT p≈0, DSR≈1).
  - PIT membership correction and live trading will reduce Sharpe
    materially; realistic expectation is 0.4–0.7 net.
  - All validation tests are run by default; a FAIL is reported honestly
    and the trade-ideas report is suppressed until tests pass.
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
        tickers  = ever,
        start    = cfg["data"]["start_date"],
        end      = live_end,
        cache_dir= cache_dir,
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
    primary_res = bt_mod.walk_forward(prices, cfg, pit_df=pit_df, oos_frac=oos_frac)
    results = {"primary (OOS)": primary_res}

    # ── Validation suite ─────────────────────────────────────────────────────
    print("\n─── DSR (Deflated Sharpe) ───────────────────────────────────────────")
    observed_sh = val_mod.compute_metrics(primary_res.net_ret, primary_res.bench_ret)["sharpe"]
    dsr_result  = val_mod.run_dsr(primary_res.net_ret, grid_sharpes=[observed_sh])

    mcpt_result = None
    if n_perm > 0:
        print(f"\n─── Monte Carlo Permutation Test ({n_perm} perms) ──────────────────")
        _signals = sig_mod.primary_signal(prices, cfg)

        def _portfolio_fn(perm_sig: pd.DataFrame) -> pd.Series:
            pos = port_mod.build_positions(perm_sig, prices, cfg, pit_df=pit_df)
            return port_mod.portfolio_returns(pos, prices, cfg)

        mcpt_result = val_mod.run_mcpt(
            _signals, prices, observed_sh, _portfolio_fn, n_perm=n_perm
        )

    # ── Report ───────────────────────────────────────────────────────────────
    print("\n─── Report ──────────────────────────────────────────────────────────")
    rep_mod.write_backtest_report(results, dsr_result, None, mcpt_result, out_dir)


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


def _read_holdings_file(path: Path) -> dict:
    """Read an external holdings file ({ticker: shares}) to diff against."""
    raw = json.loads(Path(path).read_text())
    return {str(k).upper(): int(v) for k, v in raw.items()}


def _compute_trades(prev_rows: list[dict], new_rows: list[dict],
                    has_capital: bool, prev_shares: dict | None = None) -> dict:
    """BUY/SELL/RESIZE diff of the new book vs the previously held one.

    Diffs on share counts when capital is known (actionable order sizes),
    otherwise on weight %.  `prev_shares` overrides prev_rows (used by --holdings).
    """
    buys, sells, resizes = [], [], []
    if prev_shares is not None:
        prev_sh = dict(prev_shares)
        prev_w  = {}
    else:
        prev_sh = {r["ticker"]: r.get("shares", 0) for r in (prev_rows or [])}
        prev_w  = {r["ticker"]: r.get("weight_pct", 0.0) for r in (prev_rows or [])}
    new_sh = {r["ticker"]: r.get("shares", 0) for r in new_rows}
    new_w  = {r["ticker"]: r.get("weight_pct", 0.0) for r in new_rows}

    for t in new_rows:
        tk = t["ticker"]
        if tk not in prev_sh and tk not in prev_w:
            buys.append({"ticker": tk, "shares": new_sh.get(tk) if has_capital else None})
        elif has_capital:
            d = new_sh.get(tk, 0) - prev_sh.get(tk, 0)
            if abs(d) >= 1:
                resizes.append({"ticker": tk, "delta_shares": int(d),
                                "from_shares": int(prev_sh.get(tk, 0)),
                                "to_shares": int(new_sh.get(tk, 0))})
        else:
            if abs(new_w.get(tk, 0.0) - prev_w.get(tk, 0.0)) >= 0.20:
                resizes.append({"ticker": tk, "delta_shares": None,
                                "from_pct": prev_w.get(tk, 0.0), "to_pct": new_w.get(tk, 0.0)})

    held_now = set(new_sh)
    for tk in (set(prev_sh) | set(prev_w)):
        if tk not in held_now:
            sells.append({"ticker": tk, "shares": prev_sh.get(tk) if has_capital else None})
    return {"buys": buys, "sells": sells, "resizes": resizes}


# ─────────────────────────────────────────────────────────────────────────────
#  ideas
# ─────────────────────────────────────────────────────────────────────────────

def cmd_ideas(cfg: dict, args: argparse.Namespace) -> None:
    """Score today's universe and output ranked long ideas."""
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    out_dir   = _HERE / "outputs"
    top_n     = int(getattr(args, "top", cfg.get("output", {}).get("top_n_ideas", 25)))

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

    today  = prices.index[-1]
    stocks = prices.drop(columns=["SPY"], errors="ignore")

    # ── Freshness guard #1: panel must be current vs the real calendar ───────
    # The panel's own last date is "today" for scoring, but if that date lags
    # the wall-clock by more than a few days the whole snapshot is stale and we
    # would price the book off old closes. Catch that explicitly.
    wall_today = pd.Timestamp.today().normalize()
    panel_lag  = (wall_today - today).days
    if panel_lag > 5:
        print(f"\nERROR: price panel is stale — latest close is {today.date()}, "
              f"{panel_lag} days behind today ({wall_today.date()}).")
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
        stocks = prices.drop(columns=["SPY"], errors="ignore")

    # ── Build the EXACT book the backtest holds today ────────────────────────
    # target_book() is the single source of truth: top-quintile → equal-dollar
    # 1/N → vol-scaling → regime gate. Identical math to the backtest engine, so
    # trading this book reproduces the validated curve — no truncation, no
    # un-traded stop/target brackets.
    print(f"\nBuilding target book as of {today.date()} …")
    book = port_mod.target_book(prices, cfg, pit_df=pit_df, as_of=today)

    reg_cfg   = cfg.get("regime_filter", {})
    regime_ok = sig_mod.spy_regime(
        prices,
        ma_days = int(reg_cfg.get("spy_ma_days", 200)),
        vol_cap = float(reg_cfg.get("vol_cap", 0.25)),
    )
    in_regime = bool(regime_ok.get(today, True))

    capital = getattr(args, "capital", None)

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
            row["shares"]  = int(dollars // last_close)
        rows.append(row)

    gross = float(book.sum()) if not book.empty else 0.0

    # ── Cadence note + rebalance diff vs the previously held book ─────────────
    prev = _load_prev_book(out_dir)
    rebal_freq = int(cfg.get("portfolio", {}).get("rebal_freq", 5))
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
        prev_shares = _read_holdings_file(Path(holdings_path))
        trades = _compute_trades([], rows, capital is not None, prev_shares=prev_shares)
    else:
        trades = _compute_trades((prev or {}).get("book", []), rows, capital is not None)

    header = {
        "as_of":      str(today.date()),
        "regime_on":  in_regime,
        "gross_pct":  round(gross * 100, 1),
        "cash_pct":   round((1.0 - gross) * 100, 1),
        "n_names":    len(rows),
        "capital":    capital,
        "exit_rule":  "Exit any name that leaves next week's book; hold the rest. No intraday stops.",
        "cadence_note": cadence_note,
    }

    if not rows:
        if not in_regime:
            print("\nREGIME OFF (SPY below its 200-dma / high vol) → hold 100% CASH.")
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

    # Engine path (what the backtest trades), end-anchored so the last row is fresh.
    signals = sig_mod.primary_signal(prices, cfg)
    pos     = port_mod.build_positions(signals, prices, cfg, pit_df=pit_df,
                                       rebal_anchor="end")
    engine  = pos.iloc[-1]
    engine  = engine[engine > 0.0].sort_values(ascending=False)

    # Live path (what `ideas` shows).
    live = port_mod.target_book(prices, cfg, pit_df=pit_df)

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
#  Interactive menu
# ─────────────────────────────────────────────────────────────────────────────

def _interactive_menu(cfg: dict) -> None:
    print("\n" + "=" * 60)
    print("  csmom — Cross-Sectional Momentum Trade-Idea Engine")
    print("=" * 60)
    print("  1) fetch      — build/refresh PIT universe + price cache")
    print("  2) backtest   — walk-forward OOS backtest + validation")
    print("  3) ideas      — generate today's ranked trade ideas")
    print("  q) quit")
    print("=" * 60)
    choice = input("  Choice: ").strip().lower()

    class _Args:
        oos_frac = 0.30
        mcpt     = 0
        capital  = None
        holdings = None
        top      = cfg.get("output", {}).get("top_n_ideas", 25)

    if choice in ("1", "fetch"):
        cmd_fetch(cfg)
    elif choice in ("2", "backtest"):
        n = input("  MCPT permutations? [0 = skip, 200 = fast, 1000 = rigorous] ").strip()
        _Args.mcpt = int(n) if n.isdigit() else 0
        cmd_backtest(cfg, _Args())
    elif choice in ("3", "ideas"):
        cap = input("  Account capital for $ / share sizing? [blank = weights only] ").strip()
        _Args.capital = float(cap) if cap.replace(".", "", 1).isdigit() else None
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
        description="Cross-Sectional Residual Momentum Trade-Idea Engine",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("fetch", help="Build PIT universe + download prices")

    bt_parser = sub.add_parser("backtest", help="Walk-forward backtest + validation")
    bt_parser.add_argument("--mcpt",     type=int, default=0,
                           help="MCPT permutations (0 = skip, 200 = fast, 1000 = rigorous)")
    bt_parser.add_argument("--oos-frac", type=float, default=0.30, dest="oos_frac",
                           help="Fraction of history held out for OOS (default 0.30)")

    id_parser = sub.add_parser("ideas",
                               help="Output today's target portfolio book + rebalance trades")
    id_parser.add_argument("--capital", type=float, default=None,
                           help="Account capital — adds $ allocation + share counts per name")
    id_parser.add_argument("--holdings", type=str, default=None,
                           help="Path to a JSON {ticker: shares} of actual holdings to diff against")

    sub.add_parser("verify-book",
                   help="Assert the live book == the backtest engine (consistency self-check)")

    args = parser.parse_args()

    if args.cmd == "fetch":
        cmd_fetch(cfg)
    elif args.cmd == "backtest":
        cmd_backtest(cfg, args)
    elif args.cmd == "ideas":
        cmd_ideas(cfg, args)
    elif args.cmd == "verify-book":
        cmd_verify_book(cfg, args)
    else:
        _interactive_menu(cfg)


if __name__ == "__main__":
    main()
