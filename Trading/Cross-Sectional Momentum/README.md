# csmom — Multi-Strategy Trade-Idea Engine

**Primary strategy (as of 2026-08-05): a 3-way fixed-weight blend** —
40% SPYM (growth) / 30% macro regime tilt / 30% multi-asset absolute-momentum
rotation — rebalanced **monthly** (last trading day of each month), holding
shares with drift in between. `ideas` outputs the **exact target book the
backtest trades**: every ticker, its sleeve, target weight, and (given
capital) dollars, plus the rebalance trade list vs your last book.

> The growth sleeve holds **SPYM** (State Street SPDR Portfolio S&P 500 ETF,
> 0.02% expense ratio) rather than SPY (~0.09%) — identical S&P 500 exposure
> at a lower ongoing cost. Configurable via `blend.growth_ticker` in
> `config.yaml`. The benchmark shown in every report ("SPY buy-and-hold")
> always stays literal SPY regardless of this setting — that's a fixed
> reference for comparison, not a statement about what's held.

The original **equity cross-sectional momentum engine** (ranks S&P 1500
stocks by a composite momentum score, weekly rebalance) is preserved intact
and fully working under the `equity-*` commands — see
[Equity engine (secondary)](#equity-engine-secondary) below. It is no longer
the default because repeated testing (sector-neutral, beta-capped,
inverse-vol-weighted, and a real inverse-ETF hedge) never found its
stock-picking alpha to be statistically significant (t ≈ 0.4–1.1 across every
variant tried) — its returns are well explained by market beta alone. The
blend uses SPY as a fair, simpler substitute for that same beta exposure and
adds two genuinely diversifying sleeves on top.

> **Why the blend, briefly:** its edge is **diversification across three
> weakly-correlated return streams**, not stock-picking skill — the classic,
> well-established portfolio-theory effect of combining imperfectly-correlated
> strategies. Validated OOS Sharpe 1.316 vs SPY buy-and-hold's own 1.344 over
> the identical window, but MaxDD -8.6% vs SPY's -18.8% (less than half) — the
> drawdown reduction is the more robust, better-established claim than any
> specific Sharpe edge, which is window-dependent (see *Validated results*).

> **Universe note:** `fetch` builds point-in-time S&P 1500 membership (for the
> equity engine) and downloads the full price panel both strategies need,
> including the blend's macro/rotation ETF universe (11 sector SPDRs, TIP,
> LQD, IEF, TLT, GLD, DBC, DBMF, BTAL, SHY, EFA, EEM, AGG, RWR). Run it once;
> `ideas` auto-refreshes prices daily on its own after that.

---

## Quick start

```bash
# 0. Install dependencies (once)
pip install -r requirements.txt

# 1. Build the PIT universe + download the full price panel (20–40 min; re-run monthly)
python csmom.py fetch

# 2. Run the walk-forward backtest + validation (re-run after fetch or config changes)
python csmom.py backtest

# 3. Generate today's target blend book + trade list (run any trading day — prices auto-refresh)
python csmom.py ideas --capital 100000
```

That's it. The book prints to console and is written to
`outputs/blend_ideas_TIMESTAMP.json`, plus `outputs/blend_book.json`
(persisted state used for next month's rebalance diff).

> **Cold start (first time deploying real capital):** with no prior book on
> disk, `ideas --capital N` computes and shows the *currently valid* target
> book directly — no `--force` needed. It will show every position as a BUY.
> This book was decided on the most recent month-end that has already passed;
> you are not "waiting" for anything by starting today.

> **Ongoing workflow:** run `python csmom.py ideas` (capital is remembered
> from your first run) on or shortly after the **1st of every month** — this
> reliably catches each month's completed rebalance with only a 1–2 day lag,
> matching the backtest's own 1-day execution-lag convention (decide at the
> last trading day of the month's close, execute at the next open). Safe to
> also run it daily/from cron if you want: it **self-gates** on the real
> monthly rebalance calendar and prints a `HOLD` status with zero trades on
> any day that isn't a rebalance — no network refresh, no new output files.
> Pass `--force` to rebuild off-schedule anyway (e.g. after a config change).
>
> **Between rebalances, let the weights drift — do not top up to target.**
> Hold-with-drift is exactly what the backtest simulates; rebuying to the
> exact target mid-month is a different (untested) strategy.
>
> `verify-book` asserts the live book equals the backtest engine at any time.

> **Tip:** `python csmom.py` with no arguments opens an interactive menu if you prefer.

---

## What each command does (plain English)

### Step 1 — `fetch` (run once, then monthly)

Downloads the full price panel both strategies need: the PIT-reconstructed
S&P 1500 (for the equity engine, kept up to date even though it's secondary
now) plus the blend's ETF universe (sector SPDRs, TIP/LQD/IEF/TLT/GLD/DBC/
DBMF/BTAL/SHY, EFA/EEM/AGG/RWR). First run takes 20–40 minutes; after that
under a minute.

**You do not need to run `fetch` before each `ideas` run.** `ideas`
auto-refreshes the price cache whenever it detects the cache is behind by
even one trading day. Run `fetch` monthly, or whenever you want the PIT
membership table itself refreshed.

### Step 2 — `backtest`

Walk-forward backtest of the **blend**: splits the date range 70%
in-sample / 30% out-of-sample, validates on the OOS period only. Simulates
the real live process — monthly rebalance to the fresh 3-sleeve target
(40% SPYM / 30% macro tilt / 30% rotation), then holds those shares and lets
the weights drift until the next month-end, charging costs on actual
turnover. Reports: alpha/beta vs SPY, a 5-fold walk-forward consistency
check (worst fold matters more than the average), per-year and crisis-window
breakdown, rolling 12-month window distribution, and the Deflated Sharpe
Ratio deflated against every blend-weight split ever tried
(`config.yaml → blend.trial_sharpes`).

Output: `outputs/backtest_TIMESTAMP_blend.[txt|json|png]`

### Step 3 — `ideas [--capital N] [--force]`

**The only command you need to run monthly** (safe to run daily/from cron
too — see *Quick start* above for the self-gating behavior). Auto-refreshes
prices from Yahoo Finance if the cache is stale, with the same partial-download
safety and dividend/split re-basing detection as the equity engine had.

Builds the exact target blend book — the same engine the backtest trades —
via `blend.target_book`, and prints every holding with its **sleeve**
(growth/macro tilt/rotation), target weight, and (with `--capital`) the
**dollar amount to buy** (fractional shares, e.g. Robinhood), plus the
dollar buy/sell/resize trades vs your last book. Capital is **remembered**
from your first `--capital` run — you don't need to pass it again every month.

Output: `outputs/blend_ideas_TIMESTAMP.json` (+ `outputs/blend_book.json` state)

### `verify-book`

Asserts the live blend book is identical to the backtest position engine.
Run it any time you want proof the two are in sync.

---

## Equity engine (secondary)

The original single-strategy flow — S&P 1500 cross-sectional composite
momentum, weekly rebalance — is fully preserved, just renamed so it doesn't
collide with the blend's primary command names:

```bash
python csmom.py equity-backtest [--mcpt N] [--oos-frac 0.30] [--folds 5]
python csmom.py equity-ideas    [--capital N] [--holdings file.json] [--force]
python csmom.py equity-verify-book
```

Behavior is unchanged from before the blend was added: `equity-ideas`
self-gates on `portfolio.rebal_freq` (5 trading days), auto-refreshes prices,
and outputs to `outputs/ideas_TIMESTAMP.[txt|json]` + `outputs/portfolio_book.json`
— the *same* output filenames the equity engine always used (the blend uses
separate `blend_book.json`/`blend_ideas_*` names, so running both strategies
side by side does not clobber either one's state). See *Validated results*
below for its numbers and the honest reason it's no longer the default.

---

## How to change the backtest date range

Applies to **both** `backtest` (blend) and `equity-backtest` — they share the
same `data.start_date`/`end_date` window resolution.

Open `config.yaml` (in this folder) and change these two lines:

```yaml
data:
  start_date: "2023-01-01"   # ← change this
  end_date:   "2026-06-01"   # ← and this
```

Then re-run `python csmom.py backtest`.

**Important:** the momentum signal needs 12 months of price history to warm up
before it can produce its first trade signal.  If you set `start_date: "2023-01-01"`,
the first actual signals will appear around January 2024, and with a 70/30
split, the out-of-sample test window starts around mid-2024.

**Why 2023–2026 is a good choice:** market dynamics *are* different post-2022.
The 2022 rate-shock environment punished momentum severely; 2023–2025 saw a
momentum recovery.  Running over a tighter recent window answers "does this
signal still work right now?" rather than "did it ever work historically?".

You do not need to re-run `fetch` after changing dates — the price cache
already covers 2010–2025.  If you set `end_date` beyond what the cache covers,
run `fetch` again and it will download the missing dates.

---

## Where the data came from — and the missing-data question

**Data source:** Yahoo Finance, accessed via the free `yfinance` Python library.
Yahoo Finance stores historical daily prices (open, high, low, close, volume)
for every stock that is *currently listed*.  For large-cap stocks like AAPL or
SPY that have been listed for decades, Yahoo's history typically goes back to
the 1980s or 1990s.  We just restricted the download to 2010–present because:

1. The S&P constituent-change history on Wikipedia becomes sparse before 2010.
2. Pre-2010 market dynamics (pre-QE, pre-passive-investing dominance) behave
   quite differently from the modern regime.

**What you saw during the download:** A progress bar showing 503 of 504 tickers
completing, then this line:

```
1 Failed download:
['FDXF']: YFPricesMissingError('possibly delisted ...')
```

`FDXF` (FedEx Freight, recently added to the index) has no Yahoo Finance price
history at all — it was not separately listed for most of the backtest period.
It was skipped.  All other 502 S&P 500 tickers downloaded successfully with
history going back to at least 2010.  There is **no gap in the data for the
other stocks**.

**What "survivorship bias" means here:** Yahoo Finance only stores data for
stocks that are *currently* trading.  If a company was in the S&P 500 in 2015
but was acquired or went bankrupt by 2020, Yahoo may no longer carry its price
history.  This means the backtest is slightly optimistic — it can only hold
stocks that survived long enough to still be listed today.  The `fetch` command
partially corrects this by filtering which stocks the strategy *selects* on any
given date, but it cannot recover prices for stocks that have since disappeared.
That is why the backtested Sharpe (~0.97 over 2010–2025) is an upper bound;
the realistic live Sharpe is expected to be **0.4–0.7**.

---

## Changing other parameters (all in `config.yaml`)

**Blend (primary) — `blend:` section:**

```yaml
blend:
  growth_ticker:   SPYM   # what the growth sleeve actually holds — swap for SPY,
                          #   VOO, IVV, etc. any time; benchmark reporting always
                          #   stays literal SPY regardless of this setting.
  weight_spy:      0.40   # growth engine weight. Weights are renormalized if they
  weight_macro:    0.30   #   don't sum to 1 — feel free to try other splits.
  weight_rotation: 0.30   # multi-asset absolute-momentum rotation
  rotation_top_n:  2      # how many rotation slots to fill (validated with 2)
  trial_sharpes: [...]    # every weight-split OOS Sharpe ever tried — keeps the
                          #   blend's own DSR honest. Append when you sweep new
                          #   splits (use csm.trials.record_trial_sharpes with
                          #   section="blend" — NOT the default "validation").
```

**Equity engine (secondary) — everything else:**

```yaml
signal:
  window: 252      # 12 months of lookback — reduce to 126 (6mo) for faster signal
  skip:   21       # skip the most recent month to avoid short-term reversal
  quantile: 0.80   # buy the top 20%; try 0.90 for top 10% (more concentrated)

portfolio:
  rebal_freq: 5    # rebalance every 5 trading days (weekly); try 21 for monthly
  max_names: 25    # hold the 25 highest-conviction names (ranked by signal)

costs:
  commission_bps: 0      # 0 for a broker that trades stock/ETFs commission-free
  half_spread_bps: 5     # bid/ask half-spread (5 bps); increase for less liquid names

regime_filter:
  enabled: true
  spy_ma_days: 200       # go to cash when SPY < its 200-day moving average AND vol is high
```

---

## Validated results — blend (primary, last updated 2026-08-05)

**Walk-forward OOS — monthly-rebalance simulation, config's own 2015-2026 window, 30% holdout**

| Strategy | Sharpe | CAGR | Max Drawdown | Ann. turnover |
|---|---|---|---|---|
| Blend (OOS) | +1.316 | +13.6% | -8.6% | 4.1× |
| SPY buy-and-hold | +1.344 | +21.1% | -18.8% | — |

DSR = 0.986 across the blend's own 7-trial weight-split search (pass). Worst
of 5 walk-forward folds: Sharpe +0.41 (bar: >0.30). 86% of rolling 12-month
windows profitable; worst window return -7.2%, worst window MaxDD -18.8%.
Alpha vs SPY on this window: t=+0.65 (not significant *on this specific
recent, SPY-favorable slice*) — see the honesty note below.

> **Composition:** 40% SPYM (`csm/blend.py`, `blend.growth_ticker`) / 30% macro regime tilt
> (`csm/macro_regime.py` — classifies Goldilocks/Reflation/Stagflation/
> Deflation from market-observable growth & inflation proxies, holds that
> quadrant's sector/asset basket) / 30% multi-asset absolute-momentum
> rotation (`csm/multiasset.py` — ranks IEF/TLT/GLD/DBC/DBMF/BTAL by 12-1
> momentum, holds the top 2 positive-momentum names, else SHY). Fixed
> weights, monthly rebalance, no regime on/off switching between sleeves —
> switching was tested and found to cost more (false positives) than it saved.

> **Honesty note — the Sharpe edge is window-dependent; the drawdown
> reduction is not.** A 6-split weight-tuning sweep found OOS Sharpe rises
> monotonically with SPY weight on this particular 2015-2026 window (a
> historically exceptional SPY bull run) — very likely reward for loading up
> on that specific window's regime, not genuine skill, and the same
> overfitting-to-recent-window risk this project repeatedly guards against.
> On the longer 2010-2026 sample (tested via a standalone ETF-panel
> reconstruction, not yet re-run through the live engine on that full window),
> the blend **beat** SPY's own Sharpe (1.00 vs 0.867) with **half its
> drawdown** (-17.6% vs -33.7%) and a genuinely significant alpha, t≈2.05.
> Trust the drawdown-reduction claim more than any specific Sharpe-vs-SPY
> number — it held on every window tested, including this one.

> **Why SPY substitutes for the equity engine:** repeated testing (below)
> found the equity cross-sectional momentum book's returns are not
> significantly different from a ~0.5–0.7-beta SPY position. Beta-hedging it
> with a real inverse ETF (SH/SDS) made results *worse*, not better —
> confirmation that there wasn't hidden alpha to isolate. SPY is therefore a
> fair, simpler stand-in for that same beta exposure inside the blend.

---

## Validated results — equity engine (secondary, last updated 2026-07-16)

> The **Stage 0 spike** below is the original S&P-500-only exploration run with
> no point-in-time correction — kept for historical reference, not what's traded.
> The **Walk-forward OOS** table further down uses the full PIT-corrected S&P 1500
> (`fetch` has been run) with gross capped at 100% (no untradeable leverage) and
> dual-class shares deduped — those are the numbers `equity-ideas` and the
> stopping-rule bars below are validated against. **These numbers are why the
> equity engine is no longer the default** — see the alpha-significance note below.

**Stage 0 spike — S&P 500 only, 2010–2025, no PIT correction (survivorship-biased upper bound, historical reference only)**

| Strategy                    | Sharpe | CAGR   | Max Drawdown |
|-----------------------------|--------|--------|--------------|
| Residual momentum           | +0.97  | +15.7% | -36.3%       |
| Naive 12-1 momentum         | +0.98  | +19.3% | -36.5%       |
| SPY buy-and-hold            | +0.85  | +14.0% | -33.7%       |
| Random stock selection (null)| +0.56 | —      | —            |

- **Deflated Sharpe = 0.9999** (1.0 = certainty the result isn't just lucky parameter search)
- **Permutation test p-value ≈ 0.000** (the strategy sits ~12 standard deviations above what
  a random stock-picking strategy would achieve with the same mechanics)

**Walk-forward OOS — realistic weekly-rebalance simulation (S&P 1500, PIT, 30% holdout)**

These come from the unified engine: rebalance every 5 trading days, hold shares
with drift between, costs on real turnover, gross capped at 100% (no leverage) —
the **same book `ideas` gives you**.

| Strategy | Sharpe | CAGR | Max Drawdown | Ann. turnover |
|---|---|---|---|---|
| Composite (OOS) | +1.33 | +22.0% | -11.1% | 18.4× |
| SPY buy-and-hold | +1.38 | +21.7% | -18.8% | — |

DSR = 0.978 **across all 8 configurations ever tried** (pass); MCPT p = 0.0000
(1000 permutations — null 95th-percentile Sharpe is +0.22).

_Prior run (2026-07-09, plain residual momentum): Sharpe +1.14, CAGR +19.0%,
MaxDD -12.5%, DSR 0.981 — re-run `backtest` yourself any time to refresh this row._

> **Signal upgrade (2026-07-16): composite conviction rank.** The signal is now
> the equal-weight mean of three cross-sectional z-scores: residual momentum
> (Blitz–Huij–Martens), **frog-in-the-pan information continuity** (Da–Gurun–
> Warachka — prefer names whose gains came in many small steps), and **52-week-
> high proximity** (George–Hwang). A 7-variant sweep on identical data tested
> this against a graded VIX-term-structure regime gate, turnover-hysteresis
> bands (3 widths), and a defensive-IEF sleeve: the composite was the **only**
> variant to clear the pre-registered +0.1 Sharpe bar (+1.33 vs the +1.17
> residual-momentum baseline, same MaxDD). Component weights are fixed at
> equal **by design** — no weight optimization — and every trial's Sharpe is
> recorded in `config.yaml → validation.trial_sharpes`, so the DSR permanently
> deflates against the full search. The losing variants remain available as
> config flags (`regime_filter.mode: graded`, `portfolio.hold_band`,
> `regime_filter.defensive: IEF`) but default off.

> **Concentration:** the book holds the **25 highest-conviction** names of the top
> quintile (`max_names: 25`), ranked by signal strength. A sweep on the current
> engine (2026-07-12, `sweep_max_names.py` reproduces it) shows OOS Sharpe is a
> **flat plateau across caps 10–75** (spread ≈ 0.12, well inside estimation noise
> on ~2.9 years of OOS data — no cap in that range is statistically distinguishable),
> with clear degradation only past ~100 names as the long tail of the quintile
> dilutes the signal. So 25 is kept as a diversification/robustness choice, **not**
> a fitted optimum: tighter caps concentrate single-name and theme risk (10% per
> name at cap 10) for no reliable Sharpe gain, and the flat surface around the
> parameter is itself evidence the strategy isn't overfit to it.

> **Note on meta-labeling (removed):** an ML "meta filter" (RandomForest on
> triple-barrier labels) was tested and **removed**. When re-scored every
> rebalance — the only way you can actually trade it — it *underperformed* the
> plain primary book and roughly tripled turnover/costs. Earlier runs where it
> "won" were an artifact of freezing each name's size at entry, which isn't
> tradeable. The engine now trades the primary residual-momentum book directly.

> **2026-08-04/05 — why this engine is no longer the default.** A pre-registered
> kill criterion (alpha t-stat vs SPY must clear 1.5 across sector-neutral and
> beta-controlled variants) was tested rigorously: sector-capping
> (`portfolio.max_per_sector`), beta-capping (`signal.max_beta`), and
> inverse-vol weighting (`portfolio.weighting: inv_vol`) were all tried once
> each, plus combinations. **None cleared the bar** — every variant's alpha
> t-stat sat at 0.4–1.1, including the unmodified baseline. A real inverse-ETF
> beta hedge (SH/SDS, sized from the book's own rolling beta) made Sharpe
> *worse* (0.671 → 0.401 → -0.166 as hedge intensity increased) rather than
> revealing hidden skill — the clearest possible confirmation that the
> engine's returns are explained by market beta, not stock-picking ability.
> Fully working and available under `equity-*` if you want it, but the honest
> recommendation is the blend above.

---

## What the overfitting tests mean

| Test | What it asks | Pass threshold |
|------|-------------|----------------|
| **Deflated Sharpe (DSR)** | "After adjusting for the number of parameter combinations you tried, is the Sharpe still impressive?" | DSR > 0.90 |
| **Monte Carlo Permutation Test (MCPT)** — run with `backtest --mcpt 1000` | "If we randomly shuffled which stocks were top-ranked on each date (destroying all predictive signal), what Sharpe would we still get just from market exposure? Is our real Sharpe clearly above that noise floor?" | p < 0.05 |

(`sweep_signal_window.py` also reports PBO — Probability of Backtest Overfitting —
across the candidate lookback windows.)

---

## File layout

```
Cross-Sectional Momentum/
├── csmom.py              ← main script (run this) — blend commands are primary,
│                            equity commands live under equity-*
├── config.yaml           ← all parameters, incl. `blend:` (weights) section
├── requirements.txt      ← Python dependencies
├── spike_residual_momentum.py   ← Stage 0 validation script (standalone)
├── csm/
│   │   Blend (primary):
│   ├── blend.py          ← 3-way weights + self-contained simulator (blend_target_weights,
│   │                        simulate_blend, walk_forward_blend[_folds], target_book)
│   ├── macro_regime.py   ← Goldilocks/Reflation/Stagflation/Deflation classifier + sector/asset tilt
│   ├── multiasset.py     ← defensive rotation (IEF/TLT/GLD/DBC/DBMF/BTAL, 12-1 abs. momentum)
│   ├── regime_state.py   ← Kritzman turbulence + absorption-ratio (wired but not in the blend)
│   ├── slow_bleed.py     ← breadth + SPY absolute-momentum slow-decline detector (same)
│   ├── trials.py         ← programmatic trial_sharpes bookkeeping (section-aware — keep
│   │                        `validation.trial_sharpes` and `blend.trial_sharpes` separate)
│   │   Equity engine (secondary):
│   ├── afml.py           ← de Prado ML primitives (triple-barrier, purged CV, DSR, PBO)
│   ├── universe.py       ← point-in-time index membership reconstruction + GICS sector map
│   ├── signals.py        ← composite momentum, regime filter (binary/graded/robust), vol-scaling
│   ├── portfolio.py      ← ranking → position weights; target_book (live = backtest)
│   │   Shared by both:
│   ├── data.py           ← price download + caching (downloads BOTH strategies' universes)
│   ├── costs.py          ← transaction costs (commission + spread)
│   ├── backtest.py       ← equity walk-forward driver + simulate_live (weekly drift sim)
│   ├── validation.py     ← DSR, PBO, MCPT, alpha/beta, regime breakdown, rolling-window summary
│   └── report.py         ← TXT + JSON + equity-curve PNG output
└── outputs/
    ├── cache/                    ← downloaded price data (auto-populated by fetch)
    ├── blend_book.json           ← last live BLEND book (for the monthly trade diff)
    ├── portfolio_book.json       ← last live EQUITY book (for the weekly trade diff)
    ├── backtest_*_blend.[txt|json|png]  ← blend backtest reports
    ├── backtest_*.[txt|json|png]        ← equity backtest reports
    ├── blend_ideas_*.json               ← blend trade-book (JSON; also printed to console)
    └── ideas_*.[txt|json]                ← equity trade-book reports
```

---

## Caveats (honest)

1. **The blend's Sharpe edge over SPY is window-dependent** (see the honesty
   note in *Validated results*) — real on the longer 2010-2026 sample, roughly
   matching SPY on the shorter, recent, bull-market-dominated OOS slice. The
   drawdown reduction (roughly half of SPY's MaxDD) held on every window tested.
2. **The blend's edge is diversification, not stock-picking skill.** It
   combines three weakly-correlated return streams; it does not claim to
   predict which stocks or sectors will outperform beyond what the (freely
   available, market-observable) macro/momentum proxies already capture.
3. **The macro regime classifier substitutes market-observable proxies for
   official macro data** this environment couldn't reach (FRED CPI/M2)
   — arguably more honest for a systematic strategy anyway (no lag/revisions),
   but worth knowing if you expected literal CPI/M2 inputs.
4. **The equity engine's results are optimistic** until you run `fetch`
   (point-in-time membership). Even then, delisted-stock price history is
   unavailable on Yahoo Finance, and its own alpha was never statistically
   significant (see *Validated results — equity engine* above) — that's the
   documented reason it's secondary now.
5. **This is a research tool, not a signal service.** Past validation does not
   guarantee future performance.

---

## When to stop trusting a live drawdown (pre-registered rule)

Decide the bar *before* going live, or every bad week will feel like a reason to
second-guess the strategy — a Sharpe ~1.3 book still loses money over plenty of
short windows by design. Only act on one of these:

1. **Drawdown bar** — live drawdown-from-peak exceeds **-8.6%** (the current
   validated blend OOS MaxDD, see *Validated results* above) by a meaningful
   margin. A live DD near or inside that historical worst case is what
   "validated" means, not evidence something broke.
2. **Sharpe bar** — trailing 12-month live Sharpe goes negative. A single bad
   month is well inside the base-rate noise of a strategy whose worst
   walk-forward fold was Sharpe +0.41 and whose worst rolling 12-month window
   returned -7.2%.
3. **Structural bar** — act immediately, regardless of P&L: `verify-book`
   fails, the price cache goes stale without raising, or the monthly
   rebalance gate misfires (e.g. `ideas` shows HOLD past a month-end that has
   clearly passed). These are implementation failures, not variance.

Re-run `backtest` after any code or config change — the drawdown/Sharpe bars
above are only meaningful relative to the *current* engine's validated numbers.

---

## References

- López de Prado, M. (2018). *Advances in Financial Machine Learning.*
- Blitz, D., Huij, J. & Martens, M. (2011). Residual Momentum.
- Barroso, P. & Santa-Clara, P. (2015). Momentum has its moments.
- Daniel, K. & Moskowitz, T. (2016). Momentum crashes.
- Masters, T. (2019). *Statistically Sound Indicators for Financial Market Prediction.*
- Antonacci, G. (2014). *Dual Momentum Investing* — absolute-momentum
  cash/asset substitution, the basis for the rotation sleeve and the
  slow-bleed detector's momentum leg.
- Kritzman, M. & Li, Y. (2010). Skulls, Financial Turbulence, and Risk
  Management — Mahalanobis-distance turbulence (wired via `regime_state.py`,
  not currently part of the blend).
- Kritzman, M., Li, Y., Page, S. & Rigobon, R. (2011). Principal Components
  as a Measure of Systemic Risk — the absorption ratio (same module).
