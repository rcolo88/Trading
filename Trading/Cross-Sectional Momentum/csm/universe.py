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


def _clean_ticker(t: str) -> str:
    return str(t).strip().replace(".", "-").upper()


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
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
    """Walk the changes table backward from today to reconstruct PIT membership.

    Returns a DataFrame indexed by date with one column 'members' (set of tickers).
    We represent this as a long-form table: (date, ticker) where the ticker was
    *added* on that date.  Consumers build a daily membership set from this.
    """
    if changes.empty:
        # Fallback: assume current membership is static for the whole history
        start = pd.Timestamp(history_start)
        return pd.DataFrame({"date": [start] * len(current),
                             "ticker": current,
                             "action": ["add"] * len(current)})

    # current members are in the index as of today; walk backward
    members = set(current)
    event_dates = sorted(changes["date"].unique(), reverse=True)

    snapshots = []
    snapshot_date = pd.Timestamp("today").normalize()

    for evt_date in event_dates:
        if evt_date < pd.Timestamp(history_start):
            break
        # Record membership *before* applying this date's events
        snapshots.append({"date": snapshot_date, "members": frozenset(members)})
        # Undo events on this date (add back removals, remove adds)
        evts = changes[changes["date"] == evt_date]
        for _, row in evts.iterrows():
            if row["action"] == "add":
                members.discard(row["ticker"])
            else:
                members.add(row["ticker"])
        snapshot_date = evt_date - pd.Timedelta(days=1)

    # Remaining membership covers history_start to the oldest event
    snapshots.append({"date": snapshot_date, "members": frozenset(members)})

    # Expand to long-form (date, ticker, action)
    records = []
    for snap in snapshots:
        for tk in snap["members"]:
            records.append({"date": snap["date"], "ticker": tk, "action": "add"})
    if not records:
        return pd.DataFrame(columns=["date", "ticker", "action"])
    return pd.DataFrame(records).sort_values("date")


def build_pit_membership(cache_dir: Path,
                         start: str = "2010-01-01") -> pd.DataFrame:
    """Load or build the point-in-time S&P 1500 membership table.

    Returns a DataFrame with columns: date (Timestamp), ticker (str), sub_index (str).
    Each row records that `ticker` was *added* to `sub_index` on `date`.
    Use `get_members_on(df, query_date)` to get the active set for any date.
    """
    cache_path = cache_dir / "universe_pit.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    print("Building point-in-time S&P 1500 membership (Wikipedia) …")
    all_records: list[pd.DataFrame] = []

    for sub_idx, url in _INDEX_URLS.items():
        try:
            tables  = _fetch_html(url)
            current = _current_tickers(tables)
            changes = _parse_changes(tables)
            pit     = _pit_from_changes(current, changes, history_start=start)
            pit["sub_index"] = sub_idx
            all_records.append(pit)
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
    return combined


def get_members_on(pit_df: pd.DataFrame, query_date: pd.Timestamp) -> set[str]:
    """Active S&P 1500 members on `query_date` per the PIT membership table.

    For each ticker, the most recent 'add' event on or before query_date counts.
    If the ticker's most recent event is 'remove', it is excluded.
    """
    past = pit_df[pit_df["date"] <= query_date]
    if past.empty:
        return set()
    latest = past.sort_values("date").groupby("ticker").last().reset_index()
    return set(latest.loc[latest["action"] == "add", "ticker"])


def get_all_ever_members(pit_df: pd.DataFrame) -> list[str]:
    """Union of all tickers that ever appeared in the S&P 1500 (for bulk price download)."""
    return sorted(pit_df["ticker"].unique().tolist())
