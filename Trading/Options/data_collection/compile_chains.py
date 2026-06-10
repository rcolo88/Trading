"""Assemble the daily logged SPY chains into one backtestable dataset.

`chain_logger.py` drops a snapshot per run into `data/raw/chains/SPY_chain_YYYY-MM-DD[_HHMM].csv`,
but nothing consumed them. This rolls them up into the canonical
`data/processed/SPY_real_options_<min>_<max>.csv` that `load_sample_spy_options_data` reads under
`data_source.mode: real`. Unlike the sparse DoltHub dump, these are the *full* chain you actually
trade (every quoted strike), so they persist day-to-day and suit multi-day calendars.

Rules:
  * Multiple intraday snapshots per day -> keep the LATEST (afternoon ~15:00) as the EOD mark.
  * Dedupe by (quote_date, expiration, strike, option_type).
  * Backfill a `vix` column from yfinance ^VIX for any snapshot logged before VIX capture existed.

    opt_venv/bin/python data_collection/compile_chains.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.data_fetchers.real_chain_loader import CANONICAL_COLS, _fetch_underlying  # noqa: E402

RAW_DIR = _PROJECT_ROOT / "data" / "raw" / "chains"
PROCESSED_DIR = _PROJECT_ROOT / "data" / "processed"
# Sort key so the latest intraday snapshot of a day wins: date, then HHMM (no-time files sort first).
_STAMP = re.compile(r"SPY_chain_(\d{4}-\d{2}-\d{2})(?:_(\d{4}))?\.csv$")


def _snapshot_order(path: Path):
    m = _STAMP.search(path.name)
    return (m.group(1), m.group(2) or "0000") if m else (path.name, "")


def compile_chains(verbose: bool = True) -> Path:
    files = sorted(RAW_DIR.glob("SPY_chain_*.csv"), key=_snapshot_order)
    if not files:
        raise FileNotFoundError(f"No logged chains in {RAW_DIR}. Run chain_logger.py first.")

    frames = []
    for f in files:
        df = pd.read_csv(f)
        df["quote_date"] = pd.to_datetime(df["quote_date"]).dt.normalize()
        df["expiration"] = pd.to_datetime(df["expiration"]).dt.normalize()
        frames.append(df)
    allrows = pd.concat(frames, ignore_index=True)

    # Latest snapshot wins: files are processed in time order, so keep the last occurrence.
    allrows = allrows.drop_duplicates(
        subset=["quote_date", "expiration", "strike", "option_type"], keep="last"
    )

    # Backfill VIX where missing (older snapshots predate VIX capture in the logger).
    if "vix" not in allrows.columns or allrows["vix"].isna().any():
        lo = allrows["quote_date"].min().strftime("%Y-%m-%d")
        hi = allrows["quote_date"].max().strftime("%Y-%m-%d")
        und = _fetch_underlying(lo, hi)
        vix_by_date = und["vix"]
        vix_by_date.index = pd.to_datetime(vix_by_date.index).normalize()
        filled = allrows["quote_date"].map(vix_by_date)
        allrows["vix"] = allrows["vix"].fillna(filled) if "vix" in allrows.columns else filled

    # Conform to the canonical schema (add any missing optional columns as NA, order them).
    for col in CANONICAL_COLS:
        if col not in allrows.columns:
            allrows[col] = pd.NA
    out = allrows[CANONICAL_COLS].sort_values(
        ["quote_date", "expiration", "strike", "option_type"]
    ).reset_index(drop=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    lo = out["quote_date"].min().strftime("%Y-%m-%d")
    hi = out["quote_date"].max().strftime("%Y-%m-%d")
    dest = PROCESSED_DIR / f"SPY_real_options_{lo}_{hi}.csv"
    out.to_csv(dest, index=False)

    if verbose:
        print(f"Compiled {len(files)} snapshots -> {len(out):,} contracts over "
              f"{out['quote_date'].nunique()} day(s) [{lo} .. {hi}]")
        print(f"Saved -> {dest}")
        print(f"Backtest it: set config data_source.mode=real and real_data.start/end to {lo}/{hi}")
    return dest


if __name__ == "__main__":
    compile_chains()
