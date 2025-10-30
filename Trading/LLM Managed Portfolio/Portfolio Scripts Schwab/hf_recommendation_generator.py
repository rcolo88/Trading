"""
HuggingFace Recommendation Generator
Runs HF agents and generates trading recommendations markdown document
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from agents import NewsAgent, MarketAgent, RiskAgent, ToneAgent
from hf_config import MODELS


class HFRecommendationGenerator:
    """Generates trading recommendation documents using HuggingFace agents"""

    def __init__(self):
        """Initialize all HF agents"""
        print("🤖 Initializing HuggingFace agents...")

        self.news_agent = NewsAgent(MODELS["news"])
        self.market_agent = MarketAgent(MODELS["market"])
        self.risk_agent = RiskAgent(MODELS["risk"])
        self.tone_agent = ToneAgent(MODELS["tone"])

        print("✅ All HF agents initialized")

    def load_portfolio_document(self) -> str:
        """Load daily_portfolio_analysis.md for agent analysis"""

        # Look in parent directory for daily_portfolio_analysis.md
        parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
        analysis_file = os.path.join(parent_dir, 'daily_portfolio_analysis.md')

        if not os.path.exists(analysis_file):
            raise FileNotFoundError(
                f"daily_portfolio_analysis.md not found at {analysis_file}\n"
                "Run with --report-only first to generate portfolio analysis"
            )

        with open(analysis_file, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"📄 Loaded portfolio analysis document ({len(content)} chars)")
        return content

    def run_agent_analysis(self, document_text: str) -> Dict:
        """Run all HF agents and collect their analyses"""

        print("\n🔬 Running HuggingFace agent analysis...")
        print("=" * 60)

        # Run news analysis
        print("\n📰 Running News Sentiment Analysis...")
        news_analysis = self.news_agent.analyze_portfolio_document(document_text, max_items=10)
        print(f"   Sentiment: {news_analysis.overall_sentiment}")
        print(f"   Confidence: {news_analysis.confidence:.1%}")
        print(f"   Tickers identified: {', '.join(news_analysis.mentioned_tickers[:5])}")

        # Run market analysis
        print("\n📊 Running Market Sentiment Analysis...")
        market_analysis = self.market_agent.analyze_portfolio_document(document_text)
        print(f"   Market Outlook: {market_analysis.market_sentiment}")
        print(f"   Strength: {market_analysis.strength}")
        print(f"   Confidence: {market_analysis.confidence:.1%}")

        # Run risk analysis
        print("\n🛡️  Running Risk Assessment...")
        risk_analysis = self.risk_agent.analyze_portfolio_document(document_text)
        print(f"   Risk Level: {risk_analysis.risk_level.upper()}")
        print(f"   Concerns: {len(risk_analysis.concerns)}")
        print(f"   Confidence: {risk_analysis.confidence:.1%}")

        # Run tone analysis (on combined summary)
        print("\n💬 Running Market Tone Analysis...")
        summary_text = self._create_summary_for_tone(news_analysis, market_analysis, risk_analysis)
        tone_result = self.tone_agent.analyze_text(summary_text)
        print(f"   Tone: {tone_result.sentiment if tone_result else 'N/A'}")

        print("\n✅ Agent analysis complete")

        return {
            "news": news_analysis,
            "market": market_analysis,
            "risk": risk_analysis,
            "tone": tone_result,
            "timestamp": datetime.now().isoformat()
        }

    def _create_summary_for_tone(self, news_analysis, market_analysis, risk_analysis) -> str:
        """Create a summary text for tone analysis"""

        summary_parts = []

        if news_analysis:
            summary_parts.append(f"News sentiment is {news_analysis.overall_sentiment}.")

        if market_analysis:
            summary_parts.append(
                f"Market outlook is {market_analysis.market_sentiment} with {market_analysis.strength} strength."
            )

        if risk_analysis:
            summary_parts.append(f"Portfolio risk level is {risk_analysis.risk_level}.")

        return " ".join(summary_parts)

    def generate_trading_document(self, analysis_results: Dict, portfolio_data: Dict = None) -> str:
        """Generate trading recommendations markdown document"""

        print("\n📝 Generating trading recommendations document...")

        news = analysis_results["news"]
        market = analysis_results["market"]
        risk = analysis_results["risk"]
        tone = analysis_results["tone"]

        # Document header
        doc = "# 🤖 LLM Trading Recommendations (HuggingFace Generated)\n\n"
        doc += "---\n\n"

        # Document metadata
        doc += "## 📅 DOCUMENT HEADER\n"
        doc += f"*Date: {datetime.now().strftime('%Y-%m-%d')}*  \n"
        doc += f"*Market Conditions: {self._generate_market_conditions(market, tone)}*  \n"
        doc += f"*Portfolio Performance: {self._generate_performance_summary(portfolio_data)}*  \n"
        doc += "\n---\n\n"

        # Risk management section
        doc += "## 🛡️ RISK MANAGEMENT UPDATES\n\n"
        doc += "### ⚙️ Dynamic Risk Parameters\n"
        doc += self._generate_risk_parameters(risk, market)
        doc += "\n"
        doc += "### 🎯 Position-Specific Risk Adjustments\n"
        doc += self._generate_position_risk_adjustments(risk, news)
        doc += "\n---\n\n"

        # Orders section (placeholder - user will fill in manually)
        doc += "## 📋 ORDERS SECTION\n\n"
        doc += "### 🔥 IMMEDIATE EXECUTION (HIGH PRIORITY)\n\n"
        doc += self._generate_order_suggestions(news, market, risk, "HIGH")
        doc += "\n"
        doc += "### ⚖️ POSITION MANAGEMENT (MEDIUM PRIORITY)\n\n"
        doc += self._generate_order_suggestions(news, market, risk, "MEDIUM")
        doc += "\n"
        doc += "### 📈 STRATEGIC POSITIONING (LOW PRIORITY)\n\n"
        doc += self._generate_order_suggestions(news, market, risk, "LOW")
        doc += "\n"

        # Market analysis section
        doc += "## MARKET ANALYSIS & RATIONALE\n\n"
        doc += "### Current Market Environment\n"
        doc += self._generate_market_environment(market, tone)
        doc += "\n\n"
        doc += "### Risk Assessment\n"
        doc += self._generate_risk_assessment(risk)
        doc += "\n\n"
        doc += "### News Sentiment Summary\n"
        doc += self._generate_news_summary(news)
        doc += "\n\n"

        # Strategic allocation section
        doc += "## STRATEGIC ALLOCATION TARGETS\n\n"
        doc += "### Target Portfolio Composition\n"
        doc += self._generate_allocation_targets(market, risk)
        doc += "\n"

        # Execution notes
        doc += "## EXECUTION NOTES\n\n"
        doc += "### AI Analysis Summary\n"
        doc += f"- **News Sentiment**: {news.overall_sentiment} (Confidence: {news.confidence:.1%})\n"
        doc += f"- **Market Outlook**: {market.market_sentiment} - {market.strength} (Confidence: {market.confidence:.1%})\n"
        doc += f"- **Risk Level**: {risk.risk_level.upper()} (Confidence: {risk.confidence:.1%})\n"
        doc += f"- **Overall Tone**: {tone.sentiment if tone else 'N/A'}\n"
        doc += "\n"
        doc += "### Recommendation Review Process\n"
        doc += "1. Review AI-generated order suggestions above\n"
        doc += "2. Manually validate each recommendation against current portfolio\n"
        doc += "3. Edit quantities, priorities, and reasoning as needed\n"
        doc += "4. Transfer approved orders to `manual_trades_override.json`\n"
        doc += "5. Execute with `python main.py --execute-manual-trades`\n"
        doc += "\n---\n\n"

        # Footer
        doc += f"*Generated by HuggingFace Agent System on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        doc += "*This is an AI-generated recommendation. Manual review and approval required before execution.*\n"

        print("✅ Trading document generated")
        return doc

    def _generate_market_conditions(self, market, tone) -> str:
        """Generate market conditions summary"""

        conditions = []

        if market:
            conditions.append(f"{market.market_sentiment} market outlook")
            conditions.append(f"{market.strength} strength")

        if tone and hasattr(tone, 'confidence'):
            conditions.append(f"tone confidence {tone.confidence:.1%}")

        if not conditions:
            return "Market analysis in progress"

        return ", ".join(conditions)

    def _generate_performance_summary(self, portfolio_data: Optional[Dict]) -> str:
        """Generate portfolio performance summary"""

        if not portfolio_data:
            return "Portfolio performance data not available - run --report-only first"

        # This would be populated from portfolio_data if available
        return "Performance metrics available in daily_portfolio_analysis.md"

    def _generate_risk_parameters(self, risk, market) -> str:
        """Generate risk management parameters"""

        params = ""

        # Determine risk budget based on risk level
        if risk.risk_level == "high":
            risk_budget = "CONSERVATIVE"
            cash_reserve = "15%"
            max_position = "15%"
        elif risk.risk_level == "low":
            risk_budget = "MODERATE-AGGRESSIVE"
            cash_reserve = "5%"
            max_position = "20%"
        else:  # medium
            risk_budget = "MODERATE"
            cash_reserve = "10%"
            max_position = "18%"

        params += f"**MAX-POSITION-SIZE {max_position}** - Based on {risk.risk_level} risk environment  \n"
        params += f"**CASH-RESERVE {cash_reserve}** - Liquidity buffer for {risk.risk_level} risk conditions  \n"
        params += f"**RISK-BUDGET {risk_budget}** - Aligned with current risk assessment  \n"

        return params

    def _generate_position_risk_adjustments(self, risk, news) -> str:
        """Generate position-specific risk adjustments"""

        adjustments = ""

        # Extract tickers with high/low sentiment from news
        if news and news.mentioned_tickers:
            # Suggest stop losses for positions mentioned in risk concerns
            for ticker in news.mentioned_tickers[:3]:
                if risk.risk_level == "high":
                    adjustments += f"**SET STOP-LOSS {ticker} -12%** - Protective stop in high-risk environment  \n"
                else:
                    adjustments += f"**SET STOP-LOSS {ticker} -15%** - Standard risk management  \n"

        if not adjustments:
            adjustments = "*Review individual position risks and set appropriate stop-loss levels*\n"

        return adjustments

    def _generate_order_suggestions(self, news, market, risk, priority: str) -> str:
        """Generate order suggestions based on agent analysis"""

        suggestions = ""

        # High priority: Strong signals with high confidence
        if priority == "HIGH":
            if market.market_sentiment == "Bullish" and news.overall_sentiment == "positive" and risk.risk_level != "high":
                suggestions += "**BUY [XXX] shares of [TICKER]** - Strong bullish signals with positive news sentiment and manageable risk  \n\n"
            elif market.market_sentiment == "Bearish" or risk.risk_level == "high":
                suggestions += "**SELL [XXX] shares of [TICKER]** - Bearish market outlook with elevated risk levels warrant defensive positioning  \n\n"
            else:
                suggestions += "*No high-priority orders suggested by AI - market signals mixed*\n\n"

        # Medium priority: Moderate signals
        elif priority == "MEDIUM":
            if news.confidence > 0.60 and market.confidence > 0.60:
                suggestions += "**HOLD all [XXX] shares of [TICKER]** - Moderate confidence in current positioning  \n\n"
            else:
                suggestions += "*Review positions with neutral sentiment for potential rebalancing*\n\n"

        # Low priority: Strategic adjustments
        else:  # LOW
            if risk.risk_level == "low" and market.market_sentiment != "Bearish":
                suggestions += "**BUY [XXX] shares of [TICKER]** - Strategic allocation increase in low-risk environment  \n\n"
            else:
                suggestions += "*Consider strategic adjustments based on long-term outlook*\n\n"

        return suggestions

    def _generate_market_environment(self, market, tone) -> str:
        """Generate market environment analysis"""

        analysis = f"Market sentiment shows {market.market_sentiment} outlook with {market.strength} strength. "

        if market.market_factors:
            factors = ", ".join(list(market.market_factors)[:5])
            analysis += f"Key market factors include: {factors}. "

        if tone and hasattr(tone, 'sentiment'):
            analysis += f"Overall market tone is {tone.sentiment}."

        return analysis

    def _generate_risk_assessment(self, risk) -> str:
        """Generate risk assessment text"""

        assessment = f"Current portfolio risk level assessed as **{risk.risk_level.upper()}** "
        assessment += f"with {risk.confidence:.1%} confidence. "

        if risk.concerns:
            assessment += f"\n\nIdentified {len(risk.concerns)} risk factors:\n"
            for concern in risk.concerns[:5]:
                assessment += f"- {concern}\n"

        if risk.recommended_actions:
            assessment += f"\nRecommended risk management actions:\n"
            for action in risk.recommended_actions[:3]:
                assessment += f"- {action}\n"

        return assessment

    def _generate_news_summary(self, news) -> str:
        """Generate news sentiment summary"""

        summary = f"Overall news sentiment is **{news.overall_sentiment.upper()}** "
        summary += f"with {news.confidence:.1%} confidence. "
        summary += f"Analyzed {news.news_items_analyzed} news items. "

        if news.mentioned_tickers:
            tickers = ", ".join(news.mentioned_tickers[:10])
            summary += f"\n\nTickers mentioned in news analysis: {tickers}"

        return summary

    def _generate_allocation_targets(self, market, risk) -> str:
        """Generate strategic allocation targets"""

        targets = ""

        # Adjust allocation based on market sentiment and risk
        if market.market_sentiment == "Bullish" and risk.risk_level == "low":
            targets += "- **Growth/Momentum**: 45%\n"
            targets += "- **Value/Cyclical**: 25%\n"
            targets += "- **Defensive/Quality**: 20%\n"
            targets += "- **Cash Reserve**: 10%\n"
        elif risk.risk_level == "high" or market.market_sentiment == "Bearish":
            targets += "- **Growth/Momentum**: 25%\n"
            targets += "- **Value/Cyclical**: 20%\n"
            targets += "- **Defensive/Quality**: 35%\n"
            targets += "- **Cash Reserve**: 20%\n"
        else:  # Moderate/Neutral
            targets += "- **Growth/Momentum**: 35%\n"
            targets += "- **Value/Cyclical**: 25%\n"
            targets += "- **Defensive/Quality**: 25%\n"
            targets += "- **Cash Reserve**: 15%\n"

        return targets

    def save_trading_document(self, content: str) -> str:
        """Save trading document to trading_recommendations directory"""

        # Create trading_recommendations directory in parent directory
        parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
        recommendations_dir = os.path.join(parent_dir, 'trading_recommendations')
        os.makedirs(recommendations_dir, exist_ok=True)

        # Generate filename with current date
        filename = f"trading_recommendations_{datetime.now().strftime('%Y%m%d')}.md"
        filepath = os.path.join(recommendations_dir, filename)

        # Save document
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"💾 Saved trading document to: {filename}")
        return filepath

    def generate_full_recommendation(self, portfolio_data: Optional[Dict] = None) -> str:
        """Complete workflow: Load portfolio, run analysis, generate document"""

        print("\n" + "=" * 60)
        print("🤖 HUGGINGFACE TRADING RECOMMENDATION GENERATOR")
        print("=" * 60)

        # Load portfolio document
        portfolio_document = self.load_portfolio_document()

        # Run agent analysis
        analysis_results = self.run_agent_analysis(portfolio_document)

        # Generate trading document
        trading_document = self.generate_trading_document(analysis_results, portfolio_data)

        # Save document
        filepath = self.save_trading_document(trading_document)

        print("\n" + "=" * 60)
        print("✅ RECOMMENDATION GENERATION COMPLETE")
        print("=" * 60)
        print(f"\n📄 Document saved to: {filepath}")
        print(f"\n📋 Next steps:")
        print(f"   1. Review the generated recommendations in {os.path.basename(filepath)}")
        print(f"   2. Manually edit Portfolio Scripts Schwab/manual_trades_override.json")
        print(f"   3. Set 'enabled': true in manual_trades_override.json")
        print(f"   4. Execute trades with: python main.py")
        print()

        return filepath


def main():
    """Standalone execution for testing"""
    generator = HFRecommendationGenerator()
    generator.generate_full_recommendation()


if __name__ == "__main__":
    main()
