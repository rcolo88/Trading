# ADR 0003: Market-observable proxies instead of FRED releases for the macro classifier

**Status:** Adopted, 2026-08-05 (commit `46a4f0d`); **partially revisited later the same day in
`b18d499`, and materially reopened by the 2026-08-12 docs audit — see Consequences.**

## Context

The macro regime classifier (`csm/macro_regime.py`) needed growth and inflation signals to place the
market into one of four quadrants (Goldilocks/Reflation/Stagflation/Deflation). The original design
brief referenced official macro releases (CPI, M2, "global liquidity", "fiscal policy") — but several
of those either weren't reachable from this environment at the time (`fred.stlouisfed.org` timed
out) or aren't free, machine-readable series at all ("global liquidity"/"fiscal policy").

## Decision

Substitute market-observable proxies for the same underlying ideas: a 63-day cyclicals-minus-
defensives equity spread for growth, and a TIP-vs-IEF breakeven-inflation proxy averaged with
commodity momentum for inflation. The module docstring (`csm/macro_regime.py:11-16`) frames this as
"arguably more honest for a systematic strategy anyway" — official releases are lagged and revised,
a daily market proxy isn't.

## Consequences

- **This is the origin of the 0.766 growth-sleeve correlation problem.** A price-based growth axis
  is, by construction, unable to diversify away from a price-based growth sleeve. This was measured
  and partially addressed on 2026-08-05 by fixing the macro *basket composition*
  (`macro_baskets: v2`, [ADR 0004](0004-macro-baskets-v2.md)) rather than the classifying axis
  itself — the axis remains price-based in the live config today.
- **The "FRED timed out" premise no longer fully holds.** `csm/fred.py`, built the same day this ADR
  was first adopted, found that `api.stlouisfed.org` (as opposed to `fred.stlouisfed.org`) works
  reliably — and a FRED-based growth axis (NFCI+UNRATE+T10Y2Y) was built and tested that same day.
  It was tested and rejected — but see the next point.
- **That rejection's evidence was later found to be contaminated.** The 2026-08-12 docs audit found
  the FRED vintage cache had a duplicate-row bug spanning exactly the 2000-2002 portion of the
  holdout used to reject the FRED axis (see [`GAPS.md` #1-2](../GAPS.md)). The rejection recorded in
  `config.yaml:158-164` and formalized in [ADR 0005](0005-reject-fred-growth-axis-and-risk-overlays.md)
  should currently be read as **unproven, not settled**, pending a clean re-run.
- The infrastructure this ADR's "we can't reach FRED" premise blocked is now built (`csm/fred.py`)
  and is being extended well beyond the original CPI/M2 ask — see the Phase 2 macro-data-layer work
  referenced in [`CHANGELOG.md`](../CHANGELOG.md).
