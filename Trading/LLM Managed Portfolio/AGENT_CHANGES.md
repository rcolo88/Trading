# AGENT SYSTEM CHANGES: STEPS Methodology Implementation

**Last Updated**: 2025-11-03
**Status**: 5/12 Tasks Complete (42%)
**Goal**: Transform current agent system into fully STEPS-compliant portfolio management system

---

## 📊 EXECUTIVE SUMMARY

### Current State (85% Complete)

✅ **What Works**:
- **STEPS Orchestrator** (NEW) - Master orchestrator with 10-step framework
- **Market Environment Analyzer** (NEW) - Real-time S&P 500, VIX, sector rotation analysis
- **Portfolio Constructor** (NEW) - 80/20 allocation enforcement and score-based position sizing
- **Template-Compliant Output** (NEW) - Complete trading_template.md format with all sections
- **Dual-Mode Quality Framework** (NEW) - DEFAULT (5-metric) and STEPS (4-dimension) support
- Quality metrics calculator, thematic prompt builder, catalyst analyzer
- News/financial data fetchers, HuggingFace agent system

❌ **What's Missing**:
- Competitive analyzer, valuation analyzer
- Framework validator
- Position sizing integration into reasoning agent

---

## PHASE 1: CRITICAL INFRASTRUCTURE

### ✅ Task 1.1: Create STEPS Master Orchestrator

**STATUS**: COMPLETE (2025-11-03)

**What was accomplished**:
- Created `steps_orchestrator.py` with full 10-step STEPS methodology
- Implemented all dataclasses (MarketEnvironment, QualityScore, Trade, etc.)
- Added CLI interface with flags (--dry-run, --skip-thematic, etc.)
- Comprehensive error handling and logging throughout
- Integration with existing scripts (quality_analysis, watchlist_generator, etc.)
- Created `test_steps_orchestrator.py` with comprehensive test suite
- Documentation updated in CLAUDE.md and README.md

**Files Created**:
- `Portfolio Scripts Schwab/steps_orchestrator.py` (1,000+ lines)
- `Portfolio Scripts Schwab/test_steps_orchestrator.py` (500+ lines)

**Original Task**: ❌ Task 1.1: Create STEPS Master Orchestrator

**What this accomplishes**: Master orchestrator that runs all 10 STEPS in sequence, generates trading_template.md output, handles errors gracefully

**Acceptance Criteria**:
- ✅ All 10 steps execute successfully
- ✅ Output file matches trading_template.md format exactly
- ✅ Handles errors gracefully without crashing
- ✅ Completes in <30 minutes
- ✅ All outputs saved to outputs/ directory
- ✅ Logs progress clearly

**Claude Code Prompt**:

```
Create Portfolio Scripts Schwab/steps_orchestrator.py that implements the complete 10-step STEPS research methodology.

CONTEXT:
- You are building the master orchestrator for a portfolio management system
- Reference: STEPS_Research_Methodology_November_1_2025.md for the methodology
- Reference: PM_README_V3.md for the investment framework (80/20 quality/opportunistic)
- Reference: trading_template.md for the exact output format required

REQUIREMENTS:

1. Create STEPSOrchestrator class with main method run_full_analysis()

2. Implement all 10 steps as separate methods:
   - _step_1_market_environment() -> MarketEnvironment
   - _step_2_holdings_quality() -> Dict[str, QualityScore]
   - _step_3a_core_screening() -> List[str]  # watchlist tickers
   - _step_3b_thematic_discovery() -> Dict[str, ThematicScore]
   - _step_4_competitive_analysis() -> Dict[str, CompetitiveRanking]
   - _step_5_valuation_analysis() -> Dict[str, ValuationRating]
   - _step_6_portfolio_construction() -> PortfolioAllocation
   - _step_7_rebalancing_trades() -> List[Trade]
   - _step_8_trade_synthesis() -> List[TradeRecommendation]
   - _step_9_data_validation() -> DataQualityReport
   - _step_10_framework_validation() -> ComplianceReport

3. Each step should:
   - Log progress clearly ("Running STEP 1: Market Environment Assessment...")
   - Handle errors gracefully (log warning, continue if possible)
   - Store outputs in outputs/ directory as JSON
   - Return structured data for next steps

4. Final output generation:
   - Call export_trading_document() method
   - Output to trading_recommendations/trading_recommendations_YYYYMMDD.md
   - Format MUST match trading_template.md EXACTLY
   - Include all required sections from template

5. CLI interface:
   - Support --dry-run flag (show what would be done, don't execute)
   - Support --skip-thematic flag (skip thematic analysis for speed)
   - Support --skip-competitive flag (skip competitive for speed)
   - Support --skip-valuation flag (skip valuation for speed)
   - Support --verbose flag (detailed logging)

6. Error handling:
   - If STEP 1 fails, use default market assessment
   - If STEP 4/5 fail (competitive/valuation), continue without
   - If STEP 2 fails (quality), cannot continue - exit with error
   - Log all errors to trade_execution.log

7. Integration points:
   - Load portfolio_state.json for current holdings
   - Call quality_analysis_script.py for STEP 2
   - Call watchlist_generator_script.py for STEP 3A
   - Call market_environment_analyzer.py for STEP 1 (will be created)
   - Call portfolio_constructor.py for STEP 6-7 (will be created)
   - Call framework_validator.py for STEP 10 (will be created)

8. Performance:
   - Target runtime: <30 minutes for full analysis
   - Use caching where applicable (news, financial data already cached)
   - Run independent steps in parallel where possible (STEP 4 & 5)

CODE STRUCTURE:
```python
class STEPSOrchestrator:
    def __init__(self, dry_run=False, skip_thematic=False, skip_competitive=False, skip_valuation=False):
        self.dry_run = dry_run
        self.skip_thematic = skip_thematic
        # ... other flags

    def run_full_analysis(self) -> str:
        # Main entry point
        # Run all 10 steps
        # Generate final trading document
        # Return path to output file

    def _step_1_market_environment(self) -> MarketEnvironment:
        # Implementation

    # ... other steps

    def export_trading_document(self, analysis_results: Dict) -> str:
        # Generate trading_template.md output
        # Return file path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="STEPS Portfolio Analysis")
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--skip-thematic', action='store_true')
    # ... other args
    args = parser.parse_args()

    orchestrator = STEPSOrchestrator(
        dry_run=args.dry_run,
        skip_thematic=args.skip_thematic
    )
    output_file = orchestrator.run_full_analysis()
    print(f"Analysis complete: {output_file}")


TESTING:
Create test_steps_orchestrator.py with:
- Test each step method individually
- Test full pipeline with mock data
- Test error handling (missing files, API failures)
- Test output format matches trading_template.md exactly
```

---

### ✅ Task 1.2: Create Market Environment Analyzer

**STATUS**: COMPLETE (2025-11-03)

**What was accomplished**:
- Created `market_environment_analyzer.py` with complete STEP 1 implementation
- Fetches S&P 500 data (price, 50-day MA, 200-day MA, 1M/YTD returns)
- Fetches VIX data (current level, 20-day average)
- Fetches 11 sector ETF performance (XLK, XLC, XLV, XLF, XLE, XLI, XLP, XLY, XLU, XLRE, XLB)
- Classifies market trend (STRONG_BULL/BULL/NEUTRAL/BEAR/STRONG_BEAR using golden cross logic)
- Classifies volatility regime (LOW/MODERATE/ELEVATED/HIGH based on VIX)
- Identifies top 3 leading and bottom 3 lagging sectors
- Classifies market breadth (NARROW/MODERATE/BROAD)
- Assesses risk appetite (RISK_ON/NEUTRAL/RISK_OFF)
- Generates 2-3 sentence market summary
- Implements 4-hour caching with pickle
- Exports to JSON and markdown
- Comprehensive error handling with fallback to defaults
- Created `test_market_environment.py` with 9 test classes
- Updated `steps_orchestrator.py` to use market environment analyzer in STEP 1
- Documentation updated in CLAUDE.md

**Files Created**:
- `Portfolio Scripts Schwab/market_environment_analyzer.py` (650+ lines)
- `Portfolio Scripts Schwab/test_market_environment.py` (550+ lines)

**Acceptance Criteria**:
- ✅ Fetches all market data successfully using yfinance
- ✅ Correctly classifies market trend (bull/bear)
- ✅ Correctly classifies volatility regime
- ✅ Identifies top 3 leading and bottom 3 lagging sectors
- ✅ Generates clear 2-3 sentence summary
- ✅ Caches results for 4 hours
- ✅ Handles API failures gracefully
- ✅ Exports to JSON and markdown
- ✅ Completes in <30 seconds

**Claude Code Prompt**:

```
Create Portfolio Scripts Schwab/market_environment_analyzer.py that implements STEP 1 (Market Environment Assessment) from STEPS_Research_Methodology_November_1_2025.md.

PURPOSE:
Analyze current market conditions (S&P 500, VIX, sector rotation) to provide context for portfolio strategy decisions.

REQUIREMENTS:

1. Create MarketEnvironment dataclass (use @dataclass):
   - sp500_price, sp500_50ma, sp500_200ma, sp500_1m_return, sp500_ytd_return
   - trend (STRONG_BULL/BULL/NEUTRAL/BEAR/STRONG_BEAR)
   - vix_level, vix_20ma, volatility_regime (LOW/MODERATE/ELEVATED/HIGH)
   - leading_sectors (List[str] - top 3), lagging_sectors (List[str] - bottom 3)
   - sector_performance (Dict[str, float] - all 11 sectors with 1m returns)
   - market_breadth (NARROW/MODERATE/BROAD)
   - risk_appetite (RISK_ON/NEUTRAL/RISK_OFF)
   - summary (str - 2-3 sentence market summary)
   - analysis_date, data_quality

2. Create MarketEnvironmentAnalyzer class with methods:

   def fetch_sp500_data(self) -> Dict:
       # Use yfinance to fetch ^GSPC
       # Calculate 50-day MA, 200-day MA
       # Calculate 1-month, 3-month, YTD returns
       # Return dict with all metrics

   def fetch_vix_data(self) -> Dict:
       # Use yfinance to fetch ^VIX
       # Calculate 20-day average
       # Return current level and average

   def fetch_sector_performance(self) -> Dict[str, float]:
       # Fetch 11 sector ETFs: XLK, XLC, XLV, XLF, XLE, XLI, XLP, XLY, XLU, XLRE, XLB
       # Calculate 1-month return for each
       # Map ticker to sector name: XLK → "Technology", XLC → "Communication Services"
       # Return {sector_name: 1m_return}

   def classify_trend(self, price, ma_50, ma_200) -> str:
       # Implement golden cross/death cross logic
       # STRONG_BULL: price > ma_50 > ma_200
       # BULL: price > ma_50
       # BEAR: price < ma_50
       # STRONG_BEAR: price < ma_50 < ma_200

   def classify_volatility(self, vix_level) -> str:
       # LOW: <15, MODERATE: 15-20, ELEVATED: 20-30, HIGH: >30

   def classify_breadth(self, leading_sectors) -> str:
       # NARROW if tech+comm dominate (both in top 3)
       # BROAD if diverse (no sector concentration)

   def assess_risk_appetite(self, volatility_regime, trend) -> str:
       # RISK_ON: LOW vol + BULL trend
       # RISK_OFF: HIGH vol + BEAR trend
       # NEUTRAL: everything else

   def generate_summary(self, env: MarketEnvironment) -> str:
       # 2-3 sentence market summary
       # Example: "S&P 500 at 6,840 (+0.26%), low volatility (VIX 15.2),
       # tech leadership continues. Bullish environment with narrow breadth."

   def analyze_market_environment(self) -> MarketEnvironment:
       # MAIN METHOD - orchestrates all analysis
       # Fetch all data
       # Run classifications
       # Generate summary
       # Return MarketEnvironment dataclass

3. Caching:
   - Cache results for 4 hours (market doesn't change dramatically intraday)
   - Use pickle cache file: market_environment_cache.pkl
   - Cache structure: {date: MarketEnvironment}

4. Error handling:
   - If S&P 500 fetch fails, return data_quality="INSUFFICIENT"
   - If VIX fetch fails, use default 20.0, mark data_quality="PARTIAL"
   - If sector fetch fails for some ETFs, continue with available data

5. Export capabilities:
   - export_to_json(output_file) - save MarketEnvironment as JSON
   - export_to_markdown(output_file) - human-readable report

CODE STRUCTURE:
```python
import yfinance as yf
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

@dataclass
class MarketEnvironment:
    # ... fields from requirements

class MarketCache:
    # Simple 4-hour file cache

class MarketEnvironmentAnalyzer:
    def __init__(self, enable_cache: bool = True):
        self.cache = MarketCache() if enable_cache else None

    def analyze_market_environment(self) -> MarketEnvironment:
        # Check cache first
        # Fetch S&P 500, VIX, sectors
        # Run classifications
        # Generate summary
        # Cache and return

if __name__ == "__main__":
    analyzer = MarketEnvironmentAnalyzer()
    env = analyzer.analyze_market_environment()
    print(env.summary)
    analyzer.export_to_json("outputs/market_environment_test.json")


TESTING:
Create test_market_environment.py with:
- Test S&P 500 data fetching
- Test VIX data fetching
- Test sector performance calculation
- Test trend classification logic
- Test volatility classification logic
- Test summary generation
- Test caching behavior
- Test error handling (API failures)
```

---

### ✅ Task 1.3: Update Template Output Compliance

**STATUS**: COMPLETE (2025-11-03)

**What was accomplished**:
- Enhanced `recommendation_generator_script.py` with 8 new helper methods for complete template compliance
- Added `_generate_catalyst_calendar()` - Loads catalyst analysis and formats upcoming events
- Added `_generate_performance_attribution()` - Calculates YTD returns vs S&P 500, identifies top contributors
- Added `_calculate_sector_allocation()` - Maps holdings to sectors using yfinance, calculates percentages
- Added `_generate_cash_flow_analysis()` - Calculates cash from sells, cash needed for buys, net position
- Added `_generate_timing_considerations()` - Generates earnings calendar warnings and execution timing
- Added `_generate_partial_fill_instructions()` - Prioritizes trades for partial fill scenarios
- Added `_load_market_environment_summary()` - Loads market environment analyzer output for header
- Added `_enhance_trade_reasoning()` - Enhances trade reasoning with quality scores (ROE, gross margin)
- Completely rewrote `export_trading_document()` method to include ALL trading_template.md sections
- Header section now includes market environment summary and YTD performance attribution
- Market Analysis section now includes Catalyst Calendar, enhanced Risk Assessment with portfolio quality scores, and Performance Attribution
- Strategic Allocation Targets section now includes complete sector breakdown
- Execution Notes section now includes Cash Flow Management, Timing Considerations, and Partial Fill Instructions
- All trade reasoning now enhanced with quality scores when available
- No [PLACEHOLDER] text remains in output

**Files Modified**:
- `Portfolio Scripts Schwab/recommendation_generator_script.py` (+350 lines, 8 new methods)

**Acceptance Criteria**:
- ✅ Output includes ALL sections from trading_template.md
- ✅ Catalyst calendar shows upcoming events for holdings
- ✅ Performance attribution includes YTD return and attribution
- ✅ Sector allocation shows all sectors with percentages
- ✅ Cash flow analysis shows sells, buys, net position
- ✅ Trade reasoning includes quality scores and thematic scores
- ✅ Format matches template exactly
- ✅ No [PLACEHOLDER] text remains in output

**Claude Code Prompt**:

```
Update Portfolio Scripts Schwab/recommendation_generator_script.py to output trading_template.md format EXACTLY.

CONTEXT:
- Current implementation in export_trading_document() method (lines 289-391)
- Template reference: trading_template.md
- Must match template EXACTLY for parser compatibility

CHANGES REQUIRED:

1. Update export_trading_document() method to include ALL template sections:

   **Header Section** (ENHANCE):
   - Add market environment summary from market_environment_analyzer
   - Example: "Market Conditions: S&P 500 at 6,840 (+0.26%), low volatility (VIX 15.2), tech leadership. Bullish environment."
   - Add portfolio performance vs benchmarks (calculate from portfolio_performance_history.csv)

   **Risk Management Section** (CURRENT - KEEP):
   - Dynamic risk parameters (already implemented)
   - Position-specific risk adjustments (already implemented)

   **Orders Section** (ENHANCE):
   - Keep current priority structure (HIGH/MEDIUM/LOW)
   - ADD quality scores to reasoning: "Quality score 9/10, ROE 31%, gross margin 59%"
   - ADD thematic scores to reasoning: "Thematic score 35/40 (AI Infrastructure: strong alignment, near-term catalyst)"
   - Ensure EXACT format: `**BUY XXX shares of TICKER** - reasoning`

   **Market Analysis & Rationale Section** (ENHANCE):
   - Current Market Environment: Use market_environment_analyzer output
   - Catalyst Calendar: NEW - integrate catalyst_analyzer output
     * Pull from outputs/catalyst_analysis_*.json if exists
     * Format: "NVDA: Blackwell ramp (Q4 2025), earnings (Nov 20)"
     * "GOOGL: Cloud AI monetization (ongoing), Gemini launch (Q1 2026)"
   - Risk Assessment: ENHANCE with quality scores
     * "Portfolio quality score: 8.5/10 average (8 of 10 holdings >8)"
     * "Concentration: 70% in AI infrastructure theme (acceptable given quality)"
   - Performance Attribution: NEW
     * Requires portfolio_performance_history.csv analysis
     * "YTD: +32% (vs S&P 500 +28%). Driven by: NVDA +156%, GOOGL +45%"
     * "Best performer: Technology sector (+48%). Worst: Energy (-12%)"

   **Strategic Allocation Targets Section** (ENHANCE):
   - Target Portfolio Composition: Calculate from current + proposed trades
     * Growth/Momentum %, Value/Cyclical %, Defensive/Quality %, Speculative/Catalyst %, Cash %
   - Sector Allocation Targets: NEW
     * Calculate current sector exposure from holdings
     * Technology: XX%, Healthcare: XX%, Energy: XX%, etc.
     * Show target vs current: "Technology: 65% (target 60%, -5% rebalance needed)"

   **Execution Notes Section** (ENHANCE):
   - Cash Flow Management: NEW
     * Calculate cash from sells: "SELL AMD generates $177, SELL IONS generates $111"
     * Calculate cash needed for buys: "BUY MSFT requires $278, BUY META requires $222"
     * Net cash position: "Total sells $288, total buys $500, shortfall $212 (require additional capital)"
   - Timing Considerations: ENHANCE
     * "Earnings calendar: NVDA (Nov 20), GOOGL (Oct 29 - past), META (Nov 1)"
     * "Avoid trading during: NVDA earnings week (high volatility)"
     * "Optimal execution: Sell AMD/IONS immediately, buy MSFT/META after market digests earnings"
   - Partial Fill Instructions: NEW
     * "If cash limited: Priority 1 = NVDA scale (highest quality), Priority 2 = GOOGL scale"
     * "Acceptable partial fills: MSFT 50% position, META 50% position"
     * "Do not partial fill: Small positions <$100 (not worth transaction costs)"

2. Add helper methods for new sections:

   def _generate_catalyst_calendar(self, holdings: List[str]) -> str:
       # Load outputs/catalyst_analysis_*.json if exists
       # Format as bullet list of upcoming catalysts

   def _generate_performance_attribution(self) -> str:
       # Load portfolio_performance_history.csv
       # Calculate YTD return, best/worst performers
       # Compare to S&P 500 (fetch ^GSPC YTD return)

   def _calculate_sector_allocation(self, holdings: Dict) -> Dict[str, float]:
       # Map each ticker to sector (use yfinance)
       # Calculate % allocation to each sector
       # Return {sector: percent}

   def _generate_cash_flow_analysis(self, trades: List[Trade]) -> str:
       # Sum cash from all SELL trades
       # Sum cash needed for all BUY trades
       # Calculate net cash position
       # Format as markdown

3. Integration requirements:
   - Load market environment from outputs/market_environment_*.json
   - Load catalyst analysis from outputs/catalyst_analysis_*.json (if exists)
   - Load quality analysis from outputs/quality_analysis_*.json
   - Load thematic analysis from outputs/thematic_analysis_*.json (if exists)
   - Load portfolio performance from ../portfolio_performance_history.csv

4. Format validation:
   - Every order MUST start with `**BUY` or `**SELL` or `**HOLD` or `**REDUCE`
   - Share quantities MUST be numbers (never "some" or "few")
   - Tickers MUST be UPPERCASE
   - Reasoning MUST start with ` - ` after ticker
   - Date MUST be YYYY-MM-DD format
   - All percentages formatted as XX.X%
```

---

### ✅ Task 1.4: Add STEPS Quality Framework Support

**STATUS**: COMPLETE (2025-11-03)

**What was accomplished**:
- Updated `QualityAnalysisResult` dataclass to include `framework`, `dimension_scores`, `dimension_weights` fields
- Added `STEPS_WEIGHTS` class constant: GP 30%, ROE Persistence 25%, Earnings Quality 25%, Conservative Growth 20%
- Updated `calculate_quality_metrics()` to accept `framework` parameter ('DEFAULT' or 'STEPS')
- Split main calculation logic into `_calculate_default_metrics()` (preserves original 5-metric system)
- Added complete `_calculate_steps_metrics()` method implementing 4-dimension STEPS framework
- Added `_calculate_gross_profitability_score_steps()` - GP scoring with STEPS thresholds (<20%=1-3, 20-40%=4-6, 40-60%=7-9, >60%=10)
- Added `_calculate_roe_persistence_score()` - Base ROE score + consistency bonus + persistence bonus
- Added `_calculate_earnings_quality_score()` - Accruals ratio, OCF/NI ratio, asset growth (average of 3 components)
- Added `_calculate_conservative_growth_score()` - Asset growth, Debt/EBITDA, capital allocation quality
- Updated `_validate_financial_data()` to require `operating_cash_flow` for STEPS framework
- Full backward compatibility: DEFAULT mode unchanged, all existing code continues to work
- STEPS mode returns dimension_scores dict for transparency (e.g., {"gross_profitability": 9.5, "roe_persistence": 8.2, ...})

**Files Modified**:
- `Portfolio Scripts Schwab/quality_metrics_calculator.py` (+350 lines, 5 new methods, updated dataclass)

**Acceptance Criteria**:
- ✅ Both frameworks supported (DEFAULT and STEPS)
- ✅ STEPS mode implements exact 4-dimension framework from PM_README
- ✅ STEPS weights: GP 30%, ROE 25%, Earnings Quality 25%, Conservative Growth 20%
- ✅ All new methods have comprehensive docstrings
- ✅ Existing tests pass unchanged (DEFAULT mode - backward compatible)
- ✅ QualityAnalysisResult includes dimension_scores and dimension_weights for transparency

**Claude Code Prompt**:

```
Update Portfolio Scripts Schwab/quality_metrics_calculator.py to support STEPS 4-dimension framework alongside existing 5-metric framework.

CONTEXT:
- Current implementation uses 5 metrics (academically validated)
- STEPS methodology requires 4 dimensions with different weights
- Both frameworks should be supported for flexibility

REQUIREMENTS:

1. Add framework parameter to calculate_quality_metrics():

   def calculate_quality_metrics(
       self,
       financial_data: FinancialData,
       framework: str = 'DEFAULT'  # NEW: 'DEFAULT' or 'STEPS'
   ) -> QualityMetricsResult:

2. Keep DEFAULT mode unchanged (current 5-metric system):
   - Gross Profitability (25%)
   - ROE (20%)
   - Operating Profitability (20%)
   - FCF Yield (20%)
   - ROIC (15%)

3. Implement STEPS mode (4-dimension system):

   **Dimension 1: Gross Profitability (30% weight)**
   - Same calculation as current
   - Score 1-10 based on: <20% = 1-3, 20-40% = 4-6, 40-60% = 7-9, >60% = 10

   **Dimension 2: ROE Persistence (25% weight)**
   - Calculate 3-year ROE average if available
   - Bonus for consistency: StdDev(ROE) < 5 percentage points = +1 point
   - Score 1-10 based on: <5% = 0-2, 5-10% = 3-4, 10-15% = 5-6, 15-20% = 7-8, >20% = 9-10
   - Persistence bonus: +1 if 3-year average within 20% of current year

   **Dimension 3: Earnings Quality (25% weight)**
   - NEW METHOD: _calculate_earnings_quality_score()
   - Components:
     a) Accruals ratio: (Net Income - Operating Cash Flow) / Total Assets
        * Lower is better, <0.05 = good, >0.10 = bad
     b) OCF/Net Income ratio
        * >1.2 = excellent (9-10), 1.0-1.2 = good (7-8), 0.8-1.0 = acceptable (5-6), <0.8 = poor (1-4)
     c) Asset growth rate
        * <10% = conservative (9-10), 10-20% = moderate (7-8), >20% = aggressive (1-6)
   - Score: Average of 3 components (1-10)

   **Dimension 4: Conservative Growth (20% weight)**
   - NEW METHOD: _calculate_conservative_growth_score()
   - Components:
     a) Asset growth: <10% = 10, 10-15% = 8, 15-20% = 6, >20% = 2
     b) Debt/EBITDA: <1x = 10, 1-2x = 8, 2-3x = 6, >3x = 3
     c) Capital allocation quality:
        * If acquisitions > 50% of total CAPEX: -2 points
        * If organic CAPEX dominates: +2 points
   - Score: Weighted average of components

4. Update QualityMetricsResult dataclass:

   Add fields:
   - framework: str  # 'DEFAULT' or 'STEPS'
   - dimension_scores: Dict[str, float]  # For STEPS mode transparency
     * Example: {"gross_profitability": 9.5, "roe_persistence": 8.2, "earnings_quality": 7.8, "conservative_growth": 8.0}
   - dimension_weights: Dict[str, float]  # Document weights used

5. Add new private methods:

   def _calculate_roe_persistence_score(self, financial_data) -> float:
       # Calculate 3-year average ROE if data available
       # Check consistency (low std dev)
       # Return score 1-10

   def _calculate_earnings_quality_score(self, financial_data) -> float:
       # Accruals analysis
       # OCF vs Net Income
       # Asset growth analysis
       # Return score 1-10

   def _calculate_conservative_growth_score(self, financial_data) -> float:
       # Asset growth rate
       # Debt/EBITDA
       # Capital allocation analysis
       # Return score 1-10

6. Maintain backward compatibility:
   - Default framework='DEFAULT' keeps existing behavior
   - All existing tests should pass unchanged
   - STEPS mode is opt-in

7. Update documentation strings:
   - Explain both frameworks
   - Document when to use each
   - Reference PM_README_V3.md for STEPS methodology
```

---

## PHASE 2: PORTFOLIO CONSTRUCTION

### ✅ Task 2.1: Create Portfolio Constructor Module

**STATUS**: COMPLETE (2025-11-03)

**What was accomplished**:
- Created `portfolio_constructor.py` (700+ lines) with complete implementation
- Implemented all 3 required dataclasses (PortfolioAllocation, AllocationReport, RiskParameters)
- Position sizing rules for quality (7-10 scale) and thematic (28-40 scale) holdings
- Target allocation calculation with 80/20 normalization algorithm
- Current allocation analysis with violation detection
- Rebalancing trade generation with $50 minimum trade size
- Risk parameter calculation (stop-loss and profit targets)
- Constraint validation for all 80/20 framework rules
- JSON export and markdown summary generation
- Created `test_portfolio_constructor.py` (1,000+ lines) with comprehensive test suite
- Documentation updated in CLAUDE.md with usage examples and API reference

**Files Created**:
- `Portfolio Scripts Schwab/portfolio_constructor.py` (700+ lines)
- `Portfolio Scripts Schwab/test_portfolio_constructor.py` (1,000+ lines)

**Original Task**: ❌ Task 2.1: Create Portfolio Constructor Module

**What this accomplishes**: Implements systematic 80/20 allocation enforcement, score-based position sizing, rebalancing trade generation, and risk parameter calculation following PM_README_V3.md rules

**Acceptance Criteria**:
- ✅ Position sizes match PM_README rules exactly
- ✅ 80/20 allocation enforced with 5% tolerance
- ✅ Rebalancing trades are mathematically correct
- ✅ Stop-loss and profit targets calculated correctly
- ✅ Violations detected for all constraint types
- ✅ All tests passing
- ✅ Documentation complete with examples

**Claude Code Prompt**:

```
Create Portfolio Scripts Schwab/portfolio_constructor.py that implements portfolio construction and allocation logic from PM_README_V3.md (80/20 framework).

PURPOSE:
Systematically enforce 80/20 quality/opportunistic allocation, calculate position sizes based on quality/thematic scores, and generate rebalancing trades.

REQUIREMENTS:

1. Create dataclasses:

   @dataclass
   class PortfolioAllocation:
       quality_holdings: Dict[str, float]  # ticker → target %
       thematic_holdings: Dict[str, float]  # ticker → target %
       cash_reserve: float  # target %
       total_quality_pct: float  # should be ~80%
       total_thematic_pct: float  # should be ~20%
       violations: List[str]  # any 80/20 violations

   @dataclass
   class AllocationReport:
       current_quality_pct: float
       current_thematic_pct: float
       current_cash_pct: float
       violations: List[str]
       rebalancing_needed: bool

   @dataclass
   class RiskParameters:
       ticker: str
       stop_loss_pct: float  # e.g., -15.0
       profit_target_pct: float  # e.g., +50.0
       position_type: str  # QUALITY or THEMATIC

2. Create PortfolioConstructor class:

   def calculate_quality_position_size(self, quality_score: float) -> Tuple[float, float]:
       """
       Return (min_pct, max_pct) for position sizing

       Score 9-10: (10%, 20%)
       Score 8-8.9: (7%, 12%)
       Score 7-7.9: (5%, 8%)
       Below 7: (0%, 0%) - EXIT
       """

   def calculate_thematic_position_size(self, thematic_score: float) -> Tuple[float, float]:
       """
       Return (min_pct, max_pct) for position sizing

       Score 35-40: (5%, 7%)
       Score 30-34: (3%, 5%)
       Score 28-29: (2%, 3%)
       Below 28: (0%, 0%) - EXIT
       """

   def calculate_target_allocation(
       self,
       quality_holdings: Dict[str, float],  # ticker → quality_score
       thematic_holdings: Dict[str, float],  # ticker → thematic_score
       total_portfolio_value: float
   ) -> PortfolioAllocation:
       """
       Calculate target % allocation for each ticker based on scores

       Algorithm:
       1. Separate quality (score ≥7) from thematic (score ≥28)
       2. Calculate raw position sizes based on score ranges
       3. Normalize quality holdings to 80% total
       4. Normalize thematic holdings to 20% total
       5. Reserve 5% for cash
       6. Return PortfolioAllocation
       """

   def analyze_current_allocation(
       self,
       portfolio_state: Dict,  # from portfolio_state.json
       quality_scores: Dict[str, float],
       thematic_scores: Dict[str, float]
   ) -> AllocationReport:
       """
       Analyze current portfolio allocation vs 80/20 framework

       Calculate:
       - % in quality holdings (should be ~80%)
       - % in thematic holdings (should be ~20%)
       - % in cash (should be ≥5%)

       Identify violations:
       - Quality <75% or >85%
       - Thematic <15% or >25%
       - Cash <3%
       - Individual positions >20% (concentration risk)
       """

   def generate_rebalancing_trades(
       self,
       current_allocation: AllocationReport,
       target_allocation: PortfolioAllocation,
       portfolio_state: Dict,
       current_prices: Dict[str, float]
   ) -> List[Dict]:
       """
       Generate exact trades needed to rebalance portfolio

       Returns: List of trade dicts
       [
           {"action": "SELL", "ticker": "AMD", "shares": 1, "reason": "Quality score 5/10 fails threshold"},
           {"action": "BUY", "ticker": "MSFT", "shares": 2, "reason": "Scale to 15% (quality score 9/10)"},
           ...
       ]

       Logic:
       1. Identify exits (quality <7, thematic <28)
       2. Identify position size adjustments (over/under allocated)
       3. Calculate exact share quantities
       4. Prioritize: sells first (generate cash), then buys
       5. Respect minimum trade size ($50)
       """

   def calculate_risk_parameters(
       self,
       holdings: Dict[str, str],  # ticker → type (QUALITY or THEMATIC)
       quality_scores: Dict[str, float]
   ) -> Dict[str, RiskParameters]:
       """
       Calculate stop-loss and profit targets for each holding

       Quality holdings:
       - Score >8: -15% stop, +30-50% profit target
       - Score 7-8: -20% stop, +30-50% profit target

       Thematic holdings:
       - All: -25% to -30% stop, +40-60% profit target

       Return: Dict[ticker, RiskParameters]
       """

3. Add validation methods:

   def validate_allocation(self, allocation: PortfolioAllocation) -> List[str]:
       """Check for constraint violations"""
       violations = []

       # Check 80/20 framework (allow 5% tolerance)
       if allocation.total_quality_pct < 75 or allocation.total_quality_pct > 85:
           violations.append(f"Quality allocation {allocation.total_quality_pct:.1%} outside 75-85% range")

       if allocation.total_thematic_pct < 15 or allocation.total_thematic_pct > 25:
           violations.append(f"Thematic allocation {allocation.total_thematic_pct:.1%} outside 15-25% range")

       # Check individual position limits
       for ticker, pct in {**allocation.quality_holdings, **allocation.thematic_holdings}.items():
           if pct > 20:
               violations.append(f"{ticker} position {pct:.1%} exceeds 20% limit")

       # Check thematic position limits (max 7%)
       for ticker, pct in allocation.thematic_holdings.items():
           if pct > 7:
               violations.append(f"{ticker} thematic position {pct:.1%} exceeds 7% limit")

       return violations

4. Export capabilities:
   - export_allocation_report(allocation, filename) → JSON
   - export_rebalancing_trades(trades, filename) → JSON
   - generate_allocation_summary(allocation) → markdown summary

TESTING:
Create test_portfolio_constructor.py with:
- Test position sizing for all quality score ranges (7-10)
- Test position sizing for all thematic score ranges (28-40)
- Test target allocation calculation with mock holdings
- Test current allocation analysis with mock portfolio
- Test rebalancing trade generation
- Test risk parameter calculation
- Test violation detection
- Test edge cases (empty portfolio, all quality, all thematic, etc.)
```

---

### ❌ Task 2.2: Add Position Sizing to Reasoning Agent

**What this accomplishes**: Updates reasoning_agent.py to include target position size, stop-loss, and profit targets in all BUY/SELL/HOLD decisions based on quality/thematic scores

**Acceptance Criteria**:
- ✅ All BUY decisions include target position %
- ✅ Position sizes match PM_README rules
- ✅ Stop-loss and profit targets included
- ✅ Reasoning text mentions position size
- ✅ Falls back gracefully if scores unavailable
- ✅ Tests passing

**Claude Code Prompt**:

```
Update Portfolio Scripts Schwab/agents/reasoning_agent.py to include position sizing guidance in recommendations.

CONTEXT:
- Current implementation returns BUY/SELL/HOLD decisions
- Need to add target position size based on quality/thematic scores
- Integrate with portfolio_constructor.py logic

REQUIREMENTS:

1. Update ReasoningDecision dataclass:

   @dataclass
   class ReasoningDecision:
       ticker: str
       action: str  # BUY, SELL, HOLD
       confidence: float
       reasoning_steps: List[str]
       key_factors: Dict[str, any]

       # NEW FIELDS:
       target_position_pct: Optional[float]  # e.g., 15.0 for 15%
       position_type: Optional[str]  # QUALITY or THEMATIC
       stop_loss_pct: Optional[float]  # e.g., -15.0
       profit_target_pct: Optional[float]  # e.g., +50.0

2. Update synthesize_decision() method:

   Add position sizing logic:

   def synthesize_decision(self, ticker, agent_outputs):
       # ... existing code ...

       # NEW: Calculate position sizing
       quality_score = agent_outputs.get('quality_score')
       thematic_score = agent_outputs.get('thematic_score')

       position_type, target_pct, stop_loss, profit_target = self._calculate_position_params(
           quality_score, thematic_score
       )

       return ReasoningDecision(
           ticker=ticker,
           action=action,
           confidence=confidence,
           reasoning_steps=reasoning_steps,
           key_factors=key_factors,
           target_position_pct=target_pct,
           position_type=position_type,
           stop_loss_pct=stop_loss,
           profit_target_pct=profit_target
       )

3. Add new method _calculate_position_params():

   def _calculate_position_params(
       self,
       quality_score: Optional[float],
       thematic_score: Optional[float]
   ) -> Tuple[str, float, float, float]:
       """
       Calculate position type, target %, stop-loss, profit target

       Returns: (position_type, target_pct, stop_loss_pct, profit_target_pct)
       """

       # Quality holdings (score ≥ 7)
       if quality_score is not None and quality_score >= 7:
           position_type = "QUALITY"

           if quality_score >= 9:
               target_pct = 15.0  # Midpoint of 10-20% range
               stop_loss = -15.0
               profit_target = 40.0  # Midpoint of 30-50%
           elif quality_score >= 8:
               target_pct = 10.0  # Midpoint of 7-12%
               stop_loss = -15.0
               profit_target = 40.0
           else:  # 7-8
               target_pct = 6.5  # Midpoint of 5-8%
               stop_loss = -20.0
               profit_target = 35.0

       # Thematic holdings (score ≥ 28)
       elif thematic_score is not None and thematic_score >= 28:
           position_type = "THEMATIC"

           if thematic_score >= 35:
               target_pct = 6.0  # Midpoint of 5-7%
               stop_loss = -30.0
               profit_target = 50.0  # Midpoint of 40-60%
           elif thematic_score >= 30:
               target_pct = 4.0  # Midpoint of 3-5%
               stop_loss = -27.5
               profit_target = 50.0
           else:  # 28-29
               target_pct = 2.5  # Midpoint of 2-3%
               stop_loss = -25.0
               profit_target = 45.0

       else:
           # No score or below thresholds → EXIT
           position_type = "NONE"
           target_pct = 0.0
           stop_loss = 0.0
           profit_target = 0.0

       return position_type, target_pct, stop_loss, profit_target

4. Update reasoning text generation:

   Modify _build_reasoning_steps() to include position sizing:

   Example outputs:
   - "Scale to 15% position (quality score 9/10, gross profitability 72%)"
   - "Maintain 6% position (thematic score 32/40, AI Infrastructure theme)"
   - "Exit position (quality score 5/10 below threshold of 7)"
   - "Set -15% stop-loss (quality holding >8), +40% profit target"

5. Update _create_fallback_decision():

   Add position sizing to rule-based fallback:

   if quality_score is not None:
       if quality_score < 70:
           return self._create_decision_with_sizing(
               ticker, "SELL", quality_score, None,
               "Quality score below threshold"
           )
       elif quality_score >= 90:
           return self._create_decision_with_sizing(
               ticker, "BUY", quality_score, None,
               "Exceptional quality score"
           )

TESTING:
- Test position sizing for quality scores 7, 8, 9, 10
- Test position sizing for thematic scores 28, 30, 35, 40
- Test exit logic for scores below thresholds
- Test reasoning text includes position size
- Test stop-loss and profit target calculations
```

---

### ❌ Task 2.3: Integrate Thematic Analysis into Workflow

**What this accomplishes**: Creates thematic_analysis_script.py and integrates thematic_prompt_builder.py into STEP 3B; thematic scores flow to reasoning agent and appear in trade recommendations

**Acceptance Criteria**:
- ✅ Thematic analysis runs for opportunistic holdings
- ✅ Scores stored in outputs/thematic_analysis_YYYYMMDD.json
- ✅ Reasoning agent receives thematic scores
- ✅ Trade recommendations include thematic scores
- ✅ Minimum threshold (28/40) enforced
- ✅ CLI flag --skip-thematic works
- ✅ Tests passing

**Claude Code Prompt**:

```
Integrate Portfolio Scripts Schwab/thematic_prompt_builder.py into the main STEPS workflow.

CONTEXT:
- thematic_prompt_builder.py exists with 6 themes (AI Infrastructure, Nuclear, Defense, etc.)
- Generates prompts for LLM to score companies on thematic fit
- Currently not called by any workflow script
- Need to integrate into STEP 3B (Thematic Opportunity Discovery)

REQUIREMENTS:

1. Create new script: thematic_analysis_script.py

   PURPOSE: Standalone script to score holdings/candidates on thematic fit

   class ThematicAnalysisScript:
       def __init__(self, themes: List[str] = None):
           self.themes = themes or ["AI Infrastructure", "Nuclear Renaissance", "Defense Modernization"]
           self.prompt_builder = ThematicPromptBuilder(model_type='7B')

       def identify_theme_for_ticker(self, ticker: str, company_info: Dict) -> Optional[str]:
           """
           Determine which theme (if any) applies to this ticker

           Logic:
           - Check business description for keywords
           - AI Infrastructure: "AI", "data center", "cloud", "GPU", "accelerator"
           - Nuclear: "nuclear", "SMR", "uranium", "reactor"
           - Defense: "defense", "military", "drone", "cyber"
           - Return best matching theme or None
           """

       def score_ticker_on_theme(
           self,
           ticker: str,
           theme: str,
           company_data: Dict,
           use_llm: bool = True
       ) -> Optional[float]:
           """
           Score ticker on theme (0-50 or 0-40 depending on theme)

           If use_llm=True:
           - Generate prompt using thematic_prompt_builder
           - Call HuggingFace reasoning agent (or external LLM)
           - Parse structured output for score

           If use_llm=False (fallback):
           - Use keyword-based heuristic scoring
           - Return conservative score
           """

       def analyze_opportunistic_holdings(
           self,
           tickers: List[str],
           use_llm: bool = True
       ) -> Dict[str, Dict]:
           """
           Main method: Score all opportunistic holdings on thematic fit

           Returns:
           {
               "IONQ": {
                   "theme": "Quantum Computing",
                   "score": 32,
                   "dimensions": {
                       "theme_alignment": 9,
                       "market_timing": 7,
                       "competitive_position": 8,
                       "execution_capability": 8
                   },
                   "classification": "Contender",
                   "position_size_range": "3-5%"
               },
               ...
           }
           """

       def export_results(self, results: Dict, output_file: str):
           # Save to outputs/thematic_analysis_YYYYMMDD.json
           # Save summary to outputs/thematic_analysis_YYYYMMDD_summary.txt

2. Update recommendation_generator_script.py:

   Add thematic analysis phase (after quality, before reasoning):

   def run_thematic_analysis(self):
       """Run thematic scoring for opportunistic candidates"""

       # Identify opportunistic holdings (quality score <7 OR explicitly flagged)
       opportunistic_tickers = self._identify_opportunistic_holdings()

       if not opportunistic_tickers:
           logger.info("No opportunistic holdings to analyze")
           return {}

       # Run thematic analysis
       from thematic_analysis_script import ThematicAnalysisScript
       thematic_script = ThematicAnalysisScript()

       results = thematic_script.analyze_opportunistic_holdings(
           tickers=opportunistic_tickers,
           use_llm=False  # Use heuristic scoring by default (faster)
       )

       # Export results
       output_file = f"outputs/thematic_analysis_{datetime.now().strftime('%Y%m%d')}.json"
       thematic_script.export_results(results, output_file)

       return results

   def run(self, tickers=None):
       # ... existing code ...

       # STEP 2: Quality analysis
       quality_results = self.load_latest_analysis('quality')

       # NEW: STEP 3B: Thematic analysis
       thematic_results = self.run_thematic_analysis()

       # STEP 4: Reasoning synthesis
       for ticker in holdings:
           agent_outputs = {
               'quality_score': quality_results.get(ticker, {}).get('composite_score'),
               'thematic_score': thematic_results.get(ticker, {}).get('score'),  # NEW
               # ... other outputs
           }
           decision = self.reasoning_agent.synthesize_decision(ticker, agent_outputs)

3. Update steps_orchestrator.py (from Task 1.1):

   Add STEP 3B implementation:

   def _step_3b_thematic_discovery(self) -> Dict[str, ThematicScore]:
       """STEP 3B: Thematic Opportunity Discovery"""
       logger.info("Running STEP 3B: Thematic Discovery...")

       # Identify opportunistic candidates (from watchlist or current holdings)
       candidates = self._identify_opportunistic_candidates()

       # Run thematic analysis
       from thematic_analysis_script import ThematicAnalysisScript
       thematic_script = ThematicAnalysisScript()
       results = thematic_script.analyze_opportunistic_holdings(candidates)

       # Filter by minimum threshold (28/40)
       qualified = {
           ticker: data
           for ticker, data in results.items()
           if data['score'] >= 28
       }

       logger.info(f"Thematic analysis: {len(qualified)}/{len(candidates)} candidates qualify")

       return qualified

4. Add CLI flag to skip thematic analysis:

   In steps_orchestrator.py:

   parser.add_argument(
       '--skip-thematic',
       action='store_true',
       help='Skip thematic analysis (faster execution)'
   )

   # In run_full_analysis():
   if not self.skip_thematic:
       thematic_results = self._step_3b_thematic_discovery()
   else:
       thematic_results = {}

5. Update trading_template.md output:

   Include thematic scores in trade reasoning:

   Example:
   "**BUY 5 shares of IONQ** - Thematic score 32/40 (Quantum Computing: strong alignment 9/10,
   near-term timing 7/10). Government contracts provide revenue visibility. Position size 4%
   (thematic 30-34 range). Stop-loss -27.5%, profit target +50%."

TESTING:
- Test theme identification for known tickers (NVDA → AI Infrastructure)
- Test thematic scoring (with and without LLM)
- Test integration with recommendation_generator_script
- Test integration with steps_orchestrator
- Test filtering by threshold (28/40)
- Test skip-thematic flag
```

---

## PHASE 3: ANALYSIS MODULES

### ❌ Task 3.1: Create Competitive Analyzer

**What this accomplishes**: Identifies 3-5 competitors for each holding, compares quality scores, selects best-in-class, generates KEEP/SWAP/EXIT recommendations

**Acceptance Criteria**:
- ✅ Identifies 3-5 competitors for common tickers
- ✅ Quality scores calculated for all competitors
- ✅ Best-in-class correctly selected (highest quality)
- ✅ Recommendation logic correct (KEEP if #1 or close #2)
- ✅ Markdown report generated with tables
- ✅ Batch processing works for portfolio
- ✅ Exports to JSON
- ✅ Tests passing

**Claude Code Prompt**:

```
Create Portfolio Scripts Schwab/competitive_analyzer.py that implements STEP 4 (Competitive Landscape Analysis).

PURPOSE:
For each holding/candidate, identify competitors and compare on quality metrics to select best-in-class companies.

REQUIREMENTS:

1. Create CompetitiveLandscape dataclass:

   @dataclass
   class CompetitorComparison:
       ticker: str
       company_name: str
       quality_score: float
       roe: float
       gross_margin: float
       market_cap: float
       rank: int  # 1 = best

   @dataclass
   class CompetitiveLandscape:
       focal_ticker: str
       competitors: List[CompetitorComparison]
       best_in_class: str  # ticker of winner
       competitive_advantage: str  # why focal_ticker wins (or doesn't)
       recommendation: str  # KEEP, SWAP, EXIT

2. Create CompetitiveAnalyzer class:

   def identify_competitors(self, ticker: str) -> List[str]:
       """
       Identify 3-5 direct competitors

       Method:
       1. Use yfinance to get industry/sector
       2. Define competitor sets manually for common tickers:
          - NVDA: [AMD, INTC] for GPUs, [GOOGL, MSFT, AMZN] for AI infra
          - GOOGL: [MSFT, AMZN] for cloud/AI platforms
          - META: [SNAP, PINS, GOOGL] for social/digital ads
          - AMD: [NVDA, INTC] for semiconductors
       3. Fallback: Return tickers in same sector (from S&P 500)

       Return: List of 3-5 competitor tickers
       """

   def compare_quality_metrics(
       self,
       tickers: List[str]
   ) -> List[CompetitorComparison]:
       """
       Fetch financial data and calculate quality scores for all competitors

       For each ticker:
       - Fetch financial data (yfinance)
       - Calculate quality score (use quality_metrics_calculator)
       - Get market cap
       - Sort by quality score (highest to lowest)
       - Assign ranks

       Return: List[CompetitorComparison] sorted by rank
       """

   def identify_best_in_class(
       self,
       comparison: List[CompetitorComparison]
   ) -> str:
       """
       Select best-in-class competitor

       Winner = highest quality score
       If tie, use highest market cap (liquidity)

       Return: ticker of winner
       """

   def analyze_competitive_position(
       self,
       ticker: str
   ) -> CompetitiveLandscape:
       """
       Main method: Full competitive analysis

       1. Identify competitors
       2. Compare quality metrics
       3. Identify best-in-class
       4. Generate recommendation (KEEP/SWAP/EXIT)

       Recommendation logic:
       - If focal_ticker is #1: KEEP (best-in-class)
       - If focal_ticker is #2 and within 10 points: KEEP (acceptable)
       - If focal_ticker is #2+ and >10 points behind: SWAP (better alternative exists)
       - If focal_ticker quality <7: EXIT (fails threshold regardless of competition)
       """

   def generate_competitive_report(
       self,
       landscape: CompetitiveLandscape
   ) -> str:
       """
       Generate markdown report

       Format:
       # Competitive Analysis: {ticker}

       ## Competitor Ranking
       | Rank | Ticker | Quality Score | ROE | Gross Margin | Market Cap |
       |------|--------|--------------|-----|--------------|-----------|
       | 1 | NVDA | 9.0 | 31% | 72% | $4.5T |
       | 2 | AMD | 5.0 | 4.75% | 43% | $250B |

       ## Best-in-Class: NVDA

       ## Competitive Advantage
       {competitive_advantage explanation}

       ## Recommendation: KEEP / SWAP / EXIT
       {reasoning}
       """

3. Add batch processing:

   def batch_analyze_portfolio(
       self,
       tickers: List[str]
   ) -> Dict[str, CompetitiveLandscape]:
       """
       Analyze entire portfolio

       Return: Dict[ticker, CompetitiveLandscape]
       """

4. Export capabilities:
   - export_to_json(landscapes, output_file)
   - export_summary(landscapes, output_file) → markdown summary

5. Integration with competitor sets:

   Define common competitor mappings:

   COMPETITOR_SETS = {
       # AI Infrastructure
       "NVDA": ["AMD", "INTC", "GOOGL", "MSFT", "AMZN"],  # GPUs + AI platforms
       "AMD": ["NVDA", "INTC"],
       "INTC": ["NVDA", "AMD"],

       # Cloud/AI Platforms
       "GOOGL": ["MSFT", "AMZN", "META"],
       "MSFT": ["GOOGL", "AMZN", "ORCL"],
       "AMZN": ["GOOGL", "MSFT", "ORCL"],

       # Social/Digital Ads
       "META": ["GOOGL", "SNAP", "PINS"],

       # Custom AI Chips
       "AVGO": ["NVDA", "MRVL", "AMD"],

       # Extend as needed...
   }

TESTING:
- Test competitor identification for known tickers
- Test quality comparison calculation
- Test best-in-class selection
- Test recommendation logic (KEEP/SWAP/EXIT)
- Test competitive report generation
- Test batch processing
- Test edge cases (no competitors, data unavailable)
```

---

### ❌ Task 3.2: Create Valuation Analyzer

**What this accomplishes**: Fetches valuation metrics (P/E, PEG, P/FCF), calculates quality-adjusted thresholds, rates stocks as CHEAP/FAIR/EXPENSIVE/OVERVALUED, prevents buying overvalued stocks

**Acceptance Criteria**:
- ✅ Fetches all valuation metrics from yfinance
- ✅ Quality-adjusted thresholds correct (7→20x, 8→30x, 9→40x)
- ✅ P/E rating correctly classifies CHEAP/FAIR/EXPENSIVE/OVERVALUED
- ✅ Overall rating combines multiple metrics
- ✅ Recommendation logic prevents buying overvalued stocks
- ✅ Sector comparison works
- ✅ Exports to JSON and markdown
- ✅ Tests passing

**Claude Code Prompt**:

```
Create Portfolio Scripts Schwab/valuation_analyzer.py that implements STEP 5 (Valuation Analysis).

PURPOSE:
Assess whether stocks are reasonably valued given their quality scores, preventing overpaying even for high-quality companies.

REQUIREMENTS:

1. Create ValuationMetrics dataclass:

   @dataclass
   class ValuationMetrics:
       ticker: str
       price: float
       market_cap: float

       # Valuation multiples
       pe_trailing: Optional[float]
       pe_forward: Optional[float]
       peg_ratio: Optional[float]  # P/E / growth rate
       price_to_fcf: Optional[float]
       ev_to_ebitda: Optional[float]
       fcf_yield: Optional[float]  # FCF / market cap

       # Growth metrics
       revenue_growth: Optional[float]  # YoY %
       earnings_growth: Optional[float]  # YoY %

       # Sector comparison
       sector: str
       sector_median_pe: Optional[float]

       # Data quality
       data_quality: str  # COMPLETE, PARTIAL, INSUFFICIENT

   @dataclass
   class ValuationRating:
       ticker: str
       quality_score: float

       # Thresholds
       max_pe_allowed: float  # Quality-adjusted
       actual_pe: float

       # Ratings
       pe_rating: str  # CHEAP, FAIR, EXPENSIVE, OVERVALUED
       peg_rating: str  # CHEAP (<1.0), FAIR (1.0-2.0), EXPENSIVE (>2.0)
       fcf_rating: str  # GOOD (>3%), ACCEPTABLE (1-3%), POOR (<1%)

       # Overall
       overall_rating: str  # CHEAP, FAIR, EXPENSIVE, OVERVALUED
       recommendation: str  # BUY, HOLD, AVOID
       reasoning: str

2. Create ValuationAnalyzer class:

   def fetch_valuation_metrics(self, ticker: str) -> ValuationMetrics:
       """
       Fetch valuation data using yfinance

       Fields to fetch:
       - Current price
       - Market cap
       - Trailing P/E (from info['trailingPE'])
       - Forward P/E (from info['forwardPE'])
       - PEG ratio (from info['pegRatio'])
       - EV/EBITDA (from info['enterpriseToEbitda'])
       - Revenue growth (calculate from financials)
       - Earnings growth (calculate from earnings history)
       - Sector (from info['sector'])

       Calculate:
       - Price/FCF: price / (FCF per share)
       - FCF yield: FCF / market cap
       - PEG: P/E / earnings_growth_rate

       Return: ValuationMetrics
       """

   def calculate_quality_adjusted_threshold(self, quality_score: float) -> float:
       """
       Calculate maximum acceptable P/E based on quality score

       From PM_README_V3.md:
       - Quality score <7: Max 15x P/E (shouldn't own anyway)
       - Quality score 7-8: Max 20x P/E
       - Quality score 8-9: Max 30x P/E
       - Quality score >9: Max 40x P/E (premium allowed for exceptional quality)

       Return: max P/E threshold
       """
       if quality_score < 7:
           return 15.0
       elif quality_score < 8:
           return 20.0
       elif quality_score < 9:
           return 30.0
       else:
           return 40.0

   def rate_pe_valuation(
       self,
       actual_pe: float,
       max_pe: float
   ) -> str:
       """
       Rate P/E valuation

       - actual_pe < 0.7 * max_pe: CHEAP
       - actual_pe < 1.0 * max_pe: FAIR
       - actual_pe < 1.2 * max_pe: EXPENSIVE (but acceptable)
       - actual_pe >= 1.2 * max_pe: OVERVALUED (avoid)
       """

   def rate_peg_ratio(self, peg: float) -> str:
       """
       Rate PEG ratio

       - PEG < 1.0: CHEAP (growing faster than P/E suggests)
       - PEG 1.0-2.0: FAIR
       - PEG > 2.0: EXPENSIVE
       """

   def rate_fcf_yield(self, fcf_yield: float) -> str:
       """
       Rate FCF yield

       - FCF yield >5%: EXCELLENT
       - FCF yield 3-5%: GOOD
       - FCF yield 1-3%: ACCEPTABLE
       - FCF yield <1%: POOR
       """

   def assess_valuation(
       self,
       ticker: str,
       quality_score: float,
       metrics: ValuationMetrics
   ) -> ValuationRating:
       """
       Main method: Comprehensive valuation assessment

       1. Calculate quality-adjusted P/E threshold
       2. Rate P/E (vs threshold)
       3. Rate PEG
       4. Rate FCF yield
       5. Combine into overall rating
       6. Generate recommendation

       Overall rating logic:
       - If P/E is OVERVALUED: overall = OVERVALUED
       - If 2+ metrics are EXPENSIVE: overall = EXPENSIVE
       - If 2+ metrics are CHEAP: overall = CHEAP
       - Else: overall = FAIR

       Recommendation:
       - OVERVALUED → AVOID (don't buy even if quality high)
       - EXPENSIVE → HOLD (acceptable for existing positions if quality >8)
       - FAIR → BUY (good entry point)
       - CHEAP → BUY (excellent entry point)
       """

   def fetch_sector_median_pe(self, sector: str) -> float:
       """
       Get sector median P/E for comparison

       Hardcode common sectors (update periodically):
       - Technology: 28x
       - Communication Services: 22x
       - Healthcare: 25x
       - Financials: 12x
       - Energy: 10x
       - etc.

       Fallback: 20x (market average)
       """

3. Add comparison features:

   def compare_to_sector(
       self,
       ticker: str,
       metrics: ValuationMetrics
   ) -> str:
       """
       Compare valuation to sector median

       Return: "Premium to sector" or "Discount to sector" or "In-line with sector"
       """

4. Export capabilities:
   - export_to_json(ratings, output_file)
   - generate_valuation_report(rating) → markdown
   - export_summary(ratings, output_file) → summary table

TESTING:
- Test valuation metrics fetching
- Test quality-adjusted threshold calculation
- Test P/E rating for various scenarios
- Test PEG rating
- Test FCF yield rating
- Test overall rating logic
- Test recommendation logic
- Test sector comparison
- Test edge cases (negative P/E, missing data)
```

---

### ❌ Task 3.3: Create Data Quality Validator

**What this accomplishes**: Tracks data sources, detects missing/stale metrics, validates data consistency, generates quality reports with completeness scores

**Acceptance Criteria**:
- ✅ Detects all missing critical metrics
- ✅ Flags stale data (>90 days)
- ✅ Identifies data inconsistencies
- ✅ Quality score accurately reflects data completeness
- ✅ Report generation works
- ✅ Tests passing

**Claude Code Prompt**:

```
Create Portfolio Scripts Schwab/data_validator.py that implements STEP 9 (Data Validation).

PURPOSE:
Track data quality, detect missing/stale data, and document data sources for transparency.

REQUIREMENTS:

1. Create DataQualityReport dataclass:

   @dataclass
   class MetricSource:
       metric_name: str
       value: float
       source: str  # e.g., "yfinance", "manual", "calculated"
       fetch_date: str
       confidence: str  # HIGH, MEDIUM, LOW

   @dataclass
   class DataQualityReport:
       ticker: str
       overall_quality: str  # COMPLETE, PARTIAL, INSUFFICIENT
       metrics: List[MetricSource]
       missing_metrics: List[str]
       stale_metrics: List[str]  # >30 days old
       warnings: List[str]

2. Create DataValidator class:

   def validate_financial_data(
       self,
       ticker: str,
       financial_data: FinancialData
   ) -> DataQualityReport:
       """
       Validate completeness and freshness of financial data

       Check:
       - All required fields present (revenue, COGS, assets, equity, etc.)
       - Data is recent (<30 days for price, <90 days for fundamentals)
       - No obvious errors (negative revenue, market cap, etc.)

       Return: DataQualityReport
       """

   def detect_missing_metrics(
       self,
       financial_data: FinancialData
   ) -> List[str]:
       """
       Identify missing critical metrics

       Required metrics:
       - Revenue, COGS, Total Assets, Shareholder Equity
       - Operating Income, Net Income, Operating Cash Flow
       - Total Debt, Market Cap

       Return: List of missing metric names
       """

   def detect_stale_data(
       self,
       financial_data: FinancialData,
       max_age_days: int = 90
   ) -> List[str]:
       """
       Identify metrics that are too old

       Check last_updated date for each metric
       If >max_age_days, flag as stale

       Return: List of stale metric names
       """

   def validate_data_consistency(
       self,
       financial_data: FinancialData
   ) -> List[str]:
       """
       Detect inconsistencies in data

       Checks:
       - Revenue > 0
       - Market cap > 0
       - Assets > Equity (if debt exists)
       - Operating income <= Revenue
       - Gross margin <= 100%

       Return: List of warnings
       """

   def generate_quality_score(
       self,
       report: DataQualityReport
   ) -> float:
       """
       Calculate data quality score (0-10)

       Score calculation:
       - Start at 10
       - -2 for each missing critical metric
       - -1 for each stale metric
       - -0.5 for each warning
       - Minimum 0

       Return: score 0-10
       """

3. Add reporting:

   def generate_validation_report(
       self,
       ticker: str,
       report: DataQualityReport
   ) -> str:
       """
       Generate markdown data quality report

       Format:
       # Data Quality Report: {ticker}

       ## Overall Quality: COMPLETE / PARTIAL / INSUFFICIENT
       Quality Score: 8.5/10

       ## Metrics Summary
       - Total metrics: 15
       - Complete: 13
       - Missing: 2
       - Stale: 0

       ## Missing Metrics
       - Forward P/E (not available)
       - Analyst estimates (no coverage)

       ## Data Sources
       | Metric | Value | Source | Date | Confidence |
       |--------|-------|--------|------|-----------|
       | Revenue | $130.5B | yfinance | 2025-10-28 | HIGH |
       | ROE | 31.8% | calculated | 2025-11-01 | HIGH |

       ## Warnings
       - Asset growth 25% (above 20% threshold)
       """

4. Integration:

   def batch_validate_portfolio(
       self,
       tickers: List[str]
   ) -> Dict[str, DataQualityReport]:
       """Validate entire portfolio"""

TESTING:
- Test detection of missing metrics
- Test detection of stale data
- Test consistency validation
- Test quality score calculation
- Test report generation
```

---

## PHASE 4: VALIDATION & POLISH

### ❌ Task 4.1: Create Framework Compliance Validator

**What this accomplishes**: Validates 80/20 allocation, position sizing, quality/thematic thresholds; detects violations; calculates compliance score; generates compliance reports

**Acceptance Criteria**:
- ✅ Detects all allocation violations
- ✅ Detects oversized positions (>20%)
- ✅ Detects quality holdings below threshold (<7)
- ✅ Detects thematic holdings below threshold (<28)
- ✅ Compliance score accurate
- ✅ Markdown report generated
- ✅ Tests passing

**Claude Code Prompt**:

```
Create Portfolio Scripts Schwab/framework_validator.py that implements STEP 10 (Framework Validation).

PURPOSE:
Ensure all recommendations comply with PM_README_V3.md framework rules (80/20, position sizing, quality thresholds).

REQUIREMENTS:

1. Create ComplianceReport dataclass:

   @dataclass
   class Violation:
       severity: str  # CRITICAL, WARNING, INFO
       category: str  # ALLOCATION, POSITION_SIZE, THRESHOLD, CONCENTRATION
       ticker: Optional[str]
       message: str
       current_value: float
       expected_value: float

   @dataclass
   class ComplianceReport:
       portfolio_value: float
       compliance_score: float  # 0-100%
       violations: List[Violation]
       allocation_quality_pct: float
       allocation_thematic_pct: float
       allocation_cash_pct: float
       framework_compliant: bool  # True if no CRITICAL violations

2. Create FrameworkValidator class:

   def validate_80_20_allocation(
       self,
       portfolio_allocation: PortfolioAllocation
   ) -> List[Violation]:
       """
       Validate 80/20 framework compliance

       Rules (from PM_README_V3.md):
       - Quality holdings: 75-85% (80% target ±5% tolerance)
       - Opportunistic holdings: 15-25% (20% target ±5% tolerance)
       - Cash reserve: ≥3% (5% recommended)

       Violations:
       - CRITICAL: Quality <70% or >90%, Opportunistic >30%, Cash <2%
       - WARNING: Quality 70-75% or 85-90%, Opportunistic 25-30%, Cash 2-3%
       - INFO: Minor deviations within tolerance
       """

   def validate_position_sizing(
       self,
       holdings: Dict[str, float],  # ticker → current %
       quality_scores: Dict[str, float],
       thematic_scores: Dict[str, float]
   ) -> List[Violation]:
       """
       Validate position sizes match framework rules

       Quality position rules:
       - Score 9-10: Should be 10-20%
       - Score 8-8.9: Should be 7-12%
       - Score 7-7.9: Should be 5-8%

       Thematic position rules:
       - Score 35-40: Should be 5-7% (max)
       - Score 30-34: Should be 3-5%
       - Score 28-29: Should be 2-3%

       Violations:
       - CRITICAL: Position >20% (concentration risk), thematic position >7%
       - WARNING: Position outside recommended range by >2%
       - INFO: Position slightly outside range (<2%)
       """

   def validate_quality_thresholds(
       self,
       holdings: Dict[str, str],  # ticker → type (QUALITY or THEMATIC)
       quality_scores: Dict[str, float]
   ) -> List[Violation]:
       """
       Validate all quality holdings meet minimum threshold

       Rules:
       - Quality holdings must have score ≥7
       - Thematic holdings exempt from quality threshold

       Violations:
       - CRITICAL: Quality holding with score <7 (exit immediately)
       - WARNING: Quality holding with score 7.0-7.5 (monitor closely)
       """

   def validate_thematic_thresholds(
       self,
       thematic_holdings: List[str],
       thematic_scores: Dict[str, float]
   ) -> List[Violation]:
       """
       Validate all thematic holdings meet minimum threshold

       Rules:
       - Thematic holdings must have score ≥28/40

       Violations:
       - CRITICAL: Thematic holding with score <28 (exit immediately)
       - WARNING: Thematic holding with score 28-30 (risky, monitor)
       """

   def calculate_compliance_score(
       self,
       violations: List[Violation]
   ) -> float:
       """
       Calculate overall compliance score (0-100%)

       Score calculation:
       - Start at 100
       - -20 for each CRITICAL violation
       - -5 for each WARNING violation
       - -1 for each INFO violation
       - Minimum 0

       Return: score 0-100
       """

   def validate_portfolio(
       self,
       portfolio_state: Dict,
       quality_scores: Dict[str, float],
       thematic_scores: Dict[str, float],
       portfolio_allocation: PortfolioAllocation
   ) -> ComplianceReport:
       """
       Main method: Full framework validation

       Run all validation checks:
       1. 80/20 allocation
       2. Position sizing
       3. Quality thresholds
       4. Thematic thresholds
       5. Concentration risk (any position >20%)

       Combine all violations into ComplianceReport
       Calculate compliance score

       Return: ComplianceReport
       """

3. Add reporting:

   def generate_compliance_report_markdown(
       self,
       report: ComplianceReport
   ) -> str:
       """
       Generate markdown compliance report

       Format:
       # Framework Compliance Report

       ## Compliance Score: 85/100
       Status: ✅ COMPLIANT (no critical violations)

       ## Allocation Summary
       - Quality Holdings: 78% (target 80%, range 75-85%) ✅
       - Opportunistic Holdings: 17% (target 20%, range 15-25%) ✅
       - Cash Reserve: 5% (minimum 3%) ✅

       ## Violations

       ### CRITICAL (0)
       None

       ### WARNING (2)
       - NVDA: Position 22% exceeds recommended 20% max (concentration risk)
       - IONS: Quality score 3.75/10 below threshold 7 (exit recommended)

       ### INFO (1)
       - Cash 5% slightly below recommended 5-7% range

       ## Recommendations
       1. Trim NVDA position to 18% (reduce concentration)
       2. Exit IONS immediately (quality failure)
       3. Maintain cash at 5-7% range
       """

TESTING:
- Test 80/20 allocation validation
- Test position sizing validation
- Test quality threshold validation
- Test thematic threshold validation
- Test compliance score calculation
- Test report generation
```

---

### ❌ Task 4.2: Update Reasoning Agent Thresholds

**What this accomplishes**: Updates reasoning_agent.py to use STEPS decision thresholds (quality <70 for SELL instead of <60), adds thematic score logic, adds STEPS framework references to reasoning text

**Acceptance Criteria**:
- ✅ Quality threshold changed from <60 to <70 for SELL
- ✅ Position sizing aligned with STEPS ranges
- ✅ Thematic score logic added
- ✅ Reasoning text includes framework references
- ✅ Docstrings document threshold sources
- ✅ All tests passing

**Claude Code Prompt**:

~~~
Update Portfolio Scripts Schwab/agents/reasoning_agent.py to use STEPS decision thresholds.

CONTEXT:
- Current implementation uses quality <60 for SELL decisions
- STEPS methodology (PM_README_V3.md) requires quality <70 for exits from core
- Need exact threshold alignment

CHANGES REQUIRED:

1. Update _create_fallback_decision() method:

   Current code (line ~85):
    ```python
   if quality_score < 60:
       return ReasoningDecision(ticker=ticker, action="SELL", ...)
    ```

   Change to:
   ```python
   if quality_score < 70:  # STEPS threshold (PM_README_V3.md line 594)
       return ReasoningDecision(
           ticker=ticker,
           action="SELL",
           confidence=0.9,
           reasoning_steps=[
               f"Quality score {quality_score:.1f}/10 below threshold 7.0",
               "Exit from core holdings (STEPS requirement)",
               "Free capital for higher quality opportunities"
           ],
           key_factors={
               "quality_score": quality_score,
               "threshold": 70.0,
               "violation": "quality_below_minimum"
           },
           target_position_pct=0.0,
           position_type="NONE",
           stop_loss_pct=0.0,
           profit_target_pct=0.0
       )
   ```

2. Update quality score ranges for position sizing:

   Current thresholds → STEPS thresholds:
   - <60 → SELL: Change to <70 → SELL
   - 60-70 → HOLD: Change to 70-80 → HOLD with 5-8% position
   - 70-80 → BUY: Change to 80-90 → BUY with 7-12% position
   - >80 → STRONG BUY: Change to >90 → STRONG BUY with 10-20% position

3. Add thematic score integration:

   ```python
   # After quality score logic, add thematic logic
   if thematic_score is not None:
       if thematic_score < 28:
           return ReasoningDecision(
               ticker=ticker,
               action="SELL",
               confidence=0.85,
               reasoning_steps=[
                   f"Thematic score {thematic_score:.1f}/40 below threshold 28",
                   "Insufficient thematic alignment (STEPS requirement)",
                   "Exit opportunistic position"
               ],
               key_factors={
                   "thematic_score": thematic_score,
                   "threshold": 28.0,
                   "violation": "thematic_below_minimum"
               },
               target_position_pct=0.0,
               position_type="THEMATIC",
               stop_loss_pct=0.0,
               profit_target_pct=0.0
           )
   ```

4. Update reasoning text templates:

   Add STEPS framework references in reasoning:
   - "Quality score 9.0/10 (STEPS: excellent for core, target 10-20% position)"
   - "Quality score 7.2/10 (STEPS: minimum threshold met, target 5-8% position)"
   - "Quality score 6.8/10 (STEPS: below threshold, EXIT recommended)"
   - "Thematic score 32/40 (STEPS: strong contender, target 3-5% position)"

5. Document threshold sources:

   Add docstring to _create_fallback_decision():
   """
   Create rule-based decision when LLM reasoning fails

   Decision thresholds from PM_README_V3.md (80/20 Framework):

   Quality Holdings (Core 80%):
   - Score <7.0: EXIT (line 594)
   - Score 7.0-7.9: HOLD with 5-8% position (line 66)
   - Score 8.0-8.9: BUY/SCALE with 7-12% position (line 65)
   - Score ≥9.0: STRONG BUY with 10-20% position (line 64)

   Thematic Holdings (Opportunistic 20%):
   - Score <28: EXIT (line 117)
   - Score 28-29: HOLD with 2-3% position (line 122)
   - Score 30-34: BUY with 3-5% position (line 121)
   - Score 35-40: STRONG BUY with 5-7% position (line 120)
   """

TESTING:
- Test quality score 69 → SELL decision
- Test quality score 71 → HOLD decision
- Test quality score 85 → BUY decision
- Test quality score 95 → STRONG BUY decision
- Test thematic score 27 → SELL decision
- Test thematic score 32 → BUY decision
- Test reasoning text includes STEPS references
~~~

---

## PROGRESS TRACKING

**Overall**: 4/12 Tasks Complete (33%)

**Phase 1: Critical Infrastructure** (4/4) ✅ Task 1.1, 1.2, 1.3, 1.4 Complete - PHASE COMPLETE!
**Phase 2: Portfolio Construction** (0/3)
**Phase 3: Analysis Modules** (0/3)
**Phase 4: Validation & Polish** (0/2)

---

## FINAL DELIVERABLE

**Single Command**:
```bash
conda run -n trading_env python "Portfolio Scripts Schwab/steps_orchestrator.py"
```

**Output**:
- `trading_recommendations/trading_recommendations_YYYYMMDD.md` (perfect template match)
- All intermediate outputs in `outputs/`
- Complete STEPS compliance
- Ready for manual review

**Success Metrics**:
- ✅ 100% STEPS coverage (all 10 steps)
- ✅ Perfect trading_template.md compliance
- ✅ 80/20 framework enforced
- ✅ Position sizing automated
- ✅ Quality thresholds validated
- ✅ Runtime <30 minutes
- ✅ All tests passing

---

*End of AGENT_CHANGES.md*
