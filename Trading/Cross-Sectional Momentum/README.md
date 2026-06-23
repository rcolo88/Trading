# Cross-Sectional Residual Momentum — Trade-Idea Engine

Ranks US large/mid/small-cap stocks by **residual (idiosyncratic) momentum** —
how much a stock outperformed its market exposure, not just its raw return — and
outputs the **exact long-only portfolio book the backtest trades**: every name,
its target weight, and (given capital) dollars + shares, plus this week's
buy/sell/resize list.  The backtest and the live `ideas` book run the *same*
engine — rebalance every 5 trading days, hold shares with drift between — so what
you trade is what was validated.  Every backtest is run through three overfitting
tests so results are honest, not optimistic curve-fits.

> **Universe note — important before you run anything:**
> - **Before `fetch`:** the backtest and ideas commands fall back to the
>   *current* S&P 500 only (~500 stocks).  This is what all validation results
>   below are based on.
> - **After `fetch`:** the full S&P 1500 (S&P 500 + S&P 400 MidCap +
>   S&P 600 SmallCap, ~1 500 stocks) is used, with point-in-time membership
>   so the backtest only holds names that were actually in the index on each date.
> - Run `fetch` once to unlock the S&P 1500 universe.  Until then everything
>   is S&P 500.

---

## Quick start

```bash
# 0. Install dependencies (once)
pip install -r requirements.txt

# 1. Download prices and build the S&P 1500 universe (20–40 min first time, <1 min after)
python csmom.py fetch

# 2. Run the walk-forward backtest + validation
python csmom.py backtest

# 3. Generate today's target book + this week's trades
python csmom.py ideas --capital 100000
```

That's it. The book is written to `outputs/ideas_TIMESTAMP.txt` and `.json`.

> **Run `ideas` once every 5 trading days (weekly).** That cadence *is* the
> backtest's rebalance schedule — run it daily and you trade more than was
> validated. `verify-book` asserts the live book equals the backtest engine.

> **Tip:** `python csmom.py` with no arguments opens an interactive menu if you prefer.

---

## What each command does (plain English)

### Step 1 — `fetch` (run once, then monthly)

Downloads prices for every stock ever in the S&P 500/400/600 from Yahoo Finance
and reconstructs *which* stocks were in the index *on each date*, so the backtest
never looks ahead.  First run takes 20–40 minutes; after that the cache makes it
under a minute.

### Step 2 — `backtest`

Splits the date range 70% in-sample / 30% out-of-sample and validates on the
out-of-sample period only.  It **simulates the real live process**: every 5
trading days it rebalances the whole book to the fresh target (top-quintile →
equal-dollar → vol-scaled → regime-gated), then holds those shares and lets the
weights drift until the next rebalance, charging costs on actual turnover.  Runs
the Deflated Sharpe Ratio test (and MCPT with `--mcpt N`) to guard against
overfitting.

Output: `outputs/backtest_TIMESTAMP.[txt|json|png]`

### Step 3 — `ideas [--capital N]`

Builds the exact target portfolio book for today — the same engine the backtest
trades — and prints every holding with its target weight, and (with `--capital`)
dollar allocation and share count, plus an exposure/regime header and the
buy/sell/resize trades vs your last book.  Hold each name until it leaves the
weekly book; there are no intraday stops.  `--holdings file.json` diffs against
your actual broker positions.

Output: `outputs/ideas_TIMESTAMP.[txt|json]` (+ `outputs/portfolio_book.json` state)

### `verify-book`

Asserts the live `ideas` book is identical to the backtest position engine (the
book matches exactly). Run it any time you want proof the two are in sync.

---

## How to change the backtest date range

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

```yaml
signal:
  window: 252      # 12 months of lookback — reduce to 126 (6mo) for faster signal
  skip:   21       # skip the most recent month to avoid short-term reversal
  quantile: 0.80   # buy the top 20%; try 0.90 for top 10% (more concentrated)

portfolio:
  rebal_freq: 5    # rebalance every 5 trading days (weekly); try 21 for monthly

costs:
  commission_bps: 5      # brokerage commission per trade (5 basis points = 0.05%)
  half_spread_bps: 5     # bid/ask half-spread (5 bps); increase for less liquid names

regime_filter:
  enabled: true
  spy_ma_days: 200       # go to cash when SPY < its 200-day moving average AND vol is high

portfolio:
  rebal_freq: 5          # rebalance every 5 trading days (weekly) — run `ideas` on this cadence
  max_names: 100         # cap on number of longs held
```

---

## Validated results (as of initial run)

> All numbers below are **S&P 500 only** (fetch not yet run).
> Expect results to change — likely modestly lower — once the full S&P 1500
> is used, because mid/small-cap names have wider spreads and higher turnover costs.

**Stage 0 spike — current S&P 500 only, 2010–2025 (survivorship-biased upper bound)**

| Strategy                    | Sharpe | CAGR   | Max Drawdown |
|-----------------------------|--------|--------|--------------|
| Residual momentum           | +0.97  | +15.7% | -36.3%       |
| Naive 12-1 momentum         | +0.98  | +19.3% | -36.5%       |
| SPY buy-and-hold            | +0.85  | +14.0% | -33.7%       |
| Random stock selection (null)| +0.56 | —      | —            |

- **Deflated Sharpe = 0.9999** (1.0 = certainty the result isn't just lucky parameter search)
- **Permutation test p-value ≈ 0.000** (the strategy sits ~12 standard deviations above what
  a random stock-picking strategy would achieve with the same mechanics)

**Walk-forward OOS — realistic weekly-rebalance simulation (S&P 1500, 30% holdout)**

These come from the unified engine: rebalance every 5 trading days, hold shares
with drift between, costs on real turnover — the **same book `ideas` gives you**.

| Strategy | Sharpe | CAGR | Max Drawdown | Ann. turnover |
|---|---|---|---|---|
| Primary (OOS) | +1.03 | +16.6% | -16.6% | 14.5× |
| SPY buy-and-hold | +1.46 | +23.4% | -18.8% | — |

DSR = 0.97 (pass).

> **Note on meta-labeling (removed):** an ML "meta filter" (RandomForest on
> triple-barrier labels) was tested and **removed**. When re-scored every
> rebalance — the only way you can actually trade it — it *underperformed* the
> plain primary book and roughly tripled turnover/costs. Earlier runs where it
> "won" were an artifact of freezing each name's size at entry, which isn't
> tradeable. The engine now trades the primary residual-momentum book directly.

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
├── csmom.py              ← main script (run this)
├── config.yaml           ← all parameters (edit this to change dates/settings)
├── requirements.txt      ← Python dependencies
├── spike_residual_momentum.py   ← Stage 0 validation script (standalone)
├── csm/
│   ├── afml.py           ← de Prado ML primitives (triple-barrier, purged CV, DSR, PBO)
│   ├── universe.py       ← point-in-time index membership reconstruction
│   ├── data.py           ← price download + caching
│   ├── signals.py        ← residual/naive momentum, regime filter, vol-scaling
│   ├── portfolio.py      ← ranking → position weights; target_book (live = backtest)
│   ├── costs.py          ← transaction costs (commission + spread)
│   ├── backtest.py       ← walk-forward driver + simulate_live (weekly drift sim)
│   ├── validation.py     ← DSR, PBO, Monte Carlo permutation test
│   └── report.py         ← TXT + JSON + equity PNG output
└── outputs/
    ├── cache/            ← downloaded price data (auto-populated by fetch)
    ├── portfolio_book.json      ← last live book (for the weekly trade diff)
    ├── backtest_*.txt/json/png   ← backtest reports
    └── ideas_*.txt/json          ← trade book reports
```

---

## Caveats (honest)

1. **Results are optimistic** until you run `fetch` (point-in-time membership).
   Even then, delisted-stock price history is unavailable on Yahoo Finance.
2. **The 0.97 Sharpe will drop** to something in the 0.4–0.7 range with real
   data, transaction costs, and market-impact on mid/small-cap names.
3. **This is a research tool, not a signal service.**  Past validation does not
   guarantee future performance.

---

## References

- López de Prado, M. (2018). *Advances in Financial Machine Learning.*
- Blitz, D., Huij, J. & Martens, M. (2011). Residual Momentum.
- Barroso, P. & Santa-Clara, P. (2015). Momentum has its moments.
- Daniel, K. & Moskowitz, T. (2016). Momentum crashes.
- Masters, T. (2019). *Statistically Sound Indicators for Financial Market Prediction.*
