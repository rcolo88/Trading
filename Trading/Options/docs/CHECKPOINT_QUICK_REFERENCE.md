# Checkpoint & Resume - Quick Reference

## Quick Start

### Fresh Run with Checkpoints (Enabled by Default)

```python
results = optimizer.run_optimization(
    checkpoint_every=10  # Save every 10 combinations (default)
)
```

**What happens:**
- Saves to `optimization_checkpoints/BullPutSpread_20250123_143022.csv`
- Progress saved every 10 combinations
- If interrupted, no work lost!

---

### Resume from Checkpoint

```python
# After interruption, resume where you left off:
results = optimizer.run_optimization(
    resume_from='optimization_checkpoints/BullPutSpread_20250123_143022.csv'
)
```

**What happens:**
- Loads previous results
- Skips already-completed combinations
- Continues from where it stopped

---

## Common Scenarios

### 1. Long Optimization (Overnight Run)

```python
# Set higher checkpoint frequency for longer runs
optimizer.set_parameter_range('dte', min=20, max=50, step=1)        # 31 values
optimizer.set_parameter_range('delta', min=0.20, max=0.60, step=0.02)  # 21 values
# Total: 651 combinations!

results = optimizer.run_optimization(
    checkpoint_every=25,  # Save more frequently
    confirm=True  # Will show time estimate
)
```

### 2. Interrupted? No Problem!

```
Running optimization...
Progress: 150/651 (23.0%)
    💾 Checkpoint saved: 150 results → BullPutSpread_20250123_143022.csv
^C  <-- You press Ctrl+C

⚠️  Interrupted by user (Ctrl+C)
💾 Saving checkpoint before exit...
    💾 Checkpoint saved: 150 results → BullPutSpread_20250123_143022.csv

To resume later, use:
  results = optimizer.run_optimization(
      resume_from='optimization_checkpoints/BullPutSpread_20250123_143022.csv'
  )
```

**Resume:**
```python
results = optimizer.run_optimization(
    resume_from='optimization_checkpoints/BullPutSpread_20250123_143022.csv'
)

# Output:
# 🔄 RESUME MODE: Loading checkpoint from BullPutSpread_20250123_143022.csv
# 📂 Found existing checkpoint: BullPutSpread_20250123_143022.csv
#     ✓ Loaded 150 previous results
#     ✓ Will skip 150 already-completed combinations
#     ✓ Resuming: 150 already done, 501 remaining
```

### 3. Inspect Checkpoint Files

Checkpoints are just CSV files - open in Excel/Google Sheets:

```csv
dte,delta,sharpe_ratio,total_return,max_drawdown,win_rate,profit_factor
30,0.25,1.52,0.24,-0.08,0.65,2.1
30,0.27,1.48,0.22,-0.09,0.62,2.0
35,0.25,1.67,0.28,-0.05,0.68,2.3
```

**Location:** `optimization_checkpoints/` directory

---

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `checkpoint_every` | `10` | Save progress every N combinations |
| `resume_from` | `None` | Path to checkpoint file, or None for fresh run |

---

## How It Works

### Checkpoint File Naming

```
optimization_checkpoints/
    <StrategyName>_<Timestamp>.csv

Example:
    BullPutSpread_20250123_143022.csv
    CallCalendarSpread_20250123_150845.csv
```

### What Gets Saved

**Each row contains:**
- All parameter values tested (dte, delta, etc.)
- All performance metrics (sharpe_ratio, total_return, etc.)
- Error message (if backtest failed)

### Resume Logic

```
1. Load checkpoint CSV
2. Build set of completed parameter combinations
3. For each combination to test:
   a. Already in set? → Skip it
   b. Not in set? → Run backtest
4. Append new results to loaded results
5. Save updated checkpoint
```

---

## Troubleshooting

### "Checkpoint file not found"

**Problem:** Typo in filename or wrong path

**Solution:**
```python
# List available checkpoints
import os
checkpoints = os.listdir('optimization_checkpoints')
print(checkpoints)

# Use correct filename
results = optimizer.run_optimization(
    resume_from=f'optimization_checkpoints/{checkpoints[0]}'
)
```

### "All combinations already completed"

**Problem:** Trying to resume completed optimization

**Solution:** This is normal! Just means optimization finished.
```
📂 Found existing checkpoint: BullPutSpread_20250123_143022.csv
    ✓ Loaded 651 previous results
    ✓ Will skip 651 already-completed combinations
    ✓ Resuming: 651 already done, 0 remaining

OPTIMIZATION COMPLETE
Total combinations tested: 651
```

### "Parameters don't match"

**Problem:** Checkpoint from different parameter ranges

**Solution:** Start fresh or use correct checkpoint
```python
# Fresh run creates new checkpoint
results = optimizer.run_optimization()  # Don't specify resume_from
```

---

## Performance Impact

**Overhead:** Minimal!
- Saving CSV every 10 combinations: ~0.01 seconds
- Loading checkpoint: ~0.1 seconds
- Checking if combination done: O(1) lookup

**Example:**
```
Without checkpoints: 10,000 combinations in 8 hours
With checkpoints:    10,000 combinations in 8 hours 2 minutes
                     ↑ 0.4% overhead
```

---

## Best Practices

### 1. Choose `checkpoint_every` Based on Runtime

| Avg Time/Backtest | Recommended `checkpoint_every` |
|-------------------|-------------------------------|
| < 1 second | 50 |
| 1-5 seconds | 25 |
| 5-30 seconds | 10 (default) |
| > 30 seconds | 5 |

**Rationale:** More frequent checkpoints for slower backtests = less work lost.

### 2. Clean Up Old Checkpoints

```python
# Delete old checkpoints to save space
import os
from pathlib import Path

checkpoint_dir = Path('optimization_checkpoints')
old_files = sorted(checkpoint_dir.glob('*.csv'))[:-5]  # Keep 5 newest

for f in old_files:
    f.unlink()  # Delete
```

### 3. Name Your Optimizations

```python
# Add descriptive names to checkpoint directory
checkpoint_path = Path(f'optimization_checkpoints/{experiment_name}/')
checkpoint_path.mkdir(exist_ok=True)

# Then checkpoints go in subdirectories:
# optimization_checkpoints/
#     experiment_1_baseline/
#         BullPutSpread_20250123_143022.csv
#     experiment_2_high_iv/
#         BullPutSpread_20250123_150845.csv
```

---

## Advanced: Manual Checkpoint Management

### Save Results Manually

```python
# After optimization
optimizer.results.to_csv('my_custom_checkpoint.csv', index=False)
```

### Load and Merge Checkpoints

```python
import pandas as pd

# Load multiple checkpoint files
df1 = pd.read_csv('optimization_checkpoints/run1.csv')
df2 = pd.read_csv('optimization_checkpoints/run2.csv')

# Merge (remove duplicates)
combined = pd.concat([df1, df2]).drop_duplicates()
combined.to_csv('merged_checkpoint.csv', index=False)
```

### Resume from Custom Checkpoint

```python
results = optimizer.run_optimization(
    resume_from='my_custom_checkpoint.csv'
)
```

---

## See Also

- [Full Learning Guide](LEARNING_INCREMENTAL_SAVE_RESUME.md) - Complete implementation walkthrough
- [Optimization Runtime Estimation](OPTIMIZATION_RUNTIME_ESTIMATION.md) - Time estimation feature
- [Parameter Optimization Guide](../README.md) - Main documentation
