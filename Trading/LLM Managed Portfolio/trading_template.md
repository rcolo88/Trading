# 🤖 LLM Trading Recommendations Template

**CRITICAL: This template is designed for LLM completion. Follow ALL formatting rules exactly.**

---

## 📅 DOCUMENT HEADER
*Date: [YYYY-MM-DD]*  
*Market Conditions: [Brief 1-2 sentence market summary]*  
*Portfolio Performance: [Current vs benchmarks with specific %]*  

---

## 🛡️ RISK MANAGEMENT UPDATES

### ⚙️ Dynamic Risk Parameters
**SET STOP-LOSS [TICKER] -[XX]%** - [Specific reasoning for stop-loss level]  
**UPDATE PROFIT-TARGET [TICKER] +[XX]%** - [Specific reasoning for profit target]  
**MAX-POSITION-SIZE [XX]%** - [Overall position sizing rationale]  
**CASH-RESERVE [XX]%** - [Cash management strategy]  
**RISK-BUDGET [AGGRESSIVE|MODERATE|CONSERVATIVE]** - [Risk profile justification]  

### 🎯 Position-Specific Risk Adjustments
**SET STOP-LOSS [TICKER] -[XX]%** - [Individual position risk reasoning]  
**UPDATE PROFIT-TARGET [TICKER] +[XX]%** - [Individual target reasoning]  

---

## 📋 ORDERS SECTION

### 🔥 IMMEDIATE EXECUTION (HIGH PRIORITY)

**BUY [XXX] shares of [TICKER]** - [Detailed reasoning for purchase including catalysts, valuation, technical factors]

**SELL [XXX] shares of [TICKER]** - [Detailed reasoning for sale including risk management, profit taking, or strategy pivot]

**SELL all [XXX] shares of [TICKER]** - [Complete exit reasoning including risk factors or better opportunities]

### ⚖️ POSITION MANAGEMENT (MEDIUM PRIORITY)

**BUY [XXX] shares of [TICKER]** - [Position building rationale and allocation strategy]

**HOLD all [XXX] shares of [TICKER]** - [Hold reasoning including upcoming catalysts or maintaining strategic allocation]

**REDUCE [TICKER] by [XXX] shares** - [Position trimming reasoning and risk management]

### 📈 STRATEGIC POSITIONING (LOW PRIORITY)

**BUY [XXX] shares of [TICKER]** - [Long-term strategic positioning and allocation rationale]

**SET STOP-LOSS [TICKER] -[XX]%** - [Position-specific risk management]

**UPDATE PROFIT-TARGET [TICKER] +[XX]%** - [Revised target based on new information]

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

---

## 🤖 LLM COMPLETION INSTRUCTIONS

### ⚠️ CRITICAL PARSING REQUIREMENTS

**The trading system will automatically parse your output. Follow these rules EXACTLY or orders will fail:**

1. **Action Words**: Only use: `BUY`, `SELL`, `REDUCE`, `HOLD`, `SET STOP-LOSS`, `UPDATE PROFIT-TARGET`
2. **Ticker Format**: Always UPPERCASE (NVDA, AMD, TSLA) - never lowercase
3. **Share Quantities**: Always use exact numbers (15, 100, 250) - never "some" or "few"
4. **Order Format**: Always start with `**` and include ` - ` before reasoning
5. **Priority Sections**: Keep orders in their priority sections for proper execution flow

### 📝 EXACT SYNTAX REQUIREMENTS

#### ✅ CORRECT Order Formats:
```
**BUY 15 shares of NVDA** - AI infrastructure momentum driving growth
**SELL 10 shares of AMD** - Profit taking at resistance level
**SELL all 19 shares of SOUN** - Exit underperforming position
**HOLD all 23 shares of QS** - Maintain allocation ahead of earnings
**REDUCE TSLA by 50 shares** - Trim position after strong run
```

#### ✅ CORRECT Risk Management Formats:
```
**SET STOP-LOSS NVDA -15%** - Protect against AI sector volatility
**UPDATE PROFIT-TARGET IONS +40%** - Increase target based on pipeline progress
**MAX-POSITION-SIZE 20%** - Limit individual position risk
**CASH-RESERVE 5%** - Maintain liquidity for opportunities
**RISK-BUDGET MODERATE** - Balanced approach given market conditions
```

#### ❌ INCORRECT Formats (WILL FAIL):
```
Buy some nvda shares - AI looks good (lowercase, vague quantity)
**BUY NVDA 15 shares**: Good opportunity (wrong word order, colon instead of dash)
**Purchase 15 NVDA** → Momentum play (wrong action word, wrong separator)
**BUY 15 NVDA** Due to earnings (missing "shares of", wrong separator)
```

### 🎯 COMPLETION GUIDELINES

1. **Fill ALL placeholder sections** - Don't leave [BRACKETS] empty
2. **Use current market data** - Reference actual market conditions
3. **Be specific with reasoning** - Include catalysts, technicals, fundamentals
4. **Maintain priority order** - High priority trades execute first
5. **Consider cash flow** - Sells generate cash for buys

### 🔍 VALIDATION CHECKLIST

Before submitting, verify:
- [ ] All tickers are UPPERCASE
- [ ] All orders start with `**` and end with reasoning after ` - `
- [ ] Share quantities are specific numbers
- [ ] Priority sections are maintained
- [ ] Risk management parameters have correct +/- signs
- [ ] Date format is YYYY-MM-DD
- [ ] No placeholder brackets remain unfilled

### 🚫 COMMON PARSING ERRORS TO AVOID

1. **Mixed case tickers**: nvda, Amd, TsLa ❌ → NVDA, AMD, TSLA ✅
2. **Vague quantities**: "some shares", "a few" ❌ → "15 shares" ✅
3. **Wrong separators**: colon (:), arrow (→) ❌ → dash (-) ✅
4. **Missing word "shares"**: "BUY 15 NVDA" ❌ → "BUY 15 shares of NVDA" ✅
5. **Wrong action words**: "Purchase", "Acquire" ❌ → "BUY" ✅

### 📊 PRIORITY EXECUTION ORDER

**Orders execute in this sequence for optimal cash flow:**
1. 🔥 HIGH PRIORITY sells (generate cash)
2. ⚖️ MEDIUM PRIORITY sells & reduces  
3. 🔥 HIGH PRIORITY buys (use available cash)
4. ⚖️ MEDIUM PRIORITY buys
5. 📈 LOW PRIORITY trades
6. 👍 HOLD confirmations (no execution needed)