"""
Quality Persistence Analyzer

Identifies "quality compounders" - companies that sustain high quality metrics over time.
Analyzes historical financial data to distinguish truly durable businesses from
one-time performers or cyclical companies.

Key Features:
- Multi-year persistence tracking (ROE, margins, ROIC, FCF)
- Company classification (Compounder/Improver/Deteriorator/Inconsistent)
- Trend analysis and mean reversion risk assessment
- Compounder confidence scoring
- Visualization of quality metrics over time
- LLM prompt generation based on persistence patterns

Author: Trading System
Date: 2025-10-30
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
from scipy import stats
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# Import existing quality system
from quality.quality_metrics_calculator import QualityMetricsCalculator
from quality.quality_llm_prompts import QualityLLMPromptGenerator

# Import market cap classifier for tier-based analysis
from quality.market_cap_classifier import MarketCapTier, MarketCapClassifier

# Configure logging
logger = logging.getLogger(__name__)


class PersistenceClassification(Enum):
    """Company quality persistence classification."""
    QUALITY_COMPOUNDER = "Quality Compounder"      # Sustained excellence
    QUALITY_IMPROVER = "Quality Improver"          # Improving trends
    QUALITY_DETERIORATOR = "Quality Deteriorator"  # Declining quality
    INCONSISTENT = "Inconsistent"                  # Cyclical/volatile
    INSUFFICIENT_DATA = "Insufficient Data"        # Not enough history


@dataclass
class PersistenceMetrics:
    """Historical persistence metrics for a company."""
    ticker: str
    years_analyzed: int
    start_year: int
    end_year: int

    # ROE metrics
    roe_mean: float
    roe_std: float
    roe_cv: float  # Coefficient of variation
    roe_trend_slope: float
    roe_years_above_15pct: int
    roe_consistency_score: float  # 0-10

    # Margin metrics
    gross_margin_mean: float
    gross_margin_std: float
    gross_margin_trend_slope: float
    operating_margin_mean: float
    operating_margin_std: float
    operating_margin_trend_slope: float

    # ROIC metrics
    roic_mean: float
    roic_std: float
    roic_trend_slope: float
    roic_years_above_15pct: int

    # FCF metrics
    fcf_conversion_mean: float  # FCF / Net Income
    fcf_conversion_std: float
    fcf_positive_years: int

    # Overall scores
    persistence_score: float  # 0-100
    consistency_score: float  # 0-100
    trend_score: float       # -100 to +100 (negative = deteriorating)

    # Recent vs historical
    recent_3yr_roe_mean: Optional[float]
    recent_vs_historical_roe: Optional[float]  # Recent - Historical
    mean_reversion_risk: str  # Low/Medium/High

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'ticker': self.ticker,
            'years_analyzed': self.years_analyzed,
            'period': f"{self.start_year}-{self.end_year}",
            'roe': {
                'mean': self.roe_mean,
                'std': self.roe_std,
                'cv': self.roe_cv,
                'trend_slope': self.roe_trend_slope,
                'years_above_15pct': self.roe_years_above_15pct,
                'consistency_score': self.roe_consistency_score
            },
            'margins': {
                'gross_margin_mean': self.gross_margin_mean,
                'operating_margin_mean': self.operating_margin_mean
            },
            'roic': {
                'mean': self.roic_mean,
                'years_above_15pct': self.roic_years_above_15pct
            },
            'fcf': {
                'conversion_mean': self.fcf_conversion_mean,
                'positive_years': self.fcf_positive_years
            },
            'scores': {
                'persistence': self.persistence_score,
                'consistency': self.consistency_score,
                'trend': self.trend_score
            },
            'mean_reversion_risk': self.mean_reversion_risk
        }


@dataclass
class PersistenceAnalysisResult:
    """Complete persistence analysis result."""
    ticker: str
    classification: PersistenceClassification
    compounder_confidence: float  # 0-100
    persistence_metrics: PersistenceMetrics
    trend_analysis: Dict[str, Any]
    key_insights: List[str]
    warnings: List[str]
    llm_prompt: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'ticker': self.ticker,
            'classification': self.classification.value,
            'compounder_confidence': self.compounder_confidence,
            'persistence_metrics': self.persistence_metrics.to_dict(),
            'trend_analysis': self.trend_analysis,
            'key_insights': self.key_insights,
            'warnings': self.warnings
        }


@dataclass
class TierEligibility:
    """
    Tier eligibility assessment combining market cap and ROE persistence.

    Used to validate if a holding meets tier-specific requirements from
    quality_investing_thresholds_research.md:
    - Large Cap ($50B+): 5+ years ROE >15%
    - Mid Cap ($2B-$50B): 2-3 years ROE >15% + incremental ROCE advantage
    - Small Cap ($500M-$2B): 6-8 quarters positive ROE trend + strict quality filters
    """
    ticker: str
    market_cap: Optional[float]
    market_cap_tier: Optional[MarketCapTier]
    meets_roe_persistence: bool
    roe_persistence_years: float  # Actual years/quarters meeting threshold
    incremental_roce_advantage: Optional[float]  # % advantage (for mid-cap)
    reasoning: str
    validation_date: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'ticker': self.ticker,
            'market_cap': self.market_cap,
            'market_cap_tier': self.market_cap_tier.value if self.market_cap_tier else None,
            'meets_roe_persistence': self.meets_roe_persistence,
            'roe_persistence_years': self.roe_persistence_years,
            'incremental_roce_advantage': self.incremental_roce_advantage,
            'reasoning': self.reasoning,
            'validation_date': self.validation_date
        }


class QualityPersistenceAnalyzer:
    """
    Analyzes quality metric persistence over time to identify durable businesses.

    Focus on identifying "quality compounders" - companies that consistently
    deliver high returns over many years, not just current snapshot winners.

    Example:
        >>> analyzer = QualityPersistenceAnalyzer()
        >>>
        >>> # Historical data as DataFrame
        >>> df = pd.DataFrame({
        ...     'year': [2019, 2020, 2021, 2022, 2023],
        ...     'ticker': ['AAPL'] * 5,
        ...     'revenue': [260_000e6, 275_000e6, 366_000e6, 394_000e6, 383_000e6],
        ...     'net_income': [55_000e6, 57_000e6, 95_000e6, 100_000e6, 97_000e6],
        ...     'shareholder_equity': [90_000e6, 65_000e6, 63_000e6, 50_000e6, 62_000e6],
        ...     # ... other fields
        ... })
        >>>
        >>> result = analyzer.analyze_company(df)
        >>> print(f"{result.classification.value}: {result.compounder_confidence:.1f}% confidence")
    """

    # Minimum data requirements
    MIN_YEARS_REQUIRED = 3
    PREFERRED_YEARS = 5
    IDEAL_YEARS = 10

    # Thresholds for quality compounders
    COMPOUNDER_ROE_THRESHOLD = 0.15  # 15% minimum average ROE
    COMPOUNDER_ROIC_THRESHOLD = 0.15  # 15% minimum average ROIC
    COMPOUNDER_CONSISTENCY_THRESHOLD = 70  # Minimum consistency score

    # Trend thresholds
    STRONG_POSITIVE_TREND = 0.02  # 2% improvement per year
    WEAK_POSITIVE_TREND = 0.005   # 0.5% improvement per year
    WEAK_NEGATIVE_TREND = -0.005  # -0.5% decline per year
    STRONG_NEGATIVE_TREND = -0.02 # -2% decline per year

    def __init__(self):
        """Initialize the persistence analyzer."""
        self.calculator = QualityMetricsCalculator()
        self.prompt_generator = QualityLLMPromptGenerator()
        logger.info("QualityPersistenceAnalyzer initialized")

    def analyze_company(
        self,
        historical_data: pd.DataFrame,
        ticker: Optional[str] = None,
        generate_llm_prompt: bool = False
    ) -> PersistenceAnalysisResult:
        """
        Analyze quality persistence for a single company.

        Args:
            historical_data: DataFrame with columns:
                - year (int): Year of data
                - ticker (str): Stock ticker (optional if ticker param provided)
                - revenue, cogs, sga, total_assets, net_income,
                  shareholder_equity, free_cash_flow, total_debt, nopat
            ticker: Override ticker (if not in DataFrame)
            generate_llm_prompt: Whether to generate LLM analysis prompt

        Returns:
            PersistenceAnalysisResult with classification and metrics
        """
        # Extract ticker
        if ticker is None:
            if 'ticker' not in historical_data.columns:
                raise ValueError("ticker must be provided as parameter or in DataFrame")
            ticker = historical_data['ticker'].iloc[0]

        logger.info(f"Analyzing quality persistence for {ticker} "
                   f"({len(historical_data)} years of data)")

        # Validate data
        self._validate_data(historical_data)

        # Calculate persistence metrics
        persistence_metrics = self.calculate_persistence_metrics(historical_data, ticker)

        # Classify company
        classification, confidence = self.classify_company(persistence_metrics)

        # Analyze trends
        trend_analysis = self.analyze_quality_trends(historical_data, persistence_metrics)

        # Generate insights and warnings
        insights = self._generate_insights(persistence_metrics, classification, trend_analysis)
        warnings = self._generate_warnings(persistence_metrics, trend_analysis)

        # Generate LLM prompt if requested
        llm_prompt = None
        if generate_llm_prompt:
            llm_prompt = self.generate_persistence_analysis_prompt(
                persistence_metrics,
                classification,
                trend_analysis
            )

        result = PersistenceAnalysisResult(
            ticker=ticker,
            classification=classification,
            compounder_confidence=confidence,
            persistence_metrics=persistence_metrics,
            trend_analysis=trend_analysis,
            key_insights=insights,
            warnings=warnings,
            llm_prompt=llm_prompt
        )

        logger.info(f"{ticker}: {classification.value} ({confidence:.1f}% confidence)")
        return result

    def calculate_persistence_metrics(
        self,
        historical_data: pd.DataFrame,
        ticker: str
    ) -> PersistenceMetrics:
        """
        Calculate persistence metrics from historical data.

        Args:
            historical_data: DataFrame with annual financial data
            ticker: Stock ticker symbol

        Returns:
            PersistenceMetrics object
        """
        df = historical_data.sort_values('year').copy()
        years = len(df)

        # Calculate annual metrics
        df['roe'] = df['net_income'] / df['shareholder_equity']
        df['gross_margin'] = (df['revenue'] - df['cogs']) / df['revenue']
        df['operating_margin'] = (df['revenue'] - df['cogs'] - df['sga']) / df['revenue']
        df['roic'] = df['nopat'] / (df['total_debt'] + df['shareholder_equity'])
        df['fcf_conversion'] = df['free_cash_flow'] / df['net_income'].replace(0, np.nan)

        # ROE metrics
        roe_mean = df['roe'].mean()
        roe_std = df['roe'].std()
        roe_cv = roe_std / abs(roe_mean) if roe_mean != 0 else np.inf
        roe_years_above_15 = (df['roe'] > 0.15).sum()

        # Calculate ROE trend
        years_numeric = np.arange(years)
        roe_slope, _, _, _, _ = stats.linregress(years_numeric, df['roe'])

        # ROE consistency score (0-10)
        roe_consistency = self._calculate_consistency_score(
            df['roe'],
            threshold=0.15,
            cv=roe_cv
        )

        # Margin metrics
        gross_margin_mean = df['gross_margin'].mean()
        gross_margin_std = df['gross_margin'].std()
        operating_margin_mean = df['operating_margin'].mean()
        operating_margin_std = df['operating_margin'].std()

        # Margin trends
        gm_slope, _, _, _, _ = stats.linregress(years_numeric, df['gross_margin'])
        om_slope, _, _, _, _ = stats.linregress(years_numeric, df['operating_margin'])

        # ROIC metrics
        roic_mean = df['roic'].mean()
        roic_std = df['roic'].std()
        roic_slope, _, _, _, _ = stats.linregress(years_numeric, df['roic'])
        roic_years_above_15 = (df['roic'] > 0.15).sum()

        # FCF metrics
        fcf_conversion_mean = df['fcf_conversion'].mean()
        fcf_conversion_std = df['fcf_conversion'].std()
        fcf_positive_years = (df['free_cash_flow'] > 0).sum()

        # Overall scores
        persistence_score = self._calculate_persistence_score(
            roe_mean, roe_years_above_15, roic_mean, years
        )
        consistency_score = self._calculate_overall_consistency(
            roe_cv, gross_margin_std, roic_std
        )
        trend_score = self._calculate_trend_score(
            roe_slope, gm_slope, om_slope, roic_slope
        )

        # Recent vs historical
        recent_3yr_roe = None
        recent_vs_historical = None
        if years >= 5:
            recent_3yr_roe = df['roe'].tail(3).mean()
            historical_roe = df['roe'].head(years - 3).mean()
            recent_vs_historical = recent_3yr_roe - historical_roe

        # Mean reversion risk
        mean_reversion_risk = self._assess_mean_reversion_risk(
            roe_mean, recent_vs_historical, roe_cv
        )

        return PersistenceMetrics(
            ticker=ticker,
            years_analyzed=years,
            start_year=int(df['year'].min()),
            end_year=int(df['year'].max()),
            roe_mean=roe_mean,
            roe_std=roe_std,
            roe_cv=roe_cv,
            roe_trend_slope=roe_slope,
            roe_years_above_15pct=roe_years_above_15,
            roe_consistency_score=roe_consistency,
            gross_margin_mean=gross_margin_mean,
            gross_margin_std=gross_margin_std,
            gross_margin_trend_slope=gm_slope,
            operating_margin_mean=operating_margin_mean,
            operating_margin_std=operating_margin_std,
            operating_margin_trend_slope=om_slope,
            roic_mean=roic_mean,
            roic_std=roic_std,
            roic_trend_slope=roic_slope,
            roic_years_above_15pct=roic_years_above_15,
            fcf_conversion_mean=fcf_conversion_mean,
            fcf_conversion_std=fcf_conversion_std,
            fcf_positive_years=fcf_positive_years,
            persistence_score=persistence_score,
            consistency_score=consistency_score,
            trend_score=trend_score,
            recent_3yr_roe_mean=recent_3yr_roe,
            recent_vs_historical_roe=recent_vs_historical,
            mean_reversion_risk=mean_reversion_risk
        )

    def classify_company(
        self,
        metrics: PersistenceMetrics
    ) -> Tuple[PersistenceClassification, float]:
        """
        Classify company based on persistence metrics.

        Args:
            metrics: PersistenceMetrics object

        Returns:
            Tuple of (classification, confidence_score)
        """
        # Check minimum data requirement
        if metrics.years_analyzed < self.MIN_YEARS_REQUIRED:
            return PersistenceClassification.INSUFFICIENT_DATA, 0.0

        # Quality Compounder criteria:
        # 1. High average ROE (>15%)
        # 2. High consistency (low CV, high % years above threshold)
        # 3. Stable or improving trends
        # 4. High ROIC

        is_high_roe = metrics.roe_mean >= self.COMPOUNDER_ROE_THRESHOLD
        is_high_roic = metrics.roic_mean >= self.COMPOUNDER_ROIC_THRESHOLD
        is_consistent = metrics.consistency_score >= self.COMPOUNDER_CONSISTENCY_THRESHOLD
        is_stable_trend = metrics.trend_score >= -10  # Not declining significantly

        # Calculate confidence based on data quality and metrics
        data_quality_factor = min(1.0, metrics.years_analyzed / self.IDEAL_YEARS)

        # Quality Compounder
        if is_high_roe and is_high_roic and is_consistent and is_stable_trend:
            # Strong compounder if improving trend
            if metrics.trend_score > 20:
                confidence = 85 + (15 * data_quality_factor)
            else:
                confidence = 70 + (15 * data_quality_factor)

            # Bonus for very consistent performance
            if metrics.roe_years_above_15pct == metrics.years_analyzed:
                confidence = min(100, confidence + 10)

            return PersistenceClassification.QUALITY_COMPOUNDER, confidence

        # Quality Improver
        # Strong positive trend, even if starting from lower base
        if metrics.trend_score > 30 and metrics.roe_trend_slope > self.STRONG_POSITIVE_TREND:
            # Check if recent performance is strong
            if metrics.recent_3yr_roe_mean and metrics.recent_3yr_roe_mean > 0.12:
                confidence = 65 + (20 * data_quality_factor)
                return PersistenceClassification.QUALITY_IMPROVER, confidence

        # Quality Deteriorator
        # Declining trends, especially from high base
        if metrics.trend_score < -20 or metrics.roe_trend_slope < self.STRONG_NEGATIVE_TREND:
            confidence = 60 + (15 * data_quality_factor)
            return PersistenceClassification.QUALITY_DETERIORATOR, confidence

        # Inconsistent/Cyclical
        # High volatility, no clear trend
        if metrics.roe_cv > 0.5 or metrics.consistency_score < 40:
            confidence = 55 + (15 * data_quality_factor)
            return PersistenceClassification.INCONSISTENT, confidence

        # Default: Moderate quality, but not clear compounder
        # Could be decent company, just not meeting compounder criteria
        if is_high_roe or is_high_roic:
            confidence = 45 + (10 * data_quality_factor)
            return PersistenceClassification.INCONSISTENT, confidence

        # Low quality
        confidence = 35 + (10 * data_quality_factor)
        return PersistenceClassification.INCONSISTENT, confidence

    def analyze_quality_trends(
        self,
        historical_data: pd.DataFrame,
        metrics: PersistenceMetrics
    ) -> Dict[str, Any]:
        """
        Analyze quality metric trends and drivers.

        Args:
            historical_data: DataFrame with annual data
            metrics: PersistenceMetrics object

        Returns:
            Dictionary with trend analysis
        """
        df = historical_data.sort_values('year').copy()

        # Calculate year-over-year changes
        df['revenue_growth'] = df['revenue'].pct_change()
        df['asset_growth'] = df['total_assets'].pct_change()
        df['debt_growth'] = df['total_debt'].pct_change()

        analysis = {
            'overall_trend_direction': self._describe_trend(metrics.trend_score),
            'roe_trend': self._describe_metric_trend(metrics.roe_trend_slope, 'ROE'),
            'margin_trend': {
                'gross': self._describe_metric_trend(metrics.gross_margin_trend_slope, 'Gross Margin'),
                'operating': self._describe_metric_trend(metrics.operating_margin_trend_slope, 'Operating Margin')
            },
            'roic_trend': self._describe_metric_trend(metrics.roic_trend_slope, 'ROIC'),

            # Trend drivers
            'avg_revenue_growth': df['revenue_growth'].mean() if 'revenue_growth' in df else None,
            'avg_asset_growth': df['asset_growth'].mean() if 'asset_growth' in df else None,

            # Stability metrics
            'roe_range': {
                'min': df['roe'].min() if 'roe' in df else None,
                'max': df['roe'].max() if 'roe' in df else None,
                'range': df['roe'].max() - df['roe'].min() if 'roe' in df else None
            },

            # Recent performance
            'recent_acceleration': self._detect_acceleration(df) if len(df) >= 5 else None,
            'recent_vs_historical': metrics.recent_vs_historical_roe,

            # Mean reversion analysis
            'mean_reversion_risk': metrics.mean_reversion_risk,
            'roe_vs_industry_proxy': self._estimate_industry_comparison(metrics.roe_mean)
        }

        return analysis

    def generate_persistence_analysis_prompt(
        self,
        metrics: PersistenceMetrics,
        classification: PersistenceClassification,
        trend_analysis: Dict[str, Any]
    ) -> str:
        """
        Generate targeted LLM prompt based on persistence classification.

        Args:
            metrics: PersistenceMetrics object
            classification: Company classification
            trend_analysis: Trend analysis results

        Returns:
            Optimized LLM prompt string
        """
        sections = []

        # Role definition (varies by classification)
        if classification == PersistenceClassification.QUALITY_COMPOUNDER:
            sections.append(
                "You are analyzing a potential quality compounder - "
                "a company with sustained high returns over many years."
            )
        elif classification == PersistenceClassification.QUALITY_IMPROVER:
            sections.append(
                "You are analyzing a quality improver - "
                "a company showing improving quality metrics over time."
            )
        elif classification == PersistenceClassification.QUALITY_DETERIORATOR:
            sections.append(
                "You are analyzing a deteriorating business - "
                "quality metrics are declining over time."
            )
        else:
            sections.append(
                "You are analyzing a company with inconsistent quality metrics."
            )

        # Historical performance summary
        sections.append(
            f"\nCompany: {metrics.ticker}\n"
            f"Analysis Period: {metrics.start_year}-{metrics.end_year} ({metrics.years_analyzed} years)\n"
            f"Classification: {classification.value}"
        )

        # Key metrics
        sections.append(
            f"\nHistorical Quality Metrics:\n"
            f"- Average ROE: {metrics.roe_mean:.1%} (years >15%: {metrics.roe_years_above_15pct}/{metrics.years_analyzed})\n"
            f"- ROE Volatility: {metrics.roe_cv:.2f} (lower = more consistent)\n"
            f"- Average ROIC: {metrics.roic_mean:.1%}\n"
            f"- Avg Gross Margin: {metrics.gross_margin_mean:.1%}\n"
            f"- FCF Conversion: {metrics.fcf_conversion_mean:.1f}x (FCF/NI)"
        )

        # Trend information
        sections.append(
            f"\nTrends:\n"
            f"- ROE Trend: {trend_analysis['roe_trend']}\n"
            f"- Margin Trend: {trend_analysis['margin_trend']['gross']}\n"
            f"- Overall Trend Score: {metrics.trend_score:.0f}/100"
        )

        # Recent vs historical
        if metrics.recent_vs_historical_roe is not None:
            sections.append(
                f"\nRecent vs Historical:\n"
                f"- Recent 3yr ROE: {metrics.recent_3yr_roe_mean:.1%}\n"
                f"- Change vs Historical: {metrics.recent_vs_historical_roe:+.1%}\n"
                f"- Mean Reversion Risk: {metrics.mean_reversion_risk}"
            )

        # Targeted questions based on classification
        if classification == PersistenceClassification.QUALITY_COMPOUNDER:
            sections.append(
                "\nAnalysis Focus:\n"
                "1. What competitive advantages sustain these high returns?\n"
                "2. Is the moat widening or narrowing?\n"
                "3. Any signs of saturation or margin pressure?\n"
                "4. Can these returns persist for another 5-10 years?"
            )
        elif classification == PersistenceClassification.QUALITY_IMPROVER:
            sections.append(
                "\nAnalysis Focus:\n"
                "1. What's driving the improvement (scale, efficiency, pricing)?\n"
                "2. Is improvement sustainable or cyclical?\n"
                "3. How much more room for improvement?\n"
                "4. When will ROE/margins peak?"
            )
        elif classification == PersistenceClassification.QUALITY_DETERIORATOR:
            sections.append(
                "\nAnalysis Focus:\n"
                "1. What's causing the decline (competition, disruption, execution)?\n"
                "2. Is this reversible or structural?\n"
                "3. Has management acknowledged the issues?\n"
                "4. Any turnaround catalysts?"
            )
        else:
            sections.append(
                "\nAnalysis Focus:\n"
                "1. What causes the volatility (cyclical industry, poor execution)?\n"
                "2. Is there an underlying trend beneath the noise?\n"
                "3. Should we avoid or wait for clearer signals?"
            )

        # Output format
        sections.append(
            "\nProvide:\n"
            "PERSISTENCE ASSESSMENT: Durable/Improving/Deteriorating/Cyclical\n"
            "COMPETITIVE MOAT: [width and direction]\n"
            "KEY DRIVERS: [2-3 main factors]\n"
            "RISKS TO THESIS: [2-3 key risks]\n"
            "VERDICT: [50 words on sustainability]\n"
            "CONFIDENCE: High/Medium/Low"
        )

        prompt = "\n".join(sections)

        # Estimate tokens
        estimated_tokens = len(prompt) // 4
        logger.info(f"Generated persistence analysis prompt: ~{estimated_tokens} tokens")

        return prompt

    def visualize_persistence(
        self,
        historical_data: pd.DataFrame,
        ticker: str,
        save_path: Optional[str] = None,
        show_plot: bool = True
    ) -> None:
        """
        Visualize quality metrics over time.

        Args:
            historical_data: DataFrame with annual data
            ticker: Stock ticker
            save_path: Optional path to save figure
            show_plot: Whether to display plot
        """
        df = historical_data.sort_values('year').copy()

        # Calculate metrics
        df['roe'] = df['net_income'] / df['shareholder_equity']
        df['gross_margin'] = (df['revenue'] - df['cogs']) / df['revenue']
        df['operating_margin'] = (df['revenue'] - df['cogs'] - df['sga']) / df['revenue']
        df['roic'] = df['nopat'] / (df['total_debt'] + df['shareholder_equity'])
        df['fcf_conversion'] = df['free_cash_flow'] / df['net_income'].replace(0, np.nan)

        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'{ticker} - Quality Persistence Analysis', fontsize=16, fontweight='bold')

        # Plot 1: ROE over time
        ax1 = axes[0, 0]
        ax1.plot(df['year'], df['roe'] * 100, marker='o', linewidth=2, markersize=8, label='ROE')
        ax1.axhline(y=15, color='g', linestyle='--', alpha=0.5, label='15% Threshold')
        ax1.fill_between(df['year'], 0, df['roe'] * 100, alpha=0.2)
        ax1.set_xlabel('Year', fontweight='bold')
        ax1.set_ylabel('ROE (%)', fontweight='bold')
        ax1.set_title('Return on Equity', fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Margins over time
        ax2 = axes[0, 1]
        ax2.plot(df['year'], df['gross_margin'] * 100, marker='s', linewidth=2, label='Gross Margin')
        ax2.plot(df['year'], df['operating_margin'] * 100, marker='^', linewidth=2, label='Operating Margin')
        ax2.set_xlabel('Year', fontweight='bold')
        ax2.set_ylabel('Margin (%)', fontweight='bold')
        ax2.set_title('Profitability Margins', fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Plot 3: ROIC over time
        ax3 = axes[1, 0]
        ax3.plot(df['year'], df['roic'] * 100, marker='D', linewidth=2, markersize=8, color='orange', label='ROIC')
        ax3.axhline(y=15, color='g', linestyle='--', alpha=0.5, label='15% Threshold')
        ax3.fill_between(df['year'], 0, df['roic'] * 100, alpha=0.2, color='orange')
        ax3.set_xlabel('Year', fontweight='bold')
        ax3.set_ylabel('ROIC (%)', fontweight='bold')
        ax3.set_title('Return on Invested Capital', fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Plot 4: FCF Conversion
        ax4 = axes[1, 1]
        colors = ['green' if x > 1.0 else 'orange' if x > 0 else 'red' for x in df['fcf_conversion']]
        ax4.bar(df['year'], df['fcf_conversion'], color=colors, alpha=0.7)
        ax4.axhline(y=1.0, color='g', linestyle='--', alpha=0.5, label='1.0x (FCF = NI)')
        ax4.set_xlabel('Year', fontweight='bold')
        ax4.set_ylabel('FCF / Net Income', fontweight='bold')
        ax4.set_title('Free Cash Flow Conversion', fontweight='bold')
        ax4.legend()
        ax4.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Saved persistence visualization to {save_path}")

        if show_plot:
            plt.show()
        else:
            plt.close()

    def analyze_universe(
        self,
        universe_data: Dict[str, pd.DataFrame],
        min_compounder_confidence: float = 70.0
    ) -> pd.DataFrame:
        """
        Batch analyze multiple companies and rank by compounder quality.

        Args:
            universe_data: Dict mapping tickers to historical DataFrames
            min_compounder_confidence: Minimum confidence for compounder classification

        Returns:
            DataFrame with ranked companies and key metrics
        """
        logger.info(f"Analyzing universe of {len(universe_data)} companies")

        results = []
        for ticker, df in universe_data.items():
            try:
                analysis = self.analyze_company(df, ticker=ticker)
                results.append({
                    'ticker': ticker,
                    'classification': analysis.classification.value,
                    'compounder_confidence': analysis.compounder_confidence,
                    'persistence_score': analysis.persistence_metrics.persistence_score,
                    'consistency_score': analysis.persistence_metrics.consistency_score,
                    'trend_score': analysis.persistence_metrics.trend_score,
                    'avg_roe': analysis.persistence_metrics.roe_mean,
                    'avg_roic': analysis.persistence_metrics.roic_mean,
                    'years_data': analysis.persistence_metrics.years_analyzed,
                    'roe_consistency': analysis.persistence_metrics.roe_consistency_score,
                    'mean_reversion_risk': analysis.persistence_metrics.mean_reversion_risk
                })
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
                continue

        # Create DataFrame and sort
        df_results = pd.DataFrame(results)

        # Rank by compounder confidence
        df_results = df_results.sort_values('compounder_confidence', ascending=False)

        # Filter compounders
        df_compounders = df_results[
            df_results['compounder_confidence'] >= min_compounder_confidence
        ].copy()

        logger.info(
            f"Universe analysis complete: {len(df_compounders)} quality compounders "
            f"found (confidence ≥{min_compounder_confidence}%)"
        )

        return df_results

    # Helper methods

    def _validate_data(self, df: pd.DataFrame) -> None:
        """Validate historical data format."""
        required_cols = [
            'year', 'revenue', 'cogs', 'sga', 'total_assets', 'net_income',
            'shareholder_equity', 'free_cash_flow', 'total_debt', 'nopat'
        ]

        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        if len(df) < self.MIN_YEARS_REQUIRED:
            raise ValueError(
                f"Insufficient data: {len(df)} years (minimum: {self.MIN_YEARS_REQUIRED})"
            )

    def _calculate_consistency_score(
        self,
        series: pd.Series,
        threshold: float,
        cv: float
    ) -> float:
        """Calculate consistency score (0-10) for a metric."""
        # Component 1: % of years above threshold (0-5 points)
        pct_above = (series > threshold).sum() / len(series)
        threshold_score = pct_above * 5

        # Component 2: Low coefficient of variation (0-5 points)
        # CV < 0.2 = 5 points, CV > 1.0 = 0 points
        if cv < 0.2:
            cv_score = 5.0
        elif cv > 1.0:
            cv_score = 0.0
        else:
            cv_score = 5.0 * (1.0 - ((cv - 0.2) / 0.8))

        return threshold_score + cv_score

    def _calculate_persistence_score(
        self,
        roe_mean: float,
        roe_years_above_15: int,
        roic_mean: float,
        total_years: int
    ) -> float:
        """Calculate overall persistence score (0-100)."""
        # Component 1: Average ROE level (0-40 points)
        if roe_mean >= 0.25:
            roe_score = 40
        elif roe_mean >= 0.15:
            roe_score = 20 + ((roe_mean - 0.15) / 0.10) * 20
        else:
            roe_score = max(0, (roe_mean / 0.15) * 20)

        # Component 2: Consistency (0-30 points)
        consistency = (roe_years_above_15 / total_years) * 30

        # Component 3: ROIC (0-30 points)
        if roic_mean >= 0.20:
            roic_score = 30
        elif roic_mean >= 0.15:
            roic_score = 15 + ((roic_mean - 0.15) / 0.05) * 15
        else:
            roic_score = max(0, (roic_mean / 0.15) * 15)

        return roe_score + consistency + roic_score

    def _calculate_overall_consistency(
        self,
        roe_cv: float,
        gm_std: float,
        roic_std: float
    ) -> float:
        """Calculate overall consistency score (0-100)."""
        # Lower CV/std = higher score

        # ROE consistency (40% weight)
        if roe_cv < 0.2:
            roe_score = 40
        elif roe_cv < 0.5:
            roe_score = 40 * (0.5 - roe_cv) / 0.3
        else:
            roe_score = 0

        # Margin consistency (30% weight)
        if gm_std < 0.03:
            gm_score = 30
        elif gm_std < 0.10:
            gm_score = 30 * (0.10 - gm_std) / 0.07
        else:
            gm_score = 0

        # ROIC consistency (30% weight)
        if roic_std < 0.05:
            roic_score = 30
        elif roic_std < 0.15:
            roic_score = 30 * (0.15 - roic_std) / 0.10
        else:
            roic_score = 0

        return roe_score + gm_score + roic_score

    def _calculate_trend_score(
        self,
        roe_slope: float,
        gm_slope: float,
        om_slope: float,
        roic_slope: float
    ) -> float:
        """Calculate trend score (-100 to +100)."""
        # Positive slope = positive score

        def slope_to_score(slope: float, weight: float) -> float:
            if slope > self.STRONG_POSITIVE_TREND:
                return weight
            elif slope > self.WEAK_POSITIVE_TREND:
                return weight * 0.5
            elif slope > self.WEAK_NEGATIVE_TREND:
                return 0
            elif slope > self.STRONG_NEGATIVE_TREND:
                return -weight * 0.5
            else:
                return -weight

        roe_score = slope_to_score(roe_slope, 40)
        gm_score = slope_to_score(gm_slope, 20)
        om_score = slope_to_score(om_slope, 20)
        roic_score = slope_to_score(roic_slope, 20)

        return roe_score + gm_score + om_score + roic_score

    def _assess_mean_reversion_risk(
        self,
        roe_mean: float,
        recent_vs_historical: Optional[float],
        roe_cv: float
    ) -> str:
        """Assess mean reversion risk."""
        # High ROE + Recent outperformance + Low volatility = Higher mean reversion risk

        if roe_mean < 0.15:
            return "Low"  # Already below-average, less room to revert

        if recent_vs_historical is None:
            return "Medium"  # Unknown

        # High recent outperformance
        if recent_vs_historical > 0.05 and roe_mean > 0.25:
            return "High"

        # Moderate outperformance
        if recent_vs_historical > 0.02:
            return "Medium"

        # Consistent performance
        if abs(recent_vs_historical) < 0.02 and roe_cv < 0.3:
            return "Low"

        return "Medium"

    def _describe_trend(self, trend_score: float) -> str:
        """Convert trend score to description."""
        if trend_score > 50:
            return "Strong Improvement"
        elif trend_score > 20:
            return "Moderate Improvement"
        elif trend_score > -20:
            return "Stable"
        elif trend_score > -50:
            return "Moderate Decline"
        else:
            return "Significant Decline"

    def _describe_metric_trend(self, slope: float, metric_name: str) -> str:
        """Describe metric trend from slope."""
        if slope > self.STRONG_POSITIVE_TREND:
            return f"{metric_name} improving strongly (+{slope*100:.1f}% per year)"
        elif slope > self.WEAK_POSITIVE_TREND:
            return f"{metric_name} improving modestly (+{slope*100:.1f}% per year)"
        elif slope > self.WEAK_NEGATIVE_TREND:
            return f"{metric_name} stable ({slope*100:+.1f}% per year)"
        elif slope > self.STRONG_NEGATIVE_TREND:
            return f"{metric_name} declining modestly ({slope*100:.1f}% per year)"
        else:
            return f"{metric_name} declining significantly ({slope*100:.1f}% per year)"

    def _detect_acceleration(self, df: pd.DataFrame) -> str:
        """Detect if metrics are accelerating or decelerating recently."""
        if len(df) < 5:
            return "Insufficient data"

        # Compare recent 2 years vs prior 3 years
        recent_2yr = df.tail(2)
        prior_3yr = df.head(len(df) - 2).tail(3)

        recent_roe = recent_2yr['roe'].mean() if 'roe' in recent_2yr else 0
        prior_roe = prior_3yr['roe'].mean() if 'roe' in prior_3yr else 0

        change = recent_roe - prior_roe

        if change > 0.03:
            return "Accelerating"
        elif change < -0.03:
            return "Decelerating"
        else:
            return "Stable"

    def _estimate_industry_comparison(self, roe_mean: float) -> str:
        """Rough industry comparison (without actual industry data)."""
        # Very rough benchmarks
        if roe_mean > 0.25:
            return "Well above average (top quartile)"
        elif roe_mean > 0.15:
            return "Above average"
        elif roe_mean > 0.10:
            return "Average"
        else:
            return "Below average"

    def _generate_insights(
        self,
        metrics: PersistenceMetrics,
        classification: PersistenceClassification,
        trend_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate key insights from workflows."""
        insights = []

        # Classification insight
        insights.append(f"Classified as {classification.value}")

        # ROE consistency
        if metrics.roe_years_above_15pct == metrics.years_analyzed:
            insights.append(
                f"Exceptional consistency: ROE >15% in all {metrics.years_analyzed} years analyzed"
            )
        elif metrics.roe_years_above_15pct / metrics.years_analyzed > 0.8:
            insights.append(
                f"High consistency: ROE >15% in {metrics.roe_years_above_15pct}/{metrics.years_analyzed} years"
            )

        # Trend insights
        if metrics.trend_score > 50:
            insights.append("Strong improving trend across multiple quality metrics")
        elif metrics.trend_score < -50:
            insights.append("⚠️ Significant deterioration in quality metrics")

        # Recent performance
        if metrics.recent_vs_historical_roe and metrics.recent_vs_historical_roe > 0.05:
            insights.append(f"Recent ROE significantly above historical average (+{metrics.recent_vs_historical_roe:.1%})")

        # FCF quality
        if metrics.fcf_conversion_mean > 1.2 and metrics.fcf_positive_years == metrics.years_analyzed:
            insights.append("Strong FCF generation: consistently converts earnings to cash")

        return insights

    def _generate_warnings(
        self,
        metrics: PersistenceMetrics,
        trend_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate warnings from workflows."""
        warnings = []

        # Limited data warning
        if metrics.years_analyzed < self.PREFERRED_YEARS:
            warnings.append(
                f"Limited history: Only {metrics.years_analyzed} years analyzed "
                f"(prefer {self.PREFERRED_YEARS}+ years)"
            )

        # Mean reversion warning
        if metrics.mean_reversion_risk == "High":
            warnings.append(
                "⚠️ High mean reversion risk: Recent ROE significantly above historical average"
            )

        # Volatility warning
        if metrics.roe_cv > 0.5:
            warnings.append(
                f"High ROE volatility (CV: {metrics.roe_cv:.2f}): Returns may be cyclical or unstable"
            )

        # Deteriorating trends
        if metrics.trend_score < -20:
            warnings.append("⚠️ Deteriorating quality metrics: Multiple metrics declining")

        # Negative FCF years
        if metrics.fcf_positive_years < metrics.years_analyzed * 0.8:
            warnings.append(
                f"Inconsistent FCF: Only {metrics.fcf_positive_years}/{metrics.years_analyzed} years positive"
            )

        return warnings

    # ==================== TIER-SPECIFIC ROE PERSISTENCE METHODS ====================
    #
    # Added for 4-tier market cap framework implementation.
    # These methods validate if holdings meet tier-specific ROE persistence requirements
    # from quality_investing_thresholds_research.md

    def validate_roe_persistence_for_tier(
        self,
        ticker: str,
        tier: MarketCapTier,
        historical_data: pd.DataFrame
    ) -> Tuple[bool, str]:
        """
        Validate if a holding meets tier-specific ROE persistence requirements.

        Requirements by tier (from quality_investing_thresholds_research.md):
        - LARGE_CAP: Prefer 5+ consecutive years with ROE >15%, minimum 2 years
                    (flexible to accommodate yfinance's typical 3-4 year limitation)
        - MID_CAP: 2-3 consecutive years with ROE >15%
        - SMALL_CAP: 6-8 consecutive quarters with positive ROE trend (2+ years minimum)
        - MICRO_CAP: Not eligible for portfolio

        Args:
            ticker: Stock ticker symbol
            tier: Market capitalization tier
            historical_data: DataFrame with annual/quarterly financial data

        Returns:
            Tuple of (passes_requirement: bool, reasoning: str)

        Example:
            >>> analyzer = QualityPersistenceAnalyzer()
            >>> passes, reason = analyzer.validate_roe_persistence_for_tier(
            ...     'AAPL',
            ...     MarketCapTier.LARGE_CAP,
            ...     historical_df
            ... )
            >>> print(f"Passes: {passes}, Reason: {reason}")
        """
        # Micro cap not eligible
        if tier == MarketCapTier.MICRO_CAP:
            return False, "MICRO_CAP tier not eligible for portfolio"

        # Calculate ROE for each period
        df = historical_data.sort_values('year').copy()

        # Check if we have required columns
        required_cols = ['net_income', 'shareholder_equity']
        if not all(col in df.columns for col in required_cols):
            return False, f"Missing required columns: {required_cols}"

        # Calculate ROE
        df['roe'] = df['net_income'] / df['shareholder_equity'].replace(0, np.nan)
        df = df.dropna(subset=['roe'])

        if len(df) == 0:
            return False, "No valid ROE data available"

        # LARGE CAP: Prefer 5+ consecutive years with ROE >15%, minimum 2 years
        # Note: yfinance typically provides 3-4 years, so we accept 2+ as minimum
        if tier == MarketCapTier.LARGE_CAP:
            roe_above_threshold = (df['roe'] > 0.15).astype(int)

            # Find longest consecutive streak
            max_streak = 0
            current_streak = 0

            for value in roe_above_threshold:
                if value == 1:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 0

            years_analyzed = len(df)
            years_above_15 = (df['roe'] > 0.15).sum()

            # Flexible validation: prefer 5+, accept 2+ minimum
            if max_streak >= 5:
                return True, f"LARGE_CAP requirement met: {max_streak} consecutive years ROE >15% (ideal: analyzed {years_analyzed} years)"
            elif max_streak >= 2:
                # Accept with note about limited data
                return True, f"LARGE_CAP requirement met: {max_streak} consecutive years ROE >15% (minimum met, prefer 5+; analyzed {years_analyzed} years)"
            else:
                return False, f"LARGE_CAP requirement NOT met: Only {max_streak} consecutive years ROE >15% (need 2+ minimum). Total years >15%: {years_above_15}/{years_analyzed}"

        # MID CAP: Require 2-3 consecutive years with ROE >15%
        elif tier == MarketCapTier.MID_CAP:
            roe_above_threshold = (df['roe'] > 0.15).astype(int)

            # Find longest consecutive streak
            max_streak = 0
            current_streak = 0

            for value in roe_above_threshold:
                if value == 1:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 0

            years_analyzed = len(df)

            if max_streak >= 2:
                return True, f"MID_CAP requirement met: {max_streak} consecutive years ROE >15% (analyzed {years_analyzed} years)"
            else:
                return False, f"MID_CAP requirement NOT met: Only {max_streak} consecutive years ROE >15% (need 2+)"

        # SMALL CAP: Require 6-8 consecutive quarters with positive ROE trend
        elif tier == MarketCapTier.SMALL_CAP:
            # For small cap, we need quarterly data, but if we only have annual,
            # we'll use a simplified approach: check for improving trend in recent periods

            years_analyzed = len(df)

            # If we have <2 years of data, can't determine trend
            if years_analyzed < 2:
                return False, f"SMALL_CAP requirement NOT met: Need at least 2 years of data to determine trend (have {years_analyzed})"

            # Calculate trend using linear regression
            if len(df) >= 2:
                years = np.arange(len(df))
                roe_values = df['roe'].values

                # Linear regression
                slope, intercept, r_value, p_value, std_err = stats.linregress(years, roe_values)

                # Check if trend is positive
                if slope > 0:
                    # Count consecutive periods with positive ROE
                    consecutive_positive = 0
                    current_consecutive = 0

                    for roe in roe_values:
                        if roe > 0:
                            current_consecutive += 1
                            consecutive_positive = max(consecutive_positive, current_consecutive)
                        else:
                            current_consecutive = 0

                    # For annual data, we approximate quarters (1 year ≈ 4 quarters)
                    # So 2 consecutive positive annual periods ≈ 8 quarters
                    quarters_equivalent = consecutive_positive * 4

                    if consecutive_positive >= 2 and slope > 0.01:  # Positive trend and at least 2 years
                        return True, f"SMALL_CAP requirement met: Positive ROE trend ({slope*100:.1f}% per year) with {consecutive_positive} consecutive positive years (~{quarters_equivalent} quarters equivalent)"
                    else:
                        return False, f"SMALL_CAP requirement NOT met: Positive trend but only {consecutive_positive} consecutive positive years (need ~2 years / 8 quarters)"
                else:
                    return False, f"SMALL_CAP requirement NOT met: ROE trend is negative ({slope*100:.1f}% per year)"

        # Should never reach here
        return False, f"Unknown tier: {tier}"

    def calculate_incremental_roce(
        self,
        historical_data: pd.DataFrame
    ) -> float:
        """
        Calculate incremental ROCE to identify companies with improving returns.

        Incremental ROCE = (Change in NOPAT) / (Change in Invested Capital)

        For mid-cap quality detection, research suggests looking for companies where
        incremental ROCE exceeds traditional ROCE by 5%+ (indicates improving capital
        deployment efficiency).

        Args:
            historical_data: DataFrame with annual financial data including:
                - nopat (Net Operating Profit After Tax)
                - total_debt
                - shareholder_equity
                - year

        Returns:
            Incremental ROCE advantage (percentage points)
            Returns 0.0 if insufficient data or calculation fails

        Example:
            >>> analyzer = QualityPersistenceAnalyzer()
            >>> advantage = analyzer.calculate_incremental_roce(historical_df)
            >>> if advantage > 5.0:
            ...     print(f"Strong incremental ROCE advantage: +{advantage:.1f}%")
        """
        df = historical_data.sort_values('year').copy()

        # Check for required columns
        required_cols = ['nopat', 'total_debt', 'shareholder_equity']
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"Missing columns for incremental ROCE calculation: {required_cols}")
            return 0.0

        # Need at least 2 years of data
        if len(df) < 2:
            logger.warning("Insufficient data for incremental ROCE (need 2+ years)")
            return 0.0

        # Calculate invested capital for each year
        df['invested_capital'] = df['total_debt'] + df['shareholder_equity']

        # Remove rows with zero or NaN invested capital
        df = df[df['invested_capital'] > 0].copy()

        if len(df) < 2:
            return 0.0

        # Calculate traditional ROCE for most recent year
        latest_year = df.iloc[-1]
        traditional_roce = latest_year['nopat'] / latest_year['invested_capital']

        # Calculate incremental ROCE (most recent year vs prior year)
        current = df.iloc[-1]
        prior = df.iloc[-2]

        delta_nopat = current['nopat'] - prior['nopat']
        delta_invested_capital = current['invested_capital'] - prior['invested_capital']

        # If invested capital didn't change or decreased, can't calculate incremental ROCE
        if delta_invested_capital <= 0:
            return 0.0

        incremental_roce = delta_nopat / delta_invested_capital

        # Calculate advantage (incremental - traditional) in percentage points
        advantage = (incremental_roce - traditional_roce) * 100

        logger.debug(f"Traditional ROCE: {traditional_roce*100:.1f}%, "
                    f"Incremental ROCE: {incremental_roce*100:.1f}%, "
                    f"Advantage: {advantage:.1f}%")

        return advantage

    def assess_tier_eligibility(
        self,
        ticker: str,
        market_cap: Optional[float] = None
    ) -> TierEligibility:
        """
        Assess if a ticker meets tier-specific eligibility requirements.

        Combines market cap classification and ROE persistence validation to determine
        if a holding qualifies for its tier under the 4-tier framework.

        This is a convenience method that:
        1. Classifies market cap tier (if not provided)
        2. Fetches historical financial data
        3. Validates tier-specific ROE persistence
        4. Calculates incremental ROCE (for mid-cap)

        Args:
            ticker: Stock ticker symbol
            market_cap: Optional market cap in dollars (fetched if not provided)

        Returns:
            TierEligibility object with full assessment

        Example:
            >>> analyzer = QualityPersistenceAnalyzer()
            >>> eligibility = analyzer.assess_tier_eligibility('AAPL')
            >>> if eligibility.meets_roe_persistence:
            ...     print(f"{ticker} meets {eligibility.market_cap_tier.value} requirements")
            ... else:
            ...     print(f"Failed: {eligibility.reasoning}")

        Note:
            This method requires yfinance for data fetching. For batch processing,
            consider caching historical data and calling validate_roe_persistence_for_tier
            directly.
        """
        # Classify market cap tier
        classifier = MarketCapClassifier(enable_cache=True)

        if market_cap is None:
            market_cap_result = classifier.classify_ticker(ticker)
            market_cap = market_cap_result.market_cap
            tier = market_cap_result.tier

            if market_cap_result.error:
                return TierEligibility(
                    ticker=ticker,
                    market_cap=None,
                    market_cap_tier=None,
                    meets_roe_persistence=False,
                    roe_persistence_years=0.0,
                    incremental_roce_advantage=None,
                    reasoning=f"Failed to fetch market cap: {market_cap_result.error}",
                    validation_date=datetime.now().strftime("%Y-%m-%d")
                )
        else:
            tier = classifier.classify_by_market_cap(market_cap)

        # Fetch historical financial data (this is a simplified version)
        # In production, you'd use a proper data fetcher
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)

            # Get annual financials
            financials = stock.financials.T  # Transpose to get years as rows
            balance_sheet = stock.balance_sheet.T

            # Build historical dataframe
            df = pd.DataFrame()
            df['year'] = financials.index.year

            # Map common fields
            field_mapping = {
                'Net Income': 'net_income',
                'Total Revenue': 'revenue',
                'Cost Of Revenue': 'cogs',
                'Operating Income': 'operating_income',
                'Total Assets': 'total_assets',
                'Stockholders Equity': 'shareholder_equity',
                'Total Debt': 'total_debt',
            }

            for yf_field, our_field in field_mapping.items():
                if yf_field in financials.columns:
                    df[our_field] = financials[yf_field].values
                elif yf_field in balance_sheet.columns:
                    df[our_field] = balance_sheet[yf_field].values

            # Calculate NOPAT (simplified: operating income * (1 - 0.21 tax rate))
            if 'operating_income' in df.columns:
                df['nopat'] = df['operating_income'] * 0.79

            # Validate ROE persistence
            passes, reasoning = self.validate_roe_persistence_for_tier(ticker, tier, df)

            # Calculate incremental ROCE (for mid-cap)
            incremental_roce_adv = None
            if tier == MarketCapTier.MID_CAP:
                incremental_roce_adv = self.calculate_incremental_roce(df)

            # Determine years of ROE persistence
            roe_years = 0.0
            if 'net_income' in df.columns and 'shareholder_equity' in df.columns:
                df['roe'] = df['net_income'] / df['shareholder_equity'].replace(0, np.nan)
                roe_years = (df['roe'] > 0.15).sum()

            return TierEligibility(
                ticker=ticker,
                market_cap=market_cap,
                market_cap_tier=tier,
                meets_roe_persistence=passes,
                roe_persistence_years=float(roe_years),
                incremental_roce_advantage=incremental_roce_adv,
                reasoning=reasoning,
                validation_date=datetime.now().strftime("%Y-%m-%d")
            )

        except Exception as e:
            logger.error(f"Failed to assess tier eligibility for {ticker}: {e}")
            return TierEligibility(
                ticker=ticker,
                market_cap=market_cap,
                market_cap_tier=tier,
                meets_roe_persistence=False,
                roe_persistence_years=0.0,
                incremental_roce_advantage=None,
                reasoning=f"Error fetching historical data: {str(e)}",
                validation_date=datetime.now().strftime("%Y-%m-%d")
            )


# Example usage and testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    # Example: Create historical data for a quality compounder (Apple-like)
    apple_data = pd.DataFrame({
        'year': [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023],
        'ticker': ['AAPL'] * 10,
        'revenue': [182e9, 234e9, 216e9, 229e9, 266e9, 260e9, 275e9, 366e9, 394e9, 383e9],
        'cogs': [112e9, 140e9, 132e9, 142e9, 164e9, 162e9, 170e9, 213e9, 223e9, 215e9],
        'sga': [18e9, 19e9, 19e9, 20e9, 22e9, 23e9, 24e9, 25e9, 26e9, 26e9],
        'total_assets': [231e9, 290e9, 321e9, 375e9, 366e9, 339e9, 324e9, 351e9, 353e9, 353e9],
        'net_income': [39e9, 53e9, 46e9, 48e9, 60e9, 55e9, 57e9, 95e9, 100e9, 97e9],
        'shareholder_equity': [111e9, 120e9, 129e9, 134e9, 107e9, 90e9, 65e9, 63e9, 50e9, 62e9],
        'free_cash_flow': [50e9, 69e9, 53e9, 51e9, 64e9, 58e9, 73e9, 93e9, 111e9, 99e9],
        'total_debt': [29e9, 54e9, 75e9, 97e9, 93e9, 92e9, 112e9, 119e9, 120e9, 111e9],
        'nopat': [45e9, 58e9, 52e9, 54e9, 65e9, 60e9, 62e9, 98e9, 103e9, 100e9]
    })

    # Initialize analyzer
    analyzer = QualityPersistenceAnalyzer()

    # Analyze company
    result = analyzer.analyze_company(
        apple_data,
        ticker='AAPL',
        generate_llm_prompt=True
    )

    print("\n" + "="*80)
    print("QUALITY PERSISTENCE ANALYSIS - AAPL")
    print("="*80)
    print(f"\nClassification: {result.classification.value}")
    print(f"Compounder Confidence: {result.compounder_confidence:.1f}%")
    print(f"\nPersistence Score: {result.persistence_metrics.persistence_score:.1f}/100")
    print(f"Consistency Score: {result.persistence_metrics.consistency_score:.1f}/100")
    print(f"Trend Score: {result.persistence_metrics.trend_score:.1f}/100")

    print(f"\nKey Metrics ({result.persistence_metrics.start_year}-{result.persistence_metrics.end_year}):")
    print(f"  Average ROE: {result.persistence_metrics.roe_mean:.1%}")
    print(f"  ROE Volatility (CV): {result.persistence_metrics.roe_cv:.2f}")
    print(f"  Years ROE >15%: {result.persistence_metrics.roe_years_above_15pct}/{result.persistence_metrics.years_analyzed}")
    print(f"  Average ROIC: {result.persistence_metrics.roic_mean:.1%}")
    print(f"  FCF Conversion: {result.persistence_metrics.fcf_conversion_mean:.2f}x")

    print(f"\nTrend Analysis:")
    print(f"  Overall: {result.trend_analysis['overall_trend_direction']}")
    print(f"  ROE: {result.trend_analysis['roe_trend']}")
    print(f"  Margins: {result.trend_analysis['margin_trend']['gross']}")
    print(f"  Mean Reversion Risk: {result.persistence_metrics.mean_reversion_risk}")

    print(f"\nKey Insights:")
    for insight in result.key_insights:
        print(f"  • {insight}")

    if result.warnings:
        print(f"\nWarnings:")
        for warning in result.warnings:
            print(f"  ⚠️  {warning}")

    # Visualize
    print(f"\nGenerating visualization...")
    analyzer.visualize_persistence(apple_data, 'AAPL', show_plot=False)

    # Print LLM prompt
    if result.llm_prompt:
        print(f"\n" + "="*80)
        print("GENERATED LLM PROMPT:")
        print("="*80)
        print(result.llm_prompt)
