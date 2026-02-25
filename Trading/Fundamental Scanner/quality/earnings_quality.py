"""
Earnings Quality Module for Quality Analysis

This module implements earnings quality metrics based on academic research:
- Sloan (1996): Accrual Anomaly - low accruals predict higher returns
- Piotroski (2000): F-Score - 9 binary signals for financial health
- Dechow, Khimich, Sloan (2011): Accrual Anomaly Review

Metrics:
1. Accrual Ratio: (Net Income - Operating Cash Flow) / Average Total Assets
2. Cash Conversion: Operating Cash Flow / Net Income
3. Piotroski F-Score: 9-component binary score

Red Flag Thresholds (from UPDATES.md):
- Accrual Ratio > 10%: HIGH severity
- Accrual Ratio < -10%: MODERATE severity (potential distress)
- Cash Conversion < 0.8: HIGH severity
- F-Score ≤ 3: CRITICAL severity

Author: Quality Analysis System
Date: January 2026
"""

from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EarningsQualityResult:
    """Complete earnings quality analysis result."""
    accrual_ratio: Optional[float]
    cash_conversion: Optional[float]
    f_score: int
    f_score_breakdown: Dict[str, int]
    earnings_quality_score: float  # 0-10 scale
    red_flags: List[Dict]
    is_high_quality: bool
    
    def to_dict(self) -> dict:
        return {
            'accrual_ratio': self.accrual_ratio,
            'cash_conversion': self.cash_conversion,
            'f_score': self.f_score,
            'f_score_breakdown': self.f_score_breakdown,
            'earnings_quality_score': self.earnings_quality_score,
            'red_flags': self.red_flags,
            'is_high_quality': self.is_high_quality
        }


@dataclass
class PiotroskiScoreBreakdown:
    """Detailed breakdown of Piotroski F-Score components."""
    f_roa: int  # ROA > 0
    f_cfo: int  # CFO > 0
    f_droa: int  # ROA increased YoY
    f_accrual: int  # CFO > Net Income (low accruals)
    f_dlever: int  # Leverage decreased YoY
    f_dliquid: int  # Current ratio increased YoY
    f_eq_offer: int  # No new shares issued
    f_dmargin: int  # Gross margin increased YoY
    f_dturn: int  # Asset turnover increased YoY
    
    @property
    def total_score(self) -> int:
        """Calculate total F-Score (0-9)."""
        return (
            self.f_roa + self.f_cfo + self.f_droa + self.f_accrual +
            self.f_dlever + self.f_dliquid + self.f_eq_offer +
            self.f_dmargin + self.f_dturn
        )


class EarningsQualityAnalyzer:
    """
    Analyze earnings quality metrics for stock evaluation.
    
    Implements academically-validated metrics for assessing earnings quality:
    - Accrual Ratio (Sloan, 1996)
    - Cash Conversion Ratio
    - Piotroski F-Score (Piotroski, 2000)
    
    Example:
        >>> analyzer = EarningsQualityAnalyzer()
        >>> result = analyzer.analyze({
        ...     'net_income': 100,
        ...     'operating_cash_flow': 120,
        ...     'total_assets': 1000,
        ...     'prior_total_assets': 900,
        ...     'current_assets': 500,
        ...     'prior_current_assets': 400,
        ...     'current_liabilities': 300,
        ...     'prior_current_liabilities': 250,
        ...     'total_debt': 200,
        ...     'prior_total_debt': 220,
        ...     'revenue': 1000,
        ...     'prior_revenue': 900,
        ...     'cogs': 600,
        ...     'prior_cogs': 550,
        ...     'shares_outstanding': 50,
        ...     'prior_shares_outstanding': 50
        ... })
        >>> print(f"F-Score: {result.f_score}/9")
    """
    
    # Red flag thresholds (from UPDATES.md)
    ACCRUAL_RATIO_HIGH = 0.10  # >10% = HIGH severity
    ACCRUAL_RATIO_LOW = -0.10  # <-10% = MODERATE severity
    CASH_CONVERSION_LOW = 0.80  # <0.8 = HIGH severity
    F_SCORE_CRITICAL = 3  # ≤3 = CRITICAL
    
    # F-Score thresholds
    F_SCORE_EXCELLENT = 8
    F_SCORE_GOOD = 6
    F_SCORE_MODERATE = 4
    
    def __init__(self):
        """Initialize the Earnings Quality Analyzer."""
        logger.info("EarningsQualityAnalyzer initialized")
    
    def calculate_accrual_ratio(
        self,
        net_income: float,
        operating_cash_flow: float,
        total_assets: float,
        prior_total_assets: float
    ) -> Optional[float]:
        """
        Calculate Accrual Ratio.
        
        Accrual Ratio = (Net Income - Operating Cash Flow) / Average Total Assets
        
        Interpretation:
        - Low/Negative accruals = HIGH earnings quality
        - High positive accruals = LOW earnings quality (potential manipulation)
        
        Args:
            net_income: Current period net income
            operating_cash_flow: Current period operating cash flow
            total_assets: Current period total assets
            prior_total_assets: Prior period total assets
            
        Returns:
            Accrual ratio as decimal (e.g., 0.05 = 5%)
            None if calculation not possible
        """
        try:
            avg_assets = (total_assets + prior_total_assets) / 2
            
            if avg_assets <= 0:
                logger.warning("Cannot calculate accrual ratio: average assets <= 0")
                return None
            
            accruals = net_income - operating_cash_flow
            accrual_ratio = accruals / avg_assets
            
            logger.debug(f"Accrual ratio: {accrual_ratio:.4f} ({accrual_ratio*100:.2f}%)")
            
            return accrual_ratio
            
        except Exception as e:
            logger.error(f"Error calculating accrual ratio: {e}")
            return None
    
    def calculate_cash_conversion(
        self,
        operating_cash_flow: float,
        net_income: float
    ) -> Optional[float]:
        """
        Calculate Cash Conversion Ratio.
        
        Cash Conversion = Operating Cash Flow / Net Income
        
        Interpretation:
        - >1.0: Company converts earnings to cash efficiently
        - 0.8-1.0: Acceptable cash conversion
        - <0.8: Poor cash conversion (HIGH red flag)
        
        Args:
            operating_cash_flow: Current period operating cash flow
            net_income: Current period net income
            
        Returns:
            Cash conversion ratio (e.g., 1.2 = 120%)
            None if calculation not possible
        """
        try:
            if net_income <= 0:
                logger.warning("Cannot calculate cash conversion: net income <= 0")
                return None
            
            cash_conversion = operating_cash_flow / net_income
            
            logger.debug(f"Cash conversion: {cash_conversion:.4f}x")
            
            return cash_conversion
            
        except Exception as e:
            logger.error(f"Error calculating cash conversion: {e}")
            return None
    
    def calculate_piotroski_f_score(
        self,
        financial_data: Dict[str, float]
    ) -> Tuple[int, PiotroskiScoreBreakdown]:
        """
        Calculate Piotroski F-Score (9 binary signals).
        
        The F-Score evaluates financial health using 9 binary criteria:
        - Profitability (4 points): ROA, CFO, ROA change, Accruals
        - Leverage/Liquidity (3 points): Leverage change, Liquidity change, Shares
        - Operating Efficiency (2 points): Margin change, Turnover change
        
        Scoring (each criterion met = 1 point, max 9):
        - 8-9: Excellent
        - 6-7: Good
        - 4-5: Moderate
        - 0-3: Poor (CRITICAL red flag)
        
        Args:
            financial_data: Dictionary with current and prior year financials:
                - net_income, prior_net_income
                - operating_cash_flow (or None)
                - total_assets, prior_total_assets
                - shareholder_equity, prior_shareholder_equity
                - current_assets, prior_current_assets
                - current_liabilities, prior_current_liabilities
                - total_debt, prior_total_debt
                - shares_outstanding, prior_shares_outstanding
                - revenue, prior_revenue
                - cogs, prior_cogs
                
        Returns:
            Tuple of (total_score, PiotroskiScoreBreakdown)
        """
        # Extract current and prior year data
        ni = financial_data.get('net_income', 0)
        prior_ni = financial_data.get('prior_net_income', 0)
        
        ocf = financial_data.get('operating_cash_flow', ni)  # Fallback to NI if OCF missing
        prior_ocf = financial_data.get('prior_operating_cash_flow', prior_ni)
        
        # Debug: Check what data we have for GOOGL
        logger.debug(f"Piotroski data: NI={ni:.1f}, OCF={ocf:.1f}, Assets={financial_data.get('total_assets', 0):.1f}")
        logger.debug(f"Piotroski prior: NI={prior_ni:.1f}, OCF={prior_ocf:.1f}, Assets={financial_data.get('prior_total_assets', 0):.1f}")
        
        ta = financial_data.get('total_assets', 1)
        prior_ta = financial_data.get('prior_total_assets', 1)
        
        se = financial_data.get('shareholder_equity', 1)
        prior_se = financial_data.get('prior_shareholder_equity', 1)
        
        ca = financial_data.get('current_assets', 0)
        prior_ca = financial_data.get('prior_current_assets', 0)
        
        cl = financial_data.get('current_liabilities', 0)
        prior_cl = financial_data.get('prior_current_liabilities', 0)
        
        td = financial_data.get('total_debt', 0)
        prior_td = financial_data.get('prior_total_debt', 0)
        
        shares = financial_data.get('shares_outstanding', 0)
        prior_shares = financial_data.get('prior_shares_outstanding', 0)
        
        rev = financial_data.get('revenue', 0)
        prior_rev = financial_data.get('prior_revenue', 0)
        
        cogs = financial_data.get('cogs', 0)
        prior_cogs = financial_data.get('prior_cogs', 0)
        
        # ===== PROFITABILITY SIGNALS (4 points) =====
        
        # F_ROA: ROA > 0 (1 point)
        roa = ni / ta if ta > 0 else 0
        f_roa = 1 if roa > 0 else 0
        
        # F_CFO: CFO > 0 (1 point)
        f_cfo = 1 if ocf > 0 else 0
        
        # F_ΔROA: ROA increased YoY (1 point)
        prior_roa = prior_ni / prior_ta if prior_ta > 0 else 0
        f_droa = 1 if roa > prior_roa else 0
        
        # F_ACCRUAL: CFO > Net Income (low accruals) (1 point)
        # Note: Piotroski uses the inverse of Sloan - CFO > NI is good
        f_accrual = 1 if ocf > ni else 0
        
        # ===== LEVERAGE/LIQUIDITY SIGNALS (3 points) =====
        
        # F_ΔLEVER: Long-term debt/Assets decreased YoY (1 point)
        lever = td / ta if ta > 0 else 0
        prior_lever = prior_td / prior_ta if prior_ta > 0 else 0
        f_dlever = 1 if lever < prior_lever else 0
        
        # F_ΔLIQUID: Current ratio increased YoY (1 point)
        current_ratio = ca / cl if cl > 0 else 0
        prior_current_ratio = prior_ca / prior_cl if prior_cl > 0 else 0
        f_dliquid = 1 if current_ratio > prior_current_ratio else 0
        
        # F_EQ_OFFER: No new shares issued (1 point)
        f_eq_offer = 1 if shares <= prior_shares else 0
        
        # ===== OPERATING EFFICIENCY SIGNALS (2 points) =====
        
        # F_ΔMARGIN: Gross margin increased YoY (1 point)
        gm = (rev - cogs) / rev if rev > 0 else 0
        prior_gm = (prior_rev - prior_cogs) / prior_rev if prior_rev > 0 else 0
        f_dmargin = 1 if gm > prior_gm else 0
        
        # F_ΔTURN: Asset turnover increased YoY (1 point)
        turnover = rev / ta if ta > 0 else 0
        prior_turnover = prior_rev / prior_ta if prior_ta > 0 else 0
        f_dturn = 1 if turnover > prior_turnover else 0
        
        # Create breakdown
        breakdown = PiotroskiScoreBreakdown(
            f_roa=f_roa,
            f_cfo=f_cfo,
            f_droa=f_droa,
            f_accrual=f_accrual,
            f_dlever=f_dlever,
            f_dliquid=f_dliquid,
            f_eq_offer=f_eq_offer,
            f_dmargin=f_dmargin,
            f_dturn=f_dturn
        )
        
        total_score = breakdown.total_score
        
        logger.debug(f"Piotroski F-Score: {total_score}/9")
        logger.debug(
            f"Breakdown: P={f_roa+f_cfo+f_droa+f_accrual}, "
            f"L={f_dlever+f_dliquid+f_eq_offer}, "
            f"E={f_dmargin+f_dturn}"
        )
        
        return total_score, breakdown
    
    def detect_earnings_red_flags(
        self,
        accrual_ratio: Optional[float],
        cash_conversion: Optional[float],
        f_score: int
    ) -> List[Dict]:
        """
        Detect earnings quality red flags.
        
        Args:
            accrual_ratio: Calculated accrual ratio
            cash_conversion: Calculated cash conversion ratio
            f_score: Piotroski F-Score
            
        Returns:
            List of red flag dictionaries with category, severity, and description
        """
        red_flags = []
        
        # High Accruals (HIGH severity)
        if accrual_ratio is not None and accrual_ratio > self.ACCRUAL_RATIO_HIGH:
            red_flags.append({
                'category': 'HIGH ACCRUALS',
                'severity': 'HIGH',
                'description': f"Accrual ratio at {accrual_ratio*100:.1f}% (threshold: {self.ACCRUAL_RATIO_HIGH*100:.0f}%). "
                             "High accruals may indicate aggressive accounting or unsustainable earnings.",
                'metric_value': accrual_ratio
            })
        
        # Very Negative Accruals (MODERATE severity - potential distress)
        if accrual_ratio is not None and accrual_ratio < self.ACCRUAL_RATIO_LOW:
            red_flags.append({
                'category': 'VERY NEGATIVE ACCRUALS',
                'severity': 'MODERATE',
                'description': f"Accrual ratio at {accrual_ratio*100:.1f}% (threshold: {self.ACCRUAL_RATIO_LOW*100:.0f}%). "
                             "Very negative accruals may indicate asset write-downs or distress.",
                'metric_value': accrual_ratio
            })
        
        # Low Cash Conversion (HIGH severity)
        if cash_conversion is not None and cash_conversion < self.CASH_CONVERSION_LOW:
            red_flags.append({
                'category': 'LOW CASH CONVERSION',
                'severity': 'HIGH',
                'description': f"Cash conversion at {cash_conversion:.2f}x (threshold: {self.CASH_CONVERSION_LOW:.1f}x). "
                             "Company struggles to convert earnings to cash.",
                'metric_value': cash_conversion
            })
        
        # Critical F-Score (CRITICAL severity)
        if f_score <= self.F_SCORE_CRITICAL:
            severity = 'CRITICAL' if f_score <= 2 else 'HIGH'
            red_flags.append({
                'category': 'POOR FINANCIAL HEALTH',
                'severity': severity,
                'description': f"F-Score at {f_score}/9 (threshold: {self.F_SCORE_CRITICAL}). "
                             "Multiple indicators suggest financial weakness.",
                'metric_value': f_score
            })
        
        return red_flags
    
    def calculate_earnings_quality_score(self, f_score: int, 
                                         accrual_ratio: Optional[float],
                                         cash_conversion: Optional[float]) -> float:
        """
        Calculate overall earnings quality score (0-10 scale).
        
        Scoring based on F-Score with adjustments for accruals and cash conversion.
        
        Args:
            f_score: Piotroski F-Score (0-9)
            accrual_ratio: Accrual ratio (-1 to 1)
            cash_conversion: Cash conversion ratio (0 to infinity)
            
        Returns:
            Score from 0-10
        """
        # Base score from F-Score
        # Map 0-9 to 0-8 range, then add adjustment
        base_score = (f_score / 9) * 8  # 0-8 range
        
        # Accrual adjustment (lower accruals = better)
        if accrual_ratio is not None:
            if accrual_ratio < 0:
                # Negative accruals are good
                accrual_adj = 0.5
            elif accrual_ratio < 0.05:
                # Low positive accruals
                accrual_adj = 0.3
            elif accrual_ratio < 0.10:
                # Moderate accruals
                accrual_adj = 0.0
            else:
                # High accruals
                accrual_adj = -0.5
        else:
            accrual_adj = 0.0
        
        # Cash conversion adjustment
        if cash_conversion is not None:
            if cash_conversion >= 1.2:
                cash_adj = 0.5
            elif cash_conversion >= 1.0:
                cash_adj = 0.3
            elif cash_conversion >= 0.8:
                cash_adj = 0.0
            else:
                cash_adj = -0.5
        else:
            cash_adj = 0.0
        
        # Calculate final score
        score = min(10.0, max(0.0, base_score + accrual_adj + cash_adj))
        
        # Debug logging for GOOGL optimization
        logger.info(f"Earnings Quality: F-Score={f_score}/9, Base={base_score:.1f}, "
                   f"Accrual={accrual_ratio:.3f}({accrual_adj:+.1f}), "
                   f"CashConv={cash_conversion:.2f}({cash_adj:+.1f}), Final={score:.1f}")
        
        return round(score, 1)
    
    def analyze(self, financial_data: Dict[str, float]) -> EarningsQualityResult:
        """
        Complete earnings quality analysis.
        
        Args:
            financial_data: Dictionary with financial metrics
            
        Returns:
            EarningsQualityResult with all metrics and red flags
        """
        # Check for missing/zero data - return 0.0 score if all critical fields are missing
        net_income = financial_data.get('net_income', 0)
        operating_cash_flow = financial_data.get('operating_cash_flow', 0)
        total_assets = financial_data.get('total_assets', 0)
        
        if (net_income == 0 and operating_cash_flow == 0 and total_assets == 0):
            logger.warning(f"Earnings quality: All critical fields are zero/missing, returning 0.0 score")
            return EarningsQualityResult(
                accrual_ratio=None,
                cash_conversion=None,
                f_score=0,
                f_score_breakdown={},
                earnings_quality_score=0.0,
                red_flags=[{'category': 'MISSING DATA', 'severity': 'CRITICAL', 
                            'description': 'All critical earnings fields are missing or zero'}],
                is_high_quality=False
            )
        
        # Calculate Accrual Ratio
        accrual_ratio = self.calculate_accrual_ratio(
            net_income=financial_data.get('net_income', 0),
            operating_cash_flow=financial_data.get('operating_cash_flow', 
                            financial_data.get('net_income', 0)),
            total_assets=financial_data.get('total_assets', 1),
            prior_total_assets=financial_data.get('prior_total_assets', 1)
        )
        
        # Calculate Cash Conversion
        cash_conversion = self.calculate_cash_conversion(
            operating_cash_flow=financial_data.get('operating_cash_flow',
                            financial_data.get('net_income', 0)),
            net_income=financial_data.get('net_income', 1)
        )
        
 # Check if FMP provides pre-calculated F-Score (more accurate)
        fmp_f_score = financial_data.get('piotroski_score_fmp')
        if fmp_f_score is not None:
            f_score = int(fmp_f_score)
            # Create a basic breakdown for compatibility
            breakdown = PiotroskiScoreBreakdown(
                f_roa=1 if f_score >= 6 else 0,  # Approximation
                f_cfo=1 if f_score >= 5 else 0,  # Approximation
                f_droa=1 if f_score >= 7 else 0,  # Approximation
                f_accrual=1 if f_score >= 6 else 0,  # Approximation
                f_dlever=1 if f_score >= 5 else 0,  # Approximation
                f_dliquid=1 if f_score >= 5 else 0,  # Approximation
                f_eq_offer=1 if f_score >= 6 else 0,  # Approximation
                f_dmargin=1 if f_score >= 7 else 0,  # Approximation
                f_dturn=1 if f_score >= 6 else 0   # Approximation
            )
            logger.info(f"Using FMP pre-calculated F-Score: {f_score}/9")
        else:
            # Fallback to calculation
            f_score, breakdown = self.calculate_piotroski_f_score(financial_data)
            logger.info(f"Calculated F-Score: {f_score}/9")
        
        # Convert breakdown to dict for serialization
        f_score_breakdown = {
            'f_roa': breakdown.f_roa,
            'f_cfo': breakdown.f_cfo,
            'f_droa': breakdown.f_droa,
            'f_accrual': breakdown.f_accrual,
            'f_dlever': breakdown.f_dlever,
            'f_dliquid': breakdown.f_dliquid,
            'f_eq_offer': breakdown.f_eq_offer,
            'f_dmargin': breakdown.f_dmargin,
            'f_dturn': breakdown.f_dturn
        }
        
        # Detect red flags
        red_flags = self.detect_earnings_red_flags(
            accrual_ratio=accrual_ratio,
            cash_conversion=cash_conversion,
            f_score=f_score
        )
        
        # Calculate overall score
        quality_score = self.calculate_earnings_quality_score(
            f_score=f_score,
            accrual_ratio=accrual_ratio,
            cash_conversion=cash_conversion
        )
        
        # Determine if high quality (score >= 7)
        is_high_quality = quality_score >= 7.0
        
        logger.info(
            f"Earnings quality analysis: F-Score={f_score}/9, "
            f"Quality Score={quality_score}/10, "
            f"Red Flags={len(red_flags)}"
        )
        
        return EarningsQualityResult(
            accrual_ratio=accrual_ratio,
            cash_conversion=cash_conversion,
            f_score=f_score,
            f_score_breakdown=f_score_breakdown,
            earnings_quality_score=quality_score,
            red_flags=red_flags,
            is_high_quality=is_high_quality
        )


def get_earnings_quality_analyzer() -> EarningsQualityAnalyzer:
    """Factory function to get an EarningsQualityAnalyzer instance."""
    return EarningsQualityAnalyzer()


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example financial data
    data = {
        'ticker': 'AAPL',
        # Current year
        'net_income': 99_803_000_000,
        'operating_cash_flow': 111_443_000_000,
        'total_assets': 352_755_000_000,
        'shareholder_equity': 62_146_000_000,
        'current_assets': 143_566_000_000,
        'current_liabilities': 105_392_000_000,
        'total_debt': 111_088_000_000,
        'shares_outstanding': 15_700_000_000,
        'revenue': 394_328_000_000,
        'cogs': 223_546_000_000,
        # Prior year
        'prior_net_income': 99_803_000_000 * 0.9,
        'prior_operating_cash_flow': 111_443_000_000 * 0.85,
        'prior_total_assets': 352_755_000_000 * 0.9,
        'prior_shareholder_equity': 62_146_000_000 * 0.85,
        'prior_current_assets': 143_566_000_000 * 0.85,
        'prior_current_liabilities': 105_392_000_000 * 0.9,
        'prior_total_debt': 111_088_000_000 * 0.95,
        'prior_shares_outstanding': 15_800_000_000,
        'prior_revenue': 383_285_000_000,
        'prior_cogs': 214_137_000_000
    }
    
    # Run analysis
    analyzer = EarningsQualityAnalyzer()
    result = analyzer.analyze(data)
    
    print("=" * 60)
    print("EARNINGS QUALITY ANALYSIS")
    print("=" * 60)
    print(f"Accrual Ratio: {result.accrual_ratio:.4f} ({result.accrual_ratio*100:.2f}%)" 
          if result.accrual_ratio else "Accrual Ratio: N/A")
    print(f"Cash Conversion: {result.cash_conversion:.2f}x" 
          if result.cash_conversion else "Cash Conversion: N/A")
    print(f"F-Score: {result.f_score}/9")
    print(f"Quality Score: {result.earnings_quality_score}/10")
    print(f"High Quality: {result.is_high_quality}")
    
    if result.red_flags:
        print("\nRED FLAGS:")
        for rf in result.red_flags:
            print(f"  [{rf['severity']}] {rf['category']}: {rf['description'][:80]}...")
    
    print("=" * 60)
