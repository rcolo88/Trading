"""Bridge to the sibling **Fundamental Scanner** project.

The scanner (``../Fundamental Scanner``) ranks a quality universe and writes
``outputs/opportunities_YYYYMMDD.json`` — a list of dicts with ``ticker``,
``opportunity_score``, ``qarp_score``, ``tier``, ``sector``, ``market_cap``, ``gates_passed`` and a
nested ``signals`` block (f_score, gross_profitability, earnings_yield, shareholder_yield, …).

This module is the *what to own* feed for the Trend Reversal *when to own it* overlay. It only
reads the scanner's output files — it never re-runs the scan — so it has no extra dependencies and
cannot stale the scanner's cache.

NOTE on honesty: the scanner scores stocks on **today's** fundamentals, so any basket it returns is
forward-looking only. Backtesting the *selection* over history would be hindsight bias (we have no
point-in-time fundamentals). The overlay scripts therefore measure the *timing* contribution
separately and validate on a non-hindsight proxy. See ``scripts/09_scanner_overlay.py``.
"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass

# Default location of the sibling project, relative to this repo's root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SCANNER_DIR = os.path.normpath(os.path.join(_REPO_ROOT, "..", "Fundamental Scanner"))


@dataclass
class Candidate:
    ticker: str
    score: float          # opportunity_score (0-100, higher = better quality/value)
    qarp: float           # quality-at-reasonable-price score
    tier: str             # Compounder / Cash Return / Rising Quality / Neutral / ...
    sector: str
    market_cap: float
    gates_passed: bool
    signals: dict         # raw signal block (f_score, earnings_yield, etc.)

    @property
    def f_score(self) -> int | None:
        return self.signals.get("f_score")

    @property
    def earnings_yield(self) -> float | None:
        return self.signals.get("earnings_yield")


def latest_scan(scanner_dir: str | None = None) -> str:
    """Return the path to the newest ``opportunities_*.json`` the scanner has written."""
    d = scanner_dir or DEFAULT_SCANNER_DIR
    pattern = os.path.join(d, "outputs", "opportunities_*.json")
    files = [f for f in glob.glob(pattern) if "red" not in f and "top" not in f]
    if not files:
        raise FileNotFoundError(
            f"No scanner output found under {pattern}. Run the Fundamental Scanner first "
            f"(python main_quality_analysis.py --score-only)."
        )
    # File names are date-stamped (opportunities_YYYYMMDD.json) so lexicographic == chronological.
    return max(files)


def load_candidates(path: str | None = None, scanner_dir: str | None = None) -> list[Candidate]:
    """Load every scored ticker from a scanner JSON (defaults to the latest), ranked by score desc."""
    path = path or latest_scan(scanner_dir)
    with open(path) as fh:
        raw = json.load(fh)
    out = [
        Candidate(
            ticker=row["ticker"],
            score=float(row.get("opportunity_score") or 0.0),
            qarp=float(row.get("qarp_score") or 0.0),
            tier=row.get("tier", ""),
            sector=row.get("sector", ""),
            market_cap=float(row.get("market_cap") or 0.0),
            gates_passed=bool(row.get("gates_passed", False)),
            signals=row.get("signals", {}) or {},
        )
        for row in raw
    ]
    out.sort(key=lambda c: c.score, reverse=True)
    return out


def top_candidates(
    n: int = 10,
    require_gates: bool = True,
    path: str | None = None,
    scanner_dir: str | None = None,
) -> list[Candidate]:
    """Top-``n`` candidates by opportunity score, optionally restricted to names that pass all gates.

    ``require_gates=True`` mirrors the scanner's own shortlist logic — only names that clear the hard
    quality gates (F-score, asset growth, accruals, Beneish M, Altman Z, interest coverage) qualify.
    """
    cands = load_candidates(path, scanner_dir)
    if require_gates:
        cands = [c for c in cands if c.gates_passed]
    return cands[:n]
