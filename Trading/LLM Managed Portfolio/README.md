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

**New to the system? Follow this 5-minute guide to run your first investment opportunity analysis.**

#### Step 1: Quick Analysis (2-5 minutes)

Find quality investment opportunities from S&P 500:

```bash
cd "Portfolio Scripts Schwab"
python quality_analysis_script.py --limit 50
```

**What this does:**
- Screens top 50 S&P 500 stocks by market cap
- Calculates quality scores using 5 research-backed metrics
- Identifies SELL candidates (weak holdings with quality <70)
- Identifies BUY alternatives (strong opportunities with quality ≥85)
- Outputs to `outputs/quality_analysis_YYYYMMDD.json`

**Expected output:**
```
Analyzing 50 tickers from S&P 500...
✅ Fetched financial data for 48/50 tickers
📊 Quality Analysis Complete:
   - SELL Candidates: 2 holdings (quality <70)
   - BUY Alternatives: 5 opportunities (quality ≥85)
   - Results saved to outputs/quality_analysis_20251111.json
```

#### Step 2: Weekly Screening (12-17 minutes)

Complete 10-step STEPS analysis:

```bash
cd "Portfolio Scripts Schwab"
python steps_orchestrator.py
```

**What this does:**
- Runs complete STEPS methodology (10 steps)
- Screens full S&P 500 (~500 stocks) for opportunities
- Analyzes market environment (S&P 500, VIX, sector rotation)
- Compares holdings quality vs watchlist alternatives
- Integrates news sentiment and risk analysis
- Generates trading_recommendations.md with specific BUY/SELL/HOLD orders

**Expected output:**
```
STEP 1/10: Market Environment Assessment ✅
STEP 2/10: Holdings Quality Analysis ✅
STEP 3A/10: Core Quality Screening (S&P 500) ✅
...
STEP 10/10: Framework Validation ✅

📋 Trading Recommendations Generated:
   - File: trading_recommendations/trading_recommendations_20251111.md
   - SELL: 2 positions (quality <70)
   - BUY: 3 opportunities (quality ≥85)
   - HOLD: 5 positions (maintain allocation)
```

#### Step 3: Review & Approve Recommendations

```bash
# Review the generated recommendations
cat trading_recommendations/trading_recommendations_20251111.md

# If you approve, edit manual override file
# Copy approved trades to:
nano "Portfolio Scripts Schwab/manual_trades_override.json"

# Set "enabled": true to authorize execution
```

#### Step 4: Execute Trades (Market Hours Only)

```bash
# Execute approved trades
python main.py
```

**Important:** Trades only execute during market hours (Mon-Fri 9:30AM-4PM ET).

---

#### Advanced Options

**Test run (no file writes):**
```bash
python steps_orchestrator.py --dry-run
```

**Quick analysis (skip optional steps):**
```bash
python steps_orchestrator.py --skip-thematic --skip-competitive --skip-valuation
```

**Report generation only (available 24/7):**
```bash
python main.py --report-only
```

**Account status check (available 24/7):**
```bash
python main.py --account-status --dry-run
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

## System Architecture Overview

### How the System Works

The LLM Managed Portfolio system uses a **hybrid approach** combining:
1. **Data-driven analysis** (STEPS 1-7): Quantitative quality metrics, market cap classification, financial data
2. **AI-powered synthesis** (STEP 8): HuggingFace FinBERT agents + DeepSeek-R1 reasoning for BUY/SELL/HOLD decisions
3. **Human approval** (You): Review recommendations before executing any trades

```
┌─────────────────────────────────────────────────────────────────┐
│ DATA SOURCES                                                     │
│   • Schwab API: Real-time prices (SPY proxy for S&P 500, sectors)│
│   • yfinance: Fundamentals + VIX fallback (when Schwab unavail) │
│   • Yahoo Finance: News articles (7-day history)                │
│   • Wikipedia: Index lists (S&P 500, S&P 400, S&P 600)         │
│   Note: Schwab API does NOT support direct index quotes         │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEPS 1-7: DATA ANALYSIS (Pure Math, No AI)                     │
│                                                                  │
│  STEP 1: Market Environment (Schwab API + yfinance fallback)   │
│    → S&P 500 (SPY proxy), VIX (yfinance), sector rotation      │
│                                                                  │
│  STEP 2: Quality Analysis (5 Research-Backed Metrics)           │
│    → Gross Profitability (30%) - Strongest predictor           │
│    → ROE (25%) - Persistence power                             │
│    → Operating Profitability (20%)                             │
│    → FCF Yield (15%)                                           │
│    → ROIC (10%)                                                │
│    → Classify into 4-tier market cap framework                 │
│                                                                  │
│  STEP 3A: Quality Screening (S&P 500 Watchlist)                │
│    → Screen ~500 stocks for quality ≥70                        │
│    → Output: quality_watchlist_YYYYMMDD.csv                    │
│                                                                  │
│  STEP 3B-5: Additional Analysis (Optional)                      │
│    → Thematic scoring, competitive analysis, valuation         │
│                                                                  │
│  STEP 6: Portfolio Construction (4-Tier Framework)              │
│    → Large Cap (65-70%): $50B+, position 8-15%                 │
│    → Mid Cap (15-20%): $2B-$50B, position 5-10%                │
│    → Small Cap (10-15%): $500M-$2B, position 2-4%              │
│    → Thematic (5-10%): Score ≥28/40, position 1.5-2.5%         │
│                                                                  │
│  STEP 7: Rebalancing Trades                                     │
│    → Generate specific buy/sell orders                         │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: TRADE SYNTHESIS (AI Agents Make Decisions)              │
│                                                                  │
│  1. Load all STEPS 1-7 outputs (quality, thematic, tier data)   │
│                                                                  │
│  2. Run FinBERT Sentiment Agents:                               │
│     • NewsAgent: Analyzes recent news sentiment                 │
│     • MarketAgent: Overall market sentiment                     │
│     • RiskAgent: Portfolio risk assessment                      │
│     • ToneAgent: Market tone detection                          │
│                                                                  │
│  3. For EACH stock (holdings + watchlist):                      │
│     Build agent_outputs dict:                                   │
│       {                                                         │
│         'quality_analysis': {score: 85, tier: 'ELITE', ...},   │
│         'thematic_score': 32,                                   │
│         'market_cap_tier': 'LARGE_CAP',                         │
│         'roe_persistence_years': 8,                             │
│         'news_sentiment': {...},  # From NewsAgent             │
│         'market_sentiment': {...},  # From MarketAgent         │
│         'risk_assessment': {...},  # From RiskAgent            │
│         'current_holding': True,  # Context flag               │
│         'current_shares': 15  # Actual shares owned            │
│       }                                                         │
│                                                                  │
│  4. Run ReasoningAgent (DeepSeek-R1):                           │
│     • Synthesizes ALL inputs                                    │
│     • Applies STEPS thresholds:                                 │
│       - Quality <70 → EXIT                                      │
│       - Thematic <28 → EXIT                                     │
│       - Red flags >3 → EXIT                                     │
│     • Returns ReasoningDecision:                                │
│       {                                                         │
│         action: 'BUY',  # or SELL/HOLD                         │
│         confidence: 0.85,                                       │
│         reasoning_steps: ["Step 1...", "Step 2..."],           │
│         target_position_pct: 12.0,  # From tier rules          │
│         position_type: 'QUALITY',                              │
│         stop_loss_pct: -15.0,                                  │
│         profit_target_pct: 40.0                                │
│       }                                                         │
│                                                                  │
│  5. Python Code Formats Markdown (NOT an LLM):                  │
│     • Uses hardcoded template structure                         │
│     • Inserts ReasoningAgent decisions                          │
│     • Categorizes by priority (HIGH/MEDIUM/LOW)                 │
│     • Writes to trading_recommendations_YYYYMMDD.md             │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEPS 9-10: VALIDATION                                          │
│   • Data quality check (completeness, freshness)                │
│   • Framework compliance check (allocation, position sizing)    │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ OUTPUT FILES                                                     │
│   📄 trading_recommendations/trading_recommendations_YYYYMMDD.md│
│   📊 outputs/quality_analysis_YYYYMMDD.json                     │
│   📊 outputs/quality_watchlist_YYYYMMDD.csv                     │
│   📊 outputs/market_environment_YYYYMMDD.json                   │
│   📊 outputs/compliance_YYYYMMDD.json                           │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ HUMAN REVIEW & APPROVAL (You)                                   │
│   1. Review trading_recommendations.md                          │
│   2. Edit manual_trades_override.json with approved trades      │
│   3. Set "enabled": true                                        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ TRADE EXECUTION (market hours only)                             │
│   • python main.py (executes approved trades)                   │
│   • Updates portfolio_state.json                                │
│   • Logs all actions to trade_execution.log                     │
└─────────────────────────────────────────────────────────────────┘
```

### Key Architectural Principles

**1. Data-Driven Foundation (STEPS 1-7)**
- Pure mathematical calculations, no AI hallucination
- 5 research-backed quality metrics with academic validation
- 4-tier market cap framework from quality_investing_thresholds_research.md
- Deterministic, reproducible, transparent

**2. AI for Synthesis, Not Analysis (STEP 8)**
- FinBERT agents analyze sentiment (news, market, risk)
- DeepSeek-R1 reasoning agent synthesizes ALL inputs
- AI makes BUY/SELL/HOLD recommendations with reasoning
- Python code formats output (not an LLM summarizer)

**3. Human-in-the-Loop (Always)**
- System NEVER executes trades automatically
- All recommendations require manual review and approval
- You control what gets executed via manual_trades_override.json
- Safety-first design

**4. Performance-Optimized**
- Daily analysis: 50 tickers, 2-5 minutes
- Weekly screening: 500 tickers (S&P 500), 12-17 minutes
- Monthly deep dive: 1,500 tickers (future: S&P 500+400+600), 45-60 minutes
- 24-hour caching for financial data, 4-hour for market cap

**5. No Vendor Lock-In**
- Free data sources: yfinance, Yahoo Finance, Wikipedia
- Open-source models: FinBERT (HuggingFace), DeepSeek-R1
- Optional: Schwab API for real-time quotes (free for customers)

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

**STEPS Orchestrator - Primary Workflow**

The STEPS (Systematic Trading & Evaluation for Portfolio Success) framework is the **recommended workflow** for all portfolio analysis and trading decisions. It implements a comprehensive 10-step methodology with a research-backed 4-tier market cap framework.

```bash
# Full 10-step STEPS analysis (recommended)
cd "Portfolio Scripts Schwab"
python steps_orchestrator.py

# Quick analysis (skip optional steps for faster execution)
python steps_orchestrator.py --skip-thematic --skip-competitive --skip-valuation

# Test run (show what would be done without executing)
python steps_orchestrator.py --dry-run

# Detailed logging for debugging
python steps_orchestrator.py --verbose
```

**The 10 STEPS Framework:**

1. **Market Environment Assessment**
   - Analyzes S&P 500 trend, VIX volatility, 11-sector rotation
   - Uses **Schwab API** for real-time price data
   - Classifies market conditions: STRONG_BULL/BULL/NEUTRAL/BEAR/STRONG_BEAR
   - Determines risk appetite: RISK_ON/NEUTRAL/RISK_OFF

2. **Holdings Quality Analysis** (CRITICAL STEP)
   - Calculates quality scores using 5 research-backed metrics (weighted by importance):
     1. **Gross Profitability (30%)**: Revenue - COGS / Assets (Sharpe ratio 0.85, strongest predictor)
     2. **ROE (25%)**: Powerful for persistence (15%+ for 10 years vastly outperforms)
     3. **Operating Profitability (20%)**: Comparable to gross profitability in Fama-French
     4. **FCF Yield (15%)**: Top quintile outperforms by ~10% annually
     5. **ROIC (10%)**: Core quality assessment metric
   - Classifies holdings into 4-tier market cap framework
   - Uses **yfinance** for fundamental data (Schwab API doesn't provide)

3A. **Core Quality Screening**
   - Identifies quality opportunities from S&P 500 universe
   - Filters by tier-specific requirements (ROE persistence, strict filters)

3B. **Thematic Opportunity Discovery**
   - Scores opportunistic/thematic investments (0-40 scale)
   - Themes: AI Infrastructure, Nuclear, Defense, Climate, Longevity/Biotech

4. **Competitive Analysis**
   - Compares holdings vs. direct competitors
   - Identifies better alternatives in same sector

5. **Valuation Analysis**
   - Assesses whether stocks are reasonably priced
   - P/E, P/B, PEG ratio analysis

6. **Portfolio Construction** (4-Tier Framework)
   - **Large Cap (65-70%)**: $50B+, 5+ years ROE >15%, position 8-15%
   - **Mid Cap (15-20%)**: $2B-$50B, 2-3 years ROE >15%, incremental ROCE +5%, position 5-10%
   - **Small Cap (10-15%)**: $500M-$2B, 6-8 quarters ROE trend, strict filters (FCF+, D/E<1.0, GP>30%), position 2-4%
   - **Thematic (5-10%)**: Thematic score ≥28/40, position 1.5-2.5%
   - Determines optimal allocation and position sizes

7. **Rebalancing Trades**
   - Generates specific buy/sell orders to reach target allocation
   - Minimum $50 trade size to avoid micro-trades

8. **Trade Synthesis** (Agent-Powered Decision Making)
   - **recommendation_generator_script.py** orchestrates the decision process:
     - Loads all STEPS 1-7 outputs (quality scores, thematic scores, market environment, tier data)
     - Runs **MarketAgent** (FinBERT) → market sentiment analysis
     - Runs **RiskAgent** (FinBERT) → portfolio risk assessment
     - Runs **ToneAgent** (FinBERT) → overall market tone
     - For EACH stock (holdings + watchlist alternatives):
       - Combines all data into `agent_outputs` dict (quality, thematic, tier, ROE persistence, news, market, risk)
       - Runs **ReasoningAgent** (DeepSeek-R1) → synthesizes all inputs into BUY/SELL/HOLD decision with reasoning steps
       - ReasoningAgent applies STEPS thresholds (quality <70 = EXIT, thematic <28 = EXIT, red flags >3 = EXIT)
       - Returns `ReasoningDecision` with action, confidence, reasoning_steps, position sizing
     - Python code programmatically generates trading_recommendations.md file (NOT an LLM summarizer)
       - Uses hardcoded template structure (headers, sections, formatting)
       - Inserts ReasoningAgent decisions and reasoning text into template
       - Categorizes by priority (HIGH/MEDIUM/LOW) and action (BUY/SELL/HOLD)
   - **Key Distinction**: ReasoningAgent makes decisions, Python code formats markdown file

**STEP 8 Detailed Architecture:**

```python
# For EACH stock, build agent_outputs dict:
agent_outputs = {
    # From STEPS 1-7 (Data Analysis)
    'quality_analysis': {
        'composite_score': 85.0,           # From STEP 2 (0-100 scale)
        'tier': 'ELITE',                   # From STEP 2
        'red_flags_count': 1               # From STEP 2
    },
    'thematic_score': 32.0,                # From STEP 3B (0-40 scale, None if not thematic)
    'market_cap_tier': 'LARGE_CAP',        # From STEP 6 (LARGE_CAP/MID_CAP/SMALL_CAP/THEMATIC)
    'roe_persistence_years': 8,            # From STEP 2 (years of ROE >15%)
    'roe_trend_quarters': None,            # From STEP 2 (for small caps only)
    'incremental_roce': None,              # From STEP 2 (for mid caps only)
    'strict_filters_passed': None,         # From STEP 2 (for small caps only)

    # From FinBERT Agents (Live Analysis)
    'news_sentiment': {...},               # NewsAgent (FinBERT) result
    'market_sentiment': {...},             # MarketAgent (FinBERT) result
    'risk_assessment': {...},              # RiskAgent (FinBERT) result

    # Context Flags
    'current_holding': True,               # FIXED: True for holdings, False for alternatives
    'current_shares': 15                   # DYNAMIC: Actual shares from portfolio_state.json (0 for alternatives)
}

# ReasoningAgent (DeepSeek-R1) synthesizes all inputs:
decision = reasoning_agent.synthesize_decision(ticker, agent_outputs)

# Returns ReasoningDecision:
ReasoningDecision(
    action='BUY',                          # BUY/SELL/HOLD
    confidence=0.85,                       # 0.0-1.0
    reasoning_steps=[                      # Step-by-step reasoning
        "Quality score 8.5/10 (STEPS: Strong tier)",
        "Market cap tier: LARGE_CAP (position range 8-15%)",
        "ROE persistence: 8 years >15% (meets Large Cap requirement)",
        "News sentiment: positive, market: bullish",
        "Decision: BUY with 12.0% position"
    ],
    target_position_pct=12.0,              # Position sizing from tier rules
    position_type='QUALITY',               # QUALITY or THEMATIC
    stop_loss_pct=-15.0,                   # Risk management
    profit_target_pct=40.0
)

# Python code formats markdown (NOT LLM):
f.write(f"**BUY 15 shares of NVDA** - {reasoning_steps}\n\n")
```

**Data Flow Summary:**
- STEPS 1-7 generate quantitative data (scores, tiers, persistence metrics)
- FinBERT agents generate sentiment data (news, market, risk)
- ReasoningAgent (DeepSeek-R1) synthesizes ALL inputs → BUY/SELL/HOLD + reasoning
- Python template code writes markdown file with decisions

9. **Data Quality Validation**
   - Verifies data completeness and freshness
   - Tracks 9 required metrics, flags stale data (>90 days)

10. **Framework Compliance Validation**
   - Ensures 4-tier allocation compliance
   - Validates position sizing, tier requirements
   - Compliance score (0-100) with violation tracking

**Data Source Strategy**:
- **Price Data**: ✅ **Schwab API** (real-time quotes for S&P 500, VIX, sector ETFs, all holdings)
- **Fundamental Data**: yfinance (balance sheets, income statements, cash flow - Schwab API doesn't provide)
- **Best of Both Worlds**: Real-time pricing accuracy + comprehensive fundamental data

**Output Files**:
- `trading_recommendations/trading_recommendations_YYYYMMDD.md` - Final trading document
- `outputs/market_environment_YYYYMMDD.json` - Market assessment
- `outputs/quality_analysis_YYYYMMDD.json` - Quality scores for all holdings
- `outputs/portfolio_allocation_YYYYMMDD.json` - Target allocation with violations
- `outputs/compliance_YYYYMMDD.json` - Framework compliance report

**Performance**:
- Target runtime: <30 minutes for full analysis
- Uses caching for news and financial data (4-hour cache for market data)
- Independent steps can run in parallel

**High-Level Workflow Diagram**:

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT: Portfolio State + Market Data                            │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Market Environment (Schwab API)                         │
│   → S&P 500, VIX, 11 sectors (real-time prices)                │
│   → Trend, volatility, breadth, risk appetite                  │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Quality Analysis (yfinance fundamentals)                │
│   → 5 metrics weighted by research importance:                  │
│      • Gross Profitability (30%) - strongest predictor          │
│      • ROE (25%) - persistence power                            │
│      • Operating Profitability (20%)                            │
│      • FCF Yield (15%)                                          │
│      • ROIC (10%)                                               │
│   → Classify into 4-tier market cap framework                   │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEPS 3-5: Screening & Analysis                                 │
│   → 3A: S&P 500 quality screening by tier                      │
│   → 3B: Thematic scoring (AI/Nuclear/Defense/Climate/Bio)      │
│   → 4: Competitive analysis vs. peers                          │
│   → 5: Valuation analysis (P/E, P/B, PEG)                      │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Portfolio Construction (4-Tier Framework)               │
│   → Large Cap (65-70%): $50B+, 5yr ROE>15%, 8-15% position    │
│   → Mid Cap (15-20%): $2-50B, 2yr ROE>15%, 5-10% position     │
│   → Small Cap (10-15%): $0.5-2B, 6-8qtr trend, 2-4% position  │
│   → Thematic (5-10%): Score≥28/40, 1.5-2.5% position          │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Rebalancing Trades                                      │
│   → Generate specific buy/sell orders                          │
│   → Move current → target allocation                           │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: Trade Synthesis (Reasoning Agent)                       │
│   → Apply decision thresholds:                                 │
│      • Quality <70 → EXIT                                      │
│      • Thematic <28 → EXIT                                     │
│      • Red flags >3 → EXIT                                     │
│   → Position sizing by tier and score                          │
│   → Generate trading_recommendations.md                        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEPS 9-10: Validation                                          │
│   → 9: Data quality (completeness, freshness, consistency)     │
│   → 10: Framework compliance (allocation, position sizing)     │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ OUTPUT: trading_recommendations_YYYYMMDD.md                     │
│   + JSON reports (quality, allocation, compliance)             │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ HUMAN REVIEW & APPROVAL                                         │
│   → Review recommendations                                      │
│   → Edit manual_trades_override.json                           │
│   → Set "enabled": true                                        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ TRADE EXECUTION (market hours)                                  │
│   → python main.py (executes approved trades)                  │
│   → Updates portfolio_state.json                               │
└─────────────────────────────────────────────────────────────────┘
```

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

## How Investment Discovery Works

This section explains the core investment opportunity discovery process in detail.

### STEP 3A: Quality Screening (Watchlist Generation)

**Goal:** Screen the S&P 500 universe to find quality investment opportunities.

**Process:**

1. **Fetch S&P 500 Ticker List**
   ```python
   # From Wikipedia (free, updated regularly)
   url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
   tickers = pd.read_html(url)[0]['Symbol'].tolist()
   # Returns ~500-505 tickers
   ```

2. **Parallel Financial Data Fetching**
   - Uses `ThreadPoolExecutor` with 10 workers
   - Fetches via yfinance for each ticker:
     - Income statement: revenue, COGS, SG&A, operating income, net income
     - Balance sheet: total assets, shareholder equity, total debt
     - Cash flow: operating cash flow, free cash flow
     - Market data: market cap, current price, P/E ratio, sector, industry
   - Takes 12-17 minutes for ~500 tickers
   - Uses 24-hour cache to avoid redundant API calls

3. **Quality Metrics Calculation**

   For each stock, calculate 5 research-backed metrics:

   | Metric | Formula | Weight | Research Basis |
   |--------|---------|--------|----------------|
   | **Gross Profitability** | (Revenue - COGS) / Assets | 30% | Sharpe ratio 0.85, strongest predictor |
   | **ROE** | Net Income / Equity | 25% | 15%+ for 10 years vastly outperforms |
   | **Operating Profitability** | (Rev - COGS - SG&A) / Assets | 20% | Comparable to GP in Fama-French |
   | **FCF Yield** | Free Cash Flow / Market Cap | 15% | Top quintile +10% annually |
   | **ROIC** | NOPAT / (Debt + Equity) | 10% | Core quality metric |

   **Composite Score** = Weighted average (0-100 scale)

4. **Market Cap Classification**
   ```python
   # 4-tier framework (from quality_investing_thresholds_research.md)
   if market_cap >= 50e9:
       tier = "LARGE_CAP"      # ≥$50B
   elif market_cap >= 2e9:
       tier = "MID_CAP"        # $2B-$50B
   elif market_cap >= 500e6:
       tier = "SMALL_CAP"      # $500M-$2B
   else:
       tier = "MICRO_CAP"      # <$500M (excluded from portfolio)
   ```

5. **Red Flag Detection**

   Automatically identifies 6 types of quality concerns:
   - **High Accruals:** (Net Income - OCF) / Assets > 10% (earnings quality issue)
   - **Excessive Leverage:** Total Debt / Assets > 60% (financial risk)
   - **Declining Margins:** Gross margin down >5% YoY (competitive pressure)
   - **Aggressive Asset Growth:** Asset growth >20% YoY (empire building)
   - **Negative Cash Flow:** FCF < 0 (cash burn)
   - **Low ROIC:** ROIC < 10% (poor capital efficiency)

6. **Filtering and Ranking**
   ```python
   # Filter by minimum quality score (default: 70)
   quality_opportunities = [stock for stock in results if stock.score >= 70]

   # Sort by composite score (highest first)
   ranked = sorted(quality_opportunities, key=lambda x: x.score, reverse=True)
   ```

7. **Output Files**
   - `outputs/quality_watchlist_YYYYMMDD.csv` - Top opportunities (CSV format)
   - `outputs/quality_watchlist_YYYYMMDD_full.json` - Complete results with red flags
   - `outputs/quality_watchlist_YYYYMMDD_summary.txt` - Human-readable top 50

### STEP 2: Holdings Quality Analysis

**Goal:** Analyze current portfolio holdings using same quality metrics and compare to watchlist.

**Process:**

1. **Load Portfolio Holdings**
   ```python
   # From portfolio_state.json
   holdings = {
       "NVDA": {"shares": 15, "cost_basis": 180.50},
       "GOOGL": {"shares": 10, "cost_basis": 145.20},
       # ...
   }
   ```

2. **Calculate Quality for Holdings**
   - Same 5 metrics as watchlist screening
   - Same 4-tier market cap classification
   - **Additional tier-specific analysis:**

   **Large Cap ($50B+) Requirements:**
   ```python
   # Check ROE persistence (5+ years >15%)
   roe_history = get_roe_history(ticker, years=10)
   persistence_years = sum(1 for roe in roe_history if roe > 0.15)

   if persistence_years >= 5:
       meets_large_cap_criteria = True
   ```

   **Mid Cap ($2B-$50B) Requirements:**
   ```python
   # Check ROE persistence (2-3 years >15%)
   roe_history = get_roe_history(ticker, years=5)
   persistence_years = sum(1 for roe in roe_history if roe > 0.15)

   # Check incremental ROCE improvement
   incremental_roce = calculate_incremental_roce(ticker)

   if persistence_years >= 2 and incremental_roce > 0.05:
       meets_mid_cap_criteria = True
   ```

   **Small Cap ($500M-$2B) Requirements:**
   ```python
   # Check 6-8 quarters positive ROE trend
   roe_quarterly = get_roe_quarterly(ticker, quarters=8)
   trend_positive = all(roe_quarterly[i] < roe_quarterly[i+1] for i in range(len(roe_quarterly)-1))

   # Apply strict filters
   strict_filters = {
       'fcf_positive': free_cash_flow > 0,
       'debt_to_equity': total_debt / equity < 1.0,
       'gross_margin': (revenue - cogs) / revenue > 0.30
   }

   if trend_positive and all(strict_filters.values()):
       meets_small_cap_criteria = True
   ```

3. **Comparison Logic**

   **Identify SELL Candidates (Weak Holdings):**
   ```python
   sell_candidates = []

   for ticker, data in holdings_quality.items():
       # EXIT if quality <70 (STEPS threshold from PM_README_V3.md)
       if data['composite_score'] < 70:
           sell_candidates.append({
               'ticker': ticker,
               'quality_score': data['composite_score'],
               'reason': f"Quality {data['composite_score']:.1f} below STEPS threshold (70)"
           })
   ```

   **Identify BUY Alternatives (Strong Opportunities):**
   ```python
   buy_alternatives = []

   # Find weakest holding
   weakest_holding_score = min(h['composite_score'] for h in holdings_quality.values())

   for ticker, data in watchlist_quality.items():
       # BUY if Elite quality (≥85)
       if data['composite_score'] >= 85:
           buy_alternatives.append({
               'ticker': ticker,
               'quality_score': data['composite_score'],
               'tier': data['tier'],
               'reason': f"Elite quality {data['composite_score']:.1f} (STEPS Elite tier ≥85)"
           })

       # BUY if 15+ points better than weakest holding
       elif data['composite_score'] >= 70 and (data['composite_score'] - weakest_holding_score) > 15:
           buy_alternatives.append({
               'ticker': ticker,
               'quality_score': data['composite_score'],
               'improvement': data['composite_score'] - weakest_holding_score,
               'reason': f"Quality {data['composite_score']:.1f}, +{improvement:.1f} better than weakest holding"
           })
   ```

4. **Example Output**

   ```json
   {
     "holdings_quality": {
       "NVDA": {
         "composite_score": 90.0,
         "tier": "ELITE",
         "market_cap_tier": "LARGE_CAP",
         "roe_persistence_years": 8,
         "red_flags": []
       },
       "XYZ": {
         "composite_score": 65.0,
         "tier": "WEAK",
         "market_cap_tier": "LARGE_CAP",
         "roe_persistence_years": 2,
         "red_flags": ["declining_margins", "low_roic"]
       }
     },
     "recommendations": {
       "sell_candidates": [
         {
           "ticker": "XYZ",
           "quality_score": 65.0,
           "reason": "Quality 65.0 below STEPS threshold (70)"
         }
       ],
       "buy_alternatives": [
         {
           "ticker": "MSFT",
           "quality_score": 88.0,
           "tier": "ELITE",
           "reason": "Elite quality 88.0 (STEPS Elite tier ≥85)"
         },
         {
           "ticker": "GOOGL",
           "quality_score": 85.0,
           "improvement": 20.0,
           "reason": "Quality 85.0, +20.0 better than weakest holding"
         }
       ]
     }
   }
   ```

### News & Risk Integration

**How news and risk analysis feed into decisions:**

1. **News Sentiment Analysis (NewsAgent - FinBERT)**
   ```python
   # Fetch recent news (7 days from Yahoo Finance)
   headlines = get_recent_news(ticker, days=7)

   # Analyze sentiment with FinBERT
   news_result = news_agent.analyze(headlines)
   # Returns: {'sentiment': 'positive', 'score': 0.85, 'reasoning': '...'}
   ```

2. **Risk Assessment (RiskAgent - FinBERT)**
   ```python
   # Analyze portfolio-level risk
   risk_result = risk_agent.analyze(portfolio_context)
   # Returns: {'label': 'MODERATE', 'score': 0.6, 'reasoning': '...'}
   ```

3. **Integration in ReasoningAgent**
   ```python
   # Combine quality + news + risk → final decision
   decision = reasoning_agent.synthesize_decision(ticker, {
       'quality_analysis': {'composite_score': 85, 'tier': 'ELITE'},
       'thematic_score': None,
       'news_sentiment': {'sentiment': 'positive', 'score': 0.85},
       'market_sentiment': {'sentiment': 'bullish'},
       'risk_assessment': {'label': 'MODERATE'},
       'current_holding': False
   })

   # Returns: ReasoningDecision(
   #   action='BUY',
   #   confidence=0.90,
   #   reasoning_steps=[
   #     "Quality score 8.5/10 (STEPS: Elite tier)",
   #     "News sentiment: positive (0.85 confidence)",
   #     "Market risk: MODERATE (acceptable for quality stock)",
   #     "Decision: BUY with 12.0% position (Large Cap Elite tier: 10-20% range)"
   #   ]
   # )
   ```

4. **Decision Priority Logic**

   The ReasoningAgent applies thresholds in this order:

   ```python
   # Priority 1: Thematic score check
   if thematic_score and thematic_score < 28:
       return ReasoningDecision(action='SELL', reason='Thematic <28 threshold')

   # Priority 2: Quality score check
   if quality_score < 70:
       return ReasoningDecision(action='SELL', reason='Quality <70 threshold')

   # Priority 3: Red flags check
   if red_flags_count > 3:
       return ReasoningDecision(action='SELL', reason='Excessive red flags')

   # Priority 4: Elite quality BUY
   if quality_score >= 85 and not current_holding:
       return ReasoningDecision(action='BUY', reason='Elite quality ≥85')

   # Priority 5: Negative news + marginal quality
   if news_sentiment == 'negative' and quality_score < 75:
       return ReasoningDecision(action='SELL', reason='Negative news + weak quality')

   # Priority 6: Default HOLD
   return ReasoningDecision(action='HOLD', reason='Quality ≥70, no major concerns')
   ```

### Complete Discovery Flow Example

**Scenario:** Finding a replacement for weak holding XYZ

1. **Weekly Screening (STEP 3A)**
   ```bash
   python steps_orchestrator.py
   ```
   - Screens S&P 500 (~500 stocks)
   - Finds 50 stocks with quality ≥70
   - Top result: MSFT (quality 88.0, Large Cap Elite)

2. **Holdings Analysis (STEP 2)**
   - Current holding: XYZ (quality 65.0, 2 red flags)
   - Identified as SELL candidate (quality <70)

3. **Comparison**
   - MSFT quality 88.0 vs XYZ quality 65.0
   - Improvement: +23.0 points
   - Both Large Cap, so same position sizing rules apply

4. **News & Risk Check (STEP 8)**
   - MSFT news: Positive (Azure growth, AI partnerships)
   - XYZ news: Negative (margin compression, losing market share)
   - Portfolio risk: MODERATE (acceptable)

5. **Final Recommendation**
   ```markdown
   ### 🔥 IMMEDIATE EXECUTION (HIGH PRIORITY)

   **SELL all 10 shares of XYZ** - Quality score 6.5/10 below STEPS threshold (7.0).
   Red flags: declining margins, low ROIC. News sentiment negative.
   EXIT from core holdings (STEPS requirement).

   **BUY 10 shares of MSFT** - Quality score 8.8/10 (STEPS: Elite tier).
   Large Cap with 8 years ROE >15% persistence (meets Large Cap requirement).
   News sentiment positive (Azure growth +39% YoY).
   Target position: 12.0% (QUALITY). Stop-loss: -15%, Profit target: +40%.
   ```

6. **Human Review & Approval**
   - Review trading_recommendations.md
   - Decide: Approve the swap (makes sense - upgrade quality by 23 points)
   - Edit manual_trades_override.json:
   ```json
   {
     "enabled": true,
     "trades": [
       {"action": "SELL", "ticker": "XYZ", "shares": 10, "priority": "HIGH"},
       {"action": "BUY", "ticker": "MSFT", "shares": 10, "priority": "HIGH"}
     ]
   }
   ```

7. **Execution (Market Hours)**
   ```bash
   python main.py
   # Executes approved trades
   # SELL XYZ first (generates cash)
   # Then BUY MSFT (uses cash from XYZ sale)
   ```

This complete flow demonstrates how the system discovers opportunities, compares to holdings, integrates news/risk, and generates actionable recommendations—all while keeping you in control of final decisions.

## Understanding Output Files

The STEPS workflow generates multiple output files. Here's what each contains and how to use them.

### 📊 `outputs/quality_watchlist_YYYYMMDD.csv`

**Purpose:** Top quality investment opportunities from S&P 500 screening (STEP 3A).

**Columns:**
| Column | Description | Example | How to Use |
|--------|-------------|---------|------------|
| `ticker` | Stock ticker symbol | NVDA | Company identifier |
| `quality_score` | Composite quality score (0-100) | 90.0 | Higher = better quality |
| `tier` | Quality classification | ELITE | ELITE/STRONG/MODERATE/WEAK |
| `market_cap_tier` | Market cap classification | LARGE_CAP | LARGE/MID/SMALL/MICRO |
| `gross_profitability` | (Rev-COGS)/Assets | 0.45 | Higher = more efficient |
| `roe` | Net Income/Equity | 0.32 | Higher = better returns |
| `operating_profitability` | (Rev-COGS-SG&A)/Assets | 0.38 | Higher = operational efficiency |
| `fcf_yield` | FCF/Market Cap | 0.05 | Higher = better cash generation |
| `roic` | NOPAT/(Debt+Equity) | 0.25 | Higher = capital efficiency |
| `market_cap` | Market capitalization | 2.8e12 | Company size in dollars |
| `sector` | Business sector | Technology | Industry category |
| `red_flags` | Number of quality concerns | 0 | Lower = fewer concerns |

**How to Read:**
```csv
ticker,quality_score,tier,market_cap_tier,gross_profitability,roe,operating_profitability,fcf_yield,roic,market_cap,sector,red_flags
NVDA,90.0,ELITE,LARGE_CAP,0.45,0.32,0.38,0.05,0.25,2800000000000,Technology,0
MSFT,88.0,ELITE,LARGE_CAP,0.42,0.35,0.36,0.04,0.28,3100000000000,Technology,0
GOOGL,85.0,ELITE,LARGE_CAP,0.38,0.25,0.32,0.06,0.24,1900000000000,Communication Services,0
```

**Typical Use:**
- **Top 10-20 rows**: Elite quality opportunities (score ≥85) for immediate consideration
- **Filter by `market_cap_tier`**: Focus on Large/Mid/Small caps based on portfolio needs
- **Check `red_flags`**: Prefer 0-1 red flags, avoid 3+ red flags
- **Compare `quality_score` to holdings**: Look for 15+ point improvements

### 📄 `outputs/quality_analysis_YYYYMMDD.json`

**Purpose:** Complete analysis of holdings quality + BUY/SELL recommendations.

**Structure:**
```json
{
  "holdings_quality": {
    "NVDA": {
      "composite_score": 90.0,
      "tier": "ELITE",
      "market_cap_tier": "LARGE_CAP",
      "roe_persistence_years": 8,
      "incremental_roce": null,
      "roe_trend_quarters": null,
      "strict_filters_passed": null,
      "red_flags": [],
      "metrics": {
        "gross_profitability": 0.45,
        "roe": 0.32,
        "operating_profitability": 0.38,
        "fcf_yield": 0.05,
        "roic": 0.25
      }
    }
  },
  "market_cap_tiers": {
    "NVDA": "LARGE_CAP"
  },
  "roe_persistence": {
    "NVDA": {
      "persistence_years": 8,
      "avg_roe": 0.28,
      "trend": "increasing"
    }
  },
  "strict_filters": {
    "SOME_SMALL_CAP": {
      "passed": true,
      "fcf_positive": true,
      "debt_to_equity_below_1": true,
      "gross_margin_above_30": true
    }
  },
  "recommendations": {
    "sell_candidates": [
      {
        "ticker": "XYZ",
        "quality_score": 65.0,
        "tier": "WEAK",
        "reason": "Quality 65.0 below STEPS threshold (70)",
        "red_flags": ["declining_margins", "low_roic"]
      }
    ],
    "buy_alternatives": [
      {
        "ticker": "MSFT",
        "quality_score": 88.0,
        "tier": "ELITE",
        "market_cap_tier": "LARGE_CAP",
        "reason": "Elite quality 88.0 (STEPS Elite tier ≥85)",
        "red_flags": []
      }
    ]
  }
}
```

**How to Use:**
- **`holdings_quality`**: Check quality score for each current holding
  - Score <70: Consider selling
  - Score 70-84: Monitor, maintain
  - Score ≥85: Hold/add if underweight
- **`roe_persistence`**: Verify tier-specific requirements
  - Large Cap: Need 5+ years ROE >15%
  - Mid Cap: Need 2-3 years ROE >15%
  - Small Cap: Check `strict_filters_passed`
- **`recommendations.sell_candidates`**: Weak holdings to exit
- **`recommendations.buy_alternatives`**: Strong opportunities to add

### 📝 `trading_recommendations/trading_recommendations_YYYYMMDD.md`

**Purpose:** Final trading document with specific BUY/SELL/HOLD orders (template format).

**Sections:**

1. **Document Header**
   ```markdown
   *Date: 2025-11-11*
   *Market Conditions: S&P 500 +1.2%, VIX 15.8 (low volatility), sector rotation to Technology*
   *Portfolio Performance: 8 holdings, $95,432 total value, +12.3% YTD*
   ```

2. **Risk Management Updates**
   ```markdown
   **MAX-POSITION-SIZE 20%** - Maximum single position risk
   **CASH-RESERVE 5%** - Maintain liquidity for opportunities
   **RISK-BUDGET MODERATE** - Balanced approach given MODERATE risk environment
   ```

3. **Orders Section** (by priority)

   **HIGH PRIORITY (Execute First):**
   ```markdown
   **SELL all 10 shares of XYZ** - Quality score 6.5/10 below STEPS threshold (7.0).
   Red flags: declining margins, low ROIC. News sentiment negative.
   EXIT from core holdings (STEPS requirement).

   **BUY 10 shares of MSFT** - Quality score 8.8/10 (STEPS: Elite tier).
   Large Cap with 8 years ROE >15% persistence. News sentiment positive.
   Target position: 12.0% (QUALITY). Stop-loss: -15%, Profit target: +40%.
   ```

   **MEDIUM PRIORITY:**
   ```markdown
   **HOLD all 15 shares of NVDA** - Quality 9.0/10 (STEPS: Elite tier).
   Maintain allocation at 18.5%. News sentiment positive.
   ```

   **LOW PRIORITY:**
   ```markdown
   **BUY 5 shares of GOOGL** - Quality 8.5/10 (STEPS: Elite tier).
   Strategic positioning for long-term growth.
   ```

4. **Market Analysis & Rationale**
   - Current market environment
   - Catalyst calendar (upcoming events)
   - Risk assessment
   - Performance attribution

**How to Use:**
1. Read each section carefully
2. Understand the reasoning for each trade
3. Decide which trades to approve
4. Copy approved trades to `manual_trades_override.json`
5. Set `"enabled": true` to authorize

### 📊 `outputs/market_environment_YYYYMMDD.json`

**Purpose:** Market conditions from STEP 1 (trend, volatility, sector rotation).

**Structure:**
```json
{
  "sp500_price": 5800.45,
  "sp500_50ma": 5650.20,
  "sp500_200ma": 5400.10,
  "sp500_1m_return": 0.025,
  "sp500_ytd_return": 0.18,
  "trend": "BULL",
  "vix_level": 15.8,
  "vix_20ma": 16.5,
  "volatility_regime": "LOW",
  "leading_sectors": ["Technology", "Communication Services", "Consumer Discretionary"],
  "lagging_sectors": ["Energy", "Materials", "Utilities"],
  "sector_performance": {
    "XLK": 0.032,
    "XLC": 0.028,
    "XLY": 0.025,
    ...
  },
  "market_breadth": "MODERATE",
  "risk_appetite": "RISK_ON",
  "summary": "S&P 500 in confirmed BULL trend above 50/200-day MAs. Low volatility (VIX 15.8) supports risk-taking. Technology leading with 3.2% monthly gain.",
  "analysis_date": "2025-11-11"
}
```

**How to Use:**
- **`trend`**: STRONG_BULL/BULL → favor quality growth, BEAR/STRONG_BEAR → favor defensive
- **`volatility_regime`**: LOW → normal position sizing, HIGH → reduce position sizes by 30-50%
- **`risk_appetite`**: RISK_ON → aggressive positioning, RISK_OFF → raise cash to 10-15%
- **`leading_sectors`**: Consider adding exposure to top 3 sectors
- **`market_breadth`**: NARROW → sector-specific risk, BROAD → diversify broadly

### 📋 `outputs/compliance_YYYYMMDD.json`

**Purpose:** Framework validation from STEP 10 (4-tier allocation, position sizing).

**Structure:**
```json
{
  "portfolio_value": 100000.0,
  "compliance_score": 92.0,
  "framework_compliant": true,
  "allocation_quality_pct": 78.0,
  "allocation_thematic_pct": 17.0,
  "allocation_cash_pct": 5.0,
  "violations": [
    {
      "severity": "INFO",
      "category": "ALLOCATION",
      "message": "Quality allocation 78.0% slightly below target range (80% ±5%)",
      "current_value": 78.0,
      "expected_value": 80.0
    }
  ],
  "validation_date": "2025-11-11"
}
```

**Severity Levels:**
- **INFO** (-1 point): Minor deviation, no action needed
- **WARNING** (-5 points): Near threshold, monitor closely
- **CRITICAL** (-20 points): Violation, must fix before trading

**How to Use:**
- **`framework_compliant`**: Must be `true` to execute trades
- **`compliance_score`**: 80+ = good, 60-80 = needs rebalancing, <60 = critical issues
- **`violations`**: Address CRITICAL violations immediately, WARNING within 1 week
- **Target allocation**:
  - Quality: 75-85% (target 80%)
  - Thematic: 15-25% (target 20%)
  - Cash: ≥3% (target 5%)

### 📈 `outputs/data_validation_YYYYMMDD.json`

**Purpose:** Data quality validation from STEP 9 (completeness, freshness).

**Structure:**
```json
{
  "NVDA": {
    "ticker": "NVDA",
    "overall_quality": "COMPLETE",
    "quality_score": 10.0,
    "missing_metrics": [],
    "stale_metrics": [],
    "warnings": [],
    "metrics": [
      {
        "metric_name": "revenue",
        "value": 130500000000,
        "source": "yfinance",
        "fetch_date": "2025-11-11",
        "confidence": "HIGH"
      }
    ],
    "validation_date": "2025-11-11"
  }
}
```

**Quality Classifications:**
- **COMPLETE** (score ≥8.0): All data present and recent, full confidence
- **PARTIAL** (score 5.0-7.9): Some missing/stale data, moderate confidence
- **INSUFFICIENT** (score <5.0): Critical data missing, low confidence, DO NOT TRADE

**How to Use:**
- Check `overall_quality` before trading
- INSUFFICIENT → Skip stock, data too poor
- PARTIAL → Acceptable but monitor closely
- COMPLETE → Full confidence
- Review `stale_metrics` (>90 days old) and consider updating

### Quick Reference: Which File to Use When

| Use Case | File to Check | What to Look For |
|----------|---------------|------------------|
| Find new opportunities | `quality_watchlist_*.csv` | Top 20 rows with score ≥85 |
| Check holding quality | `quality_analysis_*.json` | `holdings_quality` section |
| Identify weak holdings | `quality_analysis_*.json` | `sell_candidates` array |
| Get trading recommendations | `trading_recommendations_*.md` | All sections, copy to override |
| Check market conditions | `market_environment_*.json` | `trend`, `volatility_regime`, `risk_appetite` |
| Verify framework compliance | `compliance_*.json` | `framework_compliant`, `violations` |
| Validate data quality | `data_validation_*.json` | `overall_quality` per ticker |

All JSON files can be loaded into Python for programmatic analysis:
```python
import json

with open('outputs/quality_analysis_20251111.json', 'r') as f:
    data = json.load(f)

# Check if any holdings need to be sold
sell_candidates = data['recommendations']['sell_candidates']
for candidate in sell_candidates:
    print(f"SELL {candidate['ticker']}: {candidate['reason']}")
```

## Common Workflows

Practical workflows for different analysis frequencies and use cases.

### Workflow 1: Daily Quick Check (2-5 minutes)

**Goal:** Quickly identify any urgent opportunities or risks in top S&P 500 stocks.

**When to run:** Every trading day, morning or lunch break.

```bash
cd "Portfolio Scripts Schwab"

# Quick analysis of top 50 S&P 500 stocks
python quality_analysis_script.py --limit 50
```

**What to look for:**
1. Check `outputs/quality_analysis_YYYYMMDD_summary.txt`
2. Look for SELL candidates (holdings with quality <70)
3. Look for BUY alternatives scoring ≥85 (Elite opportunities)
4. If any CRITICAL alerts, investigate further

**Action items:**
- If 0 SELL candidates + 0 Elite alternatives → No action needed
- If SELL candidates found → Flag for weekly review
- If Elite alternative appears → Consider adding to shopping list

**Time:** 2-5 minutes (uses 24-hour cache, no refetching needed)

---

### Workflow 2: Weekly Full Screening (12-17 minutes)

**Goal:** Complete STEPS analysis to generate trading recommendations.

**When to run:** Once per week (recommended: Sunday evening or Monday morning).

```bash
cd "Portfolio Scripts Schwab"

# Full 10-step STEPS analysis
python steps_orchestrator.py

# Review generated recommendations
cat ../trading_recommendations/trading_recommendations_20251111.md
```

**What the system does:**
1. **STEP 1**: Analyze market environment (S&P 500, VIX, sectors)
2. **STEP 2**: Calculate quality for all holdings
3. **STEP 3A**: Screen full S&P 500 (~500 stocks) for opportunities
4. **STEP 3B**: Score thematic/opportunistic positions (optional, use `--skip-thematic` to skip)
5. **STEPS 4-7**: Competitive analysis, valuation, portfolio construction, rebalancing
6. **STEP 8**: AI synthesis (agents make BUY/SELL/HOLD decisions)
7. **STEPS 9-10**: Data validation, framework compliance check

**Output files generated:**
- `trading_recommendations/trading_recommendations_YYYYMMDD.md` ← **Main file**
- `outputs/quality_watchlist_YYYYMMDD.csv` ← Top opportunities
- `outputs/quality_analysis_YYYYMMDD.json` ← Holdings analysis
- `outputs/market_environment_YYYYMMDD.json` ← Market conditions
- `outputs/compliance_YYYYMMDD.json` ← Framework validation

**Review checklist:**
- [ ] Read trading_recommendations.md from top to bottom
- [ ] Understand the reasoning for each recommended trade
- [ ] Check market environment (BULL/BEAR, volatility regime)
- [ ] Verify compliance score ≥80 (framework compliant)
- [ ] Decide which trades to approve

**If you approve trades:**
```bash
# Edit manual override file
nano "Portfolio Scripts Schwab/manual_trades_override.json"

# Add approved trades (copy from trading_recommendations.md)
# Set "enabled": true

# Execute during market hours (Mon-Fri 9:30AM-4PM ET)
python main.py
```

**Time:** 12-17 minutes total (screening 10-15 min, review 2-5 min)

---

### Workflow 3: Monthly Deep Dive (Future: 45-60 minutes)

**Goal:** Comprehensive analysis across S&P 1500 (Large + Mid + Small caps).

**When to run:** Once per month (first Sunday of the month).

**Note:** This workflow requires the configurable watchlist module (coming in Week 2-4).

```bash
cd "Portfolio Scripts Schwab"

# Monthly deep dive with expanded universe
python steps_orchestrator.py --watchlist-index combined_sp

# This screens:
# - S&P 500 (Large Cap: ~500 stocks)
# - S&P MidCap 400 (Mid Cap: ~400 stocks)
# - S&P SmallCap 600 (Small Cap: ~600 stocks)
# Total: ~1,500 stocks
```

**What's different from weekly:**
- **3x more stocks** screened (~1,500 vs ~500)
- **Mid/Small cap focus** - Find quality opportunities outside S&P 500
- **Longer runtime** - 45-60 minutes (vs 12-17 minutes weekly)

**Best practices:**
- Run overnight or during off-hours (long runtime)
- Focus on Small Cap section (highest potential for undiscovered quality)
- Check strict filters for Small Caps (FCF+, D/E<1.0, GP>30%)
- Verify ROE persistence for Mid Caps (2-3 years >15%)

**Unique opportunities:**
- Small caps with quality ≥70 (2-4% position, high growth potential)
- Mid caps with incremental ROCE >5% (5-10% position, emerging quality)

**Time:** 45-60 minutes (screening 40-50 min, review 5-10 min)

---

### Workflow 4: Finding Small Cap Opportunities

**Goal:** Identify high-quality small caps that meet strict STEPS criteria.

**When to run:** After monthly deep dive (when screening S&P 600).

```bash
# Step 1: Screen S&P SmallCap 600 (Future: requires watchlist module)
python quality_analysis_script.py --index sp600

# Step 2: Open CSV and filter
# In Excel/Google Sheets/Python:
import pandas as pd

df = pd.read_csv('outputs/quality_watchlist_20251111.csv')

# Filter for small caps with quality ≥70
small_caps = df[
    (df['market_cap_tier'] == 'SMALL_CAP') &
    (df['quality_score'] >= 70) &
    (df['red_flags'] <= 1)
].sort_values('quality_score', ascending=False)

print(f"Found {len(small_caps)} quality small caps")
print(small_caps[['ticker', 'quality_score', 'sector', 'fcf_yield', 'roe']].head(20))
```

**Additional checks for small caps:**
1. **Strict filters** (from outputs/quality_analysis_*.json):
   ```python
   strict_filters = data['strict_filters'][ticker]
   if strict_filters['passed']:
       print(f"✅ {ticker} passes all strict filters")
       print(f"  FCF Positive: {strict_filters['fcf_positive']}")
       print(f"  D/E < 1.0: {strict_filters['debt_to_equity_below_1']}")
       print(f"  GP > 30%: {strict_filters['gross_margin_above_30']}")
   ```

2. **ROE trend** (6-8 quarters positive):
   ```python
   roe_data = data['roe_persistence'][ticker]
   if roe_data['trend_quarters'] >= 6:
       print(f"✅ {ticker} has {roe_data['trend_quarters']} quarters positive ROE trend")
   ```

3. **News sentiment** (avoid negative catalysts):
   ```python
   # Check news analysis output
   news = news_data['results'][ticker]
   if news['sentiment'] == 'negative':
       print(f"⚠️ {ticker} has negative news sentiment - investigate")
   ```

**Position sizing for small caps:**
- Quality 70-79: 2-3% position
- Quality ≥80: 3-4% position (max for small caps)
- Never exceed 4% for single small cap (higher risk)
- Total small cap allocation: 10-15% of portfolio

---

### Workflow 5: Replacing Weak Holdings

**Goal:** Systematically upgrade portfolio quality by swapping weak holdings for strong alternatives.

**When to run:** After weekly screening, when SELL candidates identified.

```bash
# Step 1: Identify weak holdings
python quality_analysis_script.py

# Step 2: Review sell_candidates
cat outputs/quality_analysis_20251111_summary.txt | grep -A 10 "SELL Candidates"
```

**Example output:**
```
SELL Candidates (2):
1. XYZ - Quality 65.0/10 (WEAK)
   - Reason: Quality 65.0 below STEPS threshold (70)
   - Red flags: declining_margins, low_roic
   - Market Cap Tier: LARGE_CAP

2. ABC - Quality 68.0/10 (WEAK)
   - Reason: Quality 68.0 below STEPS threshold (70)
   - Red flags: excessive_leverage
   - Market Cap Tier: MID_CAP
```

**Step 3: Find replacements from same tier**

For XYZ (Large Cap, quality 65.0):
```bash
# Look for Large Cap alternatives scoring ≥80
cat outputs/quality_watchlist_20251111.csv | grep "LARGE_CAP" | head -20
```

**Comparison criteria:**
- [ ] Alternative quality ≥80 (15+ points better than XYZ 65.0)
- [ ] Same market cap tier (LARGE_CAP)
- [ ] Red flags ≤1 (XYZ has 2)
- [ ] Positive news sentiment (check outputs/news_analysis_*.json)
- [ ] Meets tier-specific requirements (5+ years ROE >15% for Large Cap)

**Example: Replacing XYZ (quality 65.0) with MSFT (quality 88.0)**

Decision rationale:
- Quality improvement: +23 points (88.0 - 65.0)
- Red flags improvement: 0 vs 2
- Both Large Cap (same tier, same position sizing rules)
- MSFT: 8 years ROE >15% (meets Large Cap requirement)
- News sentiment: MSFT positive, XYZ negative

**Step 4: Execute swap**
```json
{
  "enabled": true,
  "trades": [
    {
      "action": "SELL",
      "ticker": "XYZ",
      "shares": 10,
      "reason": "Quality 65.0 below threshold, 2 red flags",
      "priority": "HIGH"
    },
    {
      "action": "BUY",
      "ticker": "MSFT",
      "shares": 10,
      "reason": "Quality 88.0, Elite tier, +23 improvement over XYZ",
      "priority": "HIGH"
    }
  ]
}
```

---

### Workflow 6: Risk Management Check

**Goal:** Verify portfolio is within risk parameters before trading.

**When to run:** Before executing any trades.

```bash
# Check framework compliance
cat outputs/compliance_20251111.json | python -m json.tool | grep -A 5 "framework_compliant"

# Check data quality
cat outputs/data_validation_20251111.json | python -m json.tool | grep "overall_quality"

# Check market environment
cat outputs/market_environment_20251111.json | python -m json.tool | grep -E "(trend|volatility_regime|risk_appetite)"
```

**Risk checkpoints:**

1. **Framework Compliance** (CRITICAL - must pass)
   ```json
   {
     "framework_compliant": true,  // Must be true
     "compliance_score": 92.0,      // ≥80 recommended
     "violations": []               // No CRITICAL violations
   }
   ```
   - If `framework_compliant: false` → **DO NOT TRADE** until fixed
   - If `compliance_score < 60` → Rebalance before adding new positions

2. **Data Quality** (CRITICAL - must be COMPLETE or PARTIAL)
   ```json
   {
     "NVDA": {
       "overall_quality": "COMPLETE"  // COMPLETE/PARTIAL acceptable, INSUFFICIENT not
     }
   }
   ```
   - If any ticker shows `INSUFFICIENT` → Skip that ticker
   - If multiple tickers `PARTIAL` → Consider waiting for data refresh

3. **Market Environment** (Adjust position sizing)
   ```json
   {
     "trend": "BULL",                    // BULL → normal sizing, BEAR → reduce
     "volatility_regime": "LOW",         // LOW → normal, HIGH → reduce 30-50%
     "risk_appetite": "RISK_ON"          // RISK_ON → aggressive, RISK_OFF → defensive
   }
   ```

   **Position sizing adjustments:**
   | Market Condition | Action |
   |------------------|--------|
   | BULL + LOW Vol + RISK_ON | Normal position sizes (use STEPS recommendations) |
   | BEAR + HIGH Vol + RISK_OFF | Reduce all positions by 30-50%, raise cash to 15% |
   | Mixed conditions | Moderate adjustment (-20%), be selective |

**Example risk adjustment:**
```
Original recommendation: BUY 10 shares NVDA (12% position)
Market: BEAR, HIGH volatility, RISK_OFF

Adjusted: BUY 6 shares NVDA (7.2% position, 40% reduction)
Reasoning: High volatility reduces position size, maintain quality but lower risk
```

---

### Workflow 7: Portfolio Rebalancing

**Goal:** Bring portfolio back to 4-tier framework targets.

**When to run:** Quarterly, or when compliance score <80.

```bash
# Check current allocation
cat outputs/compliance_20251111.json | python -m json.tool
```

**Target allocation (from quality_investing_thresholds_research.md):**
- Quality: 75-85% (target 80%)
- Thematic: 15-25% (target 20%)
- Cash: ≥3% (target 5%)

**Example rebalancing scenario:**

Current allocation:
- Quality: 72% (**below** 75% minimum)
- Thematic: 23% (within range)
- Cash: 5% (target)

**Action plan:**
1. Identify underweight quality positions
2. Add to top-rated quality holdings (score ≥85)
3. Or sell lowest-quality thematic positions to buy quality

```bash
# Find top quality opportunities to add
head -10 outputs/quality_watchlist_20251111.csv
# Focus on tickers scoring 85-100

# Manual trades to increase quality allocation to 80%
# Need to add 8% quality exposure
# If portfolio value = $100,000, need $8,000 more quality positions
```

---

### Quick Reference: When to Use Each Workflow

| Frequency | Workflow | Runtime | Purpose |
|-----------|----------|---------|---------|
| **Daily** | Quick Check | 2-5 min | Catch urgent opportunities/risks |
| **Weekly** | Full Screening | 12-17 min | Generate trading recommendations |
| **Monthly** | Deep Dive | 45-60 min | Find small/mid cap opportunities |
| **As needed** | Small Cap Search | 10-15 min | Focus on small cap universe |
| **As needed** | Replace Weak Holdings | 15-20 min | Systematic quality upgrade |
| **Before trading** | Risk Management Check | 5 min | Verify safe to trade |
| **Quarterly** | Portfolio Rebalancing | 20-30 min | Maintain framework compliance |

## Watchlist Configuration

The system supports flexible watchlist screening across multiple stock indexes to find opportunities across different market cap tiers.

### Supported Indexes

| Index | Tickers | Market Cap | Use Case | Runtime |
|-------|---------|------------|----------|---------|
| **SP500** | ~500 | Large Cap (≥$50B) | Weekly screening | 12-17 min |
| **SP400** | ~400 | Mid Cap ($2B-$50B) | Mid-cap opportunities | 10-14 min |
| **SP600** | ~600 | Small Cap ($500M-$2B) | Small-cap discovery | 15-20 min |
| **NASDAQ100** | ~100 | Tech Focus | Tech sector analysis | 3-5 min |
| **COMBINED_SP** | ~1,500 | All Tiers | Monthly deep dive | 45-60 min |

### Configuration Examples

**Daily Quick Check (50 tickers):**
```bash
python quality_analysis_script.py --index sp500 --limit 50
```

**Weekly Full Screening (S&P 500):**
```bash
python steps_orchestrator.py --watchlist-index sp500
```

**Monthly Deep Dive (S&P 1,500 - all market caps):**
```bash
python steps_orchestrator.py --watchlist-index combined_sp
```

**Focus on Mid-Caps:**
```bash
python watchlist_generator_script.py --index sp400
```

**Focus on Small-Caps:**
```bash
python watchlist_generator_script.py --index sp600
```

### Configuration in Code

```python
from watchlist_config import WatchlistConfig, WatchlistIndex

# Configure in hf_config.py
WATCHLIST_CONFIG = WatchlistConfig(index=WatchlistIndex.SP500)

# Or use different index
WATCHLIST_CONFIG = WatchlistConfig(index=WatchlistIndex.COMBINED_SP)

# With limit for faster analysis
WATCHLIST_CONFIG = WatchlistConfig(index=WatchlistIndex.SP500, limit=50)
```

**For detailed configuration options, see:** [`Portfolio Scripts Schwab/WATCHLIST_CONFIGURATION_GUIDE.md`](Portfolio%20Scripts%20Schwab/WATCHLIST_CONFIGURATION_GUIDE.md)

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