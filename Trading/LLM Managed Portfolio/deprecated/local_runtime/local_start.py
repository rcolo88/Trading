#!/usr/bin/env python3
"""
Local LLM Trading System - Updated Integration Point
Now points to the full local LLM trading system in local_runtime/

This file serves as a compatibility bridge and quick start guide.
The actual system is implemented in main_local.py with full integration.
"""

import os
import sys
import asyncio

def show_system_info():
    """Show information about the local LLM trading system"""
    
    print("🤖 Local LLM Trading System")
    print("=" * 50)
    print("A complete local LLM-powered trading system that:")
    print("• Uses 4 specialized financial LLM models")
    print("• Generates trading recommendations locally")
    print("• Integrates with Schwab API for execution")
    print("• Creates compatible trading documents")
    print("• Operates entirely within local_runtime/")
    print()
    
    print("📊 Model Configuration:")
    print("• News Analysis: AdaptLLM/Llama-3-FinMA-8B-Instruct")
    print("• Market Analysis: Qwen/Qwen2.5-14B-Instruct") 
    print("• Trading Decision: deepseek-ai/DeepSeek-R1-Distill-Qwen-14B")
    print("• Risk Validation: microsoft/Phi-3-medium-4k-instruct")
    print()
    
    print("🚀 Quick Start Options:")
    print("1. Full Trading Execution:")
    print("   python main_local.py")
    print()
    print("2. Analysis Only (No Trading):")
    print("   python main_local.py --analysis-only")
    print()
    print("3. Test Components:")
    print("   python main_local.py --test-components")
    print()
    print("4. CPU Mode (No GPU Required):")
    print("   python main_local.py --force-cpu --analysis-only")
    print()
    
    print("📁 System Structure:")
    print("• main_local.py - Main system entry point")
    print("• local_llm_server.py - Multi-model LLM server")
    print("• llm_analysis_pipeline.py - 4-model analysis chain")
    print("• local_trading_executor.py - Trading execution orchestrator")
    print("• Portfolio Scripts Schwab/ - Complete portfolio system copy")
    print()


async def run_quick_demo():
    """Run a quick demonstration of the system"""
    
    print("🧪 Running Quick System Demo...")
    print()
    
    try:
        # Import the main system
        from main_local import LocalLLMTradingSystem
        
        # Initialize system
        system = LocalLLMTradingSystem()
        
        # Show portfolio summary
        summary = system.get_portfolio_summary()
        print(f"📊 Portfolio Summary:")
        print(f"   Total Value: ${summary['total_value']:,.2f}")
        print(f"   Cash: ${summary['cash']:,.2f} ({summary['cash_percentage']:.1f}%)")
        print(f"   Active Positions: {summary['active_positions']}")
        print()
        
        # Test components
        await system.test_llm_components()
        
        print("✅ Quick demo completed successfully!")
        print("   Use 'python main_local.py --help' for full options")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("   This is expected if dependencies are not installed")
        print("   Run: pip install -r installation.sh requirements")


def main():
    """Main entry point for local_start.py"""
    
    if len(sys.argv) > 1 and sys.argv[1] == '--demo':
        # Run quick demo
        asyncio.run(run_quick_demo())
    else:
        # Show system info and usage
        show_system_info()
        
        print("💡 Next Steps:")
        print("1. Review installation requirements in installation.sh")
        print("2. Install dependencies: pip install vllm transformers torch")
        print("3. Run: python main_local.py --test-components")
        print("4. For full trading: python main_local.py")
        print()
        print("Use --demo flag to run quick component test:")
        print("python local_start.py --demo")


if __name__ == "__main__":
    main()