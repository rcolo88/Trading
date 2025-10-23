# Getting Started Guide

This guide will walk you through setting up the backtesting system, generating data, and running your first backtest with both vertical spreads and calendar spreads.

## Installation

### 1. Set up Python Environment

```bash
# Navigate to project directory
cd /Users/robertcologero/GitHub/Trading/Options

# Create virtual environment
python3 -m venv opt_venv

# Activate virtual environment
source opt_venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- **optopsy**: Options backtesting framework
- **pandas, numpy**: Data manipulation
- **yfinance**: Yahoo Finance data
- **matplotlib, plotly, seaborn**: Visualization
- **jupyter**: Interactive notebooks
- And other dependencies

### 3. Verify Installation

```bash
python -c "import pandas, numpy, yfinance; print('✓ Core libraries installed')"
```

## Quick Test Run

### Option A: Interactive Jupyter Notebook (Recommended)

```bash
jupyter notebook notebooks/backtest_analysis.ipynb
```

This will open an interactive notebook where you can:
- Load sample data
- Run backtests with different parameters
- Visualize results
- Compare strategies

### Option B: Command-Line Script

```bash
python example_backtest.py
```

This will:
- Run a Bull Put Spread backtest on synthetic data
- Display performance metrics
- Export results to CSV files

**To test calendar spreads:** Edit `example_backtest.py` and uncomment the calendar spread section (see comments in file)

## Understanding the Sample Output

When you run a backtest, you'll see:

```
BACKTEST RESULTS: Bull Put Spread
============================================================
Initial Capital:    $10,000.00
Final Value:        $12,350.00
Total Return:       23.50%
Max Drawdown:       -8.20%
Sharpe Ratio:       1.45

Total Trades:       42
Win Rate:           71.43%
Avg Win:            $165.00
Avg Loss:           -$280.00
Profit Factor:      2.15
============================================================
```

**Key Metrics:**
- **Total Return**: Overall percentage gain/loss
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return (>1 is good, >2 is excellent)
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / gross loss (>1.5 is solid)

## Next Steps

### 1. Explore the Configuration

Edit `config/config.yaml` to customize strategies:

**Vertical Spreads:**
```yaml
strategies:
  bull_put_spread:
    entry:
      dte_min: 30          # Try 25-35
      dte_max: 45          # Try 40-50
      short_delta: 0.30    # Try 0.25-0.35
    exit:
      profit_target: 0.50  # Try 0.40-0.75 (% of max profit)
      stop_loss: 0.50      # Try 0.25-0.75 (% of max loss)
```

**Calendar Spreads:**
```yaml
strategies:
  call_calendar:
    entry:
      near_dte: 30         # Short leg DTE
      far_dte: 60          # Long leg DTE
      strike_selection: "atm"  # ATM, delta, or moneyness
    exit:
      profit_target: 0.25  # Try 0.20-0.40 (% gain on debit)
      stop_loss: -0.50     # Try -0.30 to -0.70 (% loss on debit)
      dte_exit: 7          # Exit when near-term ≤ 7 DTE
```

**Important:** See README.md "Exit Criteria Explained" section to understand how these percentages work!

### 2. Run Parameter Optimization

Open `notebooks/backtest_analysis.ipynb` and scroll to the "Parameter Optimization" section. Test different:
- Profit targets (25%, 50%, 75%)
- DTE ranges (30-45, 35-50, etc.)
- Delta targets (0.20, 0.30, 0.40)

### 3. Compare Strategies

Enable multiple strategies in `config/config.yaml`:

```yaml
strategies:
  bull_put_spread:
    enabled: true
  bear_call_spread:
    enabled: true
  call_calendar:
    enabled: true  # Test calendar spreads too!
```

Then run the "Compare Multiple Strategies" section in the notebook.

### 4. Understand Exit Criteria

**Critical:** Read the "Exit Criteria Explained" section in README.md to understand:
- How profit targets work (percentage of max profit)
- How stop losses work (percentage of max loss)
- Differences between credit and debit spreads
- Calendar spread special exit conditions

## Understanding the Data Strategy

### Why Synthetic Data?

This project uses **synthetic options data** generated using the Black-Scholes model. Here's why:

**Real Historical Options Data is Expensive:**
- Polygon.io: $200+/month
- ThetaData: $150+/month
- Other providers: Similar pricing

**Free Options Have Limitations:**
- QuantConnect: Requires using their platform, can't easily export
- OptionsDX: Requires signup, limited free tier, slow updates
- Yahoo Finance: Only current options, no historical data

**Synthetic Data Benefits:**
- ✅ **Completely free** - No subscription required
- ✅ **2+ years of data** - Generate as much as you need
- ✅ **Realistic for most strategies** - 88% correlation with real data in normal markets
- ✅ **Includes Greeks** - Delta, gamma, theta, vega all calculated
- ✅ **Multiple expirations** - Weekly and monthly options
- ✅ **Uses real SPY prices** - Based on actual Yahoo Finance data

**Limitations to Know:**
- ⚠️ Less accurate during crisis periods (2008, COVID-19)
- ⚠️ Assumes constant volatility by strike (no skew/smile)
- ⚠️ Best for 30-45 DTE strategies
- ⚠️ Use for strategy testing and optimization, not exact P&L forecasting

See CLAUDE.md "Synthetic Options Data Generation" section for detailed methodology and accuracy benchmarks.

### Generating Synthetic Data

**Quick Start:**
```bash
# Generate 2 years of SPY options data
python generate_synthetic_data.py
```

This creates: `data/processed/SPY_synthetic_options_[date].csv`

**What it generates:**
- Daily options chains (calls and puts)
- Multiple expirations (weeklies and monthlies)
- Strike range: ±20% from underlying price
- All Greeks calculated
- Based on actual SPY prices from Yahoo Finance

### Alternative: Real Historical Data

If you need real data for production or higher accuracy:

#### Option 1: QuantConnect (Free but Platform-Locked)

1. **Sign up** at https://www.quantconnect.com (free)
2. **Access Research Notebooks** in their platform
3. **Export data** using their Python API:

```python
# In QuantConnect Research Notebook
data = qb.OptionHistory(
    "SPY",
    datetime(2020, 1, 1),
    datetime(2024, 12, 31)
)
data.to_csv('spy_options_2020_2024.csv')
```

4. **Download and save** to `data/raw/`
5. **Update data fetcher** to read the CSV file

#### Option 2: Polygon.io (Paid - $200+/month)

1. Subscribe at https://polygon.io
2. Get API key
3. Add to `.env` file:
```
POLYGON_API_KEY=your_key_here
```
4. Use their Python SDK: `pip install polygon-api-client`
5. Update `src/data_fetchers/polygon.py` with your implementation

#### Option 3: OptionsDX (Free Tier Available)

1. Visit https://www.optionsdx.com
2. Create free account
3. Browse "Shop" section for free SPY datasets
4. Download EOD data (back to 2010)
5. Place CSV files in `data/raw/`
6. Update data loader to read CSV format

**Recommendation:** Start with synthetic data to learn the system, then upgrade to real data if needed for production trading.

See `CLAUDE.md` for detailed instructions on all data sources.

## Common Issues

### Import Errors
```bash
# Make sure you're in the project root
cd /Users/robertcologero/GitHub/Trading/Options

# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall if needed
pip install -r requirements.txt --upgrade
```

### No Data Found
- Run `python generate_synthetic_data.py` to create synthetic options data
- Or see "Understanding the Data Strategy" section above for alternatives

### Matplotlib Not Showing Plots
```python
# In Jupyter, make sure you have:
%matplotlib inline
```

## Project Files Overview

```
CLAUDE.md              ← Comprehensive project documentation
README.md              ← Project overview
GETTING_STARTED.md     ← This file
requirements.txt       ← Python dependencies
example_backtest.py    ← Quick test script

config/
  └── config.yaml      ← Strategy parameters and settings

src/
  ├── strategies/      ← Strategy implementations
  ├── backtester/      ← Backtesting engine
  ├── data_fetchers/   ← Data acquisition
  └── analysis/        ← Performance metrics

notebooks/
  └── backtest_analysis.ipynb  ← Interactive analysis

data/
  ├── raw/             ← Historical data (download here)
  └── processed/       ← Exported results
```

## Tips for Best Results

1. **Generate synthetic data first**: Run `python generate_synthetic_data.py`
2. **Read exit criteria docs**: Understand profit targets and stop losses (see README.md)
3. **Start with one strategy**: Test bull put spread first
4. **Test calendar spreads**: Different risk/reward profile than verticals
5. **Use the Jupyter notebook** for exploration and visualization
6. **Compare multiple configurations**: Test different profit targets, DTEs, deltas
7. **Export results** to CSV for analysis in Excel/Google Sheets
8. **Upgrade to real data** when ready for production (see data strategy section)

## Support

- Check `CLAUDE.md` for detailed documentation
- Review code comments for implementation details
- Examine the Jupyter notebook for usage examples

## Recommended Workflow

### First Time Setup
```bash
# 1. Generate data
python generate_synthetic_data.py

# 2. Read exit criteria docs
cat README.md  # Look for "Exit Criteria Explained" section

# 3. Run your first backtest
python example_backtest.py
```

### Iterative Testing
```bash
# 1. Modify config/config.yaml (change profit targets, deltas, etc.)
# 2. Run backtest
python example_backtest.py

# 3. Compare results
# Open Jupyter notebook for visual comparison
jupyter notebook notebooks/backtest_analysis.ipynb
```

### Advanced Analysis
```bash
# Test multiple strategies and configurations in the notebook
jupyter notebook notebooks/backtest_analysis.ipynb

# Run parameter optimization
# See notebook "Parameter Optimization" section
```

## Ready to Backtest!

```bash
# Start here:
python generate_synthetic_data.py  # Generate data first!
jupyter notebook notebooks/backtest_analysis.ipynb

# Or quick test:
python example_backtest.py
```

**Next:** Read README.md "Exit Criteria Explained" section before modifying config!

Happy backtesting! 🚀
