# Quality Analysis Lookback Periods Reference Guide

**Last Updated:** January 16, 2026  
**Purpose:** Guidance on lookback periods for quality investing metrics

---

## Executive Summary

This document provides recommended lookback periods for each section of the quality analysis framework, based on academic research findings. The lookback period determines the time window over which metrics are measured, and choosing appropriate periods is critical for capturing true quality signals while filtering out noise.

### Core Quality Score Matrix

Based on meta-analysis of academic research, optimal factor weights with recommended lookback periods:

| Factor Category | Weight | Primary Metric | Secondary Metrics | Lookback Period |
|----------------|--------|----------------|-------------------|-----------------|
| Profitability | 35% | Gross Profitability | ROE, ROIC, Operating Margin | 1-3 years |
| Earnings Quality | 20% | Accrual Ratio | Cash Conversion, F-Score components | 1-3 years |
| Growth Quality | 15% | Asset Growth (inverse) | Revenue Quality, Margin Trend | 1-5 years |
| Safety | 15% | Leverage Ratios | Beta, Volatility, Z-Score | 1-5 years |
| ROE Persistence | 15% | Years > 15% ROE | ROE Trend, Incremental ROCE | 3-5 years |

### Market Cap Adjustment Framework

The lookback period should be adjusted based on company market capitalization to account for data quality and volatility differences. Smaller caps have less data and higher volatility, requiring shorter lookback periods:

| Market Cap Tier | Size Definition | Lookback Multiplier | Adjusted Lookback Range |
|-----------------|----------------|---------------------|------------------------|
| Mega Cap | > $200B | 1.25x (extended) | 1-5 years |
| Large Cap | $10B - $200B | 1.0x (baseline) | 1-5 years |
| Mid Cap | $2B - $10B | 0.75x (reduced) | 1-4 years |
| Small Cap | $300M - $2B | 0.5x (minimum) | 1-3 years |
| Micro Cap | < $300M | 0.35x (very minimum) | 1-2 years |

**Formula:** `Adjusted Lookback = Base Lookback × Market Cap Multiplier`

**Example:**
- Base lookback for ROE Persistence: 5 years
- Large Cap multiplier: 1.0x
- Adjusted lookback: 5 × 1.0 = 5 years (full 5-year assessment)

- Base lookback for ROE Persistence: 5 years
- Small Cap multiplier: 0.5x
- Adjusted lookback: 5 × 0.5 = 2.5 years (rounded to 2-3 years)

---

## Section 1: Earnings Quality (20% Weight)

### Metrics Covered
- Accrual Ratio
- Cash Conversion Ratio
- Piotroski F-Score Components

### Recommended Lookback Period: 1-3 Years

#### Primary Research Foundation

**Sloan (1996) - The Accrual Anomaly**
- Original research used **1-year accrual ratios** measured from annual financial statements
- The study ranked stocks by prior year's accrual ratio and held for one year
- Key finding: Firms with small or negative accruals outperformed by approximately 10% annually
- Implementation: Use trailing 12-month or most recent annual data

**Piotroski (2000) - F-Score**
- Uses **year-over-year comparisons** (1-year lookback) for all 9 signals
- Signals compare current year metrics to prior year metrics
- Designed for value investors screening for financial health
- Implementation: Compare most recent fiscal year to prior fiscal year

**Dechow, Khimich, and Sloan (2011) - Accrual Anomaly Review**
- Confirmed 1-year measurement period is optimal for accrual-based signals
- Longer windows reduce predictive power due to information decay
- Quarterly measurements show similar patterns but with more noise

#### Recommended Implementation

| Metric | Lookback Period | Calculation Method |
|--------|----------------|-------------------|
| Accrual Ratio | 1 year | (Net Income - Operating Cash Flow) / Average Total Assets |
| Cash Conversion | Trailing 12 months | Operating Cash Flow / Net Income |
| F_ROA | 1 year | ROA current year vs. prior year |
| F_CFO | 1 year | CFO > 0 |
| F_ΔROA | 1 year | ROA increase YoY |
| F_ACCRUAL | 1 year | CFO > Net Income |
| F_ΔLEVER | 1 year | Long-term debt/Assets decrease YoY |
| F_ΔLIQUID | 1 year | Current ratio increase YoY |
| F_EQ_OFFER | 1 year | No new shares issued |
| F_ΔMARGIN | 1 year | Gross margin increase YoY |
| F_ΔTURN | 1 year | Asset turnover increase YoY |

#### Scoring Approach

For Earnings Quality scoring, consider using a **multi-year composite**:

1. **Primary Score (Weight: 70%)**: Most recent 1-year metrics
2. **Consistency Bonus (Weight: 30%)**: Average of trailing 3 years

This approach rewards both current quality and historical consistency while preventing companies with one good year from scoring highly.

#### Red Flag Thresholds

| Metric | Red Flag Threshold | Severity |
|--------|-------------------|----------|
| Accrual Ratio | > 10% (positive) | HIGH |
| Accrual Ratio | < -10% (very negative) | MODERATE (potential distress) |
| Cash Conversion | < 0.8 | HIGH |
| F-Score | ≤ 3 | CRITICAL |
| Negative Operating Cash Flow | Any period | MODERATE |

---

## Section 2: Growth Quality (15% Weight)

### Metrics Covered
- Asset Growth (inverse relationship)
- Revenue Quality
- Margin Trend

### Recommended Lookback Period: 3-5 Years

#### Primary Research Foundation

**Cooper, Gulen, and Schill (2008) - Asset Growth Anomaly**
- Original research used **annual asset growth** measured over 1-year periods
- Key finding: Low asset growth stocks outperformed high asset growth stocks by approximately 20% annually
- Portfolio formation used 1-year asset growth ranks, holding for 1 year
- Implementation: Calculate annual asset growth rate from balance sheet changes

**AQR Quality Minus Junk (Asness, Frazzini, Pedersen, 2014)**
- Growth metrics use **5-year growth rates** for profitability measures
- Growth scores based on 5-year changes in:
  - Gross profits
  - ROE
  - ROA
  - Cash flow from operations
  - Gross margin
- Rationale: Longer windows capture sustainable growth patterns
- Implementation: Compound annual growth rate (CAGR) over 5 years

**Chan, Karceski, and Lakonishok - Growth Persistence Research**
- Found limited persistence in long-term earnings growth beyond chance
- Recommended **3-5 year measurement periods** for growth analysis
- Growth forecasts (IBES) showed low predictive power
- Implementation: Use 3-year or 5-year CAGR with trend analysis

#### Recommended Implementation

| Metric | Lookback Period | Calculation Method |
|--------|----------------|-------------------|
| Asset Growth | 1 year (primary), 3 years (secondary) | (Total Assets_t - Total Assets_{t-1}) / Total Assets_{t-1} |
| Asset Growth Trend | 3 years | Slope of asset growth over 3 years |
| Revenue Growth | 3-5 years | Revenue CAGR |
| Revenue Quality | 3 years | Core Revenue / Total Revenue (average) |
| Margin Trend | 3-5 years | Change in operating/gross margin |
| Gross Margin Improvement | 3 years | Current margin - margin 3 years ago |

#### Scoring Approach

For Growth Quality scoring, use **shorter windows for asset growth** (which needs to be timely) and **longer windows for margin/revenue trends** (which need to be persistent):

1. **Asset Growth (40% of Growth Quality)**: 1-year measurement
   - Lower is better (contrarian signal)
   - Flag if > 20% annually

2. **Revenue Quality (30% of Growth Quality)**: 3-year average
   - Higher core revenue percentage is better
   - Measures sustainability of revenue base

3. **Margin Trend (30% of Growth Quality)**: 3-5 year trend
   - Improving margins indicate operating leverage
   - Calculate margin change over measurement period

#### Red Flag Thresholds

| Metric | Red Flag Threshold | Severity |
|--------|-------------------|----------|
| Asset Growth | > 20% annually | HIGH |
| Asset Growth | > 30% annually | CRITICAL |
| Revenue Decline | 3-year CAGR < 0% | HIGH |
| Margin Compression | > 500 bps decline over 3 years | HIGH |

---

## Section 3: Safety (15% Weight)

### Metrics Covered
- Leverage Ratios
- Beta (Market Risk)
- Volatility (Idiosyncratic)
- Z-Score (Bankruptcy Risk)

### Recommended Lookback Period: 1-5 Years (varies by metric)

#### Primary Research Foundation

**Asness, Frazzini, Pedersen (2014) - QMJ Safety Metrics**
- Beta calculated using **5-year rolling regression** against market
- Idiosyncratic volatility measured over **3-5 year periods**
- Leverage ratios use **most recent quarterly** or annual data
- Bankruptcy measures (Ohlson O-Score, Altman Z-Score) use annual financial data

**Fama-French Five-Factor Model (2015)**
- Factor definitions use annual accounting data
- RMW (Robust Minus Weak profitability) uses annual operating profitability
- CMA (Conservative Minus Aggressive investment) uses annual asset growth
- Market beta typically calculated over **36-60 months**

**Academic Literature on Beta Estimation**
- Dimson (1979): Recommended using **longer horizons** (up to 5 years) to reduce estimation error
- Vasicek (1973): Bayesian approach blending with market average
- Common practice: **3-year rolling beta** is standard in industry
- For low-volatility strategies: **5-year lookback** recommended

**Volatility Measurement Standards**
- Historical volatility typically measured over **1-3 year periods**
- For quality screening: **3-year annualized volatility** is common
- Idiosyncratic volatility requires longer windows to be reliable

**Altman Z-Score**
- Original research used **annual financial statement data**
- Predicts bankruptcy within 2 years
- Formula: Z = 1.2X1 + 1.4X2 + 3.3X3 + 0.6X4 + 1.0X5
- Update annually or quarterly

#### Recommended Implementation

| Metric | Lookback Period | Calculation Method |
|--------|----------------|-------------------|
| Beta | 3-5 years | Rolling regression against market index |
| Idiosyncratic Volatility | 3 years | Residuals from market regression |
| Total Debt/Equity | Most recent quarter | Total Debt / Total Equity |
| Debt/EBITDA | Trailing 12 months | Total Debt / EBITDA |
| Interest Coverage | Trailing 12 months | EBIT / Interest Expense |
| Current Ratio | Most recent quarter | Current Assets / Current Liabilities |
| Quick Ratio | Most recent quarter | (Cash + Receivables) / Current Liabilities |
| Altman Z-Score | Most recent annual | 5-variable bankruptcy predictor |
| Earnings Volatility | 3-5 years | Standard deviation of EPS over period |

#### Scoring Approach

For Safety scoring, use **longer windows for volatility measures** and **shorter windows for leverage ratios**:

1. **Beta (30% of Safety)**: 5-year rolling
   - Lower is better (more defensive)
   - Blend with industry average if insufficient history

2. **Volatility (20% of Safety)**: 3-year historical
   - Idiosyncratic (stock-specific) volatility preferred
   - Lower is better

3. **Leverage (30% of Safety)**: Most recent quarter
   - Leverage is a snapshot measure
   - D/E < 1.0 preferred, < 0.5 ideal

4. **Bankruptcy Risk (20% of Safety)**: Most recent annual
   - Z-Score > 3.0 = Safe
   - Z-Score 1.8-3.0 = Grey zone
   - Z-Score < 1.8 = Danger zone

#### Red Flag Thresholds

| Metric | Red Flag Threshold | Severity |
|--------|-------------------|----------|
| Debt/Equity | > 1.5 | HIGH |
| Debt/EBITDA | > 4.0x | HIGH |
| Interest Coverage | < 2.0x | HIGH |
| Current Ratio | < 1.0 | MODERATE |
| Altman Z-Score | < 1.8 | CRITICAL |
| Beta | > 1.5 | MODERATE (higher risk) |

---

## Section 4: ROE Persistence (15% Weight)

### Metrics Covered
- Years with ROE > 15%
- ROE Trend
- Incremental ROCE

### Recommended Lookback Period: 3-5 Years

#### Primary Research Foundation

**Fama and French (2000, 2015) - Profitability Research**
- Original five-factor model used **annual ROE measurements**
- RMW factor based on annual operating profitability
- Persistence defined as maintaining high profitability over time
- Implementation: Use annual ROE over full available history

**Compounder Research - Lake Street, O'Shaughnessy**
- Studies of "compounders" (long-term wealth creators)
- Looked at **5-10 year ROE persistence**
- Companies maintaining ROE > 15% for 3+ years showed superior risk-adjusted returns
- Implementation: Count consecutive years above threshold

**Novy-Marx (2013) - Gross Profitability Premium**
- Used **annual and quarterly** profitability measurements
- Found gross profitability subsumes most quality factors
- Lookback period: Annual measurement sufficient for screening

**Piotroski and Ng (2015) - Earnings Sustainability**
- Research on persistence of profitability
- Found that **3-5 year windows** optimal for measuring persistence
- Shorter windows capture too much noise
- Longer windows miss structural changes

#### Recommended Implementation

| Metric | Lookback Period | Calculation Method |
|--------|----------------|-------------------|
| ROE (Annual) | Most recent year | Net Income / Average Equity |
| ROE Mean | 3-5 years | Average ROE over measurement period |
| ROE > 15% Count | 5 years | Number of years with ROE > 15% |
| ROE Trend | 3-5 years | Slope of ROE over period |
| ROE Stability | 3-5 years | Standard deviation of ROE (lower is better) |
| Incremental ROCE | 3 years | Most recent ROE - Average ROE prior 2 years |
| ROIC | Most recent year | NOPAT / Invested Capital |

#### Scoring Approach

For ROE Persistence scoring, use **longer windows to measure consistency**:

1. **Years Above Threshold (40% of ROE Persistence)**: 5-year window
   - Count years with ROE > 15%
   - 5/5 years = Maximum score
   - 0/5 years = Minimum score
   - Alternative: Use 10% threshold for more companies

2. **ROE Trend (30% of ROE Persistence)**: 3-5 year slope
   - Improving ROE indicates improving business quality
   - Calculate linear trend over period
   - Positive slope = improving

3. **ROE Quality (30% of ROE Persistence)**: 3-5 year average
   - Mean ROE over measurement period
   - Higher average indicates sustained profitability
   - Compare against cost of capital

#### Red Flag Thresholds

| Metric | Red Flag Threshold | Severity |
|--------|-------------------|----------|
| ROE Mean (5-year) | < 8% | HIGH |
| ROE Decline | 3-year downward trend | MODERATE |
| Years with ROE > 15% | 0 of 5 years | HIGH |
| ROIC | < WACC (estimate) | MODERATE |

---

## Summary: Lookback Period Recommendations

### Quick Reference Table

| Section | Weight | Primary Lookback | Multiplier Range | Rationale |
|---------|--------|-----------------|------------------|-----------|
| Earnings Quality | 20% | 1 year | 0.35x - 1.25x | Accruals decay quickly; F-Score is YoY comparison |
| Growth Quality | 15% | 3-5 years | 0.35x - 1.25x | Growth needs persistence but shorter for small caps |
| Safety | 15% | 3-5 years | 0.35x - 1.25x | Leverage = snapshot; Volatility needs shorter for small caps |
| ROE Persistence | 15% | 5 years | 0.35x - 1.25x | Persistence requires years but shorter for small caps |

**Key Rule:** Multiply base lookback by market cap multiplier (smaller cap = smaller multiplier = shorter lookback)

### Implementation Best Practices

1. **Market Cap Adjustments**: Apply smaller multipliers for smaller caps (less data, more volatile):
   - Mega Cap (> $200B): 1.25x multiplier (extended lookback)
   - Large Cap ($10B-$200B): 1.0x multiplier (baseline)
   - Mid Cap ($2B-$10B): 0.75x multiplier (reduced lookback)
   - Small Cap ($300M-$2B): 0.5x multiplier (minimum lookback)
   - Micro Cap (< $300M): 0.35x multiplier (very minimum)

2. **Data Availability**: If insufficient history exists, use whatever data is available but note the limitation in scoring.

3. **Updating Frequency**: 
   - Annual metrics: Update annually with 10-K data
   - Quarterly metrics: Update quarterly with 10-Q data
   - Market metrics (beta, volatility): Update monthly or quarterly

4. **Blending Approach**: Consider blending current-year metrics with trailing averages to reduce noise.

5. **Missing Data**: Apply penalties or neutral scores when data is unavailable rather than excluding companies.

6. **International Considerations**: For non-US companies with different reporting standards, consider using 0.75x of normal lookbacks.

---

## Appendix A: Academic Citations

### Earnings Quality
- Sloan, R.G. (1996). "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows About Future Earnings?" *The Accounting Review*, 71(3), 289-315.
- Piotroski, J.D. (2000). "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." *Journal of Accounting Research*, 38, 1-41.
- Dechow, P.M., Khimich, N.V., & Sloan, R.G. (2011). "The Accrual Anomaly." *University of California, Berkeley Working Paper*.

### Growth Quality
- Cooper, M.J., Gulen, H., & Schill, M.J. (2008). "Asset Growth and the Cross-Section of Stock Returns." *Journal of Finance*, 63(4), 1609-1651.
- Asness, C.S., Frazzini, A., & Pedersen, L.H. (2014). "Quality Minus Junk." *AQR Capital Management Working Paper*.
- Chan, L.K.C., Karceski, J., & Lakonishok, J. "The Level and Persistence of Growth Rates." *Journal of Finance*.

### Safety
- Asness, C.S., Frazzini, A., & Pedersen, L.H. (2014). "Quality Minus Junk." *Review of Accounting Studies*, 24(1), 34-112.
- Fama, E.F. & French, K.R. (2015). "A Five-Factor Asset Pricing Model." *Journal of Financial Economics*, 116(1), 1-22.
- Altman, E.I. (1968). "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy." *Journal of Finance*, 23(4), 589-609.

### ROE Persistence
- Fama, E.F. & French, K.R. (2000). "Forecasting Profitability and Earnings." *Journal of Business*, 73(2), 161-175.
- Novy-Marx, R. (2013). "The Other Side of Value: The Gross Profitability Premium." *Journal of Financial Economics*, 108(1), 1-28.
- Fama, E.F. & French, K.R. (2015). "A Five-Factor Asset Pricing Model." *Journal of Financial Economics*, 116(1), 1-22.

---

## Appendix B: Implementation Code Reference

### Example: Accrual Ratio Calculation (1-year lookback)
```python
def calculate_accrual_ratio(net_income, operating_cash_flow, total_assets, prior_total_assets):
    """
    Calculate Accrual Ratio per Sloan (1996)
    Lookback: 1 year
    """
    avg_assets = (total_assets + prior_total_assets) / 2
    if avg_assets == 0:
        return None
    accruals = net_income - operating_cash_flow
    return accruals / avg_assets
```

### Example: Asset Growth Calculation (1-year lookback)
```python
def calculate_asset_growth(total_assets, prior_total_assets):
    """
    Calculate Asset Growth per Cooper et al. (2008)
    Lookback: 1 year
    """
    if prior_total_assets == 0:
        return None
    return (total_assets - prior_total_assets) / prior_total_assets
```

### Example: ROE Persistence Calculation (5-year lookback)
```python
def calculate_roe_persistence(roe_history, threshold=0.15):
    """
    Calculate ROE persistence metrics
    Lookback: 5 years (or available history)
    """
    if len(roe_history) < 1:
        return None
    
    years_above_threshold = sum(1 for roe in roe_history if roe >= threshold)
    avg_roe = sum(roe_history) / len(roe_history)
    
    # Calculate trend (simple linear regression)
    if len(roe_history) >= 2:
        x = range(len(roe_history))
        slope = (roe_history[-1] - roe_history[0]) / len(roe_history)
    else:
        slope = 0
    
    return {
        'years_above_threshold': years_above_threshold,
        'avg_roe': avg_roe,
        'roe_trend': slope,
        'persistence_score': years_above_threshold / len(roe_history)
    }
```

### Example: Beta Calculation (5-year lookback)
```python
def calculate_beta(stock_returns, market_returns, lookback_periods=60):
    """
    Calculate rolling beta
    Lookback: 5 years (60 months) standard
    """
    if len(stock_returns) < 12 or len(market_returns) < 12:
        return None
    
    # Use available data up to lookback period
    n = min(lookback_periods, len(stock_returns), len(market_returns))
    
    stock_slice = stock_returns[-n:]
    market_slice = market_returns[-n:]
    
    covariance = np.cov(stock_slice, market_slice)[0][1]
    market_variance = np.var(market_slice)
    
    if market_variance == 0:
        return None
    
    return covariance / market_variance
```

---

## Appendix C: Quality Score Weighting Matrix with Lookback Periods

Based on meta-analysis of academic research, this appendix provides the optimal factor weights combined with recommended lookback periods. Just as the analysis algorithm adjusts lookback periods based on market cap, these periods are context-dependent and may require adjustment based on company characteristics.

### C.1 Core Quality Score Matrix

| Factor Category | Weight | Primary Metric | Secondary Metrics | Lookback Period | Academic Base |
|----------------|--------|----------------|-------------------|-----------------|---------------|
| **Profitability** | 35% | Gross Profitability | ROE, ROIC, Operating Margin | 1-3 years | Novy-Marx (2013), Fama-French (2015) |
| **Earnings Quality** | 20% | Accrual Ratio | Cash Conversion, F-Score components | 1-3 years | Sloan (1996), Piotroski (2000) |
| **Growth Quality** | 15% | Asset Growth (inverse) | Revenue Quality, Margin Trend | 1-5 years | Cooper et al. (2008), AQR QMJ |
| **Safety** | 15% | Leverage Ratios | Beta, Volatility, Z-Score | 1-5 years | Asness et al. (2014), Fama-French |
| **ROE Persistence** | 15% | Years > 15% ROE | ROE Trend, Incremental ROCE | 3-5 years | Fama-French (2015), Compounder Research |

### C.2 Detailed Lookback Periods by Metric

#### C.2.1 Profitability Metrics (35% Weight)

| Metric | Default Lookback | Small Cap Adjustment | Large Cap Adjustment | Rationale |
|--------|-----------------|---------------------|---------------------|-----------|
| Gross Profitability | 1 year | 2 years | 1 year | Large caps have more stable margins; small caps benefit from longer averaging |
| ROE | 1 year | 2-3 years | 1 year | Small caps more volatile; longer window filters noise |
| ROIC | 1 year | 2 years | 1 year | Capital intensity varies by size |
| Operating Margin | 1-2 years | 2-3 years | 1 year | Margins more stable in mature companies |
| FCF Margin | Trailing 12 months | 2 years | Trailing 12 months | Cash flow more variable in small caps |

**Market Cap Adjustment Logic for Profitability:**
- **Large Cap (> $10B)**: Use 1-year lookback as default; high-quality data and stable operations
- **Mid Cap ($2B-$10B)**: Use 0.75x baseline; shorter window captures current conditions
- **Small Cap ($300M-$2B)**: Use 0.5x baseline; higher volatility requires shorter windows
- **Micro Cap (< $300M)**: Use 0.35x baseline; limited data and high volatility

#### C.2.2 Earnings Quality Metrics (20% Weight)

| Metric | Default Lookback | Small Cap Adjustment | Large Cap Adjustment | Rationale |
|--------|-----------------|---------------------|---------------------|-----------|
| Accrual Ratio | 1 year | 0.5x (6-12 months) | 1.0x (1 year) | Small caps may have one-off items; longer window less useful |
| Cash Conversion | Trailing 12 months | 0.5x (6-12 months) | 1.0x (12 months) | Small caps have variable cash generation; focus on recent |
| F-Score (Overall) | 1 year (current vs. prior) | 1.0x | 1.0x | F-Score methodology is inherently YoY |
| F_ROA | 1 year | 0.5x | 1.0x | Small cap ROA more volatile; shorter window cleaner |
| F_CFO | 1 year | 1.0x | 1.0x | Binary measure; no averaging needed |
| F_ACCRUAL | 1 year | 0.5x | 1.0x | Small caps may have one-off items; focus on current |
| F_ΔLEVER | 1 year | 1.0x | 1.0x | Snapshot measure; compare to prior year |
| F_ΔLIQUID | 1 year | 1.0x | 1.0x | Snapshot measure; compare to prior year |

**Market Cap Adjustment Logic for Earnings Quality:**
- **Large Cap**: Standard 1-year Piotroski methodology applies
- **Mid Cap**: Slight reduction to 0.75x; focus on recent performance
- **Small Cap**: Reduce to 0.5x; one-year lookback captures current state
- **Micro Cap**: Reduce to 0.35x; use most recent annual data only

#### C.2.3 Growth Quality Metrics (15% Weight)

| Metric | Default Lookback | Small Cap Adjustment | Large Cap Adjustment | Rationale |
|--------|-----------------|---------------------|---------------------|-----------|
| Asset Growth | 1 year | 1 year | 1 year | Cooper et al. uses annual measurement; timely signal |
| Asset Growth Trend | 3 years | 0.5x (1-2 years) | 1.25x (3-4 years) | Small caps need shorter trend window |
| Revenue CAGR | 3-5 years | 0.5x (1-2 years) | 1.25x (4-5 years) | Small caps change faster; large caps more stable |
| Revenue Quality | 3 years | 0.75x (2-3 years) | 1.0x (3 years) | Smaller sample for small caps |
| Margin Trend | 3-5 years | 0.5x (1-2 years) | 1.25x (4-5 years) | Large caps show persistent trends |
| Gross Margin Improvement | 3 years | 0.5x (1-2 years) | 1.25x (3-4 years) | Small caps may show larger swings |

**Market Cap Adjustment Logic for Growth Quality:**
- **Large Cap**: Use 1.25x baseline (5-year windows); slower-changing fundamentals
- **Mid Cap**: Use 0.75x baseline; balance based on growth stage
- **Small Cap**: Use 0.5x baseline; faster-changing business models need shorter windows
- **Micro Cap**: Use 0.35x baseline; high volatility requires recent data focus

#### C.2.4 Safety Metrics (15% Weight)

| Metric | Default Lookback | Small Cap Adjustment | Large Cap Adjustment | Rationale |
|--------|-----------------|---------------------|---------------------|-----------|
| Beta | 3-5 years | 0.5x (1-2 years) | 1.25x (4-5 years) | Small caps have less stable beta; recent more relevant |
| Idiosyncratic Volatility | 3 years | 0.5x (1-2 years) | 1.25x (3-4 years) | Small caps inherently more volatile |
| Total Debt/Equity | Most recent quarter | 1.0x | 1.0x | Leverage is a snapshot measure |
| Debt/EBITDA | Trailing 12 months | 1.0x | 1.0x | Earnings-based; use available data |
| Interest Coverage | Trailing 12 months | 1.0x | 1.0x | Coverage is a snapshot measure |
| Current Ratio | Most recent quarter | 1.0x | 1.0x | Liquidity is a snapshot measure |
| Altman Z-Score | Most recent annual | 1.0x | 1.0x | Designed as annual predictor |
| Earnings Volatility | 3-5 years | 0.5x (1-2 years) | 1.25x (4-5 years) | Small caps inherently more volatile |

**Market Cap Adjustment Logic for Safety:**
- **Large Cap**: Use 1.25x baseline (5-year beta/volatility); stable market relationship
- **Mid Cap**: Use 0.75x baseline; recent stability more relevant
- **Small Cap**: Use 0.5x baseline; higher estimation error with longer windows
- **Micro Cap**: Use 0.35x baseline; use recent data only

#### C.2.5 ROE Persistence Metrics (15% Weight)

| Metric | Default Lookback | Small Cap Adjustment | Large Cap Adjustment | Rationale |
|--------|-----------------|---------------------|---------------------|-----------|
| ROE (Annual) | Most recent year | Most recent year | Most recent year | Snapshot profitability measure |
| ROE Mean | 3-5 years | 0.5x (1-2 years) | 1.25x (4-5 years) | Small caps benefit from shorter averaging |
| ROE > 15% Count | 5 years | 0.5x (2-3 years) | 1.25x (5+ years) | Fewer small caps meet threshold; use shorter window |
| ROE Trend | 3-5 years | 0.5x (1-2 years) | 1.25x (4-5 years) | Trend calculation with recent data |
| ROE Stability | 3-5 years | 0.5x (1-2 years) | 1.25x (4-5 years) | Shorter window for small caps |
| Incremental ROCE | 3 years | 0.5x (1-2 years) | 1.25x (3-4 years) | Year-over-year change measure |
| ROIC | Most recent year | Most recent year | Most recent year | Snapshot capital efficiency |

**Market Cap Adjustment Logic for ROE Persistence:**
- **Large Cap**: Use 1.25x baseline (5-year lookback); stable operations allow long-term assessment
- **Mid Cap**: Use 0.75x baseline; depends on business maturity
- **Small Cap**: Use 0.5x baseline; faster-changing profitability dynamics
- **Micro Cap**: Use 0.35x baseline; may not have 5 years of data

### C.3 Market Cap-Based Lookback Adjustment Framework

The analysis algorithm should apply the following adjustments based on market capitalization:

#### C.3.1 Market Cap Tiers and Default Adjustments

| Market Cap Tier | Size Definition | Default Multiplier | Minimum Lookback | Maximum Lookback |
|-----------------|----------------|--------------------|------------------|------------------|
| Mega Cap | > $200B | 1.25x (extended) | 1 year | 5 years |
| Large Cap | $10B - $200B | 1.0x (baseline) | 1 year | 5 years |
| Mid Cap | $2B - $10B | 0.75x (reduced) | 1 year | 4 years |
| Small Cap | $300M - $2B | 0.5x (minimum) | 1 year | 3 years |
| Micro Cap | < $300M | 0.35x (very minimum) | 1 year | 2 years |

**Formula:**
```
Adjusted Lookback = Base Lookback × Market Cap Multiplier
```

**Example (Large Cap):**
- Base lookback for ROE Mean: 5 years
- Large Cap multiplier: 1.0x
- Adjusted lookback: 5 × 1.0 = 5 years (full 5-year assessment)

**Example (Small Cap):**
- Base lookback for ROE Mean: 5 years
- Small Cap multiplier: 0.5x
- Adjusted lookback: 5 × 0.5 = 2.5 years (rounded to 2-3 years)

#### C.3.2 Sector-Specific Considerations

Beyond market cap, certain sectors may warrant lookback period adjustments:

| Sector Type | Characteristics | Recommended Adjustment |
|-------------|----------------|----------------------|
| Technology | Fast-changing business models | Reduce lookback by 20-30% |
| Financials | Regulated, stable metrics | Standard lookback |
| Utilities | Stable, slow-changing | Standard or extend 10-20% |
| Healthcare | R&D-intensive, cyclical | Extend lookback 10-20% |
| Consumer Cyclicals | Variable with economy | Standard lookback |
| Industrials | Capital-intensive, long cycles | Extend lookback 10-20% |

#### C.3.3 Data Availability Adjustments

| Data Availability | Action |
|------------------|--------|
| Full history available | Use optimal lookback |
| 3-4 years available | Use available years; note limitation |
| 1-2 years available | Use 1-year defaults; apply confidence penalty |
| IPO < 1 year ago | Use most recent data only; flag as insufficient |

### C.4 Implementation Algorithm

```python
def get_adjusted_lookback(base_lookback, market_cap, sector=None, data_years=None):
    """
    Calculate adjusted lookback period based on company characteristics.
    
    Smaller caps have less data and higher volatility, requiring shorter lookbacks.
    Larger caps have more stable metrics and more data, allowing longer lookbacks.
    
    Parameters:
    -----------
    base_lookback : int
        Default lookback period in years
    market_cap : float
        Company market capitalization in USD
    sector : str, optional
        GICS sector for sector-specific adjustments
    data_years : int, optional
        Years of available historical data
    
    Returns:
    --------
    int
        Adjusted lookback period in years
    """
    # Market cap tier determination (smaller cap = smaller multiplier = shorter lookback)
    if market_cap >= 200e9:  # > $200B (Mega)
        multiplier = 1.25  # Extended lookback
    elif market_cap >= 10e9:  # $10B-$200B (Large)
        multiplier = 1.0   # Baseline
    elif market_cap >= 2e9:   # $2B-$10B (Mid)
        multiplier = 0.75  # Reduced lookback
    elif market_cap >= 300e6: # $300M-$2B (Small)
        multiplier = 0.5   # Minimum lookback
    else:  # < $300M (Micro)
        multiplier = 0.35  # Very minimum lookback
    
    # Sector adjustments
    sector_extensions = {
        'Technology': 0.8,   # Fast-changing; reduce lookback
        'Healthcare': 1.1,   # R&D-intensive; extend slightly
        'Utilities': 1.1,    # Slow-changing; extend slightly
        'Industrials': 1.1,  # Long cycles; extend slightly
    }
    
    if sector in sector_extensions:
        multiplier *= sector_extensions[sector]
    
    # Calculate adjusted lookback
    adjusted = base_lookback * multiplier
    
    # Data availability constraint
    if data_years is not None:
        adjusted = min(adjusted, max(1, data_years))  # Can't exceed available data
        if adjusted < 1:
            adjusted = 1.0
    
    return round(adjusted, 1)
```

### C.5 Composite Quality Score Calculation

With lookback periods integrated, the complete scoring formula becomes:

```
Quality Score = (
    0.35 × Profitability_Score(base_lookback=1-3) +
    0.20 × EarningsQuality_Score(base_lookback=1-3) +
    0.15 × GrowthQuality_Score(base_lookback=1-5) +
    0.15 × Safety_Score(base_lookback=1-5) +
    0.15 × ROEPersistence_Score(base_lookback=3-5)
) × Safety_Multiplier × DataQuality_Multiplier
```

**Where:**

| Multiplier | Calculation | Impact |
|------------|------------|--------|
| Safety_Multiplier | Reduces score for high leverage, high volatility | 0.7x - 1.0x |
| DataQuality_Multiplier | Reduces score for insufficient history | 0.8x - 1.0x |

### C.6 Quick Reference Card

#### Default Lookbacks by Market Cap

| Metric Category | Mega Cap | Large Cap | Mid Cap | Small Cap | Micro Cap |
|----------------|----------|-----------|---------|-----------|-----------|
| Profitability | 1-2 years | 1 year | 0.75 year | 0.5 year | 0.35 year |
| Earnings Quality | 1 year | 1 year | 0.75 year | 0.5 year | 0.35 year |
| Growth Quality | 4-5 years | 3-5 years | 2-3 years | 1-2 years | 1 year |
| Safety | 4-5 years | 3-5 years | 2-3 years | 1-2 years | 1 year |
| ROE Persistence | 5+ years | 5 years | 3-4 years | 2-3 years | 1-2 years |

**Key Principle:** Smaller caps require shorter lookbacks due to data availability and higher volatility.

#### Common Adjustment Scenarios

| Scenario | Adjustment |
|----------|-----------|
| High-growth tech company (large cap) | Use 0.8x baseline; fast-changing sector |
| Regulated utility (large cap) | Use 1.25x baseline; stable metrics |
| Newly public company (2 years data) | Use 2-year lookback maximum, apply penalty |
| Foreign private issuer | Standard lookback; may need data adjustments |
| Financial institution | Use sector-specific Z-Score |
| Distressed small cap | Use 0.5x baseline; focus on recent data |

**Remember:** Smaller caps = shorter lookbacks | Larger caps = longer lookbacks

---

*Appendix C compiled from academic research and implementation best practices. Always backtest adjustments before deployment.*

---

*Document compiled for quality analysis implementation guidance. Always conduct independent due diligence and backtest before implementation.*
