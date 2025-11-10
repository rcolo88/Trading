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
- **AI-Optimized Output**: Formatted text file for AI agent analysis
- **Automated Trade Execution**: Full automation from document parsing to trade execution
- **Multi-Format Document Processing**: Supports both Markdown (.md) and PDF (.pdf) files
- **Sophisticated Cash Flow Management**: SELL→BUY prioritization with partial fill support
- **Professional Risk Management**: Pre-execution validation and cash reserve protection
- **Complete Audit Trail**: Comprehensive logging and state management

## Installation & Setup

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

#### Step 2: Generate AI Trading Recommendations

**Two Orchestration Systems Available:**

| Feature | DEFAULT Orchestrator | STEPS Orchestrator |
|---------|---------------------|-------------------|
| **Purpose** | Trade execution & reporting | Complete 10-step portfolio analysis |
| **Price Data Source** | ✅ Schwab API (real-time) | ✅ Schwab API (real-time) |
| **Fundamental Data** | N/A | yfinance (Schwab doesn't provide fundamentals) |
| **Market Hours Required** | Trading only | Analysis: 24/7, Trading: market hours |
| **Schwab Integration** | Full (account sync, live trading) | Price data + optional trading |
| **Speed** | Fast (<1 min) | Comprehensive (5-10 min) |
| **Best For** | Daily execution workflow | Weekly deep analysis |
| **Trading Recommendations** | Via manual_trades_override.json | Via trading_recommendations.md |
| **4-Tier Framework** | ✅ Fully integrated | ✅ Fully integrated |

**Option A: STEPS Orchestrator (RECOMMENDED - Complete 10-Step Analysis)**

**System**: Comprehensive STEPS Portfolio Analysis Framework

```bash
# Full 10-step STEPS analysis
cd "Portfolio Scripts Schwab"
python steps_orchestrator.py

# Quick analysis (skip optional steps)
python steps_orchestrator.py --skip-thematic --skip-competitive --skip-valuation

# Test run
python steps_orchestrator.py --dry-run
```

**What happens:**
1. **Market Environment** - Analyzes S&P 500, VIX, sector rotation (✅ Schwab API for real-time prices)
2. **Holdings Quality** - Calculates quality scores with 4-tier classification (yfinance for fundamentals)
3A. **Core Screening** - Identifies quality opportunities from S&P 500
3B. **Thematic Discovery** - Scores opportunistic investments
4. **Competitive Analysis** - Compares vs. direct competitors
5. **Valuation Analysis** - Assesses reasonable pricing
6. **Portfolio Construction** - Determines 4-tier allocation
7. **Rebalancing Trades** - Generates specific trade recommendations
8. **Trade Synthesis** - Integrates all analysis with tier-aware reasoning
9. **Data Validation** - Verifies data quality
10. **Framework Validation** - Ensures 4-tier compliance

**Data Source Strategy**:
- **Price Data**: ✅ Schwab API (real-time quotes for S&P 500, VIX, sector ETFs, holdings)
- **Fundamental Data**: yfinance (balance sheets, income statements - Schwab API doesn't provide)
- **Best of both worlds**: Real-time pricing accuracy + comprehensive fundamental data

**Option B: DEFAULT Orchestrator (Fast Trade Execution)**

**System**: Main portfolio management workflow with Schwab integration

```bash
# Generate portfolio report
cd "Portfolio Scripts Schwab"
python main.py --report-only

# Execute trades from manual_trades_override.json
python main.py
```

**What happens:**
- ✅ Uses Schwab API for real-time price data
- ✅ Full Schwab account integration (sync, live trading)
- ✅ Fast execution (<1 minute)
- ✅ Market hours validation
- ⚠️ No comprehensive 10-step analysis (requires STEPS)

**Data Source**: Uses SchwabDataFetcher for all price quotes, ensuring real-time accuracy for trading decisions.

**Option C: HuggingFace Multi-Agent Analysis Pipeline (Legacy)**

**Automated Agent Workflow**:
```bash
# Generate AI-powered trading recommendations
python "Portfolio Scripts Schwab/main.py" --generate-hf-recommendations
```

**What happens:**
- **News Agent** analyzes financial news sentiment for your holdings
- **Market Agent** assesses overall market outlook and momentum
- **Risk Agent** evaluates portfolio risk levels with conservative bias
- **Tone Agent** determines aggregate market environment sentiment
- **Quality Agent** scores fundamental quality metrics (drives 80% core allocation)
- **Thematic Prompt Builder** evaluates sector-specific themes (drives 20% opportunistic)
- **Catalyst Analyzer** identifies upcoming events affecting positions
- **Trade Agent** synthesizes all signals into concrete BUY/SELL/HOLD orders

**Output**: `trading_recommendations/trading_recommendations_YYYYMMDD.md`
- Prioritized orders (HIGH/MEDIUM/LOW priority)
- Detailed reasoning for each recommendation
- Risk management parameters (stop-loss, profit targets)
- AI analysis summary with confidence scores

#### Step 3: Review and Approve Recommendations
- Review the generated `trading_recommendations_YYYYMMDD.md` file
- Manually edit `Portfolio Scripts Schwab/manual_trades_override.json` with approved trades
- Set `"enabled": true` to authorize execution

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
- Handles various order formats automatically from AI agent output
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
1. ✅ Trades execute based on AI agent recommendations
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

1. **`portfolio_analysis_output.txt`**: Formatted for AI agent analysis (legacy)
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
- Check that AI agent output includes clear BUY/SELL commands

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

## 📊 Quality Metrics System

### Overview
An academically-validated system for identifying "quality compounders" - companies with durable competitive advantages that sustain high returns over time. Fully integrated with the HuggingFace agent framework for comprehensive fundamental analysis.

### Quick Start
```python
from agents import QualityAgent

# Analyze single stock
quality_agent = QualityAgent()
result = quality_agent.analyze(financial_data)

print(f"Quality Tier: {result.quality_analysis.tier.value}")
print(f"Investment Rating: {result.investment_rating}")  # STRONG BUY → STRONG SELL
print(f"Risk Level: {result.risk_level}")  # Low/Medium/High
```

### The Five Quality Metrics

| Metric | Formula | Weight | Elite Threshold |
|--------|---------|--------|-----------------|
| **Gross Profitability** | (Revenue - COGS) / Assets | 25% | ≥45% |
| **Return on Equity** | Net Income / Equity | 20% | ≥25% |
| **Operating Profitability** | (Revenue - COGS - SG&A) / Assets | 20% | ≥30% |
| **FCF Yield** | Free Cash Flow / Market Cap | 20% | ≥8% |
| **ROIC** | NOPAT / (Debt + Equity) | 15% | ≥20% |

### Quality Tiers & Classifications

**Point-in-Time Quality** (QualityMetricsCalculator):
- **Elite** (85-100): Exceptional quality, strong moats → Core holdings
- **Strong** (70-84): High quality, sustainable → Buy/Hold
- **Moderate** (50-69): Average quality → Selective
- **Weak** (0-49): Poor quality → Avoid/Sell

**Historical Persistence** (QualityPersistenceAnalyzer):
- **Quality Compounder**: Sustained excellence (10+ years ROE >15%)
- **Quality Improver**: Accelerating metrics, positive trends
- **Quality Deteriorator**: Declining performance, fading moat
- **Inconsistent**: Cyclical or volatile, no clear trend

### Key Features
- ✅ **Offline Operation**: No API calls, zero costs, no rate limits
- ✅ **Lightning Fast**: <10ms per stock, <100ms for 10-stock portfolio
- ✅ **HF Agent Compatible**: Works seamlessly with News/Market/Risk agents
- ✅ **Red Flag Detection**: 6 types (high accruals, leverage, margin deterioration)
- ✅ **Historical Analysis**: Track quality persistence over 3-10+ years
- ✅ **LLM Prompt Generation**: Optimized prompts (<600 tokens for 7B models)
- ✅ **Academic Validation**: Based on Novy-Marx, Piotroski, Sloan, et al.

### Integration Patterns

**Pattern 1: Quality-First Screening** (Reduce API costs by 50-80%)
```python
# Step 1: Quality filter (fast, offline)
quality_results = quality_agent.analyze_portfolio(holdings)
top_picks = quality_agent.get_top_quality_picks(quality_results, min_score=70)

# Step 2: HF sentiment analysis only on quality stocks
for ticker in top_picks:
    news_sentiment = news_agent.analyze(headlines)
    risk_assessment = risk_agent.analyze(context)
```

**Pattern 2: Comprehensive Multi-Agent Analysis**
```python
from example_quality_agent_integration import IntegratedAnalysisEngine

engine = IntegratedAnalysisEngine()
results = engine.analyze_stock_comprehensive(
    ticker='AAPL',
    financial_data=data,
    market_context="Strong Q4 earnings...",
    news_headlines=["Apple beats expectations", "iPhone sales strong"]
)

# Weighted synthesis: Quality 50%, Market 20%, Risk 15%, News 10%, Tone 5%
print(results['综合_assessment']['overall_recommendation'])
```

**Pattern 3: Compounder Identification**
```python
from quality_persistence_analyzer import QualityPersistenceAnalyzer

analyzer = QualityPersistenceAnalyzer()
result = analyzer.analyze_company(historical_data)

if result.classification.value == "Quality Compounder":
    print(f"✓ {result.ticker}: Durable compounder ({result.compounder_confidence:.0f}% confidence)")
    print(f"  Average ROE: {result.persistence_metrics.roe_mean:.1%} over {result.persistence_metrics.years_analyzed} years")
```

### Red Flags Detected

| Flag | Threshold | Severity | Implication |
|------|-----------|----------|-------------|
| **High Accruals** | >5% of assets | HIGH | Aggressive accounting, unsustainable earnings |
| **Excessive Asset Growth** | >20% YoY | MEDIUM | Overexpansion, integration risk |
| **Margin Deterioration** | >-3% YoY | HIGH | Competitive pressure, operational issues |
| **High Leverage** | D/E >2.0x | HIGH/MED | Financial risk, interest burden |
| **Negative FCF** | <$0 | HIGH | Cash burn, liquidity concerns |
| **Negative ROE** | <0% | HIGH | Value destruction |

### System Components

**Core Modules** (`Portfolio Scripts Schwab/`):
1. `quality_metrics_calculator.py` - 5 metrics, composite scoring (1,200 lines)
2. `quality_llm_prompts.py` - Prompt generation for 7B models (500 lines)
3. `agents/quality_agent.py` - HF agent integration (700 lines)
4. `quality_persistence_analyzer.py` - Historical analysis (1,000 lines)
5. `example_quality_integration.py` - yfinance integration
6. `example_quality_agent_integration.py` - Multi-agent synthesis

**Test Suites**:
```bash
# Test quality calculator (6/6 tests passing)
python "Portfolio Scripts Schwab/test_quality_metrics.py"

# Test quality agent
python "Portfolio Scripts Schwab/agents/quality_agent.py"

# Test persistence analyzer (6/7 tests passing)
python "Portfolio Scripts Schwab/test_quality_persistence.py"
```

### Academic Foundation
Based on peer-reviewed research:
- **Novy-Marx (2013)** - "The Other Side of Value" - Gross Profitability Premium
- **Piotroski (2000)** - "Value Investing" - F-Score methodology
- **Sloan (1996)** - "Do Stock Prices Fully Reflect..." - Accruals analysis
- **Cooper et al. (2008)** - "Asset Growth and Cross-Section of Returns"
- **Ball et al. (2015)** - "Deflating Profitability" - Operating profitability

### Performance Stats
- **Speed**: Single stock <10ms, Portfolio (10 stocks) <100ms
- **Memory**: ~5MB for quality agent, <1KB per analysis
- **Scalability**: 100+ stocks per second
- **Cost**: $0 (offline calculation)
- **Test Status**: ✅ 12/13 tests passing

## 🔌 Schwab API Integration

### Overview
The system provides full integration with Schwab's brokerage API for real-time trading, account synchronization, and market data. This enables live trade execution and automatic portfolio reconciliation with your actual Schwab account.

### Core Features

**Account Data Synchronization:**
- Pull real positions directly from Schwab account
- Automatic reconciliation between local state and actual holdings
- Cash balance sync for accurate fund tracking
- Transaction history retrieval for auditing

**Live Trade Execution:**
- Real order placement through Schwab API (market and limit orders)
- Dry-run mode for safe testing without real trades
- Order status tracking and confirmation
- Automatic position reconciliation after execution

**Safety & Risk Management:**
- Pre-trade validation for buying power, position limits, cash reserves
- Batch order validation for cash flow feasibility
- Risk metrics including position concentration and diversification
- Daily trade limits to prevent over-trading

### Key Modules

**schwab_account_manager.py** - Account data synchronization with Schwab, discovers linked accounts, fetches real-time positions and balances, syncs data to local portfolio state, generates comprehensive account summaries, retrieves transaction history.

**schwab_trade_executor.py** - Live trade execution through Schwab API, places market and limit orders, tracks order status and confirmation, supports dry-run mode for testing, generates execution summaries, performs automatic reconciliation after trades.

**schwab_safety_validator.py** - Pre-trade validation and risk management, validates orders pre-execution, analyzes batch order cash flow, checks position size and concentration, enforces cash reserve requirements, monitors daily trade limits, generates portfolio risk summaries.

### Trading Workflows

**Daily Portfolio Sync:**
1. Sync account data with Schwab
2. Review account status
3. Check risk metrics
4. Generate analysis report

**Testing New Strategy:**
1. Test document parsing
2. Dry-run with real account data
3. Review simulated results
4. Execute live if satisfied

**Safe Live Trading:**
1. Sync account with Schwab
2. Test in dry-run mode
3. Execute live trades
4. Verify reconciliation

### Configuration Requirements

**Prerequisites:**
- Schwab Developer Account at developer.schwab.com
- API credentials (key and app secret)
- Callback URL configured as https://127.0.0.1:8182
- schwab-py library installed

**Credentials File:** Create schwab_credentials.json in Portfolio Scripts Schwab/ directory with API key, app secret, callback URL, and token path. Never commit this file to version control.

### Safety Features

**Multiple Protection Layers:**
- Explicit live trading flag required for real orders
- Dry-run default (system defaults to simulation unless explicitly live)
- Pre-trade validation before execution
- Position limits enforced (30% max per position)
- Cash reserves maintained (5% minimum)
- Daily trade limits (50 max trades per day)
- Duplicate detection prevents accidental re-execution

**Configurable Safety Limits:**
- Max position size: 30% of portfolio
- Max daily trades: 50 trades
- Min cash reserve: 5% of portfolio value
- Max position value: $50,000 per position

**Order Priority System:** Orders execute in cash-flow-optimized sequence: high priority sells (generate cash first), position reductions, medium priority sells, high priority buys (with available cash), low priority sells, medium priority buys, low priority buys.

### Command Reference

**Read-Only Commands** (no trading): report generation, account status viewing, risk analysis, API connection testing, document parsing tests.

**Account Synchronization:** sync portfolio with Schwab account, load previous day positions for recovery.

**Trading Commands:** dry-run mode (simulated trades), live trading mode (REAL trades requiring explicit flag), full execution mode (default behavior).

### Market Hours Policy

**Trading Operations** (require market hours Mon-Fri 9:30AM-4PM ET): live trading execution, Schwab account synchronization.

**Read-Only Operations** (available 24/7): account status display, risk summaries, report generation, API testing, dry-run simulations.

### Troubleshooting

**Common Issues:**
- "No account hash available" - Run account sync to discover accounts, ensure credentials are configured
- "Schwab API client not available" - Check credentials file exists with valid keys, verify callback URL matches exactly
- "Order rejected: HTTP 401" - API token may have expired (delete and re-authenticate), verify credentials are correct
- "Account manager not initialized" - Ensure using dry-run or live-trading flag to enable account manager
- Trades not executing - Verify market is open, check trade execution log for errors, ensure sufficient buying power, verify orders pass validation

**Logging:** All trade activity logged to trade_execution.log including order placement attempts, execution results, error messages, and reconciliation status.

**Important Warnings:**
- Live trading places REAL orders with REAL money - always test with dry-run first
- Market hours restrictions apply for live trading
- Schwab API has rate limits (120 orders/minute) that system respects
- Always verify positions after live trades
- Never commit credentials to version control

## 🤖 HuggingFace Agent System

### Overview
An AI-powered trading recommendation system using HuggingFace Inference API to analyze portfolio data and generate trading recommendations. The system uses specialized FinBERT models for financial sentiment analysis and produces human-readable documents following structured formats for manual review and approval before execution.

### Complete Agent Workflow & Data Flow

The HuggingFace agent system implements a **multi-agent architecture** that combines cloud-based sentiment analysis with offline fundamental analysis to drive the 80/20 portfolio framework.

#### **INPUT STAGE**

**1. Portfolio State** (`portfolio_state.json`)
- Current holdings with ticker symbols, share counts, entry prices
- Cash balance available for new positions
- Last update timestamp for tracking changes
- Loaded automatically on script startup

**2. Daily Portfolio Analysis** (`daily_portfolio_analysis.md`)
- Generated by: `python "Portfolio Scripts Schwab/main.py" --report-only`
- Contains: Portfolio weights, P&L, risk alerts, benchmark comparison, news items
- Used as primary context document for all agent analysis
- Available 24/7 (no market hours required)

#### **AGENT ANALYSIS STAGE**

**HuggingFace API Agents** (Cloud-based sentiment analysis):

**3. News Agent**
- Model: `mrm8488/distilroberta-finetuned-financial-news-sentiment`
- Input: News items extracted from daily_portfolio_analysis.md
- Processing: Analyzes each news item for sentiment (positive/negative/neutral)
- Output: Overall sentiment, confidence score (0.0-1.0), mentioned tickers list
- Purpose: Identify earnings surprises, FDA approvals, market-moving events
- Performance: 2-5 seconds per analysis, cached for 5 minutes

**4. Market Agent**
- Model: `StephanAkkerman/FinTwitBERT`
- Input: Market context and portfolio summary from daily analysis
- Processing: Evaluates overall market direction and strength
- Output: Market outlook (Bullish/Bearish/Neutral), strength level, confidence score
- Purpose: Assess macro environment and market momentum
- Performance: 2-5 seconds per analysis

**5. Risk Agent**
- Model: `ProsusAI/finbert`
- Input: Portfolio summary, positions, and market context
- Processing: Conservative risk assessment with safety bias
- Output: Risk level (high/medium/low), list of concerns, recommended actions
- Purpose: Identify portfolio vulnerabilities and risk factors
- Performance: 2-5 seconds per analysis
- Note: Defaults to higher risk when uncertain (conservative bias)

**6. Tone Agent**
- Model: `yiyanghkust/finbert-tone`
- Input: Combined summary from News + Market + Risk agents
- Processing: Aggregate sentiment analysis
- Output: Overall tone (positive/negative/neutral), confidence score
- Purpose: Determine overall market environment sentiment
- Performance: 2-5 seconds per analysis

**Offline Agents** (Local calculation, no API calls):

**7. Quality Agent** (**DRIVES 80% CORE ALLOCATION**)
- Module: `quality_metrics_calculator.py`
- Input: Financial data for each holding (revenue, COGS, assets, equity, etc.)
- Processing: Calculates 5 academically-validated quality metrics
- Metrics Calculated:
  - Gross Profitability = (Revenue - COGS) / Assets (weight: 25%)
  - ROE = Net Income / Equity (weight: 20%)
  - Operating Profitability = (Revenue - COGS - SG&A) / Assets (weight: 20%)
  - FCF Yield = Free Cash Flow / Market Cap (weight: 20%)
  - ROIC = NOPAT / (Debt + Equity) (weight: 15%)
- Output: Composite quality score (0-100), tier classification (Elite/Strong/Moderate/Weak), red flags
- Purpose: Identify high-quality compounders for core portfolio (80% allocation)
- Performance: <10ms per stock, <100ms for 10-stock portfolio
- Cost: $0 (offline calculation)

**8. Thematic Prompt Builder** (**DRIVES 20% OPPORTUNISTIC ALLOCATION**)
- Module: `thematic_prompt_builder.py`
- Input: Company data, selected theme, market context
- Processing: Evaluates company on 5 theme-specific dimensions (1-10 scale each)
- Supported Themes:
  - AI Infrastructure (value chain, tech differentiation, traction, moat, unit economics)
  - Nuclear Renaissance (tech readiness, regulatory, partnerships, gov support, timeline)
  - Defense Modernization (program stability, tech superiority, growth runway, financials, geopolitics)
  - Climate Technology (tech maturity, unit economics, policy support, demand, carbon impact)
  - Longevity/Biotech (science quality, clinical progress, commercial potential, IP, management)
- Output: Thematic score (0-50), classification (Leader/Contender/Laggard), investment stance (BUY/HOLD/AVOID)
- Purpose: Evaluate growth opportunities for opportunistic portfolio (20% allocation)
- Performance: <1ms prompt generation
- Cost: $0 (offline prompt building, requires LLM for analysis)

**9. Catalyst Analyzer** (**OPTIMIZES ENTRY/EXIT TIMING**)
- Module: `catalyst_analyzer.py`
- Input: Company data, upcoming events/catalysts
- Processing: Prioritizes catalysts by formula = time/(months) + probability + impact + direction_bonus
- Catalyst Types: Earnings, FDA approvals, product launches, contract awards, regulatory decisions
- Timeline Buckets: Near-term (0-6mo), Medium-term (6-18mo), Long-term (18mo+)
- Output: Prioritized catalyst list with dates, probability (H/M/L), impact (H/M/L), direction (+/-/neutral)
- Purpose: Time entries/exits around specific events rather than passive buy-and-hold
- Performance: <5ms per company
- Cost: $0 (offline calculation)

**10. Trade Agent** (Pure logic synthesis)
- Module: `agents/trade_agent.py`
- Input: All agent outputs (News, Market, Risk, Quality, Thematic)
- Processing: Applies trading rules to synthesize signals
- Trading Rules:
  - Profit taking: If position return >= 15%, generate SELL (HIGH priority)
  - Stop loss: If position return <= -8%, generate SELL (HIGH priority)
  - Risk-based selling: If market Bearish AND risk high, generate SELL
  - Buy signals: If news positive AND market Bullish AND risk not high, generate BUY
- Position Sizing:
  - Maximum 20% per position (hard limit)
  - Strong signals = 10% allocation, Moderate = 5%, Weak = 3%
- Output: Concrete BUY/SELL/HOLD orders with share quantities, priority levels, reasoning
- Purpose: Synthesize all agent signals into executable trade orders
- Performance: <1ms synthesis
- Cost: $0 (pure logic, no API calls)

#### **OUTPUT STAGE**

**11. Trading Recommendations Document**
- File: `trading_recommendations/trading_recommendations_YYYYMMDD.md`
- Generated by: `python "Portfolio Scripts Schwab/main.py" --generate-hf-recommendations`
- Contains:
  - AI analysis summary (News/Market/Risk/Tone sentiment with confidence scores)
  - Prioritized orders (HIGH/MEDIUM/LOW priority sections)
  - Detailed reasoning for each recommendation
  - Risk management parameters (stop-loss levels, profit targets)
  - Market conditions and portfolio performance context
- Format: Markdown document matching trading_template.md structure
- Available: 24/7 (no market hours required)

**12. Manual Approval Gateway**
- File: `Portfolio Scripts Schwab/manual_trades_override.json`
- Process:
  1. Human reviews `trading_recommendations_YYYYMMDD.md`
  2. Manually edits JSON file with approved trades
  3. Sets `"enabled": true` to authorize execution
- JSON Structure:
  ```json
  {
    "enabled": true,
    "trades": [
      {
        "action": "BUY",
        "ticker": "NVDA",
        "shares": 5,
        "reason": "AI infrastructure - approved from HF recommendation",
        "priority": "HIGH"
      }
    ]
  }
  ```
- Safety: AI never executes trades directly - all trades require explicit human approval

**13. Trade Execution & Portfolio Updates**
- Executed by: `python "Portfolio Scripts Schwab/main.py"`
- Updates:
  - `portfolio_state.json` - Current holdings and cash balance
  - `trade_execution.log` - Complete audit trail
  - `portfolio_performance_history.csv` - Historical tracking
- Reconciliation: Schwab API sync for live trading (if enabled)
- Available: Market hours only (Mon-Fri 9:30AM-4PM ET)

### 80/20 Portfolio Framework Integration

The agent system directly implements the **80% Quality Core / 20% Opportunistic** portfolio allocation strategy through specialized agents.

#### **80% CORE ALLOCATION - Quality-Driven (Quality Agent)**

**Screening Methodology:**
- Agent: Quality Agent (offline, $0 cost, <10ms per stock)
- Module: `quality_metrics_calculator.py`
- Approach: Calculate composite quality score from 5 weighted metrics

**Quality Metrics & Scoring:**

| Metric | Formula | Weight | Elite Threshold | Purpose |
|--------|---------|--------|-----------------|---------|
| **Gross Profitability** | (Revenue - COGS) / Assets | 25% | ≥45% | Revenue efficiency |
| **Return on Equity** | Net Income / Equity | 20% | ≥25% | Capital efficiency |
| **Operating Profitability** | (Revenue - COGS - SG&A) / Assets | 20% | ≥30% | Operational excellence |
| **FCF Yield** | Free Cash Flow / Market Cap | 20% | ≥8% | Cash generation |
| **ROIC** | NOPAT / (Debt + Equity) | 15% | ≥20% | Invested capital returns |

**Quality Score Thresholds & Position Sizing (STEPS Framework):**

| Tier | Score Range (0-100) | Score Range (0-10) | Position Size | Stop-Loss | Profit Target |
|------|---------------------|--------------------|--------------|-----------|--------------|
| **Elite** | 90-100 | 9.0-10.0 | 10-20% | -15% | +40% |
| **Strong** | 80-89 | 8.0-8.9 | 7-12% | -15% | +40% |
| **Moderate** | 70-79 | 7.0-7.9 | 5-8% | -20% | +40% |
| **Below Threshold** | 0-69 | <7.0 | **EXIT** | N/A | N/A |

**Investment Rules for Core (80%):**
- ✅ **DO**: Buy companies with quality score ≥ 70 (7.0 on 10-point scale)
- ✅ **DO**: Size positions based on quality score (higher quality = larger position)
- ✅ **DO**: Hold through normal market volatility (long-term compounders)
- ✅ **DO**: Require positive free cash flow and ROE > 15% for 3+ years
- ❌ **DON'T**: Exceed 20% in any single core position
- ❌ **DON'T**: Exit unless quality score drops below 70 (STEPS threshold)
- ❌ **DON'T**: Prioritize cheap valuations over quality (avoid value traps)

**Red Flag Detection:**
- High accruals (>5% of assets) - aggressive accounting
- Excessive asset growth (>20% YoY) - overexpansion risk
- Margin deterioration (>-3% YoY) - competitive pressure
- High leverage (D/E >2.0x) - financial risk
- Negative FCF or ROE - value destruction

**Core Holdings Philosophy:**
- "Sleep well at night" positions backed by academic research (Novy-Marx, Piotroski, Sloan)
- Target 7-12 total core positions for appropriate diversification
- Average quality score target: >8.0 across all core holdings
- Low portfolio turnover (<25% annually)

#### **20% OPPORTUNISTIC ALLOCATION - Thematic-Driven (Thematic Prompt Builder + Catalyst Analyzer)**

**Screening Methodology:**
- Agent: Thematic Prompt Builder (offline, $0 cost, <1ms prompt generation)
- Module: `thematic_prompt_builder.py`
- Approach: Score companies on 5 theme-specific dimensions (1-10 scale each)

**Theme Selection Process:**
1. **Identify 2-3 mega-trends** with clear 12-18 month catalysts
2. **Evaluate themes** on catalyst strength, timeline alignment, market size
3. **Select themes** with government backing or corporate necessity
4. **Find companies** that are pure-plays or picks-and-shovels providers

**Supported Thematic Sectors:**

| Theme | Key Dimensions | Catalyst Examples |
|-------|----------------|-------------------|
| **AI Infrastructure** | Value chain, tech differentiation, traction, moat, unit economics | Data center build-out, GPU demand, power/cooling needs |
| **Nuclear Renaissance** | Tech readiness, regulatory progress, partnerships, gov support, timeline | SMR approvals, uranium supply shortage, climate policy |
| **Defense Modernization** | Program stability, tech superiority, growth runway, financials, geopolitics | Defense budget increases, drone warfare, hypersonics |
| **Climate Technology** | Tech maturity, unit economics, policy support, demand, carbon impact | IRA subsidies, carbon credits, grid modernization |
| **Longevity/Biotech** | Science quality, clinical progress, commercial potential, IP, management | FDA approvals, GLP-1 adoption, clinical trial results |

**Thematic Score Thresholds & Position Sizing (STEPS Framework):**

| Classification | Score Range (0-40) | Position Size | Stop-Loss | Profit Target |
|----------------|-------------------|---------------|-----------|---------------|
| **Leader** | 35-40 | 5-7% | -27.5% | +50% |
| **Strong Contender** | 30-34 | 3-5% | -27.5% | +50% |
| **Contender** | 28-29 | 2-3% | -25% | +45% |
| **Below Threshold** | 0-27 | **EXIT** | N/A | N/A |

**Catalyst Integration for Timing:**
- Use Catalyst Analyzer to identify near-term (0-6mo) positive catalysts
- Enter positions 2-4 months before high-probability catalyst
- Scale into positions as catalyst date approaches
- Exit within days/weeks after catalyst if price target hit
- Avoid entering <2 weeks before catalyst (premium priced in)

**Investment Rules for Opportunistic (20%):**
- ✅ **DO**: Score minimum 28/40 on thematic dimensions (STEPS threshold)
- ✅ **DO**: Position 2-4 months before high-probability positive catalysts
- ✅ **DO**: Set tighter stop-losses (-25% to -30%) due to higher volatility
- ✅ **DO**: Take profits aggressively (+40-60% gains)
- ✅ **DO**: Accept negative FCF IF runway >12mo AND revenue growing >50%
- ❌ **DON'T**: Exceed 7% in any single opportunistic position
- ❌ **DON'T**: Exceed 20% total allocation to opportunistic holdings
- ❌ **DON'T**: Hold through stop-loss levels (cut losers quickly)
- ❌ **DON'T**: Average down on thesis breaks (acknowledge mistakes)

**Opportunistic Holdings Philosophy:**
- Event-driven momentum plays with clear catalysts
- Higher risk, higher reward compared to core (2-3x return potential)
- Maximum 20% total allocation (can be 15-18% if limited opportunities)
- Think in quarters (not years) - exit after catalyst or thesis break

#### **Portfolio Construction Rules (Universal)**

**Allocation Discipline:**
- **ALWAYS** maintain 80/20 split between quality core and thematic opportunistic
- **NEVER** violate framework discipline regardless of market conditions
- **ALWAYS** have 5-10% cash reserve for new opportunities

**Position Sizing Validation:**
- Core positions: Quality Score drives size (7-20% range)
- Opportunistic positions: Thematic Score drives size (2-7% range)
- Total portfolio: 80% in quality positions + 20% in thematic + 5-10% cash

**Rebalancing Triggers:**
- Quality score drops below 7 → Exit from core allocation
- Thematic score drops below 28 → Exit from opportunistic
- Position grows >20% of portfolio → Trim to target weight
- Weekly score recalculation identifies drift from targets

#### **Agent Workflow Execution Commands**

**Complete Daily Workflow:**
```bash
# Step 1: Generate portfolio analysis (available 24/7)
python "Portfolio Scripts Schwab/main.py" --report-only

# Step 2: Generate AI recommendations (available 24/7)
python "Portfolio Scripts Schwab/main.py" --generate-hf-recommendations

# Step 3: Review recommendations
# File: trading_recommendations/trading_recommendations_YYYYMMDD.md
# Contains: Quality scores for core, thematic scores for opportunistic

# Step 4: Approve trades manually
# Edit: Portfolio Scripts Schwab/manual_trades_override.json
# Set: "enabled": true

# Step 5: Execute approved trades (market hours only)
python "Portfolio Scripts Schwab/main.py"
```

**Read-Only Operations (Available 24/7):**
- `--report-only` - Generate daily_portfolio_analysis.md
- `--generate-hf-recommendations` - Run all agents and generate trading document
- `--account-status` - Check Schwab account status
- `--risk-summary` - Portfolio risk analysis
- `--dry-run` - Simulate trades without execution

**Trading Operations (Market Hours Required Mon-Fri 9:30AM-4PM ET):**
- Default execution - Execute trades from manual_trades_override.json
- `--live-trading` - Execute real trades via Schwab API
- `--sync-schwab-account` - Sync portfolio with Schwab account

#### **Data Flow Diagram**

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT STAGE                                                     │
├─────────────────────────────────────────────────────────────────┤
│ portfolio_state.json → daily_portfolio_analysis.md (--report-only)│
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ AGENT ANALYSIS STAGE (--generate-hf-recommendations)            │
├─────────────────────────────────────────────────────────────────┤
│ ┌─ HuggingFace API Agents (Cloud) ────────────────────────┐    │
│ │ News Agent → Market Agent → Risk Agent → Tone Agent     │    │
│ │ (10-20 seconds total, cached 5min)                      │    │
│ └──────────────────────────────────────────────────────────┘    │
│                             ↓                                   │
│ ┌─ Offline Agents (Local, Instant) ───────────────────────┐    │
│ │ Quality Agent ──→ 80% CORE ALLOCATION                   │    │
│ │   ├─ Gross Profitability, ROE, Op Profit, FCF, ROIC    │    │
│ │   ├─ Score 0-100, Tier Elite/Strong/Moderate/Weak      │    │
│ │   └─ Position sizing: 5-20% based on quality score     │    │
│ │                                                          │    │
│ │ Thematic Prompt Builder ──→ 20% OPPORTUNISTIC ALLOCATION│    │
│ │   ├─ AI Infra, Nuclear, Defense, Climate, Longevity    │    │
│ │   ├─ Score 0-50, Leader/Contender/Laggard             │    │
│ │   └─ Position sizing: 2-7% based on thematic score     │    │
│ │                                                          │    │
│ │ Catalyst Analyzer ──→ ENTRY/EXIT TIMING                 │    │
│ │   ├─ Near-term (0-6mo), Medium (6-18mo), Long (18mo+) │    │
│ │   └─ Priority scoring for optimal timing               │    │
│ │                                                          │    │
│ │ Trade Agent ──→ SYNTHESIS                               │    │
│ │   └─ Combine all signals → BUY/SELL/HOLD orders        │    │
│ └──────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ OUTPUT STAGE                                                    │
├─────────────────────────────────────────────────────────────────┤
│ trading_recommendations_YYYYMMDD.md                            │
│   ├─ Quality scores (80% core candidates)                     │
│   ├─ Thematic scores (20% opportunistic candidates)           │
│   ├─ Catalyst timeline (entry/exit timing)                    │
│   └─ Prioritized orders (HIGH/MEDIUM/LOW)                     │
│                             ↓                                   │
│ HUMAN REVIEW & APPROVAL                                         │
│   └─ manual_trades_override.json ("enabled": true)            │
│                             ↓                                   │
│ TRADE EXECUTION (market hours only)                            │
│   └─ portfolio_state.json + trade_execution.log updated       │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture Philosophy
The HF agent system provides **AI analysis with human control** - recommendations are generated by AI but all trades require explicit manual approval. This ensures complete separation between AI recommendations and trading decisions.

### Specialized Models Used

**News Agent** - mrm8488/distilroberta-finetuned-financial-news-sentiment - Analyzes financial news sentiment with automatic ticker extraction, identifies earnings surprises and market-moving events, processes portfolio documents with intelligent text parsing.

**Market Agent** - StephanAkkerman/FinTwitBERT - Analyzes market commentary and social sentiment, evaluates overall market tone and direction, identifies bullish/bearish sentiment shifts.

**Risk Agent** - ProsusAI/finbert - Assesses risk factors and financial health with conservative bias, evaluates portfolio risk levels, identifies warning signs and concerns, defaults to higher risk when uncertain for safety.

**Tone Agent** - yiyanghkust/finbert-tone - Determines overall market tone (positive/negative/neutral), provides market environment context, weighs in on trading climate.

**Quality Agent** - Offline calculation, no API calls - Analyzes fundamental quality metrics, identifies quality compounders, detects red flags in financials, provides investment ratings.

**Trade Agent** - Pure logic synthesis, no API calls - Synthesizes all agent outputs into concrete trade orders, applies trading rules (profit taking, stop loss), enforces position limits and risk management, generates prioritized order lists.

### Workflow Features

**AI Analysis → Human Review → Manual Execution:**
Complete separation ensures humans retain control. AI never executes trades directly. All trades require manual approval via manual_trades_override.json. Template-based output matches trading_template.md format for consistency.

**24/7 Availability:** Recommendation generation works anytime (no market hours required). Account status and risk analysis available outside market hours. Only actual trading requires market open hours.

**Smart Retry Logic:** Handles HuggingFace API rate limits (503, 429) automatically with exponential backoff for network errors. Respects Retry-After headers for rate limiting. Special 20-30 second wait for model loading (cold start). Up to 3 retry attempts with intelligent delays.

**In-Memory Caching:** 5-minute TTL reduces redundant API calls. LRU eviction for cache management (max 100 entries). Shared cache across all agents. Automatic cleanup of expired entries. Cache keys based on model ID + input text hash.

### System Operation

**Consensus Building:** System aggregates results using weighted voting with configurable weights per agent: NewsAgent 25%, MarketAgent 30%, RiskAgent 30%, ToneAgent 15%. Weighted voting based on confidence scores. Risk override prevents risky trades even with positive sentiment. BUY/SELL/HOLD recommendation with confidence scores and reasoning.

**Manual Override Priority:** manual_trades_override.json always takes precedence over document parsing. Set "enabled": true to bypass AI recommendations entirely. Structured JSON format for manual trade entry. Priority-based execution (HIGH → MEDIUM → LOW). Maintains safety validations and market hours enforcement.

**Enhanced Natural Language Parser:** Supports multiple order formats: "SELL 10 shares of QS", "BUY 1 share of XLV", "HOLD all 2 shares of NVDA", "REDUCE CYTK by 50%". Five different regex patterns for flexibility. Fallback maintains backward compatibility. Extracts priority levels automatically (HIGH/MEDIUM/LOW).

### Configuration & Customization

**Trading Parameters** (configurable in hf_config.py):
- Max position size: 20% (adjustable)
- Min cash reserve: $100 (configurable)
- Confidence threshold: 65% (tunable)

**Retry Configuration:**
- Max retries: 3 attempts
- Exponential base: 2.0x multiplier
- Base delay: 1.0 seconds
- Max delay: 60 seconds

**Agent Weights** (customizable for different strategies):
- Adjust weights to emphasize specific agents
- Must sum to 1.0 for proper weighting
- Higher weight = more influence on final decision
- Risk agent weight often kept high for safety

### API Rate Limits & Performance

**HuggingFace Inference API Limits:**
- Free tier: ~30 requests/hour per model without token
- With token: Higher limits
- Caching significantly reduces API calls
- First call may take 30-60s (model loading)

**Performance Characteristics:**
- Cache hit: <0.01 seconds (instant)
- Cache miss: 2-5 seconds (API latency)
- 503 errors: Additional 20-30 seconds per retry
- 429 errors: Additional 60+ seconds per retry
- Memory usage: ~1-2KB per cached entry
- Max memory: ~100-200KB for full cache

### Integration Patterns

**Quality-First Filter** - Reduce HF API calls by 50-80% by screening with offline Quality Agent first, then running expensive HF sentiment analysis only on quality stocks. Focus API calls on companies that pass fundamental screening.

**Multi-Agent Synthesis** - Comprehensive stock evaluation combining quality fundamentals, news sentiment, market sentiment, and risk assessment. Weighted synthesis produces final recommendation with confidence scores.

**Portfolio Quality Report** - Daily monitoring with automated quality assessment, actionable insights for top picks and concerns, tracks quality score changes over time.

### Output Format

**ConsensusResult Structure:** Overall sentiment (positive/negative/neutral), confidence score (0.0 to 1.0), recommendation (BUY/SELL/HOLD), detailed reasoning summary, individual agent results with timestamps and models used, generation timestamp.

**Trade Order Format:** Ticker symbol, action (BUY/SELL/REDUCE/HOLD), share quantities or target values, detailed reasoning, priority level (HIGH/MEDIUM/LOW), optional limit prices, stop loss levels (-8% default), profit targets (+15% default).

### Safety Features

**Conservative Risk Bias:** Risk agent defaults to higher risk assessment when uncertain for safety. High risk signals (>75% confidence) can override positive sentiment. Multiple validation layers before any execution.

**Manual Review Required:** No trades execute without explicit human approval. Priority-based execution order. Position limits enforced (20% max). Stop loss and profit targets included. Cash reserve management (5% minimum maintained).

**Portfolio Analysis Integration:** Reads from daily_portfolio_analysis.md (generated by --report-only). Outputs to trading_recommendations/trading_recommendations_YYYYMMDD.md. Executes via manual_trades_override.json mechanism. Uses existing trade_executor.py for order execution. Maintains all safety validations and market hours enforcement.

### Dependencies

**HuggingFace Dependencies:** requests >= 2.31.0 for API communication, transformers >= 4.30.0 for model configurations and utilities.

**Existing System Dependencies:** yfinance, pandas, numpy, matplotlib, pandas-market-calendars, pytz (already installed for portfolio system).

### Troubleshooting

**Models Loading Slowly:** First API call may take 30-60 seconds as HuggingFace loads model into memory. Subsequent calls are faster due to model remaining loaded.

**Rate Limit Errors:** Reduce analysis frequency, add HuggingFace token for higher limits, increase retry delays in configuration.

**Import Errors:** Ensure correct directory and conda environment activated. Test imports to verify agent availability.

**Connection Errors:** Check internet connection, verify HuggingFace API status, ensure no firewall blocking.

## 🔐 Security & Credentials Management

### Protected Files
The following files contain sensitive information and are protected by .gitignore to never commit to version control:

**Critical Credential Files:** schwab_credentials.json (API key and app secret), schwab_token.json (OAuth access/refresh tokens), all *_credentials.json files, all *_token.json and *.token files.

**Logs & Temporary Data:** trade_execution.log (contains trade details), all *.log files, all *.tmp temporary files.

**Configuration Files:** .env (environment variables), local_config.json (local settings).

### Security Checklist

**Before First Commit:**
- Verify .gitignore exists in both root and Portfolio Scripts Schwab/
- Confirm schwab_credentials.json is listed in .gitignore
- Never create credentials with different names (use template provided)
- Run git status to verify no credential files are staged

**Credential Management:**
- Use only schwab_credentials.json for credentials (never rename)
- Keep schwab_credentials_template.json (safe to commit - no real credentials)
- Store backup credentials securely (password manager, encrypted drive)
- Rotate API keys periodically

**Regular Security Checks:** Use git ls-files to check if sensitive files are tracked. Command should return NOTHING for credentials, tokens, or logs. If files appear, remove from git cache immediately.

### Safe Files to Commit

**Template Files** (safe - no real credentials): schwab_credentials_template.json with placeholder values, all README and documentation files, all Python source code modules.

**Portfolio State Files:** portfolio_state.json may contain your positions (add to .gitignore if you want privacy), portfolio_performance_history.csv (historical data), daily_portfolio_analysis.md (analysis output). Consider adding these to .gitignore if you don't want to share positions/balances publicly.

### API Security Best Practices

**Schwab Developer Account:**
- Use dedicated Schwab developer account (not main trading account)
- Set appropriate API permissions (read-only for testing)
- Monitor API usage in developer portal

**Callback URL Security:**
- Use https://127.0.0.1:8182 (localhost only)
- Never expose callback endpoint to public internet
- Verify URL matches exactly in Schwab developer portal

**Token Management:**
- Access tokens expire after 30 minutes
- Refresh tokens valid for 7 days
- System handles automatic refresh
- Delete schwab_token.json to force re-authentication

**API Rate Limits:**
- Respect Schwab's limits (120 orders/minute)
- System includes automatic rate limiting
- Monitor usage to avoid temporary bans

### Credential Exposure Response

**Immediate Actions if Credentials Exposed:**
1. Revoke API keys at developer.schwab.com immediately
2. Delete compromised application
3. Create new application with fresh credentials
4. Remove file from git history using git filter-branch (use with caution)
5. Contact Schwab support at traderapi@schwab.com

**Prevention for Future:**
- Enable git pre-commit hooks to prevent credential commits
- Use secret scanning tools (git-secrets, trufflehog)
- Regular security audits of committed files

### File Permission Recommendations

Set restrictive permissions on sensitive files: Make credentials readable only by you (chmod 600), make scripts executable (chmod +x for Python files).

### Security Audit Commands

**Check for Exposed Credentials:** Search for potential API keys in codebase (excluding git and markdown), search for tokens, list all JSON files for review.

**Verify .gitignore is Working:** Create test credentials file, check git status (should NOT show the file), clean up test file.

### Environment Variables Alternative

For additional security, consider using environment variables instead of JSON files. Set SCHWAB_API_KEY and SCHWAB_APP_SECRET as environment variables or in .env file (must be in .gitignore). Modify schwab_data_fetcher.py to read from environment variables as fallback.

### Pre-Commit Checklist

Before every commit:
- Run git status to verify no credential files listed
- Run git diff --staged to review all changes
- Check no API keys, tokens, or passwords in code
- Verify .gitignore is up to date
- Test build succeeds without errors

### Security Resources

- Schwab API Support: traderapi@schwab.com
- Developer Portal: developer.schwab.com
- Git Security Guide: Official GitHub security documentation

## 🏗️ Agent Architecture

### Base Agent Foundation

**Enhanced Base Agent** provides robust foundation for HuggingFace Inference API interactions with production-grade features. Never crashes - returns None on all errors instead of raising exceptions. Comprehensive logging at DEBUG, INFO, WARNING, and ERROR levels.

**Smart Retry Logic:**

*HTTP 503 - Model Loading:* Special handling for cold start when model first loads into memory. Random 20-30 second wait time allows model loading. Up to 3 retry attempts with logging.

*HTTP 429 - Rate Limiting:* Respects Retry-After header from API response. Defaults to 60 second wait if header not present. Up to 3 retry attempts with logged wait times.

*Network Errors:* Exponential backoff for timeout/connection errors. Delay pattern: 1s, 2s, 4s for successive attempts. Up to 3 retry attempts with error logging.

**In-Memory Caching System:**

*SimpleCache Class:* 5-minute TTL (configurable time-to-live). LRU eviction when full (max 100 entries). Automatic cleanup of expired entries. Shared cache instance across all agents.

*Cache Key Generation:* Hash of model ID + input text using SHA-256. Same text with different models = different cache keys. Consistent key generation ensures reliable caching.

*Cache Operations:* Get from cache (returns None if not found/expired). Set in cache after API call. Clear all cache entries globally. Get cache statistics (size, TTL, max size).

**Classification Response Parsing:** Robust parser handles single-level lists and nested lists. Validates response structure and required keys. Returns None instead of crashing on invalid formats. Type validation ensures data integrity.

**Error Handling Flow:** All API calls return None on error (never raise exceptions). Check for None before parsing response. Return neutral AgentResult if errors occur. Always provide user with usable result (never crash). Log all errors with context for debugging.

### News Agent Architecture

**Advanced NewsAgent** provides sophisticated financial news sentiment analysis with automatic document parsing, ticker extraction, and intelligent aggregation. Designed specifically to analyze daily_portfolio_analysis.md files and extract actionable sentiment insights.

**Document Parsing Capabilities:**

*Section-Based Extraction:* Finds "News", "Events", "Market News", "Headlines" sections. Supports multiple section header variations (case-insensitive). Prioritizes structured content over unstructured paragraphs.

*Multiple List Format Support:* Bullet points (-, *, •, ▪). Numbered lists (1., 2., 3.). Paragraph splitting as fallback. Financial keyword filtering for relevance.

*News Detection Heuristic:* Requires 2+ financial keywords (earnings, revenue, profit, analyst, forecast, etc.). Minimum length 20 characters. Filters out non-financial content. Normalizes and deduplicates entries.

**Ticker Extraction System:**

*Multiple Format Support:* $AAPL format, Apple (AAPL) parenthetical format, (AAPL) standalone format, shares of GOOGL context format, stock MSFT mention format.

*Blacklist Filtering:* 50+ common words automatically filtered (A, I, FOR, THE, AND, OR, TO, AT, IN, ON, etc.). Time/location terms (US, UK, EU, AM, PM, ET). Business terms (CEO, CFO, CTO, IPO, AGO). Common verbs (ADD, BUY, SELL, GET, GO, SEE). Prevents false positive ticker detection.

**Intelligent Aggregation:** Combines multiple news items using confidence-weighted voting. Each sentiment weighted by its confidence score. Higher confidence results have more influence. Overall sentiment determined by weighted majority. Breakdown shows percentage of positive/negative/neutral.

**Structured Output:** NewsAnalysis dataclass contains sentiment (positive/negative/neutral), weighted confidence (0.0 to 1.0), extracted tickers list, sentiment breakdown percentages, count of news items analyzed, and raw individual results for inspection.

**Performance Optimization:**

*API Call Management:* Each news item = 1 API call. Configurable max_items to control costs/latency. Default 10 items balances coverage and speed. 5 items = ~10-15 seconds, 10 items = ~20-30 seconds, 20 items = ~40-60 seconds.

*Caching Benefits:* Base agent caches responses for 5 minutes. Re-analyzing same document within cache TTL is instant. Significant speedup for iterative analysis.

*Memory Efficiency:* Each NewsAnalysis: ~1-2KB. Each AgentResult: ~500 bytes. 10 items with results: ~10-15KB total.

### Trade Agent Architecture

**TradeAgent** is a pure logic agent that synthesizes outputs from all sentiment analysis agents (News, Market, Risk, Quality) to generate concrete trade orders. Makes NO API calls - only applies trading rules to agent results. Zero costs, no rate limits, instant execution.

**Trading Logic Rules:**

*Profit Taking:* If position return >= 15%, generate SELL order with HIGH priority.

*Stop Loss:* If position return <= -8%, generate SELL order with HIGH priority.

*Risk-Based Selling:* If market is Bearish AND risk is high, generate SELL with position-dependent priority.

*Buy Signals:* If news positive AND market Bullish AND risk not high, generate BUY with high priority. Confidence-based priority assignment (>70% = HIGH, 55-70% = MEDIUM, <55% = LOW).

**Position Sizing & Limits:**

*Maximum Position Size:* 20% of portfolio per position (hard limit). Automatically caps buy orders to respect limit. Calculates remaining capacity for existing positions.

*Buy Allocation:* Strong signals = 10% of portfolio. Moderate signals = 5% of portfolio. Weak signals = 3% of portfolio. Allocation capped at remaining capacity to 20% max.

**Signal Weighting System:** News sentiment: 30% weight. Market overall sentiment: 25% weight. Market position-specific sentiment: 20% weight. Risk assessment: 25% weight. Must sum to 1.0 for proper balance.

**Priority Assignment:** HIGH priority for confidence >= 70%, profit taking, or stop loss triggers. MEDIUM priority for confidence 55-70%. LOW priority for confidence < 55%. Execution order: HIGH → MEDIUM → LOW for optimal cash flow.

**Trade Order Generation:** Synthesizes all agent inputs into concrete orders. Applies trading rules systematically. Enforces risk management limits automatically. Generates prioritized order lists. Includes stop loss and profit target calculations. Never crashes - gracefully handles missing inputs.

**Output Compatibility:** Generates TradeOrder objects compatible with existing trade_executor.py. Standard format for ticker, action, shares, target values, reasoning, priority, limits, stops, and targets. Pre-sorted by priority for executor. Works seamlessly with existing Schwab integration.

**Configuration & Customization:**

*Adjustable Thresholds:* Profit take threshold (default 15%). Stop loss threshold (default -8%). Confidence thresholds for priorities. Position sizing allocations.

*Customizable Weights:* News, market, risk weights adjustable. Must maintain sum = 1.0. Higher weight = more influence on decisions. Risk weight often kept high for safety.

**Error Handling:** No API calls means no API failures possible. All inputs are optional - system adapts. Missing agent results are handled gracefully. Returns empty list (HOLD) if insufficient signals. Never crashes - defensive programming throughout.

## 📊 Thematic Prompt Builder

### Overview
Specialized prompt generation system for thematic and growth investing analysis supporting the opportunistic 20% portfolio allocation strategy. Generates optimized prompts for 7B-70B parameter language models to systematically evaluate companies across sector-specific dimensions using structured 5-dimension scoring frameworks.

### Supported Investment Themes

**AI Infrastructure:** Data centers, networking, power, cooling. Dimensions: value chain position, technical differentiation, customer traction, competitive moat, unit economics.

**Nuclear Renaissance:** SMR technology, uranium, enrichment, services. Dimensions: technology readiness level, regulatory progress, strategic partnerships, government support, commercialization timeline.

**Defense Modernization:** Drones, cyber, space, hypersonics. Dimensions: program stability, technology superiority, growth runway, financial strength, geopolitical tailwinds.

**Climate Technology:** Adaptation, mitigation, infrastructure. Dimensions: technology maturity, unit economics, policy support, demand/scalability, carbon impact.

**Longevity/Biotech:** GLP-1 drugs, aging therapies, medical devices. Dimensions: science quality, clinical progress, commercial potential, IP position, management/financing.

**Generic Thematic:** Flexible template for emerging themes with user-defined custom dimensions.

### Model Optimization

**Token Budget Management:** System provides three model size configurations with appropriate token budgets. 7B models (800 tokens) optimized for fast, cost-effective analysis. 13B models (1200 tokens) provide balanced coverage. 70B models (2000 tokens) enable comprehensive deep analysis. Automatic validation ensures prompts stay within budget limits with <10% tolerance.

**Compression Features:** Optional compression mode reduces token usage by 3-5% through whitespace removal and phrase compression. Maintains prompt structure and meaning while optimizing for token efficiency. Automatically applied when prompts approach budget limits.

**Utility Functions:** Token estimation using 4 characters per token heuristic for English text. Automatic validation against model-specific budgets. Text truncation with ellipsis for context management. Prompt compression for token savings.

### Scoring Framework

**Systematic Evaluation:** Each theme evaluates companies across exactly 5 specific dimensions rated on 1-10 scale. Total score calculated out of 50 points maximum. Each dimension requires one-sentence rationale explaining the score. Structured output format ensures consistency across evaluations.

**Classification Tiers:** Leader classification for 40-50 points indicating market leaders. Contender classification for 30-39 points indicating strong players. Laggard classification for 0-29 points indicating weak positioning. Investment stance derived from classification.

**Investment Stance Rules:** BUY stance recommended for scores above 35 points. HOLD stance suggested for scores 25-35 points. AVOID stance indicated for scores below 25 points. Stance includes key strength and key risk factors.

### Integration with 80/20 Strategy

**Core 80% Allocation:** Use Quality Agent for fundamental screening. Focus on ROE persistence above 15% for 10+ years. Evaluate gross profitability, ROIC, operating profitability. Target quality scores greater than 7 for core positions. Position sizing: 10-20% for quality score 9-10, 7-12% for score 8-8.9, 5-8% for score 7-7.9.

**Opportunistic 20% Allocation:** Use Thematic Prompt Builder for growth analysis. Evaluate on theme-specific dimensions relevant to sector. Minimum thematic score of 28 out of 50 points required. Position sizing: 5-7% for score 40-50 (leaders), 3-5% for score 35-39 (strong contenders), 2-3% for score 30-34 (contenders), 2-3% for score 28-29 (weak contenders). Do not invest if score below 28.

**Portfolio Construction Rules:** Maintain strict 80/20 split between quality core and thematic opportunistic. Never exceed 7% position size in any single opportunistic holding. Total opportunistic allocation capped at 20% of portfolio. Set tighter stop-losses for opportunistic positions (-25% to -30%). Take profits more aggressively on thematic positions (+40-60% gains).

### Theme-Specific Dimensions

**AI Infrastructure Analysis:** Value chain position evaluates proximity to AI workloads and stack placement. Technical differentiation assesses proprietary technology and competitive advantages. Customer traction examines revenue growth and product-market fit. Competitive moat analyzes barriers to entry and switching costs. Unit economics evaluates gross margins and path to profitability.

**Nuclear Renaissance Analysis:** Technology readiness measures TRL level and design maturity. Regulatory progress tracks NRC approval status and licensing timeline. Strategic partnerships assess utility partnerships and government contracts. Government support evaluates policy tailwinds and subsidies. Commercialization timeline estimates time to first revenue and capital requirements.

**Defense Modernization Analysis:** Program stability examines contract backlog and multi-year programs. Technology superiority assesses technical edge over adversaries. Growth runway analyzes TAM expansion and new program wins. Financial strength evaluates operating margins and free cash flow. Geopolitical tailwinds assess defense budget trajectory and threat environment.

**Climate Technology Analysis:** Technology maturity measures TRL and commercial deployment scale. Unit economics evaluates cost competitiveness and margin profile. Policy support examines IRA benefits and mandates. Demand and scalability assess market pull and production capability. Carbon impact quantifies CO2 reduction potential and cost effectiveness.

**Longevity/Biotech Analysis:** Science quality evaluates mechanism validity and data quality. Clinical progress tracks trial stage and endpoint achievement. Commercial potential assesses market size and pricing power. IP position examines patent protection and exclusivity timeline. Management and financing evaluate team quality and cash runway.

### Workflow Integration

**Weekly Theme Selection Process:** Scan market catalysts including regulatory changes, technology disruptions, demographic shifts, geopolitical events. Select 2-3 themes with strongest 12-18 month outlook and clear near-term catalysts. Identify pure-play companies and picks-and-shovels providers in selected themes.

**Company Analysis Steps:** Gather financial data and business descriptions. Prepare market context including trends, policy tailwinds, competitive landscape. Generate prompts using appropriate theme-specific method. Send prompts to HuggingFace API or local LLM for analysis. Parse structured output for scores, rationales, classification.

**Position Management:** Apply score-based position sizing automatically. Respect 20% total opportunistic allocation cap strictly. Set stop-losses based on volatility (-25% to -30% for high-growth). Define profit targets based on theme momentum (+40-60%). Review scores weekly and exit if score drops below 28.

### Output Structure

**Dimension Scores:** Each of 5 dimensions receives score from 1-10. One-sentence rationale explains reasoning for each score. Scores aggregate to overall score out of 50 points.

**Classification:** Leader (40-50 points) indicates market leadership position. Contender (30-39 points) indicates strong competitive position. Laggard (0-29 points) indicates weak or unproven position.

**Investment Analysis:** Key strength identifies primary competitive advantage in one sentence. Key risk identifies primary concern or vulnerability in one sentence. Investment stance provides BUY/HOLD/AVOID recommendation with score thresholds.

### Performance Characteristics

**Token Efficiency:** AI Infrastructure prompts: 428-454 tokens on 7B model. Nuclear Renaissance prompts: 380-398 tokens. Defense Modernization prompts: 394 tokens on 13B model. Climate Technology prompts: 384 tokens. Longevity/Biotech prompts: 397 tokens. Generic thematic prompts: 276-307 tokens. All well within respective model budgets.

**Compression Effectiveness:** Compression mode reduces token usage by 3-5% on average. 15-token savings typical for 7B prompts (411 → 396 tokens). Maintains prompt structure and semantic meaning. Applied automatically when approaching budget limits.

**Test Coverage:** Comprehensive test suite with 10 test suites covering all functionality. Model initialization tests for all three model sizes. Theme-specific prompt generation tests for all 6 themes. Utility method tests for token estimation, validation, compression. Edge case tests for minimal data, empty contexts, error handling. All 10/10 test suites passing successfully.

### Implementation Files

**Core Module:** thematic_prompt_builder.py contains main ThematicPromptBuilder class (900+ lines). Includes all 6 theme-specific prompt methods. Provides utility methods for token management. Full type hints and comprehensive docstrings.

**Test Suite:** test_thematic_prompt_builder.py provides comprehensive testing (600+ lines). Tests all theme-specific prompt generation methods. Validates token budgets and compression. Tests edge cases and error handling. 10/10 test suites with 100% pass rate.

### Best Practices

**Theme Selection Guidelines:** Focus on themes with clear 12-18 month catalysts (not 5+ year speculation). Require minimum $10B total addressable market with less than 20% penetration. Look for multiple demand drivers to reduce single-point-of-failure risk. Verify government backing or corporate necessity for theme sustainability.

**Company Evaluation Standards:** Minimum thematic score of 28 out of 50 points required for investment consideration. Require at least 3 dimensions scoring 6+ out of 10 points. Red flag raised if any dimension scores below 4 points. Prioritize leaders (40-50) and strong contenders (35-39) for best risk-reward.

**Risk Management Rules:** Negative free cash flow acceptable IF runway exceeds 12 months AND revenue growing above 50%. Set tighter stop-losses for opportunistic holdings (-25% to -30% vs -8% for core). Take profits more aggressively on thematic winners (+40-60% vs +15% for core). Review thematic scores weekly and exit if score drops below 28 threshold.

## 📅 Catalyst Analyzer

### Overview
Event-driven trading analysis system identifying and prioritizing upcoming catalysts (specific events) that could drive stock performance. Enables timing entries and exits around events rather than passive buy-and-hold strategies. Integrates with HuggingFace LLMs to identify earnings reports, FDA approvals, product launches, contract awards, regulatory decisions, and corporate actions across three time horizons.

### Catalyst Types and Timeline Classification

**Catalyst Categories:** Earnings reports and guidance updates, FDA approvals and clinical trial results, product launches and technology milestones, contract awards and partnership announcements, regulatory decisions and policy changes, spin-offs/mergers/corporate actions.

**Timeline Buckets:** Near-term (0-6 months) for events within next 6 months requiring immediate positioning. Medium-term (6-18 months) for events 6-18 months out allowing gradual accumulation. Long-term (18+ months) for events beyond 18 months to monitor but not act on yet.

### Priority Scoring System

**Mathematical Formula:** Score = time_weight/(timeline_months) + probability_weight × probability_score + impact_weight × impact_score + direction_bonus

**Default Weights:** time=2.0 (proximity matters), probability=3.0 (likelihood is important), impact=5.0 (magnitude most critical), direction_bonus=2.0 (positive catalyst bonus, negative catalyst penalty -1.0).

**Probability Scores:** High (>70% likely) = 3.0 points. Medium (30-70% likely) = 2.0 points. Low (<30% likely) = 1.0 points.

**Impact Scores:** High (>10% price move) = 3.0 points. Medium (3-10% price move) = 2.0 points. Low (<3% price move) = 1.0 points.

**Direction Adjustment:** Positive catalysts receive +2.0 bonus. Negative catalysts receive -1.0 penalty. Neutral catalysts receive no adjustment.

### Workflow Process

**Step 1 - Generate Prompt:** Use generate_catalyst_prompt() to create structured LLM prompt requesting top 5 catalysts across three time horizons. Each catalyst requires name, timeline months, probability (H/M/L), impact (H/M/L), direction (+/-/neutral), dependencies, and context notes.

**Step 2 - Parse Response:** Use parse_catalyst_response() to extract structured data from LLM output. Handles multiple response formats with robust regex patterns. Creates Catalyst objects with all attributes and estimated dates.

**Step 3 - Prioritize:** Use prioritize_catalysts() to score each catalyst using formula. Sorts by priority score descending. Sooner events with higher impact and probability score highest.

**Step 4 - Generate Reports:** Use generate_catalyst_summary_report() for comprehensive markdown reports. Use create_monitoring_schedule() for calendar with catalyst dates and monthly check-in reminders. Reports include executive summary, top 5 catalysts, detailed timeline tables, and trading implications.

**Step 5 - Portfolio Analysis:** Use batch_analyze_catalysts() to process multiple companies efficiently. Identify near-term opportunities across entire portfolio. Focus attention on highest priority upcoming events.

### Trading Applications

**Entry Timing Strategies:** Position 2-4 months before high-probability positive catalysts to capture run-up. Larger positions (5-7%) for high-impact events with strong conviction. Scale into positions as catalyst date approaches and confidence increases. Avoid entering less than 2 weeks before catalyst when premium already priced in.

**Exit Timing Strategies:** Take profits within days after catalyst occurs if price target hit. Exit before negative catalyst with high probability to avoid drawdown. Use tighter stop-losses for event-driven trades (-15% to -20% vs -8% for core). Book profits aggressively after catalyst materializes (+20-40% targets vs +15% for core).

**Risk Management Techniques:** Consider protective options for binary events like FDA decisions or trial results. Reduce position size 1-2 weeks before uncertain high-impact events. Set calendar reminders for catalyst dates and monthly portfolio reviews. Use smaller position sizes for binary catalysts (3-5% vs 7-12% for quality).

**Catalyst Clustering:** Identify when multiple high-impact catalysts occur within 3-6 months for same company. Increased volatility likely around catalyst clusters. Consider larger position if positive catalysts cluster with low correlation. Reduce position if negative catalysts cluster or dependencies create risk cascade.

### Integration with Portfolio Strategy

**Core 80% Quality Holdings:** Monitor catalysts to optimize entry timing by buying dips before positive catalysts. Use catalysts to validate conviction in long-term holdings. Exit if negative long-term catalyst emerges threatening business model like patent expiration or regulatory threat. Set looser stop-losses (-8% to -10%) given longer time horizon.

**Opportunistic 20% Thematic Holdings:** Use catalyst-driven entries by positioning 2-4 months before major positive catalyst. Set aggressive profit targets by exiting within days/weeks after catalyst if target hit. Focus on near-term catalysts (0-6 months) to identify best timing for thematic trades. Use medium-term catalysts to build watchlist for future thematic opportunities.

**Portfolio Construction Guidelines:** Maintain calendar of all near-term catalysts across entire portfolio. Avoid excessive concentration of catalysts in same timeframe to prevent correlation risk. Balance between catalyst-driven trades and longer-term quality compounders. Maximum 20% of portfolio in high-risk binary catalyst trades. Reserve cash for catalyst-driven opportunities (5-10% cash minimum).

### Output Structures

**Catalyst Object Attributes:** name (catalyst description), timeline (near/medium/long classification), timeline_months (estimated months until event), probability (H/M/L likelihood), impact (H/M/L expected price move), direction (+/-/neutral price direction), dependencies (prerequisite events), notes (additional context 1-2 sentences), priority_score (calculated priority), estimated_date (best guess date).

**Summary Report Sections:** Executive summary with catalyst counts and bullish/bearish bias. Top 5 priority catalysts with detailed attributes. Catalyst calendar by timeline with markdown tables. Monitoring schedule with next 10 events and check-in reminders. Trading implications with entry/exit recommendations and risk management guidance.

### Performance Characteristics

**Test Results:** 7 out of 8 test suites passing with comprehensive coverage. Parsing handles multiple LLM response formats robustly with fallback patterns. Prioritization uses mathematically sound scoring with configurable weights. Report generation produces comprehensive markdown with tables and recommendations. Batch processing analyzes entire portfolio efficiently in single operation.

**Implementation Stats:** Main analyzer class catalyst_analyzer.py contains 900+ lines with full docstrings. Test suite test_catalyst_analyzer.py provides 600+ lines comprehensive testing. Covers prompt generation, response parsing, prioritization, scheduling, reporting, and batch analysis.

### Best Practices

**Catalyst Identification:** Focus on binary events with clear outcomes like FDA approval yes/no or earnings beat/miss. Assign high impact only to events likely to move stock more than 10%. Be conservative with probability assessments to avoid anchoring bias. Document dependencies carefully to track prerequisite events and cascade risks.

**Entry Timing:** Enter positions 2-4 months before positive high-impact catalyst to capture anticipation run-up. Avoid entering less than 2 weeks before catalyst when premium already priced in. Scale into positions as conviction increases and catalyst date approaches. Use smaller initial positions for binary catalysts with uncertain outcomes.

**Monitoring Cadence:** Set calendar reminders 1 month before each catalyst for status check. Review catalyst status in monthly portfolio reviews. Update probability and impact assessments as new information emerges. Exit immediately if catalyst delays significantly or dependencies fail. Track realized outcomes to calibrate future probability estimates.

**Risk Management:** Use smaller position sizes for binary catalysts (3-5% vs 7-12% for quality holdings). Set tighter stop-losses for event-driven trades (-15% to -20% vs -8% for core). Consider protective puts for high-impact negative catalysts. Book profits aggressively after catalyst occurs rather than hoping for continuation. Limit total catalyst-driven trades to 20% of portfolio maximum.

## Competitive Edge

This automated system provides several advantages in the AI vs AI portfolio competition:

1. **Near-Instant Execution**: No manual trade entry delays after AI agent analysis
2. **Zero Manual Errors**: Automated validation prevents typos and calculation mistakes
3. **Optimal Cash Flow**: SELL→BUY prioritization prevents failed trades due to insufficient funds
4. **Complete Automation**: 95%+ automation with AI agent workflow
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

#### **Option 1: HuggingFace Agent Workflow (Cloud-Based AI)**
```bash
# Step 1: Generate portfolio analysis
python "Portfolio Scripts Schwab/main.py" --report-only

# Step 2: Generate AI recommendations via HuggingFace agents
python "Portfolio Scripts Schwab/main.py" --generate-hf-recommendations

# Step 3: Review and approve trades in manual_trades_override.json

# Step 4: Execute approved trades
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

| Feature | HuggingFace Agents (Cloud) | Local LLM Runtime |
|---------|----------------------------|-------------------|
| **Analysis Quality** | Excellent (specialized FinBERT models) | Excellent (specialized financial models) |
| **Speed** | 10-20 seconds (first run), ~5s (cached) | 3-7 minutes (GPU) / 8-18 min (CPU) |
| **Cost** | Free tier (~30 req/hr) or API fees | Free after setup |
| **Privacy** | Data sent to HuggingFace API | 100% local processing |
| **Customization** | Model selection only | Full model control |
| **Availability** | Service dependent | Always available |

### When to Use Local LLM Runtime

**Ideal For:**
- High-frequency trading with multiple daily analyses
- Privacy-sensitive portfolio management  
- Users with capable GPU hardware (RTX 4090+)
- Complete automation without external dependencies
- Development and backtesting scenarios

**Stick with HuggingFace Agents If:**
- Limited hardware resources (no GPU needed)
- Occasional trading (few times per week)
- Prefer cloud-based specialized FinBERT models
- Don't want to manage local infrastructure
- Want fast analysis with caching (5-20 seconds)

### Documentation
- **Complete Setup Guide**: `local_runtime/README_LOCAL.md`
- **System Architecture**: `local_runtime/system_architecture`  
- **Installation Scripts**: `local_runtime/installation.sh`
- **Model Configurations**: `local_runtime/local_llm_server.py`

The local LLM runtime represents the **ultimate evolution** of the portfolio management system - complete AI-powered trading automation with zero external dependencies while maintaining full compatibility with the existing proven workflow.