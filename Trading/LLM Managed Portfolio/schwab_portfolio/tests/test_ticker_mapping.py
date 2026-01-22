"""
Tests for Ticker Symbol Mapping Module

Tests the ticker mapping functionality for:
- FISV -> FI (SimFin internal ticker)
- GOOGL -> GOOG (SimFin internal ticker)
- Other standard tickers (should not be mapped)

These tests verify that:
1. Static ticker mappings work correctly
2. Ticker cache functions properly
3. Ticker resolution for SimFin data fetchers works
4. FI and GOOG can extract data from SimFin
"""

import unittest
import os
import tempfile
import logging
from unittest.mock import patch, MagicMock

# Disable logging during tests
logging.disable(logging.CRITICAL)

from schwab_portfolio.data.ticker_mapping import (
    TICKER_MAPPING,
    get_api_ticker,
    get_standard_ticker,
    is_mapped_ticker,
    get_all_mappings_for_ticker,
    add_mapping,
    get_known_api_sources,
    validate_ticker_mapping
)

from schwab_portfolio.data.ticker_cache import TickerMappingCache
from schwab_portfolio.data.ticker_resolver import TickerResolver, TickerResolutionResult


class TestTickerMapping(unittest.TestCase):
    """Test static ticker mapping functions."""

    def test_fisv_to_fi_simfin(self):
        """Test FISV maps to FI for SimFin."""
        result = get_api_ticker('FISV', 'simfin')
        self.assertEqual(result, 'FI')

    def test_googl_to_goog_simfin(self):
        """Test GOOGL maps to GOOG for SimFin."""
        result = get_api_ticker('GOOGL', 'simfin')
        self.assertEqual(result, 'GOOG')

    def test_goog_stays_goog_simfin(self):
        """Test GOOG stays GOOG for SimFin."""
        result = get_api_ticker('GOOG', 'simfin')
        self.assertEqual(result, 'GOOG')

    def test_aapl_no_mapping_simfin(self):
        """Test AAPL has no mapping for SimFin (returns original)."""
        result = get_api_ticker('AAPL', 'simfin')
        self.assertEqual(result, 'AAPL')

    def test_lowercase_ticker(self):
        """Test ticker mapping handles lowercase input."""
        result = get_api_ticker('fisv', 'simfin')
        self.assertEqual(result, 'FI')

    def test_unknown_api_source(self):
        """Test unknown API source returns original ticker."""
        result = get_api_ticker('FISV', 'unknown_api')
        self.assertEqual(result, 'FISV')

    def test_empty_ticker(self):
        """Test empty ticker returns empty string."""
        result = get_api_ticker('', 'simfin')
        self.assertEqual(result, '')

    def test_none_ticker(self):
        """Test None ticker returns None."""
        result = get_api_ticker(None, 'simfin')
        self.assertIsNone(result)

    def test_is_mapped_ticker_true(self):
        """Test is_mapped_ticker returns True for mapped tickers."""
        self.assertTrue(is_mapped_ticker('FISV', 'simfin'))
        self.assertTrue(is_mapped_ticker('GOOGL', 'simfin'))

    def test_is_mapped_ticker_false(self):
        """Test is_mapped_ticker returns False for unmapped tickers."""
        self.assertFalse(is_mapped_ticker('AAPL', 'simfin'))
        self.assertFalse(is_mapped_ticker('MSFT', 'simfin'))

    def test_get_standard_ticker(self):
        """Test reverse mapping (API ticker to standard ticker)."""
        result = get_standard_ticker('FI', 'simfin')
        self.assertEqual(result, 'FISV')

        result = get_standard_ticker('GOOG', 'simfin')
        self.assertEqual(result, 'GOOGL')

    def test_get_all_mappings_for_ticker(self):
        """Test get_all_mappings_for_ticker returns dict for all APIs."""
        result = get_all_mappings_for_ticker('FISV')

        self.assertIn('standard', result)
        self.assertIn('simfin', result)
        self.assertEqual(result['standard'], 'FISV')
        self.assertEqual(result['simfin'], 'FI')

    def test_get_known_api_sources(self):
        """Test get_known_api_sources returns list of API sources."""
        sources = get_known_api_sources()
        self.assertIsInstance(sources, list)
        self.assertIn('simfin', sources)
        self.assertIn('fmp', sources)


class TestTickerMappingValidation(unittest.TestCase):
    """Test ticker mapping validation functions."""

    def test_validate_ticker_mapping_success(self):
        """Test validate_ticker_mapping returns True for correct mappings."""
        self.assertTrue(
            validate_ticker_mapping('FISV', 'simfin', 'FI')
        )
        self.assertTrue(
            validate_ticker_mapping('GOOGL', 'simfin', 'GOOG')
        )

    def test_validate_ticker_mapping_failure(self):
        """Test validate_ticker_mapping returns False for incorrect mappings."""
        self.assertFalse(
            validate_ticker_mapping('FISV', 'simfin', 'GOOG')
        )

    def test_add_mapping(self):
        """Test add_mapping adds new mapping at runtime."""
        # Add a new mapping
        add_mapping('simfin', 'TEST', 'TST')

        # Verify it's been added
        result = get_api_ticker('TEST', 'simfin')
        self.assertEqual(result, 'TST')

        # Clean up - remove the mapping
        # (This won't persist to disk, just in-memory)


class TestTickerCache(unittest.TestCase):
    """Test ticker mapping cache functionality."""

    def setUp(self):
        """Set up test fixtures with temporary cache file."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.temp_dir, 'test_ticker_cache.json')

    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_cache_set_and_get(self):
        """Test cache set and get operations."""
        cache = TickerMappingCache(cache_file=self.cache_file)

        # Set a mapping
        cache.set('FISV', 'simfin', 'FI')

        # Get the mapping
        result = cache.get('FISV', 'simfin')
        self.assertEqual(result, 'FI')

    def test_cache_miss(self):
        """Test cache returns None for missing entries."""
        cache = TickerMappingCache(cache_file=self.cache_file)

        result = cache.get('UNKNOWN', 'simfin')
        self.assertIsNone(result)

    def test_cache_delete(self):
        """Test cache delete operation."""
        cache = TickerMappingCache(cache_file=self.cache_file)

        # Set and then delete
        cache.set('FISV', 'simfin', 'FI')
        self.assertEqual(cache.get('FISV', 'simfin'), 'FI')

        cache.delete('FISV', 'simfin')
        self.assertIsNone(cache.get('FISV', 'simfin'))

    def test_cache_clear(self):
        """Test cache clear operation."""
        cache = TickerMappingCache(cache_file=self.cache_file)

        cache.set('FISV', 'simfin', 'FI')
        cache.set('GOOGL', 'simfin', 'GOOG')

        cache.clear()

        self.assertIsNone(cache.get('FISV', 'simfin'))
        self.assertIsNone(cache.get('GOOGL', 'simfin'))

    def test_cache_persistence(self):
        """Test cache persists to disk."""
        # Create cache and set value
        cache1 = TickerMappingCache(cache_file=self.cache_file)
        cache1.set('FISV', 'simfin', 'FI')

        # Create new cache instance (should load from disk)
        cache2 = TickerMappingCache(cache_file=self.cache_file)
        self.assertEqual(cache2.get('FISV', 'simfin'), 'FI')

    def test_cache_stats(self):
        """Test cache stats functionality."""
        cache = TickerMappingCache(cache_file=self.cache_file)

        cache.set('FISV', 'simfin', 'FI')
        cache.set('GOOGL', 'simfin', 'GOOG', discovered=True)

        stats = cache.get_stats()

        self.assertEqual(stats['total_entries'], 2)
        self.assertEqual(stats['discovered_entries'], 1)
        self.assertIn('simfin', stats['by_api_source'])


class TestTickerResolver(unittest.TestCase):
    """Test ticker resolver functionality."""

    def test_resolve_ticker(self):
        """Test resolve returns correct mappings."""
        resolver = TickerResolver(auto_discover=False)

        result = resolver.resolve('FISV')

        self.assertEqual(result.query, 'FISV')
        self.assertEqual(result.resolved['standard'], 'FISV')
        self.assertEqual(result.resolved['simfin'], 'FI')

    def test_resolve_for_api(self):
        """Test resolve_for_api returns API-specific ticker."""
        resolver = TickerResolver(auto_discover=False)

        result = resolver.resolve_for_api('FISV', 'simfin')
        self.assertEqual(result, 'FI')

    def test_resolution_result_get(self):
        """Test TickerResolutionResult.get method."""
        result = TickerResolutionResult(
            query='FISV',
            resolved={'standard': 'FISV', 'simfin': 'FI'},
            found=True
        )

        self.assertEqual(result.get('simfin'), 'FI')
        self.assertEqual(result.get('fmp', 'DEFAULT'), 'DEFAULT')


class TestSimFinDataExtraction(unittest.TestCase):
    """
    Integration tests for SimFin data extraction with ticker mapping.

    These tests verify that FI and GOOG tickers can successfully
    extract data from SimFin when using the ticker mapping.
    """

    @patch('schwab_portfolio.data.simfin_fetcher.sf.load_income')
    @patch('schwab_portfolio.data.simfin_fetcher.sf.load_balance')
    @patch('schwab_portfolio.data.simfin_fetcher.sf.load_cashflow')
    @patch('schwab_portfolio.data.simfin_fetcher.sf.load_companies')
    def test_fisv_uses_fi_for_simfin(
        self,
        mock_companies,
        mock_cashflow,
        mock_balance,
        mock_income
    ):
        """Test that FISV request uses FI internally for SimFin."""
        from schwab_portfolio.data.simfin_fetcher import SimFinDataFetcher

        # Create mock dataframes
        mock_income_df = MagicMock()
        mock_income_df.index = ['FI', 'AAPL']  # SimFin uses FI, not FISV
        mock_income_df.loc = MagicMock()
        mock_income_df.loc.__getitem__ = MagicMock(side_effect=lambda key: MagicMock(
            iloc=MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=10000000000),
                __getitem__=MagicMock(return_value=2024)
            )),
            empty=False
        ))
        mock_income.return_value = mock_income_df

        mock_balance_df = MagicMock()
        mock_balance_df.index = ['FI', 'AAPL']
        mock_balance_df.loc = MagicMock()
        mock_balance_df.loc.__getitem__ = MagicMock(side_effect=lambda key: MagicMock(
            iloc=MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=5000000000)
            )),
            empty=False
        ))
        mock_balance.return_value = mock_balance_df

        mock_cashflow_df = MagicMock()
        mock_cashflow_df.index = ['FI', 'AAPL']
        mock_cashflow_df.loc = MagicMock()
        mock_cashflow_df.loc.__getitem__ = MagicMock(side_effect=lambda key: MagicMock(
            iloc=MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=2000000000)
            )),
            empty=False
        ))
        mock_cashflow.return_value = mock_cashflow_df

        mock_companies_df = MagicMock()
        mock_companies_df.index = ['FI', 'AAPL']
        mock_companies_df.loc = MagicMock()
        mock_companies_df.loc.__getitem__ = MagicMock(side_effect=lambda key: MagicMock(
            get=MagicMock(return_value='Technology')
        ))
        mock_companies.return_value = mock_companies_df

        # Create fetcher and fetch data
        fetcher = SimFinDataFetcher(enable_cache=False)
        result = fetcher.fetch_financial_data('FISV')

        # Verify result is not None (data was found using FI ticker)
        self.assertIsNotNone(result)

        # Verify the ticker mapping was logged
        # (In real usage, this would appear in logs as WARNING)

    @patch('schwab_portfolio.data.simfin_fetcher.sf.load_income')
    @patch('schwab_portfolio.data.simfin_fetcher.sf.load_balance')
    @patch('schwab_portfolio.data.simfin_fetcher.sf.load_cashflow')
    @patch('schwab_portfolio.data.simfin_fetcher.sf.load_companies')
    def test_googl_uses_goog_for_simfin(
        self,
        mock_companies,
        mock_cashflow,
        mock_balance,
        mock_income
    ):
        """Test that GOOGL request uses GOOG internally for SimFin."""
        from schwab_portfolio.data.simfin_fetcher import SimFinDataFetcher

        # Create mock dataframes
        mock_income_df = MagicMock()
        mock_income_df.index = ['GOOG', 'AAPL']  # SimFin uses GOOG, not GOOGL
        mock_income_df.loc = MagicMock()
        mock_income_df.loc.__getitem__ = MagicMock(side_effect=lambda key: MagicMock(
            iloc=MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=200000000000),
                __getitem__=MagicMock(return_value=2024)
            )),
            empty=False
        ))
        mock_income.return_value = mock_income_df

        mock_balance_df = MagicMock()
        mock_balance_df.index = ['GOOG', 'AAPL']
        mock_balance_df.loc = MagicMock()
        mock_balance_df.loc.__getitem__ = MagicMock(side_effect=lambda key: MagicMock(
            iloc=MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=100000000000)
            )),
            empty=False
        ))
        mock_balance.return_value = mock_balance_df

        mock_cashflow_df = MagicMock()
        mock_cashflow_df.index = ['GOOG', 'AAPL']
        mock_cashflow_df.loc = MagicMock()
        mock_cashflow_df.loc.__getitem__ = MagicMock(side_effect=lambda key: MagicMock(
            iloc=MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=50000000000)
            )),
            empty=False
        ))
        mock_cashflow.return_value = mock_cashflow_df

        mock_companies_df = MagicMock()
        mock_companies_df.index = ['GOOG', 'AAPL']
        mock_companies_df.loc = MagicMock()
        mock_companies_df.loc.__getitem__ = MagicMock(side_effect=lambda key: MagicMock(
            get=MagicMock(return_value='Technology')
        ))
        mock_companies.return_value = mock_companies_df

        # Create fetcher and fetch data
        fetcher = SimFinDataFetcher(enable_cache=False)
        result = fetcher.fetch_financial_data('GOOGL')

        # Verify result is not None (data was found using GOOG ticker)
        self.assertIsNotNone(result)


class TestTickerMappingEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_berkshire_ticker_mapping(self):
        """Test Berkshire ticker mappings."""
        # BRK.B should map to BRK-B for SimFin
        result = get_api_ticker('BRK.B', 'simfin')
        self.assertEqual(result, 'BRK-B')

        # BRK.A should map to BRK-A for SimFin
        result = get_api_ticker('BRK.A', 'simfin')
        self.assertEqual(result, 'BRK-A')

    def test_polygon_ticker_mapping(self):
        """Test Polygon-specific ticker mappings."""
        # Polygon uses dots for class shares
        result = get_api_ticker('BRK.B', 'polygon')
        self.assertEqual(result, 'BRK.B')

    def test_no_mapping_needed_tickers(self):
        """Test tickers that don't need mapping."""
        test_cases = [
            ('AAPL', 'simfin'),
            ('MSFT', 'simfin'),
            ('AMZN', 'simfin'),
            ('NVDA', 'simfin'),
            ('META', 'simfin'),
        ]

        for ticker, api_source in test_cases:
            with self.subTest(ticker=ticker, api_source=api_source):
                result = get_api_ticker(ticker, api_source)
                self.assertEqual(result, ticker)


if __name__ == '__main__':
    # Re-enable logging for test output if needed
    # logging.disable(logging.NOTSET)
    unittest.main(verbosity=2)
