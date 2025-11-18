# Performance Metrics

## Primary Metrics

### Profit & Loss Metrics

- **Total P&L**: Cumulative profit/loss over the entire backtest period
- **Total Return %**: (Final Value - Initial Capital) / Initial Capital × 100
- **Annualized Return**: Yearly return percentage, compounded
  - Formula: `((Final Value / Initial Capital) ^ (1 / Years)) - 1`

### Risk-Adjusted Returns

- **Sharpe Ratio**: Risk-adjusted return measuring excess return per unit of volatility
  - Formula: `(Return - Risk-Free Rate) / Standard Deviation of Returns`
  - Annualized using √252 for daily returns
  - Higher is better (> 1.0 is good, > 2.0 is excellent)

- **Sortino Ratio**: Similar to Sharpe but only penalizes downside volatility
  - Uses downside deviation instead of total standard deviation
  - Better measure for strategies with asymmetric returns

- **Calmar Ratio**: Return divided by maximum drawdown
  - Formula: `Annualized Return / Max Drawdown`
  - Measures return per unit of worst-case risk

### Drawdown Metrics

- **Max Drawdown**: Largest peak-to-trough decline in account value
  - Formula: `(Trough Value - Peak Value) / Peak Value × 100`
  - Critical for understanding worst-case scenarios

- **Drawdown Duration**: Length of time to recover from drawdown
- **Current Drawdown**: Current account value vs. all-time high

### Trade Statistics

- **Win Rate**: Percentage of profitable trades
  - Formula: `(Winning Trades / Total Trades) × 100`
  - Typical target: 60-80% for credit spreads

- **Average Win**: Mean profit on winning trades
- **Average Loss**: Mean loss on losing trades

- **Profit Factor**: Ratio of gross profits to gross losses
  - Formula: `Total Gross Profit / Total Gross Loss`
  - > 1.0 means profitable, > 2.0 is very good

- **Payoff Ratio**: Average Win / Average Loss
  - Used in Kelly Criterion calculation
  - Higher ratio allows for lower win rate

## Secondary Metrics

### Greeks Exposure

Track portfolio-level Greeks over time:

- **Delta**: Directional exposure (how much position moves with underlying)
- **Gamma**: Rate of change of delta (risk near expiration)
- **Theta**: Time decay (daily P&L from passage of time)
- **Vega**: Volatility exposure (P&L from IV changes)

### Time-Based Metrics

- **Trade Duration**: Average days in trade
  - For spreads: typically 7-30 days
  - Longer duration = more capital tied up

- **Monthly Returns**: Performance breakdown by month
  - Identify seasonal patterns
  - Check consistency

- **Yearly Returns**: Annual performance summary
  - Compound annual growth rate (CAGR)
  - Year-over-year comparison

### Correlation Metrics

- **Correlation to SPY**: How closely strategy tracks the underlying
  - -1.0 to +1.0 range
  - Near 0 = market-neutral
  - Positive = bullish bias
  - Negative = bearish bias

- **Beta**: Systematic risk relative to SPY
  - 1.0 = moves with market
  - < 1.0 = less volatile than market
  - > 1.0 = more volatile than market

## Interpreting Results

### Good Backtest Results (Benchmarks)

- **Sharpe Ratio**: > 1.0 (excellent if > 2.0)
- **Win Rate**: 60-80% for credit spreads, 40-60% for debit spreads
- **Max Drawdown**: < 20% (< 10% is excellent)
- **Profit Factor**: > 1.5 (> 2.0 is very good)
- **Calmar Ratio**: > 0.5 (> 1.0 is excellent)

### Red Flags

- **Too high win rate (>95%)**: May indicate look-ahead bias or overfitting
- **Too high Sharpe (>4)**: Likely unrealistic, check for data errors
- **Large max drawdown (>30%)**: Strategy may be too risky
- **Low profit factor (<1.2)**: Strategy may not be robust
- **Very few trades (<50)**: Not enough statistical significance

## Implementation

Metrics are calculated using the `PerformanceAnalyzer` class in `src/analysis/metrics.py`:

```python
from src.analysis.metrics import PerformanceAnalyzer

analyzer = PerformanceAnalyzer(
    equity_curve=results['equity_curve'],
    trades=results['trades']
)

# Calculate all metrics
metrics = analyzer.calculate_all_metrics(initial_capital=10000)

# Generate report
report = analyzer.generate_report(metrics)
print(report)

# Visualizations
analyzer.plot_equity_curve()
analyzer.plot_drawdown()
analyzer.plot_monthly_returns()
analyzer.plot_trade_distribution()
```

See `notebooks/backtest_analysis.ipynb` for interactive examples.
