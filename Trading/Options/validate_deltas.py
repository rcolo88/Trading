#!/usr/bin/env python3
"""
Validate Delta Values in Synthetic Options Data

This script systematically checks delta values at different DTEs and moneyness levels
to ensure the Black-Scholes calculations are producing realistic results.
"""

import pandas as pd
import numpy as np

# Load the synthetic data
print("Loading synthetic options data...")
df = pd.read_csv('data/processed/SPY_synthetic_options_2021-01-01_2025-6-30.csv')
df['quote_date'] = pd.to_datetime(df['quote_date'])
df['expiration'] = pd.to_datetime(df['expiration'])

print(f"Loaded {len(df):,} option contracts\n")

# Pick a representative date for analysis
analysis_date = pd.to_datetime('2021-01-04')
day_data = df[df['quote_date'] == analysis_date].copy()

spot_price = day_data['underlying_price'].iloc[0]
vix = day_data['vix'].iloc[0]
iv = day_data['iv'].iloc[0]

print("="*80)
print(f"DELTA VALIDATION ANALYSIS")
print("="*80)
print(f"Analysis Date: {analysis_date.date()}")
print(f"SPY Price: ${spot_price:.2f}")
print(f"VIX: {vix:.2f}")
print(f"Implied Vol (used in pricing): {iv:.2%}")
print("="*80)

# Define DTE values to check
dte_targets = [4, 8, 10, 15, 20, 30, 40, 45]

print("\nCHECKING DELTAS AT DIFFERENT DTEs\n")

for target_dte in dte_targets:
    # Find closest DTE
    dte_data = day_data[abs(day_data['dte'] - target_dte) <= 2].copy()

    if len(dte_data) == 0:
        print(f"⚠️  No data found for ~{target_dte} DTE")
        continue

    actual_dte = dte_data['dte'].iloc[0]
    exp_date = dte_data['expiration'].iloc[0]

    print(f"\n{'='*80}")
    print(f"DTE: {actual_dte} days (target: {target_dte}) - Expiring {exp_date.date()}")
    print(f"{'='*80}")

    # Check different moneyness levels
    # For CALLS: strike > spot = OTM, strike < spot = ITM
    # For PUTS: strike > spot = ITM, strike < spot = OTM
    call_levels = [
        ("ATM", 0.0),
        ("1% OTM", 0.01),   # Higher strike for calls
        ("1% ITM", -0.01),  # Lower strike for calls
        ("2% OTM", 0.02),
        ("2% ITM", -0.02),
        ("5% OTM", 0.05),
        ("5% ITM", -0.05),
    ]

    print("\nCALL OPTIONS:")
    print(f"{'Moneyness':<12} {'Strike':<10} {'Delta':<10} {'Price':<10} {'Assessment':<20}")
    print("-"*80)

    for label, pct in call_levels:
        target_strike = spot_price * (1 + pct)

        # Find closest strike
        calls = dte_data[dte_data['option_type'] == 'call'].copy()
        calls['strike_diff'] = abs(calls['strike'] - target_strike)
        closest_call = calls.nsmallest(1, 'strike_diff')

        if len(closest_call) > 0:
            strike = closest_call['strike'].iloc[0]
            delta = closest_call['delta'].iloc[0]
            price = closest_call['last'].iloc[0]

            # Assess if delta is reasonable for CALLS
            assessment = ""
            if abs(pct) < 0.005:  # ATM
                if 0.45 <= delta <= 0.55:
                    assessment = "✓ Good"
                else:
                    assessment = "⚠️  Unexpected"
            elif pct < 0:  # ITM (lower strike for calls)
                expected_min = 0.55 if actual_dte > 30 else 0.60
                if delta >= expected_min:
                    assessment = "✓ Good"
                else:
                    assessment = "⚠️  Low for ITM"
            else:  # OTM (higher strike for calls)
                expected_max = 0.45 if actual_dte > 30 else 0.40
                if delta <= expected_max:
                    assessment = "✓ Good"
                else:
                    assessment = "⚠️  High for OTM"

            print(f"{label:<12} ${strike:<9.2f} {delta:<10.4f} ${price:<9.2f} {assessment:<20}")

    # For puts: higher strike = ITM, lower strike = OTM
    put_levels = [
        ("ATM", 0.0),
        ("1% OTM", -0.01),  # Lower strike for puts
        ("1% ITM", 0.01),   # Higher strike for puts
        ("2% OTM", -0.02),
        ("2% ITM", 0.02),
        ("5% OTM", -0.05),
        ("5% ITM", 0.05),
    ]

    print("\nPUT OPTIONS:")
    print(f"{'Moneyness':<12} {'Strike':<10} {'Delta':<10} {'Price':<10} {'Assessment':<20}")
    print("-"*80)

    for label, pct in put_levels:
        target_strike = spot_price * (1 + pct)

        # Find closest strike
        puts = dte_data[dte_data['option_type'] == 'put'].copy()
        puts['strike_diff'] = abs(puts['strike'] - target_strike)
        closest_put = puts.nsmallest(1, 'strike_diff')

        if len(closest_put) > 0:
            strike = closest_put['strike'].iloc[0]
            delta = closest_put['delta'].iloc[0]
            abs_delta = abs(delta)
            price = closest_put['last'].iloc[0]

            # Assess if delta is reasonable for PUTS
            assessment = ""
            if abs(pct) < 0.005:  # ATM
                if 0.45 <= abs_delta <= 0.55:
                    assessment = "✓ Good"
                else:
                    assessment = "⚠️  Unexpected"
            elif pct > 0:  # ITM for puts (higher strike)
                expected_min = 0.55 if actual_dte > 30 else 0.60
                if abs_delta >= expected_min:
                    assessment = "✓ Good"
                else:
                    assessment = "⚠️  Low for ITM"
            else:  # OTM for puts (lower strike)
                expected_max = 0.45 if actual_dte > 30 else 0.40
                if abs_delta <= expected_max:
                    assessment = "✓ Good"
                else:
                    assessment = "⚠️  High for OTM"

            print(f"{label:<12} ${strike:<9.2f} {delta:<10.4f} ${price:<9.2f} {assessment:<20}")

print("\n" + "="*80)
print("VALIDATION COMPLETE")
print("="*80)
print("\nExpected Delta Behavior Summary:")
print("  - ATM options: ~0.50 delta (±0.05) across all DTEs")
print("  - ITM options: Higher delta, increases as DTE decreases")
print("  - OTM options: Lower delta, decreases as DTE decreases")
print("\n" + "="*80)
