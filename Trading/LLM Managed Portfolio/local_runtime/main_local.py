"""
Main Local LLM Trading System Entry Point
Standalone local LLM trading system that works entirely in local_runtime/

This system:
1. Uses copied Portfolio Scripts Schwab system in local_runtime/
2. Runs all LLM analysis locally without external dependencies
3. Generates compatible trading recommendation documents
4. Executes trades through the copied portfolio system
5. Does not modify original Portfolio Scripts Schwab directory
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime

# Add the Portfolio Scripts Schwab directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
portfolio_dir = os.path.join(current_dir, 'Portfolio Scripts Schwab')
sys.path.append(portfolio_dir)

from local_trading_executor import LocalTradingExecutor, create_local_trading_executor
from portfolio_manager import PortfolioManager
from schwab_data_fetcher import SchwabDataFetcher
from market_hours import enforce_market_hours


class LocalLLMTradingSystem:
    """Main orchestrator for local LLM trading system"""
    
    def __init__(self):
        """Initialize the local LLM trading system"""
        print("🤖 Initializing Local LLM Trading System")
        print("=" * 60)
        
        # Initialize core portfolio components
        self.portfolio = PortfolioManager()
        self.data_fetcher = SchwabDataFetcher()
        self.trading_executor = None
        
        print(f"✅ Portfolio system initialized")
        print(f"   Portfolio: {len(self.portfolio.holdings)} positions")
        print(f"   Cash: ${self.portfolio.cash:.2f}")
        print(f"   Data source: {type(self.data_fetcher).__name__}")
    
    def configure_llm_system(self, enabled_models: list = None, force_cpu: bool = False,
                            quick_mode: bool = True, generate_documents: bool = True):
        """Configure the local LLM system"""
        
        # Create and configure trading executor
        self.trading_executor = create_local_trading_executor(
            portfolio_manager=self.portfolio,
            data_fetcher=self.data_fetcher,
            enabled_models=enabled_models or ["trading_decision", "risk_validation"],
            force_cpu=force_cpu,
            quick_mode=quick_mode,
            generate_documents=generate_documents
        )
        
        print(f"🔧 LLM system configured:")
        print(f"   Models: {enabled_models or ['trading_decision', 'risk_validation']}")
        print(f"   CPU mode: {force_cpu}")
        print(f"   Quick mode: {quick_mode}")
        print(f"   Generate docs: {generate_documents}")
    
    async def run_full_execution(self):
        """Run full LLM trading execution"""
        
        if not self.trading_executor:
            raise RuntimeError("LLM system not configured - call configure_llm_system() first")
        
        print(f"\n🚀 STARTING LOCAL LLM TRADING EXECUTION")
        print("=" * 50)
        
        # Execute automated trading
        trade_results = await self.trading_executor.execute_automated_trading()
        
        # Generate final report
        await self._generate_final_report(trade_results)
        
        return trade_results
    
    async def run_analysis_only(self):
        """Run LLM analysis and document generation without executing trades"""
        
        if not self.trading_executor:
            raise RuntimeError("LLM system not configured - call configure_llm_system() first")
        
        print(f"\n📊 RUNNING ANALYSIS-ONLY MODE")
        print("=" * 40)
        
        # Initialize components
        await self.trading_executor._initialize_components()
        
        # Run analysis pipeline
        pipeline_result = await self.trading_executor._run_analysis_pipeline()
        
        # Generate document
        if self.trading_executor.generate_documents:
            await self.trading_executor._generate_compatible_document(pipeline_result)
        
        # Show recommendations
        print(f"\n📋 GENERATED RECOMMENDATIONS:")
        for i, rec in enumerate(pipeline_result.final_recommendations, 1):
            print(f"   {i}. {rec.action.value} {rec.shares} shares of {rec.ticker}")
            if rec.reason:
                print(f"      Reason: {rec.reason}")
        
        # Cleanup
        if self.trading_executor.llm_server:
            await self.trading_executor.llm_server.shutdown()
        
        return pipeline_result
    
    async def test_llm_components(self):
        """Test LLM components without trading"""
        
        print(f"\n🧪 TESTING LLM COMPONENTS")
        print("=" * 30)
        
        try:
            from local_llm_server import LocalLLMServer
            from context_assembler import ContextAssembler
            from report_generator import ReportGenerator
            
            # Test context assembly
            print("🔄 Testing context assembler...")
            report_gen = ReportGenerator(self.portfolio, self.data_fetcher)
            context_assembler = ContextAssembler(self.portfolio, self.data_fetcher, report_gen)
            
            context = context_assembler.assemble_trading_context()
            print(f"✅ Context assembled: {len(context)} sections")
            
            # Test LLM server (CPU mode only for testing)
            print("🔄 Testing LLM server (CPU mode)...")
            llm_server = LocalLLMServer(enable_models=["risk_validation"])
            success = await llm_server.initialize_models(force_cpu=True)
            
            if success:
                print("✅ LLM server initialized successfully")
                
                # Test generation
                health = await llm_server.health_check()
                print(f"📊 Server health: {health}")
                
                await llm_server.shutdown()
                print("✅ LLM server shutdown completed")
            else:
                print("❌ LLM server initialization failed")
                
        except Exception as e:
            print(f"❌ Component testing failed: {e}")
            import traceback
            traceback.print_exc()
    
    async def _generate_final_report(self, trade_results):
        """Generate final execution report"""
        
        print(f"\n📊 GENERATING FINAL REPORT")
        print("=" * 40)
        
        try:
            from report_generator import ReportGenerator
            
            report_generator = ReportGenerator(self.portfolio, self.data_fetcher)
            report_data = report_generator.generate_report()
            
            if report_data:
                print("✅ Portfolio report generated successfully")
            else:
                print("❌ Portfolio report generation failed")
                
        except Exception as e:
            print(f"❌ Report generation error: {e}")
    
    def get_portfolio_summary(self):
        """Get current portfolio summary"""
        
        total_positions = len([p for p in self.portfolio.holdings.values() if p.get('shares', 0) > 0])
        
        # Calculate total value (simplified)
        total_equity = 0
        try:
            tickers = list(self.portfolio.holdings.keys())
            if tickers:
                prices, _, _ = self.data_fetcher.fetch_current_data(tickers)
                for ticker, position in self.portfolio.holdings.items():
                    shares = position.get('shares', 0)
                    if shares > 0 and ticker in prices:
                        total_equity += shares * prices[ticker]
        except:
            pass
        
        total_value = total_equity + self.portfolio.cash
        
        return {
            "total_value": total_value,
            "cash": self.portfolio.cash,
            "equity_value": total_equity,
            "cash_percentage": (self.portfolio.cash / total_value * 100) if total_value > 0 else 100,
            "active_positions": total_positions
        }


async def main():
    """Main entry point for local LLM trading system"""
    
    parser = argparse.ArgumentParser(description='Local LLM Trading System')
    parser.add_argument('--analysis-only', action='store_true',
                       help='Run analysis and generate documents without executing trades')
    parser.add_argument('--test-components', action='store_true',
                       help='Test LLM components without trading')
    parser.add_argument('--force-cpu', action='store_true',
                       help='Force CPU-only mode for LLM inference')
    parser.add_argument('--full-pipeline', action='store_true',
                       help='Use full 4-model pipeline instead of quick mode')
    parser.add_argument('--no-documents', action='store_true',
                       help='Skip document generation')
    parser.add_argument('--models', nargs='+', 
                       choices=['news_analysis', 'market_analysis', 'trading_decision', 'risk_validation'],
                       help='Specify which models to enable')
    
    args = parser.parse_args()
    
    # Market hours validation (can be disabled for testing)
    try:
        enforce_market_hours()
    except SystemExit:
        if not (args.analysis_only or args.test_components):
            raise
        print("⚠️ Market closed - running in analysis/test mode")
    
    # Initialize system
    trading_system = LocalLLMTradingSystem()
    
    # Show portfolio summary
    summary = trading_system.get_portfolio_summary()
    print(f"\n📊 CURRENT PORTFOLIO SUMMARY:")
    print(f"   Total Value: ${summary['total_value']:,.2f}")
    print(f"   Cash: ${summary['cash']:,.2f} ({summary['cash_percentage']:.1f}%)")
    print(f"   Equity: ${summary['equity_value']:,.2f}")
    print(f"   Active Positions: {summary['active_positions']}")
    
    try:
        if args.test_components:
            # Test components mode
            await trading_system.test_llm_components()
            
        else:
            # Configure LLM system
            trading_system.configure_llm_system(
                enabled_models=args.models or ["trading_decision", "risk_validation"],
                force_cpu=args.force_cpu,
                quick_mode=not args.full_pipeline,
                generate_documents=not args.no_documents
            )
            
            if args.analysis_only:
                # Analysis-only mode
                pipeline_result = await trading_system.run_analysis_only()
                print(f"\n✅ Analysis completed - {len(pipeline_result.final_recommendations)} recommendations generated")
                
            else:
                # Full execution mode
                trade_results = await trading_system.run_full_execution()
                successful_trades = len([r for r in trade_results if r.executed])
                print(f"\n✅ Trading execution completed - {successful_trades}/{len(trade_results)} trades successful")
        
        print(f"\n🎯 Local LLM Trading System completed successfully")
        
    except KeyboardInterrupt:
        print(f"\n🔄 Local LLM Trading System interrupted by user")
    except Exception as e:
        print(f"❌ Local LLM Trading System failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())