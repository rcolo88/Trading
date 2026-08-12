# Gaps register

Every entry below is a **pre-registered protocol** — hypothesis, exact variant, acceptance bar, and
the holdout it must survive — written before any run, matching the discipline `config.yaml` already
applies to every adopted/rejected change (see the rejection table in
[`METHODOLOGY.md`](METHODOLOGY.md)).

**Standing rule for every entry below that proposes testing a new variant:** testing it is a new
trial. Append its Sharpe to `blend.trial_sharpes` (via `csm.trials.record_trial_sharpes(...,
section="blend")`) regardless of outcome, which further deflates the DSR — see
[`VALIDATION.md`](VALIDATION.md) for how fast that bar has already moved (3.6× in 40 trials).
Acquiring data is not a trial; testing a strategy variant built on it is.

Status legend: 🔴 open · 🟡 partially addressed · 🟢 resolved (moves here with its result once tested).

---

## 1. 🔴 The duplicated FRED vintage cache

`outputs/cache/fred_vintages.parquet` contains **429,654 rows in exact-duplicate `(series_id, asof,
date)` groups**, spanning 100 vintage pairs from 2000-01-31 to 2002-10-31 (verified this session:
`NFCI` 33 asofs, `T10Y2Y` 33 asofs, `UNRATE` 34 asofs affected; values agree in every duplicate
group, so the corruption is structural, not a data-quality issue). `csm/fred.py:188` returns
`hit.set_index("date")["value"]` with no dedupe, so affected vintages come back with a **duplicated
index, halving every rolling-window computation** over that span.

**Reproduction:**
```python
import pandas as pd
df = pd.read_parquet("outputs/cache/fred_vintages.parquet")
d = df.duplicated(subset=["series_id","asof","date"], keep=False)
assert d.sum() == 429654          # rows in duplicated groups
sub = df[(df.series_id=="UNRATE") & (df.asof=="2002-10-31")]
assert len(sub) == 480 and sub["date"].nunique() == 240   # doubled
```
Downstream effect on the growth-axis vote: `UNRATE` as-of 2002-10-31 gives **+0.6902 with the bug vs
+0.0148 deduped** — large enough to flip the vote's sign, and its 12-month rolling MA effectively
spans 6 real months instead of 12. `T10Y2Y`'s `len >= 252` history guard
(`csm/macro_regime.py:139`) likewise passes on only 126 real observations in the affected window.

**Consequence:** this span sits inside the 2000-2014 holdout used to reject the FRED growth axis
(`config.yaml:158-164`). **That rejection should be treated as unproven, not settled**, until the
cache is repaired and the test is re-run.

**Protocol:** fix (not a strategy test — a data-integrity fix, no new trial):
1. Dedupe on read (`csm/fred.py:188`, before `.set_index("date")`) and on write (`:183-185`, the
   `pd.concat` into `_MEM_FULL`).
2. One-time repair pass over the existing cache (lossless — values agree within every duplicate
   group, verified).
3. Add a regression guard: `vintage_series` asserts its returned index is unique.
4. Re-verify the growth vote flips back: `+0.6902 → +0.0148` for the reproduction case above.

---

## 2. 🔴 The ALFRED non-realtime fallback is a live look-ahead vector for NFCI

`csm/fred.py:85-94` asserts NFCI and T10Y2Y "have no real revision history" to justify falling back
to a non-realtime (fully-revised) query when an `asof` predates ALFRED's vintage archive
(`:111-118`). Measured directly against the cache this session (deduped):

| Series | Reference dates | Revised | Verdict |
|---|---|---|---|
| `T10Y2Y` | 12,132 | 0 (0.0%) | claim holds — fallback is safe |
| `UNRATE` | 558 | 197 (35.3%) | already correctly vintaged (ALFRED covers its full history) |
| `NFCI` | 2,426 | **1,830 (75.4%)** | **claim is false** — one reference week (2008-12-12) moves 2.31 → 3.00 across vintages, a ~30% swing |

Since NFCI's ALFRED vintages only start ~2011-05, **every pre-2011 NFCI read in the 2000-2014
holdout is silently fully-revised data**, not a point-in-time read. Compounds gap 1 — both land in
the same holdout, for the same series family.

**Protocol:** fix, not a strategy test:
1. Add an explicit `SERIES_REGISTRY` (series ID → `revision: none | revised`, frequency,
   description), populated from measurement, not assumption.
2. `revision: revised` series may never take the silent non-realtime fallback — warn, or flag the
   row so a contaminated read is auditable rather than invisible.
3. `revision: none` series get a cost optimization as a side effect: one API call ever, sliced by
   `observation_end=asof`, provably equivalent to per-asof vintaging when nothing is ever revised —
   check the equivalence for `T10Y2Y` across all 319 cached asofs before relying on the shortcut.
4. Add `--verify-revisions`: pull a sample of vintages per series and report the measured revision
   rate, so the registry is checkable rather than another asserted claim — this is exactly the
   process that would have caught the current NFCI error.

---

## 3. 🔴 Wire PBO + MCPT to the blend

The traded strategy's only overfitting control is the DSR — `csmom.py:944` hardcodes `None` for both
PBO and MCPT (see [`VALIDATION.md`](VALIDATION.md)). Highest-value gap that requires **no new search
trial** — it measures what already exists.

**Protocol:**
1. Wire `val_mod.run_mcpt` into `cmd_blend_backtest`, permuting sleeve-selection or basket
   assignment at each rebalance date, same pattern as the equity engine's `run_mcpt`
   (`csm/validation.py:246-314`).
2. Wire `val_mod.run_pbo` using a returns matrix across all currently-adopted config's historical
   trial variants (weight splits, basket versions) as columns.
3. Note before running: the existing PBO call site (`sweep_signal_window.py:124`) uses only 3
   configs, where the CSCV rank statistic is nearly meaningless — don't reuse that as a template for
   column count; use the full trial history instead.
4. Acceptance bar: MCPT p < 0.05, PBO < 0.50 — the same bars the equity engine already uses.

---

## 4. 🔴 Re-run `backtest` and refresh the README numbers

Not a new trial — the current live config (`macro_baskets: v2`, adopted 2026-08-05) has never had
`backtest` re-run against it; the saved report (`outputs/backtest_20260805_101038_blend.json`,
`n_trials: 7`) predates both the v2 flip and the growth of `blend.trial_sharpes` to 40 entries.

**Protocol:** run `python csmom.py backtest`, update [`VALIDATION.md`](VALIDATION.md)'s corrected-numbers
table with the fresh Sharpe/CAGR/MaxDD/DSR, and replace the `README.md` numbers with a link to that
table.

---

## 5. 🔴 Macro coverage — a dollar/FX axis (the user's yen question)

Zero FX data exists anywhere in the repo (see [`DATA_INPUTS.md`](DATA_INPUTS.md)). The one prior
FRED experiment this project ran was framed **only as a growth-axis replacement**, and that framing
is part of why it was rejected (it moved one signal, not added a new one). This protocol is
deliberately framed differently.

**Hypothesis:** USD/JPY (or the broad dollar index) carries information orthogonal to both existing
axes — dollar strength/weakness and carry-unwind risk are not proxied by either the cyclicals-minus-
defensives growth score or the TIP-DBC inflation score.

**Variant to test:** `DEXJPUS` (USD/JPY) and `DTWEXBGS` (broad trade-weighted dollar) as **either**
(a) a new orthogonal third axis alongside growth/inflation in the quadrant classifier, **or** (b) a
standalone risk-off exposure gate (e.g. a sharp yen appreciation / dollar move as a carry-unwind
signal) — not as a replacement for the existing price-based growth axis. Test both framings
separately since they're different hypotheses.

**Acceptance bar:** must not degrade the 2000-2014 holdout on any of Sharpe / MaxDD / 2008 return —
matching every other adopted-vs-rejected decision in this project's history.

**Data prerequisite:** Phase 2 macro scraper (adds `DEXJPUS`/`DTWEXBGS`/`DTWEXAFEGS`/`DEXUSEU` to the
registry as `revision: none` series — cheap, ~1 call each, permanently cached).

---

## 6. 🔴 Macro coverage — credit, curve, and the missing inflation axis

**Missing series:** `BAMLH0A0HYM2` (HY OAS), `BAMLC0A0CM` (IG OAS), `BAA10Y`, `T10Y3M`, `DFII10`,
`T10YIE`, `T5YIFR`, `CPIAUCSL`, `PCEPILFE`.

**Protocol A — credit/curve as a risk-off overlay:** test HY OAS widening and/or `T10Y3M` inversion
as inputs to a new or existing risk-off gate (`csm/blend_overlay.py`), same acceptance bar as gap 5.

**Protocol B — close the half-migrated quadrant:** add `inflation_score_macro` (CPIAUCSL/PCEPILFE/
T10YIE point-in-time vote, same pattern as `growth_score_macro`) so that a future
`macro_growth_axis: macro` test isn't confounded by an inflation axis still on ETF prices. This is a
prerequisite for re-testing gap 1's contaminated rejection cleanly, not a strategy change on its own
— safe to build and leave default-off ahead of any adoption decision.

---

## 7. 🔴 Allocator — the 40/30/30 blend weights are hand-set constants

`config.yaml:147-151` are three literal numbers, chosen by a 7-trial (now 40-trial) hand-search and
explicitly *not* re-optimized further (`METHODOLOGY.md`'s rejection table). López de Prado's direct
answer to "how should sleeve weights be set" is **Hierarchical Risk Parity (HRP) / Nested Clustered
Optimization (NCO) over a Marchenko-Pastur-denoised covariance matrix** — none of which exists
anywhere in this tree (confirmed: zero hits for HRP, NCO, Marchenko-Pastur, detoning, Ledoit-Wolf).

**User decision (recorded 2026-08-12): flag and write the protocol, do not implement or run yet.**

**Protocol:** implement HRP over the 3-sleeve return covariance (denoised via Marchenko-Pastur if the
sample is long enough to make denoising meaningful with only 3 assets — likely not, worth checking
first), re-derive weights **only** on data before the 2000-2014 holdout, then score forward on the
holdout the same way every other candidate in this project has been scored. Compare against the
current fixed 40/30/30 on Sharpe, MaxDD, and the worst-year metric.

**Honest counter-argument to record alongside the protocol:** with only 3 sleeves, HRP's clustering
step has very little structure to exploit — it may not meaningfully differ from equal- or
inverse-vol weighting at N=3. And running this search adds trials that deflate the DSR further for a
strategy whose weights might not move much. Worth doing for completeness and because it's the
literal López de Prado answer to the question asked, but go in with modest expectations.

---

## 8. 🟡 Dead AFML surface

Only 3 of `csm/afml.py`'s 10 functions are called anywhere in this project: `deflated_sharpe_ratio`,
`prob_backtest_overfitting`, `probabilistic_sharpe_ratio` (indirectly, via `run_dsr`). Uncalled:
`get_daily_vol`, `cusum_events`, `add_vertical_barrier`, `get_events`, `get_bins`, `num_co_events`,
`avg_uniqueness`, `return_attribution_weights`, `PurgedKFold`/`cv_score`, `bet_size_from_prob`. This
is intentional dead code, not an oversight — it's what remains after meta-labeling was deliberately
removed (commit `8650801`, see [ADR 0006](decisions/0006-remove-meta-labeling.md)) — but
`README.md:443` still advertises "triple-barrier, purged CV" as part of the live stack, which is no
longer true.

**Action (documentation, not code):** correct `README.md:443`. Decide, function by function, whether
to delete the dead code or keep it as an available-if-meta-labeling-returns primitive — no strong
reason to do either urgently; record whichever choice is made.

---

## 9. 🔴 Not implemented anywhere in the tree

Recorded as a known set so it reads as a deliberate inventory rather than an unknown unknown:
**CPCV** (Combinatorially Purged Cross-Validation — distinct from the CSCV/PBO that *is*
implemented), **fractional differentiation**, **SADF / structural-break tests**, **sequential
bootstrap**, **MDI/MDA/SFI feature importance** (clustered or otherwise), **minimum backtest length**
/ Bailey-Borwein-López de Prado-Zhu false-discovery bounds, and any general-purpose **bootstrap /
White's Reality Check / Hansen's SPA**. None of these are prioritized above — they're higher-effort,
lower-marginal-value than gaps 1-7 given the project's current scale (3 sleeves, no ML model in the
live path since meta-labeling's removal), but worth having in view.

---

## 10. 🔴 Cross-project hygiene

`csm/afml.py` is triple-vendored **byte-identical** across Cross-Sectional Momentum, RAAM, and Trend
Reversal (confirmed via diff) — a fix to one copy doesn't propagate. Concretely costly example found
this session: `Options/src/analysis/overfitting.py:148-154`'s independent DSR implementation never
passes skew or kurtosis to its PSR calculation, so it computes under Gaussian defaults
(`skew=0, kurtosis=3`) — precisely wrong for option-selling returns, whose defining characteristic is
negative skew and fat tails. That makes the Options project's DSR **overstated**. This is a
cross-project bug; fixing it is out of scope for this project's docs effort, but worth flagging to
whoever next touches `Options/`.
