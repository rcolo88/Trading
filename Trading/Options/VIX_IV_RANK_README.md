# VIX and IV Rank Implementation

## Overview
The synthetic options data generator now includes **VIX (CBOE Volatility Index)** and **IV Rank** for every trading day, allowing you to filter trades based on implied volatility conditions.

## What Was Added

### 1. VIX Data (`vix` column)
- **Source**: Downloaded from Yahoo Finance (ticker: ^VIX)
- **Description**: The CBOE Volatility Index, representing the market's expectation of 30-day volatility
- **Range in dataset**: 11.86 - 38.57
- **Mean**: 19.37

### 2. IV Rank (`iv_rank` column)
- **Formula**: `IV Rank = [(Current VIX - 52-week Low VIX) / (52-week High VIX - 52-week Low VIX)] × 100`
- **Range**: 0 - 100
  - **0** = VIX at the lowest point in the past year
  - **100** = VIX at the highest point in the past year
- **Lookback Period**: 252 trading days (~1 year)
- **Mean**: 26.92

## How IV Rank Works

IV Rank tells you where current implied volatility sits relative to its 1-year range:

- **Low IV (< 30)**: 64.2% of days in dataset
  - Good time to **BUY options** (premiums are cheap)
  - Consider: Bull call spreads, bear put spreads, long straddles

- **Medium IV (30-70)**: 29.4% of days
  - Neutral environment
  - Most strategies viable

- **High IV (> 70)**: 6.4% of days
  - Good time to **SELL options** (premiums are expensive)
  - Consider: Bull put spreads, bear call spreads, iron condors

## Usage in Backtesting

### Example 1: Filter for High IV Entry (Credit Spreads)
```python
# Only enter credit spreads when IV Rank > 40
if config['market_filters']['use_iv_rank']:
    iv_rank_min = config['market_filters']['iv_rank_min']
    
    # Filter options data
    high_iv_days = options_data[options_data['iv_rank'] >= iv_rank_min]
```

### Example 2: Filter for Low IV Entry (Debit Spreads)
```python
# Only enter debit spreads when IV Rank < 30
low_iv_days = options_data[options_data['iv_rank'] < 30]
```

### Example 3: Dynamic Strategy Selection
```python
# Use different strategies based on IV environment
if iv_rank > 70:
    strategy = BullPutSpread()  # Sell premium
elif iv_rank < 30:
    strategy = BullCallSpread()  # Buy options
else:
    strategy = None  # Skip trade
```

## Configuration

Update `config/config.yaml` to use IV Rank filters:

```yaml
# Market filters (optional entry conditions)
market_filters:
  use_iv_rank: true
  iv_rank_min: 40  # For credit spreads
  iv_rank_max: 70  # For debit spreads
```

## Data Statistics

From your 3-year SPY dataset (2022-2024):

| Metric | VIX | IV Rank |
|--------|-----|---------|
| Min | 11.86 | 0.00 |
| Max | 38.57 | 100.00 |
| Mean | 19.37 | 26.92 |
| Median | 18.39 | 19.90 |

### Notable High IV Events (IV Rank = 100)
1. **March 2022**: Ukraine war, VIX 33-36 (Bearish panic)
2. **August 2024**: Market correction, VIX 23 (Relative to calm 2024)

### Notable Low IV Periods (IV Rank = 0)
1. **January-April 2023**: Market recovery, VIX 17-18 (Complacency)

## Files Modified

1. **`src/data_fetchers/synthetic_generator.py`**
   - Added VIX download in `fetch_underlying_data()`
   - Added IV Rank calculation using 252-day rolling window
   - Updated `generate_options_chain()` to include VIX and IV Rank in each option row

2. **`data/processed/SPY_synthetic_options_2022-01-01_2024-12-31.csv`**
   - Now includes `vix` and `iv_rank` columns for every option contract

## Next Steps

1. **Test IV Rank Filters**: Update your config.yaml to use IV rank filtering
2. **Compare Strategies**: Backtest credit spreads with high IV vs low IV entry
3. **Optimize Thresholds**: Find optimal IV rank thresholds for your strategies

## References

- [IV Rank Formula](https://www.projectfinance.com/iv-rank-percentile/)
- [CBOE VIX Index](https://www.cboe.com/tradable_products/vix/)
- [Using IV Rank in Options Trading](https://www.warriortrading.com/implied-volatility-iv-rank/)

---
Generated: October 25, 2025
Dataset: SPY 2022-2024 (752 trading days)
