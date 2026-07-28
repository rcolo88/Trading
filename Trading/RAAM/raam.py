#!/usr/bin/env python3
"""raam — Ranked Asset Allocation Model (Giordano 2018, 2018 Charles H. Dow Award).

Subcommands:
  fetch        Download/refresh OHLC price history for the 7Twelve universe.
  backtest     Walk-forward OOS backtest (default) or --full-sample paper-
               comparable run, vs the paper's own benchmark set, + DSR/MCPT.
  ideas        Output this month's target portfolio book — the exact holdings
               the backtest trades (n_select slots at fixed weight, cash-
               substituted per the momentum filter) — plus the rebalance
               trade list vs your last book.
  verify-book  Assert the live book == the backtest position engine.

Usage:
  python raam.py                      # interactive menu
  python raam.py fetch
  python raam.py backtest [--mcpt N] [--oos-frac 0.30] [--full-sample]
  python raam.py ideas    [--capital N] [--holdings file.json]
  python raam.py verify-book

HONEST EXPECTATIONS:
  The paper claims Sharpe 1.94 (2004-2017) — GROSS of all costs, fit on
  undisclosed wM/wV/wC weights, with 2 of 12 assets' pre-inception history
  filled by interpolation through the 2008 crisis. None of that survives
  here: real data only (an asset joins the ranking pool only once it has real
  history), equal wM=wV=wC by design (no fitting), and every return is net of
  commission+spread. Every `backtest` report prints a paper-comparison table
  so the resulting gap is visible, not hidden.
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

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from raam import backtest as bt_mod
from raam import data as data_mod
from raam import indicators as ind_mod
from raam import portfolio as port_mod
from raam import ranking as rank_mod
from raam import report as rep_mod
from raam import universe as univ_mod
from raam import validation as val_mod


# ─────────────────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────────────────

def load_config(path: Path = _HERE / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _live_end() -> str:
    """End date for LIVE commands — tomorrow (yfinance's `end` is exclusive)
    so the download always includes the most recent available close."""
    return (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _backtest_window(cfg: dict) -> tuple[str, str]:
    """Resolve the backtest [start, end] window from config.data."""
    data_cfg = cfg.get("data", {})
    start = data_cfg.get("start_date")
    if start in (None, "", "auto"):
        start = data_mod._CACHE_HISTORY_START
    start = pd.Timestamp(start)

    ceiling = pd.Timestamp.today().normalize()
    end_cfg = data_cfg.get("end_date")
    end = ceiling if end_cfg in (None, "", "auto") else min(pd.Timestamp(end_cfg), ceiling)

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _all_tickers() -> list[str]:
    return univ_mod.ALL_TICKERS + [univ_mod.SPY]


# ─────────────────────────────────────────────────────────────────────────────
#  fetch
# ─────────────────────────────────────────────────────────────────────────────

def cmd_fetch(cfg: dict) -> None:
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    tickers   = _all_tickers()
    print(f"─── OHLC price download: {len(tickers)} tickers (7Twelve universe + SPY) ───")
    panel = data_mod.load_ohlc_panel(tickers, start="auto", end=_live_end(),
                                     cache_dir=cache_dir, refresh="full")
    close = data_mod.close_panel(panel)
    print("\n  First real close per ticker (defines the availability mask — see "
          "raam/universe.py:eligible_on):")
    for t, _num, sleeve, _name in univ_mod.ROSTER:
        s = close[t].dropna()
        first = str(s.index.min().date()) if len(s) else "N/A"
        print(f"    {t:<6} {first:<12} {sleeve}")
    print("\nfetch complete.")


# ─────────────────────────────────────────────────────────────────────────────
#  backtest
# ─────────────────────────────────────────────────────────────────────────────

def cmd_backtest(cfg: dict, args: argparse.Namespace) -> None:
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    out_dir   = _HERE / "outputs"
    tickers   = _all_tickers()

    bt_start, bt_end = _backtest_window(cfg)
    print(f"  Backtest window: {bt_start} -> {bt_end}")
    panel = data_mod.load_ohlc_panel(tickers, start=bt_start, end=bt_end, cache_dir=cache_dir)
    close = data_mod.close_panel(panel)

    full_sample_mode = bool(getattr(args, "full_sample", False))
    oos_frac = float(getattr(args, "oos_frac", None)
                     or cfg.get("validation", {}).get("walk_forward_oos_frac", 0.30))
    n_perm   = int(getattr(args, "mcpt", 0))

    if full_sample_mode:
        print("\n─── Full-sample backtest (paper-comparable window) ─────────────────")
        results = bt_mod.full_sample(panel, close, cfg)
        mode = "full_sample"
    else:
        print(f"\n─── Walk-forward backtest ({int((1 - oos_frac) * 100)}% IS / "
              f"{int(oos_frac * 100)}% OOS) ──")
        print("  Simulating the live process: rebalance monthly, hold with drift …")
        results = bt_mod.walk_forward(panel, close, cfg, oos_frac=oos_frac)
        mode = "walk_forward"

    raam_res   = results["RAAM (Total Rank)"]
    eval_start = raam_res.net_ret.index.min()

    print("\n─── DSR (Deflated Sharpe) ───────────────────────────────────────────")
    observed_sh = val_mod.compute_metrics(raam_res.net_ret, raam_res.bench_ret)["sharpe"]
    trial_grid  = [float(s) for s in cfg.get("validation", {}).get("trial_sharpes", [])]
    dsr_result  = val_mod.run_dsr(raam_res.net_ret, grid_sharpes=trial_grid + [observed_sh])

    mcpt_result = None
    if n_perm > 0:
        print(f"\n─── Monte Carlo Permutation Test ({n_perm} perms) ──────────────────")
        indicators = ind_mod.compute_indicators(panel, univ_mod.RANKABLE, cfg)
        total_rank = rank_mod.compute_total_rank(indicators, close, cfg)
        mcpt_result = val_mod.run_mcpt(total_rank, indicators["M"], close, cfg,
                                       observed_sh, eval_start=eval_start, n_perm=n_perm)

    print("\n─── Report ──────────────────────────────────────────────────────────")
    rep_mod.write_backtest_report(results, dsr_result, None, mcpt_result, out_dir, mode=mode)


# ─────────────────────────────────────────────────────────────────────────────
#  ideas — book persistence + rebalance diff
# ─────────────────────────────────────────────────────────────────────────────

BOOK_FILE = "portfolio_book.json"


def _load_prev_book(out_dir: Path) -> dict | None:
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
    """{"TICKER": dollar_value} of current holdings to diff against."""
    raw = json.loads(Path(path).read_text())
    return {str(k).upper(): float(v) for k, v in raw.items()}


def _compute_trades(prev_rows: list[dict], new_rows: list[dict],
                    has_capital: bool, prev_dollars: dict | None = None) -> dict:
    """BUY/SELL/RESIZE diff of the new book vs the previously held one."""
    buys, sells, resizes = [], [], []
    if prev_dollars is not None:
        prev_d = {k: float(v) for k, v in prev_dollars.items()}
        prev_w: dict = {}
    else:
        prev_d = {r["ticker"]: r.get("dollars", 0.0) for r in (prev_rows or [])}
        prev_w = {r["ticker"]: r.get("weight_pct", 0.0) for r in (prev_rows or [])}
    new_d = {r["ticker"]: r.get("dollars", 0.0) for r in new_rows}
    new_w = {r["ticker"]: r.get("weight_pct", 0.0) for r in new_rows}

    for t in new_rows:
        tk = t["ticker"]
        if tk not in prev_d and tk not in prev_w:
            buys.append({"ticker": tk,
                        "dollars": round(new_d.get(tk, 0.0), 2) if has_capital else None})
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
            sells.append({"ticker": tk,
                          "dollars": round(prev_d.get(tk, 0.0), 2) if has_capital else None})
    return {"buys": buys, "sells": sells, "resizes": resizes}


def cmd_ideas(cfg: dict, args: argparse.Namespace) -> None:
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    out_dir   = _HERE / "outputs"
    tickers   = _all_tickers()
    cash      = univ_mod.CASH_TICKER
    n_select  = int(cfg.get("ranking", {}).get("n_select", 5))

    panel = data_mod.load_ohlc_panel(tickers, start="auto", end=_live_end(),
                                     cache_dir=cache_dir, refresh="auto")
    close = data_mod.close_panel(panel)

    # Last date with a near-complete cross-section — guards a partial download
    # (only 12 tickers total, so "all but one present" is the right bar).
    cov_thresh   = max(5, panel["Close"].shape[1] - 1)
    today        = close.dropna(thresh=cov_thresh).index[-1]
    wall_today   = pd.Timestamp.today().normalize()
    panel_lag_bd = int(np.busday_count(today.date(), wall_today.date()))
    if wall_today.dayofweek < 5 and not data_mod.market_close_passed():
        panel_lag_bd -= 1   # today's session is still open — its close can't exist yet

    if panel_lag_bd >= 1:
        print(f"Cache is {panel_lag_bd} trading day(s) behind — refreshing prices …")
        panel = data_mod.load_ohlc_panel(tickers, start="auto", end=_live_end(),
                                         cache_dir=cache_dir, refresh="full")
        close = data_mod.close_panel(panel)
        today = close.dropna(thresh=cov_thresh).index[-1]
        panel_lag_bd = int(np.busday_count(today.date(), wall_today.date()))
        if wall_today.dayofweek < 5 and not data_mod.market_close_passed():
            panel_lag_bd -= 1

    if panel_lag_bd > 3:
        print(f"\nERROR: price panel is stale — latest close is {today.date()}, "
              f"{panel_lag_bd} trading days behind today ({wall_today.date()}).")
        print("  Run `python raam.py fetch` to refresh the price cache, then try again.")
        return

    print(f"\nBuilding target book as of {today.date()} …")
    book = port_mod.target_book(panel, close, cfg, as_of=today)

    prev = _load_prev_book(out_dir)
    capital = getattr(args, "capital", None)
    if capital is None:
        prev_capital = (prev or {}).get("header", {}).get("capital")
        if prev_capital is not None:
            capital = float(prev_capital)
            print(f"  No --capital given — using last book's capital: ${capital:,.0f}")

    rows: list[dict] = []
    for rank, (ticker, weight) in enumerate(book.items(), start=1):
        last_close = float(close[ticker].dropna().iloc[-1])
        row = {
            "rank":       rank,
            "ticker":     ticker,
            "sleeve":     univ_mod.SLEEVE.get(ticker, ""),
            "weight":     round(float(weight), 6),
            "weight_pct": round(float(weight) * 100, 2),
            "last_close": round(last_close, 2),
            "as_of":      str(today.date()),
        }
        if capital is not None and last_close > 0:
            dollars = float(weight) * capital
            row["dollars"] = round(dollars, 2)
            row["shares"]  = round(dollars / last_close, 4)
        rows.append(row)

    n_slots_filled = sum(1 for t in book.index if t != cash)
    cash_weight    = float(book.get(cash, 0.0))
    n_cash_slots   = int(round(cash_weight * n_select))

    rebal_dates  = rank_mod.month_end_dates(close.index)
    cadence_note = ""
    if prev and prev.get("header", {}).get("as_of"):
        prev_as_of = pd.Timestamp(prev["header"]["as_of"])
        upcoming   = rebal_dates[rebal_dates > today]
        if prev_as_of == today:
            cadence_note = "same-day rerun — book unchanged unless data refreshed."
        elif len(upcoming):
            cadence_note = f"next scheduled rebalance: {upcoming[0].date()} (month-end)."
        else:
            cadence_note = "book reflects the latest available month-end rebalance."

    holdings_path = getattr(args, "holdings", None)
    if holdings_path:
        prev_dollars = _read_holdings_file(Path(holdings_path))
        trades = _compute_trades([], rows, capital is not None, prev_dollars=prev_dollars)
    else:
        trades = _compute_trades((prev or {}).get("book", []), rows, capital is not None)

    header = {
        "as_of":          str(today.date()),
        "n_select":       n_select,
        "n_slots_filled": n_slots_filled,
        "n_cash_slots":   n_cash_slots,
        "cash_pct":       round(cash_weight * 100, 1),
        "capital":        capital,
        "exit_rule":      "Hold each slot until the next month-end rebalance changes it. "
                          "No intraday stops.",
        "cadence_note":   cadence_note,
    }

    rep_mod.write_ideas_report(rows, header, trades, out_dir)
    if not holdings_path:
        _save_book(out_dir, {"header": header, "book": rows})


# ─────────────────────────────────────────────────────────────────────────────
#  verify-book — prove `ideas` holds exactly what the backtest engine holds
# ─────────────────────────────────────────────────────────────────────────────

def cmd_verify_book(cfg: dict, args: argparse.Namespace) -> None:
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    tickers   = _all_tickers()

    panel = data_mod.load_ohlc_panel(tickers, start="auto", end=_live_end(), cache_dir=cache_dir)
    close = data_mod.close_panel(panel)

    cov_thresh = max(5, panel["Close"].shape[1] - 1)
    as_of = close.dropna(thresh=cov_thresh).index[-1]

    engine_pos = port_mod.build_positions_from_scratch(panel, close, cfg)
    engine     = engine_pos.loc[as_of]
    engine     = engine[engine > 0.0].sort_values(ascending=False)

    live = port_mod.target_book(panel, close, cfg, as_of=as_of)

    same_names = set(engine.index) == set(live.index)
    all_idx    = sorted(set(engine.index) | set(live.index))
    max_w_diff = float((engine.reindex(all_idx).fillna(0.0)
                        - live.reindex(all_idx).fillna(0.0)).abs().max()) if all_idx else 0.0

    print("\n─── verify-book: live ideas book vs backtest engine ───")
    print(f"  as of: {as_of.date()}")
    print(f"  engine names: {len(engine)}   live names: {len(live)}")
    print(f"  identical name set: {same_names}")
    print(f"  max per-name weight diff: {max_w_diff:.2e}")
    ok = same_names and max_w_diff < 1e-9
    print(f"  MATCH: {'PASS' if ok else 'FAIL'}")
    print("  (the backtest chains this exact book monthly with drift — simulate_drift)")


# ─────────────────────────────────────────────────────────────────────────────
#  Interactive menu
# ─────────────────────────────────────────────────────────────────────────────

def _interactive_menu(cfg: dict) -> None:
    print("\n" + "=" * 60)
    print("  raam — Ranked Asset Allocation Model")
    print("=" * 60)
    print("  1) fetch        — download/refresh OHLC price cache")
    print("  2) backtest     — walk-forward OOS backtest + validation")
    print("  3) backtest --full-sample — paper-comparable full-history run")
    print("  4) ideas        — generate this month's target book")
    print("  5) verify-book  — check live book == backtest engine")
    print("  q) quit")
    print("=" * 60)
    choice = input("  Choice: ").strip().lower()

    class _Args:
        oos_frac    = cfg.get("validation", {}).get("walk_forward_oos_frac", 0.30)
        mcpt        = 0
        full_sample = False
        capital     = None
        holdings    = None

    if choice in ("1", "fetch"):
        cmd_fetch(cfg)
    elif choice in ("2", "backtest"):
        n = input("  MCPT permutations? [0 = skip, 200 = fast, 1000 = rigorous] ").strip()
        _Args.mcpt = int(n) if n.isdigit() else 0
        cmd_backtest(cfg, _Args())
    elif choice == "3":
        _Args.full_sample = True
        cmd_backtest(cfg, _Args())
    elif choice in ("4", "ideas"):
        cap = input("  Account capital for $ / share sizing? [blank = weights only] ").strip()
        _Args.capital = float(cap) if cap.replace(".", "", 1).isdigit() else None
        cmd_ideas(cfg, _Args())
    elif choice in ("5", "verify-book"):
        cmd_verify_book(cfg, _Args())
    elif choice in ("q", "quit"):
        print("  Goodbye.")
    else:
        print("  Unrecognised choice.  Run `python raam.py --help` for usage.")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg = load_config()

    parser = argparse.ArgumentParser(
        prog="raam",
        description="RAAM — Ranked Asset Allocation Model (Giordano 2018)",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("fetch", help="Download/refresh OHLC price cache")

    bt_parser = sub.add_parser("backtest", help="Walk-forward backtest + validation")
    bt_parser.add_argument("--mcpt", type=int, default=0,
                           help="MCPT permutations (0 = skip, 200 = fast, 1000 = rigorous)")
    bt_parser.add_argument("--oos-frac", type=float, default=None, dest="oos_frac",
                           help="Fraction of history held out for OOS (default from config)")
    bt_parser.add_argument("--full-sample", action="store_true", dest="full_sample",
                           help="Run over the full available history instead of OOS-only "
                                "(paper-comparable mode)")

    id_parser = sub.add_parser("ideas", help="Output this month's target portfolio book + trades")
    id_parser.add_argument("--capital", type=float, default=None,
                           help="Account capital — adds the $ to buy per name (fractional shares)")
    id_parser.add_argument("--holdings", type=str, default=None,
                           help="Path to a JSON {ticker: dollar_value} of holdings to diff against")

    sub.add_parser("verify-book", help="Assert the live book == the backtest engine")

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
