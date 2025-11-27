# yfinance Rate Limit Workarounds (2025)

## Problem Overview

As of 2025, Yahoo Finance has tightened rate limits to manage increased traffic. yfinance is **not an official API** - it scrapes Yahoo Finance web endpoints. When Yahoo detects many rapid requests from the same IP or pattern, it returns HTTP 429 "Too Many Requests" errors or may temporarily ban requests.

## Current Implementation Status

### ✅ Already Implemented
1. **24-Hour Caching** - `FinancialDataCache` reduces redundant API calls
2. **Error Handling** - Try/except blocks catch failures gracefully
3. **Data Quality Assessment** - Validates fetched data completeness

### ❌ Missing (Need to Add)
1. **Delays Between Requests** - No time.sleep() in batch_fetch()
2. **Exponential Backoff Retry** - No retry logic for 429 errors
3. **Custom User-Agent** - Using default yfinance headers
4. **Rate Limit Detection** - No specific handling for HTTP 429

## Recommended Workarounds

### 1. Add Delays Between Requests ⭐ **HIGH PRIORITY**

**Implementation:**
```python
import time

def batch_fetch(self, tickers: List[str], delay: float = 2.0):
    """Fetch with delays to avoid rate limits"""
    results = {}

    for i, ticker in enumerate(tickers):
        logger.info(f"Fetching {i+1}/{len(tickers)}: {ticker}")
        data = self.fetch_financial_data(ticker)
        results[ticker] = data

        # Add delay between requests (except for last one)
        if i < len(tickers) - 1:
            time.sleep(delay)  # 2-3 seconds recommended

    return results
```

**Benefits:**
- Simple and effective
- 2-3 second delays prevent most 429 errors
- Works with existing caching system

### 2. Exponential Backoff Retry Logic ⭐ **HIGH PRIORITY**

**Implementation:**
```python
import time
from requests.exceptions import HTTPError

def fetch_with_retry(self, ticker: str, max_retries: int = 3):
    """Fetch with exponential backoff retry"""

    for attempt in range(max_retries):
        try:
            return self.fetch_financial_data(ticker)

        except HTTPError as e:
            if e.response.status_code == 429:  # Too Many Requests
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # 1s, 2s, 4s, 8s...
                    logger.warning(f"Rate limit hit for {ticker}, retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Rate limit persists after {max_retries} retries: {ticker}")
                    return None
            else:
                raise  # Re-raise non-429 errors
```

**Benefits:**
- Automatically retries on rate limits
- Exponential delays (1s, 2s, 4s...) give Yahoo time to reset
- Graceful degradation if retries fail

### 3. Custom User-Agent Headers

**Implementation:**
```python
import yfinance as yf

# Set custom headers globally
yf.set_tz_cache_location("cache")  # Optional cache location

# Per-request headers (if yfinance supports)
stock = yf.Ticker(ticker, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})
```

**Benefits:**
- Some users report 200 responses instead of 429 with different User-Agent
- Makes requests look more like browser traffic
- Lower priority than delays/retries

### 4. Upgrade yfinance Package

**Check Current Version:**
```bash
pip show yfinance
```

**Upgrade to Latest:**
```bash
pip install --upgrade yfinance
```

**Recommended:** Version 0.2.54+ (fixes some 429 bugs)

### 5. Leverage Cache More Aggressively

**Current:** 24-hour cache
**Recommendation:** Extend to 48-72 hours for fundamental data (doesn't change daily)

**Implementation:**
```python
# In FinancialDataCache.__init__
cache_hours = 48  # 2 days instead of 1 day
```

**Benefits:**
- Fundamental data (revenue, assets, etc.) changes quarterly
- Price data can still be fetched fresh from Schwab API
- Dramatically reduces yfinance API calls

### 6. Batch Size Limits

**Implementation:**
```python
def batch_fetch(self, tickers: List[str], batch_size: int = 50):
    """Process in smaller batches with breaks"""

    all_results = {}

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} tickers)")

        batch_results = self._fetch_batch_with_delay(batch, delay=2.0)
        all_results.update(batch_results)

        # Longer break between batches
        if i + batch_size < len(tickers):
            logger.info("Pausing 30s between batches...")
            time.sleep(30)

    return all_results
```

**Benefits:**
- Process large watchlists (500+ tickers) without hitting limits
- 30-second breaks between batches reset rate limit counters
- Progress tracking for long-running fetches

## Priority Implementation Order

### Phase 1: Quick Wins (Immediate)
1. ✅ Add `time.sleep(2.0)` in batch_fetch() between requests
2. ✅ Extend cache to 48 hours for fundamentals

### Phase 2: Robustness (This Week)
3. ✅ Implement exponential backoff retry logic
4. ✅ Add batch size limits for large watchlists

### Phase 3: Optimization (Optional)
5. ⚠️ Test custom User-Agent headers
6. ⚠️ Upgrade yfinance to latest version

## Alternative Data Sources (If Rate Limits Persist)

### Finnhub API (Recommended)
- **Free Tier:** 60 API calls/minute
- **Already Integrated:** Used for news fetching
- **Coverage:** Fundamentals, earnings, financials
- **Cost:** Free tier sufficient for portfolio analysis

### Alpha Vantage
- **Free Tier:** 25 API calls/day
- **Coverage:** Fundamental data, earnings
- **Cost:** Free tier very limited

### Schwab API (Already Available)
- **Use for:** Real-time price data, historical prices
- **Use yfinance for:** Fundamentals, financials (lower frequency)
- **Benefit:** Reduce yfinance calls by ~50%

## Testing Rate Limit Handling

```bash
# Test with small watchlist first
cd "Portfolio Scripts Schwab"
python analysis/quality_analysis_script.py --watchlist-limit 10

# Monitor for 429 errors in logs
tail -f quality_analysis.log | grep -i "429\|rate limit"

# Test with larger watchlist
python analysis/quality_analysis_script.py --watchlist-limit 100
```

## Monitoring & Alerts

**Add Logging for Rate Limits:**
```python
if 'Too Many Requests' in str(e) or '429' in str(e):
    logger.error(f"⚠️  RATE LIMIT HIT: {ticker} - Consider adding delays")
    # Optionally: Send alert, pause execution
```

**Track Success Rate:**
```python
success_rate = success_count / len(tickers)
if success_rate < 0.8:  # Less than 80% success
    logger.warning(f"⚠️  Low success rate ({success_rate:.1%}) - Rate limits likely")
```

## Summary

**Immediate Actions:**
1. Add 2-second delays between yfinance requests in batch_fetch()
2. Extend cache to 48 hours for fundamental data
3. Implement exponential backoff retry for 429 errors
4. Add batch size limits (50 tickers per batch with 30s breaks)

**Expected Impact:**
- **Current:** Likely 429 errors on watchlists >50 tickers
- **After Fixes:** Should handle 500+ tickers reliably with caching + delays

**Long-term Strategy:**
- Use Schwab API for price data (already implemented)
- Use yfinance for fundamentals only (quarterly updates)
- Consider Finnhub API as backup data source
- Aggressive caching reduces API dependency by 90%+
