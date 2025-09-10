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

### Chart Outputs (Generated in `Portfolio Scripts Schwab/`)
- `Portfolio Scripts Schwab/LLM Managed Portfolio Performance.png` - Time series performance chart
- `Portfolio Scripts Schwab/LLM Position Details.png` - Position breakdown charts

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

## Recent Updates (2025-09-10)

### Portfolio Analysis Consolidation  
- **REMOVED**: `portfolio_analysis_output.txt` (legacy JSON format) - **File completely removed from codebase**
- **ENHANCED**: `daily_portfolio_analysis.md` - Now comprehensive single source for all analysis
- **INCLUDES**: Portfolio weights, cash %, risk alerts, raw JSON data for LLM processing
- **BENEFIT**: Streamlined Claude analysis workflow with all data in one markdown file

### Chart Output Consolidation
- **CONSOLIDATED**: All chart outputs now generated in `Portfolio Scripts Schwab/` folder only
- **REMOVED**: Duplicate legacy charts from root directory  
- **CENTRALIZED**: `LLM Managed Portfolio Performance.png` and `LLM Position Details.png` in primary Schwab folder
- **BENEFIT**: Single source of truth for all portfolio visualizations

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

## 🤖 Local LLM Runtime System (NEW)

### Overview
A complete standalone local LLM-powered trading system that operates entirely within `local_runtime/` directory. This system provides an alternative to external LLM dependencies by using locally-hosted specialized financial models.

### Quick Start
```bash
# Navigate to local LLM system
cd local_runtime

# View system information and options
python local_start.py

# Test components (CPU mode - no GPU required)
python main_local.py --test-components --force-cpu

# Analysis only mode (generates recommendations without trading)
python main_local.py --analysis-only --force-cpu

# Full trading execution (requires GPU for optimal performance)
python main_local.py
```

### Architecture
The local LLM system uses 4 specialized financial models:
1. **News Analysis**: `AdaptLLM/Llama-3-FinMA-8B-Instruct` - Financial news sentiment
2. **Market Analysis**: `Qwen/Qwen2.5-14B-Instruct` - Technical analysis
3. **Trading Decision**: `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B` - Core recommendations  
4. **Risk Validation**: `microsoft/Phi-3-medium-4k-instruct` - Safety checks

### Key Features
- **Standalone Operation**: Complete copy of Portfolio Scripts Schwab system
- **Compatible Output**: Generates standard `trading_recommendation_*.md` files
- **Flexible Modes**: CPU/GPU, quick/full pipeline, analysis/trading
- **Safety Layers**: Multi-model risk validation and hard-coded limits
- **Zero Impact**: Does not modify original `Portfolio Scripts Schwab/` directory

### Integration with Existing System
```bash
# Original Schwab system (unchanged)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py"

# Local LLM alternative
cd local_runtime && python main_local.py

# Both systems use same portfolio state files and output formats
```

### Resource Requirements
- **CPU Mode**: 16GB+ RAM, any modern CPU (slower but functional)
- **GPU Mode (Quick)**: 8GB+ VRAM, 16GB+ RAM
- **GPU Mode (Full)**: 20GB+ VRAM, 32GB+ RAM

### Dependencies
```bash
# Core LLM dependencies
pip install vllm transformers torch accelerate

# Existing portfolio system dependencies
pip install yfinance pandas numpy matplotlib pandas-market-calendars pytz
```

### Development Workflow
1. **Testing**: Use `python main_local.py --test-components --force-cpu`
2. **Analysis**: Use `python main_local.py --analysis-only --force-cpu` 
3. **Production**: Use `python main_local.py` for full execution
4. **Documentation**: See `local_runtime/README_LOCAL.md` for complete details

The local LLM system provides a complete alternative to external LLM dependencies while maintaining full compatibility with the existing portfolio management workflow.