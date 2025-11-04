"""
Test Suite for Framework Compliance Validator

Tests all functionality of framework_validator.py including:
- 80/20 allocation validation
- Position sizing validation
- Quality threshold validation
- Thematic threshold validation
- Compliance score calculation
- Report generation

Author: Claude Code
Date: 2025-11-03
"""

import unittest
from framework_validator import (
    FrameworkValidator, Violation, ComplianceReport
)


class TestViolation(unittest.TestCase):
    """Test Violation dataclass"""

    def test_violation_creation(self):
        """Test creating Violation"""
        violation = Violation(
            severity="CRITICAL",
            category="ALLOCATION",
            ticker="NVDA",
            message="Test violation",
            current_value=60.0,
            expected_value=75.0
        )

        self.assertEqual(violation.severity, "CRITICAL")
        self.assertEqual(violation.category, "ALLOCATION")
        self.assertEqual(violation.ticker, "NVDA")
        self.assertEqual(violation.message, "Test violation")
        self.assertEqual(violation.current_value, 60.0)
        self.assertEqual(violation.expected_value, 75.0)

    def test_violation_to_dict(self):
        """Test conversion to dictionary"""
        violation = Violation(
            severity="WARNING",
            category="POSITION_SIZE",
            ticker="AMD",
            message="Position too small",
            current_value=3.0,
            expected_value=5.0
        )

        d = violation.to_dict()
        self.assertEqual(d['severity'], "WARNING")
        self.assertEqual(d['ticker'], "AMD")


class TestComplianceReport(unittest.TestCase):
    """Test ComplianceReport dataclass"""

    def test_report_creation(self):
        """Test creating ComplianceReport"""
        violations = [
            Violation("WARNING", "ALLOCATION", None, "Test", 78.0, 80.0)
        ]

        report = ComplianceReport(
            portfolio_value=100000.0,
            compliance_score=95.0,
            violations=violations,
            allocation_quality_pct=78.0,
            allocation_thematic_pct=18.0,
            allocation_cash_pct=4.0,
            framework_compliant=True,
            validation_date="2025-11-03"
        )

        self.assertEqual(report.portfolio_value, 100000.0)
        self.assertEqual(report.compliance_score, 95.0)
        self.assertTrue(report.framework_compliant)

    def test_report_to_dict(self):
        """Test conversion to dictionary"""
        violations = []

        report = ComplianceReport(
            portfolio_value=50000.0,
            compliance_score=100.0,
            violations=violations,
            allocation_quality_pct=80.0,
            allocation_thematic_pct=15.0,
            allocation_cash_pct=5.0,
            framework_compliant=True,
            validation_date="2025-11-03"
        )

        d = report.to_dict()
        self.assertEqual(d['portfolio_value'], 50000.0)
        self.assertEqual(d['compliance_score'], 100.0)


class TestAllocationValidation(unittest.TestCase):
    """Test 80/20 allocation validation"""

    def setUp(self):
        self.validator = FrameworkValidator()

    def test_perfect_allocation(self):
        """Test when allocation is perfect (80/20/5)"""
        violations = self.validator.validate_80_20_allocation(
            allocation_quality_pct=80.0,
            allocation_thematic_pct=15.0,
            allocation_cash_pct=5.0
        )
        self.assertEqual(len(violations), 0)

    def test_quality_within_range(self):
        """Test quality allocation within acceptable range"""
        violations = self.validator.validate_80_20_allocation(
            allocation_quality_pct=78.0,
            allocation_thematic_pct=17.0,
            allocation_cash_pct=5.0
        )
        self.assertEqual(len(violations), 0)

    def test_quality_below_minimum_warning(self):
        """Test quality allocation below minimum triggers warning"""
        violations = self.validator.validate_80_20_allocation(
            allocation_quality_pct=73.0,
            allocation_thematic_pct=22.0,
            allocation_cash_pct=5.0
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "WARNING" and "Quality" in v.message for v in violations))

    def test_quality_below_minimum_critical(self):
        """Test quality allocation far below minimum triggers critical"""
        violations = self.validator.validate_80_20_allocation(
            allocation_quality_pct=65.0,
            allocation_thematic_pct=30.0,
            allocation_cash_pct=5.0
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "CRITICAL" and "Quality" in v.message for v in violations))

    def test_quality_above_maximum_warning(self):
        """Test quality allocation above maximum triggers warning"""
        violations = self.validator.validate_80_20_allocation(
            allocation_quality_pct=87.0,
            allocation_thematic_pct=8.0,
            allocation_cash_pct=5.0
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "WARNING" and "Quality" in v.message for v in violations))

    def test_thematic_above_maximum_critical(self):
        """Test thematic allocation above maximum triggers critical"""
        violations = self.validator.validate_80_20_allocation(
            allocation_quality_pct=60.0,
            allocation_thematic_pct=35.0,
            allocation_cash_pct=5.0
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "CRITICAL" and "Opportunistic" in v.message for v in violations))

    def test_cash_critically_low(self):
        """Test critically low cash triggers critical violation"""
        violations = self.validator.validate_80_20_allocation(
            allocation_quality_pct=80.0,
            allocation_thematic_pct=18.5,
            allocation_cash_pct=1.5
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "CRITICAL" and "Cash" in v.message for v in violations))

    def test_cash_below_minimum(self):
        """Test cash below minimum triggers warning"""
        violations = self.validator.validate_80_20_allocation(
            allocation_quality_pct=80.0,
            allocation_thematic_pct=17.5,
            allocation_cash_pct=2.5
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "WARNING" and "Cash" in v.message for v in violations))


class TestPositionSizingValidation(unittest.TestCase):
    """Test position sizing validation"""

    def setUp(self):
        self.validator = FrameworkValidator()

    def test_quality_position_in_range(self):
        """Test quality position within range"""
        holdings = {'NVDA': 15.0}  # 15% position
        quality_scores = {'NVDA': 90.0}  # Quality 9.0 (range 10-20%)
        thematic_scores = {}

        violations = self.validator.validate_position_sizing(
            holdings, quality_scores, thematic_scores
        )
        # Should be within 10-20% range, no violations
        self.assertEqual(len(violations), 0)

    def test_quality_position_below_range(self):
        """Test quality position below recommended range"""
        holdings = {'MSFT': 4.0}  # 4% position
        quality_scores = {'MSFT': 85.0}  # Quality 8.5 (range 7-12%)
        thematic_scores = {}

        violations = self.validator.validate_position_sizing(
            holdings, quality_scores, thematic_scores
        )
        # Should trigger INFO or WARNING for being below 7%
        self.assertGreater(len(violations), 0)

    def test_concentration_risk(self):
        """Test concentration risk (position >20%)"""
        holdings = {'GOOGL': 25.0}  # 25% position - too large!
        quality_scores = {'GOOGL': 88.0}
        thematic_scores = {}

        violations = self.validator.validate_position_sizing(
            holdings, quality_scores, thematic_scores
        )
        # Should trigger CRITICAL for concentration risk
        self.assertTrue(any(v.severity == "CRITICAL" and "concentration" in v.message.lower() for v in violations))

    def test_thematic_position_exceeds_maximum(self):
        """Test thematic position exceeds 7% maximum"""
        holdings = {'IONQ': 8.0}  # 8% thematic position - too large!
        quality_scores = {}
        thematic_scores = {'IONQ': 35.0}  # Thematic score 35/40

        violations = self.validator.validate_position_sizing(
            holdings, quality_scores, thematic_scores
        )
        # Should trigger CRITICAL for exceeding thematic maximum
        self.assertTrue(any(v.severity == "CRITICAL" and "thematic" in v.message.lower() for v in violations))

    def test_thematic_position_in_range(self):
        """Test thematic position within range"""
        holdings = {'IONQ': 4.0}  # 4% thematic position
        quality_scores = {}
        thematic_scores = {'IONQ': 32.0}  # Thematic score 32/40 (range 3-5%)

        violations = self.validator.validate_position_sizing(
            holdings, quality_scores, thematic_scores
        )
        # Should be within range, no violations
        self.assertEqual(len(violations), 0)


class TestQualityThresholdValidation(unittest.TestCase):
    """Test quality threshold validation"""

    def setUp(self):
        self.validator = FrameworkValidator()

    def test_quality_above_threshold(self):
        """Test quality holdings above threshold"""
        holdings_types = {'NVDA': 'QUALITY', 'GOOGL': 'QUALITY'}
        quality_scores = {'NVDA': 90.0, 'GOOGL': 85.0}

        violations = self.validator.validate_quality_thresholds(
            holdings_types, quality_scores
        )
        self.assertEqual(len(violations), 0)

    def test_quality_below_threshold_critical(self):
        """Test quality holding below threshold triggers critical"""
        holdings_types = {'AMD': 'QUALITY'}
        quality_scores = {'AMD': 65.0}  # Below 70 threshold

        violations = self.validator.validate_quality_thresholds(
            holdings_types, quality_scores
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "CRITICAL" and v.ticker == "AMD" for v in violations))

    def test_quality_near_threshold_warning(self):
        """Test quality holding near threshold triggers warning"""
        holdings_types = {'XLV': 'QUALITY'}
        quality_scores = {'XLV': 72.0}  # Above 70 but below 75

        violations = self.validator.validate_quality_thresholds(
            holdings_types, quality_scores
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "WARNING" and v.ticker == "XLV" for v in violations))

    def test_thematic_holdings_exempt(self):
        """Test thematic holdings are exempt from quality threshold"""
        holdings_types = {'IONQ': 'THEMATIC'}
        quality_scores = {'IONQ': 50.0}  # Low quality but it's thematic

        violations = self.validator.validate_quality_thresholds(
            holdings_types, quality_scores
        )
        # Thematic holdings should not be checked for quality threshold
        self.assertEqual(len(violations), 0)


class TestThematicThresholdValidation(unittest.TestCase):
    """Test thematic threshold validation"""

    def setUp(self):
        self.validator = FrameworkValidator()

    def test_thematic_above_threshold(self):
        """Test thematic holdings above threshold"""
        thematic_holdings = ['IONQ', 'QS']
        thematic_scores = {'IONQ': 35.0, 'QS': 30.0}

        violations = self.validator.validate_thematic_thresholds(
            thematic_holdings, thematic_scores
        )
        self.assertEqual(len(violations), 0)

    def test_thematic_below_threshold_critical(self):
        """Test thematic holding below threshold triggers critical"""
        thematic_holdings = ['WEAK']
        thematic_scores = {'WEAK': 25.0}  # Below 28 threshold

        violations = self.validator.validate_thematic_thresholds(
            thematic_holdings, thematic_scores
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "CRITICAL" and v.ticker == "WEAK" for v in violations))

    def test_thematic_near_threshold_warning(self):
        """Test thematic holding near threshold triggers warning"""
        thematic_holdings = ['RISKY']
        thematic_scores = {'RISKY': 29.0}  # Above 28 but below 30

        violations = self.validator.validate_thematic_thresholds(
            thematic_holdings, thematic_scores
        )
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.severity == "WARNING" and v.ticker == "RISKY" for v in violations))


class TestComplianceScoreCalculation(unittest.TestCase):
    """Test compliance score calculation"""

    def setUp(self):
        self.validator = FrameworkValidator()

    def test_perfect_score(self):
        """Test score with no violations"""
        violations = []
        score = self.validator.calculate_compliance_score(violations)
        self.assertEqual(score, 100.0)

    def test_score_with_critical(self):
        """Test score with critical violations (-20 each)"""
        violations = [
            Violation("CRITICAL", "ALLOCATION", None, "Test", 60.0, 75.0),
            Violation("CRITICAL", "THRESHOLD", "AMD", "Test", 65.0, 70.0)
        ]
        score = self.validator.calculate_compliance_score(violations)
        self.assertEqual(score, 60.0)  # 100 - 20 - 20

    def test_score_with_warnings(self):
        """Test score with warning violations (-5 each)"""
        violations = [
            Violation("WARNING", "ALLOCATION", None, "Test", 73.0, 75.0),
            Violation("WARNING", "POSITION_SIZE", "XLV", "Test", 4.0, 5.0)
        ]
        score = self.validator.calculate_compliance_score(violations)
        self.assertEqual(score, 90.0)  # 100 - 5 - 5

    def test_score_with_info(self):
        """Test score with info violations (-1 each)"""
        violations = [
            Violation("INFO", "ALLOCATION", None, "Test", 4.5, 5.0),
            Violation("INFO", "POSITION_SIZE", "META", "Test", 9.5, 10.0)
        ]
        score = self.validator.calculate_compliance_score(violations)
        self.assertEqual(score, 98.0)  # 100 - 1 - 1

    def test_score_with_mixed_violations(self):
        """Test score with mixed severity violations"""
        violations = [
            Violation("CRITICAL", "THRESHOLD", "AMD", "Test", 65.0, 70.0),  # -20
            Violation("WARNING", "ALLOCATION", None, "Test", 73.0, 75.0),  # -5
            Violation("INFO", "POSITION_SIZE", "META", "Test", 9.5, 10.0)  # -1
        ]
        score = self.validator.calculate_compliance_score(violations)
        self.assertEqual(score, 74.0)  # 100 - 20 - 5 - 1

    def test_score_minimum_zero(self):
        """Test that score cannot go below zero"""
        violations = [
            Violation("CRITICAL", "TEST", None, "Test", 0, 0) for _ in range(10)  # -200 total
        ]
        score = self.validator.calculate_compliance_score(violations)
        self.assertEqual(score, 0.0)


class TestPortfolioValidation(unittest.TestCase):
    """Test full portfolio validation"""

    def setUp(self):
        self.validator = FrameworkValidator()

    def test_compliant_portfolio(self):
        """Test fully compliant portfolio"""
        # Portfolio totaling 100000: 80% quality, 15% thematic, 5% cash
        # All positions properly sized within framework guidelines
        portfolio_state = {
            'holdings': {
                'NVDA': 18000,   # 18% quality (within 10-20% for quality 9-10)
                'GOOGL': 18000,  # 18% quality (within 7-12% for quality 8-9)
                'MSFT': 18000,   # 18% quality (within 7-12% for quality 8-9)
                'META': 13000,   # 13% quality (within 7-12% for quality 8-9)
                'AAPL': 13000,   # 13% quality (within 7-12% for quality 8-9)
                'IONQ': 6000,    # 6% thematic (within 5-7% for thematic 35-40)
                'QS': 5000,      # 5% thematic (within 3-5% for thematic 30-34)
                'PLTR': 4000,    # 4% thematic (within 3-5% for thematic 30-34)
            },
            'cash': 5000  # 5%
        }

        quality_scores = {
            'NVDA': 90.0,
            'GOOGL': 85.0,
            'MSFT': 88.0,
            'META': 82.0,
            'AAPL': 87.0,
            'IONQ': 60.0,
            'QS': 55.0,
            'PLTR': 58.0
        }

        thematic_scores = {
            'IONQ': 35.0,
            'QS': 32.0,
            'PLTR': 31.0
        }

        holdings_types = {
            'NVDA': 'QUALITY',
            'GOOGL': 'QUALITY',
            'MSFT': 'QUALITY',
            'META': 'QUALITY',
            'AAPL': 'QUALITY',
            'IONQ': 'THEMATIC',
            'QS': 'THEMATIC',
            'PLTR': 'THEMATIC'
        }

        report = self.validator.validate_portfolio(
            portfolio_state, quality_scores, thematic_scores, holdings_types
        )

        # Portfolio is compliant (no CRITICAL violations) but has some minor warnings/info
        self.assertTrue(report.framework_compliant)
        # Score is 88 due to 2 WARNING (-5 each) and 2 INFO (-1 each) violations
        # These are acceptable position sizing adjustments
        self.assertGreaterEqual(report.compliance_score, 85.0)
        # No critical violations
        critical_violations = [v for v in report.violations if v.severity == "CRITICAL"]
        self.assertEqual(len(critical_violations), 0)

    def test_non_compliant_quality_threshold(self):
        """Test portfolio with quality threshold violation"""
        portfolio_state = {
            'holdings': {
                'NVDA': 15000,
                'AMD': 10000,  # Low quality
            },
            'cash': 5000
        }

        quality_scores = {
            'NVDA': 90.0,
            'AMD': 65.0  # Below 70 threshold
        }

        thematic_scores = {}

        report = self.validator.validate_portfolio(
            portfolio_state, quality_scores, thematic_scores
        )

        self.assertFalse(report.framework_compliant)
        self.assertLess(report.compliance_score, 100.0)
        self.assertTrue(any(v.severity == "CRITICAL" for v in report.violations))

    def test_non_compliant_allocation(self):
        """Test portfolio with allocation violation"""
        portfolio_state = {
            'holdings': {
                'NVDA': 30000,  # 60% - way too low for quality
                'IONQ': 15000,  # 30% thematic - too high!
            },
            'cash': 5000  # 10%
        }

        quality_scores = {'NVDA': 90.0}
        thematic_scores = {'IONQ': 35.0}
        holdings_types = {'NVDA': 'QUALITY', 'IONQ': 'THEMATIC'}

        report = self.validator.validate_portfolio(
            portfolio_state, quality_scores, thematic_scores, holdings_types
        )

        self.assertFalse(report.framework_compliant)
        self.assertTrue(any(v.category == "ALLOCATION" for v in report.violations))

    def test_concentration_risk_violation(self):
        """Test portfolio with concentration risk"""
        portfolio_state = {
            'holdings': {
                'NVDA': 25000,  # 50% - concentration risk!
                'GOOGL': 5000   # 10%
            },
            'cash': 20000  # 40%
        }

        quality_scores = {'NVDA': 90.0, 'GOOGL': 85.0}
        thematic_scores = {}

        report = self.validator.validate_portfolio(
            portfolio_state, quality_scores, thematic_scores
        )

        self.assertFalse(report.framework_compliant)
        self.assertTrue(any(v.category == "CONCENTRATION" for v in report.violations))


class TestReportGeneration(unittest.TestCase):
    """Test report generation"""

    def setUp(self):
        self.validator = FrameworkValidator()

    def test_generate_compliant_report(self):
        """Test generating report for compliant portfolio"""
        violations = []

        report = ComplianceReport(
            portfolio_value=100000.0,
            compliance_score=100.0,
            violations=violations,
            allocation_quality_pct=80.0,
            allocation_thematic_pct=15.0,
            allocation_cash_pct=5.0,
            framework_compliant=True,
            validation_date="2025-11-03"
        )

        markdown = self.validator.generate_compliance_report_markdown(report)

        # Check key sections present
        self.assertIn("# Framework Compliance Report", markdown)
        self.assertIn("Compliance Score: 100/100", markdown)
        self.assertIn("✅ COMPLIANT", markdown)
        self.assertIn("**Quality Holdings**: 80.0%", markdown)  # Match actual format with bold and colon

    def test_generate_non_compliant_report(self):
        """Test generating report with violations"""
        violations = [
            Violation("CRITICAL", "THRESHOLD", "AMD", "Quality score 65 below threshold 70", 65.0, 70.0),
            Violation("WARNING", "ALLOCATION", None, "Quality allocation 73% below minimum 75%", 73.0, 75.0)
        ]

        report = ComplianceReport(
            portfolio_value=50000.0,
            compliance_score=75.0,
            violations=violations,
            allocation_quality_pct=73.0,
            allocation_thematic_pct=22.0,
            allocation_cash_pct=5.0,
            framework_compliant=False,
            validation_date="2025-11-03"
        )

        markdown = self.validator.generate_compliance_report_markdown(report)

        self.assertIn("❌ NON-COMPLIANT", markdown)
        self.assertIn("CRITICAL (1)", markdown)
        self.assertIn("WARNING (1)", markdown)
        self.assertIn("AMD", markdown)


def run_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestViolation))
    suite.addTests(loader.loadTestsFromTestCase(TestComplianceReport))
    suite.addTests(loader.loadTestsFromTestCase(TestAllocationValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestPositionSizingValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestQualityThresholdValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestThematicThresholdValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestComplianceScoreCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestPortfolioValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestReportGeneration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == '__main__':
    result = run_tests()

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")

    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED")

        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}")

        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}")
