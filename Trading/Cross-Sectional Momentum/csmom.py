#!/usr/bin/env python3
"""csmom — Cross-Sectional Residual Momentum Trade-Idea Engine.

Subcommands:
  fetch      Build (or refresh) the point-in-time S&P 1500 membership table
             and download price history.
  backtest   Run a walk-forward backtest with DSR + PBO + MCPT validation.
  ideas      Score today's universe and output ranked long ideas with
             triple-barrier stop/target levels.

Usage:
  python csmom.py                     # interactive menu
  python csmom.py fetch
  python csmom.py backtest [--meta] [--mcpt N] [--oos-frac 0.30]
  python csmom.py ideas    [--top N]

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


# ─────────────────────────────────────────────────────────────────────────────
#  fetch
# ─────────────────────────────────────────────────────────────────────────────

def cmd_fetch(cfg: dict) -> None:
    """Build PIT membership + download price panel."""
    cache_dir = _HERE / cfg["data"]["cache_dir"]

    print("─── Point-in-time S&P 1500 membership ──────────────────────────────")
    pit_df = univ_mod.build_pit_membership(cache_dir, start=cfg["data"]["start_date"])
    ever   = univ_mod.get_all_ever_members(pit_df)
    today  = univ_mod.get_members_on(pit_df, pd.Timestamp.today())
    print(f"  Ever in S&P 1500: {len(ever)} unique tickers")
    print(f"  In index today  : {len(today)} tickers")

    print("\n─── Price panel download ─────────────────────────────────────────────")
    prices = data_mod.load_price_panel(
        tickers  = ever,
        start    = cfg["data"]["start_date"],
        end      = cfg["data"]["end_date"],
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

    prices = data_mod.load_price_panel(
        tickers  = ever,
        start    = cfg["data"]["start_date"],
        end      = cfg["data"]["end_date"],
        cache_dir= cache_dir,
    )

    oos_frac = float(getattr(args, "oos_frac", 0.30))
    meta_on  = bool(getattr(args, "meta", False))
    n_perm   = int(getattr(args, "mcpt",  0))   # 0 = skip MCPT (fast mode)

    print(f"\n─── Walk-forward backtest ({int((1-oos_frac)*100)}% IS / {int(oos_frac*100)}% OOS) ──")
    primary_res, meta_res = bt_mod.walk_forward(
        prices, cfg, pit_df=pit_df, oos_frac=oos_frac, meta_enabled=meta_on,
        out_dir=out_dir if meta_on else None,
    )

    results = {"primary (OOS)": primary_res}
    if meta_res is not None:
        results["meta-labeled (OOS)"] = meta_res

    # ── Validation suite ─────────────────────────────────────────────────────
    print("\n─── DSR (Deflated Sharpe) ───────────────────────────────────────────")
    observed_sh = val_mod.compute_metrics(primary_res.net_ret, primary_res.bench_ret)["sharpe"]
    dsr_result  = val_mod.run_dsr(primary_res.net_ret, grid_sharpes=[observed_sh])

    pbo_result = None
    if meta_res is not None:
        print("\n─── PBO (Probability of Backtest Overfitting) ───────────────────────")
        ret_matrix = pd.concat([primary_res.net_ret.rename("primary"),
                                meta_res.net_ret.rename("meta")], axis=1).dropna()
        pbo_result = val_mod.run_pbo(ret_matrix)

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
    rep_mod.write_backtest_report(results, dsr_result, pbo_result, mcpt_result, out_dir)


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

    prices = data_mod.load_price_panel(
        tickers  = ever,
        start    = cfg["data"]["start_date"],
        end      = cfg["data"]["end_date"],
        cache_dir= cache_dir,
    )

    today  = prices.index[-1]
    stocks = prices.drop(columns=["SPY"], errors="ignore")

    # Current PIT members
    if pit_df is not None:
        members = univ_mod.get_members_on(pit_df, today)
        valid_cols = [c for c in stocks.columns if c in members]
    else:
        valid_cols = list(stocks.columns)

    print(f"\nScoring {len(valid_cols)} stocks as of {today.date()} …")

    signals = sig_mod.primary_signal(prices, cfg)
    today_sig = signals.loc[today].reindex(valid_cols).dropna()
    if today_sig.empty:
        print("ERROR: no signal values for today. Check data freshness.")
        return

    # Regime check
    reg_cfg   = cfg.get("regime_filter", {})
    regime_ok = sig_mod.spy_regime(
        prices,
        ma_days = int(reg_cfg.get("spy_ma_days", 200)),
        vol_cap = float(reg_cfg.get("vol_cap", 0.25)),
    )
    in_regime = bool(regime_ok.get(today, True))
    if not in_regime:
        print("\nWARNING: Market regime filter is OFF (SPY below 200-dma + high vol).")
        print("  Strategy would go to cash — no new longs recommended.\n")

    # Rank and pick top-quintile
    quantile  = float(cfg.get("signal", {}).get("quantile", 0.80))
    threshold = today_sig.quantile(quantile)
    longs     = today_sig[today_sig >= threshold].sort_values(ascending=False)

    # ── Meta-model scoring ────────────────────────────────────────────────────
    from csm.model import load_meta_model, score_current_candidates
    meta_bundle = load_meta_model(out_dir)
    ml_cfg  = cfg.get("meta_labeling", {})
    min_prob = float(ml_cfg.get("min_prob_take", 0.55))

    if meta_bundle is not None:
        print(f"\n[Meta-model] Loaded  IS-end={meta_bundle['is_end']}  "
              f"trained={meta_bundle['trained_at'][:10]}")
        prob_take_ser = score_current_candidates(
            tickers       = list(longs.index),
            prices        = prices,
            clf           = meta_bundle["clf"],
            feature_names = meta_bundle["feature_names"],
            cfg           = cfg,
            as_of         = today,
        )
        passing = prob_take_ser[prob_take_ser >= min_prob]
        if passing.empty:
            print(f"  NOTE: 0/{len(longs)} candidates cleared P(take) >= {min_prob:.0%}. "
                  "Showing all with real scores (no filter applied).")
        else:
            sorted_idx = prob_take_ser.reindex(passing.index).sort_values(ascending=False).index
            longs = longs.reindex(sorted_idx).dropna()
            print(f"  {len(longs)} candidates cleared P(take) >= {min_prob:.0%}; "
                  "sorted by P(take) descending.")
    else:
        prob_take_ser = None
        print("\n[Meta-model] Not found — run `backtest --meta` first for real P(take) scores.")
        print("  Showing primary signal ranking with placeholder P(take) = 100%.")

    # Triple-barrier stop/target levels using idio-vol
    from csm.afml import get_daily_vol
    pt_m    = float(ml_cfg.get("pt_multiple",   1.5))
    sl_m    = float(ml_cfg.get("sl_multiple",   1.0))
    bw_days = int(ml_cfg.get("barrier_window",  42))

    ideas = []
    rank  = 1
    for ticker, score in longs.head(top_n).items():
        close_ser = stocks[ticker].dropna()
        if len(close_ser) < 60:
            continue
        entry  = float(close_ser.iloc[-1])
        idio_v = float(get_daily_vol(close_ser).iloc[-1]) if len(close_ser) > 50 else 0.01
        stop   = round(entry * (1.0 - sl_m * idio_v * np.sqrt(bw_days)), 2)
        target = round(entry * (1.0 + pt_m * idio_v * np.sqrt(bw_days)), 2)
        if prob_take_ser is not None and ticker in prob_take_ser.index:
            prob = float(prob_take_ser[ticker])
        else:
            prob = 1.0
        ideas.append({
            "rank":         rank,
            "ticker":       ticker,
            "signal_score": round(float(score), 4),
            "prob_take":    round(prob, 4),
            "entry_price":  round(entry, 2),
            "stop":         stop,
            "target":       target,
            "horizon_days": bw_days,
            "regime_ok":    in_regime,
            "as_of":        str(today.date()),
        })
        rank += 1

    if not ideas:
        print("No candidates meet the signal threshold today.")
        return

    rep_mod.write_ideas_report(ideas, out_dir)


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
        meta     = False
        mcpt     = 0
        top      = cfg.get("output", {}).get("top_n_ideas", 25)

    if choice in ("1", "fetch"):
        cmd_fetch(cfg)
    elif choice in ("2", "backtest"):
        meta = input("  Enable meta-labeling? [y/N] ").strip().lower() == "y"
        _Args.meta = meta
        n = input("  MCPT permutations? [0 = skip, 200 = fast, 1000 = rigorous] ").strip()
        _Args.mcpt = int(n) if n.isdigit() else 0
        cmd_backtest(cfg, _Args())
    elif choice in ("3", "ideas"):
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
    bt_parser.add_argument("--meta",     action="store_true",
                           help="Enable meta-labeling (takes longer)")
    bt_parser.add_argument("--mcpt",     type=int, default=0,
                           help="MCPT permutations (0 = skip, 200 = fast, 1000 = rigorous)")
    bt_parser.add_argument("--oos-frac", type=float, default=0.30, dest="oos_frac",
                           help="Fraction of history held out for OOS (default 0.30)")

    id_parser = sub.add_parser("ideas", help="Generate today's ranked trade ideas")
    id_parser.add_argument("--top", type=int, default=25,
                           help="Number of ideas to output (default 25)")

    args = parser.parse_args()

    if args.cmd == "fetch":
        cmd_fetch(cfg)
    elif args.cmd == "backtest":
        cmd_backtest(cfg, args)
    elif args.cmd == "ideas":
        cmd_ideas(cfg, args)
    else:
        _interactive_menu(cfg)


if __name__ == "__main__":
    main()
