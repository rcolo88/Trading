#!/bin/bash
###############################################################################
# Quick Test Script - Tests analysis system (NO API KEYS NEEDED!)
###############################################################################

echo ""
echo "================================================================"
echo "  QUICK TEST - Portfolio Analysis (No API Keys Required)"
echo "  Uses Yahoo Finance for news and financial data"
echo "================================================================"
echo ""

# Check current portfolio
echo "[1/2] Current Portfolio:"
cat ../portfolio_state.json | python -c "import sys, json; data=json.load(sys.stdin); print(f\"  Cash: \${data['cash']:.2f}\"); print(f\"  Holdings: {list(data['holdings'].keys())}\"); [print(f\"    {ticker}: {info['shares']} shares\") for ticker, info in data['holdings'].items()]"
echo ""

# Run quality analysis on current portfolio
echo "[2/2] Running quality analysis..."
echo "Command: python quality_analysis_script.py --watchlist-limit 10"
echo ""

/opt/anaconda3/bin/python quality_analysis_script.py --watchlist-limit 10

echo ""
echo "================================================================"
echo "  Test Complete! Check outputs:"
echo "================================================================"
echo "  cat outputs/quality_analysis_*_summary.txt"
echo "================================================================"
