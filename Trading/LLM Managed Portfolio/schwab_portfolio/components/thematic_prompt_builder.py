"""
Thematic Prompt Builder - Sector-Specific LLM Prompt Generation

This module provides specialized prompt generators for thematic/growth investing analysis,
supporting the opportunistic 20% allocation strategy. Each theme evaluates companies
across 5 specific dimensions with 1-10 scoring.

Themes Supported:
- AI Infrastructure (compute, networking, power, cooling)
- Nuclear Renaissance (SMR, uranium, services, regulatory)
- Defense Modernization (drones, cyber, space, hypersonics)
- Climate Technology (adaptation, mitigation, infrastructure)
- Longevity/Biotech (GLP-1, longevity, medical devices)
- Generic Thematic (flexible custom theme template)

Usage:
    builder = ThematicPromptBuilder(model_type='7B')
    prompt = builder.ai_infrastructure_prompt(company_data, context)

Author: Portfolio Management System
Version: 1.0.0
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re


class ModelType(Enum):
    """Supported model types with token budgets."""
    SMALL_7B = "7B"      # 800 token budget
    MEDIUM_13B = "13B"   # 1200 token budget
    LARGE_70B = "70B"    # 2000 token budget


@dataclass
class ThematicScore:
    """
    Thematic analysis scoring result.

    Attributes:
        dimension_scores: Dict mapping dimension names to scores (1-10)
        dimension_rationales: Dict mapping dimension names to reasoning
        overall_score: Total score out of 50
        classification: Company classification (Leader/Contender/Laggard)
        key_strength: Primary competitive advantage
        key_risk: Primary concern or risk factor
        investment_stance: BUY/HOLD/AVOID recommendation
        confidence: Confidence in analysis (0.0-1.0)
    """
    dimension_scores: Dict[str, int]
    dimension_rationales: Dict[str, str]
    overall_score: int
    classification: str
    key_strength: str
    key_risk: str
    investment_stance: str
    confidence: float


class ThematicPromptBuilder:
    """
    Generates optimized prompts for thematic investment analysis.

    Designed to work with HuggingFace 7B-70B models for sector-specific
    company evaluation across multiple dimensions. Supports the 20%
    opportunistic allocation strategy with systematic thematic scoring.

    Attributes:
        model_type: Target model size (7B/13B/70B)
        max_tokens: Token budget for prompts
        compress_mode: Whether to use compressed prompts
    """

    # Token budgets by model size
    TOKEN_BUDGETS = {
        ModelType.SMALL_7B: 800,
        ModelType.MEDIUM_13B: 1200,
        ModelType.LARGE_70B: 2000
    }

    # Classification thresholds
    CLASSIFICATION_THRESHOLDS = {
        "Leader": 40,      # 40-50 points
        "Contender": 30,   # 30-39 points
        "Laggard": 0       # 0-29 points
    }

    def __init__(self, model_type: str = '7B', compress_mode: bool = False):
        """
        Initialize thematic prompt builder.

        Args:
            model_type: Model size ('7B', '13B', or '70B')
            compress_mode: Enable prompt compression for token savings

        Raises:
            ValueError: If model_type is invalid
        """
        try:
            self.model_type = ModelType(model_type)
        except ValueError:
            valid_types = [t.value for t in ModelType]
            raise ValueError(f"Invalid model_type '{model_type}'. Must be one of: {valid_types}")

        self.max_tokens = self.TOKEN_BUDGETS[self.model_type]
        self.compress_mode = compress_mode

    def ai_infrastructure_prompt(
        self,
        company_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate AI infrastructure investment analysis prompt.

        Evaluates companies in the AI infrastructure value chain including
        data centers, networking, power, cooling, and supporting services.

        Dimensions:
        1. Value Chain Position (1-10): Where in stack, proximity to AI workloads
        2. Technical Differentiation (1-10): Technology moat, competitive advantages
        3. Customer Traction (1-10): Revenue growth, customer concentration, ARR
        4. Competitive Moat (1-10): Barriers to entry, switching costs
        5. Unit Economics (1-10): Gross margins, CAC payback, LTV/CAC

        Args:
            company_data: Company financial and business data
            context: Optional market context and comparisons

        Returns:
            Formatted prompt string optimized for model_type
        """
        ticker = company_data.get('ticker', 'UNKNOWN')
        company_name = company_data.get('name', ticker)

        # Build prompt sections
        prompt_parts = []

        # Role definition (60 tokens)
        prompt_parts.append(
            "You are an AI infrastructure investment analyst evaluating companies "
            "in the AI compute value chain (data centers, networking, power, cooling)."
        )

        # Company context (150 tokens)
        prompt_parts.append(f"\n## Company: {company_name} ({ticker})")

        if 'business_description' in company_data:
            desc = self._truncate_text(company_data['business_description'], 100)
            prompt_parts.append(f"Business: {desc}")

        if 'revenue' in company_data and 'revenue_growth' in company_data:
            prompt_parts.append(
                f"Revenue: ${company_data['revenue']/1e9:.2f}B | "
                f"Growth: {company_data['revenue_growth']:.1%}"
            )

        if 'gross_margin' in company_data:
            prompt_parts.append(f"Gross Margin: {company_data['gross_margin']:.1%}")

        # Analysis framework (200 tokens)
        prompt_parts.append(
            "\n## Rate the company on these 5 dimensions (1-10 scale):\n"
            "\n1. VALUE CHAIN POSITION"
            "\n   - Where in AI infrastructure stack (compute/network/power/cooling)?"
            "\n   - Proximity to AI workloads and criticality?"
            "\n   - Position in value chain (picks-and-shovels vs direct exposure)?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n2. TECHNICAL DIFFERENTIATION"
            "\n   - Proprietary technology or unique IP?"
            "\n   - Technical advantages over competitors?"
            "\n   - Innovation velocity and R&D effectiveness?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n3. CUSTOMER TRACTION"
            "\n   - Revenue growth trajectory and acceleration?"
            "\n   - Customer concentration risk?"
            "\n   - Evidence of product-market fit?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n4. COMPETITIVE MOAT"
            "\n   - Barriers to entry (capital, technology, relationships)?"
            "\n   - Customer switching costs?"
            "\n   - Competitive positioning vs alternatives?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n5. UNIT ECONOMICS"
            "\n   - Gross margins sustainable at scale?"
            "\n   - Customer acquisition costs and payback?"
            "\n   - Path to profitability and cash generation?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
        )

        # Output requirements (150 tokens)
        prompt_parts.append(
            "\n## Output Format:"
            "\nOVERALL SCORE: [Sum of 5 scores] / 50"
            "\n\nCLASSIFICATION: [Leader 40-50 / Contender 30-39 / Laggard 0-29]"
            "\n\nKEY STRENGTH: [Primary competitive advantage in 1 sentence]"
            "\n\nKEY RISK: [Primary concern or risk in 1 sentence]"
            "\n\nINVESTMENT STANCE: [BUY if score >35 / HOLD if 25-35 / AVOID if <25]"
        )

        # Market context if provided (100 tokens)
        if context and 'market_trends' in context:
            trends = self._truncate_text(context['market_trends'], 80)
            prompt_parts.append(f"\n\nMarket Context: {trends}")

        prompt = "\n".join(prompt_parts)

        # Compress if needed and validate length
        if self.compress_mode:
            prompt = self.compress_prompt(prompt)

        self.validate_prompt_length(prompt)

        return prompt

    def nuclear_renaissance_prompt(
        self,
        company_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate nuclear energy investment analysis prompt.

        Evaluates companies in nuclear renaissance including SMR technology,
        uranium mining/enrichment, services, and supporting infrastructure.

        Dimensions:
        1. Technology Readiness (1-10): TRL level, design maturity, testing progress
        2. Regulatory Progress (1-10): NRC approval status, licensing timeline
        3. Strategic Partnerships (1-10): Utility partnerships, government contracts
        4. Government Support (1-10): Policy tailwinds, subsidies, mandates
        5. Commercialization Timeline (1-10): Near-term revenue visibility

        Args:
            company_data: Company financial and business data
            context: Optional market context and comparisons

        Returns:
            Formatted prompt string optimized for model_type
        """
        ticker = company_data.get('ticker', 'UNKNOWN')
        company_name = company_data.get('name', ticker)

        prompt_parts = []

        # Role definition (60 tokens)
        prompt_parts.append(
            "You are a nuclear energy investment analyst evaluating companies "
            "in the nuclear renaissance (SMR, uranium, enrichment, services)."
        )

        # Company context (150 tokens)
        prompt_parts.append(f"\n## Company: {company_name} ({ticker})")

        if 'business_description' in company_data:
            desc = self._truncate_text(company_data['business_description'], 100)
            prompt_parts.append(f"Business: {desc}")

        if 'revenue' in company_data:
            prompt_parts.append(f"Revenue: ${company_data['revenue']/1e9:.2f}B")

        # Analysis framework (200 tokens)
        prompt_parts.append(
            "\n## Rate the company on these 5 dimensions (1-10 scale):\n"
            "\n1. TECHNOLOGY READINESS"
            "\n   - Technology Readiness Level (TRL 1-9)?"
            "\n   - Design maturity and testing validation?"
            "\n   - Proven vs developmental technology?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n2. REGULATORY PROGRESS"
            "\n   - NRC approval status and timeline?"
            "\n   - Licensing progress and hurdles?"
            "\n   - International regulatory approvals?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n3. STRATEGIC PARTNERSHIPS"
            "\n   - Utility partnerships and MOUs?"
            "\n   - Government contracts and funding?"
            "\n   - Customer pipeline and commitments?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n4. GOVERNMENT SUPPORT"
            "\n   - Policy tailwinds (IRA, state mandates)?"
            "\n   - Subsidies and loan guarantees?"
            "\n   - Bipartisan political support?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n5. COMMERCIALIZATION TIMELINE"
            "\n   - Time to first revenue/deployment?"
            "\n   - Capital requirements and runway?"
            "\n   - Execution risk assessment?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
        )

        # Output requirements (150 tokens)
        prompt_parts.append(
            "\n## Output Format:"
            "\nOVERALL SCORE: [Sum of 5 scores] / 50"
            "\n\nCLASSIFICATION: [Leader 40-50 / Contender 30-39 / Laggard 0-29]"
            "\n\nKEY STRENGTH: [Primary competitive advantage in 1 sentence]"
            "\n\nKEY RISK: [Primary concern or risk in 1 sentence]"
            "\n\nINVESTMENT STANCE: [BUY if score >35 / HOLD if 25-35 / AVOID if <25]"
        )

        if context and 'uranium_prices' in context:
            prompt_parts.append(
                f"\n\nMarket Context: Uranium spot price ${context['uranium_prices']:.2f}/lb"
            )

        prompt = "\n".join(prompt_parts)

        if self.compress_mode:
            prompt = self.compress_prompt(prompt)

        self.validate_prompt_length(prompt)

        return prompt

    def defense_modernization_prompt(
        self,
        company_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate defense modernization investment analysis prompt.

        Evaluates companies in defense tech including drones, cyber, space,
        hypersonics, and next-gen weapons systems.

        Dimensions:
        1. Program Stability (1-10): Contract backlog, multi-year programs
        2. Technology Superiority (1-10): Tech edge over adversaries
        3. Growth Runway (1-10): TAM expansion, new programs
        4. Financial Strength (1-10): Margins, ROIC, cash generation
        5. Geopolitical Tailwinds (1-10): Budget increases, threat environment

        Args:
            company_data: Company financial and business data
            context: Optional market context and comparisons

        Returns:
            Formatted prompt string optimized for model_type
        """
        ticker = company_data.get('ticker', 'UNKNOWN')
        company_name = company_data.get('name', ticker)

        prompt_parts = []

        # Role definition (60 tokens)
        prompt_parts.append(
            "You are a defense technology analyst evaluating companies in "
            "defense modernization (drones, cyber, space, hypersonics)."
        )

        # Company context (150 tokens)
        prompt_parts.append(f"\n## Company: {company_name} ({ticker})")

        if 'business_description' in company_data:
            desc = self._truncate_text(company_data['business_description'], 100)
            prompt_parts.append(f"Business: {desc}")

        if 'backlog' in company_data:
            prompt_parts.append(
                f"Contract Backlog: ${company_data['backlog']/1e9:.2f}B"
            )

        if 'revenue' in company_data and 'operating_margin' in company_data:
            prompt_parts.append(
                f"Revenue: ${company_data['revenue']/1e9:.2f}B | "
                f"Op Margin: {company_data['operating_margin']:.1%}"
            )

        # Analysis framework (200 tokens)
        prompt_parts.append(
            "\n## Rate the company on these 5 dimensions (1-10 scale):\n"
            "\n1. PROGRAM STABILITY"
            "\n   - Contract backlog and visibility?"
            "\n   - Multi-year program commitments?"
            "\n   - Customer concentration (DoD vs commercial)?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n2. TECHNOLOGY SUPERIORITY"
            "\n   - Technical edge over adversaries?"
            "\n   - Innovation velocity and R&D?"
            "\n   - Proprietary capabilities?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n3. GROWTH RUNWAY"
            "\n   - TAM expansion potential?"
            "\n   - New program wins and pipeline?"
            "\n   - International expansion opportunities?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n4. FINANCIAL STRENGTH"
            "\n   - Operating margins and ROIC?"
            "\n   - Free cash flow generation?"
            "\n   - Balance sheet and capital efficiency?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n5. GEOPOLITICAL TAILWINDS"
            "\n   - Defense budget trajectory?"
            "\n   - Threat environment driving demand?"
            "\n   - Bipartisan support for funding?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
        )

        # Output requirements (150 tokens)
        prompt_parts.append(
            "\n## Output Format:"
            "\nOVERALL SCORE: [Sum of 5 scores] / 50"
            "\n\nCLASSIFICATION: [Leader 40-50 / Contender 30-39 / Laggard 0-29]"
            "\n\nKEY STRENGTH: [Primary competitive advantage in 1 sentence]"
            "\n\nKEY RISK: [Primary concern or risk in 1 sentence]"
            "\n\nINVESTMENT STANCE: [BUY if score >35 / HOLD if 25-35 / AVOID if <25]"
        )

        if context and 'defense_budget' in context:
            prompt_parts.append(
                f"\n\nMarket Context: DoD budget ${context['defense_budget']/1e9:.0f}B"
            )

        prompt = "\n".join(prompt_parts)

        if self.compress_mode:
            prompt = self.compress_prompt(prompt)

        self.validate_prompt_length(prompt)

        return prompt

    def climate_tech_prompt(
        self,
        company_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate climate technology investment analysis prompt.

        Evaluates companies in climate adaptation and mitigation including
        infrastructure resilience, renewable energy, carbon capture, and
        electrification technologies.

        Dimensions:
        1. Technology Maturity (1-10): TRL level, commercial deployment
        2. Unit Economics (1-10): Cost competitiveness, margin profile
        3. Policy Support (1-10): IRA benefits, mandates, subsidies
        4. Demand & Scalability (1-10): Market pull, production scale
        5. Carbon Impact (1-10): Emissions reduction potential

        Args:
            company_data: Company financial and business data
            context: Optional market context and comparisons

        Returns:
            Formatted prompt string optimized for model_type
        """
        ticker = company_data.get('ticker', 'UNKNOWN')
        company_name = company_data.get('name', ticker)

        prompt_parts = []

        # Role definition (60 tokens)
        prompt_parts.append(
            "You are a climate technology analyst evaluating companies in "
            "climate adaptation/mitigation (infrastructure, energy, carbon capture)."
        )

        # Company context (150 tokens)
        prompt_parts.append(f"\n## Company: {company_name} ({ticker})")

        if 'business_description' in company_data:
            desc = self._truncate_text(company_data['business_description'], 100)
            prompt_parts.append(f"Business: {desc}")

        if 'revenue' in company_data and 'revenue_growth' in company_data:
            prompt_parts.append(
                f"Revenue: ${company_data['revenue']/1e9:.2f}B | "
                f"Growth: {company_data['revenue_growth']:.1%}"
            )

        # Analysis framework (200 tokens)
        prompt_parts.append(
            "\n## Rate the company on these 5 dimensions (1-10 scale):\n"
            "\n1. TECHNOLOGY MATURITY"
            "\n   - Technology Readiness Level (TRL)?"
            "\n   - Commercial deployment scale?"
            "\n   - Proven vs developmental technology?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n2. UNIT ECONOMICS"
            "\n   - Cost competitive with alternatives?"
            "\n   - Gross margin profile at scale?"
            "\n   - Path to profitability and cash flow?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n3. POLICY SUPPORT"
            "\n   - IRA tax credits and benefits?"
            "\n   - State/federal mandates?"
            "\n   - International policy tailwinds?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n4. DEMAND & SCALABILITY"
            "\n   - Market pull and customer demand?"
            "\n   - Production scalability?"
            "\n   - Supply chain readiness?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n5. CARBON IMPACT"
            "\n   - CO2 reduction potential (tons/year)?"
            "\n   - Cost per ton CO2 avoided?"
            "\n   - Contribution to climate goals?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
        )

        # Output requirements (150 tokens)
        prompt_parts.append(
            "\n## Output Format:"
            "\nOVERALL SCORE: [Sum of 5 scores] / 50"
            "\n\nCLASSIFICATION: [Leader 40-50 / Contender 30-39 / Laggard 0-29]"
            "\n\nKEY STRENGTH: [Primary competitive advantage in 1 sentence]"
            "\n\nKEY RISK: [Primary concern or risk in 1 sentence]"
            "\n\nINVESTMENT STANCE: [BUY if score >35 / HOLD if 25-35 / AVOID if <25]"
        )

        if context and 'carbon_prices' in context:
            prompt_parts.append(
                f"\n\nMarket Context: Carbon price ${context['carbon_prices']:.2f}/ton CO2"
            )

        prompt = "\n".join(prompt_parts)

        if self.compress_mode:
            prompt = self.compress_prompt(prompt)

        self.validate_prompt_length(prompt)

        return prompt

    def longevity_biotech_prompt(
        self,
        company_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate longevity/biotech investment analysis prompt.

        Evaluates companies in longevity medicine, GLP-1 drugs, medical devices,
        and breakthrough therapies.

        Dimensions:
        1. Science Quality (1-10): Mechanism validity, data quality
        2. Clinical Progress (1-10): Trial stage, endpoints, enrollment
        3. Commercial Potential (1-10): Market size, pricing power, competition
        4. IP Position (1-10): Patent protection, exclusivity timeline
        5. Management & Financing (1-10): Team quality, cash runway

        Args:
            company_data: Company financial and business data
            context: Optional market context and comparisons

        Returns:
            Formatted prompt string optimized for model_type
        """
        ticker = company_data.get('ticker', 'UNKNOWN')
        company_name = company_data.get('name', ticker)

        prompt_parts = []

        # Role definition (60 tokens)
        prompt_parts.append(
            "You are a biotech investment analyst evaluating companies in "
            "longevity medicine (GLP-1, aging, breakthrough therapies)."
        )

        # Company context (150 tokens)
        prompt_parts.append(f"\n## Company: {company_name} ({ticker})")

        if 'business_description' in company_data:
            desc = self._truncate_text(company_data['business_description'], 100)
            prompt_parts.append(f"Business: {desc}")

        if 'pipeline' in company_data:
            pipeline = self._truncate_text(company_data['pipeline'], 80)
            prompt_parts.append(f"Pipeline: {pipeline}")

        if 'cash' in company_data and 'burn_rate' in company_data:
            runway_months = company_data['cash'] / (company_data['burn_rate'] / 12)
            prompt_parts.append(f"Cash Runway: {runway_months:.0f} months")

        # Analysis framework (200 tokens)
        prompt_parts.append(
            "\n## Rate the company on these 5 dimensions (1-10 scale):\n"
            "\n1. SCIENCE QUALITY"
            "\n   - Mechanism of action validity?"
            "\n   - Preclinical and clinical data quality?"
            "\n   - Scientific team credentials?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n2. CLINICAL PROGRESS"
            "\n   - Trial stage (preclinical/Phase 1/2/3/NDA)?"
            "\n   - Endpoint achievement and statistical power?"
            "\n   - Enrollment progress and timeline?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n3. COMMERCIAL POTENTIAL"
            "\n   - Addressable market size?"
            "\n   - Pricing power and reimbursement?"
            "\n   - Competitive landscape?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n4. IP POSITION"
            "\n   - Patent protection strength?"
            "\n   - Exclusivity timeline (years)?"
            "\n   - Freedom to operate?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
            "\n\n5. MANAGEMENT & FINANCING"
            "\n   - Management team quality and track record?"
            "\n   - Cash runway sufficiency?"
            "\n   - Partnership/financing prospects?"
            "\n   Score: [1-10]"
            "\n   Rationale: [1 sentence]"
        )

        # Output requirements (150 tokens)
        prompt_parts.append(
            "\n## Output Format:"
            "\nOVERALL SCORE: [Sum of 5 scores] / 50"
            "\n\nCLASSIFICATION: [Leader 40-50 / Contender 30-39 / Laggard 0-29]"
            "\n\nKEY STRENGTH: [Primary competitive advantage in 1 sentence]"
            "\n\nKEY RISK: [Primary concern or risk in 1 sentence]"
            "\n\nINVESTMENT STANCE: [BUY if score >35 / HOLD if 25-35 / AVOID if <25]"
        )

        if context and 'sector_funding' in context:
            prompt_parts.append(
                f"\n\nMarket Context: Biotech funding ${context['sector_funding']/1e9:.1f}B"
            )

        prompt = "\n".join(prompt_parts)

        if self.compress_mode:
            prompt = self.compress_prompt(prompt)

        self.validate_prompt_length(prompt)

        return prompt

    def generic_thematic_prompt(
        self,
        company_data: Dict[str, Any],
        theme_name: str,
        dimensions: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate flexible thematic investment analysis prompt for custom themes.

        Allows user-defined themes with custom evaluation dimensions. Useful for
        emerging themes not covered by predefined templates.

        Args:
            company_data: Company financial and business data
            theme_name: Name of the theme (e.g., "Quantum Computing", "Space Economy")
            dimensions: List of 5 dimension names to evaluate
            context: Optional market context and comparisons

        Returns:
            Formatted prompt string optimized for model_type

        Raises:
            ValueError: If dimensions list doesn't contain exactly 5 items
        """
        if len(dimensions) != 5:
            raise ValueError(f"Must provide exactly 5 dimensions, got {len(dimensions)}")

        ticker = company_data.get('ticker', 'UNKNOWN')
        company_name = company_data.get('name', ticker)

        prompt_parts = []

        # Role definition (60 tokens)
        prompt_parts.append(
            f"You are an investment analyst evaluating companies in the "
            f"{theme_name} theme."
        )

        # Company context (150 tokens)
        prompt_parts.append(f"\n## Company: {company_name} ({ticker})")

        if 'business_description' in company_data:
            desc = self._truncate_text(company_data['business_description'], 100)
            prompt_parts.append(f"Business: {desc}")

        if 'revenue' in company_data:
            prompt_parts.append(f"Revenue: ${company_data['revenue']/1e9:.2f}B")

        # Analysis framework with custom dimensions (200 tokens)
        prompt_parts.append(
            f"\n## Rate the company on these 5 dimensions (1-10 scale):\n"
        )

        for i, dimension in enumerate(dimensions, 1):
            prompt_parts.append(
                f"\n{i}. {dimension.upper()}"
                f"\n   - Evaluate company strength in this dimension"
                f"\n   Score: [1-10]"
                f"\n   Rationale: [1 sentence]"
            )

        # Output requirements (150 tokens)
        prompt_parts.append(
            "\n\n## Output Format:"
            "\nOVERALL SCORE: [Sum of 5 scores] / 50"
            "\n\nCLASSIFICATION: [Leader 40-50 / Contender 30-39 / Laggard 0-29]"
            "\n\nKEY STRENGTH: [Primary competitive advantage in 1 sentence]"
            "\n\nKEY RISK: [Primary concern or risk in 1 sentence]"
            "\n\nINVESTMENT STANCE: [BUY if score >35 / HOLD if 25-35 / AVOID if <25]"
        )

        if context and 'market_context' in context:
            ctx = self._truncate_text(context['market_context'], 80)
            prompt_parts.append(f"\n\nMarket Context: {ctx}")

        prompt = "\n".join(prompt_parts)

        if self.compress_mode:
            prompt = self.compress_prompt(prompt)

        self.validate_prompt_length(prompt)

        return prompt

    # Utility Methods

    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count for a text string.

        Uses approximate heuristic: 1 token ≈ 4 characters for English text.
        More accurate than word count for LLM tokenization.

        Args:
            text: Input text to estimate

        Returns:
            Estimated token count
        """
        # Simple heuristic: ~4 chars per token for English
        # More sophisticated: use tiktoken library for exact counts
        return len(text) // 4

    def validate_prompt_length(self, prompt: str) -> Tuple[bool, int, int]:
        """
        Validate that prompt fits within model token budget.

        Args:
            prompt: Prompt string to validate

        Returns:
            Tuple of (is_valid, token_count, max_tokens)

        Raises:
            ValueError: If prompt exceeds token budget by >10%
        """
        token_count = self.estimate_token_count(prompt)
        is_valid = token_count <= self.max_tokens

        if not is_valid:
            overage_pct = ((token_count - self.max_tokens) / self.max_tokens) * 100

            if overage_pct > 10:
                raise ValueError(
                    f"Prompt exceeds token budget by {overage_pct:.1f}%: "
                    f"{token_count} tokens > {self.max_tokens} max for {self.model_type.value}"
                )

        return is_valid, token_count, self.max_tokens

    def compress_prompt(self, prompt: str) -> str:
        """
        Compress prompt by removing unnecessary whitespace and verbosity.

        Techniques:
        - Remove extra whitespace and newlines
        - Compress repeated phrases
        - Shorten common words (you→u, are→r, etc.)
        - Preserve critical structure and meaning

        Args:
            prompt: Original prompt string

        Returns:
            Compressed prompt string
        """
        # Remove extra whitespace
        compressed = re.sub(r'\n\s*\n', '\n', prompt)  # Multiple newlines → single
        compressed = re.sub(r'  +', ' ', compressed)    # Multiple spaces → single

        # Compress common phrases (only if severely over budget)
        token_count = self.estimate_token_count(compressed)
        if token_count > self.max_tokens * 1.1:  # >10% over
            replacements = {
                'You are an': "You're a",
                'You are a': "You're a",
                'investment analyst': 'analyst',
                'evaluate': 'rate',
                'evaluating': 'rating',
                'competitive advantage': 'advantage',
                'in 1 sentence': '(1 sent)',
                'Primary concern or risk': 'Key risk',
                'Primary competitive advantage': 'Key strength',
            }

            for old, new in replacements.items():
                compressed = compressed.replace(old, new)

        return compressed

    def _truncate_text(self, text: str, max_length: int) -> str:
        """
        Truncate text to maximum length with ellipsis.

        Args:
            text: Input text
            max_length: Maximum character length

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."


# Test harness
if __name__ == "__main__":
    print("ThematicPromptBuilder - Test Suite\n")
    print("=" * 70)

    # Test initialization
    print("\n1. Testing model type initialization...")
    for model_type in ['7B', '13B', '70B']:
        builder = ThematicPromptBuilder(model_type=model_type)
        print(f"   {model_type}: Token budget = {builder.max_tokens}")

    # Test AI infrastructure prompt
    print("\n2. Testing ai_infrastructure_prompt()...")
    builder = ThematicPromptBuilder(model_type='7B')

    company_data = {
        'ticker': 'SMCI',
        'name': 'Super Micro Computer Inc',
        'business_description': 'Server and storage solutions for AI data centers',
        'revenue': 14.9e9,
        'revenue_growth': 1.10,
        'gross_margin': 0.15
    }

    prompt = builder.ai_infrastructure_prompt(company_data)
    token_count = builder.estimate_token_count(prompt)
    print(f"   Generated prompt: {token_count} tokens (max {builder.max_tokens})")
    print(f"   Preview: {prompt[:200]}...")

    # Test nuclear renaissance prompt
    print("\n3. Testing nuclear_renaissance_prompt()...")
    company_data = {
        'ticker': 'OKLO',
        'name': 'Oklo Inc',
        'business_description': 'Advanced fission power plant developer',
        'revenue': 0.1e9
    }

    prompt = builder.nuclear_renaissance_prompt(company_data)
    token_count = builder.estimate_token_count(prompt)
    print(f"   Generated prompt: {token_count} tokens")

    # Test generic thematic prompt
    print("\n4. Testing generic_thematic_prompt()...")
    dimensions = [
        "Technology Leadership",
        "Market Timing",
        "Competitive Position",
        "Financial Health",
        "Execution Capability"
    ]

    company_data = {
        'ticker': 'IONQ',
        'name': 'IonQ Inc',
        'business_description': 'Quantum computing systems',
        'revenue': 0.05e9
    }

    prompt = builder.generic_thematic_prompt(
        company_data,
        theme_name="Quantum Computing",
        dimensions=dimensions
    )
    token_count = builder.estimate_token_count(prompt)
    print(f"   Generated prompt: {token_count} tokens")

    # Test utility methods
    print("\n5. Testing utility methods...")
    test_text = "This is a test prompt for token estimation." * 20
    estimated = builder.estimate_token_count(test_text)
    print(f"   Token estimation: {estimated} tokens for {len(test_text)} chars")

    is_valid, count, max_tokens = builder.validate_prompt_length(prompt)
    print(f"   Validation: valid={is_valid}, count={count}, max={max_tokens}")

    compressed = builder.compress_prompt(test_text)
    savings = len(test_text) - len(compressed)
    print(f"   Compression: saved {savings} chars ({savings/len(test_text)*100:.1f}%)")

    print("\n" + "=" * 70)
    print("✅ All tests completed successfully!")
    print("\nUsage example:")
    print("  builder = ThematicPromptBuilder(model_type='7B')")
    print("  prompt = builder.ai_infrastructure_prompt(company_data)")
    print("  # Send prompt to HuggingFace model for analysis")
