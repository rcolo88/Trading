# Watchlist Configuration Guide

## Overview

The Watchlist Configuration System provides flexible screening across multiple stock indexes to identify investment opportunities across different market cap tiers. This replaces the hardcoded S&P 500 watchlist with a configurable system that enables screening of mid-cap and small-cap companies.

**Key Feature**: Screen 1,500+ stocks from the S&P Composite 1500 (large + mid + small cap) to find quality opportunities across the full market cap spectrum.

## Supported Indexes

| Index | Description | Ticker Count | Market Cap Range | Use Case |
|-------|-------------|--------------|------------------|----------|
| **SP500** | S&P 500 | ~500 | ≥$50B (Large Cap) | Daily/weekly screening for large cap opportunities |
| **SP400** | S&P MidCap 400 | ~400 | $2B-$50B (Mid Cap) | Finding mid-cap growth opportunities |
| **SP600** | S&P SmallCap 600 | ~600 | $500M-$2B (Small Cap) | Finding small-cap quality opportunities |
| **NASDAQ100** | NASDAQ-100 | ~100 | Varies (Tech Focus) | Tech-focused large cap screening |
| **COMBINED_SP** | S&P Composite 1500 | ~1,500 | $500M+ (All Tiers) | Monthly deep dive across all market caps |
| **CUSTOM** | Custom Ticker List | User-defined | Any | Hand-picked screening |

## Quick Start

### CLI Usage

**Daily Quick Check** (2-5 minutes, uses cache):
```bash
cd "Portfolio Scripts Schwab"
python quality_analysis_script.py --index sp500 --limit 50
```

**Weekly Full Screening** (12-17 minutes):
```bash
python steps_orchestrator.py --watchlist-index sp500
```

**Monthly Deep Dive** (45-60 minutes, screens 1,500 stocks):
```bash
python steps_orchestrator.py --watchlist-index combined_sp
```

**Focus on Mid-Caps** (10-14 minutes):
```bash
python watchlist_generator_script.py --index sp400
```

**Focus on Small-Caps** (15-20 minutes):
```bash
python watchlist_generator_script.py --index sp600
```

**Tech-Focused Screening** (3-5 minutes):
```bash
python quality_analysis_script.py --index nasdaq100
```

### Python API Usage

```python
from watchlist_config import WatchlistConfig, WatchlistIndex
from quality_analysis_script import QualityAnalysisScript

# Daily screening (50 tickers from S&P 500)
config = WatchlistConfig(index=WatchlistIndex.SP500, limit=50)
script = QualityAnalysisScript(watchlist_config=config)
script.run()

# Weekly screening (full S&P 500)
config = WatchlistConfig(index=WatchlistIndex.SP500)
script = QualityAnalysisScript(watchlist_config=config)
script.run()

# Monthly screening (S&P 1500 - all market caps)
config = WatchlistConfig(index=WatchlistIndex.COMBINED_SP)
script = QualityAnalysisScript(watchlist_config=config)
script.run()

# Custom ticker list
config = WatchlistConfig(
    index=WatchlistIndex.CUSTOM,
    custom_tickers=['NVDA', 'GOOGL', 'MSFT', 'AMZN']
)
script = QualityAnalysisScript(watchlist_config=config)
script.run()
```

## Configuration in hf_config.py

The default watchlist configuration can be changed in `hf_config.py`:

```python
from watchlist_config import WatchlistConfig, WatchlistIndex

# Default: S&P 500 (recommended for weekly analysis)
WATCHLIST_CONFIG = WatchlistConfig(index=WatchlistIndex.SP500)

# Alternative: S&P 1500 for comprehensive screening
WATCHLIST_CONFIG = WatchlistConfig(index=WatchlistIndex.COMBINED_SP)

# Alternative: Limited S&P 500 for daily quick checks
WATCHLIST_CONFIG = WatchlistConfig(index=WatchlistIndex.SP500, limit=50)

# Alternative: Custom ticker list
WATCHLIST_CONFIG = WatchlistConfig(
    index=WatchlistIndex.CUSTOM,
    custom_tickers=['NVDA', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']
)
```

## Command-Line Arguments

### quality_analysis_script.py

```bash
python quality_analysis_script.py [OPTIONS]

Options:
  --index {sp500,sp400,sp600,nasdaq100,combined_sp}
                        Index to screen (default: sp500)
  --limit LIMIT         Maximum number of watchlist tickers to analyze (default: 50)
                        Use 0 for no limit (screen entire index)
```

**Examples:**
```bash
# Screen top 50 from S&P 500 (daily, 2-5 min)
python quality_analysis_script.py --index sp500 --limit 50

# Screen full S&P 500 (weekly, 12-17 min)
python quality_analysis_script.py --index sp500 --limit 0

# Screen S&P MidCap 400 (10-14 min)
python quality_analysis_script.py --index sp400 --limit 0

# Screen S&P Composite 1500 (monthly, 45-60 min)
python quality_analysis_script.py --index combined_sp --limit 0
```

### watchlist_generator_script.py

```bash
python watchlist_generator_script.py [OPTIONS]

Options:
  --index {sp500,sp400,sp600,nasdaq100,combined_sp}
                        Index to screen (default: sp500)
  --limit LIMIT         Limit number of tickers to screen (default: None)
  --min-quality SCORE   Minimum quality score for inclusion (default: 70.0)
  --workers N           Number of parallel workers (default: 10)
```

**Examples:**
```bash
# Generate watchlist from S&P 500
python watchlist_generator_script.py --index sp500

# Generate watchlist from S&P MidCap 400
python watchlist_generator_script.py --index sp400

# Generate watchlist from S&P SmallCap 600
python watchlist_generator_script.py --index sp600

# Generate watchlist from S&P 1500 (comprehensive)
python watchlist_generator_script.py --index combined_sp

# Faster analysis with limit
python watchlist_generator_script.py --index combined_sp --limit 200
```

### steps_orchestrator.py

```bash
python steps_orchestrator.py [OPTIONS]

Options:
  --watchlist-index {sp500,sp400,sp600,nasdaq100,combined_sp}
                        Watchlist index to screen (default: sp500)
  --watchlist-limit LIMIT
                        Limit number of watchlist tickers (default: None)
  --skip-thematic       Skip thematic analysis for faster execution
  --skip-competitive    Skip competitive analysis for faster execution
  --skip-valuation      Skip valuation analysis for faster execution
  --dry-run             Test without writing files
  --verbose             Enable detailed debug logging
```

**Examples:**
```bash
# Full STEPS analysis with S&P 500
python steps_orchestrator.py --watchlist-index sp500

# Full STEPS analysis with S&P 1500 (comprehensive)
python steps_orchestrator.py --watchlist-index combined_sp

# Fast analysis with limited tickers
python steps_orchestrator.py --watchlist-index sp500 --watchlist-limit 100

# Focus on mid-caps with S&P 400
python steps_orchestrator.py --watchlist-index sp400

# Dry run to test configuration
python steps_orchestrator.py --watchlist-index combined_sp --dry-run
```

## Performance Expectations

| Configuration | Tickers | Runtime | Use Case |
|---------------|---------|---------|----------|
| SP500 (limit=50) | 50 | 2-5 min | Daily quick check (uses 24h cache) |
| SP500 (full) | ~500 | 12-17 min | Weekly full screening |
| SP400 (full) | ~400 | 10-14 min | Mid-cap focus |
| SP600 (full) | ~600 | 15-20 min | Small-cap focus |
| NASDAQ100 | ~100 | 3-5 min | Tech sector focus |
| COMBINED_SP | ~1,500 | 45-60 min | Monthly comprehensive analysis |

**Optimization Tips:**
- Use `--limit` to screen fewer tickers for faster results
- Daily checks: Use cached data (automatic with 24-hour cache)
- Weekly analysis: Full index screening
- Monthly analysis: S&P 1500 comprehensive screening

## Finding Small-Cap Opportunities

The S&P SmallCap 600 and COMBINED_SP configurations enable screening for small-cap quality companies:

### Step 1: Generate Small-Cap Watchlist

```bash
# Option A: Focus only on small caps
python watchlist_generator_script.py --index sp600

# Option B: Screen all market caps (includes small caps)
python watchlist_generator_script.py --index combined_sp
```

### Step 2: Review Output Files

Check `outputs/quality_watchlist_YYYYMMDD.csv`:
```python
import pandas as pd

df = pd.read_csv('outputs/quality_watchlist_20251111.csv')

# Filter for small caps only
small_caps = df[df['market_cap_tier'] == 'SMALL_CAP']

# Sort by quality score
small_caps = small_caps.sort_values('quality_score', ascending=False)

# Apply strict filters for small caps
# - Quality score ≥70
# - Red flags ≤1
# - Gross margin >30%
filtered = small_caps[
    (small_caps['quality_score'] >= 70) &
    (small_caps['red_flags'] <= 1) &
    (small_caps['gross_profitability'] > 0.30)
]

print(filtered[['ticker', 'quality_score', 'market_cap_tier', 'gross_profitability']])
```

### Step 3: Run STEPS Analysis with Small-Cap Focus

```bash
# Full STEPS analysis screening small caps
python steps_orchestrator.py --watchlist-index sp600

# Or comprehensive across all market caps
python steps_orchestrator.py --watchlist-index combined_sp
```

## Custom Ticker Lists

For targeted screening of specific stocks:

### Method 1: hf_config.py Configuration

```python
# In hf_config.py
WATCHLIST_CONFIG = WatchlistConfig(
    index=WatchlistIndex.CUSTOM,
    custom_tickers=[
        # AI Infrastructure
        'NVDA', 'AMD', 'AVGO', 'INTC',
        # Cloud Computing
        'AMZN', 'GOOGL', 'MSFT', 'CRM',
        # Semiconductors
        'TSM', 'ASML', 'QCOM', 'TXN'
    ]
)
```

### Method 2: Python API

```python
from watchlist_config import WatchlistConfig, WatchlistIndex
from quality_analysis_script import QualityAnalysisScript

config = WatchlistConfig(
    index=WatchlistIndex.CUSTOM,
    custom_tickers=['NVDA', 'GOOGL', 'MSFT', 'AMZN']
)

script = QualityAnalysisScript(watchlist_config=config)
script.run()
```

## Integration with 4-Tier Framework

The watchlist system integrates seamlessly with the 4-tier market cap framework:

### Large Cap (65-70% allocation)
- **Source**: SP500, NASDAQ100
- **Criteria**: Market cap ≥$50B, 5+ years ROE >15%
- **Position Size**: 8-15% per holding
- **Use**: `--watchlist-index sp500` or `--watchlist-index nasdaq100`

### Mid Cap (15-20% allocation)
- **Source**: SP400
- **Criteria**: Market cap $2B-$50B, 2-3 years ROE >15%, incremental ROCE >5%
- **Position Size**: 5-10% per holding
- **Use**: `--watchlist-index sp400`

### Small Cap (10-15% allocation)
- **Source**: SP600
- **Criteria**: Market cap $500M-$2B, 6-8 qtrs ROE trend, strict filters (FCF+, D/E<1.0, GP>30%)
- **Position Size**: 2-4% per holding
- **Use**: `--watchlist-index sp600`

### Thematic (5-10% allocation)
- **Source**: CUSTOM (theme-specific tickers)
- **Criteria**: Thematic score ≥28/40
- **Position Size**: 1.5-2.5% per holding
- **Use**: Custom ticker lists for specific themes

## Workflow Examples

### Workflow 1: Weekly Portfolio Review

```bash
# Monday morning: Quick check of top 50 opportunities
python quality_analysis_script.py --index sp500 --limit 50

# Review outputs/quality_analysis_YYYYMMDD.json for:
# - SELL candidates (holdings with quality <70)
# - BUY alternatives (watchlist with quality ≥85)
```

### Workflow 2: Monthly Deep Dive

```bash
# First Saturday of month: Comprehensive screening
python steps_orchestrator.py --watchlist-index combined_sp

# This screens 1,500 stocks across all market caps
# Focus on finding:
# - Mid-cap opportunities (SP400)
# - Small-cap opportunities (SP600)
# - Undervalued large caps

# Review trading_recommendations/trading_recommendations_YYYYMMDD.md
```

### Workflow 3: Sector-Specific Analysis

```bash
# Tech sector focus using NASDAQ-100
python quality_analysis_script.py --index nasdaq100

# Review for:
# - Tech leaders with quality ≥85
# - AI infrastructure plays
# - Cloud computing opportunities
```

### Workflow 4: Mid-Cap Growth Hunt

```bash
# Screen S&P MidCap 400 for growth opportunities
python watchlist_generator_script.py --index sp400

# Filter outputs/quality_watchlist_YYYYMMDD.csv for:
# - Quality score ≥75
# - ROE persistence 2-3 years
# - Incremental ROCE >5%
# - Market cap $2B-$50B
```

## Troubleshooting

### Issue: Fetcher Timeout or Failure

**Symptom**: `Failed to fetch tickers from sp500`

**Solution**:
```bash
# Check internet connection
ping wikipedia.org

# Try manual fetch to diagnose
python -c "from financial_data_fetcher import get_sp500_tickers; print(len(get_sp500_tickers()))"

# If Wikipedia is blocked, consider alternative:
# - Use CUSTOM index with manual ticker list
# - Check firewall/proxy settings
```

### Issue: Analysis Takes Too Long

**Symptom**: Quality analysis running >30 minutes

**Solution**:
```bash
# Use limit parameter to reduce ticker count
python quality_analysis_script.py --index sp500 --limit 100

# Or use smaller index
python quality_analysis_script.py --index nasdaq100

# Reduce parallel workers if memory-constrained
python watchlist_generator_script.py --index sp500 --workers 5
```

### Issue: Duplicate Tickers in COMBINED_SP

**Symptom**: Same ticker appears multiple times

**Solution**: The system automatically deduplicates. If you see duplicates in the output file, this is a bug. Report it with:
```bash
python -c "from watchlist_config import WatchlistConfig, WatchlistIndex; config = WatchlistConfig(index=WatchlistIndex.COMBINED_SP); tickers = config.get_tickers(); print(f'Total: {len(tickers)}, Unique: {len(set(tickers))}')"
```

## Testing

Run the comprehensive test suite:

```bash
cd "Portfolio Scripts Schwab"
python test_watchlist_config.py
```

**Expected Output**:
```
test_enum_members (__main__.TestWatchlistIndex) ... ok
test_enum_values (__main__.TestWatchlistIndex) ... ok
test_get_tickers_combined_sp (__main__.TestWatchlistConfig) ... ok
...
----------------------------------------------------------------------
Ran 30 tests in 0.5s

OK
```

## Best Practices

### Daily Analysis (2-5 minutes)
- Use `--index sp500 --limit 50`
- Leverages 24-hour cache for speed
- Focus on catching urgent opportunities

### Weekly Analysis (12-17 minutes)
- Use `--index sp500` (no limit)
- Run on weekends or evenings
- Generate full trading recommendations

### Monthly Analysis (45-60 minutes)
- Use `--index combined_sp`
- Run first weekend of month
- Comprehensive screening across all market caps
- Find mid/small-cap opportunities

### Targeted Analysis
- Mid-cap focus: `--index sp400`
- Small-cap focus: `--index sp600`
- Tech focus: `--index nasdaq100`
- Theme focus: Use CUSTOM with hand-picked tickers

## API Reference

### WatchlistIndex Enum

```python
class WatchlistIndex(Enum):
    SP500 = "sp500"              # S&P 500 (large cap)
    SP400 = "sp400"              # S&P MidCap 400
    SP600 = "sp600"              # S&P SmallCap 600
    NASDAQ100 = "nasdaq100"      # NASDAQ-100 (tech large cap)
    COMBINED_SP = "combined_sp"  # SP500 + SP400 + SP600
    CUSTOM = "custom"            # Custom ticker list
```

### WatchlistConfig Dataclass

```python
@dataclass
class WatchlistConfig:
    index: WatchlistIndex
    custom_tickers: Optional[List[str]] = None
    limit: Optional[int] = None

    def get_tickers(self) -> List[str]:
        """Get tickers based on configuration"""
        ...

    def get_ticker_count(self) -> int:
        """Get expected number of tickers"""
        ...
```

### Helper Functions

```python
def get_default_watchlist_config(frequency: str) -> WatchlistConfig:
    """
    Get default configuration for frequency

    Args:
        frequency: "daily", "weekly", or "monthly"

    Returns:
        WatchlistConfig for the frequency
    """
```

## Migration from Legacy WATCHLIST_TICKERS

If you have code using the deprecated `WATCHLIST_TICKERS`:

**Old Code:**
```python
from hf_config import HFConfig

# Set custom ticker list
HFConfig.WATCHLIST_TICKERS = ['NVDA', 'GOOGL', 'MSFT']
```

**New Code:**
```python
from watchlist_config import WatchlistConfig, WatchlistIndex
from hf_config import HFConfig

# Set custom ticker list
HFConfig.WATCHLIST_CONFIG = WatchlistConfig(
    index=WatchlistIndex.CUSTOM,
    custom_tickers=['NVDA', 'GOOGL', 'MSFT']
)
```

**Backward Compatibility**: The legacy `WATCHLIST_TICKERS` is still supported but will log a deprecation warning. Update to `WATCHLIST_CONFIG` as soon as possible.

## Support

For issues or questions:
1. Review this guide thoroughly
2. Check the test suite: `python test_watchlist_config.py`
3. Review output files in `outputs/` directory
4. Check logs in `trade_execution.log`
5. Consult `CLAUDE.md` for system architecture

## Related Documentation

- **README.md**: Quick start guide and system overview
- **CLAUDE.md**: Complete system architecture
- **quality_investing_thresholds_research.md**: 4-tier framework methodology
- **QUICKSTART.md**: Step-by-step getting started guide
