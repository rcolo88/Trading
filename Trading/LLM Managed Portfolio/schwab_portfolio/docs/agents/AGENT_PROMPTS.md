# Agent System Implementation Prompts

## Overview
This document contains sequential prompts for Claude Code to transform the agent system from analyzing portfolio state to actively discovering investment opportunities using live news and financial data.

**Current Problem**: Agents analyze existing portfolio without live data sources
**Target Architecture**: Agents consume live news + financials → generate trading_template.md with HOLD or BETTER alternatives

---

## PROMPT 1: Build News Fetcher Module

### Objective
Create `Portfolio Scripts Schwab/news_fetcher.py` to fetch real-time news from reliable APIs without hallucination.

### Requirements
1. **Primary Data Source**: Use `yfinance` for Yahoo Finance news (free, unlimited, no API key required)
2. **Fallback Source** (optional): NewsAPI or Finnhub if yfinance insufficient
3. **Target Companies**:
   - Fetch news for all current holdings (from portfolio_state.json)
   - Fetch news for watchlist tickers (configurable list in hf_config.py)
4. **Output Format**: Return structured list of news items per ticker:
   ```python
   {
       "NVDA": [
           {
               "title": "Nvidia announces new AI chip",
               "published": "2025-10-31T10:30:00Z",
               "source": "Reuters",
               "url": "https://...",
               "summary": "Brief summary...",
               "relevance": 0.95  # confidence score if available
           }
       ]
   }
   ```
5. **Anti-Hallucination**:
   - Only return actual fetched news (no LLM generation)
   - Validate timestamps (reject future dates)
   - Deduplicate by title similarity
   - Filter by recency (last 7 days only)
6. **Error Handling**:
   - Handle API rate limits gracefully
   - Return empty list if no news found (don't fail)
   - Log all API errors
7. **Performance**:
   - Cache results for 4 hours (news doesn't change that fast)
   - Batch requests where possible
   - Target <30 seconds for 10-20 tickers

### Integration Points
- Import existing `hf_config.py` for watchlist configuration
- Add `WATCHLIST_TICKERS` to hf_config.py (list of tickers to monitor)
- Add caching using same mechanism as base_agent.py

### Testing
Create `test_news_fetcher.py` that:
- Fetches news for 3 test tickers (NVDA, AAPL, TSLA)
- Validates output structure
- Checks for duplicates
- Verifies timestamp recency

---

## PROMPT 2: Build Financial Analysis Module

### Objective
Create `Portfolio Scripts Schwab/financial_analyzer.py` to fetch and calculate financial metrics for current holdings AND alternatives.

### Requirements
1. **Data Source**: Use `yfinance` for all financial data (already installed)
2. **Metrics to Calculate**:
   - Quality Metrics (use existing `quality_metrics_calculator.py`)
     - Gross Profitability, ROE, Operating Profitability, FCF Yield, ROIC
     - Composite quality score (0-100)
     - Red flag detection
   - Thematic Metrics (use existing `thematic_prompt_builder.py`)
     - Generate prompts for selected themes
     - Store prompts for LLM evaluation
   - Catalyst Data (use existing `catalyst_analyzer.py`)
     - Extract upcoming earnings dates
     - Extract known events from news
3. **Target Companies**:
   - All current holdings (from portfolio_state.json)
   - All watchlist tickers (from hf_config.py)
4. **Output Format**:
   ```python
   {
       "NVDA": {
           "basic_info": {
               "market_cap": 1200000000000,
               "sector": "Technology",
               "industry": "Semiconductors",
               "current_price": 450.25,
               "pe_ratio": 45.5
           },
           "quality": {
               "score": 85.5,
               "tier": "Elite",
               "gross_profitability": 0.62,
               "roe": 0.35,
               "roic": 0.28,
               "fcf_yield": 0.025,
               "red_flags": []
           },
           "thematic_prompts": {
               "AI Infrastructure": "...",  # Generated prompt
           },
           "catalysts": {
               "next_earnings": "2025-11-20",
               "upcoming_events": []
           },
           "in_portfolio": True,
           "current_shares": 10
       }
   }
   ```
5. **Anti-Hallucination**:
   - Only use yfinance data (no LLM generation of financials)
   - Handle missing data gracefully (set to None, don't guess)
   - Validate data ranges (reject impossible values like negative revenue)
   - Cross-check calculated metrics with yfinance reported metrics
6. **Error Handling**:
   - Handle missing tickers gracefully
   - Handle incomplete financial data (set metrics to None)
   - Log all failures
7. **Performance**:
   - Cache yfinance data for 4 hours
   - Process tickers in parallel where possible
   - Target <60 seconds for 20 tickers

### Integration Points
- Reuse `quality_metrics_calculator.py` (no changes needed)
- Reuse `thematic_prompt_builder.py` (no changes needed)
- Reuse `catalyst_analyzer.py` for earnings extraction
- Add caching mechanism

### Testing
Create `test_financial_analyzer.py` that:
- Analyzes 3 test tickers (NVDA, AAPL, MSFT)
- Validates quality scores are 0-100
- Validates all metrics are reasonable
- Handles missing data ticker gracefully

---

## PROMPT 3: Build Watchlist Configuration

### Objective
Enhance `Portfolio Scripts Schwab/hf_config.py` to include watchlist and screening parameters.

### Requirements
1. **Add Watchlist Tickers**:
   ```python
   # Watchlist: Tickers to monitor for potential buys
   WATCHLIST_TICKERS = [
       # AI Infrastructure
       "NVDA", "AMD", "SMCI", "DELL", "AVGO",
       # Nuclear Renaissance
       "SMR", "OKLO", "NNE", "CCJ", "UEC",
       # Defense Modernization
       "PLTR", "ASTS", "RKLB", "LMT", "NOC",
       # Climate Tech
       "TSLA", "ENPH", "RUN", "NEE", "AES",
       # Longevity/Biotech
       "LLY", "NVO", "IONS", "CRSP", "EDIT"
   ]
   ```
2. **Add Screening Thresholds**:
   ```python
   # Quality thresholds for core portfolio (80% allocation)
   QUALITY_MIN_SCORE = 70  # Minimum quality score for core holdings
   QUALITY_IDEAL_SCORE = 85  # Ideal score for elite compounders

   # Thematic thresholds for opportunistic portfolio (20% allocation)
   THEMATIC_MIN_SCORE = 28  # Minimum thematic score (out of 50)
   THEMATIC_IDEAL_SCORE = 40  # Leader-level thematic score

   # Position sizing rules
   MAX_POSITION_SIZE = 0.20  # 20% max per position
   MAX_OPPORTUNISTIC_ALLOCATION = 0.20  # 20% total for thematic
   MIN_CASH_RESERVE = 0.05  # 5% minimum cash
   ```
3. **Add Active Themes**:
   ```python
   # Active themes for opportunistic screening
   ACTIVE_THEMES = [
       "AI Infrastructure",
       "Nuclear Renaissance",
       "Defense Modernization"
   ]
   ```

### Integration
- No new files needed, just enhance existing `hf_config.py`
- Agents will import these constants

---

## PROMPT 4: Enhance Agent Prompts for Live Data

### Objective
Update agent prompt generation to consume live news and financial data instead of just portfolio state.

### Requirements
1. **Update News Agent** (`agents/news_agent.py`):
   - Accept news items from news_fetcher.py
   - Analyze sentiment for each ticker's news
   - Identify catalysts mentioned in news
   - Output structured sentiment per ticker

2. **Update Market Agent** (`agents/market_agent.py`):
   - Accept market-level news (SPY, QQQ, indices)
   - Analyze overall market sentiment
   - Consider VIX, sector rotation, macro trends

3. **Update Quality Agent** (`agents/quality_agent.py`):
   - Accept financial analysis from financial_analyzer.py
   - Compare quality scores: current holdings vs watchlist
   - Identify holdings below quality threshold
   - Identify watchlist tickers above quality threshold
   - Output: SELL recommendations (weak holdings), BUY recommendations (strong alternatives)

4. **Create Thematic Agent** (`agents/thematic_agent.py`):
   - NEW AGENT (doesn't exist yet)
   - Accept thematic prompts from financial_analyzer.py
   - For each active theme, evaluate holdings vs watchlist
   - Output: SELL recommendations (weak thematic fit), BUY recommendations (strong thematic fit)

5. **Update Trade Agent** (`agents/trade_agent.py`):
   - Synthesize inputs from all agents
   - Apply trading rules (profit taking, stop loss, quality/thematic screening)
   - Generate concrete BUY/SELL/HOLD orders
   - Format output as `trading_template.md`

### Key Changes
- Agents should compare CURRENT HOLDINGS vs WATCHLIST ALTERNATIVES
- Agents should recommend SELLING weak holdings and BUYING stronger alternatives
- Agents should maintain 80/20 allocation (80% quality, 20% thematic)

---

## PROMPT 5: Build Agent Orchestrator Pipeline

### Objective
Create enhanced `Portfolio Scripts Schwab/agent_orchestrator.py` (or update `hf_recommendation_generator.py`) to orchestrate full pipeline.

### Requirements
1. **Pipeline Steps**:
   ```python
   def generate_recommendations():
       # Step 1: Load current portfolio state
       portfolio = load_portfolio_state()

       # Step 2: Fetch live news
       holdings = list(portfolio['positions'].keys())
       watchlist = hf_config.WATCHLIST_TICKERS
       all_tickers = holdings + watchlist
       news_data = news_fetcher.fetch_news(all_tickers)

       # Step 3: Fetch and analyze financials
       financial_data = financial_analyzer.analyze_tickers(all_tickers)

       # Step 4: Run sentiment agents (HuggingFace API)
       news_results = news_agent.analyze(news_data)
       market_results = market_agent.analyze(news_data, ['SPY', 'QQQ', 'VIX'])
       risk_results = risk_agent.analyze(portfolio, market_results)

       # Step 5: Run offline agents
       quality_results = quality_agent.compare_holdings_vs_watchlist(
           holdings=holdings,
           watchlist=watchlist,
           financial_data=financial_data
       )
       thematic_results = thematic_agent.evaluate_themes(
           holdings=holdings,
           watchlist=watchlist,
           financial_data=financial_data,
           active_themes=hf_config.ACTIVE_THEMES
       )

       # Step 6: Synthesize recommendations
       trade_results = trade_agent.synthesize(
           news=news_results,
           market=market_results,
           risk=risk_results,
           quality=quality_results,
           thematic=thematic_results,
           portfolio=portfolio
       )

       # Step 7: Generate trading_template.md
       generate_trading_document(trade_results)
   ```

2. **Output Format**: `trading_recommendations/trading_recommendations_YYYYMMDD.md`
   - Follow exact `trading_template.md` format
   - Include SELL recommendations for weak holdings
   - Include BUY recommendations for strong alternatives
   - Include HOLD recommendations with reasoning
   - Include risk management parameters
   - Include market analysis section

3. **Integration with main.py**:
   - Add `--generate-recommendations` flag (rename from `--generate-hf-recommendations`)
   - Pipeline runs AFTER `--report-only` generates daily_portfolio_analysis.md
   - Available 24/7 (no market hours requirement)

4. **Error Handling**:
   - If news_fetcher fails, continue with stale news (log warning)
   - If financial_analyzer fails for a ticker, skip that ticker (don't fail entire pipeline)
   - If HuggingFace API fails, retry with exponential backoff (existing logic)

---

## PROMPT 6: Update main.py Integration

### Objective
Integrate the new pipeline into `Portfolio Scripts Schwab/main.py`.

### Requirements
1. **Update CLI Arguments**:
   ```python
   parser.add_argument('--generate-recommendations',
                      action='store_true',
                      help='Generate AI trading recommendations using live news and financial data')
   ```

2. **Execution Flow**:
   ```bash
   # Step 1: Generate portfolio analysis (always runs first)
   python "Portfolio Scripts Schwab/main.py" --report-only

   # Step 2: Generate AI recommendations (new integrated pipeline)
   python "Portfolio Scripts Schwab/main.py" --generate-recommendations

   # Step 3: Review output
   # File: trading_recommendations/trading_recommendations_20251031.md

   # Step 4: If approved, manually execute
   # Edit manual_trades_override.json, set enabled=true
   python "Portfolio Scripts Schwab/main.py"
   ```

3. **Dependencies**:
   - `--generate-recommendations` should auto-run `--report-only` first if not already done today
   - Check if daily_portfolio_analysis.md exists and is from today
   - If not, generate it before running agents

---

## PROMPT 7: End-to-End Testing

### Objective
Create comprehensive test suite for the full pipeline.

### Requirements
1. **Create `test_agent_pipeline.py`**:
   - Test news fetcher with 3 tickers
   - Test financial analyzer with 3 tickers
   - Test all agents with mock data
   - Test orchestrator pipeline
   - Test trading_template.md generation
   - Validate output format matches template exactly

2. **Create `test_integration.py`**:
   - Run full pipeline with real portfolio
   - Verify all files generated correctly
   - Check that trading_template.md is parseable
   - Validate recommendations are actionable

3. **Manual Test**:
   ```bash
   # Clean slate test
   python "Portfolio Scripts Schwab/main.py" --report-only
   python "Portfolio Scripts Schwab/main.py" --generate-recommendations

   # Review output
   cat trading_recommendations/trading_recommendations_20251031.md

   # Validate format
   python "Portfolio Scripts Schwab/main.py" --test-parser
   ```

---

## PROMPT 8: Documentation Update

### Objective
Update `CLAUDE.md` and `README.md` to reflect new architecture.

### Requirements
1. **Update CLAUDE.md**:
   - Document new agent pipeline
   - Document news_fetcher.py and financial_analyzer.py
   - Update workflow diagrams
   - Update CLI commands

2. **Update README.md**:
   - Update "How It Works" section
   - Update agent descriptions
   - Add watchlist configuration section
   - Update workflow examples

3. **Create AGENT_ARCHITECTURE.md**:
   - Detailed architecture diagram
   - Data flow between modules
   - API dependencies and rate limits
   - Troubleshooting guide

---

## Implementation Order

**Phase 1: Data Fetching (Prompts 1-3)**
1. Build news_fetcher.py → Test → Verify real news
2. Build financial_analyzer.py → Test → Verify real data
3. Update hf_config.py with watchlist and thresholds

**Phase 2: Agent Enhancement (Prompt 4)**
4. Update News Agent for live news
5. Update Quality Agent for comparative analysis
6. Create Thematic Agent for thematic analysis
7. Update Trade Agent for synthesis

**Phase 3: Integration (Prompts 5-6)**
8. Build agent_orchestrator.py pipeline
9. Integrate into main.py
10. Test end-to-end workflow

**Phase 4: Validation (Prompts 7-8)**
11. Create test suites
12. Run integration tests
13. Update documentation

---

## Success Criteria

### Must Have
- ✅ News fetcher returns real news (no hallucinations)
- ✅ Financial analyzer returns real metrics from yfinance
- ✅ Agents compare holdings vs watchlist
- ✅ trading_template.md includes SELL (weak) and BUY (strong alternatives)
- ✅ Pipeline runs end-to-end without errors
- ✅ Output format matches trading_template.md exactly

### Nice to Have
- ✅ Parallel processing for faster execution
- ✅ Rich logging and progress indicators
- ✅ Visualization of holdings vs watchlist scores
- ✅ Historical tracking of recommendations vs outcomes

---

## Open Questions

1. **News API Choice**: Start with yfinance news? Or use NewsAPI/Finnhub?
2. **Watchlist Management**: Static list in hf_config.py? Or dynamic screening?
3. **LLM Choice for Thematic Agent**: Use HuggingFace API? Or local model? Or Claude API?
4. **Frequency**: Daily cron job? Weekly? On-demand only?
5. **Alert System**: Email/SMS alerts for high-priority recommendations?

---

## Notes for Implementation

- Prioritize anti-hallucination: Only use real data from APIs, never LLM-generated facts
- Cache aggressively: News and financial data don't change every minute
- Fail gracefully: If one ticker fails, don't crash entire pipeline
- Test with small watchlist first (5 tickers), then scale to 20+
- Monitor API rate limits (yfinance is generous, but still has limits)
- Consider costs: yfinance is free, HuggingFace free tier is limited
