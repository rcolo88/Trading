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

## 1. 🟢 The duplicated FRED vintage cache — RESOLVED 2026-08-12

**Result:** all four protocol steps are done. `csm/fred.py:312` dedupes on read
(`_load_mem_index`), `:389` dedupes on write, `repair_vintage_cache()` (`:440-468`) does the
one-time on-disk repair, and `vintage_series` (`:404-408`) now asserts a unique index as a
regression guard. Verified directly against the live cache this session: `outputs/cache/
fred_vintages.parquet` has **0 rows in duplicate `(series_id, asof, date)` groups** (was 429,654),
and the reproduction case from this entry's original writeup now gives the correct deduped answer:
`UNRATE`'s growth vote as-of 2002-10-31 is **+0.0148** (240 real monthly observations), not the
buggy **+0.6902** (480 doubled observations) recorded when this bug was found.

**Consequence for gap 1's own downstream claim:** the 2000-2014 holdout rejection of the FRED
growth axis (`config.yaml:158-164`) sits partly inside the now-repaired span — the cache
corruption is fixed, but the rejection test itself has **not been re-run** against the clean
cache. Treat the rejection as still-unverified-but-now-testable, not as re-confirmed. (Original
entry, kept below for the record:)

## 1 (original). The duplicated FRED vintage cache

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

## 2. 🟡 The ALFRED non-realtime fallback is a live look-ahead vector for NFCI

**Status update 2026-08-12:** protocol steps 1-3 are done — `SERIES_REGISTRY` exists
(`csm/fred.py:79-176`, all 24 entries measured via `verify_revision_rate`, not assumed), a
`revision: "revised"` series taking the fallback now gets `fallback_revised=True` stamped and a
printed warning (`:265-268`), and `revision: "none"` series get the one-call cost shortcut
(`_fetch_full_series`). **Step 4 is not done** — `verify_revision_rate()` (`:471-520`) exists and
was used to measure all 24 registry entries by hand this session, but there is no `--verify-revisions`
CLI flag; the check is repeatable only by importing the function directly, not from the command
line as the protocol specifies. Leaving this 🟡 until that CLI wiring exists.

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

## 5. 🟡 Macro coverage — a dollar/FX axis (the user's yen question)

**Status update 2026-08-12 — 2000-2014 holdout result, both framings tested:**

| Variant | Sharpe | CAGR | MaxDD | 2008 return |
|---|---|---|---|---|
| Baseline (live config) | 0.6564 | +5.6% | -32.15% | -13.27% |
| (a) `macro_fx_axis: carry_unwind` | 0.6463 | +5.8% | -32.15% | **-15.63%** |
| (b) `risk_overlay: fx` | **0.8327** | **+7.3%** | **-28.25%** | **+3.64%** |

**Framing (a) REJECTED** — degrades holdout Sharpe (0.656→0.646) and 2008 return (-13.27%→-15.63%);
MaxDD ties exactly (the override basket-redirect apparently never touches the actual drawdown path).
Forcing the deflation basket on a stress date doesn't help here, and hurts in the one year it should
matter most.

**Framing (b) CLEARS every leg of the acceptance bar, by a wide margin** — better Sharpe, CAGR, and
MaxDD than baseline, and 2008 flips from a -13.27% loss to a +3.64% gain. This is a materially
different result from every prior overlay tested in this project (`robust`/`gtt`/`ladder` all traded
one problem for another — see the rejection table in METHODOLOGY.md); this is the first overlay to
improve BOTH the holdout and, pending the primary-window check below, the recent window. Plausible
mechanism, not a fluke: the 2008 crisis's most acute phase (Sept-Oct 2008, post-Lehman) included a
real, large yen-carry-unwind event — this is exactly the risk this gate is designed to catch, not an
unrelated correlation. **Primary-window (2015-2026) OOS result, both framings** (baseline 1.4802):

| Variant | Primary-window OOS Sharpe | CAGR | MaxDD |
|---|---|---|---|
| (a) `macro_fx_axis: carry_unwind` | 1.4672 | +14.5% | -7.8% |
| (b) `risk_overlay: fx` | 1.4150 | +14.1% | -7.8% |

Framing (a) stays REJECTED (holdout failure already disqualifies it; primary window is also flat-to-
slightly-worse, so nothing recovers it).

**Framing (b) 5-fold multi-fold check (2026-08-12, requested follow-up) — REVISES the verdict below.**
Worst-fold Sharpe: **+0.07** (bar >0.30; baseline's already-marginal fold 1 is +0.29). Full breakdown
vs. baseline, same 5 folds as everywhere else in this project:

| Fold | Baseline Sharpe | `risk_overlay: fx` Sharpe | Δ |
|---|---|---|---|
| 1 (2015-2017) | +0.29 | **+0.07** | -0.22 |
| 2 (2017-2019) | +1.12 | +0.98 | -0.14 |
| 3 (2019-2021) | +1.35 | +1.30 | -0.05 |
| 4 (2021-2024) | +0.66 | +0.62 | -0.04 |
| 5 (2024-2026) | +1.54 | +1.47 | -0.07 |

**The overlay is worse on every single fold**, not just the one that already failed — confirmed real
via exact daily-return diffs (not a rounding artifact or bug: e.g. fold 2's Dec-2018 trigger measurably
reallocates DBC/BTAL/GLD/IEF weights for a month, Sharpe 0.98 vs 1.12 at full precision). Mechanism:
15 of 139 rebal dates trigger a 0.5-exposure de-risking event, most of them NOT actual crises (2016
yen strength, 2022-09 dollar strength) — each one is a small "insurance premium" paid in quiet
periods, and fold 1 (2015-04-2017) happens to contain 7 of the 15 triggers, concentrating the cost
enough to turn an already-marginal fold meaningfully worse rather than just tied.

**Revised verdict: this is a real risk-management tradeoff, not a free improvement.** The 2000-2014
holdout result (Sharpe 0.83 vs 0.66, MaxDD -28.3% vs -32.2%, 2008 +3.6% vs -13.3%) is genuine
catastrophic-tail protection — but unlike `macro_baskets: v2`'s adoption (better on every metric, one
*narrow* multi-fold miss), this overlay is worse on the *entire* multi-fold breakdown and the primary
OOS window (1.415 vs 1.480), and makes the one fold that already failed the bar fail it harder. **Not
recommended for adoption as an unconditional overlay** — it trades ordinary-period Sharpe for crisis
protection, which is a legitimate choice but a different one than "improves the strategy," and should
be a deliberate user decision (e.g. "I want this specific insurance") rather than a default flip.

Both framings were smoke-tested against 2015-2026 point-in-time data before the holdout run and
produce economically sensible triggers (yen-appreciation vote fires 2016-02, 2022-11/12, 2024-07 —
the run-up to the actual August 2024 unwind; dollar-spike vote fires 2020-03 and 2022-09). Both
variants' Sharpes are recorded in `blend.trial_sharpes` (43 trials now, was 40).

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

## 6. 🟢 Macro coverage — credit, curve, and the missing inflation axis — RESOLVED 2026-08-12 (both protocols tested and rejected)

**Missing series:** `BAMLH0A0HYM2` (HY OAS), `BAMLC0A0CM` (IG OAS), `BAA10Y`, `T10Y3M`, `DFII10`,
`T10YIE`, `T5YIFR`, `CPIAUCSL`, `PCEPILFE`.

**Protocol A — credit/curve as a risk-off overlay:** test HY OAS widening and/or `T10Y3M` inversion
as inputs to a new or existing risk-off gate (`csm/blend_overlay.py`), same acceptance bar as gap 5.

**Status update 2026-08-12 — 2000-2014 holdout result:**

| Variant | Sharpe | CAGR | MaxDD | 2008 return |
|---|---|---|---|---|
| Baseline (live config) | 0.6564 | +5.6% | -32.15% | -13.27% |
| `risk_overlay: credit_curve` | 0.6207 | +5.3% | -32.15% | -13.27% |

**REJECTED** — Sharpe/CAGR degrade with no compensating benefit; MaxDD and 2008 return are *exactly*
identical to baseline to 4 decimal places, meaning the overlay never actually reduced exposure during
2008 at all. Mechanism: `BAMLH0A0HYM2` fails open for the entire holdout (its own history starts
2023-08-14, see the data caveat below), so only the `T10Y3M` vote was live — and the curve inverted
in 2006-2007 (ahead of the crisis, as it classically does) but had already re-steepened by the time
the actual 2008 crash hit (the Fed's 2008 cuts un-invert the curve at the short end), so the overlay
de-risked during the pre-crisis runup and was back to full exposure exactly when it would have
mattered. This is the same lead/lag failure mode already documented for `risk_overlay: gtt`
(economic-signal overlays tend to normalize before the actual crash). Confirms Protocol A does not
add value built this way; not worth a second attempt without a genuinely different mechanism.

Important limitation discovered while building it: the `BAMLH0A0HYM2` FRED series ID's own history
only starts 2023-08-14 (confirmed via the `fred/series` endpoint) — it cannot cover the 2000-2014
holdout or the GFC at all.

**Protocol B — close the half-migrated quadrant:** add `inflation_score_macro` (CPIAUCSL/PCEPILFE/
T10YIE point-in-time vote, same pattern as `growth_score_macro`) so that a future
`macro_growth_axis: macro` test isn't confounded by an inflation axis still on ETF prices. This is a
prerequisite for re-testing gap 1's contaminated rejection cleanly, not a strategy change on its own
— safe to build and leave default-off ahead of any adoption decision.

**Protocol B result (2026-08-12) — REJECTED, its first-ever return test:**

| Window | Baseline Sharpe | `macro_inflation_axis: macro` Sharpe | Baseline MaxDD | Variant MaxDD | Baseline 2008 | Variant 2008 |
|---|---|---|---|---|---|---|
| Primary (2015-2026) | 1.483 | **1.536** | -7.8% | -7.8% | — | — |
| Holdout (2000-2014) | 0.656 | **0.640** | -32.1% | -32.8% | -13.27% | -14.13% |

Textbook overfit-to-recent-window signature — the exact pattern this project has rejected every
previous time it appeared (Phase 3 re-levering, `risk_overlay: robust`, the original FRED growth
axis): better Sharpe on 2015-2026, worse Sharpe/MaxDD/2008 on the 2000-2014 holdout. **Rejected.**
Trial Sharpe (1.5363) recorded in `blend.trial_sharpes`.

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

**Manual grid result (2026-08-12) — supports the counter-argument above, HRP still not run.** Not
the HRP/NCO protocol above (still not implemented — this was a simpler 10-point manual grid around
40/30/30, run to directly answer "does 40/30/30 still hold" alongside this session's macro-coverage
sweep), but directly relevant: no combination tested beats the current 40/30/30 on both the primary
window AND the 2000-2014 holdout simultaneously.

| Direction | Primary Sharpe | Holdout Sharpe | Holdout MaxDD | Holdout 2008 |
|---|---|---|---|---|
| 40/30/30 (current) | 1.483 | 0.656 | -32.1% | -13.27% |
| More SPY (50/10/40) | **1.540** | 0.589 | -36.4% | -17.91% |
| Less SPY (30/30/40) | 1.406 | **0.678** | **-29.6%** | **-9.14%** |
| Less SPY, less macro (20/20/60) | 1.206 | 0.623 | -31.8% | -5.46% |
| Less macro only (40/20/40) | 1.486 (~tied) | 0.638 | -32.9% | -13.59% |

Every direction reproduces the same Sharpe-vs-robustness tradeoff already seen twice this session (the
Phase 3 growth-relevering rejection above, and the `risk_overlay: fx` multi-fold result in gap 5):
more SPY buys recent-window Sharpe by selling holdout/crisis robustness, less SPY does the reverse,
and no point on the grid gets both. **40/30/30 is a genuine, non-arbitrary point on this tradeoff
curve, not an unexamined default** — consistent with (though not a substitute for) what HRP would be
expected to find per the counter-argument above. All 9 new grid-point Sharpes recorded in
`blend.trial_sharpes` (54 trials now, was 43 before this session's macro-coverage + reweighting pass).

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

---

## 11. 🟢 Macro coverage — oil — RESOLVED 2026-08-12 (tested and rejected)

Found during a 2026-08-12 macro-coverage audit prompted by the user asking specifically about oil.
`DCOILWTICO` (WTI, `revision: none`, registered in `csm/fred.py` but zero call sites) was never even
written up as a candidate, unlike gaps 5-6 — this entry closes that.

**Measurement done (not a trial — a correlation check, per this file's standing rule):** WTI's 63-day
return vs. `DBC`'s 63-day momentum (the term already inside `inflation_score`,
`csm/macro_regime.py:79-82`) over their full 2006-2026 overlap (n=5,097 daily obs): **correlation
0.63** (daily-return correlation 0.41). This is meaningfully lower than the 0.766 correlation that
motivated `macro_baskets: v2` (memory csm-market-neutral-macro-tests) — oil is NOT simply a relabeled
version of the existing DBC term — but also not low enough to call clearly orthogonal. Ambiguous
enough that testing it ad hoc would violate this file's own discipline (see the standing rule at the
top); it needs its own hypothesis and acceptance bar before any code is written, same as every other
entry here.

**Hypothesis (not yet tested):** WTI level or momentum carries reflation/stagflation information at
the margin beyond DBC's broader (multi-commodity, ~similarly energy-heavy) basket — most plausibly as
a THIRD vote inside `inflation_score_macro` (gap 6 Protocol B) alongside CPIAUCSL/PCEPILFE/T10YIE,
rather than a standalone axis or overlay (oil doesn't have an obvious risk-off framing the way FX or
credit spreads do).

**Variant to test:** add a WTI vote (e.g. YoY change vs. its own trailing MA, matching the CPI/PCE
vote shape already in `inflation_score_macro`) and re-run that axis's still-outstanding first-ever
return test (gap 6 Protocol B is built but never backtested) with and without the oil vote, isolating
its marginal contribution.

**Acceptance bar:** same as every other gap here — must not degrade the 2000-2014 holdout on Sharpe /
MaxDD / 2008 return. `DCOILWTICO`'s own history goes back to 1986, so no coverage gap on this series
specifically.

**Data prerequisite:** none — `DCOILWTICO` is already registered `revision: none` and cheap.

**Result (2026-08-12) — REJECTED.** Built the 4th vote (`inflation_score_macro(..., include_oil=True)`)
and isolated its marginal contribution against the 3-vote baseline (itself already rejected, see gap
6 Protocol B above):

| Window | 3-vote (no oil) Sharpe | +oil (4-vote) Sharpe | Holdout MaxDD (both) | Holdout 2008 (both) |
|---|---|---|---|---|
| Primary (2015-2026) | 1.536 | **1.510** (worse) | — | — |
| Holdout (2000-2014) | 0.640 | **0.622** (worse) | -32.8% (tied) | -14.13% (tied) |

Oil makes the axis strictly worse on both windows, with MaxDD/2008 identical to 4 decimal places —
the WTI vote's own trigger pattern doesn't touch the base axis's already-set regime calls often
enough to move drawdown or the 2008 return at all, and where it does move the vote average, it moves
it the wrong way. No dedicated axis or overlay warranted. Trial Sharpe (1.5101) recorded in
`blend.trial_sharpes`. This closes gap 11.
