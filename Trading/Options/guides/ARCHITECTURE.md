# Architecture & Technology Stack

## Directory Structure

```
/Options/
├── CLAUDE.md                    # Project overview and documentation index
├── CHANGELOG.md                 # Version history and updates
├── requirements.txt             # Python dependencies
├── config/
│   └── config.yaml             # Configuration for data sources, strategies
├── data/
│   ├── raw/                    # Downloaded historical options data
│   └── processed/              # Cleaned, formatted data for backtesting
├── src/
│   ├── data_fetchers/          # Data acquisition modules
│   │   ├── __init__.py
│   │   ├── quantconnect.py    # QuantConnect data integration
│   │   ├── cboe.py            # CBOE DataShop integration
│   │   ├── yahoo_options.py   # Yahoo Finance current options data
│   │   ├── polygon.py         # Placeholder for future Polygon.io upgrade
│   │   └── synthetic_generator.py  # Synthetic options data generator
│   ├── strategies/             # Strategy implementations
│   │   ├── __init__.py
│   │   ├── base_strategy.py   # Abstract strategy template
│   │   ├── vertical_spreads.py # Bull/bear put/call spreads
│   │   └── calendar_spreads.py # Call/put calendar and diagonal spreads
│   ├── backtester/             # Backtesting engine
│   │   ├── __init__.py
│   │   └── optopsy_wrapper.py # Optopsy library integration
│   ├── analysis/               # Performance analysis
│   │   ├── __init__.py
│   │   └── metrics.py         # P&L, Greeks, risk metrics
│   ├── optimization/           # Parameter optimization
│   │   ├── __init__.py
│   │   └── parameter_optimizer.py  # Grid search optimizer
│   └── utils/                  # Utility functions
│       ├── __init__.py
│       └── black_scholes.py   # Black-Scholes pricing and Greeks
├── guides/                     # Documentation guides
│   ├── ARCHITECTURE.md         # This file
│   ├── DATA_GUIDE.md          # Data sources and acquisition
│   ├── DATA_VALIDATION.md     # Quality assurance
│   ├── STRATEGIES.md          # Strategy implementations
│   ├── WORKFLOWS.md           # Common workflows
│   ├── METRICS.md             # Performance metrics
│   └── RESEARCH.md            # Research notes and roadmap
├── notebooks/
│   └── backtest_analysis.ipynb # Interactive backtesting and visualization
└── tests/
    └── test_strategies.py      # Unit tests for strategies
```

## Technology Stack

### Core Libraries

- **Optopsy**: Options backtesting framework with vertical spread support
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computations
- **Matplotlib/Plotly**: Visualization
- **yfinance**: Underlying price data for SPY

### Optional Libraries

- **QuantConnect**: Free hour-level historical options data
- **scipy**: Statistical analysis and optimization
- **pytest**: Testing framework
- **py_vollib**: Black-Scholes pricing and Greeks calculations
- **openpyxl**: Excel export functionality

## Module Descriptions

### Data Fetchers (`src/data_fetchers/`)

- **synthetic_generator.py**: Generates realistic options chains using Black-Scholes model
- **quantconnect.py**: Integration with QuantConnect API (hour-level data)
- **cboe.py**: CBOE DataShop integration for SPX options
- **yahoo_options.py**: Yahoo Finance for current options chains and SPY prices
- **polygon.py**: Future integration with Polygon.io API

### Strategies (`src/strategies/`)

- **base_strategy.py**: Abstract base class defining strategy interface
  - Entry/exit signal generation
  - Position sizing
  - Performance tracking
- **vertical_spreads.py**: Bull/bear put/call spreads implementation
- **calendar_spreads.py**: Call/put calendar and diagonal spreads

### Backtester (`src/backtester/`)

- **optopsy_wrapper.py**: Main backtesting engine
  - Data preparation
  - Strategy execution
  - Result aggregation
  - Trade export functionality

### Analysis (`src/analysis/`)

- **metrics.py**: Performance analysis
  - P&L metrics (total, annualized)
  - Risk metrics (Sharpe, Sortino, Calmar ratios)
  - Trade statistics (win rate, profit factor)
  - Visualization tools

### Optimization (`src/optimization/`)

- **parameter_optimizer.py**: Grid search optimization
  - Parameter range definition
  - Systematic backtesting
  - Performance comparison
  - Sensitivity analysis

### Utils (`src/utils/`)

- **black_scholes.py**: Options pricing and Greeks
  - Black-Scholes-Merton model
  - Delta, gamma, theta, vega calculations
  - Dividend-adjusted pricing

## Design Principles

1. **Modular Architecture**: Each component is independent and swappable
2. **Data Source Agnostic**: Easy to switch between synthetic and real data
3. **Strategy Extensibility**: New strategies inherit from BaseStrategy
4. **Configuration-Driven**: All parameters in config.yaml
5. **Test Coverage**: Unit tests for critical components
6. **Type Safety**: Type hints throughout codebase
