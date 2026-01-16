"""
Tests for Quality Analysis Framework

This module contains comprehensive tests for all quality analysis modules:
- Earnings Quality Analyzer
- Growth Quality Analyzer
- Safety Analyzer
- Lookback Calculator
- Multiplier Calculator
- Quality Metrics Calculator

Author: Quality Analysis System
Date: January 2026
"""

import unittest
from typing import Dict, List
import logging

logging.basicConfig(level=logging.WARNING)

from schwab_portfolio.quality import (
    QualityMetricsCalculator,
    EarningsQualityAnalyzer,
    GrowthQualityAnalyzer,
    SafetyAnalyzer,
    LookbackCalculator,
    MultiplierCalculator,
    QualityTier
)


class TestEarningsQualityAnalyzer(unittest.TestCase):
    """Tests for Earnings Quality Analyzer."""

    def setUp(self):
        self.analyzer = EarningsQualityAnalyzer()

    def test_accrual_ratio_calculation(self):
        """Test accrual ratio calculation."""
        accrual_ratio = self.analyzer.calculate_accrual_ratio(
            net_income=100,
            operating_cash_flow=120,
            total_assets=1000,
            prior_total_assets=900
        )
        self.assertIsNotNone(accrual_ratio)
        self.assertAlmostEqual(accrual_ratio, -0.02, places=2)

    def test_accrual_ratio_high_accruals(self):
        """Test high accruals detection."""
        accrual_ratio = self.analyzer.calculate_accrual_ratio(
            net_income=150,
            operating_cash_flow=100,
            total_assets=1000,
            prior_total_assets=900
        )
        self.assertGreater(accrual_ratio, 0.05)

    def test_cash_conversion_calculation(self):
        """Test cash conversion calculation."""
        cash_conversion = self.analyzer.calculate_cash_conversion(
            operating_cash_flow=120,
            net_income=100
        )
        self.assertAlmostEqual(cash_conversion, 1.20, places=2)

    def test_cash_conversion_low(self):
        """Test low cash conversion detection."""
        cash_conversion = self.analyzer.calculate_cash_conversion(
            operating_cash_flow=60,
            net_income=100
        )
        self.assertLess(cash_conversion, 0.80)

    def test_piotroski_f_score(self):
        """Test Piotroski F-Score calculation."""
        financial_data = {
            'net_income': 100,
            'prior_net_income': 80,
            'operating_cash_flow': 120,
            'prior_operating_cash_flow': 100,
            'total_assets': 1000,
            'prior_total_assets': 900,
            'shareholder_equity': 500,
            'prior_shareholder_equity': 450,
            'current_assets': 300,
            'prior_current_assets': 250,
            'current_liabilities': 200,
            'prior_current_liabilities': 180,
            'total_debt': 100,
            'prior_total_debt': 120,
            'shares_outstanding': 50,
            'prior_shares_outstanding': 50,
            'revenue': 1000,
            'prior_revenue': 900,
            'cogs': 600,
            'prior_cogs': 550
        }

        f_score, breakdown = self.analyzer.calculate_piotroski_f_score(financial_data)

        self.assertIsInstance(f_score, int)
        self.assertGreaterEqual(f_score, 0)
        self.assertLessEqual(f_score, 9)
        self.assertEqual(breakdown.total_score, f_score)

    def test_full_analysis(self):
        """Test complete earnings quality analysis."""
        financial_data = {
            'net_income': 100,
            'operating_cash_flow': 120,
            'total_assets': 1000,
            'prior_total_assets': 900,
            'shareholder_equity': 500,
            'prior_shareholder_equity': 450,
            'current_assets': 300,
            'prior_current_assets': 250,
            'current_liabilities': 200,
            'prior_current_liabilities': 180,
            'total_debt': 100,
            'prior_total_debt': 120,
            'shares_outstanding': 50,
            'prior_shares_outstanding': 50,
            'revenue': 1000,
            'prior_revenue': 900,
            'cogs': 600,
            'prior_cogs': 550
        }

        result = self.analyzer.analyze(financial_data)

        self.assertIsNotNone(result.earnings_quality_score)
        self.assertGreaterEqual(result.earnings_quality_score, 0)
        self.assertLessEqual(result.earnings_quality_score, 10)


class TestGrowthQualityAnalyzer(unittest.TestCase):
    """Tests for Growth Quality Analyzer."""

    def setUp(self):
        self.analyzer = GrowthQualityAnalyzer()

    def test_asset_growth_calculation(self):
        """Test asset growth rate calculation."""
        asset_growth = self.analyzer.calculate_asset_growth_rate(
            total_assets=1100,
            prior_total_assets=1000
        )
        self.assertAlmostEqual(asset_growth, 0.10, places=2)

    def test_asset_growth_score_low_growth(self):
        """Test high score for low asset growth."""
        asset_growth = self.analyzer.calculate_asset_growth_rate(
            total_assets=1050,
            prior_total_assets=1000
        )
        score = self.analyzer.calculate_asset_growth_score(asset_growth)
        self.assertGreater(score, 8)

    def test_revenue_cagr_calculation(self):
        """Test revenue CAGR calculation."""
        revenues = [1200, 1100, 1000, 900, 800]
        cagr = self.analyzer.calculate_revenue_cagr(revenues)
        self.assertIsNotNone(cagr)
        self.assertGreater(cagr, 0)

    def test_margin_trend_calculation(self):
        """Test margin trend calculation."""
        margins = [0.25, 0.24, 0.23, 0.22, 0.21]
        trend = self.analyzer.calculate_margin_trend(margins, lookback_periods=3)
        self.assertIsNotNone(trend)

    def test_full_analysis(self):
        """Test complete growth quality analysis."""
        financial_data = {
            'total_assets': 1100,
            'prior_total_assets': 1000,
            'revenues': [1200, 1100, 1000, 900, 800],
            'margins': [0.25, 0.24, 0.23, 0.22, 0.21]
        }

        result = self.analyzer.analyze(financial_data)

        self.assertIsNotNone(result.growth_quality_score)
        self.assertGreaterEqual(result.growth_quality_score, 0)
        self.assertLessEqual(result.growth_quality_score, 10)


class TestSafetyAnalyzer(unittest.TestCase):
    """Tests for Safety Analyzer."""

    def setUp(self):
        self.analyzer = SafetyAnalyzer()

    def test_z_score_calculation(self):
        """Test Altman Z-Score calculation."""
        z_score = self.analyzer.calculate_altman_z_score(
            total_assets=10000,
            total_equity=6000,
            retained_earnings=2000,
            ebit=1500,
            sales=8000,
            working_capital=1500
        )
        self.assertIsNotNone(z_score)
        self.assertGreater(z_score, 2.0)  # Should be in safe zone (>2.0)

    def test_z_score_distress(self):
        """Test Z-Score in distress zone."""
        z_score = self.analyzer.calculate_altman_z_score(
            total_assets=5000,
            total_equity=500,
            retained_earnings=-200,
            ebit=100,
            sales=3000,
            working_capital=-500
        )
        self.assertLess(z_score, 2.0)  # Should be in distress

    def test_debt_to_ebitda_calculation(self):
        """Test Debt/EBITDA calculation."""
        ratio = self.analyzer.calculate_debt_to_ebitda(
            total_debt=2000,
            ebitda=2000
        )
        self.assertAlmostEqual(ratio, 1.0, places=2)

    def test_interest_coverage_calculation(self):
        """Test interest coverage calculation."""
        coverage = self.analyzer.calculate_interest_coverage(
            ebit=1500,
            interest_expense=100
        )
        self.assertAlmostEqual(coverage, 15.0, places=1)

    def test_interest_coverage_weak(self):
        """Test weak interest coverage."""
        coverage = self.analyzer.calculate_interest_coverage(
            ebit=150,
            interest_expense=100
        )
        self.assertAlmostEqual(coverage, 1.5, places=1)

    def test_full_analysis(self):
        """Test complete safety analysis."""
        financial_data = {
            'total_assets': 10000,
            'total_equity': 6000,
            'retained_earnings': 2000,
            'ebit': 1500,
            'sales': 8000,
            'total_debt': 2000,
            'ebitda': 2500,
            'interest_expense': 100,
            'working_capital': 1500
        }

        result = self.analyzer.analyze(financial_data)

        self.assertIsNotNone(result.safety_score)
        self.assertGreaterEqual(result.safety_score, 0)
        self.assertLessEqual(result.safety_score, 10)


class TestLookbackCalculator(unittest.TestCase):
    """Tests for Lookback Calculator."""

    def setUp(self):
        self.calculator = LookbackCalculator()

    def test_market_cap_classification(self):
        """Test market cap tier classification."""
        tier = self.calculator.classify_market_cap(50_000_000_000)
        self.assertEqual(tier.value, 'Large Cap')

        tier = self.calculator.classify_market_cap(500_000_000)
        self.assertEqual(tier.value, 'Small Cap')

        tier = self.calculator.classify_market_cap(5_000_000_000)
        self.assertEqual(tier.value, 'Mid Cap')

        tier = self.calculator.classify_market_cap(300_000_000_000)
        self.assertEqual(tier.value, 'Mega Cap')

    def test_multiplier_retrieval(self):
        """Test market cap multiplier retrieval."""
        self.assertEqual(self.calculator.get_multiplier(
            self.calculator.classify_market_cap(50_000_000_000)
        ), 1.0)

        self.assertEqual(self.calculator.get_multiplier(
            self.calculator.classify_market_cap(500_000_000)
        ), 0.5)

    def test_sector_adjustment(self):
        """Test sector adjustment retrieval."""
        self.assertEqual(self.calculator.get_sector_adjustment('Technology'), 0.8)
        self.assertEqual(self.calculator.get_sector_adjustment('Healthcare'), 1.1)
        self.assertEqual(self.calculator.get_sector_adjustment('Financials'), 1.0)

    def test_lookback_calculation(self):
        """Test adjusted lookback calculation."""
        result = self.calculator.calculate_lookback(
            base_lookback=5,
            market_cap=50_000_000_000,  # Large Cap
            sector='Technology',
            data_years=5
        )

        self.assertIsNotNone(result)
        self.assertLess(result.adjusted_lookback, 5)  # Reduced by sector adjustment


class TestMultiplierCalculator(unittest.TestCase):
    """Tests for Multiplier Calculator."""

    def setUp(self):
        self.calculator = MultiplierCalculator()

    def test_safety_multiplier_excellent(self):
        """Test safety multiplier for excellent safety metrics."""
        multiplier = self.calculator.calculate_safety_multiplier(
            z_score=4.5,
            debt_to_ebitda=1.2,
            interest_coverage=12.0,
            beta=0.9
        )
        self.assertGreater(multiplier, 0.95)

    def test_safety_multiplier_poor(self):
        """Test safety multiplier for poor safety metrics."""
        multiplier = self.calculator.calculate_safety_multiplier(
            z_score=1.2,
            debt_to_ebitda=4.5,
            interest_coverage=1.5,
            beta=1.6
        )
        self.assertLess(multiplier, 0.90)

    def test_data_quality_multiplier(self):
        """Test data quality multiplier."""
        multiplier = self.calculator.calculate_data_quality_multiplier(
            available_years=5,
            required_years=5,
            data_completeness=1.0,
            has_audited_statements=True
        )
        self.assertGreater(multiplier, 0.95)

    def test_data_quality_multiplier_poor(self):
        """Test data quality multiplier with limited data."""
        multiplier = self.calculator.calculate_data_quality_multiplier(
            available_years=2,
            required_years=5,
            data_completeness=0.7,
            has_audited_statements=False
        )
        self.assertLess(multiplier, 0.90)

    def test_market_cap_multiplier(self):
        """Test market cap multiplier retrieval."""
        self.assertEqual(
            self.calculator.get_market_cap_multiplier(50_000_000_000),
            1.0
        )
        self.assertEqual(
            self.calculator.get_market_cap_multiplier(500_000_000),
            0.5
        )

    def test_full_multiplier_calculation(self):
        """Test complete multiplier calculation."""
        result = self.calculator.calculate_multipliers(
            safety_metrics={
                'z_score': 4.0,
                'debt_to_ebitda': 1.5,
                'interest_coverage': 10.0,
                'beta': 1.0
            },
            data_years=5,
            required_years=5,
            data_completeness=1.0,
            has_audited_statements=True,
            market_cap=50_000_000_000
        )

        self.assertIsNotNone(result.safety_multiplier)
        self.assertIsNotNone(result.data_quality_multiplier)
        self.assertIsNotNone(result.combined_multiplier)


class TestQualityMetricsCalculator(unittest.TestCase):
    """Tests for Quality Metrics Calculator."""

    def setUp(self):
        self.calculator = QualityMetricsCalculator()

    def test_new_5factor_framework_initialization(self):
        """Test that NEW_5FACTOR weights sum to 1.0."""
        weights = self.calculator.NEW_5FACTOR_WEIGHTS
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_default_framework_initialization(self):
        """Test that DEFAULT weights sum to 1.0."""
        weights = self.calculator.METRIC_WEIGHTS
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_new_5factor_quality_analysis(self):
        """Test NEW_5FACTOR framework quality analysis."""
        financial_data = {
            'ticker': 'TEST',
            'revenue': 1000,
            'cogs': 600,
            'total_assets': 2000,
            'net_income': 200,
            'shareholder_equity': 1000,
            'free_cash_flow': 250,
            'market_cap': 5000,
            'total_debt': 500,
            'nopat': 180,
            'operating_cash_flow': 220,
            'prior_total_assets': 1800,
            'prior_net_income': 180,
            'prior_revenue': 900,
            'prior_cogs': 550,
            'roe_history': [0.20, 0.22, 0.21, 0.23, 0.22, 0.20, 0.21, 0.23, 0.22, 0.21],
            'revenues': [1000, 900, 850, 800, 750],
            'margins': [0.40, 0.39, 0.38, 0.40, 0.41],
            'total_assets': 2000,
            'prior_total_assets': 1800,
            'ebit': 300,
            'interest_expense': 50,
            'retained_earnings': 500,
            'sales': 1000
        }

        result = self.calculator.calculate_quality_metrics(
            financial_data,
            framework='NEW_5FACTOR'
        )

        self.assertEqual(result.ticker, 'TEST')
        self.assertEqual(result.framework, 'NEW_5FACTOR')
        self.assertIsNotNone(result.composite_score)
        self.assertIsInstance(result.tier, QualityTier)
        self.assertIsNotNone(result.dimension_scores)
        self.assertIsNotNone(result.multiplier_result)

    def test_default_framework_quality_analysis(self):
        """Test DEFAULT framework quality analysis."""
        financial_data = {
            'ticker': 'TEST',
            'revenue': 1000,
            'cogs': 600,
            'sga': 100,
            'total_assets': 2000,
            'net_income': 200,
            'shareholder_equity': 1000,
            'free_cash_flow': 250,
            'market_cap': 5000,
            'total_debt': 500,
            'nopat': 180
        }

        result = self.calculator.calculate_quality_metrics(
            financial_data,
            framework='DEFAULT'
        )

        self.assertEqual(result.ticker, 'TEST')
        self.assertEqual(result.framework, 'DEFAULT')
        self.assertIsNotNone(result.composite_score)

    def test_tier_classification(self):
        """Test tier classification."""
        tier = self.calculator._classify_tier(90.0)
        self.assertEqual(tier, QualityTier.ELITE)

        tier = self.calculator._classify_tier(75.0)
        self.assertEqual(tier, QualityTier.STRONG)

        tier = self.calculator._classify_tier(60.0)
        self.assertEqual(tier, QualityTier.MODERATE)

        tier = self.calculator._classify_tier(40.0)
        self.assertEqual(tier, QualityTier.WEAK)


class TestIntegration(unittest.TestCase):
    """Integration tests for quality analysis framework."""

    def setUp(self):
        self.calculator = QualityMetricsCalculator()

    def test_full_quality_analysis_pipeline(self):
        """Test complete quality analysis with all data."""
        financial_data = {
            'ticker': 'AAPL',
            'revenue': 394_328_000_000,
            'cogs': 223_546_000_000,
            'sga': 26_094_000_000,
            'total_assets': 352_755_000_000,
            'net_income': 99_803_000_000,
            'shareholder_equity': 62_146_000_000,
            'free_cash_flow': 111_443_000_000,
            'market_cap': 3_000_000_000_000,
            'total_debt': 111_088_000_000,
            'nopat': 85_000_000_000,
            'operating_cash_flow': 111_443_000_000,
            'prior_total_assets': 320_000_000_000,
            'prior_net_income': 90_000_000_000,
            'prior_revenue': 383_000_000_000,
            'prior_cogs': 214_000_000_000,
            'roe_history': [0.46, 0.49, 0.55, 0.61, 0.56, 0.50, 0.63, 0.83, 1.00, 1.60],
            'revenues': [394_328_000_000, 383_285_000_000, 365_817_000_000, 333_736_000_000, 294_135_000_000],
            'margins': [0.43, 0.44, 0.42, 0.41, 0.40],
            'total_assets': 352_755_000_000,
            'prior_total_assets': 320_000_000_000,
            'ebit': 120_000_000_000,
            'interest_expense': 3_933_000_000,
            'retained_earnings': 30_000_000_000,
            'sales': 394_328_000_000,
            'ebitda': 125_000_000_000
        }

        result = self.calculator.calculate_quality_metrics(
            financial_data,
            framework='NEW_5FACTOR'
        )

        self.assertIsNotNone(result)
        self.assertGreater(result.composite_score, 50)
        self.assertIn(result.tier.value, ['Elite', 'Strong', 'Moderate', 'Weak'])


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestEarningsQualityAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestGrowthQualityAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestSafetyAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestLookbackCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestMultiplierCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestQualityMetricsCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
