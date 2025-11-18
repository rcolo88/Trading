# Data Sources & Acquisition

## Overview

This guide covers all data sources for historical options data, including free and paid options, and the synthetic data generation methodology used for backtesting.

## Current Implementation (Free)

### 1. QuantConnect - Hour-Level Historical Options Data

- **Tier**: Free
- **Coverage**: SPY/SPX with good historical depth
- **Granularity**: Hour-level data
- **Limitation**: Requires QuantConnect account, limited to their platform API
- **Access**: Sign up at quantconnect.com

### 2. Yahoo Finance (yfinance) - Current Options Chains

- **Tier**: Free
- **Coverage**: Current options chains and underlying prices
- **Limitation**: No historical options data, only current chains
- **Use case**: Underlying SPY price data, current options for validation
- **Access**: Python library `yfinance`

### 3. CBOE DataShop - Limited Historical Data

- **Tier**: Limited free tier
- **Coverage**: SPX index options
- **Limitation**: Limited free tier, may not cover 3-5 years
- **Access**: CBOE DataShop website

## Additional Free Data Sources

### 4. OptionsDX - Free Historical Data

- **Website**: https://www.optionsdx.com
- **Coverage**: SPY, SPX, VIX and other popular tickers
- **Historical depth**: EOD data back to 2010
- **Data quality**: Includes pre-calculated Greeks, IV, underlying price
- **Granularity**: Up to minutely intervals available
- **Cost**: Free tier with limited selection, paid for comprehensive data
- **Access method**:
  - Create account on optionsdx.com
  - Browse "Shop" section for free datasets
  - "Checkout" with no billing info required for free data
  - Download links provided via email and account page
  - Files stored on ShareFile.com (access lasts 100 days)
- **Data format**: Monthly CSV files
- **Limitations**:
  - Requires account signup even for free data
  - Updates reportedly slow for free tier
  - Limited selection compared to paid options
- **Status**: VIABLE - Provides 2+ years of free SPY options data

### 5. Polygon.io Free Tier - Options Data

- **Plan**: Options Basic (Free)
- **Coverage**: All US options tickers
- **Historical depth**: Advertised 2 years, actual coverage from 2022+ for options
- **Data quality**: End-of-day, Greeks, IV, Open Interest
- **Rate limit**: 5 API calls per minute
- **Cost**: Free (upgrades from $29/month)
- **Access method**:
  - Sign up at polygon.io
  - Get API key
  - Use polygon-py client library
- **Limitations**:
  - Very limited API rate (5 calls/min)
  - EOD data only (no intraday)
  - Some features require paid plan
  - May not have full historical depth for all tickers
- **Status**: Worth testing, may require paid upgrade for practical use

## Schwab Developer API

- **Status**: Available but limited for this use case
- **Capabilities**: Real-time options chains, equity historical data
- **Limitation**: Does NOT provide historical options data for expired contracts
- **Potential use**: Could be used for paper trading or live implementation after backtesting

## Future Upgrade Path (Paid)

- **Polygon.io**: Comprehensive minute-level historical options data ($200+/month)
- **Databento**: Professional-grade options data
- **ThetaData**: Specialized options historical data provider

## Synthetic Options Data Generation

### Why Synthetic Data?

Since obtaining 2+ years of accurate historical options data for free is challenging, generating synthetic options data using the Black-Scholes model is a **viable alternative** for backtesting strategy performance.

### GitHub Reference Implementation

- **Repository**: `aspiringfastlaner/spx_options_backtesting`
- **Description**: Python scripts for backtesting SPX put strategies using Black-Scholes proxies
- **Approach**: Uses historical underlying prices with Black-Scholes model to estimate option prices
- **Use case**: Demonstrates practical implementation of synthetic options data for backtesting

### Methodology: Generating Synthetic Options Chains

#### Step 1: Obtain Underlying Price Data

```python
# Free from Yahoo Finance via yfinance
import yfinance as yf
spy = yf.Ticker("SPY")
prices = spy.history(start="2022-01-01", end="2024-12-31")
```

#### Step 2: Calculate Historical Volatility

```python
# Rolling historical volatility calculation
returns = prices['Close'].pct_change()
volatility = returns.rolling(window=30).std() * np.sqrt(252)
```

#### Step 3: Generate Options Chain Using Black-Scholes

```python
# Using py_vollib library
from py_vollib.black_scholes import black_scholes
from py_vollib.black_scholes.greeks.analytical import delta, gamma, theta, vega

# For each trading day:
for date in trading_dates:
    S = underlying_price[date]  # Spot price
    K = strike_prices  # Array of strikes around current price
    T = days_to_expiration / 365  # Time to expiration in years
    r = risk_free_rate  # Treasury rate (e.g., 0.04 for 4%)
    sigma = historical_volatility[date]  # Calculated volatility

    # Calculate option prices
    call_price = black_scholes('c', S, K, T, r, sigma)
    put_price = black_scholes('p', S, K, T, r, sigma)

    # Calculate Greeks
    call_delta = delta('c', S, K, T, r, sigma)
    put_delta = delta('p', S, K, T, r, sigma)
    # ... gamma, theta, vega
```

#### Step 4: Generate Delta-Targeted Strikes

```python
# For vertical spreads, we need specific deltas (e.g., 0.30, 0.20)
def find_strike_by_delta(target_delta, option_type, S, T, r, sigma):
    """Binary search to find strike matching target delta"""
    # Implementation finds strike where delta ≈ target_delta
```

#### Step 5: Create Standard Expirations

```python
# Generate weekly and monthly expirations
expirations = []
# Weekly: Every Friday
# Monthly: 3rd Friday of each month
# Calculate DTE for each date
```

### Accuracy Considerations

#### Strengths

- **Good for relative comparisons**: Comparing strategy A vs B performance trends
- **Free and reproducible**: No data costs, fully controlled
- **Sufficient for most backtests**: Especially 30-45 DTE strategies in normal markets
- **Educational value**: Understand options pricing fundamentals

#### Limitations

1. **Constant volatility assumption**: Real volatility varies by strike (volatility smile/skew)
   - Impact: May misprice OTM options
   - Solution: Use implied volatility surface if available, or accept approximation

2. **Model assumptions**: Black-Scholes assumes:
   - No dividends (SPY does pay dividends - use Black-Scholes-Merton instead)
   - Constant risk-free rate
   - Log-normal returns
   - No transaction costs
   - European-style exercise (American options can be exercised early)

3. **Crisis periods**:
   - Research shows 100%+ mispricing during 2008 crisis and COVID-19
   - Underestimates tail risk
   - Normal market R² ≈ 88% vs real data, crisis R² << 50%

4. **Longer-dated options**:
   - Accuracy decreases significantly for 60+ DTE
   - Our use case (30-45 DTE) is within acceptable range

5. **Bid-Ask spread**:
   - Synthetic data produces mid-market prices
   - Need to manually add realistic spread (e.g., 2-5% of option price)

6. **Liquidity**:
   - Real options may not always be tradeable at model prices
   - Especially true for far OTM/ITM strikes

### When Synthetic Data is Acceptable

#### Good for:

- Comparing vertical spread strategies (bull put vs bear call)
- Testing entry/exit timing rules
- Optimizing delta targets and DTE parameters
- Understanding strategy behavior in trending/ranging markets
- Educational/learning purposes
- Proof of concept before investing in real data

#### Not recommended for:

- High-frequency trading strategies
- Crisis period analysis (use real data)
- Precise P&L forecasting (use for relative trends only)
- Strategies sensitive to volatility skew (e.g., ratio spreads)
- Production trading decisions

### Research-Backed Accuracy Benchmarks

Based on academic studies comparing Black-Scholes to real market data:

- **Normal markets**: 88% R² correlation with actual prices
- **Near-term options (< 45 DTE)**: Price differences typically < 10%
- **At-the-money options**: Highest accuracy (< 5% error)
- **30 delta options**: Within acceptable range for backtesting trends
- **Crisis periods**: Accuracy drops significantly, use with caution

### Implementation in This Project

#### Recommended Approach

1. Start with synthetic data generation for immediate backtesting
2. Validate framework logic and strategy implementation
3. Test parameter sensitivity and optimization
4. Document assumptions clearly in backtest reports
5. Upgrade to real data (OptionsDX free tier or Polygon.io) when:
   - Moving toward live trading
   - Need higher accuracy for specific trades
   - Conducting professional-grade research

#### Files Implemented

- `src/data_fetchers/synthetic_generator.py` - Main generator
- `src/utils/black_scholes.py` - Pricing and Greeks calculations
- `config/config.yaml` - Volatility model settings
- `generate_synthetic_data.py` - Easy-to-use script for data generation

## Conclusion

Synthetic data generation is a **practical and cost-effective solution** for backtesting vertical spread strategies on SPY, especially when combined with awareness of its limitations and proper risk disclaimers.

See [DATA_VALIDATION.md](DATA_VALIDATION.md) for comprehensive quality assurance and validation results.
