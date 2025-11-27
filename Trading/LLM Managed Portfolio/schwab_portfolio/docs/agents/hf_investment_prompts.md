# HuggingFace Investment Research - Implementation Prompts

## Philosophy
Focus on **quality metrics** (not value or momentum) combined with **thematic analysis** for growth companies. Quality acts as risk management; thematic analysis is the alpha source.

---

# PART 1: QUALITY METRICS FRAMEWORK

## Prompt 1: Core Quality Metrics Calculator

```
Create a QualityMetricsCalculator class that calculates five academically-validated quality metrics:

1. Gross Profitability = (Revenue - COGS) / Total Assets (25% weight)
2. Return on Equity (ROE) = Net Income / Shareholder Equity (20% weight)
3. Operating Profitability = (Revenue - COGS - SG&A) / Total Assets (20% weight)
4. Free Cash Flow Yield = Free Cash Flow / Market Cap (20% weight)
5. ROIC = NOPAT / (Total Debt + Total Equity) (15% weight)

Features needed:
- Score each metric 0-10 based on absolute thresholds and percentile ranking
- Calculate weighted composite score (0-100)
- Classify into tiers: Elite (85-100), Strong (70-84), Moderate (50-69), Weak (0-49)
- Identify companies maintaining ROE >15% for 10+ years
- Detect red flags: high accruals (>5%), excessive asset growth (>20% YoY), deteriorating margins, high leverage (D/E >2.0)

Input: Dictionary with financial metrics
Output: Metrics, scores, composite score, tier classification, red flags, summary text

Include comprehensive docstrings and type hints.
```

---

## Prompt 2: Quality Screening Prompt Generator

```
Create generate_quality_screening_prompt() function that generates optimized prompts for HuggingFace LLM models.

Prompt structure (under 600 tokens for 7B models):
- Role: "You are an equity research analyst specializing in quality investing"
- Present the 5 calculated quality metrics with scores
- Chain-of-thought steps: (1) assess profitability, (2) examine returns, (3) analyze cash flow, (4) identify strengths, (5) identify concerns, (6) check red flags, (7) synthesize

Request structured output:
- QUALITY RATING: Strong/Moderate/Weak
- KEY STRENGTHS: (2-3 bullets)
- KEY CONCERNS: (2-3 bullets)
- RED FLAGS: Yes/No with specifics
- OVERALL ASSESSMENT: (50 words max)
- CONFIDENCE: High/Medium/Low

Include batch version for processing multiple companies.
```

---

## Prompt 3: Quality Persistence Analyzer

```
Create QualityPersistenceAnalyzer class to identify "quality compounders" - companies sustaining high metrics over time.

Input: Historical financial data (pandas DataFrame), minimum 3-5 years per company

Key methods:
1. calculate_persistence_metrics(): Track ROE/margin/ROIC/FCF stability and trends over time
2. classify_company(): Categorize as Quality Compounder (sustained excellence), Quality Improver (improving trends), Quality Deteriorator (declining), or Inconsistent (cyclical)
3. analyze_quality_trends(): Identify mean reversion risk, recent vs historical performance, trend drivers
4. generate_persistence_analysis_prompt(): Create targeted LLM prompts based on classification
5. visualize_persistence(): Chart ROE, margins, ROIC, FCF conversion over time
6. analyze_universe(): Batch process multiple companies, rank by compounder confidence

Focus: Identify truly durable businesses through historical consistency, not just current snapshots.
```

---

# PART 2: THEMATIC INVESTING FRAMEWORK

## Prompt 4: Thematic Prompt Template Builder

```
Create ThematicPromptBuilder class with sector-specific prompt generators for growth/thematic investing.

Initialize with model_type ('7B'/'13B'/'70B') to set token budgets (800/1200/2000 tokens).

Implement theme-specific methods that rate companies 1-10 across 5 dimensions:

1. ai_infrastructure_prompt(): Value chain position, technical differentiation, traction, moat, unit economics
2. nuclear_renaissance_prompt(): Technology readiness, regulatory progress, partnerships, government support, timeline
3. defense_modernization_prompt(): Program stability, tech superiority, growth runway, financials, geopolitical tailwinds
4. climate_tech_prompt(): Technology maturity, unit economics, policy support, demand/scalability, carbon impact
5. longevity_biotech_prompt(): Science quality, clinical progress, commercial potential, IP position, management/financing
6. generic_thematic_prompt(): Flexible template for custom themes with user-defined criteria

All prompts output: 5 scores with rationales, overall score /50, classification, key strength/risk, investment stance.

Include utilities: estimate_token_count(), validate_prompt_length(), compress_prompt()
```

---

## Prompt 5: Catalyst Calendar Generator

```
Build CatalystAnalyzer class that identifies upcoming events that could drive stock performance.

Key methods:
1. generate_catalyst_prompt(): Ask LLM to create calendar with near-term (0-6mo), medium-term (6-18mo), long-term (18mo+) catalysts. For each: name, timeline, probability (H/M/L), impact (H/M/L), direction (+/-/neutral), dependencies. Request top 5 prioritized.

2. parse_catalyst_response(): Extract structured data from LLM output (handle format variations)

3. prioritize_catalysts(): Score by formula: time_weight/(timeline_months) + probability_score + impact_score + direction_bonus. Default weights: time=2.0, prob=3.0, impact=5.0

4. create_monitoring_schedule(): Generate calendar with key dates and check-in reminders

5. generate_catalyst_summary_report(): Markdown report with executive summary, top 5 catalysts, detailed calendar tables, monitoring recommendations

6. batch_analyze_catalysts(): Process multiple companies for portfolio monitoring

Focus: Help time entries/exits around specific events rather than just "buy and hold."
```

---

## Prompt 6: Theme Timing Analyzer

```
Create ThemeTimingAnalyzer to assess which thematic sectors are currently favorable vs late-cycle.

Key methods:
1. analyze_theme_momentum(): Calculate for theme basket: absolute momentum (1M/3M/6M/12M returns), relative strength vs market, dispersion (high=early cycle, low=mature), breadth (% positive, new highs)

2. generate_theme_assessment_prompt(): Ask LLM to classify cycle stage (Early/Mid/Late/Mature), assess leadership rotation, identify catalysts/risks, provide contrarian take, recommend action (Accumulate/Hold/Trim/Avoid)

3. detect_rotation_signals(): Identify if capital rotating between themes (from high-growth to value, risk-on to risk-off, etc.)

4. compare_theme_valuations(): Calculate median P/E, P/S, EV/Sales vs historical percentile and market average

5. generate_theme_timing_report(): Markdown report with cycle stage, momentum, valuation, recommendations

6. batch_theme_analysis(): Process multiple themes, detect rotations, rank by attractiveness

Focus: Prevent investing in great themes at wrong time (late-cycle, overcrowded).
```

---

## Prompt 7: Multi-Theme Portfolio Constructor

```
Build ThematicPortfolioBuilder that creates diversified portfolios across themes.

Initialize with risk_tolerance ('conservative'/'moderate'/'aggressive').

Key methods:
1. load_thematic_analyses(): Import LLM outputs and scores for each theme

2. calculate_theme_correlations(): Build correlation matrix between themes (low correlation = better diversification)

3. optimize_allocation(): Determine optimal weights using hybrid approach: start with conviction scores, adjust for correlations, apply concentration limits, respect cycle stage. Constraints: max_concentration (e.g., 35%), min_allocation (e.g., 10%). Output: allocations, expected return/volatility, diversification score

4. generate_portfolio_rationale_prompt(): Ask LLM to explain: portfolio narrative (why these themes now?), allocation reasoning (justify each weight), diversification story (how themes complement), risk factors (what hurts multiple themes?), rebalancing triggers, time horizon

5. generate_portfolio_report(): Markdown report with allocations, investment thesis, correlation matrix, risk management, monitoring guidelines

6. backtest_allocation(): Simulate historical performance with rebalancing

7. stress_test_portfolio(): Test under adverse scenarios (crash, rate spike, recession, bubble burst)

Focus: Balance conviction with diversification for smoother returns across volatile themes.
```

---

## Implementation Priority

**Phase 1 (Core Quality):**
- Prompt 1: Quality Metrics Calculator
- Prompt 2: Quality Prompt Generator
- Test on 5-10 companies

**Phase 2 (Quality Depth):**
- Prompt 3: Quality Persistence Analyzer
- Test identifying compounders in S&P 500

**Phase 3 (Thematic Foundation):**
- Prompt 4: Thematic Prompt Builder (all 5 sectors)
- Test on sample companies in each theme

**Phase 4 (Thematic Enhancement):**
- Prompt 5: Catalyst Calendar Generator
- Prompt 6: Theme Timing Analyzer
- Test identifying catalysts and cycle stages

**Phase 5 (Portfolio Integration):**
- Prompt 7: Multi-Theme Portfolio Constructor
- Combine quality screening + thematic analysis
- Generate full portfolio report

---

## Key Design Principles

1. **Quality First**: Use quality metrics as risk management, not alpha generation
2. **Thematic Alpha**: Forward-looking thematic analysis is your edge
3. **Simplicity**: Fewer factors = clearer attribution and easier execution
4. **Parseable Outputs**: All LLM prompts request structured formats with numerical scores
5. **Batch Processing**: Design for analyzing multiple companies/themes efficiently
6. **Token Optimization**: Keep prompts under 800 tokens for 7B models