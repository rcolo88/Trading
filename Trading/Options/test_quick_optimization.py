#!/usr/bin/env python3
"""Quick test to debug optimization issue."""

import sys
from pathlib import Path
from typing import Dict, Any
import yaml
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization.parameter_optimizer import ParameterOptimizer
from src.optimization.results_compiler import compile_results

print("\n" + "="*70)
print("QUICK OPTIMIZATION TEST")
print("="*70 + "\n")

# Load configuration
print("1. Loading configuration...")
with open('config/config.yaml', 'r') as f:
    config: Dict[str, Any] = yaml.safe_load(f)
print("   ✓ Config loaded")

# Load data
print("\n2. Loading data...")
options_data: pd.DataFrame = load_sample_spy_options_data()
start_date: str = options_data['quote_date'].min().strftime('%Y-%m-%d')
end_date: str = options_data['quote_date'].max().strftime('%Y-%m-%d')
underlying_data: pd.DataFrame = fetch_spy_data(start_date, end_date)
print(f"   ✓ Data loaded")

# Create optimizer
print("\n3. Creating optimizer...")
backtester: OptopsyBacktester = OptopsyBacktester(config)
optimizer: ParameterOptimizer = ParameterOptimizer(
    strategy_type='vertical',
    strategy_class=BullPutSpread,
    backtester=backtester,
    options_data=options_data,
    underlying_data=underlying_data,
    base_config=config
)

# Minimal parameter ranges
optimizer.set_parameter_range('dte', min=30, max=40, step=10)
optimizer.set_parameter_range('short_delta', min=0.25, max=0.35, step=0.10)
print(f"   ✓ Optimizer configured with {optimizer.get_total_combinations()} combinations")

# Run optimization
print("\n4. Running optimization...")
results: pd.DataFrame = optimizer.run_optimization(
    mode='grid',
    optimization_metric='sharpe_ratio',
    confirm=False,
    num_samples=1
)
print(f"   ✓ Optimization complete: {len(results)} results")
print(f"   Results columns: {list(results.columns)}")
print(f"   Results shape: {results.shape}")

# Save results
print("\n5. Saving results...")
results_dir: Path = Path('optimization_results')
results_dir.mkdir(exist_ok=True)

from datetime import datetime
timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S')
filename: str = f'BullPutSpread_TEST_{timestamp}.csv'
filepath: Path = results_dir / filename

results.to_csv(filepath, index=False)
print(f"   ✓ Results saved to: {filepath}")

# Verify file exists
if filepath.exists():
    print(f"   ✓ File verified: {filepath.stat().st_size} bytes")
else:
    print(f"   ✗ ERROR: File not found!")

# Test compilation
print("\n6. Testing compilation...")
master_path: Path = compile_results(
    new_results=results,
    strategy_name='BullPutSpread',
    config=config
)
print(f"   ✓ Compiled to: {master_path}")

# Verify compiled file
if master_path.exists():
    print(f"   ✓ Compiled file verified: {master_path.stat().st_size} bytes")
else:
    print(f"   ✗ ERROR: Compiled file not found!")

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70 + "\n")
