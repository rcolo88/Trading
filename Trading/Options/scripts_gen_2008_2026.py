#!/usr/bin/env python3
"""One-off: generate the full 2008-2026 continuous synthetic dataset (for the CAGR/Sharpe-over-
the-full-span question), on the skew+spread+level-corrected generator. Not a permanent script."""
import sys
sys.path.insert(0, ".")
from src.data_fetchers.synthetic_generator import SyntheticOptionsGenerator, synthetic_data_filename

cfg_dates = {"symbol": "SPY", "start_date": "2008-01-01", "end_date": "2026-07-10", "max_dte": 90}
fname = synthetic_data_filename({"synthetic_data": cfg_dates})
print("Target file:", fname)

gen = SyntheticOptionsGenerator(symbol="SPY", risk_free_rate=0.04, dividend_yield=0.015,
                                 volatility_window=30, use_vix_for_iv=True)
gen.generate_historical_chains(
    start_date="2008-01-01", end_date="2026-07-10",
    include_weekly=True, max_dte=90, save_to_csv=True,
    output_path=f"data/processed/{fname}",
)
print("DONE")
