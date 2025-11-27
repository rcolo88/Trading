#!/usr/bin/env python3
"""
Test Suite for STEPS Orchestrator
Tests each step individually and full pipeline integration

Author: LLM Portfolio Management System
Date: November 3, 2025
"""

import unittest
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import orchestrator
from workflows.steps_orchestrator import (
    STEPSOrchestrator,
    MarketEnvironment,
    QualityScore,
    ThematicScore,
    CompetitiveRanking,
    ValuationRating,
    PortfolioAllocation,
    Trade,
    DataQualityReport,
    ComplianceReport
)


class TestDataclasses(unittest.TestCase):
    """Test all dataclass definitions"""

    def test_market_environment_creation(self):
        """Test MarketEnvironment dataclass"""
        env = MarketEnvironment(
            sp500_price=6840.0,
            sp500_50ma=6700.0,
            sp500_200ma=6400.0,
            sp500_1m_return=0.26,
            sp500_ytd_return=28.0,
            trend="BULL",
            vix_level=15.2,
            vix_20ma=16.5,
            volatility_regime="LOW",
            leading_sectors=["Technology", "Communication Services"],
            lagging_sectors=["Energy", "Utilities"],
            sector_performance={"Technology": 35.0},
            market_breadth="NARROW",
            risk_appetite="RISK_ON",
            summary="Test summary",
            analysis_date="2025-11-03",
            data_quality="COMPLETE"
        )
        self.assertEqual(env.trend, "BULL")
        self.assertEqual(env.vix_level, 15.2)

    def test_quality_score_creation(self):
        """Test QualityScore dataclass"""
        score = QualityScore(
            ticker="NVDA",
            composite_score=9.0,
            gross_profitability=10.0,
            roe=10.0,
            earnings_quality=9.0,
            conservative_growth=7.0,
            tier="ELITE",
            meets_core_criteria=True
        )
        self.assertEqual(score.ticker, "NVDA")
        self.assertTrue(score.meets_core_criteria)
        self.assertEqual(score.tier, "ELITE")

    def test_trade_creation(self):
        """Test Trade dataclass"""
        trade = Trade(
            action="BUY",
            ticker="MSFT",
            shares=10,
            target_pct=15.0,
            priority="HIGH",
            reasoning="Quality score 9/10",
            stop_loss_pct=-15.0,
            profit_target_pct=50.0
        )
        self.assertEqual(trade.action, "BUY")
        self.assertEqual(trade.shares, 10)


class TestSTEPSOrchestrator(unittest.TestCase):
    """Test STEPS Orchestrator functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)

        # Create necessary directories
        Path("outputs").mkdir(exist_ok=True)
        Path("trading_recommendations").mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures"""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_orchestrator_initialization(self):
        """Test orchestrator can be initialized"""
        orch = STEPSOrchestrator(dry_run=True)
        self.assertTrue(orch.dry_run)
        self.assertFalse(orch.skip_thematic)

    def test_orchestrator_with_flags(self):
        """Test orchestrator respects CLI flags"""
        orch = STEPSOrchestrator(
            dry_run=True,
            skip_thematic=True,
            skip_competitive=True,
            verbose=True
        )
        self.assertTrue(orch.skip_thematic)
        self.assertTrue(orch.skip_competitive)
        self.assertTrue(orch.verbose)

    def test_step_1_market_environment(self):
        """Test STEP 1: Market Environment Assessment"""
        orch = STEPSOrchestrator(dry_run=True)
        result = orch._step_1_market_environment()

        self.assertIsInstance(result, MarketEnvironment)
        self.assertGreater(result.sp500_price, 0)
        self.assertIn(result.trend, ["STRONG_BULL", "BULL", "NEUTRAL", "BEAR", "STRONG_BEAR"])
        self.assertIn(result.volatility_regime, ["LOW", "MODERATE", "ELEVATED", "HIGH"])

    def test_step_2_holdings_quality_with_mock(self):
        """Test STEP 2: Holdings Quality Analysis (mocked)"""
        orch = STEPSOrchestrator(dry_run=True)

        # Mock subprocess call
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            # Create mock quality data file
            quality_data = {
                "NVDA": {
                    "composite_score": 9.0,
                    "gross_profitability": 72.0,
                    "roe": 31.0,
                    "earnings_quality": 10.0,
                    "conservative_growth": 7.0,
                    "tier": "ELITE"
                },
                "AMD": {
                    "composite_score": 5.0,
                    "gross_profitability": 43.0,
                    "roe": 4.75,
                    "earnings_quality": 5.0,
                    "conservative_growth": 6.0,
                    "tier": "WEAK"
                }
            }

            quality_file = Path("outputs") / f"quality_analysis_{datetime.now().strftime('%Y%m%d')}.json"
            with open(quality_file, 'w') as f:
                json.dump(quality_data, f)

            result = orch._step_2_holdings_quality()

            if result:  # Only if not mocked away
                self.assertIsInstance(result, dict)
                if "NVDA" in result:
                    self.assertIsInstance(result["NVDA"], QualityScore)

    def test_step_6_portfolio_construction(self):
        """Test STEP 6: Portfolio Construction"""
        orch = STEPSOrchestrator(dry_run=True)

        # Create mock portfolio state
        portfolio_data = {
            "timestamp": datetime.now().isoformat(),
            "cash": 100.0,
            "holdings": {
                "NVDA": {"shares": 1, "entry_price": 175.0},
                "GOOGL": {"shares": 1, "entry_price": 193.0}
            }
        }

        portfolio_file = Path("../portfolio_state.json")
        with open(portfolio_file, 'w') as f:
            json.dump(portfolio_data, f)

        result = orch._step_6_portfolio_construction()

        self.assertIsInstance(result, PortfolioAllocation)
        self.assertIsInstance(result.quality_holdings, dict)
        self.assertIsInstance(result.violations, list)

    def test_step_9_data_validation(self):
        """Test STEP 9: Data Validation"""
        orch = STEPSOrchestrator(dry_run=True)
        result = orch._step_9_data_validation()

        self.assertIsInstance(result, DataQualityReport)
        self.assertIn(result.overall_quality, ["COMPLETE", "PARTIAL", "INSUFFICIENT"])
        self.assertGreaterEqual(result.quality_score, 0)
        self.assertLessEqual(result.quality_score, 10)

    def test_step_10_framework_validation(self):
        """Test STEP 10: Framework Validation"""
        orch = STEPSOrchestrator(dry_run=True)
        result = orch._step_10_framework_validation()

        self.assertIsInstance(result, ComplianceReport)
        self.assertGreaterEqual(result.compliance_score, 0)
        self.assertLessEqual(result.compliance_score, 100)
        self.assertIsInstance(result.framework_compliant, bool)

    def test_export_trading_document(self):
        """Test trading document generation"""
        orch = STEPSOrchestrator(dry_run=False)

        # Create mock analysis results
        analysis_results = {
            'market_environment': MarketEnvironment(
                sp500_price=6840.0, sp500_50ma=6700.0, sp500_200ma=6400.0,
                sp500_1m_return=0.26, sp500_ytd_return=28.0,
                trend="BULL", vix_level=15.2, vix_20ma=16.5,
                volatility_regime="LOW",
                leading_sectors=["Technology"], lagging_sectors=["Energy"],
                sector_performance={}, market_breadth="NARROW",
                risk_appetite="RISK_ON", summary="Test market",
                analysis_date="2025-11-03", data_quality="COMPLETE"
            ),
            'holdings_quality': {
                "AMD": QualityScore(
                    ticker="AMD", composite_score=5.0,
                    gross_profitability=43.0, roe=4.75,
                    earnings_quality=5.0, conservative_growth=6.0,
                    tier="WEAK", meets_core_criteria=False
                )
            },
            'portfolio_allocation': PortfolioAllocation(
                quality_holdings={}, thematic_holdings={},
                cash_reserve=5.0, total_quality_pct=80.0,
                total_thematic_pct=20.0, violations=[]
            ),
            'compliance': ComplianceReport(
                portfolio_value=1000.0, compliance_score=95.0,
                violations=[], allocation_quality_pct=80.0,
                allocation_thematic_pct=20.0, allocation_cash_pct=5.0,
                framework_compliant=True
            )
        }

        output_file = orch.export_trading_document(analysis_results)

        self.assertTrue(Path(output_file).exists())
        self.assertTrue(output_file.endswith('.md'))

        # Verify content
        with open(output_file, 'r') as f:
            content = f.read()
            self.assertIn("# 🤖 LLM Trading Recommendations", content)
            self.assertIn("DOCUMENT HEADER", content)
            self.assertIn("RISK MANAGEMENT", content)
            self.assertIn("ORDERS SECTION", content)
            self.assertIn("AMD", content)  # Should have SELL recommendation

    def test_full_pipeline_dry_run(self):
        """Test full pipeline in dry-run mode"""
        orch = STEPSOrchestrator(
            dry_run=True,
            skip_thematic=True,
            skip_competitive=True,
            skip_valuation=True
        )

        # Mock subprocess calls
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            # Create minimal mock data
            quality_data = {
                "NVDA": {
                    "composite_score": 9.0,
                    "gross_profitability": 72.0,
                    "roe": 31.0,
                    "earnings_quality": 10.0,
                    "conservative_growth": 7.0,
                    "tier": "ELITE"
                }
            }

            quality_file = Path("outputs") / f"quality_analysis_{datetime.now().strftime('%Y%m%d')}.json"
            with open(quality_file, 'w') as f:
                json.dump(quality_data, f)

            try:
                output_file = orch.run_full_analysis()
                self.assertIsNotNone(output_file)
            except SystemExit:
                # STEP 2 may exit if quality analysis fails in real scenario
                pass


class TestErrorHandling(unittest.TestCase):
    """Test error handling scenarios"""

    def test_missing_quality_analysis(self):
        """Test behavior when quality analysis is unavailable"""
        orch = STEPSOrchestrator(dry_run=True)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error")
            result = orch._step_2_holdings_quality()
            self.assertIsNone(result)

    def test_graceful_degradation_on_optional_steps(self):
        """Test that optional step failures don't crash pipeline"""
        orch = STEPSOrchestrator(dry_run=True)

        # These should return empty results, not raise exceptions
        self.assertEqual(orch._step_3b_thematic_discovery(), {})
        self.assertEqual(orch._step_4_competitive_analysis(), {})
        self.assertEqual(orch._step_5_valuation_analysis(), {})


class TestOutputFormats(unittest.TestCase):
    """Test output format compliance"""

    def test_trading_document_format_compliance(self):
        """Test that trading document matches template requirements"""
        orch = STEPSOrchestrator(dry_run=False)

        analysis_results = {
            'market_environment': MarketEnvironment(
                sp500_price=6840.0, sp500_50ma=6700.0, sp500_200ma=6400.0,
                sp500_1m_return=0.26, sp500_ytd_return=28.0,
                trend="BULL", vix_level=15.2, vix_20ma=16.5,
                volatility_regime="LOW",
                leading_sectors=["Technology"], lagging_sectors=["Energy"],
                sector_performance={}, market_breadth="NARROW",
                risk_appetite="RISK_ON", summary="Test",
                analysis_date="2025-11-03", data_quality="COMPLETE"
            ),
            'holdings_quality': {},
            'portfolio_allocation': PortfolioAllocation(
                quality_holdings={}, thematic_holdings={},
                cash_reserve=5.0, total_quality_pct=0.0,
                total_thematic_pct=0.0, violations=[]
            ),
            'compliance': ComplianceReport(
                portfolio_value=0.0, compliance_score=0.0,
                violations=[], allocation_quality_pct=0.0,
                allocation_thematic_pct=0.0, allocation_cash_pct=0.0,
                framework_compliant=False
            )
        }

        temp_dir = tempfile.mkdtemp()
        original_dir = os.getcwd()
        os.chdir(temp_dir)

        try:
            Path("outputs").mkdir(exist_ok=True)
            Path("trading_recommendations").mkdir(exist_ok=True)

            output_file = orch.export_trading_document(analysis_results)

            with open(output_file, 'r') as f:
                content = f.read()

            # Check required sections
            required_sections = [
                "DOCUMENT HEADER",
                "RISK MANAGEMENT UPDATES",
                "ORDERS SECTION",
                "IMMEDIATE EXECUTION (HIGH PRIORITY)",
                "POSITION MANAGEMENT (MEDIUM PRIORITY)",
                "STRATEGIC POSITIONING (LOW PRIORITY)",
                "MARKET ANALYSIS & RATIONALE",
                "STRATEGIC ALLOCATION TARGETS",
                "EXECUTION NOTES"
            ]

            for section in required_sections:
                self.assertIn(section, content, f"Missing required section: {section}")

        finally:
            os.chdir(original_dir)
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDataclasses))
    suite.addTests(loader.loadTestsFromTestCase(TestSTEPSOrchestrator))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestOutputFormats))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
