"""Point-in-time S&P 1500 index membership reconstruction.

Reconstructs historical membership from Wikipedia's current constituent tables
plus the "Changes" (additions/removals + effective dates) table for each sub-index.
The result is a point-in-time CSV so the backtester only holds names that were
*actually* in the index on a given date.

Disclosed residual bias: yfinance lacks price history for most delisted names,
so the PIT membership correction removes look-ahead *selection* bias but cannot
fully resurrect dead stocks.  Survivorship impact is therefore not entirely
eliminated; it is disclosed in every report.
"""
from __future__ import annotations

import re
import warnings
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

warnings.filterwarnings("ignore")

_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

_INDEX_URLS = {
    "sp500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "sp400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "sp600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
}

# Column aliases used across different Wikipedia table layouts
_TICKER_COLS   = ["Symbol", "Ticker symbol", "Ticker"]
_DATE_COLS     = ["Date", "Date added", "Effective date"]
_ADDED_COLS    = ["Added", "Added Ticker", "Ticker"]
_REMOVED_COLS  = ["Removed", "Removed Ticker", "Removed ticker"]
_SECTOR_COLS   = ["GICS Sector"]
_SUBIND_COLS   = ["GICS Sub-Industry"]


def _clean_ticker(t: str) -> str:
    return str(t).strip().replace(".", "-").upper()


def _flat_name(col) -> str:
    """Flatten a (possibly MultiIndex) column label to a single matchable string.

    Wikipedia's "Changes" tables use MultiIndex columns where Wikipedia repeats
    the group name at both levels, e.g. ('Effective Date', 'Effective Date') or
    ('Added', 'Ticker').  Deduping repeated levels and joining the rest gives
    "Effective Date" / "Added Ticker" — exactly the names candidates expect.
    """
    if isinstance(col, tuple):
        parts: list[str] = []
        for c in col:
            s = str(c).strip()
            if s and s.lower() != "nan" and s not in parts:
                parts.append(s)
        return " ".join(parts)
    return str(col).strip()


def _find_col(df: pd.DataFrame, candidates: list[str]):
    """Return the ORIGINAL column key (str or tuple) matching a candidate name.

    Matches case-insensitively against the flattened column name, so this works
    for both plain single-level columns and Wikipedia's MultiIndex tables.
    """
    flat_map = {_flat_name(c).lower(): c for c in df.columns}
    for cand in candidates:
        key = flat_map.get(cand.lower())
        if key is not None:
            return key
    return None


def _fetch_html(url: str) -> list[pd.DataFrame]:
    r = requests.get(url, headers=_UA, timeout=30)
    r.raise_for_status()
    return pd.read_html(StringIO(r.text))


def _current_tickers(tables: list[pd.DataFrame]) -> list[str]:
    """Extract current constituent tickers from the first valid table."""
    for t in tables:
        col = _find_col(t, _TICKER_COLS)
        if col:
            return [_clean_ticker(x) for x in t[col].dropna().tolist()]
    return []


def _extract_sectors(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """Extract (ticker, sector, sub_industry) from the current-constituents table.

    CURRENT classification only — Wikipedia doesn't carry historical GICS
    reassignments, so this is a disclosed residual bias (same pattern as the
    delisted-price gap): a name's sector here is its sector TODAY, not
    necessarily what it was on some historical rebalance date.
    """
    for t in tables:
        tcol = _find_col(t, _TICKER_COLS)
        scol = _find_col(t, _SECTOR_COLS)
        if tcol is None or scol is None:
            continue
        icol = _find_col(t, _SUBIND_COLS)
        out = pd.DataFrame({
            "ticker":     [_clean_ticker(x) for x in t[tcol]],
            "sector":     t[scol].astype(str).str.strip(),
            "sub_industry": t[icol].astype(str).str.strip() if icol is not None else "",
        })
        return out.dropna(subset=["ticker"]).drop_duplicates(subset=["ticker"])
    return pd.DataFrame(columns=["ticker", "sector", "sub_industry"])


def _parse_changes(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """Extract additions and removals with their effective dates.

    Returns DataFrame with columns: date, ticker, action ('add'|'remove').
    """
    rows = []
    for tbl in tables[1:]:           # changes table is usually the second one
        date_col    = _find_col(tbl, _DATE_COLS)
        added_col   = _find_col(tbl, _ADDED_COLS)
        removed_col = _find_col(tbl, _REMOVED_COLS)
        if date_col is None or (added_col is None and removed_col is None):
            continue

        for _, row in tbl.iterrows():
            raw_date = str(row[date_col])
            try:
                eff_date = pd.to_datetime(raw_date, errors="coerce")
                if pd.isnull(eff_date):
                    continue
                eff_date = eff_date.date()
            except Exception:
                continue

            if added_col and pd.notna(row.get(added_col, None)):
                tk = _clean_ticker(str(row[added_col]))
                if tk and tk != "NAN":
                    rows.append({"date": eff_date, "ticker": tk, "action": "add"})

            if removed_col and pd.notna(row.get(removed_col, None)):
                tk = _clean_ticker(str(row[removed_col]))
                if tk and tk != "NAN":
                    rows.append({"date": eff_date, "ticker": tk, "action": "remove"})

    if not rows:
        return pd.DataFrame(columns=["date", "ticker", "action"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates().sort_values("date")


def _pit_from_changes(current: list[str], changes: pd.DataFrame,
                      history_start: str = "2010-01-01") -> pd.DataFrame:
    """Build a point-in-time membership EVENT LOG (not snapshots) from the changes table.

    Returns (date, ticker, action) rows where `action` is the literal event that
    happened to `ticker` on `date` ('add' or 'remove'). `get_members_on` finds each
    ticker's most recent event on/before a query date, so removals MUST appear as
    explicit 'remove' rows — a snapshot-of-full-membership representation (the
    previous implementation) never emits a 'remove' once a ticker drops out, so
    `get_members_on` would keep counting it as a member forever after its last
    recorded snapshot. This walks backward from today's membership, undoing every
    event on/after `history_start` to find the membership immediately BEFORE the
    window, emits that as synthetic 'add' events at `history_start`, then appends
    every real event inside the window unchanged.
    """
    history_start_ts = pd.Timestamp(history_start)
    if changes.empty:
        # Fallback: assume current membership is static for the whole history
        return pd.DataFrame({"date": [history_start_ts] * len(current),
                             "ticker": current,
                             "action": ["add"] * len(current)})

    # Walk backward from today's membership, undoing every in-window event, to
    # find what membership was immediately before `history_start`.
    members = set(current)
    for _, row in changes.sort_values("date", ascending=False).iterrows():
        if row["date"] < history_start_ts:
            break
        if row["action"] == "add":
            members.discard(row["ticker"])
        else:
            members.add(row["ticker"])

    starting = pd.DataFrame({"date": history_start_ts,
                             "ticker": sorted(members),
                             "action": "add"})
    in_window = changes.loc[changes["date"] >= history_start_ts,
                            ["date", "ticker", "action"]]
    return pd.concat([starting, in_window], ignore_index=True).sort_values("date")


# PIT history always goes back this far regardless of the analysis start_date in config.
# Changing start_date in config.yaml never requires re-running fetch.
_PIT_HISTORY_START = "2010-01-01"


def build_pit_membership(cache_dir: Path,
                         start: str = _PIT_HISTORY_START) -> pd.DataFrame:
    """Load or build the point-in-time S&P 1500 membership table.

    Returns a DataFrame with columns: date (Timestamp), ticker (str), sub_index (str).
    Each row records that `ticker` was *added* to `sub_index` on `date`.
    Use `get_members_on(df, query_date)` to get the active set for any date.
    """
    cache_path = cache_dir / "universe_pit.parquet"
    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        # Rebuild if the cached PIT doesn't cover our full history start
        if not cached.empty and pd.to_datetime(cached["date"].min()) > pd.Timestamp(_PIT_HISTORY_START) + pd.Timedelta(days=365):
            print(f"PIT cache only starts {cached['date'].min().date()} — rebuilding from {_PIT_HISTORY_START} …")
            cache_path.unlink()
        else:
            return cached

    print("Building point-in-time S&P 1500 membership (Wikipedia) …")
    all_records: list[pd.DataFrame] = []
    sector_records: list[pd.DataFrame] = []

    for sub_idx, url in _INDEX_URLS.items():
        try:
            tables  = _fetch_html(url)
            current = _current_tickers(tables)
            changes = _parse_changes(tables)
            pit     = _pit_from_changes(current, changes, history_start=_PIT_HISTORY_START)
            pit["sub_index"] = sub_idx
            all_records.append(pit)
            sec = _extract_sectors(tables)
            if not sec.empty:
                sector_records.append(sec)
            print(f"  {sub_idx}: {len(current)} current members, "
                  f"{len(changes)} change events parsed")
        except Exception as exc:
            print(f"  WARNING: could not parse {sub_idx} ({exc}); using current snapshot")
            # Graceful fallback: current snapshot as static membership
            tickers = [_clean_ticker(t) for t in current] if "current" in dir() else []
            if tickers:
                fallback = pd.DataFrame({
                    "date": pd.Timestamp(start),
                    "ticker": tickers,
                    "action": "add",
                    "sub_index": sub_idx,
                })
                all_records.append(fallback)

    if not all_records:
        raise RuntimeError("Failed to build universe — no index data retrieved.")

    combined = pd.concat(all_records, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.drop_duplicates(subset=["date", "ticker", "sub_index"])

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(cache_path, index=False)
    print(f"PIT membership cached → {cache_path}")

    if sector_records:
        sectors = (pd.concat(sector_records, ignore_index=True)
                     .drop_duplicates(subset=["ticker"]))
        sectors.to_parquet(cache_dir / "universe_sectors.parquet", index=False)
        print(f"Sector map cached → {cache_dir / 'universe_sectors.parquet'} "
              f"({len(sectors)} tickers, current classification only)")

    return combined


def get_sector_map(cache_dir: Path) -> dict[str, str]:
    """Ticker -> GICS sector, from the cache built alongside PIT membership.

    CURRENT classification only (see `_extract_sectors`) — a name's sector here
    is its sector TODAY, not point-in-time. Returns {} if the cache doesn't
    exist yet (run `fetch` first); callers should treat a missing sector as
    "unknown" rather than erroring.
    """
    path = cache_dir / "universe_sectors.parquet"
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    return dict(zip(df["ticker"], df["sector"]))


def get_members_on(pit_df: pd.DataFrame, query_date: pd.Timestamp) -> set[str]:
    """Active S&P 1500 members on `query_date` per the PIT membership table.

    For each ticker, the most recent 'add' event on or before query_date counts.
    If the ticker's most recent event is 'remove', it is excluded.
    If query_date precedes all PIT events, falls back to the earliest snapshot.
    """
    past = pit_df[pit_df["date"] <= query_date]
    if past.empty:
        # query_date is before the PIT history starts — use earliest available snapshot
        past = pit_df[pit_df["date"] == pit_df["date"].min()]
    latest = past.sort_values("date").groupby("ticker").last().reset_index()
    return set(latest.loc[latest["action"] == "add", "ticker"])


def get_all_ever_members(pit_df: pd.DataFrame) -> list[str]:
    """Union of all tickers that ever appeared in the S&P 1500 (for bulk price download)."""
    return sorted(pit_df["ticker"].unique().tolist())
