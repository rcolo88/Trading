# Research Notes & Development

## Optopsy Library

### Overview

- **GitHub**: github.com/michaelchu/optopsy
- **Stars**: ~1.2k
- **Status**: Maintained, last update 2024
- **License**: MIT

### Key Features

- Built-in support for vertical spreads, iron condors, straddles, strangles
- Integrates seamlessly with Pandas workflow
- Flexible strategy definition
- Statistical analysis focused
- Well-documented API

### Why Optopsy?

1. **Proven Framework**: Mature library with active community
2. **Vertical Spread Support**: Core strategies already implemented
3. **Pandas Integration**: Works with our data pipeline
4. **Faster Development**: Don't reinvent the wheel

## Alternative Approaches Considered

### 1. OptionSuite

- **Status**: Less mature
- **Pros**: Has put vertical spread examples
- **Cons**: Smaller community, less documentation
- **Decision**: Rejected in favor of Optopsy

### 2. Custom Framework

- **Pros**: Full control, tailored to exact needs
- **Cons**: Significant development time, potential bugs
- **Decision**: Rejected - use Optopsy for proven framework

### 3. QuantConnect Platform

- **Pros**: Free data, integrated backtesting
- **Cons**: Locked into their platform, limited flexibility
- **Decision**: Use for data only, not backtesting engine

## Data Source Research

### Free Options (Currently Used)

1. **Synthetic Generation**: Black-Scholes model (primary method)
   - Pros: Free, unlimited, validated accuracy
   - Cons: Model limitations, not real market data
   - Best for: Strategy development, parameter optimization

2. **OptionsDX Free Tier**: Real historical data
   - Pros: Real market data, pre-calculated Greeks
   - Cons: Limited selection, slow updates
   - Best for: Validation of synthetic results

3. **Polygon.io Free Tier**: 2 years EOD data
   - Pros: Real data, official API
   - Cons: 5 calls/min rate limit, limited depth
   - Best for: Small-scale validation

### Paid Options (Future Upgrade)

1. **Polygon.io** ($200+/month)
   - Best overall paid option
   - Minute-level historical options data
   - Comprehensive coverage
   - Professional-grade API

2. **Databento**
   - Professional-grade options data
   - High-frequency data available
   - Enterprise pricing

3. **ThetaData**
   - Specialized options historical data
   - Good community support
   - Mid-tier pricing

### Not Recommended

- **Schwab Developer API**: No historical options data for expired contracts
- **Yahoo Finance**: No historical options data
- **CBOE DataShop**: Very limited free tier

## Known Issues and Limitations

### Data Limitations

1. **Historical Options Data**: Free sources are limited
   - 3-5 years of comprehensive SPY options data is difficult to obtain for free
   - Currently using synthetic generation as primary source
   - Validated accuracy: 88% R² in normal markets

2. **Data Granularity**: Free sources provide daily or hourly data vs tick-level
   - Hour-level data from QuantConnect may miss intraday volatility
   - Acceptable for most strategies but limits high-frequency testing

3. **Survivorship Bias**: Free datasets may not include all expired contracts
   - Could skew results if incomplete
   - Synthetic data avoids this issue

### Technical Debt

- **Data quality checks**: Need to establish validation pipeline
- **Transaction cost assumptions**: Current estimates need market validation
- **Slippage models**: Using estimates, not actual market slippage
- **Test coverage**: Need more unit tests for edge cases

## Future Enhancements

### Short-term Roadmap

- [ ] Implement diagonal spread strike selection logic (different strikes)
- [ ] Add iron condor and iron butterfly strategies
- [ ] Implement rolling strategies (close and reopen positions)
- [ ] Add volatility-based entry signals (VIX, IV rank)
- [ ] Create paper trading integration with Schwab API
- [ ] Optimize calendar spread exit logic for theta decay
- [ ] Add walk-forward analysis
- [ ] Implement Monte Carlo simulation

### Long-term Vision

- [ ] Machine learning for parameter optimization
- [ ] Real-time monitoring dashboard
- [ ] Multi-asset backtesting (QQQ, IWM, individual stocks)
- [ ] Portfolio-level risk management
- [ ] Integration with live trading (Schwab API)
- [ ] Options pricing model validation (compare historical vs theoretical)
- [ ] Volatility surface modeling
- [ ] Advanced Greeks tracking and hedging
- [ ] Performance attribution analysis
- [ ] Risk factor decomposition

## Contributing Guidelines

Since this is a personal project, notes for future reference:

### Code Quality

- **Document all assumptions**: Transaction costs, slippage, etc.
- **Use type hints**: Better code clarity and IDE support
- **Comment complex logic**: Especially Greek calculations and risk metrics
- **Write tests**: Unit tests for strategy logic

### Architecture

- **Keep data fetchers modular**: Easy data source swapping
- **Strategy extensibility**: New strategies inherit from BaseStrategy
- **Configuration-driven**: Parameters in config.yaml, not hardcoded
- **Separation of concerns**: Clear boundaries between modules

### Testing

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test end-to-end backtesting workflow
- **Validation tests**: Compare synthetic vs real data when available
- **Performance tests**: Ensure backtests complete in reasonable time

### Documentation

- **Update CHANGELOG.md**: Document all significant changes
- **Keep guides current**: Update relevant guide files when features change
- **Example notebooks**: Provide working examples for common tasks
- **Inline comments**: Explain "why" not just "what"

## References

### Documentation

- **Optopsy**: [PyPI](https://pypi.org/project/optopsy/)
- **Schwab Developer API**: [developer.schwab.com](https://developer.schwab.com/)
- **py_vollib**: Black-Scholes Greeks library ([GitHub](https://github.com/vollib/py_vollib))

### Educational Resources

- **CBOE Options Institute**: Professional options education
- **Options Industry Council**: Free courses and tools
- **QuantStart**: Backtesting best practices
- **PyQuant News**: Python quant finance

### Academic Papers

- Black-Scholes-Merton Model: [Wikipedia](https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model)
- Kelly Criterion: Optimal position sizing mathematics
- Options pricing: Comparison of theoretical vs market prices

## Development Progress Tracking

### Phase 1: Foundation ✅ Complete
- [x] Project planning and architecture
- [x] CLAUDE.md documentation (now streamlined)
- [x] Requirements.txt and environment setup
- [x] Directory structure creation
- [x] Configuration system

### Phase 2: Data Infrastructure ✅ Complete
- [x] Data fetcher modules
- [x] Data validation and cleaning
- [x] Synthetic data generation (2+ years SPY)
- [x] Data format standardization for Optopsy
- [x] Delta validation (100% accuracy)

### Phase 3: Strategy Implementation ✅ Complete
- [x] Base strategy template
- [x] Vertical spread strategies
- [x] Calendar spread strategies
- [x] Entry/exit logic
- [x] Position sizing and risk management

### Phase 4: Backtesting Engine ✅ Complete
- [x] Optopsy integration wrapper
- [x] Transaction cost modeling
- [x] Slippage assumptions
- [x] Portfolio-level backtesting
- [x] Trade export functionality

### Phase 5: Analysis & Optimization 🔄 In Progress
- [x] Performance metrics calculation
- [x] Visualization dashboard (notebooks)
- [x] Parameter optimization (grid search)
- [ ] Walk-forward testing
- [ ] Monte Carlo simulation

### Phase 6: Documentation & Testing 🔄 In Progress
- [ ] Unit tests (partial coverage)
- [ ] Integration tests
- [x] User guides (this documentation)
- [x] Example notebooks
