# Advanced NewsAgent - Technical Documentation

## Overview

The enhanced `NewsAgent` provides sophisticated financial news sentiment analysis with automatic document parsing, ticker extraction, and intelligent aggregation. It's designed to analyze `daily_portfolio_analysis.md` files and extract actionable sentiment insights.

## Key Features

### 1. Document Parsing
Automatically extracts news items from structured documents using multiple strategies:

- **Section-based extraction**: Finds "News", "Events", "Market News", "Headlines" sections
- **Bullet point detection**: Extracts items marked with -, *, •, ▪
- **Numbered list parsing**: Handles 1., 2., 3. formatted lists
- **Paragraph splitting**: Falls back to paragraph-based extraction
- **Financial filtering**: Uses heuristics to identify relevant news

### 2. Ticker Extraction
Intelligently extracts stock tickers from text with multiple format support:

#### Supported Formats
```python
"$AAPL"                          → AAPL
"Apple (AAPL)"                   → AAPL
"(AAPL)"                         → AAPL
"shares of GOOGL"                → GOOGL
"stock MSFT"                     → MSFT
```

#### Blacklist Filtering
Automatically filters out 50+ common words that look like tickers:
- Short words: A, I, FOR, THE, AND, OR, TO, AT, IN, ON...
- Time/location: US, UK, EU, AM, PM, ET...
- Business terms: CEO, CFO, CTO, IPO, AGO...
- Common verbs: ADD, BUY, SELL, GET, GO, SEE...

### 3. Intelligent Aggregation
Combines multiple news items using confidence-weighted voting:

```python
# Each sentiment is weighted by its confidence
weighted_score = sum(confidence * weight for each result)

# Example:
# - News 1: positive (0.9 confidence) → weight = 0.9
# - News 2: positive (0.7 confidence) → weight = 0.7
# - News 3: negative (0.6 confidence) → weight = 0.6
# Overall: positive (0.72 weighted confidence)
```

### 4. Structured Output

Returns `NewsAnalysis` dataclass:
```python
@dataclass
class NewsAnalysis:
    sentiment: str              # "positive", "negative", "neutral"
    confidence: float           # 0.0 to 1.0 (weighted)
    tickers: List[str]          # ["AAPL", "MSFT", "NVDA"]
    breakdown: Dict[str, float] # {"positive": 0.7, "negative": 0.2, "neutral": 0.1}
    news_items_analyzed: int    # Number of items processed
    raw_results: List[AgentResult]  # Individual item results
```

## Usage Examples

### Basic Single-Text Analysis

```python
from agents import NewsAgent

agent = NewsAgent()

news_text = "Apple Inc. reported record earnings, beating analyst expectations."
result = agent.analyze(news_text, context={"ticker": "AAPL"})

print(f"Sentiment: {result.sentiment}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Reasoning: {result.reasoning}")
```

### Document Analysis (Primary Use Case)

```python
from agents import NewsAgent

agent = NewsAgent()

# Read portfolio analysis file
with open('daily_portfolio_analysis.md', 'r') as f:
    document = f.read()

# Analyze (limits to 10 news items by default)
analysis = agent.analyze_portfolio_document(document, max_items=10)

# Access results
print(f"Overall: {analysis.sentiment} ({analysis.confidence:.1%})")
print(f"Tickers: {', '.join(analysis.tickers)}")
print(f"Items: {analysis.news_items_analyzed}")

# Sentiment breakdown
for sentiment, percentage in analysis.breakdown.items():
    print(f"{sentiment}: {percentage:.1%}")

# Individual results
for result in analysis.raw_results:
    print(f"- {result.sentiment} ({result.confidence:.1%}): {result.reasoning[:60]}")
```

### Ticker Extraction Only

```python
agent = NewsAgent()

text = """
Portfolio update: $AAPL gained 3%, Microsoft (MSFT) announced
new products, and shares of NVDA surged on AI news.
"""

tickers = agent._extract_tickers(text)
print(f"Found tickers: {tickers}")
# Output: ['AAPL', 'MSFT', 'NVDA']
```

### Custom Max Items

```python
# Analyze only first 5 news items (faster, fewer API calls)
analysis = agent.analyze_portfolio_document(document, max_items=5)

# Analyze more items for comprehensive coverage
analysis = agent.analyze_portfolio_document(document, max_items=15)
```

## Document Format Requirements

### Recommended Format

```markdown
# Daily Portfolio Analysis

## News and Events

- Apple (AAPL) reports strong quarterly earnings
- Federal Reserve signals rate cuts
- $NVDA announces new AI chip lineup
- Tech sector shows resilience amid volatility

## Market Headlines

1. Microsoft (MSFT) expands cloud services
2. Amazon (AMZN) faces increased competition
3. Tesla (TSLA) delivers record vehicles
```

### Supported Sections

The agent searches for these section headers (case-insensitive):
- "News"
- "Events"
- "Market News"
- "Headlines"
- "Recent News"
- "Breaking"
- "Latest"
- "Top Stories"

### Supported List Formats

```markdown
# Bullet points
- Item 1
* Item 2
• Item 3
▪ Item 4

# Numbered lists
1. Item one
2. Item two
3. Item three

# Paragraphs (fallback)
First news paragraph.

Second news paragraph.
```

## Advanced Features

### News Detection Heuristic

The agent uses keyword-based filtering to identify relevant news:

```python
financial_keywords = [
    'earnings', 'revenue', 'profit', 'loss', 'stock', 'share',
    'market', 'price', 'trading', 'investor', 'analyst',
    'forecast', 'guidance', 'quarter', 'Q1', 'Q2', 'Q3', 'Q4',
    'announced', 'report', 'beats', 'misses', 'expects',
    'outlook', 'growth', 'decline', 'surge', 'rally', 'drop',
    'gain', 'fell', 'rose', 'up', 'down', 'percent', '%'
]

# Requires: 2+ financial keywords AND length > 20 characters
```

### Duplicate Removal

The agent automatically:
- Removes exact duplicates
- Normalizes text (lowercase, strip whitespace)
- Preserves order of first occurrence
- Filters items shorter than 20 characters

### Error Handling

All errors return neutral results instead of crashing:

```python
# API failure
NewsAnalysis(
    sentiment="neutral",
    confidence=0.0,
    tickers=[],
    breakdown={"positive": 0.0, "negative": 0.0, "neutral": 1.0},
    news_items_analyzed=0,
    raw_results=[]
)
```

## Performance Considerations

### API Call Optimization

```python
# Each news item = 1 API call
# Limit items to control costs/latency

max_items=5   # ~5 API calls, ~10-15 seconds
max_items=10  # ~10 API calls, ~20-30 seconds (default)
max_items=20  # ~20 API calls, ~40-60 seconds
```

### Caching Benefits

The base agent caches responses for 5 minutes:
```python
# First analysis: 10 items × 2-3 seconds = 20-30 seconds
analysis1 = agent.analyze_portfolio_document(doc, max_items=10)

# Same document within 5 minutes: Instant (cached)
analysis2 = agent.analyze_portfolio_document(doc, max_items=10)
```

### Memory Usage

- Each `NewsAnalysis`: ~1-2KB
- Each `AgentResult`: ~500 bytes
- 10 items with results: ~10-15KB total

## Integration Examples

### With Portfolio System

```python
from agents import NewsAgent
from portfolio_manager import PortfolioManager

# Load portfolio
portfolio = PortfolioManager()
portfolio.load_state()

# Analyze news
agent = NewsAgent()
with open('daily_portfolio_analysis.md', 'r') as f:
    analysis = agent.analyze_portfolio_document(f.read())

# Use for decision making
if analysis.sentiment == "positive" and analysis.confidence > 0.70:
    print(f"Strong positive signals for: {', '.join(analysis.tickers)}")
elif analysis.sentiment == "negative" and analysis.confidence > 0.70:
    print(f"Warning: Negative sentiment for: {', '.join(analysis.tickers)}")
```

### With Trading Logic

```python
from agents import NewsAgent
from trading_models import TradeOrder, OrderType, OrderPriority

agent = NewsAgent()
analysis = agent.analyze_portfolio_document(document)

orders = []
for ticker in analysis.tickers:
    if analysis.sentiment == "positive" and analysis.confidence > 0.75:
        orders.append(TradeOrder(
            ticker=ticker,
            action=OrderType.BUY,
            shares=10,
            priority=OrderPriority.MEDIUM,
            reason=f"Strong positive news sentiment ({analysis.confidence:.1%})"
        ))
```

### Export to JSON

```python
import json

analysis = agent.analyze_portfolio_document(document)

# Export full analysis
with open('news_analysis.json', 'w') as f:
    json.dump(analysis.to_dict(), f, indent=2)
```

## Testing

Run the comprehensive test suite:

```bash
cd "Portfolio Scripts Schwab"
python test_news_agent_advanced.py
```

### Test Coverage

1. **Ticker Extraction**: Multiple formats, blacklist filtering
2. **News Extraction**: Section parsing, bullet points, numbered lists
3. **News Filtering**: Heuristic validation
4. **Aggregation**: Weighted sentiment combination
5. **Edge Cases**: Empty documents, no news, tickers only
6. **Full Pipeline**: End-to-end document analysis (optional API call)

## Configuration

### Adjust Ticker Blacklist

Edit `news_agent.py`:
```python
TICKER_BLACKLIST = {
    'A', 'I', 'FOR', # ... existing
    'YOUR', 'CUSTOM', 'WORDS'  # Add more
}
```

### Modify Financial Keywords

Edit `_looks_like_news()` method:
```python
financial_keywords = [
    'earnings', 'revenue',  # ... existing
    'your', 'custom', 'keywords'  # Add more
]
```

### Change Aggregation Weights

Edit `_aggregate_results()` method:
```python
# Current: confidence-weighted
weight = result.confidence if result.confidence > 0 else 0.1

# Equal weighting:
weight = 1.0

# Custom weighting:
weight = result.confidence ** 2  # Emphasize high confidence
```

## Troubleshooting

### No News Items Found

**Symptoms**: `news_items_analyzed = 0`

**Solutions**:
1. Check document format (use recommended section headers)
2. Verify bullet points or numbered lists
3. Add financial keywords to text
4. Review logs for extraction patterns matched

### Too Many/Few Tickers

**Symptoms**: Unexpected ticker count

**Solutions**:
1. Review ticker blacklist for false negatives
2. Add specific words to blacklist
3. Check ticker formats in document
4. Use `$TICKER` format for explicit extraction

### Low Confidence Results

**Symptoms**: `confidence < 0.5`

**Solutions**:
1. Review individual item results
2. Check for mixed sentiment news
3. Verify news items contain clear sentiment
4. Consider increasing `max_items` for better aggregation

## API Rate Limits

### Free Tier (No Token)
- ~30 requests/hour per model
- 10 news items = 10 API calls
- Recommended: `max_items=5` for frequent analysis

### With HuggingFace Token
- Higher rate limits
- Recommended: `max_items=10-20`

Set token:
```bash
export HUGGINGFACE_TOKEN="your_token_here"
```

## Best Practices

1. **Limit items**: Start with `max_items=5`, increase if needed
2. **Use caching**: Analyze same document multiple times within 5 minutes
3. **Format documents**: Use clear section headers and bullet points
4. **Monitor logs**: Check extraction and parsing success
5. **Validate tickers**: Review extracted tickers for accuracy
6. **Check confidence**: Only act on high-confidence results (>0.65)
7. **Handle errors**: Always check for neutral sentiment with 0.0 confidence

## Summary

The enhanced NewsAgent provides:

✅ **Automatic parsing**: Extracts news from markdown documents
✅ **Smart ticker extraction**: 4 format patterns, 50+ word blacklist
✅ **Intelligent aggregation**: Confidence-weighted sentiment combination
✅ **Structured output**: Clean dataclass with all details
✅ **Rate limit friendly**: Configurable max items (default: 10)
✅ **Error resilient**: Returns neutral on all failures
✅ **Production ready**: Comprehensive logging and testing

Perfect for analyzing `daily_portfolio_analysis.md` files in your Schwab trading system!
