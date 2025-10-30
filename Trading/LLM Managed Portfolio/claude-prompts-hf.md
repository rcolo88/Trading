# Step-by-Step Claude Prompts for HuggingFace Integration
## Complete Guide to Replace Claude in Your Schwab Trading System

### How to Use This Guide
1. Copy each prompt exactly as shown
2. Paste into a new Claude conversation
3. Save the generated code in the specified location
4. Test each component before moving to the next
5. Keep all conversations for reference

---

## 📁 PROMPT 1: Project Setup and Configuration

```
I need to integrate HuggingFace models into my existing Schwab trading system located in "Portfolio Scripts Schwab/". The system currently:
- Generates daily_portfolio_analysis.md with portfolio analysis
- Uses Claude to analyze this file and create trading recommendations
- Parses the recommendations and executes trades via Schwab API

Create a complete project setup including:

1. A folder structure to add to my existing system:
   Portfolio Scripts Schwab/
   ├── agents/           [NEW]
   │   ├── __init__.py
   │   └── [agent files]
   ├── hf_config.py     [NEW]
   └── hf_agent_system.py [NEW]

2. Create hf_config.py with:
   - HuggingFace API configuration (no token needed for free models)
   - These exact model configurations:
     * News: mrm8488/distilroberta-finetuned-financial-news-sentiment
     * Market: StephanAkkerman/FinTwitBERT  
     * Risk: ProsusAI/finbert
     * Tone: yiyanghkust/finbert-tone
   - Trading parameters: max_position=0.20, min_cash=100
   - API retry settings: 3 retries, exponential backoff

3. Create requirements_hf.txt for new dependencies

Make everything compatible with my existing trading_models.py that has TradeOrder, OrderType, and OrderPriority classes.
```

---

## 📡 PROMPT 2: Base HuggingFace Agent Class

```
Create agents/base_agent.py for my HuggingFace integration. This base class should:

1. Handle HuggingFace Inference API calls to text-classification models
2. Work with free tier (no auth token required, but support token if provided)
3. Implement smart retry logic:
   - 503 errors (model loading): wait 20-30 seconds and retry
   - 429 errors (rate limit): respect Retry-After header
   - Network errors: exponential backoff
   - Max 3 retries before giving up

4. Include simple caching:
   - In-memory cache with 5-minute TTL
   - Cache key based on model + input text hash
   - Optional cache bypass parameter

5. Response parsing for classification models:
   - Handle [{"label": "positive", "score": 0.95}] format
   - Extract top prediction
   - Return None on errors (never crash)

6. Comprehensive logging using Python's logging module

Include proper type hints and docstrings. The class should be inherited by specific agents.
```

---

## 📰 PROMPT 3: News Sentiment Analysis Agent

```
Create agents/news_agent.py that analyzes financial news using HuggingFace. Requirements:

1. Extend the base_agent.py class
2. Use model: mrm8488/distilroberta-finetuned-financial-news-sentiment
3. Parse daily_portfolio_analysis.md to find news/events sections using regex
4. Extract and analyze individual news items (limit 10 to avoid API overload)
5. Extract stock tickers from text:
   - Handle formats: $AAPL, AAPL, (AAPL), "Apple (AAPL)"
   - Filter out common words that look like tickers (A, I, FOR, etc.)
   - Return unique ticker list

6. Return structured analysis:
   {
     "sentiment": "positive/negative/neutral",
     "confidence": 0.0-1.0,
     "tickers": ["AAPL", "NVDA"],
     "breakdown": {"positive": 0.7, "negative": 0.2, "neutral": 0.1},
     "news_items": 5
   }

7. Aggregate multiple news items intelligently (weighted by confidence)

Include error handling that returns neutral sentiment on any failures.
```

---

## 📈 PROMPT 4: Market Sentiment Analysis Agent

```
Create agents/market_agent.py for market sentiment analysis:

1. Extend base_agent.py
2. Use model: StephanAkkerman/FinTwitBERT
3. Extract market commentary from daily_portfolio_analysis.md:
   - Look for sections: "Market Analysis", "Technical Overview", "Market Conditions"
   - Also analyze position performance descriptions

4. Handle FinTwitBERT's output labels: "Bearish", "Bullish", "Neutral"
5. Analyze both overall market text and position-specific commentary
6. Calculate sentiment strength based on score confidence

7. Return structure:
   {
     "sentiment": "Bullish/Bearish/Neutral",
     "strength": "strong/moderate/weak",
     "confidence": 0.0-1.0,
     "market_factors": ["interest rates", "earnings"],
     "position_sentiments": {"AAPL": "Bullish", "NVDA": "Neutral"}
   }

Include fallback to neutral sentiment if analysis fails.
```

---

## 🛡️ PROMPT 5: Risk Assessment Agent

```
Create agents/risk_agent.py using FinBERT for risk analysis:

1. Extend base_agent.py
2. Use model: ProsusAI/finbert
3. Extract risk-related content from daily_portfolio_analysis.md:
   - Risk warnings, alerts, stop-loss mentions
   - Portfolio concentration warnings
   - Market volatility indicators
   - Any "caution" or "warning" text

4. Analyze each risk factor separately
5. Classify overall risk level based on aggregated sentiment
6. Identify specific risk concerns

7. Return structure:
   {
     "risk_level": "high/medium/low",
     "confidence": 0.0-1.0,
     "concerns": ["high concentration", "market volatility"],
     "risk_scores": {"systemic": 0.7, "position": 0.3, "market": 0.5},
     "recommended_action": "reduce exposure/maintain/increase"
   }

Default to "medium" risk if uncertain. Be conservative in risk assessment.
```

---

## 🤖 PROMPT 6: Trade Generation Logic

```
Create agents/trade_agent.py that generates actual trading decisions. This agent:

1. Does NOT call any API - it's pure logic
2. Takes input from all other agents plus portfolio state
3. Generates TradeOrder objects compatible with my existing