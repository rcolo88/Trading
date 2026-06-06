# Trend Reversal — Repaint-Aware Backtesting & Tuning

A Python port, honest backtest, and fine-tuning of the ThinkOrSwim **Trend Reversal** indicator
([usethinkscript.com thread 183](https://usethinkscript.com/threads/trend-reversal-for-thinkorswim.183/)),
benchmarked against a suite of medium-term strategies. Validation borrows from Marcos López de Prado,
*Advances in Financial Machine Learning* (AFML): triple-barrier labeling, purged cross-validation,
meta-labeling, the Deflated Sharpe Ratio, and the Probability of Backtest Overfitting.

## The indicator is two systems, with opposite repaint behavior

Reading the full ThinkScript reveals two independent signal engines:

| | System A — EMA ribbon (bar colors) | System B — ZigZag "Reversal" arrows |
|---|---|---|
| Logic | EMA 9/14/21 of close, latched buy/sell state machine | `ZigZagHighLow` pivots + reversal arrows |
| Repaints? | **No** (on closed bars) | **Yes** |
| Tradeable? | Yes | Only the *causal* version |

**System A does not repaint on closed bars.** Every input (close-based EMAs, the bar's own
high/low) is final at the bar's close. The "signal disappears" warning from the forum is the *live,
still-forming* bar flickering — once a daily bar closes, its color is permanent. `test_indicators.py`
asserts this directly: recomputing on longer histories never changes past signals.

**System B (the ZigZag arrows) genuinely repaints**, because a ZigZag pivot is provisional until
price reverses far enough, so arrows slide backward in time. Backtesting against the final pivot
location is look-ahead cheating. `scripts/04_repaint_demo.py` quantifies the trap: the *same* rule
shows **97% CAGR / 3.9 Sharpe** with look-ahead vs **−6% CAGR / −0.2 Sharpe** when traded honestly.

So we **trade System A** and treat System B only as (a) a causal confirmation filter or (b) a
demonstration of repaint bias — never the look-ahead version.

## No-look-ahead execution model

Every strategy shares one execution convention, enforced by the engine and the test suite:

* Signal for bar `t` uses data through the **close of `t`**.
* The position is entered at the **open of `t+1`** (`exec_pos = target.shift(1)`).
* Returns are **open-to-open**; commission + slippage are charged on each position change.

Because the position held at the open of `t` derives only from the close of `t-1`, the engine
cannot look ahead — `test_backtest.py` proves it (a perfect-foresight signal does *not* get paid).

## Install & run

```bash
pip install -r requirements.txt          # pandas, numpy, scipy, scikit-learn, statsmodels, yfinance, matplotlib

python scripts/01_run_trend_reversal.py SPY    # faithful port: metrics + plots
python scripts/02_optimize.py SPY              # tune EMAs w/ Deflated Sharpe, PBO, walk-forward
python scripts/03_bakeoff.py SPY QQQ IWM       # all strategies on one engine
python scripts/04_repaint_demo.py SPY          # quantify the repaint look-ahead bias
python scripts/05_meta_labeling.py SPY         # AFML meta-labeling of the signal
python scripts/06_long_hold.py                 # long-only swing: buy green, hold, exit target/sell
python scripts/07_alpha_vs_spy.py              # CAPM alpha/beta of the strategy vs SPY buy & hold
python scripts/08_signal_chart.py              # live BUY/SELL arrow charts + current status to trade
python scripts/09_scanner_overlay.py           # time the Fundamental Scanner's top-N quality names
python scripts/10_index_candidates.py          # S&P 500 inclusion-candidate basket + trend overlay
python scripts/11_four_way.py                  # all four quality+timing approaches in one table
python scripts/12_rolling_sixmonth.py          # the four approaches over rolling 6-month windows
python scripts/13_scanner_charts.py            # re-run scanner fresh, paint a chart for each top-20 name
python scripts/14_tune_trend_reversal.py       # EMA-length x timeframe tuning, overfitting-aware
pytest tests/ -q                               # offline correctness + no-look-ahead guards
```

Each script writes its plots/CSVs into its **own subfolder** under `outputs/` (e.g. `outputs/bakeoff/`,
`outputs/four_way/`, `outputs/signal_charts/`) to keep the top level tidy; the one exception is the
combined scanner chart from script 13, which lands directly at `outputs/scanner_top20_painted.png`.
Downloaded OHLCV is cached in `data/`.

## Long-only swing workflow (`scripts/06_long_hold.py`)

The intended use: **buy a stock when Trend Reversal flips to a buy, hold it for weeks, and sell when
either a profit target is reached or a sell signal appears — long or cash, never short.** Defaults to
a handful of trending large caps (AAPL, MSFT, NVDA, AMZN, GOOGL) plus SPY.

```bash
# Full history, 10% profit target, exit when the green signal ends:
python scripts/06_long_hold.py

# >>> Backtest just the past ~6 months of data (what you asked for):
python scripts/06_long_hold.py --months 6

# Let winners run — no profit target, exit only on the sell signal (best for trenders, see below):
python scripts/06_long_hold.py --target 0

# Custom tickers / target / exit trigger:
python scripts/06_long_hold.py --months 6 --target 0.15 --exit sell_signal AAPL MSFT SPY
```

Flags: `--months N` restricts to the last N months (signals stay warm because they're computed on a
longer download, then sliced). `--target` is the profit target as a fraction (`0` = signal-only
exit). `--exit buy_end` sells when the green state ends (momentum down); `--exit sell_signal` waits
for the red signal. Output is a per-ticker table + averages vs buy & hold, plus equity plots.

**Key finding — a fixed profit target hurts a trend strategy.** Capping gains at a fixed % cuts the
fat-tailed winners that make trend-following work. On 2005–present (exit when green ends):

| Exit rule | NVDA total return | AAPL total return | avg Sharpe |
|---|---|---|---|
| 10% target | 1.8x | 5x | 0.59 |
| 20% target | 8x | 19.5x | 0.68 |
| **No target (signal-only)** | **137x** | **40x** | **0.71** |

So prefer `--target 0` and let the sell signal exit you; if you want downside protection, an ATR
trailing stop is a better tool than a fixed target. Either way the long-only version holds ~35–60% of
the time and roughly halves buy & hold's drawdown.

## Package layout

```
trendrev/
  data.py         yfinance OHLCV + CSV cache
  indicators.py   EMA/ATR/RSI/MACD, SuperTrend, Donchian, causal & repainting ZigZag
  strategies.py   faithful Trend Reversal state machine + benchmark strategies (REGISTRY)
  backtest.py     vectorized next-open engine, costs, equity, trade ledger
  metrics.py      CAGR, Sharpe/Sortino, max DD, Calmar, win%, profit factor, exposure
  afml.py         de Prado toolkit (see below)
  optimize.py     grid search + anchored walk-forward + DSR/PBO
  plotting.py     price/signals, equity, drawdown, heatmaps, PBO histogram
  scanner.py      reads the sibling Fundamental Scanner's top-N quality picks (the "what to own" feed)
```

## Alpha vs SPY buy & hold (`scripts/07_alpha_vs_spy.py`)

Answers "how much does this beat just holding the S&P 500?" properly — it regresses each long-only
strategy's daily returns on SPY buy & hold (CAPM) for **annualized alpha, beta, and a t-stat**, and
also builds an equal-weight portfolio of the strategies. Results 2005–present, signal-only exit:

| | Strategy CAGR | Ann. alpha | t-stat | beta |
|---|---|---|---|---|
| **Portfolio (eq-wt)** | **15.8%** | **+11.0%** | **4.28** ✓ | 0.38 |
| NVDA | 25.9% | +21.2% | 3.15 ✓ | 0.60 |
| AAPL | 18.9% | +15.2% | 3.50 ✓ | 0.36 |
| GOOGL / AMZN | 14.x% | +11% | 2.2–2.7 ✓ | 0.4 |
| MSFT | 6.8% | +4.4% | 1.25 ✗ | 0.30 |
| SPY itself | 5.5% | +2.4% | 1.31 ✗ | 0.29 |

The portfolio adds **~11%/yr of significant alpha (t≈4.3) at beta 0.38** — return largely independent
of the market. **Caveats:** on SPY itself the alpha is *not* significant (on the index the strategy
reduces risk, it doesn't add return); and AAPL/NVDA/GOOGL are hindsight winners, so the regression
alpha is real but *picking those names up front* is the actual hard part (selection bias). Re-run on
your own candidate names — `python scripts/07_alpha_vs_spy.py TICKER ...`.

## Live trade charts (`scripts/08_signal_chart.py`)

Generates a chart per ticker — candles colored by the **non-repainting** Trend Reversal state, the
EMA 9/14/21 ribbon, and **BUY ▲ / SELL ▼ arrows** at each flip — and prints the current status so you
know what to do now:

```bash
python scripts/08_signal_chart.py                      # default basket, last ~9 months
python scripts/08_signal_chart.py --lookback 120 NVDA SPY
```

Example status line: `NVDA  BUY/LONG since 2026-04-10 @ 188.63 | now 214.75 (+13.8%)`. Charts land in
`outputs/signal_charts/<TICKER>_trade_chart.png`. It always re-downloads fresh data so the latest bar is current.

## Combining with fundamentals — "what to own" × "when to own it"

Two scripts pair the non-repainting timing overlay with a slow-moving *universe filter*. The
architecture is identical in both: a quality/flow screen picks the **basket**, and Trend Reversal
System-A decides **when each name is held vs. cash** (long-only, equal-weight 1/N sleeves). The
overlay's job is **drawdown reduction**, and the scripts are built to keep us honest about which part
of the result is causal and which is hindsight.

### `scripts/09_scanner_overlay.py` — time the Fundamental Scanner's top-N

Reads the latest `opportunities_*.json` from the sibling **Fundamental Scanner** (`../Fundamental
Scanner/outputs/`), takes the top-N quality names, prints **what to do right now** on each
(BUY-NOW / HOLD-green / AVOID-red / neutral), and runs the equal-weight green-only portfolio.

```bash
python scripts/09_scanner_overlay.py                  # scanner top-10, full history
python scripts/09_scanner_overlay.py --top-n 15 --months 24
python scripts/09_scanner_overlay.py --no-proxy AAPL MSFT NVDA   # explicit names
```

It splits the result into three honestly-labelled layers:

| Layer | What it measures | Honesty |
|---|---|---|
| SPY buy & hold | the market baseline | clean |
| **Basket** buy & hold | the **SELECTION** effect | **hindsight** — names chosen by *today's* fundamentals |
| Basket **+ overlay** | SELECTION **+ TIMING** | timing is causal; selection still hindsight |
| `QUAL` + overlay | the **TIMING** effect alone | **clean** — a quality ETF, no name-selection bias |

**What it actually shows (top-10, 2005–present):** the overlay cuts the basket's max drawdown from
**−53% to −27%** (and on the non-hindsight `QUAL` ETF, **−32% → −18%**) — but at a real cost to
return *and* risk-adjusted return (basket Sharpe 0.79 → overlay 0.59; timing alpha t≈0.3, **not
significant**). **Verdict: the overlay is a drawdown tool, not a free lunch.** Use it if you value a
shallower max drawdown more than raw Sharpe, or can't stomach holding through a −50% basket
drawdown. The headline basket CAGR leans on hindsight stock-picking; don't trust it as a live edge.

> **Why we can't just backtest the selection:** the scanner scores stocks on *today's* fundamentals,
> and we have no point-in-time fundamental history. So a backtest of "hold the current top-10 since
> 2005" is selection bias. The live BUY/HOLD/AVOID readout has **zero** such bias and is the
> immediately-usable part; for a clean read on the *timing*, watch the `QUAL` row and forward-log the
> scanner's weekly top-N from here on.

### `scripts/10_index_candidates.py` — S&P 500 "bubble" candidates

Passive and 401k flows are price-insensitive buyers, so index membership carries a structural demand
tailwind. But the classic *trade the announcement* edge is largely gone — Greenwood & Sammon, *The
Disappearing Index Effect* (J. Finance 2025), measure the S&P 500 addition pop falling from **~7.3%
in the 1990s to a statistically-insignificant ~0.8% in the 2010s** as it got front-run. So this
script uses inclusion **candidacy as a universe filter**, not an event trade:

* **ADD candidates** — quality names **not yet** in the S&P 500 that clear S&P's own bar (cap near
  the inclusion threshold, **positive GAAP earnings**, quality gates). S&P's profitability rule is
  itself a quality gate, so these are flow-tailwind quality large-caps.
* **DROP watch** — current members that have shrunk below the threshold or failed the gates. Treated
  as **avoid / exit on red**, never shorted (the deletion effect is also dead and shorting fights the
  low-drawdown goal).

```bash
python scripts/10_index_candidates.py                  # default $15–60B cap band
python scripts/10_index_candidates.py --min-cap 18 --max-n 12 --months 36
```

Current S&P 500 membership is pulled from Wikipedia (cached to `data/sp500_members.csv`). Same
caveat as script 09: it uses *today's* membership and caps, so the candidate basket result reflects
the **timing-overlay behaviour**, not a tradeable historical edge. On the current candidate basket
the overlay again roughly halves drawdown (**−54% → −21%**).

### `scripts/11_four_way.py` — the four approaches, side by side

Runs all four ways of combining the quality screen with the timing tool on one engine, same costs and
window, so the ablation is clean:

| Approach | Universe | Entry | Exit |
|---|---|---|---|
| **Fundamental scanner** | top-N quality | buy all now, hold | — |
| **Fundamental scanner + entry timing** | top-N quality | when 'buy' paints | hold (live: until it leaves top-N) |
| **Fundamental scanner + full timing** | top-N quality | when 'buy' paints | when 'sell' paints |
| **S&P 500 + full timing** | S&P 500 | when 'buy' paints | when 'sell' paints |

```bash
python scripts/11_four_way.py                       # scanner top-10 AND top-20, 60 largest S&P 500
python scripts/11_four_way.py --sp500-full --months 36
```

> **Where the comparison table (CAGR / Sharpe / max DD / exposure) is saved:** every run writes it to
> **`outputs/four_way/four_way_comparison.csv`** and a rendered image **`outputs/four_way/four_way_comparison.png`**.
> By default it includes the scanner **top-10 and top-20** rows, the three timing variants of each,
> SPY buy & hold, and S&P 500 + full timing.

**Result (scanner top-10 and top-20, 2005–present).** The S&P 500 column is shown two ways because the size of
the universe matters: the 60 *largest* members trend unusually cleanly and flatter the result, while the full
~500 (the honest test) include the laggards too.

| | CAGR | Sharpe | max DD | exposure |
|---|---|---|---|---|
| SPY buy & hold | 10.9% | 0.66 | **−55%** | 100% |
| Fundamental scanner (top 10) | 16.4% | 0.79 | −53% | 100% |
| Fundamental scanner (top 20) | 17.2% | 0.86 | −48% | 100% |
| Fundamental scanner + entry timing (top 10) | 16.1% | 0.78 | −53% | 100% |
| Fundamental scanner + entry timing (top 20) | 17.6% | 0.88 | −48% | 100% |
| Fundamental scanner + full timing (top 10) | 8.8% | 0.73 | **−24%** | 97% |
| Fundamental scanner + full timing (top 20) | 9.0% | 0.83 | **−21%** | 99% |
| S&P 500 + full timing — **top-60** | 10.9% | **1.06** | −22% | 100% |
| S&P 500 + full timing — **full ~500** | 8.1% | **0.87** | **−23%** | 100% |

**Spreading the money from top-10 to top-20 helped on every axis** — higher return, higher Sharpe,
*and* shallower drawdown — and the rolling view (below) confirms it holds across windows, not just on
the full sample. Part of that is plain diversification (lower idiosyncratic risk); part is hindsight
luck in which extra names made the cut. So treat the *direction* (more names → calmer) as the robust
takeaway and the exact return bump as flattered.

Three findings fall straight out of the ablation:

1. **Entry timing alone is worthless (scanner → scanner + entry timing).** Over a long horizon you
   make one entry decision per name, so waiting for the green paint barely moves CAGR, Sharpe, *or*
   drawdown (−53% either way). Entry timing matters only over short windows — try `--months 12`.
2. **Exit timing is where the drawdown protection lives (+ entry timing → + full timing).** Cutting
   positions on the red signal roughly **halves max drawdown (−53% → −24%)** — but it also halves
   CAGR, because you sit out part of every recovery. Sharpe is roughly unchanged: you trade return
   for calm, not for free alpha.
3. **S&P 500 + full timing gives the best Sharpe and a robust drawdown cut — but it does *not* beat
   SPY on raw return once you use the honest full universe.** The −22/−23% drawdown holds across both
   samples (vs SPY's −55%), and Sharpe stays best-in-table (0.87–1.06 vs SPY 0.66). But raw CAGR
   falls from a flattering 10.9% on the 60 mega-caps to **8.1% on the full ~500 — below SPY's
   10.9%.** So it is a *much smoother ride for slightly less money*, not free alpha: you give up
   ~3%/yr of return to cut drawdown by more than half. Whether that trade is worth it is the honest
   question — it depends on whether you'd actually hold through a −55% SPY drawdown.

So the honest hierarchy for low drawdown is **S&P 500 + full timing ≳ scanner + full timing ≫ scanner
≈ scanner + entry timing**: the value is in *exit* timing across a *broad* universe, not in entry
timing or in narrowing to ten quality names — but even the best version buys its calm by sacrificing
some raw return.

### `scripts/13_scanner_charts.py` — fresh scanner → one scrollable painted chart of the top 20

One command that re-runs the Fundamental Scanner, then paints all of its top-20 names into a **single
tall, scrollable PNG** so you can eyeball which ones currently have a 'buy':

```bash
python scripts/13_scanner_charts.py            # fresh re-score, one combined chart of the top 20
python scripts/13_scanner_charts.py --lookback 45   # show 45 daily bars per panel instead of 30
python scripts/13_scanner_charts.py --fetch    # full fundamental refetch first (slow, ~1–2h)
python scripts/13_scanner_charts.py --no-scan  # skip re-scoring, chart the latest existing top-N
```

It (1) runs `main_quality_analysis.py --score-only` in `../Fundamental Scanner` so the shortlist is
fresh, (2) reads the freshly-written top-20, (3) downloads fresh prices, **resamples to 3-day bars**
(the tuning sweet spot, see script 14), and writes **one** `outputs/scanner_top20_painted.png` — a
vertical stack of one panel per ticker, each showing the **last 14 three-day bars** with full candles,
a **date under every bar**, the EMA 9/14/21 ribbon, and BUY ▲ / SELL ▼ arrows (panel title shows
`● BUY` when it is green right now). It also prints a live status line per name and a final list of
which top-20 names are flashing a buy. Use `--lookback N` for more/fewer bars. (The old
one-PNG-per-ticker `scanner_charts/` folder is deleted automatically.)

> The script reports the scan's date: if it isn't today, the scanner's fundamental cache is
> empty/expired (entries expire after 7 days) so it could not re-score, and you're seeing the latest
> available top-20 — run `--fetch` for a genuinely fresh fundamental pass. The price charts are
> always fresh.

### `scripts/12_rolling_sixmonth.py` — rolling 6-month view (where the timing actually earns its keep)

A single full-history Sharpe hides *when* a strategy helps. This runs the same four approaches over
every rolling 6-month window (daily close, monthly step) and reports the distribution. The indicator
is computed on full history and only the returns are sliced per window, so the EMA ribbon/state
machine are always warmed up — a cold 6-month recompute would misfire for the first ~month.

**Across all 251 rolling 6-month windows (2005–present):**

| Approach | median Sharpe | % windows profitable | median 6mo ret | **worst 6mo ret** | median maxDD |
|---|---|---|---|---|---|
| SPY buy & hold | 1.18 | 78% | +6.9% | **−43.5%** | −7.9% |
| Fundamental scanner (top 10) | 1.06 | 78% | +9.3% | **−40.0%** | −10.0% |
| Fundamental scanner (top 20) | 1.11 | 79% | +9.1% | −39.6% | −9.2% |
| Fundamental scanner + full timing (top 10) | 0.68 | 67% | +3.4% | **−14.9%** | −6.4% |
| Fundamental scanner + full timing (top 20) | 0.86 | 69% | +4.1% | **−12.6%** | **−5.4%** |
| S&P 500 + full timing | 1.16 | **79%** | +5.1% | **−12.9%** | **−5.4%** |

(Entry-timing rows omitted — they track the plain scanner rows. Top-20 + full timing now essentially
**matches the broad S&P 500** on drawdown and worst-window, at a higher hit rate than top-10.)

The rolling frame reveals what the single number buried: **the full-timing approaches barely change
the *median* window, but they slash the *tail*.** The worst 6-month stretch goes from −40/−44% (SPY,
scanner) to −13/−15% (full timing) — a ~70% cut in the ugliest loss. S&P 500 + full timing also has
the highest hit rate (79% of windows profitable) and the shallowest typical drawdown (−5.4%). That is
precisely a low-drawdown profile: you don't win more often or by a wider median margin, you just
**stop having −40% half-years.**

Two honest caveats the rolling view also makes visible: (1) the untimed scanner (with or without
entry timing) has the same tail risk as SPY — confirming quality is a *return* tilt, not crash
protection; (2) in the **latest 6 months** the scanner names are actually *down* (~−3.5%) while the
mega-cap-driven S&P 500 + full timing is up ~21% — a live
reminder that quality/value goes through long stretches of underperformance versus momentum.

### `scripts/14_tune_trend_reversal.py` — can we tune EMA lengths / timeframe? (mostly no, except bar size)

Sweeps the EMA ribbon `(superfast, fast, slow)` + low-filter (36 valid configs) across four
timeframes — daily, 2-day, 3-day, weekly (resampled from daily) — evaluated as the scanner top-20
long-only full-timing portfolio, with Deflated Sharpe, PBO, a noise metric (trades/year), and a
70/30 walk-forward holdout.

**Finding 1 — fine-tuning the EMA lengths is fitting noise; keep 9/14/21.** On any timeframe all 36
configs cluster within ~0.85–0.97 Sharpe, and **PBO is 57–73%** (you can't reliably pick a winner).
The holdout proves it: the in-sample-best daily config (5/34/50) **lost to 9/14/21 out-of-sample**
(OOS Sharpe **0.422 vs 0.443**). Deflated Sharpe ≈100% says the *family* has skill — it's the
*tuning* that doesn't survive. So don't bother optimising the triple.

**Finding 2 — the bar *timeframe* is the real, config-independent lever, and slower is calmer.**
Holding the EMAs at your **9/14/21** and only changing the bar size:

| Timeframe | Sharpe | max DD | trades/yr (per name) |
|---|---|---|---|
| Daily | 0.855 | −19.9% | **2.9** |
| 2-day | 0.871 | −19.3% | 1.5 |
| **3-day** | **0.892** | −20.7% | **1.0** |
| Weekly | 0.910 | −22.8% | 0.6 |

Coarsening the bars **monotonically raises Sharpe and roughly halves trade frequency at each step**
(2.9 → 0.6 round-trips/year) — a structural noise reduction, not a fitted parameter, so it's far more
trustworthy than the EMA grid. Caveat: on **weekly** the full red "sell" state almost never paints,
so the strategy quietly degenerates toward buy & hold (highest CAGR ~12.7%, but buy-&-hold-like
−24% drawdown — it stops being a timing system). **3-day daily-close bars are the sweet spot**:
best Sharpe among the still-timing frames, ~⅓ the whipsaws of daily, comparable drawdown.

**Takeaway:** keep EMA 9/14/21; if you want less noise and a slightly higher Sharpe, run the signal
on **2–3 day bars** rather than daily. Don't go to weekly expecting "timing" — there it's ~buy & hold.

## AFML toolkit (`trendrev/afml.py`)

| Function | AFML ch. | Purpose here |
|---|---|---|
| `get_daily_vol`, `cusum_events` | 2–3 | Event-based sampling for labels |
| `add_vertical_barrier`, `get_events`, `get_bins` | 3 | Triple-barrier labels + meta-labeling |
| `num_co_events`, `avg_uniqueness`, `return_attribution_weights` | 4 | De-overlap concurrent labels |
| `PurgedKFold`, `cv_score` | 7 | Leakage-free cross-validation |
| `bet_size_from_prob` | 10 | Probability → position size |
| `probabilistic_sharpe_ratio`, `deflated_sharpe_ratio` | 14 | Skill vs track-record length & trial count |
| `prob_backtest_overfitting` (CSCV) | 11–12 | How likely the tuning is overfit |

## What the backtests actually show (SPY/QQQ/IWM daily, 2005–2026, 1+5 bps costs)

1. **As a symmetric long/short system on indices, Trend Reversal is poor** — shorting an
   index that mostly rises is a structural drag (SPY long/short Sharpe ≈ 0, CAGR ≈ −1.5%).
2. **Long-only flips it into a legitimate risk-reducer.** Long-only **13/21/50** on SPY: Sharpe
   **0.60**, CAGR **5.6%**, max drawdown **−19%** at ~60% exposure — vs buy & hold's Sharpe 0.66,
   CAGR 11%, **−55%** drawdown. It roughly matches risk-adjusted return with **~⅓ the drawdown**.
   The edge is crash avoidance, not out-returning the index.
3. **Tuning prefers a longer slow EMA (50 over 21)** and the `low>EMA9` filter on — but the
   improvement is modest, **Deflated Sharpe ≈ 61%** and **PBO ≈ 29%**, so don't over-trust the peak.
   Walk-forward OOS Sharpe (0.18) tracks in-sample (0.22): stable, not overfit, just modest.
4. **Meta-labeling adds real, measurable skill** (PurgedKFold accuracy 0.72 vs 0.54 base rate) and
   slashes drawdown (−59%→−18%) and volatility, but cannot manufacture profit from a near-zero-edge
   primary signal — direction and instrument choice dominate.

## Caveats

* `displace > 0` in the original script does `price[-displace]` = genuine future look-ahead; this
  port keeps `displace = 0` and you should never set it positive for live or backtest use.
* yfinance daily data is split/dividend adjusted; results assume next-open fills with 6 bps
  round-trip-ish cost. Tune `commission_bps`/`slippage_bps` to your broker.
* Index results need not match your live experience on single names / 6h bars — re-run the scripts
  on your actual tickers (every script takes a ticker argument).

## Suggested next steps

* Run `01`–`03` on the specific tickers you trade; the long-only / longer-slow-EMA variant is the
  one to scrutinize.
* Add an ATR trailing stop as an exit variant in `strategies.trend_reversal` and re-optimize.
* Port the 6h timeframe by resampling 1h yfinance data in `data.py` (intraday history ~730 days).
