"""Automatic `validation.trial_sharpes` bookkeeping for DSR deflation.

Manually pasting each new sweep's Sharpe into config.yaml was pure discipline —
skip it once and the Deflated Sharpe Ratio silently forgets the selection bias
of the search that picked the current config. This appends programmatically,
preserving every comment/format in config.yaml (round-trip via ruamel.yaml),
and skips values already present so re-running a sweep doesn't duplicate.
"""
from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.preserve_quotes = True


def record_trial_sharpes(config_path: Path, sharpes: list[float],
                         tol: float = 1e-4, section: str = "validation") -> int:
    """Append any of `sharpes` not already present (within `tol`) to
    config.yaml's `<section>.trial_sharpes`. Returns how many were newly added.

    `section` MUST match the strategy being swept: "validation" for the
    equity cross-sectional momentum engine, "blend" for the 3-way blend —
    these are different strategies/search spaces, and mixing their trial
    Sharpes into one list would silently corrupt both DSR computations
    (confirmed this happened once — see memory csm-market-neutral-macro-tests).
    """
    data = _yaml.load(config_path)
    val = data.setdefault(section, {})
    existing = list(val.get("trial_sharpes", []))

    added = 0
    for s in sharpes:
        s = round(float(s), 4)
        if not any(abs(s - e) < tol for e in existing):
            existing.append(s)
            added += 1

    if added:
        val["trial_sharpes"] = existing
        with open(config_path, "w") as f:
            _yaml.dump(data, f)
    return added
