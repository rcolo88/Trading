# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
