"""
Example: Running backtest and exporting trade details to CSV/XLSX.

This script demonstrates how to:
1. Run a backtest for a strategy
2. Export detailed trade information to a file
3. Review individual trade details

The exported file includes:
- Underlying price and VIX at entry/exit
- Strike prices, deltas, prices for each leg
- Position direction (+1 long, -1 short)
- Expiration dates
- P&L and exit reasons
"""

import yaml
from src.strategies.vertical_spreads import BullPutSpread
from src.strategies.calendar_spreads import CallCalendarSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

# Load configuration
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Load data
print("Loading options data...")
options_data = load_sample_spy_options_data()

start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
underlying_data = fetch_spy_data(start_date, end_date)

print(f"Data loaded: {len(options_data)} option contracts\n")

# Example 1: Bull Put Spread with CSV export
print("="*80)
print("EXAMPLE 1: Bull Put Spread - CSV Export")
print("="*80)

bull_put_config = config['strategies']['bull_put_spread']
bull_put_strategy = BullPutSpread(bull_put_config)

backtester = OptopsyBacktester(config)
results = backtester.run_backtest(
    strategy=bull_put_strategy,
    options_data=options_data,
    underlying_data=underlying_data
)

backtester.print_results(results)

# Export to CSV
print("\nExporting trades to CSV...")
filepath = backtester.export_trades(results, format='csv')
print(f"Trades exported to: {filepath}")
print(f"Review this file to see detailed information about each trade.\n")

# Example 2: Call Calendar Spread with XLSX export
print("="*80)
print("EXAMPLE 2: Call Calendar Spread - XLSX Export")
print("="*80)

call_calendar_config = config['strategies']['call_calendar']
call_calendar_strategy = CallCalendarSpread(call_calendar_config)

backtester = OptopsyBacktester(config)
results = backtester.run_backtest(
    strategy=call_calendar_strategy,
    options_data=options_data,
    underlying_data=underlying_data
)

backtester.print_results(results)

# Export to Excel
print("\nExporting trades to Excel...")
filepath = backtester.export_trades(results, format='xlsx')
print(f"Trades exported to: {filepath}")
print(f"Open this file in Excel to review trade details with formatting.\n")

print("="*80)
print("TRADE EXPORT COMPLETE")
print("="*80)
print("\nExported files contain the following information:")
print("  1. Underlying price and VIX at entry/exit")
print("  2. Day trade was executed")
print("  3. Contract expiration dates (near/far for calendar, single for vertical)")
print("  4. Deltas of each contract")
print("  5. Prices of each leg")
print("  6. Position direction: +1 (long/buy) or -1 (short/sell)")
print("  7. P&L, commissions, and exit reasons")
print("\nCheck the 'backtest_results/' directory for your exported files.")
