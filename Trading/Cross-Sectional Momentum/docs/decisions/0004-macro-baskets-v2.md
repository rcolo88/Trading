# ADR 0004: `macro_baskets: v2` — majority non-equity stagflation/deflation baskets

**Status:** Adopted, 2026-08-05 (commit `b18d499`)

## Context

The macro-tilt sleeve was measured at **0.766 daily correlation with the growth sleeve** —
approximately 70% of the book was effectively one equity-beta bet. Root cause: `REGIME_BASKETS`
(v1) held 5-8 sector SPDRs (equity) in *every* quadrant, including stagflation and deflation, where
the entire strategic point of the quadrant is to hold something other than equity beta.

Two candidate fixes were tested: change the classifying *signal* (a FRED-based growth axis — see
[ADR 0003](0003-market-proxies-over-fred-releases.md)), or change the basket *composition*. The
FRED-axis change barely moved the correlation and overfit the tested window. The basket-composition
change worked.

## Decision

`REGIME_BASKETS_V2` (`csm/macro_regime.py:62-67`) pushes the stagflation and deflation baskets to
majority non-equity holdings (real assets, duration, credit), leaving goldilocks/reflation
equity-tilted, which is directionally correct when growth is genuinely up. Result: correlation with
the growth sleeve dropped to 0.50, and Sharpe/MaxDD/alpha improved on every window tested, including
a new 2000-2014 holdout (built the same day, extending price history back to 1999) that covers the
GFC for the first time.

The one blemish: v2 misses one narrow multi-fold bar (0.290 vs the 0.30 threshold) — disclosed
rather than hidden, and outweighed by v2's higher DSR (0.945 vs v1's 0.924 against the same 40-trial
list) and its across-the-board improvement everywhere else, including the holdout.

## Consequences

- `blend.macro_baskets: v2` is the live setting (`config.yaml:165`); `v1` remains available to
  revert to.
- The classifying axis itself is unchanged by this fix — it's still the price-based
  cyclicals-minus-defensives spread from [ADR 0003](0003-market-proxies-over-fred-releases.md). This
  ADR treats the symptom (what gets held); the axis (what triggers holding it) is still open — see
  [`GAPS.md` #6](../GAPS.md)'s protocol for the missing `inflation_score_macro` companion.
- No `backtest` run against this config has been re-saved since the flip — the last saved blend
  report predates it. See [`GAPS.md` #4](../GAPS.md).
