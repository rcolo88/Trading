#!/usr/bin/env python3
"""
Market Environment Analyzer - STEP 1 of STEPS Methodology

Analyzes current market conditions (S&P 500, VIX, sector rotation) to provide
context for portfolio strategy decisions.

Features:
- S&P 500 trend analysis (golden cross/death cross)
- VIX volatility regime classification
- Sector rotation analysis (11 sector ETFs)
- Market breadth and risk appetite assessment
- 4-hour caching for efficiency
- JSON and markdown export
- Uses Schwab API for real-time price data

Author: LLM Portfolio Management System
Date: November 10, 2025 (Updated to use Schwab API)
"""

import pickle
import json
import logging
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# Import Schwab data fetcher for real-time price data
from schwab_data_fetcher import SchwabDataFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Sector ETF to sector name mapping
SECTOR_ETF_MAP = {
    "XLK": "Technology",
    "XLC": "Communication Services",
    "XLV": "Healthcare",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLP": "Consumer Staples",
    "XLY": "Consumer Discretionary",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials"
}


@dataclass
class MarketEnvironment:
    """Market environment assessment output"""

    # S&P 500 metrics
    sp500_price: float
    sp500_50ma: float
    sp500_200ma: float
    sp500_1m_return: float
    sp500_ytd_return: float

    # Trend classification
    trend: str  # STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR

    # Volatility metrics
    vix_level: float
    vix_20ma: float
    volatility_regime: str  # LOW, MODERATE, ELEVATED, HIGH

    # Sector rotation
    leading_sectors: List[str]  # Top 3
    lagging_sectors: List[str]  # Bottom 3
    sector_performance: Dict[str, float]  # All 11 sectors with 1m returns

    # Market characterization
    market_breadth: str  # NARROW, MODERATE, BROAD
    risk_appetite: str  # RISK_ON, NEUTRAL, RISK_OFF

    # Summary
    summary: str  # 2-3 sentence market summary
    analysis_date: str
    data_quality: str  # COMPLETE, PARTIAL, INSUFFICIENT


class MarketCache:
    """Simple 4-hour file cache for market data"""

    def __init__(self, cache_file: str = "market_environment_cache.pkl"):
        self.cache_file = Path(cache_file)
        self.cache_duration = timedelta(hours=4)

    def get(self) -> Optional[MarketEnvironment]:
        """Retrieve cached market environment if valid"""
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'rb') as f:
                cached_data = pickle.load(f)

            # Check if cache is still valid
            cache_time = datetime.fromisoformat(cached_data['timestamp'])
            if datetime.now() - cache_time < self.cache_duration:
                logger.info(f"Using cached market data from {cache_time}")
                return cached_data['environment']
            else:
                logger.info("Cache expired, will fetch fresh data")
                return None

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    def set(self, environment: MarketEnvironment):
        """Cache market environment with timestamp"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'environment': environment
            }
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            logger.info(f"Cached market data to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")


class MarketEnvironmentAnalyzer:
    """Analyzes current market environment (STEP 1 of STEPS)"""

    def __init__(self, enable_cache: bool = True):
        """
        Initialize market environment analyzer

        Args:
            enable_cache: If True, use 4-hour cache for market data
        """
        self.cache = MarketCache() if enable_cache else None
        self.schwab_fetcher = SchwabDataFetcher()
        logger.info("Initialized MarketEnvironmentAnalyzer with Schwab API")

    def fetch_sp500_data(self) -> Dict:
        """
        Fetch S&P 500 data using Schwab API

        Note: Uses SPY (SPDR S&P 500 ETF) as proxy since Schwab API
        does not support direct index quotes. SPY tracks S&P 500 with 99.9% correlation.

        Returns:
            Dict with price, moving averages, and returns
        """
        try:
            logger.info("Fetching S&P 500 data via Schwab API (using SPY as proxy)...")

            # Use SPY ETF as S&P 500 proxy (Schwab API doesn't support direct index quotes)
            sp500_ticker = "SPY"  # SPDR S&P 500 ETF Trust (best S&P 500 proxy)

            # Get historical data (252 trading days ≈ 1 year)
            response = self.schwab_fetcher.client.get_price_history_every_day(
                sp500_ticker,
                start_datetime=datetime.now() - timedelta(days=365),
                end_datetime=datetime.now()
            )

            if response.status_code != 200:
                logger.error(f"Failed to fetch S&P 500 history: Status {response.status_code}")
                return None

            history_data = response.json()

            # Parse historical candles into pandas Series
            if 'candles' not in history_data or not history_data['candles']:
                logger.error("No S&P 500 historical data available")
                return None

            candles = history_data['candles']
            dates = [pd.to_datetime(c['datetime'], unit='ms') for c in candles]
            close_prices = [c['close'] for c in candles]

            # Create pandas Series for calculations
            hist = pd.Series(close_prices, index=dates)

            if len(hist) == 0:
                logger.error("No S&P 500 data available")
                return None

            # Current price
            current_price = hist.iloc[-1]

            # Calculate moving averages
            ma_50 = hist.tail(50).mean() if len(hist) >= 50 else hist.mean()
            ma_200 = hist.tail(200).mean() if len(hist) >= 200 else hist.mean()

            # Calculate returns
            one_month_ago_price = hist.iloc[-21] if len(hist) >= 21 else hist.iloc[0]
            ytd_start_price = hist.iloc[0]

            one_month_return = ((current_price - one_month_ago_price) / one_month_ago_price) * 100
            ytd_return = ((current_price - ytd_start_price) / ytd_start_price) * 100

            result = {
                'price': current_price,
                'ma_50': ma_50,
                'ma_200': ma_200,
                '1m_return': one_month_return,
                'ytd_return': ytd_return
            }

            logger.info(f"S&P 500: ${current_price:.2f} (1M: {one_month_return:+.2f}%, YTD: {ytd_return:+.2f}%) [Schwab API]")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch S&P 500 data from Schwab API: {e}")
            return None

    def fetch_vix_data(self) -> Dict:
        """
        Fetch VIX data using Schwab API with yfinance fallback

        Note: Schwab API may not support VIX index quotes. Falls back to yfinance
        (ticker ^VIX) for free historical VIX data. Final fallback is default 20.0.

        Returns:
            Dict with current level and 20-day average
        """
        # Try Schwab API first
        try:
            logger.info("Fetching VIX data via Schwab API...")
            vix_ticker_schwab = "$VIX.X"  # Schwab format for VIX index

            response = self.schwab_fetcher.client.get_price_history_every_day(
                vix_ticker_schwab,
                start_datetime=datetime.now() - timedelta(days=30),
                end_datetime=datetime.now()
            )

            if response.status_code == 200:
                history_data = response.json()

                if 'candles' in history_data and history_data['candles'] and len(history_data['candles']) > 0:
                    candles = history_data['candles']
                    close_prices = [c['close'] for c in candles]

                    current_level = close_prices[-1]
                    ma_20 = np.mean(close_prices[-20:]) if len(close_prices) >= 20 else np.mean(close_prices)

                    logger.info(f"VIX: {current_level:.2f} (20-day avg: {ma_20:.2f}) [Schwab API]")
                    return {'level': current_level, 'ma_20': ma_20, 'quality': 'COMPLETE'}

        except Exception as e:
            logger.warning(f"Schwab API VIX fetch failed: {e}")

        # Fallback to yfinance (free, accurate VIX data)
        try:
            import yfinance as yf
            logger.info("Fetching VIX data via yfinance fallback (^VIX)...")

            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1mo")  # Last 30 days

            if not hist.empty:
                close_prices = hist['Close'].values
                current_level = close_prices[-1]
                ma_20 = np.mean(close_prices[-20:]) if len(close_prices) >= 20 else np.mean(close_prices)

                logger.info(f"VIX: {current_level:.2f} (20-day avg: {ma_20:.2f}) [yfinance fallback]")
                return {'level': current_level, 'ma_20': ma_20, 'quality': 'COMPLETE'}

        except Exception as e:
            logger.warning(f"yfinance VIX fetch failed: {e}")

        # Final fallback to default
        logger.warning("Using default VIX value 20.0 (no data source available)")
        return {'level': 20.0, 'ma_20': 20.0, 'quality': 'PARTIAL'}

    def fetch_sector_performance(self) -> Dict[str, float]:
        """
        Fetch 1-month performance for 11 sector ETFs using Schwab API

        Returns:
            Dict mapping sector name to 1-month return %
        """
        logger.info("Fetching sector performance via Schwab API...")
        sector_performance = {}

        for etf, sector_name in SECTOR_ETF_MAP.items():
            try:
                # Get 1 month of historical data
                response = self.schwab_fetcher.client.get_price_history_every_day(
                    etf,
                    start_datetime=datetime.now() - timedelta(days=30),
                    end_datetime=datetime.now()
                )

                if response.status_code == 200:
                    history_data = response.json()

                    if 'candles' in history_data and history_data['candles'] and len(history_data['candles']) >= 2:
                        candles = history_data['candles']
                        start_price = candles[0]['close']
                        end_price = candles[-1]['close']
                        one_month_return = ((end_price - start_price) / start_price) * 100
                        sector_performance[sector_name] = one_month_return
                        logger.debug(f"{sector_name} ({etf}): {one_month_return:+.2f}%")
                    else:
                        logger.warning(f"Insufficient data for {etf}")
                else:
                    logger.warning(f"Failed to fetch {etf}: Status {response.status_code}")

            except Exception as e:
                logger.warning(f"Failed to fetch {etf}: {e}")

        logger.info(f"Successfully fetched {len(sector_performance)}/11 sectors via Schwab API")
        return sector_performance

    def classify_trend(self, price: float, ma_50: float, ma_200: float) -> str:
        """
        Classify market trend using golden cross/death cross logic

        Args:
            price: Current S&P 500 price
            ma_50: 50-day moving average
            ma_200: 200-day moving average

        Returns:
            Trend classification: STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR
        """
        if price > ma_50 and ma_50 > ma_200:
            return "STRONG_BULL"
        elif price > ma_50:
            return "BULL"
        elif price < ma_50 and ma_50 < ma_200:
            return "STRONG_BEAR"
        elif price < ma_50:
            return "BEAR"
        else:
            return "NEUTRAL"

    def classify_volatility(self, vix_level: float) -> str:
        """
        Classify volatility regime based on VIX level

        Args:
            vix_level: Current VIX level

        Returns:
            Volatility regime: LOW, MODERATE, ELEVATED, HIGH
        """
        if vix_level < 15:
            return "LOW"
        elif vix_level < 20:
            return "MODERATE"
        elif vix_level < 30:
            return "ELEVATED"
        else:
            return "HIGH"

    def classify_breadth(self, sector_performance: Dict[str, float]) -> str:
        """
        Classify market breadth based on sector concentration

        Args:
            sector_performance: Dict of sector returns

        Returns:
            Market breadth: NARROW, MODERATE, BROAD
        """
        if not sector_performance:
            return "MODERATE"

        # Sort sectors by performance
        sorted_sectors = sorted(sector_performance.items(), key=lambda x: x[1], reverse=True)
        top_3_sectors = [s[0] for s in sorted_sectors[:3]]

        # Check if Tech and Communication Services both in top 3 (narrow leadership)
        if "Technology" in top_3_sectors and "Communication Services" in top_3_sectors:
            return "NARROW"

        # Check diversity of top performers
        positive_sectors = sum(1 for _, perf in sector_performance.items() if perf > 0)
        total_sectors = len(sector_performance)

        if positive_sectors >= total_sectors * 0.7:
            return "BROAD"
        else:
            return "MODERATE"

    def assess_risk_appetite(self, volatility_regime: str, trend: str) -> str:
        """
        Assess market risk appetite based on volatility and trend

        Args:
            volatility_regime: Current volatility classification
            trend: Current trend classification

        Returns:
            Risk appetite: RISK_ON, NEUTRAL, RISK_OFF
        """
        # RISK_ON: Low volatility + bullish trend
        if volatility_regime == "LOW" and trend in ["BULL", "STRONG_BULL"]:
            return "RISK_ON"

        # RISK_OFF: High volatility + bearish trend
        if volatility_regime in ["ELEVATED", "HIGH"] and trend in ["BEAR", "STRONG_BEAR"]:
            return "RISK_OFF"

        # NEUTRAL: everything else
        return "NEUTRAL"

    def generate_summary(self, env: MarketEnvironment) -> str:
        """
        Generate 2-3 sentence market summary

        Args:
            env: MarketEnvironment dataclass

        Returns:
            Human-readable market summary
        """
        # Sentence 1: S&P 500 status
        s1 = f"S&P 500 at {env.sp500_price:.0f} ({env.sp500_1m_return:+.2f}% 1M), "
        s1 += f"{env.volatility_regime.lower()} volatility (VIX {env.vix_level:.1f}), "
        s1 += f"{env.leading_sectors[0] if env.leading_sectors else 'mixed'} leadership."

        # Sentence 2: Market characterization
        trend_text = env.trend.replace("_", " ").lower()
        s2 = f"{trend_text.capitalize()} environment with {env.market_breadth.lower()} breadth."

        # Sentence 3: Risk appetite
        if env.risk_appetite == "RISK_ON":
            s3 = "Market conditions favor risk-taking (quality growth positions)."
        elif env.risk_appetite == "RISK_OFF":
            s3 = "Defensive posture warranted (raise cash, trim speculative)."
        else:
            s3 = "Neutral risk environment (maintain balanced allocation)."

        return f"{s1} {s2} {s3}"

    def analyze_market_environment(self) -> MarketEnvironment:
        """
        Main method: Execute complete market environment analysis

        Returns:
            MarketEnvironment dataclass with all metrics
        """
        logger.info("=" * 60)
        logger.info("STEP 1: Market Environment Assessment")
        logger.info("=" * 60)

        # Check cache first
        if self.cache:
            cached_env = self.cache.get()
            if cached_env:
                return cached_env

        # Fetch all market data
        sp500_data = self.fetch_sp500_data()
        vix_data = self.fetch_vix_data()
        sector_performance = self.fetch_sector_performance()

        # Determine data quality
        data_quality = "COMPLETE"
        if not sp500_data:
            logger.error("Cannot proceed without S&P 500 data")
            data_quality = "INSUFFICIENT"
            # Return minimal environment
            return MarketEnvironment(
                sp500_price=0, sp500_50ma=0, sp500_200ma=0,
                sp500_1m_return=0, sp500_ytd_return=0,
                trend="NEUTRAL", vix_level=20.0, vix_20ma=20.0,
                volatility_regime="MODERATE",
                leading_sectors=[], lagging_sectors=[],
                sector_performance={},
                market_breadth="MODERATE", risk_appetite="NEUTRAL",
                summary="Insufficient market data available",
                analysis_date=datetime.now().strftime("%Y-%m-%d"),
                data_quality=data_quality
            )

        if vix_data.get('quality') == 'PARTIAL':
            data_quality = "PARTIAL"

        if len(sector_performance) < 8:
            data_quality = "PARTIAL"

        # Run classifications
        trend = self.classify_trend(
            sp500_data['price'],
            sp500_data['ma_50'],
            sp500_data['ma_200']
        )

        volatility_regime = self.classify_volatility(vix_data['level'])

        market_breadth = self.classify_breadth(sector_performance)

        risk_appetite = self.assess_risk_appetite(volatility_regime, trend)

        # Identify leading and lagging sectors
        if sector_performance:
            sorted_sectors = sorted(sector_performance.items(), key=lambda x: x[1], reverse=True)
            leading_sectors = [s[0] for s in sorted_sectors[:3]]
            lagging_sectors = [s[0] for s in sorted_sectors[-3:]]
        else:
            leading_sectors = []
            lagging_sectors = []

        # Create MarketEnvironment
        env = MarketEnvironment(
            sp500_price=sp500_data['price'],
            sp500_50ma=sp500_data['ma_50'],
            sp500_200ma=sp500_data['ma_200'],
            sp500_1m_return=sp500_data['1m_return'],
            sp500_ytd_return=sp500_data['ytd_return'],
            trend=trend,
            vix_level=vix_data['level'],
            vix_20ma=vix_data['ma_20'],
            volatility_regime=volatility_regime,
            leading_sectors=leading_sectors,
            lagging_sectors=lagging_sectors,
            sector_performance=sector_performance,
            market_breadth=market_breadth,
            risk_appetite=risk_appetite,
            summary="",  # Will be filled next
            analysis_date=datetime.now().strftime("%Y-%m-%d"),
            data_quality=data_quality
        )

        # Generate summary
        env.summary = self.generate_summary(env)

        # Cache result
        if self.cache:
            self.cache.set(env)

        logger.info("=" * 60)
        logger.info(f"Market Summary: {env.summary}")
        logger.info("=" * 60)

        return env

    def export_to_json(self, environment: MarketEnvironment, output_file: str):
        """
        Export market environment to JSON

        Args:
            environment: MarketEnvironment to export
            output_file: Path to output JSON file
        """
        try:
            with open(output_file, 'w') as f:
                json.dump(asdict(environment), f, indent=2)
            logger.info(f"Exported market environment to {output_file}")
        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")

    def export_to_markdown(self, environment: MarketEnvironment, output_file: str):
        """
        Export market environment to markdown report

        Args:
            environment: MarketEnvironment to export
            output_file: Path to output markdown file
        """
        try:
            with open(output_file, 'w') as f:
                f.write("# Market Environment Analysis\n\n")
                f.write(f"**Date**: {environment.analysis_date}\n")
                f.write(f"**Data Quality**: {environment.data_quality}\n\n")

                f.write("## Executive Summary\n\n")
                f.write(f"{environment.summary}\n\n")

                f.write("## S&P 500 Metrics\n\n")
                f.write(f"- **Current Price**: ${environment.sp500_price:,.2f}\n")
                f.write(f"- **50-day MA**: ${environment.sp500_50ma:,.2f}\n")
                f.write(f"- **200-day MA**: ${environment.sp500_200ma:,.2f}\n")
                f.write(f"- **1-Month Return**: {environment.sp500_1m_return:+.2f}%\n")
                f.write(f"- **YTD Return**: {environment.sp500_ytd_return:+.2f}%\n")
                f.write(f"- **Trend**: {environment.trend}\n\n")

                f.write("## Volatility Metrics\n\n")
                f.write(f"- **VIX Level**: {environment.vix_level:.2f}\n")
                f.write(f"- **VIX 20-day MA**: {environment.vix_20ma:.2f}\n")
                f.write(f"- **Volatility Regime**: {environment.volatility_regime}\n\n")

                f.write("## Market Characterization\n\n")
                f.write(f"- **Market Breadth**: {environment.market_breadth}\n")
                f.write(f"- **Risk Appetite**: {environment.risk_appetite}\n\n")

                f.write("## Sector Rotation\n\n")
                f.write("### Leading Sectors (Top 3)\n\n")
                for i, sector in enumerate(environment.leading_sectors, 1):
                    perf = environment.sector_performance.get(sector, 0)
                    f.write(f"{i}. **{sector}**: {perf:+.2f}%\n")

                f.write("\n### Lagging Sectors (Bottom 3)\n\n")
                for i, sector in enumerate(environment.lagging_sectors, 1):
                    perf = environment.sector_performance.get(sector, 0)
                    f.write(f"{i}. **{sector}**: {perf:+.2f}%\n")

                f.write("\n### All Sector Performance\n\n")
                f.write("| Sector | 1-Month Return |\n")
                f.write("|--------|----------------|\n")

                sorted_sectors = sorted(
                    environment.sector_performance.items(),
                    key=lambda x: x[1],
                    reverse=True
                )

                for sector, perf in sorted_sectors:
                    f.write(f"| {sector} | {perf:+.2f}% |\n")

            logger.info(f"Exported markdown report to {output_file}")

        except Exception as e:
            logger.error(f"Failed to export markdown: {e}")


def main():
    """CLI interface for testing"""
    import argparse

    parser = argparse.ArgumentParser(description="Market Environment Analyzer (STEP 1)")
    parser.add_argument('--no-cache', action='store_true', help='Disable caching')
    parser.add_argument('--json', type=str, help='Export to JSON file')
    parser.add_argument('--markdown', type=str, help='Export to markdown file')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run analysis
    analyzer = MarketEnvironmentAnalyzer(enable_cache=not args.no_cache)
    env = analyzer.analyze_market_environment()

    # Print summary
    print("\n" + "=" * 60)
    print("MARKET ENVIRONMENT ANALYSIS")
    print("=" * 60)
    print(f"\nDate: {env.analysis_date}")
    print(f"Data Quality: {env.data_quality}\n")
    print(f"Summary:\n{env.summary}\n")
    print(f"Trend: {env.trend}")
    print(f"Volatility: {env.volatility_regime} (VIX {env.vix_level:.1f})")
    print(f"Risk Appetite: {env.risk_appetite}")
    print(f"Market Breadth: {env.market_breadth}")

    if env.leading_sectors:
        print(f"\nLeading Sectors: {', '.join(env.leading_sectors)}")
    if env.lagging_sectors:
        print(f"Lagging Sectors: {', '.join(env.lagging_sectors)}")

    # Export if requested
    if args.json:
        analyzer.export_to_json(env, args.json)

    if args.markdown:
        analyzer.export_to_markdown(env, args.markdown)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
