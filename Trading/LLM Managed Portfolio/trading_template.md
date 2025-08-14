# Trading Recommendations Template

*Date: [CURRENT_DATE]*
*Market Conditions: [BRIEF_MARKET_SUMMARY]*
*Portfolio Performance: [CURRENT_PERFORMANCE_VS_BENCHMARKS]*

## RISK MANAGEMENT UPDATES

### Dynamic Risk Parameters
**SET STOP-LOSS [TICKER] [PERCENTAGE]%** - [Reasoning for stop-loss level]
**UPDATE PROFIT-TARGET [TICKER] [PERCENTAGE]%** - [Reasoning for profit target]
**MAX-POSITION-SIZE [PERCENTAGE]%** - [Overall position sizing rationale]
**CASH-RESERVE [PERCENTAGE]%** - [Cash management strategy]
**RISK-BUDGET [AGGRESSIVE|MODERATE|CONSERVATIVE]** - [Risk profile justification]

### Position-Specific Risk Adjustments
**SET STOP-LOSS [TICKER] [PERCENTAGE]%** - [Individual position risk reasoning]
**UPDATE PROFIT-TARGET [TICKER] [PERCENTAGE]%** - [Individual target reasoning]

## ORDERS

### IMMEDIATE EXECUTION (HIGH PRIORITY)

**BUY [NUMBER] shares of [TICKER]** - [Detailed reasoning for purchase including catalysts, valuation, technical factors]

**SELL [NUMBER] shares of [TICKER]** - [Detailed reasoning for sale including risk management, profit taking, or strategy pivot]

**SELL all [NUMBER] shares of [TICKER]** - [Complete exit reasoning including risk factors or better opportunities]

### POSITION MANAGEMENT (MEDIUM PRIORITY)

**BUY [NUMBER] shares of [TICKER]** - [Position building rationale and allocation strategy]

**HOLD all [NUMBER] shares of [TICKER]** - [Hold reasoning including upcoming catalysts or maintaining strategic allocation]

**REDUCE [TICKER] by [NUMBER] shares** - [Position trimming reasoning and risk management]

### STRATEGIC POSITIONING (LOW PRIORITY)

**BUY [NUMBER] shares of [TICKER]** - [Long-term strategic positioning and allocation rationale]

**SET STOP-LOSS [TICKER] [PERCENTAGE]%** - [Position-specific risk management]

**UPDATE PROFIT-TARGET [TICKER] [PERCENTAGE]%** - [Revised target based on new information]

## MARKET ANALYSIS & RATIONALE

### Current Market Environment
[Analysis of current market conditions, volatility, sector rotation, macroeconomic factors]

### Catalyst Calendar
[Upcoming events, earnings, FDA approvals, product launches, economic data that could impact positions]

### Risk Assessment
[Current portfolio risk level, concentration analysis, correlation risks, market exposure]

### Performance Attribution
[Analysis of recent performance drivers, sector allocation, individual position contributions]

## STRATEGIC ALLOCATION TARGETS

### Target Portfolio Composition
- **Growth/Momentum**: [PERCENTAGE]%
- **Value/Cyclical**: [PERCENTAGE]%
- **Defensive/Quality**: [PERCENTAGE]%
- **Speculative/Catalyst**: [PERCENTAGE]%
- **Cash Reserve**: [PERCENTAGE]%

### Sector Allocation Targets
- **Technology**: [PERCENTAGE]%
- **Healthcare/Biotech**: [PERCENTAGE]%
- **Energy**: [PERCENTAGE]%
- **Financial**: [PERCENTAGE]%
- **Consumer**: [PERCENTAGE]%
- **Other**: [PERCENTAGE]%

## EXECUTION NOTES

### Cash Flow Management
[Strategy for managing cash flows, including proceeds from sales and funding for purchases]

### Timing Considerations
[Market timing factors, earnings calendars, economic events that might affect execution]

### Partial Fill Instructions
[Guidance on handling partial fills for large positions or limited cash scenarios]

---

## TEMPLATE INSTRUCTIONS FOR LLM:

### Required Format Elements:
1. **Use exact action words**: BUY, SELL, HOLD, SET STOP-LOSS, UPDATE PROFIT-TARGET
2. **Specify exact quantities**: "15 shares of NVDA" not "some NVDA shares"
3. **Use ticker symbols in CAPS**: NVDA, IONS, AMD (not lowercase)
4. **Include priority levels**: HIGH PRIORITY, MEDIUM PRIORITY, LOW PRIORITY
5. **Provide detailed reasoning**: Each order must include specific rationale

### Risk Management Syntax:
- **Stop-Loss**: `SET STOP-LOSS NVDA -15%` (negative percentage)
- **Profit Target**: `UPDATE PROFIT-TARGET IONS +40%` (positive percentage)
- **Position Limits**: `MAX-POSITION-SIZE 20%` (maximum single position)
- **Cash Reserve**: `CASH-RESERVE 5%` (minimum cash to maintain)
- **Risk Profile**: `RISK-BUDGET MODERATE` (AGGRESSIVE/MODERATE/CONSERVATIVE)

### Order Syntax Examples:
- **Buy Order**: `BUY 15 shares of NVDA - AI infrastructure momentum`
- **Sell Order**: `SELL 10 shares of AMD - Profit taking at resistance`
- **Sell All**: `SELL all 19 shares of SOUN - Exit underperforming position`
- **Hold**: `HOLD all 23 shares of QS - Maintain allocation ahead of earnings`

### Parsing Requirements:
- Each order must be on its own line
- Start orders with ** (double asterisk)
- Include dash (-) before reasoning
- Use specific share quantities, not percentages
- Maintain consistent ticker symbol formatting

### Priority Guidelines:
- **HIGH PRIORITY**: Risk management, immediate market opportunities, stop-loss triggers
- **MEDIUM PRIORITY**: Portfolio rebalancing, position adjustments, catalyst positioning
- **LOW PRIORITY**: Long-term strategic moves, minor allocation adjustments