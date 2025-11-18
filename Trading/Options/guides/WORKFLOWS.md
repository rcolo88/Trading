# Common Workflows

## Kelly Criterion Position Sizing

The Kelly Criterion provides mathematically optimal position sizing based on your strategy's win rate and payoff ratio.

### Kelly Formula

```
f* = (p × b - q) / b

Where:
  f* = Fraction of capital to risk (Kelly %)
  p = Win rate (probability of winning)
  q = Loss rate (1 - p)
  b = Payoff ratio = Average Win / Average Loss
```

### Workflow: Calculate Kelly Percentage

**Step 1: Configure strategy parameters**

Edit `config/config.yaml` with your initial strategy parameters (DTE, delta, profit targets, etc.)

**Step 2: Run backtest to generate trade history**

```python
# In notebooks/backtest_analysis.ipynb or your script
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.strategies.vertical_spreads import BullPutSpread

backtester = OptopsyBacktester(config)
strategy = BullPutSpread(config)

results = backtester.run_backtest(
    strategy=strategy,
    options_data=options_data,
    underlying_data=underlying_data
)
```

**Step 3: Open Kelly Criterion notebook**

```bash
jupyter notebook notebooks/Kelly_Criteria.ipynb
```

**Step 4: Calculate Kelly % from backtest results**

```python
# Extract metrics from results
win_rate = results['win_rate_pct'] / 100  # Convert to decimal
avg_win = results['avg_win']
avg_loss = abs(results['avg_loss'])
payoff_ratio = avg_win / avg_loss

# Calculate Kelly %
p = win_rate
q = 1 - win_rate
b = payoff_ratio
kelly_pct = (p * b - q) / b

print(f"Win Rate: {win_rate:.2%}")
print(f"Payoff Ratio: {payoff_ratio:.2f}")
print(f"Full Kelly: {kelly_pct:.2%}")
print(f"Half Kelly: {kelly_pct/2:.2%}")
print(f"Quarter Kelly: {kelly_pct/4:.2%}")
```

**Step 5: Manually update config.yaml**

```yaml
position_sizing:
  method: 'kelly'
  kelly_pct: 0.15  # Use Half Kelly or Quarter Kelly
  risk_per_trade_percent: 2.0
  max_positions: 5
```

**Step 6: Re-run backtest with Kelly-based sizing**

Run the backtest again using the updated Kelly percentage for more realistic position sizing.

### Important Notes

- **Use Half Kelly (50%) or Quarter Kelly (25%)**: Full Kelly is too aggressive and can lead to large drawdowns
- **Recalculate periodically**: As your strategy evolves, update Kelly % based on new results
- **Consider constraints**: Max positions and account size may limit Kelly implementation

## Trade Export & Review

After running a backtest, you can export detailed trade information to CSV or XLSX files for review and analysis.

### Usage Example

```python
# Run backtest
backtester = OptopsyBacktester(config)
results = backtester.run_backtest(
    strategy=strategy,
    options_data=options_data,
    underlying_data=underlying_data
)

# Export trades to CSV (default)
backtester.export_trades(results)

# Or export to Excel
backtester.export_trades(results, format='xlsx')

# Specify custom output directory
backtester.export_trades(results, output_dir='my_trades', format='csv')
```

### Export Contents

Each exported file contains:

#### 1. Entry Information
- `entry_date`: Date trade was executed
- `underlying_price_entry`: SPY price at entry
- `vix_entry`: VIX level at entry
- `entry_dte`: Days to expiration at entry
- `entry_price`: Spread entry price (debit or credit)
- `contracts`: Number of contracts traded

#### 2. Leg Details (for each leg)
- `leg1_strike`, `leg2_strike`: Strike prices
- `leg1_type`, `leg2_type`: 'call' or 'put'
- `leg1_position`, `leg2_position`: +1 (long) or -1 (short)
- `leg1_delta`, `leg2_delta`: Delta at entry
- `leg1_price`, `leg2_price`: Individual leg prices
- `leg1_expiration`, `leg2_expiration`: Expiration dates

#### 3. Calendar Spread Specific
- `near_expiration`: Near-term contract expiration
- `far_expiration`: Far-term contract expiration

#### 4. Exit Information
- `exit_date`: Date trade was closed
- `underlying_price_exit`: SPY price at exit
- `vix_exit`: VIX level at exit
- `exit_price`: Spread exit price
- `exit_reason`: Why the trade was closed

#### 5. P&L
- `pnl`: Gross profit/loss
- `commission`: Transaction costs
- `net_pnl`: Net profit/loss after commissions
- `days_in_trade`: Duration of trade

### Output Files

Files are saved in `backtest_results/` directory (or custom path) with static filenames:
- `Bull_Put_Spread.csv`
- `Call_Calendar_Spread.xlsx`
- `Bear_Call_Spread.csv`

**Note**: Files are overwritten on each backtest run to maintain a clean workspace.

### Requirements for XLSX Export

```bash
pip install openpyxl
```

## Backtesting Workflow

### Step 1: Generate or Load Data

**Option A: Generate synthetic data**
```bash
python generate_synthetic_data.py
```

**Option B: Load real data**
```python
from src.data_fetchers.polygon import load_polygon_data
options_data = load_polygon_data('SPY', start_date='2022-01-01', end_date='2024-12-31')
```

### Step 2: Configure Strategy

Edit `config/config.yaml` with desired parameters:
- Strategy selection
- Entry/exit rules
- Position sizing
- Backtest date range

### Step 3: Run Backtest

```python
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.strategies.vertical_spreads import BullPutSpread

# Load config
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize
backtester = OptopsyBacktester(config)
strategy = BullPutSpread(config)

# Run backtest
results = backtester.run_backtest(
    strategy=strategy,
    options_data=options_data,
    underlying_data=underlying_data
)

# Print results
backtester.print_results(results)
```

### Step 4: Analyze Results

```python
from src.analysis.metrics import PerformanceAnalyzer

analyzer = PerformanceAnalyzer(
    equity_curve=results['equity_curve'],
    trades=results['trades']
)

# Generate report
metrics = analyzer.calculate_all_metrics(initial_capital=10000)
report = analyzer.generate_report(metrics)
print(report)

# Visualize
analyzer.plot_equity_curve()
analyzer.plot_drawdown()
analyzer.plot_monthly_returns()
```

### Step 5: Export Trades

```python
backtester.export_trades(results, format='csv')
```

### Step 6: Optimize Parameters (Optional)

```python
from src.optimization.parameter_optimizer import quick_optimize_vertical

results = quick_optimize_vertical(
    strategy_class=BullPutSpread,
    backtester=backtester,
    options_data=options_data,
    underlying_data=underlying_data,
    config=config,
    dte_range=(30, 45),
    delta_range=(0.25, 0.40),
    profit_target_range=(0.40, 0.60)
)

# Get best parameters
best = results.head(5)
print(best)
```

## Data Generation Workflow

### Quick Start: 2 Years of Synthetic Data

```bash
# Generate 2 years of SPY options data
python generate_synthetic_data.py
```

This creates:
- `data/processed/spy_options_synthetic_2year.pkl`
- `data/processed/spy_underlying_2year.pkl`

### Custom Date Range

```python
from src.data_fetchers.synthetic_generator import SyntheticOptionsGenerator

generator = SyntheticOptionsGenerator(
    symbol="SPY",
    use_vix_for_iv=True  # Use VIX for realistic pricing
)

# Generate data
options_data, underlying_data = generator.generate_historical_chains(
    start_date="2020-01-01",
    end_date="2023-12-31"
)

# Save
options_data.to_pickle('data/processed/spy_options_custom.pkl')
underlying_data.to_pickle('data/processed/spy_underlying_custom.pkl')
```

### Validation

```bash
# Validate delta calculations
python validate_deltas.py

# Visualize delta decay
python visualize_delta_decay.py
```
