"""Price panel data layer: yfinance download + parquet cache.

All price data is split/dividend-adjusted (auto_adjust=True).
The cache stores a single Close-price parquet keyed by the union of all
tickers requested.

Refresh strategy (see load_price_panel):
  auto — serve the cache when fresh; tail-refresh when stale.
  tail — incremental: pull only the last ~10 trading days for all tickers and
         splice onto the cache; fully re-download ONLY tickers whose
         adjusted-price basis shifted (dividend/split since the last pull) or
         that are new to the cache. ~1000× less data than a full pull, so it is
         fast and rarely rate-limited.
  full — re-download everything (the `fetch` command).

A partially-failed bulk download (rate limiting, DNS outage) leaves the newest
row populated for only a subset of tickers; such trailing rows are DROPPED
before caching so consumers always see complete closes — better to hold
yesterday's full cross-section than today's fragment.
"""
from __future__ import annotations

import warnings
from datetime import time as _dtime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")


def _yfmt(ticker: str) -> str:
    """Normalise ticker to yfinance format (dots → dashes)."""
    return ticker.strip().replace(".", "-").upper()


# The cache always stores data from this far back so the signal has warmup headroom.
# Changing start_date in config.yaml restricts the *analysis* window, not the download.
_CACHE_HISTORY_START = "2010-01-01"

# 2026-08-05 blend-return-research project: the blend (csm/blend.py) trades
# ONLY the non-stock ETF/index set (SIGNAL_EXCLUDE, below) and never scores
# individual stocks, so that set can carry a much longer history without
# paying to re-download 1700+ stock tickers back to 1999 (most don't have
# that history anyway, and the equity engine's own PIT universe starts 2010).
# The stock universe stays on _CACHE_HISTORY_START; SIGNAL_EXCLUDE tickers use
# this floor instead, giving the blend pre-GFC/dotcom coverage for a genuine
# out-of-sample holdout. yfinance simply returns each ticker's real inception
# forward when requested from before it existed — no assumed dates.
_LONG_HISTORY_START = "1999-01-01"

# ── Panel column roles ────────────────────────────────────────────────────────
# AUX_COLS are index series carried in the panel for regime overlays (VIX term
# structure); they are never tradeable and never part of the stock cross-section.
# DEFENSIVE_TICKER is a tradeable ETF sleeve (regime_filter.defensive) held by
# the engine like a position but excluded from signal computation, so the
# cross-sectional ranking can never select it.
AUX_COLS         = ["^VIX", "^VIX3M"]
DEFENSIVE_TICKER = "IEF"

# 2026-08-04 regime-robustness project (see memory csm-regime-robustness-project):
# REGIME_DETECT_COLS are a 7-asset-class cross-section (SPY + these 4, plus
# TLT/GLD already covered by DEFENSIVE_ROSTER below) used ONLY to compute the
# turbulence/absorption-ratio/slow-bleed regime signals (csm/regime_state.py,
# csm/slow_bleed.py) — never tradeable, never signal-scored, same role as
# AUX_COLS. DEFENSIVE_ROSTER is the multi-asset rotation's HOLDABLE candidate
# set (csm/multiasset.py, regime_filter.defensive: rotation) — tradeable like
# DEFENSIVE_TICKER but excluded from equity signal scoring. ROTATION_CASH_TICKER
# is the rotation's own cash fallback when no candidate has positive momentum.
REGIME_DETECT_COLS   = ["EFA", "EEM", "AGG", "RWR"]
DEFENSIVE_ROSTER     = ["IEF", "TLT", "GLD", "DBC", "DBMF", "BTAL"]
ROTATION_CASH_TICKER = "SHY"

# 2026-08-05 3-way blend project (see memory csm-market-neutral-macro-tests):
# MACRO_SECTOR_COLS (11 GICS sector SPDRs) + MACRO_ASSET_COLS (TIP, LQD — the
# two tickers csm/macro_regime.py needs beyond what REGIME_DETECT_COLS/
# DEFENSIVE_ROSTER already cover: EEM/DBC/GLD/TLT/IEF) drive the standalone
# macro regime tilt sleeve (csm/macro_regime.py, csm/blend.py). Pure
# asset-allocation tickers — never tradeable by the equity cross-sectional
# ranker, same role as REGIME_DETECT_COLS.
MACRO_SECTOR_COLS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
                     "XLP", "XLRE", "XLU", "XLV", "XLY"]
MACRO_ASSET_COLS  = ["TIP", "LQD"]

# 2026-08-05: the blend's growth sleeve holds this ETF (config `blend.growth_ticker`,
# default here) — tradeable like DEFENSIVE_TICKER, excluded from equity signal
# scoring. Verified via yfinance + State Street directly before adopting: real
# daily volume back to 2010 (not a backfill artifact), 0.02% expense ratio,
# $153B AUM, tracks the S&P 500 identically to SPY. SPY itself stays a
# permanent, separate download regardless of this — it is always the
# BENCHMARK ("SPY buy-and-hold" row) independent of what the growth sleeve
# actually holds, so the two roles never collide even when they're the same
# ticker (the default before 2026-08-05 was SPY for both).
GROWTH_TICKER = "SPYM"

def _dedupe(cols: list[str]) -> list[str]:
    """Stable-order de-dup — DEFENSIVE_TICKER ("IEF") is also a member of
    DEFENSIVE_ROSTER, so naive list concatenation double-lists it, which
    would duplicate that column wherever these lists select from a price
    panel (pandas silently returns a 2-column DataFrame for a duplicated
    label, breaking any Series-shaped arithmetic downstream)."""
    seen: set[str] = set()
    out = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


NON_STOCK_COLS   = _dedupe(["SPY"] + AUX_COLS + REGIME_DETECT_COLS
                           + MACRO_SECTOR_COLS + MACRO_ASSET_COLS)  # drop these to get the stock panel
SIGNAL_EXCLUDE   = _dedupe(NON_STOCK_COLS + [DEFENSIVE_TICKER]
                          + DEFENSIVE_ROSTER + [ROTATION_CASH_TICKER]
                          + [GROWTH_TICKER])  # never receive a signal score

# yfinance-formatted tickers eligible for the _LONG_HISTORY_START floor —
# every ticker the blend can ever hold, so a full/rebase download reaches
# back to 1999 for these regardless of the stock-universe floor above.
_LONG_HISTORY_YF = {_yfmt(t) for t in SIGNAL_EXCLUDE}

# Tail refresh: trading days of overlap re-downloaded to verify the adjustment
# basis (a dividend/split re-bases the ENTIRE adjusted history, not just the tail).
_TAIL_OVERLAP_BD = 10
# Overlap prices differing by more than this (relative) → ticker was re-based.
_BASIS_RTOL = 1e-3


def market_close_passed() -> bool:
    """True once today's NYSE regular-session close (16:00 ET + buffer) has passed.

    On early-close days (half sessions) this treats 13:00–16:05 ET as still
    in-progress, so the loader falls back to the prior close for a few hours —
    always the safe direction (an older real close, never an intraday print).
    """
    return pd.Timestamp.now(tz="America/New_York").time() >= _dtime(16, 5)


def _drop_intraday_row(panel: pd.DataFrame,
                       now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Drop a trailing row dated today while today's session is still open.

    Yahoo reports the live intraday price as today's "close" during market
    hours. The backtest only ever sees completed closes (signal at close of t,
    execution t+1), so an intraday row must never reach the signal, the book,
    or the cache — a cached intraday print would later masquerade as the final
    close and suppress the evening refresh.
    """
    if now is None:
        now = pd.Timestamp.now(tz="America/New_York")
    if (len(panel) and panel.index[-1].date() == now.date()
            and now.time() < _dtime(16, 5)):
        print(f"  Dropping in-progress session row {panel.index[-1].date()} — "
              f"intraday prices are not closes.")
        panel = panel.iloc[:-1]
    return panel


def _drop_partial_tail(panel: pd.DataFrame, min_frac: float = 0.5) -> pd.DataFrame:
    """Drop trailing rows whose ticker coverage collapses vs the recent norm.

    Persisting a partial row poisons every consumer: ffill imputes fake 0%
    returns for the missing tickers and the freshness gate reads the cache as
    current. Compares each trailing row's non-NaN count against the median of
    the 21 rows before it.
    """
    if panel.empty:
        return panel
    cov = panel.notna().sum(axis=1)
    while len(panel) > 21:
        ref = float(cov.iloc[-22:-1].median())
        if ref > 0 and float(cov.iloc[-1]) < min_frac * ref:
            print(f"  Dropping partial trailing row {panel.index[-1].date()} "
                  f"({int(cov.iloc[-1])}/{int(ref)} tickers) — incomplete download.")
            panel = panel.iloc[:-1]
            cov   = cov.iloc[:-1]
        else:
            break
    return panel


def _yf_close(tickers: list[str], start, end, tries: int = 2) -> pd.DataFrame:
    """Bulk-download adjusted closes, retrying tickers that returned nothing."""
    out = pd.DataFrame()
    remaining = list(tickers)
    for attempt in range(tries):
        if not remaining:
            break
        if attempt:
            print(f"  Retrying {len(remaining)} tickers that returned no data …")
        raw = yf.download(remaining, start=start, end=end,
                          auto_adjust=True, progress=True, threads=True, timeout=60)
        if raw is None or len(raw) == 0:
            continue
        close = (raw["Close"] if isinstance(raw.columns, pd.MultiIndex)
                 else raw[["Close"]].rename(columns={"Close": remaining[0]}))
        close.index = pd.to_datetime(close.index)
        out = close.combine_first(out) if not out.empty else close
        got = set(out.columns[out.notna().any()])
        remaining = [t for t in remaining if t not in got]
    return out


def _yf_close_mixed_floor(yf_tickers: list[str], end) -> pd.DataFrame:
    """Like `_yf_close`, but tickers in `_LONG_HISTORY_YF` (the blend's ETF/
    index universe) are downloaded from `_LONG_HISTORY_START`; everything
    else (the stock universe) from `_CACHE_HISTORY_START`. One combined panel."""
    long_yf  = sorted(set(yf_tickers) & _LONG_HISTORY_YF)
    short_yf = sorted(set(yf_tickers) - _LONG_HISTORY_YF)
    parts = []
    if long_yf:
        parts.append(_yf_close(long_yf, _LONG_HISTORY_START, end))
    if short_yf:
        parts.append(_yf_close(short_yf, _CACHE_HISTORY_START, end))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, axis=1) if len(parts) > 1 else parts[0]


_STALE_WARN_DAYS = 5  # flag AUX_COLS (regime-signal inputs) whose trailing
                      # gap exceeds this many calendar days — a real upstream
                      # feed gap (verified 2026-08-05: ^VIX3M missing 12
                      # trading days on Yahoo), not something a re-fetch fixes.


def _warn_stale_aux(panel: pd.DataFrame) -> None:
    """Surface a stale AUX_COLS tail explicitly (see csm/signals.py's
    _vix_contango_vote, which independently withholds its vote on these same
    dates) instead of letting downstream ffill silently paper over a gap."""
    if panel.empty:
        return
    panel_end = panel.index.max()
    for col in AUX_COLS:
        if col not in panel.columns:
            continue
        valid = panel[col].dropna()
        if valid.empty:
            continue
        lag = (panel_end - valid.index.max()).days
        if lag > _STALE_WARN_DAYS:
            print(f"  WARNING: {col} data is stale — last real print "
                  f"{valid.index.max().date()}, {lag} calendar days behind "
                  f"the panel's latest date {panel_end.date()}. This is a "
                  f"source-side gap (re-fetching will not resolve it); "
                  f"regime signals that consume {col} handle this explicitly.")


def _tail_refresh(cached: pd.DataFrame, needed_yf: list[str],
                  inv_map: dict, end) -> pd.DataFrame:
    """Splice fresh closes onto the cache, fully re-downloading only where needed."""
    last_good  = cached.index[-1]        # last complete row (partial tail already dropped)
    tail_start = (last_good - pd.tseries.offsets.BDay(_TAIL_OVERLAP_BD)).strftime("%Y-%m-%d")
    print(f"Tail refresh: downloading closes from {tail_start} …")
    tail = _yf_close(needed_yf, tail_start, end).rename(columns=inv_map)

    fresh     = [c for c in tail.columns if tail[c].notna().any()]
    known     = [c for c in fresh if c in cached.columns]
    brand_new = [c for c in fresh if c not in cached.columns]   # new universe entrants

    # Adjustment-basis check on the overlap: if a dividend/split hit since the
    # last pull, the whole adjusted history shifted → full re-download for that
    # ticker. Unverifiable overlaps (no common non-NaN dates) are re-based too.
    overlap = cached.index.intersection(tail.index)
    rebase, matched = list(brand_new), []
    if len(overlap) and known:
        rel = (tail.loc[overlap, known] / cached.loc[overlap, known] - 1.0).abs().max()
        for c in known:
            (matched if rel.get(c, np.nan) <= _BASIS_RTOL else rebase).append(c)
    else:
        rebase += known

    panel = cached
    if matched:
        panel = tail[matched].combine_first(panel)   # new tail wins on the overlap

    if rebase:
        print(f"  {len(rebase)} tickers re-based (dividend/split) or new to the "
              f"cache — re-downloading their full history …")
        full = _yf_close_mixed_floor([_yfmt(c) for c in rebase], end).rename(columns=inv_map)
        got  = [c for c in full.columns if full[c].notna().any()]
        panel = pd.concat([panel.drop(columns=[c for c in got if c in panel.columns]),
                           full[got]], axis=1)
        failed = sorted(set(rebase) - set(got))
        if failed:
            print(f"  WARNING: {len(failed)} re-based tickers failed to download — "
                  f"keeping their cached (possibly stale-basis) history: "
                  f"{', '.join(failed[:8])}" + (" …" if len(failed) > 8 else ""))

    n_stale = len([c for c in cached.columns if c not in fresh])
    if n_stale:
        print(f"  {len(fresh)} tickers updated; {n_stale} returned no new data "
              f"(delisted or failed) — cached history retained.")
    return panel


def load_price_panel(
    tickers:        list[str],
    start:          str,
    end:            str,
    cache_dir:      Path,
    refresh:        str = "auto",
    force_download: bool = False,   # back-compat alias for refresh="full"
) -> pd.DataFrame:
    """Return adj-close price panel (DatetimeIndex × tickers) sliced to [start, end].

    The on-disk cache always covers _CACHE_HISTORY_START → end so the momentum
    signal (252-day window) has enough history regardless of start_date in config.

    refresh = "auto" | "tail" | "full"  (see module docstring). In "auto" mode the
    cache is served as-is when its latest complete close is within 5 trading days
    of `end` — callers that need same-day data (`ideas`) check the exact lag
    themselves and re-call with refresh="tail".
    """
    if force_download:
        refresh = "full"
    if start in (None, "", "auto"):
        start = _CACHE_HISTORY_START

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "prices.parquet"

    yfmt_map   = {t: _yfmt(t) for t in tickers}
    inv_map    = {v: k for k, v in yfmt_map.items()}
    needed_yf  = sorted(set(yfmt_map.values()) | {"SPY"} | set(AUX_COLS)
                        | {DEFENSIVE_TICKER} | set(REGIME_DETECT_COLS)
                        | set(DEFENSIVE_ROSTER) | {ROTATION_CASH_TICKER}
                        | set(MACRO_SECTOR_COLS) | set(MACRO_ASSET_COLS)
                        | {GROWTH_TICKER})
    target_end = pd.Timestamp(end)

    cached = pd.DataFrame()
    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        cached.columns = [inv_map.get(c, c) for c in cached.columns]
        cached = _drop_intraday_row(cached)   # heal a same-day intraday row
        cached = _drop_partial_tail(cached)   # heal a previously-poisoned tail

    # Rebuild if the cache doesn't cover _CACHE_HISTORY_START — e.g. that constant
    # was extended further back (2010 -> 2004) after the cache was already built.
    # Without this check "auto"/"tail" would silently keep serving the old,
    # shorter-history cache forever (they only ever check tail freshness).
    # SPY is the reference column for both floors: it is always present and
    # always long-history-eligible, so its own earliest date reveals whether
    # the cache was ever rebuilt under the newer (longer) floor.
    if not cached.empty:
        cache_floor = cached.index.min()
        spy_floor = (cached["SPY"].dropna().index.min()
                    if "SPY" in cached.columns and cached["SPY"].notna().any()
                    else cache_floor)
        want_floor = pd.Timestamp(_LONG_HISTORY_START)
        if spy_floor > want_floor + pd.Timedelta(days=10):
            print(f"Cache's long-history reference (SPY) only starts {spy_floor.date()} — "
                  f"_LONG_HISTORY_START is {_LONG_HISTORY_START}; forcing full re-download "
                  f"of the long-history (ETF/index) columns …")
            # Deliberately DON'T clear `cached` — the "full" branch below merges
            # by column (`keep` falls back to old data for any column absent
            # from this call's `needed_yf`), so a blend-only call (tickers=[])
            # correctly extends just the ETF columns while leaving the
            # separately-floored stock columns untouched.
            refresh = "full"

    # ── auto: serve the cache when complete and fresh ─────────────────────────
    if refresh == "auto" and not cached.empty:
        missing    = [t for t in needed_yf if inv_map.get(t, t) not in cached.columns]
        panel_last = cached.index[-1]
        if not missing and panel_last >= target_end - pd.tseries.offsets.BDay(5):
            present = _dedupe([t for t in list(tickers) + SIGNAL_EXCLUDE
                              if t in cached.columns])
            panel   = cached[present].loc[start:end]
            print(f"Loaded price cache: {len(present)} tickers × {len(panel)} days  "
                  f"(history from {cached.index.min().date()}, "
                  f"fresh through {panel_last.date()})")
            _warn_stale_aux(panel)
            return panel
        print(f"Cache stale/incomplete (latest complete close {panel_last.date()}"
              + (f", {len(missing)} tickers missing" if missing else "")
              + ") — incremental refresh …")
        refresh = "tail"

    # ── tail: incremental splice onto the existing cache ─────────────────────
    if refresh == "tail" and not cached.empty:
        panel = _tail_refresh(cached, needed_yf, inv_map, end)
    # ── full: re-download everything (fetch, or no usable cache) ─────────────
    else:
        print("Full re-download of all price history …")
        new = _yf_close_mixed_floor(needed_yf, end).rename(columns=inv_map)
        got = [c for c in new.columns if new[c].notna().any()]
        # Column-wise merge: a ticker that downloaded takes its ENTIRE new column
        # (never mix old and new adjusted-price bases); a ticker that failed
        # keeps its cached column.
        keep = [c for c in cached.columns if c not in got]
        if got:
            panel = pd.concat([new[got], cached[keep]], axis=1) if keep else new[got]
        else:
            panel = cached
        if panel.empty:
            raise RuntimeError("Price download returned no data and no cache exists — "
                               "check network / Yahoo availability and retry.")
        failed = sorted(set(inv_map.get(t, t) for t in needed_yf) - set(got))
        if failed:
            print(f"  WARNING: {len(failed)} tickers failed to download — "
                  f"cached history retained where available: "
                  f"{', '.join(failed[:8])}" + (" …" if len(failed) > 8 else ""))

    panel = panel.dropna(axis=1, how="all").sort_index()
    panel = _drop_intraday_row(panel)   # never cache an in-progress session
    panel = _drop_partial_tail(panel)

    panel.rename(columns=yfmt_map).to_parquet(cache_path)
    print(f"Price cache updated: {panel.shape[1]} tickers × {panel.shape[0]} days  "
          f"(history from {panel.index.min().date()}, through {panel.index.max().date()})")

    result = panel.loc[start:end]
    _warn_stale_aux(result)
    return result


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns, forward-fill at most 3 days of NaN (halts, etc.)."""
    return prices.ffill(limit=3).pct_change().replace([np.inf, -np.inf], np.nan)


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return np.log1p(daily_returns(prices))


def pit_filter(
    returns:    pd.DataFrame,
    pit_df:     pd.DataFrame,
    query_date: pd.Timestamp,
) -> pd.Series:
    """Restrict a cross-section of returns to PIT-valid tickers on query_date.

    Returns the returns Series for valid tickers on that date.
    """
    from csm.universe import get_members_on
    valid = get_members_on(pit_df, query_date)
    cols  = [c for c in returns.columns if c in valid or c == "SPY"]
    return returns.loc[query_date, cols] if query_date in returns.index else pd.Series(dtype=float)
