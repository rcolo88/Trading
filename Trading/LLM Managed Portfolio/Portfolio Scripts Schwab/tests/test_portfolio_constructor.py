#!/usr/bin/env python3
"""
Test Suite for Portfolio Constructor Module - 4-Tier Market Cap Framework

Tests position sizing, allocation calculation, rebalancing, and risk parameters
for the 4-tier market cap framework (Large/Mid/Small/Thematic).

Author: LLM Portfolio Management System
Date: November 6, 2025
"""

import unittest
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Import the module to test
from core.portfolio_constructor import (
    PortfolioConstructor,
    TieredAllocation,
    AllocationReport,
    RiskParameters
)
from quality.market_cap_classifier import MarketCapTier


class TestPositionSizing(unittest.TestCase):
    """Test tier-specific position sizing calculations"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_large_cap_roe_20_plus(self):
        """Test large cap position sizing for ROE ≥20%"""
        position_pct = self.constructor.calculate_large_cap_position_size(0.25)  # 25% ROE
        self.assertEqual(position_pct, 12.5)  # Midpoint of 10-15%

        position_pct = self.constructor.calculate_large_cap_position_size(0.20)  # 20% ROE exactly
        self.assertEqual(position_pct, 12.5)

    def test_large_cap_roe_15_to_20(self):
        """Test large cap position sizing for ROE 15-20%"""
        position_pct = self.constructor.calculate_large_cap_position_size(0.18)  # 18% ROE
        self.assertEqual(position_pct, 10.0)  # Midpoint of 8-12%

        position_pct = self.constructor.calculate_large_cap_position_size(0.15)  # 15% ROE exactly
        self.assertEqual(position_pct, 10.0)

    def test_large_cap_below_threshold(self):
        """Test large cap exit when ROE <15%"""
        position_pct = self.constructor.calculate_large_cap_position_size(0.12)  # 12% ROE
        self.assertEqual(position_pct, 0.0)  # EXIT

    def test_mid_cap_with_incremental_roce(self):
        """Test mid cap position sizing with incremental ROCE advantage"""
        # ROE 20%+, incremental ROCE +5%
        position_pct = self.constructor.calculate_mid_cap_position_size(0.22, 8.0)
        self.assertEqual(position_pct, 8.5)  # Midpoint of 7-10%

        # ROE 15-20%, incremental ROCE +5%
        position_pct = self.constructor.calculate_mid_cap_position_size(0.18, 6.0)
        self.assertEqual(position_pct, 6.5)  # Midpoint of 5-8%

    def test_mid_cap_without_incremental_roce(self):
        """Test mid cap position sizing without incremental ROCE advantage"""
        # ROE 20%+ but no incremental ROCE advantage
        position_pct = self.constructor.calculate_mid_cap_position_size(0.22, 2.0)
        self.assertEqual(position_pct, 6.5)  # Conservative sizing

        # ROE 15-20%, no incremental ROCE advantage
        position_pct = self.constructor.calculate_mid_cap_position_size(0.18, 3.0)
        self.assertEqual(position_pct, 5.0)  # Minimum position

    def test_mid_cap_below_threshold(self):
        """Test mid cap exit when ROE <15%"""
        position_pct = self.constructor.calculate_mid_cap_position_size(0.12, 8.0)
        self.assertEqual(position_pct, 0.0)  # EXIT

    def test_small_cap_top_quality(self):
        """Test small cap position sizing for top quality (≥80)"""
        position_pct = self.constructor.calculate_small_cap_position_size(True, 85.0)
        self.assertEqual(position_pct, 4.0)  # Maximum for small cap

    def test_small_cap_mid_quality(self):
        """Test small cap position sizing for mid quality (70-80)"""
        position_pct = self.constructor.calculate_small_cap_position_size(True, 75.0)
        self.assertEqual(position_pct, 3.0)

    def test_small_cap_low_quality(self):
        """Test small cap position sizing for low quality (60-70)"""
        position_pct = self.constructor.calculate_small_cap_position_size(True, 65.0)
        self.assertEqual(position_pct, 2.0)  # Minimum position

    def test_small_cap_fails_strict_filters(self):
        """Test small cap exit when failing strict filters"""
        position_pct = self.constructor.calculate_small_cap_position_size(False, 90.0)
        self.assertEqual(position_pct, 0.0)  # EXIT even with high quality

    def test_small_cap_bottom_quintile(self):
        """Test small cap exit for bottom quintile quality (<60)"""
        position_pct = self.constructor.calculate_small_cap_position_size(True, 55.0)
        self.assertEqual(position_pct, 0.0)  # EXIT

    def test_thematic_position_sizing(self):
        """Test thematic position sizing (uniform 2%)"""
        position_pct = self.constructor.calculate_thematic_position_size(35.0)
        self.assertEqual(position_pct, 2.0)

        position_pct = self.constructor.calculate_thematic_position_size(28.0)
        self.assertEqual(position_pct, 2.0)  # Meets threshold

    def test_thematic_below_threshold(self):
        """Test thematic exit when score <28"""
        position_pct = self.constructor.calculate_thematic_position_size(27.5)
        self.assertEqual(position_pct, 0.0)  # EXIT


class TestSmallCapFilters(unittest.TestCase):
    """Test small cap strict quality filters"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_passes_all_filters(self):
        """Test small cap that passes all strict filters"""
        financial_data = {
            'free_cash_flow': 100e6,  # Positive FCF
            'total_debt': 200e6,
            'shareholder_equity': 500e6,  # D/E = 0.4 (<1.0)
            'gross_margin': 0.35  # 35% (>30%)
        }
        passes, failed = self.constructor.validate_small_cap_filters('TEST', financial_data)
        self.assertTrue(passes)
        self.assertEqual(len(failed), 0)

    def test_fails_fcf_requirement(self):
        """Test small cap failure on FCF requirement"""
        financial_data = {
            'free_cash_flow': -50e6,  # Negative FCF
            'total_debt': 200e6,
            'shareholder_equity': 500e6,
            'gross_margin': 0.35
        }
        passes, failed = self.constructor.validate_small_cap_filters('TEST', financial_data)
        self.assertFalse(passes)
        self.assertTrue(any('FCF' in f for f in failed))

    def test_fails_debt_equity_requirement(self):
        """Test small cap failure on D/E requirement"""
        financial_data = {
            'free_cash_flow': 100e6,
            'total_debt': 600e6,
            'shareholder_equity': 500e6,  # D/E = 1.2 (>1.0)
            'gross_margin': 0.35
        }
        passes, failed = self.constructor.validate_small_cap_filters('TEST', financial_data)
        self.assertFalse(passes)
        self.assertTrue(any('D/E' in f for f in failed))

    def test_fails_gross_margin_requirement(self):
        """Test small cap failure on gross margin requirement"""
        financial_data = {
            'free_cash_flow': 100e6,
            'total_debt': 200e6,
            'shareholder_equity': 500e6,
            'gross_margin': 0.25  # 25% (<30%)
        }
        passes, failed = self.constructor.validate_small_cap_filters('TEST', financial_data)
        self.assertFalse(passes)
        self.assertTrue(any('Gross margin' in f for f in failed))

    def test_fails_multiple_requirements(self):
        """Test small cap failing multiple filters"""
        financial_data = {
            'free_cash_flow': -50e6,  # Fail
            'total_debt': 600e6,
            'shareholder_equity': 500e6,  # D/E = 1.2, Fail
            'gross_margin': 0.20  # 20%, Fail
        }
        passes, failed = self.constructor.validate_small_cap_filters('TEST', financial_data)
        self.assertFalse(passes)
        self.assertEqual(len(failed), 3)  # All 3 filters fail


class TestAllocationCalculation(unittest.TestCase):
    """Test target allocation calculation with 4-tier framework"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_balanced_4_tier_portfolio(self):
        """Test allocation with all 4 tiers represented"""
        holdings_by_tier = {
            MarketCapTier.LARGE_CAP: {
                'AAPL': 0.25,  # 25% ROE
                'MSFT': 0.18   # 18% ROE
            },
            MarketCapTier.MID_CAP: {
                'NVDA': {'roe': 0.18, 'incremental_roce_advantage': 8.0}
            },
            MarketCapTier.SMALL_CAP: {
                'QS': {'quality_score': 75.0}
            },
            'THEMATIC': {
                'IONQ': 32.0  # Thematic score
            }
        }

        financial_data = {
            'QS': {
                'free_cash_flow': 100e6,
                'total_debt': 200e6,
                'shareholder_equity': 500e6,
                'gross_margin': 0.35
            }
        }

        allocation = self.constructor.calculate_target_allocation(
            holdings_by_tier, financial_data, 100000.0
        )

        # Check tier allocations are within target ranges
        self.assertGreaterEqual(allocation.total_large_cap_pct, 62.5)  # 67.5% ± 2.5%
        self.assertLessEqual(allocation.total_large_cap_pct, 72.5)

        self.assertGreaterEqual(allocation.total_mid_cap_pct, 12.5)  # 17.5% ± 2.5%
        self.assertLessEqual(allocation.total_mid_cap_pct, 22.5)

        self.assertGreaterEqual(allocation.total_small_cap_pct, 7.5)  # 12.5% ± 2.5%
        self.assertLessEqual(allocation.total_small_cap_pct, 17.5)

        self.assertGreaterEqual(allocation.total_thematic_pct, 2.5)  # 7.5% ± 2.5%
        self.assertLessEqual(allocation.total_thematic_pct, 12.5)

        # Check total sums to ~100% (may be over 100% if all tiers at target)
        total = (allocation.total_large_cap_pct + allocation.total_mid_cap_pct +
                 allocation.total_small_cap_pct + allocation.total_thematic_pct +
                 allocation.cash_reserve)
        self.assertAlmostEqual(total, 100.0, places=0)

        # When all 4 tiers are at target (105% allocated), cash will be negative
        # This should generate violations
        if allocation.cash_reserve < 3.0:
            self.assertGreater(len(allocation.violations), 0,
                             "Should have violations when cash reserve insufficient")

    def test_large_cap_only_portfolio(self):
        """Test allocation with only large cap holdings"""
        holdings_by_tier = {
            MarketCapTier.LARGE_CAP: {
                'AAPL': 0.25,
                'MSFT': 0.18,
                'GOOGL': 0.22
            }
        }

        allocation = self.constructor.calculate_target_allocation(
            holdings_by_tier, {}, 100000.0
        )

        # Large cap should be normalized to target 67.5%
        self.assertAlmostEqual(allocation.total_large_cap_pct, 67.5, places=0)
        self.assertEqual(allocation.total_mid_cap_pct, 0.0)
        self.assertEqual(allocation.total_small_cap_pct, 0.0)
        self.assertEqual(allocation.total_thematic_pct, 0.0)

        # Should have violations for missing tiers
        self.assertGreater(len(allocation.violations), 0)

    def test_small_cap_filtered_out(self):
        """Test that small cap failing filters is excluded"""
        holdings_by_tier = {
            MarketCapTier.LARGE_CAP: {'AAPL': 0.20},
            MarketCapTier.SMALL_CAP: {
                'QS': {'quality_score': 80.0}  # High quality but will fail filters
            }
        }

        financial_data = {
            'QS': {
                'free_cash_flow': -50e6,  # Negative FCF - FAIL
                'total_debt': 200e6,
                'shareholder_equity': 500e6,
                'gross_margin': 0.35
            }
        }

        allocation = self.constructor.calculate_target_allocation(
            holdings_by_tier, financial_data, 100000.0
        )

        # QS should be excluded due to failing FCF filter
        self.assertNotIn('QS', allocation.small_cap_holdings)
        self.assertEqual(allocation.total_small_cap_pct, 0.0)

    def test_normalization_to_targets(self):
        """Test that each tier is normalized to target percentage"""
        holdings_by_tier = {
            MarketCapTier.LARGE_CAP: {
                'AAPL': 0.25,  # Raw: 12.5%
                'MSFT': 0.20   # Raw: 12.5%
                # Total raw: 25%, should normalize to 67.5%
            },
            MarketCapTier.MID_CAP: {
                'NVDA': {'roe': 0.20, 'incremental_roce_advantage': 8.0}
                # Raw: 8.5%, should normalize to 17.5%
            }
        }

        allocation = self.constructor.calculate_target_allocation(
            holdings_by_tier, {}, 100000.0
        )

        # Large cap should be exactly 67.5%
        self.assertAlmostEqual(allocation.total_large_cap_pct, 67.5, places=1)
        # Mid cap should be exactly 17.5%
        self.assertAlmostEqual(allocation.total_mid_cap_pct, 17.5, places=1)

    def test_position_limits_respected(self):
        """Test that position limits are checked (may be violated and reported)"""
        holdings_by_tier = {
            MarketCapTier.LARGE_CAP: {
                'AAPL': 0.30,   # Very high ROE
                'MSFT': 0.25,   # High ROE
                'GOOGL': 0.22,  # High ROE
                'META': 0.20,   # High ROE
                'NVDA': 0.18    # Good ROE
            }
        }

        allocation = self.constructor.calculate_target_allocation(
            holdings_by_tier, {}, 100000.0
        )

        # With 5 holdings splitting 67.5%, each gets ~13.5%, which is under 15% limit
        for ticker, pct in allocation.large_cap_holdings.items():
            self.assertLessEqual(pct, 15.0, f"{ticker} position {pct:.1f}% should be ≤15%")

        # Total large cap should be at target
        self.assertAlmostEqual(allocation.total_large_cap_pct, 67.5, places=1)


class TestValidation(unittest.TestCase):
    """Test constraint violation detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_large_cap_below_minimum(self):
        """Test detection of large cap allocation below 62.5%"""
        allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 10.0},
            mid_cap_holdings={'NVDA': 20.0},
            small_cap_holdings={},
            thematic_holdings={},
            cash_reserve=70.0,
            total_large_cap_pct=60.0,  # Below 62.5%
            total_mid_cap_pct=20.0,
            total_small_cap_pct=0.0,
            total_thematic_pct=0.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('Large cap' in v and 'below' in v for v in violations))

    def test_large_cap_above_maximum(self):
        """Test detection of large cap allocation above 72.5%"""
        allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 75.0},
            mid_cap_holdings={},
            small_cap_holdings={},
            thematic_holdings={},
            cash_reserve=25.0,
            total_large_cap_pct=75.0,  # Above 72.5%
            total_mid_cap_pct=0.0,
            total_small_cap_pct=0.0,
            total_thematic_pct=0.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('Large cap' in v and 'above' in v for v in violations))

    def test_mid_cap_below_minimum(self):
        """Test detection of mid cap allocation below 12.5%"""
        allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 70.0},
            mid_cap_holdings={'NVDA': 10.0},
            small_cap_holdings={},
            thematic_holdings={},
            cash_reserve=20.0,
            total_large_cap_pct=70.0,
            total_mid_cap_pct=10.0,  # Below 12.5%
            total_small_cap_pct=0.0,
            total_thematic_pct=0.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('Mid cap' in v and 'below' in v for v in violations))

    def test_position_exceeds_tier_limit(self):
        """Test detection of positions exceeding tier-specific limits"""
        allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 20.0},  # Exceeds 15% large cap limit
            mid_cap_holdings={'NVDA': 12.0},    # Exceeds 10% mid cap limit
            small_cap_holdings={'QS': 5.0},     # Exceeds 4% small cap limit
            thematic_holdings={'IONQ': 3.0},    # Exceeds 2.5% thematic limit
            cash_reserve=60.0,
            total_large_cap_pct=20.0,
            total_mid_cap_pct=12.0,
            total_small_cap_pct=5.0,
            total_thematic_pct=3.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)

        # Should have violations for all 4 tiers
        self.assertTrue(any('AAPL' in v and 'exceeds' in v for v in violations))
        self.assertTrue(any('NVDA' in v and 'exceeds' in v for v in violations))
        self.assertTrue(any('QS' in v and 'exceeds' in v for v in violations))
        self.assertTrue(any('IONQ' in v and 'exceeds' in v for v in violations))

    def test_insufficient_cash_reserve(self):
        """Test detection of cash reserve below 3%"""
        allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 67.5},
            mid_cap_holdings={'NVDA': 17.5},
            small_cap_holdings={'QS': 12.5},
            thematic_holdings={},
            cash_reserve=2.5,  # Below 3%
            total_large_cap_pct=67.5,
            total_mid_cap_pct=17.5,
            total_small_cap_pct=12.5,
            total_thematic_pct=0.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('Cash reserve' in v and 'below' in v for v in violations))

    def test_valid_allocation_no_violations(self):
        """Test that valid 4-tier allocation has no violations"""
        allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 12.5, 'MSFT': 10.0},
            mid_cap_holdings={'NVDA': 8.5},
            small_cap_holdings={'QS': 3.0},
            thematic_holdings={'IONQ': 2.0},
            cash_reserve=5.0,
            total_large_cap_pct=67.5,  # Within 62.5-72.5%
            total_mid_cap_pct=17.5,    # Within 12.5-22.5%
            total_small_cap_pct=12.5,  # Within 7.5-17.5%
            total_thematic_pct=7.5,    # Within 2.5-12.5%
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertEqual(len(violations), 0, f"Expected no violations but got: {violations}")


class TestRebalancingTrades(unittest.TestCase):
    """Test rebalancing trade generation"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_generate_rebalancing_trades(self):
        """Test generation of rebalancing trades"""
        portfolio_state = {
            'cash': 500.0,
            'holdings': {
                'AAPL': {'shares': 10, 'entry_price': 150.0},
                'MSFT': {'shares': 5, 'entry_price': 400.0}
            }
        }

        target_allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 12.5, 'MSFT': 10.0, 'GOOGL': 10.0},
            mid_cap_holdings={'NVDA': 8.5},
            small_cap_holdings={},
            thematic_holdings={},
            cash_reserve=5.0,
            total_large_cap_pct=67.5,
            total_mid_cap_pct=17.5,
            total_small_cap_pct=12.5,
            total_thematic_pct=7.5,
            violations=[]
        )

        current_prices = {'AAPL': 180.0, 'MSFT': 450.0, 'GOOGL': 150.0, 'NVDA': 500.0}

        trades = self.constructor.generate_rebalancing_trades(
            portfolio_state, target_allocation, current_prices
        )

        # Should generate BUY orders for new positions (GOOGL, NVDA)
        buy_trades = [t for t in trades if t['action'] == 'BUY']
        self.assertGreater(len(buy_trades), 0)

        # Verify trades have required fields
        for trade in trades:
            self.assertIn('action', trade)
            self.assertIn('ticker', trade)
            self.assertIn('shares', trade)
            self.assertIn('reasoning', trade)
            self.assertIn('priority', trade)

    def test_minimum_trade_size_respected(self):
        """Test that trades below $50 are not generated"""
        portfolio_state = {
            'cash': 10000.0,
            'holdings': {
                'AAPL': {'shares': 50, 'entry_price': 150.0}
            }
        }

        # Target allocation very close to current (should produce tiny trades)
        target_allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 67.5},
            mid_cap_holdings={},
            small_cap_holdings={},
            thematic_holdings={},
            cash_reserve=32.5,
            total_large_cap_pct=67.5,
            total_mid_cap_pct=0.0,
            total_small_cap_pct=0.0,
            total_thematic_pct=0.0,
            violations=[]
        )

        current_prices = {'AAPL': 180.0}

        trades = self.constructor.generate_rebalancing_trades(
            portfolio_state, target_allocation, current_prices
        )

        # Verify all trades meet minimum size
        for trade in trades:
            ticker = trade['ticker']
            shares = trade['shares']
            price = current_prices.get(ticker, 100.0)
            trade_value = abs(shares * price)
            self.assertGreaterEqual(trade_value, 50.0,
                                  f"Trade {trade['action']} {shares} {ticker} = ${trade_value:.2f} below $50 minimum")


class TestRiskParameters(unittest.TestCase):
    """Test tier-specific risk parameter calculation"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_large_cap_risk_params(self):
        """Test risk parameters for large cap holdings"""
        holdings_by_tier = {
            'AAPL': 'LARGE_CAP',
            'MSFT': 'LARGE_CAP'
        }

        risk_params = self.constructor.calculate_risk_parameters(holdings_by_tier)

        self.assertEqual(risk_params['AAPL'].stop_loss_pct, -15.0)
        self.assertEqual(risk_params['AAPL'].profit_target_pct, 30.0)
        self.assertEqual(risk_params['AAPL'].position_type, 'LARGE_CAP')

        self.assertEqual(risk_params['MSFT'].stop_loss_pct, -15.0)
        self.assertEqual(risk_params['MSFT'].profit_target_pct, 30.0)

    def test_mid_cap_risk_params(self):
        """Test risk parameters for mid cap holdings"""
        holdings_by_tier = {'NVDA': 'MID_CAP'}

        risk_params = self.constructor.calculate_risk_parameters(holdings_by_tier)

        self.assertEqual(risk_params['NVDA'].stop_loss_pct, -20.0)
        self.assertEqual(risk_params['NVDA'].profit_target_pct, 40.0)
        self.assertEqual(risk_params['NVDA'].position_type, 'MID_CAP')

    def test_small_cap_risk_params(self):
        """Test risk parameters for small cap holdings"""
        holdings_by_tier = {'QS': 'SMALL_CAP'}

        risk_params = self.constructor.calculate_risk_parameters(holdings_by_tier)

        self.assertEqual(risk_params['QS'].stop_loss_pct, -25.0)
        self.assertEqual(risk_params['QS'].profit_target_pct, 50.0)
        self.assertEqual(risk_params['QS'].position_type, 'SMALL_CAP')

    def test_thematic_risk_params(self):
        """Test risk parameters for thematic holdings"""
        holdings_by_tier = {'IONQ': 'THEMATIC', 'PLTR': 'THEMATIC'}

        risk_params = self.constructor.calculate_risk_parameters(holdings_by_tier)

        self.assertEqual(risk_params['IONQ'].stop_loss_pct, -30.0)
        self.assertEqual(risk_params['IONQ'].profit_target_pct, 60.0)
        self.assertEqual(risk_params['IONQ'].position_type, 'THEMATIC')

    def test_mixed_portfolio_risk_params(self):
        """Test risk parameters for portfolio with all 4 tiers"""
        holdings_by_tier = {
            'AAPL': 'LARGE_CAP',
            'NVDA': 'MID_CAP',
            'QS': 'SMALL_CAP',
            'IONQ': 'THEMATIC'
        }

        risk_params = self.constructor.calculate_risk_parameters(holdings_by_tier)

        # Verify each tier has correct risk parameters
        self.assertEqual(risk_params['AAPL'].stop_loss_pct, -15.0)
        self.assertEqual(risk_params['NVDA'].stop_loss_pct, -20.0)
        self.assertEqual(risk_params['QS'].stop_loss_pct, -25.0)
        self.assertEqual(risk_params['IONQ'].stop_loss_pct, -30.0)

        self.assertEqual(risk_params['AAPL'].profit_target_pct, 30.0)
        self.assertEqual(risk_params['NVDA'].profit_target_pct, 40.0)
        self.assertEqual(risk_params['QS'].profit_target_pct, 50.0)
        self.assertEqual(risk_params['IONQ'].profit_target_pct, 60.0)


class TestExportFunctions(unittest.TestCase):
    """Test JSON and markdown export functions"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_allocation_to_json(self):
        """Test JSON export of allocation"""
        allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 12.5, 'MSFT': 10.0},
            mid_cap_holdings={'NVDA': 8.5},
            small_cap_holdings={'QS': 3.0},
            thematic_holdings={'IONQ': 2.0},
            cash_reserve=5.0,
            total_large_cap_pct=67.5,
            total_mid_cap_pct=17.5,
            total_small_cap_pct=12.5,
            total_thematic_pct=7.5,
            violations=[]
        )

        output_file = Path(self.temp_dir) / 'allocation.json'
        self.constructor.export_allocation_to_json(allocation, str(output_file))

        self.assertTrue(output_file.exists())
        with open(output_file, 'r') as f:
            data = json.load(f)
            self.assertIn('large_cap_holdings', data)
            self.assertIn('mid_cap_holdings', data)
            self.assertIn('small_cap_holdings', data)
            self.assertIn('thematic_holdings', data)
            self.assertEqual(data['total_large_cap_pct'], 67.5)

    def test_generate_allocation_summary(self):
        """Test markdown summary generation"""
        allocation = TieredAllocation(
            large_cap_holdings={'AAPL': 12.5, 'MSFT': 10.0},
            mid_cap_holdings={'NVDA': 8.5},
            small_cap_holdings={'QS': 3.0},
            thematic_holdings={'IONQ': 2.0},
            cash_reserve=5.0,
            total_large_cap_pct=67.5,
            total_mid_cap_pct=17.5,
            total_small_cap_pct=12.5,
            total_thematic_pct=7.5,
            violations=['Test violation']
        )

        summary = self.constructor.generate_allocation_summary(allocation)

        self.assertIn('4-Tier Portfolio Allocation Summary', summary)
        self.assertIn('Large Cap (Core)', summary)
        self.assertIn('Mid Cap (Growth)', summary)
        self.assertIn('Small Cap (Opportunistic)', summary)
        self.assertIn('Thematic', summary)
        self.assertIn('AAPL', summary)
        self.assertIn('NVDA', summary)
        self.assertIn('QS', summary)
        self.assertIn('IONQ', summary)
        self.assertIn('Test violation', summary)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_roe_boundary_15_percent(self):
        """Test ROE boundary at exactly 15%"""
        # Large cap
        position_pct = self.constructor.calculate_large_cap_position_size(0.15)
        self.assertEqual(position_pct, 10.0)  # Should be included

        position_pct = self.constructor.calculate_large_cap_position_size(0.1499)
        self.assertEqual(position_pct, 0.0)  # Should be excluded

    def test_roe_boundary_20_percent(self):
        """Test ROE boundary at exactly 20%"""
        # Large cap
        position_pct = self.constructor.calculate_large_cap_position_size(0.20)
        self.assertEqual(position_pct, 12.5)  # Higher tier

        position_pct = self.constructor.calculate_large_cap_position_size(0.1999)
        self.assertEqual(position_pct, 10.0)  # Lower tier

    def test_quality_score_boundary_60(self):
        """Test small cap quality score boundary at 60"""
        position_pct = self.constructor.calculate_small_cap_position_size(True, 60.0)
        self.assertEqual(position_pct, 2.0)  # Should be included

        position_pct = self.constructor.calculate_small_cap_position_size(True, 59.9)
        self.assertEqual(position_pct, 0.0)  # Should be excluded

    def test_thematic_score_boundary_28(self):
        """Test thematic score boundary at exactly 28"""
        position_pct = self.constructor.calculate_thematic_position_size(28.0)
        self.assertEqual(position_pct, 2.0)  # Should be included

        position_pct = self.constructor.calculate_thematic_position_size(27.99)
        self.assertEqual(position_pct, 0.0)  # Should be excluded

    def test_empty_portfolio(self):
        """Test allocation with empty portfolio"""
        allocation = self.constructor.calculate_target_allocation({}, {}, 100000.0)

        self.assertEqual(allocation.total_large_cap_pct, 0.0)
        self.assertEqual(allocation.total_mid_cap_pct, 0.0)
        self.assertEqual(allocation.total_small_cap_pct, 0.0)
        self.assertEqual(allocation.total_thematic_pct, 0.0)
        self.assertAlmostEqual(allocation.cash_reserve, 100.0, places=0)
        self.assertGreater(len(allocation.violations), 0)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPositionSizing))
    suite.addTests(loader.loadTestsFromTestCase(TestSmallCapFilters))
    suite.addTests(loader.loadTestsFromTestCase(TestAllocationCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestRebalancingTrades))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestExportFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
