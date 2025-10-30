# LLM Managed Portfolio - System Architecture

## ⚠️ IMPORTANT: Current Implementation Location

**ALWAYS use the modular implementation in `Portfolio Scripts Schwab/` directory.**

- ✅ **Current/Recommended**: `Portfolio Scripts Schwab/` - Fully modular Schwab API system
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
# Full execution (trading + reporting) - REQUIRES MARKET HOURS
conda run -n trading_env python "Portfolio Scripts Schwab/main.py"

# Read-only operations (available 24/7)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --report-only
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --generate-hf-recommendations
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --account-status --dry-run
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --risk-summary --dry-run

# Testing operations (available 24/7)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --test-parser
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --dry-run
```

### ❌ Legacy Scripts (DO NOT USE)
```bash
# DEPRECATED - Only kept for reference
conda run -n options python Daily_Portfolio_Script.py
conda run -n options python Daily_Portfolio_Script_new_parse.py --test-parser
```

## Modular System Architecture

### Core Modules in `Portfolio Scripts Schwab/`
1. **`main.py`** - System orchestrator and entry point
2. **`portfolio_manager.py`** - Holdings, cash, and state management
3. **`schwab_data_fetcher.py`** - Schwab API market data retrieval
4. **`schwab_account_manager.py`** - Account synchronization with Schwab
5. **`schwab_trade_executor.py`** - Live trade execution via Schwab API
6. **`schwab_safety_validator.py`** - Pre-trade safety validation
7. **`trade_executor.py`** - Document parsing and order execution
8. **`report_generator.py`** - Analysis, reporting, and chart generation
9. **`market_hours.py`** - Market hours validation
10. **`trading_models.py`** - Data structures and enums
11. **`hf_recommendation_generator.py`** - HuggingFace AI recommendation orchestrator
12. **`hf_config.py`** - HuggingFace model configurations
13. **`agents/`** - HuggingFace agent modules (news, market, risk, tone)

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

### HuggingFace Agent System
- **requests** >= 2.31.0 - HuggingFace API communication
- **transformers** >= 4.30.0 - Model configurations and utilities

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
1. **Always reference `Portfolio Scripts Schwab/` modules** for current implementation
2. **Individual modules are sized** for optimal Claude processing (~200-700 lines each)
3. **Clear interfaces** between modules make changes easier to implement
4. **State persistence** ensures changes don't break portfolio continuity
5. **Read-only operations** (account status, reports, risk analysis) can run 24/7
6. **Trading operations** (live trading, account sync) require market hours (Mon-Fri 9:30AM-4PM ET)

### Common Tasks
- **Portfolio analysis**: Focus on `report_generator.py`
- **Schwab integration**: Work with `schwab_account_manager.py`, `schwab_trade_executor.py`
- **Trading logic**: Work with `trade_executor.py` and `trading_models.py`
- **Data issues**: Examine `schwab_data_fetcher.py` for Schwab API integration
- **State management**: Check `portfolio_manager.py` for holdings/cash operations

### Execution for Testing
```bash
# Test parsing without trading (available 24/7)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --test-parser

# Generate report only (available 24/7)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --report-only

# Check account status (available 24/7)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --account-status --dry-run
```

## System Flow

1. **Market Hours Validation** - Enforces market hours for trading operations only
   - **Trading operations** (--live-trading, --sync-schwab-account): Require market hours
   - **Read-only operations** (--report-only, --account-status, --risk-summary): Available 24/7
2. **Module Initialization** - Load portfolio state, configure Schwab API client
3. **Document Processing** - Parse trading recommendations (PDF/Markdown)
4. **Trade Execution** - Execute orders via Schwab API with safety validation
5. **Portfolio Updates** - Update holdings and save state
6. **Report Generation** - Create analysis, charts, and export data
7. **State Persistence** - Save all changes for next run

## Recent Updates

### Market Hours Policy Update (2025-10-13)
- **ENHANCED**: Market hours validation now distinguishes between trading and read-only operations
- **READ-ONLY 24/7**: `--account-status`, `--risk-summary`, `--report-only`, `--test-schwab-api`, `--dry-run` available anytime
- **TRADING HOURS**: `--live-trading`, `--sync-schwab-account` require market open (Mon-Fri 9:30AM-4PM ET)
- **BENEFIT**: Check account status, run reports, and test functionality outside market hours

### Portfolio Analysis Consolidation (2025-09-10)  
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

## 🤖 HuggingFace Agent System (NEW)

### Overview
An AI-powered trading recommendation system that uses HuggingFace Inference API to analyze portfolio data and generate trading recommendations. The system produces human-readable markdown documents following the `trading_template.md` format, which you manually review and approve before execution.

### Quick Start
```bash
# Step 1: Generate portfolio analysis (available 24/7)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --report-only

# Step 2: Generate AI trading recommendations (available 24/7)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --generate-hf-recommendations

# Step 3: Review generated recommendations
# Open: trading_recommendations/trading_recommendations_YYYYMMDD.md

# Step 4: Manually edit manual_trades_override.json with approved trades
# Set "enabled": true in the file

# Step 5: Execute approved trades (requires market hours)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py"
```

### Architecture
The HF agent system uses 4 specialized FinBERT models via HuggingFace Inference API:
1. **News Sentiment**: `mrm8488/distilroberta-finetuned-financial-news-sentiment` - Financial news analysis
2. **Market Sentiment**: `StephanAkkerman/FinTwitBERT` - Market outlook and trends
3. **Risk Assessment**: `ProsusAI/finbert` - Portfolio risk analysis with conservative bias
4. **Market Tone**: `yiyanghkust/finbert-tone` - Overall market tone detection

### Key Components in `Portfolio Scripts Schwab/`
1. **`hf_config.py`** - Model configurations and trading parameters
2. **`agents/base_agent.py`** - Base agent with smart retry logic and caching
3. **`agents/news_agent.py`** - News sentiment analysis with ticker extraction
4. **`agents/market_agent.py`** - Market sentiment and trend analysis
5. **`agents/risk_agent.py`** - Risk assessment with conservative bias
6. **`agents/tone_agent.py`** - Market tone analysis
7. **`hf_recommendation_generator.py`** - Orchestrates agents and generates markdown

### Workflow Features
- **AI Analysis → Human Review → Manual Execution**: Complete separation of AI recommendations and trading decisions
- **Manual Override Priority**: `manual_trades_override.json` always takes precedence
- **Template-Based Output**: Generates documents matching `trading_template.md` format
- **No Automatic Trading**: AI never executes trades directly - all trades require manual approval
- **24/7 Availability**: Recommendation generation works anytime (no market hours required)
- **Smart Retry Logic**: Handles HuggingFace API rate limits (503, 429) automatically
- **In-Memory Caching**: 5-minute cache reduces redundant API calls

### HuggingFace Agent Workflow
```bash
# Full workflow example
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --report-only
conda run -n trading_env python "Portfolio Scripts Schwab/main.py" --generate-hf-recommendations

# Review: trading_recommendations/trading_recommendations_20251030.md
# Edit: Portfolio Scripts Schwab/manual_trades_override.json
# Add approved trades and set "enabled": true

# Execute (market hours only)
conda run -n trading_env python "Portfolio Scripts Schwab/main.py"
```

### Manual Override JSON Format
```json
{
  "enabled": true,
  "trades": [
    {
      "action": "BUY",
      "ticker": "NVDA",
      "shares": 5,
      "reason": "AI infrastructure growth - approved from HF recommendation",
      "priority": "HIGH"
    },
    {
      "action": "SELL",
      "ticker": "XLV",
      "shares": 2,
      "reason": "Profit taking at 15% gain",
      "priority": "HIGH"
    }
  ]
}
```

### Dependencies
```bash
# HuggingFace dependencies
pip install requests>=2.31.0 transformers>=4.30.0

# Existing portfolio system dependencies (already installed)
pip install yfinance pandas numpy matplotlib pandas-market-calendars pytz
```

### Safety Features
- **Conservative Risk Bias**: Risk agent defaults to higher risk levels when uncertain
- **Manual Review Required**: No trades execute without explicit human approval
- **Priority-Based Execution**: HIGH → MEDIUM → LOW execution order
- **Position Limits**: 20% max position size enforced
- **Stop Loss & Profit Targets**: Risk management built into recommendations
- **Cash Reserve Management**: Dynamic cash allocation based on risk level

### Integration with Existing System
The HF system integrates seamlessly with the existing Schwab trading workflow:
- Reads from `daily_portfolio_analysis.md` (generated by --report-only)
- Outputs to `trading_recommendations/trading_recommendations_YYYYMMDD.md`
- Executes via `manual_trades_override.json` (same mechanism as manual trading)
- Uses existing `trade_executor.py` for order execution
- Maintains all safety validations and market hours enforcement

The HuggingFace Agent System provides AI-powered trading analysis while keeping humans firmly in control of all trading decisions.