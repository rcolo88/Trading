"""
Quality Analysis Agent
Analyzes company quality metrics and integrates with the HuggingFace agent system.

Unlike other agents, this doesn't call a sentiment model but instead processes
quality metrics calculated by QualityMetricsCalculator.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

# Handle both module and standalone imports
try:
    from .base_agent import AgentResult
except ImportError:
    from base_agent import AgentResult

from quality.quality_metrics_calculator import (
    QualityMetricsCalculator,
    QualityAnalysisResult,
    QualityTier,
    RedFlag
)
from quality.quality_llm_prompts import (
    QualityLLMPromptGenerator,
    LLMAnalysisResponse
)


@dataclass
class QualityAgentResult:
    """Extended result for quality analysis with additional metrics."""
    agent_result: AgentResult  # Standard agent result
    quality_analysis: QualityAnalysisResult  # Full quality metrics
    investment_rating: str  # BUY/HOLD/SELL
    risk_level: str  # Low/Medium/High
    position_recommendation: str  # Overweight/Neutral/Underweight
    llm_prompt: Optional[str] = None  # Generated LLM prompt if requested

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "agent_result": self.agent_result.to_dict(),
            "quality_tier": self.quality_analysis.tier.value,
            "composite_score": self.quality_analysis.composite_score,
            "red_flags_count": len(self.quality_analysis.red_flags),
            "investment_rating": self.investment_rating,
            "risk_level": self.risk_level,
            "position_recommendation": self.position_recommendation,
            "metrics": {
                ms.name: {"value": ms.value, "score": ms.score}
                for ms in self.quality_analysis.metric_scores
            },
            "red_flags": [
                {
                    "category": rf.category,
                    "severity": rf.severity,
                    "description": rf.description
                }
                for rf in self.quality_analysis.red_flags
            ]
        }


class QualityAgent:
    """
    Analyzes company quality metrics and provides investment recommendations.

    This agent integrates QualityMetricsCalculator with the HF agent system,
    following the same interface pattern as other agents but processing
    quality metrics instead of making sentiment API calls.
    """

    def __init__(self):
        """Initialize the quality agent."""
        self.calculator = QualityMetricsCalculator()
        self.prompt_generator = QualityLLMPromptGenerator()
        self.logger = __import__('logging').getLogger(f"{self.__class__.__name__}")
        self.logger.info("QualityAgent initialized")

    def analyze(
        self,
        financial_data: Dict[str, Any],
        generate_llm_prompt: bool = False,
        context: Optional[str] = None
    ) -> QualityAgentResult:
        """
        Analyze company quality metrics and return AgentResult.

        Args:
            financial_data: Financial data dictionary (see QualityMetricsCalculator)
            generate_llm_prompt: Whether to generate LLM prompt for external use
            context: Optional context for LLM prompt generation

        Returns:
            QualityAgentResult with analysis and recommendations
        """
        ticker = financial_data.get('ticker', 'UNKNOWN')
        self.logger.info(f"Analyzing quality metrics for {ticker}")

        # Calculate quality metrics
        try:
            quality_result = self.calculator.calculate_quality_metrics(financial_data)
        except Exception as e:
            self.logger.error(f"Failed to calculate quality metrics for {ticker}: {e}")
            # Return error result
            return self._create_error_result(ticker, str(e))

        # Convert to AgentResult format
        agent_result = self._convert_to_agent_result(quality_result)

        # Determine investment rating
        investment_rating = self._determine_investment_rating(quality_result)

        # Determine risk level
        risk_level = self._determine_risk_level(quality_result)

        # Determine position recommendation
        position_rec = self._determine_position_recommendation(quality_result)

        # Generate LLM prompt if requested
        llm_prompt = None
        if generate_llm_prompt:
            llm_prompt = self.prompt_generator.generate_quality_screening_prompt(
                quality_result,
                context=context
            )

        result = QualityAgentResult(
            agent_result=agent_result,
            quality_analysis=quality_result,
            investment_rating=investment_rating,
            risk_level=risk_level,
            position_recommendation=position_rec,
            llm_prompt=llm_prompt
        )

        self.logger.info(
            f"{ticker}: {quality_result.tier.value} tier, "
            f"Score {quality_result.composite_score:.1f}, "
            f"Rating {investment_rating}"
        )

        return result

    def analyze_portfolio(
        self,
        portfolio_holdings: Dict[str, Dict[str, Any]],
        generate_report: bool = True
    ) -> Dict[str, QualityAgentResult]:
        """
        Analyze quality metrics for entire portfolio.

        Args:
            portfolio_holdings: Dict mapping tickers to financial data
            generate_report: Whether to generate comparative report

        Returns:
            Dictionary mapping tickers to QualityAgentResult
        """
        self.logger.info(f"Analyzing portfolio quality for {len(portfolio_holdings)} holdings")

        results = {}
        for ticker, financial_data in portfolio_holdings.items():
            try:
                result = self.analyze(financial_data)
                results[ticker] = result
            except Exception as e:
                self.logger.error(f"Error analyzing {ticker}: {e}")

        self.logger.info(f"Portfolio analysis complete: {len(results)} stocks analyzed")

        if generate_report and results:
            report = self._generate_portfolio_report(results)
            self.logger.info(f"Generated portfolio quality report ({len(report)} chars)")

        return results

    def get_top_quality_picks(
        self,
        portfolio_results: Dict[str, QualityAgentResult],
        min_score: float = 70.0,
        max_picks: int = 5
    ) -> List[str]:
        """
        Get top quality stocks from portfolio analysis.

        Args:
            portfolio_results: Results from analyze_portfolio()
            min_score: Minimum composite score threshold
            max_picks: Maximum number of picks to return

        Returns:
            List of ticker symbols, sorted by quality score
        """
        # Filter by minimum score and no high-severity red flags
        candidates = []
        for ticker, result in portfolio_results.items():
            quality = result.quality_analysis
            high_severity_flags = [
                rf for rf in quality.red_flags
                if rf.severity == "HIGH"
            ]

            if quality.composite_score >= min_score and len(high_severity_flags) == 0:
                candidates.append((ticker, quality.composite_score))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Return top picks
        top_picks = [ticker for ticker, score in candidates[:max_picks]]

        self.logger.info(f"Top quality picks: {', '.join(top_picks)}")
        return top_picks

    def get_quality_concerns(
        self,
        portfolio_results: Dict[str, QualityAgentResult],
        min_red_flags: int = 2
    ) -> List[str]:
        """
        Get stocks with quality concerns from portfolio analysis.

        Args:
            portfolio_results: Results from analyze_portfolio()
            min_red_flags: Minimum number of high-severity red flags

        Returns:
            List of ticker symbols with concerns
        """
        concerns = []
        for ticker, result in portfolio_results.items():
            quality = result.quality_analysis
            high_severity = [
                rf for rf in quality.red_flags
                if rf.severity == "HIGH"
            ]

            if len(high_severity) >= min_red_flags or quality.tier == QualityTier.WEAK:
                concerns.append(ticker)

        self.logger.info(f"Quality concerns: {', '.join(concerns)}")
        return concerns

    def _convert_to_agent_result(self, quality_result: QualityAnalysisResult) -> AgentResult:
        """
        Convert QualityAnalysisResult to standard AgentResult format.

        Args:
            quality_result: Quality analysis result

        Returns:
            AgentResult compatible with other agents
        """
        # Map quality tier to sentiment
        sentiment_map = {
            QualityTier.ELITE: "positive",
            QualityTier.STRONG: "positive",
            QualityTier.MODERATE: "neutral",
            QualityTier.WEAK: "negative"
        }
        sentiment = sentiment_map[quality_result.tier]

        # Calculate confidence based on score and red flags
        base_confidence = quality_result.composite_score / 100.0
        high_severity_flags = [
            rf for rf in quality_result.red_flags
            if rf.severity == "HIGH"
        ]
        confidence_penalty = len(high_severity_flags) * 0.05
        confidence = max(0.0, min(1.0, base_confidence - confidence_penalty))

        # Generate reasoning
        reasoning = self._generate_reasoning(quality_result)

        return AgentResult(
            agent_name="QualityAgent",
            sentiment=sentiment,
            confidence=confidence,
            score=quality_result.composite_score,
            label=quality_result.tier.value,
            reasoning=reasoning,
            timestamp=datetime.now(),
            model_used="QualityMetricsCalculator",
            raw_response={
                "tier": quality_result.tier.value,
                "composite_score": quality_result.composite_score,
                "red_flags_count": len(quality_result.red_flags),
                "is_consistent_roe": quality_result.is_consistent_roe_performer
            }
        )

    def _generate_reasoning(self, quality_result: QualityAnalysisResult) -> str:
        """Generate human-readable reasoning for quality assessment."""
        lines = []

        # Overall quality
        lines.append(
            f"{quality_result.ticker} rated as {quality_result.tier.value} quality "
            f"(score: {quality_result.composite_score:.1f}/100)."
        )

        # Top metrics
        top_metrics = sorted(
            quality_result.metric_scores,
            key=lambda x: x.score,
            reverse=True
        )[:2]

        metric_names = {
            'gross_profitability': 'Gross Profitability',
            'roe': 'ROE',
            'operating_profitability': 'Operating Profitability',
            'fcf_yield': 'FCF Yield',
            'roic': 'ROIC'
        }

        strengths = ", ".join([
            f"{metric_names.get(ms.name, ms.name)} {ms.value:.1%}"
            for ms in top_metrics
        ])
        lines.append(f"Strengths: {strengths}.")

        # Red flags
        if quality_result.red_flags:
            high_severity = [
                rf for rf in quality_result.red_flags
                if rf.severity == "HIGH"
            ]
            if high_severity:
                lines.append(
                    f"⚠️ {len(high_severity)} high-severity red flag(s): "
                    f"{', '.join(rf.category for rf in high_severity[:3])}."
                )
        else:
            lines.append("No red flags detected.")

        # Consistent performer
        if quality_result.is_consistent_roe_performer:
            lines.append("✓ Elite performer: ROE >15% for 10+ years.")

        return " ".join(lines)

    def _determine_investment_rating(self, quality_result: QualityAnalysisResult) -> str:
        """Determine BUY/HOLD/SELL rating based on quality metrics."""
        high_severity_flags = [
            rf for rf in quality_result.red_flags
            if rf.severity == "HIGH"
        ]

        # BUY criteria
        if quality_result.tier == QualityTier.ELITE and len(high_severity_flags) == 0:
            return "STRONG BUY"
        elif quality_result.tier == QualityTier.STRONG and len(high_severity_flags) == 0:
            return "BUY"
        elif quality_result.tier == QualityTier.STRONG and len(high_severity_flags) <= 1:
            return "BUY"

        # HOLD criteria
        elif quality_result.tier in [QualityTier.STRONG, QualityTier.MODERATE]:
            return "HOLD"

        # SELL criteria
        elif len(high_severity_flags) >= 3:
            return "STRONG SELL"
        elif quality_result.tier == QualityTier.WEAK:
            return "SELL"

        # Default
        return "HOLD"

    def _determine_risk_level(self, quality_result: QualityAnalysisResult) -> str:
        """Determine risk level (Low/Medium/High) based on quality metrics."""
        high_severity_flags = [
            rf for rf in quality_result.red_flags
            if rf.severity == "HIGH"
        ]
        medium_severity_flags = [
            rf for rf in quality_result.red_flags
            if rf.severity == "MEDIUM"
        ]

        # High risk
        if len(high_severity_flags) >= 2:
            return "High"
        elif quality_result.tier == QualityTier.WEAK:
            return "High"

        # Medium risk
        elif len(high_severity_flags) == 1:
            return "Medium"
        elif quality_result.tier == QualityTier.MODERATE:
            return "Medium"
        elif len(medium_severity_flags) >= 2:
            return "Medium"

        # Low risk
        else:
            return "Low"

    def _determine_position_recommendation(self, quality_result: QualityAnalysisResult) -> str:
        """Determine position sizing recommendation."""
        high_severity_flags = [
            rf for rf in quality_result.red_flags
            if rf.severity == "HIGH"
        ]

        # Overweight
        if quality_result.tier == QualityTier.ELITE and len(high_severity_flags) == 0:
            if quality_result.is_consistent_roe_performer:
                return "Overweight"
            return "Overweight"
        elif quality_result.tier == QualityTier.STRONG and len(high_severity_flags) == 0:
            return "Neutral to Overweight"

        # Underweight
        elif quality_result.tier == QualityTier.WEAK:
            return "Underweight"
        elif len(high_severity_flags) >= 2:
            return "Underweight"

        # Neutral
        else:
            return "Neutral"

    def _create_error_result(self, ticker: str, error_msg: str) -> QualityAgentResult:
        """Create error result when quality calculation fails."""
        self.logger.error(f"Creating error result for {ticker}: {error_msg}")

        agent_result = AgentResult(
            agent_name="QualityAgent",
            sentiment="neutral",
            confidence=0.0,
            score=0.0,
            label="ERROR",
            reasoning=f"Failed to calculate quality metrics: {error_msg}",
            timestamp=datetime.now(),
            model_used="QualityMetricsCalculator",
            raw_response={"error": error_msg}
        )

        # Create minimal quality result
        from quality.quality_metrics_calculator import QualityAnalysisResult, QualityTier

        quality_result = QualityAnalysisResult(
            ticker=ticker,
            metric_scores=[],
            composite_score=0.0,
            tier=QualityTier.WEAK,
            red_flags=[],
            is_consistent_roe_performer=False,
            summary=f"Error: {error_msg}",
            raw_metrics={}
        )

        return QualityAgentResult(
            agent_result=agent_result,
            quality_analysis=quality_result,
            investment_rating="HOLD",
            risk_level="Unknown",
            position_recommendation="Neutral"
        )

    def _generate_portfolio_report(self, results: Dict[str, QualityAgentResult]) -> str:
        """Generate comprehensive portfolio quality report."""
        lines = []
        lines.append("=" * 80)
        lines.append("PORTFOLIO QUALITY ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Summary statistics
        elite = sum(1 for r in results.values() if r.quality_analysis.tier == QualityTier.ELITE)
        strong = sum(1 for r in results.values() if r.quality_analysis.tier == QualityTier.STRONG)
        moderate = sum(1 for r in results.values() if r.quality_analysis.tier == QualityTier.MODERATE)
        weak = sum(1 for r in results.values() if r.quality_analysis.tier == QualityTier.WEAK)

        lines.append("Quality Tier Distribution:")
        lines.append(f"  Elite:    {elite:3d} ({elite/len(results)*100:5.1f}%)")
        lines.append(f"  Strong:   {strong:3d} ({strong/len(results)*100:5.1f}%)")
        lines.append(f"  Moderate: {moderate:3d} ({moderate/len(results)*100:5.1f}%)")
        lines.append(f"  Weak:     {weak:3d} ({weak/len(results)*100:5.1f}%)")
        lines.append("")

        # Average score
        avg_score = sum(r.quality_analysis.composite_score for r in results.values()) / len(results)
        lines.append(f"Average Quality Score: {avg_score:.1f}/100")
        lines.append("")

        # Investment ratings
        lines.append("Investment Ratings:")
        rating_counts = {}
        for result in results.values():
            rating = result.investment_rating
            rating_counts[rating] = rating_counts.get(rating, 0) + 1

        for rating, count in sorted(rating_counts.items()):
            lines.append(f"  {rating:15} {count:3d}")
        lines.append("")

        # Red flags summary
        total_red_flags = sum(len(r.quality_analysis.red_flags) for r in results.values())
        high_severity_total = sum(
            len([rf for rf in r.quality_analysis.red_flags if rf.severity == "HIGH"])
            for r in results.values()
        )

        lines.append(f"Red Flags: {total_red_flags} total ({high_severity_total} high-severity)")
        lines.append("")

        # Top quality picks
        lines.append("Top Quality Stocks:")
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1].quality_analysis.composite_score,
            reverse=True
        )
        for ticker, result in sorted_results[:5]:
            lines.append(
                f"  {ticker:8} | {result.quality_analysis.composite_score:5.1f} | "
                f"{result.quality_analysis.tier.value:10} | {result.investment_rating}"
            )
        lines.append("")

        # Quality concerns
        concerns = [
            ticker for ticker, result in results.items()
            if result.quality_analysis.tier == QualityTier.WEAK or
            len([rf for rf in result.quality_analysis.red_flags if rf.severity == "HIGH"]) >= 2
        ]

        if concerns:
            lines.append("⚠️  Quality Concerns:")
            for ticker in concerns:
                result = results[ticker]
                high_flags = [rf for rf in result.quality_analysis.red_flags if rf.severity == "HIGH"]
                lines.append(f"  {ticker}: {len(high_flags)} high-severity red flags")
        else:
            lines.append("✓ No major quality concerns")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def get_model_info(self) -> dict:
        """Get information about this agent."""
        return {
            "agent_name": "QualityAgent",
            "model_name": "Quality Metrics Calculator",
            "model_id": "academically_validated_quality_metrics",
            "task": "quality-analysis",
            "metrics_calculated": 5,
            "red_flags_detected": 6
        }


# Standalone usage example
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    # Example data
    example_data = {
        'ticker': 'AAPL',
        'revenue': 394_328_000_000,
        'cogs': 223_546_000_000,
        'sga': 26_094_000_000,
        'total_assets': 352_755_000_000,
        'net_income': 99_803_000_000,
        'shareholder_equity': 62_146_000_000,
        'free_cash_flow': 111_443_000_000,
        'market_cap': 3_000_000_000_000,
        'total_debt': 111_088_000_000,
        'nopat': 85_000_000_000,
        'roe_history': [0.46, 0.49, 0.55, 0.61, 0.56, 0.50, 0.63, 0.83, 1.00, 1.60],
    }

    # Initialize agent
    agent = QualityAgent()

    # Analyze single stock
    result = agent.analyze(example_data, generate_llm_prompt=True)

    print("\n" + "=" * 80)
    print("QUALITY AGENT ANALYSIS")
    print("=" * 80)
    print(f"\nTicker: {result.quality_analysis.ticker}")
    print(f"Quality Tier: {result.quality_analysis.tier.value}")
    print(f"Composite Score: {result.quality_analysis.composite_score:.1f}/100")
    print(f"Investment Rating: {result.investment_rating}")
    print(f"Risk Level: {result.risk_level}")
    print(f"Position Recommendation: {result.position_recommendation}")
    print(f"\nAgent Result:")
    print(f"  Sentiment: {result.agent_result.sentiment}")
    print(f"  Confidence: {result.agent_result.confidence:.1%}")
    print(f"  Reasoning: {result.agent_result.reasoning}")

    if result.llm_prompt:
        print(f"\n{'-'*80}")
        print("GENERATED LLM PROMPT:")
        print(f"{'-'*80}")
        print(result.llm_prompt)
