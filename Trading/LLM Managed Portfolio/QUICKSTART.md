# Quick Start Guide - 4-Tier Portfolio Analysis System

## Goal
Generate `trading_recommendations/trading_recommendations_YYYYMMDD.md` with AI-powered trading recommendations using the 4-tier market cap framework.

## Prerequisites

1. **Environment Setup**
```bash
# Activate trading environment
conda activate trading_env

# Or create new environment if needed
conda create -n trading_env python=3.11 yfinance matplotlib pandas numpy pandas-market-calendars pytz -c conda-forge -y
```

2. **API Key (Optional but Recommended)**
```bash
# Get free key at https://finnhub.io/
export FINNHUB_API_KEY='your_key_here'
```

## Running the System

### Option 1: Full Automated Pipeline (Recommended)

```bash
cd "Portfolio Scripts Schwab"
./run_all_analysis.sh
```

**What it does:**
1. Generates portfolio report
2. Fetches and analyzes news (if API key set)
3. Runs quality analysis with 4-tier classification
4. Generates trading recommendations

**Output:**
- `trading_recommendations/trading_recommendations_YYYYMMDD.md` ← **REVIEW THIS FILE**

### Option 2: STEPS Orchestrator (Comprehensive 10-Step Analysis)

```bash
cd "Portfolio Scripts Schwab"
python steps_orchestrator.py
```

**What it does:**
- Executes all 10 STEPS of portfolio analysis
- Classifies holdings by market cap tier (Large/Mid/Small/Thematic)
- Validates tier-specific requirements (ROE persistence, strict filters)
- Generates tier-aware recommendations

**Output:**
- `trading_recommendations/trading_recommendations_YYYYMMDD.md`
- `outputs/quality_analysis_YYYYMMDD.json` (includes market_cap_tiers, roe_persistence, strict_filters)

### Option 3: Manual Step-by-Step

```bash
cd "Portfolio Scripts Schwab"

# Step 1: Quality analysis (includes 4-tier classification)
python quality_analysis_script.py

# Step 2: Generate recommendations
python recommendation_generator_script.py
```

## Review and Execute Trades

### 1. Review Recommendations
```bash
cat trading_recommendations/trading_recommendations_20251110.md
```

Look for:
- **Tier-specific reasoning** (e.g., "Large cap tier mismatch: Only 3 years ROE >15%")
- **Position sizing by tier** (Large: 8-15%, Mid: 5-10%, Small: 2-4%, Thematic: 1.5-2.5%)
- **Tier-specific stop-loss** (Large: -15%, Mid: -20%, Small: -25%, Thematic: -30%)

### 2. Approve Trades (Manual)
Edit `Portfolio Scripts Schwab/manual_trades_override.json`:
```json
{
  "enabled": true,
  "trades": [
    {
      "action": "SELL",
      "ticker": "XYZ",
      "shares": 10,
      "reason": "Tier mismatch: Mid cap without 2-3 years ROE persistence",
      "priority": "HIGH"
    },
    {
      "action": "BUY",
      "ticker": "ABC",
      "shares": 5,
      "reason": "Large cap opportunity: Quality 80, ROE 7 years",
      "priority": "HIGH"
    }
  ]
}
```

### 3. Execute Trades (Market Hours Only)
```bash
cd ..  # Return to main directory
python "Portfolio Scripts Schwab/main.py"
```

## Understanding the 4-Tier Framework

### Tier Allocation Targets
- **Large Cap (65-70%)**: Mega-cap quality compounders with 5+ years ROE >15%
- **Mid Cap (15-20%)**: Mid-cap growth with 2-3 years ROE >15%, incremental ROCE +5%
- **Small Cap (10-15%)**: Small-cap quality with 6-8 qtrs ROE trend, FCF+, D/E<1.0, GP>30%
- **Thematic (5-10%)**: Opportunistic theme-driven holdings with score ≥28/40

### Position Sizing by Tier
| Tier | Position Range | Max Position | Stop-Loss | Profit Target |
|------|----------------|--------------|-----------|---------------|
| Large Cap | 8-15% | 15% | -15% | +30% |
| Mid Cap | 5-10% | 10% | -20% | +40% |
| Small Cap | 2-4% | 4% | -25% | +50% |
| Thematic | 1.5-2.5% | 2.5% | -30% | +60% |

### Tier Mismatch Detection
The system automatically flags holdings that don't meet tier requirements:
- **Large Cap** without 5+ years ROE >15% → SELL or downgrade
- **Mid Cap** without 2-3 years ROE or ROCE +5% → SELL
- **Small Cap** failing strict filters → SELL
- **Thematic** with score <28 → SELL

## Troubleshooting

### No trading_recommendations file generated
- Check `outputs/quality_analysis_YYYYMMDD.json` exists
- Verify portfolio_state.json has holdings
- Run with verbose: `python recommendation_generator_script.py --verbose`

### Holdings classified in wrong tier
- Check market cap: Large ≥$50B, Mid $2B-$50B, Small $500M-$2B
- Verify ROE data availability in yfinance
- Review `outputs/quality_analysis_YYYYMMDD.json` for tier classification

### Tier mismatch warnings
- This is expected! The system identifies holdings that don't meet tier requirements
- Review reasoning and consider SELL recommendations
- Example: Large cap with only 2 years ROE >15% should be downgraded or exited

## Files Created

### Input Files
- `portfolio_state.json` - Current holdings and cash
- `Portfolio Scripts Schwab/manual_trades_override.json` - Manual trade approval

### Output Files
- `trading_recommendations/trading_recommendations_YYYYMMDD.md` - Final recommendations
- `outputs/quality_analysis_YYYYMMDD.json` - Quality + tier data
- `outputs/news_analysis_YYYYMMDD.json` - News sentiment
- `outputs/market_environment_YYYYMMDD.json` - Market context

## Next Steps

1. **First Run**: `./run_all_analysis.sh` to generate recommendations
2. **Review**: Read the trading_recommendations file carefully
3. **Approve**: Edit manual_trades_override.json with approved trades
4. **Execute**: Run main.py during market hours (Mon-Fri 9:30AM-4PM ET)
5. **Monitor**: Track tier compliance in outputs/compliance_YYYYMMDD.json

## Support

- Documentation: `CLAUDE.md` - Complete system architecture
- Research: `research docs/quality_investing_thresholds_research.md` - 4-tier framework methodology
- Next Steps: `NEXT_STEPS.md` - Implementation progress
- Tests: Run `python test_portfolio_constructor.py` to verify 4-tier logic
