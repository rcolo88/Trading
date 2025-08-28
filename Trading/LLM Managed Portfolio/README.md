# Daily Portfolio Script

A Python-based automated portfolio tracking and analysis system designed for systematic daily trading decisions using AI-powered portfolio management with full automation capabilities.

## Engineer Goal

Support the PM (Portfolio Manager) in creating a useful financial functions to maximize stock market return. 

## Features

- **Real-time Portfolio Tracking**: Monitor current values, P&L, and position weights
- **Benchmark Comparison**: Performance vs S&P 500 (SPY) and Russell 2000 (IWM)
- **Risk Management Alerts**: Automated stop-loss and profit target notifications
- **Weight Drift Analysis**: Track deviation from target allocations
- **Volume Anomaly Detection**: Identify unusual trading activity
- **Performance Charting**: Visual comparison against market benchmarks
- **Historical Metrics Export**: Enhanced CSV tracking for comprehensive analysis
- **AI-Optimized Output**: Formatted text file for Claude analysis
- **🤖 Automated Trade Execution**: Full automation from document parsing to trade execution
- **📄 Multi-Format Document Processing**: Supports both Markdown (.md) and PDF (.pdf) files
- **💰 Sophisticated Cash Flow Management**: SELL→BUY prioritization with partial fill support
- **🛡️ Professional Risk Management**: Pre-execution validation and cash reserve protection
- **📝 Complete Audit Trail**: Comprehensive logging and state management

## Installation & Setup

### Prerequisites
- Python 3.8+
- Internet connection for market data

### Dependencies
```bash
pip install yfinance pandas numpy matplotlib os datetime
pip install pdfplumber  # For PDF document processing (recommended)
# OR alternatively:
pip install PyPDF2      # Alternative PDF processing
```

### Quick Start

#### Modular System (Recommended)
```bash
# Full execution (trading + reporting)
conda run -n trading_env python "Portfolio Scripts/main.py"

# Report generation only (safe for any time)
conda run -n trading_env python "Portfolio Scripts/main.py" --report-only

# Load positions from saved state (recovery mode)
conda run -n trading_env python "Portfolio Scripts/main.py" --load-previous-day

# Test document parsing without trading
conda run -n trading_env python "Portfolio Scripts/main.py" --test-parser
```

#### Legacy System (Deprecated)
```bash
python Daily_Portfolio_Script.py
```

## Command Line Options

### Portfolio Recovery
Use this when you need to restore your portfolio positions from the last saved state:

```bash
conda run -n trading_env python "Portfolio Scripts/main.py" --load-previous-day
```

**When to use**:
- Portfolio shows incorrect/hardcoded positions
- After system updates or code changes
- When `portfolio_state.json` timestamp is behind performance history
- To recover from initialization issues

**What it does**:
- Loads positions and cash from `portfolio_state.json`
- Compares with current hardcoded defaults
- Updates portfolio if positions differ
- Shows summary of restored positions
- Saves updated state for persistence

### Report-Only Mode
Generate portfolio analysis without executing any trades:

```bash
conda run -n trading_env python "Portfolio Scripts/main.py" --report-only
```

**Safe to run anytime** - no trading operations, only market data analysis.

### Document Parser Testing
Test trading document parsing without executing trades:

```bash
conda run -n trading_env python "Portfolio Scripts/main.py" --test-parser
```

Useful for validating trading recommendations before live execution.

## Daily Workflow

### Morning Routine (Every Trading Day)

#### Step 1: Generate Daily Analysis
**Time**: After market open (9:30 AM ET) or during lunch break (12:00-1:00 PM ET)

```bash
cd "LLM Managed Portfolio"
python Daily_Portfolio_Script.py
```

**What happens:**
- Script fetches current market prices for all positions
- Calculates P&L, weight drift, and benchmark performance
- Generates risk alerts and volume anomalies
- Creates performance chart comparing portfolio vs S&P 500 vs Russell 2000
- Exports enhanced historical metrics to CSV
- Produces `portfolio_analysis_output.txt` for AI analysis

#### Step 2: Get Claude's Trading Recommendations
**Platform**: Claude.ai chat interface

**Method A** (Recommended): 
- Upload the generated `portfolio_analysis_output.txt` file directly to Claude

**Method B** (Alternative):
- Copy contents of `portfolio_analysis_output.txt`
- Paste into Claude chat

**Request Format**: Ask Claude to provide recommendations in this format:
```
"Please provide your trading recommendations in the structured ORDERS format with explicit BUY/SELL commands and share quantities using the following structure:

## ORDERS

### IMMEDIATE EXECUTION (HIGH PRIORITY)
**SELL all 19 shares of SOUN** - Risk management
**SELL 3 shares of CYTK** - Reduce exposure before earnings

### POSITION MANAGEMENT (MEDIUM PRIORITY)
**HOLD all 3 shares of IONS** - FDA catalyst upcoming
**BUY 15 shares of NVDA** - AI infrastructure play
"
```

#### Step 3: Save Claude's Response
- Save Claude's response as `trading_recommendation.md` or `trading_recommendation.pdf`
- The system will auto-detect the most recent file

#### Step 4: Execute Automated Trading
**No manual intervention required!**

```bash
python Daily_Portfolio_Script.py
```

**The system automatically:**
- 🔍 **Detects** the most recent trading recommendation file
- 📄 **Parses** orders from markdown or PDF format
- 💰 **Validates** cash flow and trade feasibility
- ⚡ **Executes** trades in optimal order (SELL→BUY)
- 💾 **Updates** portfolio holdings permanently
- 📝 **Logs** every action for complete audit trail

**Expected Output:**
```
🤖 AUTOMATED TRADE EXECUTION
📄 Document: trading_recommendation_aug12.md
📋 PARSED ORDERS (3):
1. SELL 19 shares of SOUN (HIGH)
2. SELL 3 shares of CYTK (HIGH)  
3. BUY 15 shares of NVDA (MEDIUM)

💰 CASH FLOW ANALYSIS:
✅ All trades are feasible with current cash flow strategy

⚡ EXECUTING TRADES...
📤 PAPER TRADE: SOLD 19 shares of SOUN at $10.65 = $202.35
📤 PAPER TRADE: SOLD 3 shares of CYTK at $34.71 = $104.13
📥 PAPER TRADE: BOUGHT 15 shares of NVDA at $180.50 = $2,707.50

📊 EXECUTION SUMMARY:
✅ Executed: 3
❌ Failed: 0
```

#### Step 5: Review and Continue
**After successful execution:**
- Portfolio holdings automatically updated in memory and saved to `portfolio_state.json`
- Complete trade log saved to `trade_execution.log`
- Updated performance metrics exported to CSV
- Ready for next day's analysis

## State Management & Data Persistence

### Portfolio State Management
The system uses a **dual approach** for robust state management:

#### **portfolio_state.json (Current Holdings)**
- **Purpose**: Stores your current portfolio state (what you own RIGHT NOW)
- **Content**: Cash balance, all positions with shares/prices/allocations
- **Usage**: Loaded on script startup, updated after successful trades
- **Benefit**: Portfolio persists between script runs - no lost trades!

**Example `portfolio_state.json`:**
```json
{
  "timestamp": "2025-08-12T16:54:45.509068",
  "cash": 408.89,
  "holdings": {
    "IONS": {"shares": 3, "entry_price": 37.01, "allocation": 111.03},
    "NVDA": {"shares": 1, "entry_price": 175.0, "allocation": 175.0}
  },
  "last_update": "2025-08-12 16:54:45"
}
```

#### **trade_execution.log (Audit Trail)**
- **Purpose**: Complete transaction history (bank statement of all trades)
- **Content**: Every buy/sell action with timestamps, prices, and context
- **Usage**: Compliance, debugging, performance analysis
- **Benefit**: Full audit trail for regulatory compliance and analysis

**Example `trade_execution.log`:**
```
2025-08-12 16:54:45,509 - INFO - AUTOMATED TRADE EXECUTION SESSION STARTED
2025-08-12 16:54:46,123 - INFO - Processing document: trading_recommendation_aug12.md
2025-08-12 16:54:47,456 - INFO - TRADE EXECUTED: SOLD 19 shares of SOUN at $10.65 = $202.35
2025-08-12 16:54:47,789 - INFO - POSITION CLOSED: Removed SOUN position entirely
2025-08-12 16:54:48,012 - INFO - Cash updated: $2.34 + $202.35 = $204.69
```

### Why Both Are Needed
- **State File** = Current account balance (what you have now)
- **Log File** = Bank statement (transaction history)
- **Together** = Complete operational continuity + full audit trail

## Portfolio Management Features

### Current Script Capabilities

#### **Position Tracking**: 
- Any number of positions with any ticker symbols
- Flexible allocations with different share counts and entry prices
- Cash management tracking available cash for new positions
- Automatic calculations where all P&L, weights, and metrics update automatically

#### **Automated Trading**:
- ✅ **SELL orders**: Exact share quantities (`SELL 19 shares of SOUN`)
- ✅ **REDUCE orders**: Percentage-based position sizing (`REDUCE CYTK by 50%`)
- ✅ **BUY orders**: Including entirely new positions (`BUY 15 shares of NVDA`)
- ✅ **HOLD orders**: Recognized and appropriately ignored
- ✅ **Cash management**: Real-time balance updates after each trade
- ✅ **Partial fills**: Automatic handling when insufficient cash available

#### **Risk Management**:
- Pre-execution validation prevents cash flow failures
- Configurable cash reserves (default: $10 emergency fund)
- Multiple partial fill modes: AUTOMATIC, SMART, ASK, REJECT
- Real-time alerts for stop-losses and profit targets
- Portfolio concentration monitoring and rebalancing alerts

#### **Document Processing**:
- Auto-detects files using patterns: `trading_recommendation*.md/pdf`
- Parses both markdown and PDF formats
- Handles various Claude command formats automatically
- Extracts priority levels (HIGH/MEDIUM/LOW) automatically

### Making Portfolio Changes

The system now **automatically updates holdings** after trades! No manual changes needed.

**Previous workflow (manual)**:
```python
# OLD: Manual updates required
'SOUN': {'shares': 19, 'entry_price': 11.01, 'allocation': 209.19},  # DELETE this manually
'NVDA': {'shares': 15, 'entry_price': 180.50, 'allocation': 2707.50}, # ADD this manually
```

**Current workflow (automated)**:
```bash
# NEW: Completely automated
python Daily_Portfolio_Script.py  # Trades execute and holdings update automatically!
```

**What happens automatically:**
1. ✅ Trades execute based on Claude's recommendations
2. ✅ Holdings updated in memory during execution
3. ✅ Updated holdings saved to `portfolio_state.json`
4. ✅ Next script run loads current holdings automatically
5. ✅ No manual intervention required!

### Partial Fill Configuration

Configure how the system handles insufficient cash:

```python
# In your script or via configuration:
portfolio.set_partial_fill_mode(PartialFillMode.AUTOMATIC)  # Default: auto-fill max affordable
# portfolio.set_partial_fill_mode(PartialFillMode.SMART)    # Auto-fill if >80% affordable
# portfolio.set_partial_fill_mode(PartialFillMode.ASK)      # Ask for confirmation
# portfolio.set_partial_fill_mode(PartialFillMode.REJECT)   # Only complete orders
```

## Enhanced Historical Tracking

### **portfolio_historical_metrics.csv** - Comprehensive Data
The CSV now includes detailed position tracking:

**Portfolio-Level Metrics:**
- Account value, P&L, growth percentage
- Cash available, total positions, concentration risk
- Benchmark prices (SPY, IWM, VIX)

**Individual Position Details (per ticker):**
- Number of shares, entry price, current price
- Current value, P&L dollar, P&L percentage  
- Portfolio weight, weight drift

**Example CSV columns:**
```
date,account_value,total_pnl_percent,NVDA_shares,NVDA_current_price,NVDA_pnl_pct,NVDA_weight,...
```

## Weekly Procedures

#### Friday After Market Close
- **Performance Review**: Analyze weekly returns vs benchmarks using enhanced CSV data
- **Risk Assessment**: Review position concentration and correlation via weight tracking
- **Catalyst Calendar**: Update upcoming earnings/events for next week
- **Stop-Loss Review**: Adjust levels based on volatility changes from alerts

#### Weekend Planning
- **Research Updates**: Review analyst reports and news for holdings
- **Market Outlook**: Assess macro factors for coming week using benchmark data
- **Rebalancing Needs**: Plan any significant portfolio adjustments using drift analysis
- **Cash Management**: Optimize cash allocation for opportunities

### Monthly Procedures

#### Comprehensive Portfolio Review
- **Performance Analysis**: Calculate Sharpe ratio, maximum drawdown from historical CSV
- **Goal Assessment**: Progress toward December 27, 2025 target using growth tracking
- **Strategy Refinement**: Adjust approach based on market conditions and alerts
- **Risk Management Update**: Review and adjust all stop-loss levels

## Output Files Generated

1. **`portfolio_analysis_output.txt`**: Formatted for Claude AI analysis
2. **`portfolio_historical_metrics.csv`**: Enhanced daily performance tracking with position details
3. **`portfolio_state.json`**: Current portfolio holdings (auto-managed)
4. **`trade_execution.log`**: Complete audit trail of all trades
5. **`trade_execution_YYYYMMDD_HHMMSS.json`**: Detailed execution reports per session
6. **Performance charts**: Visual benchmark comparison (displayed and saved)
7. **Position detail charts**: Portfolio breakdown and performance analysis

## Troubleshooting

### Common Issues

**Data Fetch Errors:**
- Check internet connection and market hours
- Some tickers may be temporarily unavailable
- Script continues with last known prices

**VIX Data Issues:**
- Script attempts multiple VIX data sources
- Continues without VIX if unavailable
- Does not affect portfolio analysis

**Chart Display Problems:**
- Requires matplotlib backend
- May need X11 forwarding for remote systems
- Charts save to file if display unavailable

**Document Processing Issues:**
- Ensure file is named `trading_recommendation*` for auto-detection
- For PDF support, install: `pip install pdfplumber`
- Check that Claude's format includes clear BUY/SELL commands

**State Management Issues:**
- If holdings seem wrong, check `portfolio_state.json` for accuracy
- Delete `portfolio_state.json` to reset to default holdings
- Check `trade_execution.log` for trade history

### Performance Optimization

**Faster Data Retrieval:**
- Script caches recent data
- Parallel API calls for multiple tickers
- Graceful degradation on API limits

**Memory Management:**
- Historical CSV automatically manages size
- Old chart files can be safely deleted
- Price data refreshed daily
- State files remain small and efficient

## Competitive Edge

This automated system provides several advantages in the AI vs AI portfolio competition:

1. **Near-Instant Execution**: No manual trade entry delays after Claude's analysis
2. **Zero Manual Errors**: Automated validation prevents typos and calculation mistakes
3. **Optimal Cash Flow**: SELL→BUY prioritization prevents failed trades due to insufficient funds
4. **Complete Automation**: 95%+ automation requires only saving Claude's document
5. **Professional Risk Management**: Cash reserves, partial fills, and pre-validation
6. **Full Audit Trail**: Every trade logged for compliance and analysis
7. **Data-Driven Decisions**: Enhanced metrics provide deeper insights
8. **Systematic Execution**: Removes emotional bias from trade execution
9. **Benchmark Awareness**: Always aware of relative performance vs indices
10. **Catalyst Tracking**: Positioned for upcoming events and earnings through automated alerts

The combination of automated analysis, AI-powered decision making, and systematic execution creates a professional-grade portfolio management system optimized for maximum returns within the competition timeframe.

## Competition Timeline

- **Start Date**: August 5, 2025
- **End Date**: December 27, 2025  
- **Duration**: 144 calendar days / ~102 trading days
- **Goal**: Maximum absolute return vs competing AI strategist

**Current Status**: Fully automated system operational and ready for competition.

Success metrics: Total portfolio value on December 27, 2025. Winner takes all.

## System Status: PRODUCTION READY 🚀

Your enhanced portfolio management system now provides:
- **Professional-grade automation** (95%+ automated)
- **Institutional-quality risk management**
- **Complete audit trails and compliance**
- **Real-time performance tracking**
- **Multi-format document processing**
- **Sophisticated cash flow management**

**Ready to dominate the AI vs AI competition!**

## 🤖 Local LLM Runtime (Advanced)

### Overview
For advanced users seeking complete independence from external LLM services, the system now includes a **standalone local LLM runtime** that provides the same AI-powered trading recommendations using locally-hosted specialized financial models.

### Key Benefits
- 🔒 **Complete Privacy**: All analysis runs locally, no external API calls
- 🚀 **No Rate Limits**: Unlimited analysis without service restrictions  
- 💰 **Zero API Costs**: One-time setup, no ongoing service fees
- 🎯 **Financial Specialization**: Purpose-built models for trading analysis
- ⚡ **High Performance**: Optimized inference with GPU acceleration

### Quick Start
```bash
# Navigate to local LLM system
cd local_runtime

# View system capabilities and requirements
python local_start.py

# Test system components (CPU mode - no GPU required)
python main_local.py --test-components --force-cpu

# Generate trading analysis without executing trades
python main_local.py --analysis-only --force-cpu

# Full automated trading with local LLMs (requires GPU)
python main_local.py
```

### Architecture
The local runtime uses **4 specialized financial LLM models** in a sequential analysis pipeline:

1. **📰 News Analysis**: `AdaptLLM/Llama-3-FinMA-8B-Instruct`
   - Sentiment analysis, earnings surprises, FDA approvals
   - 8GB VRAM requirement

2. **📈 Market Analysis**: `Qwen/Qwen2.5-14B-Instruct`  
   - Technical patterns, support/resistance, momentum analysis
   - 20GB VRAM requirement

3. **💼 Trading Decision**: `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`
   - Core BUY/SELL/HOLD recommendations with position sizing
   - 20GB VRAM requirement

4. **🛡️ Risk Validation**: `microsoft/Phi-3-medium-4k-instruct`
   - Safety checks, compliance, position limits validation  
   - 8GB VRAM requirement

### System Requirements

#### **GPU Mode (Recommended)**
- **NVIDIA GPU**: 24GB+ VRAM (RTX 4090, A100, etc.)
- **System RAM**: 32GB+ recommended
- **Storage**: 100GB+ free space for models
- **Performance**: 3-7 minutes end-to-end execution

#### **CPU Mode (Fallback)**
- **Any Modern CPU**: 16+ cores recommended
- **System RAM**: 64GB+ recommended  
- **Performance**: 8-18 minutes end-to-end execution

### Installation
```bash
# Core dependencies
pip install vllm transformers torch accelerate

# Existing portfolio system dependencies (already installed)
pip install yfinance pandas numpy matplotlib pandas-market-calendars pytz

# CUDA support (for GPU acceleration)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Integration with Existing Workflow

The local LLM system **seamlessly integrates** with your existing portfolio management workflow:

#### **Option 1: Traditional Workflow (External Claude)**
```bash
# Step 1: Generate analysis
python "Portfolio Scripts Schwab/main.py" --report-only

# Step 2: Upload to Claude.ai → get recommendations → save as trading_recommendation.md

# Step 3: Execute trades  
python "Portfolio Scripts Schwab/main.py"
```

#### **Option 2: Local LLM Workflow (Fully Automated)**
```bash
# Single command - complete end-to-end automation
cd local_runtime && python main_local.py

# OR analysis-only mode for testing
cd local_runtime && python main_local.py --analysis-only
```

### Output Compatibility
The local LLM system generates **identical output formats**:
- Same `trading_recommendation_*.md` files
- Same `portfolio_state.json` updates  
- Same `trade_execution.log` entries
- Same performance charts and analysis

### Advanced Configuration

#### **Model Selection**
```bash
# Quick mode - trading + risk models only (faster)
python main_local.py --models trading_decision risk_validation

# Full pipeline - all 4 models (comprehensive analysis)
python main_local.py --full-pipeline
```

#### **Resource Management**
```bash
# Force CPU-only operation (no GPU required)
python main_local.py --force-cpu --analysis-only

# GPU mode with memory optimization
python main_local.py --models risk_validation trading_decision
```

### Safety & Risk Management

The local LLM system includes **multiple safety layers**:

- **Multi-Model Validation**: Each recommendation validated by specialized risk model
- **Hard-Coded Limits**: Position sizing (20% max), cash reserves (5% min)
- **Emergency Circuit Breakers**: Daily loss limits, volatility protection
- **Audit Trail**: Complete logging identical to main system

### Performance Comparison

| Feature | External Claude | Local LLM Runtime |
|---------|-----------------|-------------------|
| **Analysis Quality** | Excellent | Excellent (specialized models) |
| **Speed** | 2-5 minutes | 3-7 minutes (GPU) / 8-18 min (CPU) |
| **Cost** | API fees | Free after setup |
| **Privacy** | Data sent externally | 100% local processing |
| **Customization** | Limited | Full model control |
| **Availability** | Service dependent | Always available |

### When to Use Local LLM Runtime

**Ideal For:**
- High-frequency trading with multiple daily analyses
- Privacy-sensitive portfolio management  
- Users with capable GPU hardware (RTX 4090+)
- Complete automation without external dependencies
- Development and backtesting scenarios

**Stick with External Claude If:**
- Limited hardware resources
- Occasional trading (few times per week)
- Prefer proven external LLM quality
- Don't want to manage local infrastructure

### Documentation
- **Complete Setup Guide**: `local_runtime/README_LOCAL.md`
- **System Architecture**: `local_runtime/system_architecture`  
- **Installation Scripts**: `local_runtime/installation.sh`
- **Model Configurations**: `local_runtime/local_llm_server.py`

The local LLM runtime represents the **ultimate evolution** of the portfolio management system - complete AI-powered trading automation with zero external dependencies while maintaining full compatibility with the existing proven workflow.