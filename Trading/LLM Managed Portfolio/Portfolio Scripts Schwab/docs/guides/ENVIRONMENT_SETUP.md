# Environment Setup Guide

## Primary Conda Environment

- **Environment Name**: `trading_env` (recommended) or `options` (legacy)
- **Python Version**: 3.11+
- **Location**: `/Users/robertcologero/opt/anaconda3/envs/trading_env/`

## Environment Creation

```bash
# Create new recommended environment
conda create -n trading_env python=3.11 yfinance matplotlib pandas numpy pandas-market-calendars pytz scipy -c conda-forge -y

# Activate environment
conda activate trading_env

# Or use existing legacy environment
conda activate options
```

## Dependencies

### Core Requirements
```bash
conda install -n trading_env yfinance matplotlib pandas numpy pandas-market-calendars pytz scipy -c conda-forge -y
```

**Packages**:
- **yfinance** - Market data retrieval
- **matplotlib** - Chart generation
- **pandas** - Data manipulation and analysis
- **numpy** - Numerical operations
- **pandas-market-calendars** - Market hours validation
- **pytz** - Timezone handling
- **scipy** - Scientific computing

### Agent System Requirements
```bash
pip install finnhub-python>=2.4.0 requests>=2.31.0 transformers>=4.30.0
```

**Packages**:
- **finnhub-python** >= 2.4.0 - Finnhub API for news fetching
- **requests** >= 2.31.0 - HuggingFace API communication
- **transformers** >= 4.30.0 - Model configurations and utilities

### Optional (for PDF parsing)
```bash
pip install pdfplumber
# OR
pip install PyPDF2
```

## Troubleshooting

### pip "bad interpreter" Error

**Symptom**: `pip: bad interpreter: No such file or directory` when trying to install packages

**Root Cause**: pip executable has incorrect shebang path (often `/Users/robertcologero/opt/...` instead of `/opt/...`)

**Solutions**:

```bash
# Option 1: Use python -m pip (immediate workaround)
/opt/anaconda3/envs/trading_env/bin/python -m pip install <package>

# Option 2: Reinstall pip to fix shebang (permanent fix)
/opt/anaconda3/bin/conda install -n trading_env --force-reinstall pip -y

# Verify fix
head -1 /opt/anaconda3/envs/trading_env/bin/pip  # Should show correct path
pip --version  # Should work without errors
```

**Note**: This issue can occur when conda environments are moved or when environment paths change. Always use `conda install --force-reinstall pip` to regenerate pip with correct paths.

### Common Issues

**Import Errors**:
- Ensure you've activated the correct environment: `conda activate trading_env`
- Verify package installation: `pip list | grep <package_name>`
- Reinstall if needed: `pip install --force-reinstall <package>`

**API Key Issues**:
- **Schwab API**: Configure `schwab_credentials.json` with your API credentials
- **Finnhub API**: Set environment variable `export FINNHUB_API_KEY='your_key_here'`
- Get free Finnhub key at https://finnhub.io/

**Path Issues**:
- Always run scripts from the project root directory
- Use absolute paths when referencing files
- Check working directory: `pwd`

## Verification

Test that your environment is set up correctly:

```bash
# Activate environment
conda activate trading_env

# Test imports
python -c "import yfinance; import pandas; import numpy; import matplotlib; print('✅ Core dependencies OK')"

# Test Schwab connection (requires credentials)
python "Portfolio Scripts Schwab/main.py" --test-schwab-api

# Test agent system (requires API keys)
cd "Portfolio Scripts Schwab"
python -c "from agents.base_agent import BaseAgent; print('✅ Agent system OK')"
```

## Requirements Files

Reference requirements files are available:

- `requirements_schwab.txt` - Core Schwab API requirements
- `requirements_hf.txt` - HuggingFace agent requirements

Install from requirements:
```bash
pip install -r requirements_schwab.txt
pip install -r requirements_hf.txt
```

## Environment Management

**List environments**:
```bash
conda env list
```

**Remove environment** (if needed):
```bash
conda env remove -n trading_env
```

**Export environment** (for reproducibility):
```bash
conda env export -n trading_env > environment.yml
```

**Create from exported file**:
```bash
conda env create -f environment.yml
```

## Next Steps

After environment setup:
1. Configure API credentials (Schwab, Finnhub)
2. Test system with `--test-schwab-api` flag
3. Run report generation: `python main.py --report-only`
4. Review `docs/guides/QUICK_START.md` for workflow examples
