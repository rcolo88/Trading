# Fundamental Scanner

Profitability-anchored quality screen for US and foreign equities. Cross-sectionally ranks a universe (S&P 500 through Russell 3000) using academically validated factors — gross profits-to-assets, Piotroski F-Score, accrual ratio, asset growth, Altman Z, Beneish M, shareholder yield, quality acceleration — with a QARP (Quality-At-Reasonable-Price) overlay.

**Data source:** yfinance only — free, no API key required. All fetches go through a rate-limited parallel fetcher with exponential backoff on 429s, plus a persistent on-disk cache so runs are **resumable** — interrupt and re-run to pick up where you left off.

Methodology is documented in [`quality_investing_academic_research.md`](./quality_investing_academic_research.md).

---

## Quick Start

### 1. Install

```bash
pip install -r requirements_schwab.txt
pip install tqdm
```

### 2. Fetch data (resumable, one-time)

**Recommended: Two-step workflow**

```bash
# Step 1: Fetch all data (default: combined SP1500 = S&P 500 + 400 + 600)
python main_quality_analysis.py --fetch-only
```

You'll see two progress bars:
- **Fetching current** — current fundamentals (market cap, revenue, net income, …)
- **Fetching history** — 5 years of income / balance / cash flow statements

At ~1 req/sec, combined SP1500 (~1500 tickers) takes 1–2 hours. A smaller index like SP500 (~500 tickers) takes 20–30 minutes.

**Safe to interrupt with Ctrl-C.** Every ticker is persisted to `merged_opportunity_cache.pkl` the moment it's fetched. Re-running the same command resumes from where you stopped.

Start small to test:
```bash
# Test with first 50 tickers
python main_quality_analysis.py --fetch-only --limit 50
```

### 3. Score the data (instant, re-runnable)

```bash
# Step 2: Score all cached tickers (takes <1 second)
python main_quality_analysis.py --score-only
```

This generates three files in `outputs/`:

```bash
ls -lh outputs/
# - opportunities_20260424.json
# - opportunities_20260424_top.txt  ← Read this one first
# - opportunities_20260424_red.txt
```

| File | Contents |
|------|----------|
| `opportunities_YYYYMMDD.json` | Full ranked dataset (every ticker, every signal, every z-score) |
| `opportunities_YYYYMMDD_top.txt` | **Human-readable top-N shortlist** — start here |
| `opportunities_YYYYMMDD_red.txt` | Every ticker that failed a hard gate |

**Pro tip:** Re-run scoring anytime with different parameters (e.g., `--top-n 50`) without re-fetching.

### 4. Re-run or expand (optional)

**Re-score with different parameters:**
```bash
# Show top 50 instead of 25:
python main_quality_analysis.py --score-only --top-n 50
```

**Fetch additional indices:**
```bash
# Add SP600 to your existing SP500+SP400 cache:
python main_quality_analysis.py --fetch-only --index sp600

# Then re-score everything together:
python main_quality_analysis.py --score-only
```

**One-step workflow** (fetch + score in one command):
```bash
# Fetch missing tickers and score:
python main_quality_analysis.py  # Default: combined_sp
```

Cache entries expire after 7 days. Run `--fetch-only` again to refresh stale tickers.

---

## Typical Workflow

```bash
# Week 1: Fetch full S&P 1500 (one-time, ~60-90 min). Ctrl-C safe.
python main_quality_analysis.py --fetch-only

# Score the data (instant):
python main_quality_analysis.py --score-only

# Daily/weekly: Re-score with updated parameters (no fetching):
python main_quality_analysis.py --score-only --top-n 50

# Week later: Refresh stale cache (7-day TTL):
python main_quality_analysis.py --fetch-only  # Only fetches expired tickers
python main_quality_analysis.py --score-only
```

**Building cache incrementally:**
```bash
# Day 1: SP500 (~25 min)
python main_quality_analysis.py --fetch-only --index sp500

# Day 2: Add SP400 (~20 min)
python main_quality_analysis.py --fetch-only --index sp400

# Day 3: Add SP600 (~25 min)
python main_quality_analysis.py --fetch-only --index sp600

# Score all ~1500 tickers together (instant):
python main_quality_analysis.py --score-only
```

---

## Understanding the Output Files

### `opportunities_YYYYMMDD_top.txt` — Top Opportunities Shortlist

Human-readable ranked list of stocks that **passed all hard gates**. Each ticker is classified into one of four tiers:

| Tier | Criteria | Investment Thesis |
|------|----------|-------------------|
| **Compounder** | Top 10% quality score, all gates pass | Excellent businesses at fair/good prices. Hold long-term. |
| **Discount Compounder** | Top 20% QARP score (quality + value blend) | High-quality companies trading at attractive valuations. **Priority buy list**. |
| **Rising Quality** | Quality acceleration > 0 + above-median quality | Improving businesses. Watchlist for entry. |
| **Cash Return** | Shareholder yield > 5% + GPOA > 30% | Strong cash generators returning capital. Yield + quality hybrid. |

**Example output:**
```
Rank  Ticker    Tier                     Opp    QARP    GPOA    F  Sector
------------------------------------------------------------------------------------------
   1  RNG       Cash Return             82.8    73.7  121.0%    8  Technology
   2  CL        Neutral                 82.1    69.6   75.0%    5  Consumer Defensive
   3  YELP      Cash Return             78.8    75.2  138.0%    7  Communication Services
```

**Column definitions:**
- **Rank**: Position in ranked universe (1 = best)
- **Ticker**: Stock symbol
- **Tier**: Quality classification (see table above)
- **Opp**: Opportunity Score (0-100) — composite quality score weighted by Novy-Marx profitability anchor
  - 70+ = Excellent quality
  - 60-70 = Good quality
  - 50-60 = Above average
  - <50 = Below average
- **QARP**: Quality At Reasonable Price score (0-100) — 60% quality + 40% value blend
  - 70+ = High quality at attractive valuation ⭐ **Buy candidates**
  - 60-70 = Good quality, fair price
  - 50-60 = Average
  - <50 = Overvalued or low quality
- **GPOA**: Gross Profitability Over Assets (%) — (Revenue - COGS) / Total Assets × 100
  - >40% = Excellent capital efficiency (Novy-Marx 2013)
  - 30-40% = Good
  - 20-30% = Moderate
  - <20% = Weak
- **F**: Piotroski F-Score (0-9) — higher = better fundamentals (profitability + leverage + efficiency)
  - 8-9 = Excellent fundamentals
  - 6-7 = Good fundamentals
  - 5 = Minimum passing threshold (hard gate)
  - <5 = **Red-flagged** (excluded from rankings)
- **Sector**: GICS sector classification

**Interpreting the scores:**
- Focus on **QARP score** for buy candidates (quality + value blend)
- **GPOA** is the primary quality signal (Novy-Marx: profitability subsumes quality)
- **F-Score ≥ 6** indicates solid fundamentals across 9 dimensions
- Top 25 typically have Opp scores 70-85, QARP scores 60-75

**Why aren't AAPL/MSFT/NVDA here?**
- They often appear in **Compounder** tier (high quality)
- But rarely in **Discount Compounder** (too expensive by value metrics)
- QARP = 60% quality + 40% value → premium-priced stocks penalized

---

### `opportunities_YYYYMMDD_red.txt` — Red-Flagged Tickers

Stocks that **failed at least one hard gate**. Excluded from ranked shortlist.

**Example:**
```
ABC - GATE FAILURES: ['f_score', 'accrual_ratio']
  F-Score: 3 (threshold: ≥5) ❌
  Accrual Ratio: 0.15 (threshold: ≤0.10) ❌
  Reason: Low earnings quality + aggressive accounting
```

**Common gate failures:**
- **f_score < 5**: Weak fundamentals (Piotroski 2000)
- **asset_growth > 40%**: Empire building, likely overexpansion (Cooper 2008)
- **accrual_ratio > 10%**: Earnings not backed by cash (Sloan 1996)
- **beneish_m > -1.78**: Possible earnings manipulation (Beneish 1999)
- **altman_z < 1.80**: Bankruptcy risk (Altman 1968)
- **interest_coverage < 2×**: Can't service debt

**These are AVOID signals** — academic research shows these stocks underperform.

---

### `opportunities_YYYYMMDD.json` — Full Dataset

Complete ranked data with all signals and z-scores. Use for custom analysis in Python/notebooks.

**Structure:**
```json
{
  "AAPL": {
    "rank": 45,
    "quality_score": 0.78,
    "quality_z": 1.52,
    "qarp_z": 0.43,
    "tier": "Compounder",
    "gate_failures": [],
    "signals": {
      "gross_profitability": 0.45,
      "roe_persistence": 0.52,
      "cash_flow_quality": 1.15,
      "accrual_ratio": -0.03,
      "asset_growth": 0.08,
      "shareholder_yield": 0.02,
      "f_score": 8,
      "altman_z": 5.2,
      "beneish_m": -2.5
    },
    "z_scores": {
      "gross_profitability_z": 2.1,
      "roe_persistence_z": 1.8,
      ...
    }
  }
}
```

**Key fields:**
- `quality_score`: Composite quality (0-1), higher = better
- `quality_z`: Cross-sectional z-score for quality (relative to universe)
- `qarp_z`: QARP z-score (60% quality + 40% value)
- `tier`: Compounder | Discount Compounder | Rising Quality | Cash Return
- `gate_failures`: List of failed gates (empty = passed all)
- `signals`: Raw metric values (e.g., GPOA, F-Score, accruals)
- `z_scores`: Cross-sectional z-scores for each signal

**Use cases:**
- Filter by custom criteria (e.g., `f_score >= 8` + `altman_z > 3`)
- Re-rank by different weights (more growth vs. safety)
- Build sector-specific screens
- Export to Excel/Pandas for further analysis

---

## Hard Gates

A ticker is excluded from the ranked shortlist if it fails any of these (missing data is *not* a failure — gate is skipped if its input is None):

| Gate | Threshold | Source |
|------|-----------|--------|
| Piotroski F-Score | ≥ 5 | Piotroski (2000) |
| Asset Growth (YoY) | ≤ 40% | Cooper-Gulen-Schill (2008) |
| Accrual Ratio | ≤ 10% | Sloan (1996) |
| Beneish M-Score | ≤ -1.78 | Beneish (1999) |
| Altman Z-Score | ≥ 1.80 | Altman (1968) |
| Interest Coverage | ≥ 2× | Safety |

---

## Common Flags

| Flag | Purpose | Default |
|------|---------|---------|
| `--fetch-only` | Only fetch data, do not score (resumable) | off |
| `--score-only` | Only score cached data, do not fetch | off |
| `--index` | Single index: `sp500`, `sp400`, `sp600`, `nasdaq100`, `russell1000/2000/3000`, `combined_sp` | `combined_sp` |
| `--indices` | Comma-separated combination, e.g. `sp500,sp400` | — |
| `--ticker` | Individual stock analysis | — |
| `--limit N` | Only process first N tickers | 0 (all) |
| `--workers N` | Parallel workers (max 10 — yfinance limit) | 10 |
| `--rate R` | Requests per second | 1.0 |
| `--top-n N` | Number in the shortlist | 25 |

**Troubleshooting:**
- Hit 429s? Lower `--rate 0.5` and `--workers 5`
- Want to test? Use `--limit 50` to process first 50 tickers only

---

## Caching Summary

Two caches, both free and on-disk:

| File | Purpose | TTL |
|------|---------|-----|
| `financial_cache.pkl` | Current-year fundamentals (per `FinancialData`) | 48 h |
| `merged_opportunity_cache.pkl` | Scorer-ready merged dict with 5-year history | 7 d |

Delete either file to force a full refresh.

---

## Individual Stock Analysis

**Cross-sectional z-scores require a universe** — analyzing a single ticker in isolation produces z-scores of 0.0.

### Recommended Workflow (Meaningful Rankings)

```bash
# Step 1: Build a cached universe (one-time)
python main_quality_analysis.py --fetch-only

# Step 2: Score a single ticker against the full universe
python main_quality_analysis.py --ticker NVDA --score-only
```

This scores NVDA against all ~1500 cached tickers, producing:
- **Cross-sectional z-scores** (where NVDA ranks vs. the universe)
- **Rank** (e.g., "45 of 1502")
- **Percentile estimates** for each signal

**Output files:**
```
outputs/opportunities_20260424_single_NVDA.txt  # Human-readable with rank & percentiles
outputs/opportunities_20260424_single_NVDA.json # Full scoring data
```

### Fallback: Isolated Analysis (No Rankings)

```bash
# Fetch + analyze a single ticker (z-scores will be 0.0)
python main_quality_analysis.py --ticker NVDA
```

This fetches NVDA's data and shows raw signals, but **z-scores are meaningless** (N=1).

---

## Codebase Map

```
main_quality_analysis.py                 # CLI entrypoint (--fetch-only, --score-only)
quality_investing_academic_research.md   # Methodology & academic citations
merged_opportunity_cache.pkl             # (generated) persistent merged-dict cache

data/
  parallel_fetcher.py                    # ThreadPool + rate limit + 48h cache
  financial_data_fetcher.py              # yfinance current-year fetcher
  yfinance_fetcher.py                    # yfinance + currency conversion (foreign)
  ratio_calculator.py                    # ROE, ROIC, Altman Z, accruals, margins
  watchlist_config.py                    # Index -> ticker list resolver

quality/
  opportunity_scorer.py                  # Cross-sectional QMJ + QARP + hard gates
  earnings_quality.py                    # Piotroski F-Score, accrual ratio

workflows/
  opportunity_discovery.py               # Two-phase workflow (gather + score)

outputs/                                 # Generated reports (git-ignored)
  opportunities_YYYYMMDD.json            # Full ranked dataset
  opportunities_YYYYMMDD_top.txt         # Human-readable shortlist
  opportunities_YYYYMMDD_red.txt         # Red-flagged tickers
```

---

## Frequently Asked Questions

### Why aren't AAPL/MSFT/NVDA in the top outputs?

This is actually a **feature, not a bug** of the academic methodology. Here's why:

**QARP (Quality At Reasonable Price) Penalty**

The scanner uses a QARP overlay (60% quality + 40% value):
- AAPL, MSFT, NVDA are **excellent quality** companies
- But they trade at **premium valuations** (high P/E, low FCF yield, high EV/EBITDA)
- Result: Great quality score, poor value score → **excluded from "Discount Compounder" tier**

**Quality Acceleration Filter**

The "Rising Quality" tier requires **quality acceleration** (improving rate of improvement):
- Mega-caps have been excellent for **years** → flat quality trajectory
- Smaller companies showing **improvement** rank higher in this tier
- Think: 2nd derivative matters, not just level

**Cross-Sectional Z-Scores**

The scorer ranks **relative to the universe**, not absolute:
- NVDA might have 50% gross margins, but so do many software companies
- Asset-light businesses (GOOGL, META) can score **lower** on GPOA (gross profits / **assets**) than asset-heavy industrials with better capital efficiency

**Where they DO appear:**
- **"Compounder" tier** (top 10% quality, all gates pass) — if not overvalued
- **Full JSON** with high quality scores but mediocre QARP scores
- **Red-flagged list** if they fail hard gates (e.g., NVDA often fails F-Score, asset growth, or Beneish M due to rapid expansion)

**This is intentional** — the scanner finds **value in quality**, not just quality. It's designed to avoid overpaying for excellent businesses.

---

## Troubleshooting

- **Many 429 errors during fetch** — lower `--rate` to 0.5 and `--workers` to 5. The fetcher already retries with exponential backoff, but sustained 429s mean you're throttled; wait a few minutes and resume (cache preserves progress).
- **`ModuleNotFoundError: tqdm`** — `pip install tqdm`. Progress bar is optional but recommended for long runs.
- **A ticker has mostly `None` signals** — yfinance coverage is thin for some small-cap and foreign issuers. The scorer will still rank them using whatever signals are present; gates missing inputs are skipped rather than failing.
- **Foreign ticker with wrong currency** — delete `currency_rates_cache.json` to force refresh.
- **Want to start over** — `rm merged_opportunity_cache.pkl financial_cache.pkl`.
