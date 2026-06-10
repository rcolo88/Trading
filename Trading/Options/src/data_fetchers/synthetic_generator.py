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
        volatility_window: int = 30,
        use_vix_for_iv: bool = True
    ):
        """
        Initialize synthetic data generator.

        Args:
            symbol: Underlying symbol (default: SPY)
            risk_free_rate: Annual risk-free rate (default: 4%)
            dividend_yield: Annual dividend yield for SPY (default: 1.5%)
            volatility_window: Days for rolling volatility calculation (default: 30)
            use_vix_for_iv: If True, use VIX as IV proxy; if False, use historical vol (default: True)
        """
        self.symbol = symbol
        self.risk_free_rate = risk_free_rate
        self.dividend_yield = dividend_yield
        self.volatility_window = volatility_window
        self.use_vix_for_iv = use_vix_for_iv

        # IV-surface shape (so synthetic chains have real skew + term structure, not one flat IV).
        # Without these every strike/expiration shares one IV, which makes calendars a free lunch and
        # produces the degenerate ties + inflated Sharpe. Values are deliberately modest and SPY-like.
        self.skew_slope = 0.60   # IV rises as strike falls (equity put skew); per unit log-moneyness
        self.skew_curv = 1.50    # smile convexity (both deep wings richer)
        self.term_slope = 0.10   # mild contango: longer-dated slightly higher IV (per year past 30d)
        self.min_half_spread = 0.025  # floor on half bid/ask ($) so cheap options aren't priced tight

        self.underlying_data = None
        self.volatility = None

    def _iv_surface(self, spot: float, strike: float, dte: int, base_vol: float) -> float:
        """IV for one (strike, dte) from a base level: equity skew × mild term structure.

        This is what makes the synthetic data non-degenerate — a calendar's near/far legs and a
        vertical's two strikes now carry *different* IVs, so skew/term-structure risk is modelled
        rather than assumed away. Still a model: use real data (data_source.mode=real) for conclusions.
        """
        m = np.log(strike / spot) if spot > 0 and strike > 0 else 0.0  # log-moneyness (<0 = low strike)
        skew = 1.0 - self.skew_slope * m + self.skew_curv * m * m
        term = 1.0 + self.term_slope * (dte - 30.0) / 365.0
        return float(np.clip(base_vol * skew * term, 0.03, 3.0))

    def fetch_underlying_data(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Fetch historical underlying price data and VIX from Yahoo Finance.
        Calculates IV Percentile based on SPY's implied volatility over 252 trading days.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data, VIX, SPY IV, and IV Percentile
        """
        print(f"Fetching {self.symbol} price data from Yahoo Finance...")
        print(f"Date range: {start_date} to {end_date}")

        # Fetch underlying (SPY) data
        ticker = yf.Ticker(self.symbol)
        data = ticker.history(start=start_date, end=end_date)

        if data.empty:
            raise ValueError(f"No data found for {self.symbol}")

        # Remove timezone info and normalize to 12:00 PM (noon) ET for market midday
        data.index = data.index.tz_localize(None)
        data.index = data.index.map(lambda x: x.replace(hour=12, minute=0, second=0, microsecond=0))

        # Standardize column names
        data.columns = [col.lower() for col in data.columns]

        # Calculate returns first (needed for volatility calculation)
        data['returns'] = data['close'].pct_change()

        # Calculate rolling volatility (annualized)
        data['volatility'] = data['returns'].rolling(
            window=self.volatility_window
        ).std() * np.sqrt(252)

        # Forward fill any NaN volatility values
        data['volatility'] = data['volatility'].bfill()

        # Fetch VIX data (implied volatility index for reference)
        print(f"Fetching VIX data from Yahoo Finance...")
        vix_ticker = yf.Ticker("^VIX")
        vix_data = vix_ticker.history(start=start_date, end=end_date)

        if not vix_data.empty:
            # Remove timezone and normalize to 12:00 PM (noon) ET
            vix_data.index = vix_data.index.tz_localize(None)
            vix_data.index = vix_data.index.map(lambda x: x.replace(hour=12, minute=0, second=0, microsecond=0))
            vix_close = vix_data['Close'].rename('vix')

            # Merge VIX data with underlying data
            data = data.join(vix_close, how='left')

            # Forward fill any missing VIX values (for holidays/weekends)
            data['vix'] = data['vix'].ffill()

            print(f"✓ VIX data merged (for reference)")
            print(f"  VIX range: {data['vix'].min():.2f} - {data['vix'].max():.2f}")
        else:
            print(f"⚠️  Warning: Could not fetch VIX data")
            data['vix'] = np.nan

        # Calculate SPY's Implied Volatility from ATM options
        # For synthetic data, we use VIX as a proxy for SPY IV since:
        # 1. VIX represents S&P 500 implied volatility
        # 2. SPY tracks S&P 500
        # 3. This is the volatility we'll use to price SPY options
        print(f"Calculating SPY implied volatility...")
        if 'vix' in data.columns and not data['vix'].isna().all():
            # Use VIX as SPY IV proxy (convert from percentage to decimal for internal use)
            data['spy_iv'] = data['vix'] / 100.0
        else:
            # Fallback to historical volatility if VIX unavailable
            data['spy_iv'] = data['volatility']

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
        vix: float = None,
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
            vix: VIX level (for reference)
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
            # Per-strike, per-expiration IV from the surface (skew + term structure), not a flat vol.
            iv_k = self._iv_surface(spot_price, strike, dte, volatility)

            # Calculate call option
            call_data = calculate_all_greeks(
                S=spot_price,
                K=strike,
                T=T,
                r=self.risk_free_rate,
                sigma=iv_k,
                option_type='call',
                q=self.dividend_yield
            )

            # Calculate put option
            put_data = calculate_all_greeks(
                S=spot_price,
                K=strike,
                T=T,
                r=self.risk_free_rate,
                sigma=iv_k,
                option_type='put',
                q=self.dividend_yield
            )

            # Add call option
            if add_spread:
                spread = max(self.min_half_spread, call_data['price'] * spread_pct / 2)
                call_bid = max(0.01, call_data['price'] - spread)
                call_ask = call_data['price'] + spread
            else:
                call_bid = call_ask = call_data['price']

            options.append({
                'quote_date': quote_date,
                'underlying_symbol': self.symbol,
                'underlying_price': spot_price,
                'vix': vix if vix is not None else np.nan,
                'expiration': expiration_date,
                'dte': dte,
                'strike': strike,
                'option_type': 'call',
                'bid': call_bid,
                'ask': call_ask,
                'last': call_data['price'],
                'volume': np.random.randint(100, 5000),  # Synthetic volume
                'open_interest': np.random.randint(500, 20000),  # Synthetic OI
                'iv': iv_k,
                'delta': call_data['delta'],
                'abs_delta': abs(call_data['delta']),  # Absolute delta for filtering
                'gamma': call_data['gamma'],
                'theta': call_data['theta'] / 365,  # Convert to daily
                'vega': call_data['vega']
            })

            # Add put option
            if add_spread:
                spread = max(self.min_half_spread, put_data['price'] * spread_pct / 2)
                put_bid = max(0.01, put_data['price'] - spread)
                put_ask = put_data['price'] + spread
            else:
                put_bid = put_ask = put_data['price']

            options.append({
                'quote_date': quote_date,
                'underlying_symbol': self.symbol,
                'underlying_price': spot_price,
                'vix': vix if vix is not None else np.nan,
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
                'abs_delta': abs(put_data['delta']),  # Absolute delta for filtering
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

            # Get VIX if available
            vix = self.underlying_data.loc[quote_date, 'vix'] if 'vix' in self.underlying_data.columns else None

            # Determine which volatility to use for pricing
            if self.use_vix_for_iv and vix is not None and not np.isnan(vix):
                # Use VIX as implied volatility (convert from percentage to decimal)
                pricing_vol = vix / 100.0
            else:
                # Fall back to historical volatility
                pricing_vol = vol

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
                    volatility=pricing_vol,  # Use VIX-based IV instead of historical vol
                    vix=vix
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
    save_to_csv: bool = True,
    use_vix_for_iv: bool = True
) -> pd.DataFrame:
    """
    Quick function to generate 2 years of SPY synthetic options data.

    Args:
        start_date: Start date (default: 2022-01-01)
        end_date: End date (default: 2024-12-31)
        save_to_csv: Save to CSV file
        use_vix_for_iv: Use VIX as IV proxy for realistic pricing (default: True)

    Returns:
        DataFrame with synthetic options data
    """
    generator = SyntheticOptionsGenerator(
        symbol="SPY",
        risk_free_rate=0.04,  # 4% annual
        dividend_yield=0.015,  # 1.5% for SPY
        volatility_window=30,
        use_vix_for_iv=use_vix_for_iv
    )

    return generator.generate_historical_chains(
        start_date=start_date,
        end_date=end_date,
        include_weekly=True,
        max_dte=60,
        save_to_csv=save_to_csv
    )


def synthetic_data_filename(config: dict) -> str:
    """Return the canonical synthetic-data CSV name for the `synthetic_data` config block.

    This is the ONE place the naming convention lives -- the generator saves to this
    name and every loader reads from it, so they can never drift apart.
    """
    sd = config["synthetic_data"]
    return f"{sd['symbol']}_synthetic_options_{sd['start_date']}_{sd['end_date']}.csv"


def real_data_filename(config: dict) -> str:
    """Return the canonical CSV name for a REAL (DoltHub/logged) options dataset.

    Mirrors `synthetic_data_filename` so `real_chain_loader.py` writes exactly the file this
    module's loader reads when `data_source.mode: real`.
    """
    rd = config["real_data"]
    return f"{rd['symbol']}_real_options_{rd['start_date']}_{rd['end_date']}.csv"


def _load_options_config() -> dict:
    """Read config/config.yaml from the project root (parent of src/)."""
    import yaml
    from pathlib import Path
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _read_options_csv(csv_file) -> pd.DataFrame:
    """Read an options CSV, normalize the date columns, and print a short summary."""
    import os
    print(f"Loading data from: {os.path.basename(csv_file)}")
    data = pd.read_csv(csv_file)
    data['quote_date'] = pd.to_datetime(data['quote_date'])
    data['expiration'] = pd.to_datetime(data['expiration'])
    print(f"✓ Loaded {len(data):,} option contracts")
    print(f"  Date range: {data['quote_date'].min().date()} to {data['quote_date'].max().date()}")
    print(f"  Trading days: {data['quote_date'].nunique()}")
    print(f"  Expirations: {data['expiration'].nunique()}")
    return data


def load_sample_spy_options_data(specific_file: str = None, config: dict = None) -> pd.DataFrame:
    """
    Load SPY options data from pre-generated synthetic data CSV.

    This function loads the full synthetic dataset generated by
    generate_synthetic_data.py script. If no CSV file is found,
    it will generate a minimal sample dataset.

    The data is based on real SPY closing prices from Yahoo Finance
    with option prices calculated using the Black-Scholes-Merton model.

    Args:
        specific_file: Optional explicit filename to load (escape hatch). If given,
                       it overrides the config-derived dataset.
        config: Optional pre-loaded config dict. If None (and no specific_file),
                config/config.yaml is read to derive the dataset filename.

    Returns:
        DataFrame with synthetic options data
    """
    import os
    import glob
    from pathlib import Path

    print("Loading SPY options data...")

    # Get the project root directory (parent of src/)
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data" / "processed"

    # Escape hatch: an explicit filename always wins.
    if specific_file:
        csv_file = data_dir / specific_file
        if not csv_file.exists():
            raise FileNotFoundError(f"Specified file not found: {csv_file}")
        return _read_options_csv(csv_file)

    cfg = config or _load_options_config()

    # Real-data mode: load the DoltHub/logged dataset named by the real_data config block.
    # This is the honest dataset (true skew + term structure); synthetic stays the default
    # only for fast plumbing/CI runs.
    if cfg.get("data_source", {}).get("mode") == "real":
        real_name = real_data_filename(cfg)
        real_path = data_dir / real_name
        if not real_path.exists():
            rd = cfg["real_data"]
            raise FileNotFoundError(
                f"data_source.mode=real but '{real_name}' is missing from data/processed/.\n"
                f"   Build it first:\n"
                f"   opt_venv/bin/python -m src.data_fetchers.real_chain_loader "
                f"--start {rd['start_date']} --end {rd['end_date']}"
            )
        print(f"Loading REAL dataset: {real_name}")
        return _read_options_csv(real_path)

    # Default: derive the canonical filename from the synthetic_data config block,
    # so the file the generator wrote is exactly the file we load here.
    derived_name = synthetic_data_filename(cfg)
    derived_path = data_dir / derived_name

    if derived_path.exists():
        print(f"Loading config-derived dataset: {derived_name}")
        return _read_options_csv(derived_path)

    # Config points at a dataset that hasn't been generated yet. Fall back to the
    # MOST RECENTLY GENERATED csv (by mtime, not filename order) so work continues.
    pattern = str(data_dir / "SPY_synthetic_options_*.csv")
    csv_files = glob.glob(pattern)
    if csv_files:
        csv_file = max(csv_files, key=os.path.getmtime)
        print(f"⚠️  Config dataset not found: {derived_name}")
        print(f"   Falling back to most recently generated file: {os.path.basename(csv_file)}")
        print(f"   (Run: python generate_synthetic_data.py  to build the config dataset.)")
        return _read_options_csv(csv_file)

    # If no CSV found at all, generate a small sample (2 months for quick testing)
    print("⚠️  No synthetic data CSV found in data/processed/")
    print("   Run: python generate_synthetic_data.py")
    print("   Generating minimal sample dataset...")

    generator = SyntheticOptionsGenerator(symbol="SPY")
    return generator.generate_historical_chains(
        start_date="2024-01-01",
        end_date="2024-02-29",
        include_weekly=False,  # Monthly only for speed
        max_dte=45,
        save_to_csv=False
    )
