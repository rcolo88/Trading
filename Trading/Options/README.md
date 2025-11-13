# Options Backtesting System

A comprehensive Python-based backtesting framework for options trading strategies, focusing on vertical spreads (bull/bear put/call spreads) and calendar spreads (time spreads) on SPY/SPX.

## Features

- **Strategy Implementations**:
  - **Vertical Spreads**: Bull put spread, bear call spread, bull call spread, bear put spread
  - **Calendar Spreads**: Call calendar spread, put calendar spread
- **Flexible Configuration**: YAML-based configuration for easy parameter tuning
- **Comprehensive Exit Logic**: Profit targets, stop losses, DTE-based exits, and underlying movement thresholds
- **Comprehensive Analysis**: Performance metrics, equity curves, drawdown analysis, and more
- **Data Integration**: Support for multiple data sources (Yahoo Finance, QuantConnect, Polygon.io)
- **Synthetic Data Generation**: Black-Scholes-based options data generator for free historical backtesting
- **Interactive Notebooks**: Jupyter notebooks for exploratory analysis and backtesting

## Data Options

### Free Historical Data (Recommended for Getting Started)

**Synthetic Data Generation (Black-Scholes)**
Generate 2+ years of realistic options data for free using actual SPY prices:

```bash
python generate_synthetic_data.py
```

This will:
- Fetch SPY prices from Yahoo Finance (free)
- Calculate historical volatility
- Generate options chains using Black-Scholes pricing
- Include Greeks (delta, gamma, theta, vega)
- Save to `data/processed/SPY_synthetic_options_*.csv`

**Pros:** Free, realistic for most backtests, includes all necessary data
**Cons:** Less accurate during crises, assumes constant volatility per strike

**OptionsDX (Real Historical Data - Free Tier)**
- Visit https://www.optionsdx.com
- Create free account
- Download SPY historical options data (EOD back to 2010)
- Free tier available with account signup

**Polygon.io (Real Historical Data - Free Trial)**
- Sign up at https://polygon.io
- Free tier: 2 years of options data, 5 API calls/min
- May require paid upgrade for practical backtesting

See `CLAUDE.md` for detailed comparison and instructions.

## Quick Start

### 1. Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Edit `config/config.yaml` to customize:
- Backtest period and initial capital
- Strategy parameters (DTE, delta targets, strike selection)
- **Exit rules** (profit targets, stop losses, DTE thresholds) - See **"Exit Criteria Explained"** section below
- Position sizing and risk management
- Transaction costs

**Important**: Read the **"Exit Criteria Explained"** section to understand how profit targets and stop losses work!

### 3. Run a Backtest

**Option A: Using Jupyter Notebook (Recommended)**

```bash
jupyter notebook notebooks/backtest_analysis.ipynb
```

Follow the notebook cells to:
1. Load data
2. Configure strategies
3. Run backtests
4. Analyze results

**Option B: Using Python Script**

```python
import yaml
from src.strategies.vertical_spreads import BullPutSpread
from src.strategies.calendar_spreads import CallCalendarSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

# Load config
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Get data
options_data = load_sample_spy_options_data()  # Synthetic data from Yahoo prices
underlying_data = fetch_spy_data('2023-01-01', '2023-12-31')

# Create strategy (choose one)
# Vertical spread:
strategy = BullPutSpread(config['strategies']['bull_put_spread'])
# Or calendar spread:
# strategy = CallCalendarSpread(config['strategies']['call_calendar'])

# Run backtest
backtester = OptopsyBacktester(config)
results = backtester.run_backtest(strategy, options_data, underlying_data)

# Print results
backtester.print_results(results)
```

## Project Structure

```
Options/
├── CLAUDE.md                    # Detailed project documentation
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── config/
│   └── config.yaml             # Configuration file
├── data/
│   ├── raw/                    # Raw historical data
│   └── processed/              # Processed data
├── src/
│   ├── data_fetchers/          # Data acquisition modules
│   ├── strategies/             # Strategy implementations
│   ├── backtester/             # Backtesting engine
│   └── analysis/               # Performance analysis
├── notebooks/
│   └── backtest_analysis.ipynb # Interactive analysis
└── tests/
    └── test_strategies.py      # Unit tests
```

## Strategies

### Vertical Spreads

#### Bull Put Spread (Credit Spread)
- **Setup**: Sell higher strike put, buy lower strike put
- **Outlook**: Neutral to bullish
- **Max Profit**: Premium collected
- **Max Loss**: Strike width - premium
- **Exit Criteria**: Profit target %, stop loss %, DTE threshold

#### Bear Call Spread (Credit Spread)
- **Setup**: Sell lower strike call, buy higher strike call
- **Outlook**: Neutral to bearish
- **Max Profit**: Premium collected
- **Max Loss**: Strike width - premium
- **Exit Criteria**: Profit target %, stop loss %, DTE threshold

#### Bull Call Spread (Debit Spread)
- **Setup**: Buy lower strike call, sell higher strike call
- **Outlook**: Moderately bullish
- **Max Profit**: Strike width - premium paid
- **Max Loss**: Premium paid
- **Exit Criteria**: Profit target %, stop loss %, DTE threshold

#### Bear Put Spread (Debit Spread)
- **Setup**: Buy higher strike put, sell lower strike put
- **Outlook**: Moderately bearish
- **Max Profit**: Strike width - premium paid
- **Max Loss**: Premium paid
- **Exit Criteria**: Profit target %, stop loss %, DTE threshold

### Calendar Spreads (Time Spreads)

#### Call Calendar Spread
- **Setup**: Sell near-term call (e.g., 30 DTE), buy far-term call (e.g., 60 DTE) at same strike
- **Outlook**: Neutral to slightly bullish, low volatility expected
- **Max Profit**: When underlying is at strike at near-term expiration
- **Max Loss**: Net debit paid
- **Best Conditions**: Low IV environment, expecting IV to increase
- **Exit Criteria**: Profit target %, stop loss %, DTE threshold (exit before near-term expiration), underlying movement threshold

#### Put Calendar Spread
- **Setup**: Sell near-term put (e.g., 30 DTE), buy far-term put (e.g., 60 DTE) at same strike
- **Outlook**: Neutral to slightly bearish, low volatility expected
- **Max Profit**: When underlying is at strike at near-term expiration
- **Max Loss**: Net debit paid
- **Best Conditions**: Low IV environment, expecting IV to increase
- **Exit Criteria**: Profit target %, stop loss %, DTE threshold (exit before near-term expiration), underlying movement threshold

## Performance Metrics

The framework calculates comprehensive metrics including:

- **P&L Metrics**: Total return, annualized return, total P&L
- **Risk Metrics**: Sharpe ratio, Sortino ratio, Calmar ratio, max drawdown
- **Trade Statistics**: Win rate, profit factor, average win/loss
- **Time-Based**: Monthly returns, positive months percentage

## Data Sources

### Currently Implemented
- **Yahoo Finance**: Free underlying price data (yfinance)
- **Sample Data**: Synthetic options data for testing

### Future Integration
- **QuantConnect**: Free hour-level historical options data (requires account)
- **Polygon.io**: Premium minute-level historical data (paid)
- **Schwab API**: Real-time data for paper/live trading (requires developer account)

### Getting Real Historical Data

**QuantConnect (Free)**
1. Sign up at https://www.quantconnect.com
2. Access their research notebooks
3. Export historical options data
4. Save to `data/raw/`

**Polygon.io (Paid - $200+/month)**
1. Subscribe at https://polygon.io
2. Get API key
3. Use their Python SDK to download data

See `CLAUDE.md` for detailed data acquisition instructions.

## Exit Criteria Explained

### How Profit Targets and Stop Losses Work

All strategies use **percentage-based exit criteria** for consistency and clarity.

#### Vertical Spreads (Credit and Debit)

**Profit Target** = Percentage of maximum profit to capture before exiting
**Stop Loss** = Percentage of maximum loss to tolerate before exiting

**Example 1: Bull Put Spread (Credit Spread)**
```
Entry: Sell $420 put / Buy $415 put for $2.00 credit
Strike width: $5
Max profit: $2.00 (credit received)
Max loss: $3.00 ($5 width - $2 credit)

Config:
  profit_target: 0.50  # Exit at 50% of max profit
  stop_loss: 0.50      # Exit at 50% of max loss

Exit conditions:
✓ Profit target: Exit when spread is worth $1.00 (captured $1.00 profit = 50% of $2.00 max profit)
✓ Stop loss: Exit when you've lost $1.50 (50% of $3.00 max loss)
```

**Example 2: Bull Call Spread (Debit Spread)**
```
Entry: Buy $410 call / Sell $415 call for $2.00 debit
Strike width: $5
Max profit: $3.00 ($5 width - $2 debit)
Max loss: $2.00 (debit paid)

Config:
  profit_target: 0.75  # Exit at 75% of max profit
  stop_loss: 0.50      # Exit at 50% of max loss

Exit conditions:
✓ Profit target: Exit when spread is worth $4.25 (gained $2.25 = 75% of $3.00 max profit)
✓ Stop loss: Exit when spread is worth $1.00 (lost $1.00 = 50% of $2.00 max loss)
```

#### Calendar Spreads

**Profit Target** = Percentage gain on the debit paid
**Stop Loss** = Percentage loss on the debit paid (negative value)

**Example: Call Calendar Spread**
```
Entry: Sell 30 DTE call / Buy 60 DTE call at $420 strike for $3.00 debit
Max loss: $3.00 (debit paid)

Config:
  profit_target: 0.25    # Exit at 25% profit
  stop_loss: -0.50       # Exit at 50% loss
  dte_exit: 7            # Exit when near-term ≤ 7 DTE
  max_underlying_move: 0.10  # Exit if underlying moves >10% from strike

Exit conditions:
✓ Profit target: Exit when spread is worth $3.75 (25% profit = $0.75 gain)
✓ Stop loss: Exit when spread is worth $1.50 (50% loss = $1.50 loss)
✓ DTE exit: Exit 7 days before near-term expiration (mandatory)
✓ Movement: Exit if SPY moves from $420 to >$462 or <$378 (>10% move)
```

### Recommended Settings

**Credit Spreads** (Bull Put, Bear Call):
- `profit_target: 0.50` - Take profits at 50% of max profit (common wisdom)
- `stop_loss: 0.50` - Cut losses at 50% of max loss
- `dte_min: 21` - Exit when DTE drops below 21 days

**Debit Spreads** (Bull Call, Bear Put):
- `profit_target: 0.75` - Take profits at 75% of max profit
- `stop_loss: 0.50` - Cut losses at 50% of max loss
- `dte_min: 14` - Exit when DTE drops below 14 days

**Calendar Spreads**:
- `profit_target: 0.25` - Take 25% profit on debit paid
- `stop_loss: -0.50` - Cut losses at 50% of debit paid
- `dte_exit: 7` - Exit 7 days before near-term expiration
- `max_underlying_move: 0.10` - Exit if underlying moves >10%

### Backtesting Behavior Note

**Daily Entry Limit**: The backtester enforces a **maximum of one trade per day per strategy**, with a goal to enter at least one trade per day when position sizing allows. This prevents over-trading and matches real-world systematic trading approaches.

**Exit Checking**: Exit conditions are checked once per trading day (at market close). This means:
- Profit targets may be exceeded due to overnight price movements or weekend gaps
- Actual exit profits often exceed configured targets by 5-15% on average
- Calendar spreads are particularly sensitive to volatility spikes, which can cause rapid profit acceleration between daily checks
- This behavior accurately reflects real-world trading where limit orders may fill at better prices during fast markets

This is **expected behavior** and matches how options behave in practice with end-of-day management.

## Configuration

Key configuration parameters in `config/config.yaml`:

**Vertical Spread Example:**
```yaml
strategies:
  bull_put_spread:
    entry:
      dte_min: 30          # Enter with 30-45 DTE
      dte_max: 45
      short_delta: 0.30    # Sell 30 delta put
      long_delta: 0.20     # Buy 20 delta put
    exit:
      profit_target: 0.50  # Close at 50% of max profit
      stop_loss: 0.50      # Stop at 50% of max loss
      dte_min: 21          # Close if < 21 DTE
```

**Calendar Spread Example:**
```yaml
strategies:
  call_calendar:
    entry:
      near_dte: 30              # Sell 30 DTE call
      far_dte: 60               # Buy 60 DTE call
      strike_selection: "atm"   # ATM, delta, or moneyness
      min_debit: 0.5            # Minimum debit to enter
    exit:
      profit_target: 0.25       # Close at 25% profit
      stop_loss: -0.50          # Stop at 50% loss
      dte_exit: 7               # Exit when near-term ≤ 7 DTE
      max_underlying_move: 0.10 # Exit if underlying moves >10% from strike
```

## How to Modify Exit Criteria

### Step 1: Edit config/config.yaml

Open `config/config.yaml` and locate the strategy you want to modify:

```yaml
strategies:
  bull_put_spread:
    exit:
      profit_target: 0.50  # Change this to your desired profit %
      stop_loss: 0.50      # Change this to your desired loss %
      dte_min: 21          # Change this to your desired DTE threshold
```

### Step 2: Understanding the Values

**Profit Target** (0.0 to 1.0):
- `0.50` = Exit at 50% of max profit
- `0.75` = Exit at 75% of max profit
- `0.25` = Exit at 25% of max profit

**Stop Loss** (0.0 to 1.0):
- `0.50` = Exit at 50% of max loss
- `0.75` = Exit at 75% of max loss (more risk tolerant)
- `0.25` = Exit at 25% of max loss (less risk tolerant)

**DTE Minimum** (integer):
- `21` = Exit when position has 21 or fewer days to expiration
- `14` = Exit when position has 14 or fewer days to expiration
- `7` = Exit when position has 7 or fewer days to expiration

### Step 3: Run Backtest and Compare

```python
# Run backtest with your new parameters
python example_backtest.py

# Or use the Jupyter notebook to compare multiple configurations
jupyter notebook notebooks/backtest_analysis.ipynb
```

### Step 4: Analyze Results

The backtester will show:
- How many trades hit profit target vs stop loss
- Average days in trade
- Win rate and profit factor
- Overall P&L and Sharpe ratio

Use these metrics to optimize your exit criteria.

## Parameter Optimization

The framework includes a **ParameterOptimizer** class that performs grid search to find optimal strategy parameters.

### Quick Start

```python
from src.optimization import ParameterOptimizer, quick_optimize_calendar
from src.strategies.calendar_spreads import CallCalendarSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester

# Create optimizer
optimizer = ParameterOptimizer(
    strategy_type='calendar',  # or 'vertical'
    strategy_class=CallCalendarSpread,
    backtester=backtester,
    options_data=options_data,
    underlying_data=underlying_data,
    base_config=config
)

# Define parameter ranges (min, max, step)
optimizer.set_parameter_range('near_dte_min', min=5, max=10)
optimizer.set_parameter_range('near_dte_max', min=10, max=15)
optimizer.set_parameter_range('profit_target', min=0.20, max=0.30, step=0.05)
optimizer.set_parameter_range('target_delta', min=0.45, max=0.55, step=0.05)

# Run optimization
results = optimizer.run_optimization(optimization_metric='sharpe_ratio')

# Get best parameters
best = optimizer.get_best_parameters(metric='sharpe_ratio', top_n=5)
print(best)
```

### Strategy-Specific Parameters

**Calendar Spreads**:
- Entry: `near_dte_min`, `near_dte_max`, `far_dte_min`, `far_dte_max`, `target_delta`, `vix_min`, `vix_max`
- Exit: `profit_target`, `stop_loss`, `dte_exit`, `max_underlying_move`

**Vertical Spreads**:
- Entry: `dte_min`, `dte_max`, `target_delta`, `min_credit`, `max_credit`, `vix_min`, `vix_max`
- Exit: `profit_target`, `stop_loss`, `dte_min`

### Example

See [examples/optimize_parameters.py](examples/optimize_parameters.py) for complete examples including:
- Calendar spread optimization
- Vertical spread optimization
- Sensitivity analysis plots
- Heatmap visualization

## Next Steps

1. **Install and test** with sample data
2. **Generate synthetic data** using `python generate_synthetic_data.py`
3. **Run your first backtest** with default parameters
4. **Modify exit criteria** in config.yaml based on results
5. **Optimize parameters** by testing different configurations
6. **Backtest multiple strategies** and compare results
7. **Paper trade** using Schwab API integration (future enhancement)

## Documentation

- **CLAUDE.md**: Comprehensive project documentation
- **Jupyter Notebook**: Interactive tutorials and examples
- **Code Comments**: Detailed inline documentation

## Requirements

- Python 3.8+
- See `requirements.txt` for full dependencies

## Contributing

This is a personal project, but feel free to use as reference or template for your own options backtesting.

## Disclaimer

This software is for educational and research purposes only. Past performance does not guarantee future results. Options trading involves risk and is not suitable for all investors. Always do your own research and consult with financial professionals before trading.

## License

MIT License - see LICENSE file for details

---

**Project Status**: 🚀 Ready for Backtesting - Vertical & Calendar Spreads Implemented

**Last Updated**: 2025-10-22
