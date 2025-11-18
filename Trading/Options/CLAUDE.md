# SPY/SPX Options Backtesting System

## Project Goal

Python-based backtesting framework for options trading strategies on SPY/SPX, focusing on:
- **Vertical Spreads**: Bull Put, Bull Call (credit/debit spreads)
- **Calendar Spreads**: Call/Put time spreads
- **Performance Analysis**: Sharpe ratio, win rate, max drawdown, Kelly Criterion sizing

**Status**: 🚀 Ready for Backtesting - Vertical & Calendar Spreads Implemented

## Quick Start

1. Generate synthetic data: `python generate_synthetic_data.py`
2. Configure strategies: `config/config.yaml`
3. Run backtests: `notebooks/backtest_analysis.ipynb`

## Documentation

- [Architecture](guides/ARCHITECTURE.md) - System design and directory structure
- [Data Guide](guides/DATA_GUIDE.md) - Data sources and synthetic generation
- [Data Validation](guides/DATA_VALIDATION.md) - Quality assurance and delta validation
- [Strategies](guides/STRATEGIES.md) - Strategy implementations
- [Workflows](guides/WORKFLOWS.md) - Kelly sizing, trade export, backtesting
- [Metrics](guides/METRICS.md) - Performance metrics
- [Research](guides/RESEARCH.md) - Library notes, known issues, roadmap

## Important Reminders

📝 **Keep CHANGELOG.md Updated**: Document all significant changes, bug fixes, and features

🔄 **Push to GitHub Regularly**: Commit and push changes frequently to maintain backup and version history

See [CHANGELOG.md](CHANGELOG.md) for complete version history.
