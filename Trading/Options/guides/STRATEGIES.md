# Strategy Implementations

## Core Strategies

### 1. Bull Put Spread (Credit Spread)

**Setup**: Sell higher strike put, buy lower strike put

**Profit/Loss**:
- **Max profit**: Premium collected (credit received)
- **Max loss**: Strike difference - premium
- **Breakeven**: Short strike - net credit

**Use case**: Neutral to bullish outlook

**Why this strategy**:
- High win rate (60-80%)
- Consistent income generation
- Defined risk/reward
- Benefits from time decay

**Ideal conditions**:
- Bullish or neutral market outlook
- High implied volatility (sell expensive premium)
- Strong support levels below current price

### 2. Bull Call Spread (Debit Spread)

**Setup**: Buy lower strike call, sell higher strike call

**Profit/Loss**:
- **Max profit**: Strike difference - premium paid
- **Max loss**: Premium paid (net debit)
- **Breakeven**: Long strike + net debit

**Use case**: Moderately bullish outlook

**Why this strategy**:
- Limited risk with defined maximum loss
- Defined reward potential
- Directional bullish play
- Lower cost than outright call purchase

**Ideal conditions**:
- Moderately bullish market outlook
- Low to moderate implied volatility
- Strong upside catalyst or trend

### 3. Call Calendar Spread (Time Spread)

**Setup**: Sell near-term call, buy far-term call (same strike)

**Profit/Loss**:
- **Max profit**: When underlying is at strike at near-term expiration
- **Max loss**: Net debit paid
- **Profit zone**: Underlying stays near the strike price

**Use case**: Neutral to slightly bullish, expect low volatility

**Best conditions**:
- Low IV environment, expecting IV to increase
- Underlying expected to stay range-bound
- Near-term expiration approaching (maximize theta decay difference)

**Why this strategy**:
- Profits from time decay (theta)
- Benefits from volatility expansion
- Lower risk than outright long call
- Can be adjusted/rolled

## Strategy Parameters

All strategy parameters are defined in `config/config.yaml` including:

### Entry Criteria

- **DTE ranges**: Days to expiration targets (e.g., 30-45 DTE)
- **Delta targets**: Option delta for strike selection (e.g., 0.30 delta)
- **Credit/Debit ranges**: Min/max premium thresholds
- **VIX filters**: Optional VIX-based entry conditions

### Exit Rules

- **Profit targets**: Close at X% of max profit (e.g., 50% of credit)
- **Stop losses**: Exit at X% loss threshold (e.g., 2x credit)
- **DTE exit**: Close before expiration (e.g., exit at 7 DTE)
- **Time-based exits**: For calendar spreads, exit before near-term expiration

### Position Sizing

- **Risk per trade**: Percentage of account to risk (e.g., 2%)
- **Max positions**: Maximum concurrent positions (e.g., 5)
- **Kelly Criterion**: Optimal position sizing based on win rate and payoff ratio

## Strategy Selection Guide

| Market Outlook | Volatility | Best Strategy |
|----------------|------------|---------------|
| Bullish | High IV | Bull Put Spread (sell premium) |
| Bullish | Low IV | Bull Call Spread (buy cheaper) |
| Neutral | Low IV → High IV | Call Calendar Spread |
| Neutral | High IV | Bull Put Spread (far OTM) |

## Implementation Files

- **`src/strategies/base_strategy.py`**: Abstract base class
  - Entry/exit signal generation
  - Position sizing
  - Performance tracking

- **`src/strategies/vertical_spreads.py`**: Vertical spread implementations
  - BullPutSpread
  - BullCallSpread
  - BearPutSpread
  - BearCallSpread

- **`src/strategies/calendar_spreads.py`**: Time spread implementations
  - CallCalendarSpread
  - PutCalendarSpread
  - DiagonalSpread (framework)

## Example Configuration

```yaml
strategies:
  bull_put:
    entry:
      dte_min: 30
      dte_max: 45
      target_delta: 0.30
      min_credit: 0.30
      max_credit: 2.00
    exit:
      profit_target: 0.50  # 50% of max profit
      stop_loss: 2.00      # 2x credit
      dte_min: 7           # Exit at 7 DTE

  call_calendar:
    entry:
      near_dte: 30
      far_dte: 60
      target_delta: 0.50
      min_debit: 1.00
      max_debit: 20.00
    exit:
      profit_target: 0.25  # 25% of debit
      stop_loss: 1.00      # 100% loss
      dte_exit: 3          # Exit 3 days before near expiration
```

For detailed configuration examples, see `config/config.yaml`.
