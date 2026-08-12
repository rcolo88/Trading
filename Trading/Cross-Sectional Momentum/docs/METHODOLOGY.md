# Methodology — how the positive-Sharpe portfolio was actually built

This traces the **live** path — what `backtest`/`ideas`/`verify-book` actually run today — not the
project's full history (see [`CHANGELOG.md`](CHANGELOG.md) for that). Numbers in this file are for
orientation only; the authoritative, continuously-corrected figures live in
[`VALIDATION.md`](VALIDATION.md).

## What is traded

Not the equity cross-sectional momentum engine the project started as. As of 2026-08-05 (commit
`46a4f0d`), the primary strategy is a **3-way fixed-weight ETF blend**, rebalanced monthly:

| Sleeve | Weight | Holds |
|---|---|---|
| Growth | 40% | SPYM (`blend.growth_ticker`) |
| Macro regime tilt | 30% | One of 4 quadrant baskets, `csm/macro_regime.py` |
| Defensive rotation | 30% | Top 2 of a 6-ETF momentum roster, `csm/multiasset.py` |

`csmom.py:1314-1329` routes `backtest`/`ideas`/`verify-book` to this blend; the original equity
engine is preserved but demoted to `equity-backtest`/`equity-ideas`/`equity-verify-book`
(`csmom.py:1290-1310`). It was demoted because repeated testing (sector-neutral, beta-capped,
inverse-vol-weighted, a real inverse-ETF hedge) never found its stock-picking alpha statistically
significant — every variant's alpha t-stat sat at 0.4–1.1. See
[ADR 0001](decisions/0001-blend-replaces-equity-engine.md).

## The three sleeves

**Sleeve 1 — growth (40%).** Holds SPYM, not literal SPY — 0.02% expense ratio vs SPY's ~0.09%,
verified to have real trading history back to 2010 before adoption. The benchmark shown in every
report ("SPY buy-and-hold") always reads the literal `SPY` column regardless of this setting
(`csm/blend.py:212`) — it is a fixed comparison point, not a statement about what's held.

**Sleeve 2 — macro regime tilt (30%), `csm/macro_regime.py`.** Classifies the market into one of
four Goldilocks/Reflation/Stagflation/Deflation quadrants from two zero-crossing scores:

- Growth axis (`growth_score`, `:71-76`): 63-day return of equal-weight cyclicals
  `[XLY, XLI, XLF, XLB]` minus defensives `[XLU, XLP, XLV]`.
- Inflation axis (`inflation_score`, `:79-82`): `((TIP − IEF 63d return) + DBC 63d return) / 2` — a
  market breakeven-inflation proxy averaged with commodity momentum.
- `classify_regime` (`:148-165`) assigns the quadrant by sign; `macro_tilt_weights` (`:168-203`)
  equal-weights that quadrant's basket from `REGIME_BASKETS_V2` (`:62-67`), falling back to cash
  (SHY) if no basket ticker has enough history yet.

Both axes are **price-derived, not FRED-derived** — see [`DATA_INPUTS.md`](DATA_INPUTS.md) for why,
and for the measured cost of that choice (0.766 correlation with the growth sleeve).

**Sleeve 3 — defensive rotation (30%), `csm/multiasset.py`.** Ranks `[IEF, TLT, GLD, DBC, DBMF,
BTAL]` by 12-1 absolute momentum (`absolute_momentum`, `:98-101`) — the same formation convention as
the equity engine's own signal. Holds the top 2 **with positive momentum only**
(`defensive_weights`, `:104-135`); unfilled slots park in SHY rather than assuming an inception date
for a not-yet-listed name.

**Weight assembly (`csm/blend.py:69-151`, `blend_target_weights`).** Tickers appearing in both the
macro basket and the rotation roster (TLT, GLD) correctly **accumulate** both legs' contributions
(`:144-150`) rather than one overwriting the other — confirmed live: `outputs/blend_book.json`
shows GLD at 21% = 15% from the rotation slot + 6% from the macro deflation basket.

## The simulator

`simulate_blend` (`csm/blend.py:154-220`) — event-driven, hold-with-drift:

1. Each bar, existing holdings drift with the day's return (`:187`).
2. On a pending rebalance, execute at that day's price: cost = `|target_$ − current_$|.sum() ×
   cost_rate` (`:192`), where `cost_rate` is 5 bps one-way on gross turnover (`commission_bps: 0` +
   `half_spread_bps: 5`, `config.yaml:111-113`).
3. On a rebalance date (last trading day of the month, `month_end_dates`, `csm/multiasset.py:75-95`),
   the *next* bar's open executes the *this* bar's close-computed target — a strict 1-day lag.
4. The reported OOS window is **warm-started** from the last rebalance strictly before `oos_start`
   (`:175-177`), so the book is already invested when the window opens rather than starting from cash.

No vol targeting, no regime gate, and no position cap exist in this path — fixed weights by design.
The module docstring (`csm/blend.py:14-16`) is explicit about why: regime-switching between the
three sleeves was tested and found to create false-positive costs that exceeded what it saved.

## The discipline that actually produced the result

The single most transferable thing in this project is not any one number — it's the rejection rule
applied to every candidate improvement: **reject anything that improves the 2015-2026 window while
degrading the 2000-2014 holdout.** That holdout is a standalone ETF-panel reconstruction (not yet
re-run through the live engine on its full span) that, critically, covers the GFC — the 2015-2026
config window does not. Every rejection below fired that exact rule:

| Candidate | 2015-2026 result | 2000-2014 holdout result | Verdict |
|---|---|---|---|
| 60/20/20 weights | OOS Sharpe 1.384 (best of the sweep) | MaxDD −12.0%, worst year −9.4% | Rejected — reward for the recent SPY bull run |
| FRED growth axis (`macro_growth_axis: macro`) | Best OOS Sharpe of 4 variants, 1.524 | Sharpe 0.586, 2008 −18.46% (worse than baseline) | Rejected — see the contamination note below |
| `risk_overlay: robust` | Alpha t=2.31, a project record | Sharpe 0.465, MaxDD −36.7% | Rejected |
| `risk_overlay: gtt` | Worse Sharpe/CAGR/alpha, no offsetting benefit | 2008 −0.81% vs baseline's −13.27% | Rejected — insurance that doesn't pay for itself outside its one crisis |
| `risk_overlay: ladder` | Middling everywhere | Worst multi-fold result, 0.037 | Rejected |
| Phase-3 re-levering (50/55/60% growth) | OOS Sharpe rises monotonically 1.472→1.555 | Holdout Sharpe falls monotonically 0.656→0.554, MaxDD to −39.17%, 2008 to −21.81% | Decisively rejected — textbook overfit-to-recent-window signature |
| `macro_baskets: v2` | Better on every full-history/OOS metric | Better on every metric, one narrow multi-fold miss (0.290 vs 0.30 bar) | **Adopted** — the sole survivor of this whole pass |

Full narrative for each row is in `config.yaml:123-265` and the corresponding
[ADR](decisions/0005-reject-fred-growth-axis-and-risk-overlays.md).

**Caveat on the FRED-growth-axis row:** the vintage data behind that rejection was later found to
contain a duplicate-row bug in exactly the years (2000-2002) inside the holdout — see
[`GAPS.md` #1-2](GAPS.md). The rejection should currently be read as *unproven*, not settled.

## What this result actually is

Carried over from `csm/blend.py:6-16`: the edge is **diversification across three weakly-correlated
return streams, not stock-picking skill.** It does not claim to predict which stocks or sectors will
outperform beyond what the (freely available, market-observable) macro/momentum proxies already
capture. The alpha t-stat is 0.65 on the 2015-2026 config window (not significant on this specific,
SPY-favorable slice) and 2.05 on the longer 2010-2026 reconstruction. The claim that held on **every**
window tested, and is more robust than any single Sharpe number, is the drawdown reduction —
roughly half of SPY's MaxDD.

## What actually gets refreshed at a month-end rebalance

Data type matters here — the answer is not the same for prices, macro releases, and index membership.

**Prices: yes, genuinely re-scraped, every run.** `cmd_blend_ideas` loads the panel with
`_live_end()` = tomorrow (`csmom.py:89-97`, yfinance's `end` is exclusive, so this always includes
the latest available close), and the warmup window is anchored 30 months back from **today**, not
from `config.start_date` (`_ideas_start`, `csmom.py:100-112`). If the cached SPY close is ≥1 trading
day behind, it auto-refreshes with `refresh="tail"` (`csmom.py:1017-1021`), which re-downloads a
short overlap and **cross-checks the adjustment basis on it** (`csm/data.py:265-276`) — so a
dividend or split re-basing the whole adjusted price history is caught rather than silently spliced
onto stale data.

**Staleness fails closed, not open.** A partial trailing row is dropped
(`_drop_partial_tail`, `csm/data.py:161`), the panel is trimmed to complete rows so a
half-downloaded row can never become the as-of date (`csmom.py:1035`), and if the panel is still
more than 3 trading days behind, the command **errors out and emits no book** rather than trading
off old data (`csmom.py:1024-1031`).

**Ordering nuance:** the network-free pre-check (`csmom.py:987-998`) runs *before* any refresh, so
on a HOLD day nothing downloads at all — a quiet HOLD run is the design working, not a failed fetch.

**Macro / FRED: nothing is refreshed today, because nothing is used.** With the live
`blend.macro_growth_axis: price`, `growth_score_macro` is never called, so `csm/fred.py` never
executes in the `ideas` path — no API call, no vintage-cache read. The macro sleeve's quadrant is
classified entirely from the ETF prices refreshed above. This is defensible (no release lag or
revision risk) but concrete: **there is currently no macro-release input to go stale.** Phase 2 of
the project's macro work (see [`GAPS.md`](GAPS.md)) builds the scraper this will need the moment a
macro-axis variant is ever adopted; it does not change what `ideas` reads today.

**Index membership: not in the blend path at all.** The point-in-time S&P 1500 Wikipedia scrape
belongs to `fetch` and the equity engine. The blend trades a fixed ~14-ticker ETF set, so running
`fetch` monthly is only necessary if you also trade `equity-ideas`.
