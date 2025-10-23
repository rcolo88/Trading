"""
Black-Scholes pricing and Greeks calculations.

This module provides functions for calculating option prices and Greeks
using the Black-Scholes-Merton model. Used for generating synthetic
options data when historical data is unavailable.
"""

from typing import Tuple
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq


def black_scholes_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0
) -> float:
    """
    Calculate option price using Black-Scholes-Merton model.

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annual)
        option_type: 'call' or 'put'
        q: Dividend yield (annual), default 0.0

    Returns:
        Option price
    """
    if T <= 0:
        # At expiration
        if option_type.lower() in ['call', 'c']:
            return max(0, S - K)
        else:
            return max(0, K - S)

    if sigma <= 0:
        # No volatility
        if option_type.lower() in ['call', 'c']:
            return max(0, S * np.exp(-q * T) - K * np.exp(-r * T))
        else:
            return max(0, K * np.exp(-r * T) - S * np.exp(-q * T))

    # Calculate d1 and d2
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type.lower() in ['call', 'c']:
        price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:  # put
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)

    return max(0, price)  # Price can't be negative


def delta(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0
) -> float:
    """
    Calculate option delta (sensitivity to underlying price).

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility
        option_type: 'call' or 'put'
        q: Dividend yield

    Returns:
        Delta value
    """
    if T <= 0:
        if option_type.lower() in ['call', 'c']:
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0

    if sigma <= 0:
        if option_type.lower() in ['call', 'c']:
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0

    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

    if option_type.lower() in ['call', 'c']:
        return np.exp(-q * T) * norm.cdf(d1)
    else:  # put
        return -np.exp(-q * T) * norm.cdf(-d1)


def gamma(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0
) -> float:
    """
    Calculate option gamma (rate of change of delta).

    Gamma is the same for calls and puts.

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility
        q: Dividend yield

    Returns:
        Gamma value
    """
    if T <= 0 or sigma <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

    return (np.exp(-q * T) * norm.pdf(d1)) / (S * sigma * np.sqrt(T))


def theta(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0
) -> float:
    """
    Calculate option theta (time decay).

    Note: Returns theta per year. Divide by 365 for daily theta.

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility
        option_type: 'call' or 'put'
        q: Dividend yield

    Returns:
        Theta value (per year)
    """
    if T <= 0:
        return 0.0

    if sigma <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    term1 = -(S * norm.pdf(d1) * sigma * np.exp(-q * T)) / (2 * np.sqrt(T))

    if option_type.lower() in ['call', 'c']:
        term2 = -r * K * np.exp(-r * T) * norm.cdf(d2)
        term3 = q * S * np.exp(-q * T) * norm.cdf(d1)
        return term1 + term2 + term3
    else:  # put
        term2 = r * K * np.exp(-r * T) * norm.cdf(-d2)
        term3 = -q * S * np.exp(-q * T) * norm.cdf(-d1)
        return term1 + term2 + term3


def vega(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0
) -> float:
    """
    Calculate option vega (sensitivity to volatility).

    Vega is the same for calls and puts.
    Note: Returns vega per 1% change in volatility.

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility
        q: Dividend yield

    Returns:
        Vega value (per 1% volatility change)
    """
    if T <= 0 or sigma <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

    return S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T) / 100


def implied_volatility(
    option_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str,
    q: float = 0.0
) -> float:
    """
    Calculate implied volatility from option price.

    Uses Brent's method to solve for volatility.

    Args:
        option_price: Market price of option
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        option_type: 'call' or 'put'
        q: Dividend yield

    Returns:
        Implied volatility (annual)
    """
    if T <= 0:
        return 0.0

    # Define objective function
    def objective(sigma):
        return black_scholes_price(S, K, T, r, sigma, option_type, q) - option_price

    try:
        # Use Brent's method to find root
        iv = brentq(objective, 0.001, 5.0, maxiter=100)
        return iv
    except (ValueError, RuntimeError):
        # If optimization fails, return 0
        return 0.0


def find_strike_by_delta(
    target_delta: float,
    S: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0,
    tolerance: float = 0.01
) -> float:
    """
    Find strike price that produces target delta.

    Uses binary search to find the strike.

    Args:
        target_delta: Desired delta value (e.g., 0.30)
        S: Current stock price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility
        option_type: 'call' or 'put'
        q: Dividend yield
        tolerance: Acceptable delta difference

    Returns:
        Strike price producing target delta
    """
    # Convert target delta to absolute value for comparison
    target_delta_abs = abs(target_delta)

    # Set search range based on option type
    if option_type.lower() in ['call', 'c']:
        # For calls, search below current price for higher deltas
        K_low = S * 0.5
        K_high = S * 1.5
    else:
        # For puts, search above current price for higher deltas (absolute)
        K_low = S * 0.5
        K_high = S * 1.5

    # Binary search
    max_iterations = 100
    for _ in range(max_iterations):
        K_mid = (K_low + K_high) / 2
        current_delta = delta(S, K_mid, T, r, sigma, option_type, q)
        current_delta_abs = abs(current_delta)

        if abs(current_delta_abs - target_delta_abs) < tolerance:
            return K_mid

        # Adjust search range
        if option_type.lower() in ['call', 'c']:
            if current_delta_abs > target_delta_abs:
                K_low = K_mid  # Move strike higher (delta decreases)
            else:
                K_high = K_mid
        else:  # put
            if current_delta_abs > target_delta_abs:
                K_high = K_mid  # Move strike lower (delta magnitude decreases)
            else:
                K_low = K_mid

    # Return best approximation
    return (K_low + K_high) / 2


def calculate_all_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0
) -> dict:
    """
    Calculate option price and all Greeks.

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility
        option_type: 'call' or 'put'
        q: Dividend yield

    Returns:
        Dictionary with price and Greeks
    """
    return {
        'price': black_scholes_price(S, K, T, r, sigma, option_type, q),
        'delta': delta(S, K, T, r, sigma, option_type, q),
        'gamma': gamma(S, K, T, r, sigma, q),
        'theta': theta(S, K, T, r, sigma, option_type, q),
        'vega': vega(S, K, T, r, sigma, q)
    }
