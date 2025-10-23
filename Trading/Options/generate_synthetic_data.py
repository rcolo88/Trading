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
from datetime import datetime, timedelta

# Add src to path
sys.path.append('src')

from data_fetchers.synthetic_generator import SyntheticOptionsGenerator


def main():
    print("\n" + "="*70)
    print("SYNTHETIC OPTIONS DATA GENERATOR")
    print("="*70)
    print("\nThis script generates realistic options data using Black-Scholes pricing")
    print("based on actual historical SPY prices from Yahoo Finance.")
    print("\nWARNING: This may take several minutes to complete.")
    print("The script will download ~2 years of price data and generate options chains.")

    # Configuration
    symbol = "SPY"
    start_date = "2022-01-01"
    end_date = "2024-12-31"

    print(f"\nConfiguration:")
    print(f"  Symbol: {symbol}")
    print(f"  Date range: {start_date} to {end_date}")
    print(f"  Include weekly expirations: Yes")
    print(f"  Maximum DTE: 60 days")

    # User confirmation
    response = input("\nProceed with data generation? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled by user.")
        return

    # Initialize generator
    print("\nInitializing generator...")
    generator = SyntheticOptionsGenerator(
        symbol=symbol,
        risk_free_rate=0.04,      # 4% annual
        dividend_yield=0.015,     # 1.5% for SPY
        volatility_window=30      # 30-day rolling volatility
    )

    # Generate data
    try:
        options_df = generator.generate_historical_chains(
            start_date=start_date,
            end_date=end_date,
            include_weekly=True,
            max_dte=60,
            save_to_csv=True
        )

        print("\n" + "="*70)
        print("SUCCESS!")
        print("="*70)
        print(f"\nGenerated {len(options_df):,} option contracts")
        print(f"\nThe data has been saved to:")
        print(f"  data/processed/{symbol}_synthetic_options_{start_date}_{end_date}.csv")

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
