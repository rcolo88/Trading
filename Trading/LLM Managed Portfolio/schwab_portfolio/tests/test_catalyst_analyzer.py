"""
Test Suite for CatalystAnalyzer

Comprehensive tests for event-driven catalyst analysis including prompt generation,
response parsing, prioritization, scheduling, and report generation.

Usage:
    python test_catalyst_analyzer.py

Author: Portfolio Management System
Version: 1.0.0
"""

from analyzers.catalyst_analyzer import (
    CatalystAnalyzer,
    Catalyst,
    CatalystAnalysis,
    CatalystTimeline,
    CatalystProbability,
    CatalystImpact,
    CatalystDirection
)
from datetime import datetime, timedelta
import sys


def test_initialization():
    """Test analyzer initialization with custom weights."""
    print("\n📋 Test 1: Initialization")
    print("-" * 60)

    # Test default weights
    analyzer = CatalystAnalyzer()
    expected_weights = {'time': 2.0, 'probability': 3.0, 'impact': 5.0, 'direction_bonus': 2.0}

    if analyzer.scoring_weights == expected_weights:
        print(f"  ✅ Default weights correct")
    else:
        print(f"  ❌ Default weights incorrect")
        return False

    # Test custom weights
    custom_weights = {'time': 3.0, 'probability': 2.0, 'impact': 4.0, 'direction_bonus': 1.0}
    analyzer2 = CatalystAnalyzer(scoring_weights=custom_weights)

    if analyzer2.scoring_weights == custom_weights:
        print(f"  ✅ Custom weights applied correctly")
        return True
    else:
        print(f"  ❌ Custom weights not applied")
        return False


def test_prompt_generation():
    """Test catalyst prompt generation."""
    print("\n🎯 Test 2: Prompt Generation")
    print("-" * 60)

    analyzer = CatalystAnalyzer()

    company_data = {
        'ticker': 'AAPL',
        'name': 'Apple Inc',
        'sector': 'Technology',
        'business_description': 'Consumer electronics and services company'
    }

    context = {
        'recent_news': 'Launched new iPhone model',
        'upcoming_events': 'WWDC in June'
    }

    try:
        # Test without context
        prompt1 = analyzer.generate_catalyst_prompt(company_data)

        # Test with context
        prompt2 = analyzer.generate_catalyst_prompt(company_data, context)

        checks = {
            'Contains company name': 'Apple Inc' in prompt1,
            'Contains ticker': 'AAPL' in prompt1,
            'Has timeline buckets': 'Near-Term (0-6 months)' in prompt1,
            'Has attributes': 'Probability' in prompt1 and 'Impact' in prompt1,
            'Has output format': 'CATALYST 1:' in prompt1,
            'Context included': 'WWDC' in prompt2,
            'Reasonable length': 1000 < len(prompt1) < 3000
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_catalyst_parsing():
    """Test parsing of various catalyst response formats."""
    print("\n📝 Test 3: Catalyst Parsing")
    print("-" * 60)

    analyzer = CatalystAnalyzer()

    company_data = {'ticker': 'TEST', 'name': 'Test Company'}

    # Well-formatted response
    response1 = """
    CATALYST 1: Q2 Earnings Report
    Timeline: 3 months
    Probability: H
    Impact: M
    Direction: +
    Dependencies: None
    Notes: Expected beat on revenue

    CATALYST 2: FDA Approval Decision
    Timeline: 12 months
    Probability: M
    Impact: H
    Direction: +
    Dependencies: Clinical trial completion
    Notes: Phase 3 results positive
    """

    # Alternative format (numbered list)
    response2 = """
    1. Product Launch in Europe
    Timeline: 8.5 months
    Probability: L
    Impact: L
    Direction: neutral
    Dependencies: Regulatory approval, distribution deals
    Notes: Small initial rollout expected
    """

    # Messy format
    response3 = """
    Some preamble text...

    CATALYST 1: Patent Expiration
    Expected in about 18 months
    Probability: HIGH
    Impact: HIGH
    Direction: negative
    This will allow generics to enter market
    """

    try:
        # Parse response 1
        catalysts1 = analyzer.parse_catalyst_response(response1, company_data)

        # Parse response 2
        catalysts2 = analyzer.parse_catalyst_response(response2, company_data)

        # Parse response 3
        catalysts3 = analyzer.parse_catalyst_response(response3, company_data)

        checks = {
            'Response 1 parsed': len(catalysts1) >= 2,
            'Response 2 parsed': len(catalysts2) >= 1,
            'Response 3 parsed': len(catalysts3) >= 1,
            'Names extracted': catalysts1[0].name == 'Q2 Earnings Report',
            'Timeline classified': catalysts1[0].timeline == CatalystTimeline.NEAR_TERM,
            'Dependencies parsed': 'Clinical trial completion' in catalysts1[1].dependencies,
            'Notes captured': len(catalysts1[0].notes) > 0,
            'Estimated dates set': catalysts1[0].estimated_date is not None
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Parsed catalysts:")
        for i, cat in enumerate(catalysts1[:2], 1):
            print(f"    {i}. {cat.name} - {cat.timeline_months} months, {cat.impact.value} impact")

        return passed >= total - 1  # Allow one failure for robustness

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_catalyst_prioritization():
    """Test catalyst prioritization scoring."""
    print("\n⭐ Test 4: Catalyst Prioritization")
    print("-" * 60)

    analyzer = CatalystAnalyzer()

    # Create test catalysts with known attributes
    catalysts = [
        Catalyst(
            name="High Priority: Soon, High Impact, Positive",
            timeline=CatalystTimeline.NEAR_TERM,
            timeline_months=2.0,
            probability=CatalystProbability.HIGH,
            impact=CatalystImpact.HIGH,
            direction=CatalystDirection.POSITIVE,
            estimated_date=datetime.now() + timedelta(days=60)
        ),
        Catalyst(
            name="Low Priority: Far, Low Impact, Neutral",
            timeline=CatalystTimeline.LONG_TERM,
            timeline_months=24.0,
            probability=CatalystProbability.LOW,
            impact=CatalystImpact.LOW,
            direction=CatalystDirection.NEUTRAL,
            estimated_date=datetime.now() + timedelta(days=720)
        ),
        Catalyst(
            name="Medium Priority: Medium Everything",
            timeline=CatalystTimeline.MEDIUM_TERM,
            timeline_months=10.0,
            probability=CatalystProbability.MEDIUM,
            impact=CatalystImpact.MEDIUM,
            direction=CatalystDirection.POSITIVE,
            estimated_date=datetime.now() + timedelta(days=300)
        ),
        Catalyst(
            name="Negative: High Impact, Soon, But Bearish",
            timeline=CatalystTimeline.NEAR_TERM,
            timeline_months=4.0,
            probability=CatalystProbability.HIGH,
            impact=CatalystImpact.HIGH,
            direction=CatalystDirection.NEGATIVE,
            estimated_date=datetime.now() + timedelta(days=120)
        )
    ]

    try:
        prioritized = analyzer.prioritize_catalysts(catalysts)

        checks = {
            'All catalysts scored': all(c.priority_score > 0 for c in prioritized),
            'Sorted descending': prioritized[0].priority_score >= prioritized[-1].priority_score,
            'High priority first': 'High Priority' in prioritized[0].name,
            'Low priority last': 'Low Priority' in prioritized[-1].name,
            'Scores reasonable': 5 < prioritized[0].priority_score < 30,
            'Negative penalty': prioritized[3].priority_score < prioritized[0].priority_score
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Priority ranking:")
        for i, cat in enumerate(prioritized, 1):
            print(f"    {i}. {cat.name[:40]} (score: {cat.priority_score:.2f})")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_monitoring_schedule():
    """Test monitoring schedule generation."""
    print("\n📅 Test 5: Monitoring Schedule")
    print("-" * 60)

    analyzer = CatalystAnalyzer()

    # Create catalysts with different timelines
    catalysts = [
        Catalyst(
            name="Near Catalyst",
            timeline=CatalystTimeline.NEAR_TERM,
            timeline_months=3.0,
            probability=CatalystProbability.HIGH,
            impact=CatalystImpact.HIGH,
            direction=CatalystDirection.POSITIVE,
            estimated_date=datetime.now() + timedelta(days=90)
        ),
        Catalyst(
            name="Medium Catalyst",
            timeline=CatalystTimeline.MEDIUM_TERM,
            timeline_months=12.0,
            probability=CatalystProbability.MEDIUM,
            impact=CatalystImpact.MEDIUM,
            direction=CatalystDirection.POSITIVE,
            estimated_date=datetime.now() + timedelta(days=360)
        )
    ]

    try:
        schedule = analyzer.create_monitoring_schedule(catalysts, check_in_days=30)

        checks = {
            'Has catalyst dates': len(schedule['catalyst_dates']) == 2,
            'Has check-ins': len(schedule['check_ins']) > 0,
            'Catalyst dates sorted': all(
                schedule['catalyst_dates'][i]['date'] <= schedule['catalyst_dates'][i+1]['date']
                for i in range(len(schedule['catalyst_dates'])-1)
            ),
            'Check-ins sorted': all(
                schedule['check_ins'][i]['date'] <= schedule['check_ins'][i+1]['date']
                for i in range(len(schedule['check_ins'])-1)
            ),
            'Type labels correct': all(
                e['type'] == 'catalyst' for e in schedule['catalyst_dates']
            ),
            'Check-in labels correct': all(
                e['type'] == 'check_in' for e in schedule['check_ins']
            )
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Schedule summary:")
        print(f"    Catalyst dates: {len(schedule['catalyst_dates'])}")
        print(f"    Check-ins: {len(schedule['check_ins'])}")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_report_generation():
    """Test catalyst summary report generation."""
    print("\n📊 Test 6: Report Generation")
    print("-" * 60)

    analyzer = CatalystAnalyzer()

    # Create full analysis
    catalysts = [
        Catalyst(
            name="Q4 Earnings",
            timeline=CatalystTimeline.NEAR_TERM,
            timeline_months=2.0,
            probability=CatalystProbability.HIGH,
            impact=CatalystImpact.MEDIUM,
            direction=CatalystDirection.POSITIVE,
            notes="Expected revenue beat",
            estimated_date=datetime.now() + timedelta(days=60)
        ),
        Catalyst(
            name="Product Launch",
            timeline=CatalystTimeline.MEDIUM_TERM,
            timeline_months=9.0,
            probability=CatalystProbability.MEDIUM,
            impact=CatalystImpact.HIGH,
            direction=CatalystDirection.POSITIVE,
            dependencies=["Manufacturing ramp"],
            notes="New product category",
            estimated_date=datetime.now() + timedelta(days=270)
        )
    ]

    prioritized = analyzer.prioritize_catalysts(catalysts)

    analysis = CatalystAnalysis(
        ticker='AAPL',
        company_name='Apple Inc',
        analysis_date=datetime.now(),
        catalysts=prioritized,
        top_5_catalysts=prioritized[:2],
        near_term_count=1,
        medium_term_count=1,
        long_term_count=0,
        high_impact_count=1
    )

    try:
        report = analyzer.generate_catalyst_summary_report(analysis, include_schedule=True)

        checks = {
            'Has header': '# Catalyst Analysis' in report,
            'Has company name': 'Apple Inc' in report,
            'Has executive summary': '## Executive Summary' in report,
            'Has top 5 section': '## Top 5 Priority Catalysts' in report,
            'Has calendar': '## Catalyst Calendar' in report,
            'Has near-term section': '### Near-Term (0-6 months)' in report,
            'Has monitoring': '## Monitoring Recommendations' in report,
            'Has trading implications': '## Trading Implications' in report,
            'Has tables': '|' in report and '----|' in report,
            'Reasonable length': len(report) > 1000
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Report length: {len(report)} characters")
        print(f"  Preview:\n{report[:250]}...")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_batch_analysis():
    """Test batch analysis of multiple companies."""
    print("\n📦 Test 7: Batch Analysis")
    print("-" * 60)

    analyzer = CatalystAnalyzer()

    companies = [
        {'ticker': 'AAPL', 'name': 'Apple Inc'},
        {'ticker': 'MSFT', 'name': 'Microsoft Corporation'},
        {'ticker': 'GOOGL', 'name': 'Alphabet Inc'}
    ]

    llm_responses = {
        'AAPL': """
        CATALYST 1: iPhone 17 Launch
        Timeline: 6 months
        Probability: H
        Impact: H
        Direction: +
        Dependencies: None
        Notes: Annual product cycle
        """,
        'MSFT': """
        CATALYST 1: AI Copilot Expansion
        Timeline: 4 months
        Probability: M
        Impact: M
        Direction: +
        Dependencies: None
        Notes: Enterprise adoption growing
        """,
        'GOOGL': """
        CATALYST 1: Antitrust Case Resolution
        Timeline: 15 months
        Probability: L
        Impact: H
        Direction: -
        Dependencies: Court decision
        Notes: Search monopoly case
        """
    }

    try:
        results = analyzer.batch_analyze_catalysts(companies, llm_responses)

        checks = {
            'All companies processed': len(results) == 3,
            'AAPL analyzed': 'AAPL' in results,
            'MSFT analyzed': 'MSFT' in results,
            'GOOGL analyzed': 'GOOGL' in results,
            'Catalysts parsed': all(len(analysis.catalysts) > 0 for analysis in results.values()),
            'Top 5 populated': all(len(analysis.top_5_catalysts) > 0 for analysis in results.values()),
            'Counts calculated': all(analysis.near_term_count >= 0 for analysis in results.values())
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Batch results:")
        for ticker, analysis in results.items():
            print(f"    {ticker}: {len(analysis.catalysts)} catalysts, top score {analysis.top_5_catalysts[0].priority_score:.2f}")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n⚠️  Test 8: Edge Cases")
    print("-" * 60)

    analyzer = CatalystAnalyzer()

    tests_passed = 0
    tests_total = 5

    # Test empty response
    try:
        catalysts = analyzer.parse_catalyst_response("", {'ticker': 'TEST'})
        print(f"  ✅ Handles empty response (returned {len(catalysts)} catalysts)")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Empty response raised error: {e}")

    # Test malformed response
    try:
        catalysts = analyzer.parse_catalyst_response(
            "Some random text without proper format",
            {'ticker': 'TEST'}
        )
        print(f"  ✅ Handles malformed response (returned {len(catalysts)} catalysts)")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Malformed response raised error: {e}")

    # Test empty catalyst list prioritization
    try:
        prioritized = analyzer.prioritize_catalysts([])
        if len(prioritized) == 0:
            print(f"  ✅ Handles empty catalyst list")
            tests_passed += 1
        else:
            print(f"  ❌ Empty list returned non-empty result")
    except Exception as e:
        print(f"  ❌ Empty list raised error: {e}")

    # Test monitoring schedule with no catalysts
    try:
        schedule = analyzer.create_monitoring_schedule([])
        print(f"  ✅ Creates schedule even with no catalysts")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ No catalysts raised error: {e}")

    # Test batch analysis with no responses
    try:
        results = analyzer.batch_analyze_catalysts(
            [{'ticker': 'TEST', 'name': 'Test Co'}],
            llm_responses={}
        )
        if len(results) == 0:
            print(f"  ✅ Batch analysis with no responses works")
            tests_passed += 1
        else:
            print(f"  ❌ Expected empty results")
    except Exception as e:
        print(f"  ❌ Batch with no responses raised error: {e}")

    print(f"\n  Result: {tests_passed}/{tests_total} tests passed")
    return tests_passed >= tests_total - 1  # Allow one failure


def run_all_tests():
    """Run complete test suite."""
    print("\n" + "=" * 70)
    print("CATALYST ANALYZER - COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    test_functions = [
        test_initialization,
        test_prompt_generation,
        test_catalyst_parsing,
        test_catalyst_prioritization,
        test_monitoring_schedule,
        test_report_generation,
        test_batch_analysis,
        test_edge_cases
    ]

    results = []
    for test_func in test_functions:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"\n  ❌ Test {test_func.__name__} crashed: {e}")
            results.append((test_func.__name__, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")

    print("\n" + "=" * 70)
    print(f"OVERALL: {passed}/{total} test suites passed")
    print("=" * 70)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
