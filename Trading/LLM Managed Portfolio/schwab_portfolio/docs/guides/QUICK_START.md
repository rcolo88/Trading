# Quick Start Guide

## How to Run Scripts

### Prerequisites
- Conda environment `trading_env` activated
- API credentials configured (Schwab, Finnhub)
- Working directory: `LLM Managed Portfolio/`

### Current Modular System (ALWAYS USE THIS)

Execute from the main project directory:

```bash
# Activate environment
conda activate trading_env

# Full execution (trading + reporting) - REQUIRES MARKET HOURS
python "Portfolio Scripts Schwab/main.py"

# Read-only operations (available 24/7)
python "Portfolio Scripts Schwab/main.py" --report-only
python "Portfolio Scripts Schwab/main.py" --generate-hf-recommendations
python "Portfolio Scripts Schwab/main.py" --account-status --dry-run
python "Portfolio Scripts Schwab/main.py" --risk-summary --dry-run

# Testing operations (available 24/7)
python "Portfolio Scripts Schwab/main.py" --test-parser
python "Portfolio Scripts Schwab/main.py" --dry-run
python "Portfolio Scripts Schwab/main.py" --test-schwab-api
```

## 🎯 STEPS Portfolio Analysis (RECOMMENDED)

**Complete 10-step STEPS research methodology in a single command.**

```bash
cd "Portfolio Scripts Schwab"

# Full analysis (all 10 steps)
python analysis/steps_orchestrator.py

# Quick analysis (skip optional steps for speed)
python analysis/steps_orchestrator.py --skip-thematic --skip-competitive --skip-valuation

# Test run (show what would be done without executing)
python analysis/steps_orchestrator.py --dry-run

# Detailed logging
python analysis/steps_orchestrator.py --verbose
```

**The 10 STEPS:**
1. Market Environment Assessment
2. Holdings Quality Analysis (CRITICAL)
3A. Core Quality Screening
3B. Thematic Discovery
4. Competitive Analysis
5. Valuation Analysis
6. Portfolio Construction
7. Rebalancing Trades
8. Trade Synthesis
9. Data Validation
10. Framework Validation

**Outputs:**
- `outputs/market_environment_YYYYMMDD.json`
- `outputs/quality_analysis_YYYYMMDD.json`
- `trading_recommendations/trading_recommendations_YYYYMMDD.md`

**Human-in-the-Loop Workflow:**
```bash
# Step 1: Run STEPS analysis (generates recommendations)
cd "Portfolio Scripts Schwab"
python analysis/steps_orchestrator.py

# Step 2: Review the generated recommendations
cat ../trading_recommendations/trading_recommendations_20251114.md

# Step 3: If approved, manually edit manual_trades_override.json
# Copy approved trades from recommendations, set "enabled": true

# Step 4: Execute approved trades (requires market hours)
python main.py
```

## 🤖 Autonomous Agent System

**The agent system autonomously generates trading recommendations using live news and financial data.**

```bash
# Set API key for news analysis
export FINNHUB_API_KEY='your_key_here'

# Run complete analysis pipeline
cd "Portfolio Scripts Schwab"
./run_all_analysis.sh           # Daily analysis
./run_all_analysis.sh --weekly  # Weekly analysis (includes S&P 500 screening)

# OR run individual steps manually:
python analysis/news_analysis_script.py              # Fetch & analyze news
python analysis/quality_analysis_script.py           # Quality metrics analysis
python analysis/thematic_analysis_script.py          # Thematic scoring
python analysis/watchlist_generator_script.py        # Weekly S&P 500 screening
python analysis/recommendation_generator_script.py   # Generate trading_template.md
```

**Outputs:**
- `outputs/news_analysis_YYYYMMDD.json`
- `outputs/quality_analysis_YYYYMMDD.json`
- `outputs/thematic_analysis_YYYYMMDD.json`
- `outputs/quality_watchlist_YYYYMMDD.csv`
- `trading_recommendations/trading_recommendations_YYYYMMDD.md`

**Review and execute:**
```bash
# Review recommendations
cat ../trading_recommendations/trading_recommendations_20251114.md

# If approved, edit manual_trades_override.json
# Set "enabled": true

# Execute trades (requires market hours)
python main.py
```

## Common Workflows

### Daily Portfolio Report
```bash
cd "Portfolio Scripts Schwab"
python main.py --report-only
```

**Generates**:
- `daily_portfolio_analysis.md` - Current portfolio analysis
- `LLM Managed Portfolio Performance.png` - Performance chart
- `LLM Position Details.png` - Position breakdown

### Weekly Full Analysis
```bash
cd "Portfolio Scripts Schwab"
python analysis/steps_orchestrator.py
```

**Recommended**: Run weekly (Friday after market close or Sunday)

### Monthly Deep Screening
```bash
cd "Portfolio Scripts Schwab"
# Screen all 1,500 stocks from S&P Composite 1500
python analysis/steps_orchestrator.py --watchlist-index combined_sp
```

**Runtime**: 45-60 minutes
**Recommended**: Run monthly for comprehensive opportunity discovery

### Check Account Status
```bash
python "Portfolio Scripts Schwab/main.py" --account-status --dry-run
```

**Available 24/7** - No market hours required

### Generate AI Recommendations
```bash
# Step 1: Generate report
python "Portfolio Scripts Schwab/main.py" --report-only

# Step 2: Generate HF recommendations
python "Portfolio Scripts Schwab/main.py" --generate-hf-recommendations

# Step 3: Review and approve
cat trading_recommendations/trading_recommendations_YYYYMMDD.md
```

## Market Hours vs Read-Only Operations

### Read-Only Operations (Available 24/7)
- `--report-only` - Generate portfolio report
- `--account-status` - View account summary
- `--risk-summary` - View risk analysis
- `--test-schwab-api` - Test API connection
- `--test-parser` - Test document parsing
- `--dry-run` - Simulate trades
- `--generate-hf-recommendations` - Generate AI recommendations

### Trading Operations (Market Hours Only)
- `--live-trading` - Execute REAL trades
- `--sync-schwab-account` - Sync with Schwab account
- Full execution mode (no flags)

**Market Hours**: Monday-Friday, 9:30 AM - 4:00 PM Eastern Time (NYSE/NASDAQ open)

## Execution for Testing

```bash
# Test parsing without trading (available 24/7)
python "Portfolio Scripts Schwab/main.py" --test-parser

# Generate report only (available 24/7)
python "Portfolio Scripts Schwab/main.py" --report-only

# Check account status (available 24/7)
python "Portfolio Scripts Schwab/main.py" --account-status --dry-run

# Dry run simulation (available 24/7)
python "Portfolio Scripts Schwab/main.py" --dry-run
```

## CLI Flags Reference

**STEPS Orchestrator:**
- `--dry-run` - Test without writing files
- `--skip-thematic` - Skip thematic analysis (faster)
- `--skip-competitive` - Skip competitive analysis (faster)
- `--skip-valuation` - Skip valuation analysis (faster)
- `--watchlist-index {sp500,sp400,sp600,nasdaq100,combined_sp}` - Index to screen
- `--watchlist-limit N` - Limit number of tickers
- `--verbose` - Enable detailed debug logging

**Main.py:**
- `--report-only` - Generate report without trading
- `--live-trading` - Enable LIVE trading
- `--dry-run` - Simulate trades
- `--test-parser` - Test document parsing
- `--test-schwab-api` - Test API connection
- `--account-status` - Show account summary
- `--risk-summary` - Show risk analysis
- `--sync-schwab-account` - Sync with Schwab
- `--generate-hf-recommendations` - Generate AI recommendations
- `--load-previous-day` - Load positions from history

## Troubleshooting

**"Market closed" error**:
- Check if using trading operations outside market hours
- Use read-only flags (`--report-only`, `--dry-run`) for 24/7 access

**Import errors**:
- Verify conda environment: `conda activate trading_env`
- Check imports work: `python -c "import yfinance; print('OK')"`

**API errors**:
- Schwab: Check `schwab_credentials.json` configuration
- Finnhub: Verify `FINNHUB_API_KEY` environment variable

**File not found**:
- Ensure working directory is `LLM Managed Portfolio/`
- Use absolute paths or cd to correct directory

## Next Steps

1. Review `docs/guides/STEPS_METHODOLOGY.md` for framework details
2. See `docs/guides/SYSTEM_ARCHITECTURE.md` for system design
3. Check `docs/research/` for investment methodology
