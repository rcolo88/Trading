# Documentation index

Institutional memory for this project — how the traded strategy was built, what's been validated,
what data feeds it, and what's still missing. Built 2026-08-12 in response to two questions: *how
was the current positive-Sharpe portfolio actually achieved*, and *were all available macroeconomic
indicators (FX/yen, yield curve, credit) and López de Prado's overfitting-control methods used to
the fullest*. Short answer to the second: no on both counts — see [`DATA_INPUTS.md`](DATA_INPUTS.md)
and [`GAPS.md`](GAPS.md).

## Files

| File | What it answers |
|---|---|
| [`METHODOLOGY.md`](METHODOLOGY.md) | How the live blend is built and what discipline produced it — the sleeves, the simulator, the reject-on-holdout-degradation rule, and exactly what data refreshes at a rebalance |
| [`VALIDATION.md`](VALIDATION.md) | Which overfitting tests are actually wired to the traded strategy, the trial-ledger honesty caveats, and the current authoritative numbers |
| [`DATA_INPUTS.md`](DATA_INPUTS.md) | Every data input this project has, and the full macro inventory of what it doesn't |
| [`GAPS.md`](GAPS.md) | Prioritized register of open gaps, each with a pre-registered test protocol |
| [`CHANGELOG.md`](CHANGELOG.md) | Architecture/approach history, reverse-chronological |
| [`decisions/`](decisions/) | ADRs for the consequential calls already made — context, decision, consequences |

## The one rule that keeps this from re-rotting

**Numbers live in [`VALIDATION.md`](VALIDATION.md) only.** The project `README.md` and every file in
this directory link to it rather than restating a Sharpe/DSR/MaxDD figure inline. This project has
already drifted once — four numbers in the top-level README were stale by the time this directory
was built (see `VALIDATION.md`'s corrected-numbers table) — precisely because the same figures were
copy-pasted into multiple places and only one copy got updated.

## When to update what

- **`VALIDATION.md`** — after every `backtest` run. If a number in it doesn't match the newest
  `outputs/backtest_*.json`, it's stale; fix it in the same sitting you notice it.
- **`CHANGELOG.md`** + a new file under **`decisions/`** — whenever a config change is adopted live
  (not just tested). The changelog entry is the narrative; the ADR is the structured
  context/decision/consequences record other future decisions may need to cite.
- **`GAPS.md`** — whenever a registered gap is actually tested. Move its entry's status from 🔴 open
  to 🟢 resolved (or 🟡 partially addressed) and record the result inline, whichever way the result
  went — a rejected candidate is exactly as valuable to record as an adopted one, per this project's
  own discipline (see the rejection table in `METHODOLOGY.md`).
- **`DATA_INPUTS.md`** — whenever a new data series or source is added, whether or not it's wired
  into a live signal yet.
- **`METHODOLOGY.md`** — only when the *live* path actually changes (a new sleeve, a different
  simulator behavior, a different refresh mechanism). It intentionally does not track historical
  detail — that's what `CHANGELOG.md` and the ADRs are for.

## Scope note

This directory was built in two phases. Phase 1 (documentation) made no code or config changes.
Phase 2 (the macro data layer, see `CHANGELOG.md`'s Unreleased entry) added data acquisition
infrastructure but deliberately made **no change to what the strategy trades** — no new
`blend.trial_sharpes` entry, no adopted config value change. Every macro-indicator question this
project's docs raised (does the yen help? does the yield curve help now that its evidence is
unpolluted?) is answered as a pre-registered protocol in `GAPS.md`, not as a decision already made.
