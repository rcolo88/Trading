# Quality Metrics Calculator - Usage Guide

## Overview

The `QualityMetricsCalculator` is a comprehensive tool for evaluating company quality using five academically-validated financial metrics. It provides scoring, tier classification, and red flag detection based on research by Novy-Marx, Piotroski, and other quality investing researchers.

## Quick Start

```python
from quality_metrics_calculator import QualityMetricsCalculator, format_quality_report

# Initialize calculator
calculator = QualityMetricsCalculator()

# Prepare financial data
company_data = {
    'ticker': 'AAPL',
    'revenue': 394_328_000_000,
    'cogs': 223_546_000_000,
    'sga': 26_094_000_000,
    'total_assets': 352_755_000_000,
    'net_income': 99_803_000_000,
    'shareholder_equity': 62_146_000_000,
    'free_cash_flow': 111_443_000_000,
    'market_cap': 3_000_000_000_000,
    'total_debt': 111_088_000_000,
    'nopat': 85_000_000_000,
}

# Calculate quality metrics
result = calculator.calculate_quality_metrics(company_data)

# Print results
print(f"Composite Score: {result.composite_score}/100")
print(f"Quality Tier: {result.tier.value}")
print(f"Red Flags: {len(result.red_flags)}")
```

## The Five Quality Metrics

### 1. Gross Profitability (25% weight)
**Formula:** `(Revenue - COGS) / Total Assets`

**Interpretation:**
- **Excellent (10 pts):** ≥45% - Very strong pricing power and efficiency
- **Good (7-9 pts):** 35-44% - Strong competitive position
- **Average (4-6 pts):** 25-34% - Industry average
- **Poor (1-3 pts):** 15-24% - Below average margins
- **Weak (0 pts):** <15% - Struggling with profitability

**Academic Basis:** Novy-Marx (2013) "The Other Side of Value" - Gross profitability is a powerful predictor of stock returns.

### 2. Return on Equity - ROE (20% weight)
**Formula:** `Net Income / Shareholder Equity`

**Interpretation:**
- **Excellent (10 pts):** ≥25% - Exceptional capital efficiency
- **Good (7-9 pts):** 18-24% - Strong returns to shareholders
- **Average (4-6 pts):** 12-17% - Acceptable returns
- **Poor (1-3 pts):** 5-11% - Below-average returns
- **Weak (0 pts):** <5% or negative - Poor capital allocation

**Academic Basis:** DuPont analysis framework - ROE measures how effectively management uses equity capital.

### 3. Operating Profitability (20% weight)
**Formula:** `(Revenue - COGS - SG&A) / Total Assets`

**Interpretation:**
- **Excellent (10 pts):** ≥30% - Outstanding operational efficiency
- **Good (7-9 pts):** 20-29% - Strong operational performance
- **Average (4-6 pts):** 10-19% - Average efficiency
- **Poor (1-3 pts):** 5-9% - Operational challenges
- **Weak (0 pts):** <5% - Significant inefficiency

**Academic Basis:** Ball et al. (2015) - Operating profitability predicts future earnings growth.

### 4. Free Cash Flow Yield (20% weight)
**Formula:** `Free Cash Flow / Market Cap`

**Interpretation:**
- **Excellent (10 pts):** ≥8% - Attractive valuation with strong cash generation
- **Good (7-9 pts):** 5-7% - Good value and cash flow
- **Average (4-6 pts):** 3-4% - Fair valuation
- **Poor (1-3 pts):** 1-2% - Expensive relative to cash flow
- **Weak (0 pts):** <1% or negative - Very expensive or cash-burning

**Academic Basis:** Piotroski (2000) F-Score - FCF indicates financial health and quality of earnings.

### 5. Return on Invested Capital - ROIC (15% weight)
**Formula:** `NOPAT / (Total Debt + Total Equity)`

**Interpretation:**
- **Excellent (10 pts):** ≥20% - Superior capital allocation
- **Good (7-9 pts):** 15-19% - Strong returns on capital
- **Average (4-6 pts):** 10-14% - Acceptable returns
- **Poor (1-3 pts):** 5-9% - Marginal returns
- **Weak (0 pts):** <5% - Value destruction

**Academic Basis:** Economic value added (EVA) framework - ROIC measures true economic profitability.

## Quality Tier Classification

### Elite (85-100)
Companies with exceptional quality metrics across all dimensions. These businesses typically have:
- Strong competitive moats
- Pricing power
- Exceptional management
- Sustainable competitive advantages

**Investment Approach:** Core holdings for long-term portfolios

### Strong (70-84)
High-quality companies with sustainable business models and strong fundamentals.
- Above-average margins
- Consistent cash generation
- Solid competitive positions

**Investment Approach:** Attractive for growth and quality strategies

### Moderate (50-69)
Average quality companies with some competitive strengths but also areas of concern.
- Mixed fundamentals
- Industry-average performance
- May face competitive pressures

**Investment Approach:** Selective, situation-dependent

### Weak (0-49)
Below-average quality with concerning fundamentals.
- Poor margins or returns
- Competitive disadvantages
- Financial stress

**Investment Approach:** Generally avoid unless deep value opportunity

## Red Flag Detection

The calculator automatically detects five types of red flags:

### 1. High Accruals (>5% of assets)
**Severity:** HIGH
**Implication:** May indicate:
- Aggressive revenue recognition
- Unsustainable earnings quality
- Potential accounting manipulation

**Academic Basis:** Sloan (1996) - High accruals predict lower future returns

### 2. Excessive Asset Growth (>20% YoY)
**Severity:** MEDIUM
**Implication:** May indicate:
- Aggressive expansion
- Integration challenges
- Empire building by management

**Academic Basis:** Cooper, Gulen, and Schill (2008) - Rapid asset growth predicts lower returns

### 3. Deteriorating Margins (>-3% YoY)
**Severity:** HIGH
**Implication:** May indicate:
- Competitive pressure
- Operational issues
- Loss of pricing power

### 4. High Leverage (D/E > 2.0x)
**Severity:** HIGH (>3.0x), MEDIUM (2.0-3.0x)
**Implication:**
- Financial risk
- Interest burden
- Reduced flexibility

### 5. Negative Free Cash Flow
**Severity:** HIGH
**Implication:**
- Cash burn
- Potential liquidity issues
- Unsustainable operations

### 6. Negative ROE
**Severity:** HIGH
**Implication:**
- Value destruction
- Poor capital allocation
- Fundamental business issues

## Required Input Data

### Mandatory Fields
```python
{
    'ticker': str,                    # Stock symbol
    'revenue': float,                 # Total revenue
    'cogs': float,                    # Cost of goods sold
    'sga': float,                     # Selling, general & administrative
    'total_assets': float,            # Total assets
    'net_income': float,              # Net income
    'shareholder_equity': float,      # Shareholder equity
    'free_cash_flow': float,          # Free cash flow
    'market_cap': float,              # Market capitalization
    'total_debt': float,              # Total debt
    'nopat': float                    # Net operating profit after tax
}
```

### Optional Fields (for enhanced analysis)
```python
{
    'roe_history': List[float],       # 10 years of ROE for consistency check
    'accruals': float,                # Accruals as % of assets
    'asset_growth': float,            # YoY asset growth rate
    'margin_change': float,           # YoY margin change
    'prior_year_revenue': float,      # Prior year revenue
    'prior_year_cogs': float          # Prior year COGS
}
```

## Output Structure

### QualityAnalysisResult
```python
@dataclass
class QualityAnalysisResult:
    ticker: str                           # Stock ticker
    metric_scores: List[MetricScore]      # Individual metric scores
    composite_score: float                # 0-100 weighted score
    tier: QualityTier                     # Elite/Strong/Moderate/Weak
    red_flags: List[RedFlag]              # Detected issues
    is_consistent_roe_performer: bool     # ROE >15% for 10+ years
    summary: str                          # Human-readable summary
    raw_metrics: Dict[str, float]         # Raw calculated values
```

### MetricScore
```python
@dataclass
class MetricScore:
    name: str                # Metric name
    value: float             # Raw metric value
    score: float             # 0-10 score
    weight: float            # Metric weight
    weighted_score: float    # Contribution to composite
    percentile: Optional[float]  # Percentile vs peers (if calculated)
```

### RedFlag
```python
@dataclass
class RedFlag:
    category: str            # Red flag category
    severity: str            # HIGH/MEDIUM/LOW
    description: str         # Detailed explanation
    metric_value: float      # The problematic value
```

## Advanced Usage

### Percentile Ranking vs Peers

Compare a company against peer group:

```python
# Target company data
target_data = {...}

# Peer company data
peer_data = [
    {...},  # Peer 1
    {...},  # Peer 2
    {...},  # Peer 3
]

# Calculate with percentile rankings
result = calculator.calculate_percentile_scores(
    ticker='AAPL',
    financial_data=target_data,
    peer_data=peer_data
)

# Access percentile rankings
for metric in result.metric_scores:
    print(f"{metric.name}: {metric.percentile}th percentile")
```

### Formatted Report Generation

```python
from quality_metrics_calculator import format_quality_report

# Generate detailed report
result = calculator.calculate_quality_metrics(company_data)

# With raw data included
full_report = format_quality_report(result, include_raw_data=True)
print(full_report)

# Without raw data
summary_report = format_quality_report(result, include_raw_data=False)
```

### Batch Processing Multiple Companies

```python
companies = {
    'AAPL': {...},
    'MSFT': {...},
    'GOOGL': {...}
}

results = {}
for ticker, data in companies.items():
    try:
        result = calculator.calculate_quality_metrics(data)
        results[ticker] = result
        print(f"{ticker}: {result.composite_score:.1f} ({result.tier.value})")
    except ValueError as e:
        print(f"{ticker}: Error - {e}")

# Find highest quality companies
elite_companies = [
    ticker for ticker, result in results.items()
    if result.tier == QualityTier.ELITE
]
```

## Integration with Trading System

### Example: Filter for Quality Stocks

```python
def filter_quality_stocks(portfolio_tickers, financial_data_source):
    """Filter portfolio for high-quality stocks."""
    calculator = QualityMetricsCalculator()

    high_quality = []
    concerns = []

    for ticker in portfolio_tickers:
        # Fetch financial data
        data = financial_data_source.get_data(ticker)

        # Calculate quality
        result = calculator.calculate_quality_metrics(data)

        # Filter based on criteria
        if result.tier in [QualityTier.ELITE, QualityTier.STRONG]:
            if len([rf for rf in result.red_flags if rf.severity == "HIGH"]) == 0:
                high_quality.append({
                    'ticker': ticker,
                    'score': result.composite_score,
                    'tier': result.tier.value
                })
            else:
                concerns.append({
                    'ticker': ticker,
                    'score': result.composite_score,
                    'red_flags': len(result.red_flags)
                })

    return high_quality, concerns
```

### Example: Generate Investment Report

```python
def generate_quality_report(ticker, financial_data):
    """Generate comprehensive quality report for investment decision."""
    calculator = QualityMetricsCalculator()

    # Calculate quality metrics
    result = calculator.calculate_quality_metrics(financial_data)

    # Decision logic
    decision = "UNKNOWN"

    if result.tier == QualityTier.ELITE:
        high_severity_flags = [rf for rf in result.red_flags if rf.severity == "HIGH"]
        if len(high_severity_flags) == 0:
            decision = "STRONG BUY"
        else:
            decision = "BUY (Monitor red flags)"

    elif result.tier == QualityTier.STRONG:
        if len(result.red_flags) <= 1:
            decision = "BUY"
        else:
            decision = "HOLD"

    elif result.tier == QualityTier.MODERATE:
        decision = "HOLD (Cautious)"

    else:  # WEAK
        decision = "SELL/AVOID"

    # Generate report
    report = format_quality_report(result, include_raw_data=True)
    report += f"\n\nRECOMMENDATION: {decision}\n"

    return report, decision
```

## Academic References

1. **Novy-Marx, R. (2013).** "The Other Side of Value: The Gross Profitability Premium." *Journal of Financial Economics*, 108(1), 1-28.

2. **Piotroski, J. D. (2000).** "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." *Journal of Accounting Research*, 38, 1-41.

3. **Sloan, R. G. (1996).** "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?" *The Accounting Review*, 71(3), 289-315.

4. **Cooper, M. J., Gulen, H., & Schill, M. J. (2008).** "Asset Growth and the Cross-Section of Stock Returns." *The Journal of Finance*, 63(4), 1609-1651.

5. **Ball, R., Gerakos, J., Linnainmaa, J. T., & Nikolaev, V. (2015).** "Deflating Profitability." *Journal of Financial Economics*, 117(2), 225-248.

## Best Practices

### 1. Use Complete Data
Provide all optional fields when available for comprehensive red flag detection:
- Historical ROE data for consistency analysis
- Prior year data for margin trend analysis
- Accruals data for earnings quality assessment

### 2. Context Matters
Quality metrics should be interpreted within industry context:
- Capital-intensive industries (utilities, telecoms) typically have lower ROIC
- Asset-light businesses (software, services) typically have higher margins
- Compare primarily against industry peers

### 3. Combine with Valuation
High quality doesn't guarantee high returns if overpaid:
- Elite companies may be expensive
- FCF Yield provides some valuation insight
- Consider quality-adjusted valuation metrics

### 4. Monitor Changes
Quality is dynamic, not static:
- Track scores over time
- Watch for deteriorating trends
- Pay attention to emerging red flags

### 5. Red Flags Require Investigation
Red flags are warnings, not automatic disqualifications:
- Understand the underlying causes
- Consider management's response
- Evaluate if issues are temporary or structural

## Troubleshooting

### ValueError: Missing required fields
**Solution:** Ensure all mandatory fields are present in input dictionary

### ValueError: Zero denominator
**Solution:** Check that denominators (total_assets, shareholder_equity, market_cap) are non-zero

### Unexpected low scores for high-quality company
**Solution:**
- Verify input data is in correct units (absolute values, not percentages)
- Ensure NOPAT is calculated correctly
- Check that market_cap reflects current valuation

### High-quality company showing red flags
**Solution:**
- Review the specific red flag descriptions
- Consider if flags are false positives (e.g., intentional deleveraging causing D/E spike)
- Evaluate in context of business strategy

## Testing

Run the comprehensive test suite:

```bash
python "Portfolio Scripts Schwab/test_quality_metrics.py"
```

The test suite includes:
1. Basic quality calculation
2. Multi-company comparison
3. Red flag detection
4. Percentile ranking
5. Full report generation
6. Edge case handling

## License & Attribution

This implementation is based on publicly available academic research and is provided for educational and analytical purposes. Always conduct thorough due diligence before making investment decisions.

---

**Last Updated:** 2025-10-30
**Version:** 1.0.0
