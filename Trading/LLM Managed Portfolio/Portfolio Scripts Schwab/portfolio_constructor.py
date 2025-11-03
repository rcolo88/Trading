#!/usr/bin/env python3
"""
Portfolio Constructor - 80/20 Framework Implementation

Implements systematic portfolio construction following PM_README_V3.md:
- 80% Quality Compounders (core holdings, quality score ≥7)
- 20% Opportunistic/Thematic (tactical positions, thematic score ≥28)
- 5% Cash Reserve
- Score-based position sizing
- Automated rebalancing trade generation
- Risk parameter calculation (stop-loss, profit targets)

Author: LLM Portfolio Management System
Date: November 3, 2025
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== DATACLASSES ====================

@dataclass
class PortfolioAllocation:
    """Target portfolio allocation following 80/20 framework"""
    quality_holdings: Dict[str, float]  # ticker → target % allocation
    thematic_holdings: Dict[str, float]  # ticker → target % allocation
    cash_reserve: float  # target % for cash
    total_quality_pct: float  # should be ~80%
    total_thematic_pct: float  # should be ~20%
    violations: List[str]  # any constraint violations


@dataclass
class AllocationReport:
    """Current portfolio allocation analysis"""
    current_quality_pct: float
    current_thematic_pct: float
    current_cash_pct: float
    violations: List[str]
    rebalancing_needed: bool
    quality_holdings: Dict[str, float]  # ticker → current %
    thematic_holdings: Dict[str, float]  # ticker → current %


@dataclass
class RiskParameters:
    """Risk management parameters for a position"""
    ticker: str
    stop_loss_pct: float  # e.g., -15.0
    profit_target_pct: float  # e.g., +50.0
    position_type: str  # QUALITY or THEMATIC


# ==================== PORTFOLIO CONSTRUCTOR CLASS ====================

class PortfolioConstructor:
    """
    Portfolio construction engine following 80/20 quality/opportunistic framework.

    Implements systematic allocation rules from PM_README_V3.md:
    - Quality holdings (80%): Score-based sizing (7-10 scale)
    - Thematic holdings (20%): Score-based sizing (28-40 scale)
    - Cash reserve: 5% target, 3% minimum
    - Position limits: 20% max, thematic max 7%
    """

    # Quality position sizing rules (score → min%, max%)
    QUALITY_POSITION_SIZING = {
        (9.0, 10.0): (10.0, 20.0),   # Elite: 10-20%
        (8.0, 8.99): (7.0, 12.0),    # Strong: 7-12%
        (7.0, 7.99): (5.0, 8.0),     # Moderate: 5-8%
        (0.0, 6.99): (0.0, 0.0)      # Weak: EXIT
    }

    # Thematic position sizing rules (score → min%, max%)
    THEMATIC_POSITION_SIZING = {
        (35.0, 40.0): (5.0, 7.0),    # Leader: 5-7%
        (30.0, 34.9): (3.0, 5.0),    # Strong Contender: 3-5%
        (28.0, 29.9): (2.0, 3.0),    # Contender: 2-3%
        (0.0, 27.9): (0.0, 0.0)      # Laggard: EXIT
    }

    # 80/20 allocation targets
    TARGET_QUALITY_PCT = 80.0
    TARGET_THEMATIC_PCT = 20.0
    TARGET_CASH_PCT = 5.0

    # Tolerance bands
    QUALITY_MIN = 75.0
    QUALITY_MAX = 85.0
    THEMATIC_MIN = 15.0
    THEMATIC_MAX = 25.0
    CASH_MIN = 3.0

    # Position limits
    MAX_SINGLE_POSITION = 20.0  # 20% max for any position
    MAX_THEMATIC_POSITION = 7.0  # 7% max for thematic positions

    def __init__(self):
        """Initialize Portfolio Constructor"""
        logger.info("PortfolioConstructor initialized")

    def calculate_quality_position_size(self, quality_score: float) -> Tuple[float, float]:
        """
        Calculate position size range for quality holding based on score.

        Scoring rules:
        - Score 9-10: (10%, 20%) - Elite quality
        - Score 8-8.9: (7%, 12%) - Strong quality
        - Score 7-7.9: (5%, 8%) - Moderate quality
        - Score <7: (0%, 0%) - EXIT (fails quality threshold)

        Args:
            quality_score: Quality score from 0-10

        Returns:
            Tuple of (min_pct, max_pct) for position sizing
        """
        for (score_min, score_max), (min_pct, max_pct) in self.QUALITY_POSITION_SIZING.items():
            if score_min <= quality_score <= score_max:
                return (min_pct, max_pct)

        # Default to EXIT if score not in range
        return (0.0, 0.0)

    def calculate_thematic_position_size(self, thematic_score: float) -> Tuple[float, float]:
        """
        Calculate position size range for thematic holding based on score.

        Scoring rules:
        - Score 35-40: (5%, 7%) - Leader
        - Score 30-34: (3%, 5%) - Strong Contender
        - Score 28-29: (2%, 3%) - Contender
        - Score <28: (0%, 0%) - EXIT (fails thematic threshold)

        Args:
            thematic_score: Thematic score from 0-40

        Returns:
            Tuple of (min_pct, max_pct) for position sizing
        """
        for (score_min, score_max), (min_pct, max_pct) in self.THEMATIC_POSITION_SIZING.items():
            if score_min <= thematic_score <= score_max:
                return (min_pct, max_pct)

        # Default to EXIT if score not in range
        return (0.0, 0.0)

    def calculate_target_allocation(
        self,
        quality_holdings: Dict[str, float],  # ticker → quality_score
        thematic_holdings: Dict[str, float],  # ticker → thematic_score
        total_portfolio_value: float
    ) -> PortfolioAllocation:
        """
        Calculate target % allocation for each ticker based on scores.

        Algorithm:
        1. Separate quality (score ≥7) from thematic (score ≥28)
        2. Calculate raw position sizes based on score ranges
        3. Normalize quality holdings to 80% total
        4. Normalize thematic holdings to 20% total
        5. Reserve 5% for cash
        6. Detect any constraint violations

        Args:
            quality_holdings: Dict of ticker → quality_score
            thematic_holdings: Dict of ticker → thematic_score
            total_portfolio_value: Total portfolio value in dollars

        Returns:
            PortfolioAllocation with target percentages and violations
        """
        logger.info(f"Calculating target allocation for {len(quality_holdings)} quality + {len(thematic_holdings)} thematic holdings")

        # Calculate raw position sizes
        quality_raw = {}
        for ticker, score in quality_holdings.items():
            min_pct, max_pct = self.calculate_quality_position_size(score)
            if max_pct > 0:  # Only include if not EXIT
                # Use midpoint of range
                target_pct = (min_pct + max_pct) / 2.0
                quality_raw[ticker] = target_pct

        thematic_raw = {}
        for ticker, score in thematic_holdings.items():
            min_pct, max_pct = self.calculate_thematic_position_size(score)
            if max_pct > 0:  # Only include if not EXIT
                # Use midpoint of range
                target_pct = (min_pct + max_pct) / 2.0
                thematic_raw[ticker] = target_pct

        # Calculate raw totals
        raw_quality_total = sum(quality_raw.values())
        raw_thematic_total = sum(thematic_raw.values())

        # Normalize to targets (80% quality, 20% thematic)
        quality_normalized = {}
        if raw_quality_total > 0:
            for ticker, pct in quality_raw.items():
                quality_normalized[ticker] = (pct / raw_quality_total) * self.TARGET_QUALITY_PCT

        thematic_normalized = {}
        if raw_thematic_total > 0:
            for ticker, pct in thematic_raw.items():
                thematic_normalized[ticker] = (pct / raw_thematic_total) * self.TARGET_THEMATIC_PCT

        # Calculate totals
        total_quality_pct = sum(quality_normalized.values())
        total_thematic_pct = sum(thematic_normalized.values())

        # Calculate cash reserve
        # If no holdings passed threshold, all cash
        if total_quality_pct == 0 and total_thematic_pct == 0:
            cash_reserve = 100.0
        else:
            # Cash fills the gap to 100%
            cash_reserve = max(self.TARGET_CASH_PCT, 100.0 - total_quality_pct - total_thematic_pct)

        # Create PortfolioAllocation
        allocation = PortfolioAllocation(
            quality_holdings=quality_normalized,
            thematic_holdings=thematic_normalized,
            cash_reserve=cash_reserve,
            total_quality_pct=total_quality_pct,
            total_thematic_pct=total_thematic_pct,
            violations=[]
        )

        # Validate and detect violations
        violations = self.validate_allocation(allocation)
        allocation.violations = violations

        logger.info(f"Target allocation: Quality {total_quality_pct:.1f}%, Thematic {total_thematic_pct:.1f}%, Cash {cash_reserve:.1f}%")
        if violations:
            logger.warning(f"Allocation violations detected: {len(violations)}")

        return allocation

    def analyze_current_allocation(
        self,
        portfolio_state: Dict,  # from portfolio_state.json
        quality_scores: Dict[str, float],
        thematic_scores: Dict[str, float],
        current_prices: Dict[str, float]
    ) -> AllocationReport:
        """
        Analyze current portfolio allocation vs 80/20 framework.

        Calculates:
        - % in quality holdings (should be ~80%)
        - % in thematic holdings (should be ~20%)
        - % in cash (should be ≥5%)

        Identifies violations:
        - Quality <75% or >85%
        - Thematic <15% or >25%
        - Cash <3%
        - Individual positions >20% (concentration risk)
        - Thematic positions >7%

        Args:
            portfolio_state: Portfolio state dict with holdings and cash
            quality_scores: Dict of ticker → quality_score
            thematic_scores: Dict of ticker → thematic_score
            current_prices: Dict of ticker → current_price

        Returns:
            AllocationReport with current allocation and violations
        """
        logger.info("Analyzing current portfolio allocation")

        holdings = portfolio_state.get('holdings', {})
        cash = portfolio_state.get('cash', 0.0)

        # Calculate total portfolio value
        total_value = cash
        for ticker, holding_data in holdings.items():
            shares = holding_data.get('shares', holding_data) if isinstance(holding_data, dict) else holding_data
            price = current_prices.get(ticker, 100.0)
            total_value += shares * price

        # Handle empty portfolio
        if total_value == 0:
            return AllocationReport(
                current_quality_pct=0.0,
                current_thematic_pct=0.0,
                current_cash_pct=0.0,
                violations=[],
                rebalancing_needed=False,
                quality_holdings={},
                thematic_holdings={}
            )

        # Classify holdings as quality or thematic
        quality_holdings_pct = {}
        thematic_holdings_pct = {}

        for ticker, holding_data in holdings.items():
            shares = holding_data.get('shares', holding_data) if isinstance(holding_data, dict) else holding_data
            price = current_prices.get(ticker, 100.0)
            position_value = shares * price
            position_pct = (position_value / total_value) * 100.0

            # Determine if quality or thematic based on scores
            if ticker in quality_scores and quality_scores[ticker] >= 7.0:
                quality_holdings_pct[ticker] = position_pct
            elif ticker in thematic_scores and thematic_scores[ticker] >= 28.0:
                thematic_holdings_pct[ticker] = position_pct
            else:
                # Below threshold - should be exited
                pass

        # Calculate percentages
        current_quality_pct = sum(quality_holdings_pct.values())
        current_thematic_pct = sum(thematic_holdings_pct.values())
        current_cash_pct = (cash / total_value) * 100.0

        # Detect violations
        violations = []

        if current_quality_pct < self.QUALITY_MIN:
            violations.append(f"Quality allocation {current_quality_pct:.1f}% below {self.QUALITY_MIN:.0f}%")
        elif current_quality_pct > self.QUALITY_MAX:
            violations.append(f"Quality allocation {current_quality_pct:.1f}% above {self.QUALITY_MAX:.0f}%")

        if current_thematic_pct < self.THEMATIC_MIN:
            violations.append(f"Thematic allocation {current_thematic_pct:.1f}% below {self.THEMATIC_MIN:.0f}%")
        elif current_thematic_pct > self.THEMATIC_MAX:
            violations.append(f"Thematic allocation {current_thematic_pct:.1f}% above {self.THEMATIC_MAX:.0f}%")

        if current_cash_pct < self.CASH_MIN:
            violations.append(f"Cash reserve {current_cash_pct:.1f}% below {self.CASH_MIN:.0f}%")

        # Check individual position limits
        all_positions = {**quality_holdings_pct, **thematic_holdings_pct}
        for ticker, pct in all_positions.items():
            if pct > self.MAX_SINGLE_POSITION:
                violations.append(f"{ticker} position {pct:.1f}% exceeds {self.MAX_SINGLE_POSITION:.0f}%")

        for ticker, pct in thematic_holdings_pct.items():
            if pct > self.MAX_THEMATIC_POSITION:
                violations.append(f"{ticker} thematic position {pct:.1f}% exceeds {self.MAX_THEMATIC_POSITION:.0f}%")

        # Determine if rebalancing needed
        rebalancing_needed = len(violations) > 0

        report = AllocationReport(
            current_quality_pct=current_quality_pct,
            current_thematic_pct=current_thematic_pct,
            current_cash_pct=current_cash_pct,
            violations=violations,
            rebalancing_needed=rebalancing_needed,
            quality_holdings=quality_holdings_pct,
            thematic_holdings=thematic_holdings_pct
        )

        logger.info(f"Current allocation: Quality {current_quality_pct:.1f}%, Thematic {current_thematic_pct:.1f}%, Cash {current_cash_pct:.1f}%")
        if rebalancing_needed:
            logger.warning(f"Rebalancing needed - {len(violations)} violations detected")

        return report

    def generate_rebalancing_trades(
        self,
        current_allocation: AllocationReport,
        target_allocation: PortfolioAllocation,
        portfolio_state: Dict,
        current_prices: Dict[str, float]
    ) -> List[Dict]:
        """
        Generate exact trades needed to rebalance portfolio.

        Logic:
        1. Identify exits (quality <7, thematic <28)
        2. Identify position size adjustments (over/under allocated)
        3. Calculate exact share quantities
        4. Prioritize: sells first (generate cash), then buys
        5. Respect minimum trade size ($50)

        Args:
            current_allocation: Current allocation analysis
            target_allocation: Target allocation
            portfolio_state: Current portfolio state
            current_prices: Dict of ticker → current_price

        Returns:
            List of trade dicts with action, ticker, shares, reason, priority
        """
        logger.info("Generating rebalancing trades")

        holdings = portfolio_state.get('holdings', {})
        cash = portfolio_state.get('cash', 0.0)

        # Calculate total portfolio value
        total_value = cash
        for ticker, holding_data in holdings.items():
            shares = holding_data.get('shares', holding_data) if isinstance(holding_data, dict) else holding_data
            price = current_prices.get(ticker, 100.0)
            total_value += shares * price

        trades = []

        # Step 1: Identify exits (holdings not in target)
        all_target_tickers = set(target_allocation.quality_holdings.keys()) | set(target_allocation.thematic_holdings.keys())
        for ticker, holding_data in holdings.items():
            shares = holding_data.get('shares', holding_data) if isinstance(holding_data, dict) else holding_data
            if ticker not in all_target_tickers:
                # Position should be exited
                trades.append({
                    'action': 'SELL',
                    'ticker': ticker,
                    'shares': int(shares),
                    'reasoning': f'Exit position - fails quality/thematic threshold',
                    'priority': 'HIGH'
                })

        # Step 2: Calculate position adjustments
        all_target_positions = {**target_allocation.quality_holdings, **target_allocation.thematic_holdings}

        for ticker, target_pct in all_target_positions.items():
            target_value = (target_pct / 100.0) * total_value
            price = current_prices.get(ticker, 100.0)
            target_shares = int(target_value / price)

            holding_data = holdings.get(ticker, 0)
            current_shares = holding_data.get('shares', holding_data) if isinstance(holding_data, dict) else holding_data
            current_shares = int(current_shares) if current_shares else 0
            share_diff = target_shares - current_shares

            if abs(share_diff * price) >= 50.0:  # Minimum trade size $50
                if share_diff > 0:
                    # Need to buy
                    trades.append({
                        'action': 'BUY',
                        'ticker': ticker,
                        'shares': share_diff,
                        'reasoning': f'Scale to {target_pct:.1f}% target allocation',
                        'priority': 'MEDIUM'
                    })
                elif share_diff < 0:
                    # Need to sell
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
        holdings: Dict[str, str],  # ticker → type (QUALITY or THEMATIC)
        quality_scores: Dict[str, float]
    ) -> Dict[str, RiskParameters]:
        """
        Calculate stop-loss and profit targets for each holding.

        Rules:
        Quality holdings:
        - Score >8: -15% stop, +30-50% profit target
        - Score 7-8: -20% stop, +30-50% profit target

        Thematic holdings:
        - All: -25% to -30% stop, +40-60% profit target

        Args:
            holdings: Dict of ticker → position_type (QUALITY or THEMATIC)
            quality_scores: Dict of ticker → quality_score

        Returns:
            Dict of ticker → RiskParameters
        """
        logger.info(f"Calculating risk parameters for {len(holdings)} holdings")

        risk_params = {}

        for ticker, position_type in holdings.items():
            if position_type == 'QUALITY':
                quality_score = quality_scores.get(ticker, 0.0)

                if quality_score > 8.0:
                    stop_loss = -15.0
                    profit_target = 40.0  # Midpoint of 30-50%
                else:  # 7-8
                    stop_loss = -20.0
                    profit_target = 40.0  # Midpoint of 30-50%

            else:  # THEMATIC
                stop_loss = -27.5  # Midpoint of -25 to -30%
                profit_target = 50.0  # Midpoint of 40-60%

            risk_params[ticker] = RiskParameters(
                ticker=ticker,
                stop_loss_pct=stop_loss,
                profit_target_pct=profit_target,
                position_type=position_type
            )

        logger.info(f"Calculated risk parameters for {len(risk_params)} holdings")
        return risk_params

    def validate_allocation(self, allocation: PortfolioAllocation) -> List[str]:
        """
        Check for constraint violations in allocation.

        Checks:
        - 80/20 framework (75-85% quality, 15-25% thematic)
        - Individual position limits (20% max)
        - Thematic position limits (7% max)
        - Cash reserve (≥3%)

        Args:
            allocation: PortfolioAllocation to validate

        Returns:
            List of violation messages (empty if valid)
        """
        violations = []

        # Check 80/20 framework (allow 5% tolerance)
        if allocation.total_quality_pct < self.QUALITY_MIN:
            violations.append(
                f"Quality allocation {allocation.total_quality_pct:.1f}% below {self.QUALITY_MIN:.0f}%"
            )
        elif allocation.total_quality_pct > self.QUALITY_MAX:
            violations.append(
                f"Quality allocation {allocation.total_quality_pct:.1f}% above {self.QUALITY_MAX:.0f}%"
            )

        if allocation.total_thematic_pct < self.THEMATIC_MIN:
            violations.append(
                f"Thematic allocation {allocation.total_thematic_pct:.1f}% below {self.THEMATIC_MIN:.0f}%"
            )
        elif allocation.total_thematic_pct > self.THEMATIC_MAX:
            violations.append(
                f"Thematic allocation {allocation.total_thematic_pct:.1f}% above {self.THEMATIC_MAX:.0f}%"
            )

        # Check cash reserve
        if allocation.cash_reserve < self.CASH_MIN:
            violations.append(
                f"Cash reserve {allocation.cash_reserve:.1f}% below {self.CASH_MIN:.0f}%"
            )

        # Check individual position limits
        all_positions = {**allocation.quality_holdings, **allocation.thematic_holdings}
        for ticker, pct in all_positions.items():
            if pct > self.MAX_SINGLE_POSITION:
                violations.append(
                    f"{ticker} position {pct:.1f}% exceeds {self.MAX_SINGLE_POSITION:.0f}%"
                )

        # Check thematic position limits
        for ticker, pct in allocation.thematic_holdings.items():
            if pct > self.MAX_THEMATIC_POSITION:
                violations.append(
                    f"{ticker} thematic position {pct:.1f}% exceeds {self.MAX_THEMATIC_POSITION:.0f}%"
                )

        return violations

    # ==================== EXPORT METHODS ====================

    def export_allocation_report(self, allocation: PortfolioAllocation, filename: Optional[str] = None) -> str:
        """
        Export allocation to JSON file.

        Args:
            allocation: PortfolioAllocation to export
            filename: Output filename (auto-generated if not provided)

        Returns:
            Path to exported file
        """
        if filename is None:
            filename = f"outputs/portfolio_allocation_{datetime.now().strftime('%Y%m%d')}.json"

        try:
            output_path = Path(filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(asdict(allocation), f, indent=2)

            logger.info(f"Exported allocation report to {filename}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to export allocation report: {e}")
            return ""

    def export_rebalancing_trades(self, trades: List[Dict], filename: Optional[str] = None) -> str:
        """
        Export rebalancing trades to JSON file.

        Args:
            trades: List of trade dicts
            filename: Output filename (auto-generated if not provided)

        Returns:
            Path to exported file
        """
        if filename is None:
            filename = f"outputs/rebalancing_trades_{datetime.now().strftime('%Y%m%d')}.json"

        try:
            output_path = Path(filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump({'trades': trades}, f, indent=2)

            logger.info(f"Exported {len(trades)} rebalancing trades to {filename}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to export rebalancing trades: {e}")
            return ""

    def generate_allocation_summary(self, allocation: PortfolioAllocation, total_portfolio_value: Optional[float] = None) -> str:
        """
        Generate markdown summary of allocation.

        Args:
            allocation: PortfolioAllocation to summarize
            total_portfolio_value: Optional total portfolio value in dollars

        Returns:
            Markdown formatted summary string
        """
        lines = []
        lines.append("# Portfolio Allocation Summary\n")
        lines.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}")
        if total_portfolio_value is not None:
            lines.append(f"**Portfolio Value**: ${total_portfolio_value:,.2f}\n")
        else:
            lines.append("")
        lines.append(f"**Total Quality**: {allocation.total_quality_pct:.1f}%")
        lines.append(f"**Total Thematic**: {allocation.total_thematic_pct:.1f}%")
        lines.append(f"**Cash Reserve**: {allocation.cash_reserve:.1f}%\n")

        lines.append("## Quality Holdings (80% Target)\n")
        for ticker, pct in sorted(allocation.quality_holdings.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{ticker}**: {pct:.1f}%")

        lines.append("\n## Thematic Holdings (20% Target)\n")
        for ticker, pct in sorted(allocation.thematic_holdings.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{ticker}**: {pct:.1f}%")

        if allocation.violations:
            lines.append("\n## ⚠️ Violations\n")
            for violation in allocation.violations:
                lines.append(f"- {violation}")
        else:
            lines.append("\n## ✅ No Violations\n")
            lines.append("Allocation complies with all 80/20 framework constraints.")

        return "\n".join(lines)


def main():
    """CLI interface for testing"""
    import argparse

    parser = argparse.ArgumentParser(description="Portfolio Constructor (80/20 Framework)")
    parser.add_argument('--test', action='store_true', help='Run test example')
    args = parser.parse_args()

    if args.test:
        constructor = PortfolioConstructor()

        # Test quality position sizing
        print("\n" + "=" * 60)
        print("QUALITY POSITION SIZING TEST")
        print("=" * 60)
        for score in [9.5, 8.5, 7.5, 6.5]:
            min_pct, max_pct = constructor.calculate_quality_position_size(score)
            print(f"Score {score:.1f}: {min_pct:.1f}% - {max_pct:.1f}%")

        # Test thematic position sizing
        print("\n" + "=" * 60)
        print("THEMATIC POSITION SIZING TEST")
        print("=" * 60)
        for score in [37.0, 32.0, 28.5, 25.0]:
            min_pct, max_pct = constructor.calculate_thematic_position_size(score)
            print(f"Score {score:.1f}: {min_pct:.1f}% - {max_pct:.1f}%")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
