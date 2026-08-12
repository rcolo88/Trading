# ADR 0002: Fixed 40/30/30 sleeve weights, chosen by hand-search, no ongoing optimization

**Status:** Adopted, 2026-08-05 (commit `46a4f0d`, refined same day in `b18d499`)

## Context

The blend needed some allocation across its three sleeves (growth/macro/rotation). A natural
starting point is an optimizer — but with only 3 assets, the search space is small enough that a
hand-search plus a holdout-degradation check was judged sufficient, and simpler to reason about than
introducing an optimizer's own assumptions (covariance estimation, denoising) on a 3-asset problem.

A 6-split weight-tuning sweep on the 2015-2026 config window found OOS Sharpe rising monotonically
with SPY (growth) weight, peaking at 60/20/20 (Sharpe 1.384) — but MaxDD and worst-year also
worsened monotonically (60/20/20: MaxDD −12.0%, worst year −9.4%, close to breaching a pre-registered
−10% bar). This is the classic overfit-to-recent-window signature this project's own discipline
exists to catch: 2015-2026 was, by the project's own measurement, a historically exceptional SPY
bull run (SPY buy-and-hold Sharpe 0.831 on that window vs 0.305 over 2000-2014).

A later Phase-3 re-levering pass (2026-08-05, same day as the `macro_baskets: v2` fix) tested
50/55/60% growth weight on the de-redundified basket and found the identical pattern even more
cleanly: OOS Sharpe rose monotonically 1.472→1.555 while the 2000-2014 holdout degraded
monotonically (Sharpe 0.656→0.554, MaxDD −32.15%→−39.17%, 2008 return −13.27%→−21.81%). Decisively
rejected — see [ADR 0005](0005-reject-fred-growth-axis-and-risk-overlays.md).

## Decision

40/30/30 — a modest, defensible improvement over an original equal-ish guess, chosen specifically
because it stayed roughly consistent with what performed well on the *longer* 2010-2026 window
tested earlier, rather than the highest-Sharpe option on the shorter, bull-market-favorable window.
Weights are **not re-optimized further** as a matter of policy — every subsequent test that tried to
push growth weight higher was rejected on the same holdout-degradation grounds.

## Consequences

- The weights are literal constants (`config.yaml:147-151`), read and only renormalized (never
  re-derived) by `csm/blend.py:52-66`.
- López de Prado's direct answer to "how to weight a small basket of imperfectly-correlated sleeves"
  is HRP/NCO over a denoised covariance — not implemented, flagged with a full test protocol in
  [`GAPS.md` #7](../GAPS.md), not executed pending a future decision.
- Any future weight change must clear the same 2000-2014 holdout bar every other candidate in this
  project has been held to — see the rejection table in [`METHODOLOGY.md`](../METHODOLOGY.md).
