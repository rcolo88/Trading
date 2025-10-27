#!/usr/bin/env python3
"""
Example backtest script demonstrating basic usage.

This script shows how to:
1. Load configuration
2. Fetch/load data
3. Create a strategy
4. Run a backtest
5. Analyze results
"""

import yaml
from datetime import datetime
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread, BearCallSpread
from src.strategies.calendar_spreads import CallCalendarSpread, PutCalendarSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import PerformanceAnalyzer


def main():
    print("="*70)
    print("Options Backtesting - Example Script")
    print("="*70)

    # 1. Load configuration
    print("\n1. Loading configuration...")
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    print(f"   Symbol: {config['underlying']['symbol']}")
    print(f"   Initial capital: ${config['backtest']['initial_capital']:,}")

    # 2. Load data
    print("\n2. Loading data...")
    print("   Loading sample options data...")
    options_data = load_sample_spy_options_data()
    print(f"   ✓ Loaded {len(options_data)} option contracts")

    print("   Fetching SPY price data from Yahoo Finance...")
    start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data = fetch_spy_data(start_date, end_date)
    print(f"   ✓ Loaded {len(underlying_data)} days of price data")

    # 3. Create strategy
    # You can choose which strategy to test by uncommenting the desired option:

    # Option 1: Bull Put Spread (Vertical Spread - Credit)
    print("\n3. Creating Bull Put Spread strategy...")
    bull_put_config = config['strategies']['bull_put_spread']
    strategy = BullPutSpread(bull_put_config)
    print(f"   Strategy: {strategy.name}")
    print(f"   Entry DTE range: {bull_put_config['entry']['dte_min']}-{bull_put_config['entry']['dte_max']}")
    print(f"   Short delta: {bull_put_config['entry']['short_delta']}")
    print(f"   Long delta: {bull_put_config['entry']['long_delta']}")

    # Option 2: Call Calendar Spread (Time Spread - Debit)
    # Uncomment the following lines to test calendar spreads instead:
    # print("\n3. Creating Call Calendar Spread strategy...")
    # call_calendar_config = config['strategies']['call_calendar']
    # strategy = CallCalendarSpread(call_calendar_config)
    # print(f"   Strategy: {strategy.name}")
    # print(f"   Near DTE: {call_calendar_config['entry']['near_dte']}")
    # print(f"   Far DTE: {call_calendar_config['entry']['far_dte']}")
    # print(f"   Strike selection: {call_calendar_config['entry']['strike_selection']}")

    # Option 3: Put Calendar Spread (Time Spread - Debit)
    # print("\n3. Creating Put Calendar Spread strategy...")
    # put_calendar_config = config['strategies']['put_calendar']
    # strategy = PutCalendarSpread(put_calendar_config)
    # print(f"   Strategy: {strategy.name}")
    # print(f"   Near DTE: {put_calendar_config['entry']['near_dte']}")
    # print(f"   Far DTE: {put_calendar_config['entry']['far_dte']}")

    # 4. Run backtest
    print("\n4. Running backtest...")
    print("-" * 70)
    backtester = OptopsyBacktester(config)
    results = backtester.run_backtest(
        strategy=strategy,
        options_data=options_data,
        underlying_data=underlying_data
    )

    # 5. Display results
    print("\n5. Results Summary")
    print("-" * 70)
    backtester.print_results(results)

    # 6. Detailed analysis
    print("\n6. Detailed Performance Analysis")
    print("-" * 70)
    analyzer = PerformanceAnalyzer(
        equity_curve=results['equity_curve'],
        trades=results['trades']
    )

    metrics = analyzer.calculate_all_metrics(config['backtest']['initial_capital'])
    report = analyzer.generate_report(metrics)
    print(report)

    # 7. Export results
    print("\n7. Exporting results...")
    output_dir = 'data/processed'

    # Save equity curve
    equity_file = f"{output_dir}/equity_curve_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    results['equity_curve'].to_csv(equity_file, index=False)
    print(f"   ✓ Equity curve saved to: {equity_file}")

    # Save trades
    if len(results['trades']) > 0:
        trades_file = f"{output_dir}/trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        results['trades'].to_csv(trades_file, index=False)
        print(f"   ✓ Trades saved to: {trades_file}")

    # Save metrics
    metrics_file = f"{output_dir}/metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    pd.DataFrame([metrics]).to_csv(metrics_file, index=False)
    print(f"   ✓ Metrics saved to: {metrics_file}")

    print("\n" + "="*70)
    print("Backtest complete!")
    print("="*70)
    print("\nNext steps:")
    print("1. Review the results above")
    print("2. Check exported CSV files in data/processed/")
    print("3. Run notebooks/backtest_analysis.ipynb for interactive analysis")
    print("4. Modify config/config.yaml to test different parameters")


if __name__ == '__main__':
    main()
