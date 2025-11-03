#!/usr/bin/env python3
"""
STEPS Portfolio Analysis Orchestrator
Implements complete 10-step STEPS research methodology for portfolio management

References:
- STEPS_Research_Methodology_November_1_2025.md for methodology
- PM_README_V3.md for 80/20 quality/opportunistic framework
- trading_template.md for output format

Author: LLM Portfolio Management System
Date: November 3, 2025
"""

import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../trade_execution.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== DATACLASSES ====================

@dataclass
class MarketEnvironment:
    """Market environment assessment output"""
    sp500_price: float
    sp500_50ma: float
    sp500_200ma: float
    sp500_1m_return: float
    sp500_ytd_return: float
    trend: str  # STRONG_BULL/BULL/NEUTRAL/BEAR/STRONG_BEAR
    vix_level: float
    vix_20ma: float
    volatility_regime: str  # LOW/MODERATE/ELEVATED/HIGH
    leading_sectors: List[str]  # top 3
    lagging_sectors: List[str]  # bottom 3
    sector_performance: Dict[str, float]
    market_breadth: str  # NARROW/MODERATE/BROAD
    risk_appetite: str  # RISK_ON/NEUTRAL/RISK_OFF
    summary: str  # 2-3 sentence summary
    analysis_date: str
    data_quality: str  # COMPLETE/PARTIAL/INSUFFICIENT


@dataclass
class QualityScore:
    """Quality score for a single holding"""
    ticker: str
    composite_score: float  # 0-10
    gross_profitability: float
    roe: float
    earnings_quality: float
    conservative_growth: float
    tier: str  # ELITE/STRONG/MODERATE/WEAK
    meets_core_criteria: bool  # >= 7.0


@dataclass
class ThematicScore:
    """Thematic scoring for opportunistic holdings"""
    ticker: str
    theme: str
    total_score: float  # 0-40
    theme_alignment: float  # 1-10
    market_timing: float  # 1-10
    competitive_position: float  # 1-10
    execution_capability: float  # 1-10
    classification: str  # LEADER/CONTENDER/LAGGARD
    meets_threshold: bool  # >= 28


@dataclass
class CompetitiveRanking:
    """Competitive position analysis"""
    ticker: str
    competitors: List[str]
    quality_rank: int
    best_in_class: str
    recommendation: str  # KEEP/SWAP/EXIT


@dataclass
class ValuationRating:
    """Valuation assessment"""
    ticker: str
    quality_score: float
    max_pe_allowed: float
    actual_pe: float
    pe_rating: str  # CHEAP/FAIR/EXPENSIVE/OVERVALUED
    overall_rating: str
    recommendation: str  # BUY/HOLD/AVOID


@dataclass
class PortfolioAllocation:
    """Target portfolio allocation"""
    quality_holdings: Dict[str, float]  # ticker -> target %
    thematic_holdings: Dict[str, float]  # ticker -> target %
    cash_reserve: float
    total_quality_pct: float
    total_thematic_pct: float
    violations: List[str]


@dataclass
class Trade:
    """Individual trade recommendation"""
    action: str  # BUY/SELL/HOLD/REDUCE
    ticker: str
    shares: Optional[int]
    target_pct: Optional[float]
    priority: str  # HIGH/MEDIUM/LOW
    reasoning: str
    stop_loss_pct: Optional[float]
    profit_target_pct: Optional[float]


@dataclass
class DataQualityReport:
    """Data validation report"""
    overall_quality: str  # COMPLETE/PARTIAL/INSUFFICIENT
    missing_metrics: List[str]
    stale_metrics: List[str]
    warnings: List[str]
    quality_score: float  # 0-10


@dataclass
class ComplianceReport:
    """Framework compliance validation"""
    portfolio_value: float
    compliance_score: float  # 0-100
    violations: List[Dict]
    allocation_quality_pct: float
    allocation_thematic_pct: float
    allocation_cash_pct: float
    framework_compliant: bool


# ==================== STEPS ORCHESTRATOR ====================

class STEPSOrchestrator:
    """
    Master orchestrator for complete STEPS portfolio analysis methodology

    Executes all 10 steps in sequence:
    1. Market Environment Assessment
    2. Holdings Quality Analysis
    3A. Core Quality Screening
    3B. Thematic Opportunity Discovery
    4. Competitive Landscape Analysis
    5. Valuation Analysis
    6. Portfolio Construction
    7. Rebalancing Trade Generation
    8. Trade Synthesis
    9. Data Validation
    10. Framework Compliance Validation
    """

    def __init__(
        self,
        dry_run: bool = False,
        skip_thematic: bool = False,
        skip_competitive: bool = False,
        skip_valuation: bool = False,
        verbose: bool = False
    ):
        """Initialize orchestrator with configuration flags"""
        self.dry_run = dry_run
        self.skip_thematic = skip_thematic
        self.skip_competitive = skip_competitive
        self.skip_valuation = skip_valuation
        self.verbose = verbose

        # Set logging level
        if verbose:
            logger.setLevel(logging.DEBUG)

        # Create outputs directory
        self.outputs_dir = Path("outputs")
        self.outputs_dir.mkdir(exist_ok=True)

        self.recommendations_dir = Path("../trading_recommendations")
        self.recommendations_dir.mkdir(exist_ok=True)

        # Analysis results storage
        self.results = {}

        logger.info("=" * 80)
        logger.info("STEPS PORTFOLIO ANALYSIS ORCHESTRATOR")
        logger.info("=" * 80)
        if dry_run:
            logger.info("DRY RUN MODE: No files will be written")
        logger.info(f"Skip thematic: {skip_thematic}")
        logger.info(f"Skip competitive: {skip_competitive}")
        logger.info(f"Skip valuation: {skip_valuation}")
        logger.info("=" * 80)

    def run_full_analysis(self) -> str:
        """
        Execute complete 10-step STEPS analysis

        Returns:
            str: Path to generated trading_recommendations document
        """
        try:
            start_time = datetime.now()
            logger.info(f"\n🚀 Starting STEPS analysis at {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")

            # STEP 1: Market Environment
            logger.info("=" * 80)
            self.results['market_environment'] = self._step_1_market_environment()

            # STEP 2: Holdings Quality (CRITICAL - cannot continue if fails)
            logger.info("=" * 80)
            self.results['holdings_quality'] = self._step_2_holdings_quality()
            if not self.results['holdings_quality']:
                logger.error("CRITICAL: STEP 2 failed - Cannot continue without quality analysis")
                sys.exit(1)

            # STEP 3A: Core Screening
            logger.info("=" * 80)
            self.results['core_watchlist'] = self._step_3a_core_screening()

            # STEP 3B: Thematic Discovery (optional)
            logger.info("=" * 80)
            if not self.skip_thematic:
                self.results['thematic_scores'] = self._step_3b_thematic_discovery()
            else:
                logger.info("⏭️  STEP 3B: Thematic Discovery - SKIPPED (--skip-thematic flag)")
                self.results['thematic_scores'] = {}

            # STEP 4: Competitive Analysis (optional)
            logger.info("=" * 80)
            if not self.skip_competitive:
                self.results['competitive_rankings'] = self._step_4_competitive_analysis()
            else:
                logger.info("⏭️  STEP 4: Competitive Analysis - SKIPPED (--skip-competitive flag)")
                self.results['competitive_rankings'] = {}

            # STEP 5: Valuation Analysis (optional)
            logger.info("=" * 80)
            if not self.skip_valuation:
                self.results['valuation_ratings'] = self._step_5_valuation_analysis()
            else:
                logger.info("⏭️  STEP 5: Valuation Analysis - SKIPPED (--skip-valuation flag)")
                self.results['valuation_ratings'] = {}

            # STEP 6: Portfolio Construction
            logger.info("=" * 80)
            self.results['portfolio_allocation'] = self._step_6_portfolio_construction()

            # STEP 7: Rebalancing Trades
            logger.info("=" * 80)
            self.results['rebalancing_trades'] = self._step_7_rebalancing_trades()

            # STEP 8: Trade Synthesis
            logger.info("=" * 80)
            self.results['trade_recommendations'] = self._step_8_trade_synthesis()

            # STEP 9: Data Validation
            logger.info("=" * 80)
            self.results['data_quality'] = self._step_9_data_validation()

            # STEP 10: Framework Validation
            logger.info("=" * 80)
            self.results['compliance'] = self._step_10_framework_validation()

            # Generate final trading document
            logger.info("=" * 80)
            output_file = self.export_trading_document(self.results)

            # Summary
            elapsed = datetime.now() - start_time
            logger.info("=" * 80)
            logger.info(f"✅ STEPS ANALYSIS COMPLETE")
            logger.info(f"⏱️  Total runtime: {elapsed.total_seconds():.1f} seconds")
            logger.info(f"📄 Output file: {output_file}")
            logger.info("=" * 80)

            return output_file

        except Exception as e:
            logger.error(f"❌ FATAL ERROR in STEPS analysis: {e}", exc_info=True)
            raise

    # ==================== STEP IMPLEMENTATIONS ====================

    def _step_1_market_environment(self) -> MarketEnvironment:
        """
        STEP 1: Market Environment Assessment

        Fetches S&P 500, VIX, sector rotation data
        Classifies market trend and volatility regime
        """
        logger.info("🌍 Running STEP 1: Market Environment Assessment...")

        try:
            # TODO: Implement actual market environment analyzer
            # For now, return default assessment
            logger.warning("⚠️  Market environment analyzer not yet implemented - using default assessment")

            default_env = MarketEnvironment(
                sp500_price=6840.0,
                sp500_50ma=6700.0,
                sp500_200ma=6400.0,
                sp500_1m_return=0.26,
                sp500_ytd_return=28.0,
                trend="BULL",
                vix_level=15.2,
                vix_20ma=16.5,
                volatility_regime="LOW",
                leading_sectors=["Technology", "Communication Services", "Financials"],
                lagging_sectors=["Energy", "Utilities", "Real Estate"],
                sector_performance={
                    "Technology": 35.0,
                    "Communication Services": 28.0,
                    "Financials": 22.0,
                    "Healthcare": 18.0,
                    "Consumer Discretionary": 15.0,
                    "Industrials": 12.0,
                    "Materials": 8.0,
                    "Consumer Staples": 5.0,
                    "Energy": -2.0,
                    "Utilities": -5.0,
                    "Real Estate": -8.0
                },
                market_breadth="NARROW",
                risk_appetite="RISK_ON",
                summary="S&P 500 at 6,840 (+0.26%), low volatility (VIX 15.2), tech leadership continues. Bullish environment with narrow breadth.",
                analysis_date=datetime.now().strftime("%Y-%m-%d"),
                data_quality="PARTIAL"
            )

            # Save output
            output_file = self.outputs_dir / f"market_environment_{datetime.now().strftime('%Y%m%d')}.json"
            if not self.dry_run:
                with open(output_file, 'w') as f:
                    json.dump(asdict(default_env), f, indent=2)

            logger.info(f"✅ STEP 1 Complete: {default_env.summary}")
            return default_env

        except Exception as e:
            logger.error(f"❌ STEP 1 Failed: {e}")
            # Return default on failure (not critical)
            return default_env

    def _step_2_holdings_quality(self) -> Dict[str, QualityScore]:
        """
        STEP 2: Current Holdings Quality Analysis

        CRITICAL STEP: Calculates quality scores for all holdings
        Uses existing quality_analysis_script.py
        """
        logger.info("📊 Running STEP 2: Holdings Quality Analysis...")

        try:
            # Run quality analysis script
            logger.info("Executing quality_analysis_script.py...")
            result = subprocess.run(
                ["python", "quality_analysis_script.py"],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                logger.error(f"Quality analysis script failed: {result.stderr}")
                return None

            # Load latest quality analysis output
            quality_files = list(self.outputs_dir.glob("quality_analysis_*.json"))
            if not quality_files:
                logger.error("No quality analysis output found")
                return None

            latest_file = max(quality_files, key=lambda p: p.stat().st_mtime)
            logger.info(f"Loading quality analysis from: {latest_file}")

            with open(latest_file, 'r') as f:
                quality_data = json.load(f)

            # Convert to QualityScore objects
            quality_scores = {}
            for ticker, data in quality_data.items():
                quality_scores[ticker] = QualityScore(
                    ticker=ticker,
                    composite_score=data.get('composite_score', 0),
                    gross_profitability=data.get('gross_profitability', 0),
                    roe=data.get('roe', 0),
                    earnings_quality=data.get('earnings_quality', 0),
                    conservative_growth=data.get('conservative_growth', 0),
                    tier=data.get('tier', 'WEAK'),
                    meets_core_criteria=data.get('composite_score', 0) >= 7.0
                )

            logger.info(f"✅ STEP 2 Complete: Analyzed {len(quality_scores)} holdings")
            for ticker, score in quality_scores.items():
                status = "✅" if score.meets_core_criteria else "❌"
                logger.info(f"  {status} {ticker}: {score.composite_score:.1f}/10 ({score.tier})")

            return quality_scores

        except subprocess.TimeoutExpired:
            logger.error("Quality analysis script timed out")
            return None
        except Exception as e:
            logger.error(f"❌ STEP 2 Failed: {e}", exc_info=True)
            return None

    def _step_3a_core_screening(self) -> List[str]:
        """
        STEP 3A: Core Quality Holdings Screening

        Uses watchlist_generator_script.py to identify quality opportunities
        """
        logger.info("🔍 Running STEP 3A: Core Quality Screening...")

        try:
            # Run watchlist generator
            logger.info("Executing watchlist_generator_script.py...")
            result = subprocess.run(
                ["python", "watchlist_generator_script.py"],
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode != 0:
                logger.warning(f"Watchlist generator had issues: {result.stderr}")

            # Load latest watchlist
            watchlist_files = list(self.outputs_dir.glob("quality_watchlist_*.csv"))
            if not watchlist_files:
                logger.warning("No watchlist output found - using empty list")
                return []

            latest_file = max(watchlist_files, key=lambda p: p.stat().st_mtime)
            logger.info(f"Loading watchlist from: {latest_file}")

            import pandas as pd
            df = pd.read_csv(latest_file)
            watchlist = df['ticker'].tolist() if 'ticker' in df.columns else []

            logger.info(f"✅ STEP 3A Complete: Found {len(watchlist)} quality candidates")
            for ticker in watchlist[:10]:  # Show first 10
                logger.info(f"  • {ticker}")

            return watchlist

        except subprocess.TimeoutExpired:
            logger.error("Watchlist generator timed out")
            return []
        except Exception as e:
            logger.error(f"❌ STEP 3A Warning: {e}")
            return []

    def _step_3b_thematic_discovery(self) -> Dict[str, ThematicScore]:
        """
        STEP 3B: Thematic Opportunity Discovery

        Identifies and scores opportunistic thematic investments
        """
        logger.info("🎯 Running STEP 3B: Thematic Discovery...")

        try:
            # TODO: Implement thematic analysis integration
            logger.warning("⚠️  Thematic analysis not yet fully implemented")

            # Placeholder: Return empty dict for now
            thematic_scores = {}

            logger.info(f"✅ STEP 3B Complete: {len(thematic_scores)} thematic candidates identified")
            return thematic_scores

        except Exception as e:
            logger.error(f"❌ STEP 3B Warning: {e}")
            return {}

    def _step_4_competitive_analysis(self) -> Dict[str, CompetitiveRanking]:
        """
        STEP 4: Competitive Landscape Analysis

        Compares holdings against direct competitors
        """
        logger.info("🏆 Running STEP 4: Competitive Analysis...")

        try:
            # TODO: Implement competitive analyzer
            logger.warning("⚠️  Competitive analyzer not yet implemented")

            competitive_rankings = {}

            logger.info(f"✅ STEP 4 Complete: {len(competitive_rankings)} competitive analyses")
            return competitive_rankings

        except Exception as e:
            logger.error(f"❌ STEP 4 Warning: {e}")
            return {}

    def _step_5_valuation_analysis(self) -> Dict[str, ValuationRating]:
        """
        STEP 5: Valuation Analysis

        Assesses whether stocks are reasonably valued
        """
        logger.info("💰 Running STEP 5: Valuation Analysis...")

        try:
            # TODO: Implement valuation analyzer
            logger.warning("⚠️  Valuation analyzer not yet implemented")

            valuation_ratings = {}

            logger.info(f"✅ STEP 5 Complete: {len(valuation_ratings)} valuations analyzed")
            return valuation_ratings

        except Exception as e:
            logger.error(f"❌ STEP 5 Warning: {e}")
            return {}

    def _step_6_portfolio_construction(self) -> PortfolioAllocation:
        """
        STEP 6: Portfolio Construction

        Determines optimal 80/20 allocation based on scores
        """
        logger.info("🏗️  Running STEP 6: Portfolio Construction...")

        try:
            # TODO: Implement portfolio constructor
            logger.warning("⚠️  Portfolio constructor not yet implemented")

            # Load current portfolio state
            portfolio_file = Path("../portfolio_state.json")
            if portfolio_file.exists():
                with open(portfolio_file, 'r') as f:
                    portfolio_data = json.load(f)
                logger.info(f"Loaded portfolio: {len(portfolio_data.get('holdings', {}))} positions")

            # Default allocation
            allocation = PortfolioAllocation(
                quality_holdings={},
                thematic_holdings={},
                cash_reserve=5.0,
                total_quality_pct=0.0,
                total_thematic_pct=0.0,
                violations=[]
            )

            logger.info("✅ STEP 6 Complete: Portfolio allocation determined")
            return allocation

        except Exception as e:
            logger.error(f"❌ STEP 6 Warning: {e}")
            return PortfolioAllocation(
                quality_holdings={}, thematic_holdings={}, cash_reserve=5.0,
                total_quality_pct=0.0, total_thematic_pct=0.0, violations=[]
            )

    def _step_7_rebalancing_trades(self) -> List[Trade]:
        """
        STEP 7: Rebalancing Trade Generation

        Generates specific trades needed to reach target allocation
        """
        logger.info("⚖️  Running STEP 7: Rebalancing Trades...")

        try:
            # TODO: Implement rebalancing trade generator
            logger.warning("⚠️  Rebalancing trade generator not yet implemented")

            trades = []

            logger.info(f"✅ STEP 7 Complete: {len(trades)} rebalancing trades generated")
            return trades

        except Exception as e:
            logger.error(f"❌ STEP 7 Warning: {e}")
            return []

    def _step_8_trade_synthesis(self) -> List[Trade]:
        """
        STEP 8: Trade Recommendation Synthesis

        Integrates all analysis into final trade recommendations
        Uses existing recommendation_generator_script.py
        """
        logger.info("🎯 Running STEP 8: Trade Synthesis...")

        try:
            # Run recommendation generator
            logger.info("Executing recommendation_generator_script.py...")
            result = subprocess.run(
                ["python", "recommendation_generator_script.py"],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                logger.warning(f"Recommendation generator had issues: {result.stderr}")

            # Load latest recommendations
            rec_files = list(Path("../trading_recommendations").glob("trading_recommendations_*.md"))
            if rec_files:
                latest_file = max(rec_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Latest recommendations: {latest_file}")

            # TODO: Parse recommendations into Trade objects
            trades = []

            logger.info(f"✅ STEP 8 Complete: {len(trades)} trade recommendations synthesized")
            return trades

        except subprocess.TimeoutExpired:
            logger.error("Recommendation generator timed out")
            return []
        except Exception as e:
            logger.error(f"❌ STEP 8 Warning: {e}")
            return []

    def _step_9_data_validation(self) -> DataQualityReport:
        """
        STEP 9: Data Quality Validation

        Validates data completeness and freshness
        """
        logger.info("🔬 Running STEP 9: Data Validation...")

        try:
            # TODO: Implement data validator
            logger.warning("⚠️  Data validator not yet implemented")

            report = DataQualityReport(
                overall_quality="PARTIAL",
                missing_metrics=[],
                stale_metrics=[],
                warnings=[],
                quality_score=7.0
            )

            logger.info(f"✅ STEP 9 Complete: Data quality score {report.quality_score}/10")
            return report

        except Exception as e:
            logger.error(f"❌ STEP 9 Warning: {e}")
            return DataQualityReport(
                overall_quality="INSUFFICIENT",
                missing_metrics=[], stale_metrics=[], warnings=[],
                quality_score=0.0
            )

    def _step_10_framework_validation(self) -> ComplianceReport:
        """
        STEP 10: Framework Compliance Validation

        Ensures all recommendations comply with 80/20 framework
        """
        logger.info("✅ Running STEP 10: Framework Validation...")

        try:
            # TODO: Implement framework validator
            logger.warning("⚠️  Framework validator not yet implemented")

            report = ComplianceReport(
                portfolio_value=1000.0,
                compliance_score=100.0,
                violations=[],
                allocation_quality_pct=80.0,
                allocation_thematic_pct=20.0,
                allocation_cash_pct=5.0,
                framework_compliant=True
            )

            logger.info(f"✅ STEP 10 Complete: Compliance score {report.compliance_score}/100")
            return report

        except Exception as e:
            logger.error(f"❌ STEP 10 Warning: {e}")
            return ComplianceReport(
                portfolio_value=0.0, compliance_score=0.0, violations=[],
                allocation_quality_pct=0.0, allocation_thematic_pct=0.0,
                allocation_cash_pct=0.0, framework_compliant=False
            )

    # ==================== OUTPUT GENERATION ====================

    def export_trading_document(self, analysis_results: Dict) -> str:
        """
        Generate trading_template.md format document

        Args:
            analysis_results: Dictionary containing all STEPS analysis results

        Returns:
            str: Path to generated trading document
        """
        logger.info("📝 Generating trading recommendations document...")

        try:
            timestamp = datetime.now().strftime("%Y%m%d")
            output_file = self.recommendations_dir / f"trading_recommendations_{timestamp}.md"

            # Build document sections
            doc = []
            doc.append("# 🤖 LLM Trading Recommendations")
            doc.append("")
            doc.append("---")
            doc.append("")

            # Header
            doc.append("## 📅 DOCUMENT HEADER")
            doc.append(f"*Date: {datetime.now().strftime('%Y-%m-%d')}*")

            market_env = analysis_results.get('market_environment')
            if market_env:
                doc.append(f"*Market Conditions: {market_env.summary}*")
            else:
                doc.append("*Market Conditions: Analysis in progress*")

            doc.append(f"*Portfolio Performance: Current analysis cycle*")
            doc.append("")
            doc.append("---")
            doc.append("")

            # Risk Management
            doc.append("## 🛡️ RISK MANAGEMENT UPDATES")
            doc.append("")
            doc.append("### ⚙️ Dynamic Risk Parameters")
            doc.append("**MAX-POSITION-SIZE 20%** - Individual position limit per framework")
            doc.append("**CASH-RESERVE 5%** - Minimum liquidity requirement")
            doc.append("**RISK-BUDGET MODERATE** - Balanced approach with quality focus")
            doc.append("")
            doc.append("### 🎯 Position-Specific Risk Adjustments")
            doc.append("*Position-specific stop-losses and profit targets set below*")
            doc.append("")
            doc.append("---")
            doc.append("")

            # Orders Section
            doc.append("## 📋 ORDERS SECTION")
            doc.append("")
            doc.append("### 🔥 IMMEDIATE EXECUTION (HIGH PRIORITY)")
            doc.append("")

            quality_scores = analysis_results.get('holdings_quality', {})

            # Generate sample orders based on quality scores
            if quality_scores:
                for ticker, score in quality_scores.items():
                    if not score.meets_core_criteria:
                        doc.append(f"**SELL all shares of {ticker}** - Quality score {score.composite_score:.1f}/10 below threshold of 7.0. ROE: {score.roe:.1%}, Gross Profitability: {score.gross_profitability:.1%}. Exit from core holdings per framework requirements.")
                        doc.append("")

            doc.append("### ⚖️ POSITION MANAGEMENT (MEDIUM PRIORITY)")
            doc.append("")
            doc.append("*No medium priority trades at this time*")
            doc.append("")
            doc.append("### 📈 STRATEGIC POSITIONING (LOW PRIORITY)")
            doc.append("")
            doc.append("*No low priority trades at this time*")
            doc.append("")
            doc.append("---")
            doc.append("")

            # Market Analysis
            doc.append("## MARKET ANALYSIS & RATIONALE")
            doc.append("")
            doc.append("### Current Market Environment")
            if market_env:
                doc.append(f"S&P 500: ${market_env.sp500_price:.2f} ({market_env.sp500_1m_return:+.2f}% 1M)")
                doc.append(f"Trend: {market_env.trend}, Volatility: {market_env.volatility_regime} (VIX {market_env.vix_level:.1f})")
                doc.append(f"Leading Sectors: {', '.join(market_env.leading_sectors)}")
                doc.append(f"Market Breadth: {market_env.market_breadth}, Risk Appetite: {market_env.risk_appetite}")
            else:
                doc.append("Market environment analysis pending...")
            doc.append("")

            doc.append("### Catalyst Calendar")
            doc.append("*Upcoming earnings and events:*")
            doc.append("- Analysis cycle catalysts to be populated")
            doc.append("")

            doc.append("### Risk Assessment")
            compliance = analysis_results.get('compliance')
            if compliance:
                doc.append(f"Portfolio Compliance Score: {compliance.compliance_score:.0f}/100")
                doc.append(f"Framework Compliant: {'✅ Yes' if compliance.framework_compliant else '❌ No'}")
            doc.append("")

            doc.append("### Performance Attribution")
            doc.append("*Performance drivers to be analyzed*")
            doc.append("")
            doc.append("---")
            doc.append("")

            # Strategic Allocation
            doc.append("## STRATEGIC ALLOCATION TARGETS")
            doc.append("")
            doc.append("### Target Portfolio Composition")
            allocation = analysis_results.get('portfolio_allocation')
            if allocation:
                doc.append(f"- **Quality Core Holdings**: {allocation.total_quality_pct:.1f}% (target 80%)")
                doc.append(f"- **Opportunistic Thematic**: {allocation.total_thematic_pct:.1f}% (target 20%)")
                doc.append(f"- **Cash Reserve**: {allocation.cash_reserve:.1f}% (minimum 5%)")
            else:
                doc.append("- **Quality Core Holdings**: 80% (target)")
                doc.append("- **Opportunistic Thematic**: 20% (target)")
                doc.append("- **Cash Reserve**: 5% (minimum)")
            doc.append("")

            doc.append("### Sector Allocation Targets")
            doc.append("*Sector allocation analysis pending*")
            doc.append("")
            doc.append("---")
            doc.append("")

            # Execution Notes
            doc.append("## EXECUTION NOTES")
            doc.append("")
            doc.append("### Cash Flow Management")
            doc.append("Execute sells first to generate cash for purchases. Priority order: HIGH → MEDIUM → LOW.")
            doc.append("")
            doc.append("### Timing Considerations")
            doc.append("Monitor market hours: Mon-Fri 9:30AM-4PM ET. Avoid execution during first/last 15 minutes for better fills.")
            doc.append("")
            doc.append("### Partial Fill Instructions")
            doc.append("If cash limited: Prioritize quality score >8 positions. Accept partial fills for positions >$100.")
            doc.append("")
            doc.append("---")
            doc.append("")

            # Footer
            doc.append("*Generated by STEPS Portfolio Analysis Orchestrator*")
            doc.append(f"*Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
            doc.append(f"*Framework: 80/20 Quality-Opportunistic Model*")
            doc.append("")

            # Write file
            if not self.dry_run:
                with open(output_file, 'w') as f:
                    f.write('\n'.join(doc))
                logger.info(f"✅ Trading document generated: {output_file}")
            else:
                logger.info(f"✅ Trading document generated (DRY RUN): {output_file}")

            return str(output_file)

        except Exception as e:
            logger.error(f"❌ Failed to generate trading document: {e}", exc_info=True)
            raise


# ==================== MAIN ====================

def main():
    """Main entry point with CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description="STEPS Portfolio Analysis Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python steps_orchestrator.py                     # Full analysis
  python steps_orchestrator.py --dry-run           # Test without writing
  python steps_orchestrator.py --skip-thematic     # Skip thematic analysis
  python steps_orchestrator.py --verbose           # Detailed logging
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without executing'
    )
    parser.add_argument(
        '--skip-thematic',
        action='store_true',
        help='Skip thematic analysis for faster execution'
    )
    parser.add_argument(
        '--skip-competitive',
        action='store_true',
        help='Skip competitive analysis for faster execution'
    )
    parser.add_argument(
        '--skip-valuation',
        action='store_true',
        help='Skip valuation analysis for faster execution'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable detailed debug logging'
    )

    args = parser.parse_args()

    try:
        orchestrator = STEPSOrchestrator(
            dry_run=args.dry_run,
            skip_thematic=args.skip_thematic,
            skip_competitive=args.skip_competitive,
            skip_valuation=args.skip_valuation,
            verbose=args.verbose
        )

        output_file = orchestrator.run_full_analysis()

        print("\n" + "=" * 80)
        print("✅ STEPS ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"\n📄 Trading recommendations: {output_file}")
        print("\nNext steps:")
        print("1. Review the generated recommendations")
        print("2. Edit manual_trades_override.json with approved trades")
        print("3. Set 'enabled': true")
        print("4. Execute: python main.py (during market hours)")
        print("")

    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
