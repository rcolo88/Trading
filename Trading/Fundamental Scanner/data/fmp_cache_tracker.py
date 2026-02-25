"""
FMP Cache Tracker

Manages caching and rate limiting for Financial Modeling Prep (FMP) API.
FREE tier: 250 API calls/day with 30-day data expiry.

This tracker ensures we stay within the free tier limits while maintaining
fresh data for quality analysis.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import logging

# Import standardized configuration
from .fmp_config import get_api_calls_needed, get_market_cap_tier, MarketCapTier

logger = logging.getLogger(__name__)


class FMPCacheTracker:
    """
    Tracks which stocks have been fetched from FMP and when.
    Manages 250 calls/day free tier limit with intelligent caching.

    Features:
    - 30-day cache expiry (fundamental data doesn't change daily)
    - Priority-based refresh (never fetched > oldest > newest)
    - Daily call tracking with automatic midnight reset
    - Persistent storage (survives script restarts)
    """

    def __init__(self, cache_file: str = "fmp_cache_tracker.json", api_tier: str = 'FREE'):
        """
        Initialize FMP cache tracker.

        Args:
            cache_file: Path to JSON file storing cache data
            api_tier: API tier name (FREE, PREMIUM, ENTERPRISE)
        """
        self.cache_file = cache_file
        self.cache_data = self._load_cache()
        
        # Import API tier configuration
        from .fmp_config import get_api_tier_config
        api_config = get_api_tier_config(api_tier)
        
        self.max_daily_calls = api_config['daily_limit']
        self.cache_expiry_days = api_config['cache_expiry_days']
        self.api_tier = api_tier

    def _load_cache(self) -> Dict:
        """
        Load cache tracker from disk.

        Returns:
            Dict with cache metadata and stock data
        """
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded FMP cache: {len(data.get('stocks', {}))} stocks cached")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load cache, starting fresh: {e}")

        # Initialize empty cache
        return {
            'last_reset': datetime.now().isoformat(),
            'daily_calls': 0,
            'stocks': {}  # ticker -> {'last_fetched': timestamp, 'data': {...}}
        }

    def _save_cache(self):
        """Save cache tracker to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _reset_daily_if_needed(self):
        """Reset daily call counter at midnight."""
        last_reset = datetime.fromisoformat(self.cache_data['last_reset'])
        now = datetime.now()

        if now.date() > last_reset.date():
            logger.info(f"Resetting daily call counter (was {self.cache_data['daily_calls']}/250)")
            self.cache_data['daily_calls'] = 0
            self.cache_data['last_reset'] = now.isoformat()
            self._save_cache()

    def can_fetch(self, ticker: str) -> bool:
        """
        Check if we can fetch this stock today.

        Returns False if:
        - Daily limit reached (250 calls)
        - Stock data is fresh (< 30 days old)

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if we should fetch, False if we should use cache
        """
        self._reset_daily_if_needed()

        # Check daily limit
        if self.cache_data['daily_calls'] >= self.max_daily_calls:
            logger.warning(f"Daily limit reached ({self.max_daily_calls} calls), skipping {ticker}")
            return False

        # Check if cached and fresh
        if ticker in self.cache_data['stocks']:
            last_fetched = datetime.fromisoformat(
                self.cache_data['stocks'][ticker]['last_fetched']
            )
            age_days = (datetime.now() - last_fetched).days

            if age_days < self.cache_expiry_days:
                logger.debug(f"{ticker}: Using {age_days}-day-old cache (fresh)")
                return False  # Fresh data, no need to fetch

        return True

    def get_cached_data(self, ticker: str) -> Optional[Dict]:
        """
        Get cached FMP data for a stock.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Cached data dict or None if not cached
        """
        if ticker in self.cache_data['stocks']:
            return self.cache_data['stocks'][ticker].get('data')
        return None

    def record_fetch(self, ticker: str, data: Dict, calls_used: int = 2):
        """
        Record that we fetched data for this stock.

        Args:
            ticker: Stock ticker
            data: FMP API response data
            calls_used: Number of API calls used (default 2: ratios + score)
        """
        self.cache_data['stocks'][ticker] = {
            'last_fetched': datetime.now().isoformat(),
            'data': data
        }
        self.cache_data['daily_calls'] += calls_used
        self._save_cache()

        logger.info(
            f"Cached {ticker} data ({calls_used} calls used, "
            f"total today: {self.cache_data['daily_calls']}/{self.max_daily_calls})"
        )

    def get_market_cap_for_ticker(self, ticker: str) -> float:
        """
        Get market cap for a ticker (placeholder implementation).
        In production, this would query yfinance or a market cap database.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Market capitalization in dollars
        """
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            market_cap = stock.info.get('marketCap', 0)
            return market_cap or 0
        except Exception as e:
            logger.warning(f"Could not fetch market cap for {ticker}: {e}")
            return 0

    def calculate_optimal_stocks(self, tickers: List[str], available_calls: int) -> int:
        """
        Calculate maximum stocks that can be processed based on actual API call requirements.
        
        Args:
            tickers: List of ticker symbols to analyze
            available_calls: Number of API calls available today
            
        Returns:
            Maximum number of stocks that can be processed
        """
        calls_used = 0
        max_stocks = 0
        
        for ticker in tickers:
            market_cap = self.get_market_cap_for_ticker(ticker)
            calls_needed = get_api_calls_needed(market_cap)
            
            if calls_used + calls_needed <= available_calls:
                calls_used += calls_needed
                max_stocks += 1
            else:
                break
                
        logger.info(f"Calculated capacity: {max_stocks} stocks using {calls_used}/{available_calls} calls")
        return max_stocks

    def get_stale_stocks(self, tickers: List[str], max_count: Optional[int] = None) -> List[str]:
        """
        Get list of stocks that need updating (prioritized).

        Priority:
        1. Never fetched
        2. Oldest first (>30 days)
        3. Limit to available API calls with accurate capacity calculation

        Args:
            tickers: List of stock tickers to check
            max_count: Maximum stocks to refresh (calculated if None)

        Returns:
            List of ticker symbols to fetch
        """
        self._reset_daily_if_needed()

        # Calculate available calls
        available_calls = self.max_daily_calls - self.cache_data['daily_calls']
        
        # Calculate optimal max_stocks based on actual API requirements
        if max_count is None:
            max_stocks = self.calculate_optimal_stocks(tickers, available_calls)
        else:
            max_stocks = min(max_count, self.calculate_optimal_stocks(tickers, available_calls))

        stale: List[Tuple[str, Optional[int]]] = []

        for ticker in tickers:
            if ticker not in self.cache_data['stocks']:
                stale.append((ticker, None))  # Never fetched (highest priority)
            else:
                last_fetched = datetime.fromisoformat(
                    self.cache_data['stocks'][ticker]['last_fetched']
                )
                age_days = (datetime.now() - last_fetched).days

                if age_days >= self.cache_expiry_days:
                    stale.append((ticker, age_days))  # Stale data

        # Sort by priority: Never fetched first, then oldest
        stale.sort(key=lambda x: (x[1] is not None, x[1] if x[1] is not None else 999), reverse=True)

        result = [ticker for ticker, _ in stale[:max_stocks]]

        logger.info(
            f"Identified {len(result)}/{len(tickers)} stocks needing FMP refresh "
            f"({self.cache_data['daily_calls']}/{self.max_daily_calls} calls used today)"
        )

        return result

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats (stocks cached, calls used, etc.)
        """
        self._reset_daily_if_needed()

        cached_stocks = len(self.cache_data['stocks'])
        fresh_count = 0
        stale_count = 0

        for ticker, stock_data in self.cache_data['stocks'].items():
            last_fetched = datetime.fromisoformat(stock_data['last_fetched'])
            age_days = (datetime.now() - last_fetched).days

            if age_days < self.cache_expiry_days:
                fresh_count += 1
            else:
                stale_count += 1

        return {
            'total_cached': cached_stocks,
            'fresh_cache': fresh_count,
            'stale_cache': stale_count,
            'daily_calls_used': self.cache_data['daily_calls'],
            'daily_calls_limit': self.max_daily_calls,
            'daily_calls_remaining': self.max_daily_calls - self.cache_data['daily_calls'],
            'cache_expiry_days': self.cache_expiry_days,
            'last_reset': self.cache_data['last_reset']
        }

    def get_cache_expiry(self, endpoint_type: str) -> int:
        """
        Get adaptive cache expiry time based on endpoint type.
        
        Different data types have different refresh frequencies:
        - Profile/Company info: 30 days (rarely changes)
        - Financial statements: 7 days (quarterly updates)
        - Market data: 1 day (price-sensitive)
        - Technical indicators: 1 day (price-sensitive)
        
        Args:
            endpoint_type: Type of API endpoint
            
        Returns:
            Cache expiry in days
        """
        expiry_map = {
            'profile': 30,
            'company': 30,
            'financials': 7,
            'income_statement': 7,
            'balance_sheet': 7,
            'cash_flow': 7,
            'ratios': 7,
            'market_data': 1,
            'price': 1,
            'technical': 1,
            'quote': 1,
            'default': self.cache_expiry_days
        }
        
        return expiry_map.get(endpoint_type.lower(), self.cache_expiry_days)

    def is_cache_fresh(self, ticker: str, endpoint_type: str = 'default') -> bool:
        """
        Check if cached data is fresh for a specific endpoint type.
        
        Args:
            ticker: Stock ticker symbol
            endpoint_type: Type of API endpoint
            
        Returns:
            True if cache is fresh, False if needs refresh
        """
        if ticker not in self.cache_data['stocks']:
            return False
            
        last_fetched = datetime.fromisoformat(
            self.cache_data['stocks'][ticker]['last_fetched']
        )
        
        expiry_days = self.get_cache_expiry(endpoint_type)
        age_days = (datetime.now() - last_fetched).days
        
        return age_days < expiry_days

    def get_endpoint_usage_stats(self) -> Dict[str, Dict]:
        """
        Get usage statistics by endpoint type for analytics.
        
        Returns:
            Dict mapping endpoint types to usage stats
        """
        endpoint_stats = {}
        
        for ticker, stock_data in self.cache_data['stocks'].items():
            last_fetched = datetime.fromisoformat(stock_data['last_fetched'])
            age_days = (datetime.now() - last_fetched).days
            
            # Determine endpoint type based on data structure (heuristic)
            data = stock_data.get('data', {})
            if isinstance(data, dict):
                if 'symbol' in data and any(key in data for key in ['marketCap', 'industry', 'sector']):
                    endpoint_type = 'profile'
                elif any(key in data for key in ['revenue', 'netIncome', 'grossProfit']):
                    endpoint_type = 'financials'
                elif any(key in data for key in ['price', 'change', 'volume']):
                    endpoint_type = 'market_data'
                else:
                    endpoint_type = 'default'
            else:
                endpoint_type = 'default'
                
            if endpoint_type not in endpoint_stats:
                endpoint_stats[endpoint_type] = {
                    'count': 0,
                    'fresh_count': 0,
                    'stale_count': 0,
                    'avg_age_days': 0,
                    'expiry_days': self.get_cache_expiry(endpoint_type)
                }
                
            stats = endpoint_stats[endpoint_type]
            stats['count'] += 1
            stats['avg_age_days'] = (stats['avg_age_days'] * (stats['count'] - 1) + age_days) / stats['count']
            
            expiry_days = self.get_cache_expiry(endpoint_type)
            if age_days < expiry_days:
                stats['fresh_count'] += 1
            else:
                stats['stale_count'] += 1
                
        return endpoint_stats

    def optimize_cache_strategy(self, tickers: List[str]) -> Dict:
        """
        Analyze cache usage and recommend optimization strategies.
        
        Args:
            tickers: List of tickers to analyze
            
        Returns:
            Dict with optimization recommendations
        """
        endpoint_stats = self.get_endpoint_usage_stats()
        available_calls = self.max_daily_calls - self.cache_data['daily_calls']
        
        # Calculate refresh priorities
        refresh_priorities = []
        for endpoint_type, stats in endpoint_stats.items():
            stale_ratio = stats['stale_count'] / max(stats['count'], 1)
            refresh_priority = stale_ratio * stats['count']  # Weight by volume
            
            refresh_priorities.append({
                'endpoint': endpoint_type,
                'priority': refresh_priority,
                'stale_count': stats['stale_count'],
                'total_count': stats['count'],
                'calls_needed': stats['stale_count'] * 2  # Estimate 2 calls per refresh
            })
        
        # Sort by priority
        refresh_priorities.sort(key=lambda x: x['priority'], reverse=True)
        
        # Calculate what can be refreshed today
        recommended_refreshes = []
        calls_used = 0
        
        for priority in refresh_priorities:
            if calls_used + priority['calls_needed'] <= available_calls:
                recommended_refreshes.append(priority)
                calls_used += priority['calls_needed']
            else:
                break
        
        return {
            'available_calls': available_calls,
            'recommended_refreshes': recommended_refreshes,
            'total_calls_needed': calls_used,
            'endpoint_stats': endpoint_stats,
            'optimization_score': sum(p['priority'] for p in recommended_refreshes)
        }
    
    def get_daily_analytics(self) -> Dict:
        """
        Get comprehensive daily API usage analytics and recommendations.
        
        Returns:
            Dictionary with daily usage metrics and efficiency analysis
        """
        # Basic usage metrics
        calls_used = self.cache_data['daily_calls']
        calls_remaining = self.max_daily_calls - calls_used
        usage_percentage = (calls_used / self.max_daily_calls) * 100
        
        # Get endpoint statistics
        endpoint_stats = self.get_endpoint_usage_stats()
        
        # Cache efficiency metrics
        total_stocks = len(self.cache_data['stocks'])
        fresh_stocks = sum(
            1 for ticker, stock_data in self.cache_data['stocks'].items()
            if self._is_data_fresh(stock_data)
        )
        cache_hit_rate = (fresh_stocks / max(total_stocks, 1)) * 100
        
        # Calculate cost per quality score
        quality_scores_count = sum(
            1 for ticker, stock_data in self.cache_data['stocks'].items()
            if isinstance(stock_data.get('data', {}), dict) and 'score' in str(stock_data.get('data', {}))
        )
        cost_per_quality_score = calls_used / max(quality_scores_count, 1)
        
        # Generate rate limit warnings
        warnings = []
        if usage_percentage >= 95:
            warnings.append({
                'level': 'CRITICAL',
                'message': f'API limit nearly exhausted: {usage_percentage:.1f}% used',
                'action': 'Stop processing immediately'
            })
        elif usage_percentage >= 80:
            warnings.append({
                'level': 'WARNING', 
                'message': f'API limit approaching: {usage_percentage:.1f}% used',
                'action': 'Consider reducing processing volume'
            })
        elif usage_percentage >= 60:
            warnings.append({
                'level': 'INFO',
                'message': f'API usage moderate: {usage_percentage:.1f}% used',
                'action': 'Monitor usage trends'
            })
        
        # Efficiency recommendations
        recommendations = []
        if cache_hit_rate < 50:
            recommendations.append({
                'category': 'Cache Optimization',
                'priority': 'HIGH',
                'message': f'Low cache hit rate: {cache_hit_rate:.1f}%',
                'action': 'Consider longer cache periods for stable data'
            })
        
        if cost_per_quality_score > 10:
            recommendations.append({
                'category': 'API Efficiency',
                'priority': 'MEDIUM',
                'message': f'High cost per analysis: {cost_per_quality_score:.1f} calls/score',
                'action': 'Prioritize high-value stocks first'
            })
        
        if calls_remaining < 50 and total_stocks > 100:
            recommendations.append({
                'category': 'Processing Strategy',
                'priority': 'HIGH',
                'message': f'Limited API calls remaining: {calls_remaining}',
                'action': 'Focus on high-priority market caps (Mega/Large)'
            })
        
        # Market cap tier analysis
        tier_analysis = self._analyze_tier_usage()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'daily_usage': {
                'calls_used': calls_used,
                'calls_remaining': calls_remaining,
                'usage_percentage': round(usage_percentage, 2),
                'max_daily_calls': self.max_daily_calls
            },
            'cache_efficiency': {
                'total_stocks': total_stocks,
                'fresh_stocks': fresh_stocks,
                'cache_hit_rate': round(cache_hit_rate, 2),
                'stale_stocks': total_stocks - fresh_stocks
            },
            'api_efficiency': {
                'quality_scores_generated': quality_scores_count,
                'cost_per_quality_score': round(cost_per_quality_score, 2),
                'calls_per_stock': round(calls_used / max(total_stocks, 1), 2)
            },
            'endpoint_usage': endpoint_stats,
            'market_cap_analysis': tier_analysis,
            'warnings': warnings,
            'recommendations': recommendations,
            'efficiency_score': self._calculate_efficiency_score(calls_used, cache_hit_rate, cost_per_quality_score)
        }
    
    def _is_data_fresh(self, stock_data: Dict) -> bool:
        """Check if stock data is still fresh"""
        try:
            last_fetched = datetime.fromisoformat(stock_data['last_fetched'])
            age_days = (datetime.now() - last_fetched).days
            
            # Determine endpoint type for expiry check
            data = stock_data.get('data', {})
            if isinstance(data, dict):
                if 'symbol' in data and any(key in data for key in ['marketCap', 'industry', 'sector']):
                    endpoint_type = 'profile'
                elif any(key in data for key in ['revenue', 'netIncome', 'grossProfit']):
                    endpoint_type = 'financials'
                elif any(key in data for key in ['price', 'change', 'volume']):
                    endpoint_type = 'market_data'
                else:
                    endpoint_type = 'default'
            else:
                endpoint_type = 'default'
            
            expiry_days = self.get_cache_expiry(endpoint_type)
            return age_days < expiry_days
        except:
            return False
    
    def _analyze_tier_usage(self) -> Dict:
        """Analyze API usage by market cap tier"""
        tier_stats = {}
        
        for ticker, stock_data in self.cache_data['stocks'].items():
            market_cap = stock_data.get('market_cap', 0)
            tier = get_market_cap_tier(market_cap).value
            
            if tier not in tier_stats:
                tier_stats[tier] = {
                    'count': 0,
                    'total_calls': 0,
                    'fresh_count': 0,
                    'avg_market_cap': 0
                }
            
            # Update tier statistics
            tier_stats[tier]['count'] += 1
            tier_stats[tier]['total_calls'] += get_api_calls_needed(market_cap)
            tier_stats[tier]['avg_market_cap'] += market_cap
            
            if self._is_data_fresh(stock_data):
                tier_stats[tier]['fresh_count'] += 1
        
        # Calculate averages and efficiency metrics
        for tier, stats in tier_stats.items():
            if stats['count'] > 0:
                stats['avg_market_cap'] = stats['avg_market_cap'] // stats['count']
                stats['fresh_rate'] = (stats['fresh_count'] / stats['count']) * 100
                stats['calls_per_stock'] = stats['total_calls'] / stats['count']
        
        return tier_stats
    
    def _calculate_efficiency_score(self, calls_used: int, cache_hit_rate: float, 
                                 cost_per_quality_score: float) -> float:
        """
        Calculate overall API efficiency score (0-100).
        
        Args:
            calls_used: API calls used today
            cache_hit_rate: Percentage of fresh data in cache
            cost_per_quality_score: API calls per quality score generated
            
        Returns:
            Efficiency score (0-100)
        """
        # Usage efficiency (40% weight)
        usage_efficiency = 100
        if calls_used > self.max_daily_calls * 0.9:
            usage_efficiency = 60  # Overusing
        elif calls_used > self.max_daily_calls * 0.7:
            usage_efficiency = 80  # High but reasonable
        
        # Cache efficiency (35% weight)
        cache_efficiency = cache_hit_rate
        
        # Cost efficiency (25% weight)
        cost_efficiency = max(0, 100 - (cost_per_quality_score - 1) * 10)
        cost_efficiency = min(100, cost_efficiency)
        
        # Weighted average
        overall_score = (usage_efficiency * 0.4 + 
                        cache_efficiency * 0.35 + 
                        cost_efficiency * 0.25)
        
        return round(overall_score, 2)
    
    def check_rate_warnings(self) -> List[Dict]:
        """
        Check for rate limit warnings and return actionable alerts.
        
        Returns:
            List of warning dictionaries with severity and actions
        """
        warnings = []
        calls_used = self.cache_data['daily_calls']
        usage_percentage = (calls_used / self.max_daily_calls) * 100
        
        # Critical warnings
        if usage_percentage >= 95:
            warnings.append({
                'severity': 'CRITICAL',
                'percentage': usage_percentage,
                'message': 'API limit critical - stop processing immediately',
                'action': 'STOP_PROCESSING',
                'calls_remaining': self.max_daily_calls - calls_used
            })
        
        # High warnings  
        elif usage_percentage >= 80:
            warnings.append({
                'severity': 'HIGH',
                'percentage': usage_percentage,
                'message': 'API limit approaching - consider pausing processing',
                'action': 'CONSIDER_PAUSE',
                'calls_remaining': self.max_daily_calls - calls_used
            })
        
        # Medium warnings
        elif usage_percentage >= 60:
            warnings.append({
                'severity': 'MEDIUM',
                'percentage': usage_percentage, 
                'message': 'API usage moderate - monitor closely',
                'action': 'MONITOR_USAGE',
                'calls_remaining': self.max_daily_calls - calls_used
            })
        
        # Low warnings
        elif usage_percentage >= 40:
            warnings.append({
                'severity': 'LOW',
                'percentage': usage_percentage,
                'message': 'API usage normal - continue processing',
                'action': 'CONTINUE',
                'calls_remaining': self.max_daily_calls - calls_used
            })
        
        return warnings
    
    def calculate_cost_per_quality_score(self) -> float:
        """
        Calculate API calls consumed per quality score generated.
        
        Returns:
            Cost per quality score (calls/score)
        """
        calls_used = self.cache_data['daily_calls']
        
        # Count quality scores generated
        quality_scores_count = 0
        for ticker, stock_data in self.cache_data['stocks'].items():
            data = stock_data.get('data', {})
            if isinstance(data, dict) and any(
                key in str(data).lower() for key in ['piotroski', 'z_score', 'quality']
            ):
                quality_scores_count += 1
        
        return calls_used / max(quality_scores_count, 1)
    
    def generate_usage_report(self, format_type: str = 'text') -> str:
        """
        Generate comprehensive usage report in specified format.
        
        Args:
            format_type: 'text' or 'json'
            
        Returns:
            Formatted usage report string
        """
        analytics = self.get_daily_analytics()
        warnings = self.check_rate_warnings()
        
        if format_type == 'json':
            return json.dumps({
                'analytics': analytics,
                'warnings': warnings,
                'timestamp': datetime.now().isoformat()
            }, indent=2)
        
        # Text format
        report_lines = [
            "=" * 60,
            "FMP API USAGE ANALYTICS REPORT",
            "=" * 60,
            f"Generated: {analytics['timestamp']}",
            "",
            "DAILY USAGE SUMMARY:",
            "-" * 30,
            f"Calls Used: {analytics['daily_usage']['calls_used']}/{analytics['daily_usage']['max_daily_calls']}",
            f"Usage Rate: {analytics['daily_usage']['usage_percentage']}%",
            f"Calls Remaining: {analytics['daily_usage']['calls_remaining']}",
            "",
            "CACHE EFFICIENCY:",
            "-" * 30,
            f"Total Stocks: {analytics['cache_efficiency']['total_stocks']}",
            f"Fresh Data: {analytics['cache_efficiency']['fresh_stocks']} ({analytics['cache_efficiency']['cache_hit_rate']}%)",
            f"Stale Data: {analytics['cache_efficiency']['stale_stocks']}",
            "",
            "API EFFICIENCY:",
            "-" * 30,
            f"Quality Scores Generated: {analytics['api_efficiency']['quality_scores_generated']}",
            f"Cost per Score: {analytics['api_efficiency']['cost_per_quality_score']} calls/score",
            f"Calls per Stock: {analytics['api_efficiency']['calls_per_stock']}",
            "",
            "OVERALL EFFICIENCY SCORE:",
            "-" * 30,
            f"Score: {analytics['efficiency_score']}/100",
            "",
        ]
        
        # Add warnings if any
        if warnings:
            report_lines.extend([
                "RATE LIMIT WARNINGS:",
                "-" * 30,
            ])
            for warning in warnings:
                report_lines.append(
                    f"{warning['severity']}: {warning['message']} ({warning['percentage']:.1f}%)"
                )
            report_lines.append("")
        
        # Add recommendations if any
        if analytics['recommendations']:
            report_lines.extend([
                "RECOMMENDATIONS:",
                "-" * 30,
            ])
            for rec in analytics['recommendations']:
                report_lines.append(
                    f"{rec['priority']}: {rec['message']}"
                )
            report_lines.append("")
        
        # Add market cap analysis
        if analytics['market_cap_analysis']:
            report_lines.extend([
                "MARKET CAP TIER ANALYSIS:",
                "-" * 30,
            ])
            for tier, stats in analytics['market_cap_analysis'].items():
                report_lines.append(
                    f"{tier}: {stats['count']} stocks, "
                    f"{stats['calls_per_stock']:.1f} calls/stock, "
                    f"{stats['fresh_rate']:.1f}% fresh"
                )
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def export_analytics_to_file(self, filepath: str, format_type: str = 'json') -> None:
        """
        Export analytics data to file for historical tracking.
        
        Args:
            filepath: Path to export file
            format_type: 'json' or 'csv'
        """
        analytics = self.get_daily_analytics()
        analytics['warnings'] = self.check_rate_warnings()
        
        if format_type == 'json':
            with open(filepath, 'w') as f:
                json.dump(analytics, f, indent=2)
        
        elif format_type == 'csv':
            import csv
            
            # Flatten analytics for CSV
            csv_data = {
                'timestamp': analytics['timestamp'],
                'calls_used': analytics['daily_usage']['calls_used'],
                'calls_remaining': analytics['daily_usage']['calls_remaining'],
                'usage_percentage': analytics['daily_usage']['usage_percentage'],
                'total_stocks': analytics['cache_efficiency']['total_stocks'],
                'fresh_stocks': analytics['cache_efficiency']['fresh_stocks'],
                'cache_hit_rate': analytics['cache_efficiency']['cache_hit_rate'],
                'quality_scores_generated': analytics['api_efficiency']['quality_scores_generated'],
                'cost_per_quality_score': analytics['api_efficiency']['cost_per_quality_score'],
                'efficiency_score': analytics['efficiency_score'],
                'warning_count': len(analytics['warnings']),
                'recommendation_count': len(analytics['recommendations'])
            }
            
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=csv_data.keys())
                writer.writeheader()
                writer.writerow(csv_data)
        
        logger.info(f"Analytics exported to {filepath}")
