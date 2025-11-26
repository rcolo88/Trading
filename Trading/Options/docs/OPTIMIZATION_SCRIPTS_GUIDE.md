# Parameter Optimization Scripts Guide

## Overview

Standalone Python scripts for optimizing strategy parameters. Designed to run unattended in Mac terminal, even with the screen closed (clamshell mode).

**Available Scripts:**
- `optimize_bull_put_spread.py` - Bull Put Spread optimization
- `optimize_bull_call_spread.py` - Bull Call Spread optimization
- `optimize_call_calendar_spread.py` - Call Calendar Spread optimization

---

## Quick Start

### Basic Usage

```bash
# Navigate to project directory
cd /path/to/Options

# Run optimization (simplest method)
python optimize_bull_put_spread.py
```

### Recommended Usage (Prevents Mac Sleep)

```bash
# Use caffeinate to prevent Mac from sleeping during optimization
caffeinate -i python optimize_bull_put_spread.py
```

**Why caffeinate?**
- Prevents Mac from going to sleep during long optimizations
- Essential for running with screen closed (clamshell mode)
- Automatic termination when script completes

---

## Running in Clamshell Mode (Screen Closed)

### Prerequisites

✅ **Mac must be plugged into power**
- Required for clamshell mode to work
- On battery: Mac will sleep when lid closes

✅ **External monitor connected** (optional but recommended)
- Allows you to monitor progress
- Can also run "headless" without external monitor

### Best Practices

**Method 1: With External Monitor**

1. Connect external monitor
2. Connect to power
3. Open Terminal on external monitor
4. Run optimization:
   ```bash
   caffeinate -i python optimize_bull_put_spread.py
   ```
5. Close MacBook lid
6. Script continues running, progress visible on external monitor

**Method 2: Headless (No External Monitor)**

1. Connect to power
2. Open Terminal
3. Start optimization:
   ```bash
   caffeinate -i python optimize_bull_put_spread.py > optimization.log 2>&1 &
   ```
4. Close MacBook lid
5. Script runs in background, output saved to log file

**Method 3: Using tmux/screen (Advanced)**

```bash
# Install tmux (if not installed)
brew install tmux

# Start tmux session
tmux new -s optimization

# Run optimization
caffeinate -i python optimize_bull_put_spread.py

# Detach from session: Ctrl+B, then D
# Close lid - script continues running

# Later, reattach to see progress
tmux attach -t optimization
```

---

## Understanding caffeinate Flags

### Common Flags

```bash
# Prevent idle sleep (recommended)
caffeinate -i python script.py

# Prevent display sleep (keeps screen on)
caffeinate -d python script.py

# Prevent disk sleep
caffeinate -m python script.py

# Prevent system sleep (requires AC power)
caffeinate -s python script.py

# Combine multiple flags
caffeinate -ims python script.py
```

### Recommended for Optimization Scripts

```bash
# Best for terminal use (allows display to sleep)
caffeinate -i python optimize_bull_put_spread.py

# Best for clamshell mode (prevents sleep, allows display off)
caffeinate -is python optimize_bull_put_spread.py
```

---

## Output and Results

### Progress Display

Clean progress bar output during optimization:

```
============================================================
BULL PUT SPREAD OPTIMIZATION
============================================================
Started: 2024-11-25 10:30:15
============================================================

Loading configuration...
  ✓ Configuration loaded

Loading market data...
  ✓ Options data: 155,882 rows
  ✓ Underlying data: 220 rows
  ✓ Date range: 2025-01-02 to 2025-11-18

Setting up optimizer...
  ✓ Optimizer configured
  ✓ Total combinations: 36

Starting optimization...
(Progress bar will appear below - this may take several minutes)

Optimizing BullPutSpread:  28%|████      | 10/36 [00:17<00:44, 1.71s/combo] 💾
Optimizing BullPutSpread:  56%|████████  | 20/36 [00:33<00:24, 1.56s/combo] 💾
Optimizing BullPutSpread:  83%|████████▎ | 30/36 [00:48<00:09, 1.59s/combo] 💾
Optimizing BullPutSpread: 100%|██████████| 36/36 [00:58<00:00, 1.63s/combo] ✓

============================================================
OPTIMIZATION COMPLETE
============================================================
Results saved to: optimization_results/BullPutSpread_20241125_103116.csv
Total combinations tested: 36

TOP 5 PARAMETER COMBINATIONS:
----------------------------------------------------------------------
dte  short_delta  profit_target  sharpe_ratio  total_return_pct  max_drawdown_pct  win_rate_pct
 35         0.35            0.6      0.390330          6.141601         -5.781696     37.209302
...
============================================================
Completed: 2024-11-25 10:31:16
============================================================
```

### Results Files

**Location:**
- Main results: `optimization_results/StrategyName_TIMESTAMP.csv`
- Checkpoints: `optimization_checkpoints/StrategyName_TIMESTAMP.csv`

**CSV Contents:**
- All parameter combinations tested
- Performance metrics for each combination
- Sorted by optimization metric (default: sharpe_ratio)

**Example:**
```csv
dte,short_delta,profit_target,sharpe_ratio,total_return_pct,max_drawdown_pct,...
35,0.35,0.6,0.3903,6.14,-5.78,...
35,0.35,0.4,0.3903,6.14,-5.78,...
```

---

## Customizing Parameters

### Edit Parameter Ranges

Open the script and modify the `setup_optimizer()` function:

```python
def setup_optimizer(config, options_data, underlying_data):
    # ... existing code ...

    # Customize these ranges:
    optimizer.set_parameter_range('dte', min=30, max=45, step=5)
    optimizer.set_parameter_range('short_delta', min=0.25, max=0.35, step=0.05)
    optimizer.set_parameter_range('profit_target', min=0.40, max=0.60, step=0.10)

    # ... rest of function ...
```

**Parameter Naming:**
- **Vertical Spreads:** `dte`, `short_delta`, `long_delta`, `profit_target`, `stop_loss`
- **Calendar Spreads:** `near_dte`, `far_dte`, `target_delta`, `profit_target`, `stop_loss`

### Change Optimization Metric

Modify the `run_optimization()` function:

```python
results = optimizer.run_optimization(
    optimization_metric='sharpe_ratio',  # Change to: 'total_return_pct', 'calmar_ratio', etc.
    confirm=False,
    num_samples=3,
    checkpoint_every=10
)
```

---

## Handling Long Optimizations

### Checkpoint Feature

Scripts automatically save progress every 10 combinations:
- Location: `optimization_checkpoints/`
- Resume from checkpoint if interrupted

### Resume After Interruption

If script is interrupted (Ctrl+C or crash):

```python
# In the script, uncomment resume_from line:
results = optimizer.run_optimization(
    optimization_metric='sharpe_ratio',
    confirm=False,
    resume_from='optimization_checkpoints/BullPutSpread_20241125_103030.csv'  # Uncomment this
)
```

### Monitor Long-Running Scripts

```bash
# Run in background with logging
caffeinate -i python optimize_call_calendar_spread.py > optimization.log 2>&1 &

# Monitor progress in real-time
tail -f optimization.log

# Check if still running
ps aux | grep optimize_call_calendar
```

---

## Troubleshooting

### Mac Still Goes to Sleep

**Problem:** Mac sleeps even with caffeinate
**Solutions:**
1. Ensure plugged into power (required for `-s` flag)
2. Check Energy Saver settings: System Preferences → Battery
3. Try different caffeinate flags: `caffeinate -ims`
4. Use Amphetamine app (free from App Store)

### Script Slows Down at Night

**Problem:** Script runs slower when Mac is idle
**Cause:** macOS App Nap feature
**Solutions:**
1. Use caffeinate (disables App Nap)
2. Disable App Nap in Activity Monitor:
   - Find Python process
   - Right-click → Get Info → Prevent App Nap

### Progress Bar Not Showing

**Problem:** No progress bar visible
**Cause:** tqdm not installed
**Solution:**
```bash
pip install tqdm
```

### Script Uses Too Much CPU

**Problem:** Fan running constantly, Mac hot
**Normal behavior:** Optimization is CPU-intensive
**Solutions:**
1. Run at night when Mac is idle
2. Reduce number of parameter combinations
3. Close other applications
4. Ensure good ventilation

---

## Performance Tips

### Optimize Parameter Ranges

**Start small, expand later:**
```python
# Phase 1: Coarse grid (fast)
optimizer.set_parameter_range('dte', min=30, max=45, step=15)  # 2 values

# Phase 2: Fine grid around best results (slower)
optimizer.set_parameter_range('dte', min=30, max=45, step=5)   # 4 values
```

### Parallel Execution (Advanced)

Run multiple strategies in parallel:
```bash
# Terminal 1
caffeinate -i python optimize_bull_put_spread.py > bull_put.log 2>&1 &

# Terminal 2
caffeinate -i python optimize_bull_call_spread.py > bull_call.log 2>&1 &

# Terminal 3
caffeinate -i python optimize_call_calendar_spread.py > calendar.log 2>&1 &
```

**Warning:** High CPU usage, ensure good cooling

---

## Script Comparison

| Script | Typical Combinations | Est. Runtime | CPU Intensity |
|--------|---------------------|--------------|---------------|
| Bull Put Spread | 36 | 1-2 minutes | Medium |
| Bull Call Spread | 128 | 3-5 minutes | Medium |
| Call Calendar | 144 | 5-10 minutes | Medium-High |

**Note:** Runtime depends on:
- Data size (days of history)
- Number of parameter combinations
- Mac performance (M1/M2/Intel)

---

## Best Practices Summary

✅ **DO:**
- Use `caffeinate -i` for all optimizations
- Keep Mac plugged into power
- Start with small parameter ranges
- Save results frequently (checkpoint_every=10)
- Run overnight for large optimizations
- Monitor first run to verify everything works

❌ **DON'T:**
- Run on battery in clamshell mode (will sleep)
- Set checkpoint_every too low (slows down)
- Test too many parameters at once (exponential growth)
- Close terminal window (kills process)

---

## Example Workflow

### Running Multiple Optimizations Overnight

```bash
# 1. Connect to power and external monitor (optional)

# 2. Open terminal

# 3. Navigate to project
cd ~/GitHub/Trading/Options

# 4. Start optimizations in background with logging
caffeinate -i python optimize_bull_put_spread.py > logs/bull_put.log 2>&1 &
sleep 5  # Wait a bit before starting next
caffeinate -i python optimize_bull_call_spread.py > logs/bull_call.log 2>&1 &
sleep 5
caffeinate -i python optimize_call_calendar_spread.py > logs/calendar.log 2>&1 &

# 5. Verify all running
ps aux | grep optimize

# 6. Close lid (if using external monitor) or lock screen

# 7. Next morning, check results
ls -lh optimization_results/

# 8. Review logs if needed
tail -50 logs/bull_put.log
```

---

## FAQ

**Q: Can I close the Terminal app?**
A: No, closing Terminal kills the process. Minimize it or use tmux to detach.

**Q: How do I stop a running optimization?**
A: Press Ctrl+C in the terminal. Partial results saved in checkpoints.

**Q: Can I run without external monitor?**
A: Yes, but you won't see progress. Use background mode with logging.

**Q: Will my Mac overheat?**
A: Optimization is CPU-intensive but normal. Ensure good ventilation.

**Q: How much disk space needed?**
A: Minimal. Results files are typically <1 MB each.

---

## Support

For issues or questions:
1. Check logs: `optimization.log` or `logs/`
2. Review checkpoint files for partial results
3. Verify caffeinate is running: `ps aux | grep caffeinate`
4. Check project documentation in `docs/`

---

## Summary

🔧 **Scripts:** Standalone optimization for each strategy
📊 **Output:** Clean progress bars + CSV results
💻 **Clamshell:** Use `caffeinate -i` to prevent sleep
⏱️ **Runtime:** 1-10 minutes depending on parameters
✅ **Best Practice:** `caffeinate -i python optimize_strategy.py`

**Ready to optimize!** 🚀
