# Optimization Scripts - Implementation Summary

## What Was Created

Created standalone Python scripts for parameter optimization with Mac clamshell mode support.

**Created Files:**
1. `optimize_bull_put_spread.py` - Bull Put Spread optimization
2. `optimize_bull_call_spread.py` - Bull Call Spread optimization
3. `optimize_call_calendar_spread.py` - Call Calendar Spread optimization
4. `README_OPTIMIZATION.md` - Quick start guide
5. `docs/OPTIMIZATION_SCRIPTS_GUIDE.md` - Comprehensive guide

---

## Key Features

### ✅ Clean Progress Bar Output
- Suppressed all verbose prints
- Only tqdm progress bar visible
- Fixed FutureWarning messages
- Professional terminal output

### ✅ Mac Clamshell Mode Support
- Built-in caffeinate detection and warnings
- Optimized for running with screen closed
- Prevents Mac sleep during long optimizations
- Works on battery (with warnings) or power

### ✅ Unattended Execution
- No user confirmation required
- Automatic checkpoint saves (every 10 combinations)
- Resume capability after interruption
- Background execution with logging

### ✅ Results Management
- Results saved to `optimization_results/` directory
- Checkpoints saved to `optimization_checkpoints/` directory
- CSV format for easy analysis
- Timestamp-based filenames

---

## Usage Examples

### Basic Usage

```bash
# Run optimization with sleep prevention
caffeinate -i python optimize_bull_put_spread.py
```

### Background with Logging

```bash
# Run in background, save output to log
caffeinate -i python optimize_bull_put_spread.py > optimization.log 2>&1 &

# Monitor progress
tail -f optimization.log
```

### Clamshell Mode (Screen Closed)

```bash
# 1. Connect to power
# 2. Run optimization
caffeinate -i python optimize_bull_put_spread.py

# 3. Close MacBook lid
# Script continues running
```

---

## Research Summary: Mac Sleep Prevention

### Problem
macOS can put Python scripts to sleep in several scenarios:
- **Idle sleep** - System has been inactive
- **Display sleep** - Screen turns off
- **Battery sleep** - On battery power with lid closed
- **App Nap** - macOS feature that throttles background apps

### Solution: caffeinate Command

Native macOS command that prevents sleep:

```bash
# Prevent idle sleep (recommended)
caffeinate -i python script.py

# Prevent system sleep (requires AC power)
caffeinate -s python script.py

# Combine flags
caffeinate -is python script.py
```

**Key Flags:**
- `-i` - Prevent idle sleep (works on battery)
- `-s` - Prevent system sleep (requires AC power)
- `-d` - Prevent display sleep
- `-m` - Prevent disk sleep

**Best Practice for Optimization:**
```bash
caffeinate -i python optimize_strategy.py
```

### Alternative Solutions Researched

1. **Amphetamine App** - Free app from Mac App Store
2. **pmset command** - System-wide sleep settings
3. **Subprocess in Python** - Embed caffeinate in script
4. **tmux/screen** - Terminal multiplexer for detachable sessions

**Recommendation:** Use `caffeinate -i` - simplest and most reliable.

---

## Script Architecture

### Common Structure

All scripts follow the same pattern:

```python
#!/usr/bin/env python3
"""Strategy optimization script with caffeinate support"""

# 1. Header and imports
import warnings
warnings.filterwarnings('ignore')  # Suppress warnings

# 2. Helper functions
def print_header():
    """Print formatted header"""

def load_configuration():
    """Load config.yaml"""

def load_data():
    """Load options and underlying data"""

def setup_optimizer(config, options_data, underlying_data):
    """Create optimizer with parameter ranges"""

def run_optimization(optimizer):
    """Execute optimization (no confirmation)"""

def save_results(results, optimizer):
    """Save to optimization_results/ directory"""

# 3. Main function
def main():
    """Orchestrate optimization workflow"""
    try:
        print_header()
        # Check for caffeinate
        # Load config and data
        # Setup optimizer
        # Run optimization
        # Save results
        return 0
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        return 1
    except Exception as e:
        # Print error and traceback
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

### Design Decisions

**1. No User Confirmation**
- `confirm=False` for unattended execution
- Allows overnight/background runs

**2. Clean Output**
- `warnings.filterwarnings('ignore')` suppresses pandas warnings
- `verbose=False` in backtester suppresses prints
- Only progress bar visible

**3. Caffeinate Detection**
- Checks if caffeinate is running
- Warns user if not (Mac may sleep)
- Educational - encourages best practices

**4. Error Handling**
- Try/except for graceful failures
- Ctrl+C handling with checkpoint info
- Traceback for debugging

**5. Results Organization**
- Separate directory: `optimization_results/`
- Timestamp filenames for uniqueness
- CSV format for portability

---

## Parameter Ranges

### Bull Put Spread
```python
optimizer.set_parameter_range('dte', min=30, max=45, step=5)           # 4 values
optimizer.set_parameter_range('short_delta', min=0.25, max=0.35, step=0.05)  # 3 values
optimizer.set_parameter_range('profit_target', min=0.40, max=0.60, step=0.10)  # 3 values
# Total: 4 × 3 × 3 = 36 combinations
```

### Bull Call Spread
```python
optimizer.set_parameter_range('dte', min=30, max=60, step=10)          # 4 values
optimizer.set_parameter_range('long_delta', min=0.55, max=0.70, step=0.05)   # 4 values
optimizer.set_parameter_range('short_delta', min=0.35, max=0.50, step=0.05)  # 4 values
optimizer.set_parameter_range('profit_target', min=0.50, max=0.75, step=0.25)  # 2 values
# Total: 4 × 4 × 4 × 2 = 128 combinations
```

### Call Calendar Spread
```python
optimizer.set_parameter_range('near_dte', min=20, max=35, step=5)       # 4 values
optimizer.set_parameter_range('far_dte', min=45, max=75, step=10)       # 4 values
optimizer.set_parameter_range('target_delta', min=0.45, max=0.55, step=0.05)  # 3 values
optimizer.set_parameter_range('profit_target', min=0.20, max=0.30, step=0.05)  # 3 values
# Total: 4 × 4 × 3 × 3 = 144 combinations
```

**Design Philosophy:**
- Start with coarse grid (larger steps)
- Identify promising regions
- Refine with finer grid around best results

---

## Testing Performed

### Unit Tests
✅ FutureWarning fix (`'M'` → `'ME'`)
✅ Verbose parameter in backtester
✅ Progress bar only output
✅ Caffeinate detection logic

### Integration Tests
✅ Full 36-combination optimization run
✅ Clean output verification (no repetitive prints)
✅ Results file creation
✅ Checkpoint file creation

### Test Results
```
Optimizing BullPutSpread:  28%|████      | 10/36 [00:17<00:44, 1.71s/combo] 💾
Optimizing BullPutSpread:  56%|████████  | 20/36 [00:33<00:24, 1.56s/combo] 💾
Optimizing BullPutSpread:  83%|████████▎ | 30/36 [00:48<00:09, 1.59s/combo] 💾
Optimizing BullPutSpread: 100%|██████████| 36/36 [00:58<00:00, 1.63s/combo] ✓
```

**Verification:**
- ✅ NO "Running backtest for..." messages
- ✅ NO FutureWarning messages
- ✅ Only progress bar visible
- ✅ Results saved correctly

---

## Files Modified (From Previous Work)

### Core Fixes
1. **src/analysis/metrics.py** - Fixed FutureWarning
2. **src/backtester/optopsy_wrapper.py** - Added verbose parameter
3. **src/optimization/parameter_optimizer.py** - Set verbose=False

### Bug Fix (Separate Issue)
4. **src/optimization/parameter_optimizer.py** - Fixed config passing bug

---

## Documentation Created

### User Documentation
1. **README_OPTIMIZATION.md** - Quick start guide (concise)
2. **docs/OPTIMIZATION_SCRIPTS_GUIDE.md** - Comprehensive guide (detailed)

### Technical Documentation
3. **docs/CLEAN_OUTPUT_VERIFICATION.md** - Output cleanup verification
4. **docs/BUG_FIX_OPTIMIZER_PARAMETERS.md** - Config passing bug fix
5. **docs/OPTIMIZATION_SCRIPTS_SUMMARY.md** - This file

---

## Performance Characteristics

### Typical Runtimes
| Strategy | Combinations | Runtime | CPU |
|----------|-------------|---------|-----|
| Bull Put | 36 | 1-2 min | Medium |
| Bull Call | 128 | 3-5 min | Medium |
| Calendar | 144 | 5-10 min | Med-High |

### Factors Affecting Runtime
- Data size (number of trading days)
- Parameter combinations (exponential growth)
- Mac performance (M1/M2 faster than Intel)
- Background processes

### Optimization Tips
- Reduce combinations: use larger step sizes
- Smaller date ranges for testing
- Close unnecessary applications
- Run overnight for large grids

---

## Best Practices Summary

### ✅ DO
- Use `caffeinate -i` for all optimizations
- Keep Mac plugged into power for clamshell mode
- Start with coarse parameter grids
- Save checkpoints frequently (every 10)
- Run overnight for large optimizations
- Monitor first run to verify setup

### ❌ DON'T
- Run on battery in clamshell mode
- Close Terminal window
- Set checkpoint_every too low (<5)
- Test too many parameters (exponential)
- Ignore caffeinate warnings

---

## Future Enhancements

### Potential Improvements
1. **Distributed optimization** - Run on multiple Macs
2. **GPU acceleration** - For very large grids
3. **Adaptive grids** - Smart parameter space exploration
4. **Real-time visualization** - Web dashboard for progress
5. **Email notifications** - When optimization completes
6. **Cloud execution** - AWS/GCP for unlimited runtime

### Low-Hanging Fruit
1. Add `--resume` command-line flag
2. Add `--parameters` flag for quick range changes
3. JSON config file for parameter ranges
4. Parallel strategy optimization (safe on multi-core)

---

## Troubleshooting Guide

### Mac Goes to Sleep
**Check:**
1. Using caffeinate? `ps aux | grep caffeinate`
2. Plugged into power? (required for clamshell)
3. Energy Saver settings allowing sleep?

**Solution:** `caffeinate -is python script.py`

### No Progress Bar
**Check:**
1. tqdm installed? `pip list | grep tqdm`

**Solution:** `pip install tqdm`

### Script Slow at Night
**Cause:** App Nap feature
**Solution:** Use caffeinate (disables App Nap)

### Results File Missing
**Check:**
1. Script completed? `ps aux | grep optimize`
2. Check checkpoints: `ls optimization_checkpoints/`

**Solution:** Script may have been interrupted

---

## Summary

### What We Accomplished
✅ Created 3 standalone optimization scripts
✅ Added Mac clamshell mode support
✅ Clean progress bar output only
✅ Comprehensive documentation
✅ Tested and verified working

### Key Benefits
🚀 **Unattended execution** - Run overnight with confidence
💻 **Clamshell mode** - Close lid, script continues
📊 **Clean output** - Professional progress bars
💾 **Auto-save** - Never lose progress
📝 **Well documented** - Easy to use and customize

### Ready to Use
```bash
caffeinate -i python optimize_bull_put_spread.py
```

**Scripts are production-ready!** 🎉
