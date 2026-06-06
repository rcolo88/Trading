"""Shared test fixtures. Tests are offline & deterministic — they build a synthetic OHLCV frame
instead of hitting the network, so the suite never depends on yfinance availability."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(scope="session")
def ohlcv() -> pd.DataFrame:
    """A 1500-bar synthetic daily series with trends and reversals (seeded random walk)."""
    rng = np.random.default_rng(42)
    n = 1500
    idx = pd.bdate_range("2015-01-01", periods=n, name="date")
    # Drifting random walk with regime shifts so the trend strategies actually trade.
    drift = np.concatenate([np.full(n // 3, 0.0005), np.full(n // 3, -0.0006),
                            np.full(n - 2 * (n // 3), 0.0004)])
    rets = drift + rng.normal(0, 0.01, n)
    close = 100 * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.003, n)))
    vol = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol},
                        index=idx)
