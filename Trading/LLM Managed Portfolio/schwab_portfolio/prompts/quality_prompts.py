"""
Quality Metrics LLM Prompt Generator

Generates optimized prompts for HuggingFace 7B generative models to analyze
quality metrics and provide structured investment insights.

This module bridges the QualityMetricsCalculator with generative LLMs for
enhanced analysis and recommendations.

Author: Trading System
Date: 2025-10-30
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import logging

from schwab_portfolio.quality.quality_metrics_calculator import (
    QualityAnalysisResult,
    QualityTier,
    MetricScore,
    RedFlag
)

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class LLMAnalysisRequest:
    """Structured request for LLM quality analysis."""
    ticker: str
    composite_score: float
    tier: str
    metrics: Dict[str, Tuple[float, float]]  # metric_name -> (value, score)
    red_flags: List[Dict[str, Any]]
    is_consistent_roe: bool
    context: Optional[str] = None  # Additional context (industry, market conditions, etc.)


@dataclass
class LLMAnalysisResponse:
    """Structured response from LLM quality analysis."""
    ticker: str
    quality_rating: str  # Strong/Moderate/Weak
    key_strengths: List[str]
    key_concerns: List[str]
    has_red_flags: bool
    red_flag_details: Optional[str]
    overall_assessment: str
    confidence: str  # High/Medium/Low
    raw_response: str  # Full LLM response


class QualityLLMPromptGenerator:
    """
    Generates optimized prompts for 7B parameter LLMs to analyze quality metrics.

    Designed for models like Llama-2-7B, Mistral-7B, and similar generative models.
    Prompts are optimized to stay under 600 tokens while maintaining clarity.
    """

    # Token budget guidelines (approximate)
    MAX_TOTAL_TOKENS = 600
    SYSTEM_ROLE_TOKENS = 50
    INSTRUCTIONS_TOKENS = 150
    METRICS_TOKENS = 200
    REASONING_TOKENS = 100
    OUTPUT_FORMAT_TOKENS = 100

    # Metric abbreviations for token efficiency
    METRIC_ABBREV = {
        'gross_profitability': 'GP',
        'roe': 'ROE',
        'operating_profitability': 'OP',
        'fcf_yield': 'FCF',
        'roic': 'ROIC'
    }

    METRIC_NAMES_FULL = {
        'gross_profitability': 'Gross Profitability',
        'roe': 'Return on Equity',
        'operating_profitability': 'Operating Profitability',
        'fcf_yield': 'Free Cash Flow Yield',
        'roic': 'Return on Invested Capital'
    }

    def __init__(self):
        """Initialize the prompt generator."""
        logger.info("QualityLLMPromptGenerator initialized")

    def generate_quality_screening_prompt(
        self,
        quality_result: QualityAnalysisResult,
        context: Optional[str] = None,
        include_reasoning_steps: bool = True
    ) -> str:
        """
        Generate optimized prompt for LLM quality analysis.

        Args:
            quality_result: QualityAnalysisResult from calculator
            context: Optional additional context (industry, market conditions, etc.)
            include_reasoning_steps: Whether to include chain-of-thought steps

        Returns:
            Optimized prompt string (target: <600 tokens)
        """
        # Build prompt sections
        sections = []

        # 1. Role definition (concise)
        sections.append(self._generate_role_definition())

        # 2. Company data and metrics
        sections.append(self._generate_metrics_section(quality_result))

        # 3. Red flags (if any)
        if quality_result.red_flags:
            sections.append(self._generate_red_flags_section(quality_result.red_flags))

        # 4. Chain-of-thought reasoning steps (optional)
        if include_reasoning_steps:
            sections.append(self._generate_reasoning_steps())

        # 5. Context (if provided)
        if context:
            sections.append(f"\nContext: {context[:100]}")  # Limit context to 100 chars

        # 6. Output format requirements
        sections.append(self._generate_output_format())

        # Combine sections
        prompt = "\n\n".join(sections)

        # Log token estimate
        estimated_tokens = self._estimate_tokens(prompt)
        logger.info(f"Generated prompt for {quality_result.ticker}: "
                   f"~{estimated_tokens} tokens (target: {self.MAX_TOTAL_TOKENS})")

        if estimated_tokens > self.MAX_TOTAL_TOKENS:
            logger.warning(f"Prompt exceeds target token count: {estimated_tokens} > {self.MAX_TOTAL_TOKENS}")

        return prompt

    def generate_batch_screening_prompts(
        self,
        quality_results: List[QualityAnalysisResult],
        context: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate prompts for multiple companies (batch processing).

        Args:
            quality_results: List of QualityAnalysisResult objects
            context: Optional shared context for all companies

        Returns:
            Dictionary mapping tickers to their prompts
        """
        prompts = {}

        for result in quality_results:
            try:
                prompt = self.generate_quality_screening_prompt(
                    result,
                    context=context,
                    include_reasoning_steps=True
                )
                prompts[result.ticker] = prompt
            except Exception as e:
                logger.error(f"Error generating prompt for {result.ticker}: {str(e)}")

        logger.info(f"Generated {len(prompts)} batch prompts")
        return prompts

    def generate_comparative_prompt(
        self,
        quality_results: List[QualityAnalysisResult],
        max_companies: int = 5
    ) -> str:
        """
        Generate prompt for comparative analysis of multiple companies.

        Args:
            quality_results: List of QualityAnalysisResult objects
            max_companies: Maximum number of companies to include (default: 5)

        Returns:
            Comparative analysis prompt
        """
        # Limit to max_companies
        results = sorted(
            quality_results,
            key=lambda r: r.composite_score,
            reverse=True
        )[:max_companies]

        sections = []

        # Role
        sections.append(
            "You are an equity research analyst comparing company quality metrics.\n"
        )

        # Companies summary
        sections.append("Companies to compare:\n")
        for result in results:
            sections.append(
                f"{result.ticker}: Score={result.composite_score:.1f}/100, "
                f"Tier={result.tier.value}, "
                f"RedFlags={len(result.red_flags)}"
            )

        # Metrics table
        sections.append("\nQuality Metrics:\n")
        header = f"{'Ticker':<8} {'GP':<7} {'ROE':<7} {'OP':<7} {'FCF':<7} {'ROIC':<7}"
        sections.append(header)
        sections.append("-" * len(header))

        for result in results:
            metrics = {ms.name: ms.value for ms in result.metric_scores}
            line = (
                f"{result.ticker:<8} "
                f"{metrics.get('gross_profitability', 0):<7.1%} "
                f"{metrics.get('roe', 0):<7.1%} "
                f"{metrics.get('operating_profitability', 0):<7.1%} "
                f"{metrics.get('fcf_yield', 0):<7.1%} "
                f"{metrics.get('roic', 0):<7.1%}"
            )
            sections.append(line)

        # Analysis request
        sections.append(
            "\nProvide:\n"
            "1. Rank companies by overall quality (1=best)\n"
            "2. Best quality pick (2-3 reasons)\n"
            "3. Riskiest holding (2-3 concerns)\n"
            "4. One-line verdict for each company\n"
            "Be concise (max 150 words total)."
        )

        prompt = "\n".join(sections)
        estimated_tokens = self._estimate_tokens(prompt)
        logger.info(f"Generated comparative prompt: ~{estimated_tokens} tokens")

        return prompt

    def parse_llm_response(self, response: str, ticker: str) -> LLMAnalysisResponse:
        """
        Parse structured output from LLM response.

        Args:
            response: Raw LLM response text
            ticker: Company ticker symbol

        Returns:
            Structured LLMAnalysisResponse object
        """
        # Initialize default values
        quality_rating = "Unknown"
        key_strengths = []
        key_concerns = []
        has_red_flags = False
        red_flag_details = None
        overall_assessment = ""
        confidence = "Medium"

        # Parse response line by line
        lines = response.strip().split('\n')

        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect sections
            if line.startswith("QUALITY RATING:"):
                quality_rating = line.split(":", 1)[1].strip()
            elif line.startswith("KEY STRENGTHS:"):
                current_section = "strengths"
            elif line.startswith("KEY CONCERNS:"):
                current_section = "concerns"
            elif line.startswith("RED FLAGS:"):
                red_flags_text = line.split(":", 1)[1].strip()
                has_red_flags = red_flags_text.lower().startswith("yes")
                if has_red_flags and len(red_flags_text) > 4:
                    red_flag_details = red_flags_text[4:].strip()
                current_section = None
            elif line.startswith("OVERALL ASSESSMENT:"):
                overall_assessment = line.split(":", 1)[1].strip()
                current_section = None
            elif line.startswith("CONFIDENCE:"):
                confidence = line.split(":", 1)[1].strip()
                current_section = None
            elif line.startswith("- ") or line.startswith("• "):
                # Bullet point
                bullet = line[2:].strip()
                if current_section == "strengths":
                    key_strengths.append(bullet)
                elif current_section == "concerns":
                    key_concerns.append(bullet)

        # Validate and clean
        if quality_rating not in ["Strong", "Moderate", "Weak"]:
            logger.warning(f"Invalid quality rating: {quality_rating}, defaulting to Moderate")
            quality_rating = "Moderate"

        if confidence not in ["High", "Medium", "Low"]:
            logger.warning(f"Invalid confidence: {confidence}, defaulting to Medium")
            confidence = "Medium"

        return LLMAnalysisResponse(
            ticker=ticker,
            quality_rating=quality_rating,
            key_strengths=key_strengths,
            key_concerns=key_concerns,
            has_red_flags=has_red_flags,
            red_flag_details=red_flag_details,
            overall_assessment=overall_assessment,
            confidence=confidence,
            raw_response=response
        )

    def _generate_role_definition(self) -> str:
        """Generate concise role definition."""
        return "You are an equity research analyst specializing in quality investing."

    def _generate_metrics_section(self, result: QualityAnalysisResult) -> str:
        """Generate metrics presentation section."""
        lines = [f"Company: {result.ticker}"]
        lines.append(f"Overall Quality Score: {result.composite_score:.1f}/100 ({result.tier.value} tier)")

        # Metrics with scores
        lines.append("\nQuality Metrics:")
        for ms in result.metric_scores:
            abbrev = self.METRIC_ABBREV.get(ms.name, ms.name)
            lines.append(
                f"- {abbrev}: {ms.value:.1%} (score: {ms.score:.1f}/10)"
            )

        # Consistent performer badge
        if result.is_consistent_roe_performer:
            lines.append("\n✓ ROE >15% for 10+ consecutive years")

        return "\n".join(lines)

    def _generate_red_flags_section(self, red_flags: List[RedFlag]) -> str:
        """Generate red flags section."""
        if not red_flags:
            return ""

        lines = ["Red Flags Detected:"]

        # Group by severity
        high = [rf for rf in red_flags if rf.severity == "HIGH"]
        medium = [rf for rf in red_flags if rf.severity == "MEDIUM"]

        if high:
            lines.append(f"- HIGH severity ({len(high)}): {', '.join(rf.category for rf in high[:3])}")

        if medium:
            lines.append(f"- MEDIUM severity ({len(medium)}): {', '.join(rf.category for rf in medium[:2])}")

        return "\n".join(lines)

    def _generate_reasoning_steps(self) -> str:
        """Generate chain-of-thought reasoning instructions."""
        return (
            "Analysis steps:\n"
            "1. Assess profitability (GP, OP)\n"
            "2. Examine capital returns (ROE, ROIC)\n"
            "3. Analyze cash flow quality (FCF)\n"
            "4. Identify key strengths (2-3)\n"
            "5. Identify concerns (2-3)\n"
            "6. Evaluate red flags\n"
            "7. Synthesize overall assessment"
        )

    def _generate_output_format(self) -> str:
        """Generate output format requirements."""
        return (
            "Provide structured output:\n"
            "QUALITY RATING: Strong/Moderate/Weak\n"
            "KEY STRENGTHS:\n"
            "- [strength 1]\n"
            "- [strength 2]\n"
            "KEY CONCERNS:\n"
            "- [concern 1]\n"
            "- [concern 2]\n"
            "RED FLAGS: Yes/No [specifics if yes]\n"
            "OVERALL ASSESSMENT: [max 50 words]\n"
            "CONFIDENCE: High/Medium/Low"
        )

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses rough approximation: 1 token ≈ 4 characters for English text.
        LLMs typically use subword tokenization, so this is an approximation.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        # Rule of thumb: ~4 characters per token
        # More accurate would be to use a tokenizer, but this is sufficient for estimates
        return len(text) // 4

    def create_analysis_request(
        self,
        quality_result: QualityAnalysisResult,
        context: Optional[str] = None
    ) -> LLMAnalysisRequest:
        """
        Convert QualityAnalysisResult to LLMAnalysisRequest.

        Args:
            quality_result: Quality analysis result
            context: Optional additional context

        Returns:
            Structured LLMAnalysisRequest object
        """
        # Extract metrics as (value, score) tuples
        metrics = {
            ms.name: (ms.value, ms.score)
            for ms in quality_result.metric_scores
        }

        # Convert red flags to dicts
        red_flags_list = [
            {
                'category': rf.category,
                'severity': rf.severity,
                'description': rf.description,
                'value': rf.metric_value
            }
            for rf in quality_result.red_flags
        ]

        return LLMAnalysisRequest(
            ticker=quality_result.ticker,
            composite_score=quality_result.composite_score,
            tier=quality_result.tier.value,
            metrics=metrics,
            red_flags=red_flags_list,
            is_consistent_roe=quality_result.is_consistent_roe_performer,
            context=context
        )

    def generate_investment_recommendation_prompt(
        self,
        quality_result: QualityAnalysisResult,
        current_price: Optional[float] = None,
        target_allocation: Optional[float] = None
    ) -> str:
        """
        Generate prompt for investment recommendation based on quality metrics.

        Args:
            quality_result: Quality analysis result
            current_price: Current stock price (optional)
            target_allocation: Target portfolio allocation percentage (optional)

        Returns:
            Investment-focused prompt
        """
        sections = []

        sections.append(
            "You are a portfolio manager evaluating investment decisions using quality metrics."
        )

        # Company quality summary
        sections.append(
            f"\nCompany: {quality_result.ticker}\n"
            f"Quality Score: {quality_result.composite_score:.1f}/100 ({quality_result.tier.value})\n"
            f"Red Flags: {len(quality_result.red_flags)} "
            f"({len([rf for rf in quality_result.red_flags if rf.severity == 'HIGH'])} high severity)"
        )

        # Top metrics
        top_metrics = sorted(quality_result.metric_scores, key=lambda x: x.score, reverse=True)[:3]
        sections.append("\nStrongest Metrics:")
        for ms in top_metrics:
            name = self.METRIC_NAMES_FULL.get(ms.name, ms.name)
            sections.append(f"- {name}: {ms.value:.1%} (score: {ms.score:.1f}/10)")

        # Context
        if current_price:
            sections.append(f"\nCurrent Price: ${current_price:.2f}")
        if target_allocation:
            sections.append(f"Target Allocation: {target_allocation:.1%} of portfolio")

        # Request
        sections.append(
            "\nProvide:\n"
            "RECOMMENDATION: BUY/HOLD/SELL\n"
            "RATIONALE: [30 words max]\n"
            "RISK LEVEL: Low/Medium/High\n"
            "POSITION SIZE: Overweight/Neutral/Underweight\n"
            "KEY WATCH ITEM: [one key metric or risk to monitor]"
        )

        prompt = "\n".join(sections)
        estimated_tokens = self._estimate_tokens(prompt)
        logger.info(f"Generated investment prompt: ~{estimated_tokens} tokens")

        return prompt


def format_llm_response(response: LLMAnalysisResponse) -> str:
    """
    Format LLMAnalysisResponse as human-readable text.

    Args:
        response: Parsed LLM response

    Returns:
        Formatted string
    """
    lines = []
    lines.append(f"=== LLM Quality Analysis: {response.ticker} ===\n")

    lines.append(f"Quality Rating: {response.quality_rating}")
    lines.append(f"Confidence: {response.confidence}\n")

    if response.key_strengths:
        lines.append("Key Strengths:")
        for strength in response.key_strengths:
            lines.append(f"  • {strength}")
        lines.append("")

    if response.key_concerns:
        lines.append("Key Concerns:")
        for concern in response.key_concerns:
            lines.append(f"  • {concern}")
        lines.append("")

    if response.has_red_flags:
        lines.append(f"⚠️  Red Flags: {response.red_flag_details or 'Yes'}\n")
    else:
        lines.append("✓ No red flags detected\n")

    lines.append(f"Overall Assessment:\n{response.overall_assessment}")

    return "\n".join(lines)


# Example usage and testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    # Import for testing
    from quality.quality_metrics_calculator import QualityMetricsCalculator

    # Example company data
    example_data = {
        'ticker': 'AAPL',
        'revenue': 394_328_000_000,
        'cogs': 223_546_000_000,
        'sga': 26_094_000_000,
        'total_assets': 352_755_000_000,
        'net_income': 99_803_000_000,
        'shareholder_equity': 62_146_000_000,
        'free_cash_flow': 111_443_000_000,
        'market_cap': 3_000_000_000_000,
        'total_debt': 111_088_000_000,
        'nopat': 85_000_000_000,
        'roe_history': [0.46, 0.49, 0.55, 0.61, 0.56, 0.50, 0.63, 0.83, 1.00, 1.60],
    }

    # Calculate quality metrics
    calculator = QualityMetricsCalculator()
    result = calculator.calculate_quality_metrics(example_data)

    # Generate prompts
    prompt_gen = QualityLLMPromptGenerator()

    print("\n" + "=" * 80)
    print("EXAMPLE 1: Single Company Quality Screening Prompt")
    print("=" * 80)
    prompt = prompt_gen.generate_quality_screening_prompt(result)
    print(prompt)

    print("\n" + "=" * 80)
    print("EXAMPLE 2: Investment Recommendation Prompt")
    print("=" * 80)
    investment_prompt = prompt_gen.generate_investment_recommendation_prompt(
        result,
        current_price=175.50,
        target_allocation=0.15
    )
    print(investment_prompt)

    print("\n" + "=" * 80)
    print("EXAMPLE 3: Parsing Mock LLM Response")
    print("=" * 80)

    mock_response = """
QUALITY RATING: Strong

KEY STRENGTHS:
- Exceptional profitability metrics with GP at 48% and OP at 41%
- Outstanding capital returns (ROE 161%, ROIC 49%) indicating efficient capital allocation
- Consistent elite performer with 10+ years of ROE >15%

KEY CONCERNS:
- FCF yield at 3.7% is moderate given premium valuation
- Reliance on continued innovation and product cycles

RED FLAGS: No

OVERALL ASSESSMENT: Elite quality company with exceptional profitability, returns, and consistency. Strong competitive moat evidenced by sustained high ROIC. Premium valuation justified by quality metrics.

CONFIDENCE: High
"""

    parsed = prompt_gen.parse_llm_response(mock_response, "AAPL")
    print(format_llm_response(parsed))

    print("\n" + "=" * 80)
    print("Token Estimates:")
    print("=" * 80)
    print(f"Quality screening prompt: ~{prompt_gen._estimate_tokens(prompt)} tokens")
    print(f"Investment prompt: ~{prompt_gen._estimate_tokens(investment_prompt)} tokens")
    print(f"Target limit: {prompt_gen.MAX_TOTAL_TOKENS} tokens")
