# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
