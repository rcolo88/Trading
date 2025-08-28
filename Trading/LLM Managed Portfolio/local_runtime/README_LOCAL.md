# Local LLM Trading System

A complete local LLM-powered trading system that operates entirely within the `local_runtime/` directory without modifying the original `Portfolio Scripts Schwab/` directory.

## 🎯 Overview

This system replicates the functionality of the Schwab portfolio system but replaces external LLM dependency with a sophisticated local multi-model analysis pipeline. It provides the same interface and compatibility while running entirely on local infrastructure.

## 🏗️ Architecture

```
local_runtime/
├── main_local.py              # Main system entry point
├── local_llm_server.py        # Multi-model LLM inference server
├── llm_analysis_pipeline.py   # 4-model analysis orchestration
├── context_assembler.py       # Portfolio data preparation for LLMs
├── document_generator.py      # Standard format document generation
├── local_trading_executor.py  # Trading execution orchestrator
├── local_start.py            # Quick start and system info
├── Portfolio Scripts Schwab/ # Complete copy of portfolio system
└── README_LOCAL.md           # This file
```

## 🤖 LLM Models

The system uses 4 specialized financial LLM models:

1. **News Analysis**: `AdaptLLM/Llama-3-FinMA-8B-Instruct`
   - Financial news sentiment and catalyst identification
   - 8GB VRAM, 8-bit quantization
   - Earnings, FDA approvals, analyst upgrades

2. **Market Analysis**: `Qwen/Qwen2.5-14B-Instruct`
   - Technical analysis and pattern recognition
   - 20GB VRAM, 4-bit quantization
   - Support/resistance, momentum, volume analysis

3. **Trading Decision**: `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`
   - Core trading recommendations and position sizing
   - 20GB VRAM, 4-bit quantization
   - BUY/SELL/HOLD decisions with rationale

4. **Risk Validation**: `microsoft/Phi-3-medium-4k-instruct`
   - Fast risk compliance and safety checks
   - 8GB VRAM, 8-bit quantization
   - Position limits, cash reserves, concentration risk

## 🚀 Quick Start

### 1. Basic System Information
```bash
python local_start.py
```

### 2. Test Components (No GPU Required)
```bash
python main_local.py --test-components --force-cpu
```

### 3. Analysis Only (No Trading)
```bash
python main_local.py --analysis-only --force-cpu
```

### 4. Full Trading Execution (GPU Required)
```bash
python main_local.py
```

## 📋 Command Line Options

```bash
python main_local.py [OPTIONS]

Options:
  --analysis-only     Generate analysis and documents without trading
  --test-components   Test LLM components without trading
  --force-cpu         Force CPU-only mode (no GPU required)
  --full-pipeline     Use all 4 models instead of quick mode
  --no-documents      Skip document generation
  --models [MODELS]   Specify which models to enable
  --help             Show help message
```

## ⚙️ Configuration Modes

### Quick Mode (Default)
- Uses only `trading_decision` + `risk_validation` models
- Faster execution, lower resource requirements
- Suitable for most trading scenarios

### Full Pipeline Mode
- Uses all 4 models: `news_analysis`, `market_analysis`, `trading_decision`, `risk_validation`
- Comprehensive analysis with maximum insights
- Requires more compute resources

### CPU Mode
- Forces CPU-only inference (no GPU required)
- Slower but compatible with any hardware
- Good for testing and analysis-only modes

## 🔧 Installation Requirements

### Base Requirements
```bash
pip install torch torchvision torchaudio
pip install transformers accelerate
pip install vllm  # For GPU inference
pip install yfinance pandas numpy matplotlib
pip install pandas-market-calendars pytz
```

### GPU Requirements (Optional)
- NVIDIA GPU with CUDA support
- Minimum 8GB VRAM for risk validation model
- 20GB+ VRAM recommended for full pipeline
- CUDA 12.1+ compatible drivers

### CPU Mode (Fallback)
- Any modern CPU with 16GB+ RAM
- Slower inference but fully functional
- Good for analysis and testing

## 📊 System Workflow

1. **Initialization**
   - Load portfolio state from copied system
   - Initialize market data fetcher
   - Configure LLM models based on mode

2. **Context Assembly**
   - Gather current portfolio positions
   - Fetch real-time market data
   - Prepare structured context for LLM analysis

3. **LLM Analysis Pipeline**
   - Run models in sequence: News → Market → Trading → Risk
   - Each model contributes specialized analysis
   - Validate and synthesize recommendations

4. **Document Generation**
   - Convert LLM output to standard `trading_recommendation_*.md` format
   - Ensure compatibility with existing parsers
   - Include risk management and execution notes

5. **Trade Execution**
   - Parse generated recommendations
   - Validate against safety constraints
   - Execute through portfolio management system

6. **Reporting**
   - Update portfolio state
   - Generate performance reports
   - Create analysis charts

## 🛡️ Safety Features

### Multi-Layer Validation
- LLM-based risk validation model
- Hard-coded position sizing limits
- Cash reserve requirements
- Concentration risk checks

### Risk Boundaries
- Maximum 20% position size
- Minimum 5% cash reserve
- Maximum 60% top-3 concentration
- Stop-loss compliance

### Emergency Circuit Breakers
- Daily/weekly loss limits
- Minimum portfolio value thresholds
- Volatility spike protection

## 📁 File Integration

The system maintains full compatibility with the original Schwab system:

- **Portfolio State**: Uses same `portfolio_state.json` format
- **Trading Documents**: Generates standard `trading_recommendation_*.md` files
- **Performance History**: Updates `portfolio_performance_history.csv`
- **Analysis Files**: Creates `daily_portfolio_analysis.md`

## 🔍 Monitoring and Debugging

### Log Output
The system provides comprehensive logging:
```
🤖 Initializing Local LLM Trading System
🔄 Starting LLM server initialization...
📊 LLM Server Status: {...}
🧠 Running local LLM analysis pipeline...
⚡ Executing 3 trading recommendations...
✅ LOCAL LLM TRADING EXECUTION SUMMARY
```

### Health Checks
```bash
python main_local.py --test-components
```
Tests all components and reports status.

### Troubleshooting
- **CUDA Issues**: Use `--force-cpu` flag
- **Memory Issues**: Use quick mode (default)
- **Model Loading Errors**: Check VRAM availability
- **Import Errors**: Verify dependencies installed

## 🎯 Performance Expectations

### GPU Mode (Full Pipeline)
- Model loading: 2-5 minutes
- Analysis pipeline: 30-90 seconds
- Trade execution: 5-15 seconds
- Total runtime: 3-7 minutes

### CPU Mode (Quick Analysis)
- Model loading: 5-10 minutes
- Analysis pipeline: 3-8 minutes
- Trade execution: 5-15 seconds
- Total runtime: 8-18 minutes

### Resource Usage
- **Full Pipeline + GPU**: 40GB+ VRAM, 16GB+ RAM
- **Quick Mode + GPU**: 20GB+ VRAM, 8GB+ RAM
- **CPU Only**: 0GB VRAM, 32GB+ RAM

## 🔄 Integration with Original System

The local LLM system is designed for seamless integration:

1. **Preserves Original Directory**: No changes to `Portfolio Scripts Schwab/`
2. **Compatible State Files**: Uses same portfolio state format
3. **Same API Interfaces**: Drop-in replacement for document workflow
4. **Standard Output Format**: Generates compatible trading documents

## 💡 Usage Tips

### For Development
```bash
# Test without GPU
python main_local.py --test-components --force-cpu

# Quick analysis only
python main_local.py --analysis-only --force-cpu
```

### For Production
```bash
# Full execution with safety validation
python main_local.py

# Analysis with all models
python main_local.py --analysis-only --full-pipeline
```

### For Resource-Constrained Systems
```bash
# Minimal CPU mode
python main_local.py --analysis-only --force-cpu --models trading_decision
```

## 📚 Next Steps

1. **Installation**: Follow installation.sh requirements
2. **Testing**: Run `python main_local.py --test-components`
3. **Configuration**: Adjust model selection based on hardware
4. **Integration**: Run alongside or replace existing document workflow
5. **Monitoring**: Review generated documents and trade execution logs

The system provides a complete local alternative to external LLM dependencies while maintaining full compatibility with the existing Schwab trading infrastructure.