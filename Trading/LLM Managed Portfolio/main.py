#!/usr/bin/env python3
"""
LLM Managed Portfolio - Main Entry Point
Fully modular version that breaks down the original Daily_Portfolio_Script.py
into focused, manageable modules.

This orchestrates all the modular components:
- PortfolioManager: Holdings and cash management
- SchwabDataFetcher: Schwab API market data retrieval
- SchwabAccountManager: Account data synchronization
- SchwabTradeExecutor: Live order execution
- SafetyValidator: Pre-trade validation and risk management
- TradeExecutor: Document parsing and order execution
- ReportGenerator: Analysis and reporting

Usage:
    # Read-Only Operations (Available 24/7)
    python main.py --report-only                      # Generate portfolio report
    python main.py --steps                            # Run STEPS 10-step analysis (Quality/News/Thematic/Reasoning agents)
    python main.py --generate-hf-recommendations      # Generate HF AI trading recommendations
    python main.py --account-status --dry-run         # Display Schwab account summary
    python main.py --risk-summary --dry-run           # Show portfolio risk analysis
    python main.py --sync-schwab-account              # Sync local state with Schwab account
    python main.py --test-schwab-api                  # Test Schwab API connection
    python main.py --test-parser                      # Test document parsing
    python main.py --dry-run                          # Simulate trades (testing only)
    python main.py --load-previous-day                # Load positions from saved state

    # Trading Modes (Market Hours Only)
    python main.py                                    # Execute trades (uses manual_trades_override.json if enabled)
    python main.py --live-trading                     # Execute REAL trades (requires explicit flag)

Market Hours: Trading operations require market to be open (Mon-Fri 9:30AM-4PM ET).
              Read-only operations can run anytime.
"""

import argparse
import pytz
from datetime import datetime
from schwab_portfolio.core.market_hours import enforce_market_hours, is_market_open
from schwab_portfolio.core.portfolio_manager import PortfolioManager
from schwab_portfolio.schwab_integration.schwab_data_fetcher import SchwabDataFetcher
from schwab_portfolio.schwab_integration.schwab_account_manager import SchwabAccountManager
from schwab_portfolio.schwab_integration.schwab_trade_executor import SchwabTradeExecutor
from schwab_portfolio.validators.schwab_safety_validator import SafetyValidator
from schwab_portfolio.core.trade_executor import TradeExecutor
from schwab_portfolio.core.report_generator import ReportGenerator
from schwab_portfolio.config.hf_recommendation_generator import HFRecommendationGenerator
from schwab_portfolio.analysis.steps_orchestrator import STEPSOrchestrator


class LLMManagedPortfolio:
    """Main orchestrator for the modular portfolio system"""

    def __init__(self, enable_live_trading: bool = False, dry_run: bool = True):
        """
        Initialize all modular components

        Args:
            enable_live_trading: Enable Schwab live trading integration
            dry_run: If True, simulate trades without real execution (only applies if enable_live_trading=True)
        """
        # Create core modules with Schwab API
        self.portfolio = PortfolioManager()
        self.data_fetcher = SchwabDataFetcher()

        # Initialize account manager and safety validator if live trading enabled
        self.account_manager = None
        self.safety_validator = None
        self.live_executor = None

        if enable_live_trading:
            try:
                # Initialize Schwab account manager
                self.account_manager = SchwabAccountManager(
                    self.data_fetcher.client,
                    self.portfolio
                )

                # Initialize safety validator
                self.safety_validator = SafetyValidator(
                    self.account_manager,
                    self.portfolio
                )

                # Initialize live trade executor
                self.live_executor = SchwabTradeExecutor(
                    self.data_fetcher.client,
                    self.account_manager,
                    self.portfolio,
                    dry_run=dry_run
                )

                mode = "DRY-RUN" if dry_run else "LIVE"
                print(f"🚀 Live trading integration enabled ({mode} mode)")
            except Exception as e:
                print(f"⚠️  Live trading initialization failed: {e}")
                print("   Falling back to simulated trading mode")
                enable_live_trading = False

        # Create trade executor (with optional live executor)
        self.trade_executor = TradeExecutor(
            self.portfolio,
            self.data_fetcher,
            live_executor=self.live_executor
        )

        self.report_generator = ReportGenerator(self.portfolio, self.data_fetcher)

        print("✅ Modular portfolio system initialized")
        print(f"   Portfolio: {len(self.portfolio.holdings)} positions")
        print(f"   Cash: ${self.portfolio.cash:.2f}")
        print(f"   Partial Fill Mode: {self.portfolio.partial_fill_mode.value}")
        if enable_live_trading:
            print(f"   Trading Mode: {'DRY-RUN' if dry_run else 'LIVE TRADING'}")
    
    def execute_automated_trading(self, document_path: str = None):
        """Execute automated trading workflow"""
        
        print(f"\n🤖 EXECUTING AUTOMATED TRADING WORKFLOW")
        print("=" * 50)
        
        # Execute trades using the trade executor
        results = self.trade_executor.execute_automated_trading(document_path)
        
        if results:
            successful_trades = len([r for r in results if r.executed])
            print(f"✅ Trading execution completed: {successful_trades}/{len(results)} trades successful")
        else:
            print("ℹ️  No trades were executed")
        
        return results
    
    def generate_report(self, prefer_close_prices: bool = False):
        """Generate comprehensive portfolio report"""
        
        print(f"\n📊 GENERATING PORTFOLIO REPORT")
        print("=" * 40)
        
        # Generate report using the report generator
        report_data = self.report_generator.generate_report(prefer_close_prices)
        
        if report_data:
            print("✅ Portfolio report generation completed")
        else:
            print("❌ Report generation failed")
        
        return report_data
    
    def get_portfolio_summary(self):
        """Get quick portfolio summary"""
        return self.report_generator.get_portfolio_summary()


def main():
    """Main entry point with market hours validation"""

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LLM Managed Portfolio - Fully Modular Version')
    parser.add_argument('--report-only', action='store_true',
                      help='Generate portfolio report without executing any trades')
    parser.add_argument('--test-parser', action='store_true',
                      help='Test document parsing without executing trades')
    parser.add_argument('--load-previous-day', action='store_true',
                      help='Load portfolio positions from previous day performance history')
    parser.add_argument('--test-schwab-api', action='store_true',
                      help='Test Schwab API connection and functionality')
    parser.add_argument('--sync-schwab-account', action='store_true',
                      help='Sync portfolio with actual Schwab account positions')
    parser.add_argument('--live-trading', action='store_true',
                      help='Enable LIVE trading execution through Schwab API (requires explicit flag)')
    parser.add_argument('--dry-run', action='store_true',
                      help='Simulate trades with real account data (safer testing mode)')
    parser.add_argument('--account-status', action='store_true',
                      help='Display comprehensive Schwab account status')
    parser.add_argument('--risk-summary', action='store_true',
                      help='Display portfolio risk analysis')
    parser.add_argument('--generate-hf-recommendations', action='store_true',
                      help='Generate trading recommendations using HuggingFace agents (creates markdown document)')
    parser.add_argument('--steps', action='store_true',
                      help='Run complete STEPS analysis (10-step methodology with quality, news, thematic, and reasoning agents)')
    args = parser.parse_args()
    
    # Conditional market hours validation
    market_is_open = is_market_open()
    et_tz = pytz.timezone('US/Eastern')
    current_time = datetime.now(et_tz).strftime('%Y-%m-%d %H:%M:%S %Z')

    # Define read-only operations that can run anytime
    # These operations do NOT place trades - they only read data or update local state
    read_only_operations = (
        args.report_only or
        args.account_status or
        args.risk_summary or
        args.test_schwab_api or
        args.test_parser or
        args.load_previous_day or
        args.sync_schwab_account or  # Syncing just reads from Schwab and updates local state
        args.dry_run or  # Dry-run is safe for testing anytime
        args.generate_hf_recommendations or  # HF analysis and document generation (no trading)
        args.steps  # STEPS analysis generates recommendations only (no trading)
    )

    # Define operations that actually place trades and require market hours
    trading_operations = (
        args.live_trading or
        (not read_only_operations and not args.report_only)  # Full execution mode without --dry-run
    )

    if read_only_operations and not trading_operations:
        # Read-only modes: Allow anytime, but note market status
        if market_is_open:
            print(f"📊 Market is open - Read-only mode with current prices - {current_time}")
        else:
            print(f"✅ Market is closed - Read-only mode enabled - {current_time}")
            print("ℹ️  Account status and risk analysis available 24/7")
    elif trading_operations:
        # Trading operations: Require market to be OPEN
        if not market_is_open:
            print("🚫 TRADING OPERATIONS REQUIRE MARKET TO BE OPEN")
            print(f"Current time: {current_time}")
            print("Trading operations can only run during US market hours:")
            print("• Monday-Friday, 9:30 AM - 4:00 PM Eastern Time")
            print("• On days when NYSE/NASDAQ are open (no holidays)")
            print("\nRead-only operations available anytime:")
            print("  --report-only              Generate portfolio report")
            print("  --account-status           View account summary")
            print("  --risk-summary             View risk analysis")
            print("  --sync-schwab-account      Sync local state with Schwab account")
            print("  --test-schwab-api          Test API connection")
            print("  --dry-run                  Simulate trades (testing only)")
            exit(1)
        else:
            print(f"✅ Market is open - Trading mode enabled - {current_time}")
    else:
        # Default: show market status
        if market_is_open:
            print(f"📊 Market is open - {current_time}")
        else:
            print(f"✅ Market is closed - {current_time}")
    
    print("\n" + "=" * 60)
    if args.load_previous_day:
        print("🔄 LLM MANAGED PORTFOLIO - POSITION RECOVERY MODE")
    elif args.report_only:
        print("📊 LLM MANAGED PORTFOLIO - REPORT MODE (READ-ONLY)")
    elif args.test_parser:
        print("🧪 LLM MANAGED PORTFOLIO - PARSER TEST MODE")
    elif args.test_schwab_api:
        print("🔬 LLM MANAGED PORTFOLIO - SCHWAB API TEST MODE")
    elif args.sync_schwab_account:
        print("🔄 LLM MANAGED PORTFOLIO - SCHWAB ACCOUNT SYNC MODE")
    elif args.account_status:
        print("📊 LLM MANAGED PORTFOLIO - ACCOUNT STATUS MODE")
    elif args.risk_summary:
        print("🛡️  LLM MANAGED PORTFOLIO - RISK ANALYSIS MODE")
    elif args.generate_hf_recommendations:
        print("🤖 LLM MANAGED PORTFOLIO - HF RECOMMENDATION GENERATION MODE")
    elif args.steps:
        print("📊 LLM MANAGED PORTFOLIO - STEPS ANALYSIS MODE (10-STEP METHODOLOGY)")
    elif args.live_trading:
        print("🚀 LLM MANAGED PORTFOLIO - LIVE TRADING MODE")
    elif args.dry_run:
        print("🧪 LLM MANAGED PORTFOLIO - DRY-RUN MODE")
    else:
        print("🚀 LLM MANAGED PORTFOLIO - FULL EXECUTION MODE (SCHWAB API)")
    print("=" * 60)
    
    # Handle --steps mode early (doesn't need portfolio system)
    if args.steps:
        try:
            # Run complete STEPS analysis (10-step methodology)
            print("📊 Running STEPS analysis (10-step methodology)...")
            print("   ✅ Quality Agent - Fundamental quality metrics")
            print("   ✅ News Agent - Sentiment analysis")
            print("   ✅ Thematic Agent - Thematic opportunity scoring")
            print("   ✅ Reasoning Agent - Decision synthesis (BUY/SELL/HOLD)")
            print()

            # Create STEPS orchestrator
            orchestrator = STEPSOrchestrator(
                skip_thematic=False,
                skip_competitive=False,  # Optional step
                skip_valuation=False,    # Optional step
                dry_run=False  # Generate output files
            )

            # Run complete 10-step analysis
            output_path = orchestrator.run_full_analysis()

            print("\n" + "=" * 60)
            print("✅ STEPS ANALYSIS COMPLETE")
            print("=" * 60)
            print(f"\n📄 Trading recommendations: {output_path}")
            print("\n📋 Next steps:")
            print("   1. Review the generated recommendations")
            print("   2. Edit Portfolio Scripts Schwab/manual_trades_override.json")
            print("   3. Set 'enabled': true in manual_trades_override.json")
            print("   4. Execute trades with: python main.py (during market hours)")
            return  # Exit after STEPS analysis

        except Exception as e:
            print(f"\n❌ Error running STEPS analysis: {e}")
            import traceback
            traceback.print_exc()
            raise

    # Determine trading mode
    enable_live = args.live_trading or args.dry_run or args.sync_schwab_account or args.account_status or args.risk_summary
    dry_run_mode = not args.live_trading or args.dry_run  # Default to dry-run unless explicitly live

    # Create the orchestrated portfolio system
    try:
        portfolio_system = LLMManagedPortfolio(
            enable_live_trading=enable_live,
            dry_run=dry_run_mode
        )
        
        if args.load_previous_day:
            # Load positions from saved portfolio state
            print("🔄 Loading positions from saved portfolio state...")
            previous_positions = portfolio_system.portfolio.load_positions_from_previous_day()
            
            if previous_positions != portfolio_system.portfolio.holdings:
                portfolio_system.portfolio.holdings = previous_positions
                portfolio_system.portfolio.save_portfolio_state()
                print(f"✅ Portfolio positions restored from saved state")
                print(f"   Loaded {len(previous_positions)} positions")
                print(f"   Current cash: ${portfolio_system.portfolio.cash:.2f}")
                
                # Show summary of loaded positions
                for ticker, position in previous_positions.items():
                    shares = position.get('shares', 0)
                    entry_price = position.get('entry_price', 0)
                    allocation = position.get('allocation', shares * entry_price)
                    print(f"   {ticker}: {shares} shares @ ${entry_price:.2f} (${allocation:.2f})")
                
                # Generate report to update daily_portfolio_analysis.md and performance history
                print("\n📊 Generating updated portfolio report...")
                portfolio_system.generate_report()
                print("✅ Portfolio analysis files updated with restored positions")
            else:
                print("ℹ️  No changes needed - positions already current")
                # Still generate report to ensure files are current
                print("\n📊 Generating current portfolio report...")
                portfolio_system.generate_report()
                
        elif args.test_schwab_api:
            # Test Schwab API connection and functionality
            print("🔬 Testing Schwab API connection...")
            
            # Test basic API connection
            if portfolio_system.data_fetcher.client:
                print("✅ Schwab API client initialized")
                
                # Test quote fetching
                test_tickers = ['SPY', 'AAPL']
                print(f"🎯 Testing quotes for: {test_tickers}")
                current_prices, _, _ = portfolio_system.data_fetcher.fetch_current_data(test_tickers)
                
                if current_prices:
                    print("✅ Quote fetching successful:")
                    for ticker, price in current_prices.items():
                        print(f"   {ticker}: ${price:.2f}")
                else:
                    print("❌ Quote fetching failed")
                    
                # Test data quality
                quality = portfolio_system.data_fetcher.data_quality_check()
                print(f"📊 Data quality score: {quality['quality_score']}%")
                print(f"📡 Data source: {quality['api_source']}")
                
            else:
                print("❌ Schwab API client not available")
                print("📝 Please configure schwab_credentials.json with your API credentials")
                
        elif args.sync_schwab_account:
            # Sync with actual Schwab account positions
            print("🔄 Syncing with Schwab account positions...")

            if not portfolio_system.account_manager:
                print("❌ Account manager not initialized - live trading must be enabled")
                print("   Try: python main.py --sync-schwab-account --dry-run")
                return

            # Discover accounts
            accounts = portfolio_system.account_manager.discover_accounts()
            if not accounts:
                print("❌ No Schwab accounts found")
                return

            # Sync to local portfolio
            success = portfolio_system.account_manager.sync_to_local_portfolio()

            if success:
                print("\n✅ Account sync completed successfully")
                # Generate updated report
                print("\n📊 Generating updated portfolio report...")
                portfolio_system.generate_report()
            else:
                print("\n❌ Account sync failed")

        elif args.account_status:
            # Display comprehensive account status
            print("📊 Fetching Schwab account status...")

            if not portfolio_system.account_manager:
                print("❌ Account manager not initialized")
                print("   Try: python main.py --account-status --dry-run")
                return

            # Discover and display accounts
            accounts = portfolio_system.account_manager.discover_accounts()
            if not accounts:
                print("❌ No Schwab accounts found")
                return

            # Display account summary
            portfolio_system.account_manager.print_account_summary()

        elif args.risk_summary:
            # Display risk analysis
            print("🛡️  Generating portfolio risk summary...")

            if not portfolio_system.safety_validator or not portfolio_system.account_manager:
                print("❌ Safety validator not initialized")
                print("   Try: python main.py --risk-summary --dry-run")
                return

            # Ensure account is discovered
            if not portfolio_system.account_manager.account_hash:
                portfolio_system.account_manager.discover_accounts()

            # Display risk summary
            portfolio_system.safety_validator.print_risk_summary()

        elif args.test_parser:
            # Test document parsing functionality
            print("🔍 Testing document parsing...")
            document = portfolio_system.trade_executor.find_trading_document()
            if document:
                orders = portfolio_system.trade_executor.parse_document(document)
                print(f"📋 Found {len(orders)} orders in document")
                for order in orders:
                    print(f"   {order.action.value} {order.ticker} - {order.reason}")
            else:
                print("❌ No trading document found")

        elif args.generate_hf_recommendations:
            # Generate trading recommendations using HuggingFace agents
            print("🤖 Generating HuggingFace trading recommendations...")

            try:
                # Create HF recommendation generator
                hf_generator = HFRecommendationGenerator()

                # Generate full recommendation document
                filepath = hf_generator.generate_full_recommendation()

                print("\n✅ HuggingFace recommendation generation complete")
                print(f"\n📄 Review the recommendations at: {filepath}")
                print("\n📋 Next steps:")
                print("   1. Review the AI-generated trading recommendations")
                print("   2. Edit Portfolio Scripts Schwab/manual_trades_override.json")
                print("   3. Set 'enabled': true in manual_trades_override.json")
                print("   4. Execute trades with: python main.py")

            except FileNotFoundError as e:
                print(f"\n❌ {e}")
                print("   Generate portfolio report first with: python main.py --report-only")
            except Exception as e:
                print(f"\n❌ Error generating HF recommendations: {e}")
                raise

        elif args.report_only:
            # Only generate the report without executing trades
            print("🔍 Running in read-only mode - no trades will be executed")
            if market_is_open:
                print("📊 Using current market prices during trading hours")
                portfolio_system.generate_report(prefer_close_prices=False)
            else:
                print("💰 Using most recent close prices for accurate after-hours valuation")
                portfolio_system.generate_report(prefer_close_prices=True)
            
        else:
            # Full execution mode: Execute trades then generate report
            print("🚀 Running full execution mode")

            # Step 1: Execute automated trading
            trade_results = portfolio_system.execute_automated_trading()

            # Step 2: If live trading was used, reconcile with account
            if portfolio_system.live_executor and trade_results:
                print("\n🔄 Reconciling portfolio with Schwab account after trades...")
                if portfolio_system.live_executor.reconcile_positions_after_trades():
                    print("✅ Portfolio reconciled with Schwab account")
                else:
                    print("⚠️  Portfolio reconciliation incomplete - manual verification recommended")

                # Print execution summary
                portfolio_system.live_executor.print_execution_summary()

            # Step 3: Generate updated portfolio report
            portfolio_system.generate_report()

            print(f"\n✅ Portfolio management cycle completed")
            
    except Exception as e:
        print(f"❌ Error in portfolio system: {e}")
        raise


if __name__ == "__main__":
    main()