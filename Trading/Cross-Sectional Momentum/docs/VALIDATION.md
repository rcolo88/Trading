# Validation — the overfitting-control ledger

Numbers in this file are the authoritative ones for this project — [`METHODOLOGY.md`](METHODOLOGY.md),
[`GAPS.md`](GAPS.md), and the project `README.md` link here rather than restating figures. Update
this file after every `backtest` run; a number that hasn't been re-verified against a specific
`outputs/*.json` file is a claim, not a fact.

## Current headline numbers (2026-08-12, live config)

Re-run against the actual current config (post `macro_baskets: v2`, `macro_growth_axis: price`,
`macro_inflation_axis: price`, `macro_fx_axis: none`, `risk_overlay: none`) — re-verified same-day
after a full macro-coverage sweep + reweighting grid (GAPS.md #5-#7, #11) took `blend.trial_sharpes`
from 40 to **54**; numbers below are essentially unchanged from the pre-sweep run (DSR even ticked
up slightly, 0.9473→0.9490, since most of the new trials were honest rejections with unremarkable
Sharpes rather than clustering near the top), confirming the live result is stable and that testing
everything asked for didn't quietly damage it. Source:
`outputs/backtest_20260812_213808_blend.json` / `outputs/backtest_20260812_213808_blend.txt`.

| Strategy | Sharpe | CAGR | MaxDD | Calmar | Sortino | +Months | Ann. turnover |
|---|---|---|---|---|---|---|---|
| **Blend (OOS)** | **+1.483** | **+14.8%** | **-7.8%** | +1.90 | +1.90 | 74.4% | 4.0× |
| SPY buy-and-hold | +1.354 | +21.2% | -18.8% | — | — | — | — |

DSR = **0.9490** across **55 configs tried** (pass, bar >0.90; best trial Sharpe 1.56). Alpha vs SPY:
ann. +3.96% (t=+1.25, not significant). Beta 0.50 (t=38.1), R²=0.62.

**Multi-fold walk-forward (5 folds, full 2015-2026 history):**

| Fold | Window | Sharpe | CAGR | MaxDD |
|---|---|---|---|---|
| 1 | 2015-01-02 → 2017-04-26 | **+0.29** | +1.8% | -11.3% |
| 2 | 2017-04-27 → 2019-08-21 | +1.12 | +8.3% | -10.5% |
| 3 | 2019-08-22 → 2021-12-14 | +1.35 | +18.0% | -16.3% |
| 4 | 2021-12-15 → 2024-04-12 | +0.66 | +7.1% | -13.6% |
| 5 | 2024-04-15 → 2026-08-11 | +1.54 | +16.2% | -7.8% |

**Fold 1 fails the worst-fold bar** (+0.29 vs the >0.30 threshold) — the only fold that does; folds
2-5 clear it comfortably. Not previously checked against this exact config.

Rolling 12-month windows (n=43): median Sharpe +1.05, worst window Sharpe -0.45, 86% profitable,
worst window return -6.9%, worst window MaxDD -16.3%.

This supersedes the "Corrected numbers" table below, which is kept as a record of what was wrong
and why, not as the current source of truth.

## Macro-coverage sweep (2026-08-12) — FX axis, credit/curve overlay

Prompted by an audit of which macro dimensions had never been tested (see [`GAPS.md`](GAPS.md) #5,
#6, #11). All three variants below are built, default-off, and scored against both the primary
2015-2026 window and the separate 2000-2014 holdout (baseline: Sharpe 0.656 / MaxDD -32.15% / 2008
return -13.27%, per METHODOLOGY.md).

| Variant | Primary OOS Sharpe | Holdout Sharpe | Holdout MaxDD | Holdout 2008 | Verdict |
|---|---|---|---|---|---|
| (a) `macro_fx_axis: carry_unwind` | 1.467 | 0.646 | -32.15% | -15.63% | **Rejected** |
| (b) `risk_overlay: fx` | 1.415 | **0.833** | **-28.25%** | **+3.64%** | **Promising, not adopted** |
| `risk_overlay: credit_curve` | 0.984 | 0.621 | -32.15% | -13.27% | **Rejected** |

**Framing (b) update — 5-fold multi-fold check completed, revises the initial read.** The holdout
result (Sharpe 0.83 vs 0.66, MaxDD -28.3% vs -32.2%, 2008 flips -13.27%→+3.64%) is genuine —
plausibly real, not a fitted coincidence, since the 2008 crisis's acute phase (Sept-Oct 2008)
included a real yen-carry-unwind event, exactly what this gate detects. But the 5-fold check found
the overlay is **worse on every single fold** of the primary window (not just the recent-window
Sharpe overall), including making the already-marginal fold 1 fail harder (+0.29→+0.07). This is a
real cost/benefit tradeoff (crisis insurance paid for by a small drag in ordinary periods), not the
free improvement the holdout alone suggested — **not recommended for unconditional adoption**. Full
fold-by-fold detail, and why framing (a) and `credit_curve` failed outright, is in
[`GAPS.md`](GAPS.md) #5-#6.

**Inflation-axis alternatives (2026-08-12, GAPS.md #6 Protocol B / #11) — both rejected:**

| Variant | Primary OOS Sharpe | Holdout Sharpe | Holdout MaxDD | Holdout 2008 | Verdict |
|---|---|---|---|---|---|
| `macro_inflation_axis: macro` (3-vote, first-ever test) | **1.536** | 0.640 | -32.8% | -14.13% | **Rejected** |
| + oil vote (4-vote, GAPS.md #11) | 1.510 | 0.622 | -32.8% | -14.13% | **Rejected** |

The 3-vote FRED inflation axis is the textbook overfit-to-recent-window pattern (better primary,
worse holdout on every metric) — the same signature that sank the FRED growth axis, `risk_overlay:
robust`, and the Phase 3 growth-relevering below. Adding oil made it strictly worse on both windows.

**De Prado-style correlation check (2026-08-12)** — before treating any surviving signal as adding
real information, checked pairwise correlation among all candidates at rebal-date resolution:
`fx_exposure` (the one non-trivial candidate) correlates weakly with everything (vs price growth axis
+0.08, vs price inflation axis +0.16, vs `credit_exposure` +0.06) — genuinely orthogonal information,
consistent with it being the only candidate that showed real crisis-period value. By contrast the
rejected `inflation_macro` correlates +0.38 with the existing live (price-based) inflation axis it
would have replaced — partially redundant, which helps explain why replacing the price axis with it
added no real diversification benefit despite the higher recent-window Sharpe. The oil-augmented
variant correlates +0.95 with its own 3-vote base, i.e. it's nearly the same signal plus noise.

**Weight-reoptimization (2026-08-12, GAPS.md #7)** — a 10-point manual grid around 40/30/30 (not the
deferred HRP/NCO protocol) to directly test "does 40/30/30 still hold." **No combination tested beats
the current 40/30/30 on both the primary window and the 2000-2014 holdout simultaneously** — every
direction reproduces the same Sharpe-vs-robustness tradeoff seen in the FX overlay and the pre-existing
Phase 3 rejection: more SPY weight buys primary Sharpe by selling holdout robustness (50/10/40: primary
1.540 but holdout Sharpe 0.589, MaxDD -36.4%, 2008 -17.91%); less SPY weight does the reverse (30/30/40:
primary 1.406 but holdout Sharpe 0.678, MaxDD -29.6%, 2008 -9.14%). Full grid in GAPS.md #7.

**Bottom line of this whole sweep: every new metric tested this session was either rejected outright,
or — for the one genuine exception (`risk_overlay: fx`) — a real risk/return tradeoff rather than a
free improvement.** The current 40/30/30, all-price-based config is not an unexamined default; it is
the surviving point after a systematic attempt to beat it along every axis asked about (new macro
signals, signal combinations, and sleeve reweighting), each checked against the same holdout
discipline. "Highest Sharpe possible without degrading the holdout" and "current live config" are the
same answer today.

## What's actually implemented, and how faithfully

`csm/afml.py` is a faithful, vendored port of the relevant Bailey–López de Prado (AFML) primitives —
but only 3 of its 10 functions are ever called from this project (`deflated_sharpe_ratio`,
`prob_backtest_overfitting`, and indirectly `probabilistic_sharpe_ratio`; see
[`GAPS.md` #8](GAPS.md)). Where it's used, it's done right:

- `probabilistic_sharpe_ratio` (`csm/afml.py:219-230`) is the correct Bailey–López de Prado form —
  skew and (excess-corrected) kurtosis are estimated from the **actual return series**, not assumed
  Gaussian, and the track-record-length term `n-1` is present.
- `expected_max_sharpe` (`:233-241`) is exactly the paper's formula: `σ_trials × ((1-γ)·Φ⁻¹(1-1/N) +
  γ·Φ⁻¹(1-1/(N·e)))`, using the **variance of the trial Sharpes**, `N` = trial count.
- `deflated_sharpe_ratio` (`:244-250`) benchmarks the PSR against that expected maximum — this is
  the antidote to grid-search optimism.
- `run_dsr` (`csm/validation.py:216-230`) correctly de-annualizes trial Sharpes (`/ np.sqrt(252)`,
  `:223`) before feeding them in.

Two implementation traps worth knowing about:

- **`expected_max_sharpe` returns `0.0` when `n < 2`** (`csm/afml.py:236-237`), which silently
  degrades DSR to a plain PSR-vs-zero. This has actually fired:
  `outputs/backtest_20260805_084801_blend.json` reports `dsr: 0.990, n_trials: 1` — that number is
  not deflated against anything.
- **The pass bar is `DSR > 0.90`** (`csm/validation.py:229`), looser than the conventional 0.95 used
  in the source literature.

## PBO / MCPT wiring — the traded strategy is not covered

| Test | Wired to the blend (primary, traded)? | Wired to the equity engine (secondary)? |
|---|---|---|
| DSR | Yes — `cmd_blend_backtest`, `csmom.py:904-905` | Yes — `cmd_backtest`, `csmom.py:242-247` |
| MCPT | **No** — `csmom.py:944` hardcodes `None` | Yes, opt-in via `--mcpt N` (default 0 = skipped, `csmom.py:1292-1293`) |
| PBO | **No** — `csmom.py:944` hardcodes `None` | Not wired to the CLI either — only reachable via `sweep_signal_window.py:124`, and there against just 3 configs, where the CSCV rank statistic is close to meaningless |

`csmom.py:944`:
```python
rep_mod.write_backtest_report(results, dsr_result, None, None, out_dir, ...)
```
Confirmed on disk: every `outputs/*_blend.json` has empty `"mcpt": {}` and `"pbo": {}` fields.

**The strategy actually being traded has never been permutation-tested and never PBO-tested.** Its
only overfitting control is the DSR against a hand-maintained trial list — see the next section for
how reliable that list is.

## The trial ledger

Two separate lists, and they must stay separate — `csm/trials.py:24-28` documents a past incident of
cross-contaminating them, which silently corrupted both DSR computations:

| List | Location | Count | Written by |
|---|---|---|---|
| `blend.trial_sharpes` | `config.yaml` | **43** | 40 hand-pasted + 3 recorded programmatically 2026-08-12 (first-ever `section="blend"` call, the macro-coverage sweep — see below) |
| `validation.trial_sharpes` | `config.yaml:272-285` | 13 | `sweep_signal_window.py:129-130`, `sweep_max_names.py:87-88` |

`record_trial_sharpes` (`csm/trials.py:19-45`) is a sound mechanism — round-trips `config.yaml` via
`ruamel.yaml` so comments survive, dedupes at `tol=1e-4` (`:37`) so a re-run doesn't double-count.
Until 2026-08-12 it had **never been invoked with `section="blend"`** anywhere in the tree — the
2026-08-12 macro-coverage sweep (`macro_fx_axis: carry_unwind`, `risk_overlay: fx`, `risk_overlay:
credit_curve`) is the first time it was. So:

- 40 of the 43 numbers behind the blend's DSR were pasted in by hand, not recorded programmatically;
  3 (this session's) were recorded via `record_trial_sharpes(..., section="blend")` directly.
- `config.yaml`'s own comments (`:123-221`) narrate substantially more experimentation than that —
  4 macro-axis variants, 3 risk overlays, 3 re-levered weight splits, v1/v2 baskets, holdout re-runs
  — and it's not verifiable from the repo alone that every one of those Sharpes made it into the
  list exactly once.
- Deduping at `tol=1e-4` means two genuinely distinct configurations that happen to land on the same
  Sharpe are counted as **one** trial — biasing the count downward, which makes the DSR look better
  than it should.

**N is a lower bound on trials actually run, not a trial count.**

## The deflation-bar arithmetic — why the headline DSR is stale

The DSR is a moving target: every trial added to the list raises `expected_max_sharpe` (the null
bar the observed Sharpe must clear), which mechanically lowers the DSR for the same observed result.
Computed this session directly from `config.yaml`:

```python
import yaml, numpy as np
from csm.afml import expected_max_sharpe
ts = np.array(yaml.safe_load(open("config.yaml"))["blend"]["trial_sharpes"])
for n in (7, 13, 20, 40):
    e = expected_max_sharpe(ts[:n] / np.sqrt(252))
    print(n, e * np.sqrt(252))   # annualized E[max SR] under the null
```

| Trials in the list | E[max Sharpe] under the null, annualized |
|---|---|
| 7 | 0.165 |
| 13 | 0.290 |
| 20 | 0.395 |
| **40 (current)** | **0.590** |

The null bar has risen **3.6×** since the "7-trial" search the README currently cites. This is not
a bug — the deflation is supposed to get harder as more trials accumulate — but it means a DSR
computed against 7 trials and a DSR computed against 40 are not comparable, and only the current
43-trial figure (44 including the observed Sharpe itself, per the "Current headline numbers" section
above — DSR 0.9473) describes the config as it stands. This table is kept as-computed (illustrative
of the mechanism, not re-run for the 2026-08-12 update) rather than re-run for one more row.

## Corrected numbers (historical — see the current-numbers section above instead)

| Claim | Where it was stated | Correct figure (as of the correction) | Source |
|---|---|---|---|
| Blend DSR = 0.986 across 7 trials | old `README.md` (pre-2026-08-12) | 0.945 against the 40-trial list at the time | `config.yaml:173-176` at the time; superseded by 0.9473/44 trials above |
| Blend OOS Sharpe 1.316 / CAGR 13.6% / MaxDD −8.6% | old `README.md` (pre-2026-08-12) | 1.329, same CAGR/MaxDD — but that run predated `macro_baskets: v2` going live (commit `b18d499`) | `outputs/backtest_20260805_101038_blend.json`; superseded by the 2026-08-12 re-run above (the first run against this exact live config) |
| Equity composite OOS Sharpe +1.33 / MaxDD −11.1% | old `README.md` (pre-2026-08-12) | Sharpe **+1.157**, MaxDD **−13.2%**, DSR 0.958 at 14 trials | `outputs/backtest_20260804_215755.txt` / `.json` (2026-08-04, postdates the README's 2026-07-16 numbers) — equity engine is secondary, not re-run this session |
| "de Prado ML primitives (triple-barrier, purged CV, DSR, PBO)" advertised as part of the live stack | old `README.md` (pre-2026-08-12) | Only DSR and (unused-in-CLI) PBO exist as callable primitives in the live path; triple-barrier and purged CV are dead code since meta-labeling was removed (commit `8650801`) | see [`GAPS.md` #8](GAPS.md) |

`GAPS.md` #4's action item (re-run `backtest` against the current live config and update this file)
is done as of 2026-08-12 — see the current-numbers section above. The equity-engine row is still
open (last real run 2026-08-04).
