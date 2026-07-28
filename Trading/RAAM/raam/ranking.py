"""Total Rank: combine (M), (V), (C), (T) into a monthly 5-name selection.

TOTAL RANK = wM*Rank(M) + wV*Rank(V) + wC*Rank(C) - T + M/x   (Giordano 2018, Sec. V)
Take the 5 LOWEST Total Rank names.

RESOLVED AMBIGUITY — rank direction. The paper's prose is internally
inconsistent: it says Rank(M) is "ascending" while Rank(V)/Rank(C) are
"descending," yet also says (a) the 5 LOWEST Total Rank names are chosen and
(b) "the lower the volatility of an asset... the higher its ranking." Those
cannot all be true together. The only self-consistent reading — the one under
which -T correctly REWARDS an uptrend (a confirmed breakout, T=+2, must LOWER
the Total Rank to help it win) and lower vol correctly wins — is "rank 1 =
best" for all three components: highest M, lowest V, lowest C. That is the
default (`ranking.convention: rank1_best`). The literal-paper-text reading is
also implemented (`ranking.convention: paper_literal`) purely so the
alternative is testable, not asserted as correct.

RESOLVED AMBIGUITY — tiebreak sign. The paper adds "+M/x" as a tie-breaker
"to avoid equal ranks," with x undisclosed. Taken completely literally, a
higher M would very slightly *raise* Total Rank (worse) in a tie — backwards
relative to "higher M is better" under the rank1_best convention. Default
flips the sign (`ranking.tiebreak_sign: -1`) so ties favor higher momentum,
consistent with the resolved rank convention; `+1` recovers the literal text.
Since x is large (default 1000, config `ranking.tiebreak_x`), this only ever
decides EXACT ties and never overturns a genuine rank difference.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from raam import universe as univ_mod


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last actual trading day of each calendar month present in `index`.

    Matches the paper's own cadence: "classification is done on a monthly
    basis, taking the last value of the month."

    Deliberately NOT `index.to_series().resample("ME").last()`: that treats
    whatever the LAST row of a possibly-in-progress month happens to be as if
    it were the month's close — e.g. if `index` ends 2026-07-17 (mid-July),
    resample("ME") would misclassify 2026-07-17 itself as July's month-end and
    trigger a rebalance two weeks early. Instead, generate the canonical
    business-month-end calendar and only emit one once the panel's data
    actually reaches it; `pd.date_range(..., end=index.max())` naturally
    excludes any month whose real end is still in the future.
    """
    if len(index) == 0:
        return pd.DatetimeIndex([])
    canonical = pd.date_range(index.min(), index.max(), freq="BME")
    out = []
    for me in canonical:
        avail = index[index <= me]
        if len(avail):
            out.append(avail[-1])   # last ACTUAL trading day at/before the canonical month-end
    return pd.DatetimeIndex(sorted(set(out)))


def _apply_ranks(m: pd.Series, v: pd.Series, c: pd.Series,
                 convention: str) -> tuple[pd.Series, pd.Series, pd.Series]:
    if convention == "paper_literal":
        rank_M = m.rank(ascending=True,  method="min")
        rank_V = v.rank(ascending=False, method="min")
        rank_C = c.rank(ascending=False, method="min")
    else:  # "rank1_best" (default, resolved convention — see module docstring)
        rank_M = m.rank(ascending=False, method="min")
        rank_V = v.rank(ascending=True,  method="min")
        rank_C = c.rank(ascending=True,  method="min")
    return rank_M, rank_V, rank_C


def compute_total_rank(
    indicators: dict[str, pd.DataFrame],
    close:      pd.DataFrame,
    cfg:        dict,
    tickers:    list[str] | None = None,
    eligible_fn=None,
) -> pd.DataFrame:
    """Per-rebalance-date Total Rank for every eligible ticker.

    Returns a (rebal_dates x tickers) DataFrame; NaN where a ticker is not
    eligible (per `eligible_fn`) or an indicator hasn't warmed up yet.
    Lower Total Rank = better under the default convention.

    `tickers`/`eligible_fn` default to RAAM's native 7Twelve universe
    (`univ_mod.RANKABLE` / `univ_mod.eligible_on`) — pass alternatives to run
    the identical Total Rank mechanism over a different universe (e.g. an
    S&P 1500 point-in-time eligibility function) without touching this
    function's default behavior. `eligible_fn` must have the same signature
    as `universe.eligible_on`: `(close, date, min_history_days) -> list[str]`.
    """
    rcfg = cfg.get("ranking", {})
    wM = float(rcfg.get("wM", 1.0 / 3.0))
    wV = float(rcfg.get("wV", 1.0 / 3.0))
    wC = float(rcfg.get("wC", 1.0 / 3.0))
    x             = float(rcfg.get("tiebreak_x", 1000.0))
    tiebreak_sign = float(rcfg.get("tiebreak_sign", -1.0))
    convention    = str(rcfg.get("convention", "rank1_best"))
    min_hist      = int(cfg.get("universe", {}).get("min_history_days", 252))

    tickers     = tickers if tickers is not None else univ_mod.RANKABLE
    eligible_fn = eligible_fn if eligible_fn is not None else univ_mod.eligible_on

    M, V, C, T = indicators["M"], indicators["V"], indicators["C"], indicators["T"]

    dates = month_end_dates(close.index)
    dates = dates[dates.isin(M.index)]

    out = pd.DataFrame(np.nan, index=dates, columns=tickers)
    for d in dates:
        elig = eligible_fn(close, d, min_history_days=min_hist)
        elig = [t for t in elig if t in M.columns]
        if not elig:
            continue
        m, v, c, t = M.loc[d, elig], V.loc[d, elig], C.loc[d, elig], T.loc[d, elig]
        valid = m.notna() & v.notna() & c.notna() & t.notna()
        elig  = [tk for tk in elig if bool(valid.get(tk, False))]
        if not elig:
            continue
        m, v, c, t = m[elig], v[elig], c[elig], t[elig]

        rank_M, rank_V, rank_C = _apply_ranks(m, v, c, convention)
        total = (wM * rank_M + wV * rank_V + wC * rank_C - t
                 + tiebreak_sign * (m / x))
        out.loc[d, elig] = total.values
    return out


def select_book(total_rank: pd.DataFrame, n_select: int = 5) -> pd.DataFrame:
    """Boolean (rebal_dates x tickers): the n_select lowest-Total-Rank names per date.

    Fewer than n_select eligible candidates on a date (early history, before
    the universe has 5 available tickers) selects however many exist — the
    caller (portfolio.py) still applies 20%-per-slot sizing to whatever count
    comes back, per the paper's mechanics (no artificial padding to 5).
    """
    picks = pd.DataFrame(False, index=total_rank.index, columns=total_rank.columns)
    for d in total_rank.index:
        row = total_rank.loc[d].dropna()
        if row.empty:
            continue
        chosen = row.nsmallest(min(n_select, len(row))).index
        picks.loc[d, chosen] = True
    return picks
