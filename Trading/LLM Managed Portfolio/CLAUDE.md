# LLM Managed Portfolio - System Architecture

## ⚠️ IMPORTANT: Current Implementation Location

**ALWAYS use the modular implementation in `Pieced Portfolio Scripts/` directory.**

- ✅ **Current/Recommended**: `Pieced Portfolio Scripts/` - Fully modular system
- ❌ **Legacy/Deprecated**: `Daily_Portfolio_Script.py` - Monolithic file (kept for reference only)

## Environment Setup

### Primary Conda Environment
- **Environment Name**: `trading_env` (recommended) or `options` (legacy)
- **Python Version**: 3.11+
- **Location**: `/Users/robertcologero/opt/anaconda3/envs/trading_env/`

### Environment Creation
```bash
# Create new recommended environment
conda create -n trading_env python=3.11 yfinance matplotlib pandas numpy pandas-market-calendars pytz -c conda-forge -y

# Or use existing legacy environment
conda activate options
```

## How to Run Scripts

### Current Modular System (ALWAYS USE THIS)

Execute from the main project directory:

```bash
# Full execution (trading + reporting)
conda run -n trading_env python "Pieced Portfolio Scripts/main.py"

# Report generation only (no trading)
conda run -n trading_env python "Pieced Portfolio Scripts/main.py" --report-only

# Test document parsing functionality
conda run -n trading_env python "Pieced Portfolio Scripts/main.py" --test-parser
```

### Alternative with Legacy Environment
```bash
# Use legacy environment if trading_env not available
conda run -n options python "Pieced Portfolio Scripts/main.py" --report-only
```

### ❌ Legacy Scripts (DO NOT USE)
```bash
# DEPRECATED - Only kept for reference
conda run -n options python Daily_Portfolio_Script.py
conda run -n options python Daily_Portfolio_Script_new_parse.py --test-parser
```

## Modular System Architecture

### Core Modules in `Pieced Portfolio Scripts/`
1. **`main.py`** - System orchestrator and entry point
2. **`portfolio_manager.py`** - Holdings, cash, and state management
3. **`data_fetcher.py`** - Market data retrieval and yfinance integration
4. **`trade_executor.py`** - Document parsing and trade execution
5. **`report_generator.py`** - Analysis, reporting, and chart generation
6. **`market_hours.py`** - Market hours validation
7. **`trading_models.py`** - Data structures and enums
8. **`performance_validator.py`** - Multi-method performance validation
9. **`utils.py`** - Utility functions

### Key Benefits of Modular System
- **Smaller, manageable code chunks** for easier Claude interaction
- **Clear separation of concerns** - each module has focused responsibility
- **Better error handling** and data validation
- **Enhanced market hours protection**
- **Comprehensive logging** and state persistence

## Dependencies

### Core Requirements
- **yfinance** - Market data retrieval
- **matplotlib** - Chart generation
- **pandas** - Data manipulation and analysis
- **numpy** - Numerical operations
- **pandas-market-calendars** - Market hours validation
- **pytz** - Timezone handling

### Optional (for PDF parsing)
- **pdfplumber** or **PyPDF2** - PDF document parsing

## File Locations and State

### State Files (Auto-generated)
- `portfolio_state.json` - Current portfolio holdings and cash
- `portfolio_performance_history.csv` - Historical performance tracking
- `trade_execution.log` - Trade execution log
- `daily_portfolio_analysis.md` - Analysis file for Claude review

### Chart Outputs
- `LLM Managed Portfolio Performance.png` - Time series performance chart
- `Portfolio Position Details.png` - Position breakdown charts

## Claude Integration Notes

### When Working on Code
1. **Always reference `Pieced Portfolio Scripts/` modules** for current implementation
2. **Individual modules are sized** for optimal Claude processing (~200-700 lines each)
3. **Clear interfaces** between modules make changes easier to implement
4. **State persistence** ensures changes don't break portfolio continuity

### Common Tasks
- **Portfolio analysis**: Focus on `report_generator.py` and `performance_validator.py`
- **Trading logic**: Work with `trade_executor.py` and `trading_models.py`
- **Data issues**: Examine `data_fetcher.py` for yfinance integration
- **State management**: Check `portfolio_manager.py` for holdings/cash operations

### Execution for Testing
```bash
# Test parsing without trading
conda run -n trading_env python "Pieced Portfolio Scripts/main.py" --test-parser

# Generate report only (safe for any time)  
conda run -n trading_env python "Pieced Portfolio Scripts/main.py" --report-only
```

## System Flow

1. **Market Hours Validation** - Prevents execution outside trading hours
2. **Module Initialization** - Load portfolio state, configure data fetchers
3. **Document Processing** - Parse trading recommendations (PDF/Markdown)
4. **Trade Execution** - Execute orders with cash flow validation
5. **Portfolio Updates** - Update holdings and save state
6. **Report Generation** - Create analysis, charts, and export data
7. **State Persistence** - Save all changes for next run

## Recent Updates (2025-08-28)

### Portfolio Analysis Consolidation
- **REMOVED**: `portfolio_analysis_output.txt` (legacy JSON format)  
- **ENHANCED**: `daily_portfolio_analysis.md` - Now comprehensive single source
- **INCLUDES**: Portfolio weights, cash %, risk alerts, raw JSON data for LLM processing
- **BENEFIT**: Streamlined Claude analysis workflow with all data in one markdown file

### Manual Trading Override System
- **NEW**: `Portfolio Scripts Schwab/manual_trades_override.json`  
- **CONTROL**: Set `"enabled": true` to bypass document parsing entirely
- **TEMPLATE**: Pre-populated with structured JSON format for manual trade entry
- **PRIORITY**: Manual override takes precedence over all document parsing

### Enhanced Natural Language Parser  
- **IMPROVED**: `trade_executor.py` parsing for complex order formats
- **SUPPORTS**: "SELL 10 shares of QS", "BUY 1 share of XLV", "HOLD all 2 shares of NVDA"
- **PATTERNS**: 5 different regex patterns for natural language flexibility
- **FALLBACK**: Maintains backward compatibility with simple order formats

## Migration Notes

- **Legacy files preserved** but should not be used for active development
- **State files compatible** between legacy and modular systems
- **All functionality enhanced** in modular version with better error handling
- **Same CLI arguments** supported (`--report-only`, `--test-parser`)

**Always use `Portfolio Scripts Schwab/` for the latest Schwab-compatible implementation.**