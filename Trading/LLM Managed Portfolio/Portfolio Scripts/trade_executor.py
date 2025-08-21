"""
Trade Execution Module
Handles document parsing, order validation, execution, and trade logging
"""

import os
import json
import glob
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from trading_models import TradeOrder, TradeResult, OrderType, OrderPriority, PartialFillMode


# PDF support
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    try:
        import PyPDF2
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False


class TradeExecutor:
    """Handles all trading operations including document parsing and order execution"""
    
    def __init__(self, portfolio_manager, data_fetcher):
        self.portfolio = portfolio_manager
        self.data_fetcher = data_fetcher
        
        # Configure trade execution logger
        self.trade_logger = logging.getLogger('trade_execution')
        self.trade_logger.setLevel(logging.INFO)
        
        # Create file handler if not already exists
        if not self.trade_logger.handlers:
            # Get the parent directory (one level up from Pieced Portfolio Scripts)
            parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
            log_file = os.path.join(parent_dir, 'trade_execution.log')
            
            handler = logging.FileHandler(log_file)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.trade_logger.addHandler(handler)
    
    def find_trading_document(self) -> Optional[str]:
        """Auto-detect trading recommendation document"""
        
        # Get the parent directory (one level up from Pieced Portfolio Scripts)
        parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
        
        # Search patterns for trading recommendation files
        search_patterns = [
            'trading_recommendation*.md',
            'trading_recommendation*.pdf', 
            'trading_recommendations*.md',
            'trading_recommendations*.pdf',
            'claude_recommendation*.md',
            'claude_recommendation*.pdf',
            'portfolio_analysis*.md',
            'portfolio_analysis*.pdf'
        ]
        
        found_files = []
        
        for pattern in search_patterns:
            search_path = os.path.join(parent_dir, pattern)
            matches = glob.glob(search_path)
            for match in matches:
                # Get file modification time to find most recent
                mod_time = os.path.getmtime(match)
                found_files.append((match, mod_time))
        
        if not found_files:
            print("❌ No trading recommendation files found!")
            print("🔍 Searched for patterns:")
            for pattern in search_patterns:
                print(f"   • {pattern}")
            return None
        
        # Sort by modification time (most recent first)
        found_files.sort(key=lambda x: x[1], reverse=True)
        
        if len(found_files) == 1:
            selected_file = found_files[0][0]
            print(f"📄 Found document: {selected_file}")
            return selected_file
        
        # Multiple files found - show options
        print(f"📄 Found {len(found_files)} trading documents:")
        for i, (filename, mod_time) in enumerate(found_files[:5], 1):  # Show top 5
            mod_date = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M')
            print(f"   {i}. {os.path.basename(filename)} (modified: {mod_date})")
        
        # Auto-select most recent
        selected_file = found_files[0][0]
        print(f"✅ Auto-selecting most recent: {os.path.basename(selected_file)}")
        
        return selected_file
    
    def parse_document(self, file_path: str) -> List[TradeOrder]:
        """Parse trading orders from markdown or PDF document"""
        
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return []
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext == '.md':
                return self._parse_markdown_document(file_path)
            elif file_ext == '.pdf':
                return self._parse_pdf_document(file_path)
            else:
                # Try to parse as text anyway
                print(f"⚠️ Unknown file type {file_ext}, attempting text parsing...")
                return self._parse_markdown_document(file_path)
                
        except Exception as e:
            print(f"❌ Error parsing document: {e}")
            return []
    
    def _parse_pdf_document(self, file_path: str) -> List[TradeOrder]:
        """Extract text from PDF and parse orders"""
        
        if not PDF_AVAILABLE:
            print("❌ PDF parsing not available. Please install PyPDF2 or pdfplumber:")
            print("   pip install pdfplumber")
            return []
        
        try:
            # Try pdfplumber first (more reliable)
            try:
                text_content = self._extract_with_pdfplumber(file_path)
            except Exception as e:
                print(f"⚠️ pdfplumber failed ({e}), trying PyPDF2...")
                text_content = self._extract_with_pypdf2(file_path)
            
            if not text_content.strip():
                print("❌ No text content extracted from PDF")
                return []
            
            print(f"📄 Extracted {len(text_content)} characters from PDF")
            return self._parse_text_content(text_content)
            
        except Exception as e:
            print(f"❌ Error extracting text from PDF: {e}")
            return []
    
    def _parse_markdown_document(self, file_path: str) -> List[TradeOrder]:
        """Parse orders from markdown document"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"📄 Loaded {len(content)} characters from markdown")
            return self._parse_text_content(content)
            
        except Exception as e:
            print(f"❌ Error reading markdown file: {e}")
            return []
    
    def _parse_text_content(self, content: str) -> List[TradeOrder]:
        """Parse trading orders from text content"""
        
        print("\n📋 Parsing trading orders...")
        
        # Extract orders section
        orders_text = self._extract_orders_section(content)
        if not orders_text:
            print("❌ No orders section found")
            return []
        
        orders = []
        order_count = 0
        
        for line in orders_text.split('\n'):
            line = line.strip()
            
            # Skip empty lines and headers
            if not line or line.startswith('#') or 'PRIORITY' in line.upper():
                continue
            
            # Detect priority sections
            current_priority = OrderPriority.MEDIUM
            if 'HIGH PRIORITY' in line.upper():
                current_priority = OrderPriority.HIGH
                continue
            elif 'MEDIUM PRIORITY' in line.upper():
                current_priority = OrderPriority.MEDIUM
                continue
            elif 'LOW PRIORITY' in line.upper():
                current_priority = OrderPriority.LOW
                continue
            
            # Try to parse as order line
            order = self._parse_order_line(line, current_priority)
            if order:
                orders.append(order)
                order_count += 1
                print(f"   ✅ Order {order_count}: {order.action.value} {order.ticker}")
        
        if not orders:
            print("❌ No valid orders found in document")
        else:
            print(f"📊 Successfully parsed {len(orders)} orders")
        
        return orders
    
    def _extract_orders_section(self, content: str) -> str:
        """Extract the orders section from document content"""
        
        # Look for sections that contain trading orders
        order_keywords = ['orders', 'trades', 'buy', 'sell', 'hold', 'reduce']
        lines = content.lower().split('\n')
        
        start_idx = None
        for i, line in enumerate(lines):
            if any(keyword in line for keyword in order_keywords):
                start_idx = i
                break
        
        if start_idx is not None:
            # Return from start_idx to end or to next major section
            return '\n'.join(content.split('\n')[start_idx:])
        
        # Fallback: return entire content
        return content
    
    def _parse_order_line(self, line: str, priority: OrderPriority) -> Optional[TradeOrder]:
        """Parse a single order line"""
        
        # Normalize line
        line = line.strip()
        if not line:
            return None
        
        # Remove bullet points and numbering
        line = re.sub(r'^[-•*]\s*', '', line)
        line = re.sub(r'^\d+\.\s*', '', line)
        
        # Extract action and ticker
        action_match = re.search(r'\b(BUY|SELL|REDUCE|HOLD)\s+([A-Z]{1,5})\b', line.upper())
        if not action_match:
            return None
        
        action_str = action_match.group(1)
        ticker = action_match.group(2)
        
        try:
            action = OrderType(action_str)
        except ValueError:
            return None
        
        # Extract shares if specified
        shares = None
        shares_match = re.search(r'(\d+)\s*shares?', line, re.IGNORECASE)
        if shares_match:
            shares = int(shares_match.group(1))
        
        # Extract dollar amount
        value = None
        value_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', line)
        if value_match:
            value = float(value_match.group(1).replace(',', ''))
        
        # Extract reason
        reason = self._extract_reason(line)
        
        return TradeOrder(
            ticker=ticker,
            action=action,
            shares=shares,
            target_value=value,
            reason=reason,
            priority=priority
        )
    
    def _extract_reason(self, line: str) -> str:
        """Extract reasoning from order line"""
        
        # Look for common reason indicators
        reason_indicators = ['-', ':', 'because', 'due to', 'reason']
        
        for indicator in reason_indicators:
            if indicator in line.lower():
                parts = line.lower().split(indicator, 1)
                if len(parts) > 1:
                    return parts[1].strip().capitalize()
        
        return ""
    
    def _extract_with_pdfplumber(self, file_path: str) -> str:
        """Extract text using pdfplumber"""
        import pdfplumber
        
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        return text
    
    def _extract_with_pypdf2(self, file_path: str) -> str:
        """Extract text using PyPDF2"""
        import PyPDF2
        
        text = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        
        return text
    
    def validate_cash_flow(self, orders: List[TradeOrder], current_prices: Dict[str, float]) -> Dict[str, any]:
        """Validate cash flow before executing trades"""
        print(f"\n💰 CASH FLOW ANALYSIS:")
        print("=" * 40)
        
        simulated_cash = self.portfolio.cash
        validation_results = {
            'feasible': True,
            'total_sells': 0,
            'total_buys': 0,
            'final_cash': 0,
            'warnings': [],
            'errors': []
        }
        
        # Separate sell and buy orders for simulation
        sell_orders = [o for o in orders if o.action == OrderType.SELL]
        buy_orders = [o for o in orders if o.action == OrderType.BUY]
        
        # Process sells first (they generate cash)
        print(f"💵 Starting cash: ${simulated_cash:.2f}")
        
        for order in sell_orders:
            if order.ticker in current_prices:
                current_price = current_prices[order.ticker]
                position = self.portfolio.get_position_info(order.ticker)
                
                if position and position['shares'] > 0:
                    shares_to_sell = order.shares if order.shares else position['shares']
                    shares_to_sell = min(shares_to_sell, position['shares'])
                    
                    proceeds = shares_to_sell * current_price
                    simulated_cash += proceeds
                    validation_results['total_sells'] += proceeds
                    
                    print(f"   📈 SELL {order.ticker}: {shares_to_sell} × ${current_price:.2f} = +${proceeds:.2f}")
                else:
                    validation_results['warnings'].append(f"No {order.ticker} position to sell")
        
        print(f"💰 Cash after sells: ${simulated_cash:.2f}")
        
        # Process buys (they consume cash)
        for order in buy_orders:
            if order.ticker in current_prices:
                current_price = current_prices[order.ticker]
                
                if order.target_value:
                    cost = order.target_value
                elif order.shares:
                    cost = order.shares * current_price
                else:
                    validation_results['warnings'].append(f"BUY {order.ticker}: No shares or value specified")
                    continue
                
                if cost <= simulated_cash:
                    simulated_cash -= cost
                    validation_results['total_buys'] += cost
                    shares = int(cost / current_price)
                    print(f"   📉 BUY {order.ticker}: {shares} × ${current_price:.2f} = -${cost:.2f}")
                else:
                    shortfall = cost - simulated_cash
                    validation_results['errors'].append(f"BUY {order.ticker}: Need ${cost:.2f}, have ${simulated_cash:.2f} (short ${shortfall:.2f})")
                    validation_results['feasible'] = False
        
        validation_results['final_cash'] = simulated_cash
        
        print(f"💵 Final projected cash: ${simulated_cash:.2f}")
        
        if validation_results['feasible']:
            print("✅ All orders are financially feasible")
        else:
            print("❌ Cash flow validation failed")
            for error in validation_results['errors']:
                print(f"   • {error}")
        
        return validation_results
    
    def execute_automated_trading(self, document_path: Optional[str] = None) -> List[TradeResult]:
        """Main method to execute automated trading from document"""
        print(f"\n{'='*60}")
        print(f"🤖 AUTOMATED TRADE EXECUTION")
        print(f"{'='*60}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # LOG: Start of execution session
        self.trade_logger.info("=" * 60)
        self.trade_logger.info("AUTOMATED TRADE EXECUTION SESSION STARTED")
        self.trade_logger.info("=" * 60)
        
        # Auto-detect document if not provided
        if document_path is None:
            document_path = self.find_trading_document()
            if not document_path:
                self.trade_logger.warning("No trading document found - execution cancelled")
                return []
        
        # Validate file exists
        if not os.path.exists(document_path):
            error_msg = f"File not found: {document_path}"
            print(f"❌ {error_msg}")
            self.trade_logger.error(error_msg)
            return []
        
        print(f"📄 Document: {os.path.basename(document_path)}")
        file_ext = os.path.splitext(document_path)[1].lower()
        print(f"📋 File type: {file_ext.upper()}")
        
        # LOG: Document being processed
        self.trade_logger.info(f"Processing document: {document_path} (Type: {file_ext.upper()})")
        
        # Parse orders from document
        orders = self.parse_document(document_path)
        
        if not orders:
            error_msg = "No valid orders found in document"
            print(f"❌ {error_msg}")
            self.trade_logger.error(error_msg)
            return []
        
        print(f"📊 Found {len(orders)} orders to process")
        self.trade_logger.info(f"Parsed {len(orders)} orders from document")
        
        # Get current market data
        current_prices, _, _ = self.data_fetcher.fetch_current_data(
            list(self.portfolio.holdings.keys()), 
            self.portfolio.benchmarks
        )
        
        if not current_prices:
            error_msg = "Failed to fetch current market data"
            print(f"❌ {error_msg}")
            self.trade_logger.error(error_msg)
            return []
        
        # Validate cash flow
        validation = self.validate_cash_flow(orders, current_prices)
        if not validation['feasible']:
            print("❌ Orders are not financially feasible - execution cancelled")
            self.trade_logger.error("Cash flow validation failed - execution cancelled")
            return []
        
        # Execute orders
        results = self.execute_orders(orders, current_prices)
        
        # Log final results
        successful_trades = len([r for r in results if r.executed])
        self.trade_logger.info(f"Execution completed: {successful_trades}/{len(results)} trades successful")
        self.trade_logger.info("=" * 60)
        
        return results
    
    def execute_orders(self, orders: List[TradeOrder], current_prices: Dict[str, float]) -> List[TradeResult]:
        """Execute parsed trading orders with proper cash flow management"""
        results = []
        
        print(f"💰 Starting cash balance: ${self.portfolio.cash:.2f}")
        
        # Execute orders using cash-flow-aware prioritization
        execution_phases = self._prioritize_orders_for_cash_flow(orders)
        
        for phase_name, phase_orders in execution_phases.items():
            if not phase_orders:
                continue
                
            print(f"\n📋 Executing {phase_name}:")
            print("-" * 30)
            
            for order in phase_orders:
                if order.action == OrderType.HOLD:
                    print(f"👍 HOLD {order.ticker} - No execution needed")
                    continue
                
                # Show cash before each trade
                print(f"💵 Cash available: ${self.portfolio.cash:.2f}")
                
                result = self._execute_single_order(order, current_prices)
                results.append(result)
                
                if result.executed:
                    old_cash = self.portfolio.cash
                    self._update_portfolio_holdings(result)
                    cash_change = self.portfolio.cash - old_cash
                    print(f"💰 Cash change: ${cash_change:+.2f} → New balance: ${self.portfolio.cash:.2f}")
                else:
                    print(f"❌ Failed: {result.error_message}")
        
        return results
    
    def _prioritize_orders_for_cash_flow(self, orders: List[TradeOrder]) -> Dict[str, List[TradeOrder]]:
        """Prioritize orders to optimize cash flow"""
        
        # Separate orders by type and priority
        high_priority_sells = [o for o in orders if o.action == OrderType.SELL and o.priority == OrderPriority.HIGH]
        medium_priority_sells = [o for o in orders if o.action == OrderType.SELL and o.priority == OrderPriority.MEDIUM]
        low_priority_sells = [o for o in orders if o.action == OrderType.SELL and o.priority == OrderPriority.LOW]
        
        high_priority_buys = [o for o in orders if o.action == OrderType.BUY and o.priority == OrderPriority.HIGH]
        medium_priority_buys = [o for o in orders if o.action == OrderType.BUY and o.priority == OrderPriority.MEDIUM]
        low_priority_buys = [o for o in orders if o.action == OrderType.BUY and o.priority == OrderPriority.LOW]
        
        reduces = [o for o in orders if o.action == OrderType.REDUCE]
        holds = [o for o in orders if o.action == OrderType.HOLD]
        
        # Execution order optimized for cash flow
        return {
            "High Priority Sells": high_priority_sells,
            "Position Reductions": reduces,
            "Medium Priority Sells": medium_priority_sells,
            "High Priority Buys": high_priority_buys,
            "Low Priority Sells": low_priority_sells,
            "Medium Priority Buys": medium_priority_buys,
            "Low Priority Buys": low_priority_buys,
            "Holds": holds
        }
    
    def _execute_single_order(self, order: TradeOrder, current_prices: Dict[str, float]) -> TradeResult:
        """Execute a single trading order"""
        
        timestamp = datetime.now()
        
        if order.ticker not in current_prices:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=None,
                executed_shares=None,
                execution_value=None,
                error_message=f"No price data available for {order.ticker}",
                timestamp=timestamp
            )
        
        current_price = current_prices[order.ticker]
        
        try:
            if order.action == OrderType.SELL:
                return self._execute_sell_order(order, current_price, timestamp)
            elif order.action == OrderType.BUY:
                return self._execute_buy_order(order, current_price, timestamp)
            elif order.action == OrderType.REDUCE:
                return self._execute_reduce_order(order, current_price, timestamp)
            else:
                return TradeResult(
                    order=order,
                    executed=False,
                    execution_price=None,
                    executed_shares=None,
                    execution_value=None,
                    error_message=f"Unknown order action: {order.action}",
                    timestamp=timestamp
                )
                
        except Exception as e:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=None,
                executed_shares=None,
                execution_value=None,
                error_message=str(e),
                timestamp=timestamp
            )
    
    def _execute_sell_order(self, order: TradeOrder, current_price: float, timestamp: datetime) -> TradeResult:
        """Execute a sell order"""
        
        position = self.portfolio.get_position_info(order.ticker)
        if not position or position['shares'] == 0:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=current_price,
                executed_shares=0,
                execution_value=0,
                error_message=f"No {order.ticker} position to sell",
                timestamp=timestamp
            )
        
        available_shares = position['shares']
        shares_to_sell = order.shares if order.shares else available_shares
        shares_to_sell = min(shares_to_sell, available_shares)
        
        execution_value = shares_to_sell * current_price
        
        print(f"📈 SELL {order.ticker}: {shares_to_sell} shares × ${current_price:.2f} = ${execution_value:.2f}")
        
        # Log the trade
        self.trade_logger.info(f"SELL {order.ticker}: {shares_to_sell} shares at ${current_price:.2f} = ${execution_value:.2f}")
        
        return TradeResult(
            order=order,
            executed=True,
            execution_price=current_price,
            executed_shares=shares_to_sell,
            execution_value=execution_value,
            error_message=None,
            timestamp=timestamp
        )
    
    def _execute_buy_order(self, order: TradeOrder, current_price: float, timestamp: datetime) -> TradeResult:
        """Execute a buy order"""
        
        # Determine shares to buy
        if order.shares:
            shares_to_buy = order.shares
            execution_value = shares_to_buy * current_price
        elif order.target_value:
            execution_value = order.target_value
            shares_to_buy = int(execution_value / current_price)
        else:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=current_price,
                executed_shares=0,
                execution_value=0,
                error_message="No shares or target value specified",
                timestamp=timestamp
            )
        
        # Check if we have enough cash
        available_cash = self.portfolio.cash - self.portfolio.min_cash_reserve
        
        if execution_value > available_cash:
            return self._handle_insufficient_cash(order, current_price, available_cash, timestamp)
        
        print(f"📉 BUY {order.ticker}: {shares_to_buy} shares × ${current_price:.2f} = ${execution_value:.2f}")
        
        # Log the trade
        self.trade_logger.info(f"BUY {order.ticker}: {shares_to_buy} shares at ${current_price:.2f} = ${execution_value:.2f}")
        
        return TradeResult(
            order=order,
            executed=True,
            execution_price=current_price,
            executed_shares=shares_to_buy,
            execution_value=execution_value,
            error_message=None,
            timestamp=timestamp
        )
    
    def _execute_reduce_order(self, order: TradeOrder, current_price: float, timestamp: datetime) -> TradeResult:
        """Execute a position reduction order"""
        
        position = self.portfolio.get_position_info(order.ticker)
        if not position or position['shares'] == 0:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=current_price,
                executed_shares=0,
                execution_value=0,
                error_message=f"No {order.ticker} position to reduce",
                timestamp=timestamp
            )
        
        available_shares = position['shares']
        
        # Default to reducing by half if no specific amount given
        if order.shares:
            shares_to_sell = min(order.shares, available_shares)
        else:
            shares_to_sell = available_shares // 2
        
        execution_value = shares_to_sell * current_price
        
        print(f"📊 REDUCE {order.ticker}: {shares_to_sell} shares × ${current_price:.2f} = ${execution_value:.2f}")
        
        # Log the trade
        self.trade_logger.info(f"REDUCE {order.ticker}: {shares_to_sell} shares at ${current_price:.2f} = ${execution_value:.2f}")
        
        return TradeResult(
            order=order,
            executed=True,
            execution_price=current_price,
            executed_shares=shares_to_sell,
            execution_value=execution_value,
            error_message=None,
            timestamp=timestamp
        )
    
    def _handle_insufficient_cash(self, order: TradeOrder, current_price: float, available_cash: float, timestamp: datetime) -> TradeResult:
        """Handle insufficient cash scenarios based on partial fill mode"""
        
        full_cost = (order.shares * current_price) if order.shares else order.target_value
        max_shares = int(available_cash / current_price)
        affordability_ratio = available_cash / full_cost
        
        print(f"⚠️  Insufficient cash for full order:")
        print(f"   Need: ${full_cost:.2f}, Have: ${available_cash:.2f}")
        print(f"   Can afford: {max_shares} shares ({affordability_ratio:.1%} of order)")
        
        if self.portfolio.partial_fill_mode == PartialFillMode.REJECT:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=current_price,
                executed_shares=0,
                execution_value=0,
                error_message=f"Insufficient cash (need ${full_cost:.2f}, have ${available_cash:.2f}) - REJECT mode",
                timestamp=timestamp
            )
        
        elif self.portfolio.partial_fill_mode == PartialFillMode.AUTOMATIC:
            if max_shares > 0:
                return self._execute_partial_fill(order, max_shares, current_price, timestamp)
            else:
                return TradeResult(
                    order=order,
                    executed=False,
                    execution_price=current_price,
                    executed_shares=0,
                    execution_value=0,
                    error_message="Insufficient cash even for 1 share",
                    timestamp=timestamp
                )
        
        elif self.portfolio.partial_fill_mode == PartialFillMode.SMART:
            if affordability_ratio >= self.portfolio.partial_fill_threshold:
                return self._execute_partial_fill(order, max_shares, current_price, timestamp)
            else:
                return self._ask_partial_fill_confirmation(order, max_shares, current_price, available_cash, affordability_ratio, timestamp)
        
        elif self.portfolio.partial_fill_mode == PartialFillMode.ASK_CONFIRMATION:
            return self._ask_partial_fill_confirmation(order, max_shares, current_price, available_cash, affordability_ratio, timestamp)
        
        else:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=current_price,
                executed_shares=0,
                execution_value=0,
                error_message="Unknown partial fill mode",
                timestamp=timestamp
            )
    
    def _execute_partial_fill(self, order: TradeOrder, shares: int, price: float, timestamp: datetime) -> TradeResult:
        """Execute a partial fill"""
        
        execution_value = shares * price
        
        print(f"📉 PARTIAL BUY {order.ticker}: {shares} shares × ${price:.2f} = ${execution_value:.2f}")
        
        # Log the partial trade
        self.trade_logger.info(f"PARTIAL BUY {order.ticker}: {shares} shares at ${price:.2f} = ${execution_value:.2f}")
        
        return TradeResult(
            order=order,
            executed=True,
            execution_price=price,
            executed_shares=shares,
            execution_value=execution_value,
            error_message=None,
            timestamp=timestamp
        )
    
    def _ask_partial_fill_confirmation(self, order: TradeOrder, max_shares: int, price: float, available_cash: float, affordability_ratio: float, timestamp: datetime) -> TradeResult:
        """Ask user for confirmation on partial fill (simplified for automated mode)"""
        
        # In automated mode, we'll automatically accept partial fills above a reasonable threshold
        if affordability_ratio >= 0.5:  # 50% or more of the order
            print(f"🤖 Auto-accepting partial fill ({affordability_ratio:.1%} of order)")
            return self._execute_partial_fill(order, max_shares, price, timestamp)
        else:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=price,
                executed_shares=0,
                execution_value=0,
                error_message=f"Partial fill rejected (only {affordability_ratio:.1%} affordable)",
                timestamp=timestamp
            )
    
    def _update_portfolio_holdings(self, result: TradeResult):
        """Update portfolio holdings after successful trade execution"""
        
        if not result.executed:
            return
        
        ticker = result.order.ticker
        shares_change = result.executed_shares
        cash_change = result.execution_value
        
        if result.order.action in [OrderType.SELL, OrderType.REDUCE]:
            # Selling: Add cash, reduce shares
            self.portfolio.add_cash(cash_change, f"{result.order.action.value} {ticker}")
            
            current_position = self.portfolio.get_position_info(ticker)
            if current_position:
                new_shares = current_position['shares'] - shares_change
                if new_shares <= 0:
                    # Position fully closed
                    self.portfolio.update_position(ticker, 0, current_position['entry_price'])
                else:
                    self.portfolio.update_position(ticker, new_shares, current_position['entry_price'])
        
        elif result.order.action == OrderType.BUY:
            # Buying: Reduce cash, increase shares
            self.portfolio.subtract_cash(cash_change, f"BUY {ticker}")
            
            current_position = self.portfolio.get_position_info(ticker)
            if current_position and current_position['shares'] > 0:
                # Adding to existing position - calculate weighted average entry price
                old_shares = current_position['shares']
                old_entry = current_position['entry_price']
                new_shares = old_shares + shares_change
                
                weighted_entry = ((old_shares * old_entry) + (shares_change * result.execution_price)) / new_shares
                self.portfolio.update_position(ticker, new_shares, weighted_entry)
            else:
                # New position
                self.portfolio.update_position(ticker, shares_change, result.execution_price)
        
        # Clean up any positions with 0 shares
        self.portfolio.cleanup_sold_positions()