"""
Currency Converter - Fetches live exchange rates and converts currencies

Uses exchangerate-api.com (free tier: 1000 requests/day)
"""

import requests
import time
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class CurrencyRate:
    """Represents a currency exchange rate"""
    from_currency: str
    to_currency: str
    rate: float
    timestamp: datetime


class CurrencyConverter:
    """
    Handles currency conversion using live exchange rates.
    
    Uses exchangerate-api.com free tier (1000 requests/day).
    Falls back to cached/backup rates if API is unavailable.
    """
    
    CACHE_DURATION_HOURS = 24
    
    FX_API_BASE = "https://api.exchangerate-api.com/v4/latest"
    
    BACKUP_RATES = {
        'USD': 1.0,
        'TWD': 28.0,
        'JPY': 150.0,
        'EUR': 0.92,
        'GBP': 0.79,
        'KRW': 1300.0,
        'HKD': 7.78,
        'CNY': 7.20,
        'CHF': 0.88,
        'DKK': 6.85,
        'AUD': 1.53,
        'CAD': 1.36,
        'INR': 83.0,
        'SGD': 1.34,
        'NZD': 1.65,
        'SEK': 10.4,
        'NOK': 10.7,
        'MXN': 17.1,
        'BRL': 5.0,
    }
    
    def __init__(self, cache_file: str = "currency_rates_cache.json"):
        """
        Initialize currency converter.
        
        Args:
            cache_file: Path to cache file for exchange rates
        """
        self._rate_cache: Dict[str, CurrencyRate] = {}
        self._cache_file = cache_file
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cached exchange rates from file"""
        try:
            import json
            import os
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r') as f:
                    data = json.load(f)
                    for currency, rate_data in data.items():
                        self._rate_cache[currency] = CurrencyRate(
                            from_currency=rate_data['from'],
                            to_currency='USD',
                            rate=rate_data['rate'],
                            timestamp=datetime.fromisoformat(rate_data['timestamp'])
                        )
                logger.info(f"Loaded {len(self._rate_cache)} cached currency rates")
        except Exception as e:
            logger.warning(f"Failed to load currency cache: {e}")
    
    def _save_cache(self) -> None:
        """Save exchange rates to cache file"""
        try:
            import json
            data = {}
            for currency, rate in self._rate_cache.items():
                data[currency] = {
                    'from': rate.from_currency,
                    'to': rate.to_currency,
                    'rate': rate.rate,
                    'timestamp': rate.timestamp.isoformat()
                }
            with open(self._cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save currency cache: {e}")
    
    def get_rate(self, from_currency: str, to_currency: str = 'USD') -> float:
        """
        Get exchange rate from one currency to another.
        
        Args:
            from_currency: Source currency code (e.g., 'TWD', 'JPY')
            to_currency: Target currency code (default: 'USD')
        
        Returns:
            Exchange rate as float
            
        Raises:
            CurrencyConversionError: If rate cannot be fetched
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        if from_currency == to_currency:
            return 1.0
        
        cache_key = from_currency
        
        if cache_key in self._rate_cache:
            cached = self._rate_cache[cache_key]
            age = datetime.now() - cached.timestamp
            if age < timedelta(hours=self.CACHE_DURATION_HOURS):
                return cached.rate
        
        try:
            rate = self._fetch_rate_from_api(from_currency)
            self._rate_cache[cache_key] = CurrencyRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                timestamp=datetime.now()
            )
            self._save_cache()
            return rate
        except Exception as e:
            logger.error(f"Failed to fetch rate for {from_currency}: {e}")
            return self._get_backup_rate(from_currency)
    
    def _fetch_rate_from_api(self, from_currency: str) -> float:
        """
        Fetch exchange rate from API.
        
        Args:
            from_currency: Currency code to fetch against USD
            
        Returns:
            Exchange rate (from_currency to USD)
        """
        url = f"{self.FX_API_BASE}/{from_currency}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'rates' not in data:
            raise CurrencyConversionError(f"Invalid API response for {from_currency}")
        
        to_currency = 'USD'
        if to_currency not in data['rates']:
            raise CurrencyConversionError(f"Currency {to_currency} not in API response")
        
        rate = data['rates'][to_currency]
        
        if not isinstance(rate, (int, float)) or rate <= 0:
            raise CurrencyConversionError(f"Invalid rate for {from_currency}: {rate}")
        
        logger.info(f"Fetched {from_currency} → USD rate: {rate}")
        return rate
    
    def _get_backup_rate(self, currency: str) -> float:
        """
        Get backup exchange rate from static table.
        
        Args:
            currency: Currency code
            
        Returns:
            Backup exchange rate or raises error
        """
        currency = currency.upper()
        
        if currency in self.BACKUP_RATES:
            rate = self.BACKUP_RATES[currency]
            logger.warning(f"Using backup rate for {currency}: {rate}")
            return rate
        
        raise CurrencyConversionError(f"No exchange rate available for {currency}")
    
    def convert(self, value: float, from_currency: str, to_currency: str = 'USD') -> float:
        """
        Convert a value from one currency to another.
        
        Args:
            value: Numeric value to convert
            from_currency: Source currency code
            to_currency: Target currency code
            
        Returns:
            Converted value
        """
        if value is None or value == 0:
            return value
        
        if from_currency.upper() == to_currency.upper():
            return value
        
        try:
            if to_currency.upper() == 'USD':
                rate = self.get_rate(from_currency)
                return value * rate
            elif from_currency.upper() == 'USD':
                rate = self.get_rate(to_currency)
                return value / rate
            else:
                to_usd = self.get_rate(from_currency)
                from_usd = self.get_rate(to_currency)
                usd_value = value * to_usd
                return usd_value / from_usd
        except Exception as e:
            logger.error(f"Currency conversion failed: {e}")
            raise CurrencyConversionError(f"Failed to convert {value} {from_currency} to {to_currency}")
    
    def convert_financial_data(self, data: Dict, from_currency: str) -> Dict:
        """
        Convert all numeric values in financial data dict.
        
        Args:
            data: Dictionary with financial values
            from_currency: Source currency code
            
        Returns:
            Dictionary with converted values
        """
        if from_currency.upper() == 'USD':
            return data
        
        try:
            converted = {}
            for key, value in data.items():
                if isinstance(value, (int, float)) and value != 0:
                    converted[key] = self.convert(value, from_currency)
                else:
                    converted[key] = value
            return converted
        except Exception as e:
            logger.error(f"Failed to convert financial data: {e}")
            raise CurrencyConversionError(f"Failed to convert financial data from {from_currency}")
    
    def clear_cache(self) -> None:
        """Clear the rate cache"""
        self._rate_cache.clear()
        import os
        if os.path.exists(self._cache_file):
            os.remove(self._cache_file)
        logger.info("Currency rate cache cleared")
    
    def get_supported_currencies(self) -> list:
        """Get list of supported currency codes"""
        return list(self.BACKUP_RATES.keys())


class CurrencyConversionError(Exception):
    """Raised when currency conversion fails"""
    pass


if __name__ == "__main__":
    converter = CurrencyConverter()
    
    print("Currency Converter Test")
    print("=" * 50)
    
    currencies = ['TWD', 'JPY', 'EUR', 'GBP', 'CNY']
    
    for currency in currencies:
        try:
            rate = converter.get_rate(currency)
            print(f"{currency} → USD: {rate}")
        except Exception as e:
            print(f"{currency}: Error - {e}")
    
    print("\nConversion test:")
    print(f"  1,000,000 TWD = ${converter.convert(1000000, 'TWD'):,.2f} USD")
    print(f"  100,000,000 JPY = ${converter.convert(100000000, 'JPY'):,.2f} USD")
