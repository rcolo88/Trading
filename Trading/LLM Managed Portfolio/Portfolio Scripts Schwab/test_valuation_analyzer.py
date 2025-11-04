"""
Test suite for Valuation Analyzer
Tests quality-adjusted thresholds, rating logic, and recommendations
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
from pathlib import Path

from valuation_analyzer import (
    ValuationAnalyzer,
    ValuationMetrics,
    ValuationRating
)


class TestQualityAdjustedThresholds(unittest.TestCase):
    """Test quality-adjusted P/E threshold calculation"""

    def setUp(self):
        self.analyzer = ValuationAnalyzer()

    def test_quality_below_7_max_pe_15(self):
        """Test quality score <7 gets max P/E of 15x"""
        max_pe = self.analyzer.calculate_quality_adjusted_threshold(60.0)  # 6.0 on 10-scale
        self.assertEqual(max_pe, 15.0)

    def test_quality_7_to_8_max_pe_20(self):
        """Test quality score 7-8 gets max P/E of 20x"""
        max_pe = self.analyzer.calculate_quality_adjusted_threshold(75.0)  # 7.5 on 10-scale
        self.assertEqual(max_pe, 20.0)

    def test_quality_8_to_9_max_pe_30(self):
        """Test quality score 8-9 gets max P/E of 30x"""
        max_pe = self.analyzer.calculate_quality_adjusted_threshold(85.0)  # 8.5 on 10-scale
        self.assertEqual(max_pe, 30.0)

    def test_quality_above_9_max_pe_40(self):
        """Test quality score >9 gets max P/E of 40x"""
        max_pe = self.analyzer.calculate_quality_adjusted_threshold(95.0)  # 9.5 on 10-scale
        self.assertEqual(max_pe, 40.0)

    def test_boundary_quality_70(self):
        """Test boundary at quality score 70 (7.0 on 10-scale)"""
        max_pe = self.analyzer.calculate_quality_adjusted_threshold(70.0)
        self.assertEqual(max_pe, 20.0)  # Should be in 7-8 range

    def test_boundary_quality_80(self):
        """Test boundary at quality score 80 (8.0 on 10-scale)"""
        max_pe = self.analyzer.calculate_quality_adjusted_threshold(80.0)
        self.assertEqual(max_pe, 30.0)  # Should be in 8-9 range

    def test_boundary_quality_90(self):
        """Test boundary at quality score 90 (9.0 on 10-scale)"""
        max_pe = self.analyzer.calculate_quality_adjusted_threshold(90.0)
        self.assertEqual(max_pe, 40.0)  # Should be >9 range


class TestPERating(unittest.TestCase):
    """Test P/E rating logic"""

    def setUp(self):
        self.analyzer = ValuationAnalyzer()

    def test_cheap_pe_below_70_percent(self):
        """Test CHEAP rating for P/E <70% of max"""
        max_pe = 30.0
        actual_pe = 20.0  # 66.7% of max
        rating = self.analyzer.rate_pe_valuation(actual_pe, max_pe)
        self.assertEqual(rating, "CHEAP")

    def test_fair_pe_below_100_percent(self):
        """Test FAIR rating for P/E 70-100% of max"""
        max_pe = 30.0
        actual_pe = 25.0  # 83% of max
        rating = self.analyzer.rate_pe_valuation(actual_pe, max_pe)
        self.assertEqual(rating, "FAIR")

    def test_expensive_pe_below_120_percent(self):
        """Test EXPENSIVE rating for P/E 100-120% of max"""
        max_pe = 30.0
        actual_pe = 32.0  # 107% of max
        rating = self.analyzer.rate_pe_valuation(actual_pe, max_pe)
        self.assertEqual(rating, "EXPENSIVE")

    def test_overvalued_pe_above_120_percent(self):
        """Test OVERVALUED rating for P/E >120% of max"""
        max_pe = 30.0
        actual_pe = 40.0  # 133% of max
        rating = self.analyzer.rate_pe_valuation(actual_pe, max_pe)
        self.assertEqual(rating, "OVERVALUED")

    def test_negative_pe_returns_na(self):
        """Test negative P/E returns N/A"""
        rating = self.analyzer.rate_pe_valuation(-5.0, 30.0)
        self.assertIn("N/A", rating)

    def test_exact_boundary_70_percent(self):
        """Test exact boundary at 70%"""
        max_pe = 30.0
        actual_pe = 21.0  # Exactly 70%
        rating = self.analyzer.rate_pe_valuation(actual_pe, max_pe)
        self.assertEqual(rating, "FAIR")  # Should be at transition

    def test_exact_boundary_100_percent(self):
        """Test exact boundary at 100%"""
        max_pe = 30.0
        actual_pe = 30.0  # Exactly 100%
        rating = self.analyzer.rate_pe_valuation(actual_pe, max_pe)
        self.assertEqual(rating, "EXPENSIVE")  # Should be at transition


class TestPEGRating(unittest.TestCase):
    """Test PEG ratio rating logic"""

    def setUp(self):
        self.analyzer = ValuationAnalyzer()

    def test_cheap_peg_below_1(self):
        """Test CHEAP rating for PEG <1.0"""
        rating = self.analyzer.rate_peg_ratio(0.8)
        self.assertEqual(rating, "CHEAP")

    def test_fair_peg_1_to_2(self):
        """Test FAIR rating for PEG 1.0-2.0"""
        rating = self.analyzer.rate_peg_ratio(1.5)
        self.assertEqual(rating, "FAIR")

    def test_expensive_peg_above_2(self):
        """Test EXPENSIVE rating for PEG >2.0"""
        rating = self.analyzer.rate_peg_ratio(2.5)
        self.assertEqual(rating, "EXPENSIVE")

    def test_none_peg_returns_na(self):
        """Test None PEG returns N/A"""
        rating = self.analyzer.rate_peg_ratio(None)
        self.assertEqual(rating, "N/A")

    def test_negative_peg_returns_na(self):
        """Test negative PEG returns N/A"""
        rating = self.analyzer.rate_peg_ratio(-1.0)
        self.assertEqual(rating, "N/A")


class TestFCFYieldRating(unittest.TestCase):
    """Test FCF yield rating logic"""

    def setUp(self):
        self.analyzer = ValuationAnalyzer()

    def test_excellent_fcf_above_5_percent(self):
        """Test EXCELLENT rating for FCF yield >5%"""
        rating = self.analyzer.rate_fcf_yield(6.0)
        self.assertEqual(rating, "EXCELLENT")

    def test_good_fcf_3_to_5_percent(self):
        """Test GOOD rating for FCF yield 3-5%"""
        rating = self.analyzer.rate_fcf_yield(4.0)
        self.assertEqual(rating, "GOOD")

    def test_acceptable_fcf_1_to_3_percent(self):
        """Test ACCEPTABLE rating for FCF yield 1-3%"""
        rating = self.analyzer.rate_fcf_yield(2.0)
        self.assertEqual(rating, "ACCEPTABLE")

    def test_poor_fcf_below_1_percent(self):
        """Test POOR rating for FCF yield <1%"""
        rating = self.analyzer.rate_fcf_yield(0.5)
        self.assertEqual(rating, "POOR")

    def test_none_fcf_returns_na(self):
        """Test None FCF yield returns N/A"""
        rating = self.analyzer.rate_fcf_yield(None)
        self.assertEqual(rating, "N/A")


class TestOverallRatingLogic(unittest.TestCase):
    """Test overall rating combination logic"""

    def setUp(self):
        self.analyzer = ValuationAnalyzer()

    def test_overvalued_pe_triggers_overvalued_overall(self):
        """Test OVERVALUED P/E triggers OVERVALUED overall rating"""
        metrics = ValuationMetrics(
            ticker="TEST",
            price=100.0,
            market_cap=1e9,
            pe_trailing=50.0,  # Will be OVERVALUED at max_pe=30
            peg_ratio=1.0,  # FAIR
            fcf_yield=3.0,  # GOOD
            data_quality="COMPLETE"
        )

        rating = self.analyzer.assess_valuation("TEST", 85.0, metrics)
        self.assertEqual(rating.overall_rating, "OVERVALUED")
        self.assertEqual(rating.recommendation, "AVOID")

    def test_multiple_expensive_triggers_expensive_overall(self):
        """Test 2+ EXPENSIVE metrics trigger EXPENSIVE overall"""
        metrics = ValuationMetrics(
            ticker="TEST",
            price=100.0,
            market_cap=1e9,
            pe_trailing=32.0,  # EXPENSIVE (107% of max_pe=30)
            peg_ratio=2.5,  # EXPENSIVE
            fcf_yield=3.0,  # GOOD
            data_quality="COMPLETE"
        )

        rating = self.analyzer.assess_valuation("TEST", 85.0, metrics)
        self.assertEqual(rating.overall_rating, "EXPENSIVE")
        self.assertEqual(rating.recommendation, "HOLD")

    def test_multiple_cheap_triggers_cheap_overall(self):
        """Test 2+ CHEAP metrics trigger CHEAP overall"""
        metrics = ValuationMetrics(
            ticker="TEST",
            price=100.0,
            market_cap=1e9,
            pe_trailing=15.0,  # CHEAP (50% of max_pe=30)
            peg_ratio=0.8,  # CHEAP
            fcf_yield=6.0,  # EXCELLENT
            data_quality="COMPLETE"
        )

        rating = self.analyzer.assess_valuation("TEST", 85.0, metrics)
        self.assertEqual(rating.overall_rating, "CHEAP")
        self.assertEqual(rating.recommendation, "BUY")

    def test_mixed_ratings_trigger_fair_overall(self):
        """Test mixed ratings trigger FAIR overall"""
        metrics = ValuationMetrics(
            ticker="TEST",
            price=100.0,
            market_cap=1e9,
            pe_trailing=25.0,  # FAIR
            peg_ratio=1.5,  # FAIR
            fcf_yield=3.0,  # GOOD
            data_quality="COMPLETE"
        )

        rating = self.analyzer.assess_valuation("TEST", 85.0, metrics)
        self.assertEqual(rating.overall_rating, "FAIR")

    def test_fair_with_high_quality_triggers_buy(self):
        """Test FAIR + quality ≥80 triggers BUY"""
        metrics = ValuationMetrics(
            ticker="TEST",
            price=100.0,
            market_cap=1e9,
            pe_trailing=25.0,  # FAIR
            peg_ratio=1.5,  # FAIR
            fcf_yield=3.0,  # GOOD
            data_quality="COMPLETE"
        )

        rating = self.analyzer.assess_valuation("TEST", 85.0, metrics)
        self.assertEqual(rating.recommendation, "BUY")  # Quality 85 >= 80

    def test_fair_with_low_quality_triggers_hold(self):
        """Test FAIR + quality <80 triggers HOLD"""
        # Quality 75 = 7.5 on 10-scale = max_pe of 20x
        # For FAIR rating, need P/E 70-100% of max = 14-20x
        metrics = ValuationMetrics(
            ticker="TEST",
            price=100.0,
            market_cap=1e9,
            pe_trailing=18.0,  # FAIR (90% of max_pe=20)
            peg_ratio=1.5,  # FAIR
            fcf_yield=3.0,  # GOOD
            data_quality="COMPLETE"
        )

        rating = self.analyzer.assess_valuation("TEST", 75.0, metrics)
        self.assertEqual(rating.recommendation, "HOLD")  # Quality 75 < 80


class TestDataQualityAssessment(unittest.TestCase):
    """Test data quality assessment"""

    def setUp(self):
        self.analyzer = ValuationAnalyzer()

    def test_complete_data_quality(self):
        """Test COMPLETE data quality with 3+ metrics"""
        quality = self.analyzer._assess_data_quality(
            pe=20.0,
            peg=1.5,
            fcf_yield=3.0,
            revenue_growth=0.15
        )
        self.assertEqual(quality, "COMPLETE")

    def test_partial_data_quality(self):
        """Test PARTIAL data quality with 2 metrics"""
        quality = self.analyzer._assess_data_quality(
            pe=20.0,
            peg=None,
            fcf_yield=3.0,
            revenue_growth=None
        )
        self.assertEqual(quality, "PARTIAL")

    def test_insufficient_data_quality(self):
        """Test INSUFFICIENT data quality with <2 metrics"""
        quality = self.analyzer._assess_data_quality(
            pe=20.0,
            peg=None,
            fcf_yield=None,
            revenue_growth=None
        )
        self.assertEqual(quality, "INSUFFICIENT")

    def test_insufficient_data_returns_hold(self):
        """Test insufficient data returns HOLD recommendation"""
        metrics = ValuationMetrics(
            ticker="TEST",
            price=100.0,
            market_cap=1e9,
            data_quality="INSUFFICIENT"
        )

        rating = self.analyzer.assess_valuation("TEST", 85.0, metrics)
        self.assertEqual(rating.recommendation, "HOLD")
        self.assertIn("Insufficient", rating.reasoning)


class TestExportFunctionality(unittest.TestCase):
    """Test export to JSON and markdown"""

    def setUp(self):
        self.analyzer = ValuationAnalyzer()

    def test_export_json_creates_file(self):
        """Test JSON export creates file"""
        results = {
            'TEST': ValuationRating(
                ticker='TEST',
                quality_score=85.0,
                max_pe_allowed=30.0,
                actual_pe=25.0,
                pe_rating='FAIR',
                peg_rating='FAIR',
                fcf_rating='GOOD',
                overall_rating='FAIR',
                recommendation='BUY',
                reasoning='Test reasoning'
            )
        }

        json_path = self.analyzer.export_to_json(results, date_str='TEST')

        # Verify file exists
        self.assertTrue(os.path.exists(json_path))

        # Verify content
        with open(json_path, 'r') as f:
            data = json.load(f)

        self.assertIn('TEST', data)
        self.assertEqual(data['TEST']['recommendation'], 'BUY')
        self.assertEqual(data['TEST']['overall_rating'], 'FAIR')

        # Cleanup
        os.remove(json_path)

    def test_markdown_report_creates_file(self):
        """Test markdown report generation"""
        results = {
            'TEST': ValuationRating(
                ticker='TEST',
                quality_score=85.0,
                max_pe_allowed=30.0,
                actual_pe=25.0,
                pe_rating='FAIR',
                peg_rating='FAIR',
                fcf_rating='GOOD',
                overall_rating='FAIR',
                recommendation='BUY',
                reasoning='Test reasoning'
            )
        }

        md_path = self.analyzer.generate_markdown_report(results, date_str='TEST')

        # Verify file exists
        self.assertTrue(os.path.exists(md_path))

        # Verify content
        with open(md_path, 'r') as f:
            content = f.read()

        self.assertIn('VALUATION ANALYSIS REPORT', content)
        self.assertIn('TEST', content)
        self.assertIn('BUY', content)
        self.assertIn('FAIR', content)

        # Cleanup
        os.remove(md_path)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def setUp(self):
        self.analyzer = ValuationAnalyzer()

    def test_zero_pe_handled(self):
        """Test handling of zero P/E"""
        rating = self.analyzer.rate_pe_valuation(0.0, 30.0)
        self.assertIn("N/A", rating)

    def test_very_high_pe_overvalued(self):
        """Test very high P/E is OVERVALUED"""
        rating = self.analyzer.rate_pe_valuation(100.0, 30.0)
        self.assertEqual(rating, "OVERVALUED")

    def test_very_low_pe_cheap(self):
        """Test very low P/E is CHEAP"""
        rating = self.analyzer.rate_pe_valuation(5.0, 30.0)
        self.assertEqual(rating, "CHEAP")

    def test_quality_score_0_handled(self):
        """Test quality score of 0 is handled"""
        max_pe = self.analyzer.calculate_quality_adjusted_threshold(0.0)
        self.assertEqual(max_pe, 15.0)  # Should be <7 category

    def test_quality_score_100_handled(self):
        """Test quality score of 100 is handled"""
        max_pe = self.analyzer.calculate_quality_adjusted_threshold(100.0)
        self.assertEqual(max_pe, 40.0)  # Should be >9 category


class TestBatchAnalysis(unittest.TestCase):
    """Test batch portfolio analysis"""

    def setUp(self):
        self.analyzer = ValuationAnalyzer()

    def test_batch_analyze_multiple_tickers(self):
        """Test batch analysis processes multiple tickers"""
        tickers = ['TEST1', 'TEST2', 'TEST3']
        quality_scores = {'TEST1': 85.0, 'TEST2': 75.0, 'TEST3': 95.0}

        # Mock fetch to avoid actual API calls
        def mock_fetch(ticker):
            return ValuationMetrics(
                ticker=ticker,
                price=100.0,
                market_cap=1e9,
                pe_trailing=25.0,
                peg_ratio=1.5,
                fcf_yield=3.0,
                data_quality="COMPLETE"
            )

        self.analyzer.fetch_valuation_metrics = mock_fetch

        results = self.analyzer.batch_analyze_portfolio(tickers, quality_scores)

        self.assertEqual(len(results), 3)
        self.assertIn('TEST1', results)
        self.assertIn('TEST2', results)
        self.assertIn('TEST3', results)

    def test_default_quality_score_used(self):
        """Test default quality score of 70 used when not provided"""
        tickers = ['TEST']
        quality_scores = {}  # Empty

        def mock_fetch(ticker):
            return ValuationMetrics(
                ticker=ticker,
                price=100.0,
                market_cap=1e9,
                data_quality="INSUFFICIENT"
            )

        self.analyzer.fetch_valuation_metrics = mock_fetch

        results = self.analyzer.batch_analyze_portfolio(tickers, quality_scores)

        # Should use default quality of 70
        self.assertEqual(results['TEST'].quality_score, 70.0)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
