#!/usr/bin/env python3
"""
Portfolio Constructor - 4-Tier Market Cap Framework Implementation

Implements systematic portfolio construction following quality_investing_thresholds_research.md:
- Core Holdings (65-70%): Large cap ($50B+) with 5+ years ROE >15%
- Growth Quality (15-20%): Mid cap ($2B-$50B) with 2-3 years ROE >15%
- Opportunistic Quality (10-15%): Small cap ($500M-$2B) with strict quality filters
- High Risk/Thematic (5-10%): Momentum plays and thematic investments
- Cash Reserve: 5% target, 3% minimum

Author: LLM Portfolio Management System
Date: November 6, 2025
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

# Import market cap classifier and tier eligibility
from quality.market_cap_classifier import MarketCapTier, MarketCapClassifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== DATACLASSES ====================

@dataclass
class TieredAllocation:
    """Target portfolio allocation following 4-tier market cap framework"""
    large_cap_holdings: Dict[str, float]  # ticker → target % allocation
    mid_cap_holdings: Dict[str, float]    # ticker → target % allocation
    small_cap_holdings: Dict[str, float]  # ticker → target % allocation
    thematic_holdings: Dict[str, float]   # ticker → target % allocation
    cash_reserve: float                   # target % for cash
    total_large_cap_pct: float           # should be 65-70%
    total_mid_cap_pct: float             # should be 15-20%
    total_small_cap_pct: float           # should be 10-15%
    total_thematic_pct: float            # should be 5-10%
    violations: List[str]                # any constraint violations

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class AllocationReport:
    """Current portfolio allocation analysis"""
    current_large_cap_pct: float
    current_mid_cap_pct: float
    current_small_cap_pct: float
    current_thematic_pct: float
    current_cash_pct: float
    violations: List[str]
    rebalancing_needed: bool
    large_cap_holdings: Dict[str, float]  # ticker → current %
    mid_cap_holdings: Dict[str, float]    # ticker → current %
    small_cap_holdings: Dict[str, float]  # ticker → current %
    thematic_holdings: Dict[str, float]   # ticker → current %


@dataclass
class RiskParameters:
    """Risk management parameters for a position"""
    ticker: str
    stop_loss_pct: float  # e.g., -15.0
    profit_target_pct: float  # e.g., +30.0
    position_type: str  # LARGE_CAP, MID_CAP, SMALL_CAP, or THEMATIC
    tier: Optional[MarketCapTier] = None


# ==================== PORTFOLIO CONSTRUCTOR CLASS ====================

class PortfolioConstructor:
    """
    Portfolio construction engine following 4-tier market cap framework.

    Implements systematic allocation rules from quality_investing_thresholds_research.md:
    - Large Cap (Core): 65-70%, ROE-based sizing
    - Mid Cap (Growth): 15-20%, ROE + incremental ROCE-based sizing
    - Small Cap (Opportunistic): 10-15%, strict quality filters
    - Thematic: 5-10%, uniform sizing
    - Cash reserve: 5% target, 3% minimum
    """

    # 4-Tier allocation targets
    TARGET_LARGE_CAP_PCT = 67.5   # Midpoint of 65-70%
    TARGET_MID_CAP_PCT = 17.5     # Midpoint of 15-20%
    TARGET_SMALL_CAP_PCT = 12.5   # Midpoint of 10-15%
    TARGET_THEMATIC_PCT = 7.5     # Midpoint of 5-10%
    TARGET_CASH_PCT = 5.0

    # Tolerance bands (±2.5%)
    LARGE_CAP_MIN = 62.5
    LARGE_CAP_MAX = 72.5
    MID_CAP_MIN = 12.5
    MID_CAP_MAX = 22.5
    SMALL_CAP_MIN = 7.5
    SMALL_CAP_MAX = 17.5
    THEMATIC_MIN = 2.5
    THEMATIC_MAX = 12.5
    CASH_MIN = 3.0

    # Position limits by tier
    MAX_LARGE_CAP_POSITION = 15.0   # 15% max for large cap
    MAX_MID_CAP_POSITION = 10.0     # 10% max for mid cap
    MAX_SMALL_CAP_POSITION = 4.0    # 4% max for small cap (research: 2% typical, 4% absolute max)
    MAX_THEMATIC_POSITION = 2.5     # 2.5% max for thematic

    # Small cap strict quality filters
    SMALL_CAP_MIN_FCF = 0.0  # Positive FCF required
    SMALL_CAP_MAX_DEBT_EQUITY = 1.0  # D/E <1.0
    SMALL_CAP_MIN_GROSS_PROFIT_MARGIN = 0.30  # GP >30%

    # Minimum trade size
    MIN_TRADE_VALUE = 50.0

    def __init__(self):
        """Initialize Portfolio Constructor"""
        self.market_cap_classifier = MarketCapClassifier(enable_cache=True)
        logger.info("PortfolioConstructor initialized (4-Tier Framework)")

    def calculate_large_cap_position_size(self, roe: float) -> float:
        """
        Calculate position size for large cap holding based on ROE.

        Research guidelines:
        - ROE 15-20%: 8-12% position (use midpoint 10%)
        - ROE 20%+: 10-15% position (use midpoint 12.5%)

        Args:
            roe: Return on Equity (0.15 = 15%)

        Returns:
            Target position size as percentage
        """
        if roe >= 0.20:
            return 12.5  # Midpoint of 10-15%
        elif roe >= 0.15:
            return 10.0  # Midpoint of 8-12%
        else:
            return 0.0  # Below threshold, exit

    def calculate_mid_cap_position_size(
        self,
        roe: float,
        incremental_roce_advantage: float = 0.0
    ) -> float:
        """
        Calculate position size for mid cap holding based on ROE and incremental ROCE.

        Research guidelines:
        - ROE 15-20%, incremental ROCE +5%: 5-8% position (use midpoint 6.5%)
        - ROE 20%+, incremental ROCE +5%: 7-10% position (use midpoint 8.5%)

        Args:
            roe: Return on Equity (0.15 = 15%)
            incremental_roce_advantage: Incremental ROCE advantage in percentage points

        Returns:
            Target position size as percentage
        """
        # Require incremental ROCE advantage for mid-cap quality
        if incremental_roce_advantage < 5.0:
            logger.warning(f"Mid-cap missing incremental ROCE advantage (+{incremental_roce_advantage:.1f}%, need +5%)")
            # Still allow if ROE is good, but use smaller position
            if roe >= 0.20:
                return 6.5  # Conservative sizing
            elif roe >= 0.15:
                return 5.0  # Minimum position
            else:
                return 0.0

        # Has incremental ROCE advantage
        if roe >= 0.20:
            return 8.5  # Midpoint of 7-10%
        elif roe >= 0.15:
            return 6.5  # Midpoint of 5-8%
        else:
            return 0.0  # Below threshold, exit

    def calculate_small_cap_position_size(
        self,
        passes_strict_filters: bool,
        quality_score: float
    ) -> float:
        """
        Calculate position size for small cap holding.

        Research guidelines:
        - Positive ROE trend, strict quality filters: 2-4% position
        - Use 2% for marginal quality, 4% for exceptional
        - Strict filters: FCF+, D/E<1.0, GP>30%, top 80% quality

        Args:
            passes_strict_filters: Whether holding meets all strict quality filters
            quality_score: Quality score (0-100 scale)

        Returns:
            Target position size as percentage
        """
        if not passes_strict_filters:
            return 0.0  # Exit if fails strict filters

        # Position size based on quality score
        if quality_score >= 80.0:  # Top 20%
            return 4.0  # Maximum for small cap
        elif quality_score >= 70.0:
            return 3.0  # Mid-range
        elif quality_score >= 60.0:  # Top 80% (bottom 20% excluded)
            return 2.0  # Minimum position
        else:
            return 0.0  # Bottom quintile, exit

    def calculate_thematic_position_size(self, thematic_score: float) -> float:
        """
        Calculate position size for thematic holding.

        Research guidelines:
        - Uniform sizing: 1.5-2.5% per position
        - Use 2% as standard position size

        Args:
            thematic_score: Thematic score (0-40 scale)

        Returns:
            Target position size as percentage
        """
        if thematic_score >= 28.0:  # Meets threshold
            return 2.0  # Standard thematic position
        else:
            return 0.0  # Exit

    def validate_small_cap_filters(
        self,
        ticker: str,
        financial_data: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """
        Validate strict quality filters for small cap holdings.

        Strict filters from research:
        1. Positive free cash flow
        2. Debt/Equity <1.0
        3. Gross profitability >30%
        4. Quality score top 80% (checked in position sizing)

        Args:
            ticker: Stock ticker
            financial_data: Dict with fcf, total_debt, shareholder_equity, gross_margin

        Returns:
            Tuple of (passes: bool, failed_filters: List[str])
        """
        failed_filters = []

        # Check FCF
        fcf = financial_data.get('free_cash_flow', 0.0)
        if fcf <= self.SMALL_CAP_MIN_FCF:
            failed_filters.append(f"FCF {fcf/1e9:.1f}B not positive (need >0)")

        # Check Debt/Equity
        total_debt = financial_data.get('total_debt', 0.0)
        shareholder_equity = financial_data.get('shareholder_equity', 1.0)
        if shareholder_equity > 0:
            debt_equity = total_debt / shareholder_equity
            if debt_equity > self.SMALL_CAP_MAX_DEBT_EQUITY:
                failed_filters.append(f"D/E {debt_equity:.2f} exceeds 1.0")
        else:
            failed_filters.append("Shareholder equity ≤0 (cannot calculate D/E)")

        # Check Gross Profit Margin
        gross_margin = financial_data.get('gross_margin', 0.0)
        if gross_margin < self.SMALL_CAP_MIN_GROSS_PROFIT_MARGIN:
            failed_filters.append(f"Gross margin {gross_margin*100:.1f}% below 30%")

        passes = len(failed_filters) == 0

        if not passes:
            logger.warning(f"{ticker} fails small cap strict filters: {', '.join(failed_filters)}")

        return passes, failed_filters

    def calculate_target_allocation(
        self,
        holdings_by_tier: Dict[MarketCapTier, Dict[str, float]],  # tier → {ticker → score/data}
        financial_data: Dict[str, Dict[str, float]],  # ticker → financial metrics
        total_portfolio_value: float
    ) -> TieredAllocation:
        """
        Calculate target % allocation for each ticker based on tier and scores.

        Algorithm:
        1. Classify holdings by market cap tier
        2. Apply tier-specific position sizing
        3. Validate small cap strict filters
        4. Normalize each tier to target allocation
        5. Reserve cash
        6. Detect violations

        Args:
            holdings_by_tier: Dict of tier → {ticker → roe/score data}
            financial_data: Dict of ticker → financial metrics for validation
            total_portfolio_value: Total portfolio value in dollars

        Returns:
            TieredAllocation with target percentages and violations
        """
        logger.info(f"Calculating target allocation for 4-tier framework")

        # Calculate raw position sizes by tier
        large_cap_raw = {}
        mid_cap_raw = {}
        small_cap_raw = {}
        thematic_raw = {}

        # Large Cap positions
        for ticker, roe in holdings_by_tier.get(MarketCapTier.LARGE_CAP, {}).items():
            target_pct = self.calculate_large_cap_position_size(roe)
            if target_pct > 0:
                large_cap_raw[ticker] = target_pct

        # Mid Cap positions
        for ticker, data in holdings_by_tier.get(MarketCapTier.MID_CAP, {}).items():
            if isinstance(data, dict):
                roe = data.get('roe', 0.0)
                incremental_roce_adv = data.get('incremental_roce_advantage', 0.0)
            else:
                roe = data
                incremental_roce_adv = 0.0

            target_pct = self.calculate_mid_cap_position_size(roe, incremental_roce_adv)
            if target_pct > 0:
                mid_cap_raw[ticker] = target_pct

        # Small Cap positions (with strict filters)
        for ticker, data in holdings_by_tier.get(MarketCapTier.SMALL_CAP, {}).items():
            # Validate strict filters
            ticker_financials = financial_data.get(ticker, {})
            passes_filters, failed = self.validate_small_cap_filters(ticker, ticker_financials)

            if isinstance(data, dict):
                quality_score = data.get('quality_score', 0.0)
            else:
                quality_score = data if data > 10 else data * 10  # Convert 0-10 to 0-100 if needed

            target_pct = self.calculate_small_cap_position_size(passes_filters, quality_score)
            if target_pct > 0:
                small_cap_raw[ticker] = target_pct

        # Thematic positions (tier-agnostic)
        for ticker, thematic_score in holdings_by_tier.get('THEMATIC', {}).items():
            target_pct = self.calculate_thematic_position_size(thematic_score)
            if target_pct > 0:
                thematic_raw[ticker] = target_pct

        # Calculate raw totals
        raw_large_cap_total = sum(large_cap_raw.values())
        raw_mid_cap_total = sum(mid_cap_raw.values())
        raw_small_cap_total = sum(small_cap_raw.values())
        raw_thematic_total = sum(thematic_raw.values())

        # Normalize each tier INDEPENDENTLY to its target percentage
        # Only tiers with holdings get their target allocation
        # Position limits are checked during validation, not enforced here
        large_cap_normalized = {}
        if raw_large_cap_total > 0:
            for ticker, pct in large_cap_raw.items():
                large_cap_normalized[ticker] = (pct / raw_large_cap_total) * self.TARGET_LARGE_CAP_PCT

        mid_cap_normalized = {}
        if raw_mid_cap_total > 0:
            for ticker, pct in mid_cap_raw.items():
                mid_cap_normalized[ticker] = (pct / raw_mid_cap_total) * self.TARGET_MID_CAP_PCT

        small_cap_normalized = {}
        if raw_small_cap_total > 0:
            for ticker, pct in small_cap_raw.items():
                small_cap_normalized[ticker] = (pct / raw_small_cap_total) * self.TARGET_SMALL_CAP_PCT

        thematic_normalized = {}
        if raw_thematic_total > 0:
            for ticker, pct in thematic_raw.items():
                thematic_normalized[ticker] = (pct / raw_thematic_total) * self.TARGET_THEMATIC_PCT

        # Calculate totals after normalization
        total_large_cap_pct = sum(large_cap_normalized.values())
        total_mid_cap_pct = sum(mid_cap_normalized.values())
        total_small_cap_pct = sum(small_cap_normalized.values())
        total_thematic_pct = sum(thematic_normalized.values())

        # Calculate cash reserve (may be negative if all tiers are at target)
        allocated_pct = total_large_cap_pct + total_mid_cap_pct + total_small_cap_pct + total_thematic_pct

        if allocated_pct == 0:
            cash_reserve = 100.0
        else:
            cash_reserve = 100.0 - allocated_pct

        # Create TieredAllocation
        allocation = TieredAllocation(
            large_cap_holdings=large_cap_normalized,
            mid_cap_holdings=mid_cap_normalized,
            small_cap_holdings=small_cap_normalized,
            thematic_holdings=thematic_normalized,
            cash_reserve=cash_reserve,
            total_large_cap_pct=total_large_cap_pct,
            total_mid_cap_pct=total_mid_cap_pct,
            total_small_cap_pct=total_small_cap_pct,
            total_thematic_pct=total_thematic_pct,
            violations=[]
        )

        # Validate and detect violations
        violations = self.validate_allocation(allocation)
        allocation.violations = violations

        logger.info(f"Target allocation: Large {total_large_cap_pct:.1f}%, Mid {total_mid_cap_pct:.1f}%, Small {total_small_cap_pct:.1f}%, Thematic {total_thematic_pct:.1f}%, Cash {cash_reserve:.1f}%")
        if violations:
            logger.warning(f"Allocation violations detected: {len(violations)}")

        return allocation

    def validate_allocation(self, allocation: TieredAllocation) -> List[str]:
        """
        Check for constraint violations in 4-tier allocation.

        Checks:
        - Large cap: 62.5-72.5% (±2.5% from 67.5%)
        - Mid cap: 12.5-22.5% (±2.5% from 17.5%)
        - Small cap: 7.5-17.5% (±2.5% from 12.5%)
        - Thematic: 2.5-12.5% (±2.5% from 7.5%)
        - Individual position limits by tier
        - Cash reserve ≥3%

        Args:
            allocation: TieredAllocation to validate

        Returns:
            List of violation messages (empty if valid)
        """
        violations = []

        # Check tier allocations
        if allocation.total_large_cap_pct < self.LARGE_CAP_MIN:
            violations.append(f"Large cap allocation {allocation.total_large_cap_pct:.1f}% below {self.LARGE_CAP_MIN:.1f}%")
        elif allocation.total_large_cap_pct > self.LARGE_CAP_MAX:
            violations.append(f"Large cap allocation {allocation.total_large_cap_pct:.1f}% above {self.LARGE_CAP_MAX:.1f}%")

        if allocation.total_mid_cap_pct < self.MID_CAP_MIN:
            violations.append(f"Mid cap allocation {allocation.total_mid_cap_pct:.1f}% below {self.MID_CAP_MIN:.1f}%")
        elif allocation.total_mid_cap_pct > self.MID_CAP_MAX:
            violations.append(f"Mid cap allocation {allocation.total_mid_cap_pct:.1f}% above {self.MID_CAP_MAX:.1f}%")

        if allocation.total_small_cap_pct < self.SMALL_CAP_MIN:
            violations.append(f"Small cap allocation {allocation.total_small_cap_pct:.1f}% below {self.SMALL_CAP_MIN:.1f}%")
        elif allocation.total_small_cap_pct > self.SMALL_CAP_MAX:
            violations.append(f"Small cap allocation {allocation.total_small_cap_pct:.1f}% above {self.SMALL_CAP_MAX:.1f}%")

        if allocation.total_thematic_pct < self.THEMATIC_MIN:
            violations.append(f"Thematic allocation {allocation.total_thematic_pct:.1f}% below {self.THEMATIC_MIN:.1f}%")
        elif allocation.total_thematic_pct > self.THEMATIC_MAX:
            violations.append(f"Thematic allocation {allocation.total_thematic_pct:.1f}% above {self.THEMATIC_MAX:.1f}%")

        # Check cash reserve
        if allocation.cash_reserve < self.CASH_MIN:
            violations.append(f"Cash reserve {allocation.cash_reserve:.1f}% below {self.CASH_MIN:.0f}%")

        # Check individual position limits by tier
        for ticker, pct in allocation.large_cap_holdings.items():
            if pct > self.MAX_LARGE_CAP_POSITION:
                violations.append(f"Large cap {ticker} position {pct:.1f}% exceeds {self.MAX_LARGE_CAP_POSITION:.0f}% limit")

        for ticker, pct in allocation.mid_cap_holdings.items():
            if pct > self.MAX_MID_CAP_POSITION:
                violations.append(f"Mid cap {ticker} position {pct:.1f}% exceeds {self.MAX_MID_CAP_POSITION:.0f}% limit")

        for ticker, pct in allocation.small_cap_holdings.items():
            if pct > self.MAX_SMALL_CAP_POSITION:
                violations.append(f"Small cap {ticker} position {pct:.1f}% exceeds {self.MAX_SMALL_CAP_POSITION:.0f}% limit")

        for ticker, pct in allocation.thematic_holdings.items():
            if pct > self.MAX_THEMATIC_POSITION:
                violations.append(f"Thematic {ticker} position {pct:.1f}% exceeds {self.MAX_THEMATIC_POSITION:.0f}% limit")

        return violations

    def generate_rebalancing_trades(
        self,
        portfolio_state: Dict,
        target_allocation: TieredAllocation,
        current_prices: Dict[str, float]
    ) -> List[Dict]:
        """
        Generate specific trades to move from current to target allocation.

        Args:
            portfolio_state: Portfolio state dict with holdings and cash
            target_allocation: Target TieredAllocation
            current_prices: Dict of ticker → current_price

        Returns:
            List of trade dicts with action, ticker, shares, reasoning, priority
        """
        logger.info("Generating rebalancing trades for 4-tier framework")

        holdings = portfolio_state.get('holdings', {})
        cash = portfolio_state.get('cash', 0.0)

        # Calculate total portfolio value
        total_value = cash
        for ticker, holding_data in holdings.items():
            shares = holding_data.get('shares', holding_data) if isinstance(holding_data, dict) else holding_data
            price = current_prices.get(ticker, 100.0)
            total_value += shares * price

        trades = []

        # Get all target tickers
        all_target_tickers = (
            set(target_allocation.large_cap_holdings.keys()) |
            set(target_allocation.mid_cap_holdings.keys()) |
            set(target_allocation.small_cap_holdings.keys()) |
            set(target_allocation.thematic_holdings.keys())
        )

        # Step 1: Identify exits (holdings not in target)
        for ticker, holding_data in holdings.items():
            shares = holding_data.get('shares', holding_data) if isinstance(holding_data, dict) else holding_data
            if ticker not in all_target_tickers:
                trades.append({
                    'action': 'SELL',
                    'ticker': ticker,
                    'shares': int(shares),
                    'reasoning': 'Exit position - fails tier requirements',
                    'priority': 'HIGH'
                })

        # Step 2: Calculate position adjustments
        all_target_positions = {
            **target_allocation.large_cap_holdings,
            **target_allocation.mid_cap_holdings,
            **target_allocation.small_cap_holdings,
            **target_allocation.thematic_holdings
        }

        for ticker, target_pct in all_target_positions.items():
            target_value = (target_pct / 100.0) * total_value
            price = current_prices.get(ticker, 100.0)
            target_shares = int(target_value / price)

            holding_data = holdings.get(ticker, 0)
            current_shares = holding_data.get('shares', holding_data) if isinstance(holding_data, dict) else holding_data
            current_shares = int(current_shares) if current_shares else 0
            share_diff = target_shares - current_shares

            if abs(share_diff * price) >= self.MIN_TRADE_VALUE:
                if share_diff > 0:
                    trades.append({
                        'action': 'BUY',
                        'ticker': ticker,
                        'shares': share_diff,
                        'reasoning': f'Scale to {target_pct:.1f}% target allocation',
                        'priority': 'MEDIUM'
                    })
                elif share_diff < 0:
                    trades.append({
                        'action': 'SELL',
                        'ticker': ticker,
                        'shares': abs(share_diff),
                        'reasoning': f'Reduce to {target_pct:.1f}% target allocation',
                        'priority': 'MEDIUM'
                    })

        logger.info(f"Generated {len(trades)} rebalancing trades")
        return trades

    def calculate_risk_parameters(
        self,
        holdings_by_tier: Dict[str, str]  # ticker → tier_name
    ) -> Dict[str, RiskParameters]:
        """
        Calculate stop-loss and profit targets for each holding by tier.

        Rules from research:
        Large Cap: -15% stop, +30% profit target (lower risk/reward)
        Mid Cap: -20% stop, +40% profit target (balanced)
        Small Cap: -25% stop, +50% profit target (higher risk/reward)
        Thematic: -30% stop, +60% profit target (highest risk/reward)

        Args:
            holdings_by_tier: Dict of ticker → tier_name

        Returns:
            Dict of ticker → RiskParameters
        """
        logger.info(f"Calculating risk parameters for {len(holdings_by_tier)} holdings")

        risk_params = {}

        for ticker, tier_name in holdings_by_tier.items():
            if tier_name == 'LARGE_CAP':
                stop_loss = -15.0
                profit_target = 30.0
                tier = MarketCapTier.LARGE_CAP
            elif tier_name == 'MID_CAP':
                stop_loss = -20.0
                profit_target = 40.0
                tier = MarketCapTier.MID_CAP
            elif tier_name == 'SMALL_CAP':
                stop_loss = -25.0
                profit_target = 50.0
                tier = MarketCapTier.SMALL_CAP
            else:  # THEMATIC
                stop_loss = -30.0
                profit_target = 60.0
                tier = None

            risk_params[ticker] = RiskParameters(
                ticker=ticker,
                stop_loss_pct=stop_loss,
                profit_target_pct=profit_target,
                position_type=tier_name,
                tier=tier
            )

        logger.info(f"Calculated risk parameters for {len(risk_params)} holdings")
        return risk_params

    def export_allocation_to_json(
        self,
        allocation: TieredAllocation,
        filepath: str
    ):
        """Export allocation to JSON file."""
        try:
            output_path = Path(filepath)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(allocation.to_dict(), f, indent=2)

            logger.info(f"Exported allocation to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export allocation: {e}")
            raise

    def generate_allocation_summary(
        self,
        allocation: TieredAllocation
    ) -> str:
        """Generate human-readable allocation summary."""
        lines = [
            "# 4-Tier Portfolio Allocation Summary",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "## Tier Allocation",
            f"- **Large Cap (Core)**: {allocation.total_large_cap_pct:.1f}% (target 67.5%, range 62.5-72.5%)",
            f"- **Mid Cap (Growth)**: {allocation.total_mid_cap_pct:.1f}% (target 17.5%, range 12.5-22.5%)",
            f"- **Small Cap (Opportunistic)**: {allocation.total_small_cap_pct:.1f}% (target 12.5%, range 7.5-17.5%)",
            f"- **Thematic**: {allocation.total_thematic_pct:.1f}% (target 7.5%, range 2.5-12.5%)",
            f"- **Cash**: {allocation.cash_reserve:.1f}% (target 5.0%, min 3.0%)",
            ""
        ]

        if allocation.violations:
            lines.append("## Violations")
            for violation in allocation.violations:
                lines.append(f"- ⚠️ {violation}")
            lines.append("")

        lines.append("## Large Cap Holdings (Core)")
        if allocation.large_cap_holdings:
            for ticker, pct in sorted(allocation.large_cap_holdings.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {ticker}: {pct:.1f}%")
        else:
            lines.append("- None")
        lines.append("")

        lines.append("## Mid Cap Holdings (Growth Quality)")
        if allocation.mid_cap_holdings:
            for ticker, pct in sorted(allocation.mid_cap_holdings.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {ticker}: {pct:.1f}%")
        else:
            lines.append("- None")
        lines.append("")

        lines.append("## Small Cap Holdings (Opportunistic)")
        if allocation.small_cap_holdings:
            for ticker, pct in sorted(allocation.small_cap_holdings.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {ticker}: {pct:.1f}%")
        else:
            lines.append("- None")
        lines.append("")

        lines.append("## Thematic Holdings")
        if allocation.thematic_holdings:
            for ticker, pct in sorted(allocation.thematic_holdings.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {ticker}: {pct:.1f}%")
        else:
            lines.append("- None")

        return "\n".join(lines)


# Example usage and testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    constructor = PortfolioConstructor()

    # Example: Calculate target allocation
    holdings_by_tier = {
        MarketCapTier.LARGE_CAP: {
            'AAPL': 0.25,  # 25% ROE
            'MSFT': 0.18,  # 18% ROE
            'GOOGL': 0.22  # 22% ROE
        },
        MarketCapTier.MID_CAP: {
            'NVDA': {'roe': 0.18, 'incremental_roce_advantage': 8.0}
        },
        MarketCapTier.SMALL_CAP: {
            'QS': {'quality_score': 65.0}
        },
        'THEMATIC': {
            'IONQ': 32.0  # Thematic score
        }
    }

    financial_data = {
        'QS': {
            'free_cash_flow': 100e6,
            'total_debt': 200e6,
            'shareholder_equity': 500e6,
            'gross_margin': 0.35
        }
    }

    allocation = constructor.calculate_target_allocation(
        holdings_by_tier,
        financial_data,
        100000.0
    )

    print("\n" + constructor.generate_allocation_summary(allocation))
