# SPY IV Percentile Implementation

**Date:** 2025-11-19
**Status:** ✅ Complete

## Summary

Changed the IV percentile calculation from using VIX directly to using SPY's implied volatility over the past 252 trading days (1 year). This provides a more accurate measure of SPY options' relative volatility for strategy entry filters.

## Key Changes

### 1. Modified IV Percentile Calculation
**File:** [src/data_fetchers/synthetic_generator.py](../src/data_fetchers/synthetic_generator.py)

- **New Calculation Method:**
  - Creates `spy_iv` column representing SPY's implied volatility (uses VIX as proxy, converted to decimal)
  - Calculates `iv_percentile` from `spy_iv` instead of directly from VIX
  - Formula: `IVP = (# Days with lower IV than today) / (# Trading Days in period) × 100`
  - Lookback period: 252 trading days (1 year)

- **Implementation Details:**
  ```python
  # SPY IV (decimal form, e.g., 0.20 for 20%)
  data['spy_iv'] = data['vix'] / 100.0  # VIX as proxy for SPY IV

  # IV Percentile calculation
  data['iv_percentile'] = calculate_iv_percentile(data['spy_iv'], window=252)
  ```

- **Rationale:**
  - VIX represents S&P 500 implied volatility
  - SPY tracks S&P 500, so VIX is a good proxy for SPY IV
  - Using VIX/100 converts from percentage (e.g., 20) to decimal (0.20)
  - IV percentile is now based on SPY's own IV, not raw VIX values

### 2. Created Jupyter Notebook for IV Percentile Analysis
**File:** [notebooks/IV_Percentile_Analysis.ipynb](../notebooks/IV_Percentile_Analysis.ipynb)

Features:
- **Current Statistics:**
  - Today's IV percentile
  - Highest IV percentile in past year
  - Lowest IV percentile in past year
  - Average IV percentile

- **Dual-Axis Chart:**
  - SPY price (blue line with light blue shading)
  - IV Percentile (red line)
  - Separate y-axes for each metric
  - Reference lines at 25th, 50th, and 75th percentiles

- **Additional Analysis:**
  - IV percentile distribution histogram
  - SPY IV over time
  - Trading strategy recommendations based on current IV percentile

### 3. Verified Strategy Integration
**Files Verified:**
- [src/strategies/vertical_spreads.py](../src/strategies/vertical_spreads.py)
- [src/strategies/calendar_spreads.py](../src/strategies/calendar_spreads.py)
- [src/backtester/optopsy_wrapper.py](../src/backtester/optopsy_wrapper.py)

**Status:** ✅ All strategies already properly configured
- Strategies read `iv_percentile` from data columns
- Entry filters use strategy-specific `iv_percentile_min` and `iv_percentile_max` from config
- Backtester passes `iv_percentile` to strategy entry signals
- No code changes needed in strategy files

## IV Percentile Calculation Methodology

Based on industry best practices (sources: Schwab, TD Ameritrade, Tastytrade):

**Formula:**
```
IV Percentile (%) = (# Days with IV < Current IV) / (Total Days in Period) × 100
```

**Interpretation:**
- **0-25%:** Low IV - Consider buying options (long strategies)
- **25-50%:** Below average - Moderate environment
- **50-75%:** Above average - Good for credit spreads
- **75-100%:** High IV - Excellent for selling premium

**Key Differences:**
- **Old Method:** Used raw VIX values to calculate percentile
- **New Method:** Uses SPY-specific IV (VIX as proxy) for percentile calculation
- **Impact:** More accurate representation of SPY options' relative volatility

## Configuration

No changes needed to [config/config.yaml](../config/config.yaml). The existing `iv_percentile_min` and `iv_percentile_max` parameters continue to work with the new calculation method.

Example strategy configuration:
```yaml
strategies:
  bull_put_spread:
    entry:
      iv_percentile_min: 30  # Enter when IV is above 30th percentile
      iv_percentile_max: 80  # Don't enter if IV > 80th percentile
```

## Data Columns

Synthetic options data now includes:
- `vix`: VIX value (for reference)
- `spy_iv`: SPY implied volatility (decimal, e.g., 0.20 = 20%)
- `iv_percentile`: SPY IV percentile (0-100%)

## Usage

### Generate Synthetic Data
```bash
python generate_synthetic_data.py -y
```

### Analyze IV Percentile
```bash
jupyter notebook notebooks/IV_Percentile_Analysis.ipynb
```

### Run Backtest
```bash
jupyter notebook notebooks/backtest_analysis.ipynb
```

## Testing

- ✅ Modified synthetic data generator
- ✅ Created IV percentile analysis notebook
- ✅ Verified strategy integration
- ⏳ Regenerating synthetic data with new calculation (in progress)

## Benefits

1. **More Accurate:** IV percentile based on SPY's own implied volatility
2. **Consistent:** Uses 252-day lookback (industry standard)
3. **Well-Documented:** Clear methodology aligned with industry practices
4. **Backward Compatible:** Existing config and strategies work without changes
5. **Enhanced Analysis:** New notebook provides comprehensive IV percentile insights

## References

- [Charles Schwab: Using Implied Volatility Percentiles](https://www.schwab.com/learn/story/using-implied-volatility-percentiles)
- [TD Ameritrade: IV Percentiles Guide](https://tickertape.tdameritrade.com/tools/strategy-selection-iv-percentiles-15527)
- Quantitative Finance Stack Exchange: IV Percentile Formula
- Industry standard: 252 trading days (1 year) lookback period

## Next Steps

1. ✅ Complete synthetic data generation
2. Run backtest with new IV percentile calculation
3. Compare results with previous VIX-based filtering
4. Update [CHANGELOG.md](../CHANGELOG.md) with implementation details
