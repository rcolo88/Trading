# RAAM — Ranked Asset Allocation Model

A recreation of Gioele Giordano's **Ranked Asset Allocation Model** (2018
Charles H. Dow Award winner, CMT Association), built the way
[`Cross-Sectional Momentum/`](../Cross-Sectional%20Momentum/) is built —
same overfitting-aware validation discipline, same backtest-equals-live
architecture — but a fresh implementation, not a copy.

RAAM applies an active monthly ranking overlay to Craig Israelsen's passive
**7Twelve** portfolio (12 asset-class ETFs). Each month it scores 11 of those
ETFs (the 12th, SHY, is the cash sleeve) on four components — **Momentum**,
**Volatility**, **Correlation**, **Trend** — combines them into a **Total
Rank**, holds the 5 best at a fixed **20% each**, and swaps any of the 5 with
negative momentum into cash. The backtest and the live `ideas` book run the
*same* engine — rebalance monthly, hold with drift between — so what you'd
trade is what was validated.

> **This is a recreation, not a port.** The paper's own headline number
> (Sharpe 1.94, 2004–2017) is **not reproducible** as stated and this codebase
> does not try to hit it — see *Why this doesn't match the paper* below. What
> it does deliver: the same model, on real data only, validated honestly.
>
> **On "the paper won an award, why does your version fail a test?"** — the
> Charles H. Dow Award judges originality and quality of argument, not
> statistical replication; it isn't a claim the reported Sharpe would survive
> multiple-testing correction. The DSR/PBO methodology used below is from
> López de Prado's *Advances in Financial Machine Learning* — published the
> **same year**, 2018, as this paper, so it wasn't available or expected
> practice when the paper was written. The paper also never discloses whether
> other wM/wV/wC weightings were tried before landing on the one it reports —
> undisclosed weight-searching is exactly the risk DSR exists to catch, and
> there's no way to check the paper's own robustness to it. This codebase
> discloses its full 67-weighting search (`sweep_rank_weights.py`), which is
> *why* it can fail a test the paper was never subjected to — not evidence the
> underlying idea is fake. See the nuanced DSR/MCPT/PBO discussion below.

---

## Quick start

```bash
cd RAAM
pip install -r requirements.txt

python raam.py fetch                    # OHLC for 12 ETFs + SPY — seconds, not minutes
python raam.py backtest --mcpt 1000     # walk-forward OOS backtest + DSR/MCPT (~9 min for 1000 perms)
python raam.py ideas --capital 100000   # this month's target book + trade list
```

The book is written to `outputs/ideas_TIMESTAMP.txt` / `.json`.

> **Daily workflow:** run `python raam.py ideas --capital N` any trading day —
> it auto-refreshes prices before scoring. The book only actually *changes* on
> the monthly rebalance (last trading day of the month); between rebalances
> `ideas` shows the same book, held with drift, which is exactly what the
> backtest assumes.
>
> `verify-book` asserts the live book equals the backtest engine at any time.
>
> `python raam.py` with no arguments opens an interactive menu.

---

## What each command does

### `fetch`

Downloads OHLC (not just Close — the Volatility and Trend components need the
full daily range) for the 12 7Twelve ETFs plus SPY, and caches it. There is no
point-in-time index-membership step here (unlike Cross-Sectional Momentum's
S&P 1500 reconstruction) — RAAM's universe is a fixed, named list of 12 ETFs,
so `fetch` is just a price download. With only 13 tickers it takes seconds,
and the cache always covers 2000-01-01 → today regardless of the analysis
window in `config.yaml`, so you rarely need to re-run it (prices auto-refresh
on `ideas`/`backtest` when stale).

### `backtest [--mcpt N] [--oos-frac F] [--full-sample]`

Default mode is **walk-forward**: a 70/30 in-sample/out-of-sample split,
validated strictly on the OOS tail via the same monthly-rebalance,
hold-with-drift engine `ideas` uses. Reports RAAM against the paper's own
benchmark set (Core 7Twelve equal-weight, a reconstructed Risk Parity index,
SPY) and runs the Deflated Sharpe Ratio test (plus Monte Carlo Permutation
with `--mcpt N`) to guard against overfitting.

`--full-sample` instead runs over the entire available real-data history
(2000–today) — the paper-comparable mode, printing a line-by-line comparison
against Giordano's Figure 19 in every report.

### `ideas [--capital N] [--holdings file.json]`

The only command you need to run regularly. Auto-refreshes prices if the
cache is stale, builds the exact target book the backtest trades (same
engine, same 20%-slot sizing, same cash-substitution rule), and prints it
with — given `--capital` — the dollar amount per name (fractional shares) plus
the buy/sell/resize diff vs your last book. `--holdings file.json` (a
`{"TICKER": dollar_value}` map) diffs against your actual broker holdings
instead of the saved book.

### `verify-book`

Asserts the live `ideas` book is bit-identical to the backtest position
engine. Passes with a `0.00e+00` max weight diff — the two are the same code
path by construction (`raam/portfolio.py:target_book`), this just proves a
future edit hasn't silently forked them.

---

## The model, as specified in the paper

**Universe — 7Twelve** (Giordano 2018, Table 2):

| Sleeve | Ticker | First real close |
|---|---|---|
| US Large-Cap | VV | 2004-01-30 |
| US Mid-Cap | IJH | 2000-05-26 |
| US Small-Cap | IJR | 2000-05-26 |
| Developed ex-US | EFA | 2001-08-27 |
| Emerging Markets | EEM | 2003-04-14 |
| US REIT | RWR | 2001-08-27 |
| Commodities | DBC | 2006-02-06 |
| Materials | VAW | 2004-01-30 |
| Aggregate Bond | AGG | 2003-09-29 |
| TIPS | TIP | 2003-12-05 |
| Intl Treasury | IGOV | 2009-01-30 |
| **Cash sleeve** | **SHY** | 2002-07-30 |

SHY is never ranked — it's the destination when a slot fails the momentum
filter or the universe hasn't grown enough yet to fill all 5 (see *Why 2004
doesn't work* below).

**Four components** (`raam/indicators.py`):

- **(M) Absolute Momentum** — 4-month rate of change on daily closes.
- **(V) Volatility Model** — RiskMetrics-style EWMA (λ=0.943) on Garman-Klass
  range variance (the paper says "OHLC daily data" but never names the
  single-day variance proxy — Garman-Klass is the standard way to make that
  an OHLC- rather than close-only estimator), 10-day smoothed.
- **(C) Average Relative Correlation** — 4-month mean pairwise correlation of
  each ETF against every other currently-eligible ETF.
- **(T) ATR Trend/Breakout** — `Upper = ATR(42) + max(Close, 63)`,
  `Lower = ATR(42) + max(Low, 105)`. ATR is **added** to both bands — the
  paper is explicit this is deliberate (higher vol should make the Lower Band
  *more* responsive, not less). State machine: `T=+2` the session after a
  High exceeds the Upper Band, `T=-2` the session after a Low breaches the
  Lower Band, held otherwise. Verified against a hand-constructed price path:
  the flip always lands exactly one day after the breakout, never same-day.

**Total Rank** = `wM·Rank(M) + wV·Rank(V) + wC·Rank(C) − T + tiebreak_sign·(M/x)`
→ the **5 lowest** win, each at exactly **20%**; any of the 5 with
non-positive momentum has its 20% redirected to SHY instead (all 5 negative →
100% SHY, the paper's own stated extreme case).

---

## Two ambiguities the paper leaves unresolved — and how this codebase resolves them

**1. Rank direction.** The paper's prose contradicts itself: it says Rank(M)
is ranked "ascending" while Rank(V)/Rank(C) are "descending," yet also says
the 5 *lowest* Total Rank names win and that lower volatility earns a
*higher* ranking. Those can't all be true simultaneously. The only
self-consistent reading — the one under which `−T` correctly *rewards* a
confirmed uptrend — is **rank 1 = best** for all three components (highest M,
lowest V, lowest C). That's the default (`ranking.convention: rank1_best`).
The literal contradictory text is also implemented
(`ranking.convention: paper_literal`) purely so the alternative is testable,
not because it's believed correct.

**2. The tie-breaker sign.** The paper adds `+M/x` "to avoid equal ranks,"
with `x` undisclosed. Taken completely literally, higher M would very
slightly *raise* Total Rank (worse) in a tie — backwards relative to the
resolved rank-1-is-best convention. Default flips the sign
(`ranking.tiebreak_sign: -1`) so ties favor higher momentum, consistent with
everything else; `x` (default 1000) is large enough this only ever decides
exact ties and never overturns a real rank difference.

---

## Why this doesn't match the paper

### I tried to reproduce the 1.94 directly — it can't be done with real data

The obvious objection is: "the paper won a Dow Award, so surely the 1.94 Sharpe
reproduces — reproduce it first, *then* test on new data." So I tried, giving
the paper **every legitimately-reproducible advantage at once**:

- **zero transaction costs** (the paper is explicitly gross — p.17: *"No
  transaction costs are included, all results are gross of any transaction
  fees, management fees, or any other fees"*),
- the paper's **exact window** (Jul 2004 – Nov 2017), and
- the **single best weighting out of a full 134-point sweep** — i.e. assume the
  author's undisclosed `wM/wV/wC` were the luckiest possible (itself an
  in-sample advantage the paper's honest number wouldn't have).

| Setup (all GROSS, real data only) | Equal-wt Sharpe | **Best-of-134 Sharpe** | Paper |
|---|---|---|---|
| Paper's window, 2004–2017 | 1.018 | **1.133** | **1.94** |
| Fully-real subwindow, 2010–2017 | 0.511 | **0.803** | **1.94** |

Even best-case, real data tops out at **~1.13 — still 0.81 short of 1.94**, and
the gap is *widest* (1.14) in the 2010–2017 window that contains **no synthetic
data at all**. That isolates the missing ~0.8 Sharpe to the one thing that
*cannot* be reproduced with real prices: the paper's own admission (p.17) that
*"interpolations have been made… to achieve temporal homogeneity. Data
interpolation was performed on RStudio"* — DBC (real 2006) and IGOV (real 2009)
were synthetically backfilled to 2004, straight through the 2008 crash, which
is exactly where the paper's biggest numbers live (Figure 18: +2.36% in 2008,
+54.52% in 2009). Costs (removed above) and equal-vs-fitted weights (optimized
above) each account for only ~0.1–0.2; the rest is the synthetic data plus the
full-sample Excel weight-fit.

**This is not a bug in the recreation — it's a property of the original
number**, and I'm not the first to find it: an independent replication
([QuantSeeker, Sep 2025](https://www.quantseeker.com/p/replicating-an-asset-allocation-model))
tested this exact paper and reports being *"unable to replicate the main
results,"* while still finding the rotation signals *"interesting and useful in
a broader allocation framework"* — the same two-part verdict this codebase
reaches (MCPT confirms real ranking skill; the headline Sharpe is an artifact).
The Charles H. Dow Award judges originality and argument, not independent
statistical replication — winning it is not evidence the 1.94 reproduces.
(Reproduce this yourself: `python reproduce_paper.py`.)

**The undisclosed weights.** `wM`, `wV`, `wC` are never disclosed — they were
fit in Excel, full-sample, no OOS split, **no transaction costs**. RAAM trades
**equal weights (1/3 each) by design**, with no fitting. `sweep_rank_weights.py`
tests robustness to that choice (see *Validated results* below) — the point
isn't to find a better weighting and switch to it (that would just reproduce
the paper's own undisclosed-fitting problem), it's to check whether equal
weights sit in a defensible, non-arbitrary region.

**The Jul-2004 start is impossible with real data.** DBC's first real close is
2006-02-06; IGOV's is 2009-01-30 (both verified via yfinance). The paper's
"interpolations… to achieve temporal homogeneity" means 2 of 12 assets ran on
synthetic history straight through the 2008 crisis — precisely where its
strongest evidence comes from (Figure 18: +2.36% in 2008, +54.52% in 2009).
RAAM uses **zero synthetic data**: an ETF enters the ranking pool only once it
has ≥252 real trading days of history (`raam/universe.py:eligible_on`), so the
5-slot pool ramps up from ~4 real candidates in 2004 to the full 11 by 2010.
Verified: DBC never appears in the book before ~2007, IGOV never before
~2010, and OOS results are bit-identical whether the price panel spans 3 years
or 26 years of pre-window history (see `git log` / test output — no indicator
peeks past its own row's date).

**Costs.** The paper's backtest is gross of all fees, commissions, and spread.
RAAM charges 10bps one-way (5bps commission + 5bps half-spread) on every
rebalance's turnover, like Cross-Sectional Momentum.

**The Salient Risk Parity Index isn't obtainable.** Salient was acquired by
Westwood in 2022 and the index is no longer published. The ticker that looks
like a match, `SRPIX`, actually resolves to *ProFunds Short Real Estate* — an
unrelated inverse-REIT fund. Checked directly against the paper's own Figure
19 numbers: −83% absolute return over the period vs the paper's +147%, a
hundred-plus-point miss, confirming it's the wrong instrument, not just a
noisy proxy. `raam/benchmarks.py:risk_parity_10vol` instead reconstructs what
the paper itself says the index is — *"a Risk Parity portfolio with 10%
Volatility Targeting"* — using inverse-realized-vol weights over the same
12-ETF universe RAAM ranks, monthly rebalanced, vol-targeted, capped at 100%
gross (no leverage). Computed on **our** data with **our** cost model, so it's
apples-to-apples in a way a scraped third-party series never could be. The
paper's own published Salient stats (Figure 19) are kept as reference
constants (`benchmarks.SALIENT_PUBLISHED`) and printed alongside every report,
clearly labelled as the paper's numbers, not something this code reproduces.

---

## Validated results (last updated 2026-07-20)

**Walk-forward OOS** (2000–2026 real data, 70/30 split, OOS ≈ 2018-07 to
2026-07, monthly rebalance, hold-with-drift, costed, equal wM=wV=wC):

| Strategy | Sharpe | CAGR | MaxDD | MaxDD(3mo) | Ann.STD |
|---|---|---|---|---|---|
| **RAAM (Total Rank)** | **+0.699** | +4.5% | −10.5% | −8.2% | 6.6% |
| Core 7Twelve (equal-weight) | +0.615 | +7.1% | −25.5% | −25.5% | 12.4% |
| Risk Parity 10%vol (reconstructed) | +0.548 | +2.8% | −14.5% | −10.4% | 5.3% |
| SPY buy-and-hold | +0.803 | +14.6% | −33.7% | −33.7% | 19.4% |

RAAM beats both multi-asset benchmarks on Sharpe with roughly a third of
Core 7Twelve's drawdown; it trails SPY, unsurprising for a defensive,
20%-capped-per-name multi-asset model measured over a historic US
large-cap bull run.

**Full-sample** (2000–2026, paper-comparable mode — `backtest --full-sample`):

| Strategy | Sharpe | CAGR | MaxDD | Ann.STD |
|---|---|---|---|---|
| **RAAM (Total Rank)** | **+0.819** | +5.7% | −17.5% | 7.1% |
| Core 7Twelve (equal-weight) | +0.576 | +6.4% | −41.6% | 12.1% |
| Risk Parity 10%vol (reconstructed) | +0.503 | +2.7% | −18.8% | 5.7% |
| SPY buy-and-hold | +0.507 | +8.2% | −55.2% | 19.3% |

Over the full 26-year window RAAM beats *every* benchmark, including SPY, on
both Sharpe and max drawdown (−17.5% vs SPY's −55.2%). The paper's claimed
**Sharpe 1.94** is not reproduced — expected, given real data only, equal
(not fitted) weights, and full costs; see *Why this doesn't match the paper*.

**Paper comparison** (paper's Figure 19, gross, 2004–2017, undisclosed
weights, partially interpolated data — vs this run's walk-forward OOS):

| Stat | Paper (Salient) | This run (RAAM) |
|---|---|---|
| Sharpe | 0.56 | 0.699 |
| Annualized STD | 9.8% | 6.6% |
| Worst year | −16.9% | −4.5% |
| Max DD (3-month) | −22.8% | −8.2% |

*(The paper's own RAAM Sharpe, 1.94, is the only RAAM-specific stat it
tabulates — its Figures 17/18 plot the rest without a numbers table.)*

### What the overfitting tests mean — and the honest, nuanced verdict

| Test | What it asks | Threshold | Result (OOS) |
|---|---|---|---|
| **MCPT** (shuffles which ETF gets which Total Rank each month) | Does the *ranking itself* have real predictive skill, beyond what you'd get from randomly reassigning ranks? | p < 0.05 | **p = 0.044 — PASS** |
| **DSR** (deflates Sharpe against every wM/wV/wC combo tried) | Is the *specific equal-weight configuration's* Sharpe distinguishable from the best of many zero-skill trials? | DSR > 0.90 | **0.874 — FAIL** |
| **PBO** (CSCV across the same weight sweep) | Would a config chosen as "best in-sample" from this search likely have underperformed OOS? | PBO < 0.50 | **0.531 — FAIL** |

This is not a contradiction — it's the honest shape of the evidence. **MCPT
passing** means the Total Rank mechanism genuinely has skill: shuffling which
ETF wins which rank each month (destroying the correspondence between an
asset's own M/V/C/T and its selection, while preserving the exact 5-of-K
mechanics and every ticker's real return) collapses performance, so being
*correctly selected* matters. **DSR and PBO failing** means the equal-weight
choice specifically — one of 67 weightings tried in `sweep_rank_weights.py`,
ranked 28th of 67 by OOS Sharpe — isn't statistically distinguishable from
what the luckiest of that many trials would produce by chance at this sample
size (~96 OOS months). Put plainly: **there is a real signal in the ranking
approach; there isn't yet strong enough evidence that *this particular*
weighting of it is special.**

This is exactly why equal weights are kept rather than switched to the
sweep's apparent winner (`wM=0.1, wV=0.1, wC=0.8`, Sharpe 0.890): adopting it
*because* it scored best in a 67-point search we already ran would be the
identical undisclosed-fitting mistake the paper itself made, and DSR would
punish that switch even harder (the deflation grid would then need to account
for having *selected* the winner, not merely tried it). The dispersion in the
sweep isn't random noise, either — the worst-performing corner of the grid
(wV≈0, i.e. no weight on the Volatility component) also shows far deeper
drawdowns (−20% to −27% vs −8% to −12% elsewhere), a coherent, economically
sensible pattern: dropping the risk-control component costs real drawdown
protection. That's informative about the *model*, not license to cherry-pick
a *config*.

`sweep_rank_weights.py` reproduces this (66-point simplex grid, step 0.1,
plus the explicit equal-weight point, ~10 min). Every trial's Sharpe is
recorded in `config.yaml → validation.trial_sharpes`, so DSR stays honestly
deflated against the full search — append here on any new sweep.

---

## Two drawdown numbers, on purpose

The paper reports only a **rolling 3-month** max drawdown (Figure 19:
Salient's is −22.82%). That measure bounds how far apart the peak and trough
can be (at most ~63 trading days), which will always look shallower than
reality for any strategy that grinds down slowly over a longer stretch. Every
`backtest` report here prints **both**: `MaxDD(3mo)` (the paper's own
convention, for direct comparison) and `MaxDD` (unbounded peak-to-trough, the
number that actually matters for whether you can stomach holding the
strategy). For RAAM's walk-forward OOS run these are −8.2% and −10.5%
respectively — a real but modest gap; for Core 7Twelve's full-sample run the
gap is far starker (−36.0% rolling-3mo vs −41.6% true) — worth checking
whenever you compare a max-drawdown headline figure across strategies or
papers.

---

## File layout

```
RAAM/
├── raam.py                  ← main script (run this) — fetch | backtest | ideas | verify-book
├── config.yaml               ← all parameters (edit this to change dates/weights/costs)
├── requirements.txt
├── reproduce_paper.py       ← best-case GROSS reproduction: shows 1.94 is unreachable on real data
├── sweep_rank_weights.py    ← wM/wV/wC robustness sweep + PBO (reproduces the table above)
├── raam/
│   ├── afml.py               ← de Prado ML primitives (DSR, PBO/CSCV) — vendored from csm/afml.py
│   ├── universe.py           ← 7Twelve roster, sleeves, real-data availability mask
│   ├── data.py               ← OHLC download + parquet cache
│   ├── indicators.py         ← (M) (V) (C) (T) — the four Ranking Model components
│   ├── ranking.py            ← Total Rank combine + monthly 5-name selection
│   ├── portfolio.py          ← 20%-slot sizing + cash substitution; target_book (live = backtest)
│   ├── benchmarks.py         ← Core 7Twelve, SPY, reconstructed Risk Parity, paper's published stats
│   ├── costs.py              ← transaction costs (commission + spread) — ported from csm/costs.py
│   ├── backtest.py           ← monthly-rebalance drift simulation + walk_forward + full_sample
│   ├── validation.py         ← metrics (incl. paper's own stat set), DSR, PBO, MCPT
│   └── report.py             ← TXT + JSON + equity PNG, incl. the paper-comparison table
└── outputs/
    ├── cache/                 ← downloaded OHLC data (auto-populated by fetch)
    ├── portfolio_book.json    ← last live book (for the rebalance trade diff)
    ├── backtest_*.txt/json/png
    └── ideas_*.txt/json
```

---

## Caveats (honest)

1. **The paper's 1.94 Sharpe is not a target this codebase tries to hit.**
   It's gross of costs, fit on undisclosed weights, and partially built on
   synthetic pre-inception data. None of that survives here on purpose.
2. **DSR and PBO currently fail** on the specific equal-weight configuration,
   even though MCPT confirms the ranking mechanism has genuine skill — see
   the nuanced discussion above. Treat this as "promising, not yet proven,"
   not as a green light for size.
3. **~96 OOS months is a short sample** for a monthly-rebalance strategy (vs.
   Cross-Sectional Momentum's ~2000 OOS *daily* observations). Wide
   confidence intervals are inherent to this cadence; don't over-read any
   single backtest run.
4. **This is a research tool, not a signal service.** Past validation, even
   OOS, does not guarantee future performance.

---

## References

- Giordano, G. (2018). *Ranked Asset Allocation Model.* 2018 Charles H. Dow
  Award, CMT Association.
- Israelsen, C. L. (2010). *7Twelve: A Diversified Investment Portfolio with a
  Plan.* Wiley.
- Bollerslev, T. (1986). Generalized Autoregressive Conditional
  Heteroskedasticity. *Journal of Econometrics* 31.
- Garman, M. & Klass, M. (1980). On the Estimation of Security Price
  Volatilities from Historical Data. *Journal of Business* 53.
- Wilder, J. W. (1978). *New Concepts in Technical Trading Systems.* Trend
  Research.
- López de Prado, M. (2018). *Advances in Financial Machine Learning.*
- Masters, T. (2019). *Statistically Sound Indicators for Financial Market
  Prediction.*
