"""Point-in-time FRED/ALFRED loader — economic series exactly as they looked
on a given date, with neither revision nor publication look-ahead.

Endpoint is `api.stlouisfed.org` (verified working and fast — the CSV/graph
host `fred.stlouisfed.org` times out from this environment, which is why
macro_regime.py originally substituted market-observable proxies; see its
module docstring). Plain `requests` (already a dependency) — do NOT add
`fredapi`.

The key trick: setting `realtime_start = realtime_end = asof` on the ALFRED
`series/observations` endpoint returns the series exactly as it was known on
`asof` — revisions that happened after `asof` are invisible, and reference
periods not yet published by `asof` are simply absent from the response (not
NaN-filled). Verified 2026-08-05: UNRATE queried as-of 2008-09-01 showed
2008-01 through 2008-07 with 6 of 7 months later revised, and 2008-08 not yet
published at all — both revision AND publication lag are handled by this one
parameter pair.

Every distinct (series_id, asof) pull is cached to
`outputs/cache/fred_vintages.parquet` so a backtest never re-fetches the same
vintage twice.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests


def _atomic_to_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write-then-rename so a killed process (verified 2026-08-05: an
    interrupted prefetch corrupted the cache with a cryptic pyarrow error on
    every subsequent read) can never leave a half-written parquet behind."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)

_BASE = "https://api.stlouisfed.org/fred/series/observations"
_CACHE_FILE = "fred_vintages.parquet"
_TIMEOUT_S = 30


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def get_api_key(project_root: Path | None = None) -> str:
    """FRED_API_KEY from the environment, else a `.env` file beside
    config.yaml (see .env.example). Never read from config.yaml.
    `project_root` defaults to the current working directory — every CLI
    entry point in this project is invoked with CWD = the project root
    (same convention `blend_target_weights` uses for its `cache_dir` default).
    """
    key = os.environ.get("FRED_API_KEY")
    if key:
        return key
    root = Path(project_root) if project_root is not None else Path.cwd()
    env = _load_env_file(root / ".env")
    if env.get("FRED_API_KEY"):
        return env["FRED_API_KEY"]
    raise RuntimeError(
        "FRED_API_KEY not set. Get a free key at "
        "https://fred.stlouisfed.org/docs/api/api_key.html and put it in "
        "the environment or a .env file next to config.yaml (see .env.example)."
    )


def _fetch_vintage(series_id: str, asof: pd.Timestamp, observation_start: str,
                   api_key: str) -> pd.DataFrame:
    """One ALFRED call: the series exactly as known on `asof`.

    Some series' ALFRED vintage archive doesn't reach as far back as their
    plain observation history (verified 2026-08-05: NFCI vintages start
    ~2011-05, T10Y2Y ~2014-01, despite both series existing since 1971/1976)
    — FRED returns a 400 "does not exist in ALFRED" for an earlier `asof`.
    For dates before that boundary this falls back to a plain (non-realtime)
    query, still bounded by `observation_end=asof` so no future date ever
    leaks in. This is safe specifically for NFCI/T10Y2Y: both are
    market-computed series with no real revision history (unlike UNRATE,
    whose genuine revisions are documented in this module's docstring) —
    the fallback closes a metadata gap, not a look-ahead risk.
    """
    asof_s = pd.Timestamp(asof).strftime("%Y-%m-%d")
    params = dict(series_id=series_id, api_key=api_key, file_type="json",
                  realtime_start=asof_s, realtime_end=asof_s,
                  observation_start=observation_start, observation_end=asof_s)

    # Transient 5xx (verified 2026-08-05: a bare NFCI request 500'd mid-run
    # with no other cause) get a few retries with backoff before giving up —
    # a single flaky response shouldn't kill a multi-hundred-call prefetch.
    r = None
    for attempt in range(4):
        r = requests.get(_BASE, params=params, timeout=_TIMEOUT_S)
        if r.status_code < 500:
            break
        time.sleep(2 ** attempt)

    if r.status_code == 400 and "does not exist in ALFRED" in r.text:
        params = dict(series_id=series_id, api_key=api_key, file_type="json",
                      observation_start=observation_start, observation_end=asof_s)
        for attempt in range(4):
            r = requests.get(_BASE, params=params, timeout=_TIMEOUT_S)
            if r.status_code < 500:
                break
            time.sleep(2 ** attempt)
    if r.status_code != 200:
        raise RuntimeError(f"FRED API error {r.status_code} for "
                          f"{series_id}@{asof_s}: {r.text[:200]}")
    obs = r.json().get("observations", [])
    rows = [(series_id, asof_s, o["date"],
             np.nan if o["value"] == "." else float(o["value"]))
            for o in obs]
    return pd.DataFrame(rows, columns=["series_id", "asof", "date", "value"])


# In-process cache: an (series_id, asof) index dict + the full accumulated
# frame, keyed by resolved cache path. A batch loop (e.g. growth_score_macro
# over ~300 rebal dates x 3 series) would otherwise re-read and re-scan the
# ENTIRE on-disk parquet on every single call, even cache hits — verified
# 2026-08-05 to make a multi-hundred-call batch dramatically slower once the
# file passed ~1M rows. The disk file remains the cross-process source of
# truth (a fresh process rebuilds this index from it on first use); only
# repeated calls WITHIN one process skip the redundant re-read.
_MEM_INDEX: dict[str, dict[tuple[str, str], pd.DataFrame]] = {}
_MEM_FULL:  dict[str, pd.DataFrame] = {}


def _load_mem_index(cache_path: Path) -> dict[tuple[str, str], pd.DataFrame]:
    key = str(cache_path)
    if key not in _MEM_INDEX:
        if cache_path.exists():
            full = pd.read_parquet(cache_path)
        else:
            full = pd.DataFrame(columns=["series_id", "asof", "date", "value"])
        idx: dict[tuple[str, str], pd.DataFrame] = {}
        for (sid, asof_s), grp in full.groupby(["series_id", "asof"], sort=False):
            idx[(sid, asof_s)] = grp
        _MEM_INDEX[key] = idx
        _MEM_FULL[key]  = full
    return _MEM_INDEX[key]


def vintage_series(
    series_id:         str,
    asof:              pd.Timestamp,
    observation_start: str,
    cache_dir:         Path,
    api_key:           str | None = None,
    project_root:      Path | None = None,
) -> pd.Series:
    """The series exactly as it was known on `asof`, cached to disk so the
    same (series_id, asof) pair is never re-fetched. Returns a Series indexed
    by reference date; observations not yet published by `asof` are simply
    absent — the caller must not assume a fixed-length window.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / _CACHE_FILE
    cache_key  = str(cache_path)
    asof_s = pd.Timestamp(asof).strftime("%Y-%m-%d")

    idx = _load_mem_index(cache_path)
    lookup = (series_id, asof_s)
    hit = idx.get(lookup)
    if hit is None:
        if api_key is None:
            api_key = get_api_key(project_root)
        fresh = _fetch_vintage(series_id, asof, observation_start, api_key)
        idx[lookup] = fresh
        _MEM_FULL[cache_key] = (fresh.copy() if _MEM_FULL[cache_key].empty
                                else pd.concat([_MEM_FULL[cache_key], fresh], ignore_index=True))
        _atomic_to_parquet(_MEM_FULL[cache_key], cache_path)
        hit = fresh

    s = hit.set_index("date")["value"].copy()
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def vintage_panel(
    series_id:         str,
    asof_dates:        pd.DatetimeIndex,
    observation_start: str,
    cache_dir:         Path,
    api_key:           str | None = None,
    project_root:      Path | None = None,
) -> pd.Series:
    """Point-in-time LATEST value of `series_id` at each of `asof_dates` —
    e.g. the most recently published UNRATE reading as known on every
    rebalance date. Publication lag means this is often the prior
    month/week's reading, never the current one. One `vintage_series` call
    per date (cached), so repeat backtests are free after the first run.
    """
    if api_key is None:
        api_key = get_api_key(project_root)
    out = pd.Series(index=asof_dates, dtype=float)
    for d in asof_dates:
        s = vintage_series(series_id, d, observation_start, cache_dir, api_key=api_key)
        if not s.empty:
            out.loc[d] = s.iloc[-1]
    return out
