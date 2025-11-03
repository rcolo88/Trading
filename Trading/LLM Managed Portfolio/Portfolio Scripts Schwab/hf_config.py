"""
HuggingFace Agent System Configuration
Configuration for financial sentiment analysis models and trading parameters
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class ModelConfig:
    """Configuration for a single HuggingFace model"""
    name: str
    model_id: str
    task: str
    max_length: int = 512
    temperature: float = 0.7
    top_k: int = 50


@dataclass
class RetryConfig:
    """Configuration for API retry logic"""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0  # for exponential backoff

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number using exponential backoff"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


@dataclass
class TradingParameters:
    """Trading constraints and parameters"""
    max_position_size: float = 0.20  # Max 20% of portfolio per position
    min_cash_reserve: float = 100.0  # Minimum cash to maintain
    max_portfolio_positions: int = 20  # Maximum number of positions
    min_trade_value: float = 50.0  # Minimum trade value
    confidence_threshold: float = 0.65  # Minimum confidence for trades


class HFConfig:
    """Main configuration class for HuggingFace agent system"""

    # HuggingFace API Configuration
    HF_API_URL = "https://api-inference.huggingface.co/models/"
    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")  # Optional for public models

    # News Source: Yahoo Finance via yfinance (no API key required)

    # Model Configurations
    MODELS = {
        "news": ModelConfig(
            name="News Sentiment Analyzer",
            model_id="mrm8488/distilroberta-finetuned-financial-news-sentiment",
            task="sentiment-analysis",
            max_length=512,
            temperature=0.5
        ),
        "market": ModelConfig(
            name="Market Sentiment Analyzer",
            model_id="StephanAkkerman/FinTwitBERT",
            task="sentiment-analysis",
            max_length=512,
            temperature=0.5
        ),
        "risk": ModelConfig(
            name="Risk Analyzer",
            model_id="ProsusAI/finbert",
            task="sentiment-analysis",
            max_length=512,
            temperature=0.3  # Lower temp for risk analysis
        ),
        "tone": ModelConfig(
            name="Market Tone Analyzer",
            model_id="yiyanghkust/finbert-tone",
            task="sentiment-analysis",
            max_length=512,
            temperature=0.5
        ),
        "reasoning": ModelConfig(
            name="Reasoning Agent (Decision Synthesis)",
            model_id="deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
            task="text-generation",
            max_length=2048,
            temperature=0.1,  # Lower temp for more deterministic reasoning
            top_k=40
        )
    }

    # Trading Parameters
    TRADING = TradingParameters(
        max_position_size=0.20,
        min_cash_reserve=100.0,
        max_portfolio_positions=20,
        min_trade_value=50.0,
        confidence_threshold=0.65
    )

    # Retry Configuration
    RETRY = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=60.0,
        exponential_base=2.0
    )

    # Quality Metrics Thresholds (for core 80% allocation)
    QUALITY_MIN_SCORE = 70  # Minimum quality score for core holdings
    QUALITY_IDEAL_SCORE = 85  # Ideal score for elite compounders
    QUALITY_SWAP_THRESHOLD = 15  # Min quality score difference to recommend swap

    # Thematic Metrics Thresholds (for opportunistic 20% allocation)
    THEMATIC_MIN_SCORE = 28  # Minimum thematic score (out of 50)
    THEMATIC_IDEAL_SCORE = 40  # Leader-level thematic score

    # Portfolio Allocation Rules
    MAX_POSITION_SIZE = 0.20  # 20% max per position
    MAX_OPPORTUNISTIC_ALLOCATION = 0.20  # 20% total for thematic
    MIN_CASH_RESERVE = 0.05  # 5% minimum cash

    # Watchlist Configuration
    # Note: Set to None to fetch S&P 500 dynamically via get_sp500_tickers()
    # Or provide manual list: ["NVDA", "AMD", "AAPL", "MSFT", ...]
    WATCHLIST_TICKERS = None  # Defaults to S&P 500 screening

    # Active Themes for Opportunistic Screening
    ACTIVE_THEMES = [
        "AI Infrastructure",
        "Nuclear Renaissance",
        "Defense Modernization"
    ]

    # Request Headers
    @classmethod
    def get_headers(cls) -> dict:
        """Get API request headers"""
        headers = {"Content-Type": "application/json"}
        if cls.HF_TOKEN:
            headers["Authorization"] = f"Bearer {cls.HF_TOKEN}"
        return headers

    # Model URLs
    @classmethod
    def get_model_url(cls, model_key: str) -> str:
        """Get full API URL for a model"""
        if model_key not in cls.MODELS:
            raise ValueError(f"Unknown model key: {model_key}")
        return f"{cls.HF_API_URL}{cls.MODELS[model_key].model_id}"

    # Validation
    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration settings"""
        # Check trading parameters
        if not 0 < cls.TRADING.max_position_size <= 1.0:
            raise ValueError("max_position_size must be between 0 and 1")

        if cls.TRADING.min_cash_reserve < 0:
            raise ValueError("min_cash_reserve must be non-negative")

        if cls.TRADING.confidence_threshold < 0 or cls.TRADING.confidence_threshold > 1:
            raise ValueError("confidence_threshold must be between 0 and 1")

        # Check retry config
        if cls.RETRY.max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        if cls.RETRY.base_delay <= 0:
            raise ValueError("base_delay must be positive")

        return True

    # Display Configuration
    @classmethod
    def print_config(cls):
        """Print current configuration"""
        print("\n" + "="*60)
        print("HuggingFace Agent System Configuration")
        print("="*60)

        print("\nModels:")
        for key, model in cls.MODELS.items():
            print(f"  {key:10} -> {model.name}")
            print(f"  {'':10}    {model.model_id}")

        print(f"\nTrading Parameters:")
        print(f"  Max Position Size:     {cls.TRADING.max_position_size:.1%}")
        print(f"  Min Cash Reserve:      ${cls.TRADING.min_cash_reserve:.2f}")
        print(f"  Max Positions:         {cls.TRADING.max_portfolio_positions}")
        print(f"  Min Trade Value:       ${cls.TRADING.min_trade_value:.2f}")
        print(f"  Confidence Threshold:  {cls.TRADING.confidence_threshold:.1%}")

        print(f"\nRetry Configuration:")
        print(f"  Max Retries:           {cls.RETRY.max_retries}")
        print(f"  Base Delay:            {cls.RETRY.base_delay}s")
        print(f"  Max Delay:             {cls.RETRY.max_delay}s")
        print(f"  Exponential Base:      {cls.RETRY.exponential_base}x")

        print(f"\nAPI Configuration:")
        print(f"  HuggingFace Token:     {'Set' if cls.HF_TOKEN else 'Not Set (using public access)'}")
        print("="*60 + "\n")


# Validate configuration on import
HFConfig.validate_config()


if __name__ == "__main__":
    # Display configuration when run directly
    HFConfig.print_config()
