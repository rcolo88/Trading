# Cross-Sectional Residual Momentum — Trade-Idea Engine

Ranks US large/mid/small-cap stocks by **residual (idiosyncratic) momentum** —
how much a stock outperformed its market exposure, not just its raw return —
and produces ranked long-only trade ideas with suggested hold periods (1–3 months)
and triple-barrier stop/target levels.  Every backtest is run through three
overfitting tests so results are honest, not optimistic curve-fits.

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

# 2. Run the backtest and train the ML filter
python csmom.py backtest --meta

# 3. Generate today's trade ideas
python csmom.py ideas
```

That's it. Ideas are written to `outputs/ideas_TIMESTAMP.txt` and `.json`.

> **Tip:** `python csmom.py` with no arguments opens an interactive menu if you prefer.

---

## What each command does (plain English)

### `fetch` — download data (run once, then re-run monthly)

**This is the step that upgrades the universe from S&P 500 → S&P 1500.**

Downloads historical daily prices for every stock that has ever been in the
S&P 500, S&P 400, and S&P 600 from Yahoo Finance, and also reconstructs
*which* stocks were in each index *on each date* (so the backtest doesn't
cheat by knowing in advance which stocks later made it into the index).

- First run: 20–40 minutes (≈1 500 tickers, 15+ years of daily prices).
- Subsequent runs: under a minute — data is cached to `outputs/cache/prices.parquet`.
- Until you run this, `backtest` and `ideas` use the current S&P 500 only and
  print a warning to remind you.
- Output: `outputs/cache/universe_pit.parquet` (point-in-time index membership)
  and `outputs/cache/prices.parquet` (price history).

### `backtest` — walk-forward backtest

Splits the date range in `config.yaml` 70% in-sample / 30% out-of-sample,
fits the strategy on the in-sample window, and reports performance only on
the out-of-sample period.  This is the standard guard against overfitting.

Also runs the **Deflated Sharpe Ratio** test automatically, which adjusts the
Sharpe ratio downward to account for the fact that you tried multiple parameter
configurations — a Sharpe of 1.0 after testing 10 variations isn't as
impressive as a Sharpe of 1.0 from the first try.

```
python csmom.py backtest                   # primary signal only, fast (~30 sec)
python csmom.py backtest --meta            # adds the ML filter (RandomForest trained
                                           # on IS data, predicts take/skip each trade)
python csmom.py backtest --mcpt 1000       # also runs 1 000 permutation shuffles to
                                           # compute a p-value ("could this be luck?")
python csmom.py backtest --oos-frac 0.40   # use 40% as the OOS holdout instead of 30%
```

Output: `outputs/backtest_TIMESTAMP.[txt|json|png]`

### `ideas` — today's ranked trade ideas

Scores every current index member as of the latest data date, ranks them by
residual momentum, and prints the top-N longs with:
- Signal score (higher = stronger momentum relative to market)
- **P(take)** — the ML meta-model's probability that this position will hit its profit target (real predictions when the model is available; 100% placeholder otherwise)
- Suggested entry price (last close)
- Stop-loss level (based on stock's own volatility)
- Profit-target level
- Suggested holding horizon (42 trading days ≈ 2 months, adjustable in config)

**To get real P(take) scores:** run `backtest --meta` first.  That trains the
RandomForest meta-model and saves it to `outputs/meta_model.pkl`.  The `ideas`
command then loads it automatically and filters to candidates with P(take) ≥ 55%
(configurable via `meta_labeling.min_prob_take` in `config.yaml`), sorted by
P(take) descending.  If no model file is found, a warning is printed and the
signal-score ranking is used with a 100% placeholder.

**Recommended workflow:**
```
python csmom.py fetch               # Step 1: build universe + download prices
python csmom.py backtest --meta     # Step 2: walk-forward backtest, saves ML model
python csmom.py ideas --top 25      # Step 3: real ML-filtered trade ideas
```

```
python csmom.py ideas --top 25    # top 25 ideas (default)
python csmom.py ideas --top 50    # top 50
```

Output: `outputs/ideas_TIMESTAMP.[txt|json]`

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

meta_labeling:
  barrier_window: 42     # suggested hold period in trading days (42 ≈ 2 months)
  pt_multiple: 1.5       # profit-take = 1.5× the stock's typical daily volatility
  sl_multiple: 1.0       # stop-loss   = 1.0× the stock's typical daily volatility
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

**Walk-forward OOS only (30% holdout, no meta-labeling)**

| | Sharpe | CAGR | Max Drawdown | Calmar |
|---|---|---|---|---|
| Primary (OOS) | +1.19 | +15.4% | -14.9% | +1.03 |
| SPY (same period) | +0.85 | +13.9% | -24.5% | — |

---

## What the three overfitting tests mean

| Test | What it asks | Pass threshold |
|------|-------------|----------------|
| **Deflated Sharpe (DSR)** | "After adjusting for the number of parameter combinations you tried, is the Sharpe still impressive?" | DSR > 0.90 |
| **Probability of Backtest Overfitting (PBO)** | "If you split the history into many pieces and checked whether the best in-sample config also won out-of-sample, how often did it?" | PBO < 0.50 |
| **Monte Carlo Permutation Test (MCPT)** | "If we randomly shuffled which stocks were top-ranked on each date (destroying all predictive signal), what Sharpe would we still get just from market exposure? Is our real Sharpe clearly above that noise floor?" | p < 0.05 |

All three together make it very difficult to accidentally claim an edge that isn't real.

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
│   ├── portfolio.py      ← stock ranking → position weights
│   ├── costs.py          ← transaction costs (commission + spread)
│   ├── labeling.py       ← triple-barrier labels for the ML filter
│   ├── model.py          ← RandomForest meta-model + calendar-time purged CV
│   ├── backtest.py       ← walk-forward driver
│   ├── validation.py     ← DSR, PBO, Monte Carlo permutation test
│   └── report.py         ← TXT + JSON + equity PNG output
└── outputs/
    ├── cache/            ← downloaded price data (auto-populated by fetch)
    ├── meta_model.pkl    ← trained ML filter (auto-saved by backtest --meta)
    ├── backtest_*.txt/json/png   ← backtest reports
    └── ideas_*.txt/json          ← trade idea reports
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
