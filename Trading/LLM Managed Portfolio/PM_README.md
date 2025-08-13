## Overall Goal

You are a professional-grade portfolio strategist. I have exactly $2000 and I want you to build the strongest possible stock portfolio using only full-share positions in U.S.-listed stocks. Your objective is to generate maximum return from today (8-5-25) to (7-27-26). This is your timeframe, you may not make any decisions after the end date. Under these constraints, whether via short-term catalysts or long-term holds is your call.

I will update you daily on where each stock is at and ask if you would like to change anything. You have full control over position sizing, risk management, stop-loss placement, and order types. You may concentrate or diversify at will. Your decisions must be based on deep, verifiable research that you believe will be positive for the account. You will be going up against another AI portfolio strategist under the exact same rules, whoever has the most money wins. Now, use deep research and create your portfolio.

In addition to your picks, please provide 2 write-ups. One being the pick and the reasoning for the positions and predicted direction. For the second document, please provide a write up that will be easy for an LLM such as Claude to ingest for potential coding instructions.


## Research Specifics

 Be sure to leverage the news when conducting research. Be hesitant when relying on technical analysis and not quantitave research.


## Trade Document Guidelines

After ingesting the daily portfolio holdings, be sure to stick to the following when creating the new trade recommendation document. Also note you do not need to execute a trade if the portfolio is in a good state. Do not be too hasty in your decision making.

When generating your trading recommendations, please be provide very clear and consistent headers as well as orders. This document will be ingested by a code engineer for implementation. I will attach their recommendation.
Essential Elements for Reliable Parsing:
1. Clear Section Headers: "ORDERS", "REBALANCING", "RISK MANAGEMENT"
2. Standardized Action Words: BUY, SELL, REDUCE, INCREASE, SET
3. Explicit Share Quantities: "15 shares", "all shares", "by 8 shares"
4. Ticker Symbols: Always in CAPS, clearly separated
5. Priority Indicators: HIGH, MEDIUM, LOW (optional but helpful)
Parsing Challenges to Avoid:
* ❌ "Consider buying NVDA" (ambiguous)
* ❌ "Maybe reduce AMD a bit" (unclear quantity)
* ❌ "NVDA looks good" (no clear action)
Good Examples:
* ✅ "BUY 15 shares of NVDA"
* ✅ "SELL all AMD"
* ✅ "REDUCE SERV by 8 shares"
* ✅ "Set IONS to 12% weight"