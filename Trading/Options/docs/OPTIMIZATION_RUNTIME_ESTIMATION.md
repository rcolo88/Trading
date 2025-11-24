# Parameter Optimization Runtime Estimation

## Overview

The parameter optimizer now includes **automatic runtime estimation** to help you make informed decisions before starting lengthy optimizations.

## How It Works

### 1. **Sample Backtests**
When you call `run_optimization()`, it first runs 3 random parameter combinations as samples to measure how long each backtest takes.

### 2. **Calculate Estimate**
Using the sample times, it calculates:
- **Average time** per backtest
- **Best case** (fastest sample × total combinations)
- **Worst case** (slowest sample × total combinations)

### 3. **User Confirmation**
The system displays the estimate and asks if you want to proceed:

```
============================================================
RUNTIME ESTIMATE
============================================================
Sample backtests: 3
Average time per backtest: 12.43 seconds
Time range: 11.2s - 14.1s

Total combinations: 4,096

Estimated total runtime:
  Best case:  12.7 hours
  Average:    14.1 hours
  Worst case: 16.0 hours
============================================================

Do you want to proceed with optimization? (y/n):
```

### 4. **Proceed or Cancel**
- Type `y` to continue with the optimization
- Type `n` to cancel (raises `RuntimeError`)

## Usage Examples

### Basic Usage (with confirmation - default)

```python
from src.optimization.parameter_optimizer import ParameterOptimizer
from src.strategies.vertical_spreads import BullPutSpread

# Create optimizer
optimizer = ParameterOptimizer(
    strategy_type='vertical',
    strategy_class=BullPutSpread,
    backtester=backtester,
    options_data=options_data,
    underlying_data=underlying_data,
    base_config=config
)

# Set parameter ranges
optimizer.set_parameter_range('dte', min=30, max=45, step=5)
optimizer.set_parameter_range('short_delta', min=0.25, max=0.40, step=0.05)
optimizer.set_parameter_range('profit_target', min=0.40, max=0.60, step=0.05)

# Run with confirmation (default)
results = optimizer.run_optimization(optimization_metric='sharpe_ratio')
# Will prompt: "Do you want to proceed with optimization? (y/n):"
```

### Skip Confirmation (automated runs)

```python
# For automated scripts where you don't want to be prompted
results = optimizer.run_optimization(
    optimization_metric='sharpe_ratio',
    confirm=False  # Skip confirmation prompt
)
```

### Custom Sample Size

```python
# Use more samples for more accurate estimate (but takes longer)
results = optimizer.run_optimization(
    optimization_metric='sharpe_ratio',
    confirm=True,
    num_samples=5  # Default is 3
)
```

## Parameters

### `run_optimization()` parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `optimization_metric` | str | `'sharpe_ratio'` | Metric to optimize |
| `verbose` | bool | `True` | Print progress updates |
| `confirm` | bool | `True` | Ask for user confirmation before starting |
| `num_samples` | int | `3` | Number of sample backtests for estimation |

## Output

After optimization completes, you'll see:

```
============================================================
OPTIMIZATION COMPLETE
============================================================
Total combinations tested: 4,096
Successful backtests: 4,089
Failed backtests: 7

Actual runtime: 13.8 hours
Average time per backtest: 12.11 seconds

Best sharpe_ratio: 1.8734

Best parameters:
  dte: 35
  short_delta: 0.30
  profit_target: 0.50
============================================================
```

## Tips

### Reducing Runtime

1. **Fewer parameters**: Each parameter multiplies combinations exponentially
   - 4 params × 4 values = 256 combinations ✅
   - 6 params × 4 values = 4,096 combinations ⚠️

2. **Larger step sizes**: Coarser grid = fewer values to test
   - `step=0.01` → 100 values ⚠️
   - `step=0.05` → 20 values ✅

3. **Narrow ranges**: Focus on promising regions
   - Instead of `min=0.10, max=0.60` (51 values)
   - Use `min=0.25, max=0.40` (16 values)

4. **Incremental optimization**:
   - First pass: Wide range, large steps
   - Second pass: Narrow range around best result, smaller steps

### Example: Two-Stage Optimization

```python
# STAGE 1: Coarse search
optimizer.set_parameter_range('dte', min=20, max=50, step=10)  # 4 values
optimizer.set_parameter_range('short_delta', min=0.20, max=0.50, step=0.10)  # 4 values
results1 = optimizer.run_optimization()

# Find best DTE from stage 1
best_dte = results1.iloc[0]['dte']

# STAGE 2: Fine search around best
optimizer2 = ParameterOptimizer(...)
optimizer2.set_parameter_range('dte', min=best_dte-5, max=best_dte+5, step=1)  # 11 values
optimizer2.set_parameter_range('short_delta', min=0.20, max=0.50, step=0.02)  # 16 values
results2 = optimizer2.run_optimization()
```

## Edge Cases

### All Samples Fail

If all sample backtests fail, you'll see:

```
⚠️  All sample backtests failed. Cannot estimate runtime.
Continue anyway? (y/n):
```

You can still proceed, but there's no time estimate.

### Very Fast Backtests

If each backtest takes < 1 second:

```
Estimated total runtime:
  Best case:  42 seconds
  Average:    58 seconds
  Worst case: 73 seconds
```

In this case, you can probably skip confirmation with `confirm=False`.

## Implementation Details

### Problem-Solving Approach

1. **Identified the problem**: Users had no idea how long optimization would take
2. **Found existing code**: `get_total_combinations()` already calculated total
3. **Designed solution**: Sample → estimate → confirm → proceed
4. **Implemented**: Added `_estimate_runtime_and_confirm()` helper method
5. **Integrated**: Modified `run_optimization()` to call helper before main loop
6. **Enhanced**: Added actual runtime tracking at the end

### Key Code Changes

- Added imports: `time`, `random`
- New method: `_estimate_runtime_and_confirm()`
- Modified: `run_optimization()` with new parameters
- Added: Actual runtime tracking and display

See [parameter_optimizer.py](../src/optimization/parameter_optimizer.py) for full implementation.
