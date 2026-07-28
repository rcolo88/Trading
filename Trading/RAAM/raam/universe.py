"""The 7Twelve universe: 12 ETFs, one of which (SHY) is a cash sleeve, never ranked.

Roster and sleeve grouping are transcribed from Table 2 ("RAAM: Asset Allocation
updated to 11/28/2017") in Giordano (2018). Unlike Cross-Sectional Momentum's
point-in-time S&P index membership (reconstructed from Wikipedia change tables),
this universe is fixed by construction — the paper always ranks the same 11 ETFs.
The only thing that varies over time is *availability*: some of these ETFs simply
didn't exist for the paper's full 2004 start, and no synthetic/interpolated data
is used to paper over that (see eligible_on below).
"""
from __future__ import annotations

import pandas as pd

# (ticker, sleeve #, sleeve name, full name) — Table 2 order.
ROSTER: list[tuple[str, int, str, str]] = [
    ("VV",   1, "US EQUITIES",                     "Vanguard Large-Cap ETF"),
    ("IJH",  1, "US EQUITIES",                     "iShares Core S&P Mid-Cap ETF"),
    ("IJR",  1, "US EQUITIES",                     "iShares Core S&P Small-Cap ETF"),
    ("EFA",  2, "INTERNATIONAL EQUITIES",          "iShares MSCI EAFE ETF"),
    ("EEM",  2, "INTERNATIONAL EQUITIES",          "iShares MSCI Emerging Markets ETF"),
    ("RWR",  3, "REAL ESTATE",                     "SPDR Dow Jones REIT ETF"),
    ("DBC",  4, "NATURAL RESOURCES - COMMODITIES", "PowerShares DB Commodity Tracking ETF"),
    ("VAW",  4, "NATURAL RESOURCES - COMMODITIES", "Vanguard Materials ETF"),
    ("AGG",  5, "US BONDS - INFLATION PROTECTED",  "iShares Core US Aggregate Bond ETF"),
    ("TIP",  5, "US BONDS - INFLATION PROTECTED",  "iShares TIPS Bond ETF"),
    ("IGOV", 6, "INTERNATIONAL BONDS",              "iShares International Treasury Bond ETF"),
    ("SHY",  7, "CASH",                             "iShares 1-3 Year Treasury Bond ETF"),
]

CASH_TICKER = "SHY"
RANKABLE    = [t for t, *_ in ROSTER if t != CASH_TICKER]   # the 11 ranked 1..11
ALL_TICKERS = [t for t, *_ in ROSTER]                        # all 12, incl. cash sleeve
SLEEVE      = {t: name for t, _, name, _ in ROSTER}
FULL_NAME   = {t: name for t, _, _, name in ROSTER}
SLEEVE_NUM  = {t: n for t, n, _, _ in ROSTER}

# Benchmark ticker (not part of the 7Twelve roster).
SPY = "SPY"


def eligible_on(close: pd.DataFrame, date: pd.Timestamp,
                min_history_days: int = 252) -> list[str]:
    """Rankable tickers with >= min_history_days of real closes at/before `date`.

    Real inception dates (verified via yfinance, auto_adjust=True):
      VV/VAW 2004-01-30, IJH/IJR 2000-05-26, EFA/RWR 2001-08-27, EEM 2003-04-14,
      AGG 2003-09-29, TIP 2003-12-05, DBC 2006-02-06, IGOV 2009-01-30.
    Rather than hard-coding those dates, eligibility is read directly off the
    downloaded price panel — the same "ask the data, don't assert a date" pattern
    as csm/universe.py's PIT membership, just keyed on inception instead of index
    membership. This is what keeps the 2004-2006 window honest: DBC and IGOV are
    mechanically absent from the ranking pool until they have real prices, so nothing
    stands in for them and no interpolated/backfilled series can silently reappear.
    """
    if date not in close.index:
        return []
    hist = close.loc[:date]
    out = []
    for t in RANKABLE:
        if t not in hist.columns:
            continue
        col = hist[t]
        if pd.isna(col.iloc[-1]):
            continue
        if int(col.notna().sum()) >= min_history_days:
            out.append(t)
    return out
