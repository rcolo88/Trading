"""
Local Trading Executor - Standalone Local LLM Trading System
Orchestrates local LLM analysis pipeline to generate trading recommendations

Located in local_runtime/ with complete copy of portfolio system.
Integrates all local LLM components without modifying original Schwab directory.
"""

import os
import sys
import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

# Add the Portfolio Scripts Schwab directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
portfolio_dir = os.path.join(current_dir, 'Portfolio Scripts Schwab')
sys.path.append(portfolio_dir)

from local_llm_server import LocalLLMServer, llm_server_context
from context_assembler import ContextAssembler
from llm_analysis_pipeline import LLMAnalysisPipeline, PipelineResult
from document_generator import DocumentGenerator, DocumentGenerationConfig
from trading_models import TradeOrder, TradeResult, OrderType, OrderPriority
from portfolio_manager import PortfolioManager
from schwab_data_fetcher import SchwabDataFetcher
from report_generator import ReportGenerator


class LocalTradingExecutor:
    """
    Local LLM-powered trading executor - standalone version in local_runtime
    
    Provides complete trading workflow using local LLM analysis without
    modifying the original Portfolio Scripts Schwab directory.
    """
    
    def __init__(self, portfolio_manager: PortfolioManager, data_fetcher: SchwabDataFetcher):
        """
        Initialize local trading executor
        
        Args:
            portfolio_manager: Portfolio state and position management
            data_fetcher: Market data source (Schwab API)
        """
        self.portfolio = portfolio_manager
        self.data_fetcher = data_fetcher
        
        # Initialize components (will be created when needed)
        self.llm_server = None
        self.context_assembler = None
        self.analysis_pipeline = None
        self.document_generator = None
        
        # Configuration
        self.enabled_models = ["trading_decision", "risk_validation"]  # Start with core models
        self.force_cpu = False  # Auto-detect GPU availability
        self.quick_mode = True   # Use streamlined analysis by default
        self.generate_documents = True  # Generate documents for compatibility
        self.cleanup_old_documents = True
        
        # Setup logging
        self.logger = logging.getLogger('local_trading_executor')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def configure(self, enabled_models: List[str] = None, force_cpu: bool = False,
                 quick_mode: bool = True, generate_documents: bool = True):
        """
        Configure local trading executor
        
        Args:
            enabled_models: List of models to enable (default: trading_decision, risk_validation)
            force_cpu: Force CPU-only mode even if GPU available
            quick_mode: Use streamlined analysis (trading + risk only)
            generate_documents: Generate compatible documents for fallback
        """
        
        if enabled_models:
            self.enabled_models = enabled_models
        self.force_cpu = force_cpu
        self.quick_mode = quick_mode
        self.generate_documents = generate_documents
        
        self.logger.info(f"🔧 Configured local executor: models={self.enabled_models}, "
                        f"cpu_only={force_cpu}, quick_mode={quick_mode}")
    
    async def execute_automated_trading(self, document_path: str = None) -> List[TradeResult]:
        """
        Execute automated trading using local LLM analysis
        
        Args:
            document_path: Ignored - provided for compatibility with existing interface
            
        Returns:
            List of trade execution results
        """
        
        self.logger.info("🚀 Starting local LLM automated trading execution")
        
        try:
            # Step 1: Initialize LLM infrastructure
            await self._initialize_components()
            
            # Step 2: Run LLM analysis pipeline
            pipeline_result = await self._run_analysis_pipeline()
            
            # Step 3: Generate compatible document (optional)
            if self.generate_documents:
                await self._generate_compatible_document(pipeline_result)
            
            # Step 4: Execute validated trades
            trade_results = await self._execute_trades(pipeline_result.final_recommendations)
            
            # Step 5: Cleanup and summary
            await self._cleanup_and_summarize(pipeline_result, trade_results)
            
            return trade_results
            
        except Exception as e:
            self.logger.error(f"❌ Local trading execution failed: {e}")
            return []
    
    async def _initialize_components(self):
        """Initialize all LLM components"""
        
        self.logger.info("🔄 Initializing local LLM components...")
        
        # Initialize context assembler (lightweight, no dependencies)
        if not self.context_assembler:
            report_generator = ReportGenerator(self.portfolio, self.data_fetcher)
            self.context_assembler = ContextAssembler(
                self.portfolio, 
                self.data_fetcher, 
                report_generator
            )
        
        # Initialize document generator
        if not self.document_generator:
            config = DocumentGenerationConfig(
                filename_prefix="trading_recommendation_local",
                output_directory=os.path.join(current_dir, '..')  # Save to main project directory
            )
            self.document_generator = DocumentGenerator(self.portfolio, config)
        
        # Initialize LLM server (most resource-intensive)
        if not self.llm_server:
            self.llm_server = LocalLLMServer(enable_models=self.enabled_models)
            
            self.logger.info("🔄 Starting LLM server initialization...")
            success = await self.llm_server.initialize_models(force_cpu=self.force_cpu)
            
            if not success:
                raise RuntimeError("Failed to initialize LLM server")
            
            # Health check
            health = await self.llm_server.health_check()
            self.logger.info(f"📊 LLM Server Status: {health}")
        
        # Initialize analysis pipeline
        if not self.analysis_pipeline:
            self.analysis_pipeline = LLMAnalysisPipeline(self.llm_server, self.context_assembler)
        
        self.logger.info("✅ Local LLM components initialized successfully")
    
    async def _run_analysis_pipeline(self) -> PipelineResult:
        """Run the LLM analysis pipeline"""
        
        self.logger.info("🧠 Running local LLM analysis pipeline...")
        
        if self.quick_mode:
            self.logger.info("⚡ Using quick analysis mode (trading + risk only)")
            pipeline_result = await self.analysis_pipeline.run_quick_analysis()
        else:
            self.logger.info("🔍 Using full analysis mode (4-model pipeline)")
            pipeline_result = await self.analysis_pipeline.run_full_analysis(
                include_news=True,  # Include news analysis if available
                risk_tolerance="moderate"
            )
        
        # Log pipeline summary
        summary = self.analysis_pipeline.get_pipeline_summary(pipeline_result)
        self.logger.info(f"📊 Pipeline Summary: {summary}")
        
        return pipeline_result
    
    async def _generate_compatible_document(self, pipeline_result: PipelineResult):
        """Generate compatible trading recommendation document"""
        
        if not self.generate_documents:
            return
        
        self.logger.info("📄 Generating compatible recommendation document...")
        
        try:
            document_content, file_path = self.document_generator.generate_recommendation_document(
                pipeline_result, 
                save_to_file=True
            )
            
            # Validate document format
            validation = self.document_generator.validate_document_format(document_content)
            self.logger.info(f"✅ Document validation score: {validation['format_score']}/100")
            
            if validation['format_score'] < 75:
                self.logger.warning(f"⚠️ Document format score low: {validation}")
                
        except Exception as e:
            self.logger.error(f"❌ Document generation failed: {e}")
    
    async def _execute_trades(self, recommendations: List[TradeOrder]) -> List[TradeResult]:
        """Execute validated trading recommendations"""
        
        if not recommendations:
            self.logger.info("📋 No trading recommendations to execute")
            return []
        
        self.logger.info(f"⚡ Executing {len(recommendations)} trading recommendations...")
        
        trade_results = []
        
        # Sort recommendations by priority
        sorted_recommendations = sorted(
            recommendations, 
            key=lambda x: (x.priority.value, x.ticker)
        )
        
        for i, order in enumerate(sorted_recommendations, 1):
            try:
                self.logger.info(f"🔄 Executing trade {i}/{len(recommendations)}: "
                               f"{order.action.value} {order.shares} {order.ticker}")
                
                # Use existing portfolio execution logic
                result = await self._execute_single_trade(order)
                trade_results.append(result)
                
                # Brief pause between trades
                if i < len(sorted_recommendations):
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                self.logger.error(f"❌ Trade execution failed for {order.ticker}: {e}")
                
                # Create failed trade result
                trade_results.append(TradeResult(
                    ticker=order.ticker,
                    action=order.action,
                    shares_requested=order.shares or 0,
                    shares_executed=0,
                    execution_price=0.0,
                    executed=False,
                    execution_time=datetime.now(),
                    reason=f"Execution failed: {str(e)}"
                ))
        
        successful_trades = len([r for r in trade_results if r.executed])
        self.logger.info(f"📊 Trade execution completed: {successful_trades}/{len(trade_results)} successful")
        
        return trade_results
    
    async def _execute_single_trade(self, order: TradeOrder) -> TradeResult:
        """Execute a single trade order"""
        
        # Get current market data
        current_prices, _, quality = self.data_fetcher.fetch_current_data([order.ticker])
        
        if order.ticker not in current_prices:
            raise ValueError(f"Cannot get current price for {order.ticker}")
        
        current_price = current_prices[order.ticker]
        
        # Determine shares if not specified
        shares_to_trade = order.shares
        if not shares_to_trade and order.target_value:
            shares_to_trade = int(order.target_value / current_price)
        
        if not shares_to_trade or shares_to_trade <= 0:
            raise ValueError(f"Invalid share quantity: {shares_to_trade}")
        
        # Execute based on action
        if order.action == OrderType.BUY:
            return await self._execute_buy_order(order.ticker, shares_to_trade, current_price, order.reason)
        elif order.action == OrderType.SELL:
            return await self._execute_sell_order(order.ticker, shares_to_trade, current_price, order.reason)
        elif order.action == OrderType.HOLD:
            # HOLD orders are informational - just log them
            return TradeResult(
                ticker=order.ticker,
                action=order.action,
                shares_requested=shares_to_trade,
                shares_executed=0,  # No actual execution for HOLD
                execution_price=current_price,
                executed=True,  # Consider HOLD as "executed"
                execution_time=datetime.now(),
                reason=f"HOLD position: {order.reason}"
            )
        else:
            raise ValueError(f"Unsupported action: {order.action}")
    
    async def _execute_buy_order(self, ticker: str, shares: int, price: float, reason: str) -> TradeResult:
        """Execute buy order using portfolio manager"""
        
        # Check available cash
        required_cash = shares * price
        if required_cash > self.portfolio.cash:
            # Try partial fill based on available cash
            affordable_shares = int(self.portfolio.cash / price)
            if affordable_shares > 0 and self.portfolio.partial_fill_mode.value != "reject_partial":
                shares = affordable_shares
                self.logger.warning(f"⚠️ Partial fill: {shares} shares instead of requested amount")
            else:
                raise ValueError(f"Insufficient cash: need ${required_cash:.2f}, have ${self.portfolio.cash:.2f}")
        
        # Execute buy
        success = self.portfolio.buy_position(ticker, shares, price)
        
        if success:
            self.logger.info(f"✅ BUY executed: {shares} {ticker} @ ${price:.2f}")
        
        return TradeResult(
            ticker=ticker,
            action=OrderType.BUY,
            shares_requested=shares,
            shares_executed=shares if success else 0,
            execution_price=price,
            executed=success,
            execution_time=datetime.now(),
            reason=reason
        )
    
    async def _execute_sell_order(self, ticker: str, shares: int, price: float, reason: str) -> TradeResult:
        """Execute sell order using portfolio manager"""
        
        # Check current position
        current_position = self.portfolio.holdings.get(ticker, {})
        current_shares = current_position.get('shares', 0)
        
        if current_shares <= 0:
            raise ValueError(f"No position in {ticker} to sell")
        
        # Adjust shares if trying to sell more than owned
        shares_to_sell = min(shares, current_shares)
        if shares_to_sell < shares:
            self.logger.warning(f"⚠️ Partial sell: {shares_to_sell} shares available vs {shares} requested")
        
        # Execute sell
        success = self.portfolio.sell_position(ticker, shares_to_sell, price)
        
        if success:
            self.logger.info(f"✅ SELL executed: {shares_to_sell} {ticker} @ ${price:.2f}")
        
        return TradeResult(
            ticker=ticker,
            action=OrderType.SELL,
            shares_requested=shares,
            shares_executed=shares_to_sell if success else 0,
            execution_price=price,
            executed=success,
            execution_time=datetime.now(),
            reason=reason
        )
    
    async def _cleanup_and_summarize(self, pipeline_result: PipelineResult, trade_results: List[TradeResult]):
        """Cleanup resources and provide execution summary"""
        
        self.logger.info("🧹 Cleaning up local LLM resources...")
        
        # Shutdown LLM server to free resources
        if self.llm_server:
            await self.llm_server.shutdown()
            self.llm_server = None
            self.analysis_pipeline = None  # Depends on server
        
        # Log execution summary
        successful_trades = [r for r in trade_results if r.executed]
        failed_trades = [r for r in trade_results if not r.executed]
        
        self.logger.info("📊 LOCAL LLM TRADING EXECUTION SUMMARY")
        self.logger.info(f"   Pipeline confidence: {pipeline_result.confidence_score:.1%}")
        self.logger.info(f"   Analysis time: {pipeline_result.processing_time:.1f}s")
        self.logger.info(f"   Total recommendations: {len(pipeline_result.final_recommendations)}")
        self.logger.info(f"   Successful trades: {len(successful_trades)}")
        self.logger.info(f"   Failed trades: {len(failed_trades)}")
        
        if successful_trades:
            self.logger.info("   Executed trades:")
            for trade in successful_trades:
                self.logger.info(f"     • {trade.action.value} {trade.shares_executed} {trade.ticker} @ ${trade.execution_price:.2f}")
        
        if failed_trades:
            self.logger.info("   Failed trades:")
            for trade in failed_trades:
                self.logger.info(f"     • {trade.action.value} {trade.ticker}: {trade.reason}")
        
        if pipeline_result.warnings:
            self.logger.info(f"   Warnings: {len(pipeline_result.warnings)}")
            for warning in pipeline_result.warnings:
                self.logger.info(f"     ⚠️ {warning}")


# Utility function to create local trading executor
def create_local_trading_executor(portfolio_manager: PortfolioManager, 
                                data_fetcher: SchwabDataFetcher,
                                **config_kwargs) -> LocalTradingExecutor:
    """
    Create and configure local trading executor
    
    Args:
        portfolio_manager: Portfolio management instance
        data_fetcher: Market data fetcher
        **config_kwargs: Configuration parameters for executor
        
    Returns:
        Configured LocalTradingExecutor instance
    """
    
    executor = LocalTradingExecutor(portfolio_manager, data_fetcher)
    
    if config_kwargs:
        executor.configure(**config_kwargs)
    
    return executor


# Main execution function for standalone use
async def main():
    """Main execution function for standalone local LLM trading system"""
    
    print("🤖 Local LLM Trading System - Standalone Mode")
    print("=" * 60)
    
    try:
        # Import portfolio system components
        from portfolio_manager import PortfolioManager
        from schwab_data_fetcher import SchwabDataFetcher
        
        # Initialize portfolio system
        print("🔄 Initializing portfolio system...")
        portfolio = PortfolioManager()
        data_fetcher = SchwabDataFetcher()
        
        # Create local trading executor
        print("🔄 Creating local trading executor...")
        executor = LocalTradingExecutor(portfolio, data_fetcher)
        
        # Configure for demonstration (CPU mode, quick analysis)
        executor.configure(
            enabled_models=["trading_decision", "risk_validation"],
            force_cpu=True,
            quick_mode=True,
            generate_documents=True
        )
        
        # Execute trading workflow
        print("🚀 Starting local LLM trading execution...")
        trade_results = await executor.execute_automated_trading()
        
        print("✅ Local LLM trading execution completed")
        print(f"📊 Executed {len([r for r in trade_results if r.executed])} trades successfully")
        
    except Exception as e:
        print(f"❌ Local LLM trading system failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔄 Local LLM trading system interrupted by user")
    except Exception as e:
        print(f"❌ System error: {e}")