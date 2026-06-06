"""Realistic fill model for multi-leg option spreads.

Fills are expressed as a fraction of the way from MID toward the natural price (the ask when we
buy, the bid when we sell). This matches industry practice (e.g. ORATS backtests assume a fill
~56-75% of the bid/ask width, not the mid and not the full spread):

    fraction = 0.0  -> mid               (optimistic; a patient limit that gets the midpoint)
    fraction = 0.5  -> halfway to natural (a normal working limit on a liquid name)
    fraction = 1.0  -> the natural price  (a market / marketable order that crosses the whole spread)

We use a LIMIT fraction for planned entries and exits (profit target, scheduled/DTE close) and a
MARKET fraction for stop-loss exits — because the user cannot place stop-limit orders, a stop is a
discretionary market order that crosses the spread. ``extra`` is an optional flat per-leg haircut on
top (default 0) for genuinely illiquid names.

A spread is a list of legs ``(bid, ask, is_long)``:
  * ``net_open``  — signed cash to OPEN  (>0 = net debit paid, <0 = net credit received)
  * ``net_close`` — signed cash to CLOSE (reverse every leg)
Per-share P&L is ``net_close - net_open`` for any structure (debit, credit, calendar, condor).
"""
from __future__ import annotations

from typing import Iterable, Tuple

Leg = Tuple[float, float, bool]  # (bid, ask, is_long)


def _fill(bid: float, ask: float, buy: bool, fraction: float, extra: float) -> float:
    """Transaction price for one leg: cross ``fraction`` of the half-spread, plus a flat ``extra``."""
    mid = 0.5 * (bid + ask)
    half = 0.5 * (ask - bid)
    px = mid + fraction * half if buy else mid - fraction * half
    return px * (1 + extra) if buy else px * (1 - extra)


def net_open(legs: Iterable[Leg], fraction: float = 0.5, extra: float = 0.0) -> float:
    """Signed cash paid to open the spread, per share. Long legs are bought, shorts are sold."""
    return sum(_fill(b, a, is_long, fraction, extra) * (1 if is_long else -1) for b, a, is_long in legs)


def net_close(legs: Iterable[Leg], fraction: float = 0.5, extra: float = 0.0) -> float:
    """Signed cash received to close the spread, per share. Longs are sold, shorts bought back."""
    return sum(_fill(b, a, not is_long, fraction, extra) * (1 if is_long else -1) for b, a, is_long in legs)
