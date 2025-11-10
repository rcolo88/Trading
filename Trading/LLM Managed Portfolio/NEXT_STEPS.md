# Portfolio Construction Implementation Plan

## 11/6/25 - Market Cap Tiered Framework Implementation

### Executive Summary

The research document `quality_investing_thresholds_research.md` requires a **complete replacement** of the current 80/20 framework with a **4-tier market cap-based system** with varying lookback periods for ROE persistence.

**Current System (TO BE REPLACED):** 80/20 Framework
- Quality Holdings (75-85%): Score-based sizing (7-10 scale, no market cap tiers)
- Thematic Holdings (15-25%): Score-based sizing (28-40 scale)

**New System (EXACT REPLICATION OF RESEARCH):** 4-Tier Market Cap Framework
- Core Holdings (65-70%): Large cap ($50B+) with 5+ years ROE >15%
- Growth Quality (15-20%): Mid cap ($2B-$50B) with 2-3 years ROE >15%
- Opportunistic Quality (10-15%): Small cap ($500M-$2B) with 6-8 quarters positive ROE trend
- High Risk/Thematic (5-10%): Momentum plays and thematic investments

**Implementation Approach:** Complete replacement - no backward compatibility needed.

### Architecture Assessment

**Existing Components That Can Be Leveraged:**
1. ✅ `quality_persistence_analyzer.py` - Already analyzes ROE history, just needs integration
2. ✅ `quality_metrics_calculator.py` - Already fetches market_cap data
3. ✅ `portfolio_constructor.py` - Has allocation engine, needs tier logic
4. ✅ `framework_validator.py` - Has validation framework, needs new thresholds
5. ✅ Financial data infrastructure - yfinance integration working

**Components To Be Completely Replaced:**
1. ❌ portfolio_constructor.py - Replace with 4-tier allocation logic
2. ❌ framework_validator.py - Replace with 4-tier validation
3. ❌ Position sizing rules - Tier-specific ranges from research
4. ❌ Framework thresholds - New allocation targets: 65-70/15-20/10-15/5-10
5. ❌ All 80/20 references in code and documentation

**Components To Be Created:**
1. ✨ Market cap classification system (Large/Mid/Small tier detection)
2. ✨ ROE persistence enforcement (5yr/2-3yr/6-8qtr lookback periods)
3. ✨ Incremental ROCE calculation for mid-cap quality detection
4. ✨ Small cap strict quality filters (FCF+, D/E<1.0, GP>30%)

---

## Implementation Prompts for Claude Code

**Progress Tracking:** Check off prompts as they are completed. Update this section after each implementation.

### Phase 1: Market Cap Classification System

#### - [x] Prompt 1.1: Create Market Cap Classifier Module

```
Create a new module `Portfolio Scripts Schwab/market_cap_classifier.py` that classifies stocks into market cap tiers following the research guidelines from quality_investing_thresholds_research.md.

Requirements:
1. Create an enum `MarketCapTier` with values: LARGE_CAP, MID_CAP, SMALL_CAP, MICRO_CAP
2. Define thresholds:
   - Large Cap: ≥$50B
   - Mid Cap: $2B - $50B
   - Small Cap: $500M - $2B
   - Micro Cap: <$500M (not eligible for portfolio)
3. Create a `classify_by_market_cap(market_cap: float) -> MarketCapTier` function
4. Create a `batch_classify_tickers(tickers: List[str]) -> Dict[str, MarketCapTier]` function that fetches market caps via yfinance
5. Add caching (4-hour cache like market_environment_analyzer.py) to avoid redundant API calls
6. Include comprehensive error handling for delisted tickers or missing data
7. Create a comprehensive test suite `test_market_cap_classifier.py` with at least 15 tests

Acceptance Criteria:
- All tests passing
- Handles edge cases (market cap exactly at threshold, missing data, negative values)
- Returns results in <5 seconds for 20 tickers
- Exports results to JSON format
```

#### - [x] Prompt 1.2: Integrate ROE Persistence Requirements

```
Extend the `quality_persistence_analyzer.py` module to add tier-specific ROE persistence validation following quality_investing_thresholds_research.md guidelines.

Requirements:
1. Add a new method `validate_roe_persistence_for_tier(ticker: str, tier: MarketCapTier, historical_data: Dict) -> Tuple[bool, str]`
2. Implement tier-specific validation rules:
   - LARGE_CAP: Require 5+ consecutive years with ROE >15%
   - MID_CAP: Require 2-3 consecutive years with ROE >15%
   - SMALL_CAP: Require 6-8 consecutive quarters with positive ROE trend
3. Return tuple of (passes_requirement: bool, reasoning: str)
4. Add a new method `calculate_incremental_roce(historical_data: Dict) -> float` to identify companies where incremental ROCE exceeds traditional ROCE by 5%+ (indicator of quality improvement)
5. Create dataclass `TierEligibility` with fields:
   - ticker: str
   - market_cap_tier: MarketCapTier
   - meets_roe_persistence: bool
   - roe_persistence_years: float
   - incremental_roce_advantage: float
   - reasoning: str
6. Add method `assess_tier_eligibility(ticker: str) -> TierEligibility` that combines market cap classification and ROE persistence
7. Update test suite to validate all tier-specific logic (add 20+ new tests)

Acceptance Criteria:
- Correctly identifies companies that meet/fail tier-specific ROE requirements
- Incremental ROCE calculation matches academic definition
- All tests passing (existing + new)
- Clear reasoning strings for why a company passes/fails
```

---

### Phase 2: 4-Tier Portfolio Constructor

#### - [x] Prompt 2.1: Replace Portfolio Allocation Engine

```
REPLACE the existing `portfolio_constructor.py` with a new implementation that exactly replicates the 4-tier market cap framework from quality_investing_thresholds_research.md.

IMPORTANT: This is a complete replacement, not a v2. Delete all 80/20 framework logic and replace with 4-tier system.

Requirements:
1. Define new allocation targets and constraints:
   - CORE_LARGE_CAP_TARGET = 67.5% (midpoint of 65-70%)
   - GROWTH_MID_CAP_TARGET = 17.5% (midpoint of 15-20%)
   - OPPORTUNISTIC_SMALL_CAP_TARGET = 12.5% (midpoint of 10-15%)
   - HIGH_RISK_THEMATIC_TARGET = 7.5% (midpoint of 5-10%)
   - CASH_TARGET = 5.0%
   - Tolerance bands: ±2.5% for each tier

2. Create new position sizing rules by tier:
   - Large Cap (ROE 15-20%): 8-12% position
   - Large Cap (ROE 20%+): 10-15% position
   - Mid Cap (ROE 15-20%, incremental ROCE +5%): 5-8% position
   - Mid Cap (ROE 20%+, incremental ROCE +5%): 7-10% position
   - Small Cap (positive ROE trend, strict quality filters): 2-4% position
   - Thematic (all): 1.5-2.5% position (per research: "no single small cap >2% of portfolio")

3. Implement strict quality filters for Small Cap tier (from research):
   - Positive free cash flow required
   - Debt/Equity <1.0 required
   - Gross profitability >30% required
   - Quality score must be in top 80% (exclude bottom quintile to avoid 92% of bankruptcies)

4. Create new dataclass `TieredAllocation`:
   - large_cap_holdings: Dict[str, float]
   - mid_cap_holdings: Dict[str, float]
   - small_cap_holdings: Dict[str, float]
   - thematic_holdings: Dict[str, float]
   - cash_reserve: float
   - tier_allocation_pcts: Dict[MarketCapTier, float]
   - violations: List[str]

5. Implement `calculate_tiered_allocation(holdings: Dict, quality_scores: Dict, market_caps: Dict, roe_persistence: Dict) -> TieredAllocation`

6. Generate rebalancing trades that respect tier-specific position limits

7. Add comprehensive logging showing tier classification and reasoning for each holding

Acceptance Criteria:
- Total allocation always sums to 100%
- Position sizing respects tier-specific limits
- Small cap strict quality filters enforced
- Violations clearly reported
- Compatible with existing portfolio_state.json format (data structure compatible, but logic completely replaced)
- NO references to 80/20 framework remain in code
```

#### - [x] Prompt 2.2: Replace Framework Validator

```
REPLACE the existing `framework_validator.py` with a new implementation that validates the 4-tier market cap framework.

IMPORTANT: This is a complete replacement. Delete all 80/20 validation logic and replace with 4-tier validation.

Requirements:
1. Define validation rules for each tier allocation:
   - CRITICAL violations: Core <62.5% or >72.5%, Any tier >30%, Cash <3%
   - WARNING violations: Any tier outside ±2.5% of target
   - INFO violations: Any tier within ±1% of warning threshold

2. Validate tier-specific position sizing:
   - Large cap: Max 15% per position
   - Mid cap: Max 10% per position
   - Small cap: Max 4% per position (research: 2% typical, 4% absolute max)
   - Thematic: Max 2.5% per position

3. Validate tier eligibility requirements:
   - Large cap: Must have 5+ years ROE >15%
   - Mid cap: Must have 2-3 years ROE >15%
   - Small cap: Must pass all strict quality filters (FCF+, D/E<1, GP>30%)
   - Flag holdings that are in wrong tier

4. Create `TieredComplianceReport` dataclass:
   - portfolio_value: float
   - tier_allocations: Dict[MarketCapTier, float]
   - violations: List[Violation]
   - compliance_score: float (0-100)
   - framework_compliant: bool
   - tier_eligibility_issues: List[str]

5. Implement `validate_tiered_portfolio(portfolio_state, quality_scores, market_caps, roe_persistence) -> TieredComplianceReport`

6. Generate markdown report showing tier breakdown and violations

7. Create comprehensive test suite (40+ tests covering all violation types)

Acceptance Criteria:
- Correctly identifies tier allocation violations
- Position sizing validated per tier limits
- Tier eligibility issues flagged
- Compliance score calculation accurate
- All tests passing
```

---

### Phase 3: Integration with STEPS Workflow

#### - [x] Prompt 3.1: Update STEPS Orchestrator for 4-Tier System

```
Update `steps_orchestrator.py` to integrate the 4-tier market cap framework into the STEPS workflow.

Requirements:
1. Modify STEP 2 (Quality Analysis) to include:
   - Market cap classification for all holdings
   - ROE persistence analysis (5yr/2-3yr/6-8qtr depending on tier)
   - Incremental ROCE calculation for mid-cap candidates

2. Modify STEP 6 (Portfolio Construction) to:
   - Use portfolio_constructor_v2.py for tiered allocation
   - Generate tier-specific rebalancing trades
   - Export tiered allocation report to outputs/tiered_allocation_YYYYMMDD.json

3. Modify STEP 10 (Framework Validation) to:
   - Use framework_validator_v2.py for 4-tier validation
   - Flag holdings in wrong tiers
   - Report tier-specific compliance issues

4. Add new STEP 2B: "Market Cap and Persistence Classification"
   - Classify all holdings by market cap tier
   - Validate ROE persistence requirements
   - Identify tier mismatches (e.g., small cap without strict quality filters)
   - Export to outputs/tier_classification_YYYYMMDD.json

5. Update CLI flags:
   - Add `--validate-tier-eligibility` flag to check tier requirements
   - Add `--show-tier-breakdown` flag to display tier allocation details
   - Remove any 80/20 framework flags (no longer needed)

6. Update all STEPS outputs to include tier information in trading recommendations

Acceptance Criteria:
- STEPS orchestrator runs successfully with 4-tier framework
- Tier classification integrated into quality analysis
- All outputs include tier information
- portfolio_state.json data structure remains compatible (but logic replaced)
- All 80/20 references removed from code and comments
```

#### - [x] Prompt 3.2: Update Recommendation Generator for Tiered Decisions

```
Update `recommendation_generator_script.py` and `agents/reasoning_agent.py` to support tier-based trading decisions.

Requirements:
1. Modify reasoning_agent.py decision logic:
   - Add `market_cap_tier` to agent inputs
   - Implement tier-specific BUY/SELL/HOLD thresholds
   - Large cap: BUY if ROE >15% for 5+ years AND quality score ≥75
   - Mid cap: BUY if ROE >15% for 2-3 years AND incremental ROCE +5% AND quality score ≥70
   - Small cap: BUY if positive ROE trend 6-8 qtrs AND passes all strict filters AND quality score ≥65
   - Thematic: BUY if thematic score ≥28 (unchanged)

2. Add tier mismatch detection:
   - Flag holdings classified as "Large Cap" but failing 5-year ROE requirement → Recommend SELL or reclassify to lower tier
   - Flag holdings classified as "Small Cap" but failing strict quality filters → Recommend SELL

3. Add tier-specific position sizing to recommendations:
   - Include target position size range based on tier
   - Include tier-specific stop-loss and profit targets:
     - Large cap: -15% stop, +30% target (lower risk/reward)
     - Mid cap: -20% stop, +40% target (balanced)
     - Small cap: -25% stop, +50% target (higher risk/reward)
     - Thematic: -30% stop, +60% target (highest risk/reward)

4. Update trading_template.md format to include:
   - Market cap tier for each holding
   - ROE persistence status (meets/fails tier requirement)
   - Tier-specific reasoning in BUY/SELL/HOLD decisions

5. Update recommendation_generator_script.py:
   - Load tier classification from STEP 2B output
   - Pass tier information to reasoning agent
   - Generate tier-aware trading recommendations

Acceptance Criteria:
- Reasoning agent uses tier-specific decision logic
- Tier mismatches flagged in recommendations
- Position sizing matches tier requirements
- Trading recommendations clearly explain tier classification
- All tests updated and passing
```

---

### Phase 4: Testing and Validation

#### - [ ] Prompt 4.1: Create End-to-End 4-Tier System Tests

```
Create a comprehensive end-to-end test suite `test_4tier_system.py` that validates the complete 4-tier framework implementation.

Requirements:
1. Create realistic test portfolios with all 4 tiers represented:
   - Portfolio A: Compliant (all tiers within targets)
   - Portfolio B: Core overweight (large cap >72.5%)
   - Portfolio C: Small cap violations (holdings failing strict quality filters)
   - Portfolio D: Tier mismatches (large cap without 5yr ROE persistence)

2. Test complete workflow:
   - Market cap classification → ROE persistence validation → Tier allocation → Framework validation → Trading recommendations
   - Verify data flows correctly through all steps
   - Confirm violations detected and reported

3. Test migration from 80/20 to 4-tier:
   - Verify existing portfolio_state.json can be read and converted
   - Verify holdings are correctly reclassified into new tiers
   - Verify rebalancing trades generated to reach 4-tier allocation targets

4. Performance tests:
   - Full 4-tier analysis completes in <60 seconds for 20-stock portfolio
   - Market cap classification caches work correctly
   - No redundant API calls

5. Test edge cases:
   - Holdings exactly at market cap thresholds ($50B, $2B, $500M)
   - Companies with incomplete ROE history
   - Companies transitioning between tiers (e.g., mid cap growing to large cap)
   - Portfolio with no small cap holdings
   - Portfolio 100% thematic (should trigger critical violations)

6. Integration tests:
   - STEPS orchestrator runs with `--framework-version 4-tier`
   - All outputs generated correctly
   - Trading recommendations actionable

Acceptance Criteria:
- Minimum 50 tests covering all scenarios
- All tests passing
- Code coverage >90% for all modified modules
- Performance benchmarks met
- Existing portfolio successfully migrates to 4-tier system
- All 80/20 tests replaced with 4-tier equivalents
```

#### - [ ] Prompt 4.2: Update Documentation and Migration Guide

```
Update all documentation to reflect the 4-tier market cap framework and create a migration guide.

Requirements:
1. Update CLAUDE.md:
   - REPLACE "80/20 Framework" sections with "4-Tier Market Cap Framework"
   - Document all tier-specific thresholds, position sizing, and ROE persistence requirements
   - Update Quick Start examples to show 4-tier workflow
   - Remove all 80/20 references
   - Add CLI flag documentation for `--validate-tier-eligibility` and `--show-tier-breakdown`

2. Create new document `MIGRATION_FROM_80_20.md`:
   - Explain differences between old 80/20 and new 4-tier frameworks
   - Provide comparison table (allocation targets, position sizing, risk parameters)
   - Step-by-step one-time migration instructions
   - Answer FAQs: "What happens to my existing holdings?", "How are holdings reclassified?", "What if holdings don't meet tier requirements?"
   - Include example: realistic portfolio transitioning from 80/20 to 4-tier with specific trades needed
   - This is a ONE-TIME migration guide, not for ongoing use

3. REPLACE PM_README_V3.md with PM_README_V4.md:
   - Archive PM_README_V3.md to deprecated/ folder
   - Create PM_README_V4.md documenting 4-tier framework as THE official methodology
   - Include academic research references from quality_investing_thresholds_research.md
   - Add decision trees for tier classification
   - Document rebalancing frequency: Quarterly for small/mid caps, semi-annually for large caps (from research)
   - Remove all 80/20 framework references

4. Create TIER_CLASSIFICATION_GUIDE.md:
   - Detailed explanation of each tier with examples
   - ROE persistence requirements with calculation examples
   - Strict quality filters for small cap (why each filter matters)
   - Common tier mismatch scenarios and how to resolve them

5. Update all inline code comments in modified files to reference 4-tier framework

Acceptance Criteria:
- All documentation accurate and comprehensive
- Migration guide tested with real portfolio examples
- No broken links or outdated references
- All 80/20 references removed or moved to deprecated/ folder
- PM_README_V4.md is the single source of truth for portfolio methodology
- CLAUDE.md accurately reflects 4-tier system only
```

---

### Phase 5: Optional Enhancements

#### - [ ] Prompt 5.1: Add Sector Neutrality Tracking (Optional)

```
OPTIONAL: Implement sector neutrality tracking as mentioned in quality_investing_thresholds_research.md (line 92: "Keeping sector weights similar to the broad market").

Requirements:
1. Create `sector_analyzer.py` module
2. Fetch S&P 500 sector weights (XLK, XLC, XLV, XLF, XLE, XLI, XLP, XLY, XLU, XLRE, XLB)
3. Calculate portfolio sector weights by tier
4. Generate sector deviation report (portfolio % - S&P 500 %)
5. Add warnings if any sector >±10% from market weight
6. Integrate into framework_validator_v2.py as INFO-level violations

This is a nice-to-have enhancement and can be implemented after core 4-tier system is working.
```

#### - [ ] Prompt 5.2: Add Rebalancing Frequency Automation (Optional)

```
OPTIONAL: Automate tier-specific rebalancing frequency recommendations per research guidelines (line 91: "Quarterly for small/mid caps, semi-annually for large caps").

Requirements:
1. Add `last_rebalanced_date` field to portfolio_state.json
2. Create `rebalancing_scheduler.py` module
3. Generate calendar with next rebalancing dates for each tier
4. Send reminders when rebalancing is due
5. Track rebalancing history (frequency, trades executed, outcomes)

This is a nice-to-have enhancement and can be implemented after core 4-tier system is working.
```

---

## Recommended Implementation Order

### Week 1: Foundation
- [x] Prompt 1.1: Build market cap classifier
- [x] Prompt 1.2: Extend ROE persistence analyzer
- [ ] Test tier classification on current holdings

### Week 2: Core Allocation
- [x] Prompt 2.1: Replace portfolio_constructor.py with 4-tier logic (✅ 43/43 tests passing)
- [x] Prompt 2.2: Replace framework_validator.py with 4-tier validation (✅ Functional test passed)
- [ ] Test allocation calculations

### Week 3: Integration - ✅ COMPLETED
- [x] Prompt 3.1: Update STEPS orchestrator (✅ 4-tier integration complete)
- [x] Prompt 3.2: Update recommendation generator (✅ Reasoning agent 4-tier integration complete)
- [ ] Test end-to-end workflow

### Week 4: Testing & Documentation
- [ ] Prompt 4.1: Comprehensive test suite
- [ ] Prompt 4.2: Documentation updates and migration guide
- [ ] User acceptance testing

### Week 5 (Optional): Enhancements
- [ ] Prompt 5.1: Sector neutrality tracking
- [ ] Prompt 5.2: Rebalancing frequency automation

---

## Success Criteria

**Functional Requirements:**
- ✅ 4-tier allocation system operational (65-70/15-20/10-15/5-10)
- ✅ Tier-specific ROE persistence requirements enforced (5yr/2-3yr/6-8qtr)
- ✅ Market cap classification accurate and cached
- ✅ Small cap strict quality filters enforced
- ✅ Framework validation working for 4-tier system
- ✅ Trading recommendations include tier information
- ✅ Complete replacement of 80/20 framework (no coexistence)
- ✅ One-time migration from existing 80/20 portfolio successful

**Performance Requirements:**
- ✅ Full analysis completes in <60 seconds for 20-stock portfolio
- ✅ Market cap classification caches prevent redundant API calls
- ✅ All test suites pass (existing + new)

**Documentation Requirements:**
- ✅ CLAUDE.md updated with 4-tier framework
- ✅ Migration guide created
- ✅ Tier classification guide created
- ✅ All code comments updated

**Quality Requirements:**
- ✅ Code coverage >90% for new modules
- ✅ All edge cases handled gracefully
- ✅ Clear error messages and logging
- ✅ Consistent naming conventions

---

## Risk Mitigation

**Risk 1: Breaking Changes to Existing Portfolio**
- Mitigation: One-time migration script that reclassifies holdings and generates transition trades
- Mitigation: Dry-run mode to preview migration before executing
- Mitigation: Preserve portfolio_state.json data structure (values change, format stays same)

**Risk 2: Insufficient ROE Historical Data**
- Mitigation: Graceful degradation (e.g., 3 years instead of 5 years with warning)
- Mitigation: Clear reporting when holdings fail tier requirements

**Risk 3: Portfolio Disruption During Transition**
- Mitigation: Migration generates transition trades that can be reviewed before execution
- Mitigation: Dry-run mode shows impact before making any changes
- Mitigation: Allow manual override for tier classification in edge cases

**Risk 4: Complexity Increase**
- Mitigation: Excellent documentation and examples
- Mitigation: Clear logging showing tier classification reasoning
- Mitigation: Automated validation catches mistakes

---

## Notes

- This is a COMPLETE REPLACEMENT of the 80/20 framework, not coexistence
- The 4-tier system exactly replicates the research document (quality_investing_thresholds_research.md)
- One-time migration needed for existing portfolio
- Key insight from research: "92% of bankruptcies in small cap were in lowest quality deciles" - strict quality filters are CRITICAL for small cap tier
- The current quality_persistence_analyzer.py already has most needed functionality - just needs integration into portfolio construction workflow
- Thematic allocation reduces from 15-25% to 5-10% (significant change)
- All 80/20 references will be removed from active codebase (optionally archived to deprecated/)

---

## Clarifications Needed (Before Implementation)

1. **Transition Strategy**: For existing holdings, should we immediately reclassify into tiers and generate rebalancing trades, or allow a grace period?
   - Option A: Immediate reclassification, generate trades to reach 4-tier targets
   - Option B: Immediate reclassification, but allow 30-60 days to manually adjust
   - **ANSWER**: Option A

2. **ROE Data Limitations**: What if a stock has only 3 years of data instead of required 5 years for large cap?
   - Option A: Strict - reject and mark as ineligible for large cap tier
   - Option B: Flexible - allow with warning if 3+ years of ROE >15%
   - **ANSWER**: Option B

3. **Small Cap Quality Filters**: The research requires FCF+, D/E<1.0, GP>30%. Should these be strict requirements or warnings?
   - Option A: Strict - fail holdings that don't meet all three criteria
   - Option B: Warnings for existing holdings, strict for new positions
   - **ANSWER**: Option A

4. **Existing Holdings That Fail New Requirements**: If current holding fails tier requirements (e.g., large cap without 5yr ROE >15%), what should happen?
   - Option A: Generate SELL recommendation immediately
   - Option B: Downgrade to lower tier if possible (e.g., large cap → mid cap)
   - Option C: Flag as "under review" and allow manual decision
   - **ANSWER**: Option A

5. **Testing Approach**: Should we test on paper portfolio first before applying to live account?
   - Option A: Dry-run migration mode only (no trades) for 2-4 weeks
   - Option B: Full migration immediately (generate trades and execute)
   - **ANSWER**: Option B

6. **Deprecated 80/20 Code**: Should we keep old code in a deprecated/ folder for reference?
   - Option A: Move to deprecated/ folder (available for reference)
   - Option B: Delete entirely (clean slate)
   - **ANSWER**" Option A