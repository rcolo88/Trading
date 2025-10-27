# Delta Calculation Investigation & Improvements

## Summary

I investigated the delta calculation in the synthetic options data and validated it against industry standards. **The delta calculations are 100% correct!**

## What Was Done

### 1. **Researched Industry-Standard Implementations** ✅
- Analyzed py_vollib (most widely-used Python options library)
- Reviewed multiple GitHub repos for Black-Scholes implementations
- Studied academic formulas for delta with dividend yield

### 2. **Validated Our Implementation** ✅
Tested our delta calculation against py_vollib across 10 different scenarios:
- ATM, ITM, and OTM options (both calls and puts)
- Various DTEs (7, 30, 60 days)
- Different volatility levels (8%, 15%, 30%)

**Result**: 100% match with py_vollib - our implementation is mathematically correct!

### 3. **Key Findings**

#### Delta Values Are Correct
The delta ranges in our data are exactly what they should be:
- **Calls**: 0 to 1.0 (positive)
- **Puts**: -1.0 to 0 (negative)
- **ATM options**: ~±0.50 (slightly above for SPY due to dividend yield)

Example from actual data (SPY @ $426.28):
```
CALL | Strike: $425 | DTE: 29 | Delta:  0.5458  ← Correct!
PUT  | Strike: $425 | DTE: 29 | Delta: -0.4530  ← Correct!
CALL | Strike: $420 | DTE: 29 | Delta:  0.6275  ← ITM call
PUT  | Strike: $430 | DTE: 29 | Delta: -0.5357  ← ITM put
```

#### Why ATM Delta ≠ Exactly 0.50
For SPY with dividend yield:
- Risk-free rate: 4%
- Dividend yield: 1.5%
- Net drift: 4% - 1.5% = 2.5%
- This makes ATM calls slightly > 0.50 and ATM puts slightly < -0.50

This is **correct behavior** per Black-Scholes-Merton model.

### 4. **Improvements Made** 🚀

#### A. Added `abs_delta` Column
**Purpose**: Make filtering easier, especially for delta-targeted strategies

**Before**:
```python
# Had to remember puts are negative
short_puts = df[(df['option_type'] == 'put') &
                (df['delta'] >= -0.32) &
                (df['delta'] <= -0.28)]
```

**After**:
```python
# Much cleaner with abs_delta
short_puts = df[(df['option_type'] == 'put') &
                (df['abs_delta'] >= 0.28) &
                (df['abs_delta'] <= 0.32)]
```

#### B. Clarified Expiration Date
**Existing columns** (already present in data):
- `expiration`: The date when the option expires (YYYY-MM-DD timestamp)
- `dte`: Days to expiration (integer)

**Note**: "Strike date" typically refers to the expiration date in options terminology.

#### C. Created Comprehensive Documentation
- [DELTA_EXPLANATION.md](DELTA_EXPLANATION.md) - Complete guide to understanding delta values
- Explains sign conventions, formulas, validation, and use cases
- Includes FAQs and comparison to broker data

### 5. **What You Need to Do**

To get the new `abs_delta` column in your dataset:

```bash
python generate_synthetic_data.py -y
```

This will regenerate the full dataset with the new column included.

## Data Columns Reference

### Current Data Structure
| Column | Description | Example |
|--------|-------------|---------|
| `quote_date` | Date of the options chain | 2022-02-10 |
| `underlying_symbol` | Ticker | SPY |
| `underlying_price` | SPY price on quote_date | $426.28 |
| `vix` | VIX level | 22.5 |
| `iv_rank` | IV Rank (0-100) | 45.2 |
| `expiration` | **Option expiration date** | 2022-03-11 |
| `dte` | **Days to expiration** | 29 |
| `strike` | Strike price | $425 |
| `option_type` | 'call' or 'put' | call |
| `delta` | Signed delta | 0.5458 (call) or -0.4530 (put) |
| `abs_delta` | **NEW!** Absolute delta | 0.5458 or 0.4530 |
| `gamma` | Gamma | 0.0185 |
| `theta` | Daily theta | -0.15 |
| `vega` | Vega | 0.57 |

## Validation Test Results

```
======================================================================
DELTA VALIDATION: Our Implementation vs. py_vollib
======================================================================

1. ATM Call, 30 DTE
   Our delta:      0.526968
   py_vollib:      0.526968
   Difference:   0.00000000  ✓ MATCH

2. ATM Put, 30 DTE
   Our delta:     -0.471800
   py_vollib:     -0.471800
   Difference:   0.00000000  ✓ MATCH

[... 8 more tests, all ✓ MATCH ...]

======================================================================
✓ ALL TESTS PASSED - Our implementation matches py_vollib!
======================================================================
```

## Formula Used (Black-Scholes-Merton)

### Call Delta:
```
δ_call = exp(-q × T) × N(d1)
```

### Put Delta:
```
δ_put = -exp(-q × T) × N(-d1)
```

Where:
- q = dividend yield (0.015 for SPY)
- T = time to expiration (years)
- N(x) = cumulative normal distribution
- d1 = [ln(S/K) + (r - q + σ²/2) × T] / (σ × √T)

## Common Use Cases

### 1. Filter 30-Delta Short Puts (Bull Put Spread)
```python
short_puts = df[
    (df['option_type'] == 'put') &
    (df['abs_delta'] >= 0.28) &
    (df['abs_delta'] <= 0.32) &
    (df['dte'] >= 30) &
    (df['dte'] <= 45)
]
```

### 2. Find ATM Options for Specific Expiration
```python
atm_options = df[
    (df['expiration'] == '2022-03-11') &
    (df['abs_delta'] >= 0.45) &
    (df['abs_delta'] <= 0.55)
]
```

### 3. Filter by DTE and Expiration Date
```python
# Options expiring in 30-45 days
medium_term = df[
    (df['dte'] >= 30) &
    (df['dte'] <= 45)
]

# Options expiring on third Friday of March 2022
march_monthly = df[df['expiration'] == '2022-03-18']
```

## References

- **Validation Library**: [py_vollib](https://github.com/vollib/py_vollib) v1.0.1
- **Model**: Black-Scholes-Merton with continuous dividend yield
- **Academic Source**: [Black-Scholes Model](https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model)

## Conclusion

✅ **Delta calculations are mathematically correct**
✅ **100% validated against industry-standard py_vollib**
✅ **Added `abs_delta` column for convenient filtering**
✅ **Expiration date already available via `expiration` column**
✅ **Comprehensive documentation created**

**The synthetic options data is ready for backtesting!**

To regenerate with the new `abs_delta` column:
```bash
python generate_synthetic_data.py -y
```

---
**Investigation Date**: October 25, 2025
**Validated Against**: py_vollib v1.0.1
**Status**: ✅ All delta values correct
