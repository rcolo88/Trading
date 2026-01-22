#!/usr/bin/env python3
"""
Quality Analysis Script
Standalone script to analyze quality metrics for portfolio holdings vs watchlist alternatives

Features:
- Sequential and parallel fetching modes
- Progress bars for long-running operations
- Timeout support for large indices
- SimFin as primary source for US companies
- yfinance with currency conversion for foreign companies

Outputs:
- outputs/quality_analysis_YYYYMMDD.json: Complete quality analysis results
- outputs/quality_analysis_YYYYMMDD_summary.txt: Human-readable summary with recommendations

Usage:
    # Sequential (default)
    python main_quality_analysis.py --index sp500 --limit 50

    # Parallel with progress bar
    python main_quality_analysis.py --index russell2000 --limit 0 --parallel --workers 10
"""

import json
import logging
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path

try:
    import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Add parent directory to path for imports (Portfolio Scripts Schwab/)
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.financial_data_fetcher import FinancialDataFetcher, FinancialData
from data.enhanced_hybrid_fetcher import EnhancedHybridDataFetcher
from quality.quality_metrics_calculator import QualityMetricsCalculator, QualityAnalysisResult
from quality.lookback_calculator import LookbackCalculator, DEFAULT_LOOKBACKS, QUALITY_DIMENSIONS, SECTOR_ADJUSTMENTS, MarketCapTier
from quality.market_cap_classifier import MarketCapClassifier
from components.quality_persistence_analyzer import QualityPersistenceAnalyzer
from data.watchlist_config import WatchlistConfig, WatchlistIndex

# Quality thresholds (formerly from HFConfig)
QUALITY_MIN_SCORE = 70      # Minimum quality score for holdings
QUALITY_IDEAL_SCORE = 85    # Ideal quality score for new buys
QUALITY_SWAP_THRESHOLD = 15 # Minimum score improvement to swap holdings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineProgressTracker:
    """
    Unified progress tracker for quality analysis pipeline.

    Features:
    - Single tqdm progress bar for entire pipeline
    - ETA calculation based on historical stage timings
    - Stage tracking with per-stage summaries
    - Thread-safe updates for parallel operations

    Usage:
        tracker = PipelineProgressTracker(total_tickers=500)
        tracker.start_stage("fetch")
        # ... perform fetch ...
        tracker.update_stage(250)  # 50% complete
        tracker.end_stage(success=248, failed=2)
        tracker.start_stage("quality")
        # ... continue ...
    """

    def __init__(self, total_tickers: int = 0, disable: bool = False):
        """
        Initialize progress tracker.

        Args:
            total_tickers: Total number of tickers to process
            disable: Disable progress bar (for testing or quiet mode)
        """
        self.total_tickers = total_tickers
        self.disable = disable or not HAS_TQDM

        self._pbar = None
        self._current_stage = None
        self._stage_start_time = 0.0
        self._stage_timing_history: Dict[str, float] = {}
        self._completed_in_stage = 0
        self._total_in_stage = 0

    def _create_pbar(self, desc: str, total: int):
        """Create a new progress bar"""
        if self.disable:
            return None

        return tqdm.tqdm(
            desc=desc,
            total=total,
            unit="ticker",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            mininterval=0.1,
            miniters=1,
            dynamic_ncols=True,
            file=sys.stdout,
            disable=False
        )

    def start_stage(self, stage_name: str, total: int = None):
        """
        Start a new pipeline stage.

        Args:
            stage_name: Name of the stage (fetch, quality, roe, etc.)
            total: Number of items in this stage (defaults to total_tickers)
        """
        self._current_stage = stage_name
        self._completed_in_stage = 0
        self._total_in_stage = total if total is not None else self.total_tickers
        self._stage_start_time = time.time()

        if self._pbar:
            self._pbar.close()

        self._pbar = self._create_pbar(f"[{stage_name}] Processing", self._total_in_stage)

        stage_time_estimate = self._stage_timing_history.get(stage_name, 0)
        if stage_time_estimate > 0 and self._total_in_stage > 0:
            estimated_total = stage_time_estimate
            logger.info(f"Starting {stage_name} (~{estimated_total:.0f}s remaining)")

    def update(self, n: int = 1, stage_info: str = None):
        """
        Update progress by n items.

        Args:
            n: Number of items completed
            stage_info: Optional info to show in bar (e.g., "AAPL: OK")
        """
        if self._pbar:
            self._pbar.update(n)
            self._completed_in_stage += n

            if stage_info:
                self._pbar.set_postfix_str(stage_info, refresh=False)

    def end_stage(self, success: int = 0, failed: int = 0, insufficient: int = 0):
        """
        End current stage and log summary.

        Args:
            success: Number of successful items
            failed: Number of failed items
            insufficient: Number of insufficient data items
        """
        elapsed = time.time() - self._stage_start_time
        self._stage_timing_history[self._current_stage] = elapsed

        if self._pbar:
            self._pbar.close()
            self._pbar = None

        if success + failed + insufficient > 0:
            logger.info(
                f"[{self._current_stage}] Complete in {elapsed:.1f}s: "
                f"{success} success, {failed} failed, {insufficient} insufficient"
            )

        self._current_stage = None

    def set_description(self, desc: str):
        """Update progress bar description"""
        if self._pbar:
            self._pbar.set_description_str(f"[{desc}] Processing")

    def close(self):
        """Close the progress bar"""
        if self._pbar:
            self._pbar.close()
            self._pbar = None


class LoggingSuppressor:
    """
    Context manager to suppress logging during parallel operations.

    Suppresses all loggers at WARNING level to reduce noise during parallel fetching.

    Usage:
        with LoggingSuppressor():
            # All logger.info/warning calls suppressed here
            parallel_fetch()
    """

    def __init__(self, level: int = logging.WARNING):
        """
        Initialize suppressor.

        Args:
            level: Logging level to allow (WARNING and above by default)
        """
        self.level = level
        self.original_level = None
        self._handlers_original_levels = {}

    def __enter__(self):
        root_logger = logging.getLogger()
        self.original_level = root_logger.level
        root_logger.setLevel(self.level)

        for handler in root_logger.handlers:
            self._handlers_original_levels[handler] = handler.level
            handler.setLevel(self.level)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        root_logger = logging.getLogger()
        root_logger.setLevel(self.original_level)

        for handler, original_level in self._handlers_original_levels.items():
            handler.setLevel(original_level)

        return False


class QualityAnalysisScript:
    """
    Standalone quality analysis pipeline for stock indices

    Features:
    - Sequential and parallel fetching modes
    - Unified progress bar with ETA
    - Timeout support for large indices
    - Support for Russell 2000, Russell 3000, and all S&P indexes

    Workflow:
    1. Fetch watchlist tickers from configured index (SP500/SP400/SP600/etc.)
    2. Fetch financial data for all tickers in the index
    3. Calculate quality metrics for all tickers
    4. Classify market cap tiers
    5. Analyze ROE persistence
    6. Rank stocks by quality score
    7. Export results to JSON and summary text
    """

    def __init__(self, watchlist_config: Optional[WatchlistConfig] = None):
        """
        Initialize quality analysis script

        Args:
            watchlist_config: Watchlist configuration (defaults to S&P 500)
        """
        self.watchlist_config = watchlist_config or WatchlistConfig(index=WatchlistIndex.SP500)
        
        # Use EnhancedHybridDataFetcher with SimFin as primary, yfinance as fallback
        # This system automatically detects US vs foreign companies and routes accordingly
        import os
        fmp_api_key = os.getenv('FMP_API_KEY', '')  # No longer primary, but kept for compatibility
        simfin_api_key = os.getenv('SIMFIN_API_KEY', '9916893d-f20d-45b7-b4ac-4449607d5128')
        
        self.enhanced_fetcher = EnhancedHybridDataFetcher(
            fmp_api_key=fmp_api_key,
            simfin_api_key=simfin_api_key,
            enable_simfin=True
        )
        self.financial_fetcher = FinancialDataFetcher(enable_cache=True)  # Fallback
        self.fetcher = self.enhanced_fetcher  # Use enhanced fetcher by default
        self.market_cap_classifier = MarketCapClassifier()
        self.roe_analyzer = QualityPersistenceAnalyzer()
        self.quality_calculator = QualityMetricsCalculator()
        self.results = {}
        self._start_time = None
        self._timeout_seconds = 600  # Default 10 minutes
        self._parallel_fetcher = None  # Lazy initialization for parallel mode
        self._progress_tracker = None  # Pipeline progress tracker

    def _get_parallel_fetcher(self, max_workers: int = 10):
        """Get or create parallel fetcher instance"""
        if self._parallel_fetcher is None:
            try:
                from ..data.parallel_fetcher import ParallelFetcher
                self._parallel_fetcher = ParallelFetcher(
                    max_workers=max_workers,
                    requests_per_second=1.0,
                    enable_cache=True,
                    max_retries=3
                )
            except ImportError:
                logger.warning("ParallelFetcher not available, falling back to sequential mode")
                return None
        return self._parallel_fetcher

    def _check_timeout(self) -> bool:
        """Check if timeout has been reached"""
        if self._start_time is None:
            return False
        if self._timeout_seconds <= 0:
            return False
        elapsed = time.time() - self._start_time
        if elapsed >= self._timeout_seconds:
            logger.warning(f"Timeout reached ({self._timeout_seconds}s), stopping analysis")
            return True
        return False

    def get_watchlist_tickers(self, limit: Optional[int] = None) -> List[str]:
        """
        Get watchlist tickers from configured index

        Args:
            limit: Optional limit (overrides watchlist_config.limit if provided)

        Returns:
            List of ticker symbols
        """
        if limit:
            config_with_limit = WatchlistConfig(
                index=self.watchlist_config.index,
                custom_tickers=self.watchlist_config.custom_tickers,
                multi_indices=self.watchlist_config.multi_indices,
                limit=limit
            )
            watchlist = config_with_limit.get_tickers()
        else:
            watchlist = self.watchlist_config.get_tickers()

        if not watchlist:
            logger.error(f"Failed to fetch tickers from {self.watchlist_config.index.value}")
            return []

        logger.info(f"Using {self.watchlist_config.index.value} watchlist: {len(watchlist)} tickers")
        return watchlist

    def fetch_financial_data(
        self,
        tickers: List[str],
        parallel: bool = False,
        max_workers: int = 10
    ) -> Dict[str, FinancialData]:
        """
        Fetch financial data for list of tickers

        Args:
            tickers: List of ticker symbols
            parallel: Use parallel fetching (default: False)
            max_workers: Number of parallel workers (default: 10)

        Returns:
            Dict mapping ticker -> FinancialData
        """
        logger.info(f"Fetching financial data for {len(tickers)} tickers "
                   f"(parallel={parallel}, workers={max_workers})")

        self._progress_tracker.start_stage("fetch", total=len(tickers))

        if parallel and len(tickers) > 10:
            with LoggingSuppressor():
                results = self.fetcher.parallel_batch_fetch(
                    tickers,
                    max_workers=max_workers,
                    requests_per_second=1.0,
                    show_progress=True
                ) if hasattr(self.fetcher, 'parallel_batch_fetch') else {}
                if not results:
                    for ticker in tickers:
                        data = self.fetcher.fetch_complete_data(ticker) if hasattr(self.fetcher, 'fetch_complete_data') else None
                        results[ticker] = data
                        self._progress_tracker.update(1)
        elif parallel:
            with LoggingSuppressor():
                fetcher = self._get_parallel_fetcher(max_workers)
                if fetcher:
                    results = fetcher.batch_fetch_with_callback(
                        tickers,
                        progress_callback=lambda c, t: self._progress_tracker.update(1)
                    )
                else:
                    results = {}
                    for ticker in tickers:
                        data = self.fetcher.fetch_complete_data(ticker) if hasattr(self.fetcher, 'fetch_complete_data') else None
                        results[ticker] = data
                        self._progress_tracker.update(1)
        else:
            results = {}
            for ticker in tickers:
                data = self.fetcher.fetch_complete_data(ticker) if hasattr(self.fetcher, 'fetch_complete_data') else None
                results[ticker] = data
                self._progress_tracker.update(1)

        success_count = 0
        failed_count = 0
        insufficient_count = 0

        for ticker in tickers:
            data = results.get(ticker)
            if data:
                if isinstance(data, dict):
                    data_quality = data.get('data_quality')
                else:
                    data_quality = getattr(data, 'data_quality', None)
                if data_quality == "insufficient":
                    insufficient_count += 1
                else:
                    success_count += 1
            else:
                failed_count += 1

        self._progress_tracker.end_stage(success=success_count, failed=failed_count, insufficient=insufficient_count)

        def _get_data_quality(data):
            if isinstance(data, dict):
                return data.get('data_quality')
            return getattr(data, 'data_quality', None)

        valid_results = {
            ticker: data
            for ticker, data in results.items()
            if data and _get_data_quality(data) != "insufficient"
        }

        return valid_results

    def calculate_quality_metrics(
        self,
        financial_data: Dict[str, Any]
    ) -> Dict[str, QualityAnalysisResult]:
        """
        Calculate quality metrics for all tickers

        Args:
            financial_data: Dict mapping ticker -> financial data dict (from hybrid fetcher)

        Returns:
            Dict mapping ticker -> QualityAnalysisResult
        """
        quality_results = {}
        tickers = list(financial_data.keys())
        total = len(tickers)

        self._progress_tracker.start_stage("quality", total=total)

        for ticker in tickers:
            if self._check_timeout():
                logger.warning("Timeout reached during quality calculation")
                break

            try:
                ticker_data = financial_data[ticker]
                
                # Handle both dict (hybrid fetcher) and FinancialData object formats
                if isinstance(ticker_data, dict):
                    # Hybrid fetcher returns plain dict
                    calculator_input = {'ticker': ticker}
                    # Copy all fields from the dict
                    for key, value in ticker_data.items():
                        if key not in ['fmp_data', 'yf_data', 'source']:
                            calculator_input[key] = value
                else:
                    # FinancialData object - extract fields
                    calculator_input = {
                        'ticker': ticker,
                        'revenue': ticker_data.revenue,
                        'cogs': ticker_data.cogs,
                        'sga': ticker_data.sga,
                        'total_assets': ticker_data.total_assets,
                        'net_income': ticker_data.net_income,
                        'shareholder_equity': ticker_data.shareholder_equity,
                        'free_cash_flow': ticker_data.free_cash_flow,
                        'market_cap': ticker_data.market_cap,
                        'total_debt': ticker_data.total_debt,
                        'nopat': ticker_data.nopat,
                        # New fields for safety metrics
                        'retained_earnings': ticker_data.retained_earnings,
                        'ebit': ticker_data.ebit,
                        'ebitda': ticker_data.ebitda,
                        'interest_expense': ticker_data.interest_expense,
                        'working_capital': ticker_data.working_capital,
                        'operating_income': ticker_data.operating_income
                    }

                # If hybrid fetcher already provided historical data, use it
                # Otherwise, try to fetch from yfinance
                if 'revenue_history' not in calculator_input or 'prior_total_assets' not in calculator_input:
                    try:
                        historical_data = self.financial_fetcher.fetch_historical_financials(ticker, years=10)
                        if historical_data is not None and len(historical_data) >= 3:
                            # Calculate ROE history
                            roe_history = []
                            for _, row in historical_data.iterrows():
                                if row['shareholder_equity'] and row['net_income'] and row['shareholder_equity'] > 0:
                                    roe = row['net_income'] / row['shareholder_equity']
                                    roe_history.append(roe)

                            if len(roe_history) >= 3:
                                calculator_input['roe_history'] = roe_history

                            # Extract revenue history for CAGR calculation
                            if 'revenue_history' not in calculator_input:
                                revenue_history = []
                                for _, row in historical_data.iterrows():
                                    if row.get('revenue') is not None and row['revenue'] > 0:
                                        revenue_history.append(row['revenue'])
                                if len(revenue_history) >= 2:
                                    calculator_input['revenue_history'] = revenue_history
                                    logger.info(f"Extracted {len(revenue_history)} years of revenue history for {ticker}")

                            # Calculate prior_total_assets for asset growth
                            if 'prior_total_assets' not in calculator_input:
                                assets_history = []
                                for _, row in historical_data.iterrows():
                                    if row.get('total_assets') is not None and row['total_assets'] > 0:
                                        assets_history.append(row['total_assets'])
                                if len(assets_history) >= 2:
                                    calculator_input['prior_total_assets'] = assets_history[1]
                                    logger.info(f"Prior total assets for {ticker}: {calculator_input['prior_total_assets']:,.0f}")

                            # Calculate gross margin history for margin trend
                            if 'gross_margin_history' not in calculator_input:
                                gross_margin_history = []
                                for _, row in historical_data.iterrows():
                                    if row.get('revenue') and row.get('cogs') and row['revenue'] > 0:
                                        gp = row['revenue'] - row['cogs']
                                        margin = gp / row['revenue']
                                        gross_margin_history.append(margin)
                                if len(gross_margin_history) >= 3:
                                    calculator_input['gross_margin_history'] = gross_margin_history
                                    logger.info(f"Extracted {len(gross_margin_history)} periods of margin history for {ticker}")
                    except Exception as e:
                        logger.debug(f"Could not fetch historical data for {ticker}: {e}")

                result = self.quality_calculator.calculate_quality_metrics(calculator_input)
                quality_results[ticker] = result

            except Exception as e:
                logger.warning(f"Failed to calculate quality for {ticker}: {e}")
                continue

            self._progress_tracker.update(1)

        self._progress_tracker.end_stage(success=len(quality_results), failed=total - len(quality_results), insufficient=0)

        return quality_results

    def _analyze_roe_single(self, ticker: str) -> tuple:
        """Analyze ROE persistence for a single ticker (helper for parallel execution)"""
        try:
            hist_data = self.fetcher.fetch_historical_financials(ticker)

            if hist_data is not None and len(hist_data) >= 2:
                persistence_result = self.roe_analyzer.analyze_company(hist_data, ticker=ticker)

                if persistence_result:
                    incremental_roce = persistence_result.trend_analysis.get('incremental_roce_advantage', 0.0) if persistence_result.trend_analysis else 0.0

                    return (ticker, {
                        'years_analyzed': persistence_result.persistence_metrics.years_analyzed,
                        'roe_years_above_15pct': persistence_result.persistence_metrics.roe_years_above_15pct,
                        'roe_mean': persistence_result.persistence_metrics.roe_mean,
                        'incremental_roce_advantage': incremental_roce,
                        'classification': persistence_result.classification.value,
                        'compounder_confidence': persistence_result.compounder_confidence
                    })
            return (ticker, None)
        except Exception as e:
            logger.warning(f"Failed to analyze ROE persistence for {ticker}: {e}")
            return (ticker, None)

    def analyze_roe_persistence(
        self,
        tickers: List[str],
        parallel: bool = False,
        max_workers: int = 10
    ) -> Dict[str, Dict]:
        """
        Analyze ROE persistence for multiple tickers

        Args:
            tickers: List of ticker symbols
            parallel: Use parallel execution (default: False)
            max_workers: Number of parallel workers

        Returns:
            Dict mapping ticker -> ROE persistence data
        """
        logger.info(f"Analyzing ROE persistence for {len(tickers)} tickers "
                   f"(parallel={parallel}, workers={max_workers})")

        roe_persistence = {}

        self._progress_tracker.start_stage("roe", total=len(tickers))

        if parallel and len(tickers) > 10:
            with LoggingSuppressor():
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(self._analyze_roe_single, ticker): ticker
                        for ticker in tickers
                    }

                    for future in as_completed(futures):
                        if self._check_timeout():
                            break
                        ticker, result = future.result()
                        if result:
                            roe_persistence[ticker] = result
                        self._progress_tracker.update(1)

        else:
            for ticker in tickers:
                if self._check_timeout():
                    logger.warning("Timeout reached during ROE analysis")
                    break
                ticker_result = self._analyze_roe_single(ticker)
                if ticker_result[1]:
                    roe_persistence[ticker_result[0]] = ticker_result[1]
                self._progress_tracker.update(1)

        self._progress_tracker.end_stage(success=len(roe_persistence), failed=len(tickers) - len(roe_persistence), insufficient=0)

        return roe_persistence

    def export_results(
        self,
        quality_results: Dict[str, QualityAnalysisResult],
        market_cap_tiers: Dict[str, str],
        roe_persistence: Dict[str, Dict],
        strict_filters: Dict[str, Dict],
        data_quality: Optional[Dict[str, str]] = None,
        multi_day_mode: bool = False,
        orchestrator = None
    ):
        """
        Export quality analysis results to JSON and summary text

        Args:
            quality_results: Quality analysis results for all tickers
            market_cap_tiers: Market cap tier classification
            roe_persistence: ROE persistence analysis results
            strict_filters: Small cap strict quality filters results
            data_quality: Data quality for each ticker (complete/partial/insufficient)
        """
        output_dir = Path(__file__).parent.parent / "outputs"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d")

        sorted_results = sorted(
            quality_results.items(),
            key=lambda x: x[1].composite_score,
            reverse=True
        )

        output_data = {
            'timestamp': datetime.now().isoformat(),
            'index': self.watchlist_config.index.value,
            'tickers_analyzed': len(quality_results),
            'data_quality': data_quality or {},
            'quality_results': {
                ticker: {
                    'composite_score': result.composite_score,
                    'tier': result.tier.value if result.tier else "Unknown",
                    'market_cap': result.market_cap,
                    'red_flags_count': len(result.red_flags),
                    'red_flags': [
                        {
                            'category': rf.category,
                            'severity': rf.severity,
                            'description': rf.description
                        }
                        for rf in result.red_flags
                    ],
                    'metrics': {
                        m.name: {
                            'value': m.value,
                            'score': m.score,
                            'weighted_score': m.weighted_score
                        }
                        for m in result.metric_scores
                    }
                }
                for ticker, result in sorted_results
            },
            'market_cap_tiers': market_cap_tiers,
            'roe_persistence': roe_persistence,
            'strict_filters': strict_filters
        }

        json_file = output_dir / "quality_analysis.json"
        with open(json_file, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)

        logger.info(f"Exported JSON results to {json_file}")

        # Multi-day integration: use quarterly manager for incremental updates
        if multi_day_mode and orchestrator:
            from data.quarterly_manager import QuarterlyManager
            
            quarterly_manager = QuarterlyManager(output_dir)
            
            # Prepare data for incremental update
            new_analysis_data = []
            for ticker, result in sorted_results:
                market_cap_str = f"${result.market_cap/1_000_000_000:.1f}B" if result.market_cap >= 1_000_000_000 else f"${result.market_cap/1_000_000:.1f}M"
                
                new_analysis_data.append({
                    'ticker': ticker,
                    'quality_score': result.composite_score,
                    'market_cap': market_cap_str,
                    'tier': result.tier.value if result.tier else "Unknown",
                    'red_flags': len(result.red_flags)
                })
            
            # Update summary incrementally
            quarterly_manager.update_summary_incremental(
                new_analysis_data,
                self.watchlist_config.index.value,
                len(quality_results)
            )
            
            logger.info(f"Updated summary incrementally with {len(new_analysis_data)} results")
        else:
            # Standard summary file creation
            summary_file = output_dir / "quality_analysis_summary.txt"
            with open(summary_file, 'w') as f:
                f.write("="*60 + "\n")
                f.write("QUALITY ANALYSIS SUMMARY\n")
                f.write("="*60 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Index: {self.watchlist_config.index.value}\n")
                f.write(f"Stocks Analyzed: {len(quality_results)}\n")
                f.write("="*60 + "\n\n")

                f.write("QUALITY SCORE DISTRIBUTION:\n")
                f.write("-"*60 + "\n")
                elite = sum(1 for r in quality_results.values() if r.composite_score >= 85)
                strong = sum(1 for r in quality_results.values() if 70 <= r.composite_score < 85)
                moderate = sum(1 for r in quality_results.values() if 50 <= r.composite_score < 70)
                weak = sum(1 for r in quality_results.values() if r.composite_score < 50)

                f.write(f"Elite (85-100): {elite} stocks\n")
                f.write(f"Strong (70-84): {strong} stocks\n")
                f.write(f"Moderate (50-69): {moderate} stocks\n")
                f.write(f"Weak (0-49): {weak} stocks\n")
                f.write("\n")

                f.write("="*80 + "\n")
                f.write("TOP 20 STOCKS BY QUALITY SCORE:\n")
                f.write("-"*80 + "\n")
                f.write("Rank Ticker   Market Cap   Score    Tier         Red Flags \n")
                f.write("-"*80 + "\n")

                for i, (ticker, result) in enumerate(sorted_results[:20], 1):
                    market_cap_str = f"${result.market_cap/1_000_000_000:.1f}B" if result.market_cap >= 1_000_000_000 else f"${result.market_cap/1_000_000:.1f}M"
                    tier_str = result.tier.value if result.tier else "Unknown"
                    red_flags = len(result.red_flags)
                    score_str = f"{result.composite_score:.1f}"

                    f.write(f"{i:<5} {ticker:<8} {market_cap_str:<12} {score_str:<8}    {tier_str:<12} {red_flags:<10}\n")

                f.write("\n")

                f.write("="*60 + "\n")
                f.write("MARKET CAP DISTRIBUTION:\n")
                f.write("-"*60 + "\n")

                large_cap = sum(1 for tier in market_cap_tiers.values() if tier == "Large Cap")
                mid_cap = sum(1 for tier in market_cap_tiers.values() if tier == "Mid Cap")
                small_cap = sum(1 for tier in market_cap_tiers.values() if tier == "Small Cap")
                micro_cap = sum(1 for tier in market_cap_tiers.values() if tier == "Micro Cap")

                f.write(f"Large Cap (≥$50B): {large_cap} stocks\n")
                f.write(f"Mid Cap ($2B-$50B): {mid_cap} stocks\n")
                f.write(f"Small Cap ($500M-$2B): {small_cap} stocks\n")
                f.write(f"Micro Cap (<$500M): {micro_cap} stocks\n")

                if roe_persistence:
                    f.write(f"\n{'='*60}\n")
                    f.write("ROE PERSISTENCE SUMMARY:\n")
                    f.write("-"*60 + "\n")

                    compounders = sum(1 for r in roe_persistence.values() if r.get('classification') == 'Quality Compounder')
                    improvers = sum(1 for r in roe_persistence.values() if r.get('classification') == 'Quality Improver')
                    deteriorators = sum(1 for r in roe_persistence.values() if r.get('classification') == 'Quality Deteriorator')
                    inconsistent = sum(1 for r in roe_persistence.values() if r.get('classification') == 'Inconsistent')

                    f.write(f"Quality Compounders: {compounders} stocks\n")
                    f.write(f"Quality Improvers: {improvers} stocks\n")
                    f.write(f"Quality Deteriorators: {deteriorators} stocks\n")
                    f.write(f"Inconsistent: {inconsistent} stocks\n")

                f.write(f"\n{'='*60}\n")
                f.write("LOOKBACK PERIODS BY MARKET CAP:\n")
                f.write("-"*60 + "\n")
                f.write("Market cap tier determines how many years of historical data\n")
                f.write("are used for each quality dimension. Smaller caps use shorter\n")
                f.write("lookbacks due to data availability and higher volatility.\n")
                f.write("\n")

                f.write("Market Cap Tiers and Multipliers:\n")
                f.write("-"*60 + "\n")
                for tier in MarketCapTier:
                    multiplier = LookbackCalculator.MARKET_CAP_MULTIPLIERS.get(tier, 1.0)
                    tier_name = tier.value if hasattr(tier, 'value') else str(tier)
                    f.write(f"  {tier_name}: {multiplier:.2f}x multiplier\n")
                f.write("\n")

                f.write("Quality Dimension Base Lookbacks:\n")
                f.write("-"*60 + "\n")
                for dimension, config in QUALITY_DIMENSIONS.items():
                    base = config['default_lookback']
                    min_lb = config['min_lookback']
                    max_lb = config['max_lookback']
                    dim_name = dimension.title().replace('_', ' ')
                    f.write(f"  {dim_name}: {base} years (range: {min_lb}-{max_lb})\n")
                f.write("\n")

                f.write("Formula: Adjusted Lookback = Base × Market Cap Multiplier × Sector Adjustment\n")
                f.write("\n")
                f.write("Sector Adjustments:\n")
                f.write("-"*60 + "\n")
                for sector, adj in SECTOR_ADJUSTMENTS.items():
                    f.write(f"  {sector}: {adj:.2f}x\n")
                f.write("\n")

                tier_distribution = {}
                for tier in market_cap_tiers.values():
                    tier_distribution[tier] = tier_distribution.get(tier, 0) + 1

                f.write("This Index's Market Cap Distribution:\n")
                f.write("-"*60 + "\n")
                for tier_name, count in sorted(tier_distribution.items()):
                    f.write(f"  {tier_name}: {count} stocks\n")
                f.write("\n")

                f.write("Adjusted Lookback Examples by Tier:\n")
                f.write("-"*60 + "\n")
                for tier in MarketCapTier:
                    multiplier = LookbackCalculator.MARKET_CAP_MULTIPLIERS.get(tier, 1.0)
                    tier_name = tier.value if hasattr(tier, 'value') else str(tier)
                    f.write(f"\n  {tier_name} (×{multiplier:.2f}):\n")
                    for dimension in ['profitability', 'earnings_quality', 'growth_quality', 'safety', 'roe_persistence']:
                        base = QUALITY_DIMENSIONS[dimension]['default_lookback']
                        adj = base * multiplier
                        dim_name = dimension.title().replace('_', ' ')
                        f.write(f"    {dim_name}: {adj:.1f} years\n")

            logger.info(f"Exported summary to {summary_file}")

        # Multi-day progress tracking integration
        if multi_day_mode and orchestrator:
            from data.progress_tracker import StockProgress
            
            # Update progress tracker for each successfully analyzed stock
            for ticker, result in quality_results.items():
                progress = StockProgress(
                    ticker=ticker,
                    status='completed',
                    last_updated=datetime.now(),
                    quarter=orchestrator.quarterly_manager.get_current_quarter(),
                    api_calls_used=5 if result.market_cap >= 500_000_000_000 else (4 if result.market_cap >= 10_000_000_000 else (2 if result.market_cap >= 2_000_000_000 else 0)),
                    quality_score=result.composite_score,
                    processing_time_seconds=None
                )
                orchestrator.progress_tracker.save_stock_progress(progress)
            
            logger.info(f"Updated progress for {len(quality_results)} stocks in multi-day tracker")
        else:
            print("\n" + "="*60)
            print("QUALITY ANALYSIS COMPLETE")
            print("="*60)
            print(f"Index: {self.watchlist_config.index.value}")
            print(f"Stocks analyzed: {len(quality_results)}")
            print(f"Elite quality: {elite} stocks (≥85)")
            print(f"Strong quality: {strong} stocks (70-84)")
            print(f"\nResults saved to:")
            print(f"  - {json_file}")
            if not multi_day_mode:
                print(f"  - {summary_file}")
            print("="*60 + "\n")

    def run(
        self,
        watchlist_limit: Optional[int] = None,
        parallel: bool = False,
        max_workers: int = 10,
        timeout_seconds: int = 600,
        multi_day_mode: bool = False,
        orchestrator = None
    ):
        """
        Run complete quality analysis pipeline for stock index

        Args:
            watchlist_limit: Maximum number of watchlist tickers to analyze
            parallel: Use parallel fetching (default: False)
            max_workers: Number of parallel workers (default: 10)
            timeout_seconds: Maximum runtime in seconds (default: 600 = 10 min)
            multi_day_mode: Enable multi-day orchestration integration (default: False)
            orchestrator: MultiDayOrchestrator instance for progress tracking (default: None)
        """
        self._start_time = time.time()
        self._timeout_seconds = timeout_seconds

        logger.info("Starting quality analysis pipeline")
        logger.info(f"Mode: {'Parallel' if parallel else 'Sequential'}, Workers: {max_workers}, Timeout: {timeout_seconds}s")

        watchlist = self.get_watchlist_tickers(limit=watchlist_limit)
        if not watchlist:
            logger.error("No watchlist tickers available. Exiting.")
            return

        logger.info(f"Analyzing {len(watchlist)} tickers from {self.watchlist_config.index.value}")

        if self._check_timeout():
            logger.error("Timeout before starting analysis")
            return

        self._progress_tracker = PipelineProgressTracker(total_tickers=len(watchlist))

        with LoggingSuppressor():
            financial_data = self.fetch_financial_data(
                watchlist,
                parallel=parallel,
                max_workers=max_workers
            )

            if not financial_data:
                logger.error("No financial data fetched. Exiting.")
                self._progress_tracker.close()
                return

            if self._check_timeout():
                logger.error("Timeout during data fetching")
                self._progress_tracker.close()
                return

            quality_results = self.calculate_quality_metrics(financial_data)

            if not quality_results:
                logger.error("No quality metrics calculated. Exiting.")
                self._progress_tracker.close()
                return

            if self._check_timeout():
                logger.error("Timeout during quality calculation")
                self._progress_tracker.close()
                return

            self._progress_tracker.start_stage("classifying", total=len(quality_results))
            market_cap_results = self.market_cap_classifier.batch_classify_tickers(list(quality_results.keys()))
            market_cap_tiers = {
                ticker: tier_data.tier.value if tier_data.tier else "Unknown"
                for ticker, tier_data in market_cap_results.classifications.items()
            }
            self._progress_tracker.end_stage(success=len(market_cap_tiers), failed=0, insufficient=0)

            if self._check_timeout():
                logger.error("Timeout before ROE analysis")
                self._progress_tracker.close()
                return

            roe_persistence = self.analyze_roe_persistence(
                list(quality_results.keys()),
                parallel=parallel,
                max_workers=max_workers
            )

            if self._check_timeout():
                logger.warning("Timeout during ROE analysis, continuing with available data")

            self._progress_tracker.start_stage("filters", total=len(market_cap_tiers))
            strict_filters = {}
            for ticker, tier in market_cap_tiers.items():
                if tier == "Small Cap":
                    data = financial_data.get(ticker)
                    if data:
                        try:
                            fcf_positive = data.free_cash_flow and data.free_cash_flow > 0

                            if data.total_debt and data.shareholder_equity and data.shareholder_equity > 0:
                                debt_to_equity = data.total_debt / data.shareholder_equity
                                de_pass = debt_to_equity < 1.0
                            else:
                                de_pass = False

                            if data.revenue and data.cogs and data.revenue > 0:
                                gross_margin = (data.revenue - data.cogs) / data.revenue
                                gm_pass = gross_margin > 0.30
                            else:
                                gm_pass = False

                            passed = fcf_positive and de_pass and gm_pass

                            strict_filters[ticker] = {
                                'passed': passed,
                                'fcf_positive': fcf_positive,
                                'debt_to_equity_ok': de_pass,
                                'gross_margin_ok': gm_pass
                            }
                        except Exception as e:
                            logger.warning(f"Failed to check strict filters for {ticker}: {e}")
                            continue
            self._progress_tracker.update(1)

        self._progress_tracker.end_stage(success=len(strict_filters), failed=0, insufficient=0)
        logger.info(f"Analyzed strict filters for {len(strict_filters)} small cap tickers")

        def _get_data_quality(data):
            if isinstance(data, dict):
                return data.get('data_quality')
            return getattr(data, 'data_quality', None)

        data_quality_summary = {
            ticker: _get_data_quality(data)
            for ticker, data in financial_data.items()
            if data
        }

        self.export_results(
            quality_results,
            market_cap_tiers,
            roe_persistence,
            strict_filters,
            data_quality_summary,
            multi_day_mode,
            orchestrator
        )

        self._progress_tracker.close()

        elapsed = time.time() - self._start_time
        logger.info(f"Quality analysis pipeline complete in {elapsed:.1f}s")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze quality metrics for portfolio holdings vs watchlist alternatives"
    )
    parser.add_argument(
        '--index',
        type=str,
        default='sp500',
        choices=['sp500', 'sp400', 'sp600', 'nasdaq100', 'russell1000', 'russell2000', 'russell3000', 'combined_sp'],
        help='Index to screen (default: sp500)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of watchlist tickers to analyze (default: 50). Use 0 for all.'
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Enable parallel fetching for faster analysis'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='Number of parallel workers (default: 10)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=600,
        help='Maximum runtime in seconds (default: 600 = 10 minutes)'
    )

    args = parser.parse_args()

    index_map = {
        'sp500': WatchlistIndex.SP500,
        'sp400': WatchlistIndex.SP400,
        'sp600': WatchlistIndex.SP600,
        'nasdaq100': WatchlistIndex.NASDAQ100,
        'russell1000': WatchlistIndex.RUSSELL1000,
        'russell2000': WatchlistIndex.RUSSELL2000,
        'russell3000': WatchlistIndex.RUSSELL3000,
        'combined_sp': WatchlistIndex.COMBINED_SP
    }

    watchlist_config = WatchlistConfig(
        index=index_map[args.index],
        limit=args.limit if args.limit > 0 else None
    )

    logger.info(f"Using watchlist configuration: {watchlist_config}")

    script = QualityAnalysisScript(watchlist_config=watchlist_config)
    script.run(
        watchlist_limit=args.limit if args.limit > 0 else None,
        parallel=args.parallel,
        max_workers=args.workers,
        timeout_seconds=args.timeout
    )


if __name__ == "__main__":
    main()
