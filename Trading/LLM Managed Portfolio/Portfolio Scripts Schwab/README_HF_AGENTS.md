# HuggingFace Agent System Integration

## Overview

This system integrates multiple specialized HuggingFace financial sentiment models to analyze your portfolio and generate trading recommendations. It works alongside your existing Schwab trading system by analyzing the `daily_portfolio_analysis.md` file.

## Architecture

```
Portfolio Scripts Schwab/
├── agents/                          # Agent implementations
│   ├── __init__.py                 # Agent exports
│   ├── base_agent.py               # Base class with retry logic
│   ├── news_agent.py               # News sentiment analysis
│   ├── market_agent.py             # Market sentiment analysis
│   ├── risk_agent.py               # Risk assessment
│   └── tone_agent.py               # Overall market tone
├── hf_config.py                     # Configuration and model settings
├── hf_agent_system.py               # Main orchestrator
└── requirements_hf.txt              # Additional dependencies
```

## Models Used

| Agent | Model | Purpose |
|-------|-------|---------|
| News | `mrm8488/distilroberta-finetuned-financial-news-sentiment` | Analyze financial news sentiment |
| Market | `StephanAkkerman/FinTwitBERT` | Analyze market commentary and social sentiment |
| Risk | `ProsusAI/finbert` | Assess risk factors and financial health |
| Tone | `yiyanghkust/finbert-tone` | Determine overall market tone |

## Installation

### 1. Install Dependencies

```bash
# Activate your trading environment
conda activate trading_env

# Install HuggingFace dependencies
pip install -r requirements_hf.txt
```

### 2. Optional: Set HuggingFace Token

While the free models work without authentication, setting a token can increase rate limits:

```bash
export HUGGINGFACE_TOKEN="your_token_here"
```

Or add to your shell profile (`~/.bashrc`, `~/.zshrc`):
```bash
echo 'export HUGGINGFACE_TOKEN="your_token_here"' >> ~/.zshrc
```

## Usage

### Configuration

View and customize settings in [hf_config.py](hf_config.py):

```python
# Trading Parameters
max_position_size = 0.20      # Max 20% per position
min_cash_reserve = 100.0      # Minimum cash to maintain
confidence_threshold = 0.65   # Minimum confidence for trades

# Retry Configuration
max_retries = 3               # API retry attempts
exponential_base = 2.0        # Exponential backoff multiplier
```

View configuration:
```bash
python hf_config.py
```

### Running the System

#### Test Mode (Standalone)

```bash
python hf_agent_system.py
```

This runs a test analysis with sample data and prints results.

#### Integrate with Portfolio Analysis

```python
from hf_agent_system import HFAgentSystem

# Initialize system
system = HFAgentSystem()

# Load your portfolio analysis
with open('daily_portfolio_analysis.md', 'r') as f:
    portfolio_analysis = f.read()

# Prepare context
context = {
    "cash": 5000.00,
    "total_value": 25000.00,
    "positions": ["AAPL", "NVDA", "SPY"]
}

# Run analysis
consensus = system.analyze_portfolio_data(portfolio_analysis, context)

# View results
system.print_analysis(consensus)

# Export to file
system.export_analysis(consensus, "hf_analysis.json")
```

### Integration with Existing System

The agent system can be integrated into your existing workflow:

```python
# In your main.py or custom script
from hf_agent_system import HFAgentSystem
from portfolio_manager import PortfolioManager

# Load portfolio state
portfolio = PortfolioManager()
portfolio.load_state()

# Read analysis file
with open('daily_portfolio_analysis.md', 'r') as f:
    analysis_text = f.read()

# Run HF agent analysis
hf_system = HFAgentSystem()
consensus = hf_system.analyze_portfolio_data(
    analysis_text,
    context={
        "cash": portfolio.cash,
        "total_value": portfolio.get_total_value(),
        "holdings": portfolio.get_holdings()
    }
)

# Use consensus for trading decisions
if consensus.recommendation == "BUY" and consensus.confidence > 0.70:
    print(f"Strong BUY signal: {consensus.reasoning}")
elif consensus.recommendation == "SELL" and consensus.confidence > 0.70:
    print(f"Strong SELL signal: {consensus.reasoning}")
else:
    print(f"HOLD recommendation: {consensus.reasoning}")
```

## How It Works

### 1. Multi-Agent Analysis

Each agent analyzes the portfolio text independently:

- **News Agent**: Extracts news sentiment from market commentary
- **Market Agent**: Analyzes social and market sentiment signals
- **Risk Agent**: Identifies risk factors and concerns
- **Tone Agent**: Determines overall market tone

### 2. Consensus Building

The system aggregates results using weighted voting:

```python
weights = {
    "NewsAgent": 0.25,    # 25% weight
    "MarketAgent": 0.30,  # 30% weight
    "RiskAgent": 0.30,    # 30% weight (highest for safety)
    "ToneAgent": 0.15     # 15% weight
}
```

### 3. Recommendation Generation

Based on consensus sentiment and confidence:

- **BUY**: Positive sentiment + confidence ≥ threshold + acceptable risk
- **SELL**: Negative sentiment + confidence ≥ threshold OR high risk
- **HOLD**: Low confidence or mixed signals

### 4. Risk Override

High risk signals (confidence > 75%) can override positive sentiment to prevent risky trades.

## API Rate Limits

HuggingFace Inference API limits (without token):
- Free tier: ~30 requests/hour per model
- With token: Higher limits

The system includes:
- Automatic retry with exponential backoff
- 503 handling (model loading)
- Request timeout (30s)

## Output Format

### ConsensusResult

```python
{
    "overall_sentiment": "positive",  # positive/negative/neutral
    "confidence": 0.78,                # 0.0 to 1.0
    "recommendation": "BUY",           # BUY/SELL/HOLD
    "reasoning": "Multi-Agent Analysis Summary...",
    "agent_results": [
        {
            "agent_name": "NewsAgent",
            "sentiment": "positive",
            "confidence": 0.82,
            "label": "positive",
            "score": 0.82,
            "reasoning": "Strong positive sentiment...",
            "timestamp": "2024-01-15T10:30:00",
            "model_used": "mrm8488/distilroberta-finetuned-financial-news-sentiment"
        },
        // ... other agents
    ],
    "timestamp": "2024-01-15T10:30:15"
}
```

## Customization

### Add New Agent

1. Create new agent file in `agents/` directory:

```python
from .base_agent import BaseAgent, AgentResult

class MyCustomAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_key="custom")

    def analyze(self, text, context=None):
        # Your implementation
        pass

    def _interpret_results(self, response, text, context):
        # Your interpretation logic
        pass
```

2. Add model config to `hf_config.py`:

```python
"custom": ModelConfig(
    name="My Custom Model",
    model_id="username/model-name",
    task="sentiment-analysis",
    max_length=512
)
```

3. Update `agents/__init__.py` and `hf_agent_system.py`

### Modify Weights

Edit `_build_consensus()` in [hf_agent_system.py](hf_agent_system.py:159):

```python
weights = {
    "NewsAgent": 0.30,     # Increase news weight
    "MarketAgent": 0.25,
    "RiskAgent": 0.30,
    "ToneAgent": 0.15
}
```

### Adjust Trading Parameters

Edit [hf_config.py](hf_config.py:77):

```python
TRADING = TradingParameters(
    max_position_size=0.15,        # Reduce to 15%
    min_cash_reserve=200.0,        # Increase reserve
    confidence_threshold=0.70      # Require higher confidence
)
```

## Troubleshooting

### Models Loading Slowly
First API call may take 30-60s as HuggingFace loads the model. Subsequent calls are faster.

### Rate Limit Errors
- Reduce analysis frequency
- Add HuggingFace token for higher limits
- Increase retry delays in config

### Import Errors
Ensure you're in the correct directory and environment:
```bash
cd "Portfolio Scripts Schwab"
conda activate trading_env
python -c "from agents import NewsAgent; print('Success!')"
```

### Connection Errors
Check internet connection and HuggingFace API status:
```bash
curl https://api-inference.huggingface.co/models/ProsusAI/finbert
```

## Next Steps

1. **Test the system**: Run `python hf_agent_system.py`
2. **Integrate with workflow**: Add to your main portfolio script
3. **Monitor performance**: Track recommendation accuracy
4. **Customize weights**: Adjust based on your risk tolerance
5. **Add more agents**: Extend with additional models

## Compatibility

- Compatible with existing `trading_models.py` (TradeOrder, OrderType, OrderPriority)
- Works alongside Schwab API integration
- Does not modify existing portfolio management code
- Can be enabled/disabled independently

## Resources

- [HuggingFace Inference API Docs](https://huggingface.co/docs/api-inference/index)
- [FinBERT Documentation](https://huggingface.co/ProsusAI/finbert)
- [Transformers Library](https://huggingface.co/docs/transformers/index)
