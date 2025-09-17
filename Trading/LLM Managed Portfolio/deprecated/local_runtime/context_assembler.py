"""
Context Assembler for Local LLM Analysis
Prepares portfolio and market data in structured format for LLM consumption

Integrates with portfolio system in local_runtime/Portfolio Scripts Schwab/
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import yfinance as yf
import pandas_market_calendars as mcal

# Add the Portfolio Scripts Schwab directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
portfolio_dir = os.path.join(current_dir, 'Portfolio Scripts Schwab')
sys.path.append(portfolio_dir)

from portfolio_manager import PortfolioManager
from schwab_data_fetcher import SchwabDataFetcher
from report_generator import ReportGenerator
from trading_models import PartialFillMode


class ContextAssembler:
    """Assembles comprehensive financial context for LLM analysis"""
    
    def __init__(self, portfolio_manager: PortfolioManager, 
                 data_fetcher: SchwabDataFetcher,
                 report_generator: ReportGenerator = None):
        """
        Initialize context assembler
        
        Args:
            portfolio_manager: Portfolio state and position management
            data_fetcher: Market data source
            report_generator: Optional report generator for enhanced metrics
        """
        self.portfolio = portfolio_manager
        self.data_fetcher = data_fetcher
        self.report_generator = report_generator or ReportGenerator(portfolio_manager, data_fetcher)
        
        # Setup logging
        self.logger = logging.getLogger('context_assembler')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def assemble_full_context(self, include_news: bool = True, 
                            lookback_days: int = 30) -> Dict[str, Any]:
        """
        Assemble comprehensive context for LLM analysis
        
        Args:
            include_news: Whether to fetch recent news data
            lookback_days: Historical data lookback period
            
        Returns:
            Dict containing structured financial context
        """
        
        self.logger.info(f"🔄 Assembling full financial context (lookback: {lookback_days} days)")
        
        context = {
            "timestamp": datetime.now().isoformat(),
            "market_session": self._get_market_session_info(),
            "portfolio_overview": self._get_portfolio_overview(),
            "position_details": self._get_position_details(),
            "market_data": self._get_market_data(),
            "performance_metrics": self._get_performance_metrics(),
            "risk_analysis": self._get_risk_analysis(),
            "sector_analysis": self._get_sector_analysis(),
            "cash_flow": self._get_cash_flow_analysis(),
            "constraints": self._get_trading_constraints()
        }
        
        # Optional components
        if include_news:
            context["news_analysis"] = self._get_news_context(lookback_days)
            
        # Add market context and trends
        context["market_context"] = self._get_market_context(lookback_days)
        context["technical_levels"] = self._get_technical_levels()
        
        self.logger.info("✅ Context assembly completed")
        return context
    
    def assemble_trading_context(self) -> Dict[str, Any]:
        """Assemble focused context specifically for trading decisions"""
        
        return {
            "timestamp": datetime.now().isoformat(),
            "portfolio_summary": self._get_portfolio_summary(),
            "available_cash": self.portfolio.cash,
            "position_limits": self._get_position_limits(),
            "recent_performance": self._get_recent_performance(),
            "market_state": self._get_current_market_state(),
            "risk_budget": self._get_risk_budget(),
            "trading_constraints": self._get_trading_constraints()
        }
    
    def assemble_risk_context(self) -> Dict[str, Any]:
        """Assemble context specifically for risk validation"""
        
        return {
            "timestamp": datetime.now().isoformat(),
            "portfolio_value": self._calculate_portfolio_value(),
            "position_concentrations": self._get_position_concentrations(),
            "cash_reserves": {
                "current_cash": self.portfolio.cash,
                "cash_percentage": self._get_cash_percentage(),
                "minimum_required": 0.05  # 5% minimum
            },
            "risk_metrics": self._get_detailed_risk_metrics(),
            "volatility_analysis": self._get_volatility_analysis(),
            "correlation_analysis": self._get_correlation_analysis()
        }
    
    def _get_market_session_info(self) -> Dict[str, Any]:
        """Get current market session information"""
        
        now = datetime.now()
        nyse = mcal.get_calendar('NYSE')
        
        # Get today's market schedule
        today = now.date()
        schedule = nyse.schedule(start_date=today, end_date=today)
        
        if not schedule.empty:
            market_open = schedule.iloc[0]['market_open'].to_pydatetime()
            market_close = schedule.iloc[0]['market_close'].to_pydatetime()
            
            return {
                "date": today.isoformat(),
                "market_open": market_open.time().isoformat(),
                "market_close": market_close.time().isoformat(),
                "is_market_day": True,
                "market_status": "open" if market_open <= now <= market_close else "closed",
                "time_to_close": str(market_close - now) if now < market_close else "closed"
            }
        
        return {
            "date": today.isoformat(),
            "is_market_day": False,
            "market_status": "closed"
        }
    
    def _get_portfolio_overview(self) -> Dict[str, Any]:
        """Get high-level portfolio overview"""
        
        total_value = self._calculate_portfolio_value()
        position_count = len([p for p in self.portfolio.holdings.values() if p.get('shares', 0) > 0])
        
        return {
            "total_value": round(total_value, 2),
            "cash_position": round(self.portfolio.cash, 2),
            "cash_percentage": round(self._get_cash_percentage() * 100, 1),
            "invested_value": round(total_value - self.portfolio.cash, 2),
            "position_count": position_count,
            "partial_fill_mode": self.portfolio.partial_fill_mode.value,
            "portfolio_id": getattr(self.portfolio, 'portfolio_id', 'local_runtime')
        }
    
    def _get_position_details(self) -> List[Dict[str, Any]]:
        """Get detailed information about each position"""
        
        positions = []
        current_prices, _, _ = self.data_fetcher.fetch_current_data(list(self.portfolio.holdings.keys()))
        
        for ticker, position in self.portfolio.holdings.items():
            shares = position.get('shares', 0)
            if shares == 0:
                continue
                
            entry_price = position.get('entry_price', 0)
            current_price = current_prices.get(ticker, entry_price)
            
            market_value = shares * current_price
            cost_basis = shares * entry_price
            unrealized_pnl = market_value - cost_basis
            pnl_percentage = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
            
            # Calculate position weight
            total_value = self._calculate_portfolio_value()
            weight = (market_value / total_value * 100) if total_value > 0 else 0
            
            positions.append({
                "ticker": ticker,
                "shares": shares,
                "entry_price": round(entry_price, 2),
                "current_price": round(current_price, 2),
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "pnl_percentage": round(pnl_percentage, 2),
                "portfolio_weight": round(weight, 1),
                "position_age_days": self._get_position_age(position)
            })
        
        # Sort by portfolio weight descending
        positions.sort(key=lambda x: x['portfolio_weight'], reverse=True)
        return positions
    
    def _calculate_portfolio_value(self) -> float:
        """Calculate total portfolio value"""
        
        try:
            tickers = list(self.portfolio.holdings.keys())
            if not tickers:
                return self.portfolio.cash
                
            current_prices, _, _ = self.data_fetcher.fetch_current_data(tickers)
            
            total_equity_value = 0
            for ticker, position in self.portfolio.holdings.items():
                shares = position.get('shares', 0)
                if shares > 0 and ticker in current_prices:
                    total_equity_value += shares * current_prices[ticker]
            
            return total_equity_value + self.portfolio.cash
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio value: {e}")
            return self.portfolio.cash
    
    def _get_cash_percentage(self) -> float:
        """Get cash as percentage of total portfolio"""
        
        total_value = self._calculate_portfolio_value()
        return self.portfolio.cash / total_value if total_value > 0 else 1.0
    
    def format_for_model(self, context: Dict[str, Any], model_type: str) -> str:
        """Format context data for specific model type"""
        
        if model_type == "trading_decision":
            return self._format_trading_context(context)
        elif model_type == "risk_validation":
            return self._format_risk_context(context)
        else:
            return json.dumps(context, indent=2)
    
    def _format_trading_context(self, context: Dict[str, Any]) -> str:
        """Format context specifically for trading decision model"""
        
        formatted = f"""PORTFOLIO ANALYSIS - {context['timestamp'][:10]}

=== PORTFOLIO OVERVIEW ===
Total Value: ${context['portfolio_overview']['total_value']:,.2f}
Cash Position: ${context['portfolio_overview']['cash_position']:,.2f} ({context['portfolio_overview']['cash_percentage']}%)
Active Positions: {context['portfolio_overview']['position_count']}

=== CURRENT POSITIONS ==="""

        for position in context['position_details'][:10]:  # Top 10 positions
            formatted += f"""
{position['ticker']}: {position['shares']} shares @ ${position['current_price']:.2f}
  Market Value: ${position['market_value']:,.2f} ({position['portfolio_weight']:.1f}% of portfolio)
  P&L: ${position['unrealized_pnl']:,.2f} ({position['pnl_percentage']:+.1f}%)
  Position Age: {position['position_age_days']} days"""

        formatted += f"""

=== MARKET CONTEXT ===
Market Session: {context['market_session']['market_status']}
Cash Available: ${context['portfolio_overview']['cash_position']:,.2f}

=== TRADING CONSTRAINTS ===
- Max position weight: 20%
- Minimum cash reserve: 5%
- Stop loss threshold: -15%
"""
        
        return formatted
    
    def _format_risk_context(self, context: Dict[str, Any]) -> str:
        """Format context for risk validation model"""
        
        formatted = f"""RISK VALIDATION REQUEST - {context['timestamp'][:10]}

=== PORTFOLIO RISK PROFILE ===
Portfolio Value: ${context['portfolio_overview']['total_value']:,.2f}
Cash Reserve: {context['portfolio_overview']['cash_percentage']:.1f}%

=== POSITION CONCENTRATIONS ===""

        for position in context['position_details'][:5]:
            risk_level = "HIGH" if position['portfolio_weight'] > 15 else "MEDIUM" if position['portfolio_weight'] > 10 else "LOW"
            formatted += f"""
{position['ticker']}: {position['portfolio_weight']:.1f}% - {risk_level} RISK"""

        formatted += f"""

=== RISK CONSTRAINTS ===
✓ Max Position Weight: 20%
✓ Min Cash Reserve: 5%
✓ Max Top-3 Concentration: 60%
"""
        return formatted
    
    # Placeholder methods for full implementation
    def _get_market_data(self) -> Dict[str, Any]:
        """Get current market data and benchmarks"""
        return {"note": "Market data placeholder"}
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get portfolio performance metrics"""
        return {"note": "Performance metrics placeholder"}
    
    def _get_risk_analysis(self) -> Dict[str, Any]:
        """Get portfolio risk analysis"""
        return {"note": "Risk analysis placeholder"}
    
    def _get_sector_analysis(self) -> Dict[str, Any]:
        """Get sector analysis"""
        return {"note": "Sector analysis placeholder"}
    
    def _get_cash_flow_analysis(self) -> Dict[str, Any]:
        """Analyze available cash and buying power"""
        return {
            "available_cash": round(self.portfolio.cash, 2),
            "cash_percentage": round(self._get_cash_percentage() * 100, 1),
            "buying_power": round(self.portfolio.cash * 0.95, 2)
        }
    
    def _get_trading_constraints(self) -> Dict[str, Any]:
        """Get current trading constraints and limits"""
        return {
            "max_position_weight": 20.0,
            "min_cash_reserve": 5.0,
            "stop_loss_threshold": -15.0,
            "partial_fill_mode": self.portfolio.partial_fill_mode.value
        }
    
    def _get_news_context(self, lookback_days: int) -> Dict[str, Any]:
        """Get recent news context (placeholder)"""
        return {"note": "News integration placeholder"}
    
    def _get_market_context(self, lookback_days: int) -> Dict[str, Any]:
        """Get broader market context and trends"""
        return {"note": "Market context placeholder"}
    
    def _get_technical_levels(self) -> Dict[str, Any]:
        """Get technical analysis levels for major positions"""
        return {"note": "Technical analysis placeholder"}
    
    def _get_position_age(self, position: Dict) -> int:
        """Calculate position age in days"""
        return 0  # Placeholder
    
    # Additional placeholder methods
    def _get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary"""
        return {"note": "Portfolio summary placeholder"}
    
    def _get_position_limits(self) -> Dict[str, Any]:
        """Get position limits"""
        return {"note": "Position limits placeholder"}
    
    def _get_recent_performance(self) -> Dict[str, Any]:
        """Get recent performance"""
        return {"note": "Recent performance placeholder"}
    
    def _get_current_market_state(self) -> Dict[str, Any]:
        """Get current market state"""
        return {"note": "Market state placeholder"}
    
    def _get_risk_budget(self) -> Dict[str, Any]:
        """Get risk budget"""
        return {"note": "Risk budget placeholder"}
    
    def _get_position_concentrations(self) -> Dict[str, Any]:
        """Get position concentrations"""
        return {"note": "Position concentrations placeholder"}
    
    def _get_detailed_risk_metrics(self) -> Dict[str, Any]:
        """Get detailed risk metrics"""
        return {"note": "Detailed risk metrics placeholder"}
    
    def _get_volatility_analysis(self) -> Dict[str, Any]:
        """Get volatility analysis"""
        return {"note": "Volatility analysis placeholder"}
    
    def _get_correlation_analysis(self) -> Dict[str, Any]:
        """Get correlation analysis"""
        return {"note": "Correlation analysis placeholder"}