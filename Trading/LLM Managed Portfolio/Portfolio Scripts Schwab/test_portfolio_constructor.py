#!/usr/bin/env python3
"""
Test Suite for Portfolio Constructor Module

Tests position sizing, allocation calculation, rebalancing, and risk parameters
for the STEPS 80/20 portfolio framework.

Author: LLM Portfolio Management System
Date: November 3, 2025
"""

import unittest
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Import the module to test
from portfolio_constructor import (
    PortfolioConstructor,
    PortfolioAllocation,
    AllocationReport,
    RiskParameters
)


class TestPositionSizing(unittest.TestCase):
    """Test position sizing calculations for quality and thematic holdings"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_quality_elite_range(self):
        """Test position sizing for Elite quality (9-10)"""
        min_pct, max_pct = self.constructor.calculate_quality_position_size(9.5)
        self.assertEqual(min_pct, 10.0)
        self.assertEqual(max_pct, 20.0)

        # Edge cases
        min_pct, max_pct = self.constructor.calculate_quality_position_size(9.0)
        self.assertEqual((min_pct, max_pct), (10.0, 20.0))

        min_pct, max_pct = self.constructor.calculate_quality_position_size(10.0)
        self.assertEqual((min_pct, max_pct), (10.0, 20.0))

    def test_quality_strong_range(self):
        """Test position sizing for Strong quality (8-8.99)"""
        min_pct, max_pct = self.constructor.calculate_quality_position_size(8.5)
        self.assertEqual(min_pct, 7.0)
        self.assertEqual(max_pct, 12.0)

        # Edge case
        min_pct, max_pct = self.constructor.calculate_quality_position_size(8.0)
        self.assertEqual((min_pct, max_pct), (7.0, 12.0))

    def test_quality_moderate_range(self):
        """Test position sizing for Moderate quality (7-7.99)"""
        min_pct, max_pct = self.constructor.calculate_quality_position_size(7.5)
        self.assertEqual(min_pct, 5.0)
        self.assertEqual(max_pct, 8.0)

        # Edge case
        min_pct, max_pct = self.constructor.calculate_quality_position_size(7.0)
        self.assertEqual((min_pct, max_pct), (5.0, 8.0))

    def test_quality_weak_range(self):
        """Test position sizing for Weak quality (<7) - should be EXIT"""
        min_pct, max_pct = self.constructor.calculate_quality_position_size(6.5)
        self.assertEqual(min_pct, 0.0)
        self.assertEqual(max_pct, 0.0)

        min_pct, max_pct = self.constructor.calculate_quality_position_size(5.0)
        self.assertEqual((min_pct, max_pct), (0.0, 0.0))

    def test_thematic_leader_range(self):
        """Test position sizing for Thematic Leader (35-40)"""
        min_pct, max_pct = self.constructor.calculate_thematic_position_size(37.5)
        self.assertEqual(min_pct, 5.0)
        self.assertEqual(max_pct, 7.0)

        # Edge cases
        min_pct, max_pct = self.constructor.calculate_thematic_position_size(35.0)
        self.assertEqual((min_pct, max_pct), (5.0, 7.0))

        min_pct, max_pct = self.constructor.calculate_thematic_position_size(40.0)
        self.assertEqual((min_pct, max_pct), (5.0, 7.0))

    def test_thematic_strong_contender_range(self):
        """Test position sizing for Strong Contender (30-34.9)"""
        min_pct, max_pct = self.constructor.calculate_thematic_position_size(32.0)
        self.assertEqual(min_pct, 3.0)
        self.assertEqual(max_pct, 5.0)

        # Edge case
        min_pct, max_pct = self.constructor.calculate_thematic_position_size(30.0)
        self.assertEqual((min_pct, max_pct), (3.0, 5.0))

    def test_thematic_contender_range(self):
        """Test position sizing for Contender (28-29.9)"""
        min_pct, max_pct = self.constructor.calculate_thematic_position_size(28.5)
        self.assertEqual(min_pct, 2.0)
        self.assertEqual(max_pct, 3.0)

        # Edge case
        min_pct, max_pct = self.constructor.calculate_thematic_position_size(28.0)
        self.assertEqual((min_pct, max_pct), (2.0, 3.0))

    def test_thematic_laggard_range(self):
        """Test position sizing for Laggard (<28) - should be EXIT"""
        min_pct, max_pct = self.constructor.calculate_thematic_position_size(27.5)
        self.assertEqual(min_pct, 0.0)
        self.assertEqual(max_pct, 0.0)

        min_pct, max_pct = self.constructor.calculate_thematic_position_size(20.0)
        self.assertEqual((min_pct, max_pct), (0.0, 0.0))


class TestAllocationCalculation(unittest.TestCase):
    """Test target allocation calculation with mock holdings"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_balanced_portfolio(self):
        """Test allocation with balanced quality and thematic holdings"""
        quality_holdings = {
            'NVDA': 9.0,   # Elite
            'MSFT': 8.5,   # Strong
            'GOOGL': 7.5   # Moderate
        }
        thematic_holdings = {
            'PLTR': 36.0,  # Leader
            'ARM': 31.0    # Strong Contender
        }
        total_value = 10000.0

        allocation = self.constructor.calculate_target_allocation(
            quality_holdings, thematic_holdings, total_value
        )

        # Check quality allocation is ~80%
        self.assertGreaterEqual(allocation.total_quality_pct, 75.0)
        self.assertLessEqual(allocation.total_quality_pct, 85.0)

        # Check thematic allocation is ~20%
        self.assertGreaterEqual(allocation.total_thematic_pct, 15.0)
        self.assertLessEqual(allocation.total_thematic_pct, 25.0)

        # Check cash reserve
        self.assertAlmostEqual(allocation.cash_reserve, 5.0, places=1)

        # Check individual positions don't exceed 20%
        for ticker, pct in allocation.quality_holdings.items():
            self.assertLessEqual(pct, 20.0, f"{ticker} exceeds 20% limit")

        # Check thematic positions don't exceed 7%
        for ticker, pct in allocation.thematic_holdings.items():
            self.assertLessEqual(pct, 7.0, f"{ticker} exceeds 7% thematic limit")

    def test_quality_only_portfolio(self):
        """Test allocation with only quality holdings"""
        quality_holdings = {
            'NVDA': 9.0,
            'MSFT': 8.0,
            'GOOGL': 7.5
        }
        thematic_holdings = {}
        total_value = 10000.0

        allocation = self.constructor.calculate_target_allocation(
            quality_holdings, thematic_holdings, total_value
        )

        # Quality should be normalized to 80% (not 95%)
        self.assertAlmostEqual(allocation.total_quality_pct, 80.0, places=0)
        self.assertEqual(allocation.total_thematic_pct, 0.0)
        self.assertGreater(allocation.cash_reserve, 5.0)  # More cash when no thematic

        # Should have violations for missing thematic allocation
        self.assertGreater(len(allocation.violations), 0)
        self.assertTrue(any('Thematic' in v for v in allocation.violations))

    def test_thematic_only_portfolio(self):
        """Test allocation with only thematic holdings"""
        quality_holdings = {}
        thematic_holdings = {
            'PLTR': 36.0,
            'ARM': 31.0,
            'IONQ': 28.5
        }
        total_value = 10000.0

        allocation = self.constructor.calculate_target_allocation(
            quality_holdings, thematic_holdings, total_value
        )

        # Thematic should be capped at 20% even if they're the only holdings
        self.assertEqual(allocation.total_quality_pct, 0.0)
        self.assertLessEqual(allocation.total_thematic_pct, 20.0)

        # Should have violations for missing quality allocation
        self.assertGreater(len(allocation.violations), 0)
        self.assertTrue(any('Quality' in v for v in allocation.violations))

    def test_empty_portfolio(self):
        """Test allocation with empty portfolio"""
        quality_holdings = {}
        thematic_holdings = {}
        total_value = 10000.0

        allocation = self.constructor.calculate_target_allocation(
            quality_holdings, thematic_holdings, total_value
        )

        self.assertEqual(allocation.total_quality_pct, 0.0)
        self.assertEqual(allocation.total_thematic_pct, 0.0)
        self.assertAlmostEqual(allocation.cash_reserve, 100.0, places=0)
        self.assertGreater(len(allocation.violations), 0)

    def test_weak_holdings_excluded(self):
        """Test that weak quality (<7) and laggard thematic (<28) are excluded"""
        quality_holdings = {
            'NVDA': 9.0,   # Include
            'WEAK1': 6.5,  # Exclude - weak quality
            'GOOGL': 7.5   # Include
        }
        thematic_holdings = {
            'PLTR': 36.0,   # Include
            'WEAK2': 25.0   # Exclude - laggard thematic
        }
        total_value = 10000.0

        allocation = self.constructor.calculate_target_allocation(
            quality_holdings, thematic_holdings, total_value
        )

        # Weak holdings should not appear in allocation
        self.assertNotIn('WEAK1', allocation.quality_holdings)
        self.assertNotIn('WEAK2', allocation.thematic_holdings)

        # Only strong holdings should be present
        self.assertIn('NVDA', allocation.quality_holdings)
        self.assertIn('GOOGL', allocation.quality_holdings)
        self.assertIn('PLTR', allocation.thematic_holdings)


class TestCurrentAnalysis(unittest.TestCase):
    """Test current allocation analysis with mock portfolio"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_analyze_balanced_portfolio(self):
        """Test analysis of balanced portfolio"""
        portfolio_state = {
            'cash': 500.0,
            'holdings': {
                'NVDA': {'shares': 10, 'entry_price': 450.0},
                'MSFT': {'shares': 10, 'entry_price': 420.0},
                'PLTR': {'shares': 30, 'entry_price': 30.0}
            }
        }
        quality_scores = {'NVDA': 9.0, 'MSFT': 8.5}
        thematic_scores = {'PLTR': 36.0}

        # Mock current prices
        current_prices = {'NVDA': 500.0, 'MSFT': 450.0, 'PLTR': 35.0}

        report = self.constructor.analyze_current_allocation(
            portfolio_state, quality_scores, thematic_scores, current_prices
        )

        # Portfolio value = 500 + (10*500) + (10*450) + (30*35) = 500 + 5000 + 4500 + 1050 = 11050
        # Quality = 9500 / 11050 = 85.97%
        # Thematic = 1050 / 11050 = 9.50%
        # Cash = 500 / 11050 = 4.52%

        self.assertGreater(report.current_quality_pct, 75.0)
        self.assertLess(report.current_quality_pct, 90.0)
        self.assertGreater(report.current_thematic_pct, 5.0)
        self.assertLess(report.current_thematic_pct, 15.0)

        # Should detect thematic underweight
        self.assertTrue(report.rebalancing_needed)
        self.assertTrue(any('Thematic' in v and 'below' in v for v in report.violations))

    def test_analyze_overweight_quality(self):
        """Test detection of overweight quality allocation"""
        portfolio_state = {
            'cash': 100.0,
            'holdings': {
                'NVDA': {'shares': 20, 'entry_price': 450.0},
                'MSFT': {'shares': 20, 'entry_price': 420.0}
            }
        }
        quality_scores = {'NVDA': 9.0, 'MSFT': 8.5}
        thematic_scores = {}
        current_prices = {'NVDA': 500.0, 'MSFT': 450.0}

        report = self.constructor.analyze_current_allocation(
            portfolio_state, quality_scores, thematic_scores, current_prices
        )

        # Quality = (20*500 + 20*450) / total = very high
        self.assertGreater(report.current_quality_pct, 85.0)
        self.assertTrue(report.rebalancing_needed)
        self.assertTrue(any('Quality' in v and 'above' in v for v in report.violations))

    def test_analyze_position_too_large(self):
        """Test detection of single position exceeding 20% limit"""
        portfolio_state = {
            'cash': 100.0,
            'holdings': {
                'NVDA': {'shares': 30, 'entry_price': 450.0}
            }
        }
        quality_scores = {'NVDA': 9.0}
        thematic_scores = {}
        current_prices = {'NVDA': 500.0}

        report = self.constructor.analyze_current_allocation(
            portfolio_state, quality_scores, thematic_scores, current_prices
        )

        # NVDA = 30*500 = 15000, total = 15100, NVDA = 99.3% (way over 20%)
        violations = [v for v in report.violations if 'exceeds 20%' in v]
        self.assertGreater(len(violations), 0)


class TestRebalancingTrades(unittest.TestCase):
    """Test rebalancing trade generation"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_generate_rebalancing_sells(self):
        """Test generation of sell orders for overweight positions"""
        current_allocation = AllocationReport(
            current_quality_pct=90.0,
            current_thematic_pct=5.0,
            current_cash_pct=5.0,
            violations=['Quality allocation above 85%'],
            rebalancing_needed=True,
            quality_holdings={'NVDA': 45.0, 'MSFT': 45.0},  # Both overweight
            thematic_holdings={'PLTR': 5.0}
        )

        target_allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 15.0, 'MSFT': 15.0},
            thematic_holdings={'PLTR': 5.0},
            cash_reserve=10.0,
            total_quality_pct=30.0,
            total_thematic_pct=5.0,
            violations=[]
        )

        portfolio_state = {
            'cash': 500.0,
            'holdings': {
                'NVDA': {'shares': 20, 'entry_price': 450.0},
                'MSFT': {'shares': 15, 'entry_price': 420.0},
                'PLTR': {'shares': 10, 'entry_price': 30.0}
            }
        }

        current_prices = {'NVDA': 500.0, 'MSFT': 450.0, 'PLTR': 35.0}

        trades = self.constructor.generate_rebalancing_trades(
            current_allocation, target_allocation, portfolio_state, current_prices
        )

        # Should generate sell orders for overweight positions
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        self.assertGreater(len(sell_trades), 0)

        # Verify trades have required fields
        for trade in trades:
            self.assertIn('action', trade)
            self.assertIn('ticker', trade)
            self.assertIn('shares', trade)
            self.assertIn('reasoning', trade)
            self.assertIn('priority', trade)

    def test_no_trades_when_balanced(self):
        """Test that no trades are generated when portfolio is balanced"""
        current_allocation = AllocationReport(
            current_quality_pct=80.0,
            current_thematic_pct=20.0,
            current_cash_pct=5.0,
            violations=[],
            rebalancing_needed=False,
            quality_holdings={'NVDA': 15.0, 'MSFT': 15.0},
            thematic_holdings={'PLTR': 5.0}
        )

        target_allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 15.0, 'MSFT': 15.0},
            thematic_holdings={'PLTR': 5.0},
            cash_reserve=5.0,
            total_quality_pct=80.0,
            total_thematic_pct=20.0,
            violations=[]
        )

        portfolio_state = {
            'cash': 500.0,
            'holdings': {
                'NVDA': {'shares': 10, 'entry_price': 450.0},
                'MSFT': {'shares': 10, 'entry_price': 420.0},
                'PLTR': {'shares': 10, 'entry_price': 30.0}
            }
        }

        current_prices = {'NVDA': 500.0, 'MSFT': 450.0, 'PLTR': 35.0}

        trades = self.constructor.generate_rebalancing_trades(
            current_allocation, target_allocation, portfolio_state, current_prices
        )

        # Should generate minimal or no trades
        self.assertLessEqual(len(trades), 2)  # Allow for minor adjustments

    def test_minimum_trade_size_respected(self):
        """Test that trades below $50 are not generated"""
        # Create scenario where only tiny adjustment is needed
        current_allocation = AllocationReport(
            current_quality_pct=80.1,
            current_thematic_pct=19.9,
            current_cash_pct=5.0,
            violations=[],
            rebalancing_needed=True,
            quality_holdings={'NVDA': 80.1},
            thematic_holdings={'PLTR': 19.9}
        )

        target_allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 80.0},
            thematic_holdings={'PLTR': 20.0},
            cash_reserve=5.0,
            total_quality_pct=80.0,
            total_thematic_pct=20.0,
            violations=[]
        )

        portfolio_state = {
            'cash': 100.0,
            'holdings': {
                'NVDA': {'shares': 16, 'entry_price': 450.0},
                'PLTR': {'shares': 130, 'entry_price': 30.0}
            }
        }

        current_prices = {'NVDA': 500.0, 'PLTR': 35.0}

        trades = self.constructor.generate_rebalancing_trades(
            current_allocation, target_allocation, portfolio_state, current_prices
        )

        # Verify all trades meet minimum size
        for trade in trades:
            ticker = trade['ticker']
            shares = trade['shares']
            price = current_prices[ticker]
            trade_value = shares * price
            self.assertGreaterEqual(trade_value, 50.0,
                                  f"Trade {trade['action']} {shares} {ticker} = ${trade_value} below $50 minimum")


class TestRiskParameters(unittest.TestCase):
    """Test risk parameter calculation"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_quality_elite_risk_params(self):
        """Test risk parameters for elite quality holdings (>8)"""
        holdings = {'NVDA': 'QUALITY', 'MSFT': 'QUALITY'}
        quality_scores = {'NVDA': 9.0, 'MSFT': 8.5}

        risk_params = self.constructor.calculate_risk_parameters(holdings, quality_scores)

        self.assertEqual(risk_params['NVDA'].stop_loss_pct, -15.0)
        self.assertEqual(risk_params['NVDA'].profit_target_pct, 40.0)
        self.assertEqual(risk_params['MSFT'].stop_loss_pct, -15.0)
        self.assertEqual(risk_params['MSFT'].profit_target_pct, 40.0)

    def test_quality_moderate_risk_params(self):
        """Test risk parameters for moderate quality holdings (7-8)"""
        holdings = {'GOOGL': 'QUALITY'}
        quality_scores = {'GOOGL': 7.5}

        risk_params = self.constructor.calculate_risk_parameters(holdings, quality_scores)

        self.assertEqual(risk_params['GOOGL'].stop_loss_pct, -20.0)
        self.assertEqual(risk_params['GOOGL'].profit_target_pct, 40.0)

    def test_thematic_risk_params(self):
        """Test risk parameters for thematic holdings"""
        holdings = {'PLTR': 'THEMATIC', 'ARM': 'THEMATIC'}
        quality_scores = {}

        risk_params = self.constructor.calculate_risk_parameters(holdings, quality_scores)

        self.assertEqual(risk_params['PLTR'].stop_loss_pct, -27.5)
        self.assertEqual(risk_params['PLTR'].profit_target_pct, 50.0)
        self.assertEqual(risk_params['ARM'].stop_loss_pct, -27.5)
        self.assertEqual(risk_params['ARM'].profit_target_pct, 50.0)

    def test_mixed_portfolio_risk_params(self):
        """Test risk parameters for mixed portfolio"""
        holdings = {
            'NVDA': 'QUALITY',
            'GOOGL': 'QUALITY',
            'PLTR': 'THEMATIC'
        }
        quality_scores = {'NVDA': 9.0, 'GOOGL': 7.5}

        risk_params = self.constructor.calculate_risk_parameters(holdings, quality_scores)

        # Elite quality: -15%
        self.assertEqual(risk_params['NVDA'].stop_loss_pct, -15.0)
        # Moderate quality: -20%
        self.assertEqual(risk_params['GOOGL'].stop_loss_pct, -20.0)
        # Thematic: -27.5%
        self.assertEqual(risk_params['PLTR'].stop_loss_pct, -27.5)


class TestValidation(unittest.TestCase):
    """Test violation detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_quality_below_minimum(self):
        """Test detection of quality allocation below 75%"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 10.0},
            thematic_holdings={'PLTR': 20.0},
            cash_reserve=70.0,
            total_quality_pct=70.0,  # Below 75%
            total_thematic_pct=20.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('Quality' in v and 'below 75%' in v for v in violations))

    def test_quality_above_maximum(self):
        """Test detection of quality allocation above 85%"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 50.0, 'MSFT': 40.0},
            thematic_holdings={'PLTR': 5.0},
            cash_reserve=5.0,
            total_quality_pct=90.0,  # Above 85%
            total_thematic_pct=5.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('Quality' in v and 'above 85%' in v for v in violations))

    def test_thematic_below_minimum(self):
        """Test detection of thematic allocation below 15%"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 80.0},
            thematic_holdings={'PLTR': 10.0},
            cash_reserve=10.0,
            total_quality_pct=80.0,
            total_thematic_pct=10.0,  # Below 15%
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('Thematic' in v and 'below 15%' in v for v in violations))

    def test_thematic_above_maximum(self):
        """Test detection of thematic allocation above 25%"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 60.0},
            thematic_holdings={'PLTR': 15.0, 'ARM': 15.0},
            cash_reserve=10.0,
            total_quality_pct=60.0,
            total_thematic_pct=30.0,  # Above 25%
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('Thematic' in v and 'above 25%' in v for v in violations))

    def test_position_exceeds_20_percent(self):
        """Test detection of single position exceeding 20%"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 25.0},  # Exceeds 20%
            thematic_holdings={'PLTR': 20.0},
            cash_reserve=55.0,
            total_quality_pct=25.0,
            total_thematic_pct=20.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('NVDA' in v and 'exceeds 20%' in v for v in violations))

    def test_thematic_position_exceeds_7_percent(self):
        """Test detection of thematic position exceeding 7%"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 80.0},
            thematic_holdings={'PLTR': 10.0},  # Exceeds 7%
            cash_reserve=10.0,
            total_quality_pct=80.0,
            total_thematic_pct=10.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('PLTR' in v and 'exceeds 7%' in v for v in violations))

    def test_insufficient_cash_reserve(self):
        """Test detection of cash reserve below 3%"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 80.0},
            thematic_holdings={'PLTR': 18.0},
            cash_reserve=2.0,  # Below 3%
            total_quality_pct=80.0,
            total_thematic_pct=18.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertTrue(any('Cash reserve' in v and 'below 3%' in v for v in violations))

    def test_valid_allocation_no_violations(self):
        """Test that valid allocation has no violations"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 15.0, 'MSFT': 15.0, 'GOOGL': 10.0},
            thematic_holdings={'PLTR': 5.0, 'ARM': 5.0},
            cash_reserve=5.0,
            total_quality_pct=80.0,
            total_thematic_pct=20.0,
            violations=[]
        )

        violations = self.constructor.validate_allocation(allocation)
        self.assertEqual(len(violations), 0, f"Expected no violations but got: {violations}")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()

    def test_zero_portfolio_value(self):
        """Test handling of zero portfolio value"""
        portfolio_state = {'cash': 0.0, 'holdings': {}}
        quality_scores = {}
        thematic_scores = {}
        current_prices = {}

        report = self.constructor.analyze_current_allocation(
            portfolio_state, quality_scores, thematic_scores, current_prices
        )

        self.assertEqual(report.current_quality_pct, 0.0)
        self.assertEqual(report.current_thematic_pct, 0.0)
        self.assertEqual(report.current_cash_pct, 0.0)

    def test_single_holding_portfolio(self):
        """Test portfolio with single holding"""
        quality_holdings = {'NVDA': 9.0}
        thematic_holdings = {}
        total_value = 10000.0

        allocation = self.constructor.calculate_target_allocation(
            quality_holdings, thematic_holdings, total_value
        )

        # Should still try to maintain 80/20 framework
        self.assertGreater(allocation.total_quality_pct, 0.0)
        self.assertGreater(len(allocation.violations), 0)

    def test_all_weak_holdings(self):
        """Test portfolio where all holdings are weak"""
        quality_holdings = {'WEAK1': 5.0, 'WEAK2': 4.0}
        thematic_holdings = {'WEAK3': 20.0, 'WEAK4': 15.0}
        total_value = 10000.0

        allocation = self.constructor.calculate_target_allocation(
            quality_holdings, thematic_holdings, total_value
        )

        # All holdings should be excluded
        self.assertEqual(len(allocation.quality_holdings), 0)
        self.assertEqual(len(allocation.thematic_holdings), 0)
        self.assertAlmostEqual(allocation.cash_reserve, 100.0, places=0)

    def test_boundary_quality_score_7(self):
        """Test exact boundary at quality score 7.0"""
        min_pct, max_pct = self.constructor.calculate_quality_position_size(7.0)
        self.assertEqual((min_pct, max_pct), (5.0, 8.0))

        # Just below should be EXIT
        min_pct, max_pct = self.constructor.calculate_quality_position_size(6.99)
        self.assertEqual((min_pct, max_pct), (0.0, 0.0))

    def test_boundary_thematic_score_28(self):
        """Test exact boundary at thematic score 28.0"""
        min_pct, max_pct = self.constructor.calculate_thematic_position_size(28.0)
        self.assertEqual((min_pct, max_pct), (2.0, 3.0))

        # Just below should be EXIT
        min_pct, max_pct = self.constructor.calculate_thematic_position_size(27.99)
        self.assertEqual((min_pct, max_pct), (0.0, 0.0))

    def test_very_large_portfolio_value(self):
        """Test handling of large portfolio value"""
        quality_holdings = {'NVDA': 9.0, 'MSFT': 8.5}
        thematic_holdings = {'PLTR': 36.0}
        total_value = 10_000_000.0  # $10M portfolio

        allocation = self.constructor.calculate_target_allocation(
            quality_holdings, thematic_holdings, total_value
        )

        # Should still maintain proportions
        self.assertGreater(allocation.total_quality_pct, 75.0)
        self.assertLess(allocation.total_quality_pct, 85.0)

    def test_fractional_shares_rounding(self):
        """Test that fractional shares are handled correctly"""
        current_allocation = AllocationReport(
            current_quality_pct=75.0,
            current_thematic_pct=20.0,
            current_cash_pct=5.0,
            violations=[],
            rebalancing_needed=True,
            quality_holdings={'NVDA': 40.0},
            thematic_holdings={'PLTR': 20.0}
        )

        target_allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 15.0},
            thematic_holdings={'PLTR': 20.0},
            cash_reserve=10.0,
            total_quality_pct=75.0,
            total_thematic_pct=20.0,
            violations=[]
        )

        portfolio_state = {
            'cash': 100.0,
            'holdings': {
                'NVDA': {'shares': 7, 'entry_price': 450.0},
                'PLTR': {'shares': 50, 'entry_price': 30.0}
            }
        }

        current_prices = {'NVDA': 501.23, 'PLTR': 35.67}  # Odd prices

        trades = self.constructor.generate_rebalancing_trades(
            current_allocation, target_allocation, portfolio_state, current_prices
        )

        # All share counts should be integers
        for trade in trades:
            self.assertIsInstance(trade['shares'], int)


class TestExportFunctions(unittest.TestCase):
    """Test JSON and markdown export functions"""

    def setUp(self):
        """Set up test fixtures"""
        self.constructor = PortfolioConstructor()
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_allocation_report(self):
        """Test JSON export of allocation report"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 15.0, 'MSFT': 10.0},
            thematic_holdings={'PLTR': 5.0},
            cash_reserve=5.0,
            total_quality_pct=80.0,
            total_thematic_pct=20.0,
            violations=[]
        )

        output_file = self.constructor.export_allocation_report(allocation)

        self.assertTrue(Path(output_file).exists())
        with open(output_file, 'r') as f:
            data = json.load(f)
            self.assertIn('quality_holdings', data)
            self.assertIn('thematic_holdings', data)
            self.assertEqual(data['total_quality_pct'], 80.0)

    def test_export_rebalancing_trades(self):
        """Test JSON export of rebalancing trades"""
        trades = [
            {'action': 'SELL', 'ticker': 'AMD', 'shares': 10, 'reasoning': 'Test', 'priority': 'HIGH'},
            {'action': 'BUY', 'ticker': 'NVDA', 'shares': 5, 'reasoning': 'Test', 'priority': 'HIGH'}
        ]

        output_file = self.constructor.export_rebalancing_trades(trades)

        self.assertTrue(Path(output_file).exists())
        with open(output_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(len(data['trades']), 2)
            self.assertEqual(data['trades'][0]['action'], 'SELL')

    def test_generate_allocation_summary(self):
        """Test markdown summary generation"""
        allocation = PortfolioAllocation(
            quality_holdings={'NVDA': 15.0, 'MSFT': 10.0},
            thematic_holdings={'PLTR': 5.0},
            cash_reserve=5.0,
            total_quality_pct=80.0,
            total_thematic_pct=20.0,
            violations=['Test violation']
        )

        summary = self.constructor.generate_allocation_summary(allocation, 10000.0)

        self.assertIn('Portfolio Allocation Summary', summary)
        self.assertIn('NVDA', summary)
        self.assertIn('Quality Holdings', summary)
        self.assertIn('Thematic Holdings', summary)
        self.assertIn('Test violation', summary)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPositionSizing))
    suite.addTests(loader.loadTestsFromTestCase(TestAllocationCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestCurrentAnalysis))
    suite.addTests(loader.loadTestsFromTestCase(TestRebalancingTrades))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestExportFunctions))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
