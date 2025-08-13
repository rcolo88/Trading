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
```bash
python Daily_Portfolio_Script.py
```

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