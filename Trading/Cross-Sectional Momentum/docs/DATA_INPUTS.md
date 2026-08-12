# Data inputs — the macro inventory and its holes

Answers the question "were all macro indicators used to the fullest?" directly: **no.** This file is
the complete inventory, and the honest gap list. Full protocol-level detail on closing these gaps is
in [`GAPS.md`](GAPS.md); the scraper build-out is tracked as Phase 2 of this project's docs effort
(see the repo's `docs/README.md` for status).

## Sources

Exactly two, and no others:

1. **yfinance** (`csm/data.py:29`, `auto_adjust=True`) — all price data, both the equity universe and
   the blend's ETF universe.
2. **FRED / ALFRED REST API** (`csm/fred.py:42`, `https://api.stlouisfed.org/fred/series/observations`)
   — point-in-time macro releases.

No Bloomberg, Quandl, Tiingo, or Alpha Vantage. `requirements.txt` has no `fredapi` dependency — the
loader is plain `requests` by design (see `csm/fred.py:7-8`).

**Correction:** `README.md:476-478` and `csm/macro_regime.py:12-13` both still say the environment
"couldn't reach" FRED (citing a `fred.stlouisfed.org` timeout). That's true only for that specific
host — `api.stlouisfed.org` works, and `csm/fred.py` is built on it and has been in production since
2026-08-05.

## The complete FRED inventory: three series

| Series | Meaning | Call sites | Live? |
|---|---|---|---|
| `UNRATE` | Unemployment rate | `csm/macro_regime.py:127`, `csm/blend_overlay.py:75,136` | No — only reachable via `macro_growth_axis: macro`, which is off |
| `NFCI` | Chicago Fed National Financial Conditions Index | `csm/macro_regime.py:132`, `csm/blend_overlay.py:131` | No — same |
| `T10Y2Y` | 10y-2y Treasury spread | `csm/macro_regime.py:137` | No — same |

A sweep of ~60 common FRED IDs (`DGS*`, `T10Y3M`, `T10YIE`, `DFII10`, `BAMLH0A0HYM2`, `BAA10Y`,
`VIXCLS`, `CPIAUCSL`, `PAYEMS`, `INDPRO`, `ICSA`, `WALCL`, `DTWEXBGS`, `DCOILWTICO`, `M2SL`, …)
returns zero hits anywhere in the repo. **All three of the series that do exist are switched off in
the live config** (`blend.macro_growth_axis: price`, `config.yaml:158`) — no FRED data currently
touches the traded book. Everything the project calls "macro" is ETF price momentum.

## FX / currency — entirely absent

Grep across `csm/`, `csmom.py`, `config.yaml`, `README.md` for
`usdjpy|jpy|yen|dxy|dollar|uup|fxy|fxe|dbv|carry` turns up nothing but position-sizing uses of the
word "dollar" and the ordinary English word "carry". **There is no FX series, no dollar index, and
no carry signal anywhere in this codebase. USD/JPY has never been tested.** The only non-USD
exposure at all is unhedged developed/emerging equity beta via EFA/EEM in the (currently unused)
regime-state panel. Worth noting: the sibling `Options/` project's CHANGELOG treats the August 2024
yen-carry unwind as a named market-stress window; this project has no visibility into that event at
all.

## Yield curve — one series, one vote, and it's off

`T10Y2Y` appears only inside `growth_score_macro` (`csm/macro_regime.py:103-145`) as one of three
equal-weighted point-in-time votes (`:137-140`), and that whole axis is the one
`config.yaml:158-164` records as tested and rejected for overfitting the 2015-2026 window (see the
contamination caveat below). Missing entirely:

- `T10Y3M` — the Estrella–Mishkin term spread, generally considered the stronger recession predictor
  of the two common curve measures.
- Curve *level* (as opposed to the growth-signal framing) and slope-change/steepening dynamics.
- Real yields (`DFII10`) and forward breakevens (`T5YIFR`).

IEF/TLT/SHY are held throughout the codebase as *assets* (rotation roster, regime-state panel,
deflation basket) — never differenced against each other into an actual curve signal.

## Credit spreads — absent

No `BAMLH0A0HYM2` (HY OAS), no `BAMLC0A0CM` (IG OAS), no `BAA10Y`, no HYG/JNK. `LQD` appears only as
a basket constituent (`macro_regime.py:51,66`), never differenced against Treasuries. Every "spread"
hit anywhere in the repo is a bid/ask half-spread (`config.yaml:113`, `csm/costs.py`,
`csm/blend.py:49`). `NFCI` implicitly embeds credit conditions — and it's disabled along with the
rest of the FRED axis.

## Commodities / inflation

`GLD` and `DBC` are held as assets across several baskets. TIPS exposure exists only via the
`TIP − IEF` 63-day return spread inside `inflation_score` (`csm/macro_regime.py:79-82`) — a market
breakeven-inflation proxy, not a FRED series. No oil/WTI as a series (only the word "oil" in a
docstring, `csm/macro_regime.py:24`), no copper, no copper-gold ratio, no `T10YIE`/`DFII10`.

## The live macro classifier is 100% equity-and-ETF-price-driven

With `macro_growth_axis: price` (the live setting), the growth axis is a cyclicals-minus-defensives
**equity** spread. `csm/macro_regime.py:86-88` records the measured cost of that: **0.766 daily
correlation with the SPYM growth sleeve** — meaning ~70% of the pre-fix book was effectively one
equity-beta bet before `macro_baskets: v2` was adopted to fix the basket *composition*. The
*classifying axis itself* is still equity, though — the fix treated the symptom, not the underlying
cause.

**The quadrant is half-migrated even in the unused FRED path.** `growth_score_macro` exists
(`csm/macro_regime.py:103-145`); there is no `inflation_score_macro`. So flipping
`macro_growth_axis: macro` today would still leave the inflation axis on ETF prices — a confound in
any future test of that axis.

## The infrastructure is genuinely good — the gap is coverage, not plumbing

`csm/fred.py` is a well-built point-in-time ALFRED loader:

- `realtime_start = realtime_end = asof` (`:97-99`) — the single-parameter trick that excludes both
  revision and publication look-ahead from the raw series itself.
- Cached to `outputs/cache/fred_vintages.parquet`, one row per `(series_id, asof, date)`, with
  atomic write-then-rename (`_atomic_to_parquet`, `:34-40`) so a killed process can't corrupt the
  cache — and retry-with-backoff on transient 5xx (`:104-118`).
- Adding a new series is a one-line `vintage_series(series_id, asof, ...)` call.

Known limits, worth stating plainly:

- ALFRED's vintage archive doesn't reach back as far as the plain observation history for every
  series — verified: NFCI vintages start ~2011-05, T10Y2Y ~2014-01, despite both series existing
  since 1971/1976. Earlier dates fall back to a non-realtime query bounded by `observation_end=asof`
  (`:81-95`) — see [`GAPS.md` #2](GAPS.md) for why that fallback is riskier than the code currently
  assumes.
- The cached vintage grid is **month-end only** — 319 asofs, `csm/fred.py` verified this session —
  which samples weekly `NFCI` and daily `T10Y2Y` far below their native publication frequency.
- `vintage_panel` (`csm/fred.py:193-214`) is fully implemented and documented but never called —
  dead code, exactly the right shape for the Phase 2 build-out.

**Data-integrity note carried over from [`GAPS.md` #1`](GAPS.md):** the cached vintage parquet has
429,654 duplicate rows spanning 2000-01-31 to 2002-10-31, which halves rolling-window calculations
computed over that span. That span sits inside the 2000-2014 holdout used to reject the FRED growth
axis above — so that rejection currently rests on contaminated evidence. See `GAPS.md` for the full
reproduction and fix plan.

## Data-span table

Bounds what any backtest — including the 2000-2014 holdout that carries this project's most
consequential rejection decisions — can actually cover
(`_LONG_HISTORY_START = "1999-01-01"`, `csm/data.py:52`):

| Ticker(s) | First real price |
|---|---|
| SPY, sector SPDRs (XLB/XLE/XLF/XLI/XLK/XLP/XLU/XLV/XLY), `^VIX` | 1999-01-04 |
| EFA, RWR | 2001-08-27 |
| IEF, TLT, SHY, LQD | 2002-07-30 |
| EEM | 2003-04-14 |
| AGG | 2003-09-29 |
| TIP | 2003-12-05 |
| GLD | 2004-11-18 |
| SPYM | 2005-11-15 |
| DBC | 2006-02-06 |
| `^VIX3M` | 2006-07-17 |
| BTAL | 2011-09-13 |
| XLRE | 2015-10-08 |
| XLC | 2018-06-19 |
| **DBMF** | **2019-05-08** |

Consequence: the 2000-2014 holdout runs the rotation sleeve on `[IEF, TLT, GLD, DBC]` only — no
managed-futures leg (DBMF) and no anti-beta leg (BTAL). That's a material caveat given how much
decision weight that holdout carries in this project's rejection discipline.
