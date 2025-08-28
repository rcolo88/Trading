#!/usr/bin/env python3
"""
Test yfinance API with the ETF tickers that are failing
"""

import yfinance as yf
import sys

def test_yfinance_etfs():
    print('Testing yfinance with ETF tickers...')
    tickers = ['XLV', 'VEA', 'TLT', 'SPY']  # Added SPY as control

    # Method 1: Using Ticker info
    print("\n=== Method 1: Using .info ===")
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            if current_price:
                print(f'{ticker}: ${current_price:.2f}')
            else:
                print(f'{ticker}: No price found in info')
                # Print available keys for debugging
                price_keys = [k for k in info.keys() if 'price' in k.lower() or 'close' in k.lower()]
                print(f'  Available price keys: {price_keys[:5]}')
        except Exception as e:
            print(f'{ticker}: Error - {str(e)[:100]}')

    # Method 2: Using download
    print("\n=== Method 2: Using download ===")
    try:
        data = yf.download(tickers, period='1d', progress=False)
        print('Download successful!')
        if not data.empty:
            if 'Close' in data.columns:
                latest_prices = data['Close'].iloc[-1]
                for ticker in tickers:
                    if ticker in latest_prices.index:
                        print(f'{ticker}: ${latest_prices[ticker]:.2f}')
                    else:
                        print(f'{ticker}: Not found in download results')
            else:
                print(f'Columns available: {data.columns.tolist()}')
        else:
            print('No data returned from yfinance download')
    except Exception as e:
        print(f'Download error: {e}')

    # Method 3: Using history
    print("\n=== Method 3: Using history ===")
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='1d')
            if not hist.empty and 'Close' in hist.columns:
                latest_price = hist['Close'].iloc[-1]
                print(f'{ticker}: ${latest_price:.2f}')
            else:
                print(f'{ticker}: No history data')
        except Exception as e:
            print(f'{ticker}: History error - {str(e)[:50]}')

if __name__ == '__main__':
    test_yfinance_etfs()