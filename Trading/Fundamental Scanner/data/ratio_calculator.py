"""
Financial Ratio Calculator Module

Calculates financial ratios from raw SimFin financial statements.
Based on academic research and industry best practices.

Key Features:
- ROE, ROIC, and profitability ratios
- Safety metrics (Altman Z-Score, debt ratios)
- Growth quality calculations
- Earnings quality metrics
- Margin analysis
- Source tagging for comparison with FMP
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)


@dataclass
class CalculatedRatios:
    """Container for calculated financial ratios with source tagging"""
    
    # Profitability Ratios
    roe: Optional[float] = None  # Return on Equity
    roic: Optional[float] = None  # Return on Invested Capital
    gross_margin: Optional[float] = None  # Gross Profit Margin
    operating_margin: Optional[float] = None  # Operating Profit Margin
    net_margin: Optional[float] = None  # Net Profit Margin
    gross_profitability: Optional[float] = None  # Gross Profit / Total Assets
    
    # Safety Ratios
    altman_z_score: Optional[float] = None  # Bankruptcy prediction
    debt_to_equity: Optional[float] = None  # Debt/Equity ratio
    debt_to_ebitda: Optional[float] = None  # Debt/EBITDA ratio
    interest_coverage: Optional[float] = None  # Interest Coverage ratio
    current_ratio: Optional[float] = None  # Current Assets / Current Liabilities
    
    # Growth Quality
    revenue_growth: Optional[float] = None  # Revenue growth rate
    asset_growth: Optional[float] = None  # Asset growth rate (inverse scoring)
    earnings_growth: Optional[float] = None  # Earnings growth rate
    
    # Earnings Quality
    accrual_ratio: Optional[float] = None  # (Net Income - Operating CF) / Total Assets
    cash_conversion: Optional[float] = None  # Operating CF / Net Income
    fcf_conversion: Optional[float] = None  # Free Cash Flow / Net Income
    
    # Additional Metrics
    asset_turnover: Optional[float] = None  # Revenue / Total Assets
    equity_multiplier: Optional[float] = None  # Total Assets / Shareholder Equity
    
    # Metadata
    calculation_source: str = "SimFin"  # Source of raw data
    calculation_time: Optional[str] = None
    data_quality: str = "complete"  # complete, partial, insufficient
    missing_inputs: List[str] = None  # List of missing required inputs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with source tagging"""
        result = {}
        for field, value in self.__dict__.items():
            if field == 'missing_inputs' and value:
                result[f"simfin_{field}"] = value
            elif value is not None:
                result[f"simfin_{field}"] = value
        return result


class FinancialRatioCalculator:
    """
    Calculate financial ratios from raw SimFin financial statements.
    
    Based on academic research and industry best practices:
    - ROE calculation: Net Income / Shareholder Equity
    - ROIC calculation: NOPAT / Invested Capital
    - Altman Z-Score: Original 1968 model for manufacturing companies
    - Piotroski F-Score: 9-point financial health score
    """
    
    # Constants for calculations
    CORPORATE_TAX_RATE = 0.21  # 21% federal corporate tax rate (2018+)
    
    def __init__(self):
        """Initialize ratio calculator"""
        logger.info("FinancialRatioCalculator initialized")
    
    def calculate_profitability_ratios(
        self,
        revenue: Optional[float],
        cogs: Optional[float],
        operating_income: Optional[float],
        net_income: Optional[float],
        total_assets: Optional[float],
        shareholder_equity: Optional[float],
        total_debt: Optional[float] = None
    ) -> Dict[str, Optional[float]]:
        """
        Calculate profitability ratios
        
        Args:
            revenue: Total revenue
            cogs: Cost of goods sold
            operating_income: Operating income (EBIT)
            net_income: Net income
            total_assets: Total assets
            shareholder_equity: Shareholder equity
            total_debt: Total debt (for ROIC calculation)
            
        Returns:
            Dict of profitability ratios
        """
        ratios = {}
        
        # ROE = Net Income / Shareholder Equity
        if net_income is not None and shareholder_equity is not None and shareholder_equity != 0:
            ratios['roe'] = net_income / shareholder_equity
        else:
            ratios['roe'] = None
            logger.debug("ROE calculation failed: missing net_income or shareholder_equity")
        
        # Gross Margin = (Revenue - COGS) / Revenue
        if revenue is not None and cogs is not None and revenue != 0:
            ratios['gross_margin'] = (revenue - cogs) / revenue
        else:
            ratios['gross_margin'] = None
            logger.debug("Gross margin calculation failed: missing revenue or cogs")
        
        # Operating Margin = Operating Income / Revenue
        if operating_income is not None and revenue is not None and revenue != 0:
            ratios['operating_margin'] = operating_income / revenue
        else:
            ratios['operating_margin'] = None
            logger.debug("Operating margin calculation failed: missing operating_income or revenue")
        
        # Net Margin = Net Income / Revenue
        if net_income is not None and revenue is not None and revenue != 0:
            ratios['net_margin'] = net_income / revenue
        else:
            ratios['net_margin'] = None
            logger.debug("Net margin calculation failed: missing net_income or revenue")
        
        # Gross Profitability = Gross Profit / Total Assets
        if revenue is not None and cogs is not None and total_assets is not None and total_assets != 0:
            gross_profit = revenue - cogs
            ratios['gross_profitability'] = gross_profit / total_assets
        else:
            ratios['gross_profitability'] = None
            logger.debug("Gross profitability calculation failed: missing inputs")
        
        # Asset Turnover = Revenue / Total Assets
        if revenue is not None and total_assets is not None and total_assets != 0:
            ratios['asset_turnover'] = revenue / total_assets
        else:
            ratios['asset_turnover'] = None
        
        # Equity Multiplier = Total Assets / Shareholder Equity
        if total_assets is not None and shareholder_equity is not None and shareholder_equity != 0:
            ratios['equity_multiplier'] = total_assets / shareholder_equity
        else:
            ratios['equity_multiplier'] = None
        
        return ratios
    
    def calculate_roic(
        self,
        operating_income: Optional[float],
        total_assets: Optional[float],
        shareholder_equity: Optional[float],
        total_debt: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate Return on Invested Capital (ROIC)
        
        ROIC = NOPAT / Invested Capital
        NOPAT = Operating Income * (1 - Tax Rate)
        Invested Capital = Shareholder Equity + Total Debt
        
        Args:
            operating_income: Operating income (EBIT)
            total_assets: Total assets
            shareholder_equity: Shareholder equity
            total_debt: Total debt
            
        Returns:
            ROIC as decimal or None if calculation failed
        """
        if operating_income is None:
            logger.debug("ROIC calculation failed: missing operating_income")
            return None
        
        # Calculate NOPAT (Net Operating Profit After Tax)
        nopat = operating_income * (1 - self.CORPORATE_TAX_RATE)
        
        # Calculate Invested Capital
        if total_debt is not None and shareholder_equity is not None:
            invested_capital = shareholder_equity + total_debt
        elif total_assets is not None and shareholder_equity is not None:
            # Alternative: Invested Capital = Total Assets - Current Liabilities
            # Use shareholder equity as approximation if current liabilities not available
            invested_capital = total_assets
        else:
            logger.debug("ROIC calculation failed: missing invested capital components")
            return None
        
        if invested_capital == 0:
            logger.debug("ROIC calculation failed: invested capital is zero")
            return None
        
        roic = nopat / invested_capital
        return roic
    
    def calculate_safety_ratios(
        self,
        total_assets: Optional[float],
        shareholder_equity: Optional[float],
        total_debt: Optional[float],
        retained_earnings: Optional[float],
        working_capital: Optional[float],
        ebit: Optional[float],
        ebitda: Optional[float],
        interest_expense: Optional[float],
        current_assets: Optional[float] = None,
        current_liabilities: Optional[float] = None,
        revenue: Optional[float] = None
    ) -> Dict[str, Optional[float]]:
        """
        Calculate safety ratios including Altman Z-Score
        
        Args:
            total_assets: Total assets
            shareholder_equity: Shareholder equity
            total_debt: Total debt
            retained_earnings: Retained earnings
            working_capital: Working capital (Current Assets - Current Liabilities)
            ebit: Earnings before interest and taxes
            ebitda: EBITDA
            interest_expense: Interest expense
            current_assets: Current assets (for current ratio)
            current_liabilities: Current liabilities (for current ratio)
            revenue: Revenue (for Altman Z-Score sales component)
            
        Returns:
            Dict of safety ratios
        """
        ratios = {}
        
        # Altman Z-Score (1968 original model for manufacturing companies)
        # Z = 1.2X1 + 1.4X2 + 3.3X3 + 0.6X4 + 1.0X5
        # X1 = Working Capital / Total Assets
        # X2 = Retained Earnings / Total Assets
        # X3 = EBIT / Total Assets
        # X4 = Market Value Equity / Book Value Liabilities (use Shareholder Equity / Total Debt as proxy)
        # X5 = Sales / Total Assets
        
        if (total_assets is not None and total_assets != 0 and
            working_capital is not None and retained_earnings is not None and
            ebit is not None and revenue is not None):
            
            x1 = working_capital / total_assets
            x2 = retained_earnings / total_assets
            x3 = ebit / total_assets
            x5 = revenue / total_assets
            
            # X4: Use Shareholder Equity / Total Debt as proxy for market value ratio
            if total_debt is not None and total_debt != 0:
                x4 = shareholder_equity / total_debt
            else:
                x4 = 0  # Conservative if no debt data
            
            z_score = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
            ratios['altman_z_score'] = z_score
            
        else:
            ratios['altman_z_score'] = None
            logger.debug("Altman Z-Score calculation failed: missing inputs")
        
        # Debt to Equity = Total Debt / Shareholder Equity
        if total_debt is not None and shareholder_equity is not None and shareholder_equity != 0:
            ratios['debt_to_equity'] = total_debt / shareholder_equity
        else:
            ratios['debt_to_equity'] = None
        
        # Debt to EBITDA = Total Debt / EBITDA
        if total_debt is not None and ebitda is not None and ebitda != 0:
            ratios['debt_to_ebitda'] = total_debt / ebitda
        else:
            ratios['debt_to_ebitda'] = None
        
        # Interest Coverage = EBIT / Interest Expense
        if ebit is not None and interest_expense is not None and interest_expense != 0:
            ratios['interest_coverage'] = ebit / abs(interest_expense)  # Use abs for negative interest
        else:
            ratios['interest_coverage'] = None
        
        # Current Ratio = Current Assets / Current Liabilities
        if current_assets is not None and current_liabilities is not None and current_liabilities != 0:
            ratios['current_ratio'] = current_assets / current_liabilities
        else:
            ratios['current_ratio'] = None
        
        return ratios
    
    def calculate_earnings_quality(
        self,
        net_income: Optional[float],
        operating_cash_flow: Optional[float],
        free_cash_flow: Optional[float],
        total_assets: Optional[float]
    ) -> Dict[str, Optional[float]]:
        """
        Calculate earnings quality ratios
        
        Args:
            net_income: Net income
            operating_cash_flow: Operating cash flow
            free_cash_flow: Free cash flow
            total_assets: Total assets
            
        Returns:
            Dict of earnings quality ratios
        """
        ratios = {}
        
        # Accrual Ratio = (Net Income - Operating CF) / Total Assets
        if (net_income is not None and operating_cash_flow is not None and 
            total_assets is not None and total_assets != 0):
            accruals = net_income - operating_cash_flow
            ratios['accrual_ratio'] = accruals / total_assets
        else:
            ratios['accrual_ratio'] = None
        
        # Cash Conversion = Operating CF / Net Income
        if operating_cash_flow is not None and net_income is not None and net_income != 0:
            ratios['cash_conversion'] = operating_cash_flow / net_income
        else:
            ratios['cash_conversion'] = None
        
        # FCF Conversion = Free Cash Flow / Net Income
        if free_cash_flow is not None and net_income is not None and net_income != 0:
            ratios['fcf_conversion'] = free_cash_flow / net_income
        else:
            ratios['fcf_conversion'] = None
        
        return ratios
    
    def calculate_growth_rates(
        self,
        historical_values: List[Optional[float]]
    ) -> Optional[float]:
        """
        Calculate compound annual growth rate (CAGR) from historical values
        
        Args:
            historical_values: List of historical values (oldest to newest)
            
        Returns:
            CAGR as decimal or None if calculation failed
        """
        if not historical_values or len(historical_values) < 2:
            return None
        
        # Filter out None values
        valid_values = [v for v in historical_values if v is not None and v > 0]
        
        if len(valid_values) < 2:
            return None
        
        try:
            # Calculate CAGR: (Ending/Beginning)^(1/years) - 1
            beginning = valid_values[0]
            ending = valid_values[-1]
            years = len(valid_values) - 1
            
            if beginning <= 0:
                return None
            
            cagr = (ending / beginning) ** (1 / years) - 1
            return cagr
            
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
    
    def calculate_all_ratios(
        self,
        revenue: Optional[float],
        cogs: Optional[float],
        operating_income: Optional[float],
        net_income: Optional[float],
        total_assets: Optional[float],
        shareholder_equity: Optional[float],
        total_debt: Optional[float] = None,
        retained_earnings: Optional[float] = None,
        working_capital: Optional[float] = None,
        ebit: Optional[float] = None,
        ebitda: Optional[float] = None,
        interest_expense: Optional[float] = None,
        operating_cash_flow: Optional[float] = None,
        free_cash_flow: Optional[float] = None,
        current_assets: Optional[float] = None,
        current_liabilities: Optional[float] = None,
        historical_revenue: List[Optional[float]] = None,
        historical_assets: List[Optional[float]] = None,
        historical_earnings: List[Optional[float]] = None
    ) -> CalculatedRatios:
        """
        Calculate all financial ratios from SimFin raw data
        
        Args:
            All financial statement items as optional floats
            Historical data lists for growth calculations
            
        Returns:
            CalculatedRatios object with all calculated ratios
        """
        from datetime import datetime
        
        ratios = CalculatedRatios()
        ratios.calculation_time = datetime.now().isoformat()
        
        # Track missing inputs for data quality assessment
        missing_inputs = []
        
        # Profitability Ratios
        profitability = self.calculate_profitability_ratios(
            revenue, cogs, operating_income, net_income,
            total_assets, shareholder_equity, total_debt
        )
        ratios.roe = profitability.get('roe')
        ratios.gross_margin = profitability.get('gross_margin')
        ratios.operating_margin = profitability.get('operating_margin')
        ratios.net_margin = profitability.get('net_margin')
        ratios.gross_profitability = profitability.get('gross_profitability')
        ratios.asset_turnover = profitability.get('asset_turnover')
        ratios.equity_multiplier = profitability.get('equity_multiplier')
        
        # ROIC
        ratios.roic = self.calculate_roic(
            operating_income, total_assets, shareholder_equity, total_debt
        )
        
        # Safety Ratios
        safety = self.calculate_safety_ratios(
            total_assets, shareholder_equity, total_debt, retained_earnings,
            working_capital, ebit, ebitda, interest_expense,
            current_assets, current_liabilities, revenue
        )
        ratios.altman_z_score = safety.get('altman_z_score')
        ratios.debt_to_equity = safety.get('debt_to_equity')
        ratios.debt_to_ebitda = safety.get('debt_to_ebitda')
        ratios.interest_coverage = safety.get('interest_coverage')
        ratios.current_ratio = safety.get('current_ratio')
        
        # Earnings Quality
        earnings_quality = self.calculate_earnings_quality(
            net_income, operating_cash_flow, free_cash_flow, total_assets
        )
        ratios.accrual_ratio = earnings_quality.get('accrual_ratio')
        ratios.cash_conversion = earnings_quality.get('cash_conversion')
        ratios.fcf_conversion = earnings_quality.get('fcf_conversion')
        
        # Growth Rates (from historical data)
        if historical_revenue:
            ratios.revenue_growth = self.calculate_growth_rates(historical_revenue)
        if historical_assets:
            ratios.asset_growth = self.calculate_growth_rates(historical_assets)
        if historical_earnings:
            ratios.earnings_growth = self.calculate_growth_rates(historical_earnings)
        
        # Data Quality Assessment
        required_inputs = [
            ('revenue', revenue),
            ('net_income', net_income),
            ('total_assets', total_assets),
            ('shareholder_equity', shareholder_equity)
        ]
        
        for name, value in required_inputs:
            if value is None:
                missing_inputs.append(name)
        
        ratios.missing_inputs = missing_inputs
        
        if len(missing_inputs) == 0:
            ratios.data_quality = "complete"
        elif len(missing_inputs) <= 2:
            ratios.data_quality = "partial"
        else:
            ratios.data_quality = "insufficient"
        
        logger.debug(f"Calculated {sum(1 for v in ratios.__dict__.values() if v is not None)} ratios "
                    f"with data quality: {ratios.data_quality}")
        
        return ratios


# Example usage
if __name__ == "__main__":
    # Initialize calculator
    calculator = FinancialRatioCalculator()
    
    # Example with Apple-like data
    print("\n" + "="*60)
    print("Example: Calculate ratios for Apple-like data")
    print("="*60)
    
    ratios = calculator.calculate_all_ratios(
        revenue=394328000000,  # $394B
        cogs=223546000000,    # $224B
        operating_income=119437000000,  # $119B
        net_income=99803000000,  # $100B
        total_assets=352583000000,  # $353B
        shareholder_equity=62048000000,  # $62B
        total_debt=124719000000,  # $125B
        retained_earnings=14961000000,  # $15B
        working_capital=46568000000,  # $47B
        ebit=119437000000,  # $119B
        ebitda=137437000000,  # $137B (estimated)
        interest_expense=3866000000,  # $3.9B
        operating_cash_flow=122151000000,  # $122B
        free_cash_flow=111443000000,  # $111B
        current_assets=135979000000,  # $136B
        current_liabilities=89411000000,  # $89B
    )
    
    print(f"ROE: {ratios.roe:.1%}" if ratios.roe else "ROE: N/A")
    print(f"ROIC: {ratios.roic:.1%}" if ratios.roic else "ROIC: N/A")
    print(f"Gross Margin: {ratios.gross_margin:.1%}" if ratios.gross_margin else "Gross Margin: N/A")
    print(f"Operating Margin: {ratios.operating_margin:.1%}" if ratios.operating_margin else "Operating Margin: N/A")
    print(f"Net Margin: {ratios.net_margin:.1%}" if ratios.net_margin else "Net Margin: N/A")
    print(f"Altman Z-Score: {ratios.altman_z_score:.2f}" if ratios.altman_z_score else "Altman Z-Score: N/A")
    print(f"Debt/Equity: {ratios.debt_to_equity:.2f}" if ratios.debt_to_equity else "Debt/Equity: N/A")
    print(f"Interest Coverage: {ratios.interest_coverage:.1f}" if ratios.interest_coverage else "Interest Coverage: N/A")
    print(f"Data Quality: {ratios.data_quality}")
    print(f"Missing Inputs: {ratios.missing_inputs}")
    
    # Test growth rate calculation
    print("\n" + "="*60)
    print("Example: Growth rate calculation")
    print("="*60)
    
    historical_revenue = [200000, 250000, 300000, 350000, 394328]  # Growing revenue
    growth_rate = calculator.calculate_growth_rates(historical_revenue)
    print(f"Revenue CAGR: {growth_rate:.1%}" if growth_rate else "Revenue CAGR: N/A")