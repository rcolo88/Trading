"""
Test Suite for ThematicPromptBuilder

Comprehensive tests for thematic investment prompt generation including
all 6 theme types, token budget validation, compression, and edge cases.

Usage:
    python test_thematic_prompt_builder.py

Author: Portfolio Management System
Version: 1.0.0
"""

from thematic_prompt_builder import (
    ThematicPromptBuilder,
    ThematicScore,
    ModelType
)
import sys


def test_model_initialization():
    """Test model type initialization and token budgets."""
    print("\n📋 Test 1: Model Initialization")
    print("-" * 60)

    tests_passed = 0
    tests_total = 4

    # Test valid model types
    for model_type in ['7B', '13B', '70B']:
        try:
            builder = ThematicPromptBuilder(model_type=model_type)
            expected_tokens = {
                '7B': 800,
                '13B': 1200,
                '70B': 2000
            }[model_type]

            if builder.max_tokens == expected_tokens:
                print(f"  ✅ {model_type}: Token budget = {builder.max_tokens}")
                tests_passed += 1
            else:
                print(f"  ❌ {model_type}: Expected {expected_tokens}, got {builder.max_tokens}")

        except Exception as e:
            print(f"  ❌ {model_type}: Failed with error: {e}")

    # Test invalid model type
    try:
        builder = ThematicPromptBuilder(model_type='INVALID')
        print(f"  ❌ Invalid model type should raise ValueError")
    except ValueError as e:
        print(f"  ✅ Invalid model type correctly raises ValueError")
        tests_passed += 1

    print(f"\n  Result: {tests_passed}/{tests_total} tests passed")
    return tests_passed == tests_total


def test_ai_infrastructure_prompt():
    """Test AI infrastructure prompt generation."""
    print("\n🤖 Test 2: AI Infrastructure Prompt")
    print("-" * 60)

    builder = ThematicPromptBuilder(model_type='7B')

    company_data = {
        'ticker': 'NVDA',
        'name': 'NVIDIA Corporation',
        'business_description': 'GPU and AI accelerator manufacturer, leader in AI training and inference hardware',
        'revenue': 60.9e9,
        'revenue_growth': 1.265,  # 126.5% growth
        'gross_margin': 0.75
    }

    context = {
        'market_trends': 'AI infrastructure spending expected to reach $200B by 2027'
    }

    try:
        prompt = builder.ai_infrastructure_prompt(company_data, context)
        token_count = builder.estimate_token_count(prompt)

        # Validation checks
        checks = {
            'Contains company name': 'NVIDIA Corporation' in prompt,
            'Contains ticker': 'NVDA' in prompt,
            'Contains 5 dimensions': prompt.count('Score: [1-10]') == 5,
            'Contains output format': 'OVERALL SCORE' in prompt,
            'Within token budget': token_count <= 800,
            'Includes market context': 'AI infrastructure spending' in prompt,
            'Has classification': 'CLASSIFICATION:' in prompt,
            'Has investment stance': 'INVESTMENT STANCE:' in prompt
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, check_result in checks.items():
            status = "✅" if check_result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Token count: {token_count}/{builder.max_tokens}")
        print(f"  Result: {passed}/{total} checks passed")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_nuclear_renaissance_prompt():
    """Test nuclear renaissance prompt generation."""
    print("\n☢️  Test 3: Nuclear Renaissance Prompt")
    print("-" * 60)

    builder = ThematicPromptBuilder(model_type='7B')

    company_data = {
        'ticker': 'OKLO',
        'name': 'Oklo Inc',
        'business_description': 'Advanced fission power plant developer, Aurora powerhouse design',
        'revenue': 0.05e9
    }

    context = {
        'uranium_prices': 95.50
    }

    try:
        prompt = builder.nuclear_renaissance_prompt(company_data, context)
        token_count = builder.estimate_token_count(prompt)

        checks = {
            'Contains company name': 'Oklo Inc' in prompt,
            'Has technology readiness': 'TECHNOLOGY READINESS' in prompt,
            'Has regulatory progress': 'REGULATORY PROGRESS' in prompt,
            'Has partnerships': 'STRATEGIC PARTNERSHIPS' in prompt,
            'Has government support': 'GOVERNMENT SUPPORT' in prompt,
            'Has timeline': 'COMMERCIALIZATION TIMELINE' in prompt,
            'Within token budget': token_count <= 800,
            'Includes uranium context': 'Uranium spot price $95.50' in prompt
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, check_result in checks.items():
            status = "✅" if check_result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Token count: {token_count}/{builder.max_tokens}")
        print(f"  Result: {passed}/{total} checks passed")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_defense_modernization_prompt():
    """Test defense modernization prompt generation."""
    print("\n🛡️  Test 4: Defense Modernization Prompt")
    print("-" * 60)

    builder = ThematicPromptBuilder(model_type='13B')  # Test with 13B model

    company_data = {
        'ticker': 'PLTR',
        'name': 'Palantir Technologies',
        'business_description': 'Data analytics and AI platform for defense and intelligence',
        'backlog': 4.0e9,
        'revenue': 2.2e9,
        'operating_margin': 0.13
    }

    context = {
        'defense_budget': 886e9
    }

    try:
        prompt = builder.defense_modernization_prompt(company_data, context)
        token_count = builder.estimate_token_count(prompt)

        checks = {
            'Contains backlog': 'Contract Backlog: $4.00B' in prompt,
            'Has program stability': 'PROGRAM STABILITY' in prompt,
            'Has tech superiority': 'TECHNOLOGY SUPERIORITY' in prompt,
            'Has growth runway': 'GROWTH RUNWAY' in prompt,
            'Has financial strength': 'FINANCIAL STRENGTH' in prompt,
            'Has geopolitical tailwinds': 'GEOPOLITICAL TAILWINDS' in prompt,
            'Within token budget': token_count <= 1200,
            'Includes defense budget': 'DoD budget $886B' in prompt
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, check_result in checks.items():
            status = "✅" if check_result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Token count: {token_count}/{builder.max_tokens}")
        print(f"  Result: {passed}/{total} checks passed")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_climate_tech_prompt():
    """Test climate technology prompt generation."""
    print("\n🌍 Test 5: Climate Technology Prompt")
    print("-" * 60)

    builder = ThematicPromptBuilder(model_type='7B')

    company_data = {
        'ticker': 'ENPH',
        'name': 'Enphase Energy',
        'business_description': 'Microinverter systems for residential and commercial solar',
        'revenue': 2.3e9,
        'revenue_growth': 0.35
    }

    context = {
        'carbon_prices': 85.00
    }

    try:
        prompt = builder.climate_tech_prompt(company_data, context)
        token_count = builder.estimate_token_count(prompt)

        checks = {
            'Has technology maturity': 'TECHNOLOGY MATURITY' in prompt,
            'Has unit economics': 'UNIT ECONOMICS' in prompt,
            'Has policy support': 'POLICY SUPPORT' in prompt,
            'Has demand/scalability': 'DEMAND & SCALABILITY' in prompt,
            'Has carbon impact': 'CARBON IMPACT' in prompt,
            'Within token budget': token_count <= 800,
            'Includes carbon prices': 'Carbon price $85.00' in prompt
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, check_result in checks.items():
            status = "✅" if check_result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Token count: {token_count}/{builder.max_tokens}")
        print(f"  Result: {passed}/{total} checks passed")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_longevity_biotech_prompt():
    """Test longevity/biotech prompt generation."""
    print("\n💊 Test 6: Longevity/Biotech Prompt")
    print("-" * 60)

    builder = ThematicPromptBuilder(model_type='7B')

    company_data = {
        'ticker': 'ALNY',
        'name': 'Alnylam Pharmaceuticals',
        'business_description': 'RNAi therapeutics for genetic diseases',
        'pipeline': 'Phase 3: TTR amyloidosis, hemophilia; Phase 2: hypertension',
        'cash': 2.0e9,
        'burn_rate': 0.6e9
    }

    context = {
        'sector_funding': 25.5e9
    }

    try:
        prompt = builder.longevity_biotech_prompt(company_data, context)
        token_count = builder.estimate_token_count(prompt)

        checks = {
            'Contains pipeline': 'Phase 3: TTR amyloidosis' in prompt or 'Pipeline:' in prompt,
            'Has science quality': 'SCIENCE QUALITY' in prompt,
            'Has clinical progress': 'CLINICAL PROGRESS' in prompt,
            'Has commercial potential': 'COMMERCIAL POTENTIAL' in prompt,
            'Has IP position': 'IP POSITION' in prompt,
            'Has management/financing': 'MANAGEMENT & FINANCING' in prompt,
            'Within token budget': token_count <= 800,
            'Includes runway': 'Cash Runway: 40 months' in prompt
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, check_result in checks.items():
            status = "✅" if check_result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Token count: {token_count}/{builder.max_tokens}")
        print(f"  Result: {passed}/{total} checks passed")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_generic_thematic_prompt():
    """Test generic thematic prompt with custom dimensions."""
    print("\n🎯 Test 7: Generic Thematic Prompt")
    print("-" * 60)

    builder = ThematicPromptBuilder(model_type='7B')

    company_data = {
        'ticker': 'IONQ',
        'name': 'IonQ Inc',
        'business_description': 'Quantum computing systems using trapped ion technology',
        'revenue': 0.05e9
    }

    dimensions = [
        "Quantum Coherence Time",
        "Error Correction Progress",
        "Commercial Partnerships",
        "Competitive Positioning",
        "Capital Efficiency"
    ]

    context = {
        'market_context': 'Quantum computing market expected to reach $65B by 2030'
    }

    try:
        # Test with correct number of dimensions
        prompt = builder.generic_thematic_prompt(
            company_data,
            theme_name="Quantum Computing",
            dimensions=dimensions,
            context=context
        )
        token_count = builder.estimate_token_count(prompt)

        checks = {
            'Contains theme name': 'Quantum Computing' in prompt,
            'Contains company': 'IonQ Inc' in prompt,
            'Has all 5 dimensions': all(dim.upper() in prompt for dim in dimensions),
            'Within token budget': token_count <= 800,
            'Includes context': 'Quantum computing market' in prompt,
            'Has output format': 'OVERALL SCORE' in prompt
        }

        passed = sum(checks.values())
        total = len(checks)

        for check_name, check_result in checks.items():
            status = "✅" if check_result else "❌"
            print(f"  {status} {check_name}")

        print(f"\n  Token count: {token_count}/{builder.max_tokens}")

        # Test with wrong number of dimensions
        try:
            bad_dimensions = ["Dim1", "Dim2", "Dim3"]  # Only 3 dimensions
            builder.generic_thematic_prompt(
                company_data,
                theme_name="Test Theme",
                dimensions=bad_dimensions
            )
            print(f"  ❌ Should raise ValueError for wrong dimension count")
            passed -= 1
        except ValueError:
            print(f"  ✅ Correctly raises ValueError for wrong dimension count")

        print(f"\n  Result: {passed}/{total} checks passed")

        return passed == total

    except Exception as e:
        print(f"  ❌ Failed with error: {e}")
        return False


def test_utility_methods():
    """Test utility methods for token management."""
    print("\n🔧 Test 8: Utility Methods")
    print("-" * 60)

    builder = ThematicPromptBuilder(model_type='7B')

    tests_passed = 0
    tests_total = 5

    # Test token estimation
    test_text = "This is a test prompt for token estimation. " * 10
    estimated = builder.estimate_token_count(test_text)
    expected_range = (len(test_text) // 5, len(test_text) // 3)  # Rough range

    if expected_range[0] <= estimated <= expected_range[1]:
        print(f"  ✅ Token estimation: {estimated} tokens for {len(test_text)} chars (reasonable)")
        tests_passed += 1
    else:
        print(f"  ❌ Token estimation: {estimated} tokens seems off")

    # Test validation with valid prompt
    short_prompt = "Short prompt" * 20
    is_valid, count, max_tokens = builder.validate_prompt_length(short_prompt)

    if is_valid and count <= max_tokens:
        print(f"  ✅ Validation (valid): {count} <= {max_tokens}")
        tests_passed += 1
    else:
        print(f"  ❌ Validation (valid): {count} > {max_tokens}")

    # Test validation with over-budget prompt
    long_prompt = "Very long prompt to exceed token budget. " * 100
    try:
        is_valid, count, max_tokens = builder.validate_prompt_length(long_prompt)
        if not is_valid:
            print(f"  ❌ Should raise ValueError for excessive overage")
        else:
            # Might be valid if under 10% overage
            print(f"  ✅ Validation (long): {count} tokens (within 10% tolerance)")
            tests_passed += 1
    except ValueError as e:
        print(f"  ✅ Validation (long): Correctly raises ValueError for >10% overage")
        tests_passed += 1

    # Test compression
    test_text = "You are an investment analyst evaluating companies. " * 10
    compressed = builder.compress_prompt(test_text)
    savings = len(test_text) - len(compressed)

    if savings >= 0:  # Compression should not increase length
        print(f"  ✅ Compression: Saved {savings} chars ({savings/len(test_text)*100:.1f}%)")
        tests_passed += 1
    else:
        print(f"  ❌ Compression: Increased length by {-savings} chars")

    # Test text truncation
    long_text = "A" * 200
    truncated = builder._truncate_text(long_text, 50)

    if len(truncated) <= 50 and truncated.endswith("..."):
        print(f"  ✅ Text truncation: {len(long_text)} chars → {len(truncated)} chars")
        tests_passed += 1
    else:
        print(f"  ❌ Text truncation: Failed to truncate properly")

    print(f"\n  Result: {tests_passed}/{tests_total} tests passed")
    return tests_passed == tests_total


def test_compress_mode():
    """Test compression mode functionality."""
    print("\n📦 Test 9: Compression Mode")
    print("-" * 60)

    company_data = {
        'ticker': 'TEST',
        'name': 'Test Company',
        'business_description': 'Test business description for compression testing',
        'revenue': 1.0e9
    }

    # Generate without compression
    builder_normal = ThematicPromptBuilder(model_type='7B', compress_mode=False)
    prompt_normal = builder_normal.ai_infrastructure_prompt(company_data)
    tokens_normal = builder_normal.estimate_token_count(prompt_normal)

    # Generate with compression
    builder_compressed = ThematicPromptBuilder(model_type='7B', compress_mode=True)
    prompt_compressed = builder_compressed.ai_infrastructure_prompt(company_data)
    tokens_compressed = builder_compressed.estimate_token_count(prompt_compressed)

    savings = tokens_normal - tokens_compressed
    savings_pct = (savings / tokens_normal * 100) if tokens_normal > 0 else 0

    print(f"  Normal: {tokens_normal} tokens")
    print(f"  Compressed: {tokens_compressed} tokens")
    print(f"  Savings: {savings} tokens ({savings_pct:.1f}%)")

    if savings >= 0:
        print(f"  ✅ Compression reduces or maintains token count")
        return True
    else:
        print(f"  ❌ Compression increased token count")
        return False


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n⚠️  Test 10: Edge Cases")
    print("-" * 60)

    builder = ThematicPromptBuilder(model_type='7B')

    tests_passed = 0
    tests_total = 4

    # Test with minimal company data
    minimal_data = {'ticker': 'MIN'}
    try:
        prompt = builder.ai_infrastructure_prompt(minimal_data)
        if 'MIN' in prompt:
            print(f"  ✅ Handles minimal company data")
            tests_passed += 1
        else:
            print(f"  ❌ Minimal data handling failed")
    except Exception as e:
        print(f"  ❌ Minimal data raised error: {e}")

    # Test with no context
    try:
        prompt = builder.nuclear_renaissance_prompt(minimal_data, context=None)
        print(f"  ✅ Handles None context")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ None context raised error: {e}")

    # Test with empty context
    try:
        prompt = builder.climate_tech_prompt(minimal_data, context={})
        print(f"  ✅ Handles empty context dict")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Empty context raised error: {e}")

    # Test generic prompt with empty theme name
    try:
        prompt = builder.generic_thematic_prompt(
            minimal_data,
            theme_name="",
            dimensions=["D1", "D2", "D3", "D4", "D5"]
        )
        print(f"  ✅ Handles empty theme name")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Empty theme name raised error: {e}")

    print(f"\n  Result: {tests_passed}/{tests_total} tests passed")
    return tests_passed == tests_total


def run_all_tests():
    """Run complete test suite."""
    print("\n" + "=" * 70)
    print("THEMATIC PROMPT BUILDER - COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    test_functions = [
        test_model_initialization,
        test_ai_infrastructure_prompt,
        test_nuclear_renaissance_prompt,
        test_defense_modernization_prompt,
        test_climate_tech_prompt,
        test_longevity_biotech_prompt,
        test_generic_thematic_prompt,
        test_utility_methods,
        test_compress_mode,
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
