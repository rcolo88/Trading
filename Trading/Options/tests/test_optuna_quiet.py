#!/usr/bin/env python3
"""
Quick test to verify Optuna logging suppression works.
Should only show progress bar, not trial completion messages.
"""

import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization.parameter_optimizer import ParameterOptimizer

print("\n" + "="*70)
print("TESTING OPTUNA QUIET MODE")
print("="*70)
print("You should see ONLY the progress bar below,")
print("NOT any '[I 2025-11-26 ...] Trial X finished...' messages")
print("="*70 + "\n")

# Load config and data
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

options_data = load_sample_spy_options_data()
start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
underlying_data = fetch_spy_data(start_date, end_date)

# Create optimizer
backtester = OptopsyBacktester(config)
optimizer = ParameterOptimizer(
    strategy_type='vertical',
    strategy_class=BullPutSpread,
    backtester=backtester,
    options_data=options_data,
    underlying_data=underlying_data,
    base_config=config
)

# Small parameter space for quick test
optimizer.set_parameter_range('dte', min=30, max=40, step=10)
optimizer.set_parameter_range('short_delta', min=0.25, max=0.35, step=0.10)

print("Running 5 Optuna trials...\n")

# Run Optuna optimization
results = optimizer.run_optimization(
    mode='optuna',
    n_trials=5,
    optimization_metric='sharpe_ratio',
    verbose=True
)

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
print("If you saw NO '[I ...]' messages above, the logging is suppressed ✓")
print("If you saw '[I ...]' messages, the suppression didn't work ✗")
print("="*70 + "\n")
