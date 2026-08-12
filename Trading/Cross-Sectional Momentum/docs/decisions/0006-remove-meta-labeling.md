# ADR 0006: Remove meta-labeling after an honest re-scored comparison showed it underperforms

**Status:** Adopted, 2026-06-19 (commit `8650801`)

## Context

The project's founding design (commit `2b86e2d`) included de Prado-style triple-barrier
meta-labeling: a secondary model scoring whether to "take or skip" each primary signal's bet. Early
results appeared to favor meta-labeling, but that comparison had a flaw — it froze bet size at
entry rather than re-scoring the meta-model at every rebalance, which is the only way meta-labeling
could actually be traded live (a bet's take/skip probability isn't static; re-scoring it as new
information arrives is meta-labeling's whole premise).

Before removing it, the project first unified the backtest with live trading — `simulate_live`, an
event-driven simulation that rebalances the whole book to a fresh target every 5 trading days, holds
shares with drift between rebalances, and charges costs only on real turnover with a 1-day execution
lag — so that comparing "meta vs. no meta" would be an apples-to-apples comparison of two things
actually tradeable, not two different measurement methodologies.

## Decision

Once meta-labeling was re-scored honestly at every rebalance (the only tradeable way to run it), it
underperformed the plain primary book: OOS Sharpe 0.73 vs. 1.03, and roughly 3× the turnover.
Removed `csm/model.py` and `csm/labeling.py`; `ideas --capital N` now outputs the primary book
directly with no meta flag needed.

## Consequences

- The strategy has traded the primary composite-momentum book directly, with no ML model in the
  live path, since this commit.
- Most of `csm/afml.py`'s meta-labeling-adjacent primitives — triple-barrier labeling
  (`add_vertical_barrier`, `get_events`, `get_bins`), sample-uniqueness weighting (`num_co_events`,
  `avg_uniqueness`, `return_attribution_weights`), purged cross-validation (`PurgedKFold`,
  `cv_score`), and bet sizing (`bet_size_from_prob`) — became dead code in this project as a direct
  result of this decision. They remain in the vendored `afml.py` file, correctly implemented, should
  meta-labeling ever return. See [`GAPS.md` #8](../GAPS.md).
- `README.md:443` still advertises "triple-barrier, purged CV" as part of the live methodology —
  that line predates this ADR's full consequences being tracked and should be corrected (tracked in
  [`GAPS.md` #8](../GAPS.md)).
- `simulate_live`'s backtest/live unification survived this decision and became the template the
  blend's own `simulate_blend` (added later, [ADR 0001](0001-blend-replaces-equity-engine.md))
  copied the same event-driven, hold-with-drift, warm-started shape from.
