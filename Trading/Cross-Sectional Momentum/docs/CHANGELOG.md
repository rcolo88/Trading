# Changelog

Reverse-chronological. Backfilled from the git history and the dated narrative comments already in
`config.yaml` and module docstrings — those in-code comments are the authoritative detail for each
entry; this file summarizes and points to them rather than duplicating them wholesale.

## [Unreleased]

### Docs + macro data layer (2026-08-12)

Built `docs/` (this directory) as the project's first centralized methodology/decision record —
previously scattered across `README.md`, `config.yaml` comments, and commit messages, three places
already found drifting apart (see [`VALIDATION.md`](VALIDATION.md) for the stale-number audit).
Triggered by two questions: whether all available macroeconomic indicators (FX/yen, yield curve,
credit) were being used, and whether López de Prado's methods were applied thoroughly. Answer to
both: no — see [`DATA_INPUTS.md`](DATA_INPUTS.md) and [`GAPS.md`](GAPS.md).

Found and fixed a real data-integrity defect during the audit: the FRED vintage cache
(`outputs/cache/fred_vintages.parquet`) had 429,654 duplicate rows across 100 vintages spanning
2000-01-31 to 2002-10-31, halving rolling-window computations over that span — inside the exact
holdout window used to reject the FRED macro-growth axis. See [`GAPS.md` #1-2](GAPS.md) for the full
finding, including a second bug (the ALFRED non-realtime fallback silently serves fully-revised NFCI
data, contradicting the code's own no-revision assumption for that series).

Extended the FRED scraper from 3 series (`UNRATE`/`NFCI`/`T10Y2Y`, none of them live) to a broader
macro panel — FX (including USD/JPY, previously entirely absent), the fuller yield curve, credit
spreads, activity, inflation, and liquidity — gated by an empirically-verified revision registry so
market-observed series cost one API call instead of 319. **This acquires data; it does not change
what the strategy trades** — no `blend.trial_sharpes` entry was added, no config value changed
besides a comment annotation. See [`GAPS.md`](GAPS.md) for what's pre-registered to be tested next.

---

## 2026-08-05 — CSM: fix macro sleeve's equity redundancy (basket composition, not signal)

Measured the macro-tilt sleeve at 0.766 daily correlation with the growth sleeve — ~70% of the book
was effectively one equity-beta bet, since the original regime baskets held mostly equity sector
ETFs in every quadrant, including stagflation/deflation where the whole point is to hold something
other than equity beta. Tested whether the fix belonged in the classifying signal or the basket
composition: a new FRED-based growth axis (`csm/fred.py`, point-in-time NFCI+UNRATE+T10Y2Y) barely
moved the correlation and overfit the 2015-2026 window. Rebalancing the baskets toward genuinely
non-equity assets (`REGIME_BASKETS_V2`, `macro_baskets: v2`) dropped the correlation to 0.50 and
improved Sharpe/MaxDD/alpha on every window tested, including a new 2000-2014 holdout (extended
price history back to 1999, `csm/data.py::_LONG_HISTORY_START`) that covers the GFC for the first
time. Adopted live. Three further pre-registered candidates (the FRED growth axis, three risk
overlays in `csm/blend_overlay.py`, and re-levering into more growth weight) were tested and
rejected — each improved 2015-2026 metrics while degrading the 2000-2014 holdout, the same
overfit-to-recent-window pattern already seen with the original 60/20/20 rejection. Also fixed a
real 18-day `^VIX3M` Yahoo data outage so a stale print no longer silently masqueraded as current
data in the graded regime gate. See [ADR 0004](decisions/0004-macro-baskets-v2.md) and
[ADR 0005](decisions/0005-reject-fred-growth-axis-and-risk-overlays.md).
— commit `b18d499`

## 2026-08-05 — CSM: add 3-way blend as primary strategy, regime-robustness research, multi-portfolio capital fix

The blend (`csm/blend.py`) — growth ticker (SPYM) / macro regime tilt (`csm/macro_regime.py`) /
defensive rotation (`csm/multiasset.py`), fixed 40/30/30 weights, monthly rebalance — beat SPY
buy-and-hold on Sharpe with roughly half the max drawdown (alpha t≈2.0-2.06 on a standalone
2010-2026 reconstruction) and was promoted to the primary `backtest`/`ideas`/`verify-book` commands;
the original equity engine moved to `equity-*`. See [ADR 0001](decisions/0001-blend-replaces-equity-engine.md)
and [ADR 0002](decisions/0002-fixed-40-30-30-weights.md).

Also in this commit: fixed a point-in-time universe membership bug in `csm/universe.py` (a
MultiIndex column-parsing issue plus a snapshot-vs-event-log confusion) meaning **every prior
backtest on the equity engine had been survivorship-biased**. Added the regime-robustness research
modules (`csm/regime_state.py`: Kritzman turbulence + absorption ratio; `csm/slow_bleed.py`:
breadth/momentum slow-decline detector), wired as opt-in on the equity engine (`mode: robust`), not
yet default. Fixed multi-portfolio capital handling so `ideas --capital N` correctly recomputes
dollar amounts per run without corrupting a different portfolio's remembered book. Added automated
trial-Sharpe recording (`csm/trials.py`).
— commit `46a4f0d`

## 2026-08-04 — CSM: self-gate `ideas` on the rebalance cadence

Made it safe to run `ideas` from a daily cron: it checks trading days elapsed since the last saved
book and only rebuilds/re-trades when a rebalance is actually due, otherwise prints a HOLD status
and exits without touching outputs or the network. `--force` bypasses the gate.
— commit `aeaee4f`

## 2026-07-16 — CSM: adopt composite momentum signal (resid mom + FIP + 52wk-high)

A literature-driven sweep tested four candidate overlays against the residual-momentum baseline on
identical OOS data: a graded VIX-term-structure regime gate, a turnover-hysteresis hold band, a
composite conviction signal, and a defensive-IEF sleeve. Only the composite signal — an equal-weight
z-score blend of residual momentum (Blitz-Huij-Martens), frog-in-the-pan information continuity
(Da-Gurun-Warachka), and 52-week-high proximity (George-Hwang) — cleared the pre-registered Sharpe
bar (1.17 → 1.33 OOS, unchanged drawdown) and became the default. The other three remain available
as config flags, off by default. DSR (0.978) deflates against all 8 configs tried via the new
`validation.trial_sharpes` grid.
— commit `198e670`

## 2026-06-19 — CSM: unify backtest with live trading, then remove meta-labeling

Made the backtest a literal simulation of the live weekly process (`simulate_live`: event-driven,
rebalances the book to a fresh target every 5 trading days, holds shares with drift between
rebalances, charges costs only on real turnover with a 1-day execution lag) so backtest and live are
identical by construction — `portfolio.target_book` is the single source of truth, and `verify-book`
asserts the two match exactly. Then removed meta-labeling: re-scored every rebalance (the only
tradeable way to run it), it underperformed the plain primary book (OOS Sharpe 0.73 vs 1.03) and
roughly tripled turnover; the earlier apparent "meta wins" result was an artifact of freezing bet
size at entry rather than the honest re-scored comparison. Deleted `csm/model.py` and
`csm/labeling.py`. See [ADR 0006](decisions/0006-remove-meta-labeling.md).
— commit `8650801`

## 2026-06-19 — CSM: extend continuous-OOS fix to the meta-labeling path

The meta path was still recomputing the primary signal separately on the IS and OOS slices, each
re-burning ~2×window of warmup and leaving the meta OOS score both understated and non-comparable to
the (already-fixed) continuous primary curve. Computed the signal once on the full panel and sliced
instead — IS labels still truncated to `is_prices` so a late-IS trade's barrier can't resolve on OOS
data (no train/test leak), while OOS entries are detected on the continuous, non-truncated positions.
— commit `98adc8e`

## 2026-06-19 — CSM: empirical window sweep + auto-anchored backtest end + continuous OOS fix

Tested the hypothesis that 12-month momentum was too slow to react, honestly: swept
`signal.window` ∈ {126, 189, 252} on an *identical* OOS period. Verdict: on equal footing the
12-month window won (Sharpe 0.88 vs 0.79 vs 0.63) — shorter windows had only appeared to win earlier
under a warmup-artifact measurement bug. That bug was the real finding: `walk_forward` had been
recomputing the primary signal on the OOS slice alone, re-burning ~525 days of warmup *inside* OOS
and understating long-window Sharpes. `evaluate_oos_continuous()` fixed it — computing the signal
once on the full panel and scoring only the OOS dates moved primary OOS Sharpe from +0.01 to +0.88
and DSR from 0.51 (fail) to 0.94 (pass). This became the standard OOS-scoring approach for the
project going forward.
— commit `67f81f5`

## 2026-06-18 — CSM: live ideas/fetch price off today's close, not config end_date

`ideas` had been quoting entries three weeks stale because both `fetch` and `ideas` used
`cfg.data.end_date` — a backtest-analysis-window setting — as the live download end. Added
`_live_end()` (downloads through tomorrow, since yfinance's `end` is exclusive) and a wall-clock
freshness guard that errors if the panel lags today by more than 5 days.
— commit `08d28a3`

## 2026-06-18 — CSM: fix stale price cache, phantom signals, and PIT coverage

Three interacting bugs, diagnosed from a single symptom (a stock quoted at a months-stale price):
(1) the price cache was ticker-aware but not date-aware, so an existing ticker was never refreshed
regardless of staleness; (2) `pct_change()`'s default fill turned multi-month data gaps into flat 0%
returns, producing phantom momentum signals instead of the stock correctly dropping out; (3)
point-in-time universe membership was built starting from `config.start_date`, leaving the in-sample
period with zero members and silently zeroing every in-sample position. All three fixed together.
— commit `7cbca9b`

## 2026-06-18 — CSM: dollar-based, fractional-share output for ideas

Switched the book and rebalance trade list from integer share counts (which rounded expensive names
to zero on small accounts) to dollar amounts with fractional shares, matching how the strategy is
actually traded on a fractional-share broker.
— commit `7fe4fe7`

## 2026-06-18 — CSM: rank quintile by conviction + concentrate to max_names=25

`build_positions` had been capping the top quintile in raw ticker-column order rather than by
signal strength, holding an arbitrary subset instead of the strongest names. Fixed to rank by
conviction and keep the top `max_names`; a sweep (`sweep_max_names.py`) then showed OOS Sharpe
decays monotonically as the cap grows, since the long tail of the quintile dilutes the strongest
signals and worsens drawdowns. Set `max_names` from 100 to 25: Sharpe 1.03 → 1.38, MaxDD −16.6% →
−11.4% on the S&P 1500 PIT 30%-OOS backtest at the time.
— commit `8877ee0`

## 2026-06-18 — CSM: Cross-Sectional Residual Momentum trade-idea engine (initial)

The project's founding commit: idiosyncratic (CAPM-residual) 12-1 momentum on the S&P 1500, weekly
rebalance, vol-scaling and a regime filter, triple-barrier meta-labeling with a purged-CV panel
splitter, and DSR/PBO/MCPT overfitting tests. Stage 0 spike (survivorship-biased, current S&P 500
only): Sharpe 0.97, MCPT p≈0, DSR≈1. This is the origin of the equity engine now preserved as
secondary — see the later entries above for how it evolved and why the blend eventually replaced it
as primary.
— commit `2b86e2d`
