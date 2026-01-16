# Quality Stock Analysis System

Welcome! 🎉 This is a **simple, powerful tool** that analyzes stocks using academic research-backed quality metrics. No fancy AI or trading - just solid, data-driven stock analysis to help you find high-quality companies.

## 🚀 Quick Start (5 Minutes!)

### Step 1: Install Dependencies
```bash
cd schwab_portfolio
pip install -r requirements_schwab.txt
```

### Step 2: Run Your First Analysis
```bash
# Analyze the top 50 S&P 500 stocks
python main_quality_analysis.py --index sp500 --limit 50
```

### Step 3: View Results
Check the `outputs/` folder for two files:
- **`quality_analysis_summary.txt`** - Easy-to-read summary with recommendations
- **`quality_analysis.json`** - Detailed data for programmers

**That's it!** You'll get quality scores, buy/sell recommendations, and analysis of your portfolio.

---

## 📊 What Does This Do?

This system evaluates stocks using the **NEW_5FACTOR Quality Framework** based on academic research:

### 5 Quality Dimensions

| Dimension | Weight | Metrics |
|-----------|--------|---------|
| **Profitability** | 35% | Gross Profitability, ROE, ROIC |
| **Earnings Quality** | 20% | Accrual Ratio, Cash Conversion, Piotroski F-Score |
| **Growth Quality** | 15% | Asset Growth (inverse), Revenue CAGR, Margin Trend |
| **Safety** | 15% | Beta, Altman Z-Score, Debt/EBITDA, Interest Coverage |
| **ROE Persistence** | 15% | Years with ROE >15%, ROE Trend, ROE Stability |

### Market Cap Adjustments

Smaller companies use shorter lookback periods due to data availability:

| Tier | Market Cap | Multiplier |
|------|------------|------------|
| Mega Cap | > $200B | 1.25x |
| Large Cap | $10B - $200B | 1.00x |
| Mid Cap | $2B - $10B | 0.75x |
| Small Cap | $300M - $2B | 0.50x |
| Micro Cap | < $300M | 0.35x |

### Quality Tiers

| Score Range | Tier | Interpretation |
|-------------|------|----------------|
| 85-100 | Elite | Exceptional quality |
| 70-84 | Strong | Good companies |
| 50-69 | Moderate | Average quality |
| 0-49 | Weak | Concerning fundamentals |

It then gives each stock a **quality score** (0-100) and **tier** (Elite/Strong/Moderate/Weak), and ranks them by quality within any market index.

### Score Multipliers

Final scores are adjusted by:
- **Safety Multiplier** (0.70-1.00): Based on leverage, Z-score, volatility
- **Data Quality Multiplier** (0.80-1.00): Based on data availability

---

## 🎯 Common Use Cases

### Daily Stock Screening
```bash
# Check 50 top S&P 500 stocks (2-5 minutes)
python main_quality_analysis.py --index sp500 --limit 50
```

### Weekly Deep Dive
```bash
# Analyze entire S&P 500 (12-17 minutes)
python main_quality_analysis.py --index sp500
```

### Monthly Small Cap Hunt
```bash
# Screen all S&P 1500 stocks for small cap opportunities (45-60 minutes)
python main_quality_analysis.py --index combined_sp
```

### Tech Focus
```bash
# Analyze tech-heavy NASDAQ-100 (3-5 minutes)
python main_quality_analysis.py --index nasdaq100
```

### Individual Stock Analysis
```bash
# Deep dive on specific stock
python main_quality_analysis.py --ticker AAPL

# Research before buying
python main_quality_analysis.py --ticker NVDA

# Check portfolio holding
python main_quality_analysis.py --ticker MSFT
```

**Output:** `outputs/stock_analysis_AAPL_20250116.txt` - Detailed individual analysis

#### When to Use Each Mode

| Mode | Use Case | Output | Time |
|------|----------|--------|------|
| `--index sp500` | Find highest quality stocks in an index | Ranked quality analysis | 12-17 min |
| `--ticker AAPL` | Deep dive on specific stock | Detailed individual analysis | ~5-10 sec |

### International Markets
```bash
# UK stocks (FTSE 100)
python main_quality_analysis.py --index ftse100 --limit 50

# German stocks (DAX)
python main_quality_analysis.py --index dax --limit 30

# Japanese stocks (Nikkei 225)
python main_quality_analysis.py --index nikkei225 --limit 100

# French stocks (CAC 40)
python main_quality_analysis.py --index cac40 --limit 30

# Hong Kong stocks (Hang Seng)
python main_quality_analysis.py --index hangseng --limit 50

# Chinese stocks (Shanghai Composite)
python main_quality_analysis.py --index shanghai --limit 100

# US Small Caps (Russell 2000)
python main_quality_analysis.py --index russell2000 --limit 100

# US Broad Market (Russell 1000)
python main_quality_analysis.py --index russell1000 --limit 100

# US Total Market (Russell 3000)
python main_quality_analysis.py --index russell3000 --limit 100
```

---

## 📈 Available Stock Indexes

The system can analyze stocks from these pre-built indexes:

| Index | Description | Size | Best For | Time | CLI Command |
|-------|-------------|------|----------|------|-------------|
| **`sp500`** | S&P 500 (US Large Cap) | ~500 stocks | Daily screening | 12-17 min | `--index sp500` |
| **`sp400`** | S&P MidCap 400 (US Mid Cap) | ~400 stocks | Mid-sized companies | 10-14 min | `--index sp400` |
| **`sp600`** | S&P SmallCap 600 (US Small Cap) | ~600 stocks | Small companies | 15-20 min | `--index sp600` |
| **`nasdaq100`** | NASDAQ-100 (US Tech) | ~100 stocks | Technology focus | 3-5 min | `--index nasdaq100` |
| **`combined_sp`** | S&P 1500 (US Total) | ~1500 stocks | Comprehensive | 45-60 min | `--index combined_sp` |
| **`ftse100`** | FTSE 100 (UK) | ~100 stocks | UK market | 3-5 min | `--index ftse100` |
| **`dax`** | DAX (Germany) | ~30 stocks | German market | 1-2 min | `--index dax` |
| **`nikkei225`** | Nikkei 225 (Japan) | ~225 stocks | Japanese market | 8-12 min | `--index nikkei225` |
| **`cac40`** | CAC 40 (France) | ~40 stocks | French market | 2-3 min | `--index cac40` |
| **`hangseng`** | Hang Seng (Hong Kong) | ~50 stocks | Hong Kong market | 3-5 min | `--index hangseng` |
| **`shanghai`** | Shanghai Composite (China) | ~1500+ stocks | Chinese market | 60+ min | `--index shanghai` |
| **`russell2000`** | Russell 2000* (US Small Cap) | ~600 stocks | US small caps | 60+ min | `--index russell2000` |
| **`russell1000`** | Russell 1000* (US Large/Mid) | ~900 stocks | US large/mid caps | 40+ min | `--index russell1000` |
| **`russell3000`** | Russell 3000* (US Total) | ~1500 stocks | US total market | 120+ min | `--index russell3000` |

**Note on Russell Indexes:** Russell indexes marked with (*) use S&P indexes as approximations since direct Russell data requires a paid FTSE Russell subscription. Russell 1000 is approximated by combining S&P 500 + S&P MidCap 400 (~900 stocks). Russell 2000 uses S&P SmallCap 600 (~600 stocks). Russell 3000 combines all three S&P indexes (~1500 stocks).

**⚠️ Storage Note:** Large indexes like Russell 2000/3000 and Shanghai Composite will download significant amounts of financial data and may use several GB of disk space for caching. Use `--limit` to analyze fewer stocks if storage is a concern.

### How to Add or Remove Stock Indexes

The system scrapes stock lists from **Wikipedia**. To add a new index:

#### Step 1: Find the Wikipedia Page
Look for the index's Wikipedia page (like `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies`)

#### Step 2: Add to Code (Advanced)
Edit `schwab_portfolio/data/watchlist_config.py`:

```python
class WatchlistIndex(Enum):
    SP500 = "sp500"
    SP400 = "sp400"
    SP600 = "sp600"
    NASDAQ100 = "nasdaq100"
    COMBINED_SP = "combined_sp"
    RUSSELL2000 = "russell2000"  # <-- Add new index here
    CUSTOM = "custom"
```

#### Step 3: Create Scraping Function
Edit `schwab_portfolio/data/financial_data_fetcher.py`:

```python
def get_russell2000_tickers() -> List[str]:
    """Get Russell 2000 ticker list from Wikipedia"""
    try:
        import requests
        from io import StringIO

        url = 'https://en.wikipedia.org/wiki/Russell_2000_Index'  # Wikipedia URL
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        # Find the right table (usually index 0 or 1)
        russell_table = tables[0]  # Adjust table index as needed
        tickers = russell_table['Symbol'].tolist()  # Adjust column name
        logger.info(f"Fetched {len(tickers)} Russell 2000 tickers")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch Russell 2000 tickers: {e}")
        return []
```

#### Step 4: Connect the Index
Still in `watchlist_config.py`, add the case:

```python
elif self.index == WatchlistIndex.RUSSELL2000:
    tickers = get_russell2000_tickers()
    logger.info(f"Fetched {len(tickers)} tickers from Russell 2000")
```

#### Step 5: Import the Function
Add to imports in `watchlist_config.py`:

```python
from data.financial_data_fetcher import (
    get_sp500_tickers,
    get_sp400_tickers,
    get_sp600_tickers,
    get_nasdaq100_tickers,
    get_russell2000_tickers  # <-- Add this
)
```

#### Step 6: Test It
```bash
python main_quality_analysis.py --index russell2000 --limit 10
```

**Note:** This requires Python programming knowledge. All the popular indexes listed above are already available to use! Start with smaller indexes like `dax` or `cac40` for testing.

---

---

## 🔍 Understanding the Output

### Quality Score Breakdown
- **85-100**: Elite quality (rare, exceptional companies)
- **70-84**: Strong quality (good companies to hold)
- **50-69**: Moderate quality (okay but could be better)
- **0-49**: Weak quality (consider selling)

### Red Flags Detected

The system watches for quality and risk red flags across all dimensions:

**Earnings Quality:**
- High Accruals (>10% of assets)
- Low Cash Conversion (<0.8x)
- Poor Piotroski F-Score (≤3)

**Growth Quality:**
- Excessive Asset Growth (>40%)
- Declining Revenue (negative CAGR)
- Margin Compression (>5% decline)

**Safety:**
- Bankruptcy Risk (Z-Score <1.0)
- High Leverage (Debt/EBITDA >4.0x)
- Weak Interest Coverage (<3.0x)
- High Beta (>2.0)

### Market Cap Tiers

| Tier | Market Cap | Multiplier | Use Case |
|------|------------|------------|----------|
| Mega Cap | > $200B | 1.25x | Stable, extended lookback |
| Large Cap | $10B - $200B | 1.00x | Core holdings |
| Mid Cap | $2B - $10B | 0.75x | Growth opportunities |
| Small Cap | $300M - $2B | 0.50x | Higher risk/reward |
| Micro Cap | < $300M | 0.35x | Limited data available |

---

## 🛠️ Troubleshooting

### Common Issues

**"No module named 'yfinance'"**
```bash
pip install yfinance
```

**"Failed to fetch tickers"**
- Check your internet connection
- Wikipedia may be temporarily blocking requests
- Try again in a few minutes

**"No holdings found"**
- Make sure `portfolio_state.json` exists and has holdings
- Check the JSON format is correct

**Slow performance**
- Use `--limit` to analyze fewer stocks
- Smaller indexes run faster (nasdaq100 is fastest)

### Getting Help

**Check the research docs:**
- `schwab_portfolio/docs/research/quality_investing_thresholds_research.md`
- `schwab_portfolio/docs/research/STEPS_Research_Methodology_November_1_2025.md`

**Run with more details:**
```bash
python main_quality_analysis.py --help
```

---

## 📚 Academic Foundation

This system is built on proven research:

**Quality Framework:**
- **Novy-Marx (2013)**: Gross profitability predicts returns better than traditional metrics
- **Piotroski (2000)**: F-Score fundamentals-based investing
- **Sloan (1996)**: Accrual anomaly - low accruals predict higher returns
- **Cooper, Gulen, Schill (2008)**: Asset growth anomaly - low asset growth predicts higher returns
- **Fama-French (2015)**: Quality factor definition
- **Altman (1968)**: Z-Score bankruptcy prediction

**Multi-Factor Approach:**
The NEW_5FACTOR framework combines multiple quality dimensions to identify companies with:
- Strong profitability and returns on capital
- High quality, sustainable earnings
- Conservative, profitable growth
- Low financial risk
- Persistent ROE performance over time

**No guarantees** - this is educational/research software. Always do your own research!

---

## 🎉 Happy Investing!

This tool helps you find high-quality companies using data and research. Use it to:
- Screen for new investment ideas
- Monitor your portfolio quality
- Learn about fundamental analysis

Questions? The code is open-source and well-documented. Happy stock analysis! 🚀📈