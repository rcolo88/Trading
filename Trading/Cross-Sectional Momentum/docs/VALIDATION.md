# Validation — the overfitting-control ledger

Numbers in this file are the authoritative ones for this project — [`METHODOLOGY.md`](METHODOLOGY.md),
[`GAPS.md`](GAPS.md), and the project `README.md` link here rather than restating figures. Update
this file after every `backtest` run; a number that hasn't been re-verified against a specific
`outputs/*.json` file is a claim, not a fact.

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
| `blend.trial_sharpes` | `config.yaml:225-265` | **40** | hand-pasted — no call site ever passes `section="blend"` |
| `validation.trial_sharpes` | `config.yaml:272-285` | 13 | `sweep_signal_window.py:129-130`, `sweep_max_names.py:87-88` |

`record_trial_sharpes` (`csm/trials.py:19-45`) is a sound mechanism — round-trips `config.yaml` via
`ruamel.yaml` so comments survive, dedupes at `tol=1e-4` (`:37`) so a re-run doesn't double-count —
but it is **only invoked from two scripts in the entire tree**, and `section="blend"` is never
passed by either of them. So:

- The 40 numbers behind the blend's DSR were pasted in by hand, not recorded programmatically.
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
computed against 7 trials and a DSR computed against 40 are not comparable, and only the 40-trial
figure describes the config as it stands.

## Corrected numbers

| Claim | Where it's currently stated | Correct figure | Source |
|---|---|---|---|
| Blend DSR = 0.986 across 7 trials | `README.md:285` | **0.945** against the full 40-trial list | `config.yaml:173-176`; recompute with the snippet above |
| Blend OOS Sharpe 1.316 / CAGR 13.6% / MaxDD −8.6% | `README.md:282` | Sharpe **1.329**, same CAGR/MaxDD — but this run predates `macro_baskets: v2` going live later the same day (commit `b18d499`); **not yet re-run against the current config** | `outputs/backtest_20260805_101038_blend.json` |
| Equity composite OOS Sharpe +1.33 / MaxDD −11.1% | `README.md:353` | Sharpe **+1.157**, MaxDD **−13.2%**, DSR 0.958 at 14 trials | `outputs/backtest_20260804_215755.txt` / `.json` (2026-08-04, postdates the README's 2026-07-16 numbers) |
| "de Prado ML primitives (triple-barrier, purged CV, DSR, PBO)" advertised as part of the live stack | `README.md:443` | Only DSR and (unused-in-CLI) PBO exist as callable primitives in the live path; triple-barrier and purged CV are dead code since meta-labeling was removed (commit `8650801`) | see [`GAPS.md` #8](GAPS.md) |

Action item tracked in [`GAPS.md` #4](GAPS.md): re-run `backtest` and update this table with a fresh
run against the current live config, then update `README.md` to link here instead of restating.
