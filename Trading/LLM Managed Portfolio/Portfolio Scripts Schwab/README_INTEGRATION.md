# Schwab Account Integration & Live Trading

This document describes the new Schwab account data synchronization and live trading execution features added to the portfolio management system.

## 🎉 What's New

### ✅ Account Data Synchronization
- **Pull real account positions** directly from your Schwab brokerage account
- **Automatic reconciliation** between local state and actual holdings
- **Cash balance sync** to ensure accurate available funds tracking
- **Transaction history** retrieval for auditing

### ✅ Live Trade Execution
- **Real order placement** through Schwab API (market and limit orders)
- **Dry-run mode** for safe testing without real trades
- **Order status tracking** and confirmation
- **Automatic position reconciliation** after trade execution

### ✅ Safety & Risk Management
- **Pre-trade validation** checks for buying power, position limits, and cash reserves
- **Batch order validation** for cash flow feasibility
- **Risk metrics** including position concentration and diversification analysis
- **Daily trade limits** to prevent over-trading

## 📋 New Modules

### 1. `schwab_account_manager.py`
Manages account data synchronization with Schwab.

**Key Features:**
- Discover linked Schwab accounts
- Fetch real-time account positions and balances
- Sync Schwab data to local `portfolio_state.json`
- Generate comprehensive account summaries
- Retrieve transaction history

### 2. `schwab_trade_executor.py`
Handles live trade execution through Schwab API.

**Key Features:**
- Place market orders (buy/sell)
- Place limit orders with price constraints
- Order status tracking and confirmation
- Dry-run mode for testing
- Execution summary reports
- Automatic reconciliation after trades

### 3. `schwab_safety_validator.py`
Provides pre-trade validation and risk management.

**Key Features:**
- Pre-execution order validation
- Batch order cash flow analysis
- Position size and concentration checks
- Cash reserve enforcement
- Daily trade limit monitoring
- Portfolio risk summaries

## 🚀 Usage

### Account Synchronization

Pull your actual Schwab account positions into the local portfolio:

```bash
# Sync account data (requires Schwab API credentials)
python main.py --sync-schwab-account --dry-run
```

This will:
1. Connect to your Schwab account via API
2. Fetch all current positions and cash balance
3. Compare with local `portfolio_state.json`
4. Update local state to match Schwab account
5. Generate updated portfolio report

### View Account Status

Display comprehensive account information:

```bash
# Show detailed account status
python main.py --account-status --dry-run
```

Output includes:
- Account type and number
- Cash balance and available funds
- All equity positions with shares and values
- Buying power and equity totals

### Risk Analysis

View portfolio risk metrics:

```bash
# Display risk summary
python main.py --risk-summary --dry-run
```

Output includes:
- Total portfolio value and cash percentage
- Maximum position size and concentration
- Diversification metrics
- Risk flags and warnings
- Trades executed today

### Dry-Run Trading Mode

Test trade execution with real account data but without placing actual orders:

```bash
# Execute trades in dry-run mode (safe testing)
python main.py --dry-run
```

This will:
1. Parse trading recommendations from documents
2. Validate orders against real account data
3. **Simulate** trade execution (no real orders placed)
4. Show what would have happened
5. Generate reports with simulated results

### Live Trading Mode (⚠️ Real Money!)

Execute actual trades through Schwab API:

```bash
# Execute REAL trades (requires explicit --live-trading flag)
python main.py --live-trading
```

**⚠️ WARNING:** This mode places REAL orders with REAL money!

- Requires explicit `--live-trading` flag (safety mechanism)
- All trades are logged to `trade_execution.log`
- Automatic reconciliation after execution
- Execution summary printed at completion

### Test Schwab API Connection

Verify your Schwab API credentials and connectivity:

```bash
# Test API connection
python main.py --test-schwab-api
```

## 🔐 Configuration

### Prerequisites

1. **Schwab Developer Account**: Create at [developer.schwab.com](https://developer.schwab.com/)
2. **API Credentials**: Obtain API key and app secret
3. **Callback URL**: Configure `https://127.0.0.1:8182` in your Schwab app
4. **schwab-py Library**: Install via `pip install schwab-py`

### Credentials File

Create `schwab_credentials.json` in the `Portfolio Scripts Schwab/` directory:

```json
{
    "api_key": "YOUR_API_KEY_HERE",
    "app_secret": "YOUR_APP_SECRET_HERE",
    "callback_url": "https://127.0.0.1:8182",
    "token_path": "./schwab_token.json"
}
```

**⚠️ IMPORTANT:** Never commit `schwab_credentials.json` to git! It's already in `.gitignore`.

## 🛡️ Safety Features

### Multiple Protection Layers

1. **Explicit Live Trading Flag**: Must use `--live-trading` for real orders
2. **Dry-Run Default**: System defaults to simulation unless explicitly live
3. **Pre-Trade Validation**: Orders validated before execution
4. **Position Limits**: Enforced maximum position sizes
5. **Cash Reserves**: Minimum cash percentage maintained
6. **Daily Trade Limits**: Prevents over-trading
7. **Duplicate Detection**: Prevents accidental duplicate orders

### Configurable Safety Limits

Default safety limits (can be configured):
- **Max Position Size**: 30% of portfolio
- **Max Daily Trades**: 50 trades per day
- **Min Cash Reserve**: 5% of portfolio value
- **Max Position Value**: $50,000 per position

### Order Priority System

Orders are executed in cash-flow-optimized order:
1. High priority sells (generate cash first)
2. Position reductions
3. Medium priority sells
4. High priority buys (execute with available cash)
5. Low priority sells
6. Medium priority buys
7. Low priority buys

## 📊 Command Reference

### Read-Only Commands (No Trading)
```bash
# Generate report without trades
python main.py --report-only

# View account status
python main.py --account-status --dry-run

# View risk analysis
python main.py --risk-summary --dry-run

# Test API connection
python main.py --test-schwab-api

# Test document parsing
python main.py --test-parser
```

### Account Synchronization
```bash
# Sync portfolio with Schwab account
python main.py --sync-schwab-account --dry-run

# Load previous day positions
python main.py --load-previous-day
```

### Trading Commands
```bash
# Dry-run mode (simulated trades)
python main.py --dry-run

# Live trading mode (REAL trades!)
python main.py --live-trading

# Full execution mode (default behavior)
python main.py
```

## 🔄 Typical Workflows

### Workflow 1: Daily Portfolio Sync
```bash
# Step 1: Sync account data
python main.py --sync-schwab-account --dry-run

# Step 2: Review account status
python main.py --account-status --dry-run

# Step 3: Check risk metrics
python main.py --risk-summary --dry-run

# Step 4: Generate report
python main.py --report-only
```

### Workflow 2: Testing New Trading Strategy
```bash
# Step 1: Test document parsing
python main.py --test-parser

# Step 2: Dry-run with real account data
python main.py --dry-run

# Step 3: Review results
python main.py --report-only

# Step 4: If satisfied, execute live (optional)
python main.py --live-trading
```

### Workflow 3: Safe Live Trading
```bash
# Step 1: Sync account
python main.py --sync-schwab-account --dry-run

# Step 2: Test in dry-run mode
python main.py --dry-run

# Step 3: Execute live trades
python main.py --live-trading

# Step 4: Verify reconciliation
python main.py --account-status --dry-run
```

## 📁 File Structure

```
Portfolio Scripts Schwab/
├── main.py                        # Main entry point (updated)
├── trade_executor.py              # Trade executor (updated with live support)
├── schwab_account_manager.py      # NEW: Account sync
├── schwab_trade_executor.py       # NEW: Live order execution
├── schwab_safety_validator.py     # NEW: Safety & risk checks
├── schwab_data_fetcher.py         # Market data (existing)
├── portfolio_manager.py           # Portfolio state (existing)
├── report_generator.py            # Reports (existing)
├── schwab_credentials.json        # Your API credentials (create this)
├── schwab_token.json              # OAuth tokens (auto-generated)
└── README_INTEGRATION.md          # This file
```

## 🔧 Troubleshooting

### "No account hash available"
- Run `python main.py --sync-schwab-account --dry-run` to discover accounts
- Ensure Schwab API credentials are correctly configured

### "Schwab API client not available"
- Check `schwab_credentials.json` exists and has valid credentials
- Verify API key and app secret from Schwab developer portal
- Ensure callback URL matches exactly: `https://127.0.0.1:8182`

### "Order rejected: HTTP 401"
- API token may have expired - delete `schwab_token.json` and re-authenticate
- Verify API key and app secret are correct

### "Account manager not initialized"
- Ensure you're using `--dry-run` or `--live-trading` flag
- These flags enable the account manager and live trading features

### Trades not executing
- Verify market is open (required for live trading)
- Check `trade_execution.log` for detailed error messages
- Ensure sufficient buying power in account
- Verify orders pass pre-trade validation

## 📝 Logging

All trade activity is logged to `trade_execution.log`:
- Order placement attempts
- Execution results
- Error messages
- Reconciliation status

Review this log after each trading session for audit trail.

## ⚠️ Important Warnings

1. **Live Trading Risk**: `--live-trading` mode places REAL orders with REAL money. Always test with `--dry-run` first!

2. **Market Hours**: Live trading only works during market hours (9:30 AM - 4:00 PM ET, Monday-Friday, on trading days)

3. **API Rate Limits**: Schwab API has rate limits (120 orders/minute). The system respects these limits.

4. **Account Reconciliation**: Always verify positions after live trades with `--account-status`

5. **Credentials Security**: NEVER commit `schwab_credentials.json` to version control

## 🚦 Testing Checklist

Before using live trading in production:

- [ ] Test API connection with `--test-schwab-api`
- [ ] Sync account data with `--sync-schwab-account --dry-run`
- [ ] Verify account status with `--account-status --dry-run`
- [ ] Review risk metrics with `--risk-summary --dry-run`
- [ ] Test trade parsing with `--test-parser`
- [ ] Execute dry-run trades with `--dry-run`
- [ ] Verify dry-run results with `--report-only`
- [ ] Test with 1-share orders in `--live-trading` mode
- [ ] Verify reconciliation after test trades
- [ ] Review `trade_execution.log` for any issues

## 📚 Additional Resources

- **Schwab API Documentation**: [developer.schwab.com](https://developer.schwab.com/)
- **schwab-py Library**: [schwab-py.readthedocs.io](https://schwab-py.readthedocs.io/)
- **Original README**: [README_SCHWAB.md](README_SCHWAB.md)

## 🤝 Support

For issues or questions:
1. Check `trade_execution.log` for detailed error messages
2. Review Schwab API status at developer portal
3. Test with `--dry-run` to isolate issues
4. Verify API credentials and token validity

---

**Remember**: Always test with `--dry-run` before using `--live-trading`! 🛡️
