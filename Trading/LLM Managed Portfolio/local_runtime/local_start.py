# config/model_config.py
"""
Model Configuration based on HuggingFace FinBench Leaderboard
Selection criteria: Performance, Size, Specialization
"""

MODEL_CONFIGS = {
    "news_analysis": {
        "model_id": "AdaptLLM/Llama-3-FinMA-8B-Instruct",
        "purpose": "Financial news analysis and sentiment extraction",
        "vram_required": "16GB",
        "quantization": "8bit",
        "performance_score": 0.847,  # FinBench score
        "specialized_tasks": [
            "earnings_analysis",
            "market_sentiment",
            "catalyst_identification",
            "risk_event_detection"
        ]
    },
    
    "market_analysis": {
        "model_id": "Qwen/Qwen2.5-14B-Instruct",
        "purpose": "Technical analysis and market pattern recognition",
        "vram_required": "20GB",
        "quantization": "4bit",
        "performance_score": 0.891,
        "specialized_tasks": [
            "price_prediction",
            "volume_analysis",
            "support_resistance",
            "trend_identification"
        ]
    },
    
    "trading_decision": {
        "model_id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        "purpose": "Trading strategy and position management",
        "vram_required": "20GB",
        "quantization": "4bit",
        "performance_score": 0.923,
        "specialized_tasks": [
            "position_sizing",
            "risk_management",
            "portfolio_optimization",
            "trade_timing"
        ]
    },
    
    "risk_validation": {
        "model_id": "microsoft/Phi-3-medium-4k-instruct",
        "purpose": "Fast risk checks and compliance",
        "vram_required": "8GB",
        "quantization": "8bit",
        "performance_score": 0.812,
        "specialized_tasks": [
            "stop_loss_validation",
            "position_concentration",
            "cash_flow_verification",
            "regulatory_compliance"
        ]
    }
}



# deployment/llm_server.py
"""
High-performance LLM inference server using vLLM
Handles multiple models with efficient batching
"""

import asyncio
from typing import Dict, List, Optional
from vllm import AsyncLLMEngine, SamplingParams, AsyncEngineArgs
from transformers import AutoTokenizer
import torch

class LocalLLMServer:
    def __init__(self, model_configs: Dict):
        self.engines = {}
        self.tokenizers = {}
        self.model_configs = model_configs
        
    async def initialize_models(self):
        """Load and initialize all models with optimal settings"""
        for model_name, config in self.model_configs.items():
            print(f"Loading {model_name}: {config['model_id']}")
            
            # Configure engine args for optimal performance
            engine_args = AsyncEngineArgs(
                model=config['model_id'],
                tensor_parallel_size=torch.cuda.device_count(),
                max_model_len=4096,
                gpu_memory_utilization=0.90,
                quantization=config.get('quantization', None),
                dtype="float16" if config['quantization'] == '4bit' else "auto",
                trust_remote_code=True,
                download_dir="/models/cache",
                enable_prefix_caching=True,  # Speeds up repeated prompts
                enable_chunked_prefill=True,  # Better throughput
            )
            
            # Initialize engine and tokenizer
            self.engines[model_name] = AsyncLLMEngine.from_engine_args(engine_args)
            self.tokenizers[model_name] = AutoTokenizer.from_pretrained(
                config['model_id'],
                trust_remote_code=True
            )
            
    async def generate(
        self, 
        model_name: str, 
        prompt: str, 
        max_tokens: int = 2048,
        temperature: float = 0.1,  # Low temp for financial decisions
        top_p: float = 0.95
    ) -> str:
        """Generate response from specified model"""
        
        if model_name not in self.engines:
            raise ValueError(f"Model {model_name} not loaded")
        
        sampling_params = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stop=["</s>", "\n\n### "]  # Common stop tokens
        )
        
        # Format prompt based on model template
        formatted_prompt = self._format_prompt(model_name, prompt)
        
        # Generate with streaming
        request_id = f"{model_name}_{asyncio.get_event_loop().time()}"
        results = []
        
        async for output in self.engines[model_name].generate(
            formatted_prompt, 
            sampling_params, 
            request_id
        ):
            results.append(output)
        
        # Extract text from final output
        return results[-1].outputs[0].text if results else ""
    
    def _format_prompt(self, model_name: str, prompt: str) -> str:
        """Format prompt according to model's template"""
        
        templates = {
            "news_analysis": """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a financial news analyst specializing in extracting actionable trading signals from news.
Focus on: earnings surprises, FDA approvals, M&A activity, guidance changes, analyst upgrades.
<|eot_id|><|start_header_id|>user<|end_header_id|>
{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>""",
            
            "trading_decision": """<|im_start|>system
You are a professional portfolio manager making trading decisions.
Current date: {date}
Portfolio constraints: Max position 20%, stop-loss at -15%, maintain 5% cash reserve.
Output format: JSON with explicit BUY/SELL orders and share quantities.
<|im_end|>
<|im_start|>user
{prompt}<|im_end|>
<|im_start|>assistant""",
            
            "market_analysis": """### Instruction:
Analyze the following market data and identify trading opportunities.
Focus on: momentum shifts, volume anomalies, support/resistance levels, trend strength.

### Input:
{prompt}

### Response:""",
            
            "risk_validation": """Human: Validate the following trades for risk compliance:
{prompt}