# ADR 0005: Reject the FRED growth axis, all three risk overlays, and re-levered growth weight

**Status:** Adopted, 2026-08-05 (commit `b18d499`) — **the FRED-growth-axis portion is flagged as
resting on contaminated evidence as of the 2026-08-12 docs audit; see Consequences.**

## Context

A single 2026-08-05 "blend-return-research" session tested four categories of candidate improvement
against the blend, all sharing one evaluation discipline: does it improve the 2015-2026 config
window *and* survive the 2000-2014 holdout, or does it only do the former? This ADR records every
candidate that failed that test in one place, since they share a single underlying pattern.

## Decision — all four rejected

| Candidate | 2015-2026 result | 2000-2014 holdout result | Why rejected |
|---|---|---|---|
| FRED growth axis (`macro_growth_axis: macro`, NFCI+UNRATE+T10Y2Y) | Best OOS Sharpe of 4 variants tested, 1.524 | Worst of the 4: Sharpe 0.586, 2008 return −18.46% (worse than baseline) | Overfits the recent window |
| `risk_overlay: robust` | Best full+OOS Sharpe/alpha of the pass, alpha t=2.31 (a project record at the time) | Sharpe 0.465, MaxDD −36.7% | Same overfit pattern as the FRED axis |
| `risk_overlay: gtt` (growth-trend-timing) | Worse 2015-2026 Sharpe/CAGR/alpha, no offsetting MaxDD benefit there | Dramatic 2008 protection: −0.81% vs baseline's −13.27% | Insurance that doesn't pay for itself outside the one crisis it's built for |
| `risk_overlay: ladder` (combination-vote overlay) | Middling everywhere | Worst multi-fold result of any candidate tested, 0.037 | No redeeming case in either window |
| Phase-3 re-levered growth weight (50/55/60%) | OOS Sharpe rises monotonically 1.472→1.555 | Holdout Sharpe falls monotonically 0.656→0.554, MaxDD to −39.17%, 2008 to −21.81% | Textbook overfit-to-recent-window signature, confirms the original 60/20/20 rejection generalizes |

All three risk overlays share a second flaw beyond their individual issues: each makes the
2000-2014 window's **overall** MaxDD worse than baseline (−35% to −36.7% vs baseline's −32.15%) even
while helping 2008 specifically — de-risking at the wrong moment elsewhere in that window (the
dot-com era), the same static-hedge failure mode already seen with SH-only crisis hedging.

## Consequences

- `blend.macro_growth_axis` stays at `price`, `blend.risk_overlay` stays at `none`, and
  `weight_spy`/`weight_macro`/`weight_rotation` stay at 40/30/30 — the *only* change this entire
  research pass validated was `macro_baskets: v2` ([ADR 0004](0004-macro-baskets-v2.md)).
- **The FRED-growth-axis rejection specifically should currently be read as unproven, not settled.**
  The 2026-08-12 docs audit found the FRED vintage cache had a duplicate-row bug spanning exactly
  the 2000-2002 portion of the 2000-2014 holdout this rejection depended on — see
  [`GAPS.md` #1-2](../GAPS.md) for the full finding and the fix required before re-testing cleanly.
  The three risk-overlay rejections and the re-levering rejection do not depend on FRED data and are
  not affected by this caveat.
- Any future candidate must clear the same bar: improve 2015-2026 *and* not degrade the 2000-2014
  holdout on Sharpe, MaxDD, or a named crisis-year return.
