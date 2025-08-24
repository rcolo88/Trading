# Portfolio Scripts Schwab - Schwab API Implementation

This folder contains an enhanced version of the Portfolio Scripts that replaces yfinance with the official Schwab API through the schwab-py library.

## Schwab API Overview

### Key Advantages over yfinance:
- **Professional-grade data**: Direct access to Schwab's market data
- **Higher reliability**: No scraping, official API endpoints
- **Real-time quotes**: More current pricing data
- **Extended functionality**: Access to account data, trading capabilities
- **Better rate limits**: Professional API limits vs yfinance limitations

### API Capabilities:
- **Market Data**: Real-time quotes, historical price data, option chains
- **Price History**: Multiple timeframes (minute, daily, weekly, monthly)
- **Streaming Data**: Real-time websocket streaming for live updates
- **Account Integration**: View positions, balances, transaction history
- **Trading**: Place orders, manage positions (when configured)

## Setup Requirements

### 1. Schwab Developer Account Setup
1. Create developer account at [developer.schwab.com](https://developer.schwab.com/)
2. Create a new application:
   - **API Product**: Select "Accounts and Trading Production"
   - **Order Limit**: 120 orders per minute (recommended)
   - **Callback URL**: `https://127.0.0.1:8182`
3. Wait for Schwab approval (can take 2-5 business days)
4. Obtain your API key and app secret from the developer dashboard

### 2. Installation Requirements
```bash
# Install schwab-py in your trading environment
conda activate trading_env
pip install schwab-py

# Or create new environment
conda create -n schwab_trading python=3.11 schwab-py matplotlib pandas numpy -c conda-forge
```

### 3. Configuration
Create a configuration file with your credentials:
```bash
# Create credentials file (DO NOT COMMIT TO GIT)
touch schwab_credentials.json
```

Add your credentials:
```json
{
    "api_key": "YOUR_API_KEY_HERE",
    "app_secret": "YOUR_APP_SECRET_HERE", 
    "callback_url": "https://127.0.0.1:8182",
    "token_path": "./schwab_token.json"
}
```

## Implementation Plan

### Phase 1: Drop-in Replacement for data_fetcher.py
- ✅ **SchwabDataFetcher class**: Replace DataFetcher with Schwab API calls
- ✅ **Authentication handling**: OAuth2 token management
- ✅ **Quote retrieval**: Replace yfinance quote calls with get_quote()
- ✅ **Historical data**: Replace yfinance download with get_price_history()
- ✅ **Error handling**: Robust error handling and fallback mechanisms

### Phase 2: Enhanced Features
- **Real-time streaming**: WebSocket integration for live price updates
- **Extended market data**: Options data, futures, forex
- **Account integration**: Real portfolio positions from Schwab account
- **Advanced analytics**: Professional-grade market data analysis

### Phase 3: Trading Integration (Optional)
- **Order placement**: Automated trade execution through Schwab API
- **Position management**: Sync with actual Schwab account positions
- **Risk management**: Advanced order types and risk controls

## Files Modified

### Core Files:
- **`schwab_data_fetcher.py`**: New Schwab API-based data fetcher
- **`main.py`**: Updated to use SchwabDataFetcher
- **`requirements_schwab.txt`**: Schwab-specific dependencies

### Configuration:
- **`schwab_config.py`**: Schwab API configuration management
- **`schwab_credentials.json`**: API credentials (user-created, not tracked)

## Usage

### Basic Usage (same as original):
```bash
# Full execution mode
python main.py

# Report only mode  
python main.py --report-only

# Load previous day positions
python main.py --load-previous-day
```

### Schwab-specific Features:
```bash
# Test Schwab API connection
python main.py --test-schwab-api

# Sync with actual Schwab account positions
python main.py --sync-schwab-account

# Use real-time streaming data
python main.py --streaming-mode
```

## API Rate Limits & Best Practices

### Rate Limits:
- **Market Data**: 240 requests per minute per app
- **Streaming**: Concurrent connections allowed
- **Account Data**: Lower limits apply

### Best Practices:
- **Batch requests**: Use get_quotes() for multiple symbols
- **Cache data**: Store frequently accessed data locally
- **Error handling**: Implement exponential backoff for rate limits
- **Token management**: Automatic token refresh handling

## Migration Notes

### Compatibility:
- **Same interface**: Maintains compatibility with existing portfolio system
- **Enhanced reliability**: More stable than yfinance web scraping
- **Professional data**: Higher quality market data

### Potential Issues:
- **Setup complexity**: Requires developer account approval
- **Dependencies**: Additional authentication requirements
- **Costs**: Check Schwab's pricing for API usage

## Support & Resources

### Documentation:
- **schwab-py docs**: [schwab-py.readthedocs.io](https://schwab-py.readthedocs.io)
- **Schwab Developer**: [developer.schwab.com](https://developer.schwab.com)

### Community:
- **Discord**: Schwab API Discord community
- **GitHub**: schwab-py GitHub repository

### Troubleshooting:
- **API Issues**: Contact traderapi@schwab.com
- **Registration Problems**: Common during beta, contact support
- **Rate Limits**: Implement proper backoff strategies

---

**Note**: This implementation provides a professional-grade replacement for yfinance while maintaining full compatibility with the existing portfolio management system. The Schwab API offers more reliable, real-time data that will significantly improve portfolio tracking accuracy.