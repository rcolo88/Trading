"""
Catalyst Analyzer - Event-Driven Trading Analysis

This module identifies and prioritizes upcoming catalysts (events) that could drive
stock performance. Focuses on helping time entries/exits around specific events
rather than passive buy-and-hold strategies.

Catalysts include:
- Earnings reports and guidance updates
- FDA approvals and clinical trial results
- Product launches and technology milestones
- Contract awards and partnership announcements
- Regulatory decisions and policy changes
- Spin-offs, mergers, and corporate actions

Usage:
    analyzer = CatalystAnalyzer()
    prompt = analyzer.generate_catalyst_prompt(company_data)
    # Send to LLM, get response
    catalysts = analyzer.parse_catalyst_response(llm_response, company_data)
    prioritized = analyzer.prioritize_catalysts(catalysts)
    report = analyzer.generate_catalyst_summary_report(prioritized)

Author: Portfolio Management System
Version: 1.0.0
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import re
import json


class CatalystTimeline(Enum):
    """Catalyst timeline classifications."""
    NEAR_TERM = "0-6 months"      # 0-6 months
    MEDIUM_TERM = "6-18 months"   # 6-18 months
    LONG_TERM = "18+ months"      # 18+ months


class CatalystProbability(Enum):
    """Catalyst probability of occurrence."""
    HIGH = "H"      # >70% likely
    MEDIUM = "M"    # 30-70% likely
    LOW = "L"       # <30% likely


class CatalystImpact(Enum):
    """Expected impact on stock price."""
    HIGH = "H"      # >10% price move
    MEDIUM = "M"    # 3-10% price move
    LOW = "L"       # <3% price move


class CatalystDirection(Enum):
    """Direction of expected impact."""
    POSITIVE = "+"      # Bullish catalyst
    NEGATIVE = "-"      # Bearish catalyst
    NEUTRAL = "neutral" # Uncertain direction


@dataclass
class Catalyst:
    """
    Represents a single catalyst event.

    Attributes:
        name: Catalyst description (e.g., "Q3 Earnings Report")
        timeline: Time until catalyst (near/medium/long term)
        timeline_months: Estimated months until event
        probability: Likelihood of occurrence (H/M/L)
        impact: Expected price impact magnitude (H/M/L)
        direction: Expected price direction (+/-/neutral)
        dependencies: Other events this depends on
        notes: Additional context and details
        priority_score: Calculated priority score (higher = more important)
        estimated_date: Best guess date for the event
    """
    name: str
    timeline: CatalystTimeline
    timeline_months: float
    probability: CatalystProbability
    impact: CatalystImpact
    direction: CatalystDirection
    dependencies: List[str] = field(default_factory=list)
    notes: str = ""
    priority_score: float = 0.0
    estimated_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'timeline': self.timeline.value,
            'timeline_months': self.timeline_months,
            'probability': self.probability.value,
            'impact': self.impact.value,
            'direction': self.direction.value,
            'dependencies': self.dependencies,
            'notes': self.notes,
            'priority_score': self.priority_score,
            'estimated_date': self.estimated_date.isoformat() if self.estimated_date else None
        }


@dataclass
class CatalystAnalysis:
    """
    Complete catalyst analysis for a company.

    Attributes:
        ticker: Stock ticker symbol
        company_name: Company name
        analysis_date: When analysis was performed
        catalysts: List of all identified catalysts
        top_5_catalysts: Top 5 prioritized catalysts
        near_term_count: Number of near-term catalysts
        medium_term_count: Number of medium-term catalysts
        long_term_count: Number of long-term catalysts
        high_impact_count: Number of high-impact catalysts
        summary: Executive summary text
    """
    ticker: str
    company_name: str
    analysis_date: datetime
    catalysts: List[Catalyst]
    top_5_catalysts: List[Catalyst] = field(default_factory=list)
    near_term_count: int = 0
    medium_term_count: int = 0
    long_term_count: int = 0
    high_impact_count: int = 0
    summary: str = ""


class CatalystAnalyzer:
    """
    Identifies and prioritizes upcoming catalysts for event-driven trading.

    Designed to help time entries and exits around specific events rather than
    passive buy-and-hold strategies. Generates prompts for LLMs to identify
    catalysts, parses responses, prioritizes by scoring formula, and generates
    monitoring schedules.

    Attributes:
        scoring_weights: Configurable weights for prioritization formula
    """

    # Default scoring weights
    DEFAULT_WEIGHTS = {
        'time': 2.0,      # Weight for time proximity
        'probability': 3.0,  # Weight for probability
        'impact': 5.0,    # Weight for expected impact
        'direction_bonus': 2.0  # Bonus for positive catalysts
    }

    # Probability scores
    PROBABILITY_SCORES = {
        CatalystProbability.HIGH: 3.0,
        CatalystProbability.MEDIUM: 2.0,
        CatalystProbability.LOW: 1.0
    }

    # Impact scores
    IMPACT_SCORES = {
        CatalystImpact.HIGH: 3.0,
        CatalystImpact.MEDIUM: 2.0,
        CatalystImpact.LOW: 1.0
    }

    def __init__(self, scoring_weights: Optional[Dict[str, float]] = None):
        """
        Initialize catalyst analyzer.

        Args:
            scoring_weights: Custom weights for prioritization formula.
                           If None, uses DEFAULT_WEIGHTS.
        """
        self.scoring_weights = scoring_weights or self.DEFAULT_WEIGHTS.copy()

    def generate_catalyst_prompt(
        self,
        company_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate prompt asking LLM to identify upcoming catalysts.

        Creates structured prompt requesting catalyst calendar across three
        time horizons with detailed attributes for each event.

        Args:
            company_data: Company information (ticker, name, sector, etc.)
            context: Optional additional context (recent news, filings, etc.)

        Returns:
            Formatted prompt string for LLM
        """
        ticker = company_data.get('ticker', 'UNKNOWN')
        company_name = company_data.get('name', ticker)
        sector = company_data.get('sector', 'N/A')

        prompt_parts = []

        # Role definition
        prompt_parts.append(
            "You are a catalyst research analyst specializing in event-driven "
            "trading strategies. Your task is to identify specific upcoming events "
            "(catalysts) that could drive stock price movement."
        )

        # Company context
        prompt_parts.append(f"\n## Company: {company_name} ({ticker})")
        prompt_parts.append(f"Sector: {sector}")

        if 'business_description' in company_data:
            desc = company_data['business_description'][:200]
            prompt_parts.append(f"Business: {desc}")

        if context:
            if 'recent_news' in context:
                prompt_parts.append(f"\nRecent News: {context['recent_news'][:150]}")
            if 'upcoming_events' in context:
                prompt_parts.append(f"Known Events: {context['upcoming_events']}")

        # Instructions
        prompt_parts.append(
            "\n## Create a Catalyst Calendar\n"
            "\nIdentify the TOP 5 most important upcoming catalysts across three time horizons:\n"
            "\n**Near-Term (0-6 months):** Events within next 6 months"
            "\n**Medium-Term (6-18 months):** Events 6-18 months out"
            "\n**Long-Term (18+ months):** Events beyond 18 months\n"
            "\nFor EACH catalyst, provide:\n"
            "1. **Name**: Brief description of the event"
            "\n2. **Timeline**: Estimated months until event (e.g., '2 months', '12 months')"
            "\n3. **Probability**: H (High >70%), M (Medium 30-70%), L (Low <30%)"
            "\n4. **Impact**: H (>10% price move), M (3-10%), L (<3%)"
            "\n5. **Direction**: + (positive/bullish), - (negative/bearish), neutral"
            "\n6. **Dependencies**: What must happen first for this catalyst"
            "\n7. **Notes**: Additional context (1-2 sentences)\n"
        )

        # Output format
        prompt_parts.append(
            "\n## Output Format:\n"
            "\nCATALYST 1: [Name]"
            "\nTimeline: [X months]"
            "\nProbability: [H/M/L]"
            "\nImpact: [H/M/L]"
            "\nDirection: [+/-/neutral]"
            "\nDependencies: [List or 'None']"
            "\nNotes: [Brief explanation]\n"
            "\nCATALYST 2: [Name]"
            "\n..."
            "\n\nRepeat for all 5 catalysts, prioritized by importance."
        )

        # Examples
        prompt_parts.append(
            "\n\nExample catalysts:"
            "\n- Q3 2025 Earnings Report (timeline: 3 months, probability: H, impact: M)"
            "\n- FDA Approval Decision for Drug X (timeline: 8 months, probability: M, impact: H)"
            "\n- Product Launch in China (timeline: 14 months, probability: L, impact: M)"
            "\n- Patent Expiration (timeline: 24 months, probability: H, impact: H)"
            "\n- CEO Transition Completion (timeline: 6 months, probability: H, impact: L)"
        )

        return "\n".join(prompt_parts)

    def parse_catalyst_response(
        self,
        llm_response: str,
        company_data: Dict[str, Any]
    ) -> List[Catalyst]:
        """
        Extract structured catalyst data from LLM response.

        Handles various response formats with robust parsing. Extracts all
        catalyst attributes and converts to Catalyst objects.

        Args:
            llm_response: Raw text response from LLM
            company_data: Company data for context

        Returns:
            List of parsed Catalyst objects
        """
        catalysts = []

        # Split into catalyst blocks
        # Try multiple patterns to handle format variations
        patterns = [
            r'CATALYST\s+\d+:(.+?)(?=CATALYST\s+\d+:|$)',  # "CATALYST 1:"
            r'^\d+\.(.+?)(?=^\d+\.|$)',                     # "1."
            r'##\s*(.+?)(?=##|$)'                           # "##"
        ]

        blocks = []
        for pattern in patterns:
            blocks = re.findall(pattern, llm_response, re.MULTILINE | re.DOTALL | re.IGNORECASE)
            if blocks:
                break

        if not blocks:
            # Fallback: split by double newlines
            blocks = llm_response.split('\n\n')

        for block in blocks:
            catalyst = self._parse_single_catalyst(block, company_data)
            if catalyst:
                catalysts.append(catalyst)

        return catalysts

    def _parse_single_catalyst(
        self,
        text: str,
        company_data: Dict[str, Any]
    ) -> Optional[Catalyst]:
        """
        Parse a single catalyst from text block.

        Args:
            text: Text block containing catalyst information
            company_data: Company data for context

        Returns:
            Parsed Catalyst object or None if parsing fails
        """
        # Extract name (first line or after colon)
        name_match = re.search(r'(?:CATALYST\s+\d+:\s*|^\d+\.\s*)?(.+?)(?:\n|$)', text, re.IGNORECASE)
        if not name_match:
            return None

        name = name_match.group(1).strip()
        if len(name) < 3:  # Too short to be valid
            return None

        # Extract timeline
        timeline_match = re.search(r'Timeline:\s*(\d+(?:\.\d+)?)\s*months?', text, re.IGNORECASE)
        if not timeline_match:
            timeline_match = re.search(r'(\d+(?:\.\d+)?)\s*months?', text)

        if timeline_match:
            timeline_months = float(timeline_match.group(1))
        else:
            timeline_months = 6.0  # Default

        # Classify timeline
        if timeline_months <= 6:
            timeline = CatalystTimeline.NEAR_TERM
        elif timeline_months <= 18:
            timeline = CatalystTimeline.MEDIUM_TERM
        else:
            timeline = CatalystTimeline.LONG_TERM

        # Extract probability
        prob_match = re.search(r'Probability:\s*([HML])', text, re.IGNORECASE)
        if prob_match:
            prob_str = prob_match.group(1).upper()
            probability = {
                'H': CatalystProbability.HIGH,
                'M': CatalystProbability.MEDIUM,
                'L': CatalystProbability.LOW
            }.get(prob_str, CatalystProbability.MEDIUM)
        else:
            probability = CatalystProbability.MEDIUM

        # Extract impact
        impact_match = re.search(r'Impact:\s*([HML])', text, re.IGNORECASE)
        if impact_match:
            impact_str = impact_match.group(1).upper()
            impact = {
                'H': CatalystImpact.HIGH,
                'M': CatalystImpact.MEDIUM,
                'L': CatalystImpact.LOW
            }.get(impact_str, CatalystImpact.MEDIUM)
        else:
            impact = CatalystImpact.MEDIUM

        # Extract direction
        dir_match = re.search(r'Direction:\s*([+\-]|neutral)', text, re.IGNORECASE)
        if dir_match:
            dir_str = dir_match.group(1).lower()
            if dir_str == '+' or 'posit' in dir_str:
                direction = CatalystDirection.POSITIVE
            elif dir_str == '-' or 'negat' in dir_str:
                direction = CatalystDirection.NEGATIVE
            else:
                direction = CatalystDirection.NEUTRAL
        else:
            direction = CatalystDirection.NEUTRAL

        # Extract dependencies
        dep_match = re.search(r'Dependencies:\s*(.+?)(?:\n(?:[A-Z][a-z]+:|$)|$)', text, re.IGNORECASE)
        if dep_match:
            dep_str = dep_match.group(1).strip()
            if 'none' in dep_str.lower():
                dependencies = []
            else:
                # Split by commas or semicolons
                dependencies = [d.strip() for d in re.split(r'[,;]', dep_str) if d.strip()]
        else:
            dependencies = []

        # Extract notes
        notes_match = re.search(r'Notes:\s*(.+?)(?:\n(?:[A-Z][a-z]+:|$)|$)', text, re.IGNORECASE | re.DOTALL)
        if notes_match:
            notes = notes_match.group(1).strip()
            # Truncate if too long
            if len(notes) > 300:
                notes = notes[:297] + "..."
        else:
            notes = ""

        # Calculate estimated date
        estimated_date = datetime.now() + timedelta(days=timeline_months * 30)

        return Catalyst(
            name=name,
            timeline=timeline,
            timeline_months=timeline_months,
            probability=probability,
            impact=impact,
            direction=direction,
            dependencies=dependencies,
            notes=notes,
            estimated_date=estimated_date
        )

    def prioritize_catalysts(
        self,
        catalysts: List[Catalyst],
        custom_weights: Optional[Dict[str, float]] = None
    ) -> List[Catalyst]:
        """
        Score and prioritize catalysts by importance.

        Formula: time_weight/(timeline_months) + prob_weight*prob_score +
                 impact_weight*impact_score + direction_bonus

        Args:
            catalysts: List of catalysts to prioritize
            custom_weights: Optional custom weights for scoring

        Returns:
            List of catalysts sorted by priority score (descending)
        """
        weights = custom_weights or self.scoring_weights

        for catalyst in catalysts:
            # Time component (sooner = higher priority)
            # Avoid division by zero, use max(0.5, timeline_months)
            time_score = weights['time'] / max(0.5, catalyst.timeline_months)

            # Probability component
            prob_score = self.PROBABILITY_SCORES[catalyst.probability] * weights['probability']

            # Impact component
            impact_score = self.IMPACT_SCORES[catalyst.impact] * weights['impact']

            # Direction bonus (positive catalysts get bonus)
            if catalyst.direction == CatalystDirection.POSITIVE:
                dir_bonus = weights['direction_bonus']
            elif catalyst.direction == CatalystDirection.NEGATIVE:
                dir_bonus = -weights['direction_bonus'] * 0.5  # Penalty for negative
            else:
                dir_bonus = 0.0

            # Total score
            catalyst.priority_score = time_score + prob_score + impact_score + dir_bonus

        # Sort by priority score descending
        return sorted(catalysts, key=lambda c: c.priority_score, reverse=True)

    def create_monitoring_schedule(
        self,
        catalysts: List[Catalyst],
        check_in_days: int = 30
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate calendar with key dates and check-in reminders.

        Creates monitoring schedule with catalyst dates and regular check-ins
        to reassess catalyst status.

        Args:
            catalysts: List of catalysts to monitor
            check_in_days: Days between check-in reminders (default 30)

        Returns:
            Dict with 'catalyst_dates' and 'check_ins' lists
        """
        schedule = {
            'catalyst_dates': [],
            'check_ins': []
        }

        # Add catalyst dates
        for catalyst in catalysts:
            if catalyst.estimated_date:
                schedule['catalyst_dates'].append({
                    'date': catalyst.estimated_date,
                    'catalyst_name': catalyst.name,
                    'priority_score': catalyst.priority_score,
                    'impact': catalyst.impact.value,
                    'probability': catalyst.probability.value,
                    'type': 'catalyst'
                })

        # Generate check-in reminders
        today = datetime.now()
        earliest_catalyst = min(
            (c.estimated_date for c in catalysts if c.estimated_date),
            default=today + timedelta(days=180)
        )

        # Create check-ins from now until earliest catalyst
        current_date = today + timedelta(days=check_in_days)
        while current_date < earliest_catalyst:
            schedule['check_ins'].append({
                'date': current_date,
                'catalyst_name': 'Portfolio Catalyst Review',
                'priority_score': 5.0,  # Medium priority
                'impact': 'M',
                'probability': 'H',
                'type': 'check_in'
            })
            current_date += timedelta(days=check_in_days)

        # Sort all events by date
        schedule['catalyst_dates'].sort(key=lambda x: x['date'])
        schedule['check_ins'].sort(key=lambda x: x['date'])

        return schedule

    def generate_catalyst_summary_report(
        self,
        analysis: CatalystAnalysis,
        include_schedule: bool = True
    ) -> str:
        """
        Generate comprehensive markdown report on catalysts.

        Creates formatted report with executive summary, top catalysts,
        detailed calendar tables, and monitoring recommendations.

        Args:
            analysis: Complete catalyst analysis for a company
            include_schedule: Whether to include monitoring schedule

        Returns:
            Markdown-formatted report string
        """
        report_parts = []

        # Header
        report_parts.append(f"# Catalyst Analysis: {analysis.company_name} ({analysis.ticker})")
        report_parts.append(f"\n**Analysis Date:** {analysis.analysis_date.strftime('%Y-%m-%d')}")
        report_parts.append(f"**Total Catalysts Identified:** {len(analysis.catalysts)}")

        # Executive Summary
        report_parts.append("\n## Executive Summary\n")

        if analysis.summary:
            report_parts.append(analysis.summary)
        else:
            # Generate summary
            summary = self._generate_executive_summary(analysis)
            report_parts.append(summary)

        # Top 5 Priority Catalysts
        report_parts.append("\n## Top 5 Priority Catalysts\n")

        for i, catalyst in enumerate(analysis.top_5_catalysts, 1):
            direction_symbol = {
                CatalystDirection.POSITIVE: "📈",
                CatalystDirection.NEGATIVE: "📉",
                CatalystDirection.NEUTRAL: "➡️"
            }[catalyst.direction]

            report_parts.append(
                f"\n### {i}. {catalyst.name} {direction_symbol}"
                f"\n**Timeline:** {catalyst.timeline_months:.1f} months ({catalyst.timeline.value})"
                f"\n**Probability:** {catalyst.probability.value} | **Impact:** {catalyst.impact.value} | **Direction:** {catalyst.direction.value}"
                f"\n**Priority Score:** {catalyst.priority_score:.2f}"
            )

            if catalyst.dependencies:
                report_parts.append(f"\n**Dependencies:** {', '.join(catalyst.dependencies)}")

            if catalyst.notes:
                report_parts.append(f"\n**Notes:** {catalyst.notes}")

            if catalyst.estimated_date:
                report_parts.append(f"\n**Estimated Date:** {catalyst.estimated_date.strftime('%B %Y')}")

        # Catalyst Calendar by Timeline
        report_parts.append("\n## Catalyst Calendar\n")

        # Near-term
        near_term = [c for c in analysis.catalysts if c.timeline == CatalystTimeline.NEAR_TERM]
        if near_term:
            report_parts.append("\n### Near-Term (0-6 months)\n")
            report_parts.append(self._format_catalyst_table(near_term))

        # Medium-term
        medium_term = [c for c in analysis.catalysts if c.timeline == CatalystTimeline.MEDIUM_TERM]
        if medium_term:
            report_parts.append("\n### Medium-Term (6-18 months)\n")
            report_parts.append(self._format_catalyst_table(medium_term))

        # Long-term
        long_term = [c for c in analysis.catalysts if c.timeline == CatalystTimeline.LONG_TERM]
        if long_term:
            report_parts.append("\n### Long-Term (18+ months)\n")
            report_parts.append(self._format_catalyst_table(long_term))

        # Monitoring Schedule
        if include_schedule:
            schedule = self.create_monitoring_schedule(analysis.catalysts)
            report_parts.append("\n## Monitoring Recommendations\n")
            report_parts.append(self._format_monitoring_schedule(schedule))

        # Trading Implications
        report_parts.append("\n## Trading Implications\n")
        report_parts.append(self._generate_trading_implications(analysis))

        return "\n".join(report_parts)

    def _format_catalyst_table(self, catalysts: List[Catalyst]) -> str:
        """Format catalysts as markdown table."""
        if not catalysts:
            return "*No catalysts identified in this timeframe.*\n"

        table = "| Catalyst | Months | Prob | Impact | Dir | Priority |\n"
        table += "|----------|--------|------|--------|-----|----------|\n"

        for catalyst in catalysts:
            dir_symbol = {
                CatalystDirection.POSITIVE: "+",
                CatalystDirection.NEGATIVE: "-",
                CatalystDirection.NEUTRAL: "○"
            }[catalyst.direction]

            table += (
                f"| {catalyst.name[:50]} | "
                f"{catalyst.timeline_months:.1f} | "
                f"{catalyst.probability.value} | "
                f"{catalyst.impact.value} | "
                f"{dir_symbol} | "
                f"{catalyst.priority_score:.1f} |\n"
            )

        return table

    def _format_monitoring_schedule(self, schedule: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format monitoring schedule as markdown."""
        output = []

        # Combine and sort all events
        all_events = schedule['catalyst_dates'] + schedule['check_ins']
        all_events.sort(key=lambda x: x['date'])

        # Take next 10 events
        upcoming = all_events[:10]

        output.append("\n**Next 10 Events to Monitor:**\n")
        output.append("| Date | Event | Type | Priority |")
        output.append("|------|-------|------|----------|")

        for event in upcoming:
            date_str = event['date'].strftime('%Y-%m-%d')
            event_type = event['type'].title()
            priority = f"{event['priority_score']:.1f}"

            output.append(
                f"| {date_str} | {event['catalyst_name'][:40]} | {event_type} | {priority} |"
            )

        output.append(
            "\n**Recommendation:** Set calendar reminders for catalyst dates and monthly portfolio reviews."
        )

        return "\n".join(output)

    def _generate_executive_summary(self, analysis: CatalystAnalysis) -> str:
        """Generate executive summary text."""
        summary_parts = []

        summary_parts.append(
            f"Identified **{len(analysis.catalysts)} catalysts** for {analysis.company_name} "
            f"across three time horizons:"
        )

        summary_parts.append(
            f"- **Near-term (0-6 months):** {analysis.near_term_count} catalysts"
        )
        summary_parts.append(
            f"- **Medium-term (6-18 months):** {analysis.medium_term_count} catalysts"
        )
        summary_parts.append(
            f"- **Long-term (18+ months):** {analysis.long_term_count} catalysts"
        )

        high_impact = sum(1 for c in analysis.catalysts if c.impact == CatalystImpact.HIGH)
        summary_parts.append(f"\n**{high_impact} high-impact catalysts** identified.")

        positive = sum(1 for c in analysis.catalysts if c.direction == CatalystDirection.POSITIVE)
        negative = sum(1 for c in analysis.catalysts if c.direction == CatalystDirection.NEGATIVE)

        if positive > negative:
            summary_parts.append(
                f"\n**Bias: Bullish** ({positive} positive vs {negative} negative catalysts)"
            )
        elif negative > positive:
            summary_parts.append(
                f"\n**Bias: Bearish** ({negative} negative vs {positive} positive catalysts)"
            )
        else:
            summary_parts.append(f"\n**Bias: Neutral** (balanced catalyst mix)")

        return "\n".join(summary_parts)

    def _generate_trading_implications(self, analysis: CatalystAnalysis) -> str:
        """Generate trading implications section."""
        implications = []

        # Look at top catalyst
        if analysis.top_5_catalysts:
            top = analysis.top_5_catalysts[0]

            if top.timeline_months <= 3:
                implications.append(
                    f"**Near-Term Entry Opportunity:** Top catalyst ({top.name}) is only "
                    f"{top.timeline_months:.1f} months away. Consider entry now to position "
                    "ahead of event."
                )

            if top.impact == CatalystImpact.HIGH and top.probability == CatalystProbability.HIGH:
                implications.append(
                    f"**High-Conviction Trade:** {top.name} has high probability and high impact. "
                    "This represents a strong asymmetric opportunity."
                )

        # Check for clustering
        near_term_high_impact = [
            c for c in analysis.catalysts
            if c.timeline == CatalystTimeline.NEAR_TERM and c.impact == CatalystImpact.HIGH
        ]

        if len(near_term_high_impact) >= 2:
            implications.append(
                f"**Catalyst Clustering:** {len(near_term_high_impact)} high-impact catalysts "
                "in next 6 months. Volatility likely to increase."
            )

        # Risk management
        negative_catalysts = [c for c in analysis.catalysts if c.direction == CatalystDirection.NEGATIVE]
        if negative_catalysts:
            implications.append(
                f"**Risk Management:** {len(negative_catalysts)} negative catalysts identified. "
                "Consider stop-losses or protective options."
            )

        if not implications:
            implications.append(
                "Monitor catalyst development closely. Consider position sizing based on "
                "catalyst timeline and impact."
            )

        return "\n".join(f"- {imp}" for imp in implications)

    def batch_analyze_catalysts(
        self,
        companies: List[Dict[str, Any]],
        llm_responses: Optional[Dict[str, str]] = None
    ) -> Dict[str, CatalystAnalysis]:
        """
        Process multiple companies for portfolio-wide catalyst monitoring.

        Args:
            companies: List of company data dicts
            llm_responses: Optional dict mapping ticker to LLM response
                          If None, only generates prompts

        Returns:
            Dict mapping ticker to CatalystAnalysis
        """
        results = {}

        for company_data in companies:
            ticker = company_data.get('ticker')
            if not ticker:
                continue

            # Parse response if provided
            if llm_responses and ticker in llm_responses:
                catalysts = self.parse_catalyst_response(
                    llm_responses[ticker],
                    company_data
                )

                # Prioritize
                prioritized = self.prioritize_catalysts(catalysts)

                # Count by category
                near_term = sum(1 for c in catalysts if c.timeline == CatalystTimeline.NEAR_TERM)
                medium_term = sum(1 for c in catalysts if c.timeline == CatalystTimeline.MEDIUM_TERM)
                long_term = sum(1 for c in catalysts if c.timeline == CatalystTimeline.LONG_TERM)
                high_impact = sum(1 for c in catalysts if c.impact == CatalystImpact.HIGH)

                analysis = CatalystAnalysis(
                    ticker=ticker,
                    company_name=company_data.get('name', ticker),
                    analysis_date=datetime.now(),
                    catalysts=prioritized,
                    top_5_catalysts=prioritized[:5],
                    near_term_count=near_term,
                    medium_term_count=medium_term,
                    long_term_count=long_term,
                    high_impact_count=high_impact
                )

                results[ticker] = analysis

        return results


# Test harness
if __name__ == "__main__":
    print("CatalystAnalyzer - Test Harness\n")
    print("=" * 70)

    # Test initialization
    print("\n1. Testing initialization...")
    analyzer = CatalystAnalyzer()
    print(f"   ✅ Default weights: {analyzer.scoring_weights}")

    # Test prompt generation
    print("\n2. Testing generate_catalyst_prompt()...")
    company_data = {
        'ticker': 'NVDA',
        'name': 'NVIDIA Corporation',
        'sector': 'Technology',
        'business_description': 'GPU and AI accelerator manufacturer'
    }

    prompt = analyzer.generate_catalyst_prompt(company_data)
    print(f"   ✅ Generated prompt ({len(prompt)} chars)")
    print(f"   Preview: {prompt[:150]}...")

    # Test parsing with sample response
    print("\n3. Testing parse_catalyst_response()...")
    sample_response = """
    CATALYST 1: Q1 FY2026 Earnings Report
    Timeline: 3 months
    Probability: H
    Impact: M
    Direction: +
    Dependencies: None
    Notes: Expecting strong data center GPU revenue growth

    CATALYST 2: Blackwell Architecture Launch
    Timeline: 5 months
    Probability: H
    Impact: H
    Direction: +
    Dependencies: Manufacturing ramp
    Notes: Next-gen AI training chips, significant performance improvements

    CATALYST 3: China Export Restrictions Update
    Timeline: 8 months
    Probability: M
    Impact: M
    Direction: -
    Dependencies: US-China relations
    Notes: Potential additional restrictions on advanced chip exports
    """

    catalysts = analyzer.parse_catalyst_response(sample_response, company_data)
    print(f"   ✅ Parsed {len(catalysts)} catalysts")

    for i, cat in enumerate(catalysts, 1):
        print(f"      {i}. {cat.name} ({cat.timeline_months} months, {cat.impact.value} impact)")

    # Test prioritization
    print("\n4. Testing prioritize_catalysts()...")
    prioritized = analyzer.prioritize_catalysts(catalysts)
    print(f"   ✅ Prioritized {len(prioritized)} catalysts")

    for i, cat in enumerate(prioritized, 1):
        print(f"      {i}. {cat.name} (score: {cat.priority_score:.2f})")

    # Test monitoring schedule
    print("\n5. Testing create_monitoring_schedule()...")
    schedule = analyzer.create_monitoring_schedule(prioritized)
    print(f"   ✅ Created schedule with {len(schedule['catalyst_dates'])} catalyst dates")
    print(f"      and {len(schedule['check_ins'])} check-in reminders")

    # Test report generation
    print("\n6. Testing generate_catalyst_summary_report()...")
    analysis = CatalystAnalysis(
        ticker='NVDA',
        company_name='NVIDIA Corporation',
        analysis_date=datetime.now(),
        catalysts=prioritized,
        top_5_catalysts=prioritized[:5],
        near_term_count=2,
        medium_term_count=1,
        long_term_count=0,
        high_impact_count=1
    )

    report = analyzer.generate_catalyst_summary_report(analysis)
    print(f"   ✅ Generated report ({len(report)} chars)")
    print(f"   Preview:\n{report[:300]}...")

    print("\n" + "=" * 70)
    print("✅ All tests completed successfully!")
    print("\nUsage example:")
    print("  analyzer = CatalystAnalyzer()")
    print("  prompt = analyzer.generate_catalyst_prompt(company_data)")
    print("  # Send to LLM, get response")
    print("  catalysts = analyzer.parse_catalyst_response(llm_response, company_data)")
    print("  prioritized = analyzer.prioritize_catalysts(catalysts)")
    print("  report = analyzer.generate_catalyst_summary_report(analysis)")
