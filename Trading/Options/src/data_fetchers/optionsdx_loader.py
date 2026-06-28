"""Convert OptionsDX historical EOD option-chain files into the project's long format.

OptionsDX (https://www.optionsdx.com) ships SPY EOD chains as monthly text files
(``spy_eod_YYYYMM.txt``), one row per (quote_date, expiration, strike) carrying BOTH the
call and put in a single WIDE row (``C_*`` / ``P_*`` columns). The rest of this codebase
expects a LONG format (one row per contract, with an ``option_type`` column) identical to
what ``real_chain_loader`` writes for DoltHub — see ``synthetic_generator._read_options_csv``.

Why this dataset matters: DoltHub's free SPY sample lists only ~3 expirations/day at
irregular DTEs, so a calendar's exact near+far legs are almost never both quoted, forcing the
backtester to MODEL ~96% of its daily marks off a fitted IV surface (which the optimizer then
games). OptionsDX EOD carries ~30 expirations/day and ~240 strikes/day out past a year, so the
exact contracts ARE quoted every trading day — the marks become real quotes, not a model.

This converter:
  * globs every ``spy_eod_*.txt`` under the raw dir (drop new yearly downloads in and re-run),
  * melts each wide row into a call row + a put row,
  * recomputes integer ``dte`` = (expiration - quote_date).days for consistency with the rest
    of the pipeline (OptionsDX's own DTE is fractional, measured to the expiry timestamp),
  * trims to a near-ATM / bounded-DTE band by default (the strategies only use <=~120 DTE,
    near-ATM strikes) to keep the file workable — widen via flags for wider-wing strategies,
  * merges ^VIX (yfinance) onto each quote_date so the strategies' VIX filters work,
  * writes ``data/processed/SPY_real_options_<start>_<end>.csv`` so the existing
    ``data_source.mode: real`` path loads it with NO further plumbing.

Crucially the OptionsDX bid/ask is genuine exchange quotes (unlike DoltHub's inflated mids),
so set ``data_source.price_from_iv: false`` to BACKTEST THE REAL QUOTES rather than repricing
them off the IV column — the whole point of paying for clean data.

CLI:
    opt_venv/bin/python -m src.data_fetchers.optionsdx_loader \
        --raw-dir data/raw/optionsdx --symbol SPY
"""
from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

# Raw OptionsDX columns (after stripping the "[ ... ]" brackets and surrounding spaces).
_SHARED = {
    "QUOTE_DATE": "quote_date",
    "UNDERLYING_LAST": "underlying_price",
    "EXPIRE_DATE": "expiration",
    "STRIKE": "strike",
}
# Per-side column -> canonical name. Built once for calls and once for puts.
_SIDE = {
    "BID": "bid", "ASK": "ask", "LAST": "last", "VOLUME": "volume",
    "IV": "iv", "DELTA": "delta", "GAMMA": "gamma", "THETA": "theta", "VEGA": "vega",
}
# Final column order — matches the DoltHub real CSV so _read_options_csv is happy.
_OUT_COLS = [
    "quote_date", "underlying_symbol", "underlying_price", "vix", "expiration", "dte",
    "strike", "option_type", "bid", "ask", "last", "volume", "open_interest",
    "iv", "delta", "abs_delta", "gamma", "theta", "vega",
]


def _read_one(path: str) -> pd.DataFrame:
    """Read a single OptionsDX monthly file and melt it into long (call+put) rows."""
    raw = pd.read_csv(path, low_memory=False)  # mixed-type "N x M" size cols — read whole then coerce
    raw.columns = [c.strip().strip("[]") for c in raw.columns]

    out_frames = []
    for side, prefix in (("call", "C_"), ("put", "P_")):
        cols = dict(_SHARED)
        for src, dst in _SIDE.items():
            cols[f"{prefix}{src}"] = dst
        sub = raw[list(cols.keys())].rename(columns=cols).copy()
        sub["option_type"] = side
        out_frames.append(sub)

    df = pd.concat(out_frames, ignore_index=True)

    df["quote_date"] = pd.to_datetime(df["quote_date"])
    df["expiration"] = pd.to_datetime(df["expiration"])
    for c in ("underlying_price", "strike", "bid", "ask", "last", "volume",
              "iv", "delta", "gamma", "theta", "vega"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Integer calendar-day DTE (the convention used everywhere else in the pipeline).
    df["dte"] = (df["expiration"].dt.normalize() - df["quote_date"].dt.normalize()).dt.days
    return df


def _fetch_vix(start: pd.Timestamp, end: pd.Timestamp) -> Optional[pd.Series]:
    """Daily ^VIX close indexed by date, or None if yfinance is unavailable."""
    try:
        import yfinance as yf
    except ImportError:
        print("  ! yfinance not installed — 'vix' column will be NaN")
        return None
    end_excl = (end + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    vix = yf.Ticker("^VIX").history(start=start.strftime("%Y-%m-%d"), end=end_excl, interval="1d")
    if vix.empty:
        print("  ! ^VIX history empty — 'vix' column will be NaN")
        return None
    s = vix["Close"].copy()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s


def convert_optionsdx(
    raw_dir: str = "data/raw/optionsdx",
    symbol: str = "SPY",
    out_dir: str = "data/processed",
    max_dte: int = 120,
    moneyness_band: float = 0.15,
    pattern: str = "spy_eod_*.txt",
) -> str:
    """Convert all OptionsDX monthly files under *raw_dir* to one long-format real CSV.

    Parameters
    ----------
    max_dte : keep only contracts with dte <= this (strategies use <=~66; 120 leaves headroom).
    moneyness_band : keep only |strike/spot - 1| <= this (0.15 = ±15%, covers calendars/verticals/ICs).
                     Set to a large value (e.g. 1.0) to keep the entire chain.

    Returns the written CSV path. The filename matches ``real_data_filename`` so
    ``data_source.mode: real`` loads it with the matching ``real_data`` date range.
    """
    files: List[str] = sorted(glob.glob(os.path.join(raw_dir, pattern)))
    if not files:
        raise FileNotFoundError(f"No OptionsDX files matching {pattern!r} under {raw_dir!r}")
    print(f"Converting {len(files)} OptionsDX file(s) from {raw_dir} ...")

    parts = []
    for f in files:
        df = _read_one(f)
        n0 = len(df)
        # Trim to the useful band so the file stays workable (full chain is ~1.3M rows/yr).
        df = df[df["dte"].between(0, max_dte)]
        mny = (df["strike"] / df["underlying_price"] - 1.0).abs()
        df = df[mny <= moneyness_band]
        print(f"  {os.path.basename(f)}: {n0:,} -> {len(df):,} rows "
              f"(dte<= {max_dte}, |moneyness|<= {moneyness_band:.0%})")
        parts.append(df)

    data = pd.concat(parts, ignore_index=True)
    data = data.dropna(subset=["bid", "ask", "strike", "underlying_price"])
    data = data.sort_values(["quote_date", "expiration", "strike", "option_type"]).reset_index(drop=True)

    # Enrich to the canonical schema.
    data["underlying_symbol"] = symbol
    data["abs_delta"] = data["delta"].abs()
    data["open_interest"] = np.nan  # not provided in this OptionsDX EOD export

    start, end = data["quote_date"].min(), data["quote_date"].max()
    vix = _fetch_vix(start, end)
    if vix is not None:
        data["vix"] = data["quote_date"].dt.normalize().map(vix).astype(float)
        # Forward/back fill the rare missing VIX day so filters never see NaN.
        data["vix"] = data["vix"].ffill().bfill()
    else:
        data["vix"] = np.nan

    data = data[_OUT_COLS]

    out_name = f"{symbol}_real_options_{start.strftime('%Y-%m-%d')}_{end.strftime('%Y-%m-%d')}.csv"
    out_path = Path(out_dir) / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(out_path, index=False)

    print(f"\n✓ Wrote {len(data):,} contracts -> {out_path}")
    print(f"  Date range : {start.date()} to {end.date()}  ({data['quote_date'].nunique()} trading days)")
    print(f"  Expirations: {data['expiration'].nunique()}  |  Calls/Puts: "
          f"{(data['option_type']=='call').sum():,} / {(data['option_type']=='put').sum():,}")
    print(f"\nNext: set config/config.yaml -> real_data.start_date={start.date()}, "
          f"end_date={end.date()}, data_source.mode: real, price_from_iv: false")
    return str(out_path)


def main() -> None:
    p = argparse.ArgumentParser(description="Convert OptionsDX EOD chains to the project's real-data CSV.")
    p.add_argument("--raw-dir", default="data/raw/optionsdx", help="Directory of spy_eod_*.txt files")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--out-dir", default="data/processed")
    p.add_argument("--max-dte", type=int, default=120, help="Keep contracts with dte <= this")
    p.add_argument("--moneyness-band", type=float, default=0.15, help="Keep |strike/spot-1| <= this")
    p.add_argument("--pattern", default="spy_eod_*.txt")
    args = p.parse_args()
    convert_optionsdx(
        raw_dir=args.raw_dir, symbol=args.symbol, out_dir=args.out_dir,
        max_dte=args.max_dte, moneyness_band=args.moneyness_band, pattern=args.pattern,
    )


if __name__ == "__main__":
    main()
