"""
Safety Metrics Module for Quality Analysis

This module implements safety/risk metrics for stock evaluation:
- Beta: Market sensitivity (lower is safer)
- Idiosyncratic Volatility: Firm-specific risk (lower is safer)
- Altman Z-Score: Bankruptcy probability (higher is safer)
- Debt/EBITDA: Leverage level (lower is safer)
- Interest Coverage: Ability to service debt (higher is safer)

Weight in Quality Score: 15% (UPDATES.md)

Author: Quality Analysis System
Date: January 2026
"""

from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from scipy import stats
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SafetyMetricsResult:
    """Complete safety metrics analysis result."""
    beta: Optional[float]
    beta_score: float
    idiosyncratic_volatility: Optional[float]
    ivol_score: float
    altman_z_score: Optional[float]
    z_score_score: float
    debt_to_ebitda: Optional[float]
    leverage_score: float
    interest_coverage: Optional[float]
    interest_coverage_score: float
    safety_score: float
    red_flags: List[Dict]
    is_safe: bool

    def to_dict(self) -> dict:
        return {
            'beta': self.beta,
            'beta_score': self.beta_score,
            'idiosyncratic_volatility': self.idiosyncratic_volatility,
            'ivol_score': self.ivol_score,
            'altman_z_score': self.altman_z_score,
            'z_score_score': self.z_score_score,
            'debt_to_ebitda': self.debt_to_ebitda,
            'leverage_score': self.leverage_score,
            'interest_coverage': self.interest_coverage,
            'interest_coverage_score': self.interest_coverage_score,
            'safety_score': self.safety_score,
            'red_flags': self.red_flags,
            'is_safe': self.is_safe
        }


class SafetyAnalyzer:
    """
    Analyze safety/risk metrics for stock evaluation.

    Implements comprehensive safety metrics for assessing financial stability
    and downside risk:

    Scoring (0-10 scale):
    - Beta: <0.5 = 10, 0.5-0.8 = 8-9, 0.8-1.2 = 6-7, 1.2-1.5 = 4-5, >1.5 = 1-3
    - Idiosyncratic Volatility: <15% = 10, 15-25% = 7-9, 25-35% = 4-6, >35% = 1-3
    - Altman Z-Score: >3.0 = 10, 2.0-3.0 = 7-9, 1.0-2.0 = 4-6, <1.0 = 1-3
    - Debt/EBITDA: <1.0 = 10, 1.0-2.0 = 8-9, 2.0-3.0 = 6-7, 3.0-4.0 = 4-5, >4.0 = 1-3
    - Interest Coverage: >10x = 10, 6-10x = 8-9, 3-6x = 5-7, 1-3x = 2-4, <1x = 1

    Example:
        >>> analyzer = SafetyAnalyzer()
        >>> result = analyzer.analyze({
        ...     'stock_returns': [0.01, -0.02, 0.03, ...],
        ...     'market_returns': [0.005, -0.01, 0.02, ...],
        ...     'total_debt': 1000,
        ...     'ebitda': 200,
        ...     'interest_expense': 20,
        ...     'total_assets': 5000,
        ...     'total_equity': 2000,
        ...     'retained_earnings': 500,
        ...     'ebit': 150,
        ...     'sales': 4000
        ... })
        >>> print(f"Safety Score: {result.safety_score}/10")
    """

    # Beta thresholds (lower is safer)
    BETA_EXCELLENT = 0.50  # <0.5 = 10 points
    BETA_GOOD = 0.80       # 0.5-0.8 = 8-9 points
    BETA_AVERAGE = 1.20    # 0.8-1.2 = 6-7 points
    BETA_POOR = 1.50       # 1.2-1.5 = 4-5 points

    # Idiosyncratic volatility thresholds (annualized)
    IVOL_EXCELLENT = 0.15  # <15% = 10 points
    IVOL_GOOD = 0.25       # 15-25% = 7-9 points
    IVOL_AVERAGE = 0.35    # 25-35% = 4-6 points
    IVOL_POOR = 0.50       # >35% = 1-3 points

    # Altman Z-Score thresholds
    Z_SCORE_EXCELLENT = 3.0  # >3.0 = 10 points (Safe)
    Z_SCORE_GOOD = 2.0       # 2.0-3.0 = 7-9 points (Grey)
    Z_SCORE_AVERAGE = 1.0    # 1.0-2.0 = 4-6 points (Distress)
    Z_SCORE_POOR = 0.5       # <1.0 = 1-3 points (High Distress)

    # Debt/EBITDA thresholds
    DEBT_EBITDA_EXCELLENT = 1.0   # <1.0 = 10 points
    DEBT_EBITDA_GOOD = 2.0        # 1.0-2.0 = 8-9 points
    DEBT_EBITDA_AVERAGE = 3.0     # 2.0-3.0 = 6-7 points
    DEBT_EBITDA_POOR = 4.0        # 3.0-4.0 = 4-5 points

    # Interest Coverage thresholds (times)
    INT_COV_EXCELLENT = 10.0   # >10x = 10 points
    INT_COV_GOOD = 6.0         # 6-10x = 8-9 points
    INT_COV_AVERAGE = 3.0      # 3-6x = 5-7 points
    INT_COV_POOR = 1.0         # 1-3x = 2-4 points

    def __init__(self):
        """Initialize the Safety Analyzer."""
        logger.info("SafetyAnalyzer initialized")

    def calculate_beta(
        self,
        stock_returns: List[float],
        market_returns: List[float],
        lookback_days: int = 252
    ) -> Optional[float]:
        """
        Calculate stock beta using CAPM regression.

        Beta = Cov(Stock, Market) / Var(Market)

        Args:
            stock_returns: List of stock returns
            market_returns: List of market returns
            lookback_days: Number of trading days for calculation

        Returns:
            Beta coefficient (systematic risk measure)
            None if calculation not possible
        """
        try:
            if len(stock_returns) < 30 or len(market_returns) < 30:
                logger.warning("Cannot calculate beta: insufficient data points")
                return None

            # Align arrays
            min_len = min(len(stock_returns), len(market_returns))
            stock = np.array(stock_returns[-min_len:])
            market = np.array(market_returns[-min_len:])

            # Remove NaN values
            mask = ~(np.isnan(stock) | np.isnan(market))
            stock = stock[mask]
            market = market[mask]

            if len(stock) < 30:
                logger.warning("Cannot calculate beta: insufficient valid data")
                return None

            # Calculate beta using linear regression
            slope, intercept, r_value, p_value, std_err = stats.linregress(market, stock)
            beta = slope

            logger.debug(f"Beta: {beta:.3f} (R²={r_value**2:.3f}, p-value={p_value:.4f})")

            return beta

        except Exception as e:
            logger.error(f"Error calculating beta: {e}")
            return None

    def calculate_beta_score(self, beta: Optional[float]) -> float:
        """
        Calculate beta score (0-10 scale).

        Lower beta = Higher score (less market sensitivity)

        Args:
            beta: Calculated beta coefficient

        Returns:
            Score from 0-10
        """
        if beta is None:
            return 5.0  # Neutral score if data unavailable

        # Excellent: <0.5
        if beta <= self.BETA_EXCELLENT:
            return 10.0

        # Good: 0.5-0.8 - interpolate 8-9
        elif beta <= self.BETA_GOOD:
            ratio = (beta - self.BETA_EXCELLENT) / (self.BETA_GOOD - self.BETA_EXCELLENT)
            return 8.0 + (ratio * 1.0)

        # Average: 0.8-1.2 - interpolate 6-7
        elif beta <= self.BETA_AVERAGE:
            ratio = (beta - self.BETA_GOOD) / (self.BETA_AVERAGE - self.BETA_GOOD)
            return 6.0 + (ratio * 1.0)

        # Poor: 1.2-1.5 - interpolate 4-5
        elif beta <= self.BETA_POOR:
            ratio = (beta - self.BETA_AVERAGE) / (self.BETA_POOR - self.BETA_AVERAGE)
            return 4.0 + (ratio * 1.0)

        # Very high beta
        else:
            return max(1.0, 4.0 - (beta - self.BETA_POOR) * 2)

    def calculate_idiosyncratic_volatility(
        self,
        stock_returns: List[float],
        market_returns: List[float],
        lookback_days: int = 252
    ) -> Optional[float]:
        """
        Calculate idiosyncratic volatility (firm-specific risk).

        Idiosyncratic Vol = Std Dev of residuals from CAPM regression

        Args:
            stock_returns: List of stock returns
            market_returns: List of market returns
            lookback_days: Number of trading days

        Returns:
            Annualized idiosyncratic volatility (decimal)
            None if calculation not possible
        """
        try:
            if len(stock_returns) < 30 or len(market_returns) < 30:
                logger.warning("Cannot calculate IVOL: insufficient data")
                return None

            # Align arrays
            min_len = min(len(stock_returns), len(market_returns))
            stock = np.array(stock_returns[-min_len:])
            market = np.array(market_returns[-min_len:])

            # Remove NaN values
            mask = ~(np.isnan(stock) | np.isnan(market))
            stock = stock[mask]
            market = market[mask]

            if len(stock) < 30:
                return None

            # Calculate expected returns using CAPM
            slope, intercept, r_value, p_value, std_err = stats.linregress(market, stock)
            expected_returns = slope * market + intercept

            # Calculate residuals
            residuals = stock - expected_returns

            # Calculate standard deviation of residuals
            ivol_daily = np.std(residuals, ddof=2)

            # Annualize (square root of 252 trading days)
            ivol_annual = ivol_daily * np.sqrt(252)

            logger.debug(f"Idiosyncratic Volatility: {ivol_annual:.3f} ({ivol_annual*100:.1f}%)")

            return ivol_annual

        except Exception as e:
            logger.error(f"Error calculating idiosyncratic volatility: {e}")
            return None

    def calculate_ivol_score(self, ivol: Optional[float]) -> float:
        """
        Calculate idiosyncratic volatility score (0-10 scale).

        Lower IVOL = Higher score (less firm-specific risk)

        Args:
            ivol: Annualized idiosyncratic volatility

        Returns:
            Score from 0-10
        """
        if ivol is None:
            return 5.0

        # Excellent: <15%
        if ivol <= self.IVOL_EXCELLENT:
            return 10.0

        # Good: 15-25% - interpolate 7-9
        elif ivol <= self.IVOL_GOOD:
            ratio = (ivol - self.IVOL_EXCELLENT) / (self.IVOL_GOOD - self.IVOL_EXCELLENT)
            return 7.0 + (ratio * 2.0)

        # Average: 25-35% - interpolate 4-6
        elif ivol <= self.IVOL_AVERAGE:
            ratio = (ivol - self.IVOL_GOOD) / (self.IVOL_AVERAGE - self.IVOL_GOOD)
            return 4.0 + (ratio * 2.0)

        # Poor: 35-50% - interpolate 1-3
        elif ivol <= self.IVOL_POOR:
            ratio = (ivol - self.IVOL_AVERAGE) / (self.IVOL_POOR - self.IVOL_AVERAGE)
            return 1.0 + (ratio * 2.0)

        # Very high IVOL
        else:
            return max(1.0, 3.0 - (ivol - self.IVOL_POOR) * 2)

    def calculate_altman_z_score(
        self,
        total_assets: float,
        total_equity: float,
        retained_earnings: float,
        ebit: float,
        sales: float,
        working_capital: float = None,
        market_cap: float = None
    ) -> Optional[float]:
        """
        Calculate Altman Z-Score for manufacturing companies.

        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

        Where:
        - X1 = Working Capital / Total Assets
        - X2 = Retained Earnings / Total Assets
        - X3 = EBIT / Total Assets
        - X4 = Market Value of Equity / Total Liabilities
        - X5 = Sales / Total Assets

        Interpretation:
        - Z > 3.0: Safe (Low bankruptcy probability)
        - 2.0 < Z < 3.0: Grey Zone
        - Z < 2.0: Distress (High bankruptcy probability)

        Args:
            total_assets: Total assets
            total_equity: Total shareholder equity (book value)
            retained_earnings: Accumulated retained earnings
            ebit: Earnings before interest and taxes
            sales: Total sales/revenue
            working_capital: Current assets - Current liabilities
            market_cap: Market capitalization (preferred for X4 calculation)

        Returns:
            Altman Z-Score
            None if calculation not possible
        """
        try:
            # Validate required inputs - use None checks to distinguish missing vs zero
            if total_assets is None or total_equity is None:
                logger.warning("Cannot calculate Z-Score: missing total_assets or total_equity")
                return None

            if total_assets <= 0:
                logger.warning("Cannot calculate Z-Score: total assets <= 0")
                return None

            total_liabilities = total_assets - total_equity
            if total_liabilities <= 0:
                logger.warning("Cannot calculate Z-Score: total liabilities <= 0")
                return None

            # Handle missing optional fields with defaults
            if working_capital is None:
                working_capital = 0
            if retained_earnings is None:
                retained_earnings = 0
            if ebit is None:
                ebit = 0
            if sales is None:
                sales = 0

            # Use market cap if available (preferred), otherwise fall back to book value
            if market_cap is not None and market_cap > 0:
                market_value_equity = market_cap
                logger.debug(f"Using market cap for Z-Score: ${market_cap:,.0f}")
            else:
                market_value_equity = total_equity  # Fallback to book value
                logger.debug(f"Using book value for Z-Score (market cap not available): ${total_equity:,.0f}")

            # Calculate Z-Score components
            x1 = working_capital / total_assets
            x2 = retained_earnings / total_assets
            x3 = ebit / total_assets
            x4 = market_value_equity / total_liabilities
            x5 = sales / total_assets

            # Calculate Z-Score
            z_score = (1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5)

            logger.debug(f"Altman Z-Score: {z_score:.3f} (X1={x1:.3f}, X2={x2:.3f}, X3={x3:.3f}, X4={x4:.3f}, X5={x5:.3f})")

            return z_score

        except Exception as e:
            logger.error(f"Error calculating Altman Z-Score: {e}")
            return None

    def calculate_z_score_score(self, z_score: Optional[float]) -> float:
        """
        Calculate Z-Score safety rating (0-10 scale).

        Higher Z-Score = Higher score (lower bankruptcy risk)

        Args:
            z_score: Calculated Altman Z-Score

        Returns:
            Score from 0-10
        """
        if z_score is None:
            return 5.0  # Neutral score when data is unavailable (don't penalize for missing data)

        # Return low score for near-zero Z-Score (critical bankruptcy risk)
        if z_score < 0.5:
            return 1.0  # Critical bankruptcy risk = minimum score

        # Excellent: >3.0
        if z_score >= self.Z_SCORE_EXCELLENT:
            return 10.0

        # Good: 2.0-3.0 - interpolate 7-9
        elif z_score >= self.Z_SCORE_GOOD:
            ratio = (z_score - self.Z_SCORE_GOOD) / (self.Z_SCORE_EXCELLENT - self.Z_SCORE_GOOD)
            return 7.0 + (ratio * 2.0)

        # Average: 1.0-2.0 - interpolate 4-6
        elif z_score >= self.Z_SCORE_AVERAGE:
            ratio = (z_score - self.Z_SCORE_AVERAGE) / (self.Z_SCORE_GOOD - self.Z_SCORE_AVERAGE)
            return 4.0 + (ratio * 2.0)

        # Poor: 0.5-1.0 - interpolate 1-3
        elif z_score >= self.Z_SCORE_POOR:
            ratio = (z_score - self.Z_SCORE_POOR) / (self.Z_SCORE_AVERAGE - self.Z_SCORE_POOR)
            return 1.0 + (ratio * 2.0)

        # Very distressed
        else:
            return max(1.0, 3.0 * z_score / self.Z_SCORE_POOR)

    def calculate_debt_to_ebitda(
        self,
        total_debt: float,
        ebitda: float
    ) -> Optional[float]:
        """
        Calculate Debt/EBITDA ratio.

        Debt/EBITDA = Total Debt / EBITDA

        Interpretation:
        - <1.0: Excellent (can repay debt in <1 year)
        - 1.0-2.0: Good
        - 2.0-3.0: Acceptable
        - 3.0-4.0: Concerning
        - >4.0: High risk

        Args:
            total_debt: Total debt (short-term + long-term)
            ebitda: Earnings before interest, taxes, depreciation, amortization

        Returns:
            Debt/EBITDA ratio
            None if calculation not possible
        """
        try:
            if ebitda <= 0:
                logger.warning("Cannot calculate Debt/EBITDA: EBITDA <= 0")
                return None

            ratio = total_debt / abs(ebitda)

            logger.debug(f"Debt/EBITDA: {ratio:.2f}x")

            return ratio

        except Exception as e:
            logger.error(f"Error calculating Debt/EBITDA: {e}")
            return None

    def calculate_leverage_score(self, debt_ebitda: Optional[float]) -> float:
        """
        Calculate leverage score (0-10 scale).

        Lower Debt/EBITDA = Higher score

        Args:
            debt_ebitda: Calculated Debt/EBITDA ratio

        Returns:
            Score from 0-10
        """
        if debt_ebitda is None:
            return 5.0

        # Excellent: <1.0
        if debt_ebitda <= self.DEBT_EBITDA_EXCELLENT:
            return 10.0

        # Good: 1.0-2.0 - interpolate 8-9
        elif debt_ebitda <= self.DEBT_EBITDA_GOOD:
            ratio = (debt_ebitda - self.DEBT_EBITDA_EXCELLENT) / (self.DEBT_EBITDA_GOOD - self.DEBT_EBITDA_EXCELLENT)
            return 8.0 + (ratio * 1.0)

        # Average: 2.0-3.0 - interpolate 6-7
        elif debt_ebitda <= self.DEBT_EBITDA_AVERAGE:
            ratio = (debt_ebitda - self.DEBT_EBITDA_GOOD) / (self.DEBT_EBITDA_AVERAGE - self.DEBT_EBITDA_GOOD)
            return 6.0 + (ratio * 1.0)

        # Poor: 3.0-4.0 - interpolate 4-5
        elif debt_ebitda <= self.DEBT_EBITDA_POOR:
            ratio = (debt_ebitda - self.DEBT_EBITDA_AVERAGE) / (self.DEBT_EBITDA_POOR - self.DEBT_EBITDA_AVERAGE)
            return 4.0 + (ratio * 1.0)

        # Very high leverage
        else:
            return max(1.0, 4.0 - (debt_ebitda - self.DEBT_EBITDA_POOR))

    def calculate_interest_coverage(
        self,
        ebit: Optional[float],
        interest_expense: Optional[float]
    ) -> Optional[float]:
        """
        Calculate Interest Coverage Ratio.

        Interest Coverage = EBIT / Interest Expense

        Interpretation:
        - >10x: Excellent (ample safety margin)
        - 6-10x: Good
        - 3-6x: Acceptable but concerning
        - 1-3x: Risky
        - <1x: Danger (cannot cover interest)
        - N/A: Not applicable (company has net interest income or data unavailable)

        Args:
            ebit: Earnings before interest and taxes
            interest_expense: Interest expense for the period

        Returns:
            Interest coverage ratio (times)
            None if calculation not possible (e.g., net interest income)
        """
        try:
            # Handle missing data gracefully
            if interest_expense is None or interest_expense == 0:
                # Many tech companies (AAPL, MSFT) have net interest income, not expense
                # For these companies, interest coverage is not applicable (they're financially strong)
                # Return 15.0 (excellent) and log that coverage is not applicable
                if ebit is not None and ebit > 0:
                    logger.debug(f"Interest coverage: Not applicable (company has net interest income or no debt burden)")
                    return 15.0  # Excellent - company has no meaningful interest expense
                else:
                    return None
            
            if interest_expense < 0:
                # Negative interest expense = net interest income
                # This means the company earns more in interest than it pays
                # This is financially healthy, so mark as excellent
                logger.debug(f"Interest coverage: Net interest income (financially healthy)")
                return 15.0
            
            if ebit is None or ebit <= 0:
                return None
            
            coverage = ebit / interest_expense

            logger.debug(f"Interest Coverage: {coverage:.2f}x")

            return coverage

        except Exception as e:
            logger.error(f"Error calculating interest coverage: {e}")
            return None

    def calculate_interest_coverage_score(self, coverage: Optional[float]) -> float:
        """
        Calculate interest coverage score (0-10 scale).

        Higher coverage = Higher score

        Args:
            coverage: Calculated interest coverage ratio

        Returns:
            Score from 0-10
        """
        if coverage is None:
            return 5.0

        # Excellent: >10x
        if coverage >= self.INT_COV_EXCELLENT:
            return 10.0

        # Good: 6-10x - interpolate 8-9
        elif coverage >= self.INT_COV_GOOD:
            ratio = (coverage - self.INT_COV_GOOD) / (self.INT_COV_EXCELLENT - self.INT_COV_GOOD)
            return 8.0 + (ratio * 1.0)

        # Average: 3-6x - interpolate 5-7
        elif coverage >= self.INT_COV_AVERAGE:
            ratio = (coverage - self.INT_COV_AVERAGE) / (self.INT_COV_GOOD - self.INT_COV_AVERAGE)
            return 5.0 + (ratio * 2.0)

        # Poor: 1-3x - interpolate 2-4
        elif coverage >= self.INT_COV_POOR:
            ratio = (coverage - self.INT_COV_POOR) / (self.INT_COV_AVERAGE - self.INT_COV_POOR)
            return 2.0 + (ratio * 2.0)

        # Very poor coverage
        else:
            return max(1.0, coverage * 2)

    def detect_safety_red_flags(
        self,
        beta: Optional[float],
        z_score: Optional[float],
        debt_ebitda: Optional[float],
        interest_coverage: Optional[float]
    ) -> List[Dict]:
        """
        Detect safety/red flags.

        Args:
            beta: Calculated beta
            z_score: Calculated Altman Z-Score
            debt_ebitda: Calculated Debt/EBITDA
            interest_coverage: Calculated interest coverage

        Returns:
            List of red flag dictionaries
        """
        red_flags = []

        # High Beta (HIGH severity)
        if beta is not None and beta > 2.0:
            red_flags.append({
                'category': 'HIGH BETA',
                'severity': 'HIGH',
                'description': f"Beta at {beta:.2f} (>2.0). Stock is highly volatile relative to market.",
                'metric_value': beta
            })
        elif beta is not None and beta > 1.5:
            red_flags.append({
                'category': 'ELEVATED BETA',
                'severity': 'MEDIUM',
                'description': f"Beta at {beta:.2f} (>1.5). Above-average market sensitivity.",
                'metric_value': beta
            })

        # Distress Zone (HIGH severity)
        if z_score is not None and z_score < 1.0:
            red_flags.append({
                'category': 'BANKRUPTCY RISK',
                'severity': 'CRITICAL',
                'description': f"Altman Z-Score at {z_score:.2f} (<1.0). High bankruptcy probability.",
                'metric_value': z_score
            })
        elif z_score is not None and z_score < 2.0:
            red_flags.append({
                'category': 'FINANCIAL DISTRESS',
                'severity': 'MEDIUM',
                'description': f"Altman Z-Score at {z_score:.2f} (<2.0). Entering distress zone.",
                'metric_value': z_score
            })

        # High Leverage (HIGH severity)
        if debt_ebitda is not None and debt_ebitda > 5.0:
            red_flags.append({
                'category': 'EXCESSIVE LEVERAGE',
                'severity': 'HIGH',
                'description': f"Debt/EBITDA at {debt_ebitda:.1f}x (>5.0x). Very high leverage risk.",
                'metric_value': debt_ebitda
            })
        elif debt_ebitda is not None and debt_ebitda > 4.0:
            red_flags.append({
                'category': 'HIGH LEVERAGE',
                'severity': 'MEDIUM',
                'description': f"Debt/EBITDA at {debt_ebitda:.1f}x (>4.0x). Elevated debt burden.",
                'metric_value': debt_ebitda
            })

        # Low Interest Coverage (HIGH severity)
        if interest_coverage is not None and interest_coverage < 1.0:
            red_flags.append({
                'category': 'INTEREST COVERAGE RISK',
                'severity': 'HIGH',
                'description': f"Interest coverage at {interest_coverage:.1f}x (<1.0x). Cannot cover interest.",
                'metric_value': interest_coverage
            })
        elif interest_coverage is not None and interest_coverage < 3.0:
            red_flags.append({
                'category': 'WEAK INTEREST COVERAGE',
                'severity': 'MEDIUM',
                'description': f"Interest coverage at {interest_coverage:.1f}x (<3.0x). Limited debt capacity.",
                'metric_value': interest_coverage
            })

        return red_flags

    def analyze(self, financial_data: Dict[str, any]) -> SafetyMetricsResult:
        """
        Complete safety analysis.

        Args:
            financial_data: Dictionary with financial metrics:
                - stock_returns: List of stock returns (for beta/IVOL)
                - market_returns: List of market returns (for beta/IVOL)
                - total_assets: Total assets (for Z-Score)
                - total_equity: Total equity (for Z-Score)
                - retained_earnings: Retained earnings (for Z-Score)
                - ebit: Earnings before interest and taxes (for Z-Score, Interest Coverage)
                - sales: Total sales (for Z-Score)
                - total_debt: Total debt (for Debt/EBITDA)
                - ebitda: EBITDA (for Debt/EBITDA)
                - interest_expense: Interest expense (for Interest Coverage)
                - working_capital: Working capital (for Z-Score, optional)

        Returns:
            SafetyMetricsResult with all metrics and red flags
        """
        # Calculate Beta
        stock_returns = financial_data.get('stock_returns', [])
        market_returns = financial_data.get('market_returns', [])

        if not stock_returns or not market_returns:
            # Try to use 1-year mock data if not provided
            logger.warning("Return data not provided, beta will be estimated from price data")
            beta = None
        else:
            beta = self.calculate_beta(stock_returns, market_returns)
        beta_score = self.calculate_beta_score(beta)

        # Calculate Idiosyncratic Volatility
        if not stock_returns or not market_returns:
            ivol = None
        else:
            ivol = self.calculate_idiosyncratic_volatility(stock_returns, market_returns)
        ivol_score = self.calculate_ivol_score(ivol)

        # Calculate Altman Z-Score
        z_score = self.calculate_altman_z_score(
            total_assets=financial_data.get('total_assets'),
            total_equity=financial_data.get('total_equity'),
            retained_earnings=financial_data.get('retained_earnings'),
            ebit=financial_data.get('ebit'),
            sales=financial_data.get('sales'),
            working_capital=financial_data.get('working_capital'),
            market_cap=financial_data.get('market_cap')
        )
        z_score_score = self.calculate_z_score_score(z_score)

        # Calculate Debt/EBITDA
        debt_ebitda = self.calculate_debt_to_ebitda(
            total_debt=financial_data.get('total_debt'),
            ebitda=financial_data.get('ebitda')
        )
        leverage_score = self.calculate_leverage_score(debt_ebitda)

        # Calculate Interest Coverage
        interest_coverage = self.calculate_interest_coverage(
            ebit=financial_data.get('ebit'),
            interest_expense=financial_data.get('interest_expense')
        )
        interest_coverage_score = self.calculate_interest_coverage_score(interest_coverage)

        # Calculate overall Safety Score
        # Weighting: Beta 20%, Idiosyncratic Vol 15%, Z-Score 25%, Leverage 25%, Interest Coverage 15%
        safety_score = (
            beta_score * 0.20 +
            ivol_score * 0.15 +
            z_score_score * 0.25 +
            leverage_score * 0.25 +
            interest_coverage_score * 0.15
        )

        # Detect red flags
        red_flags = self.detect_safety_red_flags(
            beta=beta,
            z_score=z_score,
            debt_ebitda=debt_ebitda,
            interest_coverage=interest_coverage
        )

        # Determine if safe (score >= 7)
        is_safe = safety_score >= 7.0

        logger.info(
            "Safety analysis: Z-Score=%s, Debt/EBITDA=%s, Score=%.1f/10, Red Flags=%d",
            f"{z_score:.2f}" if z_score else "N/A",
            f"{debt_ebitda:.1f}x" if debt_ebitda else "N/A",
            safety_score,
            len(red_flags)
        )

        return SafetyMetricsResult(
            beta=beta,
            beta_score=beta_score,
            idiosyncratic_volatility=ivol,
            ivol_score=ivol_score,
            altman_z_score=z_score,
            z_score_score=z_score_score,
            debt_to_ebitda=debt_ebitda,
            leverage_score=leverage_score,
            interest_coverage=interest_coverage,
            interest_coverage_score=interest_coverage_score,
            safety_score=round(safety_score, 1),
            red_flags=red_flags,
            is_safe=is_safe
        )


def get_safety_analyzer() -> SafetyAnalyzer:
    """Factory function to get a SafetyAnalyzer instance."""
    return SafetyAnalyzer()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example: Safe company
    data = {
        'total_assets': 10_000_000_000,
        'total_equity': 6_000_000_000,
        'retained_earnings': 2_000_000_000,
        'ebit': 1_500_000_000,
        'sales': 8_000_000_000,
        'total_debt': 2_000_000_000,
        'ebitda': 2_500_000_000,
        'interest_expense': 100_000_000,
        'working_capital': 1_500_000_000
    }

    analyzer = SafetyAnalyzer()
    result = analyzer.analyze(data)

    print("=" * 60)
    print("SAFETY METRICS ANALYSIS")
    print("=" * 60)
    print(f"Beta: {result.beta:.2f}" if result.beta else "N/A")
    print(f"Beta Score: {result.beta_score:.1f}/10")
    print(f"Idiosyncratic Vol: {result.idiosyncratic_volatility:.1%}" if result.idiosyncratic_volatility else "N/A")
    print(f"IVOL Score: {result.ivol_score:.1f}/10")
    print(f"Altman Z-Score: {result.altman_z_score:.2f}" if result.altman_z_score else "N/A")
    print(f"Z-Score Safety: {result.z_score_score:.1f}/10")
    print(f"Debt/EBITDA: {result.debt_to_ebitda:.2f}x" if result.debt_to_ebitda else "N/A")
    print(f"Leverage Score: {result.leverage_score:.1f}/10")
    print(f"Interest Coverage: {result.interest_coverage:.1f}x" if result.interest_coverage else "N/A")
    print(f"Interest Coverage Score: {result.interest_coverage_score:.1f}/10")
    print(f"Safety Score: {result.safety_score}/10")
    print(f"Is Safe: {result.is_safe}")

    if result.red_flags:
        print("\nRED FLAGS:")
        for rf in result.red_flags:
            print(f"  [{rf['severity']}] {rf['category']}: {rf['description'][:60]}...")

    print("=" * 60)

    # Example: Distressed company
    distressed_data = {
        'total_assets': 5_000_000_000,
        'total_equity': 500_000_000,
        'retained_earnings': -200_000_000,  # Negative retained earnings
        'ebit': 100_000_000,
        'sales': 3_000_000_000,
        'total_debt': 4_000_000_000,
        'ebitda': 400_000_000,  # 10x leverage
        'interest_expense': 200_000_000,  # Only 0.5x coverage
        'working_capital': -500_000_000
    }

    result2 = analyzer.analyze(distressed_data)

    print("\n" + "=" * 60)
    print("DISTRESSED COMPANY EXAMPLE")
    print("=" * 60)
    print(f"Safety Score: {result2.safety_score}/10")

    if result2.red_flags:
        print("\nRED FLAGS:")
        for rf in result2.red_flags:
            print(f"  [{rf['severity']}] {rf['category']}: {rf['description']}")
