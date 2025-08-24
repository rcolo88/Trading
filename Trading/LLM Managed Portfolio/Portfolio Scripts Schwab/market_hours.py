"""
Market Hours Validation Module
Handles checking if the US stock market is currently open
"""

import pandas_market_calendars as mcal
import pandas as pd
from datetime import datetime
import pytz


def is_market_open():
    """
    Check if US stock market is currently open (NYSE/NASDAQ)
    Returns True if market is open, False otherwise
    """
    try:
        # Get current time in Eastern Time
        et_tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(et_tz)
        
        # Create NYSE calendar
        nyse = mcal.get_calendar('NYSE')
        
        # Get today's schedule
        today = now_et.date()
        schedule = nyse.schedule(start_date=today, end_date=today)
        
        # If no schedule for today, market is closed
        if schedule.empty:
            return False
        
        # Check if current time is within market hours
        is_open = nyse.open_at_time(schedule, pd.Timestamp(now_et), only_rth=True)
        return is_open
        
    except Exception as e:
        print(f"Error checking market status: {e}")
        return False


def enforce_market_hours():
    """
    Exit script if market is not open with informative message
    """
    if not is_market_open():
        et_tz = pytz.timezone('US/Eastern')
        current_time = datetime.now(et_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        
        print("🚫 MARKET CLOSED")
        print(f"Current time: {current_time}")
        print("The script can only run during US market hours:")
        print("• Monday-Friday, 9:30 AM - 4:00 PM Eastern Time")
        print("• On days when NYSE/NASDAQ are open (no holidays)")
        print("\nPlease run this script during market hours.")
        exit(1)
    else:
        et_tz = pytz.timezone('US/Eastern')
        current_time = datetime.now(et_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        print(f"✅ Market is open - {current_time}")