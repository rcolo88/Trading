# TradeAgent - Trading Decision Synthesis Guide

## Overview

The `TradeAgent` is a pure logic agent that synthesizes outputs from all sentiment analysis agents (News, Market, Risk) to generate concrete trade orders. **It makes no API calls** - it only applies trading rules to agent results.

## Key Features

### 1. **No API Calls** ✅
Pure synthesis of other agents' outputs - no external dependencies

### 2. **Trading Logic Rules** ✅
```python
# Profit Taking
if position_return >= 15%:
    → SELL (HIGH priority)

# Stop Loss
if position_return <= -8%:
    → SELL (HIGH priority)

# Bearish + High Risk
if market == "Bearish" AND risk == "high":
    → SELL (position-dependent priority)

# Positive + Bullish + Low Risk
if news == "positive" AND market == "Bullish" AND risk != "high":
    → BUY (high priority)
```

### 3. **Position Limits** ✅
```python
MAX_POSITION_SIZE = 20%  # Maximum per position
```
- Automatically caps buy orders to respect 20% limit
- Calculates remaining capacity for existing positions

### 4. **Priority Assignment** ✅
```python
# Signal strength → Priority
confidence >= 0.70 → HIGH
confidence >= 0.55 → MEDIUM
confidence < 0.55  → LOW

# Special cases always HIGH:
- Profit taking (>15%)
- Stop loss (<-8%)
```

### 5. **TradeOrder Compatibility** ✅
Generates `TradeOrder` objects matching existing `trade_executor.py` format:
```python
TradeOrder(
    ticker="AAPL",
    action=OrderType.BUY,
    shares=50,
    target_value=9000.0,
    reason="Strong buy signal: positive news, bullish market",
    priority=OrderPriority.HIGH,
    stop_loss=162.0,  # -8%
    profit_target=202.0  # +15%
)
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ NewsAgent   │     │ MarketAgent │     │ RiskAgent   │
│ (API calls) │     │ (API calls) │     │ (API calls) │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │
       │   NewsAnalysis    │   MarketAnalysis   │   RiskAnalysis
       └───────────────────┴────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ TradeAgent  │
                    │ (NO API)    │
                    │ Pure Logic  │
                    └──────┬──────┘
                           │
                    List[TradeOrder]
                           │
                    ┌──────▼──────┐
                    │ TradeExecutor│
                    │ (Schwab API)│
                    └─────────────┘
```

## Usage Examples

### Basic Usage

```python
from agents import TradeAgent, NewsAgent, MarketAgent, RiskAgent

# Initialize agents
news_agent = NewsAgent()
market_agent = MarketAgent()
risk_agent = RiskAgent()
trade_agent = TradeAgent()

# Read portfolio analysis
with open('daily_portfolio_analysis.md', 'r') as f:
    document = f.read()

# Run sentiment analyses (API calls)
news_analysis = news_agent.analyze_portfolio_document(document, max_items=10)
market_analysis = market_agent.analyze_portfolio_document(document)
risk_analysis = risk_agent.analyze_portfolio_document(document, portfolio_data)

# Generate trade orders (NO API calls)
portfolio_data = {
    'holdings': {
        'AAPL': {'shares': 100, 'value': 18000, 'cost_basis': 15000, 'return_pct': 0.20},
        'NVDA': {'shares': 50, 'value': 25000, 'cost_basis': 22000, 'return_pct': 0.136}
    },
    'cash': 10000,
    'total_value': 53000
}

current_prices = {'AAPL': 180.0, 'NVDA': 500.0, 'MSFT': 373.0}

orders = trade_agent.generate_orders(
    news_analysis,
    market_analysis,
    risk_analysis,
    portfolio_data,
    current_prices
)

# Print summary
summary = trade_agent.generate_summary(orders, news_analysis, market_analysis, risk_analysis)
print(summary)

# Execute orders
for order in orders:
    print(f"{order.priority.value}: {order.action.value} {order.ticker}")
    if order.shares:
        print(f"  Shares: {order.shares}")
    print(f"  Reason: {order.reason}")
```

### Integration with Existing System

```python
# In your main.py or trading script
from agents import TradeAgent, NewsAgent, MarketAgent, RiskAgent
from portfolio_manager import PortfolioManager
from schwab_data_fetcher import SchwabDataFetcher

# Initialize
portfolio = PortfolioManager()
data_fetcher = SchwabDataFetcher()
trade_agent = TradeAgent()

# Load portfolio state
portfolio.load_state()

# Run agent analyses (with API calls)
news_agent = NewsAgent()
market_agent = MarketAgent()
risk_agent = RiskAgent()

with open('daily_portfolio_analysis.md', 'r') as f:
    document = f.read()

news = news_agent.analyze_portfolio_document(document)
market = market_agent.analyze_portfolio_document(document)
risk = risk_agent.analyze_portfolio_document(document, {
    'max_position_weight': portfolio.get_max_position_weight(),
    'portfolio_volatility': portfolio.calculate_volatility(),
    'cash_percentage': portfolio.get_cash_percentage()
})

# Get current prices
tickers = list(portfolio.get_holdings().keys())
current_prices = {ticker: data_fetcher.get_current_price(ticker) for ticker in tickers}

# Generate orders (NO API calls)
orders = trade_agent.generate_orders(
    news,
    market,
    risk,
    {
        'holdings': portfolio.get_holdings(),
        'cash': portfolio.cash,
        'total_value': portfolio.get_total_value()
    },
    current_prices
)

# Log summary
summary = trade_agent.generate_summary(orders, news, market, risk)
logger.info(summary)

# Execute via existing trade_executor.py
from trade_executor import TradeExecutor
executor = TradeExecutor(portfolio, data_fetcher)

for order in orders:
    result = executor.execute_order(order)
    if result.executed:
        logger.info(f"Executed: {order.action.value} {order.ticker}")
```

## Trading Logic Details

### Signal Weighting

```python
# Weight allocation (must sum to 1.0)
News Sentiment:          0.30 (30%)
Market Overall:          0.25 (25%)
Market Position-Specific: 0.20 (20%)
Risk Assessment:         0.25 (25%)
```

### Buy Signals

```python
# Generated when:
buy_weight > sell_weight AND (buy_weight - sell_weight) > 0.1

# Enhanced for:
- Positive news (0.3 weight)
- Bullish market (0.25 weight)
- Bullish position sentiment (0.2 weight)
- Low risk environment (0.1 weight)

# Special case (0.85 confidence):
news == "positive" AND
market == "Bullish" AND
risk != "high"
```

### Sell Signals

```python
# Generated when:
sell_weight > buy_weight AND (sell_weight - buy_weight) > 0.1

# Enhanced for:
- Negative news (0.3 weight)
- Bearish market (0.25 weight)
- Bearish position sentiment (0.2 weight)
- High risk environment (0.25 weight)

# Special case (0.8 confidence):
market == "Bearish" AND
risk == "high"

# Always triggers (0.9+ confidence):
- Profit taking: return >= 15%
- Stop loss: return <= -8%
```

### Position Sizing

```python
# For BUY orders:
if strength == "strong":
    allocation = 10% of portfolio
elif strength == "moderate":
    allocation = 5% of portfolio
else:  # weak
    allocation = 3% of portfolio

# Capped at:
max_allocation = min(calculated_allocation, remaining_capacity_to_20%)
```

## Priority Rules

```python
# HIGH Priority (execute first)
- Profit taking (>15% return)
- Stop loss (<-8% return)
- Strong signals (confidence >= 0.70)

# MEDIUM Priority
- Moderate signals (0.55 <= confidence < 0.70)

# LOW Priority (execute last)
- Weak signals (confidence < 0.55)
```

## Output Format

### TradeOrder Structure

```python
@dataclass
class TradeOrder:
    ticker: str                     # "AAPL"
    action: OrderType               # BUY, SELL, REDUCE, HOLD
    shares: Optional[int]           # 50 (or None for market order)
    target_value: Optional[float]   # 9000.0 (target $ amount)
    reason: str                     # Human-readable explanation
    priority: OrderPriority         # HIGH, MEDIUM, LOW
    limit_price: Optional[float]    # Not used currently
    stop_loss: Optional[float]      # 162.0 (calculated from -8%)
    profit_target: Optional[float]  # 202.0 (calculated from +15%)
```

### Example Orders

```python
[
    TradeOrder(
        ticker="AAPL",
        action=OrderType.SELL,
        shares=100,
        reason="Profit taking: 20.0% return exceeds 15.0% threshold",
        priority=OrderPriority.HIGH,
        stop_loss=None,
        profit_target=None
    ),
    TradeOrder(
        ticker="MSFT",
        action=OrderType.BUY,
        shares=26,
        target_value=9730.0,
        reason="Strong buy signal: positive news, bullish market",
        priority=OrderPriority.HIGH,
        stop_loss=343.16,
        profit_target=428.95
    ),
    TradeOrder(
        ticker="NVDA",
        action=OrderType.BUY,
        shares=10,
        target_value=5000.0,
        reason="Moderate buy signal: bullish market",
        priority=OrderPriority.MEDIUM,
        stop_loss=460.0,
        profit_target=575.0
    )
]
```

## Configuration

### Adjustable Parameters

Edit in `trade_agent.py`:

```python
class TradeAgent:
    # Trading thresholds
    MAX_POSITION_SIZE = 0.20           # 20% max per position
    PROFIT_TAKE_THRESHOLD = 0.15       # 15% profit target
    STOP_LOSS_THRESHOLD = -0.08        # -8% stop loss

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.70   # High priority
    MEDIUM_CONFIDENCE_THRESHOLD = 0.55 # Medium priority

    # Position sizing
    STRONG_ALLOCATION = 0.10   # 10% for strong signals
    MODERATE_ALLOCATION = 0.05 # 5% for moderate
    WEAK_ALLOCATION = 0.03     # 3% for weak
```

### Customizing Signal Weights

Edit in `_make_trade_decision()`:

```python
# Default weights
news_weight = 0.30
market_overall_weight = 0.25
market_position_weight = 0.20
risk_weight = 0.25

# Custom example (must sum to 1.0):
news_weight = 0.40  # Increase news importance
market_overall_weight = 0.20
market_position_weight = 0.15
risk_weight = 0.25
```

## Testing

Run the comprehensive test suite:

```bash
cd "Portfolio Scripts Schwab"
python test_trade_agent.py
```

### Test Coverage

1. ✅ Profit taking (>15%)
2. ✅ Stop loss (<-8%)
3. ✅ Bearish + high risk → SELL
4. ✅ Positive news + bullish → BUY
5. ✅ Position size limits (20%)
6. ✅ Priority assignment
7. ✅ Insufficient signals → HOLD
8. ✅ Summary generation

## Error Handling

The TradeAgent never crashes:

```python
# No API calls = no API failures
# All inputs are optional:

if news_analysis is None:
    # Skip news signals

if market_analysis is None:
    # Skip market signals

if risk_analysis is None:
    # Skip risk signals

if no signals:
    # Return empty list (HOLD)
```

## Best Practices

1. **Always run sentiment agents first**: TradeAgent needs their outputs
2. **Provide current prices**: Enables accurate share calculations
3. **Include portfolio data**: Required for position sizing and profit/loss calculations
4. **Review summary**: Generated summary explains all decisions
5. **Sort by priority**: Orders are pre-sorted but verify in executor
6. **Monitor thresholds**: Adjust profit take / stop loss based on market conditions
7. **Validate orders**: Check for sufficient cash before execution

## Integration Checklist

- [ ] Initialize TradeAgent (no API token needed)
- [ ] Run NewsAgent, MarketAgent, RiskAgent first
- [ ] Collect portfolio data (holdings, cash, total_value)
- [ ] Get current prices for all tickers
- [ ] Call `generate_orders()` with all inputs
- [ ] Review `generate_summary()` output
- [ ] Execute orders via existing `trade_executor.py`
- [ ] Log results

## Summary

The TradeAgent provides:

✅ **Zero API calls** - Pure logic synthesis
✅ **Profit taking** at 15% return
✅ **Stop loss** at -8% return
✅ **20% position limit** enforcement
✅ **Priority sorting** (HIGH → MEDIUM → LOW)
✅ **Compatible TradeOrder format** for existing system
✅ **Configurable thresholds** for customization
✅ **Comprehensive testing** with 8 test cases
✅ **Never crashes** - graceful handling of missing inputs

Perfect for integrating HuggingFace sentiment analysis into your Schwab trading system!
