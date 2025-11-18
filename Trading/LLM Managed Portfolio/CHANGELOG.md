# Changelog

All notable changes to the LLM Managed Portfolio project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Reorganized codebase into logical folder structure (agents/, analysis/, analyzers/, core/, data/, quality/, schwab/, validators/, tests/, config/)
- Consolidated markdown documentation into `Portfolio Scripts Schwab/docs/` with agents/, research/, and guides/ subdirectories
- Reduced CLAUDE.md from 2073 lines to 42 lines with references to detailed documentation
- Extracted detailed guides: ENVIRONMENT_SETUP.md, QUICK_START.md, SYSTEM_ARCHITECTURE.md, STEPS_METHODOLOGY.md

### Added
- docs/README.md - Documentation index
- docs/guides/ENVIRONMENT_SETUP.md - Complete environment setup guide
- docs/guides/QUICK_START.md - Quick start and common workflows
- docs/guides/REORGANIZATION_SUMMARY.md - Codebase reorganization documentation
- docs/guides/WATCHLIST_CONFIGURATION_GUIDE.md - Watchlist configuration guide
- CHANGELOG.md - This changelog file
- __init__.py files for all Python packages

### Removed
- Deleted example files (example_quality_agent_integration.py, example_quality_integration.py)
- Deleted backup files (framework_validator_temp_backup.py)
- Deleted unused modules (hf_agent_system.py)

## [2025-11-14] - Codebase Reorganization

### Added
- Created modular folder structure for better organization
- Created comprehensive documentation system in `Portfolio Scripts Schwab/docs/`

### Changed
- Updated all import statements to reflect new package structure
- Moved 57 Python files into logical packages
- Moved 10 documentation files into organized folders

## [2025-11-13] - Framework Compliance Validator

### Added
- Framework validator (validators/framework_validator.py) - 1,200+ lines
- Comprehensive test suite (36 tests, 100% pass rate)
- 4-tier allocation validation with strict compliance checking
- Position sizing validation by market cap tier
- Tier-specific requirement validation (ROE persistence, filters)
- Compliance score calculation (0-100) with violation severity levels
- Integration with STEPS orchestrator (STEP 10)

### Changed
- Updated recommendation generator to include compliance validation
- Enhanced STEPS orchestrator with framework validation step

## [2025-11-11] - Watchlist Configuration System

### Added
- Flexible watchlist configuration module (data/watchlist_config.py)
- Support for multiple indexes: SP500, SP400, SP600, NASDAQ100, S&P Composite 1500
- CLI arguments for index selection and ticker limits
- Python API for programmatic configuration
- Comprehensive test suite (30 tests)
- Complete user guide (WATCHLIST_CONFIGURATION_GUIDE.md)

### Changed
- Replaced hardcoded S&P 500 watchlist with configurable system
- Updated quality_analysis_script.py with --index and --limit flags
- Updated watchlist_generator_script.py with multi-index support
- Updated steps_orchestrator.py with --watchlist-index flag

### Benefits
- Screen 1,500+ stocks across all market cap tiers
- Identify mid-cap and small-cap opportunities
- Flexible daily/weekly/monthly screening workflows

## [2025-11-10] - STEPS Orchestrator & Portfolio Constructor

### Added
- STEPS orchestrator (analysis/steps_orchestrator.py) - Complete 10-step methodology
- Portfolio constructor (core/portfolio_constructor.py) - 4-tier allocation enforcement
- Market environment analyzer (analyzers/market_environment_analyzer.py) - STEP 1
- Test suites for all new modules

### Changed
- Integrated portfolio construction into STEPS workflow
- Added market environment assessment as STEP 1
- Enhanced framework with systematic rebalancing trades

## [2025-11-03] - Data Quality Validator

### Added
- Data validator (validators/data_validator.py) - 900+ lines
- Comprehensive validation for 9 critical metrics
- Missing metric detection and stale data flagging
- Data consistency validation (negative values, relationships)
- Quality score calculation (0-10) with classification
- Test suite (33 tests, 100% pass rate)
- Integration with STEPS orchestrator (STEP 9)

## [2025-10-30] - Reasoning Agent & STEPS Thresholds

### Added
- Reasoning agent (agents/reasoning_agent.py) - DeepSeek-R1 integration
- STEPS decision thresholds aligned with PM_README_V3.md
- Quality threshold: 70/100 (not legacy 60)
- Thematic threshold: 28/40
- Position sizing integration based on scores

### Changed
- Updated reasoning logic to prioritize thematic exits
- Added explicit STEPS framework references in reasoning text
- Enhanced test suite to 34 tests (100% pass rate)

## [2025-10-13] - Market Hours Policy Update

### Changed
- Enhanced market hours validation to distinguish trading vs read-only operations
- Read-only operations now available 24/7: --account-status, --risk-summary, --report-only, --dry-run
- Trading operations still require market hours: --live-trading, --sync-schwab-account

### Benefits
- Check account status and run reports anytime
- Test functionality outside market hours
- Improved developer workflow

## [2025-09-10] - Portfolio Analysis Consolidation

### Removed
- portfolio_analysis_output.txt (legacy JSON format)

### Changed
- Enhanced daily_portfolio_analysis.md as comprehensive single source
- Includes portfolio weights, cash %, risk alerts, raw JSON data
- Streamlined Claude analysis workflow

### Benefits
- All data in one markdown file
- Easier LLM processing
- Cleaner codebase

## Earlier Changes

See git history for changes prior to changelog adoption.

## Notes

### Change Categories
- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements

### Version Numbering
This project does not currently use formal version numbers. Versions are tracked by date (YYYY-MM-DD) for major milestones.
