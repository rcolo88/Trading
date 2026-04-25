# Academic Research: Quality Investing Metrics & Factor Analysis
## A Comprehensive Framework for Quantitative Stock Selection

**Compiled:** January 16, 2026
**Purpose:** Foundational research for automated hedge fund quality analysis system
**Last Updated:** April 22, 2026 — expanded with post-2024 evidence, q-factor model, G-Score, M-Score, shareholder yield, QARP, intangibles-adjusted value, and a practical opportunity-discovery framework for the scanner codebase.

---

## Executive Summary

Academic research overwhelmingly demonstrates that **profitability and quality metrics** predict stock returns better than traditional value metrics alone. This document synthesizes decades of peer-reviewed research into actionable metrics for systematic quality investing, providing the theoretical foundation for automated portfolio management systems.

### Key Findings at a Glance

| Factor | Annual Premium | Primary Research | Robustness |
|--------|----------------|------------------|------------|
| Gross Profitability | 5-7% | Novy-Marx (2013) | Very High |
| Quality (QMJ) | 3-6% | Asness et al. (2019) | Very High |
| Low Accruals | 8-10% | Sloan (1996) | High |
| Conservative Investment | 4-6% | Cooper et al. (2008) | High |
| Piotroski F-Score | 7.5%+ | Piotroski (2000) | High |
| ROE Persistence | 5-10% | Fama-French (2015) | Very High |
| Expected Growth (q5) | ~10% | Hou-Mo-Xue-Zhang (2021) | High |
| Mohanram G-Score (growth) | 10%+ spread | Mohanram (2005) | Moderate |
| Quality Acceleration | ~6-8% | Ma-Yang-Ye (2024) | Emerging |
| Shareholder (Buyback) Yield | 4-5% | Faber; MSCI | High |
| Intangibles-Adjusted Value | 1-3% uplift | Arnott et al. (2021) | Emerging |

> **Critical 2025 update (Novy-Marx & Medhat):** In spanning tests with information ratios near 0.85, profitability *subsumes* every commercial and academic "quality" composite — none of them generate positive alpha after controlling for profitability, market, size, value, investment, and momentum. This means the scanner should treat **gross profits-to-assets as the anchor factor** and evaluate every additional quality signal for incremental alpha *above profitability*.

---

## Part I: The Profitability Factor

### 1.1 Gross Profitability Premium (Novy-Marx, 2013)

The seminal paper "The Other Side of Value: The Gross Profitability Premium" (Journal of Financial Economics, 2013) established that **gross profitability is the strongest predictor of stock returns** among quality metrics.

#### Definition
```
Gross Profitability = (Revenue - COGS) / Total Assets
```

#### Key Findings

1. **Predictive Power**: Gross profitability has roughly the same power as book-to-market ratios in predicting cross-sectional returns
2. **Return Premium**: 31 basis points per month excess return (approximately 3.7% annually)
3. **Persistence**: The effect is highly persistent across time periods and market conditions
4. **Scale Independence**: Works in both large-cap and small-cap universes

#### Why Gross Profitability Works

Professor Novy-Marx explains:

> "Profitability, measured by gross profits-to-assets, has roughly the same power as book-to-market predicting the cross-section of average returns. Profitable firms generate significantly higher returns than unprofitable firms, despite having significantly higher valuation ratios."

Gross profitability represents the cleanest measure of economic efficiency because:
- It is measured **before** discretionary expenses (R&D, marketing, SG&A)
- It captures the firm's core business efficiency
- It is less susceptible to accounting manipulation than net income

#### Implementation Thresholds

| Gross Profitability | Quality Rating | Position Sizing |
|---------------------|----------------|-----------------|
| > 40% | Excellent | 15-20% |
| 30-40% | Good | 10-15% |
| 20-30% | Moderate | 5-10% |
| < 20% | Weak | Avoid or <5% |

#### FISV Analysis Application
Your FISV analysis shows **Gross Profitability of 0.16 (16%)**, which scores only **1.3/10**. This is a critical red flag indicating the company's core business efficiency is below acceptable thresholds for quality investing. However, note that **Gross Margin of 60.8%** is strong - the discrepancy suggests high asset intensity (large balance sheet relative to gross profits).

---

### 1.2 Profitability Retrospective: Recent Evidence (Novy-Marx & Medhat, 2025)

The March 2025 NBER working paper "Profitability Retrospective: What Have We Learned?" provides updated analysis:

> "Profitability subsumes all the quality factor, explaining both the performance of the strategies the investment industry markets and the factors that academics employ—none of the quality factors generated significant positive alpha relative to profitability."

**Key Update**: Profitability alone explains nearly all documented "quality" anomalies, suggesting simpler implementation strategies.

---

## Part II: The Fama-French Five-Factor Model

### 2.1 Model Specification

In 2015, Fama and French extended their three-factor model to include profitability and investment:

```
R_i - R_f = α + β₁(R_m - R_f) + β₂SMB + β₃HML + β₄RMW + β₅CMA + ε
```

Where:
- **R_m - R_f**: Market risk premium
- **SMB**: Small Minus Big (size factor)
- **HML**: High Minus Low (value factor)
- **RMW**: Robust Minus Weak (profitability factor)
- **CMA**: Conservative Minus Aggressive (investment factor)

### 2.2 Factor Definitions

#### RMW (Profitability Factor)
```
Operating Profitability = (Revenue - COGS - SG&A - Interest Expense) / Book Equity
```
- Stocks with **robust** (high) operating profitability outperform those with **weak** (low) profitability
- The only factor showing **consistent excess returns across all economic cycles since 1963**

#### CMA (Investment Factor)
```
Investment = (Total Assets_t - Total Assets_{t-1}) / Total Assets_{t-1}
```
- Firms that invest **conservatively** outperform those that invest **aggressively**
- Related to the asset growth anomaly (see Section IV)

### 2.3 Factor Performance Summary

| Factor | Avg Monthly Return | t-stat | Sharpe Ratio |
|--------|-------------------|--------|--------------|
| MKT | 0.55% | 3.2 | 0.42 |
| SMB | 0.22% | 1.8 | 0.16 |
| HML | 0.31% | 2.1 | 0.22 |
| **RMW** | **0.35%** | **3.4** | **0.31** |
| CMA | 0.28% | 2.4 | 0.25 |

**Critical Finding**: HML (value) becomes **redundant** when profitability and investment factors are included, as it has a 0.7 correlation with CMA.

---

## Part III: Quality Minus Junk (AQR Research)

### 3.1 QMJ Framework (Asness, Frazzini, Pedersen, 2014)

AQR's "Quality Minus Junk" research provides a comprehensive definition of quality across **four dimensions**:

#### 1. Profitability (Weight: ~25%)
- Gross Profits over Assets (GPOA)
- Return on Equity (ROE)
- Return on Assets (ROA)
- Cash Flow over Assets (CFOA)
- Gross Margin
- Low Accruals (see Section V)

#### 2. Growth (Weight: ~25%)
- 5-year growth in Gross Profits
- 5-year growth in ROE
- 5-year growth in ROA
- 5-year growth in CFOA
- 5-year growth in Gross Margin

#### 3. Safety (Weight: ~25%)
- Low Beta
- Low Idiosyncratic Volatility
- Low Leverage (Debt/Assets)
- Low Bankruptcy Risk (Ohlson's O-Score, Altman's Z-Score)
- Low Earnings Volatility

#### 4. Payout (Weight: ~25%)
- Net Equity Issuance (negative is good - buybacks)
- Net Debt Issuance (negative is good - deleveraging)
- Total Net Payout over Profits

### 3.2 QMJ Performance

| Sample | Period | Monthly Alpha | t-stat |
|--------|--------|---------------|--------|
| US (Long) | 1956-2024 | 0.38% | 5.02 |
| US (Broad) | 1986-2024 | 0.45% | 4.92 |
| Global | 1986-2024 | 0.42% | 5.64 |
| 24 Countries | Various | 23/24 positive | N/A |

**Key Finding**: QMJ delivers positive returns in **23 out of 24 countries studied** and provides significant crisis protection (flight to quality effect).

### 3.3 Quality Score Calculation

```python
# Simplified QMJ calculation
def calculate_quality_score(stock_data):
    # Profitability z-scores
    prof_z = z_score([gpoa, roe, roa, cfoa, gm, -accruals])
    
    # Growth z-scores (5-year changes)
    growth_z = z_score([Δgpoa, Δroe, Δroa, Δcfoa, Δgm])
    
    # Safety z-scores (inverted where high = risky)
    safety_z = z_score([-beta, -ivol, -leverage, -o_score, -earn_vol])
    
    # Payout z-scores
    payout_z = z_score([-equity_issue, -debt_issue, net_payout])
    
    # Aggregate
    quality = z_score([prof_z, growth_z, safety_z, payout_z])
    return quality
```

---

## Part IV: The Asset Growth Anomaly

### 4.1 Cooper, Gulen, and Schill (2008)

The paper "Asset Growth and the Cross-Section of Stock Returns" (Journal of Finance, 2008) documented one of the most powerful anomalies:

> "Low asset growth stocks maintained a return premium of **20% per year** over high asset growth stocks over the past 40 years."

#### Definition
```
Asset Growth = (Total Assets_t - Total Assets_{t-1}) / Total Assets_{t-1}
```

### 4.2 Key Findings

| Asset Growth Decile | Avg Annual Return | Risk-Adjusted Alpha |
|--------------------|-------------------|---------------------|
| 1 (Lowest Growth) | 18.2% | 8.5% |
| 5 (Middle) | 11.5% | 2.1% |
| 10 (Highest Growth) | -2.3% | -10.2% |
| **Spread** | **20.5%** | **18.7%** |

### 4.3 Why Asset Growth Predicts Returns

1. **Overinvestment Hypothesis**: Managers with excess cash tend to overinvest in negative NPV projects (Jensen, 1986)
2. **Market Timing**: Companies issue equity when overvalued and expand when costs are artificially low
3. **Diminishing Marginal Returns**: Aggressive expansion leads to lower returns on incremental capital
4. **Investor Overreaction**: Markets extrapolate growth rates that prove unsustainable

### 4.4 Implementation for Quality Framework

| Asset Growth Rate | Quality Signal | Action |
|-------------------|----------------|--------|
| < 0% (Shrinking) | Positive | Preferred |
| 0-10% | Neutral | Acceptable |
| 10-20% | Caution | Reduced weight |
| > 20% | Negative | **RED FLAG** |

**Recommendation for your analysis**: Add Asset Growth as a quality metric. Companies with asset growth >20% should be flagged regardless of other metrics.

---

## Part V: The Accruals Anomaly (Earnings Quality)

### 5.1 Sloan (1996) - Original Research

Richard Sloan's landmark paper "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows About Future Earnings?" (The Accounting Review, 1996) established:

> "Companies with low accrual ratios massively outperform companies with high accrual ratios. For the 40-year period between 1962 and 2001, the strategy resulted in an average annual compounded return of almost **18%**, more than double the S&P 500's 7.4% annual return."

### 5.2 Understanding Accruals

#### Definition (Balance Sheet Method)
```
Accruals = (ΔCurrent Assets - ΔCash) - (ΔCurrent Liabilities - ΔSTD - ΔITP) - Depreciation
```

Or simplified:
```
Accruals = Net Income - Operating Cash Flow
```

Scaled by assets:
```
Accrual Ratio = Accruals / Average Total Assets
```

### 5.3 Why Accruals Matter

| Accruals Level | Interpretation | Earnings Quality |
|----------------|----------------|------------------|
| Highly Negative | Cash > Earnings | **High Quality** |
| Near Zero | Cash ≈ Earnings | Good Quality |
| Highly Positive | Earnings > Cash | **Low Quality (Red Flag)** |

**Core Insight**: Earnings backed by cash flows are more persistent (sustainable) than earnings driven by accruals. High accruals often signal:
- Aggressive revenue recognition
- Delayed expense recognition
- Potential earnings manipulation
- Unsustainable growth

### 5.4 Implementation

For your FISV analysis, calculate:
```
Cash Flow Quality = Operating Cash Flow / Net Income
```

| Ratio | Quality Assessment |
|-------|---------------------|
| > 1.2 | Excellent - Cash exceeds earnings |
| 1.0-1.2 | Good - Cash approximates earnings |
| 0.8-1.0 | Moderate - Minor accrual concern |
| < 0.8 | Poor - **Significant accrual red flag** |

**FISV Analysis**: 
- Operating Cash Flow: ~$5.06B (using FCF + CapEx estimate)
- Net Income: $3.13B
- Ratio: ~1.6x = **Excellent earnings quality**

This is a positive signal that partially offsets the weak profitability metrics.

---

## Part VI: Piotroski F-Score

### 6.1 Original Research (2000)

Joseph Piotroski's "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers" (Journal of Accounting Research, 2000):

> "Stocks with the highest F-Scores (8 or 9) outperformed the market by **13.4% per year for 20 years**. An investor could improve the return of a low price-to-book portfolio by at least **7.5% per year**."

### 6.2 The Nine F-Score Components

#### Profitability (4 points)

| Signal | Criteria | Score |
|--------|----------|-------|
| F_ROA | ROA > 0 | 1 if true |
| F_CFO | CFO > 0 | 1 if true |
| F_ΔROA | ROA increased YoY | 1 if true |
| F_ACCRUAL | CFO > Net Income (low accruals) | 1 if true |

#### Leverage/Liquidity (3 points)

| Signal | Criteria | Score |
|--------|----------|-------|
| F_ΔLEVER | Long-term debt/assets decreased | 1 if true |
| F_ΔLIQUID | Current ratio increased | 1 if true |
| F_EQ_OFFER | No new shares issued | 1 if true |

#### Operating Efficiency (2 points)

| Signal | Criteria | Score |
|--------|----------|-------|
| F_ΔMARGIN | Gross margin increased | 1 if true |
| F_ΔTURN | Asset turnover increased | 1 if true |

### 6.3 Interpretation

| F-Score | Quality Tier | Recommendation |
|---------|--------------|----------------|
| 8-9 | Excellent | Strong Buy |
| 6-7 | Good | Buy |
| 4-5 | Moderate | Hold/Neutral |
| 2-3 | Weak | Avoid |
| 0-1 | Very Weak | Strong Sell |

### 6.4 Enhanced F-Score Application

**Recommendation**: Calculate F-Score for all holdings. Academic research shows 92% of small-cap bankruptcies had F-Scores in the lowest deciles, making this an excellent risk screen.

---

## Part VII: ROE Persistence & Compounders

### 7.1 The Persistence Premium

Research shows that companies maintaining **ROE > 15% for 3+ consecutive years** significantly outperform. The persistence of high ROE is a hallmark of competitive advantage.

### 7.2 Compounder Identification

| Metric | Threshold | Evidence |
|--------|-----------|----------|
| ROE | > 15% for 3+ years | ~75% maintain status YoY |
| ROE Mean | > 20% | Top decile compounders |
| Incremental ROCE | > ROCE | Indicates improving capital efficiency |

### 7.3 FISV Analysis Implications

Your FISV analysis shows:
- **Years with ROE > 15%**: 0 of 4 years
- **ROE Mean**: 8.6%
- **Classification**: Inconsistent
- **Compounder Confidence**: 39%

This is a **critical failure** under ROE persistence criteria. The 80/20 framework requires 15%+ ROE for core positions, which FISV fails to meet.

---

## Part VIII: Recommended Additions to Your Analysis System

### 8.1 New Metrics to Implement

Based on academic research, add these fields to your stock analysis output:

#### Primary Additions

| Metric | Formula | Academic Basis |
|--------|---------|----------------|
| **Asset Growth** | (Assets_t - Assets_{t-1}) / Assets_{t-1} | Cooper et al. (2008) |
| **Accrual Ratio** | (NI - OCF) / Avg Assets | Sloan (1996) |
| **Cash Flow Quality** | OCF / Net Income | Richardson et al. (2005) |
| **Piotroski F-Score** | Sum of 9 binary signals | Piotroski (2000) |
| **Net Payout Yield** | (Buybacks + Dividends - Issuance) / Market Cap | AQR QMJ |

#### Secondary Additions

| Metric | Formula | Purpose |
|--------|---------|---------|
| **Incremental ROIC** | ΔNOPAT / ΔInvested Capital | Capital efficiency trend |
| **Operating Leverage** | ΔOperating Income / ΔRevenue | Margin sensitivity |
| **Earnings Volatility** | Std Dev of EPS (5yr) | Safety measure |
| **Beta** | Market regression beta | Safety measure |
| **Altman Z-Score** | Bankruptcy predictor | Risk screen |

### 8.2 Enhanced Scoring Framework

Revise your quality score calculation to weight metrics by academic evidence:

```
Quality Score = (
    0.30 × Gross_Profitability_Score +
    0.20 × ROE_Persistence_Score +
    0.15 × Earnings_Quality_Score (Accruals) +
    0.15 × Conservative_Investment_Score +
    0.10 × ROIC_Score +
    0.10 × FCF_Yield_Score
) × Safety_Multiplier
```

Where `Safety_Multiplier` reduces score for:
- Asset Growth > 20%: 0.8x
- Negative FCF: 0.7x
- F-Score < 5: 0.8x
- High Leverage (D/E > 1.5): 0.9x

### 8.3 Red Flag Enhancements

Add these academic-backed red flags:

| Red Flag | Threshold | Severity |
|----------|-----------|----------|
| Asset Growth > 20% | Annual growth | HIGH |
| Accrual Ratio > 10% | NI - OCF / Assets | HIGH |
| F-Score ≤ 3 | Piotroski score | CRITICAL |
| ROE < 5% (4+ years) | Sustained low ROE | HIGH |
| Negative Operating Cash Flow | Any period | MODERATE |
| Debt/EBITDA > 4x | Leverage ratio | HIGH |
| Current Ratio < 1.0 | Liquidity | MODERATE |

---

## Part IX: Complete Metrics Reference Table

### 9.1 Profitability Metrics

| Metric | Formula | Threshold | Weight |
|--------|---------|-----------|--------|
| Gross Profitability | (Rev - COGS) / Assets | > 40% | 30% |
| ROE | Net Income / Equity | > 15% | 15% |
| ROA | Net Income / Assets | > 10% | 10% |
| ROIC | NOPAT / Invested Capital | > 15% | 15% |
| Operating Margin | Operating Income / Revenue | > 15% | 10% |
| FCF Margin | FCF / Revenue | > 10% | 10% |
| FCF Yield | FCF / Market Cap | > 5% | 10% |

### 9.2 Quality Metrics

| Metric | Formula | Threshold | Signal |
|--------|---------|-----------|--------|
| Accrual Ratio | (NI - OCF) / Assets | < 5% | Lower is better |
| Cash Conversion | OCF / Net Income | > 100% | Higher is better |
| Asset Growth | ΔAssets / Assets | < 15% | Lower is better |
| F-Score | Sum of 9 signals | > 6 | Higher is better |
| Gross Margin Stability | 5yr Std Dev | < 5% | Lower is better |
| Revenue Quality | Core Revenue / Total | > 90% | Higher is better |

### 9.3 Safety Metrics

| Metric | Formula | Threshold | Risk Level |
|--------|---------|-----------|------------|
| Debt/Equity | Total Debt / Equity | < 1.0 | Low Risk |
| Debt/EBITDA | Total Debt / EBITDA | < 3.0 | Low Risk |
| Interest Coverage | EBIT / Interest | > 5x | Low Risk |
| Current Ratio | Current Assets / Current Liab | > 1.5 | Low Risk |
| Quick Ratio | (Cash + Receivables) / Current Liab | > 1.0 | Low Risk |
| Altman Z-Score | Bankruptcy predictor | > 3.0 | Safe Zone |

### 9.4 Growth Quality Metrics

| Metric | Formula | Threshold | Interpretation |
|--------|---------|-----------|----------------|
| Revenue CAGR (3yr) | Compound growth | 5-20% | Sustainable |
| EPS CAGR (3yr) | Compound growth | 10-25% | Sustainable |
| FCF CAGR (3yr) | Compound growth | > 10% | Reinvestment capacity |
| ROIC Trend | 3yr slope | Positive | Improving efficiency |
| Margin Expansion | Δ Operating Margin | Positive | Operating leverage |

---

## Part X: FISV Analysis Critique & Recommendations

### 10.1 Current Analysis Strengths

Your FISV analysis correctly identifies:
- ✅ Weak overall quality (44.7/100)
- ✅ Inconsistent ROE persistence
- ✅ Below-threshold profitability metrics
- ✅ Strong FCF generation ($5.06B)
- ✅ Mid-cap categorization

### 10.2 Missing Elements to Add

Based on academic research, add:

1. **Asset Growth Rate**: Calculate and flag if > 15%
2. **Accrual Ratio**: (Net Income - OCF) / Total Assets
3. **Piotroski F-Score**: Full 9-point calculation
4. **Cash Flow Quality Ratio**: OCF / Net Income (currently ~1.6x = excellent)
5. **ROIC Trend**: Direction over 4 years
6. **Debt/EBITDA**: Total Debt / EBITDA for leverage assessment
7. **Interest Coverage**: Operating Income / Interest Expense

### 10.3 Revised FISV Assessment

| Metric | Current | New Calc | Score |
|--------|---------|----------|-------|
| Gross Profitability | 0.16 | 16% | 1.3/10 |
| ROE | 0.12 | 11.6% | 3.8/10 |
| ROIC | 0.09 | 9% | 3.4/10 |
| FCF Yield | 0.14 | 14% | 10/10 |
| **NEW: Cash Flow Quality** | - | ~1.6x | 9/10 |
| **NEW: Debt/Equity** | - | 0.92 | 6/10 |
| **NEW: Estimated F-Score** | - | ~5-6 | 5/10 |

**Revised Assessment**: FISV shows mixed quality. While profitability metrics are weak, cash generation is strong. The company converts earnings to cash efficiently (good earnings quality) but has mediocre returns on capital. Maintain SELL/AVOID recommendation but note the cash quality as a partial mitigant.

---

## Appendix A: Academic Citations

### Primary Research Papers

1. **Novy-Marx, R.** (2013). "The Other Side of Value: The Gross Profitability Premium." Journal of Financial Economics, 108(1), 1-28.

2. **Fama, E.F. & French, K.R.** (2015). "A Five-Factor Asset Pricing Model." Journal of Financial Economics, 116(1), 1-22.

3. **Asness, C.S., Frazzini, A., & Pedersen, L.H.** (2019). "Quality Minus Junk." Review of Accounting Studies, 24(1), 34-112.

4. **Sloan, R.G.** (1996). "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows About Future Earnings?" The Accounting Review, 71(3), 289-315.

5. **Cooper, M.J., Gulen, H., & Schill, M.J.** (2008). "Asset Growth and the Cross-Section of Stock Returns." Journal of Finance, 63(4), 1609-1651.

6. **Piotroski, J.D.** (2000). "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." Journal of Accounting Research, 38, 1-41.

7. **Novy-Marx, R. & Medhat, M.** (2025). "Profitability Retrospective: What Have We Learned?" NBER Working Paper No. 33601.

8. **Richardson, S.A., Sloan, R.G., Soliman, M.T., & Tuna, I.** (2005). "Accrual Reliability, Earnings Persistence and Stock Prices." Journal of Accounting and Economics, 39(3), 437-485.

### Data Sources

- Kenneth French Data Library: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- AQR Data Sets: https://www.aqr.com/Insights/Datasets
- NBER Working Papers: https://www.nber.org/papers

---

## Appendix B: Implementation Code Snippets

### B.1 Gross Profitability Calculator
```python
def calculate_gross_profitability(revenue, cogs, total_assets):
    """
    Calculate Gross Profitability per Novy-Marx (2013)
    Returns: float (as decimal, multiply by 100 for percentage)
    """
    if total_assets == 0:
        return None
    gross_profit = revenue - cogs
    return gross_profit / total_assets
```

### B.2 Accrual Ratio Calculator
```python
def calculate_accrual_ratio(net_income, operating_cash_flow, avg_total_assets):
    """
    Calculate Accrual Ratio per Sloan (1996)
    Lower is better (negative indicates high earnings quality)
    """
    if avg_total_assets == 0:
        return None
    accruals = net_income - operating_cash_flow
    return accruals / avg_total_assets
```

### B.3 Piotroski F-Score Calculator
```python
def calculate_f_score(data):
    """
    Calculate Piotroski F-Score (9 binary signals)
    data: dict with current and prior year financials
    Returns: int from 0-9
    """
    score = 0
    
    # Profitability (4 points)
    if data['roa'] > 0:
        score += 1
    if data['cfo'] > 0:
        score += 1
    if data['roa'] > data['prior_roa']:
        score += 1
    if data['cfo'] > data['net_income']:  # Low accruals
        score += 1
    
    # Leverage & Liquidity (3 points)
    if data['leverage'] < data['prior_leverage']:
        score += 1
    if data['current_ratio'] > data['prior_current_ratio']:
        score += 1
    if data['shares_outstanding'] <= data['prior_shares']:
        score += 1
    
    # Efficiency (2 points)
    if data['gross_margin'] > data['prior_gross_margin']:
        score += 1
    if data['asset_turnover'] > data['prior_asset_turnover']:
        score += 1
    
    return score
```

### B.4 Asset Growth Red Flag
```python
def check_asset_growth_flag(total_assets, prior_assets, threshold=0.20):
    """
    Flag companies with aggressive asset growth
    Based on Cooper, Gulen, Schill (2008)
    """
    if prior_assets == 0:
        return None
    growth = (total_assets - prior_assets) / prior_assets
    return {
        'rate': growth,
        'flag': growth > threshold,
        'severity': 'HIGH' if growth > 0.30 else 'MODERATE' if growth > threshold else 'NONE'
    }
```

---

## Appendix C: Quality Score Weighting Matrix

Based on meta-analysis of academic research, optimal factor weights:

| Factor Category | Weight | Primary Metric | Secondary Metrics |
|----------------|--------|----------------|-------------------|
| Profitability | 35% | Gross Profitability | ROE, ROIC, Operating Margin |
| Earnings Quality | 20% | Accrual Ratio | Cash Conversion, F-Score components |
| Growth Quality | 15% | Asset Growth (inverse) | Revenue Quality, Margin Trend |
| Safety | 15% | Leverage Ratios | Beta, Volatility, Z-Score |
| ROE Persistence | 15% | Years > 15% | ROE Trend, Incremental ROCE |

---

---

## Part XI: The 2025 Profitability Retrospective (Novy-Marx & Medhat)

### 11.1 The Subsumption Result

The March 2025 NBER working paper **"Profitability Retrospective: What Have We Learned?"** (NBER WP 33601) ran spanning tests for every major quality composite against the Fama-French factors plus momentum and profitability. The central finding:

> Profitability subsumes *all* quality factors. None of the quality factors — whether commercial (MSCI Quality, S&P 500 Quality, Russell Quality, etc.) or academic (QMJ, GMJ, Profitability-Growth-Safety composites) — generated significant positive alpha relative to profitability, the other Fama and French factors, and momentum. The t-statistic on profitability's alpha in the reverse regressions is always around six, implying information ratios of roughly **0.85**.

### 11.2 Implications for Portfolio Construction

1. **Anchor factor**: Gross profits-to-assets is the dominant signal. Any composite score that dilutes it with correlated metrics (ROE, ROA, GM) adds noise without alpha.
2. **Defensive / low-vol**: Low-beta and low-volatility "defensive" premia are also primarily driven by profitability loadings — low-vol stocks happen to be profitable.
3. **Value's lost decade**: Profitability explains about **half of value's underperformance since 2007** because growth indices loaded heavily on profitable firms that re-rated.
4. **Design rule**: Secondary quality signals (F-Score, accruals, asset growth, safety, payout) should be used as **filters and risk controls** rather than equal-weighted components that dilute the profitability signal.

### 11.3 Practical Adjustment to the Scanner

The existing `NEW_5FACTOR` framework already places 35% weight on profitability. The 2025 evidence suggests two refinements that should be layered in (implemented in `quality/opportunity_scorer.py`):

- **Cross-sectional z-score ranking** of gross profits-to-assets as the primary sort.
- **Safety/growth/payout signals used as gates** (hard filters) rather than continuous additive scores, when the goal is opportunity discovery rather than portfolio-level diversification.

---

## Part XII: The q-Factor Model and Expected Growth (Hou, Xue, Zhang)

### 12.1 The q-Factor Framework

The **q-factor model** (Hou, Xue, Zhang, 2015; Review of Financial Studies) derives factor pricing from the investment CAPM: a firm's expected return is *increasing in expected profitability* and *decreasing in the investment rate*. The four factors:

| Factor | Definition |
|--------|------------|
| MKT | Market excess return |
| ME | Size (market equity) |
| I/A | Investment-to-assets (inverse) |
| ROE | Return on equity (current) |

Unlike Fama-French RMW (which uses operating profitability), the q-factor uses **current ROE**, making it sensitive to recency and consistent with the investment CAPM derivation.

### 12.2 q5 and the Expected Growth Factor

Hou, Mo, Xue, Zhang (2021, Review of Finance, "Which Factors?") extended the model with an **expected growth factor (Eg)**. Expected growth is predicted by cross-sectional regressions of future changes in investment-to-assets on:

- **log(Tobin's q)** (investment opportunities)
- **Operating cash flows / assets** (internally financed growth capacity)
- **Change in ROE** (profitability trajectory)

The expected-growth premium averages **0.84% per month** — one of the strongest documented anomaly premia. The resulting **q5 model** outperforms every competing factor model: across 158 anomalies, the average |high-minus-low alpha| drops from 0.25%/month (q-factor) to **0.18%/month (q5)**.

### 12.3 Implementation for Opportunity Discovery

Expected growth is a forward-looking signal that the scanner can approximate without forecasting:

```
Expected_Growth_Proxy = (
    0.4 × z(log Tobin's Q or P/B)        # Investment opportunity set
  + 0.4 × z(Operating Cash Flow / Assets) # CFOA — internal funding
  + 0.2 × z(Δ ROE over 2yr)              # Profitability trajectory
)
```

This proxy slots in alongside gross profitability as a **second orthogonal quality dimension** and has been added as a first-class score in the opportunity scorer.

---

## Part XIII: The Mohanram G-Score (Growth-Stock Quality)

### 13.1 Background

Piotroski's F-Score was designed for **value stocks** (high B/M). On low-B/M "glamour" stocks, F-Score loses power because many glamour companies look healthy by backward-looking accounting metrics and then disappoint. **Partha Mohanram (2005, Review of Accounting Studies, "Separating Winners from Losers Among Low Book-to-Market Stocks")** developed the **G-Score** specifically for low-B/M firms.

### 13.2 The Eight G-Score Signals

Each signal is evaluated *relative to industry median* (not absolute thresholds):

| # | Signal | Industry-Median Comparison |
|---|--------|----------------------------|
| G1 | ROA | 1 if ROA > industry median |
| G2 | Cash Flow ROA (CFO/Assets) | 1 if CFROA > industry median |
| G3 | Earnings > Cash? | 1 if CFO > Net Income |
| G4 | Earnings stability | 1 if 5-yr σ(ROA) < industry median |
| G5 | Sales-growth stability | 1 if 5-yr σ(sales growth) < industry median |
| G6 | R&D intensity | 1 if R&D / Assets > industry median |
| G7 | CapEx intensity | 1 if CapEx / Assets > industry median |
| G8 | Advertising intensity | 1 if Ad / Assets > industry median |

### 13.3 Performance

- High G-Score (6–8): **+3.3% and +2.4%** size-adjusted returns in years 1 and 2.
- Low G-Score (0–1): **-17.9% and -13.3%** — Mohanram calls these "torpedo stocks."
- Spread of **~20%+** over 1–2 years for the long–short portfolio.
- Performance is strongest among **low B/M firms** (growth stocks) and complements F-Score, which works best in high B/M (value stocks).

### 13.4 Use in the Scanner

The scanner is index-agnostic (SP500 through Russell 3000), so B/M varies widely. The opportunity discovery module:

1. **Uses F-Score when B/M ≥ median** (value tilt).
2. **Uses G-Score when B/M < median** (growth tilt).
3. **Reports both** for transparency, so the portfolio manager can weight them.

Since the current SimFin + yfinance pipeline does not yet expose R&D, Ad, and CapEx intensity consistently, G-Score uses the **four-signal core (G1-G4)** from the profitability/earnings-quality tier — which Mohanram reports captures most of the predictive power on its own.

---

## Part XIV: The Beneish M-Score (Earnings-Manipulation Screen)

### 14.1 Purpose

Messod Beneish (1999, Financial Analysts Journal, "The Detection of Earnings Manipulation") built an **8-variable probit-style score** to flag probable earnings manipulators. It was famously one of the few academic models to flag **Enron in 1998**, two years before the collapse.

### 14.2 Formula

```
M = -4.84
  + 0.920 × DSRI   (Days Sales in Receivables Index)
  + 0.528 × GMI    (Gross Margin Index)
  + 0.404 × AQI    (Asset Quality Index)
  + 0.892 × SGI    (Sales Growth Index)
  + 0.115 × DEPI   (Depreciation Index)
  - 0.172 × SGAI   (SG&A Index)
  + 4.679 × TATA   (Total Accruals to Total Assets)
  - 0.327 × LVGI   (Leverage Index)
```

**Decision rule:** `M > -1.78` flags elevated manipulation risk.

### 14.3 Accuracy

- Original paper: correctly flagged **76%** of manipulators while falsely flagging only **17.5%** of non-manipulators.
- Beneish (2020, "The Cost of Fraud Prediction Errors") showed the M-score still has the best false-to-true-positive ratio of any rules-based method, beaten only by modern ML models.
- 2025 evidence (Özari et al., Sage): combining **Altman Z + Beneish M** via random forest identifies financial statement fraud with high precision on Borsa Istanbul data.

### 14.4 Use in the Scanner

M-Score is an **exclusion screen**, not a ranking signal. The opportunity discovery workflow:

- Computes M-Score when 3+ years of history and accrual/receivables data are available.
- Flags `M > -1.78` as a HIGH severity red flag.
- Excludes candidates from the "Elite" tier automatically, even if their composite quality score is high.

---

## Part XV: Shareholder Yield (The Payout Dimension)

### 15.1 Research Evidence

Meb Faber ("Shareholder Yield," 2007/2013) and subsequent work by MSCI, S&P, and AAII demonstrated that **total shareholder yield** — dividends + net buybacks — is a stronger predictor of returns than dividend yield alone.

```
Shareholder Yield = (Dividends + Net Buybacks) / Market Cap
Net Buybacks       = Gross Repurchases - Net Equity Issuance
```

### 15.2 Key Empirical Results

- **Top 10% buyback portfolio**: **946% return over 20 years** (~12.5% annualized), vs. ~9% for the S&P 500.
- **Top 25% by shareholder yield**: **15.3%** annualized vs. **10.7%** for bottom 25% — a **4.6% spread**.
- Buyback signal dominates dividend signal post-2003 (when buybacks overtook dividends as the primary payout mechanism).
- Combined (div + buyback) mitigates sector bias: pure-dividend strategies over-weight utilities/REITs; pure-buyback strategies over-weight tech/financials.

### 15.3 Net Issuance Anomaly

AQR's QMJ captures the flip side: **firms issuing equity underperform**. Pontiff and Woodgate (2008) document a robust short-leg effect — top-decile net issuers underperform bottom-decile net issuers by ~8% annually.

### 15.4 Scanner Implementation

```python
shareholder_yield = (dividends_paid + abs(net_buybacks)) / market_cap
net_issuance     = (shares_end - shares_start) / shares_start
```

- High shareholder yield (>5%) + high profitability = "cash-return compounder" (high-confidence signal).
- Negative shareholder yield + high asset growth = "empire builder" red flag.

---

## Part XVI: Quality at a Reasonable Price (QARP)

### 16.1 Rationale

Pure quality strategies underperformed in 2024–2025 after a decade of outperformance — Oakmark's 4Q 2025 commentary noted quality had its "worst year relative to average European stocks." The reason: high-quality firms re-rated to expensive multiples. The **QARP** approach combines quality with valuation to avoid paying extreme prices for compounders.

### 16.2 QARP Formula

```
QARP_Score = α × Quality_z + (1 - α) × Value_z

where:
  Quality_z = cross-sectional z-score of (GPOA, ROE, F-Score, -Accruals, Cash_Conv)
  Value_z   = cross-sectional z-score of (FCF_Yield, Earnings_Yield, -EV/EBITDA)
  α ≈ 0.6   (tilt toward quality)
```

### 16.3 Why It Works

- **Mean reversion in multiples**: even profitable firms underperform when bought at extreme multiples.
- **Compounding math**: buying a 20% ROIC firm at 30x earnings yields a lower IRR than a 15% ROIC firm at 12x.
- **Behavioral edge**: markets consistently over-pay for "glamour quality" (see Mohanram 2005).

### 16.4 Scanner Implementation

QARP is implemented as a second ranking in the opportunity scorer:

- **Quality-only rank** → the "compounders" list (may include richly-valued names).
- **QARP rank** → the "discount compounders" list (our recommended buy list).

---

## Part XVII: Intangibles-Adjusted Metrics (Arnott et al.)

### 17.1 The Problem

Under U.S. GAAP, internally generated intangibles (R&D, brand, organizational capital) are **expensed rather than capitalized**. This:

- Understates book value for R&D-heavy firms (tech, pharma, consumer brands).
- Inflates ROE and ROA artificially (smaller equity/asset denominators).
- Makes traditional B/M misclassify growth/value.

Arnott et al. (2021, "Reports of Value's Death May Be Greatly Exaggerated") and Park (2022) show that **capitalizing intangibles improves the value factor** and reduces quality/value correlation.

### 17.2 Methodology

**R&D capital stock (perpetual inventory method):**
```
RC_t = (1 - δ) × RC_{t-1} + R&D_t    where δ = 0.20 (typical)
```

**Organization capital stock:**
```
OC_t = (1 - δ) × OC_{t-1} + 0.30 × SG&A_t    where δ = 0.20
```
(30% of SG&A is treated as investment in intangible capital.)

**Adjusted book equity:**
```
Book_Equity_Adj = Book_Equity + RC + OC
```

**Adjusted metrics:**
```
GPOA_Adj = Gross_Profits / (Assets + RC + OC)
ROE_Adj  = Net_Income    / Book_Equity_Adj
B/M_Adj  = Book_Equity_Adj / Market_Cap
```

### 17.3 Result

- Intangibles-adjusted value factor generates ~**1–3% additional annual alpha** on top of traditional HML.
- Quality scores become more consistent across asset-heavy (industrials) and asset-light (software) firms.

### 17.4 Scanner Implementation

Requires R&D and SG&A line items, which SimFin provides inconsistently and yfinance provides for most large-caps. The opportunity scorer computes intangibles-adjusted GPOA when R&D is available and **falls back to traditional GPOA otherwise**. The adjustment is especially important when comparing tech-heavy (NASDAQ 100) and industrial-heavy (SP 600) universes in the same screen.

---

## Part XVIII: Quality Acceleration

### 18.1 New 2024 Research

Ma, Yang, Ye (2024, "Quality Acceleration and Cross-Sectional Returns," Research in International Business and Finance) document a new anomaly distinct from quality **level** and quality **growth**: quality **acceleration** — the second derivative.

Long–short portfolio sorted on quality acceleration delivers:

- **0.49% monthly equal-weighted alpha**
- **0.69% monthly value-weighted alpha**
- Significant after FF3, Carhart 4, and FF5 adjustments.

### 18.2 Computation

```
Quality_Growth_t     = Quality_Score_t - Quality_Score_{t-1}
Quality_Acceleration = Quality_Growth_t - Quality_Growth_{t-1}
```

Firms with **rising rates of improvement** in their quality metrics (ROA, ROE, GPOA, gross margin) outperform firms with stable or decelerating quality — markets under-react to the *pace* of improvement.

### 18.3 Scanner Implementation

With 4+ years of SimFin history already in the pipeline, the scanner computes:

- Quality score for the current year and each of the 3 prior years.
- Year-over-year deltas (growth) and second differences (acceleration).
- An **acceleration flag** is raised when the 2-year trailing quality acceleration is positive and above the cross-sectional 70th percentile.

---

## Part XIX: Opportunity Discovery Framework

This part connects the research directly to the scanner's code.

### 19.1 Two-Stage Pipeline

```
Stage 1: Universe Fetch (existing infrastructure)
   data.watchlist_config.WatchlistConfig
   → data.parallel_fetcher.ParallelFetcher
   → data.enhanced_hybrid_fetcher.EnhancedHybridDataFetcher
   → ratio_calculator.FinancialRatioCalculator
   → Dict[ticker, merged_financials]

Stage 2: Cross-sectional Opportunity Scoring (new module)
   quality.opportunity_scorer.OpportunityScorer
   → Cross-sectional z-scores within universe
   → QMJ-style composite + QARP composite + Expected-Growth proxy
   → Hard gates (M-Score, asset growth, F-Score floor)
   → Ranked OpportunityReport
```

### 19.2 Composite Score (Profitability-Anchored)

Consistent with Novy-Marx & Medhat (2025), profitability is the anchor. All other signals are orthogonalized through z-scoring and weighted modestly:

```
Opportunity_Score = (
    0.40 × z(Gross_Profitability)             # Anchor (Novy-Marx)
  + 0.15 × z(ROE_Persistence)                 # 5-yr median ROE
  + 0.10 × z(Cash_Flow_Quality)               # OCF / NI (Sloan)
  + 0.10 × z(Expected_Growth_Proxy)           # q5 proxy (Hou-Mo-Xue-Zhang)
  + 0.10 × z(-Accruals)                       # Low accruals good (Sloan)
  + 0.05 × z(-Asset_Growth)                   # Conservative invest (Cooper)
  + 0.05 × z(Shareholder_Yield)               # Payout (Faber / QMJ)
  + 0.05 × z(Quality_Acceleration)            # 2nd-derivative (Ma 2024)
)
```

### 19.3 Hard Gates (Exclude from Opportunity List)

| Gate | Threshold | Source |
|------|-----------|--------|
| F-Score | ≥ 5 | Piotroski (2000) |
| Asset Growth | ≤ 40% YoY | Cooper et al. (2008) |
| Accrual Ratio | ≤ 10% | Sloan (1996) |
| Beneish M | ≤ -1.78 | Beneish (1999) |
| Altman Z | ≥ 1.8 | Altman (1968) |
| Interest Coverage | ≥ 2x | Safety |

### 19.4 QARP Overlay

After cross-sectional quality ranking, the scanner re-ranks by blending in valuation:

```
QARP_Score = 0.6 × z(Quality_Composite) + 0.4 × z(Value_Composite)

Value_Composite = z(FCF_Yield) + z(Earnings_Yield) - z(EV/EBITDA)
```

### 19.5 Output Classes

| Tier | Definition | Intended Use |
|------|------------|--------------|
| **Compounder** | Top 10% quality, all gates pass | Hold long-term |
| **Discount Compounder** | Top 20% QARP, all gates pass | Priority buy |
| **Rising Quality** | Quality Acceleration > 70th %-ile + F-Score ↑ | Watch for entry |
| **Cash Return** | Shareholder Yield > 5% + GPOA > 30% | Yield + growth |
| **Red Flag** | Any HARD-GATE failure | Exclude / short candidate |

### 19.6 Integration Points in the Codebase

- **New file:** `quality/opportunity_scorer.py` — cross-sectional scorer.
- **New file:** `workflows/opportunity_discovery.py` — end-to-end workflow.
- **Modified:** `main_quality_analysis.py` — adds `--discover` flag for opportunity mode.
- **Reuses:** `data/enhanced_hybrid_fetcher.py`, `data/parallel_fetcher.py`, `data/ratio_calculator.py`, `data/watchlist_config.py`, `quality/earnings_quality.py` (F-Score).

### 19.7 Output Files

```
outputs/opportunities_YYYYMMDD.json        # Full ranked opportunity data
outputs/opportunities_YYYYMMDD_top.txt     # Human-readable top-25 shortlist
outputs/opportunities_YYYYMMDD_red.txt     # Red-flag exclusion report
```

---

## Appendix D: Extended Academic Citations (2020-2026)

### Post-2020 Primary Research

9. **Hou, K., Mo, H., Xue, C., & Zhang, L.** (2021). "An Augmented q-Factor Model with Expected Growth." *Review of Finance*, 25(1), 1-41. [Expected growth factor]

10. **Arnott, R.D., Harvey, C.R., Kalesnik, V., & Linnainmaa, J.T.** (2021). "Reports of Value's Death May Be Greatly Exaggerated." *Financial Analysts Journal*, 77(1), 44-67. [Intangibles-adjusted value]

11. **Mohanram, P.S.** (2005). "Separating Winners from Losers Among Low Book-to-Market Stocks Using Financial Statement Analysis." *Review of Accounting Studies*, 10, 133-170. [G-Score]

12. **Beneish, M.D.** (1999). "The Detection of Earnings Manipulation." *Financial Analysts Journal*, 55(5), 24-36. [M-Score]

13. **Beneish, M.D., & Vorst, P.** (2022). "The Cost of Fraud Prediction Errors." *The Accounting Review*, 97(6), 91-121. [M-Score validation]

14. **Ma, Y., Yang, B., & Ye, T.** (2024). "Quality Acceleration and Cross-Sectional Returns: Empirical Evidence." *Research in International Business and Finance*, April 2024. [Quality acceleration anomaly]

15. **Pontiff, J., & Woodgate, A.** (2008). "Share Issuance and Cross-Sectional Returns." *Journal of Finance*, 63(2), 921-945. [Net issuance anomaly]

16. **Faber, M.T.** (2013). "Shareholder Yield: A Better Approach to Dividend Investing." Cambria Investment Management. [Shareholder yield]

17. **Piotroski, J.D., & So, E.C.** (2023–2024 updates). "Piotroski F-Score under Varying Economic Conditions." *Review of Quantitative Finance and Accounting.* [F-Score regime dependence]

### Industry Research (Vetted)

- **Oakmark Funds** (4Q 2025). International Equity Market Commentary — Quality underperformance and mean reversion signal.
- **MSCI** (2025). Quality Factor Review.
- **Alpha Architect** (2025). Profitability Retrospective: Key Takeaways.
- **AQR** (2024–2025). QMJ dataset updates — `aqr.com/Insights/Datasets`.

---

*Document compiled from peer-reviewed academic research for educational and analytical purposes. Past performance of factor strategies does not guarantee future results. Always conduct independent due diligence.*
