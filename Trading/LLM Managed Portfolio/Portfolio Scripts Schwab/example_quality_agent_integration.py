"""
Quality Agent Integration Example

Demonstrates how to integrate the Quality Agent with the existing
HuggingFace agent system for comprehensive stock analysis.

This combines:
- Quality metrics analysis (QualityAgent)
- Market sentiment (MarketAgent)
- Risk assessment (RiskAgent)
- News sentiment (NewsAgent)
- Market tone (ToneAgent)

Author: Trading System
Date: 2025-10-30
"""

import sys
import logging
from typing import Dict, List, Optional
import json

# Import agents
from agents import (
    QualityAgent,
    QualityAgentResult,
    RiskAgent,
    RiskAnalysis,
    MarketAgent,
    ToneAgent,
    NewsAgent
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegratedAnalysisEngine:
    """
    Combines quality metrics with sentiment analysis agents for
    comprehensive stock evaluation.
    """

    def __init__(self):
        """Initialize all agents."""
        logger.info("Initializing Integrated Analysis Engine...")

        self.quality_agent = QualityAgent()
        self.risk_agent = RiskAgent()
        self.market_agent = MarketAgent()
        self.tone_agent = ToneAgent()
        self.news_agent = NewsAgent()

        logger.info("All agents initialized successfully")

    def analyze_stock_comprehensive(
        self,
        ticker: str,
        financial_data: Dict,
        market_context: Optional[str] = None,
        news_headlines: Optional[List[str]] = None
    ) -> Dict:
        """
        Perform comprehensive analysis combining quality and sentiment.

        Args:
            ticker: Stock ticker symbol
            financial_data: Financial data for quality analysis
            market_context: Optional market conditions text
            news_headlines: Optional list of recent news headlines

        Returns:
            Dictionary with combined analysis results
        """
        logger.info(f"Starting comprehensive analysis for {ticker}")

        results = {
            'ticker': ticker,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }

        # 1. Quality Analysis (no API calls needed)
        logger.info(f"[1/5] Running quality analysis for {ticker}...")
        try:
            quality_result = self.quality_agent.analyze(
                financial_data,
                generate_llm_prompt=True,
                context=market_context
            )
            results['quality'] = {
                'tier': quality_result.quality_analysis.tier.value,
                'score': quality_result.quality_analysis.composite_score,
                'investment_rating': quality_result.investment_rating,
                'risk_level': quality_result.risk_level,
                'position_recommendation': quality_result.position_recommendation,
                'red_flags_count': len(quality_result.quality_analysis.red_flags),
                'agent_sentiment': quality_result.agent_result.sentiment,
                'reasoning': quality_result.agent_result.reasoning
            }
            logger.info(f"  Quality: {quality_result.quality_analysis.tier.value} "
                       f"({quality_result.quality_analysis.composite_score:.1f}/100)")
        except Exception as e:
            logger.error(f"  Quality analysis failed: {e}")
            results['quality'] = {'error': str(e)}

        # 2. Market Sentiment Analysis (HF API call)
        if market_context:
            logger.info(f"[2/5] Running market sentiment analysis...")
            try:
                market_result = self.market_agent.analyze(
                    market_context,
                    context={'ticker': ticker}
                )
                results['market_sentiment'] = {
                    'sentiment': market_result.sentiment,
                    'confidence': market_result.confidence,
                    'reasoning': market_result.reasoning
                }
                logger.info(f"  Market: {market_result.sentiment} "
                           f"({market_result.confidence:.1%} confidence)")
            except Exception as e:
                logger.error(f"  Market analysis failed: {e}")
                results['market_sentiment'] = {'error': str(e)}
        else:
            results['market_sentiment'] = {'skipped': 'no_context_provided'}

        # 3. Risk Analysis (HF API call)
        logger.info(f"[3/5] Running risk analysis...")
        risk_text = f"{ticker} financial analysis. " + (market_context or "")
        try:
            risk_result = self.risk_agent.analyze(
                risk_text,
                context={
                    'ticker': ticker,
                    'position_size': 0.10  # Example 10% position
                }
            )
            results['risk_assessment'] = {
                'sentiment': risk_result.sentiment,
                'confidence': risk_result.confidence,
                'reasoning': risk_result.reasoning
            }
            logger.info(f"  Risk: {risk_result.sentiment} "
                       f"({risk_result.confidence:.1%} confidence)")
        except Exception as e:
            logger.error(f"  Risk analysis failed: {e}")
            results['risk_assessment'] = {'error': str(e)}

        # 4. Market Tone Analysis (HF API call)
        if market_context:
            logger.info(f"[4/5] Running market tone analysis...")
            try:
                tone_result = self.tone_agent.analyze(
                    market_context,
                    context={'ticker': ticker}
                )
                results['market_tone'] = {
                    'sentiment': tone_result.sentiment,
                    'confidence': tone_result.confidence,
                    'reasoning': tone_result.reasoning
                }
                logger.info(f"  Tone: {tone_result.sentiment} "
                           f"({tone_result.confidence:.1%} confidence)")
            except Exception as e:
                logger.error(f"  Tone analysis failed: {e}")
                results['market_tone'] = {'error': str(e)}
        else:
            results['market_tone'] = {'skipped': 'no_context_provided'}

        # 5. News Sentiment Analysis (HF API call)
        if news_headlines:
            logger.info(f"[5/5] Running news sentiment analysis on {len(news_headlines)} headlines...")
            try:
                news_analysis = self.news_agent.analyze_multiple_headlines(
                    news_headlines,
                    ticker=ticker
                )
                results['news_sentiment'] = {
                    'overall_sentiment': news_analysis.overall_sentiment,
                    'confidence': news_analysis.confidence,
                    'positive_count': news_analysis.positive_count,
                    'negative_count': news_analysis.negative_count,
                    'neutral_count': news_analysis.neutral_count
                }
                logger.info(f"  News: {news_analysis.overall_sentiment} "
                           f"(+{news_analysis.positive_count}/-{news_analysis.negative_count})")
            except Exception as e:
                logger.error(f"  News analysis failed: {e}")
                results['news_sentiment'] = {'error': str(e)}
        else:
            results['news_sentiment'] = {'skipped': 'no_headlines_provided'}

        # 6. Generate综合 Assessment
        results['综合_assessment'] = self._synthesize_results(results)

        logger.info(f"Comprehensive analysis complete for {ticker}")
        return results

    def _synthesize_results(self, results: Dict) -> Dict:
        """Synthesize all agent results into final recommendation."""
        synthesis = {
            'overall_recommendation': 'UNKNOWN',
            'confidence': 0.0,
            'rationale': []
        }

        # Quality score (50% weight)
        quality = results.get('quality', {})
        if 'score' in quality:
            quality_score = quality['score'] / 100.0  # Normalize to 0-1
            quality_weight = 0.50
        else:
            quality_score = 0.5
            quality_weight = 0.0
            synthesis['rationale'].append("⚠️ Quality data missing")

        # Market sentiment (20% weight)
        market_sent = results.get('market_sentiment', {})
        if 'sentiment' in market_sent:
            market_score = self._sentiment_to_score(market_sent['sentiment'])
            market_weight = 0.20
        else:
            market_score = 0.5
            market_weight = 0.0

        # Risk assessment (15% weight - inverted: negative risk = lower score)
        risk = results.get('risk_assessment', {})
        if 'sentiment' in risk:
            # Negative risk sentiment = bad for investment
            risk_score = 1.0 - self._sentiment_to_score(risk['sentiment'])
            risk_weight = 0.15
        else:
            risk_score = 0.5
            risk_weight = 0.0

        # News sentiment (10% weight)
        news = results.get('news_sentiment', {})
        if 'overall_sentiment' in news:
            news_score = self._sentiment_to_score(news['overall_sentiment'])
            news_weight = 0.10
        else:
            news_score = 0.5
            news_weight = 0.0

        # Market tone (5% weight)
        tone = results.get('market_tone', {})
        if 'sentiment' in tone:
            tone_score = self._sentiment_to_score(tone['sentiment'])
            tone_weight = 0.05
        else:
            tone_score = 0.5
            tone_weight = 0.0

        # Calculate weighted score
        total_weight = quality_weight + market_weight + risk_weight + news_weight + tone_weight
        if total_weight > 0:
            综合_score = (
                (quality_score * quality_weight) +
                (market_score * market_weight) +
                (risk_score * risk_weight) +
                (news_score * news_weight) +
                (tone_score * tone_weight)
            ) / total_weight
        else:
            综合_score = 0.5

        synthesis['综合_score'] = 综合_score
        synthesis['confidence'] = total_weight  # Higher when more data available

        # Determine recommendation
        if 综合_score >= 0.75:
            synthesis['overall_recommendation'] = "STRONG BUY"
        elif 综合_score >= 0.60:
            synthesis['overall_recommendation'] = "BUY"
        elif 综合_score >= 0.40:
            synthesis['overall_recommendation'] = "HOLD"
        elif 综合_score >= 0.25:
            synthesis['overall_recommendation'] = "SELL"
        else:
            synthesis['overall_recommendation'] = "STRONG SELL"

        # Add rationale
        if quality.get('investment_rating') in ['STRONG BUY', 'BUY']:
            synthesis['rationale'].append(f"✓ High quality: {quality.get('tier', 'N/A')} tier")
        elif quality.get('red_flags_count', 0) > 2:
            synthesis['rationale'].append(f"⚠️ Quality concerns: {quality['red_flags_count']} red flags")

        if market_sent.get('sentiment') == 'positive':
            synthesis['rationale'].append("✓ Positive market sentiment")
        elif market_sent.get('sentiment') == 'negative':
            synthesis['rationale'].append("⚠️ Negative market sentiment")

        if risk.get('sentiment') == 'negative':
            synthesis['rationale'].append("⚠️ High risk factors detected")

        return synthesis

    def _sentiment_to_score(self, sentiment: str) -> float:
        """Convert sentiment to numeric score (0-1)."""
        mapping = {
            'positive': 1.0,
            'neutral': 0.5,
            'negative': 0.0
        }
        return mapping.get(sentiment.lower(), 0.5)


def example_single_stock_analysis():
    """Example: Analyze single stock with all agents."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Comprehensive Single Stock Analysis")
    print("=" * 80)

    # Sample financial data (Apple)
    financial_data = {
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

    market_context = (
        "AAPL continues strong performance driven by iPhone 15 sales and services growth. "
        "Market showing resilience despite broader tech sector volatility."
    )

    news_headlines = [
        "Apple reports record Q4 earnings beating analyst expectations",
        "iPhone 15 sales exceed projections in key markets",
        "Apple expanding services revenue with new subscription offerings"
    ]

    # Run analysis
    engine = IntegratedAnalysisEngine()
    results = engine.analyze_stock_comprehensive(
        ticker='AAPL',
        financial_data=financial_data,
        market_context=market_context,
        news_headlines=news_headlines
    )

    # Display results
    print("\n" + "-" * 80)
    print("ANALYSIS RESULTS")
    print("-" * 80)
    print(json.dumps(results, indent=2))

    # Summary
    synthesis = results['综合_assessment']
    print("\n" + "=" * 80)
    print("SYNTHESIS")
    print("=" * 80)
    print(f"Overall Recommendation: {synthesis['overall_recommendation']}")
    print(f"Composite Score: {synthesis['综合_score']:.1%}")
    print(f"Confidence: {synthesis['confidence']:.1%}")
    print("\nRationale:")
    for reason in synthesis['rationale']:
        print(f"  {reason}")


def example_portfolio_quality_screening():
    """Example: Screen portfolio using quality agent only."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Portfolio Quality Screening (Quality Agent Only)")
    print("=" * 80)

    # Sample portfolio
    portfolio = {
        'AAPL': {
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
        },
        'MSFT': {
            'ticker': 'MSFT',
            'revenue': 211_915_000_000,
            'cogs': 65_863_000_000,
            'sga': 55_000_000_000,
            'total_assets': 411_976_000_000,
            'net_income': 72_361_000_000,
            'shareholder_equity': 238_268_000_000,
            'free_cash_flow': 71_000_000_000,
            'market_cap': 2_800_000_000_000,
            'total_debt': 79_000_000_000,
            'nopat': 60_000_000_000,
        }
    }

    quality_agent = QualityAgent()
    results = quality_agent.analyze_portfolio(portfolio, generate_report=True)

    # Display top picks
    top_picks = quality_agent.get_top_quality_picks(results, min_score=70.0, max_picks=5)
    print(f"\nTop Quality Picks: {', '.join(top_picks)}")

    # Display concerns
    concerns = quality_agent.get_quality_concerns(results, min_red_flags=2)
    if concerns:
        print(f"Quality Concerns: {', '.join(concerns)}")
    else:
        print("No quality concerns detected")


def example_quality_with_risk_analysis():
    """Example: Combine quality and risk analysis."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Quality + Risk Combined Analysis")
    print("=" * 80)

    financial_data = {
        'ticker': 'XYZ',
        'revenue': 50_000_000_000,
        'cogs': 38_000_000_000,
        'sga': 8_000_000_000,
        'total_assets': 40_000_000_000,
        'net_income': 2_500_000_000,
        'shareholder_equity': 15_000_000_000,
        'free_cash_flow': 1_500_000_000,
        'market_cap': 35_000_000_000,
        'total_debt': 18_000_000_000,  # High leverage
        'nopat': 2_200_000_000,
    }

    quality_agent = QualityAgent()
    risk_agent = RiskAgent()

    # Quality analysis
    quality_result = quality_agent.analyze(financial_data)

    # Risk analysis
    risk_text = f"XYZ Corp showing elevated debt levels at {financial_data['total_debt']/1e9:.1f}B. Leverage concerns in current market environment."
    risk_result = risk_agent.analyze(
        risk_text,
        context={'ticker': 'XYZ', 'position_size': 0.15}
    )

    # Combined decision
    print(f"\nQuality Assessment:")
    print(f"  Tier: {quality_result.quality_analysis.tier.value}")
    print(f"  Score: {quality_result.quality_analysis.composite_score:.1f}/100")
    print(f"  Rating: {quality_result.investment_rating}")
    print(f"  Red Flags: {len(quality_result.quality_analysis.red_flags)}")

    print(f"\nRisk Assessment:")
    print(f"  Sentiment: {risk_result.sentiment}")
    print(f"  Confidence: {risk_result.confidence:.1%}")
    print(f"  Reasoning: {risk_result.reasoning}")

    # Combined recommendation
    if (quality_result.quality_analysis.tier.value in ['Elite', 'Strong'] and
        risk_result.sentiment != 'negative'):
        print(f"\nCombined Recommendation: BUY")
    elif quality_result.investment_rating in ['SELL', 'STRONG SELL'] or risk_result.sentiment == 'negative':
        print(f"\nCombined Recommendation: SELL")
    else:
        print(f"\nCombined Recommendation: HOLD")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "QUALITY AGENT INTEGRATION EXAMPLES" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")

    # Note: Examples with HF API calls may fail if API is unavailable
    # Only quality agent will work reliably offline

    try:
        # Example 1: Full integration (may require HF API access)
        # example_single_stock_analysis()

        # Example 2: Quality agent only (works offline)
        example_portfolio_quality_screening()

        # Example 3: Quality + Risk
        # example_quality_with_risk_analysis()

    except Exception as e:
        logger.error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()
