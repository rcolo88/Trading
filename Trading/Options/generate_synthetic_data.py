#!/usr/bin/env python3
"""
Generate Synthetic Options Data

This script generates realistic historical options data using the Black-Scholes
model based on actual SPY prices from Yahoo Finance.

Usage:
    python generate_synthetic_data.py

The script will:
1. Fetch 2 years of SPY price data from Yahoo Finance
2. Calculate historical volatility
3. Generate options chains using Black-Scholes pricing
4. Save the data to CSV for backtesting

Output:
    data/processed/SPY_synthetic_options_YYYY-MM-DD_YYYY-MM-DD.csv
"""

import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data_fetchers.synthetic_generator import (
    SyntheticOptionsGenerator,
    synthetic_data_filename,
    _load_options_config,
)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate synthetic options data')
    parser.add_argument('-y', '--yes', action='store_true',
                       help='Skip confirmation prompt')
    args = parser.parse_args()

    print("\n" + "="*70)
    print("SYNTHETIC OPTIONS DATA GENERATOR")
    print("="*70)
    print("\nThis script generates realistic options data using Black-Scholes pricing")
    print("based on actual historical SPY prices from Yahoo Finance.")
    print("\nData frequency: END-OF-DAY prices (one data point per trading day)")
    print("Volatility source: VIX (implied volatility) - more realistic than historical vol")
    print("\nWARNING: This may take several minutes to complete.")
    print("The script will download ~2 years of price data and generate options chains.")

    # Configuration -- single source of truth lives in config/config.yaml -> synthetic_data
    config = _load_options_config()
    sd = config["synthetic_data"]
    symbol = sd["symbol"]
    start_date = sd["start_date"]
    end_date = sd["end_date"]
    max_dte_ = sd["max_dte"]

    # Derive the output path from the SAME helper the loaders use, so the file we
    # write is exactly the file they look for.
    output_path = f"data/processed/{synthetic_data_filename(config)}"

    print(f"\nConfiguration:")
    print(f"  Symbol: {symbol}")
    print(f"  Date range: {start_date} to {end_date}")
    print(f"  Data frequency: End-of-Day (EOD)")
    print(f"  Include weekly expirations: Yes")
    print(f"  Maximum DTE:  {max_dte_} days")

    # User confirmation (skip if -y flag is used)
    if not args.yes:
        try:
            response = input("\nProceed with data generation? (y/n): ")
            if response.lower() != 'y':
                print("Cancelled by user.")
                return
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
    else:
        print("\nProceeding with data generation (auto-confirmed)...")

    # Initialize generator
    print("\nInitializing generator...")
    generator = SyntheticOptionsGenerator(
        symbol=symbol,
        risk_free_rate=0.04,      # 4% annual
        dividend_yield=0.015,     # 1.5% for SPY
        volatility_window=30,     # 30-day rolling volatility
        use_vix_for_iv=True       # Use VIX as IV proxy for realistic pricing
    )

    # Generate data
    try:
        options_df = generator.generate_historical_chains(
            start_date=start_date,
            end_date=end_date,
            include_weekly=True,
            max_dte=max_dte_,
            save_to_csv=True,
            output_path=output_path
        )

        print("\n" + "="*70)
        print("SUCCESS!")
        print("="*70)
        print(f"\nGenerated {len(options_df):,} option contracts")
        print(f"\nThe data has been saved to:")
        print(f"  {output_path}")

        print("\nData Summary:")
        print(f"  Calls: {len(options_df[options_df['option_type']=='call']):,}")
        print(f"  Puts: {len(options_df[options_df['option_type']=='put']):,}")
        print(f"  Trading days: {options_df['quote_date'].nunique()}")
        print(f"  Expirations: {options_df['expiration'].nunique()}")
        print(f"  Strike range: ${options_df['strike'].min():.0f} - ${options_df['strike'].max():.0f}")

        print("\nNext Steps:")
        print("1. Run: python example_backtest.py")
        print("2. Or open: notebooks/backtest_analysis.ipynb")
        print("3. The backtest will automatically use this synthetic data")

        print("\n" + "="*70)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTroubleshooting:")
        print("1. Check your internet connection (needed for Yahoo Finance data)")
        print("2. Ensure required libraries are installed: pip install -r requirements.txt")
        print("3. Try a smaller date range if the dataset is too large")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
