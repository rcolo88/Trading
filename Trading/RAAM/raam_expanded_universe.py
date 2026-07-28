"""Does RAAM's Sharpe improve if the opportunity set widens from 11 ETFs to a
still-genuinely-diversified ~32, without losing the cross-asset-class character
that makes the Average Relative Correlation component mean anything?

Motivated by the S&P1500 experiment (raam_sp1500.py) failing badly (Sharpe
0.195) specifically because correlation among ~1000+ mostly-equity names
stopped measuring diversification and degenerated into market-beta
concentration. This tests whether a MODEST expansion -- more equity factor
tilts, more regions, more commodities, more bond types, still real asset-class
diversity, not just more stocks -- avoids that failure mode.

This is ONE exploratory structural variant, not a multi-trial search -- no
DSR/PBO here (that machinery needs a real trial distribution to be meaningful,
not one point). Reported plainly whichever way it comes out, consistent with
every other result in this codebase.

Reuses raam/ranking.py:compute_total_rank and raam/portfolio.py:build_positions
via the tickers=/eligible_fn=/cash_ticker= parameters added for the S&P1500
experiment -- no further changes to the validated raam/ package needed here.
Does not touch RAAM's own config.yaml, outputs/cache/, or the live 7Twelve
system -- separate cache at outputs/cache_expanded/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from raam import backtest as bt_mod
from raam import data as data_mod
from raam import indicators as ind_mod
from raam import portfolio as port_mod
from raam import ranking as rank_mod
from raam import universe as univ_mod
from raam.costs import turnover_stats
from raam.validation import compute_metrics

EXPANDED_CACHE_DIR = _HERE / "outputs" / "cache_expanded"

# Additive to RAAM's existing 11 (VV, IJH, IJR, EFA, EEM, RWR, DBC, VAW, AGG,
# TIP, IGOV) -- widens the pool while staying deliberately cross-asset, not
# just more equities. (ticker, sleeve label)
NEW_ROSTER: list[tuple[str, str]] = [
    ("MTUM", "US EQUITY FACTOR - MOMENTUM"),
    ("QUAL", "US EQUITY FACTOR - QUALITY"),
    ("USMV", "US EQUITY FACTOR - MIN VOL"),
    ("VYM",  "US EQUITY FACTOR - HIGH DIVIDEND"),
    ("VGK",  "INTERNATIONAL EQUITY - EUROPE"),
    ("EWJ",  "INTERNATIONAL EQUITY - JAPAN"),
    ("MCHI", "INTERNATIONAL EQUITY - CHINA"),
    ("ILF",  "INTERNATIONAL EQUITY - LATIN AMERICA"),
    ("SCZ",  "INTERNATIONAL EQUITY - EAFE SMALL-CAP"),
    ("GLD",  "COMMODITIES - GOLD"),
    ("USO",  "COMMODITIES - OIL"),
    ("DBA",  "COMMODITIES - AGRICULTURE"),
    ("TLT",  "BONDS - LONG TREASURY"),
    ("LQD",  "BONDS - INVESTMENT GRADE CORPORATE"),
    ("HYG",  "BONDS - HIGH YIELD CORPORATE"),
    ("EMB",  "BONDS - EM SOVEREIGN"),
    ("MUB",  "BONDS - MUNICIPAL"),
    ("RWX",  "REAL ESTATE - INTERNATIONAL"),
    ("PFF",  "ALTERNATIVES - PREFERRED STOCK"),
    ("IGF",  "ALTERNATIVES - GLOBAL INFRASTRUCTURE"),
]


def load_config(path: Path = _HERE / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def make_expanded_eligible_fn(tickers: list[str]):
    """Same real-data availability-mask pattern as universe.eligible_on,
    generalized over an arbitrary ticker list -- an ETF enters the pool only
    once it has >=min_history_days REAL trading closes, no synthetic/
    interpolated backfill, mirroring the native 7Twelve system's philosophy."""
    def eligible_fn(close: pd.DataFrame, date: pd.Timestamp,
                    min_history_days: int = 252) -> list[str]:
        if date not in close.index:
            return []
        hist = close.loc[:date]
        out = []
        for t in tickers:
            if t not in hist.columns:
                continue
            col = hist[t]
            if pd.isna(col.iloc[-1]):
                continue
            if int(col.notna().sum()) >= min_history_days:
                out.append(t)
        return out
    return eligible_fn


def build_expanded_positions(ohlc, close, cfg, tickers, eligible_fn):
    icfg = cfg.get("indicators", {})
    mom_window  = ind_mod.months_to_days(float(icfg.get("momentum_months", 4)))
    corr_window = ind_mod.months_to_days(float(icfg.get("correlation_months", 4)))
    vcfg = icfg.get("volatility", {})
    tcfg = icfg.get("trend", {})

    M = ind_mod.absolute_momentum(close[tickers], mom_window)
    vol_raw = ind_mod.volatility_model(
        ohlc, tickers,
        lam=float(vcfg.get("lambda", 0.943)), method=str(vcfg.get("method", "garman_klass")))
    V = ind_mod.smoothed_volatility(vol_raw, smooth_days=int(vcfg.get("smooth_days", 10)))
    T = ind_mod.atr_trend_breakout(
        ohlc, tickers,
        atr_period=int(tcfg.get("atr_period", 42)),
        upper_lookback=int(tcfg.get("upper_lookback", 63)),
        lower_lookback=int(tcfg.get("lower_lookback", 105)))
    # N~=32 -> ~500 pairs: the ORIGINAL brute-force daily correlation is fine,
    # no need for the fast rebal-date-only version built for N~1500.
    ret = close[tickers].ffill(limit=3).pct_change()
    C = ind_mod.avg_relative_correlation(ret, corr_window)

    indicators = {"M": M, "V": V, "C": C, "T": T}
    n_select = int(cfg.get("ranking", {}).get("n_select", 5))
    total_rank = rank_mod.compute_total_rank(indicators, close, cfg,
                                             tickers=tickers, eligible_fn=eligible_fn)
    picks = rank_mod.select_book(total_rank, n_select=n_select)
    pos = port_mod.build_positions(picks, M, close, cfg, tickers=tickers, cash_ticker="SHY")
    return pos


def main() -> None:
    cfg = load_config()
    end = pd.Timestamp.today().strftime("%Y-%m-%d")

    base_tickers = list(univ_mod.RANKABLE)
    new_tickers  = [t for t, _ in NEW_ROSTER]
    expanded_tickers = base_tickers + new_tickers
    fetch_tickers = expanded_tickers + [univ_mod.CASH_TICKER, univ_mod.SPY]

    print(f"─── Expanded universe: {len(base_tickers)} native + {len(new_tickers)} new "
          f"= {len(expanded_tickers)} rankable + SHY cash ───")
    ohlc = data_mod.load_ohlc_panel(fetch_tickers, start="auto", end=end,
                                    cache_dir=EXPANDED_CACHE_DIR)
    close = data_mod.close_panel(ohlc)

    present = [t for t in expanded_tickers if t in close.columns]
    missing = [t for t in expanded_tickers if t not in close.columns]
    if missing:
        print(f"  WARNING: {len(missing)} tickers had no data at all — dropped: {missing}")
    print("  First real close per NEW ticker (defines when it enters the ranking pool):")
    for t, sleeve in NEW_ROSTER:
        if t not in close.columns:
            continue
        s = close[t].dropna()
        first = str(s.index.min().date()) if len(s) else "N/A"
        print(f"    {t:<6} {first:<12} {sleeve}")

    eligible_fn = make_expanded_eligible_fn(present)
    min_hist = int(cfg.get("universe", {}).get("min_history_days", 252))

    print("\n─── Computing indicators + Total Rank across the expanded universe ───")
    pos = build_expanded_positions(ohlc, close, cfg, present, eligible_fn)
    rebal_dates = rank_mod.month_end_dates(close.index)

    # ── Primary test: honest walk-forward OOS, same 70/30 split logic as
    #    raam.backtest.walk_forward, computed on this universe's own full history ──
    oos_frac = float(cfg.get("validation", {}).get("walk_forward_oos_frac", 0.30))
    index = close.index
    n = len(index)
    is_end = index[int(n * (1 - oos_frac)) - 1]
    oos_start = is_end + pd.Timedelta(days=1)

    res_oos = bt_mod.simulate_drift(pos, rebal_dates, close, cfg, oos_start,
                                    label="RAAM (expanded universe)")
    m_oos = compute_metrics(res_oos.net_ret, res_oos.bench_ret)
    to_oos = turnover_stats(res_oos.exec_pos)

    # ── Full-sample, for continuity with the paper-comparison convention ──
    res_full = bt_mod.simulate_drift(pos, rebal_dates, close, cfg, index[0],
                                     label="RAAM (expanded universe, full-sample)")
    m_full = compute_metrics(res_full.net_ret, res_full.bench_ret)

    # ── RAAM-native, recomputed fresh on the identical OOS split for this run ──
    native_ohlc = data_mod.load_ohlc_panel(
        univ_mod.ALL_TICKERS + [univ_mod.SPY], start="auto", end=end,
        cache_dir=_HERE / cfg["data"]["cache_dir"])
    native_close = data_mod.close_panel(native_ohlc)
    res_native_oos = bt_mod.run_raam(native_ohlc, native_close, cfg, oos_start)
    m_native_oos = compute_metrics(res_native_oos.net_ret, res_native_oos.bench_ret)

    print(f"\n{'=' * 80}")
    print(f"Expanded universe ({len(present)} names) vs RAAM-native (11 names)")
    print(f"OOS window: {oos_start.date()} -> {close.index.max().date()}")
    print(f"{'=' * 80}")
    print(f"  {'Strategy':38} {'Sharpe':>8} {'CAGR':>8} {'MaxDD':>8}")
    print("  " + "-" * 66)
    print(f"  {'RAAM-native (11 ETFs), OOS':38} {m_native_oos['sharpe']:>8.3f} "
          f"{m_native_oos['cagr']:>+8.1%} {m_native_oos['max_dd']:>+8.1%}")
    print(f"  {'RAAM-expanded (' + str(len(present)) + ' ETFs), OOS':38} {m_oos['sharpe']:>8.3f} "
          f"{m_oos['cagr']:>+8.1%} {m_oos['max_dd']:>+8.1%}")
    print(f"  {'RAAM-expanded, full-sample':38} {m_full['sharpe']:>8.3f} "
          f"{m_full['cagr']:>+8.1%} {m_full['max_dd']:>+8.1%}")
    print(f"\n  Expanded-universe OOS turnover: {to_oos['annual_turnover']:.1f}x annualized "
          f"({to_oos['rebal_dates']} rebalances with turnover)")
    print("\n  Caveat: this is ONE exploratory structural variant, not a multi-trial search —\n"
          "  no DSR/PBO here (that machinery needs a real trial distribution to be meaningful,\n"
          "  not a single point). If this result looks promising, proper DSR/PBO/MCPT treatment\n"
          "  would be the honest next step before treating it as validated, exactly like every\n"
          "  other result in this codebase — not an immediate conclusion from one run.")
    print("=" * 80)


if __name__ == "__main__":
    main()
