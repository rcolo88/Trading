# Security & Credentials Management

## 🔒 Protected Files (Never Commit to Git)

The following files contain sensitive information and are protected by `.gitignore`:

### Critical Files
- ✅ `schwab_credentials.json` - Your API key and app secret
- ✅ `schwab_token.json` - OAuth access/refresh tokens
- ✅ `*_credentials.json` - Any credential files
- ✅ `*_token.json` - Any token files
- ✅ `*.token` - Token files with any extension

### Logs & Temporary Data
- ✅ `trade_execution.log` - Contains trade details
- ✅ `*.log` - All log files
- ✅ `*.tmp` - Temporary files

### Configuration
- ✅ `.env` - Environment variables
- ✅ `local_config.json` - Local settings

## 📋 Security Checklist

### Before First Commit
- [ ] Verify `.gitignore` exists in both root and `Portfolio Scripts Schwab/`
- [ ] Confirm `schwab_credentials.json` is listed in `.gitignore`
- [ ] Never create credentials with different names (use template provided)
- [ ] Run `git status` to verify no credential files are staged

### Credential Management
- [ ] Use only `schwab_credentials.json` for credentials (never rename)
- [ ] Keep `schwab_credentials_template.json` (safe to commit - no real credentials)
- [ ] Store backup credentials securely (password manager, encrypted drive)
- [ ] Rotate API keys periodically

### Regular Security Checks
```bash
# Check if any sensitive files are tracked by git
git ls-files | grep -E "(credentials|token|\.log)"

# This should return NOTHING. If it returns files, they need to be removed:
git rm --cached <filename>
```

## 🛡️ What IS Safe to Commit

### Template Files (Safe - No Real Credentials)
- ✅ `schwab_credentials_template.json` - Template with placeholder values
- ✅ `README*.md` - Documentation files
- ✅ `*.py` - Python source code (modules)

### Portfolio State Files
- ✅ `portfolio_state.json` - **May contain your positions!**
  - If you want to keep positions private, add to `.gitignore`
- ✅ `portfolio_performance_history.csv` - Historical data
- ✅ `daily_portfolio_analysis.md` - Portfolio analysis

**⚠️ PRIVACY NOTE**: If you don't want to share your actual positions/balances publicly:
```bash
# Add these to .gitignore:
echo "portfolio_state.json" >> .gitignore
echo "Portfolio States/" >> .gitignore
echo "portfolio_performance_history.csv" >> .gitignore
echo "daily_portfolio_analysis.md" >> .gitignore
```

## 🔐 API Security Best Practices

### 1. Schwab Developer Account
- Use a dedicated Schwab developer account (not your main trading account)
- Set appropriate API permissions (read-only for testing)
- Monitor API usage in developer portal

### 2. Callback URL Security
- Use `https://127.0.0.1:8182` (localhost)
- Never expose callback endpoint to public internet
- Verify URL matches exactly in Schwab developer portal

### 3. Token Management
- Tokens expire after 30 minutes (access token)
- Refresh tokens valid for 7 days
- System handles automatic refresh
- Delete `schwab_token.json` to force re-authentication

### 4. API Rate Limits
- Respect Schwab's rate limits (120 orders/minute)
- System includes automatic rate limiting
- Monitor usage to avoid temporary bans

## 🚨 What to Do If Credentials Are Exposed

### Immediate Actions
1. **Revoke API Keys**
   - Log in to [developer.schwab.com](https://developer.schwab.com/)
   - Delete the compromised application
   - Create a new application with fresh credentials

2. **Remove from Git History** (if already committed)
   ```bash
   # Remove file from git history (use with caution!)
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch schwab_credentials.json" \
     --prune-empty --tag-name-filter cat -- --all

   # Force push (only if repository is private and you're the only user)
   git push origin --force --all
   ```

3. **Contact Schwab Support**
   - Email: traderapi@schwab.com
   - Report potential credential exposure
   - Request security audit if needed

### Prevention for Future
- Enable git pre-commit hooks to prevent credential commits
- Use secret scanning tools (e.g., `git-secrets`, `trufflehog`)
- Regular security audits of committed files

## 📁 File Permission Recommendations

Set restrictive permissions on sensitive files:
```bash
# Make credentials readable only by you
chmod 600 schwab_credentials.json
chmod 600 schwab_token.json

# Make scripts executable
chmod +x main.py
```

## 🔍 Security Audit Commands

### Check for Exposed Credentials
```bash
# Search for potential API keys in codebase
grep -r "api_key" --exclude-dir=.git --exclude="*.md"

# Search for tokens
grep -r "token" --exclude-dir=.git --exclude="*.md"

# List all JSON files (review for sensitive data)
find . -name "*.json" -not -path "./.git/*"
```

### Verify .gitignore is Working
```bash
# Create a test credentials file
echo '{"test": "data"}' > schwab_credentials.json

# Check git status (should NOT show the file)
git status

# Clean up test file
rm schwab_credentials.json
```

## 🔐 Environment Variables Alternative

For additional security, consider using environment variables instead of JSON files:

```bash
# Set environment variables (Linux/Mac)
export SCHWAB_API_KEY="your_key_here"
export SCHWAB_APP_SECRET="your_secret_here"

# Or use a .env file (add .env to .gitignore!)
echo "SCHWAB_API_KEY=your_key_here" >> .env
echo "SCHWAB_APP_SECRET=your_secret_here" >> .env
```

Then modify `schwab_data_fetcher.py` to read from environment variables as fallback.

## 📞 Security Resources

- **Schwab API Support**: traderapi@schwab.com
- **Developer Portal**: [developer.schwab.com](https://developer.schwab.com/)
- **Git Security Guide**: [https://git-scm.com/book/en/v2/GitHub-Managing-Secrets](https://git-scm.com/book/en/v2/GitHub-Managing-Secrets)

## ✅ Pre-Commit Checklist

Before every commit:
- [ ] Run `git status` - verify no credential files listed
- [ ] Run `git diff --staged` - review all changes
- [ ] Check no API keys, tokens, or passwords in code
- [ ] Verify `.gitignore` is up to date
- [ ] Test build succeeds without errors

## 🎓 Training Materials

For team members or future reference:
1. Review this SECURITY.md document
2. Understand what files are sensitive
3. Know how to check if credentials are exposed
4. Practice secure credential management
5. Report any security concerns immediately

---

**Remember**: It's easier to prevent credential exposure than to fix it after the fact! 🛡️
