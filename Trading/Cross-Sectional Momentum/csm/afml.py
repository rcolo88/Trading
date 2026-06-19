# VENDORED from Trend Reversal/trendrev/afml.py
# Faithful single-process port of Marcos López de Prado,
# *Advances in Financial Machine Learning* (AFML) primitives.
# See that file for the authoritative version and full docstring.
# ─────────────────────────────────────────────────────────────
"""Marcos Lopez de Prado, *Advances in Financial Machine Learning* (AFML) primitives.

Faithful, single-process adaptations of the book's code snippets, used to make the backtest and the
parameter tuning honest in the face of (a) the indicator's repaint/overlap and (b) selection bias
from searching many parameter sets. Chapter references are noted per function.

Included:
* Event-based sampling — :func:`get_daily_vol` (Ch. 3), :func:`cusum_events` (Ch. 2).
* Triple-barrier labeling — :func:`add_vertical_barrier`, :func:`get_events`, :func:`get_bins`
  (Ch. 3), with meta-labeling support.
* Sample uniqueness & weights — :func:`num_co_events`, :func:`avg_uniqueness`,
  :func:`return_attribution_weights` (Ch. 4).
* Leakage-free CV — :class:`PurgedKFold`, :func:`cv_score` (Ch. 7).
* Bet sizing — :func:`bet_size_from_prob` (Ch. 10).
* Overfitting-aware evaluation — :func:`probabilistic_sharpe_ratio`, :func:`deflated_sharpe_ratio`
  (Ch. 14), :func:`prob_backtest_overfitting` / CSCV (Ch. 11-12).
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.model_selection import KFold


# ============================================================ event sampling (Ch. 2-3)
def get_daily_vol(close: pd.Series, span: int = 100) -> pd.Series:
    """Exponentially-weighted daily return volatility (AFML snippet 3.1). Used to set barriers."""
    idx = close.index.searchsorted(close.index - pd.Timedelta(days=1))
    idx = idx[idx > 0]
    aligned = pd.Series(close.index[idx - 1], index=close.index[close.shape[0] - idx.shape[0]:])
    ret = close.loc[aligned.index] / close.loc[aligned.values].values - 1.0
    return ret.ewm(span=span).std()


def cusum_events(close: pd.Series, threshold) -> pd.DatetimeIndex:
    """Symmetric CUSUM filter (AFML snippet 2.4): sample a bar only after a run of moves exceeds
    ``threshold`` (scalar, or a per-bar Series such as ``get_daily_vol``). Filters noise so labels
    sit on meaningful events rather than every calendar day."""
    t_events, s_pos, s_neg = [], 0.0, 0.0
    diff = np.log(close).diff().dropna()
    if isinstance(threshold, pd.Series):
        thr = threshold.reindex(diff.index).ffill().bfill()
    else:
        thr = pd.Series(float(threshold), index=diff.index)
    for i in diff.index:
        s_pos = max(0.0, s_pos + diff.loc[i])
        s_neg = min(0.0, s_neg + diff.loc[i])
        if s_neg < -thr.loc[i]:
            s_neg = 0.0
            t_events.append(i)
        elif s_pos > thr.loc[i]:
            s_pos = 0.0
            t_events.append(i)
    return pd.DatetimeIndex(t_events)


# ============================================================ triple-barrier labeling (Ch. 3)
def add_vertical_barrier(t_events: pd.DatetimeIndex, close: pd.Series, num_days: int = 10) -> pd.Series:
    """Time barrier: the bar ``num_days`` after each event (AFML snippet 3.4)."""
    idx = close.index.searchsorted(t_events + pd.Timedelta(days=num_days))
    idx = idx[idx < close.shape[0]]
    return pd.Series(close.index[idx], index=t_events[: idx.shape[0]])


def _apply_pt_sl(close: pd.Series, events: pd.DataFrame, pt_sl) -> pd.DataFrame:
    out = events[["t1"]].copy()
    pt = pt_sl[0] * events["trgt"] if pt_sl[0] > 0 else pd.Series(index=events.index, dtype=float)
    sl = -pt_sl[1] * events["trgt"] if pt_sl[1] > 0 else pd.Series(index=events.index, dtype=float)
    for loc, t1 in events["t1"].fillna(close.index[-1]).items():
        path = close[loc:t1]
        path = (path / close[loc] - 1.0) * events.at[loc, "side"]
        out.at[loc, "sl"] = path[path < sl[loc]].index.min()
        out.at[loc, "pt"] = path[path > pt[loc]].index.min()
    return out


def get_events(
    close: pd.Series,
    t_events: pd.DatetimeIndex,
    pt_sl,
    target: pd.Series,
    min_ret: float = 0.0,
    vertical: pd.Series | None = None,
    side: pd.Series | None = None,
) -> pd.DataFrame:
    """Find the first-touched barrier for each event (AFML snippets 3.3/3.6).

    ``pt_sl`` are profit-take / stop-loss multiples of ``target``. When ``side`` is provided the
    labeling becomes *meta-labeling* (size/skip a side chosen by a primary model)."""
    target = target.reindex(t_events)
    target = target[target > min_ret]
    if vertical is None:
        vertical = pd.Series(pd.NaT, index=t_events)
    if side is None:
        side_ = pd.Series(1.0, index=target.index)
        pt_sl_ = [pt_sl[0], pt_sl[0]]
    else:
        side_ = side.reindex(target.index)
        pt_sl_ = pt_sl[:2]
    events = pd.concat({"t1": vertical, "trgt": target, "side": side_}, axis=1).dropna(subset=["trgt"])
    touched = _apply_pt_sl(close, events, pt_sl_)
    events["t1"] = touched.dropna(how="all").min(axis=1)
    if side is None:
        events = events.drop("side", axis=1)
    return events


def get_bins(events: pd.DataFrame, close: pd.Series) -> pd.DataFrame:
    """Label the realized return and class for each event (AFML snippet 3.7).

    With a ``side`` column the bin is meta-labeling: 1 = take the bet, 0 = skip it."""
    events_ = events.dropna(subset=["t1"])
    px = events_.index.union(pd.DatetimeIndex(events_["t1"].values)).drop_duplicates()
    px = close.reindex(px, method="bfill")
    out = pd.DataFrame(index=events_.index)
    out["ret"] = px.loc[events_["t1"].values].values / px.loc[events_.index].values - 1.0
    if "side" in events_:
        out["ret"] *= events_["side"]
    out["bin"] = np.sign(out["ret"])
    if "side" in events_:
        out.loc[out["ret"] <= 0, "bin"] = 0
    out["t1"] = events_["t1"]
    return out


# ============================================================ sample uniqueness & weights (Ch. 4)
def num_co_events(close_index: pd.DatetimeIndex, t1: pd.Series) -> pd.Series:
    """Number of concurrent (overlapping) labels at each bar (AFML snippet 4.1)."""
    t1 = t1.fillna(close_index[-1])
    iloc = close_index.searchsorted(pd.DatetimeIndex([t1.index[0], t1.max()]))
    count = pd.Series(0.0, index=close_index[iloc[0]: iloc[1] + 1])
    for t_in, t_out in t1.items():
        count.loc[t_in:t_out] += 1.0
    return count


def avg_uniqueness(t1: pd.Series, co_events: pd.Series) -> pd.Series:
    """Average uniqueness of each label (AFML snippet 4.2)."""
    wght = pd.Series(index=t1.index, dtype=float)
    for t_in, t_out in t1.items():
        wght.loc[t_in] = (1.0 / co_events.loc[t_in:t_out]).mean()
    return wght


def return_attribution_weights(t1: pd.Series, co_events: pd.Series, close: pd.Series) -> pd.Series:
    """Sample weights by absolute return attribution, de-overlapped (AFML snippet 4.10)."""
    ret = np.log(close).diff()
    wght = pd.Series(index=t1.index, dtype=float)
    for t_in, t_out in t1.items():
        wght.loc[t_in] = (ret.loc[t_in:t_out] / co_events.loc[t_in:t_out]).sum()
    return wght.abs()


# ============================================================ purged cross-validation (Ch. 7)
class PurgedKFold(KFold):
    """K-Fold that purges training labels overlapping the test set and applies an embargo.

    AFML snippet 7.3. ``t1`` maps each observation's start time to its label end time; this is what
    lets the splitter remove leakage from overlapping triple-barrier labels."""

    def __init__(self, n_splits: int = 5, t1: pd.Series | None = None, pct_embargo: float = 0.0):
        super().__init__(n_splits=n_splits, shuffle=False)
        self.t1 = t1
        self.pct_embargo = pct_embargo

    def split(self, X, y=None, groups=None):
        if (X.index != self.t1.index).any():
            raise ValueError("X and t1 must share the same index")
        indices = np.arange(X.shape[0])
        embargo = int(X.shape[0] * self.pct_embargo)
        test_ranges = [(i[0], i[-1] + 1) for i in np.array_split(indices, self.n_splits)]
        for start, end in test_ranges:
            t0 = self.t1.index[start]
            test_idx = indices[start:end]
            max_t1_idx = self.t1.index.searchsorted(self.t1.iloc[test_idx].max())
            train_idx = self.t1.index.searchsorted(self.t1[self.t1 <= t0].index)
            if max_t1_idx < X.shape[0]:
                train_idx = np.concatenate((train_idx, indices[max_t1_idx + embargo:]))
            yield train_idx, test_idx


def cv_score(clf, X, y, sample_weight=None, scoring="accuracy", t1=None, n_splits=5, pct_embargo=0.0):
    """Cross-validated score using :class:`PurgedKFold` (AFML snippet 7.4)."""
    from sklearn.metrics import accuracy_score, log_loss

    cv = PurgedKFold(n_splits=n_splits, t1=t1, pct_embargo=pct_embargo)
    if sample_weight is None:
        sample_weight = pd.Series(1.0, index=X.index)
    scores = []
    for train, test in cv.split(X):
        fit = clf.fit(X.iloc[train], y.iloc[train], sample_weight=sample_weight.iloc[train].values)
        if scoring == "neg_log_loss":
            prob = fit.predict_proba(X.iloc[test])
            s = -log_loss(y.iloc[test], prob, sample_weight=sample_weight.iloc[test].values,
                          labels=clf.classes_)
        else:
            pred = fit.predict(X.iloc[test])
            s = accuracy_score(y.iloc[test], pred, sample_weight=sample_weight.iloc[test].values)
        scores.append(s)
    return np.array(scores)


# ============================================================ bet sizing (Ch. 10)
def bet_size_from_prob(prob: pd.Series, pred: pd.Series, num_classes: int = 2) -> pd.Series:
    """Translate a classifier probability into a signed bet size in [-1, 1] (AFML snippet 10.1)."""
    z = (prob - 1.0 / num_classes) / np.sqrt(prob * (1.0 - prob))
    return pred * (2 * norm.cdf(z) - 1.0)


# ============================================================ overfitting-aware stats (Ch. 11-14)
def probabilistic_sharpe_ratio(returns: pd.Series, sr_benchmark: float = 0.0) -> float:
    """Probability the true (per-observation) Sharpe exceeds ``sr_benchmark`` (AFML Ch. 14).

    Corrects for track-record length, skew and kurtosis. ``sr_benchmark`` is a *non-annualized*
    Sharpe (0 = 'better than random')."""
    r = returns[returns.notna()]
    n = len(r)
    sr = r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else 0.0
    skew = r.skew()
    kurt = r.kurtosis() + 3.0  # pandas returns excess kurtosis
    denom = np.sqrt((1 - skew * sr + (kurt - 1) / 4.0 * sr ** 2) / (n - 1))
    return float(norm.cdf((sr - sr_benchmark) / denom)) if denom > 0 else 0.5


def expected_max_sharpe(sr_trials: np.ndarray) -> float:
    """Expected maximum *per-observation* Sharpe under the null of zero-skill trials (AFML Ch. 14)."""
    sr_trials = np.asarray(sr_trials, dtype=float)
    n = len(sr_trials)
    if n < 2:
        return 0.0
    sigma = sr_trials.std(ddof=1)
    emc = 0.5772156649  # Euler-Mascheroni
    return float(sigma * ((1 - emc) * norm.ppf(1 - 1.0 / n) + emc * norm.ppf(1 - 1.0 / (n * np.e))))


def deflated_sharpe_ratio(returns: pd.Series, sr_trials: np.ndarray) -> float:
    """Deflated Sharpe Ratio: PSR benchmarked against the expected best of ``sr_trials`` (AFML Ch.14).

    This is the antidote to grid-search optimism — it asks whether the *selected* configuration beats
    what the luckiest of N zero-skill trials would have produced. ``sr_trials`` are the
    per-observation Sharpe ratios of every configuration tested."""
    return probabilistic_sharpe_ratio(returns, sr_benchmark=expected_max_sharpe(sr_trials))


def prob_backtest_overfitting(returns_matrix: pd.DataFrame, n_partitions: int = 16) -> dict:
    """Probability of Backtest Overfitting via CSCV (AFML Ch. 11-12).

    ``returns_matrix`` is ``T x N`` — one return column per configuration tried. Splits time into
    ``n_partitions`` blocks, and over every balanced in-sample/out-of-sample combination checks
    whether the IS-best config underperforms OOS. Returns PBO and the rank-logit distribution."""
    M = returns_matrix.dropna()
    n_partitions -= n_partitions % 2  # must be even
    rows = (len(M) // n_partitions) * n_partitions
    blocks = np.array_split(np.arange(rows), n_partitions)

    logits = []
    for is_combo in combinations(range(n_partitions), n_partitions // 2):
        is_rows = np.concatenate([blocks[k] for k in is_combo])
        oos_rows = np.concatenate([blocks[k] for k in range(n_partitions) if k not in is_combo])
        is_sr = _sr(M.iloc[is_rows])
        oos_sr = _sr(M.iloc[oos_rows])
        n_star = int(is_sr.values.argmax())
        rank = oos_sr.rank().iloc[n_star] / (len(oos_sr) + 1)
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        logits.append(np.log(rank / (1 - rank)))
    logits = np.array(logits)
    return {"pbo": float((logits <= 0).mean()), "logits": logits}


def _sr(M: pd.DataFrame) -> pd.Series:
    sd = M.std(ddof=1)
    return (M.mean() / sd.replace(0, np.nan)).fillna(0.0)
