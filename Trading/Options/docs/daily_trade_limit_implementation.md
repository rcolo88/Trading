# Daily Trade Limit Implementation

## Overview

The backtesting system now enforces a **maximum of one trade per day per strategy** rule, with a goal to enter at least one trade per day when position sizing allows.

## Implementation Details

### Backtest Logic

**Rule**: Maximum **ONE trade per day** per strategy
**Goal**: Try to enter at least **ONE trade per day** if:
- Position sizing allows (current_positions < max_positions)
- Entry signal conditions are met

### Code Changes

#### File: `src/backtester/optopsy_wrapper.py`

**1. Daily Trade Tracking** (Lines 163-169)
```python
# Daily trade tracking for enforcing one trade per day limit
trades_entered_today = 0

# Main backtest loop
for current_date in trading_dates:
    # Reset daily trade counter at start of each day
    trades_entered_today = 0
```

**2. Entry Logic with Daily Limit** (Lines 255-264)
```python
# Check for new entry signals
# BACKTEST RULE: Maximum one trade per day per strategy
# GOAL: Try to enter at least one trade per day if position sizing allows
max_positions = self.config.get('position_sizing', {}).get('max_positions', 5)
current_positions = len(strategy.get_open_positions())

# Only attempt entry if:
# 1. Haven't entered a trade today (trades_entered_today < 1)
# 2. Have room for more positions (current_positions < max_positions)
if trades_entered_today < 1 and current_positions < max_positions:
    # Generate entry signal...
```

**3. Increment Counter After Entry** (Lines 344-345)
```python
strategy.positions.append(position)

# Increment daily trade counter (enforce max one trade per day)
trades_entered_today += 1
```

**4. Daily Entry Logging** (Lines 351-362)
```python
# Track daily entry attempts for reporting
self.daily_entry_log.append({
    'date': current_date,
    'trades_entered': trades_entered_today,
    'attempted_entry': (trades_entered_today < 1 and current_positions < max_positions),
    'entry_blocked_reason': (
        'max_positions_reached' if current_positions >= max_positions
        else 'already_entered_today' if trades_entered_today >= 1
        else 'no_entry_signal' if trades_entered_today == 0
        else 'entered'
    )
})
```

**5. Statistics Compilation** (Lines 587-617)
```python
# Daily entry statistics
daily_log_df = pd.DataFrame(self.daily_entry_log)
total_trading_days = len(daily_log_df)
days_with_entry = (daily_log_df['trades_entered'] > 0).sum()
days_no_entry = total_trading_days - days_with_entry
days_blocked_by_max_positions = (daily_log_df['entry_blocked_reason'] == 'max_positions_reached').sum()
days_no_signal = (daily_log_df['entry_blocked_reason'] == 'no_entry_signal').sum()
daily_entry_rate = (days_with_entry / total_trading_days * 100) if total_trading_days > 0 else 0
```

## Results Reporting

### New Statistics Available

Backtest results now include:
- `total_trading_days`: Total business days in backtest period
- `days_with_entry`: Number of days a trade was entered
- `days_no_entry`: Number of days no trade was entered
- `days_blocked_by_max_positions`: Days entry blocked due to max positions limit
- `days_no_signal`: Days where entry signal conditions weren't met
- `daily_entry_rate_pct`: Percentage of days with successful entry
- `daily_entry_log`: Detailed DataFrame with daily entry tracking

### Print Output Example

```
============================================================
BACKTEST RESULTS: Call Calendar Spread
============================================================
Initial Capital:    $10,000.00
Final Value:        $12,500.00
Total Return:       25.00%
Max Drawdown:       -5.50%
Sharpe Ratio:       1.45

Total Trades:       45
Win Rate:           68.89%
Avg Win:            $125.50
Avg Loss:           -$85.25
Profit Factor:      2.15

--- Daily Entry Statistics ---
Total Trading Days:       252
Days with Entry:          45 (17.9%)
Days No Entry:            207
  - No entry signal:      180
  - Max positions reached: 27
============================================================
```

## Behavior Scenarios

### Scenario 1: Normal Daily Entry
```
Day 1:
- Current positions: 3
- Max positions: 5
- Trades entered today: 0
- Entry signal: YES
→ ENTER TRADE ✅
→ trades_entered_today = 1
```

### Scenario 2: Already Entered Today
```
Day 1 (continued after Scenario 1):
- Current positions: 4
- Max positions: 5
- Trades entered today: 1
- Entry signal: YES
→ DO NOT ENTER (already entered today) ❌
→ Reason: 'already_entered_today'
```

### Scenario 3: Max Positions Reached
```
Day 2:
- Current positions: 5
- Max positions: 5
- Trades entered today: 0
- Entry signal: YES
→ DO NOT ENTER (max positions reached) ❌
→ Reason: 'max_positions_reached'
```

### Scenario 4: No Entry Signal
```
Day 3:
- Current positions: 3
- Max positions: 5
- Trades entered today: 0
- Entry signal: NO (VIX too high, no valid DTE, etc.)
→ DO NOT ENTER (no signal) ❌
→ Reason: 'no_entry_signal'
```

## Daily Entry Rate Interpretation

### Good Daily Entry Rate
- **40-60%**: Excellent - strategy finds entries frequently while being selective
- **20-40%**: Good - balanced approach, not too aggressive
- **10-20%**: Acceptable - conservative or requires specific conditions

### Low Daily Entry Rate (< 10%)
Possible causes:
1. **Too restrictive entry criteria**
   - VIX filters too narrow
   - Delta targets too specific
   - DTE ranges too limited

2. **Position sizing constraints**
   - `max_positions` too low
   - Holding positions too long (can't enter new ones)

3. **Market conditions**
   - Few trading days match strategy requirements
   - Limited options availability at target strikes/DTEs

### High Daily Entry Rate (> 70%)
Possible concerns:
1. **Entry criteria too loose**
   - May be over-trading
   - Not selective enough about market conditions

2. **Position exits too fast**
   - Freeing up positions quickly for new entries
   - Check if stop losses are too tight

## Position Sizing Impact

The daily entry limit works together with position sizing:

```yaml
position_sizing:
  max_positions: 5              # Can hold up to 5 positions
  max_positions_per_strategy: 3 # (not yet implemented)
```

**Example**:
- Max positions = 5
- Currently holding: 5 positions
- Daily entry rate will drop because: `current_positions >= max_positions`
- Fix: Either increase `max_positions` or adjust exit criteria to close positions faster

## Configuration Options

Currently, the "one trade per day" limit is **hardcoded** in the backtest logic. Future enhancements could add:

```yaml
backtest:
  max_trades_per_day: 1  # Configurable limit
  min_days_between_trades: 0  # Enforce spacing (not implemented)
  allow_multiple_entries_if_signal_strong: false  # Override logic (not implemented)
```

## Analyzing Daily Entry Log

You can analyze the detailed daily entry log:

```python
# After running backtest
results = backtester.run_backtest(...)

# Access daily entry log
daily_log = results['daily_entry_log']

# Find days where signal was generated but no entry
no_entry_with_room = daily_log[
    (daily_log['trades_entered'] == 0) &
    (daily_log['entry_blocked_reason'] == 'no_entry_signal') &
    (daily_log['attempted_entry'] == True)
]

print(f"Days with room for entry but no signal: {len(no_entry_with_room)}")

# Analyze patterns
import matplotlib.pyplot as plt
daily_log['date'] = pd.to_datetime(daily_log['date'])
daily_log.set_index('date')['trades_entered'].plot(kind='bar', figsize=(15, 4))
plt.title('Daily Entry Pattern')
plt.ylabel('Trades Entered')
plt.show()
```

## Comparison: Before vs After Implementation

### Before (Implicit Limit)
- `generate_entry_signal()` called once per day
- **Effectively** one trade per day, but not documented
- No tracking of why entries didn't happen
- No statistics on daily entry rate

### After (Explicit Limit)
- ✅ Explicit `trades_entered_today < 1` check
- ✅ Clear documentation in code comments
- ✅ Tracking of all entry attempts and blocking reasons
- ✅ Comprehensive daily entry statistics
- ✅ Can easily modify to allow multiple entries if needed

## Testing

To verify the implementation:

```python
# Run a short backtest
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.strategies.calendar_spreads import CallCalendarSpread

results = backtester.run_backtest(...)

# Check daily entry statistics
print(f"Total trading days: {results['total_trading_days']}")
print(f"Days with entry: {results['days_with_entry']}")
print(f"Daily entry rate: {results['daily_entry_rate_pct']:.1f}%")

# Verify max one trade per day
daily_log = results['daily_entry_log']
max_trades_any_day = daily_log['trades_entered'].max()
assert max_trades_any_day <= 1, "ERROR: Multiple trades entered on single day!"
print("✅ Verification passed: Max one trade per day enforced")
```

## Future Enhancements

1. **Configurable daily limit**
   - Allow users to set `max_trades_per_day` in config

2. **Multiple strategies support**
   - Track daily entries per strategy when running multiple strategies
   - Enforce `max_trades_per_day_per_strategy`

3. **Priority system**
   - If multiple strategies want to enter on same day, use priority
   - Best signal quality enters first

4. **Adaptive entry**
   - Allow 2 trades per day if certain conditions met (e.g., volatility spike)
   - "Opportunistic" override for exceptional market conditions

---

**Status**: ✅ Implemented and ready for testing

**Date**: 2025-11-12

**Files Modified**:
- `src/backtester/optopsy_wrapper.py` (Lines 121, 163-169, 255-264, 344-345, 351-375, 587-617, 622-643)
