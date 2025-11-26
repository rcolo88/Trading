#!/usr/bin/env python
"""
Test Cell 16 optimization with clean output.
This mimics what the notebook does.
"""

import sys
import pandas as pd
import yaml

# Add parent to path (like notebook does)
sys.path.append('.')

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization.parameter_optimizer import ParameterOptimizer

# Load config
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Load data
print("Loading data...")
options_data = load_sample_spy_options_data()
start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
underlying_data = fetch_spy_data(start_date, end_date)

# Create backtester
backtester = OptopsyBacktester(config)

# Create optimizer (exactly like Cell 16)
optimizer = ParameterOptimizer(
    strategy_type='vertical',
    strategy_class=BullPutSpread,
    backtester=backtester,
    options_data=options_data,
    underlying_data=underlying_data,
    base_config=config
)

# Define parameter ranges (exactly like Cell 16)
optimizer.set_parameter_range('dte', min=30, max=45, step=5)           # 4 values
optimizer.set_parameter_range('short_delta', min=0.25, max=0.35, step=0.05)  # 3 values
optimizer.set_parameter_range('profit_target', min=0.40, max=0.60, step=0.10)  # 3 values
# Total combinations: 4 × 3 × 3 = 36

print(f"\n⚡ TESTING CLEAN OUTPUT:")
print("  You should see ONLY the progress bar below")
print("  NO 'Running backtest...' messages")
print("  NO FutureWarning messages\n")

# Run optimization (like Cell 16 but without confirmation for testing)
results = optimizer.run_optimization(
    optimization_metric='sharpe_ratio',
    confirm=False,  # Skip confirmation for testing
    num_samples=3,
    checkpoint_every=10
)

# Analyze results
best = optimizer.get_best_parameters(metric='sharpe_ratio', top_n=5)
print("\n" + "="*60)
print("TOP 5 PARAMETER COMBINATIONS")
print("="*60)
print(best)

print("\n" + "="*60)
print("✓ TEST COMPLETE - Check output above")
print("="*60)
print("Expected: Only progress bar, no repetitive backtest prints")
