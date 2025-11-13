# Parameter Tolerance Analysis

## Summary

The ParameterOptimizer and strategy implementations have **built-in tolerance mechanisms** for handling inexact parameter matches. However, there's a **mismatch** between calendar spread parameters in the optimizer vs actual strategy implementation.

---

## Tolerance Mechanisms by Parameter Type

### 1. **DTE (Days to Expiration)**

#### Vertical Spreads ✅
**Implementation**: [vertical_spreads.py:117-123](../src/strategies/vertical_spreads.py#L117-L123)

```python
dte_min = self.entry_config.get('dte_min', 30)
dte_max = self.entry_config.get('dte_max', 45)

valid_options = options_data[
    (options_data['dte'] >= dte_min) &
    (options_data['dte'] <= dte_max)
].copy()
```

**Tolerance**: Uses **range-based filtering** with `dte_min` and `dte_max`
- Optimizer sets: `dte_min=30, dte_max=45`
- Strategy filters: All options with DTE between 30-45 days (inclusive)
- **Works correctly** ✅

---

#### Calendar Spreads ⚠️ **ISSUE FOUND**
**Implementation**: [calendar_spreads.py:185-199](../src/strategies/calendar_spreads.py#L185-L199)

```python
near_dte_target = self.entry_config.get('near_dte', 30)
far_dte_target = self.entry_config.get('far_dte', 60)
dte_tolerance = self.entry_config.get('dte_tolerance', 5)

near_options = options_data[
    (options_data['dte'] >= near_dte_target - dte_tolerance) &
    (options_data['dte'] <= near_dte_target + dte_tolerance)
].copy()
```

**Current Tolerance**: Uses **center point + tolerance** approach
- Config sets: `near_dte=30, dte_tolerance=5`
- Strategy filters: DTE between 25-35 days (30 ± 5)

**Optimizer Expects**: `near_dte_min` and `near_dte_max` as separate parameters
- Optimizer definition: [parameter_optimizer.py:55](../src/optimization/parameter_optimizer.py#L55)
  ```python
  CALENDAR_PARAMETERS = {
      'entry': ['near_dte_min', 'near_dte_max', 'far_dte_min', 'far_dte_max', ...]
  }
  ```

**Problem**: ⚠️ **Mismatch**
- Optimizer tries to set: `near_dte_min=5, near_dte_max=15`
- Strategy expects: `near_dte=<single value>, dte_tolerance=<single value>`
- **This won't work as intended** ❌

---

### 2. **Delta (Option Greeks)**

#### Implementation (Both Spreads) ✅
**File**: [calendar_spreads.py:83-114](../src/strategies/calendar_spreads.py#L83-L114)

```python
def _find_strike_by_delta(
    self,
    options_chain: pd.DataFrame,
    target_delta: float,
    option_type: str,
    tolerance: float = 0.05  # ← Default tolerance: ±0.05
) -> Optional[float]:
    """Find strike price closest to target delta."""

    filtered = options_chain[options_chain['option_type'] == option_type].copy()

    # Find closest delta
    filtered['delta_diff'] = abs(abs(filtered['delta']) - abs(target_delta))
    closest = filtered.loc[filtered['delta_diff'].idxmin()]

    if closest['delta_diff'] <= tolerance:  # ← Check within tolerance
        return closest['strike']

    return None
```

**Tolerance**: **±0.05 delta tolerance** (hardcoded)
- Optimizer sets: `target_delta=0.50`
- Strategy searches for: Closest option with delta within [0.45, 0.55]
- If no option within ±0.05, returns `None` (no trade entry)
- **Works correctly** ✅

**Examples**:
| Optimizer Sets | Available Deltas | Match Found? | Strike Selected |
|----------------|------------------|--------------|-----------------|
| `delta=0.50` | [0.48, 0.52, 0.55] | ✅ Yes | 0.48 delta strike |
| `delta=0.30` | [0.28, 0.31, 0.35] | ✅ Yes | 0.31 delta strike |
| `delta=0.50` | [0.40, 0.44, 0.60] | ❌ No | None (no entry) |

---

### 3. **Profit Target / Stop Loss**

#### Implementation (All Strategies) ✅
**File**: [calendar_spreads.py:426-448](../src/strategies/calendar_spreads.py#L426-L448)

```python
profit_target_pct = self.exit_config.get('profit_target', 0.25)
profit_pct = (current_spread_price - position.entry_price) / position.entry_price

if profit_pct >= profit_target_pct:  # ← Exact comparison (>=)
    return Signal(..., exit_reason=f"Profit target reached: {profit_pct:.1%}")
```

**Tolerance**: **No tolerance needed** - uses `>=` comparison
- Optimizer sets: `profit_target=0.25`
- Strategy exits when: `profit_pct >= 0.25`
- Any value ≥ 25% triggers exit (could be 25.001%, 30%, 50%, etc.)
- **Works correctly** ✅

---

### 4. **VIX Filters**

#### Implementation (Both Spreads) ✅
**File**: [calendar_spreads.py:207-215](../src/strategies/calendar_spreads.py#L207-L215)

```python
vix_max = self.entry_config.get('vix_max', float('inf'))
vix_min = self.entry_config.get('vix_min', 0)

if vix and (vix > vix_max or vix < vix_min):  # ← Range check
    return None  # VIX outside strategy's acceptable range
```

**Tolerance**: **No tolerance** - exact range boundaries
- Optimizer sets: `vix_min=15, vix_max=30`
- Strategy filters: Only enters when `15 <= VIX <= 30`
- VIX = 14.99 → **rejected**
- VIX = 15.01 → **accepted**
- **Works correctly** ✅

---

## Issue Summary

### ❌ **Calendar Spread DTE Parameters - Mismatch**

**Problem**:
- **Optimizer expects**: `near_dte_min`, `near_dte_max`, `far_dte_min`, `far_dte_max`
- **Strategy expects**: `near_dte`, `far_dte`, `dte_tolerance`

**Impact**:
When optimizer sets `near_dte_min=5` and `near_dte_max=15`:
- These parameters are written to config
- Strategy looks for `near_dte` parameter (not found, uses default 30)
- Strategy uses `dte_tolerance=5` (default)
- **Result**: Filters 25-35 DTE instead of 5-15 DTE ❌

**Example Failure**:
```python
# Optimizer sets these parameters
optimizer.set_parameter_range('near_dte_min', min=5, max=10)
optimizer.set_parameter_range('near_dte_max', min=10, max=15)

# After optimization, config contains:
config['strategies']['call_calendar']['entry'] = {
    'near_dte_min': 7,
    'near_dte_max': 12,
    # ...
}

# But strategy reads:
near_dte_target = self.entry_config.get('near_dte', 30)  # ← Uses DEFAULT 30!
dte_tolerance = self.entry_config.get('dte_tolerance', 5)  # ← Uses DEFAULT 5

# Actual filter: 25-35 DTE (not 7-12 as optimizer intended)
```

---

## Recommendations

### Option 1: Update Calendar Spread Strategy (Recommended)
Modify [calendar_spreads.py](../src/strategies/calendar_spreads.py) to support min/max DTE ranges like verticals:

```python
# Replace lines 185-199 with:
near_dte_min = self.entry_config.get('near_dte_min', 25)
near_dte_max = self.entry_config.get('near_dte_max', 35)
far_dte_min = self.entry_config.get('far_dte_min', 55)
far_dte_max = self.entry_config.get('far_dte_max', 65)

near_options = options_data[
    (options_data['dte'] >= near_dte_min) &
    (options_data['dte'] <= near_dte_max)
].copy()

far_options = options_data[
    (options_data['dte'] >= far_dte_min) &
    (options_data['dte'] <= far_dte_max)
].copy()
```

**Pros**:
- Matches optimizer expectations
- Consistent with vertical spreads
- More flexible (can optimize min and max independently)

**Cons**:
- Requires updating strategy code
- Need to update config.yaml defaults

---

### Option 2: Update Optimizer to Match Strategy (Alternative)
Modify [parameter_optimizer.py](../src/optimization/parameter_optimizer.py) to use center + tolerance:

```python
CALENDAR_PARAMETERS = {
    'entry': ['near_dte', 'far_dte', 'dte_tolerance', 'target_delta', ...],
    'exit': [...]
}
```

Then optimizer would set:
```python
optimizer.set_parameter_range('near_dte', min=5, max=15)
optimizer.set_parameter_range('dte_tolerance', min=3, max=7)
```

**Pros**:
- No strategy code changes
- Maintains current calendar spread logic

**Cons**:
- Less intuitive for optimization
- Can't independently optimize min and max ranges
- Inconsistent with vertical spreads

---

### Option 3: Support Both Approaches (Best of Both Worlds)
Update calendar spread strategy to check for both parameter styles:

```python
# Try min/max first (for optimizer), fall back to center ± tolerance (for config)
near_dte_min = self.entry_config.get('near_dte_min', None)
near_dte_max = self.entry_config.get('near_dte_max', None)

if near_dte_min is None or near_dte_max is None:
    # Fall back to center ± tolerance approach
    near_dte = self.entry_config.get('near_dte', 30)
    dte_tolerance = self.entry_config.get('dte_tolerance', 5)
    near_dte_min = near_dte - dte_tolerance
    near_dte_max = near_dte + dte_tolerance

# Use near_dte_min and near_dte_max for filtering...
```

**Pros**:
- Backward compatible with existing configs
- Works with optimizer
- Most flexible

**Cons**:
- More complex logic
- Need to document both parameter styles

---

## Tolerance Summary Table

| Parameter | Type | Tolerance Mechanism | Optimizer Compatible? |
|-----------|------|---------------------|----------------------|
| **Vertical DTE** | Range | `dte_min` to `dte_max` | ✅ Yes |
| **Calendar Near DTE** | Center ± tolerance | `near_dte ± dte_tolerance` | ❌ **No - Mismatch** |
| **Calendar Far DTE** | Center ± tolerance | `far_dte ± dte_tolerance` | ❌ **No - Mismatch** |
| **Target Delta** | Center ± tolerance | Target ± 0.05 (hardcoded) | ✅ Yes (finds closest) |
| **Profit Target** | Threshold | `>=` comparison | ✅ Yes (any value above) |
| **Stop Loss** | Threshold | `<=` comparison | ✅ Yes (any value below) |
| **VIX Min/Max** | Range | `vix_min` to `vix_max` | ✅ Yes |
| **Credit/Debit** | Range | `min_credit` to `max_credit` | ✅ Yes |

---

## Action Items

- [ ] Fix calendar spread DTE parameter mismatch
- [ ] Choose Option 1, 2, or 3 from recommendations
- [ ] Update documentation to clarify tolerance behavior
- [ ] Add validation in optimizer to catch config/strategy mismatches
- [ ] Consider making delta tolerance configurable (currently hardcoded 0.05)

---

**Last Updated**: 2025-11-12
