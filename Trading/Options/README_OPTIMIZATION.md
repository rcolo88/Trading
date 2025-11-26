# Strategy Parameter Optimization - Quick Start

## 🚀 Quick Usage

### Run Single Strategy Optimization

```bash
# Best practice - prevents Mac sleep during optimization
caffeinate -i python optimize_bull_put_spread.py
```

**Available Scripts:**
- `optimize_bull_put_spread.py` - Bull Put Spread
- `optimize_bull_call_spread.py` - Bull Call Spread
- `optimize_call_calendar_spread.py` - Call Calendar Spread

---

## 📋 Prerequisites

✅ Data generated: `python generate_synthetic_data.py`
✅ Python packages installed: `pip install -r requirements.txt`
✅ Mac plugged into power (for clamshell mode)

---

## 🔧 Basic Commands

### Run Optimization (Recommended)

```bash
# Prevents Mac from sleeping during optimization
caffeinate -i python optimize_bull_put_spread.py
```

### Run in Background with Logging

```bash
# Run in background, save output to log file
caffeinate -i python optimize_bull_put_spread.py > optimization.log 2>&1 &

# Monitor progress
tail -f optimization.log

# Check if still running
ps aux | grep optimize
```

### Using Clamshell Mode (Screen Closed)

```bash
# 1. Connect to power (required!)
# 2. Optional: Connect external monitor
# 3. Run optimization
caffeinate -i python optimize_bull_put_spread.py

# 4. Close MacBook lid - script continues running
```

---

## 📊 Output

**Results Location:**
```
optimization_results/
  └── BullPutSpread_20241125_103116.csv
```

**Checkpoint Location** (for resume):
```
optimization_checkpoints/
  └── BullPutSpread_20241125_103030.csv
```

**Example Output:**
```
============================================================
OPTIMIZATION COMPLETE
============================================================
Results saved to: optimization_results/BullPutSpread_20241125_103116.csv
Total combinations tested: 36

TOP 5 PARAMETER COMBINATIONS:
dte  short_delta  profit_target  sharpe_ratio  total_return_pct
 35         0.35            0.6      0.390330          6.141601
 35         0.35            0.4      0.390330          6.141601
 35         0.30            0.5      0.150000          2.500000
...
============================================================
```

---

## ⚙️ Customization

### Change Parameter Ranges

Edit the script's `setup_optimizer()` function:

```python
# In optimize_bull_put_spread.py
optimizer.set_parameter_range('dte', min=30, max=45, step=5)
optimizer.set_parameter_range('short_delta', min=0.25, max=0.35, step=0.05)
optimizer.set_parameter_range('profit_target', min=0.40, max=0.60, step=0.10)
```

### Change Optimization Metric

Default is `sharpe_ratio`. Can change to:
- `total_return_pct`
- `calmar_ratio`
- `sortino_ratio`
- `profit_factor`

Edit in `run_optimization()` function.

---

## 🛑 Troubleshooting

### Mac Goes to Sleep
**Solution:** Ensure using `caffeinate -i` and plugged into power

### No Progress Bar
**Solution:** Install tqdm: `pip install tqdm`

### Script Interrupted
**Solution:** Resume from checkpoint (see full guide)

---

## 📚 Full Documentation

For comprehensive guide including:
- Clamshell mode best practices
- Resume from checkpoint
- Running multiple optimizations in parallel
- Advanced tmux usage
- Performance tuning

**See:** [docs/OPTIMIZATION_SCRIPTS_GUIDE.md](docs/OPTIMIZATION_SCRIPTS_GUIDE.md)

---

## ⏱️ Estimated Runtimes

| Strategy | Combinations | Runtime |
|----------|-------------|---------|
| Bull Put Spread | 36 | 1-2 min |
| Bull Call Spread | 128 | 3-5 min |
| Call Calendar | 144 | 5-10 min |

*Runtimes vary based on data size and Mac performance*

---

## 💡 Tips

✅ Start with small parameter ranges, expand later
✅ Use `caffeinate -i` to prevent sleep
✅ Run overnight for large optimizations
✅ Save checkpoint every 10 combinations
✅ Keep Mac plugged into power

❌ Don't close Terminal window (kills process)
❌ Don't run on battery in clamshell mode
❌ Don't test too many parameters at once

---

## 🎯 Example Workflow

**Optimize all strategies overnight:**

```bash
# Terminal 1: Bull Put
caffeinate -i python optimize_bull_put_spread.py > logs/bull_put.log 2>&1 &

# Terminal 2: Bull Call
caffeinate -i python optimize_bull_call_spread.py > logs/bull_call.log 2>&1 &

# Terminal 3: Calendar
caffeinate -i python optimize_call_calendar_spread.py > logs/calendar.log 2>&1 &

# Verify running
ps aux | grep optimize

# Next morning
ls -lh optimization_results/
```

---

## 📞 Questions?

- Review logs: `tail -50 optimization.log`
- Check checkpoints: `ls optimization_checkpoints/`
- See full guide: `docs/OPTIMIZATION_SCRIPTS_GUIDE.md`

---

**Ready to optimize! Run:** `caffeinate -i python optimize_bull_put_spread.py` 🚀
