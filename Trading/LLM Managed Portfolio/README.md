# Daily Portfolio Script

A Python-based automated portfolio tracking and analysis system designed for systematic daily trading decisions using AI-powered portfolio management.

## Overall Goal

You are a professional-grade portfolio strategist. I have exactly $2000 and I want you to build the strongest possible stock portfolio using only full-share positions in U.S.-listed stocks. Your objective is to generate maximum return from today (8-5-25) to (7-30-25). This is your timeframe, you may not make any decisions after the end date. Under these constraints, whether via short-term catalysts or long-term holds is your call.

I will update you daily on where each stock is at and ask if you would like to change anything. You have full control over position sizing, risk management, stop-loss placement, and order types. You may concentrate or diversify at will. Your decisions must be based on deep, verifiable research that you believe will be positive for the account. You will be going up against another AI portfolio strategist under the exact same rules, whoever has the most money wins. Now, use deep research and create your portfolio.

In addition to your picks, please provide 2 write-ups. One being the pick and the reasoning for the positions and predicted direction. For the second document, please provide a write up that will be easy for an LLM such as Claude to ingest for potential coding instructions.

## Features

- **Real-time Portfolio Tracking**: Monitor current values, P&L, and position weights
- **Benchmark Comparison**: Performance vs S&P 500 (SPY) and Russell 2000 (IWM)
- **Risk Management Alerts**: Automated stop-loss and profit target notifications
- **Weight Drift Analysis**: Track deviation from target allocations
- **Volume Anomaly Detection**: Identify unusual trading activity
- **Performance Charting**: Visual comparison against market benchmarks
- **Historical Metrics Export**: CSV tracking for trend analysis
- **AI-Optimized Output**: Formatted text file for Claude analysis

## Installation & Setup

### Prerequisites
- Python 3.8+
- Internet connection for market data

### Dependencies
```bash
pip install yfinance pandas numpy matplotlib os datetime
```

### Quick Start
```bash
python Daily_Portfolio_Script.py
```

## Daily Workflow

### Morning Routine (Every Trading Day)

#### Step 1: Generate Daily Analysis
**Time**: After market open (9:30 AM ET) or during lunch break (12:00-1:00 PM ET)

```bash
cd "LLM Managed Portfolio"
python Daily_Portfolio_Script.py
```

**What happens:**
- Script fetches current market prices for all positions
- Calculates P&L, weight drift, and benchmark performance
- Generates risk alerts and volume anomalies
- Creates performance chart comparing portfolio vs S&P 500 vs Russell 2000
- Exports historical metrics to CSV
- Produces `portfolio_analysis_output.txt` for AI analysis

#### Step 2: Upload Analysis to Claude
**Platform**: Claude.ai chat interface

**Method A** (Recommended): 
- Upload the generated `portfolio_analysis_output.txt` file directly

**Method B** (Alternative):
- Copy contents of `portfolio_analysis_output.txt`
- Paste into Claude chat

**What to expect from Claude:**
- Position-specific buy/sell/hold recommendations
- Risk management adjustments
- Stop-loss and profit target updates
- Market outlook and catalyst analysis
- Rebalancing suggestions based on weight drift

#### Step 3: Implement Trading Decisions
**Based on Claude's recommendations, execute trades through your broker**

**Immediate Actions:**
- **SELL signals**: Execute market orders for recommended position reductions
- **BUY signals**: Execute market orders for recommended position additions  
- **STOP-LOSS hits**: Close positions that have triggered risk alerts
- **PROFIT TARGETS**: Take partial or full profits on winners

**Position Management:**
- Update stop-loss orders based on new recommendations
- Adjust position sizes if significant weight drift detected
- Add new positions if Claude recommends portfolio changes

#### Step 4: Update Script with Portfolio Changes
**After executing any trades, update the script to reflect new positions**

### Making Portfolio Changes in the Script

#### Adding a New Position
1. **Add to holdings dictionary** (around line 15):
```python
self.holdings = {
    # ... existing positions ...
    'NVDA': {'shares': 5, 'entry_price': 125.50, 'allocation': 627.50}  # New position
}
```

2. **Update total investment**:
```python
self.total_investment = 2592.08  # New total after adding $627.50 position
```

3. **Update cash**:
```python
self.cash = 0.00  # Reduce cash by amount invested
```

#### Reducing/Removing a Position
1. **Update shares** (if partial sale):
```python
'SERV': {'shares': 15, 'entry_price': 10.15, 'allocation': 152.25}  # Sold 8 shares
```

2. **Remove completely** (if full sale):
```python
self.holdings = {
    # Remove the entire line for the sold position
    # 'SERV': {'shares': 23, 'entry_price': 10.15, 'allocation': 233.45},  # DELETE THIS LINE
}
```

3. **Update cash**:
```python
self.cash = 116.67  # Add proceeds from sale (15 shares × $12.50 - 8 shares × $10.15)
```

#### Example: Complete Position Change
**Scenario**: Claude recommends selling all SERV (23 shares at $12.50) and buying NVDA (5 shares at $125.50)

**Before:**
```python
self.holdings = {
    'SERV': {'shares': 23, 'entry_price': 10.15, 'allocation': 233.45},
    # ... other positions
}
self.cash = 35.42
```

**After:**
```python
self.holdings = {
    'NVDA': {'shares': 5, 'entry_price': 125.50, 'allocation': 627.50},
    # ... other positions (SERV removed)
}
self.cash = 95.92  # Original cash + SERV sale proceeds - NVDA purchase
```

### Current Script Capabilities

#### ✅ What the Script Can Handle:
- **Position tracking**: Any number of positions with any ticker symbols
- **Flexible allocations**: Different share counts and entry prices
- **Cash management**: Tracks available cash for new positions
- **Automatic calculations**: All P&L, weights, and metrics update automatically
- **Historical tracking**: Maintains performance history in CSV format

#### ❌ What Requires Manual Updates:
- **Adding new positions**: Must manually edit holdings dictionary
- **Removing positions**: Must manually delete from holdings dictionary
- **Share count changes**: Must manually update after partial sales
- **Entry price tracking**: Script uses original entry prices for cost basis

#### 🔧 Planned Enhancements:
- **Trade execution integration**: Direct broker API connectivity
- **Automated position updates**: Parse trade confirmations
- **Dynamic rebalancing**: Automatic buy/sell recommendations
- **Stop-loss automation**: Automatic order placement

### Weekly Procedures

#### Friday After Market Close
- **Performance Review**: Analyze weekly returns vs benchmarks
- **Risk Assessment**: Review position concentration and correlation
- **Catalyst Calendar**: Update upcoming earnings/events for next week
- **Stop-Loss Review**: Adjust levels based on volatility changes

#### Weekend Planning
- **Research Updates**: Review analyst reports and news for holdings
- **Market Outlook**: Assess macro factors for coming week
- **Rebalancing Needs**: Plan any significant portfolio adjustments
- **Cash Management**: Optimize cash allocation for opportunities

### Monthly Procedures

#### Comprehensive Portfolio Review
- **Performance Analysis**: Calculate Sharpe ratio, maximum drawdown
- **Goal Assessment**: Progress toward December 27, 2025 target
- **Strategy Refinement**: Adjust approach based on market conditions
- **Risk Management Update**: Review and adjust all stop-loss levels

## Output Files Generated

1. **`portfolio_analysis_output.txt`**: Formatted for Claude AI analysis
2. **`portfolio_historical_metrics.csv`**: Daily performance tracking
3. **Performance chart**: Visual benchmark comparison (displayed)
4. **Console output**: Real-time analysis summary

## Troubleshooting

### Common Issues

**Data Fetch Errors:**
- Check internet connection and market hours
- Some tickers may be temporarily unavailable
- Script continues with last known prices

**VIX Data Issues:**
- Script attempts multiple VIX data sources
- Continues without VIX if unavailable
- Does not affect portfolio analysis

**Chart Display Problems:**
- Requires matplotlib backend
- May need X11 forwarding for remote systems
- Charts save to file if display unavailable

### Performance Optimization

**Faster Data Retrieval:**
- Script caches recent data
- Parallel API calls for multiple tickers
- Graceful degradation on API limits

**Memory Management:**
- Historical CSV automatically manages size
- Old chart files can be safely deleted
- Price data refreshed daily

## Competitive Edge

This systematic approach provides several advantages in the AI vs AI portfolio competition:

1. **Daily Optimization**: Continuous refinement based on market conditions
2. **Risk Management**: Automated alerts prevent large losses
3. **Data-Driven Decisions**: Quantitative analysis removes emotional bias  
4. **Benchmark Awareness**: Always aware of relative performance
5. **Catalyst Tracking**: Positioned for upcoming events and earnings
6. **Flexible Execution**: Can quickly adapt to changing market conditions

The combination of automated analysis, AI-powered decision making, and systematic execution creates a professional-grade portfolio management system optimized for maximum returns within the competition timeframe.

## Competition Timeline

- **Start Date**: August 5, 2025
- **End Date**: December 27, 2025  
- **Duration**: 144 calendar days / ~102 trading days
- **Goal**: Maximum absolute return vs competing AI strategist

Success metrics: Total portfolio value on December 27, 2025. Winner takes all.