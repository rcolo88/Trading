"""
Per-date IV surface fitter.

For each day with DoltHub real data (~25 contracts across ~4 expirations), fit a
bivariate polynomial IV surface model.  Use the fitted surface to generate synthetic
quotes for any (strike, expiration) on that day — so the synthetic chain inherits
that day's actual skew + term structure instead of a global parametric guess.
"""
from typing import Optional, Dict
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Per-date surface fitting
# ---------------------------------------------------------------------------

def fit_day_surface(day_chain: pd.DataFrame,
                    min_points: int = 6) -> Optional[Dict]:
    """Fit a bivariate polynomial IV surface to one day's real quotes.

    Model
    -----
        IV = p00 + p10·m + p01·t + p20·m² + p11·m·t + p02·t²

    where
        m = log(strike / spot)      (log-moneyness, 0 = ATM)
        t = dte / 365               (years to expiration)

    Parameters
    ----------
    day_chain : DataFrame
        One day's real options chain (must have columns 'iv', 'dte', 'strike',
        'underlying_price').
    min_points : int
        Minimum number of valid rows required to attempt a fit.

    Returns
    -------
    dict with keys {'coeffs': ndarray(6,), 'spot': float, 'n': int}, or None on
    failure (too few points, singular matrix, implausible fit).
    """
    df = day_chain.dropna(subset=['iv', 'dte', 'underlying_price', 'strike'])
    if len(df) < min_points:
        return None

    spot = float(df['underlying_price'].iloc[0])
    if spot <= 0:
        return None

    m = np.log(np.maximum(df['strike'].values, 0.01) / spot)
    t = np.maximum(df['dte'].values, 1) / 365.0
    iv = np.clip(pd.to_numeric(df['iv'], errors='coerce').values, 0.03, 3.0)

    # Design matrix: [1, m, t, m², m·t, t²]
    A = np.column_stack([np.ones_like(m), m, t, m * m, m * t, t * t])
    try:
        coeffs, *_ = np.linalg.lstsq(A, iv, rcond=None)
    except np.linalg.LinAlgError:
        return None

    # Sanity check: fitted values at data points should be close to observed IV.
    fitted = A @ coeffs
    if np.any(np.isnan(fitted)) or np.any(np.abs(fitted - iv) > 0.75):
        return None

    # Record the (m, t) support of the fit. A bivariate polynomial with t²/m² terms
    # blows up when EXTRAPOLATED past its data — e.g. a 87-DTE far leg priced off a
    # surface fit only to 10-66 DTE gets a fabricated IV that the optimizer then games.
    # Storing the range lets _reprice_group clamp evaluation to the support (flat
    # extrapolation at the boundary IV) instead of quadratic divergence.
    return {
        'coeffs': coeffs, 'spot': spot, 'n': len(df),
        'm_lo': float(m.min()), 'm_hi': float(m.max()),
        't_lo': float(t.min()), 't_hi': float(t.max()),
    }


# ---------------------------------------------------------------------------
# Vectorised apply — one date group at a time
# ---------------------------------------------------------------------------

def _reprice_group(grp: pd.DataFrame, params: Dict,
                   r: float, spread_frac: float, min_spread: float,
                   dividend_yield: float) -> pd.DataFrame:
    """Reprice ALL rows in *grp* from a single fitted IV surface — numpy fast."""
    from scipy.stats import norm

    d = grp.copy()
    c = params['coeffs']

    S = d['underlying_price'].to_numpy(float)
    K = d['strike'].to_numpy(float)
    T = np.clip(d['dte'].to_numpy(float), 0.0, None) / 365.0

    # --- IV from fitted surface ---
    # Clamp (m, t) to the fit's support BEFORE evaluating the polynomial. Beyond the
    # support the t²/m² terms extrapolate quadratically and diverge (a 87-DTE far leg
    # priced off a 10-66 DTE fit was getting a fabricated IV the optimizer exploited).
    # Clamping = flat extrapolation at the nearest-edge IV, which is conservative and
    # internally consistent with the near leg.
    m_raw = np.log(np.maximum(K, 0.01) / params['spot'])
    m = np.clip(m_raw, params.get('m_lo', -np.inf), params.get('m_hi', np.inf))
    t = np.clip(T, params.get('t_lo', 0.0), params.get('t_hi', np.inf))
    iv = c[0] + c[1]*m + c[2]*t + c[3]*m*m + c[4]*m*t + c[5]*t*t
    iv = np.clip(iv, 0.03, 3.0)

    # --- Black-Scholes vectorised (same pattern as reprice_from_iv) ---
    is_call = d['option_type'].astype(str).str.lower().isin(['call', 'c']).to_numpy()
    with np.errstate(divide='ignore', invalid='ignore'):
        sqrtT = np.sqrt(T)
        d1 = (np.log(S / K) + (r - dividend_yield + 0.5 * iv ** 2) * T) / (iv * sqrtT)
        d2 = d1 - iv * sqrtT
        call = S * np.exp(-dividend_yield * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        put  = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-dividend_yield * T) * norm.cdf(-d1)

    mid = np.where(is_call, call, put)
    expired = T <= 0
    mid = np.where(expired,
                   np.where(is_call, np.maximum(S - K, 0.0), np.maximum(K - S, 0.0)),
                   mid)
    mid = np.nan_to_num(np.maximum(mid, 0.0), nan=0.0, posinf=0.0, neginf=0.0)

    half = np.maximum(spread_frac * mid, min_spread) / 2.0
    d['iv'] = iv
    d['bid'] = np.maximum(mid - half, 0.01)
    d['ask'] = mid + half
    d['last'] = mid

    # --- Greeks (delta, gamma, theta, vega) vectorised ---
    with np.errstate(divide='ignore', invalid='ignore'):
        norm_pdf_d1 = norm.pdf(d1)
        d['gamma'] = norm_pdf_d1 / (S * iv * sqrtT) * np.exp(-dividend_yield * T)

        # delta
        delta_call = np.exp(-dividend_yield * T) * norm.cdf(d1)
        delta_put  = -np.exp(-dividend_yield * T) * norm.cdf(-d1)
        d['delta'] = np.where(is_call, delta_call, delta_put)
        d['abs_delta'] = np.abs(d['delta'])

        # theta (per-day)
        term1 = -S * norm_pdf_d1 * iv * np.exp(-dividend_yield * T) / (2 * sqrtT)
        term2_r = r * K * np.exp(-r * T)
        term2_q = dividend_yield * S * np.exp(-dividend_yield * T)
        theta_call = term1 - term2_r * norm.cdf(d2) + term2_q * norm.cdf(d1)
        theta_put  = term1 + term2_r * norm.cdf(-d2) - term2_q * norm.cdf(-d1)
        d['theta'] = np.where(is_call, theta_call, theta_put) / 365.0

        # vega
        d['vega'] = S * norm_pdf_d1 * np.sqrt(T) * np.exp(-dividend_yield * T) / 100.0

    return d


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def apply_surface_fill(fill_rows: pd.DataFrame,
                       real_data: pd.DataFrame,
                       r: float = 0.04,
                       spread_frac: float = 0.03,
                       min_spread: float = 0.05,
                       dividend_yield: float = 0.015) -> pd.DataFrame:
    """Reprice synthetic fill rows using per-date IV surfaces fitted from real data.

    Parameters
    ----------
    fill_rows : DataFrame
        Synthetic rows being used to fill gaps.  Must have ``_date`` column
        (normalized ``quote_date``).
    real_data : DataFrame
        Complete real dataset.  Must have ``_date`` column (normalized).
    r, spread_frac, min_spread, dividend_yield : float
        Black-Scholes + spread parameters.

    Returns
    -------
    DataFrame with same columns as *fill_rows*, but IV / price / greeks replaced
    by surface-fit values for every date where a surface could be fitted.  Rows
    for dates without a valid fit are returned unchanged.
    """
    result = fill_rows.copy()
    n_total = len(result)
    n_fitted = 0

    for date, day_real in real_data.groupby('_date'):
        params = fit_day_surface(day_real)
        if params is None:
            continue
        mask = result['_date'] == date
        if not mask.any():
            continue
        idx = result.index[mask]
        subgroup = result.loc[idx]
        repaired = _reprice_group(subgroup, params,
                                   r, spread_frac, min_spread, dividend_yield)
        result.loc[idx] = repaired.values
        n_fitted += len(idx)

    pct = 100.0 * n_fitted / n_total if n_total else 0.0
    print(f"  Surface-fit: {n_fitted:,} / {n_total:,} synthetic-fill rows repriced"
          f" ({pct:.1f}%)")
    return result
