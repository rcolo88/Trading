"""
Synthetic Options Data Generator.

Generates realistic options chain data using Black-Scholes-Merton model
based on historical underlying prices. Useful when historical options
data is unavailable or too expensive.

Based on methodology from: github.com/aspiringfastlaner/spx_options_backtesting
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
import yfinance as yf

from ..utils.black_scholes import (
    black_scholes_price,
    calculate_all_greeks,
    find_strike_by_delta
)


class SyntheticOptionsGenerator:
    """
    Generate synthetic options data using Black-Scholes model.

    This class creates realistic options chains based on:
    - Historical underlying prices (from Yahoo Finance)
    - Calculated historical volatility
    - Black-Scholes-Merton pricing model
    """

    def __init__(
        self,
        symbol: str = "SPY",
        risk_free_rate: float = 0.04,
        dividend_yield: float = 0.015,
        volatility_window: int = 30
    ):
        """
        Initialize synthetic data generator.

        Args:
            symbol: Underlying symbol (default: SPY)
            risk_free_rate: Annual risk-free rate (default: 4%)
            dividend_yield: Annual dividend yield for SPY (default: 1.5%)
            volatility_window: Days for rolling volatility calculation (default: 30)
        """
        self.symbol = symbol
        self.risk_free_rate = risk_free_rate
        self.dividend_yield = dividend_yield
        self.volatility_window = volatility_window

        self.underlying_data = None
        self.volatility = None

    def fetch_underlying_data(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Fetch historical underlying price data from Yahoo Finance.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data
        """
        print(f"Fetching {self.symbol} price data from Yahoo Finance...")
        print(f"Date range: {start_date} to {end_date}")

        ticker = yf.Ticker(self.symbol)
        data = ticker.history(start=start_date, end=end_date)

        if data.empty:
            raise ValueError(f"No data found for {self.symbol}")

        # Standardize column names
        data.columns = [col.lower() for col in data.columns]

        # Calculate returns
        data['returns'] = data['close'].pct_change()

        # Calculate rolling volatility (annualized)
        data['volatility'] = data['returns'].rolling(
            window=self.volatility_window
        ).std() * np.sqrt(252)

        # Forward fill any NaN volatility values
        data['volatility'] = data['volatility'].fillna(method='bfill')

        # Use median volatility for any remaining NaN
        median_vol = data['volatility'].median()
        data['volatility'] = data['volatility'].fillna(median_vol)

        self.underlying_data = data
        self.volatility = data['volatility']

        print(f"✓ Retrieved {len(data)} days of price data")
        print(f"  Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}")
        print(f"  Volatility range: {data['volatility'].min():.2%} - {data['volatility'].max():.2%}")

        return data

    def generate_expiration_dates(
        self,
        start_date: datetime,
        end_date: datetime,
        include_weekly: bool = True,
        include_monthly: bool = True
    ) -> List[datetime]:
        """
        Generate standard options expiration dates.

        Args:
            start_date: Start date
            end_date: End date
            include_weekly: Include weekly expirations (Fridays)
            include_monthly: Include monthly expirations (3rd Friday)

        Returns:
            List of expiration dates
        """
        expirations = []
        current_date = start_date

        while current_date <= end_date + timedelta(days=90):  # Extend for DTEs
            # Monthly expiration: 3rd Friday of month
            if include_monthly:
                # Find 3rd Friday
                first_day = current_date.replace(day=1)
                # Find first Friday
                days_until_friday = (4 - first_day.weekday()) % 7
                first_friday = first_day + timedelta(days=days_until_friday)
                # Add 2 weeks for 3rd Friday
                third_friday = first_friday + timedelta(weeks=2)

                if third_friday not in expirations:
                    expirations.append(third_friday)

            # Weekly expirations: Every Friday
            if include_weekly:
                # Find all Fridays in the month
                day = current_date.replace(day=1)
                while day.month == current_date.month:
                    if day.weekday() == 4:  # Friday
                        if day not in expirations:
                            expirations.append(day)
                    day += timedelta(days=1)

            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        # Filter to valid range and sort
        expirations = [d for d in expirations if start_date <= d <= end_date + timedelta(days=90)]
        expirations.sort()

        return expirations

    def generate_strike_prices(
        self,
        spot_price: float,
        num_strikes: int = 40,
        strike_interval: float = 5.0
    ) -> np.ndarray:
        """
        Generate array of strike prices around spot price.

        Args:
            spot_price: Current underlying price
            num_strikes: Number of strikes to generate
            strike_interval: Dollar spacing between strikes

        Returns:
            Array of strike prices
        """
        # Center strikes around spot price
        half_strikes = num_strikes // 2

        # Round spot to nearest strike interval
        center_strike = np.round(spot_price / strike_interval) * strike_interval

        strikes = np.arange(
            center_strike - (half_strikes * strike_interval),
            center_strike + ((half_strikes + 1) * strike_interval),
            strike_interval
        )

        return strikes[strikes > 0]  # Remove any negative strikes

    def generate_options_chain(
        self,
        quote_date: datetime,
        expiration_date: datetime,
        spot_price: float,
        volatility: float,
        num_strikes: int = 40,
        strike_interval: float = 5.0,
        add_spread: bool = True,
        spread_pct: float = 0.02
    ) -> pd.DataFrame:
        """
        Generate complete options chain for a single date and expiration.

        Args:
            quote_date: Current date
            expiration_date: Option expiration date
            spot_price: Current underlying price
            volatility: Current volatility estimate
            num_strikes: Number of strikes to generate
            strike_interval: Dollar spacing between strikes
            add_spread: Add bid-ask spread to prices
            spread_pct: Bid-ask spread as % of mid price

        Returns:
            DataFrame with options chain data
        """
        # Calculate time to expiration
        dte = (expiration_date - quote_date).days
        T = dte / 365.0

        if dte <= 0:
            return pd.DataFrame()  # Don't generate expired options

        # Generate strikes
        strikes = self.generate_strike_prices(spot_price, num_strikes, strike_interval)

        options = []

        for strike in strikes:
            # Calculate call option
            call_data = calculate_all_greeks(
                S=spot_price,
                K=strike,
                T=T,
                r=self.risk_free_rate,
                sigma=volatility,
                option_type='call',
                q=self.dividend_yield
            )

            # Calculate put option
            put_data = calculate_all_greeks(
                S=spot_price,
                K=strike,
                T=T,
                r=self.risk_free_rate,
                sigma=volatility,
                option_type='put',
                q=self.dividend_yield
            )

            # Add call option
            if add_spread:
                spread = call_data['price'] * spread_pct / 2
                call_bid = max(0.01, call_data['price'] - spread)
                call_ask = call_data['price'] + spread
            else:
                call_bid = call_ask = call_data['price']

            options.append({
                'quote_date': quote_date,
                'underlying_symbol': self.symbol,
                'underlying_price': spot_price,
                'expiration': expiration_date,
                'dte': dte,
                'strike': strike,
                'option_type': 'call',
                'bid': call_bid,
                'ask': call_ask,
                'last': call_data['price'],
                'volume': np.random.randint(100, 5000),  # Synthetic volume
                'open_interest': np.random.randint(500, 20000),  # Synthetic OI
                'iv': volatility,
                'delta': call_data['delta'],
                'gamma': call_data['gamma'],
                'theta': call_data['theta'] / 365,  # Convert to daily
                'vega': call_data['vega']
            })

            # Add put option
            if add_spread:
                spread = put_data['price'] * spread_pct / 2
                put_bid = max(0.01, put_data['price'] - spread)
                put_ask = put_data['price'] + spread
            else:
                put_bid = put_ask = put_data['price']

            options.append({
                'quote_date': quote_date,
                'underlying_symbol': self.symbol,
                'underlying_price': spot_price,
                'expiration': expiration_date,
                'dte': dte,
                'strike': strike,
                'option_type': 'put',
                'bid': put_bid,
                'ask': put_ask,
                'last': put_data['price'],
                'volume': np.random.randint(100, 5000),
                'open_interest': np.random.randint(500, 20000),
                'iv': volatility,
                'delta': put_data['delta'],
                'gamma': put_data['gamma'],
                'theta': put_data['theta'] / 365,
                'vega': put_data['vega']
            })

        return pd.DataFrame(options)

    def generate_historical_chains(
        self,
        start_date: str,
        end_date: str,
        include_weekly: bool = True,
        max_dte: int = 60,
        save_to_csv: bool = True,
        output_path: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Generate complete historical options chains dataset.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            include_weekly: Include weekly expirations
            max_dte: Maximum DTE to include in chains
            save_to_csv: Save output to CSV
            output_path: Path for CSV output

        Returns:
            DataFrame with all historical options data
        """
        print(f"\n{'='*70}")
        print(f"GENERATING SYNTHETIC OPTIONS DATA")
        print(f"{'='*70}")
        print(f"Symbol: {self.symbol}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Risk-free rate: {self.risk_free_rate:.2%}")
        print(f"Dividend yield: {self.dividend_yield:.2%}")
        print(f"Volatility window: {self.volatility_window} days")

        # Fetch underlying data
        self.fetch_underlying_data(start_date, end_date)

        # Generate expiration dates
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        expirations = self.generate_expiration_dates(
            start_dt,
            end_dt,
            include_weekly=include_weekly,
            include_monthly=True
        )

        print(f"\nGenerated {len(expirations)} expiration dates")

        # Generate options chains for each trading day
        all_options = []
        trading_dates = self.underlying_data.index

        print(f"\nGenerating options chains for {len(trading_dates)} trading days...")

        for i, quote_date in enumerate(trading_dates):
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i+1}/{len(trading_dates)} days ({(i+1)/len(trading_dates)*100:.1f}%)")

            spot_price = self.underlying_data.loc[quote_date, 'close']
            vol = self.underlying_data.loc[quote_date, 'volatility']

            # Generate chains for all valid expirations
            for exp_date in expirations:
                dte = (exp_date - quote_date).days

                # Skip if expiration is in the past or too far out
                if dte <= 0 or dte > max_dte:
                    continue

                chain = self.generate_options_chain(
                    quote_date=quote_date,
                    expiration_date=exp_date,
                    spot_price=spot_price,
                    volatility=vol
                )

                if not chain.empty:
                    all_options.append(chain)

        # Combine all chains
        print("\nCombining all options chains...")
        options_df = pd.concat(all_options, ignore_index=True)

        print(f"\n{'='*70}")
        print(f"GENERATION COMPLETE")
        print(f"{'='*70}")
        print(f"Total option contracts: {len(options_df):,}")
        print(f"Date range: {options_df['quote_date'].min().date()} to {options_df['quote_date'].max().date()}")
        print(f"Expirations: {options_df['expiration'].nunique()}")
        print(f"Unique strikes: {options_df['strike'].nunique()}")
        print(f"Calls: {len(options_df[options_df['option_type']=='call']):,}")
        print(f"Puts: {len(options_df[options_df['option_type']=='put']):,}")

        # Save to CSV if requested
        if save_to_csv:
            if output_path is None:
                output_path = f"data/processed/{self.symbol}_synthetic_options_{start_date}_{end_date}.csv"

            print(f"\nSaving to: {output_path}")
            options_df.to_csv(output_path, index=False)
            print("✓ Saved successfully")

        print(f"{'='*70}\n")

        return options_df


# Convenience function
def generate_spy_synthetic_data(
    start_date: str = "2022-01-01",
    end_date: str = "2024-12-31",
    save_to_csv: bool = True
) -> pd.DataFrame:
    """
    Quick function to generate 2 years of SPY synthetic options data.

    Args:
        start_date: Start date (default: 2022-01-01)
        end_date: End date (default: 2024-12-31)
        save_to_csv: Save to CSV file

    Returns:
        DataFrame with synthetic options data
    """
    generator = SyntheticOptionsGenerator(
        symbol="SPY",
        risk_free_rate=0.04,  # 4% annual
        dividend_yield=0.015,  # 1.5% for SPY
        volatility_window=30
    )

    return generator.generate_historical_chains(
        start_date=start_date,
        end_date=end_date,
        include_weekly=True,
        max_dte=60,
        save_to_csv=save_to_csv
    )
