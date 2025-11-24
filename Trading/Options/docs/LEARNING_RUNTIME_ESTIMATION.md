# Learning Guide: Building Runtime Estimation Feature

## Educational Overview

This document explains **the complete problem-solving process** used to add runtime estimation to the parameter optimizer. Great for learning how to approach similar problems!

---

## The Problem-Solving Journey

### Step 1: Understand the Problem

**User's complaint:**
> "The optimization code has been running extremely long which is to be expected given the combinations."

**Why is this a problem?**
- User starts optimization, then waits... 10 minutes? 2 hours? 10 hours? Who knows!
- No way to make informed decision about whether to proceed
- Can't plan their time (grab coffee vs. go to bed)
- Frustrating user experience

**What would solve it?**
- Show estimated runtime BEFORE starting
- Let user decide if they want to wait that long
- Give them the option to cancel and adjust parameters

---

### Step 2: Investigate Existing Code

**I asked myself:** "Does the code already have pieces I can use?"

**Found in `parameter_optimizer.py`:**

```python
def get_total_combinations(self) -> int:
    """Calculate total number of parameter combinations to test."""
    if not self.parameter_ranges:
        return 0

    total = 1
    for param_info in self.parameter_ranges.values():
        total *= len(param_info['values'])

    return total
```

✅ **Great!** We already know the total number of combinations.

**What's missing?**
- ❌ No idea how long each backtest takes
- ❌ No runtime estimation
- ❌ No user confirmation prompt

---

### Step 3: Design the Solution

**Core insight:** If we time a few sample backtests, we can extrapolate to estimate total time.

**Algorithm:**
```
1. Calculate total combinations (already have this!)
2. Randomly select 3 sample combinations
3. Time each sample backtest
4. Calculate: avg_time_per_backtest = mean(sample_times)
5. Estimate: total_time = avg_time × total_combinations
6. Display estimate to user
7. Ask: "Do you want to proceed? (y/n)"
8. If yes → run optimization
   If no → raise exception and stop
```

**Key decisions made:**
- **How many samples?** → 3 (balance between accuracy and speed)
- **Random or sequential?** → Random (avoid bias from parameter order)
- **What if samples fail?** → Still show time, warn user
- **Skip confirmation option?** → Yes, add `confirm=False` parameter for automation

---

### Step 4: Implementation

#### 4.1 Add Required Imports

```python
import time      # For timing backtests
import random    # For random sampling
```

**Why these?**
- `time.time()`: Get current timestamp in seconds
- `random.sample()`: Pick random combinations without replacement

#### 4.2 Create Helper Method

```python
def _estimate_runtime_and_confirm(
    self,
    param_names: List[str],
    param_values_lists: List[List],
    total_combinations: int,
    num_samples: int = 3
) -> bool:
    """
    Run sample backtests to estimate total runtime and ask user for confirmation.

    Returns:
        True if user confirms, False otherwise
    """
```

**Why a separate method?**
- **Single Responsibility Principle**: One method = one job
- **Testability**: Can test estimation logic independently
- **Readability**: Keeps `run_optimization()` clean

**What it does:**

1. **Generate all possible combinations:**
   ```python
   all_combinations = list(product(*param_values_lists))
   ```

2. **Sample randomly:**
   ```python
   sample_size = min(num_samples, len(all_combinations))
   sample_combinations = random.sample(all_combinations, sample_size)
   ```

3. **Time each sample:**
   ```python
   for combination in sample_combinations:
       params = dict(zip(param_names, combination))

       start_time = time.time()
       self._run_single_backtest(params, verbose=False)
       elapsed = time.time() - start_time

       sample_times.append(elapsed)
   ```

4. **Calculate statistics:**
   ```python
   avg_time = np.mean(sample_times)
   min_time = np.min(sample_times)
   max_time = np.max(sample_times)

   estimated_total_seconds = avg_time * total_combinations
   ```

5. **Format human-readable time:**
   ```python
   def format_time(seconds):
       if seconds < 60:
           return f"{seconds:.0f} seconds"
       elif seconds < 3600:
           return f"{seconds / 60:.1f} minutes"
       else:
           return f"{seconds / 3600:.1f} hours"
   ```

6. **Get user input:**
   ```python
   response = input("Do you want to proceed with optimization? (y/n): ")
   return response.strip().lower() == 'y'
   ```

**Why `input()` works in Jupyter:**
- Jupyter notebooks support interactive `input()` prompts!
- User can type 'y' or 'n' and press Enter
- Execution pauses until user responds

#### 4.3 Integrate into `run_optimization()`

**Before optimization loop:**
```python
if confirm:
    user_confirmed = self._estimate_runtime_and_confirm(
        param_names=param_names,
        param_values_lists=param_values_lists,
        total_combinations=total_combinations,
        num_samples=num_samples
    )
    if not user_confirmed:
        raise RuntimeError("Optimization cancelled by user")
```

**After optimization completes:**
```python
actual_runtime = time.time() - start_time
print(f"Actual runtime: {format_time(actual_runtime)}")
print(f"Average time per backtest: {actual_runtime / len(results):.2f} seconds")
```

---

### Step 5: Testing & Refinement

**Edge cases handled:**

1. **All samples fail:**
   ```python
   if not sample_times:
       print("⚠️  All sample backtests failed. Cannot estimate runtime.")
       response = input("Continue anyway? (y/n): ")
       return response == 'y'
   ```

2. **Very few combinations:**
   ```python
   sample_size = min(num_samples, len(all_combinations))
   ```
   If only 2 combinations exist, only sample 2 (not 3).

3. **Automated runs (no user interaction):**
   ```python
   results = optimizer.run_optimization(confirm=False)  # Skip prompt
   ```

---

## How It Works: Real Example

### Setup
```python
optimizer.set_parameter_range('dte', min=30, max=45, step=5)           # 4 values
optimizer.set_parameter_range('short_delta', min=0.25, max=0.35, step=0.05)  # 3 values
optimizer.set_parameter_range('profit_target', min=0.40, max=0.60, step=0.10)  # 3 values
# Total: 4 × 3 × 3 = 36 combinations
```

### Output You'll See

```
============================================================
PARAMETER OPTIMIZATION: VERTICAL SPREADS
============================================================
Strategy: BullPutSpread
Parameters to optimize: ['dte', 'short_delta', 'profit_target']
Total combinations: 36
Optimization metric: sharpe_ratio
============================================================

============================================================
ESTIMATING RUNTIME...
============================================================
Running 3 sample backtests to estimate time...
  Sample 1/3: Testing {'dte': 35, 'short_delta': 0.30, 'profit_target': 0.50}
    ✓ Completed in 8.42 seconds
  Sample 2/3: Testing {'dte': 40, 'short_delta': 0.25, 'profit_target': 0.60}
    ✓ Completed in 9.13 seconds
  Sample 3/3: Testing {'dte': 30, 'short_delta': 0.35, 'profit_target': 0.40}
    ✓ Completed in 8.71 seconds

============================================================
RUNTIME ESTIMATE
============================================================
Sample backtests: 3
Average time per backtest: 8.75 seconds
Time range: 8.42s - 9.13s

Total combinations: 36

Estimated total runtime:
  Best case:  5.0 minutes
  Average:    5.3 minutes
  Worst case: 5.5 minutes
============================================================

Do you want to proceed with optimization? (y/n): █
```

**User types 'y' and presses Enter:**

```
✓ Starting optimization...

Progress: 7/36 (19.4%)
Progress: 14/36 (38.9%)
Progress: 21/36 (58.3%)
Progress: 28/36 (77.8%)
Progress: 35/36 (97.2%)

============================================================
OPTIMIZATION COMPLETE
============================================================
Total combinations tested: 36
Successful backtests: 36
Failed backtests: 0

Actual runtime: 5.2 minutes
Average time per backtest: 8.67 seconds

Best sharpe_ratio: 1.8734

Best parameters:
  dte: 35
  short_delta: 0.30
  profit_target: 0.50
============================================================
```

---

## Key Python Concepts Used

### 1. **Timing with `time.time()`**

```python
start = time.time()
# ... do something ...
elapsed = time.time() - start
print(f"Took {elapsed:.2f} seconds")
```

**How it works:**
- `time.time()` returns current time as float (seconds since epoch)
- Subtract start from end to get duration
- Precise to microseconds!

### 2. **Random Sampling**

```python
import random

all_items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
sample = random.sample(all_items, 3)  # Get 3 random items
# Example: [7, 2, 9]
```

**Why not `random.choice()` in a loop?**
- `sample()` guarantees no duplicates
- More efficient for multiple selections
- Single call vs. multiple

### 3. **User Input in Jupyter**

```python
response = input("Continue? (y/n): ")
# Execution pauses here until user types and presses Enter
if response.strip().lower() == 'y':
    print("Continuing...")
```

**Gotchas:**
- `input()` returns a string (even if user types numbers!)
- Always use `.strip()` to remove whitespace
- Use `.lower()` to handle "Y", "y", "YES", etc.

### 4. **Exception Raising for Control Flow**

```python
if not user_confirmed:
    raise RuntimeError("Optimization cancelled by user")
```

**Why raise an exception?**
- Immediately stops execution
- Clear error message
- Caller can catch it if needed with try/except

### 5. **Nested Function for Formatting**

```python
def run_optimization(self):
    # ...

    def format_time(seconds):
        """Helper function only used in this scope."""
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            return f"{seconds / 60:.1f} minutes"
        else:
            return f"{seconds / 3600:.1f} hours"

    print(format_time(actual_runtime))
```

**Why nested?**
- Keeps namespace clean
- Only used in one place
- Has access to outer function's variables

---

## Design Patterns Used

### 1. **Sampling for Estimation**
- Statistical technique: estimate population from sample
- Trade-off: 3 samples vs. 100% accuracy
- Good enough for user decision-making

### 2. **Progressive Disclosure**
- Don't overwhelm user with details upfront
- Show estimate first, details later
- User opts-in to long operations

### 3. **Graceful Degradation**
- If samples fail, still offer to continue
- If estimate unavailable, warn but don't crash
- Always give user control

### 4. **Separation of Concerns**
- Estimation logic separate from optimization logic
- Can test/modify independently
- Single Responsibility Principle

---

## Common Pitfalls Avoided

### ❌ Wrong: Estimate before getting data
```python
# BAD: Guess based on nothing
estimated_time = total_combinations * 10  # Random guess!
```

### ✅ Right: Measure actual performance
```python
# GOOD: Sample and measure
for sample in samples:
    start = time.time()
    run_backtest(sample)
    sample_times.append(time.time() - start)
avg_time = mean(sample_times)
```

### ❌ Wrong: Block without confirmation
```python
# BAD: Just start running
for combo in all_combinations:
    run_backtest(combo)  # Hope user is okay waiting hours!
```

### ✅ Right: Ask first
```python
# GOOD: Informed consent
show_estimate(estimated_time)
if user_confirms():
    run_optimization()
```

### ❌ Wrong: Assume `input()` won't work
```python
# BAD: "Jupyter doesn't support input()"
# Actually, it does!
```

### ✅ Right: Test in actual environment
```python
# GOOD: Try it and see
response = input("Test: ")  # Works in Jupyter!
```

---

## Extension Ideas

Want to practice? Try adding these features:

1. **Progress bar:**
   ```python
   from tqdm import tqdm
   for combo in tqdm(combinations):
       run_backtest(combo)
   ```

2. **Save/resume optimization:**
   - Save results after each combination
   - Resume from checkpoint if interrupted

3. **Adaptive sampling:**
   - If first samples are fast, use fewer samples
   - If slow, use more samples for better estimate

4. **Parallel processing:**
   - Run multiple backtests simultaneously
   - Adjust time estimate for parallelization

5. **Email notification:**
   - Send email when optimization completes
   - Include summary of best parameters

---

## Summary: Problem-Solving Process

1. **Understand the problem** - User has no idea how long optimization will take
2. **Investigate existing code** - Found `get_total_combinations()` already exists
3. **Design solution** - Sample → measure → estimate → confirm
4. **Implement incrementally** - Add imports → create helper → integrate → test
5. **Handle edge cases** - Failed samples, automated runs, small datasets
6. **Document** - Write this guide so others can learn!

**Key takeaway:** Always break down big problems into small, testable pieces. This wasn't one massive change—it was a series of small, logical steps.

---

## Try It Yourself!

Run the updated notebook cells (16 and 21) and see the runtime estimation in action. Type 'n' to cancel if the estimate is too long, then adjust your parameters to reduce combinations!

**Experiment:**
- Try with just 2 parameters (4 × 3 = 12 combinations) - should be fast
- Try with 5 parameters (4 × 3 × 3 × 5 × 4 = 720 combinations) - see the estimate jump!
- Type 'n' to cancel and appreciate how useful this feature is!
