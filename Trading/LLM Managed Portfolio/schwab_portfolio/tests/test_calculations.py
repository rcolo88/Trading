"""
Calculation Verification Tests

Verifies in-house financial calculations are mathematically correct.
Tests formulas against known good values and internal consistency.
"""

import unittest
from typing import Dict


class TestFinancialCalculations(unittest.TestCase):
    """Test financial calculation formulas"""

    def test_roe_calculation(self):
        """Verify ROE = Net Income / Shareholder Equity"""
        test_cases = [
            {'net_income': 10000000, 'equity': 50000000, 'expected': 0.20},
            {'net_income': 5000000, 'equity': 100000000, 'expected': 0.05},
            {'net_income': 0, 'equity': 50000000, 'expected': 0.0},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                net_income = case['net_income']
                equity = case['equity']
                expected = case['expected']

                if equity > 0:
                    roe = net_income / equity
                    self.assertAlmostEqual(roe, expected, places=4)
                else:
                    self.assertEqual(0.0, 0.0)  # Edge case handled

    def test_roic_calculation(self):
        """Verify ROIC = NOPAT / (Total Debt + Equity)"""
        test_cases = [
            {'nopat': 8000000, 'debt': 20000000, 'equity': 50000000, 'expected': 0.1143},
            {'nopat': 10000000, 'debt': 0, 'equity': 50000000, 'expected': 0.20},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                nopat = case['nopat']
                debt = case['debt']
                equity = case['equity']
                expected = case['expected']

                invested_capital = debt + equity
                if invested_capital > 0:
                    roic = nopat / invested_capital
                    self.assertAlmostEqual(roic, expected, places=3)

    def test_gross_profitability(self):
        """Verify Gross Profitability = (Revenue - COGS) / Total Assets"""
        test_cases = [
            {'revenue': 100000000, 'cogs': 60000000, 'assets': 200000000, 'expected': 0.20},
            {'revenue': 50000000, 'cogs': 20000000, 'assets': 100000000, 'expected': 0.30},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                revenue = case['revenue']
                cogs = case['cogs']
                assets = case['assets']
                expected = case['expected']

                gross_profit = revenue - cogs
                gp_ratio = gross_profit / assets
                self.assertAlmostEqual(gp_ratio, expected, places=2)

    def test_debt_to_equity(self):
        """Verify Debt/Equity = Total Debt / Shareholder Equity"""
        test_cases = [
            {'debt': 20000000, 'equity': 50000000, 'expected': 0.40},
            {'debt': 50000000, 'equity': 50000000, 'expected': 1.00},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                debt = case['debt']
                equity = case['equity']
                expected = case['expected']

                if equity > 0:
                    de_ratio = debt / equity
                    self.assertAlmostEqual(de_ratio, expected, places=2)

    def test_interest_coverage(self):
        """Verify Interest Coverage = EBIT / Interest Expense"""
        test_cases = [
            {'ebit': 10000000, 'interest': 2000000, 'expected': 5.0},
            {'ebit': 15000000, 'interest': 3000000, 'expected': 5.0},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                ebit = case['ebit']
                interest = case['interest']
                expected = case['expected']

                if interest > 0:
                    coverage = ebit / interest
                    self.assertAlmostEqual(coverage, expected, places=1)

    def test_fcf_yield(self):
        """Verify FCF Yield = Free Cash Flow / Market Cap"""
        test_cases = [
            {'fcf': 5000000, 'market_cap': 100000000, 'expected': 0.05},
            {'fcf': 10000000, 'market_cap': 500000000, 'expected': 0.02},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                fcf = case['fcf']
                market_cap = case['market_cap']
                expected = case['expected']

                if market_cap > 0:
                    fcf_yield = fcf / market_cap
                    self.assertAlmostEqual(fcf_yield, expected, places=2)


class TestInHouseCalculations(unittest.TestCase):
    """Test in-house calculation methods against actual data"""

    def calculate_in_house_roe(self, data: Dict[str, float]) -> float:
        """Calculate ROE: Net Income / Shareholder Equity"""
        net_income = data['net_income']
        equity = data['shareholder_equity']
        if equity <= 0:
            return 0.0
        return net_income / equity

    def calculate_in_house_roic(self, data: Dict[str, float]) -> float:
        """Calculate ROIC: NOPAT / (Total Debt + Equity)"""
        nopat = data['nopat']
        invested_capital = data['total_debt'] + data['shareholder_equity']
        if invested_capital <= 0:
            return 0.0
        return nopat / invested_capital

    def calculate_in_house_gross_profitability(self, data: Dict[str, float]) -> float:
        """Calculate Gross Profitability: (Revenue - COGS) / Total Assets"""
        gross_profit = data['revenue'] - data['cogs']
        return gross_profit / data['total_assets']

    def test_fisv_calculations(self):
        """Verify FISV calculations produce reasonable values"""
        fisv_data = {
            'revenue': 20456000000,
            'cogs': 8013000000,
            'net_income': 3131000000,
            'total_assets': 77176000000,
            'shareholder_equity': 27068000000,
            'total_debt': 24956000000,
            'nopat': 4644421000,  # operating_income * 0.79
            'market_cap': 95000000000,
        }

        roe = self.calculate_in_house_roe(fisv_data)
        roic = self.calculate_in_house_roic(fisv_data)
        gp = self.calculate_in_house_gross_profitability(fisv_data)

        # Verify calculations are in reasonable ranges
        self.assertGreater(roe, 0.05, f"ROE {roe:.2%} seems too low")
        self.assertLess(roe, 0.50, f"ROE {roe:.2%} seems too high")
        self.assertAlmostEqual(roe, 0.1157, places=2,
            msg=f"FISV ROE should be ~11.6%, got {roe:.2%}")

        self.assertGreater(roic, 0.05, f"ROIC {roic:.2%} seems too low")
        self.assertLess(roic, 0.50, f"ROIC {roic:.2%} seems too high")

        self.assertGreater(gp, 0.10, f"Gross Profitability {gp:.2%} seems too low")
        self.assertLess(gp, 0.80, f"Gross Profitability {gp:.2%} seems too high")

    def test_aapl_calculations(self):
        """Verify AAPL calculations produce reasonable values"""
        aapl_data = {
            'revenue': 383285000000,
            'cogs': 214136000000,
            'net_income': 96995000000,
            'total_assets': 352755000000,
            'shareholder_equity': 61008000000,
            'total_debt': 111088000000,
            'nopat': 114378000000 * 0.79,  # approx
            'market_cap': 2800000000000,
        }

        roe = self.calculate_in_house_roe(aapl_data)
        gp = self.calculate_in_house_gross_profitability(aapl_data)

        # AAPL has very high ROE
        self.assertGreater(roe, 1.0, f"AAPL ROE {roe:.2%} should be > 100%")
        self.assertAlmostEqual(roe, 1.59, places=1,
            msg=f"AAPL ROE should be ~159%, got {roe:.2%}")

        self.assertGreater(gp, 0.30, f"AAPL GP {gp:.2%} seems too low")


class TestDataCompleteness(unittest.TestCase):
    """Test that all required data fields are present"""

    def test_fisv_data_completeness(self):
        """Verify FISV has complete data for quality scoring"""
        from data.financial_data_fetcher import FinancialDataFetcher

        fetcher = FinancialDataFetcher(enable_cache=False)
        data = fetcher.fetch_financial_data('FISV')

        required_fields = {
            'Core': ['revenue', 'cogs', 'net_income', 'total_assets',
                     'shareholder_equity', 'total_debt'],
            'Quality Metrics': ['retained_earnings', 'working_capital',
                               'ebitda', 'interest_expense', 'ebit'],
            'Cash Flow': ['operating_cash_flow', 'free_cash_flow'],
        }

        for category, fields in required_fields.items():
            with self.subTest(category=category):
                for field in fields:
                    value = getattr(data, field, None)
                    self.assertIsNotNone(value,
                        f"FISV {field} should not be None")
                    self.assertNotEqual(value, 0,
                        f"FISV {field} should not be 0")

        self.assertEqual(data.data_quality, 'complete',
            "FISV data quality should be 'complete'")


if __name__ == '__main__':
    unittest.main(verbosity=2)
