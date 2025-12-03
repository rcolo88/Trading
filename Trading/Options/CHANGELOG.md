# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
