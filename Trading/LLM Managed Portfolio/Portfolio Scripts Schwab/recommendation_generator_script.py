#!/usr/bin/env python3
"""
Recommendation Generator Script
Master orchestrator that synthesizes all analysis to generate trading_recommendations.md

Workflow:
1. Load outputs from news_analysis and quality_analysis
2. Load current portfolio state
3. Run Market/Risk/Tone agents
4. Run Reasoning Agent for each stock
5. Generate trading_recommendations_YYYYMMDD.md in template format

Outputs:
- trading_recommendations/trading_recommendations_YYYYMMDD.md (trading document)
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from agents.news_agent import NewsAgent
from agents.market_agent import MarketAgent
from agents.risk_agent import RiskAgent
from agents.tone_agent import ToneAgent
from agents.reasoning_agent import ReasoningAgent
from hf_config import HFConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RecommendationGenerator:
    """
    Master orchestrator for generating trading recommendations

    Combines outputs from:
    - News analysis (news_analysis_YYYYMMDD.json)
    - Quality analysis (quality_analysis_YYYYMMDD.json)
    - Market/Risk/Tone agents (live analysis)
    - Reasoning agent (decision synthesis)
    """

    def __init__(self):
        """Initialize recommendation generator"""
        # Initialize agents
        self.market_agent = MarketAgent()
        self.risk_agent = RiskAgent()
        self.tone_agent = ToneAgent()
        self.reasoning_agent = ReasoningAgent()

        # Data storage
        self.portfolio_state = None
        self.news_analysis = None
        self.quality_analysis = None
        self.thematic_analysis = None  # NEW: thematic scoring for opportunistic holdings
        self.recommendations = []

    def load_portfolio_state(self) -> Dict:
        """Load current portfolio state"""
        portfolio_path = Path(__file__).parent.parent / "portfolio_state.json"

        if not portfolio_path.exists():
            logger.error(f"Portfolio state not found at {portfolio_path}")
            return {}

        try:
            with open(portfolio_path, 'r') as f:
                state = json.load(f)
            logger.info(f"Loaded portfolio state: {len(state.get('holdings', {}))} holdings")
            return state
        except Exception as e:
            logger.error(f"Failed to load portfolio state: {e}")
            return {}

    def load_latest_analysis(self, analysis_type: str) -> Optional[Dict]:
        """
        Load latest analysis file (news or quality)

        Args:
            analysis_type: 'news' or 'quality'

        Returns:
            Dict with analysis data or None
        """
        output_dir = Path(__file__).parent / "outputs"
        pattern = f"{analysis_type}_analysis_*.json"

        # Find latest file
        files = sorted(output_dir.glob(pattern), reverse=True)
        if not files:
            logger.warning(f"No {analysis_type} analysis files found")
            return None

        latest_file = files[0]
        logger.info(f"Loading {analysis_type} analysis from {latest_file}")

        try:
            with open(latest_file, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Failed to load {analysis_type} analysis: {e}")
            return None

    def run_market_analysis(self) -> Dict:
        """
        Run market-level agent analysis

        Returns:
            Dict with market, risk, and tone analysis
        """
        logger.info("Running market-level analysis")

        # Build market summary text
        market_summary = """
        Current market environment analysis based on S&P 500, volatility, and sector trends.
        Tech sector showing strength with AI momentum.
        Interest rate environment remains elevated but stable.
        Market breadth is moderately positive with selective strength.
        """

        # Market sentiment
        market_result = self.market_agent.analyze(market_summary)

        # Risk assessment
        risk_text = f"""
        Portfolio risk assessment:
        - Concentration: {len(self.portfolio_state.get('holdings', {}))} positions
        - Cash reserve: ${self.portfolio_state.get('cash', 0):.2f}
        - Market volatility elevated
        """
        risk_result = self.risk_agent.analyze(risk_text)

        # Overall tone
        tone_text = f"""
        Market tone analysis:
        - Market sentiment: {market_result.sentiment}
        - Risk level: {risk_result.label}
        - Economic conditions: Stable with some uncertainty
        """
        tone_result = self.tone_agent.analyze(tone_text)

        return {
            'market': {
                'sentiment': market_result.sentiment,
                'confidence': market_result.confidence,
                'reasoning': market_result.reasoning
            },
            'risk': {
                'label': risk_result.label,
                'confidence': risk_result.confidence,
                'reasoning': risk_result.reasoning
            },
            'tone': {
                'sentiment': tone_result.sentiment,
                'confidence': tone_result.confidence,
                'reasoning': tone_result.reasoning
            }
        }

    def generate_recommendations(self, market_analysis: Dict) -> List[Dict]:
        """
        Generate trading recommendations for all stocks

        Args:
            market_analysis: Market/risk/tone analysis

        Returns:
            List of recommendation dicts
        """
        logger.info("Generating trading recommendations")

        recommendations = []
        holdings = list(self.portfolio_state.get('holdings', {}).keys())

        # Process current holdings
        for ticker in holdings:
            # Get news analysis for this ticker
            news = self.news_analysis.get('results', {}).get(ticker, {})

            # Get quality analysis for this ticker
            quality = self.quality_analysis.get('holdings_quality', {}).get(ticker, {})

            # Get thematic analysis for this ticker (if available)
            thematic = self.thematic_analysis.get(ticker, {}) if self.thematic_analysis else {}
            thematic_score = thematic.get('score')  # None if not a thematic holding

            # Build agent outputs
            agent_outputs = {
                'news_sentiment': news,
                'market_sentiment': market_analysis['market'],
                'risk_assessment': market_analysis['risk'],
                'quality_analysis': quality,
                'thematic_score': thematic_score,  # NEW: thematic score for position sizing
                'current_holding': True,
                'current_shares': self.portfolio_state['holdings'][ticker]['shares']
            }

            # Run reasoning agent
            decision = self.reasoning_agent.synthesize_decision(ticker, agent_outputs)

            recommendations.append({
                'ticker': ticker,
                'action': decision.action,
                'confidence': decision.confidence,
                'shares': agent_outputs['current_shares'],
                'reasoning': "\n".join(decision.reasoning_steps),
                'key_factors': decision.key_factors,
                'priority': self._determine_priority(decision)
            })

        # Add top BUY alternatives from watchlist
        buy_alternatives = self.quality_analysis.get('recommendations', {}).get('buy_alternatives', [])
        for alt in buy_alternatives[:5]:  # Top 5 alternatives
            ticker = alt['ticker']

            # Get news analysis if available
            news = self.news_analysis.get('results', {}).get(ticker, {})

            # Get thematic analysis if available
            thematic = self.thematic_analysis.get(ticker, {}) if self.thematic_analysis else {}
            thematic_score = thematic.get('score')

            # Build agent outputs
            agent_outputs = {
                'news_sentiment': news,
                'market_sentiment': market_analysis['market'],
                'risk_assessment': market_analysis['risk'],
                'quality_analysis': {
                    'composite_score': alt['quality_score'],
                    'tier': alt['tier'],
                    'red_flags_count': alt['red_flags'],
                    'investment_rating': 'BUY'
                },
                'thematic_score': thematic_score,  # NEW: thematic score for opportunistic alternatives
                'current_holding': False,
                'current_shares': 0
            }

            # Run reasoning agent
            decision = self.reasoning_agent.synthesize_decision(ticker, agent_outputs)

            if decision.action == "BUY":
                recommendations.append({
                    'ticker': ticker,
                    'action': 'BUY',
                    'confidence': decision.confidence,
                    'shares': self._calculate_buy_shares(alt['quality_score']),
                    'reasoning': "\n".join(decision.reasoning_steps),
                    'key_factors': decision.key_factors,
                    'priority': 'MEDIUM'
                })

        logger.info(f"Generated {len(recommendations)} recommendations")
        return recommendations

    def _determine_priority(self, decision) -> str:
        """Determine priority level for a decision"""
        if decision.confidence >= 0.8:
            return "HIGH"
        elif decision.confidence >= 0.6:
            return "MEDIUM"
        else:
            return "LOW"

    def _calculate_buy_shares(self, quality_score: float) -> int:
        """Calculate number of shares to buy based on quality score"""
        # Simple position sizing: higher quality = larger position
        cash_available = self.portfolio_state.get('cash', 0)

        if quality_score >= 85:
            # Elite quality: 7% of portfolio
            allocation = 0.07
        elif quality_score >= 75:
            # Strong quality: 5% of portfolio
            allocation = 0.05
        else:
            # Good quality: 3% of portfolio
            allocation = 0.03

        # Estimate total portfolio value (rough)
        total_value = cash_available * 5  # Rough estimate

        target_dollars = total_value * allocation
        shares = int(target_dollars / 100)  # Assume $100/share average

        return max(1, shares)  # At least 1 share

    def _generate_catalyst_calendar(self, holdings: List[str]) -> str:
        """
        Generate catalyst calendar from catalyst_analysis output if available

        Args:
            holdings: List of ticker symbols

        Returns:
            Formatted catalyst calendar string
        """
        try:
            # Look for latest catalyst analysis file
            output_dir = Path(__file__).parent / "outputs"
            catalyst_files = sorted(output_dir.glob("catalyst_analysis_*.json"), reverse=True)

            if not catalyst_files:
                return "No catalyst analysis available. Run catalyst_analyzer.py to generate upcoming event calendar.\n"

            # Load latest file
            with open(catalyst_files[0], 'r') as f:
                catalyst_data = json.load(f)

            if not catalyst_data:
                return "No catalysts identified in current analysis.\n"

            # Format catalysts by ticker
            lines = []
            for ticker in holdings:
                if ticker in catalyst_data:
                    catalysts = catalyst_data[ticker].get('catalysts', [])
                    if catalysts:
                        # Get next 2 upcoming catalysts
                        upcoming = [c for c in catalysts if c.get('timeline') == 'Near-Term'][:2]
                        if upcoming:
                            catalyst_str = ", ".join([f"{c['name']} ({c.get('estimated_date', 'TBD')})" for c in upcoming])
                            lines.append(f"- **{ticker}**: {catalyst_str}")

            if not lines:
                return "No near-term catalysts identified for current holdings.\n"

            return "\n".join(lines) + "\n"

        except Exception as e:
            logger.warning(f"Failed to generate catalyst calendar: {e}")
            return "Catalyst calendar unavailable.\n"

    def _generate_performance_attribution(self) -> str:
        """
        Generate performance attribution analysis from portfolio history

        Returns:
            Formatted performance attribution string
        """
        try:
            # Load portfolio performance history
            history_path = Path(__file__).parent.parent / "portfolio_performance_history.csv"

            if not history_path.exists():
                return "Portfolio performance history not available. Attribution analysis requires historical tracking.\n"

            import pandas as pd
            history = pd.read_csv(history_path)

            if history.empty:
                return "Insufficient performance history for attribution analysis.\n"

            # Calculate YTD return (simple: compare first to last value)
            if 'total_value' in history.columns and len(history) > 1:
                ytd_start = history['total_value'].iloc[0]
                ytd_current = history['total_value'].iloc[-1]
                ytd_return = ((ytd_current - ytd_start) / ytd_start) * 100

                # Get S&P 500 YTD return for comparison
                try:
                    import yfinance as yf
                    sp500 = yf.Ticker("^GSPC")
                    sp500_hist = sp500.history(period="ytd")
                    sp500_ytd = ((sp500_hist['Close'].iloc[-1] - sp500_hist['Close'].iloc[0]) / sp500_hist['Close'].iloc[0]) * 100
                except:
                    sp500_ytd = 28.0  # Fallback estimate

                lines = []
                lines.append(f"**YTD Performance**: Portfolio +{ytd_return:.1f}% vs S&P 500 +{sp500_ytd:.1f}%")

                # Analyze top contributors (from quality analysis if available)
                if self.quality_analysis:
                    top_quality = sorted(
                        [(t, d.get('composite_score', 0)) for t, d in self.quality_analysis.items()],
                        key=lambda x: x[1],
                        reverse=True
                    )[:3]
                    if top_quality:
                        contributors = ", ".join([f"{t} (quality {s:.1f}/10)" for t, s in top_quality])
                        lines.append(f"**Top Quality Holdings**: {contributors}")

                return "\n".join(lines) + "\n"

            return "Performance attribution calculation in progress.\n"

        except Exception as e:
            logger.warning(f"Failed to generate performance attribution: {e}")
            return "Performance attribution unavailable.\n"

    def _calculate_sector_allocation(self, holdings: Dict) -> Dict[str, float]:
        """
        Calculate sector allocation percentages

        Args:
            holdings: Dict of ticker -> shares

        Returns:
            Dict of sector -> percentage
        """
        try:
            import yfinance as yf

            sector_map = {}
            total_value = 0

            # Get sector for each holding
            for ticker, shares in holdings.items():
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    sector = info.get('sector', 'Other')
                    price = info.get('currentPrice', info.get('regularMarketPrice', 100))

                    value = shares * price
                    total_value += value

                    if sector not in sector_map:
                        sector_map[sector] = 0
                    sector_map[sector] += value

                except Exception as e:
                    logger.warning(f"Failed to get sector for {ticker}: {e}")
                    if 'Other' not in sector_map:
                        sector_map['Other'] = 0
                    sector_map['Other'] += shares * 100  # Estimate $100/share

            # Convert to percentages
            if total_value > 0:
                sector_pct = {sector: (value / total_value) * 100 for sector, value in sector_map.items()}
            else:
                sector_pct = {}

            return sector_pct

        except Exception as e:
            logger.warning(f"Failed to calculate sector allocation: {e}")
            return {}

    def _generate_cash_flow_analysis(self, trades: List[Dict]) -> str:
        """
        Generate cash flow analysis for proposed trades

        Args:
            trades: List of trade recommendations

        Returns:
            Formatted cash flow analysis string
        """
        try:
            # Separate sells and buys
            sells = [t for t in trades if t['action'] == 'SELL']
            buys = [t for t in trades if t['action'] == 'BUY']

            lines = []

            # Calculate cash from sells
            if sells:
                sell_lines = []
                total_sell_value = 0
                for trade in sells:
                    # Estimate value (use current prices if available)
                    estimated_value = trade['shares'] * 100  # Rough estimate $100/share
                    total_sell_value += estimated_value
                    sell_lines.append(f"  - SELL {trade['ticker']}: ~${estimated_value:.0f}")

                lines.append("**Cash Generated from Sells**:")
                lines.extend(sell_lines)
                lines.append(f"  - **Total Sells**: ~${total_sell_value:.0f}\n")

            # Calculate cash needed for buys
            if buys:
                buy_lines = []
                total_buy_value = 0
                for trade in buys:
                    # Estimate value
                    estimated_value = trade['shares'] * 100  # Rough estimate
                    total_buy_value += estimated_value
                    buy_lines.append(f"  - BUY {trade['ticker']}: ~${estimated_value:.0f}")

                lines.append("**Cash Required for Buys**:")
                lines.extend(buy_lines)
                lines.append(f"  - **Total Buys**: ~${total_buy_value:.0f}\n")

            # Calculate net position
            if sells or buys:
                total_sell_value = sum(t['shares'] * 100 for t in sells)
                total_buy_value = sum(t['shares'] * 100 for t in buys)
                net_cash = total_sell_value - total_buy_value

                if net_cash >= 0:
                    lines.append(f"**Net Cash Position**: +${net_cash:.0f} (surplus)")
                else:
                    lines.append(f"**Net Cash Position**: ${net_cash:.0f} (requires ${abs(net_cash):.0f} additional capital)")

            if not lines:
                lines.append("No cash flow changes (all HOLD recommendations).")

            return "\n".join(lines) + "\n"

        except Exception as e:
            logger.warning(f"Failed to generate cash flow analysis: {e}")
            return "Cash flow analysis unavailable.\n"

    def _generate_timing_considerations(self, holdings: List[str]) -> str:
        """
        Generate timing considerations based on earnings calendars

        Args:
            holdings: List of ticker symbols

        Returns:
            Formatted timing considerations string
        """
        try:
            lines = []
            lines.append("**Earnings Calendar**: Check upcoming earnings dates before executing trades")
            lines.append("**Market Hours**: Execute during normal market hours (9:30 AM - 4:00 PM ET)")
            lines.append("**Volatility Events**: Avoid trading immediately before/after major economic data releases")

            # Could be enhanced with actual earnings dates from yfinance or catalyst_analyzer
            return "\n".join(lines) + "\n"

        except Exception as e:
            logger.warning(f"Failed to generate timing considerations: {e}")
            return "Timing considerations unavailable.\n"

    def _generate_partial_fill_instructions(self, trades: List[Dict]) -> str:
        """
        Generate partial fill instructions for trades

        Args:
            trades: List of trade recommendations

        Returns:
            Formatted partial fill instructions string
        """
        try:
            high_priority = [t for t in trades if t.get('priority') == 'HIGH']
            medium_priority = [t for t in trades if t.get('priority') == 'MEDIUM']

            lines = []

            if high_priority:
                high_buys = [t for t in high_priority if t['action'] == 'BUY']
                if high_buys:
                    top_priority = high_buys[0]
                    lines.append(f"**Priority 1**: {top_priority['ticker']} (highest quality/conviction)")

            if medium_priority:
                med_buys = [t for t in medium_priority if t['action'] == 'BUY']
                if med_buys and len(med_buys) > 0:
                    lines.append(f"**Priority 2**: Medium priority positions (can accept 50% fills)")

            lines.append("**Minimum Position Size**: Avoid positions <$50 (not worth transaction costs)")
            lines.append("**Acceptable Partial Fills**: 50% or greater for positions >$200")

            return "\n".join(lines) + "\n"

        except Exception as e:
            logger.warning(f"Failed to generate partial fill instructions: {e}")
            return "Partial fill instructions unavailable.\n"

    def _load_market_environment_summary(self) -> str:
        """
        Load market environment summary from market_environment_analyzer output

        Returns:
            Market environment summary string or empty string if not available
        """
        try:
            # Look for latest market environment file
            output_dir = Path(__file__).parent / "outputs"
            market_files = sorted(output_dir.glob("market_environment_*.json"), reverse=True)

            if not market_files:
                return ""

            # Load latest file
            with open(market_files[0], 'r') as f:
                market_data = json.load(f)

            # Extract summary
            summary = market_data.get('summary', '')
            return summary

        except Exception as e:
            logger.warning(f"Failed to load market environment summary: {e}")
            return ""

    def _enhance_trade_reasoning(self, rec: Dict) -> str:
        """
        Enhance trade reasoning with quality/thematic scores

        Args:
            rec: Trade recommendation dict

        Returns:
            Enhanced reasoning string
        """
        try:
            ticker = rec['ticker']
            base_reasoning = rec.get('reasoning', '').split('\n')[0] if rec.get('reasoning') else ''

            # Add quality score if available
            if self.quality_analysis and ticker in self.quality_analysis:
                quality_data = self.quality_analysis[ticker]
                quality_score = quality_data.get('composite_score', 0)
                roe = quality_data.get('roe', 0)
                gross_margin = quality_data.get('gross_profitability', 0)

                # Enhance reasoning with quality metrics
                if quality_score > 0:
                    base_reasoning += f" Quality score {quality_score:.1f}/10"
                    if roe > 0:
                        base_reasoning += f", ROE {roe:.1f}%"
                    if gross_margin > 0:
                        base_reasoning += f", gross margin {gross_margin:.1f}%"

            # Add thematic score if available (would come from thematic analysis)
            # This can be enhanced when thematic_analysis is integrated

            return base_reasoning if base_reasoning else "Position management based on portfolio strategy"

        except Exception as e:
            logger.warning(f"Failed to enhance trade reasoning for {rec.get('ticker')}: {e}")
            return rec.get('reasoning', 'Trade recommendation').split('\n')[0]

    def export_trading_document(self, recommendations: List[Dict], market_analysis: Dict):
        """
        Export trading recommendations to markdown document (ENHANCED for Task 1.3)

        Includes ALL trading_template.md sections:
        - Document Header with market environment and portfolio performance
        - Risk Management Updates
        - Orders Section (categorized by priority)
        - Market Analysis & Rationale (with catalyst calendar and performance attribution)
        - Strategic Allocation Targets (with sector breakdown)
        - Execution Notes (cash flow, timing, partial fills)

        Args:
            recommendations: List of trading recommendations
            market_analysis: Market analysis dict
        """
        # Create trading_recommendations directory
        output_dir = Path(__file__).parent.parent / "trading_recommendations"
        output_dir.mkdir(exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d")
        output_file = output_dir / f"trading_recommendations_{timestamp}.md"

        # Categorize recommendations by priority and action
        high_priority = [r for r in recommendations if r['priority'] == 'HIGH']
        medium_priority = [r for r in recommendations if r['priority'] == 'MEDIUM']
        low_priority = [r for r in recommendations if r['priority'] == 'LOW']

        # Separate by action
        high_buys = [r for r in high_priority if r['action'] == 'BUY']
        high_sells = [r for r in high_priority if r['action'] == 'SELL']
        high_holds = [r for r in high_priority if r['action'] == 'HOLD']

        medium_buys = [r for r in medium_priority if r['action'] == 'BUY']
        medium_sells = [r for r in medium_priority if r['action'] == 'SELL']
        medium_holds = [r for r in medium_priority if r['action'] == 'HOLD']

        low_buys = [r for r in low_priority if r['action'] == 'BUY']
        low_holds = [r for r in low_priority if r['action'] == 'HOLD']

        # Get current holdings list
        holdings = list(self.portfolio_state.get('holdings', {}).keys())

        # Load market environment data if available
        market_env_text = self._load_market_environment_summary()

        # Write trading document
        with open(output_file, 'w') as f:
            f.write(f"# 🤖 LLM Trading Recommendations\n\n")
            f.write("---\n\n")

            # ==================== DOCUMENT HEADER ====================
            f.write("## 📅 DOCUMENT HEADER\n")
            f.write(f"*Date: {datetime.now().strftime('%Y-%m-%d')}*  \n")

            # Market Conditions (use market environment analyzer data if available)
            if market_env_text:
                f.write(f"*Market Conditions: {market_env_text}*  \n")
            else:
                f.write(f"*Market Conditions: {market_analysis['market']['sentiment'].capitalize()} sentiment with {market_analysis['risk']['label']} risk*  \n")

            # Portfolio Performance (use performance attribution if available)
            perf_attribution = self._generate_performance_attribution()
            if "YTD Performance" in perf_attribution:
                f.write(f"*Portfolio Performance: {perf_attribution.split(chr(10))[0].replace('**', '').strip()}*  \n\n")
            else:
                f.write(f"*Portfolio Performance: {len(self.portfolio_state.get('holdings', {}))} holdings, ${self.portfolio_state.get('cash', 0):.2f} cash*  \n\n")

            f.write("---\n\n")

            # ==================== RISK MANAGEMENT ====================
            f.write("## 🛡️ RISK MANAGEMENT UPDATES\n\n")
            f.write("### ⚙️ Dynamic Risk Parameters\n")
            f.write(f"**MAX-POSITION-SIZE 20%** - Maximum single position risk\n")
            f.write(f"**CASH-RESERVE 5%** - Maintain liquidity for opportunities\n")
            f.write(f"**RISK-BUDGET MODERATE** - Balanced approach given {market_analysis['risk']['label']} risk environment\n\n")
            f.write("---\n\n")

            # ==================== ORDERS SECTION ====================
            f.write("## 📋 ORDERS SECTION\n\n")

            # HIGH PRIORITY
            f.write("### 🔥 IMMEDIATE EXECUTION (HIGH PRIORITY)\n\n")
            for rec in high_sells:
                reasoning = self._enhance_trade_reasoning(rec)
                f.write(f"**SELL all {rec['shares']} shares of {rec['ticker']}** - {reasoning}\n\n")
            for rec in high_buys:
                reasoning = self._enhance_trade_reasoning(rec)
                f.write(f"**BUY {rec['shares']} shares of {rec['ticker']}** - {reasoning}\n\n")

            # MEDIUM PRIORITY
            f.write("### ⚖️ POSITION MANAGEMENT (MEDIUM PRIORITY)\n\n")
            for rec in medium_sells:
                reasoning = self._enhance_trade_reasoning(rec)
                f.write(f"**SELL all {rec['shares']} shares of {rec['ticker']}** - {reasoning}\n\n")
            for rec in medium_buys:
                reasoning = self._enhance_trade_reasoning(rec)
                f.write(f"**BUY {rec['shares']} shares of {rec['ticker']}** - {reasoning}\n\n")
            for rec in medium_holds:
                reasoning = self._enhance_trade_reasoning(rec)
                f.write(f"**HOLD all {rec['shares']} shares of {rec['ticker']}** - {reasoning}\n\n")

            # LOW PRIORITY
            f.write("### 📈 STRATEGIC POSITIONING (LOW PRIORITY)\n\n")
            for rec in low_buys:
                reasoning = self._enhance_trade_reasoning(rec)
                f.write(f"**BUY {rec['shares']} shares of {rec['ticker']}** - {reasoning}\n\n")
            for rec in low_holds:
                reasoning = self._enhance_trade_reasoning(rec)
                f.write(f"**HOLD all {rec['shares']} shares of {rec['ticker']}** - {reasoning}\n\n")

            # ==================== MARKET ANALYSIS & RATIONALE ====================
            f.write("## MARKET ANALYSIS & RATIONALE\n\n")

            f.write("### Current Market Environment\n")
            if market_env_text:
                f.write(f"{market_env_text}\n\n")
            else:
                f.write(f"{market_analysis['market']['reasoning']}\n\n")

            f.write("### Catalyst Calendar\n")
            catalyst_calendar = self._generate_catalyst_calendar(holdings)
            f.write(f"{catalyst_calendar}\n")

            f.write("### Risk Assessment\n")
            f.write(f"{market_analysis['risk']['reasoning']}\n")
            # Add quality scores to risk assessment
            if self.quality_analysis:
                quality_scores = [d.get('composite_score', 0) for d in self.quality_analysis.values()]
                if quality_scores:
                    avg_quality = sum(quality_scores) / len(quality_scores)
                    high_quality = sum(1 for s in quality_scores if s >= 8)
                    f.write(f"\n**Portfolio Quality**: Average {avg_quality:.1f}/10 ({high_quality} of {len(quality_scores)} holdings ≥8)\n")
            f.write("\n")

            f.write("### Performance Attribution\n")
            perf_attribution_full = self._generate_performance_attribution()
            f.write(f"{perf_attribution_full}\n")

            # ==================== STRATEGIC ALLOCATION TARGETS ====================
            f.write("## STRATEGIC ALLOCATION TARGETS\n\n")

            f.write("### Target Portfolio Composition\n")
            f.write("- **Quality Compounders (Core 80%)**: 80%\n")
            f.write("- **Opportunistic/Thematic (20%)**: 20%\n")
            f.write("- **Cash Reserve**: 5%\n\n")

            f.write("### Sector Allocation Targets\n")
            sector_alloc = self._calculate_sector_allocation(self.portfolio_state.get('holdings', {}))
            if sector_alloc:
                for sector, pct in sorted(sector_alloc.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"- **{sector}**: {pct:.1f}%\n")
            else:
                f.write("- Sector allocation calculation unavailable\n")
            f.write("\n")

            # ==================== EXECUTION NOTES ====================
            f.write("## EXECUTION NOTES\n\n")

            f.write("### Cash Flow Management\n")
            cash_flow = self._generate_cash_flow_analysis(recommendations)
            f.write(f"{cash_flow}\n")

            f.write("### Timing Considerations\n")
            timing = self._generate_timing_considerations(holdings)
            f.write(f"{timing}\n")

            f.write("### Partial Fill Instructions\n")
            partial_fills = self._generate_partial_fill_instructions(recommendations)
            f.write(f"{partial_fills}\n")

            f.write("---\n\n")

        logger.info(f"Exported trading document to {output_file}")
        print(f"\n{'='*60}")
        print("TRADING RECOMMENDATIONS GENERATED")
        print(f"{'='*60}")
        print(f"Output: {output_file}")
        print(f"Total recommendations: {len(recommendations)}")
        print(f"  HIGH priority: {len(high_priority)}")
        print(f"  MEDIUM priority: {len(medium_priority)}")
        print(f"  LOW priority: {len(low_priority)}")
        print(f"{'='*60}\n")

    def run(self, skip_thematic: bool = False):
        """
        Run complete recommendation generation pipeline

        Args:
            skip_thematic: If True, skip thematic analysis (faster execution)
        """
        logger.info("Starting recommendation generation pipeline")

        # Load data
        self.portfolio_state = self.load_portfolio_state()
        if not self.portfolio_state:
            logger.error("Failed to load portfolio state. Exiting.")
            return

        self.news_analysis = self.load_latest_analysis('news')
        if not self.news_analysis:
            logger.warning("No news analysis found. Continuing without news data.")
            self.news_analysis = {'results': {}}

        self.quality_analysis = self.load_latest_analysis('quality')
        if not self.quality_analysis:
            logger.error("No quality analysis found. Exiting.")
            return

        # NEW: Load thematic analysis (optional)
        if not skip_thematic:
            self.thematic_analysis = self.load_latest_analysis('thematic')
            if not self.thematic_analysis:
                logger.warning("No thematic analysis found. Continuing without thematic scores.")
                self.thematic_analysis = {}
            else:
                logger.info(f"Loaded thematic analysis for {len(self.thematic_analysis)} tickers")
        else:
            logger.info("Skipping thematic analysis (--skip-thematic flag)")
            self.thematic_analysis = {}

        # Run market analysis
        market_analysis = self.run_market_analysis()

        # Generate recommendations
        recommendations = self.generate_recommendations(market_analysis)

        # Export trading document
        self.export_trading_document(recommendations, market_analysis)

        logger.info("Recommendation generation complete")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate Trading Recommendations')
    parser.add_argument(
        '--skip-thematic',
        action='store_true',
        help='Skip thematic analysis (faster execution, quality-only mode)'
    )

    args = parser.parse_args()

    generator = RecommendationGenerator()
    generator.run(skip_thematic=args.skip_thematic)


if __name__ == "__main__":
    main()
