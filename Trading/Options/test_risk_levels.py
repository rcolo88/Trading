#!/usr/bin/env python
"""Test different max_risk_percent values to find optimal setting."""

import yaml
from src.strategies.calendar_spreads import CallCalendarSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

# Load data once
options_data = load_sample_spy_options_data()
start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
underlying_data = fetch_spy_data(start_date, end_date)

# Test different risk levels
risk_levels = [50, 60, 65, 70, 75, 80, 100]

print("="*70)
print("TESTING DIFFERENT MAX_RISK_PERCENT VALUES")
print("="*70)
print(f"{'Max Risk %':<15} {'Return %':<15} {'Trades':<10} {'Win Rate %':<15}")
print("-"*70)

for risk_pct in risk_levels:
    # Load and modify config
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    config['position_sizing']['max_risk_percent'] = float(risk_pct)

    # Run backtest
    call_calendar_strategy = CallCalendarSpread(config['strategies']['call_calendar'])
    backtester = OptopsyBacktester(config)
    results = backtester.run_backtest(
        strategy=call_calendar_strategy,
        options_data=options_data,
        underlying_data=underlying_data
    )

    print(f"{risk_pct:<15} {results['total_return_pct']:<15.2f} {results['total_trades']:<10} {results['win_rate_pct']:<15.2f}")

print("="*70)
print("Target: 597% return with 146 trades")
print("="*70)
