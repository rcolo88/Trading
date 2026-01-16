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

This system evaluates stocks using **5 key quality metrics** based on academic research:

1. **Gross Profitability** - How efficiently the company generates profits
2. **Return on Equity (ROE)** - How well the company uses shareholder money
3. **Operating Profitability** - Profit margins from core operations
4. **Free Cash Flow Yield** - Cash generation relative to company value
5. **Return on Invested Capital (ROIC)** - Overall capital efficiency

It then gives each stock a **quality score** (0-100) and **tier** (Elite/Strong/Moderate/Weak).

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
| `--index sp500` | Find quality stocks from large universe | Comparative analysis + recommendations | 12-17 min |
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
| **`russell2000`** | Russell 2000 (US Small Cap) | ~2000 stocks | US small caps | 80+ min | `--index russell2000` |
| **`russell1000`** | Russell 1000 (US Large/Mid) | ~1000 stocks | US large/mid caps | 40+ min | `--index russell1000` |
| **`russell3000`** | Russell 3000 (US Total) | ~3000 stocks | US total market | 120+ min | `--index russell3000` |

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

## 💼 Portfolio Analysis

### Setting Up Your Portfolio

Edit `schwab_portfolio/portfolio_state.json`:

```json
{
  "holdings": {
    "AAPL": {
      "shares": 10,
      "entry_price": 175.00,
      "allocation": 1750.00
    },
    "MSFT": {
      "shares": 5,
      "entry_price": 330.00,
      "allocation": 1650.00
    }
  },
  "cash": 250.00
}
```

### Analyzing Your Holdings

The system automatically compares your holdings against the watchlist and provides:

- **SELL candidates** - Stocks in your portfolio with quality scores below 70
- **BUY alternatives** - High-quality stocks not in your portfolio
- **Quality rankings** - How your holdings stack up

---

## 🔍 Understanding the Output

### Quality Score Breakdown
- **85-100**: Elite quality (rare, exceptional companies)
- **70-84**: Strong quality (good companies to hold)
- **50-69**: Moderate quality (okay but could be better)
- **0-49**: Weak quality (consider selling)

### Red Flags Detected
The system watches for:
- High debt levels
- Declining profits
- Poor cash flow
- Accounting irregularities

### Market Cap Tiers
- **Large Cap**: $50B+ (S&P 500 companies)
- **Mid Cap**: $2B-$50B (growth potential)
- **Small Cap**: $500M-$2B (higher risk/reward)
- **Micro Cap**: <$500M (not analyzed)

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
- **Novy-Marx (2013)**: Gross profitability predicts returns better than traditional metrics
- **Piotroski (2000)**: F-Score fundamentals-based investing
- **Fama-French (1993)**: Quality and size factors matter
- **Quality Investing**: Multi-year studies show quality beats the market

**No guarantees** - this is educational/research software. Always do your own research!

---

## 🎉 Happy Investing!

This tool helps you find high-quality companies using data and research. Use it to:
- Screen for new investment ideas
- Monitor your portfolio quality
- Learn about fundamental analysis

Questions? The code is open-source and well-documented. Happy stock analysis! 🚀📈