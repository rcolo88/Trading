"""Fixed-rule (non-fitted) market-regime labels and entry gates.

Every threshold here is a literature convention (VIX bands, tastytrade IV-rank 50, SPY Trend
Reversal state), not something optimized on this backtest's data — same "adds no degrees of
freedom" property as `vix_gate.vix_rank_gate`. Regimes are defined off observable market state
(VIX complex, SPY trend), not macro labels: market state is causal, available daily, and already
impounds the macro backdrop the strategy actually trades against.

Reuses `vix_gate._load_vix` / `vix_gate.vix_iv_rank` and `trend_gate.spy_trend_state` — this
module only adds labeling/binning and gate composition on top.
"""
from __future__ import annotations

from typing import Callable, Dict, Iterable

import pandas as pd

from .vix_gate import _load_vix, vix_iv_rank
from .trend_gate import spy_trend_state


def vix_level_regime(start: str, end: str, warmup_days: int = 30) -> pd.Series:
    """Daily label from same-day VIX close: 'calm' (<15) / 'normal' (15-25) / 'stress' (>=25).

    Same-day (not lagged): matches the engine's existing absolute VIX entry filter convention
    (it reads that day's `vix` column directly), so this label is consistent with how vix_min/
    vix_max gates already behave.
    """
    warm_start = (pd.Timestamp(start) - pd.Timedelta(days=warmup_days)).strftime("%Y-%m-%d")
    vix = _load_vix(warm_start, end).loc[pd.Timestamp(start):pd.Timestamp(end)]
    labels = pd.cut(vix, bins=[-float("inf"), 15, 25, float("inf")],
                     labels=["calm", "normal", "stress"])
    return labels.rename("vix_level_regime")


def vix_rank_regime(start: str, end: str, window: int = 252, warmup_days: int = 420,
                     threshold: float = 50.0) -> pd.Series:
    """Daily label from trailing VIX IV-Rank: 'low' (<threshold) / 'high' (>=threshold).

    threshold=50 is the tastytrade convention (IVR>=50 favors premium selling).
    """
    rank = vix_iv_rank(start, end, window=window, warmup_days=warmup_days)
    labels = rank.apply(lambda r: "high" if pd.notna(r) and r >= threshold else
                         ("low" if pd.notna(r) else None))
    return labels.rename("vix_rank_regime")


def trend_regime(end: str, start_warmup: str = "2005-01-01") -> pd.Series:
    """Daily label from the (already-lagged, causal) SPY Trend Reversal state: bull/bear/neutral."""
    state = spy_trend_state(end, start_warmup)
    labels = state.map({1: "bull", -1: "bear", 0: "neutral"})
    return labels.rename("trend_regime")


def composite_regime(start: str, end: str) -> pd.DataFrame:
    """Merge VIX-level and trend labels into one daily frame plus a 3-way composite column.

    composite: 'risk-on' (bull trend AND VIX<25) / 'stress' (VIX>=25 OR bear trend) / 'chop' (else).
    Returns a DataFrame indexed by date with columns [vix_level_regime, trend_regime, composite].
    """
    vix_lbl = vix_level_regime(start, end)
    trend_lbl = trend_regime(end).loc[pd.Timestamp(start):pd.Timestamp(end)]
    df = pd.concat([vix_lbl, trend_lbl], axis=1)

    def _composite(row) -> str:
        if row["vix_level_regime"] == "stress" or row["trend_regime"] == "bear":
            return "stress"
        if row["trend_regime"] == "bull" and row["vix_level_regime"] in ("calm", "normal"):
            return "risk-on"
        return "chop"

    df["composite"] = df.apply(_composite, axis=1)
    return df


def vix_max_gate(start: str, end: str, max_vix: float, warmup_days: int = 30) -> Callable:
    """Return ``callable(date) -> bool`` allowing a new entry only when same-day VIX <= max_vix.

    A one-off absolute threshold (e.g. 30) that doesn't line up with `vix_level_regime`'s fixed
    15/25 bins — kept separate rather than overloading that binning.
    """
    warm_start = (pd.Timestamp(start) - pd.Timedelta(days=warmup_days)).strftime("%Y-%m-%d")
    vix = _load_vix(warm_start, end).loc[pd.Timestamp(start):pd.Timestamp(end)]
    by_day = {d.normalize(): float(v) for d, v in vix.items()}

    def _gate(date) -> bool:
        v = by_day.get(pd.Timestamp(date).normalize())
        return True if v is None else v <= max_vix

    return _gate


def regime_gate(labels: pd.Series, allowed: Iterable[str]) -> Callable:
    """Build a ``callable(date) -> bool`` entry gate: True only when `labels` on that date is
    in `allowed`. Drop-in for ``OptopsyBacktester(config, entry_gate=...)``, composable like the
    other fixed gates in this package.

    A date missing from `labels` (data gap) is allowed through, matching `vix_rank_gate`'s
    "never silently blocks the whole backtest on a data gap" convention.
    """
    allowed = set(allowed)
    by_day = {pd.Timestamp(d).normalize(): v for d, v in labels.items() if pd.notna(v)}

    def _gate(date) -> bool:
        v = by_day.get(pd.Timestamp(date).normalize())
        return True if v is None else v in allowed

    return _gate


def current_regime() -> Dict[str, object]:
    """Print + return today's VIX level, IV-rank, trend state, and composite regime label.

    The "what regime are we in right now" readout — answers the motivating question directly
    rather than only comparing historical regime buckets.
    """
    today = pd.Timestamp.today().normalize()
    end = today.strftime("%Y-%m-%d")
    start = (today - pd.Timedelta(days=10)).strftime("%Y-%m-%d")

    vix = _load_vix((today - pd.Timedelta(days=40)).strftime("%Y-%m-%d"), end)
    vix_today = float(vix.iloc[-1])
    vix_date = vix.index[-1]

    rank = vix_iv_rank(start, end, warmup_days=420)
    rank_today = float(rank.dropna().iloc[-1]) if rank.dropna().size else float("nan")

    trend = spy_trend_state(end)
    trend_today = trend.iloc[-1] if len(trend) else 0
    trend_label = {1: "bull", -1: "bear", 0: "neutral"}[int(trend_today)]

    vix_label = "calm" if vix_today < 15 else ("stress" if vix_today >= 25 else "normal")
    rank_label = "high" if pd.notna(rank_today) and rank_today >= 50 else "low"
    if vix_label == "stress" or trend_label == "bear":
        composite = "stress"
    elif trend_label == "bull" and vix_label in ("calm", "normal"):
        composite = "risk-on"
    else:
        composite = "chop"

    out = {
        "as_of": str(vix_date.date()),
        "vix": vix_today,
        "vix_level_regime": vix_label,
        "vix_iv_rank": rank_today,
        "vix_rank_regime": rank_label,
        "trend_regime": trend_label,
        "composite": composite,
    }
    print(f"Regime as of {out['as_of']}:")
    print(f"  VIX = {vix_today:.2f} ({vix_label})")
    print(f"  VIX IV-Rank = {rank_today:.1f} ({rank_label})" if pd.notna(rank_today)
          else "  VIX IV-Rank = n/a")
    print(f"  SPY trend = {trend_label}")
    print(f"  Composite regime = {composite}")
    return out
