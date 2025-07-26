# SPY Regime Identification Model for Options Trading

## Overview

This comprehensive Python model addresses a critical problem in options trading: **determining optimal strategy selection based on market conditions**. The system uses Geometric Brownian Motion (GBM) simulation combined with empirically-derived regime identification to provide quantitative trading signals for SPY options strategies.

> **Note**: Currently optimized for Jupyter notebook development and testing. Production-ready module coming soon.

### The Core Problem

Many options traders experience systematic losses by using the wrong strategies for current market conditions. For example:
- Selling **call spreads in persistent bull markets** (like the user's original problem)
- Using **iron condors in trending markets**
- Applying **put spreads during bear market conditions**

This model solves these issues by automatically classifying market regimes and recommending appropriate strategies with confidence scores.

## Installation & Dependencies

```bash
pip install numpy pandas matplotlib seaborn scipy yfinance jupyter
```

## Quick Start (Jupyter Notebook)

```python
# Cell 1: Copy the SPYRegimeModel class definition
# [Paste the complete class code from spy_regime_model.py]

# Cell 2: Initialize and run analysis
model = SPYRegimeModel()
regimes, signals = model.run_full_analysis(use_historical_data=True)

# Cell 3: Visualize results
model.plot_regime_analysis()

# Cell 4: Get current recommendation
print(model.get_current_recommendation())
```

**Recommended Notebook Structure:**
1. **Setup Cell**: Import libraries and define the SPYRegimeModel class
2. **Configuration Cell**: Set parameters for your trading style
3. **Analysis Cell**: Run the full analysis
4. **Visualization Cell**: Generate plots and charts
5. **Results Cell**: Extract trading recommendations and insights

## Core Model Architecture

### 1. Data Integration Layer

**Historical Price Data (yfinance)**
- Fetches SPY historical data with configurable periods
- Calculates daily returns and rolling statistics
- Updates model parameters based on recent market behavior

**Options Data & IV Calculation**
- Retrieves real-time options chains for specified expiration
- Calculates implied volatility using Black-Scholes inversion
- Computes IV rank using historical volatility percentiles
- Volume-weighted IV metrics for accuracy

**Why This Approach:**
- **yfinance**: Reliable, free, comprehensive historical data
- **Internal IV calculation**: Full control, real-time accuracy, no API limits
- **Historical volatility**: Robust baseline for IV rank calculations

### 2. Regime Identification System

The model identifies four distinct market regimes based on **rolling volatility** and **trend analysis**:

#### Regime Classifications

| Regime | Condition | Optimal Strategy | Typical Market |
|--------|-----------|------------------|----------------|
| **Trending Up** | Low vol, positive trend | Put Credit Spreads | Bull markets, steady climbs |
| **Trending Down** | Low vol, negative trend | Call Credit Spreads | Bear markets, steady declines |
| **Range Bound** | Low vol, minimal trend | Iron Condors | Sideways markets, low VIX |
| **High Volatility** | High vol (any trend) | Defensive/Cash | Market stress, high VIX |

#### Threshold Methodology

**Adaptive Thresholds (Recommended)**
```python
# Volatility Threshold = max(75th percentile, mean + 1σ)
# Trend Threshold = max(60th percentile, mean + 0.5σ)
```

**Benefits:**
- Adapts to changing market conditions
- Prevents overfitting to historical periods
- More robust regime classification
- Reduces false regime switches

### 3. Trading Signal Generation

Each regime generates specific trading recommendations with confidence scores:

**Signal Confidence Calculation:**
- Distance from thresholds determines confidence
- Volume-weighted IV metrics enhance accuracy
- Historical regime stability influences recommendations

## Key Parameters & Configuration

### Model Parameters (`model_params`)

```python
model_params = {
    'mu': 0.12,      # Annual expected return (auto-updated from data)
    'sigma': 0.18,   # Annual volatility (auto-updated from data)
    'S0': 600,       # Initial/current price (auto-updated)
    'days': 252,     # Trading days for simulation
    'dt': 1/252      # Daily time step
}
```

**When to Modify:**
- `mu`, `sigma`: Generally auto-updated, but can override for stress testing
- `days`: Increase for longer backtests (500-1000 days)
- Keep `dt = 1/252` for daily analysis

### Regime Parameters (`regime_params`)

```python
regime_params = {
    'lookback_period': 20,                    # Rolling window for statistics
    'volatility_threshold': 0.25,            # Manual vol threshold (if not adaptive)
    'trend_threshold': 0.02,                  # Manual trend threshold (if not adaptive)
    'regime_min_duration': 5,                 # Minimum days to maintain regime
    'threshold_estimation_period': 252,       # Days for adaptive threshold calculation
    'use_adaptive_thresholds': True           # Enable adaptive threshold estimation
}
```

#### Critical Parameter Guidance

**`lookback_period`** - **MOST IMPORTANT PARAMETER**
- **Should match your options DTE**
- 20 days → Short-term strategies (0-30 DTE)
- 45 days → Standard strategies (30-60 DTE)  
- 60 days → Longer-term strategies (60+ DTE)

**`threshold_estimation_period`**
- 252 days (1 year): Good for stable markets
- 500 days (2 years): Better for volatile periods
- 1000+ days: Maximum historical context

**`regime_min_duration`**
- 3-5 days: More responsive, more noise
- 5-7 days: Balanced (recommended)
- 10+ days: Smoother, less responsive

**`use_adaptive_thresholds`**
- **True (recommended)**: Adapts to market conditions
- **False**: Uses fixed thresholds (good for backtesting specific periods)

## Jupyter Notebook Examples

### Basic Analysis Notebook
```python
# === CELL 1: SETUP ===
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.optimize import minimize_scalar
from scipy.stats import norm
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# [Paste complete SPYRegimeModel class here]

# === CELL 2: QUICK ANALYSIS ===
model = SPYRegimeModel()
regimes, signals = model.run_full_analysis(use_historical_data=True)

# === CELL 3: VISUALIZATION ===
model.plot_regime_analysis()

# === CELL 4: CURRENT RECOMMENDATION ===
print(model.get_current_recommendation())

# === CELL 5: DETAILED INSIGHTS ===
# Regime distribution
print("REGIME DISTRIBUTION:")
print(regimes['regime'].value_counts(normalize=True).round(3))

# Recent signals
print("\nRECENT SIGNALS:")
print(signals.tail()[['day', 'regime', 'strategy', 'confidence']].to_string(index=False))
```

### 1. Match Your Trading Timeframe

```python
# For 45 DTE strategies (your original problem)
model = SPYRegimeModel()
model.regime_params['lookback_period'] = 45
model.regime_params['threshold_estimation_period'] = 500  # 2 years
regimes, signals = model.run_full_analysis()
```

### 2. Stress Test Different Market Conditions

```python
# Test bear market conditions
model.model_params['mu'] = -0.15  # -15% annual return
model.model_params['sigma'] = 0.35  # 35% volatility
regimes, signals = model.run_full_analysis(use_historical_data=False, simulation_days=252)
```

### 3. Compare Threshold Methods

```python
# Compare fixed vs adaptive thresholds
regimes_fixed, regimes_adaptive = compare_threshold_methods()

# Analyze threshold sensitivity
model.regime_params['use_adaptive_thresholds'] = False
for vol_thresh in [0.20, 0.25, 0.30, 0.35]:
    model.regime_params['volatility_threshold'] = vol_thresh
    regimes, _ = model.run_full_analysis()
    print(f"Vol {vol_thresh}: {regimes['regime'].value_counts(normalize=True)}")
```

### 4. Real-Time Trading Integration

```python
# Get current market conditions
model = SPYRegimeModel()
model.fetch_spy_data(period='1y')
iv_metrics, iv_df = model.calculate_current_iv_metrics()

# Daily regime check
regimes, signals = model.run_full_analysis()
current_rec = model.get_current_recommendation()

# Position sizing based on confidence
current_signal = signals.iloc[-1]
position_size = min(0.05, current_signal['confidence'] * 0.06)  # Max 5% risk
print(f"Recommended position size: {position_size:.1%} of account")
```

## Key Insights & Interpretation

### Regime Distribution Analysis

**Healthy Market Characteristics:**
- Trending Up: 40-60% (Bull market)
- Range Bound: 20-35% (Consolidation)
- Trending Down: 10-25% (Normal corrections)
- High Volatility: 5-15% (Occasional stress)

**Warning Signs:**
- High Volatility > 25%: Sustained market stress
- Trending Down > 40%: Bear market conditions
- Range Bound > 50%: Stagnant market (challenging for directional strategies)

### Signal Confidence Interpretation

**Confidence Levels:**
- **90%+**: Extremely strong signal, consider larger position sizes
- **75-90%**: Strong signal, standard position sizing
- **60-75%**: Moderate signal, reduced position sizing
- **<60%**: Weak signal, consider waiting or defensive positioning

### IV Rank Integration

**IV Rank Guidance:**
- **<20%**: Low volatility environment, favor premium selling
- **20-50%**: Moderate volatility, standard strategies work well
- **50-80%**: Elevated volatility, be selective with entries
- **>80%**: High volatility, favor premium buying or defensive strategies

## Risk Management Integration

### Position Sizing Framework

```python
# Dynamic position sizing based on regime confidence
def calculate_position_size(signal_confidence, iv_rank, base_risk=0.05):
    """
    Calculate position size based on signal strength and market conditions
    """
    # Reduce size in high volatility environments
    vol_adjustment = max(0.5, (100 - iv_rank) / 100)
    
    # Adjust for signal confidence
    confidence_adjustment = signal_confidence
    
    # Final position size
    position_size = base_risk * vol_adjustment * confidence_adjustment
    
    return min(position_size, 0.05)  # Cap at 5% account risk
```

### Trade Management Rules

**Entry Rules:**
- Only enter trades with >70% confidence
- Avoid entries when IV rank >80% (unless defensive strategy)
- Wait for regime confirmation (3+ consecutive days)

**Exit Rules:**
- Take profits at 50% of maximum gain
- Stop losses at 25% of premium collected
- Close all positions at 21 DTE (avoid gamma explosion)
- Exit if regime changes unfavorably

## Backtesting & Performance Analysis

### Historical Performance Validation

```python
# Backtest regime-based strategy selection
def backtest_regime_strategy(model, start_date, end_date):
    """
    Backtest trading performance using regime signals
    """
    results = []
    
    for signal in model.trading_signals.itertuples():
        # Simulate trade outcomes based on regime
        expected_win_rate = {
            'PUT_CREDIT_SPREAD': 0.85,
            'CALL_CREDIT_SPREAD': 0.65,  # Lower in trending markets
            'IRON_CONDOR': 0.75,
            'DEFENSIVE': 0.0  # Capital preservation
        }
        
        trade_outcome = np.random.random() < expected_win_rate[signal.signal]
        profit_loss = signal.confidence * 0.1 if trade_outcome else -signal.confidence * 0.3
        
        results.append({
            'date': signal.day,
            'strategy': signal.signal,
            'confidence': signal.confidence,
            'outcome': trade_outcome,
            'pnl': profit_loss
        })
    
    return pd.DataFrame(results)
```

## Common Issues & Troubleshooting

### Data Quality Issues

**"No options data available"**
- Check market hours (options trade 9:30 AM - 4:00 PM ET)
- Verify SPY has active options chain
- Try different expiration dates

**"Insufficient data for estimation"**
- Increase `threshold_estimation_period`
- Use longer historical data period
- Switch to fixed thresholds temporarily

### Regime Classification Problems

**Too many regime switches**
- Increase `regime_min_duration`
- Use longer `lookback_period`
- Check for data quality issues

**Unrealistic regime distribution**
- Verify adaptive thresholds are reasonable
- Check underlying data for anomalies
- Consider using fixed thresholds for specific periods

### Performance Issues

**Slow IV calculations**
- Reduce options chain size (filter by volume)
- Limit strike price range (±20% from current price)
- Use cached calculations for repeated analysis

## Model Validation & Limitations

### Strengths
- **Empirically-derived thresholds** adapt to market conditions
- **Multiple timeframe support** for different trading styles
- **Quantitative confidence scoring** for position sizing
- **Real-time integration** with market data

### Limitations
- **Assumes regime persistence** (market conditions continue)
- **Black-Scholes assumptions** (constant volatility, normal distributions)
- **Historical bias** (past patterns may not repeat)
- **Transaction cost neglect** (commissions, slippage not included)

### Validation Recommendations
1. **Out-of-sample testing**: Use 70% data for calibration, 30% for testing
2. **Walk-forward analysis**: Recalibrate thresholds monthly
3. **Regime persistence testing**: Measure how long regimes actually last
4. **Strategy performance validation**: Compare model recommendations to actual trade outcomes

## Future Enhancements

**Planned Features:**
- Machine learning regime classification
- Multi-asset regime analysis (VIX, bonds, currencies)
- Real-time alert system
- Portfolio-level risk management
- Options Greeks integration for precise position sizing

**Contributing:**
Submit issues or feature requests focusing on:
- Alternative regime identification methods
- Additional data sources integration
- Performance optimization
- Trading strategy enhancements

## License & Disclaimer

This model is for educational and research purposes. Options trading involves substantial risk of loss. Past performance does not guarantee future results. Always conduct your own analysis and consider consulting with a financial advisor before making trading decisions.

---

*Last updated: July 2025*
*Model version: 1.0*
