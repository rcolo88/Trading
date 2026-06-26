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

        # IV-surface shape — calibrated against DoltHub real data (compare_synthetic_real.py).
        # Skew term: 1.0 - slope * log_moneyness + curv * log_moneyness^2
        # Term:      1.0 + term_slope * (dte - 30) / 365
        #             + short_premium * max(0, 30-dte) / 365  (short-dated vol premium)
        self.skew_slope = 1.00          # equity put skew steepness (was 0.60 — too flat)
        self.skew_curv = 2.50           # smile convexity (was 1.50 — wings too cheap)
        self.term_slope = 0.0           # residual contango (was +0.10; short_premium does the work)
        self.short_premium = 3.0        # extra annualized vol for days below 30 DTE
        self.min_half_spread = 0.01     # floor on half bid/ask ($); SPY ATM spreads are ~1¢
        # VIX → base-vol calibration.  VIX itself is ~30d ATM, so raw vix/100 is a decent starting
        # point.  Real SPY atmf vol ≈ 0.95 * VIX + 1.5 vol-pts (low-VIX regimes have a higher
        # premium over VIX; high-VIX regimes trade near VIX).
        self.vix_scale = 0.95           # scale factor on vix/100 (was implicit 1.0)
        self.vix_offset = 0.015         # additive offset so low-vix doesn't floor out

        self.underlying_data = None
        self.volatility = None
        # Set per-day from _build_term_curve() before generating each day's chains.
        # None → fallback to hardcoded short_premium formula (used if VIX complex unavailable).
        self._day_term_curve = None

    def _iv_surface(self, spot: float, strike: float, dte: int, base_vol: float) -> float:
        """IV for one (strike, dte) from a base level: equity skew × term structure.

        When self._day_term_curve is set (VIX complex available), the term-structure
        ratio at each DTE is interpolated from real observed VIX tenors (^VIX9D/^VIX/
        ^VIX3M/^VIX6M), so contango/backwardation regimes are real, not hardcoded.
        Falls back to the parametric formula when the VIX complex is unavailable.
        """
        m = np.log(strike / spot) if spot > 0 and strike > 0 else 0.0
        skew = 1.0 - self.skew_slope * m + self.skew_curv * m * m
        if self._day_term_curve is not None:
            term = self._day_term_curve(dte)
        else:
            short_extra = max(0, 30 - dte) * self.short_premium / 365.0 if self.short_premium else 0.0
            term = 1.0 + self.term_slope * (dte - 30.0) / 365.0 + short_extra
        return float(np.clip(base_vol * skew * term, 0.03, 3.0))

    def _build_term_curve(self, date):
        """Build a per-day term-ratio callable from the real VIX tenor complex.

        Interpolates across available VIX tenors (^VIX9D=9d, ^VIX=30d, ^VIX3M=93d,
        ^VIX6M=180d) and returns a function term_ratio(dte) that gives IV(dte)/IV(30d).
        The 30d anchor (^VIX level) is already baked into base_vol; this only shapes the
        curve — so contango/backwardation comes from real observed data, not a constant.

        Returns None when fewer than 2 tenors are available (caller uses fallback).
        """
        tenor_cols = [("vix9d", 9), ("vix", 30), ("vix3m", 93), ("vix6m", 180)]
        points = []
        for col, dte_pt in tenor_cols:
            if col in self.underlying_data.columns:
                val = self.underlying_data.loc[date, col]
                if pd.notna(val) and val > 0:
                    points.append((dte_pt, float(val)))
        if len(points) < 2 or not any(d == 30 for d, _ in points):
            return None
        dtes = np.array([p[0] for p in points], dtype=float)
        vols = np.array([p[1] for p in points], dtype=float)
        vix30 = float(dict(points)[30])

        def term_ratio(dte: int) -> float:
            interp_vol = float(np.interp(float(dte), dtes, vols))
            return float(np.clip(interp_vol / vix30, 0.5, 3.0))

        return term_ratio

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

        # Fetch VIX term-structure complex for per-day term-ratio calibration.
        # ^VIX9D / ^VIX3M / ^VIX6M combined with ^VIX (30d, already fetched) give 4 tenor
        # points; _build_term_curve() interpolates these into a daily term-ratio curve so the
        # calendar sees real contango/backwardation regimes rather than a hardcoded constant.
        for vix_sym, col_name in [("^VIX9D", "vix9d"), ("^VIX3M", "vix3m"), ("^VIX6M", "vix6m")]:
            try:
                vt = yf.Ticker(vix_sym)
                vd = vt.history(start=start_date, end=end_date)
                if not vd.empty:
                    vd.index = vd.index.tz_localize(None)
                    vd.index = vd.index.map(
                        lambda x: x.replace(hour=12, minute=0, second=0, microsecond=0))
                    data = data.join(vd['Close'].rename(col_name), how='left')
                    data[col_name] = data[col_name].ffill()
                    print(f"  ✓ {vix_sym} → '{col_name}' ({data[col_name].notna().sum()} days)")
                else:
                    data[col_name] = np.nan
                    print(f"  ⚠️  {vix_sym}: no data returned — term-structure will use fallback")
            except Exception as e:
                data[col_name] = np.nan
                print(f"  ⚠️  {vix_sym}: fetch failed ({e}) — term-structure will use fallback")

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
        spread_pct: float = 0.008
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

            # Build per-day term-structure curve from the VIX complex (real contango/backwardation).
            # _iv_surface() reads self._day_term_curve; None = fallback to hardcoded formula.
            self._day_term_curve = self._build_term_curve(quote_date)

            # Determine which volatility to use for pricing
            if self.use_vix_for_iv and vix is not None and not np.isnan(vix):
                # Calibrated VIX → SPY IV: scale + offset so low-VIX regimes don't floor out
                # and high-VIX regimes don't over-shoot (see compare_synthetic_real.py).
                pricing_vol = max(vix / 100.0 * self.vix_scale + self.vix_offset, 0.05)
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


def reprice_from_iv(df: pd.DataFrame, r: float = 0.04, spread_frac: float = 0.03,
                    min_spread: float = 0.05, iv_lo: float = 0.03, iv_hi: float = 2.0) -> pd.DataFrame:
    """Re-derive bid/ask from the (clean) ``iv`` column via Black-Scholes — vectorized.

    On the DoltHub free dataset the ``iv`` column tracks VIX (for ATM ~30d, iv/VIX ≈ 0.95, ~2 vol-pts
    error) but the raw bid/ask is systematically inflated (mid-implied vol ≈ 1.47× VIX, ~8 vol-pts
    high) and noisy. Marking a held position against that bid/ask is inconsistent with entry, so
    profit/stop/dte exits misfire (a remark on fair BS vs an entry on inflated mid books phantom
    P&L). Pricing every contract off its own clean iv puts entry, exit, and daily re-marks on ONE
    fair, internally-consistent basis (true skew + term structure preserved — this is NOT flat-IV
    synthetic). The raw spread is unreliable, so a modeled spread (max(spread_frac*mid, min_spread))
    stands in; tune it with the cost model. Originals are kept as iv_raw_bid / iv_raw_ask.
    """
    from scipy.stats import norm
    d = df.copy()
    S = d['underlying_price'].to_numpy(float)
    K = d['strike'].to_numpy(float)
    T = np.clip(d['dte'].to_numpy(float), 0.0, None) / 365.0
    iv = np.clip(pd.to_numeric(d['iv'], errors='coerce').to_numpy(float), iv_lo, iv_hi)
    is_call = d['option_type'].astype(str).str.lower().isin(['call', 'c']).to_numpy()
    with np.errstate(divide='ignore', invalid='ignore'):
        sqrtT = np.sqrt(T)
        d1 = (np.log(S / K) + (r + 0.5 * iv ** 2) * T) / (iv * sqrtT)
        d2 = d1 - iv * sqrtT
        call = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        put = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    mid = np.where(is_call, call, put)
    expired = T <= 0
    mid = np.where(expired, np.where(is_call, np.maximum(S - K, 0.0), np.maximum(K - S, 0.0)), mid)
    mid = np.nan_to_num(np.maximum(mid, 0.0), nan=0.0, posinf=0.0, neginf=0.0)
    half = np.maximum(spread_frac * mid, min_spread) / 2.0
    d['iv_raw_bid'], d['iv_raw_ask'] = d['bid'], d['ask']
    d['bid'] = np.maximum(mid - half, 0.01)
    d['ask'] = mid + half
    return d


def assess_real_data_quality(df: pd.DataFrame, *, atm_band: float = 0.01,
                             dte_lo: int = 5, dte_hi: int = 50,
                             sample_days: int = 300) -> dict:
    """Diagnose whether a real options dataset is arbitrage-coherent enough to backtest.

    Two cheap, model-light checks on the dataset's OWN columns:
      * **ATM IV vs VIX** — for ATM (~near-30d) options ``iv / (VIX/100)`` should be ~1.0. The
        Massive/Polygon free-tier EOD *closes* back-solve to iv ≈ 1.3–1.6× VIX (worse at short DTE,
        i.e. exactly the calendar's near leg), so a median far above 1.0 flags inflated prices.
      * **Term-structure (calendar) coherence** — for a fixed (day, strike) the ATM call mid MUST be
        weakly increasing in DTE (a longer-dated option is worth at least as much). A high fraction
        of slices where the mid DECREASES with DTE is a no-arbitrage violation: the near-vs-far
        relationship a calendar spread trades is broken, so any calendar P&L on it is fiction.

    Returns a dict of metrics plus ``verdict`` in {clean, suspect, corrupt}. Whether to raise on
    'corrupt' is the caller's choice (load_sample_spy_options_data does, unless the config sets
    data_source.allow_low_quality). Calibrated on measured data: DoltHub = 0.93 / 0% inversions
    (clean); Massive = 1.35 / 34% inversions (corrupt).
    """
    out: dict = {"verdict": "clean", "reasons": []}
    if "option_type" not in df.columns or "underlying_price" not in df.columns:
        return out
    c = df[df["option_type"].astype(str).str.lower().isin(["call", "c"])].copy()
    if c.empty:
        return out
    c["_m"] = (c["strike"] - c["underlying_price"]).abs() / c["underlying_price"]

    # --- ATM IV vs VIX -------------------------------------------------------------------------
    ratio_med = float("nan")
    if "iv" in c.columns and "vix" in c.columns:
        atm = c[(c["_m"] <= atm_band) & (c["dte"].between(dte_lo, dte_hi))]
        iv = pd.to_numeric(atm["iv"], errors="coerce")
        vix = pd.to_numeric(atm["vix"], errors="coerce") / 100.0
        r = (iv / vix).replace([np.inf, -np.inf], np.nan).dropna()
        if len(r) >= 50:
            ratio_med = float(r.median())
            out["atm_iv_vix_median"] = ratio_med
            out["atm_iv_gt_2x_vix_frac"] = float((r > 2).mean())

    # --- Term-structure (calendar) coherence ---------------------------------------------------
    inv_rate = float("nan")
    if {"bid", "ask"}.issubset(c.columns):
        atmc = c[c["_m"] <= atm_band / 2.0].copy()
        days = atmc["quote_date"].drop_duplicates()
        if len(days) > sample_days:                       # cap cost on large files
            days = days.sample(sample_days, random_state=0)
            atmc = atmc[atmc["quote_date"].isin(days)]
        atmc["_mid"] = (pd.to_numeric(atmc["bid"], errors="coerce")
                        + pd.to_numeric(atmc["ask"], errors="coerce")) / 2.0
        bad = tot = 0
        for _, g in atmc.groupby(["quote_date", "strike"]):
            if len(g) < 3:
                continue
            m = g.sort_values("dte")["_mid"].to_numpy()
            tot += 1
            if np.any(np.diff(m) < -0.05 * m[:-1]):       # >5% drop as DTE rises = inverted
                bad += 1
        if tot >= 30:
            inv_rate = bad / tot
            out["term_inversion_rate"] = inv_rate
            out["term_slices_checked"] = tot

    # --- Verdict -------------------------------------------------------------------------------
    if ratio_med == ratio_med and (ratio_med > 1.20 or ratio_med < 0.5):
        out["verdict"] = "corrupt"
        out["reasons"].append(f"ATM iv/VIX median {ratio_med:.2f} (expect ~1.0)")
    if inv_rate == inv_rate and inv_rate > 0.10:
        out["verdict"] = "corrupt"
        out["reasons"].append(
            f"{inv_rate:.0%} of ATM term-structure slices invert (no-arbitrage violation)")
    if out["verdict"] == "clean" and (
        (ratio_med == ratio_med and ratio_med > 1.10) or (inv_rate == inv_rate and inv_rate > 0.03)
    ):
        out["verdict"] = "suspect"
    return out


def _enforce_data_quality(df: pd.DataFrame, ds: dict, name: str) -> dict:
    """Run assess_real_data_quality, print a report, and HARD-FAIL on a corrupt dataset.

    Override with data_source.allow_low_quality: true (strongly discouraged — it lets a backtest
    run on prices that are not arbitrage-coherent).
    """
    rep = assess_real_data_quality(df)
    rv, inv = rep.get("atm_iv_vix_median"), rep.get("term_inversion_rate")
    print(f"  Data-quality check on {name}:")
    print(f"    ATM iv/VIX median:            {rv:.2f}  (clean ~1.0)" if rv is not None
          else "    ATM iv/VIX median:            n/a")
    print(f"    term-structure inversion:     {inv:.0%}  (clean ~0%)" if inv is not None
          else "    term-structure inversion:     n/a")
    print(f"    verdict: {rep['verdict'].upper()}")
    if rep["verdict"] == "corrupt" and not ds.get("allow_low_quality", False):
        raise ValueError(
            f"Real options dataset '{name}' FAILED the data-quality gate: "
            f"{'; '.join(rep['reasons'])}. These prices are not arbitrage-coherent, so any backtest "
            f"on them (especially a calendar, whose P&L IS the near-vs-far relationship) is fiction. "
            f"Point real_data at a clean dataset (e.g. the DoltHub file "
            f"SPY_real_options_2021-01-01_2026-06-08.csv) or, to override anyway (NOT recommended), "
            f"set data_source.allow_low_quality: true."
        )
    return rep


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
    ds = cfg.get("data_source", {})

    # Hybrid mode: real DoltHub data wherever it exists, plus per-date-IV-surface synthetic
    # fill for any (date, expiration) pair that DoltHub does not sample.  The fill uses the
    # day's OWN real DoltHub quotes to fit a bivariate polynomial IV surface (see
    # `iv_surface_fitter.py`), so missing expirations inherit that day's actual skew + term
    # structure rather than a global parametric guess.
    if ds.get("mode") == "hybrid":
        real_name = real_data_filename(cfg)
        synth_name = synthetic_data_filename(cfg)
        real_path = data_dir / real_name
        synth_path = data_dir / synth_name
        if not real_path.exists():
            rd = cfg["real_data"]
            raise FileNotFoundError(
                f"data_source.mode=hybrid but real dataset '{real_name}' missing.\n"
                f"   Build it first:\n"
                f"   opt_venv/bin/python -m src.data_fetchers.real_chain_loader "
                f"--start {rd['start_date']} --end {rd['end_date']}"
            )
        if not synth_path.exists():
            sd = cfg["synthetic_data"]
            raise FileNotFoundError(
                f"data_source.mode=hybrid but synthetic dataset '{synth_name}' missing.\n"
                f"   Run: python generate_synthetic_data.py"
            )

        print(f"Loading REAL dataset:     {real_name}")
        real_data = _read_options_csv(real_path)
        _enforce_data_quality(real_data, ds, real_name)  # refuse arbitrage-incoherent real source
        print(f"Loading SYNTHETIC dataset: {synth_name}")
        synth_data = _read_options_csv(synth_path)

        # Normalize dates for merge key (real = midnight, synth = noon — strip time)
        real_data['_date'] = real_data['quote_date'].dt.normalize()
        real_data['_exp'] = real_data['expiration'].dt.normalize()
        synth_data['_date'] = synth_data['quote_date'].dt.normalize()
        synth_data['_exp'] = synth_data['expiration'].dt.normalize()

        # Build set of (date, expiration) pairs present in real data
        real_pairs = set(zip(real_data['_date'], real_data['_exp']))

        # Keep synthetic rows whose (date, expiration) pair DoltHub did NOT sample
        mask = ~synth_data.apply(
            lambda r: (r['_date'], r['_exp']) in real_pairs, axis=1
        )
        fill_rows = synth_data[mask].copy()

        # Reprice fill rows using per-date IV surfaces fitted from REAL data.
        # For each date where real data exists, fit a bivariate polynomial IV surface
        # from that day's real quotes, then use it to set iv/bid/ask/greeks for the
        # synthetic-fill rows on that date.  Rows for dates without real data (e.g.
        # outside the DoltHub range) keep their original synthetic pricing.
        from src.data_fetchers.iv_surface_fitter import apply_surface_fill
        ds_cfg = ds.get("reprice", {}) or {}
        fill_rows = apply_surface_fill(
            fill_rows, real_data,
            r=float(ds_cfg.get("risk_free_rate", 0.04)),
            spread_frac=float(ds_cfg.get("spread_frac", 0.03)),
            min_spread=float(ds_cfg.get("min_spread", 0.05)),
        )

        # Drop temporary columns
        real_data.drop(columns=['_date', '_exp'], inplace=True)
        fill_rows.drop(columns=['_date', '_exp'], inplace=True)

        # Tag provenance so downstream consumers can distinguish genuine quotes from
        # surface-fit fill. The optimizer uses this to cap far_dte at the REAL data's
        # max DTE — without it the combined max (incl. fill out to synthetic max_dte)
        # lets the search pick far legs in the pure-extrapolation zone (see far_dte=87
        # → $356M artifact). is_fill=False = real DoltHub quote, True = synthetic fill.
        real_data['is_fill'] = False
        fill_rows['is_fill'] = True

        # Combine — real rows first, then surface-fit synthetic fill
        result = pd.concat([real_data, fill_rows], ignore_index=True)
        print(f"  Hybrid: {len(real_data):,} real + {len(fill_rows):,} surface-fit fill"
              f" = {len(result):,} total contracts")

        # Reprice everything from iv column so hybrid entry/exit/remarks share one fair basis
        if ds.get("price_from_iv", True) and "iv" in result.columns:
            rp = ds.get("reprice", {}) or {}
            result = reprice_from_iv(
                result,
                r=float(rp.get("risk_free_rate", 0.04)),
                spread_frac=float(rp.get("spread_frac", 0.03)),
                min_spread=float(rp.get("min_spread", 0.05)),
            )
            print(f"  ✓ Repriced bid/ask from clean IV surface (spread_frac="
                  f"{rp.get('spread_frac', 0.03)}); raw kept as iv_raw_bid/iv_raw_ask")
        return result

    # Real-data mode: load the DoltHub/logged dataset named by the real_data config block.
    # This is the honest dataset (true skew + term structure); synthetic stays the default
    # only for fast plumbing/CI runs.
    if ds.get("mode") == "real":
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
        data = _read_options_csv(real_path)
        # Gate: refuse arbitrage-incoherent data (e.g. Massive/Polygon free-tier closes, which
        # back-solve to inflated IVs and invert the term structure on ~34% of slices). A calendar's
        # P&L IS the near-vs-far relationship, so corrupt prices fabricate the edge.
        _enforce_data_quality(data, ds, real_name)
        # The raw DoltHub bid/ask is the dirty field (mid implies ~1.47x VIX); the iv column is
        # clean. Reprice off iv so entry/exit/remarks share one fair basis and the exits work.
        if ds.get("price_from_iv", True) and "iv" in data.columns:
            rp = ds.get("reprice", {}) or {}
            data = reprice_from_iv(
                data,
                r=float(rp.get("risk_free_rate", 0.04)),
                spread_frac=float(rp.get("spread_frac", 0.03)),
                min_spread=float(rp.get("min_spread", 0.05)),
            )
            print(f"  ✓ Repriced bid/ask from clean IV surface (spread_frac="
                  f"{rp.get('spread_frac', 0.03)}); raw kept as iv_raw_bid/iv_raw_ask")
        return data

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
