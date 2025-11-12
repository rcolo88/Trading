#!/usr/bin/env python3
"""
Test Suite for Watchlist Configuration Module

Tests:
- WatchlistIndex enum values
- WatchlistConfig dataclass initialization
- get_tickers() method for all indexes
- Index fetcher functions (SP500, SP400, SP600, NASDAQ100)
- COMBINED_SP deduplication logic
- Limit parameter functionality
- Custom ticker lists
- Error handling
"""

import unittest
from unittest.mock import patch, MagicMock
from watchlist_config import (
    WatchlistIndex,
    WatchlistConfig,
    get_default_watchlist_config
)


class TestWatchlistIndex(unittest.TestCase):
    """Test WatchlistIndex enum"""

    def test_enum_values(self):
        """Test that all enum values are defined correctly"""
        self.assertEqual(WatchlistIndex.SP500.value, "sp500")
        self.assertEqual(WatchlistIndex.SP400.value, "sp400")
        self.assertEqual(WatchlistIndex.SP600.value, "sp600")
        self.assertEqual(WatchlistIndex.NASDAQ100.value, "nasdaq100")
        self.assertEqual(WatchlistIndex.COMBINED_SP.value, "combined_sp")
        self.assertEqual(WatchlistIndex.CUSTOM.value, "custom")

    def test_enum_members(self):
        """Test that all expected members exist"""
        expected_members = {'SP500', 'SP400', 'SP600', 'NASDAQ100', 'COMBINED_SP', 'CUSTOM'}
        actual_members = {member.name for member in WatchlistIndex}
        self.assertEqual(expected_members, actual_members)


class TestWatchlistConfig(unittest.TestCase):
    """Test WatchlistConfig dataclass"""

    def test_initialization_sp500(self):
        """Test basic initialization with SP500"""
        config = WatchlistConfig(index=WatchlistIndex.SP500)
        self.assertEqual(config.index, WatchlistIndex.SP500)
        self.assertIsNone(config.custom_tickers)
        self.assertIsNone(config.limit)

    def test_initialization_with_limit(self):
        """Test initialization with limit parameter"""
        config = WatchlistConfig(index=WatchlistIndex.SP500, limit=50)
        self.assertEqual(config.index, WatchlistIndex.SP500)
        self.assertEqual(config.limit, 50)

    def test_initialization_custom(self):
        """Test initialization with custom tickers"""
        tickers = ['NVDA', 'GOOGL', 'MSFT']
        config = WatchlistConfig(
            index=WatchlistIndex.CUSTOM,
            custom_tickers=tickers
        )
        self.assertEqual(config.index, WatchlistIndex.CUSTOM)
        self.assertEqual(config.custom_tickers, tickers)

    def test_custom_requires_tickers(self):
        """Test that CUSTOM index requires custom_tickers"""
        config = WatchlistConfig(index=WatchlistIndex.CUSTOM)
        with self.assertRaises(ValueError) as context:
            config.get_tickers()
        self.assertIn("custom_tickers must be provided", str(context.exception))

    @patch('watchlist_config.get_sp500_tickers')
    def test_get_tickers_sp500(self, mock_sp500):
        """Test get_tickers() for SP500"""
        mock_sp500.return_value = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMZN']
        config = WatchlistConfig(index=WatchlistIndex.SP500)
        tickers = config.get_tickers()

        self.assertEqual(len(tickers), 5)
        self.assertIn('AAPL', tickers)
        mock_sp500.assert_called_once()

    @patch('watchlist_config.get_sp400_tickers')
    def test_get_tickers_sp400(self, mock_sp400):
        """Test get_tickers() for SP400"""
        mock_sp400.return_value = ['ABC', 'DEF', 'GHI']
        config = WatchlistConfig(index=WatchlistIndex.SP400)
        tickers = config.get_tickers()

        self.assertEqual(len(tickers), 3)
        self.assertIn('ABC', tickers)
        mock_sp400.assert_called_once()

    @patch('watchlist_config.get_sp600_tickers')
    def test_get_tickers_sp600(self, mock_sp600):
        """Test get_tickers() for SP600"""
        mock_sp600.return_value = ['XYZ', 'JKL']
        config = WatchlistConfig(index=WatchlistIndex.SP600)
        tickers = config.get_tickers()

        self.assertEqual(len(tickers), 2)
        self.assertIn('XYZ', tickers)
        mock_sp600.assert_called_once()

    @patch('watchlist_config.get_nasdaq100_tickers')
    def test_get_tickers_nasdaq100(self, mock_nasdaq):
        """Test get_tickers() for NASDAQ100"""
        mock_nasdaq.return_value = ['TSLA', 'NFLX']
        config = WatchlistConfig(index=WatchlistIndex.NASDAQ100)
        tickers = config.get_tickers()

        self.assertEqual(len(tickers), 2)
        self.assertIn('TSLA', tickers)
        mock_nasdaq.assert_called_once()

    @patch('watchlist_config.get_sp500_tickers')
    @patch('watchlist_config.get_sp400_tickers')
    @patch('watchlist_config.get_sp600_tickers')
    def test_get_tickers_combined_sp(self, mock_sp600, mock_sp400, mock_sp500):
        """Test get_tickers() for COMBINED_SP with deduplication"""
        mock_sp500.return_value = ['AAPL', 'MSFT', 'GOOGL']
        mock_sp400.return_value = ['MSFT', 'IBM', 'ORCL']  # MSFT duplicated
        mock_sp600.return_value = ['XYZ', 'ABC', 'AAPL']   # AAPL duplicated

        config = WatchlistConfig(index=WatchlistIndex.COMBINED_SP)
        tickers = config.get_tickers()

        # Should deduplicate: unique tickers only
        unique_expected = {'AAPL', 'MSFT', 'GOOGL', 'IBM', 'ORCL', 'XYZ', 'ABC'}
        self.assertEqual(len(tickers), len(unique_expected))
        self.assertEqual(set(tickers), unique_expected)

        mock_sp500.assert_called_once()
        mock_sp400.assert_called_once()
        mock_sp600.assert_called_once()

    def test_get_tickers_custom(self):
        """Test get_tickers() for CUSTOM index"""
        custom_tickers = ['NVDA', 'GOOGL', 'MSFT', 'AMZN']
        config = WatchlistConfig(
            index=WatchlistIndex.CUSTOM,
            custom_tickers=custom_tickers
        )
        tickers = config.get_tickers()

        self.assertEqual(tickers, custom_tickers)

    @patch('watchlist_config.get_sp500_tickers')
    def test_get_tickers_with_limit(self, mock_sp500):
        """Test get_tickers() with limit parameter"""
        mock_sp500.return_value = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMZN']
        config = WatchlistConfig(index=WatchlistIndex.SP500, limit=3)
        tickers = config.get_tickers()

        self.assertEqual(len(tickers), 3)
        self.assertEqual(tickers, ['AAPL', 'MSFT', 'GOOGL'])

    @patch('watchlist_config.get_sp500_tickers')
    def test_get_tickers_normalization(self, mock_sp500):
        """Test that tickers are normalized (uppercase, stripped)"""
        mock_sp500.return_value = ['  aapl  ', 'msft', 'GOOGL']
        config = WatchlistConfig(index=WatchlistIndex.SP500)
        tickers = config.get_tickers()

        self.assertEqual(tickers, ['AAPL', 'MSFT', 'GOOGL'])

    @patch('watchlist_config.get_sp500_tickers')
    def test_get_tickers_deduplication(self, mock_sp500):
        """Test that duplicate tickers are removed"""
        mock_sp500.return_value = ['AAPL', 'MSFT', 'AAPL', 'GOOGL', 'MSFT']
        config = WatchlistConfig(index=WatchlistIndex.SP500)
        tickers = config.get_tickers()

        # Should remove duplicates while preserving order
        self.assertEqual(tickers, ['AAPL', 'MSFT', 'GOOGL'])

    @patch('watchlist_config.get_sp500_tickers')
    def test_get_tickers_empty_result(self, mock_sp500):
        """Test handling of empty ticker list"""
        mock_sp500.return_value = []
        config = WatchlistConfig(index=WatchlistIndex.SP500)
        tickers = config.get_tickers()

        self.assertEqual(tickers, [])

    def test_get_ticker_count(self):
        """Test get_ticker_count() method"""
        custom_tickers = ['NVDA', 'GOOGL', 'MSFT']
        config = WatchlistConfig(
            index=WatchlistIndex.CUSTOM,
            custom_tickers=custom_tickers
        )
        count = config.get_ticker_count()

        self.assertEqual(count, 3)

    def test_str_representation_sp500(self):
        """Test __str__() for standard index"""
        config = WatchlistConfig(index=WatchlistIndex.SP500, limit=50)
        string_repr = str(config)

        self.assertIn('sp500', string_repr)
        self.assertIn('limit=50', string_repr)

    def test_str_representation_custom(self):
        """Test __str__() for custom index"""
        config = WatchlistConfig(
            index=WatchlistIndex.CUSTOM,
            custom_tickers=['NVDA', 'GOOGL', 'MSFT']
        )
        string_repr = str(config)

        self.assertIn('CUSTOM', string_repr)
        self.assertIn('3 tickers', string_repr)
        self.assertIn('NVDA', string_repr)


class TestDefaultConfigurations(unittest.TestCase):
    """Test default configuration helpers"""

    def test_get_default_daily_config(self):
        """Test daily default configuration"""
        config = get_default_watchlist_config('daily')
        self.assertEqual(config.index, WatchlistIndex.SP500)
        self.assertEqual(config.limit, 50)

    def test_get_default_weekly_config(self):
        """Test weekly default configuration"""
        config = get_default_watchlist_config('weekly')
        self.assertEqual(config.index, WatchlistIndex.SP500)
        self.assertIsNone(config.limit)

    def test_get_default_monthly_config(self):
        """Test monthly default configuration"""
        config = get_default_watchlist_config('monthly')
        self.assertEqual(config.index, WatchlistIndex.COMBINED_SP)
        self.assertIsNone(config.limit)

    def test_get_default_invalid_frequency(self):
        """Test that invalid frequency raises error"""
        with self.assertRaises(ValueError) as context:
            get_default_watchlist_config('invalid')
        self.assertIn("Unknown frequency", str(context.exception))

    def test_get_default_case_insensitive(self):
        """Test that frequency is case-insensitive"""
        config1 = get_default_watchlist_config('DAILY')
        config2 = get_default_watchlist_config('Daily')
        config3 = get_default_watchlist_config('daily')

        self.assertEqual(config1.index, config2.index)
        self.assertEqual(config2.index, config3.index)


class TestIndexFetchers(unittest.TestCase):
    """Test index fetcher functions (integration tests)"""

    @patch('financial_data_fetcher.pd.read_html')
    def test_get_sp500_tickers_integration(self, mock_read_html):
        """Test SP500 fetcher integration"""
        from financial_data_fetcher import get_sp500_tickers

        # Mock Wikipedia table
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.tolist.return_value = ['AAPL', 'MSFT', 'GOOGL']
        mock_read_html.return_value = [mock_df]

        tickers = get_sp500_tickers()

        self.assertEqual(len(tickers), 3)
        self.assertIn('AAPL', tickers)
        mock_read_html.assert_called_once()

    @patch('financial_data_fetcher.pd.read_html')
    def test_get_sp400_tickers_integration(self, mock_read_html):
        """Test SP400 fetcher integration"""
        from financial_data_fetcher import get_sp400_tickers

        # Mock Wikipedia table
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.tolist.return_value = ['ABC', 'DEF']
        mock_read_html.return_value = [mock_df]

        tickers = get_sp400_tickers()

        self.assertEqual(len(tickers), 2)
        self.assertIn('ABC', tickers)

    @patch('financial_data_fetcher.pd.read_html')
    def test_get_sp600_tickers_integration(self, mock_read_html):
        """Test SP600 fetcher integration"""
        from financial_data_fetcher import get_sp600_tickers

        # Mock Wikipedia table
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.tolist.return_value = ['XYZ']
        mock_read_html.return_value = [mock_df]

        tickers = get_sp600_tickers()

        self.assertEqual(len(tickers), 1)
        self.assertIn('XYZ', tickers)

    @patch('financial_data_fetcher.pd.read_html')
    def test_get_nasdaq100_tickers_integration(self, mock_read_html):
        """Test NASDAQ100 fetcher integration"""
        from financial_data_fetcher import get_nasdaq100_tickers

        # Mock Wikipedia table (NASDAQ-100 is in 4th table, index 3)
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.tolist.return_value = ['TSLA', 'NFLX']
        mock_read_html.return_value = [None, None, None, mock_df]

        tickers = get_nasdaq100_tickers()

        self.assertEqual(len(tickers), 2)
        self.assertIn('TSLA', tickers)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""

    @patch('watchlist_config.get_sp500_tickers')
    def test_fetcher_failure(self, mock_sp500):
        """Test handling of fetcher failures"""
        mock_sp500.return_value = []  # Simulate failure
        config = WatchlistConfig(index=WatchlistIndex.SP500)
        tickers = config.get_tickers()

        self.assertEqual(tickers, [])

    def test_whitespace_only_tickers(self):
        """Test that whitespace-only tickers are filtered out"""
        config = WatchlistConfig(
            index=WatchlistIndex.CUSTOM,
            custom_tickers=['AAPL', '   ', 'MSFT', '']
        )
        tickers = config.get_tickers()

        # Whitespace and empty strings should be filtered
        self.assertEqual(len(tickers), 2)
        self.assertIn('AAPL', tickers)
        self.assertIn('MSFT', tickers)

    def test_none_in_ticker_list(self):
        """Test handling of None values in ticker list"""
        # Mock a fetcher that returns None values
        with patch('watchlist_config.get_sp500_tickers') as mock:
            mock.return_value = ['AAPL', None, 'MSFT', None, 'GOOGL']
            config = WatchlistConfig(index=WatchlistIndex.SP500)
            tickers = config.get_tickers()

            # None values should be filtered out
            self.assertEqual(len(tickers), 3)
            self.assertNotIn(None, tickers)


if __name__ == '__main__':
    # Run all tests with verbose output
    unittest.main(verbosity=2)
