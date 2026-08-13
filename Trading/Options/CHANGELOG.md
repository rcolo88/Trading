# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Return metrics are denominator-driven; 2022 drawdown anatomy; Sharpe-convention fix (2026-08-13)

Triggered by the user questioning whether a 6.78% CAGR was plausible for a strategy collecting ~$221
of credit daily at a ~74% win rate. It was — but only because the headline percentage was being
divided by an arbitrary capital base. Three findings and one real bug in the reporting.

**1. Under `fixed_contracts` sizing, every percentage metric is a denominator choice.** The account
value never gates entries, so `initial_capital` is a pure reporting divisor. Verified directly in
new `diag_capital_denominator.py`: running the identical config at $150k / $50k / $25k produces
**identical trade counts (2,125), identical dollar P&L ($111,691.56) and identical dollar drawdown
(-$22,821.74)** — only CAGR (6.78% / 14.83% / 22.16%) and max DD% (-10.69% / -20.77% / -34.62%)
move. The per-trade economics reconcile exactly: $223 credit, $777 max loss, avg win $183 / avg loss
-$308 at a 73.7% win rate → EV **+$52.56/trade** × 249 trades/yr ≈ **$13,109/yr**. The CAGR decays
across the span because the numerator is a flat dollar stream while the denominator compounds
($13.1k is 8.7% of the $150k start but 5.0% of the $261k finish). Average concurrent positions are
9.95, so peak *defined* risk is only ~$13.2k — roughly 7.5% of the $150k reported against.

**2. The max drawdown is the 2022 bear market, and it is a grind rather than a blow-up.** New
`diag_drawdown_anatomy.py` locates it: peak 2022-01-03 ($213,506) → trough 2022-10-12 ($190,684),
-$22,822 over 282 days, then **337 more days to recover** (~20 months underwater). Inside that
window 192 trades closed at a **43.2%** win rate (vs 73.7% overall); 109 losers averaging **-$325**
did the damage against 83 winners. The **worst single trade was -$607** — nothing approached its
$777 max loss — and the worst 10 losers together are only 16% of the window's losses. The stop fired
on **51.6%** of trades there, working as designed. This resolves the apparent paradox that dollar
drawdown (-$22.8k) exceeds peak defined risk ($13.2k): a drawdown accumulates sequentially across
non-overlapping cohorts over months, it is not a simultaneous max-loss event. 2022 is the **only**
losing year in the span (-$17,951); 2020 was **+$13,579**, so a fast crash that snaps back is
survivable while a slow year-long bleed is what hurts.

**3. FIXED — full-span and IS/OOS Sharpe were being reported under different conventions.**
`metrics.py:84` subtracts a 2% risk-free rate (excess Sharpe), but the IS/OOS slice Sharpes computed
in `compare_delta_stop_grid.py` and quoted in `DAILY_CADENCE_STRATEGY.md` were raw (no rf). At $150k
the gap is ~0.36, so "OOS 1.662 vs full-span 0.843" overstated OOS strength by roughly that much.
**Parameter rankings are unaffected** — every row within a column used the same formula — but the two
columns were never on the same scale. `make_account_size_chart.py` now matches the project
convention (`RISK_FREE = 0.02`) and reports the raw figure alongside as `sharpe_raw_no_rf`;
`DAILY_CADENCE_STRATEGY.md` gains caveat 7 spelling this out and caveat 8 on denominator dependence.
Note that under the excess convention Sharpe *falls* as capital rises (0.99 at $25k → 0.75 at
$200k), because the risk-free drag grows as percentage volatility shrinks.

**New: `DAILY_CADENCE_CARD.md`** — a deliberately short (~485 word) trading card: parameters,
per-trade economics, dollar-first results, an account-size table, and a four-sentence account of the
2022 drawdown. Intended as the day-to-day reference; `DAILY_CADENCE_STRATEGY.md` remains the full
analysis.

**New: `make_account_size_chart.py`** → `charts/daily_cadence_account_size.png`, plotting CAGR and
max drawdown against starting account size on a single percentage axis. Because the dollar P&L path
is fixed, the curve is computed exactly from one backtest (`total_value(C,t) = C + pnl_path(t)`)
rather than sampled; the P&L path is cached to `backtest_results/daily_cadence_pnl_path.csv` so
re-renders skip the backtest entirely.

### Controlled delta × stop-loss sweep — daily-cadence wing changed to a $10 FIXED width (2026-08-13)

Triggered by pushback on the 2026-08-11 recommendation: user challenged the 0.35Δ short as "too
close" and the 30% stop as "too tight," expecting the search to have landed on 25-30Δ with a 50-70%
stop for more room to manage. Investigating produced a parameter-surface tool, corrected two
misreadings, and changed the recommended wing.

**Why the existing Optuna log could not answer the question.** TPE concentrates samples in whatever
region looks promising early, so its trial log is not a parameter surface. Of 127 unique trials, 58
sat on `short_delta=0.35` — which is also the search's hard ceiling
(`optimize_daily_cadence.py:148`, `min=0.15, max=0.35`) — while 0.15-0.25Δ drew 2-5 trials each,
each with a random companion set of profit-target/exit-DTE values. The apparent "low delta scores
badly" marginal is confounded with "low delta was only ever tried alongside bad exit params." Same
for the stop-loss axis: 43 samples in the 0.25-0.35 band vs 12 in 0.55-0.70.

**New: `compare_delta_stop_grid.py`** — full factorial short_delta × stop_loss with every other
parameter pinned at the winner, so the comparison is causal. `--width N` pins the wing to a dollar
width instead of a constant delta gap. Outputs `backtest_results/compare_delta_stop_grid.csv` and
`compare_delta_stop_grid_w10.csv`.

**New: `make_delta_width_charts.py`** — renders the three figures now embedded in
`DAILY_CADENCE_STRATEGY.md` (`charts/daily_cadence_delta_stop_grid.png`,
`daily_cadence_width_vs_delta_dd.png`, `daily_cadence_wing_headtohead.png`).

**Finding 1 — `stop_loss` is a fraction of MAX LOSS, not of credit.** `vertical_spreads.py:301`
triggers on `(-profit) / max_loss >= stop_loss` with `max_loss = strike_width - credit`. At
0.35Δ/$10 (credit = 22.3% of width) the recommended `stop_loss: 0.30` is a loss of 104% of credit —
a conventional **~2× credit stop**, not a tight one. The same config number means something very
different at another delta (251% of credit at 0.20Δ). The stop is a live control at these settings,
taking 23.0% of trades; an earlier `dte_min=22` config made it look inert (0.4%) only because the
DTE floor closed everything first.

**Finding 2 — drawdown is set by WIDTH, not short delta.** The constant-0.20Δ-gap grid appears to
show low delta causing deep drawdowns (25Δ at -28.8%), but a constant delta gap makes the spread
*wider in dollars* as delta falls (credit is 6.3% of width at 0.20Δ/0.03Δ vs 20.4% at 0.35Δ/0.15Δ) —
so that test silently varied position size along with delta. Pin the dollar width and the delta axis
goes flat: -9.8 / -10.7 / -11.3 / -10.7% across 0.20→0.35Δ. **Short delta is the probability knob;
width is the risk knob.**

**Finding 3 — at constant width, 0.35Δ and SL 30% win on every cut.** Sharpe rises monotonically
with short delta on full-span (0.243 → 0.843), OOS (0.861 → 1.662), stress (0.465 → 0.847) and calm,
with no drawdown penalty, and 0.35Δ posts the *smallest* worst single trade in the grid (-$806) —
its larger credit cushions and the stop fires earlier against it. SL 30% is best at every delta on
Sharpe, stress, CAGR and drawdown; loosening to 70% costs 5-7 drawdown points. Stepping down to
0.25Δ costs ~2.5 points of CAGR for zero drawdown reduction. The user's stop-loss intuition holds
only in the calm OOS slice at 0.20-0.25Δ, and is reversed at 0.35Δ.

**Recommendation change: the wing, not the delta.** At 0.35Δ / SL 30%, a **$10 fixed wing** beats
the 0.15Δ delta-selected wing on Calmar (0.634 vs 0.562), max drawdown (-10.69% vs -16.31%) and
worst single trade (-$806 vs -$1,306), giving up 2.4 points of CAGR (6.78% vs 9.16%) and 0.13 Sharpe.
It also removes a structural tail risk: a delta-selected wing's dollar width balloons when vol
spikes — the 0.30Δ/0.10Δ row recorded a single -$6,194 trade — whereas a fixed wing's per-contract
risk is identical every day.

**This does NOT contradict the 2026-08-11 "fixed-width NOT recommended" verdict.** That rejected a
**$20** wing at 0.31Δ (OOS-stress Sharpe -1.05) chosen by a search that pinned to the top of its own
$5-$20 range. A $10 wing at 0.35Δ posts stress Sharpe +0.847. Different structures; both results
stand. `DAILY_CADENCE_STRATEGY.md` restructured accordingly — current recommendation at the top,
2026-08-11 section retained with scope notes rather than deleted.

**Unchanged caveats:** DSR 0.002 (weak) — the monotonic ranking across five metrics is the evidence,
not the absolute magnitudes; 0.35Δ remains the untested search ceiling with every trend pointing
upward; and **no rolling/adjustment logic exists in the strategy code**, which remains the most
plausible explanation for the standing tension with live 20Δ experience.

### Skew-tail + strike-grid fix, daily-cadence re-optimization — SUPERSEDES the 2026-08-10/11 daily-cadence recommendation (2026-08-11)

Triggered by pushback on the daily-cadence recommendation: user asked whether the SPY chain's
strike gaps were too coarse for precise delta matching, and whether the training window was too
benign (too little GFC/COVID) to find a robust delta/width. Investigation found a third,
compounding problem that subsumed both.

**1. IV surface skew was extrapolated unbounded past where it was actually fitted.**
`skew_calibration.py` fits the put/call skew quadratics only over `m` (log-moneyness) in
`[-0.20, 0]` / `[0, 0.06]`. Outside that band the old code let the quadratic's own curvature
(19.51/20.0) keep running — it hit 11x by `m=-0.67` on a low-spot day. Measured: 17-50% of the
2018-2023 (IS) search space priced on this extrapolation per year, worst in exactly the volatile
years (2018, 2020) that dominate the IS window, vs. ~0-1% in 2024-2026 (OOS). This inflated the
protective (long) leg's cost specifically during stress, biasing every prior daily-cadence search
against wide/low-delta structures. Fixed in `synthetic_generator.py::_iv_surface`: continues
LINEARLY at the fitted quadratic's own slope at the knot instead of letting the quadratic itself
run unbounded — continuous in value and first derivative, knots sourced directly from
`skew_calibration.py`'s `PUT_M_MIN`/`CALL_M_MAX` so the fit range and extrapolation boundary can
never drift apart.

**2. Strike grid was a fixed $5/±$100 band.** ±45% of spot in 2020 vs ±13% in 2026 — a 0.10-0.20Δ
long wing was literally unreachable on crisis days (verified: 2020-03-23's minimum available
|delta| on a 20-45 DTE put was 0.105). Fixed: `synthetic_generator.py::generate_delta_band_strikes`
— $1 spacing (matching real SPY) across a vol-adaptive band computed per (day, expiration) to span
|Δ| in [0.02, 0.60], plus a coarse $5 outer tail for marking positions that move deep ITM/OTM
after entry. `synthetic_data_filename()` now encodes grid mode so a finer regen can never silently
overwrite the old coarse-grid file. New config keys under `synthetic_data:` (`grid_mode`,
`fine_interval`, `coarse_interval`, `fine_min_abs_delta`, `fine_max_abs_delta`,
`coarse_extra_frac`) — default (`grid_mode: fixed`) unchanged so every other optimizer's reference
dataset is untouched.

**3. Performance fix (enables the above at scale).** `optopsy_wrapper.py::prepare_optopsy_data`
and a new `_get_day_groups` now memoize by IDENTITY of the input DataFrame, so a 150+ trial Optuna
search doesn't re-copy and re-process the entire multi-year dataset (previously O(days × rows) per
trial, unbounded across trials) from scratch on every single trial — required so the ~4.4x denser
corrected grid doesn't multiply search time by the same factor. Verified as a pure no-op:
identical Sharpe/trades/return/maxDD across repeated trials on the same data.

**4. Regime-conditional robustness (new).** `src/analysis/regime.py`: calm vs. stress Sharpe/max
DD/win-rate reported as SEPARATE columns, never blended into pooled Sharpe (stress windows: 2018
Q4 selloff, COVID crash, 2022 bear, plus the Aug-2024 yen-carry spike and Apr-2025 tariff-shock
selloff inside the OOS window). This is a reporting split, not a resampling of the training
data — reweighting toward stress would bias the unconditional estimate and collapse effective
sample size (COVID alone is 35 trading days); the window's ~13.5% stress share is already close to
the historical base rate. Also added purge/embargo: no new IS entries in the final 40 trading days
of the IS window (`optimize_daily_cadence.py::EMBARGO_TRADING_DAYS`), so no IS-scored trade is
force-closed at the boundary before its own exit condition could fire.

**Result:** regenerated `SPY_synthetic_options_2018-01-01_2026-07-10_db1.csv` (9.97M rows) and
re-ran both 150-trial daily-cadence Optuna searches. New delta-wing winner: 21 DTE / 0.35Δ short /
0.15Δ long / PT 80% / SL 30% (was 24 DTE / 0.35Δ / 0.19Δ / PT 90%) — full-span Sharpe 0.80 → 0.97,
CAGR 7.60% → 9.16%, achieved-delta accuracy 25% off-target → 0.0% off-target. The old report's
unresolved "20Δ live vs. backtest" tension substantially narrowed: every ~20Δ combination went
from uniformly negative Sharpe to solidly positive (0.29-0.41) under corrected pricing. The
width-wing search's new winner ($20 wide, the edge of the tested range) looks competitive on
pooled OOS Sharpe (1.03) but has a deeply negative OOS-stress Sharpe (-1.05) vs. the delta wing's
positive 0.54 in the same window — recommendation stays delta-selected wing. See
`DAILY_CADENCE_STRATEGY.md` for full before/after tables.

### Pricing model overhaul (skew, friction, vol level) + full width/delta/risk-budget validation — SUPERSEDES the 2026-08-02 strike-width verdict below (2026-08-09)

Triggered by pushback on the "adopted" 24Δ/8Δ config: user proposed 20Δ short with a fixed $5-$10
wide wing on risk grounds, distrusting the backtests' price/slippage realism. Investigation found
the distrust was justified, in three separate, compounding ways — all fixed, then the whole
width/delta/risk-budget space was re-validated on the corrected surface.

**1. Put skew was 25-60% too flat.** `src/data_fetchers/skew_calibration.py` (new) fits the real
put/call skew shape from 38 days of logged $1-strike Schwab chains (`data/raw/chains/`, compiled by
the previously-unused `data_collection/compile_chains.py`) + the DoltHub 2021-2026 sample, via a
within-(date,dte) ATM-anchored regression, DTE-restricted to 20-45 (the strategy's actual window).
Real OTM put skew is far steeper and more convex than the old symmetric model
(`skew_slope=1.00, curv=2.50`); refit as a PIECEWISE put/call curve (puts: `slope=2.34, curv=19.51`;
calls: `slope=6.21, curv=20.0`, since the two wings have genuinely different curvature) in
`synthetic_generator.py::_iv_surface`. Weighted R²=0.95-0.98 on held-out moneyness bins.

**2. Bid-ask spread was flat 0.8% regardless of delta or VIX.** Measured real spreads from the same
sources: 0.52% at 30Δ widening to 1.6% at 5Δ (thin OTM liquidity), plus a real VIX-regime effect
(~0.81% spread at VIX<20 rising to ~1.13% at VIX 25-35). Replaced with
`_spread_fraction(delta, vix)` = `0.443% + 0.0572%/delta`, ×`(1+0.05·(vix-20))` above VIX 20.
Matters because friction scales with contract COUNT while credit scales with WIDTH — at real
spreads a $5-wide wing pays ~11% of gross credit in round-trip friction vs ~1.5% for a wide
delta-selected wing, a ~7x penalty that the flat old model hid.

**3. Base vol level ran ~20-30% rich for 2024-2026 specifically — the OOS window every recent
result draws from.** `src/data_fetchers/vol_level_calibration.py` (new): the old
`vix_scale=0.95/vix_offset=0.015` constant implied a ~1.0-1.05 ATM-IV/VIX ratio; real DoltHub data
shows that ratio has been secularly declining (2022 1.04 → 2023 1.07 → 2024 0.96 → 2025 0.88 →
2026 0.91, weighted R²=0.74). Refit as a time-varying linear-in-year ratio
(`_vix_level_ratio(date)`), held FLAT at the 2022 value for any date before 2022 (no options data
exists anywhere in this project pre-2021, so nothing supports projecting the trend further back —
2008-2021 pricing, including the entire GFC stress-test window, is best-effort, not validated).
Net effect after all three fixes, validated against the live-chain overlap: put price error at
K/S 0.86-1.00 improved from +26%..+52% (skew-only fix) to -19%..+5% (all three fixes) — real
improvement, not perfect; the deep-OTM tail (where the 0.08-0.10Δ long leg lives) still runs
~15-19% cheap, an acknowledged residual.

**Regenerated all three synthetic datasets** on the corrected generator:
`SPY_synthetic_options_2018-01-01_2026-07-10.csv` (main), `..._2008-01-01_2009-12-31.csv` (GFC),
and a new `..._2008-01-01_2026-07-10.csv` (full continuous span, 4.79M contracts) built by
`scripts_gen_2008_2026.py`.

**Validation pipeline** (`compare_width_frontier.py`, `validate_finalists.py`,
`run_full_span_backtest.py`, `stress_test_gfc.py` — all new/extended):

- *140-trial grid* (short_delta {0.16,0.20,0.24,0.30} × wing {w5,w10,w15,w20,w30,d08,d10} ×
  max_risk_percent {5,10,15,20,30}) → `backtest_results/width_frontier_full.csv`,
  `charts/width_frontier_full.png`. Top Sharpe 0.66 (0.30Δ/w10/30%risk) is NOT statistically
  distinguishable from a no-skill search: deflated Sharpe ratio 0.050 (need >0.95), expected
  best-of-124-trials-under-luck is 1.22, haircut Sharpe is negative. **The grid-search "winner"
  should not be trusted as a discovered edge on its own.**
- *Walk-forward IS(2018-23)/OOS(2023-26) on 9 pre-registered finalists* (not grid-search winners —
  chosen before looking, to avoid repeating the grid's own overfitting): fixed-$5/$10-wide 0.20Δ
  structures show NEGATIVE in-sample Sharpe (-0.57, -0.43) over 2018-2023 (they lose money through
  COVID + the 2022 bear); delta-selected wings hold up better (IS Sharpe -0.09 to +0.40 depending
  on delta/long-delta).
- *GFC (2008-09) replay, 14 scenarios*: delta-selected wings with a far (0.08-0.10Δ) protective
  leg lose 3-5x less than fixed-width equivalents (best: 0.30Δ/0.08Δ/15%risk at -1.85% total,
  -2.47% maxDD vs 0.20Δ/$5-wide at -11.77%/-13.88%). Caveat: thin samples (15-25 trades/2yr) and
  the vix_max=35 gate suppresses entries during the worst VIX spikes (30% of GFC trading days had
  VIX>35, concentrated in Sep2008-Apr2009) rather than the structure surviving full exposure —
  read as "avoided the crash" more than "weathered the crash." **Tested directly**: reran the
  0.30Δ/0.24Δ finalists with vix_max=999 (no ceiling) — the fixed-width structure's loss MORE
  THAN DOUBLED (grid_w10: -11.1%→-26.0% total, -15.3%→-29.3% maxDD, 47→51 trades), while the
  delta-selected wings barely moved (grid_d08: -1.85%→-2.40%; grid_d10: -2.87%→-4.52%;
  prior_d10: -5.59%→-5.83%). Mechanism: fixed-width strikes don't adapt to vol, so a new $10-wide
  entry at VIX 80 gets thin, badly-placed protection; a delta-selected wing re-picks its strikes
  off the day's vol, so its protection widens automatically as VIX explodes. This is a 4th
  independent signal against the fixed-width/30%-risk structure specifically.
- *Full continuous 2008-2026 backtest, 9 finalists* → `backtest_results/finalists_full_span.csv`:
  answers the actual full-span CAGR/Sharpe/return question directly rather than stitching disjoint
  windows. Best non-alarming candidate: **0.30Δ/0.10Δ, 15% risk — CAGR 5.7%, Sharpe 0.46, maxDD
  -17.1%**. The 30%-risk fixed-$10-wide config posts the best raw numbers (CAGR 13.4%, Sharpe 0.58)
  but with a -57.5% max drawdown — essentially SPY's own GFC decline — so not recommended despite
  the headline Sharpe.
- *Cost sensitivity* (fill_fraction × spread_multiplier grid on finalists) → `backtest_results/cost_sensitivity_full.csv`.

**0.08Δ vs 0.10Δ long leg — a genuine tradeoff, not a clean winner (correcting an earlier claim
mid-investigation):** the grid, full-span backtest, and walk-forward all show 0.10Δ beating 0.08Δ
on Sharpe/CAGR at every short delta tested (e.g. full-span 0.30Δ: Sharpe 0.46 vs 0.17) — the extra
protection at 0.08Δ mostly goes unused in calm years, costing collected premium. But the GFC
replay shows the OPPOSITE: 0.08Δ preserves capital better in an actual crisis (-1.85% vs -2.87% at
0.30Δ/15%risk). Mechanism confirmed directly: 0.08Δ produces a wider spread (avg $19.80 vs $15.16
at 0.20Δ/20%risk) → fewer contracts fit the same risk budget (2.41 vs 2.64) → less correlated
exposure when a crash hits everything at once. **Use 0.10Δ for normal-regime Sharpe, 0.08Δ if
crisis tail protection is the priority — there is no dominant choice.**

**Capital-size dependency, quantified:** the winning wide/delta-selected structures need
$820-1,870 max risk per contract. At a $20k account and 15-30% risk budget that's 1-3 contracts,
comfortably sizeable. At a **$2,000** account, a single contract of even the best-performing
structure would consume 45-94% of the entire account — the width choice that wins at $20k is not
executable at $2k. Below roughly $5-8k, narrow ($5-wide) or no bull-put-spread trading at all is
closer to a capital constraint than a risk-preference choice.

**Verdict on the original question (0.20Δ + fixed width vs 0.24Δ/0.08Δ "optimal"):** neither. The
stated mechanism (delta drift raising PITM probability) doesn't hold up — at an equal risk budget
a narrow spread has the same max loss with a *higher* chance of realizing it. But the destination
(move away from very wide, very levered structures) was directionally right for a different
reason: capital granularity and friction, not delta drift. Recommended starting point at a $20k
account: **0.20-0.30Δ short, 0.08-0.10Δ long (delta-selected, not fixed-width), 15-20% risk
budget** — not the fixed $5/$10 width originally proposed, and not the 30% risk budget the
"adopted" config used (every severe drawdown in this project's history, old model and new, traces
to that 30% figure, independent of wing choice).

**Known unresolved limitation:** all 2008-2021 pricing (flat-extrapolated vol level, no skew
ground truth) is best-effort. The relative ranking between structures is far more trustworthy than
any absolute CAGR/Sharpe number quoted above.

### Addendum — post-fix re-validation continued past the sections above (2026-08-09, same day)

Further rounds of testing, prompted by direct pushback on early claims, materially updated two of
the findings above. Full interactive report with charts:
`backtest_results/` (grid/walkforward/GFC/full-span/cost-sensitivity/exit-params/covid CSVs) +
published artifact (see repo owner for link).

- **0.08Δ vs 0.10Δ reversed on the level-corrected grid.** The original 0.08Δ recommendation above
  was made on data that still had the vol-level bug; once fixed, **0.10Δ beats 0.08Δ on Sharpe/CAGR
  at every short delta tested** (grid, full 2008-2026 continuous span, and walk-forward all agree),
  e.g. full-span 0.30Δ: Sharpe 0.46 (0.10Δ) vs 0.17 (0.08Δ). GFC-specific capital preservation
  still favors 0.08Δ (a genuine, narrower tradeoff than first stated, not a clean win either way).
- **GFC replay was gating out the worst days by construction.** Every GFC scenario used
  vix_max=35, but 30% of GFC trading days had VIX>35 (concentrated in Sep2008-Apr2009). Rerunning
  with vix_max=999 (no ceiling) on the 0.30Δ finalists: the fixed-width structure's loss **more
  than doubled** (grid_w10: -11.1%->-26.0% total, -15.3%->-29.3% maxDD), while delta-selected
  wings barely moved (grid_d08: -1.85%->-2.40%; grid_d10: -2.87%->-4.52%) -- a fixed width doesn't
  reprice its protection as vol rises, a delta-selected wing does. 4th independent signal against
  the fixed-width/30%-risk structure.
- **Cost sensitivity (fill_fraction x spread_multiplier) on 6 finalists**: only 0.30Δ/0.10Δ/15%risk
  stays Sharpe-positive (+0.06) under the worst assumptions tested (100% fill, 3x spreads);
  everything else including 0.30Δ/$10-wide/30%risk (0.66->-0.24) goes negative.
- **Exit parameters (profit_target 0.4-0.8 x stop_loss 0.5-0.9) do NOT rescue $5-wide**: Sharpe
  stayed -0.19 to -0.37 across all 9 combinations tested (0.20Δ, 2018-2026 window) -- the friction
  penalty is paid at entry, independent of exit timing. The delta-selected comparison structure
  stayed positive throughout (+0.08 to +0.21) and improved with a HIGHER profit target than the
  0.60 used everywhere else in this investigation -- a separate, smaller finding worth a future
  look.
- **100% risk_percent stress test, 9 finalists x {$2k, $10k, $20k, $100k} accounts, full
  2008-2026 span**: every structure at every account size showed max drawdown in the 60-99.6%
  range. Account size does NOT change the outcome of over-leveraging -- $100k lands within a point
  or two of $20k on every structure, confirming leverage risk is scale-invariant. $2,000 cannot
  fund even one contract of any tested structure at a sane 15-20% risk budget (needs 45-94% of the
  account per contract); ~$10-12k is the rough floor for one contract, $20k+ is the tested,
  validated 2-3-contract zone this investigation's headline numbers were built on.
- **COVID-19 (Feb19-Apr7 2020) trade counts**: 1-2 trades per structure regardless of width/delta
  -- the ~7-week window is too short for a ~30-day-DTE strategy to show a turnover difference the
  way the 2-year GFC window did. Dollar P&L still separates: -$1,953 to -$5,190 across finalists,
  smallest for the 15%-risk delta-selected wings.

**Updated final recommendation** (supersedes the "New recommended baseline" above):
0.24-0.30Δ short / **0.10Δ** long (delta-selected, not fixed strike_width), **15-20% risk budget**,
**$20,000+ account** (below ~$10-12k, no structure funds even one contract sanely). Use 0.08Δ
specifically if GFC-style tail protection is prioritized over normal-regime Sharpe. Config.yaml's
long_delta is 0.10 (matches this); short_delta is 0.24 as the steadier of the two solid choices
tested -- 0.30Δ posts better raw numbers repeatedly but has a documented history of being the most
fragile structure under stress across two separate pricing-model iterations now, including this one.

### Results — fixed $5 strike-width wing loses to delta-selected wing; strike_width option added (2026-08-02) — SUPERSEDED, see above

Added `entry.strike_width` to `VerticalSpread.generate_entry_signal` (src/strategies/vertical_spreads.py):
pins the long wing a fixed dollar width further OTM than the short leg (puts: short − width, calls:
short + width), taking precedence over `long_delta`; guards — distinct strikes, leg existence,
debit/credit sign — already reject degenerates, and a None short strike (delta tolerance miss)
now skips the day before the width math. Intended for credit spreads; debit spreads reject via
the sign guard. Added `compare_strike_width.py` (reuses the existing synthetic CSV; runs the full
2018-01-02..2026-07-10 and 2024-01-02..2026-06-30 windows) → `charts/bull_put_width_comparison.png`
(6 metric panels + equity-curve overlay + stats table).

**Verdict: the delta-selected wing (control, 24Δ/10Δ) beats both $5-wide variants on every
risk-adjusted metric in both windows.** Full window — control: Sharpe 1.08, maxDD -43.1%, PF 1.65,
606 trades, +1173%; w5-24d: Sharpe 0.95, maxDD -49.7%, PF 1.50, 829 trades, +1145%; w5-20d:
Sharpe 0.84, maxDD -46.4%, PF 1.48, 731 trades, +641%. 2024-26 — control: Sharpe 1.63, maxDD
-30.3%, +205%, 170 trades; w5-24d: Sharpe 1.28, maxDD -39.5%, +191%, 228 trades; w5-20d: Sharpe
1.21, maxDD -38.5%, +152%, 205 trades. Mechanism: the $5 wing collects ~$1.00-1.04 credit/contract
vs $2.18-2.83 dynamic (width $13.8-17.9), so fixed-risk 30% sizing runs ~3x the contracts (24-30
vs 5-12) with the same budget — deeper drawdowns, more commission drag, lower win rate (66.5-68.8%
vs 72.3-73.5%). Saved per-window CSVs: `backtest_results/strike_width_{full,2024-26}.csv`.

### Results — vix_min floor sweep finds 17.5 sweet spot; vix 10-35 adopted; README + chart (2026-08-02)

Ran a vix_min × vix_max sweep on the robust 30 DTE / 24Δ/10Δ bull put (pt .60/sl .50/dte_min 22,
full 2018-01-02..2026-07-09 window, $20k fixed-risk 30%): 17.5 scores the best Sharpe/PF
(1.15 / 2.06, maxDD -35.6%, 319 trades, +847%) but the user's **adopted config is vix 10-35** —
the always-on variant: **Sharpe 1.08, Sortino 1.20, maxDD -43.1%, PF 1.65, 606 trades, +1173%**
(full window) and **Sharpe 1.63, maxDD -30.3%, +204.7%, 170 trades** on 2024-01-02..2026-06-30
(vs vix_min 20: Sharpe 1.24, maxDD -16.4%, 41 trades, +67%). The vix_max 30 cap loses on the full
window (Sharpe 1.00-1.02) — it only helped in crisis sub-windows, so vix_max 35 stands. VIX
distribution check (cached `vix_history.csv`): past 24 months VIX ≥ 20 on only 24.6% of days
(2024: 9.9%), which is what starves the vix_min 20 gate; vix_min 15 is gate-open 87% of days.
Updated `README.md` "Recommended Settings" with the adopted bull put configuration
(30 DTE / 24Δ/10Δ, VIX 10-35, pt 0.60, sl 0.50, dte_min 22) + the vix_min tuning table, and added
`make_bull_put_metrics_chart.py` → `charts/bull_put_vix10_35_metrics.png` (metrics dashboard,
vix 10-35 highlighted vs 15/17.5/20, both windows).

### Results — GFC (2008-09) bull put stress test (2026-07-31)

Added `stress_test_gfc.py`: regenerates the synthetic dataset for 2008-01-01..2009-12-31 (real
SPY/^VIX/^VIX3M/^VIX6M history; ^VIX9D pre-2011 fallback handled by the generator) and backtests
5 bull-put scenarios through the GFC to answer (a) how the strategy's 2018-26 search champions
hold up in the worst SPY drawdown on record (-57% peak-to-trough, VIX 80.9), and (b) what a
vix_max crisis gate is worth. Dataset: `data/processed/SPY_synthetic_options_2008-01-01_2009-12-31.csv`.

**Results (2008-01-02..2009-12-31, $20k fixed-risk 30%):** the in-sample Sharpe champion
(30 DTE / 30Δ/8Δ, no VIX gate, pt .45/sl .50/dte_min 18) goes **negative through the GFC —
Sharpe -0.45, maxDD -48.3%, -22%** — confirming it was a truncated-search (grid-edge) artifact,
not a real edge. The user's 30 DTE / 20Δ/10Δ (vix 20-35, pt .60/sl .90/dte_min 22) is
**-3.2% total, -17.9% maxDD** (effectively flat, survives the GFC intact). Best of the tested
set: 30 DTE / 24Δ/10Δ (vix 20-35, pt .60/sl .50/dte_min 22) — **+10.3%, maxDD -17.7%**.
vix_max sensitivity on the 20Δ/10Δ set: cap 25 → **worse** (-16.6%, 19 trades — fewer, unluckier
trades, no edge from the gate); cap 30 → best DD (-13.3%) but flat (+0.8%). Conclusion: the
spread structure + dte exit, not the vix_max gate, is what survives a true crisis; the
pre-registered VIX>30 skip (2026-07-19 changelog) adds protection in the 2018-26 window without
helping here. Also closes the vix_max search gap: the optimizer only ever swept vix_min
(10/15/20/25), keeping vix_max fixed at config (bull_put 35, bull_call/bear_put 17,
call_calendar 25, iron_condor 40).

### Results — Bull put regime attribution + pre-registered overlay validation (2026-07-19)

Added `src/utils/regime.py` (fixed-rule VIX-level, VIX IV-rank, SPY-trend, and composite regime
labels/gates — zero fitted thresholds, reuses `vix_gate`/`trend_gate`), `regime_attribution.py`
(Phase 1 diagnostic: labels every trade/day of a single continuous full-window backtest by regime,
no search) and `regime_overlay_validation.py` (Phase 2: 6 pre-registered entry-gate overlays
scored honestly via `walk_forward.evaluate_oos_continuous` on the walk-forward IS params, NOT
`--final`, since `--final` already saw the OOS dates).

**Phase 1 (diagnostic):** both the walk-forward and `--final` parameter sets show the same
pattern — composite "risk-on" days (bull trend + VIX<25) score Sharpe 2.2-2.5 with -8% to -17%
isolated drawdown; composite "stress" days (VIX>=25 or bear trend) score ~0.1 to -0.16 Sharpe with
-48% to -63% isolated drawdown. The worst full-window drawdown episode for BOTH param sets is the
same 2022 rate-hike bear (peak Jan/Apr 2022 → trough Sep/Oct 2022) — not 2020 COVID or 2018
Volmageddon. Counter-intuitively, "VIX IV-Rank >= 50" (the tastytrade rich-premium heuristic)
scores Sharpe -3.2 to -5.9 with -72% to -93% isolated drawdown — the opposite of the textbook
expectation — while IV-Rank < 50 scores +2.5 to +2.9. As of 2026-07-17, current conditions
(VIX 18.8, IVR 30, SPY trend bull) classify as composite "risk-on" — the strategy's best
historical bucket, not a distinct/adverse regime, at least by this VIX+trend regime definition.

**Phase 2 (honest overlay validation, walk-forward IS params, OOS-scored):** baseline (no
overlay) OOS Sharpe 1.195 (46 trades, -20.1% DD). All 6 pre-registered overlays beat baseline
except V2 (IVR>=50 entries only: Sharpe collapses to 0.15 on 5 trades, confirming the Phase 1
warning). Best: **V1 "skip entries when VIX>30"** — Sharpe 1.526, -13.8% DD, 45 trades (barely
fewer than baseline's 46 — nearly free). **V5 "IVR<50 only"** scored highest (Sharpe 1.616,
-14.2% DD) but cuts to 41 trades. Deflated-Sharpe on the best-of-7 (V0-V5 + V3b) selection: DSR
0.931 — short of the 0.95 PASS bar but far stronger than the original 1000+-trial numeric search
(bull put walk-forward DSR 0.65; calendar DSR 0.004), because a 7-variant pre-registered set adds
far less selection risk than an open-ended grid.

**Recommendation:** add "skip entries when VIX>30" (V1) as a production overlay on the `--final`
params — minimal trade-count cost, meaningfully shallower drawdown, high face-validity (avoids
opening new short-premium risk during acute vol spikes). Treat V5 (IVR<50) as a promising but
second-order finding pending Phase 3 diagnosis, since it inverts a market convention and its
mechanism (IV-rank spikes on the VIX complex co-occurring with market-wide crisis, unlike a
single-stock IV rank) is a hypothesis, not yet verified. Phase 3 (per-regime *parameter* refit,
not just an entry gate) is GO per the plan's own criterion (composite/IVR Sharpe spread >2.0 with
>=30 trades/regime) but not yet run — pending user decision given its multi-hour compute cost and
required engine changes.

### Results — Bull put vs. call calendar walk-forward comparison + bull put production fit (2026-07-16 to 2026-07-18)

Ran both strategies' walk-forward validation under the identical current config ($20k, 30% risk
cap, 2018-01-02..2026-07-10, IS 2018-2023 / OOS 2023-12-21..2026-07-10) for an honest, apples-to-
apples comparison — the previous calendar result on disk predates the config change and used a
2021-2026 window that excludes the 2018 Volmageddon, Dec-2018 selloff, and 2020 COVID crash
entirely, so it was not a fair comparison basis.

| | Bull Put | Call Calendar |
|---|---|---|
| OOS Sharpe | 1.19 | 2.06 |
| OOS return | +83% | +456% |
| OOS trades | 46 | 288 |
| OOS max drawdown | -20% | -29% |
| Deflated Sharpe (IS search) | best 1.10 vs benchmark 0.95 → **DSR 0.65** | best 1.89 vs benchmark **2.95** → **DSR 0.004** |

**Recommendation: bull put, not calendar, for real capital.** The calendar's headline numbers are
larger, but its deflated-Sharpe check is far worse — the best of ~950 trials actually UNDERSHOT
the Sharpe expected from pure chance across that (wide) grid, meaning the search provides no
statistical basis to call the result skill rather than noise. This is consistent with the
2026-07-12 audit's finding that a long calendar's edge in this dataset is entangled with a
term-structure premium the generator bakes in from real VIX9D/VIX/VIX3M/VIX6M history (calendars
are structurally long that premium) — OOS "survival" may reflect the dataset's structural
contango bias more than a market inefficiency. Bull put's DSR (0.65) is also below the 0.95 PASS
bar but at least clears the no-skill benchmark, and its search space is narrower/economically
motivated (tastytrade-anchored), reducing the raw opportunity for search overfitting. Before
trusting the calendar further: revalidate on real quoted chains (OptionsDX/DoltHub, not the
VIX-calibrated synthetic generator) with a tightened parameter grid.

**Bull put `--final` production fit** (all 8.5 years, no holdout — 1,500 Optuna trials, ~37h):
`dte target=30, short_delta=0.30, long_delta=0.08, profit_target=0.45, stop_loss=0.50×max-loss,
dte_min=20, vix_min=10`. Full-window Sharpe 1.36 (deflated-Sharpe DSR 0.881, still below the 0.95
PASS bar — expected, since this fit has no holdout to test against). Max drawdown -47%, deeper
than the OOS-only slice (-20%) because it spans the full 2018-2023 stress years compounding
continuously. Shifted modestly from the walk-forward's IS-chosen params (wider VIX entry band
10 vs 20, tighter stop 0.50 vs 0.70, earlier profit-take 0.45 vs 0.55) — expected when fitting on
8.5y vs the 6y IS slice. Recommend trading these `--final` params (per the script's own design:
walk-forward already confirmed the edge survives OOS in this region of parameter space) with
half-Kelly sizing given the still-weak DSR and the depth of the full-window drawdown.

### Changed — $20k account, 30% risk cap, 8.5-year backtest window (2026-07-15)

- `backtest.initial_capital` 10000 → **20000**; `position_sizing.max_risk_percent` 10 → **30**.
  Together these lift the per-entry risk budget from $1,000 to ~$6,000: a 30Δ/10Δ SPY put spread
  runs ~$2.5-4k max risk per contract, so the old budget sized every wide-delta entry to 0
  contracts and silently restricted any vertical optimization to narrow spreads.
- `synthetic_data.start_date` 2021-01-01 → **2018-01-01** and end extended to **2026-07-10**
  (backtest window matched): the window now contains the Feb-2018 Volmageddon, the Dec-2018
  selloff, the 2020 COVID crash and the 2022 bear — the stress regimes a short-put strategy must
  be optimized THROUGH, not around. Dataset regenerated (VIX complex fully covered, 2,140 days).
- `optimization.min_trades` 10 → **15** (floor scales with the longer history).
- Stale bull_put comments corrected (profit_target/stop_loss/dte_min descriptions didn't match
  their values).

### Fixed — Bull put spread backtest was structurally broken (2026-07-15)

A review of the vertical-spread path ahead of a bull put optimization found the same failure
class the 2026-07-12 calendar audit fixed — plus two parameter-mapping bugs that made the
`optimize_bull_put_spread.py` search a no-op:

- **Expiration pinning (`vertical_spreads.py`, `optopsy_wrapper.py`)** — verticals never pinned an
  expiration. Entry delta-targeted each leg across the WHOLE DTE window (legs could come from
  different expirations = a diagonal priced as a vertical), the wrapper booked the entry off
  `iloc[0]` at the strike (any expiration), and every exit re-quoted/DTE-checked the position
  against whichever expiration listed the strike first — usually the nearest weekly, whose
  near-zero time value systematically faked credit-spread profits and fired the DTE exit on the
  wrong calendar. Both legs are now pinned at entry to the ONE expiration closest to the target
  DTE, the expiration is stored on the signal/legs, exits re-quote strike+expiration, and a
  position whose expiration passes settles at intrinsic value instead of lingering as a zombie.
- **`vix` grid param was an exact-match filter (`parameter_optimizer.py`)** — the vertical
  expansion set `vix_min = vix_max = value`, so an entry required the day's VIX to EQUAL the grid
  value (~never true; the calendar comment even documents the trap). Verticals now take explicit
  `vix_min` / `vix_max`, and `optimize_bull_put_spread.py` optimizes `vix_min` (premium-rich gate).
- **`dte` grid param required an exact-DTE expiration** — same expansion trap
  (`dte_min = dte_max = value`); entries could only fire on days where some expiration was exactly
  N days out. `dte` now maps to `dte_target` and the strategy pins the closest expiration within
  ± `dte_tolerance` (default 5), mirroring the calendar's design.
- **`stop_loss` grid used the wrong sign convention (`optimize_bull_put_spread.py`)** — the grid
  was `-0.60..-0.30` (the calendar's fraction-of-debit convention) but the vertical validator
  requires `0..1` (fraction of max loss), so EVERY combination raised and scored NaN/-999. Grid is
  now `0.30..0.90`.
- **Degenerate-entry guard** — entries whose expiration is already at/below the exit `dte_min` are
  refused (the calendar audit's 1-day-trade failure class), and a credit spread that would open at
  a debit (or debit spread at a credit — inverted delta targeting) is rejected.
- **Sizing uses actual max loss** — `calculate_position_size` now sizes off the real per-contract
  risk (credit: width − credit; debit: the debit) when the backtester supplies the open price,
  matching the wrapper's risk-budget accounting instead of over-reserving the full strike width.
- **Stop overshoot parity** — vertical stop-loss exits now book the `stop_slippage_percent`
  monitoring-lag overshoot like calendars (no resting multi-leg stops on Robinhood).

Known constraint surfaced (not a bug): with `initial_capital: 10000` and
`position_sizing.max_risk_percent: 10` the risk budget is $1,000, but a 30Δ/10Δ SPY put spread is
~$25-40 wide (~$2,500-4,000 max risk per contract) → 0 contracts. Wide-delta combos are only
tradeable at a higher risk cap or larger account; the optimizer will otherwise select narrow
spreads by construction.

### Fixed — Calendar leg selection degeneracy + audit fixes (2026-07-12)

A full audit of the call-calendar backtest found the engine sound and the VIX-complex synthetic
dataset clean (82.7% contango days, 0% no-arb inversions, no missing trading days, exact
reproduction of the saved optimization), **but the optimizer's "best" strategy was not a calendar**:

- **Root cause** — with `near_dte=7` and `dte_tolerance=5`, the near window was [2,12] DTE and leg
  selection took `iloc[0]` = the EARLIEST expiration, so ~60% of entries sold 2-3 DTE calls. Those
  were already at/below `dte_exit=5`, so 295/296 exits were the DTE exit with a median 1-day hold —
  an overnight VRP harvest, not a time spread. Worse, sub-9-DTE options sit BELOW the shortest VIX
  tenor (^VIX9D): `term_ratio()` clamps flat there (measured 1-3 DTE ATM IV == 9d IV exactly), so
  the sold leg was priced in the surface's pure-extrapolation blind zone.
- **Fix (strategy, `calendar_spreads.py`)** — each leg is now pinned to the expiration whose DTE is
  CLOSEST to its target (near_dte/far_dte center, or the window midpoint in min/max mode), and near
  candidates with `dte <= dte_exit` are refused at entry. The net debit is priced from the exact
  selected legs (was: a ±2-day DTE re-lookup that could match a different expiration on dense chains).
- **Fix (guard, `parameter_optimizer.py`)** — the `dte_exit < near_dte` guard now compares against
  the minimum SELECTABLE near DTE (`near_dte - dte_tolerance`, or `near_dte_min`), not the center.
- **Fix (search grid, `optimize_call_calendar_spread.py`)** — `near_dte` floor raised 7 → 14 so the
  selectable window (±5) bottoms out at 9 DTE, keeping the sold leg on market-anchored pricing.
- **Fix (generator, `synthetic_generator.py`)** — put rows recorded the flat base vol in `iv`
  instead of the surface IV `iv_k` (calls were correct). Prices/greeks were unaffected; put-side IV
  consumers (contango gate, `_estimate_iv` remarks for put calendars) were reading garbage.
  Regenerate the dataset before running any PUT-side strategy; call-side runs are unaffected.
- **Fix (engine, `optopsy_wrapper.py`)** — trading dates now come from the data's own quote dates
  (the USFederalHolidayCalendar range skipped Columbus/Veterans Day — market open, positions
  unmanaged — and included Good Fridays); `vix_exit` in trade records was read from a stale loop
  variable (off by ≥1 day); end-of-backtest force-closes now pay exit commission.
- **Config** — `require_contango: true` (its default-off rationale was the corrupt Massive data;
  the current dataset's term structure is real); stale calendar comments corrected.

Recovered (previously unsaved) walk-forward numbers for the DEGENERATE winner, for the record:
IS Sharpe 2.369 (296 trades), OOS Sharpe 2.42 (53 trades). Treat as an artifact of the above, not
as a validated edge. Re-run `caffeinate -i python optimize_call_calendar_spread.py` for an honest
result under the fixed selection.

### Changed — VIX-complex–driven synthetic chains; cost-model fix; repo cleanup (2026-06-26)

**Root cause of prior "no edge" result:** Two read-only audits confirmed DoltHub's `iv` column has
no usable term structure (near-vs-far ATM IV is a coin flip — median diff 0.0003; 49/51% contango/
backwardation vs ~80% real contango). A calendar's entire P&L is the term structure, so repricing
off it produced a flat-term-structure backtest: no edge by construction. The pipeline's `reprice_from_iv`
is innocent (it preserves per-contract IV faithfully); the data source is the limit.

**Fix — VIX-complex–driven synthetic term structure:**
- `SyntheticOptionsGenerator` now fetches `^VIX9D` (9d), `^VIX` (30d), `^VIX3M` (93d), `^VIX6M`
  (180d) daily closes from Yahoo in `fetch_underlying_data`. Four tenor points per day.
- New `_build_term_curve(date)` method interpolates those tenors into a `term_ratio(dte)` callable
  (IV at DTE t divided by IV at 30d). Real contango/backwardation regimes — including the 2020 and
  2022 inversions — now flow through to generated options prices.
- `_iv_surface()` uses `self._day_term_curve` when available; falls back to the old parametric
  formula when the VIX complex is unavailable. Not circular: the term-structure carry and the
  implied-vs-realized variance premium both come from exogenous real data the strategy can't control.
- `config/config.yaml`: `mode: synthetic`, `synthetic_data.start_date: 2021-01-01` (5-year window),
  spread_frac 0.03→0.008 + min_spread 0.05→0.01 (real SPY ATM liquidity).

**Cleanup:** Removed 287M of corrupt/stale data: `data/raw/massive/`, `SPY_real_options_2024-06-16_
2026-06-16.csv` (Massive/Polygon corrupt), intermediate real-data subsets, old synthetic CSVs (all
built on flat term structure), and stale optimization_results/ (all run on bad data).

**Next step:** Run `python generate_synthetic_data.py -y` to build the new
`SPY_synthetic_options_2021-01-01_2026-06-12.csv`, validate the term-structure acceptance test
(≥70% contango), then `caffeinate -i python optimize_call_calendar_spread.py`.

### Fixed — Massive/Polygon free-tier data is corrupt; reverted to clean DoltHub + added a data-quality gate (2026-06-25)

Investigating the calendar backtest's implausible results traced to the **data**, not just params. The
Massive/Polygon free-tier pull (`SPY_real_options_2024-06-16_2026-06-16.csv`) takes each expired
contract's daily-bar **close** as the option mid (`massive_loader.py:364`); for illiquid SPY contracts
those closes are incoherent, and bid/ask + the back-solved `iv`/greeks all inherit it.

- **Evidence (dataset-wide)** — ATM **iv/VIX median 1.35** (1.58 at 5–10 DTE, where the near leg lives;
  14.8% of ATM rows >2× VIX), and **34% of ATM (day, strike) term-structure slices INVERT** (a
  longer-dated ATM call priced below a shorter-dated one — a no-arbitrage violation). A calendar's P&L
  *is* the near-vs-far relationship, so this fabricates the edge. Neither `price_from_iv:false` (raw
  bid/ask) nor `true` (reprice off `iv`) is clean, because both trace back to the corrupt close.
- **Fix — reverted to the clean DoltHub dataset.** `config.yaml` now points `real_data` /`backtest` at
  `SPY_real_options_2021-01-01_2026-06-08.csv` (955 days, 2021–2026; **iv/VIX 0.93, 0% inversions**)
  with `price_from_iv: true` (DoltHub's `iv` is clean, its bid/ask dirty). Repriced ATM prices verify
  0% term-structure inversions; a sample backtest trades 117 times (coherent, no fabricated Sharpe).
- **New — data-quality gate** (`synthetic_generator.assess_real_data_quality` + `_enforce_data_quality`,
  wired into the real & hybrid load branches). Computes ATM iv/VIX median + term-structure inversion
  rate and **HARD-FAILS** a `corrupt` dataset (iv/VIX > 1.20 or inversions > 10%) with a clear message,
  unless `data_source.allow_low_quality: true`. Verified it rejects Massive and passes DoltHub — so a
  corrupt dataset can no longer silently produce a 5-Sharpe artifact.

### Fixed — Calendar optimizer could pick `dte_exit >= near_dte` (impossible exit) (2026-06-25)

A walk-forward run returned a "best" combo of `near_dte=7, dte_exit=11` — logically impossible:
`dte_exit` closes the trade when the **near leg** has `<= dte_exit` days left
(`calendar_spreads.py:524`), so it must be strictly less than the DTE the near leg is sold at.
With `dte_exit >= near_dte` the exit condition is already true on entry day, so the "calendar"
is force-closed after ~1 day; these degenerate trades compounded into an absurd 445,187% IS
return and a spurious Sharpe.

- **Root cause** — the optimizer relies on **disjoint** search ranges to keep orderings valid
  (`near_dte` {7..28} < `far_dte` {30..45}; `vix_min` {5..20} < `vix_max` {25..60}). But
  `near_dte` {7..28} and `dte_exit` {2..14} **overlap**, so nothing prevented `dte_exit >= near_dte`.
- **Fix** (`src/optimization/parameter_optimizer.py`) — added a validation guard in the calendar
  branch of `_run_single_backtest` (alongside the existing `stop_loss`/`vix` checks): `dte_exit >=
  near_dte` raises `ValueError`. It runs **before** the backtest, so invalid Optuna trials
  short-circuit cheaply and are dropped from the leaderboard; grid trials record a NaN metric and
  can't rank. Comment in `optimize_call_calendar_spread.py` updated to note this ordering is
  guarded at runtime (overlapping ranges), not "by construction."

### Added — Calendar entry gates (contango + VIX IV-Rank) and a Massive data-quality finding (2026-06-21)

Implemented two externally-sourced, theory-grounded entry filters for the call calendar, as **fixed
gates** (literature thresholds, not optimized parameters) so they add no degrees of freedom and don't
deflate the Deflated Sharpe. Tightened the DTE search to the research consensus. Testing the contango
gate surfaced that the Massive/Polygon free-tier option prices are not trustworthy for IV-based logic.

- **Contango gate** (`src/strategies/calendar_spreads.py`, `entry.require_contango`) — refuses entries
  in backwardation (front-month IV >= back-month IV), where a long calendar structurally loses
  (externally-sourced: contango ~+18% avg vs backwardation ~-15%). Compares the two selected legs' IV
  at the chosen strike; enforced only when both carry a plausible (0.03–2.0) back-solved IV.
- **VIX IV-Rank gate** (`src/utils/vix_gate.py`, `--vix-rank[=N]`) — a long calendar is long vega, so
  enter only when vol is cheap relative to its own trailing year. Computes IV Rank off **VIX itself**
  (a clean, liquid 30-day ATM-IV index — far better than an ATM IV reconstructed from a sparse chain):
  `IV Rank = (VIX - 252d min)/(252d max - min)*100`, gate passes when `<= N` (default 30). Fetches
  `^VIX` via yfinance with a ~420-day warmup (disk-cached to `data/processed/vix_history.csv`) so the
  rank is valid on the first backtest day. Drops into the existing `entry_gate` slot and composes
  (AND) with `--TR`. Verified live: IV-Rank<=30 passes 81% of 2024-06→2026-06 days (median rank 16).
- **DTE grid tightened** (`optimize_call_calendar_spread.py`) — far leg capped at **30-45 DTE** (was
  42-to-data-max ~90; 60+ pairings overfit and drift off the real expiration grid), near leg 7-28,
  target delta 0.45-0.55 (ATM / slightly OTM). Aligns the search with the strategy literature.
- **Finding — Massive/Polygon free-tier option prices are unreliable for IV/term-structure.** The
  per-contract daily *last-trade* prints come from 1-6 contracts/day of volume and back-solve to IVs
  **2-4x VIX**, inflated worse at short DTE (e.g. 2024-06-17, VIX 12.75: a 7-DTE ATM SPY call marks
  `last`=14.53 vs a correct ~$3.80 → IV 48.7% vs ~13%). That asymmetry fabricates backwardation on
  ~99% of days, so the contango gate (correctly) rejects nearly every entry. **`require_contango`
  defaults OFF** until run on a dataset with genuine exchange quotes (e.g. OptionsDX), where the term
  structure is real. The VIX-rank gate is unaffected — it uses clean VIX, not the option prices.

### Added — OptionsDX EOD real data + a spot-consistency fix it exposed (2026-06-15)

Integrated paid-grade OptionsDX historical SPY EOD chains, which finally gives the backtester
dense enough real quotes to stop relying on a model. The DoltHub free sample lists ~3
expirations/day, so a calendar's exact legs were almost never both quoted and ~96% of daily marks
were synthesized off a fitted IV surface (which the optimizer then gamed). OptionsDX EOD carries
**~30 expirations/day and ~240 strikes/day** out past a year, so the exact contracts are quoted
every trading day.

- **`src/data_fetchers/optionsdx_loader.py`** — converts OptionsDX monthly `spy_eod_YYYYMM.txt`
  files (WIDE: one row per date/expiry/strike with `C_*`/`P_*`) into the project's LONG schema
  (one row per contract, matching `real_chain_loader`'s DoltHub output). Globs all files under
  `data/raw/optionsdx/`, melts call+put, recomputes integer DTE, trims to a near-ATM / `dte<=120`
  band (flags to widen), merges `^VIX`, and writes `SPY_real_options_<start>_<end>.csv` so the
  existing `mode: real` path loads it with no further plumbing. 2018 → 636,194 contracts, 252 days.
- **`config.yaml`**: `mode: real`, `price_from_iv: false` (OptionsDX bid/ask are genuine exchange
  quotes — backtest them directly, don't reprice; repricing is only for DoltHub's inflated mids),
  and the `real_data` / `backtest` ranges set to the OptionsDX coverage (2018 so far).
- **Result:** on a textbook 30/60 ATM calendar, daily leg marks went from **96% synthetic → 100%
  real quotes**. The model is out of the loop.
- **Fixed — spot-consistency bug the dense data exposed.** `OptopsyBacktester` sourced the spot
  for strike selection / marks / the "underlying moved too far" exit from `underlying_data`
  (yfinance, dividend-**adjusted** ≈ $241 in Jan 2018), while strikes are quoted against the
  chain's **unadjusted** `UNDERLYING_LAST` ≈ $274. The ~13% gap fired a phantom `max_underlying_move`
  exit on day ONE of nearly every trade (89 one-day churns instead of real holds). Fix: take spot
  from the option chain's own `underlying_price` column, falling back to `underlying_data` only when
  absent — one price basis for selection, marking, and exits. (No DoltHub/synthetic regression:
  their chain spot already equals the yfinance close.) After the fix the same calendar makes 17
  proper holds (13 to `dte_exit`, 4 stops), spot reads 258–291 (correct), no phantom exits.

Honest read: that 30/60 calendar still LOST ~22% in 2018 — but 2018 had Feb "Volmageddon" and the
Q4 crash, and it's one hostile year. Download more OptionsDX years (2019–2024) for a multi-regime
read before concluding. The pipeline is now trustworthy; the data window is the remaining gap.

### Fixed — hybrid-mode IV-surface extrapolation artifact: far_dte=87 → $356M (2026-06-15)

The latest calendar optimization picked `near_dte=7 / far_dte=87 / dte_exit=5` (hold ~2 days) and
reported **$10k → $356,851,728**, a single trade **+$92,402,114**, 90% win. That is not an edge — it
is the optimizer gaming a pricing hole created by **hybrid mode + a quadratic IV surface extrapolated
past the real data**. Two compounding bugs, both fixed:

- **The IV surface was extrapolating quadratically beyond its support.** `iv_surface_fitter` fits
  `IV = c0 + c1·m + c2·t + c3·m² + c4·m·t + c5·t²` to the day's REAL quotes (10–66 DTE on DoltHub SPY),
  then priced hybrid-fill contracts at ANY DTE off it. A `far_dte=87` leg sits 21 days past the fit, so
  the `t²` term diverges and the long leg gets a fabricated IV/price with no market anchor — held 2 days
  vs a 7-DTE short, it "won" ~90% on phantom P&L, then compounded (10% risk of a growing account).
  **Fix:** `fit_day_surface` now records the `(m, t)` support; `_reprice_group` clamps evaluation `(m, t)`
  to that range before the polynomial (flat IV-extrapolation at the boundary), while Black-Scholes still
  uses the leg's *real* maturity `T`. Same `near=7/far=87` config now: **$19,766 final / $1,198 largest
  win / Sharpe 1.85** (was $356M / $92M / 26.0).
- **The far_dte cap was defeated by hybrid mode.** `optimize_call_calendar_spread` caps `far_dte` at the
  data's max DTE so trials can't request unquoted expirations — but in hybrid mode it read the *combined*
  max (synthetic fill runs to `synthetic_data.max_dte`≈90), so the cap was 90 and the search wandered
  into the 67–90 DTE pure-extrapolation zone. **Fix:** the hybrid loader now tags rows `is_fill`
  (False=real DoltHub quote, True=surface fill); the optimizer caps on **real-only** DTE when the tag is
  present → far_dte cap 90 → **66**, so 87 is unreachable.

Net: the optimizer can no longer manufacture an edge from data the market never priced. Re-run
`optimize_call_calendar_spread.py --wf` for trustworthy parameters now that the hole is closed.

### Fixed — calendar exits made real: IV repricing, daily re-marks, position-sizing death-spiral (2026-06-11)

Investigating why `profit_target` / `stop_loss` / `dte_exit` were inert on real data uncovered three
compounding issues. Fixing them makes the exits actually fire — and reveals the calendar's *honest*
edge is far smaller than the previously reported numbers, which rode on dirty pricing.

- **DoltHub bid/ask is the corrupt field; the `iv` column is clean.** For ATM ~30d calls the `iv`
  column tracks VIX (iv/VIX median **0.95**, ~2 vol-pts), but the raw bid/ask **mid implies ~1.47x
  VIX** (~8 vol-pts high) — only 0.5% are hard no-arb violations, so it's systematic level/spread
  inflation, not random garbage. Spot-checked a 28d ATM call marked **$27.48** when BS says ~$12.81.
- **Reprice from the clean IV surface** (`synthetic_generator.reprice_from_iv`, on by default for real
  data via `data_source.price_from_iv`). Every contract's bid/ask is re-derived from its own `iv` via
  Black-Scholes with a modeled spread, so entry, exit, and daily re-marks share ONE fair, internally
  consistent basis (real skew + term structure preserved — NOT flat-IV synthetic). Raw quotes kept as
  `iv_raw_bid/ask`.
- **Daily Black-Scholes re-mark of held legs** (`calendar_spreads._leg_quote` -> `_bs_quote` /
  `_estimate_iv`). When a held leg's exact contract isn't quoted on a later day (sparse chains), its
  mark is synthesized from the day's interpolated IV surface instead of the position drifting to
  near-expiration — which is *why* the exits never fired (157/159 trades used to close as "Near-term
  option expired"; now 76 dte / 50 stop / 50 profit / 1 expired).
- **Position-sizing death-spiral FIXED — the true root cause of the "1 trade" backtests.** The calendar
  sizer used worst-case `max_debit` ($10 -> $1,000 risk/contract) and, with `max_risk_percent=10%` of
  $10k = $1,000, sized exactly `int(1000/1000)=1` contract at the starting capital but `int(<1000/1000)
  =0` after **any** loss — so one losing trade dropped the account below the knife-edge and it never
  traded again. (The continuous run only survived because its first trade *won*; an isolated/early
  losing first trade is exactly the earlier walk-forward "1 trade vs 70" OOS artifact.) Fix: price the
  spread first and size off the **actual debit** (`optopsy_wrapper` reorder + `entry_price` passed to
  `calculate_position_size`); ~$6-7 real debit -> ~$650 risk -> `int(980/650)=1` survives the dip.
- **Honest consequence — the calendar shows NO demonstrable edge on cleanly-priced data.** With
  consistent pricing + working exits + correct sizing, the corrected walk-forward gives IS Sharpe 1.81
  / OOS Sharpe 0.75 (18 OOS trades) but **DSR = 0.20 (WEAK — likely overfit):** the best Sharpe (1.81)
  is BELOW the no-skill selection benchmark (2.24 expected best of 65 trials), haircut Sharpe ≈ −0.43.
  Typical (non-cherry-picked) configs sit at Sharpe ~0.4–0.5. The previously reported 2.69 IS / 1.10
  OOS rode on the inflated bid/ask — not a real edge. Parameter sensitivities are now economically
  coherent (hold longer for theta = better; tight stops get whipsawed), and the framework is now
  correctly reporting "no edge" instead of a false positive. New config knobs:
  `data_source.price_from_iv`/`reprice`, calendar `exit.synthetic_remark`. Recommendation: do NOT trade
  this calendar on current evidence; apply the same actual-debit sizing fix to the vertical/IC sizers
  and re-test those, and/or validate on cleaner data (forward-logged chains or a paid source).

### Changed — trustworthy-optimization hardening: min-trades floor, storage-smart logger (2026-06-10)

- **Minimum-trades floor in the optimizer** (`parameter_optimizer.py`, `MIN_TRADES_FOR_RANKING=10`,
  override via `config.yaml` -> `optimization.min_trades`). Trials with fewer trades than the floor
  have their Sharpe/Sortino/Calmar NaN'd, so a lucky handful of trades can't win the search and
  degenerate near-zero-volatility Sharpes (|SR| ~ 1e16) no longer poison the deflated-Sharpe
  selection benchmark. Diagnosed from a real run where 268/1000 trials had |Sharpe|>50 and the DSR
  benchmark blew up to 4.1e16. Returns/trade counts are kept for audit (`below_min_trades` flag).
- **Storage-smart chain logger** (`chain_logger.py`): a full SPY chain is ~4,500 contracts/day
  (~15 expirations x dense $1 strikes), but every strategy here trades a narrow band. The logger now
  keeps a `--moneyness` band (default +/-12%, ~30% smaller files) as the robust default, with an
  opt-in `--delta-min/--delta-max` band that cuts ~2x harder. The delta path **self-protects**: it
  only applies if it retains a plausible fraction of the chain, because yfinance IV is frequently
  ~1e-5 pre-/post-market, collapsing greeks to a degenerate 0/1 step function (a naive delta filter
  kept just 17/4,267 contracts on such a day). **No logger restart needed** — launchd reads the
  script fresh each run; only a schedule change (the plist) requires a reload.
- **More real history + expiration-grid fix** (the trustworthy-data payoff). Pulled 2021-2026 from
  DoltHub — **955 trading days** with data (2023 patchy), 5.7x the prior 167. The longer history
  exposed that DoltHub lists only ~3 expirations/day at irregular DTEs (clustered near ~{13, 28,
  60}), so the calendar's default `far_dte=42` fell in a **gap** and found no far leg (**1 trade**
  over 5 years — initially mistaken for a backtester bug). Fix: densified the optimizer's `far_dte`
  grid (step 7 -> 3) so it samples *on* the data's actual expirations, while the min-trades floor
  discards the gap-landing trials. Result: **1 -> 158 trades, a believable Sharpe ~2.3** (vs the
  synthetic 8.2 artifact). Added a `--trials=N` override for fast first-pass walk-forwards on big
  datasets; `config.yaml` backtest window now spans the full 2021-2026 history.
- **Investigated, then reverted, a far-leg expiration "snap"** for the calendar: letting the calendar
  enter when no expiration sits in the exact far-DTE window made it enter at the dataset boundary,
  where the snapped far leg can't be priced as the near leg expires (exit falls back to the entry
  price -> 0 P&L) and entries then halt -- collapsing a 16-trade backtest to 1. Root cause is a
  pre-existing exit-pricing/position fragility, not safely fixable in the strategy layer; the real
  trade-count fix is more history (above). Left as a documented follow-up.
- **FIXED — trustworthy walk-forward OOS (was the #1 follow-up).** The OOS score had been a
  measurement artifact: an *isolated* OOS-only backtest under-trades vs. the *same dates in a
  continuous run* — on the 2021-2026 calendar the OOS window scored **1 trade** isolated but **70
  trades (+$19,729)** continuous — producing false "OOS NaN / LARGE degradation — overfit" verdicts
  (and almost certainly the earlier −68 OOS). Root cause is a backtester state/boundary issue (early
  degenerate 0-P&L exits + low-capital sizing starving a fresh short window), since
  `generate_entry_signal` is a pure function of the day. **Fix:** score the **OOS slice of one
  continuous IS+OOS run** (standard walk-forward methodology) via new
  `walk_forward.evaluate_oos_continuous` + `_run_single_backtest(..., return_raw=True)`; Sharpe is
  scale-invariant (`total_value` pct-change) so the slice is comparable to IS. Wired into the calendar
  and both vertical optimizers (iron_condor uses its own grid path — noted as a follow-up). Verdict is
  now 3-tier (healthy / weaker-but-persists / collapse). **Result on the calendar: OOS Sharpe ~1.10,
  70 trades, +24.5%, −4.5% DD** — the IS edge (Sharpe 2.69, DSR 0.999 PASS, stability 2.59 on
  far_dte=60) **degrades but persists OOS**, not overfit.

### Changed — walk-forward validation is now the DEFAULT for all optimizers (2026-06-10)

- **All four `optimize_*` scripts default to walk-forward (out-of-sample) validation**; the old
  full-window in-sample fit is now opt-in via `--final`. A default run splits the window into
  in-sample (~70%) and a held-out out-of-sample (~30%) tail, optimizes on IS only, then scores the
  single winning parameter set on the untouched OOS window and prints **IS vs OOS Sharpe** + a
  healthy/overfit verdict. The in-sample max is optimistic by construction (best of N trials), so it
  should never be the default deliverable — OOS is the honest number. No runtime penalty (IS is ~70%
  of the days + one OOS backtest, so it's marginally faster than `--final`).
  - `optimize_call_calendar_spread.py`: the existing `--wf` behavior is now the default; `--wf` kept as an alias.
  - `optimize_bull_call_spread.py` / `optimize_bull_put_spread.py`: gained the calendar's full
    trustworthy bundle — walk-forward, the `stability_score` column, and the deflated-Sharpe selection check.
  - `optimize_iron_condor.py`: gained the same default-WF / `--final` contract and IS-vs-OOS verdict,
    reusing its own grid backtest so IS and OOS score identically (still a fixed grid; no DSR column).
  - `--oos-frac=` tunes the split (default `0.30`). Docs: new **Validation Modes** section in
    `guides/OPTIMIZATION_SCRIPTS_GUIDE.md`, plus `REAL_DATA_WORKFLOW.md`.

### Fixed — calendar optimizer crash on near-expiry (2026-06-06)

- **`unsupported operand type(s) for -: 'NoneType' and 'float'`** during calendar optimization. The
  calendar's "Near-term option expired" exit returned a Signal **without setting `position.current_price`**,
  so `close_position` did `None - entry_price`. It only hit certain configs (e.g. small `dte_exit`) that
  hold to near-expiry, which is why some Optuna trials failed while others succeeded. Fix: price that exit
  off the remaining far long leg (near leg settles to 0), plus a defensive engine guard that falls back to
  the entry price if any strategy ever emits an unpriced exit. Verified across 16 edge configs, 0 failures.

### Fixed — Iron Condor now runs, twice-daily chain logger (2026-06-05)

- **Iron Condor repaired end-to-end** (was crashing/non-functional):
  - `Signal()` no longer crashes — the four IC strikes + credit + expiration are attached as attributes
    instead of being passed as unknown kwargs.
  - The backtester now builds a true **4-leg** IC position (it previously only ever built 2 legs, so IC
    never entered). New `_ic_position_legs` / `_ic_leg_quotes` helpers; `_get_entry_price` prices the
    4-leg net credit.
  - IC adopts the **signed cash-flow P&L** convention (`net_open`/`net_close`), so a credit bought back
    cheaper books a WIN (it was sign-inverted before). All four legs are **pinned to one expiration**.
  - Optimizer fixes: added the missing `strategies.iron_condor` block to `config.yaml`; `--TR`-style key
    map now also applies `vix_min`/`vix_max`/`max_wing_width`; result dict read wrong keys
    (`win_rate`/`max_drawdown` → `win_rate_pct`/`max_drawdown_pct`). Verified: 159 trades, signs correct.
- **Chain logger runs twice every weekday — 10:00 and 15:00** (was once at 16:15). Files are stamped
  `SPY_chain_YYYY-MM-DD_HHMM.csv` so the morning and afternoon snapshots coexist. README updated with the
  intraday-timing/sleep nuance.

### Fixed — realistic fills & slippage (2026-06-05)

- **Asymmetric, industry-standard fill model** (new `src/utils/execution.py`: `net_open`/`net_close`).
  Fills cross a configurable FRACTION of the way from mid to the natural price (ORATS-style ~0.5-0.75
  for spreads). Planned entries/profit-target/DTE exits use `limit_fill_fraction` (default 0.5); only
  stop-loss exits use `market_fill_fraction` (1.0), since stop-limit orders aren't available. Previously
  exits filled at **mid** and `slippage_percent`/`bid_ask_spread_percent` were **never read**.
  - The Call Calendar stays **profitable across the whole fill spectrum** (+164% at frac 0.5, +144% even
    at full natural-price exits) — so the strategy isn't "broken." The real red flag is its **Sharpe 7-8
    / ~100% win rate**, which is a SYNTHETIC-DATA artifact: IV is flat across strikes AND expiries, so
    the near-leg theta decay is near-deterministic. Real calendars face term-structure shifts / vol
    crush / skew. The binding constraint is now the DATA, not the fills → use real chains (DoltHub/OptionsDX).
  - (An earlier same-day pass over-penalised exits — full spread + 2%/leg on *every* exit — which wrongly
    showed the calendar at −24%. Corrected here. Do NOT "restore +359%" as on 2025-12-03 either: that was
    the opposite error, mid-price exits.)
- **Credit-spread P&L sign fixed.** Winners (e.g. a 1.20 credit bought back at ~0) were booked as
  **losses**; the signed cash-flow convention (`entry_price` = net debit>0 / credit<0) corrects it.
- **Debit verticals can now enter.** The `spread_price <= 0` guard rejected every bull-call/bear-put;
  removed (a debit *is* a positive open cost now). Fixed degenerate `bull_call_spread` deltas (0.60/0.60
  → 0.60/0.30) and added a `bear_put_spread` config block.
- **Commission double-count fixed.** `_calculate_commission` billed 2 legs × 2 sides but was called at
  both entry and exit (~2× too high); now bills one side (2 legs) per call.

### Added — `--TR` flag, research-backed ranges, real-data logger (2026-06-05)

- **`--TR` flag on the optimizers** (`optimize_call_calendar_spread.py`, `optimize_bull_call_spread.py`,
  `optimize_bull_put_spread.py`): overlays the SPY Trend Reversal signal so trades only open on 'green'
  (bullish) days. Backed by `src/utils/trend_gate.py` (`spy_trend_gate(end, direction)`), a causal
  (shift-1) gate reused by `research_trend_overlay.py`. e.g. `python optimize_call_calendar_spread.py --TR`.
- **Reflective parameter ranges** from published studies (ORATS / tastytrade): credit spreads & iron
  condor 30-45 DTE, 16-30Δ short, manage ~50% / ~21 DTE; debit verticals 30-60 DTE, buy 50-70Δ / sell
  25-40Δ, take 50-75%; calendars sell ~near / buy ~far ATM, `far_dte ≤ 63` (synthetic DTE cap). Calendar
  optimizer trials cut 1500→1000 to fit a 5h budget (~15.9s/backtest on full history).
- **`data_collection/chain_logger.py`** — appends today's real SPY chain (Schwab via schwab-py, else
  yfinance with greeks filled from IV) to `data/raw/chains/`, in the backtester's schema. Plus a
  `launchd` plist + `data_collection/README.md` detailing macOS scheduling (launchd vs cron vs n8n vs
  GitHub Actions). Build real point-in-time history to replace the synthetic chains.
- Iron condor optimizer ranges tightened to the tastytrade standard (IC strategy repaired below).

### Added — Trend Reversal integration (ask #2/#3)

- `research_trend_overlay.py` — gates options entries by the SPY Trend Reversal signal (bull-call on
  green, bear-put on red), with a clean REAL-DATA cross-check via the trendrev engine. Honest finding:
  bull calls outpace buy & hold on the long side (leverage), bear puts lose (shorting a riser); the
  green gate trades participation for drawdown/regime control, which the real-data row isolates cleanly.
- `scanner_options_watchlist.py` — Fundamental-Scanner top-N quality names × Trend Reversal (3-day bars)
  → broker-ready defined-risk call-debit-spread templates for names that *freshly* flip green. A live
  screen (no hindsight, no synthetic P&L).
- `OptopsyBacktester(config, entry_gate=...)` — optional `callable(date)->bool` market-regime gate.
- `test_execution.py` — guards the fill-model signs and that slippage always hurts.

### Reverted

- **Risk Calculation Changes Reverted** (2025-12-03):
  - Reverted recent changes to `src/backtester/optopsy_wrapper.py`, `src/strategies/base_strategy.py`, and related files
  - **Reason**: Changes broke Call Calendar Spread backtest (reduced from ~146 trades to 4 trades, -92% return instead of +600%)
  - **Status**: Code restored to last known working state from GitHub
  - **Verification**: Call Calendar now executes 115 trades with 80.87% win rate and +359.84% return

### Added
- Documentation restructuring into focused guide files in `guides/` directory
- Streamlined CLAUDE.md to ~25 lines with emphasis on changelog and GitHub

## [2025-11-17] - IV Percentile Integration

### Changed
- **Replaced VIX Level Filtering with IV Percentile**: Complete migration from absolute VIX levels to percentile-based filtering
  - Switched from IV Rank (range-based) to true IV Percentile (count-based): `% of days in lookback where VIX < current`
  - Modified [src/data_fetchers/synthetic_generator.py](src/data_fetchers/synthetic_generator.py): Calculate IV Percentile using 252-day rolling window
  - Updated [config/config.yaml](config/config.yaml): Replaced all `vix_min/vix_max` with `iv_percentile_min/iv_percentile_max`
    - bull_put_spread: 30-80th percentile (medium-high IV for premium)
    - bull_call_spread: 20-70th percentile (lower IV acceptable for debits)
    - call_calendar: 10-50th percentile (low-medium IV preferred)
  - Updated [src/strategies/vertical_spreads.py](src/strategies/vertical_spreads.py): IV Percentile filtering logic
  - Updated [src/strategies/calendar_spreads.py](src/strategies/calendar_spreads.py): IV Percentile filtering logic
  - Updated [src/backtester/optopsy_wrapper.py](src/backtester/optopsy_wrapper.py): Propagate IV Percentile through backtester
  - Updated [src/optimization/parameter_optimizer.py](src/optimization/parameter_optimizer.py): Support IV Percentile optimization

### Added
- **Trade Export Fields**: New columns in XLSX/CSV exports
  - `iv_percentile_entry`: IV Percentile at trade entry (0-100%)
  - `iv_percentile_exit`: IV Percentile at trade exit (0-100%)
  - Kept `vix_entry` and `vix_exit` for reference

### Impact
- More robust volatility filtering using market context instead of absolute levels
- IV Percentile adapts to different market regimes (2020 crisis vs 2025 calm)
- Optimizer can now test different percentile thresholds (e.g., "only enter when IV > 40th percentile")
- Better alignment with professional options trading practices

### Data Regeneration Required
⚠️ Run `python generate_synthetic_data.py -y` to regenerate options data with `iv_percentile` column (replaces `iv_rank`)
- Note: IV Percentile calculation is computationally intensive (~5-10 minutes for full dataset)
- Uses rolling 252-day window to calculate true percentile for each trading day

### Status
✅ All code updated to use IV Percentile filtering
⏳ Synthetic data regeneration pending (user can run manually)

## [2025-11-17] - Market Hours & Holiday Filtering

### Fixed
- **Timestamp Handling**: All trade entry/exit times now use 12:00 PM ET (noon) instead of midnight (00:00:00)
  - Ensures trades are recorded at market midday, consistent with end-of-day backtesting
  - Modified [src/backtester/optopsy_wrapper.py](src/backtester/optopsy_wrapper.py) to normalize all timestamps to 12pm
  - Updated [src/data_fetchers/synthetic_generator.py](src/data_fetchers/synthetic_generator.py) to preserve 12pm timestamps

- **US Market Holiday Filtering**: Backtester now excludes federal holidays from trading days
  - Implemented `USFederalHolidayCalendar` with `CustomBusinessDay` frequency
  - Prevents trades on holidays like Christmas, New Year's Day, Thanksgiving, Independence Day, etc.
  - Automatically rolls to next trading day if exit/entry would fall on holiday or weekend

### Verified
- All 151 calendar spread trades now show 12:00:00 timestamps (previously all showed 00:00:00) ✅
- Zero trades entered on known US market holidays ✅
- Exit condition `max_underlying_move: 0.10` confirmed implemented in code (though rarely triggered)

### Impact
- XLSX/CSV export files now show proper market hours timestamps
- Backtests more accurately reflect real trading conditions
- Holiday filtering prevents unrealistic trade timing assumptions

### Modified Files
- [src/backtester/optopsy_wrapper.py](src/backtester/optopsy_wrapper.py): Added holiday calendar, 12pm timestamp normalization
- [src/data_fetchers/synthetic_generator.py](src/data_fetchers/synthetic_generator.py): Timestamp normalization to 12pm instead of midnight

### Status
✅ All trades now timestamped at market hours (12pm ET) with proper holiday filtering

## [2025-11-14] - Documentation Restructuring

### Added
- Created comprehensive guide documentation:
  - `guides/ARCHITECTURE.md` - System architecture and technology stack
  - `guides/DATA_GUIDE.md` - Data sources and synthetic generation
  - `guides/DATA_VALIDATION.md` - Quality assurance and delta validation
  - `guides/STRATEGIES.md` - Strategy implementations
  - `guides/WORKFLOWS.md` - Kelly Criterion, trade export, backtesting workflows
  - `guides/METRICS.md` - Performance metrics definitions
  - `guides/RESEARCH.md` - Research notes, known issues, roadmap

### Changed
- Reduced CLAUDE.md from 847 lines to ~25 lines
- Moved changelog to standalone CHANGELOG.md file
- Restructured project documentation for better discoverability

## [2025-11-12] - Calendar Spread Backtesting Fixes & Trade Export

### Fixed
- **6 Critical Issues** preventing Call Calendar Spread from executing trades:
  1. **Sharpe Ratio Division by Zero**: Added `std() > 0` check before calculating Sharpe ratio
  2. **Missing VIX Parameter**: Backtester now passes VIX to entry signal generator
  3. **Max Debit Too Low**: Increased `max_debit` from $5 to $20 in config (SPY at ~$530 needs $8-12 debits)
  4. **Entry Price Calculation**: Fixed to handle same-strike, different-DTE options using stored expirations
  5. **Exit Signal Pricing**: Now calculates current spread price before all exit conditions to prevent TypeError
  6. **Wrong DTE in Exit Logic**: Tracks and uses specific expiration dates from entry instead of picking shortest DTE

### Root Cause
- Calendar spreads use same strike but different expirations
- Previous code filtered only by strike, finding multiple options (1 DTE, 7 DTE, 30 DTE, etc.) and picking arbitrarily
- This caused immediate exits and pricing errors

### Solution
- Store `near_expiration` and `far_expiration` in Signal and Position objects
- Filter by expiration dates in both entry and exit logic

### Added
- **Debug Mode**: Calendar spread strategies now support `debug=True` parameter to show rejection reasons
- **Trade Export Feature**: Comprehensive trade export to CSV/XLSX
  - Export individual trade details: underlying price, VIX, dates, strikes, deltas, prices, positions
  - Support for both vertical and calendar spreads
  - Static filenames (e.g., `Bull_Put_Spread.csv`) that overwrite on each run
  - Includes leg-by-leg details: delta, price, expiration, position (+1 long, -1 short)
  - Calendar-specific fields: near_expiration, far_expiration
  - Usage: `backtester.export_trades(results, format='csv')` or `format='xlsx'`

### Modified Files
- [config/config.yaml](config/config.yaml): Increased `max_debit` to 20.0
- [src/backtester/optopsy_wrapper.py](src/backtester/optopsy_wrapper.py): VIX passing, expiration tracking, calendar-aware pricing, trade export, enhanced trade recording
- [src/strategies/calendar_spreads.py](src/strategies/calendar_spreads.py): Expiration tracking, debug mode, fixed exit logic

### Status
✅ Calendar spreads now backtest correctly with proper trade execution and exit timing; trade export available for all strategies

## [2025-10-26] - Delta Validation & IV Pricing Fix

### Added
- **Delta Validation Complete**: Comprehensive validation of synthetic data quality
  - Validated 168 delta values across 7 DTEs and 7 moneyness levels
  - 100% match with industry-standard py_vollib library
  - Created automated validation scripts (`validate_deltas.py`, `visualize_delta_decay.py`)
  - Documented delta behavior patterns and time decay
  - Confirmed alignment with industry practices (30 delta at 30-45 DTE)

### Fixed
- **VIX-Based IV Pricing**: Fixed volatility source for realistic option pricing
  - **Issue**: Previously used 14.38% historical volatility instead of VIX-based IV
  - **Fix**: Modified generator to use VIX as implied volatility proxy by default
  - **Impact**: Options now priced at realistic market levels (e.g., 27% IV instead of 14%)
  - Added `use_vix_for_iv` parameter (default: True) to SyntheticOptionsGenerator
  - Updated `generate_synthetic_data.py` to use VIX pricing

### Documentation
- Added comprehensive "Synthetic Data Validation & Quality Assurance" section to CLAUDE.md
- Consolidated DELTA_VALIDATION_REPORT.md, DELTA_INVESTIGATION_SUMMARY.md, and DELTA_EXPLANATION.md
- Included validation results, delta behavior tables, and practical examples
- Documented VIX vs historical volatility differences and impact

### Validated
- ATM deltas stable at ~0.50 across all DTEs ✅
- OTM deltas decay toward 0.00 as expiration approaches ✅
- ITM deltas converge toward 1.00 as expiration approaches ✅
- Delta values match "30-45 DTE, 30-40 delta" industry rule ✅

### Status
✅ Synthetic data now uses VIX-based IV for realistic pricing, with comprehensive validation

## [2025-10-22] - Calendar Spreads Implementation

### Added
- **Calendar Spreads**: Full implementation of time-based strategies
  - Created `src/strategies/calendar_spreads.py` module
  - Implemented `CallCalendarSpread` class for call time spreads
  - Implemented `PutCalendarSpread` class for put time spreads
  - Added `DiagonalSpread` framework for future enhancement

### Features
- Same-strike, different-expiration spread logic
- Multiple strike selection methods: ATM, delta-based, moneyness-based
- Near-term and far-term DTE targeting with tolerance ranges
- Time decay exit logic (mandatory exit before near-term expiration)
- Underlying movement exit threshold
- Profit target and stop loss based on debit paid

### Configuration
- Added `call_calendar` configuration to config.yaml
- Added `put_calendar` configuration to config.yaml
- Added `call_diagonal` and `put_diagonal` configurations
- Comprehensive exit rules including DTE exit, profit targets, and stop losses

### Documentation
- Updated CLAUDE.md with calendar spread descriptions
- Added calendar spread strategy parameters
- Updated architecture diagram with calendar_spreads.py
- Added calendar spread goals and use cases

### Architecture
- Calendar spreads inherit from BaseStrategy
- Compatible with existing backtester framework
- Supports same position tracking and performance analysis

### Status
✅ Calendar spreads ready for backtesting alongside vertical spreads

## [2025-10-17] - Evening Update: Synthetic Data Generation

### Added
- **Data Solution Implemented**: Synthetic options data generation
  - Created `src/utils/black_scholes.py` - Complete Black-Scholes pricing and Greeks
  - Created `src/data_fetchers/synthetic_generator.py` - Full synthetic data generator
  - Based on research from `aspiringfastlaner/spx_options_backtesting` GitHub repo
  - Uses actual SPY prices from Yahoo Finance with Black-Scholes pricing
  - Generates realistic options chains with Greeks (delta, gamma, theta, vega)

### Documentation
- **Free Data Sources Documented**:
  - OptionsDX: Free EOD data back to 2010 (requires signup)
  - Polygon.io: Free tier with 2 years options data (5 API calls/min)
  - Synthetic generation as primary recommendation
- Added detailed "Synthetic Options Data Generation" section to CLAUDE.md
- Documented methodology, accuracy considerations, and limitations
- Research-backed accuracy benchmarks (88% R² in normal markets)
- Clear guidance on when synthetic data is/isn't appropriate

### Tools
- Created `generate_synthetic_data.py` script for easy 2-year dataset generation
- Updated README.md with data generation instructions
- Updated `load_sample_spy_options_data()` to use synthetic generator

### Status
✅ Ready to generate 2+ years of free SPY options data for backtesting

## [2025-10-17] - Initial Setup

### Added
- Initial project setup
- Created CLAUDE.md documentation
- Defined architecture and data strategy
- Researched free data sources and limitations
- Selected Optopsy as primary backtesting framework
- Created all core modules (strategies, backtester, analysis, data fetchers)
- Built complete framework with example notebooks and scripts

### Status
✅ Foundation complete, ready for implementation

---

**Project Status**: 🚀 Ready for Backtesting - Vertical & Calendar Spreads Implemented
