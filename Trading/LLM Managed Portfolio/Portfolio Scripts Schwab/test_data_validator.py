"""
Test Suite for Data Quality Validator

Tests all functionality of data_validator.py including:
- Missing metric detection
- Stale data detection
- Data consistency validation
- Quality score calculation
- Report generation
- Batch processing

Author: Claude Code
Date: 2025-11-03
"""

import unittest
from datetime import datetime, timedelta
from data_validator import (
    DataValidator, MetricSource, DataQualityReport
)


class TestMetricSource(unittest.TestCase):
    """Test MetricSource dataclass"""

    def test_metric_source_creation(self):
        """Test creating MetricSource"""
        metric = MetricSource(
            metric_name="revenue",
            value=100000000.0,
            source="yfinance",
            fetch_date="2025-11-03",
            confidence="HIGH"
        )

        self.assertEqual(metric.metric_name, "revenue")
        self.assertEqual(metric.value, 100000000.0)
        self.assertEqual(metric.source, "yfinance")
        self.assertEqual(metric.fetch_date, "2025-11-03")
        self.assertEqual(metric.confidence, "HIGH")

    def test_metric_source_to_dict(self):
        """Test conversion to dictionary"""
        metric = MetricSource(
            metric_name="net_income",
            value=50000000.0,
            source="calculated",
            fetch_date="2025-11-03",
            confidence="MEDIUM"
        )

        d = metric.to_dict()
        self.assertEqual(d['metric_name'], "net_income")
        self.assertEqual(d['value'], 50000000.0)


class TestDataQualityReport(unittest.TestCase):
    """Test DataQualityReport dataclass"""

    def test_report_creation(self):
        """Test creating DataQualityReport"""
        metrics = [
            MetricSource("revenue", 100e6, "yfinance", "2025-11-03", "HIGH")
        ]

        report = DataQualityReport(
            ticker="TEST",
            overall_quality="COMPLETE",
            quality_score=9.5,
            metrics=metrics,
            missing_metrics=[],
            stale_metrics=[],
            warnings=[],
            validation_date="2025-11-03"
        )

        self.assertEqual(report.ticker, "TEST")
        self.assertEqual(report.overall_quality, "COMPLETE")
        self.assertEqual(report.quality_score, 9.5)

    def test_report_to_dict(self):
        """Test conversion to dictionary"""
        metrics = [
            MetricSource("revenue", 100e6, "yfinance", "2025-11-03", "HIGH")
        ]

        report = DataQualityReport(
            ticker="TEST",
            overall_quality="PARTIAL",
            quality_score=7.0,
            metrics=metrics,
            missing_metrics=["cogs"],
            stale_metrics=[],
            warnings=["Revenue growth seems high"],
            validation_date="2025-11-03"
        )

        d = report.to_dict()
        self.assertEqual(d['ticker'], "TEST")
        self.assertEqual(len(d['missing_metrics']), 1)
        self.assertEqual(d['missing_metrics'][0], "cogs")


class TestMissingMetricDetection(unittest.TestCase):
    """Test missing metric detection"""

    def setUp(self):
        self.validator = DataValidator()

    def test_no_missing_metrics(self):
        """Test when all required metrics are present"""
        financial_data = {
            'revenue': 100e6,
            'cogs': 40e6,
            'total_assets': 200e6,
            'shareholder_equity': 150e6,
            'operating_income': 30e6,
            'net_income': 25e6,
            'operating_cash_flow': 35e6,
            'total_debt': 50e6,
            'market_cap': 1e9
        }

        missing = self.validator.detect_missing_metrics(financial_data)
        self.assertEqual(len(missing), 0)

    def test_some_missing_metrics(self):
        """Test when some metrics are missing"""
        financial_data = {
            'revenue': 100e6,
            'total_assets': 200e6,
            'shareholder_equity': 150e6
        }

        missing = self.validator.detect_missing_metrics(financial_data)
        self.assertGreater(len(missing), 0)
        self.assertIn('cogs', missing)
        self.assertIn('net_income', missing)

    def test_all_missing_metrics(self):
        """Test when all metrics are missing"""
        financial_data = {}

        missing = self.validator.detect_missing_metrics(financial_data)
        self.assertEqual(len(missing), len(self.validator.REQUIRED_METRICS))

    def test_none_values_treated_as_missing(self):
        """Test that None values are treated as missing"""
        financial_data = {
            'revenue': None,
            'cogs': 40e6,
            'total_assets': None
        }

        missing = self.validator.detect_missing_metrics(financial_data)
        self.assertIn('revenue', missing)
        self.assertIn('total_assets', missing)
        self.assertNotIn('cogs', missing)


class TestStaleDataDetection(unittest.TestCase):
    """Test stale data detection"""

    def setUp(self):
        self.validator = DataValidator()

    def test_fresh_data(self):
        """Test when data is fresh (< 90 days)"""
        today = datetime.now()
        financial_data = {
            'revenue': 100e6,
            'net_income': 25e6,
            'last_updated': today.strftime('%Y-%m-%d')
        }

        stale = self.validator.detect_stale_data(financial_data, max_age_days=90)
        self.assertEqual(len(stale), 0)

    def test_stale_data(self):
        """Test when data is stale (> 90 days)"""
        old_date = datetime.now() - timedelta(days=120)
        financial_data = {
            'revenue': 100e6,
            'net_income': 25e6,
            'total_assets': 200e6,
            'last_updated': old_date.strftime('%Y-%m-%d')
        }

        stale = self.validator.detect_stale_data(financial_data, max_age_days=90)
        self.assertGreater(len(stale), 0)

    def test_no_last_updated_field(self):
        """Test when last_updated field is missing"""
        financial_data = {
            'revenue': 100e6,
            'net_income': 25e6
        }

        stale = self.validator.detect_stale_data(financial_data)
        # Should return fundamental metrics as stale
        self.assertGreater(len(stale), 0)


class TestDataConsistencyValidation(unittest.TestCase):
    """Test data consistency validation"""

    def setUp(self):
        self.validator = DataValidator()

    def test_consistent_data(self):
        """Test when all data is consistent"""
        financial_data = {
            'revenue': 100e6,
            'cogs': 40e6,
            'operating_income': 30e6,
            'total_assets': 200e6,
            'shareholder_equity': 150e6,
            'total_debt': 50e6,
            'market_cap': 1e9
        }

        warnings = self.validator.validate_data_consistency(financial_data)
        self.assertEqual(len(warnings), 0)

    def test_negative_revenue(self):
        """Test detection of negative revenue"""
        financial_data = {
            'revenue': -100e6
        }

        warnings = self.validator.validate_data_consistency(financial_data)
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any('revenue' in w.lower() for w in warnings))

    def test_negative_market_cap(self):
        """Test detection of negative market cap"""
        financial_data = {
            'market_cap': -1e9
        }

        warnings = self.validator.validate_data_consistency(financial_data)
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any('market cap' in w.lower() for w in warnings))

    def test_operating_income_exceeds_revenue(self):
        """Test detection of operating income > revenue"""
        financial_data = {
            'revenue': 100e6,
            'operating_income': 150e6
        }

        warnings = self.validator.validate_data_consistency(financial_data)
        self.assertGreater(len(warnings), 0)

    def test_negative_gross_margin(self):
        """Test detection of negative gross margin"""
        financial_data = {
            'revenue': 100e6,
            'cogs': 120e6  # COGS > Revenue
        }

        warnings = self.validator.validate_data_consistency(financial_data)
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any('gross margin' in w.lower() for w in warnings))

    def test_negative_equity(self):
        """Test detection of negative equity"""
        financial_data = {
            'shareholder_equity': -50e6
        }

        warnings = self.validator.validate_data_consistency(financial_data)
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any('equity' in w.lower() for w in warnings))

    def test_excessive_leverage(self):
        """Test detection of excessive leverage (Debt/Assets > 80%)"""
        financial_data = {
            'total_assets': 100e6,
            'total_debt': 90e6  # 90% debt ratio
        }

        warnings = self.validator.validate_data_consistency(financial_data)
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any('leverage' in w.lower() or 'debt' in w.lower() for w in warnings))


class TestQualityScoreCalculation(unittest.TestCase):
    """Test quality score calculation"""

    def setUp(self):
        self.validator = DataValidator()

    def test_perfect_score(self):
        """Test calculation with no issues"""
        score = self.validator._calculate_quality_score(
            missing_metrics=[],
            stale_metrics=[],
            warnings=[]
        )
        self.assertEqual(score, 10.0)

    def test_score_with_missing_metrics(self):
        """Test penalty for missing metrics (-2 each)"""
        score = self.validator._calculate_quality_score(
            missing_metrics=['revenue', 'cogs'],  # 2 missing
            stale_metrics=[],
            warnings=[]
        )
        self.assertEqual(score, 6.0)  # 10 - (2 * 2)

    def test_score_with_stale_metrics(self):
        """Test penalty for stale metrics (-1 each)"""
        score = self.validator._calculate_quality_score(
            missing_metrics=[],
            stale_metrics=['revenue', 'net_income'],  # 2 stale
            warnings=[]
        )
        self.assertEqual(score, 8.0)  # 10 - (2 * 1)

    def test_score_with_warnings(self):
        """Test penalty for warnings (-0.5 each)"""
        score = self.validator._calculate_quality_score(
            missing_metrics=[],
            stale_metrics=[],
            warnings=['Warning 1', 'Warning 2', 'Warning 3']  # 3 warnings
        )
        self.assertEqual(score, 8.5)  # 10 - (3 * 0.5)

    def test_score_with_all_issues(self):
        """Test combined penalties"""
        score = self.validator._calculate_quality_score(
            missing_metrics=['revenue'],  # -2
            stale_metrics=['net_income'],  # -1
            warnings=['Warning 1', 'Warning 2']  # -1 total
        )
        self.assertEqual(score, 6.0)  # 10 - 2 - 1 - 1

    def test_score_minimum_zero(self):
        """Test that score cannot go below zero"""
        score = self.validator._calculate_quality_score(
            missing_metrics=['m1', 'm2', 'm3', 'm4', 'm5', 'm6'],  # -12
            stale_metrics=['s1', 's2'],  # -2
            warnings=['w1', 'w2']  # -1
        )
        self.assertEqual(score, 0.0)  # Should not be negative


class TestOverallQualityDetermination(unittest.TestCase):
    """Test overall quality classification"""

    def setUp(self):
        self.validator = DataValidator()

    def test_complete_quality(self):
        """Test COMPLETE classification"""
        quality = self.validator._determine_overall_quality(
            quality_score=9.0,
            missing_metrics=[]
        )
        self.assertEqual(quality, "COMPLETE")

    def test_partial_quality(self):
        """Test PARTIAL classification"""
        quality = self.validator._determine_overall_quality(
            quality_score=7.0,
            missing_metrics=['cogs']  # Non-critical metric
        )
        self.assertEqual(quality, "PARTIAL")

    def test_insufficient_quality_missing_critical(self):
        """Test INSUFFICIENT when critical metrics missing"""
        quality = self.validator._determine_overall_quality(
            quality_score=5.0,
            missing_metrics=['revenue', 'total_assets']  # Critical metrics
        )
        self.assertEqual(quality, "INSUFFICIENT")

    def test_insufficient_quality_low_score(self):
        """Test INSUFFICIENT with low score and missing critical"""
        quality = self.validator._determine_overall_quality(
            quality_score=3.0,
            missing_metrics=['net_income']  # Critical
        )
        self.assertEqual(quality, "INSUFFICIENT")


class TestReportGeneration(unittest.TestCase):
    """Test report generation"""

    def setUp(self):
        self.validator = DataValidator()

    def test_generate_complete_report(self):
        """Test generating report for complete data"""
        metrics = [
            MetricSource("revenue", 100e6, "yfinance", "2025-11-03", "HIGH"),
            MetricSource("net_income", 25e6, "yfinance", "2025-11-03", "HIGH")
        ]

        report = DataQualityReport(
            ticker="TEST",
            overall_quality="COMPLETE",
            quality_score=10.0,
            metrics=metrics,
            missing_metrics=[],
            stale_metrics=[],
            warnings=[],
            validation_date="2025-11-03"
        )

        markdown = self.validator.generate_validation_report(report)

        # Check key sections present
        self.assertIn("# Data Quality Report: TEST", markdown)
        self.assertIn("Overall Quality: COMPLETE", markdown)
        self.assertIn("Quality Score", markdown)
        self.assertIn("10.0/10", markdown)
        self.assertIn("excellent", markdown.lower())

    def test_generate_report_with_missing(self):
        """Test generating report with missing metrics"""
        report = DataQualityReport(
            ticker="TEST",
            overall_quality="PARTIAL",
            quality_score=6.0,
            metrics=[],
            missing_metrics=["revenue", "cogs"],
            stale_metrics=[],
            warnings=[],
            validation_date="2025-11-03"
        )

        markdown = self.validator.generate_validation_report(report)

        self.assertIn("Missing Metrics", markdown)
        self.assertIn("revenue", markdown)
        self.assertIn("cogs", markdown)

    def test_generate_report_with_warnings(self):
        """Test generating report with warnings"""
        report = DataQualityReport(
            ticker="TEST",
            overall_quality="PARTIAL",
            quality_score=7.5,
            metrics=[],
            missing_metrics=[],
            stale_metrics=[],
            warnings=["Revenue growth seems high", "Negative equity"],
            validation_date="2025-11-03"
        )

        markdown = self.validator.generate_validation_report(report)

        self.assertIn("Warnings", markdown)
        self.assertIn("Revenue growth", markdown)
        self.assertIn("Negative equity", markdown)


class TestBatchValidation(unittest.TestCase):
    """Test batch validation functionality"""

    def setUp(self):
        self.validator = DataValidator()

    def test_batch_validate_with_provided_data(self):
        """Test batch validation with provided data"""
        financial_data_dict = {
            'TEST1': {
                'revenue': 100e6,
                'cogs': 40e6,
                'total_assets': 200e6,
                'shareholder_equity': 150e6,
                'operating_income': 30e6,
                'net_income': 25e6,
                'operating_cash_flow': 35e6,
                'total_debt': 50e6,
                'market_cap': 1e9,
                'last_updated': datetime.now().strftime('%Y-%m-%d')
            },
            'TEST2': {
                'revenue': 50e6,
                'total_assets': 100e6,
                'shareholder_equity': 80e6
            }
        }

        reports = self.validator.batch_validate_portfolio(
            tickers=['TEST1', 'TEST2'],
            financial_data_dict=financial_data_dict
        )

        self.assertEqual(len(reports), 2)
        self.assertIn('TEST1', reports)
        self.assertIn('TEST2', reports)

        # TEST1 should have better quality (all metrics present)
        self.assertGreater(
            reports['TEST1'].quality_score,
            reports['TEST2'].quality_score
        )


class TestExportFunctionality(unittest.TestCase):
    """Test export functionality"""

    def setUp(self):
        self.validator = DataValidator()

    def test_to_dict_conversion(self):
        """Test that reports can be converted to dict for JSON export"""
        report = DataQualityReport(
            ticker="TEST",
            overall_quality="COMPLETE",
            quality_score=9.0,
            metrics=[],
            missing_metrics=[],
            stale_metrics=[],
            warnings=[],
            validation_date="2025-11-03"
        )

        d = report.to_dict()

        self.assertIsInstance(d, dict)
        self.assertEqual(d['ticker'], "TEST")
        self.assertEqual(d['quality_score'], 9.0)


def run_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMetricSource))
    suite.addTests(loader.loadTestsFromTestCase(TestDataQualityReport))
    suite.addTests(loader.loadTestsFromTestCase(TestMissingMetricDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestStaleDataDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestDataConsistencyValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestQualityScoreCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestOverallQualityDetermination))
    suite.addTests(loader.loadTestsFromTestCase(TestReportGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestBatchValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestExportFunctionality))

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
