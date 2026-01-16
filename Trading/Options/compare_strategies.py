#!/usr/bin/env python3
"""
Strategy Comparison Script

Runs backtests for Iron Condor and Bull Put Spread side-by-side,
comparing performance metrics in high IV environments.

Usage:
    python compare_strategies.py

Output:
    - backtest_results/comparison_*.csv - Detailed trade comparison
    - backtest_results/metrics_*.csv - Performance metrics comparison
"""

import yaml
import pandas as pd
from datetime import datetime
import os

from src.strategies.iron_condor import IronCondor
from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import PerformanceAnalyzer


def run_strategy_backtest(strategy, strategy_name, config, options_data, underlying_data):
    """Run a single strategy backtest and return results."""
    print(f"\n  Running {strategy_name}...")
    print(f"  - Entry DTE: {strategy.entry_config.get('dte_min', 'N/A')}-{strategy.entry_config.get('dte_max', 'N/A')}")
    print(f"  - IV Percentile: {strategy.entry_config.get('iv_percentile_min', 'N/A')}-{strategy.entry_config.get('iv_percentile_max', 'N/A')}")

    backtester = OptopsyBacktester(config)
    results = backtester.run_backtest(
        strategy=strategy,
        options_data=options_data,
        underlying_data=underlying_data
    )

    # Calculate additional metrics
    analyzer = PerformanceAnalyzer(
        equity_curve=results['equity_curve'],
        trades=results['trades']
    )
    metrics = analyzer.calculate_all_metrics(config['backtest']['initial_capital'])

    return results, metrics


def main():
    print("="*70)
    print("Strategy Comparison: Iron Condor vs Bull Put Spread")
    print("="*70)

    # Load configuration
    print("\n1. Loading configuration...")
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Load data
    print("\n2. Loading data...")
    print("   Loading sample options data...")
    options_data = load_sample_spy_options_data()
    print(f"   ✓ Loaded {len(options_data)} option contracts")

    print("   Fetching SPY price data...")
    start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data = fetch_spy_data(start_date, end_date)
    print(f"   ✓ Loaded {len(underlying_data)} days of price data")

    # Run backtests
    print("\n3. Running backtests...")

    # Iron Condor
    print("\n  [1/2] Iron Condor Strategy")
    iron_condor_config = config['strategies']['iron_condor']
    ic_strategy = IronCondor(iron_condor_config)
    ic_results, ic_metrics = run_strategy_backtest(
        ic_strategy, "Iron Condor", config, options_data, underlying_data
    )

    # Bull Put Spread
    print("\n  [2/2] Bull Put Spread Strategy")
    bull_put_config = config['strategies']['bull_put_spread']
    bps_strategy = BullPutSpread(bull_put_config)
    bps_results, bps_metrics = run_strategy_backtest(
        bps_strategy, "Bull Put Spread", config, options_data, underlying_data
    )

    # Compare results
    print("\n4. Comparing Results...")
    print("="*70)
    print(f"{'Metric':<30} {'Iron Condor':>18} {'Bull Put Spread':>18}")
    print("-"*70)

    metrics_to_compare = [
        ('Total Return %', 'total_return_pct', lambda x: f"{x:.2f}%"),
        ('Win Rate', 'win_rate', lambda x: f"{x:.1%}"),
        ('Profit Factor', 'profit_factor', lambda x: f"{x:.2f}"),
        ('Max Drawdown', 'max_drawdown', lambda x: f"{x:.2f}%"),
        ('Sharpe Ratio', 'sharpe_ratio', lambda x: f"{x:.2f}"),
        ('Total Trades', 'total_trades', lambda x: f"{int(x)}"),
        ('Avg Win', 'avg_win', lambda x: f"${x:.2f}"),
        ('Avg Loss', 'avg_loss', lambda x: f"${x:.2f}"),
    ]

    for metric_name, metric_key, format_fn in metrics_to_compare:
        ic_val = ic_results.get(metric_key, ic_metrics.get(metric_key, 'N/A'))
        bps_val = bps_results.get(metric_key, bps_metrics.get(metric_key, 'N/A'))

        ic_str = format_fn(ic_val) if ic_val != 'N/A' else 'N/A'
        bps_str = format_fn(bps_val) if bps_val != 'N/A' else 'N/A'

        print(f"{metric_name:<30} {ic_str:>18} {bps_str:>18}")

    # Entry statistics
    print("\n5. Entry Statistics...")
    print("="*70)
    print(f"{'Stat':<30} {'Iron Condor':>18} {'Bull Put Spread':>18}")
    print("-"*70)

    entry_stats = [
        ('Total Trading Days', 'total_trading_days'),
        ('Days with Entry', 'days_with_entry'),
        ('Entry Rate %', 'daily_entry_rate_pct'),
        ('Days No Signal', 'days_no_signal'),
        ('Days Max Risk Reached', 'days_blocked_by_max_risk'),
    ]

    for stat_name, stat_key in entry_stats:
        ic_val = ic_results.get(stat_key, 'N/A')
        bps_val = bps_results.get(stat_key, 'N/A')

        if isinstance(ic_val, (int, float)):
            if stat_name.endswith('%'):
                ic_str = f"{ic_val:.1f}%"
                bps_str = f"{bps_val:.1f}%"
            else:
                ic_str = f"{int(ic_val)}"
                bps_str = f"{int(bps_val)}"
        else:
            ic_str = str(ic_val)
            bps_str = str(bps_val)

        print(f"{stat_name:<30} {ic_str:>18} {bps_str:>18}")

    # Save comparison results
    print("\n6. Exporting results...")
    os.makedirs('backtest_results', exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Export metrics comparison
    comparison_data = {
        'Strategy': ['Iron Condor', 'Bull Put Spread'],
        'Total Return %': [ic_results['total_return_pct'], bps_results['total_return_pct']],
        'Win Rate': [ic_results['win_rate'], bps_results['win_rate']],
        'Profit Factor': [ic_results['profit_factor'], bps_results['profit_factor']],
        'Max Drawdown': [ic_results['max_drawdown'], bps_results['max_drawdown']],
        'Sharpe Ratio': [ic_metrics.get('sharpe_ratio', 0), bps_metrics.get('sharpe_ratio', 0)],
        'Total Trades': [len(ic_results['trades']), len(bps_results['trades'])],
        'Avg Win': [ic_results['avg_win'], bps_results['avg_win']],
        'Avg Loss': [ic_results['avg_loss'], bps_results['avg_loss']],
    }

    comparison_df = pd.DataFrame(comparison_data)
    comparison_file = f"backtest_results/strategy_comparison_{timestamp}.csv"
    comparison_df.to_csv(comparison_file, index=False)
    print(f"   ✓ Comparison: {comparison_file}")

    # Export trades for both strategies
    ic_trades_file = f"backtest_results/trades_iron_condor_{timestamp}.csv"
    ic_results['trades'].to_csv(ic_trades_file, index=False)
    print(f"   ✓ Iron Condor trades: {ic_trades_file}")

    bps_trades_file = f"backtest_results/trades_bull_put_spread_{timestamp}.csv"
    bps_results['trades'].to_csv(bps_trades_file, index=False)
    print(f"   ✓ Bull Put Spread trades: {bps_trades_file}")

    # Export equity curves
    ic_equity = ic_results['equity_curve'].copy()
    ic_equity['strategy'] = 'Iron Condor'
    bps_equity = bps_results['equity_curve'].copy()
    bps_equity['strategy'] = 'Bull Put Spread'

    equity_combined = pd.concat([ic_equity, bps_equity], ignore_index=True)
    equity_file = f"backtest_results/equity_curves_comparison_{timestamp}.csv"
    equity_combined.to_csv(equity_file, index=False)
    print(f"   ✓ Equity curves: {equity_file}")

    # Print summary
    print("\n" + "="*70)
    print("Comparison Summary")
    print("="*70)
    print(f"\nIron Condor Performance:")
    print(f"  Total Return: {ic_results['total_return_pct']:.2f}%")
    print(f"  Win Rate: {ic_results['win_rate']:.1%}")
    print(f"  Sharpe Ratio: {ic_metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  Total Trades: {len(ic_results['trades'])}")

    print(f"\nBull Put Spread Performance:")
    print(f"  Total Return: {bps_results['total_return_pct']:.2f}%")
    print(f"  Win Rate: {bps_results['win_rate']:.1%}")
    print(f"  Sharpe Ratio: {bps_metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  Total Trades: {len(bps_results['trades'])}")

    # Calculate advantage
    ic_sharpe = ic_metrics.get('sharpe_ratio', 0)
    bps_sharpe = bps_metrics.get('sharpe_ratio', 0)

    if ic_sharpe > bps_sharpe:
        advantage = ((ic_sharpe - bps_sharpe) / abs(bps_sharpe) * 100) if bps_sharpe != 0 else 0
        print(f"\n✓ Iron Condor has {advantage:.1f}% higher Sharpe ratio")
    else:
        advantage = ((bps_sharpe - ic_sharpe) / abs(ic_sharpe) * 100) if ic_sharpe != 0 else 0
        print(f"\n✓ Bull Put Spread has {advantage:.1f}% higher Sharpe ratio")

    print("\n" + "="*70)
    print("Next steps:")
    print("1. Review detailed trades in backtest_results/")
    print("2. Analyze equity curves in equity_curves_comparison_*.csv")
    print("3. Run optimize_iron_condor.py for parameter optimization")
    print("4. Update CHANGELOG.md with findings")


if __name__ == '__main__':
    main()
