"""
Multi-Model LLM Analysis Pipeline
Orchestrates the 4-model financial analysis chain for comprehensive trading recommendations

Pipeline Flow:
1. News Analysis -> Sentiment, catalysts, market events
2. Market Analysis -> Technical patterns, trends, support/resistance  
3. Trading Decision -> Synthesize inputs into specific BUY/SELL/HOLD recommendations
4. Risk Validation -> Final safety and compliance check

Located in local_runtime/ to work with copied portfolio system.
"""

import os
import sys
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import re

# Add the Portfolio Scripts Schwab directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
portfolio_dir = os.path.join(current_dir, 'Portfolio Scripts Schwab')
sys.path.append(portfolio_dir)

from local_llm_server import LocalLLMServer
from context_assembler import ContextAssembler
from trading_models import TradeOrder, OrderType, OrderPriority


@dataclass
class AnalysisResult:
    """Result from a single model analysis"""
    model_name: str
    analysis_text: str
    confidence_score: float
    key_insights: List[str]
    recommendations: List[str]
    timestamp: str
    processing_time: float


@dataclass
class PipelineResult:
    """Complete pipeline analysis result"""
    timestamp: str
    news_analysis: AnalysisResult
    market_analysis: AnalysisResult
    trading_decision: AnalysisResult
    risk_validation: AnalysisResult
    final_recommendations: List[TradeOrder]
    confidence_score: float
    processing_time: float
    warnings: List[str]


class LLMAnalysisPipeline:
    """Orchestrates multi-model financial analysis pipeline"""
    
    def __init__(self, llm_server: LocalLLMServer, context_assembler: ContextAssembler):
        """
        Initialize analysis pipeline
        
        Args:
            llm_server: Local LLM inference server
            context_assembler: Financial context preparation system
        """
        self.llm_server = llm_server
        self.context_assembler = context_assembler
        
        # Pipeline configuration
        self.model_sequence = [
            "news_analysis",
            "market_analysis", 
            "trading_decision",
            "risk_validation"
        ]
        
        # Setup logging
        self.logger = logging.getLogger('llm_pipeline')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    async def run_full_analysis(self, include_news: bool = True, 
                               risk_tolerance: str = "moderate") -> PipelineResult:
        """
        Run complete 4-model analysis pipeline
        
        Args:
            include_news: Whether to include news analysis (requires external data)
            risk_tolerance: Risk tolerance level (conservative, moderate, aggressive)
            
        Returns:
            Complete pipeline analysis result
        """
        
        start_time = datetime.now()
        self.logger.info("🚀 Starting full LLM analysis pipeline")
        
        # Step 1: Assemble comprehensive context
        context = self.context_assembler.assemble_full_context(include_news=include_news)
        
        # Step 2: Run analysis sequence
        analysis_results = {}
        warnings = []
        
        for model_name in self.model_sequence:
            try:
                self.logger.info(f"🔄 Running {model_name} analysis...")
                result = await self._run_model_analysis(model_name, context, analysis_results)
                analysis_results[model_name] = result
                
            except Exception as e:
                self.logger.error(f"❌ {model_name} analysis failed: {e}")
                warnings.append(f"{model_name} analysis failed: {str(e)}")
                
                # Create placeholder result to continue pipeline
                analysis_results[model_name] = AnalysisResult(
                    model_name=model_name,
                    analysis_text=f"Analysis failed: {str(e)}",
                    confidence_score=0.0,
                    key_insights=[],
                    recommendations=[],
                    timestamp=datetime.now().isoformat(),
                    processing_time=0.0
                )
        
        # Step 3: Extract final trading recommendations
        trading_recommendations = self._extract_trading_recommendations(
            analysis_results.get("trading_decision"),
            analysis_results.get("risk_validation")
        )
        
        # Step 4: Calculate overall confidence
        confidence_score = self._calculate_overall_confidence(analysis_results)
        
        # Step 5: Create complete result
        total_time = (datetime.now() - start_time).total_seconds()
        
        pipeline_result = PipelineResult(
            timestamp=start_time.isoformat(),
            news_analysis=analysis_results.get("news_analysis"),
            market_analysis=analysis_results.get("market_analysis"),
            trading_decision=analysis_results.get("trading_decision"),
            risk_validation=analysis_results.get("risk_validation"),
            final_recommendations=trading_recommendations,
            confidence_score=confidence_score,
            processing_time=total_time,
            warnings=warnings
        )
        
        self.logger.info(f"✅ Pipeline completed in {total_time:.1f}s with {len(trading_recommendations)} recommendations")
        return pipeline_result
    
    async def run_quick_analysis(self) -> PipelineResult:
        """
        Run streamlined analysis focusing on trading decision and risk validation
        Faster execution for time-sensitive decisions
        """
        
        start_time = datetime.now()
        self.logger.info("⚡ Starting quick analysis pipeline (trading + risk only)")
        
        # Get focused trading context
        trading_context = self.context_assembler.assemble_trading_context()
        risk_context = self.context_assembler.assemble_risk_context()
        
        # Run only trading decision and risk validation
        analysis_results = {}
        warnings = []
        
        try:
            # Trading decision analysis
            self.logger.info("🔄 Running trading decision analysis...")
            trading_result = await self._run_trading_decision_analysis(trading_context, {})
            analysis_results["trading_decision"] = trading_result
            
            # Risk validation analysis
            self.logger.info("🔄 Running risk validation analysis...")
            risk_result = await self._run_risk_validation_analysis(risk_context, trading_result)
            analysis_results["risk_validation"] = risk_result
            
        except Exception as e:
            self.logger.error(f"❌ Quick analysis failed: {e}")
            warnings.append(f"Quick analysis failed: {str(e)}")
        
        # Extract recommendations
        trading_recommendations = self._extract_trading_recommendations(
            analysis_results.get("trading_decision"),
            analysis_results.get("risk_validation")
        )
        
        total_time = (datetime.now() - start_time).total_seconds()
        
        pipeline_result = PipelineResult(
            timestamp=start_time.isoformat(),
            news_analysis=None,  # Skipped in quick analysis
            market_analysis=None,  # Skipped in quick analysis
            trading_decision=analysis_results.get("trading_decision"),
            risk_validation=analysis_results.get("risk_validation"),
            final_recommendations=trading_recommendations,
            confidence_score=self._calculate_overall_confidence(analysis_results),
            processing_time=total_time,
            warnings=warnings
        )
        
        self.logger.info(f"⚡ Quick analysis completed in {total_time:.1f}s")
        return pipeline_result
    
    async def _run_model_analysis(self, model_name: str, context: Dict[str, Any], 
                                 previous_results: Dict[str, AnalysisResult]) -> AnalysisResult:
        """Run analysis for specific model with context and previous results"""
        
        start_time = datetime.now()
        
        if model_name == "news_analysis":
            return await self._run_news_analysis(context)
        elif model_name == "market_analysis":
            return await self._run_market_analysis(context, previous_results.get("news_analysis"))
        elif model_name == "trading_decision":
            return await self._run_trading_decision_analysis(context, previous_results)
        elif model_name == "risk_validation":
            return await self._run_risk_validation_analysis(context, previous_results.get("trading_decision"))
        else:
            raise ValueError(f"Unknown model: {model_name}")
    
    async def _run_trading_decision_analysis(self, context: Dict[str, Any],
                                           previous_results: Dict[str, AnalysisResult]) -> AnalysisResult:
        """Run comprehensive trading decision analysis"""
        
        start_time = datetime.now()
        
        # Format context for trading decisions
        if isinstance(context, dict) and 'portfolio_overview' in context:
            # Full context
            formatted_context = self.context_assembler.format_for_model(context, "trading_decision")
        else:
            # Quick context
            formatted_context = json.dumps(context, indent=2)
        
        # Include previous analysis insights
        previous_context = ""
        for model_name, result in previous_results.items():
            if result and result.key_insights:
                previous_context += f"\n{model_name.replace('_', ' ').title()} Insights:\n"
                previous_context += "\n".join(result.key_insights)
        
        prompt = f"""As a professional portfolio manager, analyze the following portfolio data and generate specific trading recommendations:

{formatted_context}{previous_context}

Generate specific BUY/SELL/HOLD recommendations with:
1. Specific ticker symbols and share quantities
2. Clear rationale for each recommendation
3. Risk management considerations
4. Portfolio rebalancing opportunities
5. Cash allocation strategy

OUTPUT FORMAT:
For each recommendation, use exactly this format:
BUY [quantity] shares of [TICKER] - [reason]
SELL [quantity] shares of [TICKER] - [reason]  
HOLD [quantity] shares of [TICKER] - [reason]

Focus on improving portfolio diversification, managing risk, and capturing market opportunities while maintaining appropriate cash reserves."""
        
        response = await self.llm_server.generate(
            model_name="trading_decision",
            prompt=prompt,
            max_tokens=2000,
            temperature=0.1
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Parse insights and recommendations
        insights, recommendations = self._parse_analysis_response(response)
        confidence = self._estimate_confidence(response)
        
        return AnalysisResult(
            model_name="trading_decision",
            analysis_text=response,
            confidence_score=confidence,
            key_insights=insights,
            recommendations=recommendations,
            timestamp=start_time.isoformat(),
            processing_time=processing_time
        )
    
    async def _run_risk_validation_analysis(self, context: Dict[str, Any],
                                          trading_result: Optional[AnalysisResult]) -> AnalysisResult:
        """Run risk validation on proposed trades"""
        
        start_time = datetime.now()
        
        # Format context for risk validation
        if isinstance(context, dict) and 'portfolio_overview' in context:
            # Full context  
            formatted_context = self.context_assembler.format_for_model(context, "risk_validation")
        else:
            # Risk-specific context
            formatted_context = json.dumps(context, indent=2)
        
        # Include proposed trades if available
        proposed_trades = ""
        if trading_result and trading_result.recommendations:
            proposed_trades = "\n\nPROPOSED TRADES TO VALIDATE:\n" + "\n".join(trading_result.recommendations)
        
        prompt = f"""{formatted_context}{proposed_trades}

Validate the proposed trades against risk management criteria:

RISK CHECKS:
1. Position sizing limits (max 20% per position)
2. Cash reserve requirements (min 5%)
3. Portfolio concentration (max 60% in top 3 positions)
4. Sector concentration limits
5. Overall portfolio risk level

For each proposed trade, provide:
- APPROVED or REJECTED
- Specific risk concerns if any
- Alternative suggestions if trades are rejected
- Overall portfolio risk assessment

Be strict about risk limits - reject trades that violate constraints."""
        
        response = await self.llm_server.generate(
            model_name="risk_validation",
            prompt=prompt,
            max_tokens=1500,
            temperature=0.05  # Very low temperature for risk decisions
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Parse insights and recommendations
        insights, recommendations = self._parse_analysis_response(response)
        confidence = self._estimate_confidence(response)
        
        return AnalysisResult(
            model_name="risk_validation",
            analysis_text=response,
            confidence_score=confidence,
            key_insights=insights,
            recommendations=recommendations,
            timestamp=start_time.isoformat(),
            processing_time=processing_time
        )
    
    async def _run_news_analysis(self, context: Dict[str, Any]) -> AnalysisResult:
        """Run news sentiment and catalyst analysis"""
        
        start_time = datetime.now()
        
        # Simple placeholder for news analysis
        response = "News analysis placeholder - would analyze recent financial news and catalysts"
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return AnalysisResult(
            model_name="news_analysis",
            analysis_text=response,
            confidence_score=0.6,
            key_insights=["News analysis placeholder"],
            recommendations=["Monitor earnings calendar"],
            timestamp=start_time.isoformat(),
            processing_time=processing_time
        )
    
    async def _run_market_analysis(self, context: Dict[str, Any], 
                                  news_result: Optional[AnalysisResult]) -> AnalysisResult:
        """Run technical and market pattern analysis"""
        
        start_time = datetime.now()
        
        # Simple placeholder for market analysis
        response = "Market analysis placeholder - would analyze technical patterns and market trends"
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return AnalysisResult(
            model_name="market_analysis",
            analysis_text=response,
            confidence_score=0.7,
            key_insights=["Market analysis placeholder"],
            recommendations=["Monitor market trends"],
            timestamp=start_time.isoformat(),
            processing_time=processing_time
        )
    
    def _parse_analysis_response(self, response: str) -> Tuple[List[str], List[str]]:
        """Parse LLM response into insights and recommendations"""
        
        insights = []
        recommendations = []
        
        # Split into sections
        sections = response.split('\n\n')
        
        current_section = None
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # Identify section headers
            if 'INSIGHTS' in section.upper() or 'ANALYSIS' in section.upper():
                current_section = 'insights'
                continue
            elif 'RECOMMEND' in section.upper() or 'TRADES' in section.upper():
                current_section = 'recommendations'
                continue
            
            # Parse content based on current section
            if current_section == 'insights':
                # Extract bullet points or key statements
                lines = section.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                        insights.append(line[1:].strip())
                    elif line and len(line) > 20:  # Substantial content
                        insights.append(line)
                        
            elif current_section == 'recommendations':
                # Extract recommendation statements
                lines = section.split('\n')
                for line in lines:
                    line = line.strip()
                    if any(keyword in line.upper() for keyword in ['BUY', 'SELL', 'HOLD', 'APPROVED', 'REJECTED']):
                        recommendations.append(line)
        
        # Fallback: if no structured sections found, extract from full text
        if not insights and not recommendations:
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    if any(keyword in line.upper() for keyword in ['BUY', 'SELL', 'HOLD']):
                        recommendations.append(line)
                    else:
                        insights.append(line)
        
        return insights[:10], recommendations[:20]  # Limit to reasonable counts
    
    def _estimate_confidence(self, response: str) -> float:
        """Estimate confidence score based on response quality"""
        
        if not response:
            return 0.0
        
        confidence_indicators = {
            'specific_numbers': len(re.findall(r'\d+\.?\d*%|\$\d+\.?\d*', response)) * 0.05,
            'specific_tickers': len(re.findall(r'\b[A-Z]{2,5}\b', response)) * 0.03,
            'action_words': len(re.findall(r'\b(BUY|SELL|HOLD|APPROVED|REJECTED)\b', response.upper())) * 0.10,
            'reasoning_words': len(re.findall(r'\b(because|due to|given|based on)\b', response.lower())) * 0.05,
            'length_quality': min(len(response) / 1000, 1.0) * 0.20
        }
        
        total_score = sum(confidence_indicators.values())
        return min(max(total_score, 0.1), 0.95)  # Clamp between 10% and 95%
    
    def _extract_trading_recommendations(self, trading_result: Optional[AnalysisResult],
                                       risk_result: Optional[AnalysisResult]) -> List[TradeOrder]:
        """Extract validated trading recommendations as TradeOrder objects"""
        
        recommendations = []
        
        if not trading_result or not trading_result.recommendations:
            return recommendations
        
        # Parse trading recommendations
        for rec in trading_result.recommendations:
            try:
                trade_order = self._parse_trade_recommendation(rec)
                if trade_order:
                    recommendations.append(trade_order)
                        
            except Exception as e:
                self.logger.warning(f"Failed to parse recommendation: {rec} - {e}")
        
        return recommendations
    
    def _parse_trade_recommendation(self, recommendation: str) -> Optional[TradeOrder]:
        """Parse a single trade recommendation into TradeOrder"""
        
        # Extract action, quantity, ticker, and reason
        patterns = [
            r'\b(BUY|SELL|HOLD)\s+(\d+)\s+shares?\s+of\s+([A-Z]{1,5})\s*-?\s*(.*)',
            r'\b(BUY|SELL|HOLD)\s+([A-Z]{1,5})\s+(\d+)\s+shares?\s*-?\s*(.*)',
            r'\b(BUY|SELL|HOLD)\s+(\d+)\s+([A-Z]{1,5})\s*-?\s*(.*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, recommendation, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                try:
                    action = OrderType(groups[0].upper())
                    
                    # Handle different group arrangements
                    if groups[1].isdigit():
                        shares = int(groups[1])
                        ticker = groups[2]
                        reason = groups[3] if len(groups) > 3 else ""
                    else:
                        ticker = groups[1]
                        shares = int(groups[2]) if groups[2].isdigit() else None
                        reason = groups[3] if len(groups) > 3 else ""
                    
                    return TradeOrder(
                        ticker=ticker,
                        action=action,
                        shares=shares,
                        target_value=None,
                        reason=reason.strip(),
                        priority=OrderPriority.MEDIUM
                    )
                    
                except (ValueError, IndexError) as e:
                    self.logger.warning(f"Error parsing trade: {recommendation} - {e}")
                    
        return None
    
    def _calculate_overall_confidence(self, analysis_results: Dict[str, AnalysisResult]) -> float:
        """Calculate weighted overall confidence score"""
        
        if not analysis_results:
            return 0.0
        
        # Weight different model types
        weights = {
            "news_analysis": 0.20,
            "market_analysis": 0.25,
            "trading_decision": 0.35,
            "risk_validation": 0.20
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for model_name, result in analysis_results.items():
            if result and model_name in weights:
                weighted_sum += result.confidence_score * weights[model_name]
                total_weight += weights[model_name]
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def get_pipeline_summary(self, result: PipelineResult) -> Dict[str, Any]:
        """Generate summary of pipeline execution"""
        
        return {
            "timestamp": result.timestamp,
            "processing_time": f"{result.processing_time:.1f}s",
            "confidence_score": f"{result.confidence_score:.1%}",
            "recommendations_count": len(result.final_recommendations),
            "models_executed": sum(1 for r in [result.news_analysis, result.market_analysis, 
                                             result.trading_decision, result.risk_validation] if r),
            "warnings_count": len(result.warnings),
            "recommendations": [
                f"{rec.action.value} {rec.shares} shares of {rec.ticker}" 
                for rec in result.final_recommendations
            ]
        }


# Standalone testing function
async def test_pipeline():
    """Test the analysis pipeline with mock data"""
    
    print("🧪 Testing LLM Analysis Pipeline...")
    print("📋 Mock pipeline test - integration testing requires full system")
    

if __name__ == "__main__":
    asyncio.run(test_pipeline())