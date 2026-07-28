"""RAAM's ranking methodology (Momentum + Volatility + Correlation + Trend ->
Total Rank), pointed at Cross-Sectional Momentum's actual universe (the S&P
1500) instead of RAAM's native 12-ETF 7Twelve universe, scored on EXACTLY the
same OOS dates CSM itself reports on (2023-01-27 -> 2026-07-17, derived from
CSM's own start_date=2015-01-01 + 70/30 walk-forward split).

Answers: "does RAAM (5 concentrated picks, monthly rebalance -- its own native
design, not CSM's 25-name/weekly setup) still work if you widen its opportunity
set from 11 ETFs to ~1500 stocks?" This is a diagnostic, not a pitch -- the
comparison table is printed however it comes out, including if RAAM-on-S&P1500
underperforms both RAAM-native and CSM.

Reuses, unmodified:
  * CSM's cached point-in-time S&P 1500 membership (csm.universe) -- read-only,
    not rebuilt.
  * RAAM's own indicator functions (absolute_momentum, volatility_model,
    atr_trend_breakout) -- already generic over an arbitrary ticker list.
  * RAAM's own simulate_drift -- already generic over an arbitrary target-weight
    panel and close panel.
  * RAAM's own cost model (5bps commission + 5bps half-spread) -- this is a test
    of RAAM's methodology, not an adoption of CSM's cost assumptions.

New pieces, all additive (see raam/ranking.py, raam/portfolio.py,
raam/indicators.py for the corresponding non-breaking signature changes):
  * avg_relative_correlation_at_dates -- the existing avg_relative_correlation
    is a per-PAIR Python loop over the full daily index, O(N^2) in ticker count;
    intractable at N~1000+. The new function computes the identical statistic
    (avg pairwise correlation vs every other eligible ticker) but ONLY at
    rebalance dates via pandas' vectorized .corr() -- ranking.compute_total_rank
    never reads Correlation anywhere else anyway. Cross-validated bit-for-bit
    (to float64 tolerance) against the brute-force version on RAAM's own
    11-ticker universe before being trusted here.
  * A batched, retried OHLC downloader (this file only) -- RAAM's own
    raam/data.py:_download_ohlc is a single unbatched yf.download() call, fine
    for 13 tickers, not safe for ~1500-2000. Modeled on csm/data.py:_yf_close's
    proven retry-on-missing-tickers pattern (that function already handles
    ~1510 tickers successfully -- its own cache is the proof), extended to keep
    O/H/L (yfinance already returns full OHLCV; CSM's version just discards
    O/H/L after extracting Close).
  * sp1500_eligible_on -- combines CSM's PIT membership (real index constituency
    on the date, no look-ahead into future adds) with RAAM's own "no synthetic
    data" philosophy (>=252 real trading days as of that date), mirroring
    universe.eligible_on's real-data-only pattern but PIT-aware.

Does NOT touch RAAM's own config.yaml, outputs/cache/, or the live 7Twelve
system in any way -- separate cache at outputs/cache_sp1500/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import yfinance as yf

_HERE = Path(__file__).resolve().parent
_CSM_DIR = _HERE.parent / "Cross-Sectional Momentum"

sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_CSM_DIR))

from raam import backtest as bt_mod
from raam import benchmarks as bench_mod
from raam import data as data_mod
from raam import indicators as ind_mod
from raam import portfolio as port_mod
from raam import ranking as rank_mod
from raam.costs import turnover_stats
from raam.validation import compute_metrics

from csm import universe as csm_univ_mod

# CSM's own OOS window, derived this session from its cached price panel
# (start_date=2015-01-01, 70/30 split -> IS ends 2023-01-26). Fixed here rather
# than re-derived every run so all three legs are guaranteed to share the exact
# same dates even if CSM's cache is later refreshed.
OOS_START = pd.Timestamp("2023-01-27")

PIT_HISTORY_START = "2010-01-01"   # matches csm/universe.py's _PIT_HISTORY_START
SP1500_CACHE_DIR = _HERE / "outputs" / "cache_sp1500"

FIELDS = ["Open", "High", "Low", "Close"]


def load_config(path: Path = _HERE / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ─────────────────────────────────────────────────────────────────────────────
#  Batched, retried OHLC download for a ~1500-2000-ticker universe
# ─────────────────────────────────────────────────────────────────────────────

def _download_ohlc_batch(tickers: list[str], start: str, end: str,
                         tries: int = 2) -> tuple[pd.DataFrame, list[str]]:
    """One yf.download() call (+ retries on tickers that returned nothing).
    Modeled on csm/data.py:_yf_close's retry loop, extended to keep O/H/L/C."""
    out = {f: pd.DataFrame() for f in FIELDS}
    remaining = list(tickers)
    for attempt in range(tries):
        if not remaining:
            break
        raw = yf.download(remaining, start=start, end=end, auto_adjust=True,
                          progress=False, threads=True, timeout=120)
        if raw is None or len(raw) == 0:
            continue
        if isinstance(raw.columns, pd.MultiIndex):
            top = set(raw.columns.get_level_values(0))
            for f in FIELDS:
                if f not in top:
                    continue
                col = raw[f]
                out[f] = col.combine_first(out[f]) if not out[f].empty else col
        else:
            for f in FIELDS:
                if f not in raw.columns:
                    continue
                s = raw[[f]].rename(columns={f: remaining[0]})
                out[f] = s.combine_first(out[f]) if not out[f].empty else s
        got = (set(out["Close"].columns[out["Close"].notna().any()])
              if not out["Close"].empty else set())
        remaining = [t for t in remaining if t not in got]
    panel = pd.concat(out, axis=1)
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index(), remaining


def download_ohlc_batched(tickers: list[str], start: str, end: str,
                          batch_size: int = 300, tries: int = 2) -> pd.DataFrame:
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    panels, all_failed = [], []
    for bi, batch in enumerate(batches, 1):
        print(f"  Batch {bi}/{len(batches)}: {len(batch)} tickers …", flush=True)
        panel, failed = _download_ohlc_batch(batch, start, end, tries=tries)
        panels.append(panel)
        all_failed.extend(failed)
    full = pd.concat(panels, axis=1).sort_index()
    if all_failed:
        preview = ", ".join(all_failed[:10]) + (" …" if len(all_failed) > 10 else "")
        print(f"  {len(all_failed)} tickers never returned data (delisted/renamed/"
              f"bad ticker) — dropped: {preview}")
    return full


def load_sp1500_ohlc_panel(tickers: list[str], start: str, end: str,
                           cache_dir: Path, refresh: str = "auto") -> pd.DataFrame:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "ohlc.parquet"
    target_end = pd.Timestamp(end)

    if refresh == "auto" and cache_path.exists():
        cached = pd.read_parquet(cache_path)
        cached = data_mod._drop_intraday_row(cached)
        cached = data_mod._drop_partial_tail(cached)
        have = set(cached["Close"].columns) if not cached.empty else set()
        missing = [t for t in tickers if t not in have]
        panel_last = cached.index[-1] if len(cached) else pd.Timestamp("1900-01-01")
        if not missing and panel_last >= target_end - pd.tseries.offsets.BDay(5):
            print(f"Loaded S&P1500 OHLC cache: {len(have)} tickers x {len(cached)} days "
                  f"(history from {cached.index.min().date()}, fresh through {panel_last.date()})")
            return cached.loc[start:end]
        print(f"S&P1500 OHLC cache stale/incomplete ({len(missing)} tickers missing, "
              f"latest {panel_last.date()}) — full re-download …")

    print(f"Downloading OHLC for {len(tickers)} tickers, {start} -> {end} (batched) …")
    panel = download_ohlc_batched(tickers, start, end)
    panel = data_mod._drop_intraday_row(panel)
    panel = data_mod._drop_partial_tail(panel)
    panel.to_parquet(cache_path)
    n_tk = panel["Close"].shape[1] if not panel.empty else 0
    print(f"S&P1500 OHLC cache written: {n_tk} tickers x {len(panel)} days")
    return panel.loc[start:end]


# ─────────────────────────────────────────────────────────────────────────────
#  PIT-aware eligibility: real S&P1500 constituency + real trading history
# ─────────────────────────────────────────────────────────────────────────────

def make_sp1500_eligible_fn(pit_df: pd.DataFrame):
    """Returns eligible_fn(close, date, min_history_days) -> list[str], the
    same signature as universe.eligible_on, so it's a drop-in for
    ranking.compute_total_rank's eligible_fn parameter.

    Eligible = a real S&P1500 constituent on `date` (per CSM's PIT membership
    -- no look-ahead into future index adds) AND has >=min_history_days real
    trading closes as of `date` (RAAM's own real-data-only philosophy, same
    threshold used for the native 7Twelve universe).
    """
    def eligible_fn(close: pd.DataFrame, date: pd.Timestamp,
                    min_history_days: int = 252) -> list[str]:
        if date not in close.index:
            return []
        members = csm_univ_mod.get_members_on(pit_df, date)
        hist = close.loc[:date]
        out = []
        for t in members:
            if t not in hist.columns:
                continue
            col = hist[t]
            if pd.isna(col.iloc[-1]):
                continue
            if int(col.notna().sum()) >= min_history_days:
                out.append(t)
        return out
    return eligible_fn


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg = load_config()
    min_hist = int(cfg.get("universe", {}).get("min_history_days", 252))
    n_select = int(cfg.get("ranking", {}).get("n_select", 5))
    end = pd.Timestamp.today().strftime("%Y-%m-%d")

    print("─── Loading CSM's cached point-in-time S&P 1500 membership (read-only) ───")
    pit_df = csm_univ_mod.build_pit_membership(_CSM_DIR / "outputs" / "cache",
                                               start=PIT_HISTORY_START)
    sp1500_tickers = sorted(csm_univ_mod.get_all_ever_members(pit_df))
    print(f"  {len(sp1500_tickers)} tickers ever in the S&P 1500 PIT history "
          f"since {PIT_HISTORY_START}")

    fetch_tickers = sorted(set(sp1500_tickers) | {"SHY", "SPY"})
    ohlc = load_sp1500_ohlc_panel(fetch_tickers, PIT_HISTORY_START, end, SP1500_CACHE_DIR)
    close = ohlc["Close"]

    print("\n─── Computing indicators (M, V, T generic; C via the fast rebal-date-only path) ───")
    icfg = cfg.get("indicators", {})
    mom_window  = ind_mod.months_to_days(float(icfg.get("momentum_months", 4)))
    corr_window = ind_mod.months_to_days(float(icfg.get("correlation_months", 4)))
    vcfg = icfg.get("volatility", {})
    tcfg = icfg.get("trend", {})

    tickers_only = [t for t in sp1500_tickers if t in close.columns]

    M = ind_mod.absolute_momentum(close[tickers_only], mom_window)
    vol_raw = ind_mod.volatility_model(
        ohlc, tickers_only,
        lam=float(vcfg.get("lambda", 0.943)), method=str(vcfg.get("method", "garman_klass")))
    V = ind_mod.smoothed_volatility(vol_raw, smooth_days=int(vcfg.get("smooth_days", 10)))
    T = ind_mod.atr_trend_breakout(
        ohlc, tickers_only,
        atr_period=int(tcfg.get("atr_period", 42)),
        upper_lookback=int(tcfg.get("upper_lookback", 63)),
        lower_lookback=int(tcfg.get("lower_lookback", 105)))
    ret = close[tickers_only].ffill(limit=3).pct_change()
    rebal_dates = rank_mod.month_end_dates(close.index)
    C = ind_mod.avg_relative_correlation_at_dates(ret, corr_window, rebal_dates)

    indicators = {"M": M, "V": V, "C": C, "T": T}

    print("\n─── Ranking: Total Rank -> top-5 selection, monthly (RAAM-native cadence) ───")
    eligible_fn = make_sp1500_eligible_fn(pit_df)
    total_rank = rank_mod.compute_total_rank(indicators, close, cfg,
                                             tickers=tickers_only, eligible_fn=eligible_fn)
    picks = rank_mod.select_book(total_rank, n_select=n_select)
    pos = port_mod.build_positions(picks, M, close, cfg,
                                   tickers=tickers_only, cash_ticker="SHY")

    print(f"─── Scoring on the shared OOS window: {OOS_START.date()} -> {close.index.max().date()} ───")
    res_sp1500 = bt_mod.simulate_drift(pos, rebal_dates, close, cfg, OOS_START,
                                       label="RAAM (S&P1500, 5 names)")
    m_sp1500 = compute_metrics(res_sp1500.net_ret, res_sp1500.bench_ret)
    to_sp1500 = turnover_stats(res_sp1500.exec_pos)

    # ── RAAM-native (7Twelve), recomputed fresh on the identical window ──────
    raam_cfg = cfg
    raam_tickers = None  # defaults inside backtest.run_raam/compute_total_rank
    import raam.universe as univ_mod
    native_panel = data_mod.load_ohlc_panel(
        univ_mod.ALL_TICKERS + [univ_mod.SPY], start="auto", end=end,
        cache_dir=_HERE / raam_cfg["data"]["cache_dir"])
    native_close = data_mod.close_panel(native_panel)
    res_native = bt_mod.run_raam(native_panel, native_close, raam_cfg, OOS_START)
    m_native = compute_metrics(res_native.net_ret, res_native.bench_ret)

    # ── SPY buy-hold, same window ─────────────────────────────────────────────
    spy_ret = bench_mod.spy_buy_hold_returns(native_close).loc[OOS_START:]
    m_spy = compute_metrics(spy_ret, spy_ret)

    # ── CSM's own most recent backtest report (read-only, not re-derived) ────
    csm_reports = sorted((_CSM_DIR / "outputs").glob("backtest_*.json"))
    csm_line = None
    if csm_reports:
        import json
        with open(csm_reports[-1]) as f:
            csm_json = json.load(f)
        prim = csm_json.get("metrics", {}).get("primary (OOS)")
        if prim:
            csm_line = (prim["sharpe"], prim["cagr"], prim["max_dd"], prim.get("n_days"))
            # Sanity check the window actually matches what we scored above.
            expected_n = len(close.loc[OOS_START:])
            if prim.get("n_days") and abs(prim["n_days"] - expected_n) > 5:
                print(f"  WARNING: CSM's report ({csm_reports[-1].name}) covers "
                      f"n_days={prim['n_days']}, but the S&P1500/RAAM-native legs "
                      f"here cover {expected_n} days over {OOS_START.date()}->"
                      f"{close.index.max().date()} — CSM's cache may have moved; "
                      f"re-run CSM's own backtest for a strictly matched window.")

    print(f"\n{'=' * 80}\nRAAM vs CSM — same OOS dates ({OOS_START.date()} -> {close.index.max().date()})\n{'=' * 80}")
    print(f"  {'Strategy':38} {'Sharpe':>8} {'CAGR':>8} {'MaxDD':>8}")
    print("  " + "-" * 66)
    if csm_line:
        s, c, dd, _ = csm_line
        print(f"  {'CSM (primary, OOS)':38} {s:>8.3f} {c:>+8.1%} {dd:>+8.1%}")
    else:
        print(f"  {'CSM (primary, OOS)':38} {'no cached report found — run csmom.py backtest':>}")
    print(f"  {'RAAM (native, 7Twelve, 5 names)':38} {m_native['sharpe']:>8.3f} "
          f"{m_native['cagr']:>+8.1%} {m_native['max_dd']:>+8.1%}")
    print(f"  {'RAAM (S&P1500, 5 names)':38} {m_sp1500['sharpe']:>8.3f} "
          f"{m_sp1500['cagr']:>+8.1%} {m_sp1500['max_dd']:>+8.1%}")
    print(f"  {'SPY buy-and-hold':38} {m_spy['sharpe']:>8.3f} "
          f"{m_spy['cagr']:>+8.1%} {m_spy['max_dd']:>+8.1%}")

    print(f"\n  RAAM-on-S&P1500 turnover: {to_sp1500['annual_turnover']:.1f}x annualized "
          f"({to_sp1500['rebal_dates']} rebalances with turnover)")
    print( "  Caveats: (1) 5 picks drawn from ~1000+ eligible names monthly can churn far "
           "more\n           than RAAM-native's same ~11 tickers reordering slots — see "
           "turnover above.\n"
           "       (2) Average Relative Correlation among ~1000+ mostly-equity names "
           "measures\n           market-beta concentration, not genuine cross-asset-class "
           "diversification\n           (unlike the native 7Twelve run's 11 different asset "
           "classes) — same formula,\n           different economic meaning.\n"
           "       (3) No weight refitting — wM=wV=wC equal, same no-fitting principle as "
           "the\n           native 7Twelve system.")
    print("=" * 80)


if __name__ == "__main__":
    main()
