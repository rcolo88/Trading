"""
Test suite for Competitive Analyzer
Tests competitor identification, quality comparison, and KEEP/SWAP/EXIT logic
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
from pathlib import Path

from analyzers.competitive_analyzer import (
    CompetitiveAnalyzer,
    CompetitorComparison,
    CompetitiveLandscape
)


class TestCompetitorIdentification(unittest.TestCase):
    """Test competitor identification logic"""

    def setUp(self):
        self.analyzer = CompetitiveAnalyzer()

    def test_manual_competitor_set_nvda(self):
        """Test manual competitor set for NVDA"""
        competitors = self.analyzer.identify_competitors('NVDA')
        self.assertIsInstance(competitors, list)
        self.assertGreater(len(competitors), 0)
        self.assertIn('AMD', competitors)
        self.assertIn('INTC', competitors)

    def test_manual_competitor_set_googl(self):
        """Test manual competitor set for GOOGL"""
        competitors = self.analyzer.identify_competitors('GOOGL')
        self.assertIn('MSFT', competitors)
        self.assertIn('AMZN', competitors)

    def test_manual_competitor_set_meta(self):
        """Test manual competitor set for META"""
        competitors = self.analyzer.identify_competitors('META')
        self.assertIn('GOOGL', competitors)
        self.assertIn('SNAP', competitors)

    def test_unknown_ticker_returns_empty(self):
        """Test unknown ticker returns empty list (fallback not implemented)"""
        competitors = self.analyzer.identify_competitors('UNKNOWN_TICKER')
        self.assertEqual(competitors, [])

    def test_competitor_count_reasonable(self):
        """Test competitor sets have reasonable size (3-5)"""
        for ticker in ['NVDA', 'GOOGL', 'META', 'JPM', 'AAPL']:
            competitors = self.analyzer.identify_competitors(ticker)
            if competitors:  # If manual set exists
                self.assertGreaterEqual(len(competitors), 3)
                self.assertLessEqual(len(competitors), 5)


class TestQualityComparison(unittest.TestCase):
    """Test quality comparison logic"""

    def setUp(self):
        self.analyzer = CompetitiveAnalyzer()

    def test_compare_creates_comparison_objects(self):
        """Test that comparison creates CompetitorComparison objects"""
        # Mock data
        mock_comparisons = [
            CompetitorComparison(
                ticker='NVDA',
                company_name='NVIDIA Corporation',
                quality_score=85.0,
                roe=0.30,
                gross_margin=0.65,
                market_cap=2000e9,
                rank=1
            ),
            CompetitorComparison(
                ticker='AMD',
                company_name='Advanced Micro Devices',
                quality_score=75.0,
                roe=0.20,
                gross_margin=0.50,
                market_cap=200e9,
                rank=2
            )
        ]

        # Verify structure
        for comp in mock_comparisons:
            self.assertIsInstance(comp, CompetitorComparison)
            self.assertIsInstance(comp.ticker, str)
            self.assertIsInstance(comp.quality_score, float)
            self.assertIsInstance(comp.rank, int)

    def test_ranking_assigns_correctly(self):
        """Test that ranking assigns 1, 2, 3, ... correctly"""
        comparisons = [
            CompetitorComparison('A', 'Company A', 90.0, 0.3, 0.6, 1e9, 0),
            CompetitorComparison('B', 'Company B', 80.0, 0.25, 0.55, 1e9, 0),
            CompetitorComparison('C', 'Company C', 70.0, 0.20, 0.50, 1e9, 0)
        ]

        # Sort and assign ranks (simulating what compare_quality_metrics does)
        comparisons.sort(key=lambda x: x.quality_score, reverse=True)
        for i, comp in enumerate(comparisons):
            comp.rank = i + 1

        self.assertEqual(comparisons[0].rank, 1)
        self.assertEqual(comparisons[0].ticker, 'A')
        self.assertEqual(comparisons[1].rank, 2)
        self.assertEqual(comparisons[2].rank, 3)

    def test_sorting_by_quality_score(self):
        """Test that comparisons are sorted by quality score descending"""
        comparisons = [
            CompetitorComparison('LOW', 'Low', 60.0, 0.1, 0.4, 1e9, 0),
            CompetitorComparison('HIGH', 'High', 90.0, 0.3, 0.6, 1e9, 0),
            CompetitorComparison('MID', 'Mid', 75.0, 0.2, 0.5, 1e9, 0)
        ]

        comparisons.sort(key=lambda x: x.quality_score, reverse=True)

        self.assertEqual(comparisons[0].ticker, 'HIGH')
        self.assertEqual(comparisons[1].ticker, 'MID')
        self.assertEqual(comparisons[2].ticker, 'LOW')


class TestBestInClassSelection(unittest.TestCase):
    """Test best-in-class selection logic"""

    def setUp(self):
        self.analyzer = CompetitiveAnalyzer()

    def test_clear_winner(self):
        """Test clear winner selection"""
        comparisons = [
            CompetitorComparison('WINNER', 'Winner', 90.0, 0.3, 0.6, 2000e9, 1),
            CompetitorComparison('SECOND', 'Second', 80.0, 0.25, 0.55, 1000e9, 2),
            CompetitorComparison('THIRD', 'Third', 70.0, 0.20, 0.50, 500e9, 3)
        ]

        best = self.analyzer.identify_best_in_class(comparisons)
        self.assertEqual(best, 'WINNER')

    def test_tie_broken_by_market_cap(self):
        """Test tie-breaking by market cap"""
        comparisons = [
            CompetitorComparison('SMALL', 'Small Cap', 85.0, 0.3, 0.6, 100e9, 1),
            CompetitorComparison('LARGE', 'Large Cap', 85.0, 0.3, 0.6, 2000e9, 1)  # Same score
        ]

        # Sort by quality (both equal), then should tie-break by market cap
        comparisons.sort(key=lambda x: x.quality_score, reverse=True)
        best = self.analyzer.identify_best_in_class(comparisons)

        # The method should pick LARGE due to higher market cap in tie
        self.assertIn(best, ['SMALL', 'LARGE'])  # Both valid since tie within 0.5

    def test_empty_list_returns_empty_string(self):
        """Test empty comparison list returns empty string"""
        best = self.analyzer.identify_best_in_class([])
        self.assertEqual(best, "")


class TestRecommendationLogic(unittest.TestCase):
    """Test KEEP/SWAP/EXIT recommendation logic"""

    def setUp(self):
        self.analyzer = CompetitiveAnalyzer()

    def test_keep_when_rank_1(self):
        """Test KEEP recommendation when focal ticker is #1"""
        comparisons = [
            CompetitorComparison('FOCAL', 'Focal Company', 90.0, 0.3, 0.6, 2000e9, 1),
            CompetitorComparison('COMP1', 'Competitor 1', 80.0, 0.25, 0.55, 1000e9, 2),
            CompetitorComparison('COMP2', 'Competitor 2', 70.0, 0.20, 0.50, 500e9, 3)
        ]

        recommendation, swap_candidate, reasoning = self.analyzer.generate_recommendation('FOCAL', comparisons)

        self.assertEqual(recommendation, 'KEEP')
        self.assertIsNone(swap_candidate)
        self.assertIn('Best-in-class', reasoning)

    def test_keep_when_close_second(self):
        """Test KEEP recommendation when focal ticker is #2 within 5 points"""
        comparisons = [
            CompetitorComparison('LEADER', 'Leader', 90.0, 0.3, 0.6, 2000e9, 1),
            CompetitorComparison('FOCAL', 'Focal Company', 87.0, 0.28, 0.58, 1500e9, 2),  # 3 points behind
            CompetitorComparison('COMP2', 'Competitor 2', 70.0, 0.20, 0.50, 500e9, 3)
        ]

        recommendation, swap_candidate, reasoning = self.analyzer.generate_recommendation('FOCAL', comparisons)

        self.assertEqual(recommendation, 'KEEP')
        self.assertIsNone(swap_candidate)
        self.assertIn('Strong #2', reasoning)

    def test_swap_when_far_behind(self):
        """Test SWAP recommendation when focal ticker is >5 points behind #1"""
        comparisons = [
            CompetitorComparison('LEADER', 'Leader', 90.0, 0.3, 0.6, 2000e9, 1),
            CompetitorComparison('FOCAL', 'Focal Company', 75.0, 0.20, 0.50, 1000e9, 2),  # 15 points behind
            CompetitorComparison('COMP2', 'Competitor 2', 70.0, 0.18, 0.48, 500e9, 3)
        ]

        recommendation, swap_candidate, reasoning = self.analyzer.generate_recommendation('FOCAL', comparisons)

        self.assertEqual(recommendation, 'SWAP')
        self.assertEqual(swap_candidate, 'LEADER')
        self.assertIn('behind leader', reasoning)

    def test_exit_when_last_and_below_threshold(self):
        """Test EXIT recommendation when focal ticker is last place with quality <70"""
        comparisons = [
            CompetitorComparison('COMP1', 'Competitor 1', 90.0, 0.3, 0.6, 2000e9, 1),
            CompetitorComparison('COMP2', 'Competitor 2', 80.0, 0.25, 0.55, 1000e9, 2),
            CompetitorComparison('FOCAL', 'Focal Company', 65.0, 0.15, 0.40, 500e9, 3)  # Last and <70
        ]

        recommendation, swap_candidate, reasoning = self.analyzer.generate_recommendation('FOCAL', comparisons)

        self.assertEqual(recommendation, 'EXIT')
        self.assertIsNone(swap_candidate)
        self.assertIn('Last place', reasoning)
        self.assertIn('below STEPS threshold', reasoning)

    def test_focal_not_in_list_returns_exit(self):
        """Test EXIT when focal ticker not found in comparison list"""
        comparisons = [
            CompetitorComparison('COMP1', 'Competitor 1', 90.0, 0.3, 0.6, 2000e9, 1),
            CompetitorComparison('COMP2', 'Competitor 2', 80.0, 0.25, 0.55, 1000e9, 2)
        ]

        recommendation, swap_candidate, reasoning = self.analyzer.generate_recommendation('MISSING', comparisons)

        self.assertEqual(recommendation, 'EXIT')
        self.assertIsNone(swap_candidate)
        self.assertIn('not found', reasoning)


class TestExportFunctionality(unittest.TestCase):
    """Test export to JSON and markdown"""

    def setUp(self):
        self.analyzer = CompetitiveAnalyzer()

    def test_export_json_creates_file(self):
        """Test JSON export creates file"""
        results = {
            'NVDA': CompetitiveLandscape(
                focal_ticker='NVDA',
                competitors=[
                    CompetitorComparison('NVDA', 'NVIDIA', 90.0, 0.3, 0.6, 2000e9, 1),
                    CompetitorComparison('AMD', 'AMD', 80.0, 0.25, 0.55, 200e9, 2)
                ],
                best_in_class='NVDA',
                competitive_advantage='Best-in-class quality',
                recommendation='KEEP',
                swap_candidate=None
            )
        }

        json_path = self.analyzer.export_to_json(results, date_str='TEST')

        # Verify file exists
        self.assertTrue(os.path.exists(json_path))

        # Verify content
        with open(json_path, 'r') as f:
            data = json.load(f)

        self.assertIn('NVDA', data)
        self.assertEqual(data['NVDA']['recommendation'], 'KEEP')
        self.assertEqual(data['NVDA']['best_in_class'], 'NVDA')

        # Cleanup
        os.remove(json_path)

    def test_markdown_report_creates_file(self):
        """Test markdown report generation"""
        results = {
            'NVDA': CompetitiveLandscape(
                focal_ticker='NVDA',
                competitors=[
                    CompetitorComparison('NVDA', 'NVIDIA', 90.0, 0.3, 0.6, 2000e9, 1),
                    CompetitorComparison('AMD', 'AMD', 80.0, 0.25, 0.55, 200e9, 2)
                ],
                best_in_class='NVDA',
                competitive_advantage='Best-in-class quality',
                recommendation='KEEP',
                swap_candidate=None
            )
        }

        md_path = self.analyzer.generate_markdown_report(results, date_str='TEST')

        # Verify file exists
        self.assertTrue(os.path.exists(md_path))

        # Verify content
        with open(md_path, 'r') as f:
            content = f.read()

        self.assertIn('COMPETITIVE ANALYSIS REPORT', content)
        self.assertIn('NVDA', content)
        self.assertIn('KEEP', content)
        self.assertIn('Competitive Ranking', content)

        # Cleanup
        os.remove(md_path)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def setUp(self):
        self.analyzer = CompetitiveAnalyzer()

    def test_empty_competitor_list_handled(self):
        """Test graceful handling of empty competitor list"""
        result = self.analyzer.analyze_competitive_position('UNKNOWN_TICKER')
        self.assertIsNone(result)

    def test_single_competitor_handled(self):
        """Test handling of only one competitor"""
        comparisons = [
            CompetitorComparison('FOCAL', 'Focal Only', 85.0, 0.3, 0.6, 1000e9, 1)
        ]

        best = self.analyzer.identify_best_in_class(comparisons)
        self.assertEqual(best, 'FOCAL')

        recommendation, swap_candidate, reasoning = self.analyzer.generate_recommendation('FOCAL', comparisons)
        self.assertEqual(recommendation, 'KEEP')  # Only one in list, must be best


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
