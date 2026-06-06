"""trendrev — repaint-aware backtesting & tuning for the ThinkOrSwim 'Trend Reversal' indicator.

The package ports the ThinkScript indicator to Python, backtests it honestly (no look-ahead),
fine-tunes it with overfitting-aware validation, and benchmarks it against a suite of other
medium-term strategies. Validation borrows from Marcos Lopez de Prado, *Advances in Financial
Machine Learning* (purged CV, meta-labeling, deflated Sharpe, PBO) — see ``trendrev.afml``.
"""

from . import data, indicators, strategies, backtest, metrics  # noqa: F401

__all__ = ["data", "indicators", "strategies", "backtest", "metrics"]
__version__ = "0.1.0"

# afml needs scikit-learn / statsmodels (only the AFML scripts use it). Keep it optional so the
# core engine imports cleanly in lighter environments; `from trendrev import afml` still works.
try:
    from . import afml  # noqa: F401
    __all__.append("afml")
except ModuleNotFoundError:
    pass
