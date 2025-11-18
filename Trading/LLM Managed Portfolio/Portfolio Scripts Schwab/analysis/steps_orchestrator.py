#!/usr/bin/env python3
"""
STEPS Portfolio Analysis Orchestrator
Implements complete 10-step STEPS research methodology for portfolio management

References:
- STEPS_Research_Methodology_November_1_2025.md for methodology
- quality_investing_thresholds_research.md for 4-tier market cap framework
- trading_template.md for output format

Author: LLM Portfolio Management System
Date: November 6, 2025 (Updated for 4-Tier Framework)
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

# Add parent directory to path (Portfolio Scripts Schwab/)
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.watchlist_config import WatchlistConfig, WatchlistIndex
from config.hf_config import HFConfig

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
class TieredAllocation:
    """Target portfolio allocation for 4-tier market cap framework"""
    large_cap_holdings: Dict[str, float]  # ticker -> target %
    mid_cap_holdings: Dict[str, float]  # ticker -> target %
    small_cap_holdings: Dict[str, float]  # ticker -> target %
    thematic_holdings: Dict[str, float]  # ticker -> target %
    cash_reserve: float
    total_large_cap_pct: float
    total_mid_cap_pct: float
    total_small_cap_pct: float
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
        verbose: bool = False,
        watchlist_config: Optional[WatchlistConfig] = None
    ):
        """
        Initialize orchestrator with configuration flags

        Args:
            dry_run: Test mode without writing files
            skip_thematic: Skip thematic analysis (STEP 3B)
            skip_competitive: Skip competitive analysis (STEP 4)
            skip_valuation: Skip valuation analysis (STEP 5)
            verbose: Enable detailed debug logging
            watchlist_config: Watchlist configuration (defaults to HFConfig.WATCHLIST_CONFIG)
        """
        self.dry_run = dry_run
        self.skip_thematic = skip_thematic
        self.skip_competitive = skip_competitive
        self.skip_valuation = skip_valuation
        self.verbose = verbose
        self.watchlist_config = watchlist_config or HFConfig.WATCHLIST_CONFIG

        # Set logging level
        if verbose:
            logger.setLevel(logging.DEBUG)

        # Create outputs directory (relative to orchestrator file location)
        self.outputs_dir = Path(__file__).parent / "outputs"
        self.outputs_dir.mkdir(exist_ok=True)

        self.recommendations_dir = Path(__file__).parent.parent / "trading_recommendations"
        self.recommendations_dir.mkdir(exist_ok=True)

        # Analysis results storage
        self.results = {}

        # Load portfolio state
        self.portfolio_state = self._load_portfolio_state()

        logger.info("=" * 80)
        logger.info("STEPS PORTFOLIO ANALYSIS ORCHESTRATOR")
        logger.info("=" * 80)
        if dry_run:
            logger.info("DRY RUN MODE: No files will be written")
        logger.info(f"Watchlist configuration: {self.watchlist_config}")
        logger.info(f"Skip thematic: {skip_thematic}")
        logger.info(f"Skip competitive: {skip_competitive}")
        logger.info(f"Skip valuation: {skip_valuation}")
        logger.info("=" * 80)

    def _load_portfolio_state(self) -> Dict:
        """Load portfolio state from portfolio_state.json"""
        portfolio_file = Path("../portfolio_state.json")
        if portfolio_file.exists():
            try:
                with open(portfolio_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load portfolio_state.json: {e}")
                return {'holdings': {}, 'cash': 0}
        else:
            logger.warning("portfolio_state.json not found, using empty portfolio")
            return {'holdings': {}, 'cash': 0}

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
        Uses market_environment_analyzer.py
        """
        logger.info("🌍 Running STEP 1: Market Environment Assessment...")

        try:
            # Import and run market environment analyzer
            from analyzers.market_environment_analyzer import MarketEnvironmentAnalyzer

            analyzer = MarketEnvironmentAnalyzer(enable_cache=True)
            env = analyzer.analyze_market_environment()

            # Save output files
            if not self.dry_run:
                # JSON output
                json_file = self.outputs_dir / f"market_environment_{datetime.now().strftime('%Y%m%d')}.json"
                analyzer.export_to_json(env, str(json_file))

                # Markdown report
                md_file = self.outputs_dir / f"market_environment_{datetime.now().strftime('%Y%m%d')}.md"
                analyzer.export_to_markdown(env, str(md_file))

            logger.info(f"✅ STEP 1 Complete: {env.summary}")
            return env

        except Exception as e:
            logger.error(f"❌ STEP 1 Failed: {e}")
            # Return default on failure (not critical)
            logger.warning("⚠️  Using default market assessment due to error")

            default_env = MarketEnvironment(
                sp500_price=6840.0,
                sp500_50ma=6700.0,
                sp500_200ma=6400.0,
                sp500_1m_return=0.26,
                sp500_ytd_return=28.0,
                trend="NEUTRAL",
                vix_level=20.0,
                vix_20ma=20.0,
                volatility_regime="MODERATE",
                leading_sectors=["Technology"],
                lagging_sectors=["Energy"],
                sector_performance={},
                market_breadth="MODERATE",
                risk_appetite="NEUTRAL",
                summary="Market data unavailable - using neutral assessment.",
                analysis_date=datetime.now().strftime("%Y-%m-%d"),
                data_quality="INSUFFICIENT"
            )

            return default_env

    def _step_2_holdings_quality(self) -> Dict[str, QualityScore]:
        """
        STEP 2: Current Holdings Quality Analysis + Market Cap Classification

        CRITICAL STEP: Calculates quality scores and classifies by market cap tier
        Uses existing quality_analysis_script.py + market_cap_classifier.py
        """
        logger.info("📊 Running STEP 2: Holdings Quality Analysis & Market Cap Classification...")

        try:
            # Run quality analysis script with watchlist configuration
            logger.info(f"Executing quality_analysis_script.py with {self.watchlist_config}...")

            # Build command with watchlist configuration
            # Use relative script name since we set cwd to analysis/ directory
            cmd = ["python", "quality_analysis_script.py"]
            cmd.extend(["--index", self.watchlist_config.index.value])
            if self.watchlist_config.limit:
                cmd.extend(["--limit", str(self.watchlist_config.limit)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=Path(__file__).parent  # Run from analysis/ directory
            )

            # Always log subprocess output for debugging
            logger.info(f"Quality analysis subprocess returncode: {result.returncode}")
            if result.stdout:
                logger.debug(f"Quality analysis stdout: {result.stdout[:500]}")
            if result.stderr:
                logger.warning(f"Quality analysis stderr: {result.stderr[:500]}")

            if result.returncode != 0:
                logger.warning(f"Quality analysis subprocess failed with returncode {result.returncode}")
                logger.warning(f"Attempting to use existing quality analysis output...")

            # Load quality analysis output (fixed filename)
            quality_file = self.outputs_dir / "quality_analysis.json"
            if not quality_file.exists():
                logger.error(f"No quality analysis output found at {quality_file}")
                logger.error(f"Quality analysis subprocess failed and no cached output available.")
                return None

            # Check file age for warning
            import time
            file_age_hours = (time.time() - quality_file.stat().st_mtime) / 3600
            if file_age_hours > 24:
                logger.warning(f"Using quality analysis output from {file_age_hours:.1f} hours ago")

            logger.info(f"Loading quality analysis from: {quality_file}")

            with open(quality_file, 'r') as f:
                quality_data = json.load(f)

            # Convert to QualityScore objects (use holdings_quality key from JSON)
            quality_scores = {}
            holdings_quality = quality_data.get('holdings_quality', {})
            for ticker, data in holdings_quality.items():
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

            # NEW: Market cap classification for 4-tier framework
            logger.info("Classifying holdings by market cap tier...")
            from quality.market_cap_classifier import MarketCapClassifier

            classifier = MarketCapClassifier()
            tickers = list(quality_scores.keys())
            market_cap_results = classifier.batch_classify_tickers(tickers)

            # Store market cap tier results for later use
            self.results['market_cap_tiers'] = {}
            for ticker in tickers:
                tier_data = market_cap_results.classifications.get(ticker)
                if tier_data:
                    self.results['market_cap_tiers'][ticker] = tier_data.tier.value
                    logger.info(f"  📈 {ticker}: {tier_data.tier.value} (${tier_data.market_cap/1e9:.1f}B)")

            logger.info(f"✅ STEP 2 Complete: Analyzed {len(quality_scores)} holdings")
            for ticker, score in quality_scores.items():
                status = "✅" if score.meets_core_criteria else "❌"
                tier = self.results['market_cap_tiers'].get(ticker, 'UNKNOWN')
                logger.info(f"  {status} {ticker}: {score.composite_score:.1f}/10 ({score.tier}) - {tier}")

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
            # Run watchlist generator with watchlist configuration
            logger.info(f"Executing watchlist_generator_script.py with {self.watchlist_config}...")

            # Build command with watchlist configuration
            # Use relative script name since we set cwd to analysis/ directory
            cmd = ["python", "watchlist_generator_script.py"]
            cmd.extend(["--index", self.watchlist_config.index.value])
            if self.watchlist_config.limit:
                cmd.extend(["--limit", str(self.watchlist_config.limit)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=Path(__file__).parent  # Run from analysis/ directory
            )

            if result.returncode != 0:
                logger.warning(f"Watchlist generator had issues: {result.stderr}")

            # Load watchlist output (fixed filename)
            watchlist_file = self.outputs_dir / "quality_watchlist.csv"
            if not watchlist_file.exists():
                logger.warning(f"No watchlist output found at {watchlist_file} - using empty list")
                return []

            logger.info(f"Loading watchlist from: {watchlist_file}")

            import pandas as pd
            df = pd.read_csv(watchlist_file)
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

        Identifies and scores opportunistic thematic investments (20% allocation)
        Uses thematic_analysis_script.py to score holdings on theme fit
        """
        logger.info("🎯 Running STEP 3B: Thematic Discovery...")

        try:
            from analysis.thematic_analysis_script import ThematicAnalysisScript

            # Initialize thematic analyzer
            thematic_script = ThematicAnalysisScript(model_type='7B')

            # Identify opportunistic candidates
            # Option 1: All current holdings (check if any are thematic)
            # Option 2: Specific tickers flagged as opportunistic
            # For now, analyze all holdings and filter by thematic score threshold

            holdings = list(self.portfolio_state.get('holdings', {}).keys())
            logger.info(f"Analyzing {len(holdings)} holdings for thematic fit...")

            # Run thematic analysis (heuristic mode - fast)
            results = thematic_script.analyze_opportunistic_holdings(
                tickers=holdings,
                use_llm=False  # Use heuristic for speed
            )

            # Filter by minimum threshold (28/50)
            qualified_thematic = {
                ticker: data
                for ticker, data in results.items()
                if data['score'] >= 28
            }

            # Convert to ThematicScore objects
            thematic_scores = {}
            for ticker, data in qualified_thematic.items():
                thematic_scores[ticker] = ThematicScore(
                    dimension_scores=data['dimensions'],
                    dimension_rationales={k: f"Score: {v}/10" for k, v in data['dimensions'].items()},
                    overall_score=data['score'],
                    classification=data['classification'],
                    key_strength=f"{data['theme']} exposure",
                    key_risk="Thematic volatility",
                    investment_stance=data['investment_stance'],
                    confidence=data['confidence']
                )

            # Export results
            if results:
                thematic_script.export_results(results)

            logger.info(f"✅ STEP 3B Complete: {len(qualified_thematic)}/{len(results)} meet thematic threshold (≥28)")
            return thematic_scores

        except ImportError as e:
            logger.error(f"❌ STEP 3B Failed: Missing thematic_analysis_script.py - {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ STEP 3B Warning: {e}")
            return {}

    def _step_4_competitive_analysis(self) -> Dict[str, CompetitiveRanking]:
        """
        STEP 4: Competitive Landscape Analysis

        Compares holdings against direct competitors
        Identifies KEEP/SWAP/EXIT opportunities based on competitive position
        """
        logger.info("🏆 Running STEP 4: Competitive Analysis...")

        try:
            from analyzers.competitive_analyzer import CompetitiveAnalyzer

            # Initialize analyzer
            analyzer = CompetitiveAnalyzer()

            # Get holdings to analyze
            holdings = list(self.portfolio_state.get('holdings', {}).keys())
            logger.info(f"Analyzing competitive position for {len(holdings)} holdings...")

            # Run competitive analysis
            results = analyzer.batch_analyze_portfolio(holdings)

            # Export results
            if results:
                analyzer.export_to_json(results)
                analyzer.generate_markdown_report(results)

            # Convert to CompetitiveRanking format (if needed for typing)
            # For now, just use the results dict
            competitive_rankings = results

            logger.info(f"✅ STEP 4 Complete: {len(competitive_rankings)} competitive analyses")

            # Log summary
            keep_count = sum(1 for r in results.values() if r.recommendation == "KEEP")
            swap_count = sum(1 for r in results.values() if r.recommendation == "SWAP")
            exit_count = sum(1 for r in results.values() if r.recommendation == "EXIT")
            logger.info(f"  KEEP: {keep_count}, SWAP: {swap_count}, EXIT: {exit_count}")

            return competitive_rankings

        except ImportError as e:
            logger.error(f"❌ STEP 4 Failed: Missing competitive_analyzer.py - {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ STEP 4 Warning: {e}")
            return {}

    def _step_5_valuation_analysis(self) -> Dict[str, ValuationRating]:
        """
        STEP 5: Valuation Analysis

        Assesses whether stocks are reasonably valued using quality-adjusted P/E thresholds
        Prevents overpaying even for high-quality companies
        """
        logger.info("💰 Running STEP 5: Valuation Analysis...")

        try:
            from analyzers.valuation_analyzer import ValuationAnalyzer

            # Initialize analyzer
            analyzer = ValuationAnalyzer()

            # Get holdings to analyze
            holdings = list(self.portfolio_state.get('holdings', {}).keys())
            logger.info(f"Analyzing valuation for {len(holdings)} holdings...")

            # Get quality scores from quality analysis (from previous step)
            # For now, use default scores - in production would load from quality_scores dict
            quality_scores = {}
            if hasattr(self, 'quality_scores') and self.quality_scores:
                quality_scores = self.quality_scores
            else:
                # Default to 75 if quality scores not available
                quality_scores = {ticker: 75.0 for ticker in holdings}
                logger.warning("Quality scores not available, using default 75.0")

            # Run valuation analysis
            results = analyzer.batch_analyze_portfolio(holdings, quality_scores)

            # Export results
            if results:
                analyzer.export_to_json(results)
                analyzer.generate_markdown_report(results)

            valuation_ratings = results

            logger.info(f"✅ STEP 5 Complete: {len(valuation_ratings)} valuations analyzed")

            # Log summary
            buy_count = sum(1 for r in results.values() if r.recommendation == "BUY")
            hold_count = sum(1 for r in results.values() if r.recommendation == "HOLD")
            avoid_count = sum(1 for r in results.values() if r.recommendation == "AVOID")
            logger.info(f"  BUY: {buy_count}, HOLD: {hold_count}, AVOID: {avoid_count}")

            return valuation_ratings

        except ImportError as e:
            logger.error(f"❌ STEP 5 Failed: Missing valuation_analyzer.py - {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ STEP 5 Warning: {e}")
            return {}

    def _step_6_portfolio_construction(self) -> TieredAllocation:
        """
        STEP 6: Portfolio Construction

        Determines optimal 4-tier allocation (Large/Mid/Small/Thematic)
        Uses portfolio_constructor.py with 4-tier framework
        """
        logger.info("🏗️  Running STEP 6: Portfolio Construction (4-Tier Framework)...")

        try:
            from core.portfolio_constructor import PortfolioConstructor
            from quality.market_cap_classifier import MarketCapTier

            # Get quality scores and market cap tiers from STEP 2
            quality_results = self.results.get('holdings_quality', {})
            market_cap_tiers = self.results.get('market_cap_tiers', {})

            if not quality_results or not market_cap_tiers:
                logger.error("Missing quality scores or market cap tiers from STEP 2")
                return self._default_tiered_allocation()

            # Organize holdings by market cap tier
            holdings_by_tier = {
                MarketCapTier.LARGE_CAP: {},
                MarketCapTier.MID_CAP: {},
                MarketCapTier.SMALL_CAP: {},
                'THEMATIC': {}
            }

            for ticker, tier_str in market_cap_tiers.items():
                quality_data = quality_results.get(ticker)
                if not quality_data:
                    continue

                roe = quality_data.roe if hasattr(quality_data, 'roe') else 0.15

                if tier_str == 'Large Cap':
                    holdings_by_tier[MarketCapTier.LARGE_CAP][ticker] = roe
                elif tier_str == 'Mid Cap':
                    # For mid cap, need ROE and incremental ROCE advantage
                    holdings_by_tier[MarketCapTier.MID_CAP][ticker] = {
                        'roe': roe,
                        'incremental_roce_advantage': 5.0  # Placeholder
                    }
                elif tier_str == 'Small Cap':
                    # For small cap, need quality score
                    quality_score = quality_data.composite_score * 10 if hasattr(quality_data, 'composite_score') else 70
                    holdings_by_tier[MarketCapTier.SMALL_CAP][ticker] = {
                        'quality_score': quality_score
                    }

            # Get thematic holdings from STEP 3B (if available)
            thematic_results = self.results.get('thematic_scores', {})
            for ticker, thematic_data in thematic_results.items():
                if isinstance(thematic_data, dict):
                    thematic_score = thematic_data.get('total_score', 0)
                else:
                    thematic_score = thematic_data

                if thematic_score >= 28:
                    holdings_by_tier['THEMATIC'][ticker] = thematic_score

            # Prepare financial data for small cap filters
            financial_data = {}  # TODO: Load actual financial data if needed

            # Load portfolio value
            portfolio_file = Path(__file__).parent.parent / "portfolio_state.json"
            portfolio_value = 100000.0  # Default
            if portfolio_file.exists():
                with open(portfolio_file, 'r') as f:
                    portfolio_data = json.load(f)
                    portfolio_holdings = portfolio_data.get('holdings', {})
                    cash = portfolio_data.get('cash', 0)
                    # Calculate portfolio value from share counts (holdings are integers representing shares)
                    # We'll use total_value from portfolio state if available
                    portfolio_value = portfolio_data.get('total_value', 100000.0)
                    logger.info(f"Loaded portfolio: ${portfolio_value:,.2f}")

            # Calculate target allocation
            constructor = PortfolioConstructor()
            allocation = constructor.calculate_target_allocation(
                holdings_by_tier, financial_data, portfolio_value
            )

            logger.info(f"✅ STEP 6 Complete: 4-Tier allocation calculated")
            logger.info(f"  Large Cap: {allocation.total_large_cap_pct:.1f}%")
            logger.info(f"  Mid Cap: {allocation.total_mid_cap_pct:.1f}%")
            logger.info(f"  Small Cap: {allocation.total_small_cap_pct:.1f}%")
            logger.info(f"  Thematic: {allocation.total_thematic_pct:.1f}%")
            logger.info(f"  Cash: {allocation.cash_reserve:.1f}%")

            if allocation.violations:
                logger.warning(f"  ⚠️  {len(allocation.violations)} allocation violations")

            return allocation

        except Exception as e:
            logger.error(f"❌ STEP 6 Failed: {e}", exc_info=True)
            return self._default_tiered_allocation()

    def _default_tiered_allocation(self) -> TieredAllocation:
        """Return default empty allocation for error cases"""
        return TieredAllocation(
            large_cap_holdings={}, mid_cap_holdings={}, small_cap_holdings={},
            thematic_holdings={}, cash_reserve=5.0,
            total_large_cap_pct=0.0, total_mid_cap_pct=0.0,
            total_small_cap_pct=0.0, total_thematic_pct=0.0, violations=[]
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
            # Use relative script name since we set cwd to analysis/ directory
            result = subprocess.run(
                ["python", "recommendation_generator_script.py"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=Path(__file__).parent  # Run from analysis/ directory
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

        Validates data completeness and freshness for all holdings
        """
        logger.info("🔬 Running STEP 9: Data Validation...")

        try:
            from validators.data_validator import DataValidator

            validator = DataValidator()
            holdings = list(self.portfolio_state.get('holdings', {}).keys())

            if not holdings:
                logger.warning("No holdings to validate")
                return DataQualityReport(
                    overall_quality="INSUFFICIENT",
                    missing_metrics=[],
                    stale_metrics=[],
                    warnings=["No holdings in portfolio"],
                    quality_score=0.0
                )

            # Batch validate all holdings
            detailed_reports = validator.batch_validate_portfolio(holdings)

            # Aggregate results for orchestrator summary
            all_missing = []
            all_stale = []
            all_warnings = []
            total_score = 0.0

            for ticker, detail_report in detailed_reports.items():
                all_missing.extend([f"{ticker}:{m}" for m in detail_report.missing_metrics])
                all_stale.extend([f"{ticker}:{s}" for s in detail_report.stale_metrics])
                all_warnings.extend([f"{ticker}: {w}" for w in detail_report.warnings])
                total_score += detail_report.quality_score

            # Calculate average quality score
            avg_score = total_score / len(detailed_reports)

            # Determine overall quality
            if avg_score >= 8.0:
                overall = "COMPLETE"
            elif avg_score >= 5.0:
                overall = "PARTIAL"
            else:
                overall = "INSUFFICIENT"

            # Export detailed reports
            output_date = datetime.now().strftime('%Y%m%d')
            validator.export_to_json(
                detailed_reports,
                f"outputs/data_validation_{output_date}.json"
            )
            validator.export_summary(
                detailed_reports,
                f"outputs/data_validation_{output_date}_summary.md"
            )

            report = DataQualityReport(
                overall_quality=overall,
                missing_metrics=all_missing,
                stale_metrics=all_stale,
                warnings=all_warnings,
                quality_score=avg_score
            )

            logger.info(f"✅ STEP 9 Complete: Portfolio data quality {overall} (score: {avg_score:.1f}/10)")
            logger.info(f"   - Holdings validated: {len(holdings)}")
            logger.info(f"   - Total missing metrics: {len(all_missing)}")
            logger.info(f"   - Total warnings: {len(all_warnings)}")

            return report

        except Exception as e:
            logger.error(f"❌ STEP 9 Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return DataQualityReport(
                overall_quality="INSUFFICIENT",
                missing_metrics=[],
                stale_metrics=[],
                warnings=[f"Error during validation: {str(e)}"],
                quality_score=0.0
            )

    def _step_10_framework_validation(self) -> 'TieredComplianceReport':
        """
        STEP 10: Framework Compliance Validation

        Validates portfolio compliance with 4-tier market cap framework rules
        """
        logger.info("✅ Running STEP 10: 4-Tier Framework Validation...")

        try:
            from validators.framework_validator import FrameworkValidator

            validator = FrameworkValidator()

            # Get market cap tiers from STEP 2
            market_cap_tiers = self.results.get('market_cap_tiers', {})

            # Get thematic scores from STEP 3B results
            thematic_results = self.results.get('thematic_scores', {})

            # Classify holdings by market cap tier
            holdings_tiers = {}
            for ticker in self.portfolio_state.get('holdings', {}).keys():
                # Check if thematic first
                thematic_score = 0
                if ticker in thematic_results:
                    thematic_data = thematic_results[ticker]
                    if isinstance(thematic_data, dict):
                        thematic_score = thematic_data.get('total_score', 0)
                    else:
                        thematic_score = thematic_data

                if thematic_score >= 28:
                    # This is a thematic holding
                    holdings_tiers[ticker] = 'THEMATIC'
                else:
                    # Use market cap tier
                    tier_str = market_cap_tiers.get(ticker, 'Large Cap')  # Default to large cap
                    if tier_str == 'Large Cap':
                        holdings_tiers[ticker] = 'LARGE_CAP'
                    elif tier_str == 'Mid Cap':
                        holdings_tiers[ticker] = 'MID_CAP'
                    elif tier_str == 'Small Cap':
                        holdings_tiers[ticker] = 'SMALL_CAP'
                    else:
                        # Micro cap or unknown - default to small cap
                        holdings_tiers[ticker] = 'SMALL_CAP'

            # Prepare ROE persistence data (optional - would come from quality_persistence_analyzer)
            # For now, use placeholder data
            roe_persistence = None  # TODO: Integrate with quality_persistence_analyzer

            # Prepare small cap filters (optional - would come from portfolio_constructor)
            # For now, use placeholder data
            small_cap_filters = None  # TODO: Integrate with financial data

            # Run 4-tier validation
            report = validator.validate_portfolio(
                self.portfolio_state,
                holdings_tiers,
                roe_persistence,
                small_cap_filters
            )

            # Export compliance report
            output_date = datetime.now().strftime('%Y%m%d')
            validator.export_to_json(
                report,
                f"outputs/compliance_{output_date}.json"
            )

            # Generate markdown report
            markdown = validator.generate_compliance_report_markdown(report)
            with open(f"outputs/compliance_{output_date}.md", 'w') as f:
                f.write(markdown)

            # Log summary
            if report.framework_compliant:
                logger.info(f"✅ STEP 10 Complete: 4-Tier Framework COMPLIANT (score: {report.compliance_score:.0f}/100)")
            else:
                logger.warning(f"⚠️  STEP 10 Complete: 4-Tier Framework NON-COMPLIANT (score: {report.compliance_score:.0f}/100)")

            logger.info(f"  Large Cap: {report.allocation_large_cap_pct:.1f}%")
            logger.info(f"  Mid Cap: {report.allocation_mid_cap_pct:.1f}%")
            logger.info(f"  Small Cap: {report.allocation_small_cap_pct:.1f}%")
            logger.info(f"  Thematic: {report.allocation_thematic_pct:.1f}%")
            logger.info(f"  Cash: {report.allocation_cash_pct:.1f}%")

            critical_count = len([v for v in report.violations if v.severity == "CRITICAL"])
            warning_count = len([v for v in report.violations if v.severity == "WARNING"])
            info_count = len([v for v in report.violations if v.severity == "INFO"])

            logger.info(f"   - CRITICAL violations: {critical_count}")
            logger.info(f"   - WARNING violations: {warning_count}")
            logger.info(f"   - INFO violations: {info_count}")

            if critical_count > 0:
                logger.warning(f"   ⚠️  {critical_count} critical violations must be resolved!")

            return report

        except Exception as e:
            logger.error(f"❌ STEP 10 Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ComplianceReport(
                portfolio_value=0.0,
                compliance_score=0.0,
                violations=[],
                allocation_quality_pct=0.0,
                allocation_thematic_pct=0.0,
                allocation_cash_pct=0.0,
                framework_compliant=False
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
                # Quality = Large + Mid + Small cap
                total_quality_pct = (allocation.total_large_cap_pct +
                                    allocation.total_mid_cap_pct +
                                    allocation.total_small_cap_pct)
                doc.append(f"- **Large Cap Holdings**: {allocation.total_large_cap_pct:.1f}% (target 65-70%)")
                doc.append(f"- **Mid Cap Holdings**: {allocation.total_mid_cap_pct:.1f}% (target 15-20%)")
                doc.append(f"- **Small Cap Holdings**: {allocation.total_small_cap_pct:.1f}% (target 10-15%)")
                doc.append(f"- **Total Quality Core**: {total_quality_pct:.1f}% (target 80%)")
                doc.append(f"- **Opportunistic Thematic**: {allocation.total_thematic_pct:.1f}% (target 5-10%)")
                doc.append(f"- **Cash Reserve**: {allocation.cash_reserve:.1f}% (minimum 5%)")
            else:
                doc.append("- **Large Cap Holdings**: 67.5% (target 65-70%)")
                doc.append("- **Mid Cap Holdings**: 17.5% (target 15-20%)")
                doc.append("- **Small Cap Holdings**: 12.5% (target 10-15%)")
                doc.append("- **Total Quality Core**: 97.5% (target 80%)")
                doc.append("- **Opportunistic Thematic**: 7.5% (target 5-10%)")
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
  python steps_orchestrator.py                            # Full analysis (S&P 500)
  python steps_orchestrator.py --dry-run                  # Test without writing
  python steps_orchestrator.py --skip-thematic            # Skip thematic analysis
  python steps_orchestrator.py --verbose                  # Detailed logging
  python steps_orchestrator.py --watchlist-index sp400    # Screen S&P MidCap 400
  python steps_orchestrator.py --watchlist-index combined_sp  # Screen S&P 1500 (large+mid+small)
  python steps_orchestrator.py --watchlist-limit 100      # Limit to 100 tickers (faster)
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
    parser.add_argument(
        '--watchlist-index',
        type=str,
        default='combined_sp',
        choices=['sp500', 'sp400', 'sp600', 'nasdaq100', 'combined_sp'],
        help='Watchlist index to screen (default: combined_sp). Options: sp500 (large cap ~500), '
             'sp400 (mid cap ~400), sp600 (small cap ~600), nasdaq100 (tech ~100), '
             'combined_sp (S&P 1500 ~1500)'
    )
    parser.add_argument(
        '--watchlist-limit',
        type=int,
        default=None,
        help='Limit number of watchlist tickers (default: None for no limit)'
    )

    args = parser.parse_args()

    # Map CLI argument to WatchlistIndex enum
    index_map = {
        'sp500': WatchlistIndex.SP500,
        'sp400': WatchlistIndex.SP400,
        'sp600': WatchlistIndex.SP600,
        'nasdaq100': WatchlistIndex.NASDAQ100,
        'combined_sp': WatchlistIndex.COMBINED_SP
    }

    # Create watchlist config
    watchlist_config = WatchlistConfig(
        index=index_map[args.watchlist_index],
        limit=args.watchlist_limit
    )

    try:
        orchestrator = STEPSOrchestrator(
            dry_run=args.dry_run,
            skip_thematic=args.skip_thematic,
            skip_competitive=args.skip_competitive,
            skip_valuation=args.skip_valuation,
            verbose=args.verbose,
            watchlist_config=watchlist_config
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
