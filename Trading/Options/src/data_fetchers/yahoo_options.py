"""
Yahoo Finance data fetcher.

Fetches underlying stock/ETF data and current options chains from Yahoo Finance.
Note: Yahoo Finance does not provide historical options data, only current chains.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import yfinance as yf
import numpy as np


class YahooDataFetcher:
    """Fetch data from Yahoo Finance."""

    def __init__(self, symbol: str = "SPY"):
        """
        Initialize Yahoo Finance data fetcher.

        Args:
            symbol: Ticker symbol (default: SPY)
        """
        self.symbol = symbol
        self.ticker = yf.Ticker(symbol)

    def get_underlying_data(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get historical underlying price data.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data
        """
        print(f"Fetching {self.symbol} price data from {start_date} to {end_date}")

        data = self.ticker.history(
            start=start_date,
            end=end_date,
            interval='1d'
        )

        if data.empty:
            raise ValueError(f"No data found for {self.symbol}")

        # Standardize column names
        data.columns = [col.lower() for col in data.columns]

        print(f"Retrieved {len(data)} days of data")

        return data

    def get_current_options_chain(self) -> pd.DataFrame:
        """
        Get current options chain data.

        Note: This returns current data only, not historical.
        Useful for validation and understanding current market structure.

        Returns:
            DataFrame with current options chain
        """
        print(f"Fetching current options chain for {self.symbol}")

        expirations = self.ticker.options

        if not expirations:
            raise ValueError(f"No options data available for {self.symbol}")

        all_options = []

        for exp_date in expirations[:6]:  # Get next 6 expirations
            opt = self.ticker.option_chain(exp_date)

            # Process calls
            calls = opt.calls.copy()
            calls['option_type'] = 'call'
            calls['expiration'] = pd.to_datetime(exp_date)

            # Process puts
            puts = opt.puts.copy()
            puts['option_type'] = 'put'
            puts['expiration'] = pd.to_datetime(exp_date)

            all_options.append(calls)
            all_options.append(puts)

        options_df = pd.concat(all_options, ignore_index=True)

        # Calculate DTE
        options_df['quote_date'] = pd.Timestamp.now()
        options_df['dte'] = (options_df['expiration'] - options_df['quote_date']).dt.days

        # Add underlying info
        current_price = self.ticker.info.get('regularMarketPrice', 0)
        options_df['underlying_symbol'] = self.symbol
        options_df['underlying_price'] = current_price

        # Standardize column names for consistency
        column_mapping = {
            'contractSymbol': 'contract_symbol',
            'lastTradeDate': 'last_trade_date',
            'lastPrice': 'last',
            'bid': 'bid',
            'ask': 'ask',
            'volume': 'volume',
            'openInterest': 'open_interest',
            'impliedVolatility': 'iv'
        }

        options_df = options_df.rename(columns=column_mapping)

        # Calculate Greeks if not present (using Black-Scholes approximation)
        if 'delta' not in options_df.columns:
            options_df['delta'] = self._estimate_delta(options_df)

        print(f"Retrieved {len(options_df)} option contracts")

        return options_df

    def _estimate_delta(self, options_df: pd.DataFrame) -> pd.Series:
        """
        Estimate delta for options (simplified approximation).

        For a more accurate calculation, use py_vollib or implement Black-Scholes.
        This is a rough approximation for demonstration.

        Args:
            options_df: Options data

        Returns:
            Series with estimated delta values
        """
        deltas = []

        for _, row in options_df.iterrows():
            strike = row['strike']
            underlying = row['underlying_price']
            option_type = row['option_type']

            # Very simple approximation:
            # ATM options have delta ~0.5 (calls) or ~-0.5 (puts)
            # ITM options approach 1.0/-1.0
            # OTM options approach 0

            moneyness = underlying / strike if strike != 0 else 1

            if option_type == 'call':
                if moneyness > 1.1:  # ITM
                    delta = 0.7 + (moneyness - 1.1) * 0.5
                elif moneyness < 0.9:  # OTM
                    delta = 0.3 - (0.9 - moneyness) * 0.5
                else:  # ATM
                    delta = 0.5
            else:  # put
                if moneyness < 0.9:  # ITM
                    delta = -0.7 - (0.9 - moneyness) * 0.5
                elif moneyness > 1.1:  # OTM
                    delta = -0.3 + (moneyness - 1.1) * 0.5
                else:  # ATM
                    delta = -0.5

            # Clamp delta between -1 and 1
            delta = max(-1, min(1, delta))
            deltas.append(delta)

        return pd.Series(deltas, index=options_df.index)

    def get_info(self) -> Dict:
        """Get ticker information."""
        return self.ticker.info


# Utility function for easy access
def fetch_spy_data(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Convenience function to fetch SPY data.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with SPY price data
    """
    fetcher = YahooDataFetcher("SPY")
    return fetcher.get_underlying_data(start_date, end_date)
