# LLM Managed Portfolio - Architecture Summary

## Purpose
This document provides a high-level overview of the system architecture, folder structure, and workflow for designing local deployment strategies.

---

## Folder Structure

### Primary System: `Portfolio Scripts Schwab/`
**Status**: Active production system
**Purpose**: Modular Schwab API-integrated trading system

**Core Modules**:
- `main.py` - System orchestrator and CLI entry point
- `portfolio_manager.py` - Holdings and cash state management
- `schwab_data_fetcher.py` - Market data retrieval via Schwab API
- `schwab_account_manager.py` - Account synchronization
- `schwab_trade_executor.py` - Live trade execution
- `schwab_safety_validator.py` - Pre-trade validation
- `trade_executor.py` - Document parsing and order processing
- `report_generator.py` - Analysis and chart generation
- `market_hours.py` - Market hours validation
- `trading_models.py` - Data structures and enums

**Generated Outputs**:
- Charts: `LLM Managed Portfolio Performance.png`, `LLM Position Details.png`
- State: Portfolio state files (see State Management section)

### Legacy System: Root Directory
**Status**: Deprecated, kept for reference only
**Files**:
- `Daily_Portfolio_Script.py` - Monolithic legacy implementation
- `Daily_Portfolio_Script_new_parse.py` - Parser testing version

---

## State Management

### Persistent State Files (Root Directory)
- `portfolio_state.json` - Current holdings, cash balances, position details
- `portfolio_performance_history.csv` - Historical performance tracking
- `trade_execution.log` - Execution history and audit trail
- `daily_portfolio_analysis.md` - Comprehensive analysis for LLM consumption

### Configuration Files
- `Portfolio Scripts Schwab/manual_trades_override.json` - Manual trading bypass system

---

## System Workflow

### Phase 1: Initialization
1. Validate environment (conda environment, dependencies)
2. Check market hours (trading vs read-only operations)
3. Load portfolio state from `portfolio_state.json`
4. Initialize Schwab API client (if trading mode)

### Phase 2: Input Processing
**Two input methods**:
- **Document Parsing**: Parse PDF/Markdown trading recommendations
- **Manual Override**: Read structured JSON from `manual_trades_override.json`

### Phase 3: Trade Execution (Market Hours Only)
1. Parse trading orders from input
2. Validate orders through safety checks
3. Execute trades via Schwab API
4. Update portfolio state with fills
5. Log all execution details

### Phase 4: Analysis & Reporting (Available 24/7)
1. Calculate portfolio metrics (value, returns, weights)
2. Generate performance charts (time series, position breakdown)
3. Create comprehensive analysis markdown
4. Export historical performance data
5. Save updated state

### Phase 5: State Persistence
1. Write `portfolio_state.json` with current holdings
2. Append to `portfolio_performance_history.csv`
3. Update `daily_portfolio_analysis.md`
4. Archive execution logs

---

## Execution Modes

### Trading Operations (Require Market Hours)
- `--live-trading` - Execute actual trades via Schwab API
- `--sync-schwab-account` - Synchronize with Schwab account state

### Read-Only Operations (Available 24/7)
- `--report-only` - Generate analysis and charts only
- `--account-status` - Display current account information
- `--risk-summary` - Show risk metrics and alerts
- `--test-parser` - Test document parsing logic
- `--dry-run` - Simulate execution without trading

---

## Data Flow

### Input Sources
1. **Market Data**: Schwab API → Real-time quotes, option chains
2. **Trading Signals**: Document files → Parsed orders
3. **Account Data**: Schwab API → Holdings, balances, positions
4. **Manual Input**: JSON override file → Structured orders

### Processing Pipeline
1. **Data Retrieval**: Fetch market data and account state
2. **Signal Processing**: Parse and validate trading recommendations
3. **Risk Validation**: Safety checks on order sizes, portfolio impact
4. **Execution**: Submit orders to Schwab API
5. **State Update**: Persist changes to local state files

### Output Artifacts
1. **State Files**: Updated JSON and CSV files
2. **Charts**: PNG visualizations of performance and positions
3. **Analysis**: Markdown reports for LLM consumption
4. **Logs**: Execution audit trail

---

## Integration Points

### External APIs
- **Schwab API**: Primary broker integration for trading and data
- **Yahoo Finance (yfinance)**: Fallback data source for market information

### File System
- **Read**: Portfolio state, configuration files, trading documents
- **Write**: Updated state, charts, analysis reports, logs

### LLM Integration
- **Current**: External LLM analyzes `daily_portfolio_analysis.md` to generate trading recommendations

---

## Key Design Principles

1. **Modularity**: Small, focused modules for maintainability
2. **State Persistence**: All changes saved to disk immediately
3. **Safety First**: Multiple validation layers before execution
4. **Separation of Concerns**: Trading vs analysis operations isolated
5. **Market Hours Protection**: Enforce trading restrictions automatically
6. **Backwards Compatibility**: Legacy systems still functional

---

## Deployment Considerations

### Environment Requirements
- **Python**: 3.11+
- **Conda Environment**: `trading_env` or `options`
- **Dependencies**: yfinance, pandas, numpy, matplotlib, pandas-market-calendars, pytz

### Execution Context
- **Working Directory**: Project root (`/Users/robertcologero/GitHub/Trading/LLM Managed Portfolio`)
- **State Location**: Root directory
- **Output Location**: Module-specific directories (`Portfolio Scripts Schwab/` for charts)

### Security & Safety
- **API Credentials**: Schwab API tokens (environment variables or config)
- **Trade Limits**: Hard-coded maximum position sizes
- **Market Hours**: Automatic enforcement for trading operations
- **Risk Validation**: Pre-trade safety checks on all orders

---

## Summary

This system provides a complete portfolio management solution with:
- **Modular architecture** for easy maintenance and extension
- **External LLM integration** for generating trading recommendations
- **Comprehensive state management** with full persistence
- **Safety-first design** with multiple validation layers
- **Flexible operation** (trading vs read-only modes)
- **Clear separation** between trading logic and analysis

The architecture supports Schwab API integration for trading execution while maintaining clean state management and providing comprehensive analysis outputs for LLM consumption.
