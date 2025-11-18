# STEPS Analysis Flow Tracking Document

**Command**: `python main.py --steps`

This document tracks the complete flow when running STEPS analysis, including which files are called, their inputs/outputs, and which agents are utilized.

---

## 🎯 High-Level Overview

```
main.py --steps
    ↓
STEPSOrchestrator (analysis/steps_orchestrator.py)
    ↓
[10 STEPS executed sequentially]
    ↓
trading_recommendations.md (output)
```

---

## 📋 Detailed Flow with Agents

### ENTRY POINT: `main.py --steps`

**File**: `Portfolio Scripts Schwab/main.py`
**Line**: 435-470

**What It Does**:
- Parses `--steps` command line argument
- Initializes `STEPSOrchestrator`
- Calls `orchestrator.run_full_analysis()`

**Configuration**:
```python
STEPSOrchestrator(
    skip_thematic=False,      # Enable thematic agent
    skip_competitive=True,    # Skip optional competitive analysis
    skip_valuation=True,      # Skip optional valuation analysis
    dry_run=False            # Generate output files
)
```

---

### ORCHESTRATOR: `STEPSOrchestrator`

**File**: `Portfolio Scripts Schwab/analysis/steps_orchestrator.py`
**Method**: `run_full_analysis()`

**Input**:
- `portfolio_state.json` (current holdings)
- Configuration parameters (watchlist index, skip flags)

**Output**:
- `trading_recommendations/trading_recommendations_YYYYMMDD.md`

**Orchestrates**: 10 sequential STEPS (detailed below)

---

## 🔬 STEP-BY-STEP EXECUTION

### STEP 1: Market Environment Assessment

**File**: `analyzers/market_environment_analyzer.py`
**Class**: `MarketEnvironmentAnalyzer`

**Input**:
- Schwab API (S&P 500, VIX, sector ETFs)
- yfinance fallback (if Schwab fails)

**Processing**:
- Fetches S&P 500 price, 50MA, 200MA
- Fetches VIX current and 20-day average
- Fetches 11 sector ETF prices (XLK, XLC, XLV, XLF, XLE, XLI, XLP, XLY, XLU, XLRE, XLB)
- Classifies market trend (STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR)
- Classifies volatility regime (LOW, MODERATE, ELEVATED, HIGH)
- Determines market breadth (NARROW, MODERATE, BROAD)
- Determines risk appetite (RISK_ON, NEUTRAL, RISK_OFF)

**Output**:
- `outputs/market_environment_YYYYMMDD.json`
- `outputs/market_environment_YYYYMMDD.md`
- Returns `MarketEnvironment` object

**Agents Used**: None (data fetching only)

---

### STEP 2: Holdings Quality Analysis & Market Cap Classification

**File**: `analysis/quality_analysis_script.py`
**Class**: `QualityAnalysisScript`

**Subprocess Call**: `python quality_analysis_script.py --index combined_sp`

**Input**:
- `portfolio_state.json` (holdings to analyze)
- WatchlistConfig (combined_sp = S&P 1500)

**Processing**:
- **QUALITY AGENT** calculates 5 quality metrics for each holding:
  1. Gross Profitability (30% weight)
  2. Return on Equity (25% weight)
  3. Operating Profitability (20% weight)
  4. FCF Yield (15% weight)
  5. ROIC (10% weight)
- Composite quality score (0-100 scale)
- Market cap classification (Large/Mid/Small)
- ROE persistence analysis (5-year history)
- Strict filters validation (FCF+, D/E<1.0, GP>30%)

**Output**:
- `outputs/quality_analysis.json` (fixed filename - no timestamp)
- `outputs/quality_analysis_summary.txt`
- Returns quality scores dict

**Agents Used**:
- ✅ **Quality Agent** (`quality/quality_metrics_calculator.py`)
- ✅ **Quality Persistence Analyzer** (`analyzers/quality_persistence_analyzer.py`)

---

### STEP 3A: Core Quality Screening

**File**: `analysis/watchlist_generator_script.py`
**Class**: `WatchlistGenerator`

**Subprocess Call**: `python watchlist_generator_script.py --index combined_sp`

**Input**:
- WatchlistConfig (combined_sp = ~1,500 tickers from S&P 1500)
- Min quality score threshold (70.0 by default)

**Processing**:
- **QUALITY AGENT** screens 1,500 tickers from S&P 1500
- Filters by min quality score ≥70
- Ranks by composite quality score
- Parallel processing (10 workers)

**Output**:
- `outputs/quality_watchlist.csv` (fixed filename)
- `outputs/quality_watchlist_full.json`
- `outputs/quality_watchlist_summary.txt`
- Returns list of quality candidates

**Agents Used**:
- ✅ **Quality Agent** (`quality/quality_metrics_calculator.py`)

---

### STEP 3B: Thematic Opportunity Discovery

**File**: `analysis/thematic_analysis_script.py`
**Class**: `ThematicAnalysisScript`

**Subprocess Call**: `python thematic_analysis_script.py`

**Input**:
- Portfolio holdings (from STEP 2)
- yfinance data for each holding

**Processing**:
- **THEMATIC AGENT** identifies theme keywords in business descriptions
- Supported themes:
  1. AI Infrastructure (GPU, data center, cloud)
  2. Nuclear Renaissance (SMR, uranium)
  3. Defense Modernization (drones, cyber, space)
  4. Climate Technology (EV, renewable, carbon capture)
  5. Longevity/Biotech (GLP-1, aging therapies)
- Heuristic scoring algorithm (5 dimensions × 10 points = 50 max)
- Classification: Leader (40-50), Strong Contender (30-39), Contender (28-29), Laggard (<28)

**Output**:
- `outputs/thematic_analysis_YYYYMMDD.json`
- `outputs/thematic_analysis_YYYYMMDD_summary.txt`
- Returns thematic scores dict

**Agents Used**:
- ✅ **Thematic Agent** (`analyzers/thematic_prompt_builder.py`)

**Note**: This STEP is OPTIONAL (controlled by `--skip-thematic` flag)

---

### STEP 4: Competitive Analysis

**Status**: ⏭️ **SKIPPED** (optional step, not yet implemented)

**Future Implementation**: Compare holdings against direct competitors in same sector

---

### STEP 5: Valuation Analysis

**Status**: ⏭️ **SKIPPED** (optional step, not yet implemented)

**Future Implementation**: Assess whether holdings are reasonably valued (P/E, PEG, EV/EBITDA)

---

### STEP 6: Portfolio Construction (4-Tier Framework)

**File**: `analyzers/portfolio_constructor.py`
**Class**: `PortfolioConstructor`

**Input**:
- Quality scores (from STEP 2)
- Thematic scores (from STEP 3B)
- Market cap tiers (from STEP 2)
- Portfolio state

**Processing**:
- Classifies holdings into 4 tiers:
  - **Large Cap** (65-70% target): ROE>15% for 5+ years, quality≥75
  - **Mid Cap** (15-20% target): ROE>15% for 2-3 years, incremental ROCE+5%, quality≥70
  - **Small Cap** (10-15% target): 6-8 quarters ROE trend, FCF+, D/E<1.0, GP>30%, quality≥65
  - **Thematic** (5-10% target): Thematic score≥28/40
- Calculates target position sizes within each tier
- Generates rebalancing trades to reach target allocation
- Sets risk parameters (stop-losses, profit targets) by tier

**Output**:
- `outputs/portfolio_allocation_YYYYMMDD.json`
- `outputs/rebalancing_trades_YYYYMMDD.json`
- Returns allocation object with violations

**Agents Used**: None (mathematical calculation only)

**Note**: Currently has implementation issues (reported error: "Missing quality scores or market cap tiers")

---

### STEP 7: Rebalancing Trades

**Status**: ⚠️ **NOT YET IMPLEMENTED**

**Future Implementation**: Generate specific buy/sell orders to move from current to target allocation

---

### STEP 8: Trade Synthesis (Reasoning Agent)

**File**: `analysis/recommendation_generator_script.py`
**Class**: `RecommendationGeneratorScript`

**Subprocess Call**: `python recommendation_generator_script.py`

**Input**:
- `portfolio_state.json`
- `outputs/news_analysis.json` (if available)
- `outputs/quality_analysis.json` (from STEP 2)
- `outputs/thematic_analysis_YYYYMMDD.json` (from STEP 3B)

**Processing**:
1. Loads all analysis outputs
2. Runs **Market Agent**, **Risk Agent**, **Tone Agent** for portfolio-level analysis
3. For each stock, synthesizes all data and runs **Reasoning Agent**:
   - Inputs: quality score, thematic score, news sentiment, market context
   - Decision logic:
     - Quality <70 → SELL
     - Thematic <28 → SELL
     - Red flags >3 → SELL
     - Quality ≥85 AND not holding → BUY
     - News negative AND quality <75 → SELL
     - Otherwise → HOLD
   - Position sizing based on quality/thematic scores
   - Risk parameters (stop-loss, profit target) by tier
4. Generates markdown document in trading_template.md format

**Output**:
- `trading_recommendations/trading_recommendations_YYYYMMDD.md`
- Returns path to recommendations file

**Agents Used**:
- ✅ **Market Agent** (`agents/market_agent.py` - FinBERT for market sentiment)
- ✅ **Risk Agent** (`agents/risk_agent.py` - FinBERT for risk assessment)
- ✅ **Tone Agent** (`agents/tone_agent.py` - FinBERT for market tone)
- ✅ **Reasoning Agent** (`agents/reasoning_agent.py` - DeepSeek-R1 for BUY/SELL/HOLD decisions)

**HuggingFace Models**:
- Market: `StephanAkkerman/FinTwitBERT`
- Risk: `ProsusAI/finbert`
- Tone: `yiyanghkust/finbert-tone`
- Reasoning: DeepSeek-R1-Distill-Qwen-14B (local or API)

**Note**: HuggingFace API endpoint is deprecated (HTTP 410 errors observed). Agents gracefully fallback to neutral/conservative defaults when API fails.

---

### STEP 9: Data Quality Validation

**File**: `validators/data_validator.py`
**Class**: `DataValidator`

**Input**:
- Holdings from portfolio_state.json
- yfinance financial data

**Processing**:
- Validates 9 required metrics:
  1. revenue
  2. cogs
  3. total_assets
  4. shareholder_equity
  5. operating_income
  6. net_income
  7. operating_cash_flow
  8. total_debt
  9. market_cap
- Detects missing metrics (-2 points each)
- Detects stale data >90 days old (-1 point each)
- Validates data consistency (negative values, margin ranges)
- Calculates quality score (0-10)
- Classification: COMPLETE (≥8.0), PARTIAL (5.0-7.9), INSUFFICIENT (<5.0)

**Output**:
- `outputs/data_validation_20251114.json`
- `outputs/data_validation_20251114_summary.md`
- Returns validation reports

**Agents Used**: None (data validation only)

**Note**: Observed rate limiting from yfinance ("Too Many Requests")

---

### STEP 10: 4-Tier Framework Validation

**File**: `validators/framework_validator.py`
**Class**: `FrameworkValidator`

**Input**:
- Portfolio state
- Quality scores (from STEP 2)
- Thematic scores (from STEP 3B)
- Holdings types (QUALITY vs THEMATIC)

**Processing**:
- Validates 4-tier allocation:
  - Large Cap: 62.5-72.5% (target 67.5%, ±5% tolerance)
  - Mid Cap: 12.5-22.5% (target 17.5%, ±5% tolerance)
  - Small Cap: 7.5-17.5% (target 12.5%, ±5% tolerance)
  - Thematic: 2.5-12.5% (target 7.5%, ±5% tolerance)
  - Cash: ≥3% minimum
- Validates position sizing:
  - Large Cap: 8-15% per position
  - Mid Cap: 5-10% per position
  - Small Cap: 2-4% per position
  - Thematic: 1.5-2.5% per position
- Validates quality thresholds:
  - Quality holdings: score ≥70
  - Thematic holdings: score ≥28
- Calculates compliance score (starts at 100, penalties applied)
- Framework compliant: True if no CRITICAL violations

**Output**:
- `outputs/compliance_20251114.json`
- `outputs/compliance_20251114.md`
- Returns compliance report

**Agents Used**: None (compliance validation only)

---

## 📊 Final Output: Trading Recommendations Document

**File**: `trading_recommendations/trading_recommendations_YYYYMMDD.md`

**Format**: Follows `trading_template.md` specification

**Structure**:
1. **Document Header**
   - Date
   - Market conditions summary
   - Portfolio performance

2. **Risk Management Updates**
   - Dynamic risk parameters (stop-losses, profit targets, position limits, cash reserve)
   - Position-specific risk adjustments

3. **Orders Section** (3 priority levels):
   - 🔥 HIGH PRIORITY: Immediate execution
   - ⚖️ MEDIUM PRIORITY: Position management
   - 📈 LOW PRIORITY: Strategic positioning

4. **Market Analysis & Rationale**
   - Current market environment
   - Catalyst calendar
   - Risk assessment
   - Performance attribution

5. **Strategic Allocation Targets**
   - Target portfolio composition (Growth/Value/Defensive/Speculative/Cash)
   - Sector allocation targets

6. **Execution Notes**
   - Cash flow management
   - Timing considerations
   - Partial fill instructions

**Syntax**:
- `**BUY [XXX] shares of [TICKER]** - [reasoning]`
- `**SELL [XXX] shares of [TICKER]** - [reasoning]`
- `**HOLD all [XXX] shares of [TICKER]** - [reasoning]`
- `**SET STOP-LOSS [TICKER] -[XX]%** - [reasoning]`
- `**UPDATE PROFIT-TARGET [TICKER] +[XX]%** - [reasoning]`

---

## 🤖 Agent Summary

### Agents Utilized by STEPS:

1. **Quality Agent** (`quality/quality_metrics_calculator.py`)
   - **Used In**: STEP 2, STEP 3A
   - **Purpose**: Calculate 5 quality metrics, composite score, tier classification
   - **Technology**: Offline calculation (no API)
   - **Output**: Quality scores (0-100 scale)

2. **Thematic Agent** (`analyzers/thematic_prompt_builder.py`)
   - **Used In**: STEP 3B
   - **Purpose**: Score holdings on thematic fit (5 themes)
   - **Technology**: Keyword matching + heuristic scoring
   - **Output**: Thematic scores (0-50 scale)

3. **Market Agent** (`agents/market_agent.py`)
   - **Used In**: STEP 8 (Trade Synthesis)
   - **Purpose**: Analyze overall market sentiment
   - **Technology**: FinBERT (`StephanAkkerman/FinTwitBERT`) via HuggingFace API
   - **Output**: Market sentiment (bullish/bearish/neutral)

4. **Risk Agent** (`agents/risk_agent.py`)
   - **Used In**: STEP 8 (Trade Synthesis)
   - **Purpose**: Assess portfolio risk level
   - **Technology**: FinBERT (`ProsusAI/finbert`) via HuggingFace API
   - **Output**: Risk level (low/medium/high)

5. **Tone Agent** (`agents/tone_agent.py`)
   - **Used In**: STEP 8 (Trade Synthesis)
   - **Purpose**: Determine market tone
   - **Technology**: FinBERT (`yiyanghkust/finbert-tone`) via HuggingFace API
   - **Output**: Market tone (bullish/bearish/neutral)

6. **Reasoning Agent** (`agents/reasoning_agent.py`)
   - **Used In**: STEP 8 (Trade Synthesis)
   - **Purpose**: Synthesize all analysis into BUY/SELL/HOLD decisions
   - **Technology**: DeepSeek-R1-Distill-Qwen-14B (reasoning model)
   - **Decision Logic**:
     - Thematic <28 → SELL
     - Quality <70 → SELL
     - Red flags >3 → SELL
     - Quality ≥85 + not holding → BUY
     - News negative + quality <75 → SELL
     - Otherwise → HOLD
   - **Output**: Trade recommendations with position sizing and risk parameters

7. **News Agent** (`agents/news_agent.py`)
   - **Used In**: Optional pre-processing (not in core STEPS flow)
   - **Purpose**: Analyze news sentiment per ticker
   - **Technology**: FinBERT (`mrm8488/distilroberta-finetuned-financial-news-sentiment`)
   - **Output**: News sentiment scores

**Note**: Quality Agent and Thematic Agent are "passive agents" (offline calculation). Market/Risk/Tone/Reasoning/News are "active agents" (API-based).

---

## 🔧 Configuration & Customization

### Watchlist Configuration

**File**: `data/watchlist_config.py`

**Options**:
- `sp500` - S&P 500 (~500 large cap stocks)
- `sp400` - S&P MidCap 400 (~400 mid cap stocks)
- `sp600` - S&P SmallCap 600 (~600 small cap stocks)
- `nasdaq100` - NASDAQ-100 (~100 tech stocks)
- `combined_sp` - S&P Composite 1500 (~1,500 stocks across all caps) **[DEFAULT]**

**Configuration in Orchestrator**:
```python
STEPSOrchestrator(
    watchlist_config=WatchlistConfig(
        index=WatchlistIndex.COMBINED_SP,  # Screen 1,500 stocks
        limit=None  # No limit (screen all)
    )
)
```

### Skip Flags

- `skip_thematic=False` - Run thematic analysis (STEP 3B)
- `skip_competitive=True` - Skip competitive analysis (STEP 4) [not implemented]
- `skip_valuation=True` - Skip valuation analysis (STEP 5) [not implemented]

### Output Mode

- `dry_run=False` - Generate output files
- `dry_run=True` - Simulate without writing files

---

## ⚠️ Known Issues & Limitations

1. **HuggingFace API Deprecated**
   - Endpoint `https://api-inference.huggingface.co` returns HTTP 410
   - New endpoint: `https://router.huggingface.co/hf-inference`
   - **Impact**: Market/Risk/Tone agents fallback to neutral/conservative defaults

2. **HuggingFace Token Not Set**
   - User reported: "I have not entered my Huggingface information"
   - **Impact**: Agents are called but may have limited API access or use fallback logic

3. **News Agent Not in Core Flow**
   - News analysis is optional pre-processing step
   - Not automatically called by STEPS orchestrator
   - Must run `python news_analysis_script.py` separately if news data is needed

4. **STEP 6 Implementation Issues**
   - Portfolio constructor reports: "Missing quality scores or market cap tiers"
   - **Impact**: 4-tier allocation and rebalancing trades not generated correctly

5. **STEP 7 Not Implemented**
   - Rebalancing trade generation is a placeholder
   - **Impact**: No specific buy/sell orders to reach target allocation

6. **yfinance Rate Limiting**
   - Data validator reports: "Too Many Requests" for NVDA and GOOGL
   - **Impact**: Data quality validation may be incomplete for some tickers

7. **Timestamp Files in Some Outputs**
   - Quality and watchlist files now use fixed filenames (Task 1 complete)
   - But thematic, data_validation, compliance still use timestamps
   - **Impact**: Multiple dated files accumulate in outputs/

---

## 🎯 Verification Checklist

Based on user requirement: "I want to be able to confirm quality, news, and thematic agents are being used and the reasoning agent is being used."

- ✅ **Quality Agent**: Used in STEP 2 (holdings analysis) and STEP 3A (watchlist screening)
- ⚠️ **News Agent**: NOT in core STEPS flow (must run news_analysis_script.py separately)
- ✅ **Thematic Agent**: Used in STEP 3B (thematic scoring) [if `--skip-thematic` not set]
- ✅ **Reasoning Agent**: Used in STEP 8 (trade synthesis with BUY/SELL/HOLD decisions)

**Additional Agents**:
- ✅ **Market Agent**: Used in STEP 8 (portfolio-level sentiment)
- ✅ **Risk Agent**: Used in STEP 8 (portfolio risk assessment)
- ✅ **Tone Agent**: Used in STEP 8 (market tone detection)

---

## 📁 Output Files Generated

| File | Location | Description |
|------|----------|-------------|
| `quality_analysis.json` | `outputs/` | Holdings quality scores (STEP 2) |
| `quality_analysis_summary.txt` | `outputs/` | Human-readable quality summary |
| `quality_watchlist.csv` | `outputs/` | Screened quality candidates (STEP 3A) |
| `quality_watchlist_full.json` | `outputs/` | Full watchlist data |
| `quality_watchlist_summary.txt` | `outputs/` | Watchlist summary |
| `thematic_analysis_YYYYMMDD.json` | `outputs/` | Thematic scores (STEP 3B) |
| `thematic_analysis_YYYYMMDD_summary.txt` | `outputs/` | Thematic summary |
| `data_validation_YYYYMMDD.json` | `outputs/` | Data quality validation (STEP 9) |
| `data_validation_YYYYMMDD_summary.md` | `outputs/` | Data quality summary |
| `compliance_YYYYMMDD.json` | `outputs/` | Framework compliance (STEP 10) |
| `compliance_YYYYMMDD.md` | `outputs/` | Compliance summary |
| `trading_recommendations_YYYYMMDD.md` | `trading_recommendations/` | Final trading document (STEP 8) |

---

## 🔄 Next Steps After Analysis

1. **Review Recommendations**:
   ```bash
   cat trading_recommendations/trading_recommendations_20251114.md
   ```

2. **Approve Trades** (edit manual override file):
   ```bash
   nano "Portfolio Scripts Schwab/manual_trades_override.json"
   # Copy approved trades from recommendations
   # Set "enabled": true
   ```

3. **Execute Trades** (requires market hours):
   ```bash
   python main.py
   ```

---

## 📚 References

- **Research Methodology**: `docs/research/quality_investing_thresholds_research.md`
- **Trading Template**: `/trading_template.md`
- **STEPS Documentation**: `docs/STEPS_Research_Methodology_November_1_2025.md` (if exists)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Command Tested**: `python main.py --steps`
