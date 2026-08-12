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

# A sentinel `asof` used for `revision: none` series — see SERIES_REGISTRY below.
# Stored in the same (series_id, asof, date) cache as every other vintage, so
# the dedupe/write/atomic-rename machinery below needs no special-casing.
_NO_REVISION_ASOF = "ALL"


# ─────────────────────────────────────────────────────────────────────────────
#  Series registry — EMPIRICALLY VERIFIED revision behaviour, not assumed.
#
#  2026-08-12: the loader used to assert (csm/fred.py's old module docstring)
#  that NFCI and T10Y2Y "have no real revision history" to justify a silent
#  fallback to non-realtime data before ALFRED's vintage archive begins.
#  Measured directly against the cache: T10Y2Y is genuinely never revised
#  (0 of 12,132 reference dates), but NFCI is revised on 75.4% of reference
#  dates (one week moved ~30% across vintages) — the claim was FALSE for NFCI,
#  and every pre-2011 NFCI read had been silently serving fully-revised data
#  under the guise of a point-in-time read. See docs/GAPS.md #2.
#
#  `revision: "none"` means the series is a market quote or a pure accounting
#  snapshot with no revision process — safe to pull ONCE (see
#  `_fetch_full_series`/the shortcut in `vintage_series`) rather than vintaged
#  319 times. `revision: "revised"` means it's survey/estimate-based and
#  undergoes genuine methodological or seasonal-factor revisions — it must
#  always be vintaged, and may never take the silent ALFRED fallback below.
#
#  `verified` is True only for entries actually measured against real vintage
#  data this session (UNRATE/NFCI/T10Y2Y, from the existing cache) or via
#  `verify_revision_rate(...)` / `--verify-revisions`. Everything else is
#  classified from the well-established nature of the release (a market quote
#  vs. a statistical agency estimate) — the same reasoning the original code
#  used for T10Y2Y, just written down explicitly and flagged as pending
#  verification rather than asserted outright.
# ─────────────────────────────────────────────────────────────────────────────
SERIES_REGISTRY: dict[str, dict] = {
    # ── already live in macro_regime.py (measured 2026-08-12) ──────────────
    "UNRATE":       {"revision": "revised", "frequency": "monthly", "verified": True,
                      "description": "Civilian unemployment rate"},
    "NFCI":         {"revision": "revised", "frequency": "weekly", "verified": True,
                      "description": "Chicago Fed National Financial Conditions Index"},
    "T10Y2Y":       {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "10-Year minus 2-Year Treasury yield spread"},

    # ── FX (previously zero coverage) ───────────────────────────────────────
    # DEXJPUS verified 2026-08-12 (verify_revision_rate, 6-vintage sample,
    # 3,027 reference dates): 1 date (2022-08-05) shows a single one-cent
    # correction (135.32 -> 135.33) made within a week of the print and
    # stable across every later vintage -- a one-time typo-level fix, not a
    # revision process (rate 0.033%, categorically unlike NFCI's 75.4%).
    # Kept "none" -- immaterial for any macro vote at this resolution -- but
    # recorded honestly rather than rounded to a clean 0%.
    "DEXJPUS":      {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "Japanese Yen to U.S. Dollar spot exchange rate"},
    # RECLASSIFIED 2026-08-12: initially guessed "none" by analogy to a raw
    # FX rate, but these are Fed-CONSTRUCTED index series (trade-weight
    # baskets get updated as new trade data arrives), not bilateral spot
    # quotes -- categorically different from DEXJPUS/DEXUSEU above.
    # verify_revision_rate caught the error before it shipped: 87.3% of
    # reference dates revised across a 6-vintage sample (3,027 dates),
    # median magnitude ~0.18% of level -- small per-revision, but a genuine
    # ongoing process, not a rounding fix. This is exactly the check that
    # should have caught the original NFCI misclassification (docs/GAPS.md
    # #2) -- the mechanism doing its job on a NEW series this time.
    "DTWEXBGS":     {"revision": "revised", "frequency": "daily", "verified": True,
                      "description": "Trade Weighted U.S. Dollar Index: Broad, Goods and Services"},
    "DTWEXAFEGS":   {"revision": "revised", "frequency": "daily", "verified": True,
                      "description": "Trade Weighted U.S. Dollar Index: Advanced Foreign Economies"},
    "DEXUSEU":      {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "U.S. Dollar to Euro spot exchange rate"},

    # ── curve ────────────────────────────────────────────────────────────────
    # T10Y3M, DGS10 verified 2026-08-12 (6-vintage sample): 0% revision rate.
    "T10Y3M":       {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "10-Year minus 3-Month Treasury yield spread (Estrella-Mishkin)"},
    "DGS10":        {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "10-Year Treasury constant maturity rate"},
    "DGS2":         {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "2-Year Treasury constant maturity rate"},
    "DGS3MO":       {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "3-Month Treasury constant maturity rate"},
    "DFII10":       {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "10-Year Treasury Inflation-Indexed (real) yield"},
    "T10YIE":       {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "10-Year breakeven inflation rate"},
    "T5YIFR":       {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "5-Year, 5-Year forward inflation expectation rate"},

    # ── credit ───────────────────────────────────────────────────────────────
    # BAMLH0A0HYM2 verified 2026-08-12: 0% revision rate. IMPORTANT caveat
    # unrelated to revision status -- FRED's own series metadata gives this
    # ID's observation_start as 2023-08-14 (confirmed via the `fred/series`
    # endpoint), not the ~1996-97 history the older BAMLH0A0HYM2Y2 vintage
    # would suggest. This ID cannot cover the 2000-2014 holdout or any GFC
    # analysis -- see docs/DATA_INPUTS.md.
    "BAMLH0A0HYM2": {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "ICE BofA US High Yield Index Option-Adjusted Spread"},
    "BAMLC0A0CM":   {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "ICE BofA US Corporate (Investment Grade) Index OAS"},
    "BAA10Y":       {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "Moody's Baa Corporate Bond Yield minus 10-Year Treasury"},

    # ── commodity ────────────────────────────────────────────────────────────
    "DCOILWTICO":   {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "WTI crude oil spot price"},

    # ── activity (survey/estimate-based — genuinely revised) ───────────────
    # All three verified 2026-08-12: 70-91% of reference dates revised across
    # a 6-vintage sample — the "revised" classification is not a guess here.
    "ICSA":         {"revision": "revised", "frequency": "weekly", "verified": True,
                      "description": "Initial jobless claims"},
    "PAYEMS":       {"revision": "revised", "frequency": "monthly", "verified": True,
                      "description": "Nonfarm payroll employment"},
    "INDPRO":       {"revision": "revised", "frequency": "monthly", "verified": True,
                      "description": "Industrial production index"},

    # ── inflation (survey/estimate-based — genuinely revised) ──────────────
    # Both verified 2026-08-12: 73-91% of reference dates revised.
    "CPIAUCSL":     {"revision": "revised", "frequency": "monthly", "verified": True,
                      "description": "CPI, all urban consumers, seasonally adjusted"},
    "PCEPILFE":     {"revision": "revised", "frequency": "monthly", "verified": True,
                      "description": "Core PCE price index"},

    # ── liquidity / policy ──────────────────────────────────────────────────
    # WALCL, DFF verified 2026-08-12: 0% revision rate.
    "WALCL":        {"revision": "none", "frequency": "weekly", "verified": True,
                      "description": "Fed total assets (H.4.1 balance sheet, accounting snapshot)"},
    "M2SL":         {"revision": "revised", "frequency": "monthly", "verified": True,
                      "description": "M2 money stock (seasonal-factor re-benchmarking revisions)"},
    # DFF verified 2026-08-12: 0% revision rate (4,240 reference dates).
    "DFF":          {"revision": "none", "frequency": "daily", "verified": True,
                      "description": "Effective federal funds rate"},
}


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
    leaks in.

    CORRECTED 2026-08-12 (see docs/GAPS.md #2): this fallback returns
    FULLY-REVISED data, not a point-in-time read — it is only safe for a
    series with SERIES_REGISTRY[series_id]["revision"] == "none". The
    previous version of this docstring asserted that was true for both NFCI
    and T10Y2Y; measured directly against the cache, it's true for T10Y2Y
    (0 of 12,132 reference dates ever revised) but FALSE for NFCI (75.4% of
    reference dates revised, one week by ~30%). A `revision: "revised"`
    series taking this path now gets `fallback_revised=True` stamped on its
    rows so a contaminated read is auditable instead of invisible, and a
    warning is printed once per (series_id, asof).
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

    fallback_used = False
    if r.status_code == 400 and "does not exist in ALFRED" in r.text:
        fallback_used = True
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

    if fallback_used and SERIES_REGISTRY.get(series_id, {}).get("revision") == "revised":
        print(f"  WARNING: {series_id}@{asof_s} pre-dates its ALFRED vintage "
              f"archive and this series IS genuinely revised — the fallback "
              f"read below is fully-revised data, not point-in-time.")

    obs = r.json().get("observations", [])
    rows = [(series_id, asof_s, o["date"],
             np.nan if o["value"] == "." else float(o["value"]), fallback_used)
            for o in obs]
    return pd.DataFrame(rows, columns=["series_id", "asof", "date", "value", "fallback_revised"])


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


_CACHE_COLUMNS = ["series_id", "asof", "date", "value", "fallback_revised"]


def _load_mem_index(cache_path: Path) -> dict[tuple[str, str], pd.DataFrame]:
    """Load (or lazily migrate) the on-disk vintage cache into the in-process
    index, deduped on read.

    2026-08-12 fix (docs/GAPS.md #1): the cache previously accumulated
    429,654 exact-duplicate (series_id, asof, date) rows across 100 vintages
    (2000-01-31..2002-10-31), silently doubling `vintage_series`'s returned
    index and halving every rolling-window computation over that span —
    including the evidence behind a rejected strategy variant, see
    docs/decisions/0003-market-proxies-over-fred-releases.md. Deduping here
    self-heals any process that loads the (still-corrupted-on-disk, until
    `repair_vintage_cache` runs once) file; deduping again in the write path
    below stops the corruption recurring.
    """
    key = str(cache_path)
    if key not in _MEM_INDEX:
        if cache_path.exists():
            full = pd.read_parquet(cache_path)
            if "fallback_revised" not in full.columns:
                full["fallback_revised"] = False   # migrate pre-2026-08-12 cache rows
            full = full.drop_duplicates(subset=["series_id", "asof", "date"])
        else:
            full = pd.DataFrame(columns=_CACHE_COLUMNS)
        idx: dict[tuple[str, str], pd.DataFrame] = {}
        for (sid, asof_s), grp in full.groupby(["series_id", "asof"], sort=False):
            idx[(sid, asof_s)] = grp
        _MEM_INDEX[key] = idx
        _MEM_FULL[key]  = full
    return _MEM_INDEX[key]


def _fetch_full_series(series_id: str, observation_start: str, api_key: str) -> pd.DataFrame:
    """One-time, non-vintaged pull of a `revision: "none"` series' entire
    history — provably equivalent to per-asof vintaging for a series that is
    never revised (nothing to be point-in-time ABOUT), and ~319x cheaper
    (one API call instead of one per cached asof). Cached under the sentinel
    asof `_NO_REVISION_ASOF` in the SAME parquet file/index as every other
    vintage, so no separate cache format or migration path is needed.
    """
    params = dict(series_id=series_id, api_key=api_key, file_type="json",
                  observation_start=observation_start)
    r = None
    for attempt in range(4):
        r = requests.get(_BASE, params=params, timeout=_TIMEOUT_S)
        if r.status_code < 500:
            break
        time.sleep(2 ** attempt)
    if r.status_code != 200:
        raise RuntimeError(f"FRED API error {r.status_code} for "
                          f"{series_id}@ALL: {r.text[:200]}")
    obs = r.json().get("observations", [])
    rows = [(series_id, _NO_REVISION_ASOF, o["date"],
             np.nan if o["value"] == "." else float(o["value"]), False)
            for o in obs]
    return pd.DataFrame(rows, columns=_CACHE_COLUMNS)


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

    `SERIES_REGISTRY[series_id]["revision"] == "none"` series take a cost
    shortcut: pull the whole history ONCE (`_fetch_full_series`, cached under
    the `_NO_REVISION_ASOF` sentinel) and slice locally to `date <= asof` —
    provably identical to per-asof vintaging when the series is never
    revised. Series absent from the registry, or registered `"revised"`,
    always take the real per-asof vintage path.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / _CACHE_FILE
    cache_key  = str(cache_path)
    asof_s = pd.Timestamp(asof).strftime("%Y-%m-%d")

    idx = _load_mem_index(cache_path)
    no_revision = SERIES_REGISTRY.get(series_id, {}).get("revision") == "none"
    lookup = (series_id, _NO_REVISION_ASOF) if no_revision else (series_id, asof_s)
    hit = idx.get(lookup)
    if hit is None:
        if api_key is None:
            api_key = get_api_key(project_root)
        fresh = (_fetch_full_series(series_id, observation_start, api_key) if no_revision
                 else _fetch_vintage(series_id, asof, observation_start, api_key))
        idx[lookup] = fresh
        merged = (fresh.copy() if _MEM_FULL[cache_key].empty
                  else pd.concat([_MEM_FULL[cache_key], fresh], ignore_index=True))
        # Write-side dedupe (docs/GAPS.md #1): stops the read-side corruption
        # this module used to silently accumulate from ever recurring.
        _MEM_FULL[cache_key] = merged.drop_duplicates(subset=["series_id", "asof", "date"])
        _atomic_to_parquet(_MEM_FULL[cache_key], cache_path)
        hit = fresh

    if no_revision:
        hit = hit[pd.to_datetime(hit["date"]) <= pd.Timestamp(asof)]

    s = hit.set_index("date")["value"].copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    # Regression guard (docs/GAPS.md #1): deliberately NOT silently deduped
    # here — the read/write-path dedupes above are the real, permanent fix.
    # This assert exists to fail loudly if a future change ever bypasses
    # both of them, rather than let a doubled index quietly halve every
    # rolling-window computation downstream the way the original bug did.
    assert s.index.is_unique, (
        f"vintage_series({series_id}@{asof_s}) returned a duplicated index — "
        f"the cache dedupe regressed. This class of bug is silent: every "
        f"rolling-window computation over the affected span gets halved "
        f"without raising. See docs/GAPS.md #1.")
    return s


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


# ─────────────────────────────────────────────────────────────────────────────
#  Cache repair + registry verification (docs/GAPS.md #1-2)
# ─────────────────────────────────────────────────────────────────────────────

def repair_vintage_cache(cache_dir: Path) -> dict:
    """One-time repair of the on-disk vintage cache: dedupe on
    (series_id, asof, date) and re-write atomically. Lossless — every
    duplicate group's rows agree on `value` (verified 2026-08-12 against the
    live cache: 0 of 100 affected vintage groups disagreed), so this can
    never change a value, only remove exact repeats. Safe to run any number
    of times; a no-op once the cache is clean. The in-process reader
    (`_load_mem_index`) already self-heals a corrupted-on-disk file for the
    current process — this additionally fixes the file itself, and every
    other process/session sharing this cache.
    """
    cache_path = Path(cache_dir) / _CACHE_FILE
    if not cache_path.exists():
        return {"rows_before": 0, "rows_after": 0, "duplicates_removed": 0}
    df = pd.read_parquet(cache_path)
    if "fallback_revised" not in df.columns:
        df["fallback_revised"] = False
    before = len(df)
    deduped = df.drop_duplicates(subset=["series_id", "asof", "date"])
    after = len(deduped)
    if after != before:
        _atomic_to_parquet(deduped, cache_path)
    # Invalidate any in-process cache for this path so a subsequent read
    # in the SAME process sees the repaired file rather than a stale index
    # built before the repair.
    key = str(cache_path)
    _MEM_INDEX.pop(key, None)
    _MEM_FULL.pop(key, None)
    return {"rows_before": before, "rows_after": after, "duplicates_removed": before - after}


def verify_revision_rate(
    series_id:         str,
    observation_start: str,
    api_key:           str | None = None,
    project_root:      Path | None = None,
    n_samples:          int = 8,
) -> dict:
    """Empirically measure how often `series_id` is revised, by pulling a
    sample of REALTIME vintages directly (bypassing SERIES_REGISTRY entirely,
    including any `revision: "none"` shortcut) and comparing each reference
    date's value across the sampled vintages. This is the check that would
    have caught the NFCI misclassification this module shipped with for a
    week (docs/GAPS.md #2) — a registry entry is a claim, this is the
    measurement that either backs it up or contradicts it.

    Does not touch the on-disk vintage cache — these are throwaway probe
    calls, not point-in-time reads meant to be reused by a backtest.
    """
    if api_key is None:
        api_key = get_api_key(project_root)
    end = pd.Timestamp.today().normalize()
    sample_asofs = pd.date_range(end - pd.DateOffset(years=n_samples - 1), end, periods=n_samples)

    frames = []
    for d in sample_asofs:
        raw = _fetch_vintage(series_id, d, observation_start, api_key)
        if not raw.empty:
            frames.append(raw)
    if not frames:
        return {"series_id": series_id, "reference_dates": 0, "revised": 0,
                "revision_rate": None, "note": "no observations returned for any sampled vintage"}

    all_df = pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["series_id", "asof", "date"])
    n_distinct = all_df.groupby("date")["value"].nunique(dropna=False)
    revised = int((n_distinct > 1).sum())
    total = len(n_distinct)
    registered = SERIES_REGISTRY.get(series_id, {}).get("revision")
    rate = revised / total if total else 0.0
    measured = "revised" if rate > 0.0 else "none"
    return {
        "series_id":        series_id,
        "reference_dates":  total,
        "revised":          revised,
        "revision_rate":    rate,
        "n_vintages_sampled": len(sample_asofs),
        "registry_says":    registered,
        "measurement_says": measured,
        "agrees_with_registry": (registered == measured) if registered else None,
    }
