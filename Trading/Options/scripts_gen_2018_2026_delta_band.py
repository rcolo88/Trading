#!/usr/bin/env python3
"""One-off: regenerate the 2018-2026 synthetic dataset with the 2026-08-11 pricing fixes --
bounded skew-tail extrapolation (_iv_surface) + $1 vol-adaptive delta-band strike grid
(generate_delta_band_strikes), replacing the old $5/+-$100 fixed grid every prior dataset in this
project used. Deliberately does NOT touch config.yaml's project-wide default (still 'fixed', so
every other optimizer's reference dataset is untouched) -- overrides grid_mode in memory only.
synthetic_data_filename() encodes the grid mode, so this writes to a NEW file
(SPY_synthetic_options_2018-01-01_2026-07-10_db1.csv), never overwriting the existing coarse-grid
file. Not a permanent script."""
import sys
sys.path.insert(0, ".")
from src.data_fetchers.synthetic_generator import SyntheticOptionsGenerator, synthetic_data_filename

cfg_dates = {
    "symbol": "SPY", "start_date": "2018-01-01", "end_date": "2026-07-10", "max_dte": 90,
    "grid_mode": "delta_band",
    "fine_interval": 1.0, "coarse_interval": 5.0,
    "fine_min_abs_delta": 0.02, "fine_max_abs_delta": 0.60, "coarse_extra_frac": 0.35,
}
fname = synthetic_data_filename({"synthetic_data": cfg_dates})
print("Target file:", fname)

gen = SyntheticOptionsGenerator(symbol="SPY", risk_free_rate=0.04, dividend_yield=0.015,
                                 volatility_window=30, use_vix_for_iv=True)
gen.generate_historical_chains(
    start_date="2018-01-01", end_date="2026-07-10",
    include_weekly=True, max_dte=90, save_to_csv=True,
    output_path=f"data/processed/{fname}",
    grid_mode="delta_band",
    fine_interval=1.0, coarse_interval=5.0,
    fine_min_abs_delta=0.02, fine_max_abs_delta=0.60, coarse_extra_frac=0.35,
)
print("DONE")
