"""
Local LLM Inference Server
High-performance multi-model server using vLLM for financial analysis pipeline

Manages 4 specialized models:
- News Analysis: AdaptLLM/Llama-3-FinMA-8B-Instruct 
- Market Analysis: Qwen/Qwen2.5-14B-Instruct
- Trading Decision: deepseek-ai/DeepSeek-R1-Distill-Qwen-14B
- Risk Validation: microsoft/Phi-3-medium-4k-instruct
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from contextlib import asynccontextmanager

try:
    from vllm import AsyncLLMEngine, SamplingParams, AsyncEngineArgs
    from transformers import AutoTokenizer
    import torch
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    print("⚠️ vLLM not available - install with: pip install vllm")


# Model configurations from local_runtime
MODEL_CONFIGS = {
    "news_analysis": {
        "model_id": "AdaptLLM/Llama-3-FinMA-8B-Instruct",
        "purpose": "Financial news analysis and sentiment extraction",
        "vram_required": "16GB",
        "quantization": "8bit",
        "performance_score": 0.847,
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


class LocalLLMServer:
    """High-performance multi-model LLM server for financial analysis"""
    
    def __init__(self, enable_models: List[str] = None):
        """
        Initialize LLM server
        
        Args:
            enable_models: List of model names to load (default: all models)
        """
        self.engines = {}
        self.tokenizers = {}
        self.model_configs = MODEL_CONFIGS
        self.enable_models = enable_models or list(MODEL_CONFIGS.keys())
        self.is_initialized = False
        
        # Setup logging
        self.logger = logging.getLogger('local_llm_server')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        if not VLLM_AVAILABLE:
            self.logger.error("vLLM not available - please install with: pip install vllm")
            
    async def initialize_models(self, force_cpu: bool = False):
        """Load and initialize specified models with optimal settings"""
        
        if not VLLM_AVAILABLE:
            self.logger.error("Cannot initialize models - vLLM not available")
            return False
            
        if self.is_initialized:
            self.logger.info("Models already initialized")
            return True
            
        self.logger.info("🚀 Starting Local LLM Server initialization...")
        
        # Check available GPU memory
        if torch.cuda.is_available() and not force_cpu:
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            self.logger.info(f"Available GPU memory: {gpu_memory:.1f}GB")
        else:
            self.logger.info("Using CPU-only mode")
            force_cpu = True
            
        success_count = 0
        
        for model_name in self.enable_models:
            if model_name not in self.model_configs:
                self.logger.warning(f"Unknown model: {model_name}")
                continue
                
            config = self.model_configs[model_name]
            
            try:
                self.logger.info(f"Loading {model_name}: {config['model_id']}")
                
                # Configure engine args for optimal performance
                engine_args = AsyncEngineArgs(
                    model=config['model_id'],
                    tensor_parallel_size=1 if force_cpu else min(torch.cuda.device_count(), 2),
                    max_model_len=4096,
                    gpu_memory_utilization=0.85 if not force_cpu else 0,
                    quantization=None if force_cpu else config.get('quantization'),
                    dtype="float16" if not force_cpu and config['quantization'] == '4bit' else "auto",
                    trust_remote_code=True,
                    download_dir=os.path.expanduser("~/.cache/huggingface"),
                    enable_prefix_caching=True,
                    enable_chunked_prefill=True,
                    device="cpu" if force_cpu else "cuda"
                )
                
                # Initialize engine
                self.engines[model_name] = AsyncLLMEngine.from_engine_args(engine_args)
                
                # Initialize tokenizer  
                self.tokenizers[model_name] = AutoTokenizer.from_pretrained(
                    config['model_id'],
                    trust_remote_code=True
                )
                
                self.logger.info(f"✅ Successfully loaded {model_name}")
                success_count += 1
                
            except Exception as e:
                self.logger.error(f"❌ Failed to load {model_name}: {e}")
                continue
                
        self.is_initialized = success_count > 0
        self.logger.info(f"🎯 Initialization complete: {success_count}/{len(self.enable_models)} models loaded")
        
        return self.is_initialized
        
    async def generate(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.1,  # Conservative for financial decisions
        top_p: float = 0.95,
        stop_sequences: List[str] = None
    ) -> str:
        """Generate response from specified model"""
        
        if not self.is_initialized:
            raise RuntimeError("LLM server not initialized - call initialize_models() first")
            
        if model_name not in self.engines:
            raise ValueError(f"Model {model_name} not loaded. Available: {list(self.engines.keys())}")
            
        # Configure sampling parameters
        sampling_params = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stop=stop_sequences or ["</s>", "\n\n### ", "<|im_end|>"]
        )
        
        # Format prompt based on model template
        formatted_prompt = self._format_prompt(model_name, prompt)
        
        # Generate response
        request_id = f"{model_name}_{int(datetime.now().timestamp())}"
        
        try:
            results = []
            async for output in self.engines[model_name].generate(
                formatted_prompt,
                sampling_params, 
                request_id
            ):
                results.append(output)
                
            # Extract text from final output
            if results and results[-1].outputs:
                response = results[-1].outputs[0].text.strip()
                self.logger.info(f"Generated {len(response)} chars from {model_name}")
                return response
            else:
                return ""
                
        except Exception as e:
            self.logger.error(f"Generation failed for {model_name}: {e}")
            return ""
    
    def _format_prompt(self, model_name: str, prompt: str) -> str:
        """Format prompt according to model's template"""
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        templates = {
            "news_analysis": f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a financial news analyst specializing in extracting actionable trading signals from news and market data.
Current date: {current_date}
Focus on: earnings surprises, FDA approvals, M&A activity, guidance changes, analyst upgrades, sector rotation signals.
Provide concise, quantifiable insights with specific impact assessments.
<|eot_id|><|start_header_id|>user<|end_header_id|>
{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>""",
            
            "trading_decision": f"""<|im_start|>system
You are a professional portfolio manager making data-driven trading decisions.
Current date: {current_date}
Portfolio constraints: Max position 20%, stop-loss at -15%, maintain 5% cash reserve.
Output specific BUY/SELL/HOLD recommendations with share quantities and clear rationale.
Focus on risk-adjusted returns and portfolio balance.
<|im_end|>
<|im_start|>user
{prompt}<|im_end|>
<|im_start|>assistant""",
            
            "market_analysis": f"""### Instruction:
Analyze the provided market data and identify specific trading opportunities.
Current date: {current_date}
Focus on: momentum shifts, volume anomalies, support/resistance levels, trend strength, sector rotation.
Provide specific price targets and technical levels.

### Input:
{prompt}

### Response:""",
            
            "risk_validation": f"""Human: You are a risk management specialist validating trading decisions.
Current date: {current_date}
Evaluate the following for compliance with risk parameters:
- Position sizing limits (max 20% per position)
- Cash reserve requirements (min 5%) 
- Stop-loss compliance
- Overall portfolio risk concentration

Analysis to validate:
{prompt}

Please provide: APPROVED/REJECTED with specific concerns."""
        }
        
        return templates.get(model_name, prompt)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server health and model status"""
        
        status = {
            "server_status": "running" if self.is_initialized else "not_initialized",
            "models_loaded": len(self.engines),
            "available_models": list(self.engines.keys()),
            "timestamp": datetime.now().isoformat(),
            "vllm_available": VLLM_AVAILABLE
        }
        
        if VLLM_AVAILABLE and torch.cuda.is_available():
            status["gpu_memory"] = f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB"
        
        return status
    
    async def shutdown(self):
        """Gracefully shutdown all models"""
        
        self.logger.info("🔄 Shutting down LLM server...")
        
        for model_name in list(self.engines.keys()):
            try:
                # vLLM engines don't have explicit shutdown methods
                # They will be garbage collected
                del self.engines[model_name]
                del self.tokenizers[model_name]
                self.logger.info(f"✅ Shutdown {model_name}")
            except Exception as e:
                self.logger.error(f"Error shutting down {model_name}: {e}")
        
        self.engines.clear()
        self.tokenizers.clear()
        self.is_initialized = False
        self.logger.info("🎯 LLM server shutdown complete")
        
    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """Get information about a specific model"""
        
        if model_name in self.model_configs:
            info = self.model_configs[model_name].copy()
            info["loaded"] = model_name in self.engines
            info["available"] = VLLM_AVAILABLE
            return info
        return None
        
    def list_available_models(self) -> List[str]:
        """List all available model names"""
        return list(self.model_configs.keys())


@asynccontextmanager
async def llm_server_context(enable_models: List[str] = None, force_cpu: bool = False):
    """Async context manager for LLM server lifecycle"""
    
    server = LocalLLMServer(enable_models=enable_models)
    
    try:
        await server.initialize_models(force_cpu=force_cpu)
        yield server
    finally:
        await server.shutdown()


# Standalone testing function
async def test_server():
    """Test server functionality with sample prompts"""
    
    print("🧪 Testing Local LLM Server...")
    
    # Test with lightweight models for demonstration
    test_models = ["risk_validation"]  # Start with smallest model
    
    async with llm_server_context(enable_models=test_models, force_cpu=True) as server:
        if not server.is_initialized:
            print("❌ Server initialization failed")
            return
            
        # Test health check
        health = await server.health_check()
        print(f"📊 Health: {health}")
        
        # Test generation
        test_prompt = """
        Portfolio Analysis:
        - Current cash: 15%
        - NVDA position: 25% (over limit)
        - AMD position: 10%
        - Total positions: 8
        
        Proposed trades:
        - SELL 5 shares NVDA (reduce to 15%)
        - BUY 2 shares XLV (add defensive)
        """
        
        response = await server.generate(
            model_name="risk_validation",
            prompt=test_prompt,
            max_tokens=500
        )
        
        print(f"🎯 Test response ({len(response)} chars):")
        print(response[:200] + "..." if len(response) > 200 else response)


if __name__ == "__main__":
    # Run server test
    try:
        asyncio.run(test_server())
    except KeyboardInterrupt:
        print("\n🔄 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")