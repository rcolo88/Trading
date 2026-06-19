"""Meta-model: pooled RandomForest + PurgedKFoldPanel (calendar-time CV).

PurgedKFoldPanel is the key extension of afml.PurgedKFold (AFML Ch. 7) to a
*pooled* cross-sectional dataset.  Single-asset PurgedKFold purges by index;
here rows are (ticker, event_date) so we purge based on calendar time: any
training sample whose label window [event_date, t1] overlaps the test fold's
calendar span is removed, plus an embargo gap.

This prevents the most dangerous leakage mode in cross-sectional ML: a test
stock's price path overlapping a training stock's barrier window on the same
calendar dates.
"""
from __future__ import annotations

from datetime import datetime
from itertools import combinations
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.base import BaseEstimator, ClassifierMixin

from csm.afml import bet_size_from_prob

MODEL_FILE = "meta_model.pkl"


# ─────────────────────────────────────────────────────────────────────────────
#  PurgedKFoldPanel
# ─────────────────────────────────────────────────────────────────────────────

class PurgedKFoldPanel:
    """K-Fold cross-validator for pooled (ticker, date) samples.

    Test folds are contiguous calendar-time blocks (not random rows).
    Training samples whose label end time (t1) falls within or after the test
    fold's calendar start are purged.  An embargo of `pct_embargo` of the full
    time span is added after each test fold to prevent leakage from
    post-event price moves.

    Parameters
    ----------
    n_splits    : number of folds
    t1          : Series mapping (ticker, event_date) → label end date
    pct_embargo : fraction of total time span to embargo after each test fold
    """

    def __init__(self, n_splits: int = 5, t1: pd.Series | None = None,
                 pct_embargo: float = 0.02):
        self.n_splits    = n_splits
        self.t1          = t1
        self.pct_embargo = pct_embargo

    def split(self, X: pd.DataFrame, y=None, groups=None):
        """Yield (train_indices, test_indices) pairs.

        X must have a MultiIndex (ticker, event_date).  We sort by event_date
        to create calendar-sequential folds.
        """
        if not isinstance(X.index, pd.MultiIndex):
            raise ValueError("X must have MultiIndex (ticker, event_date)")

        # Sort by event date (level 1) to ensure calendar ordering
        event_dates = X.index.get_level_values("date")
        sort_order  = np.argsort(event_dates, stable=True)
        indices     = np.arange(len(X))

        # Split sorted indices into n_splits contiguous calendar blocks
        folds = np.array_split(sort_order, self.n_splits)

        t1_vals = self.t1.reindex(X.index) if self.t1 is not None else None

        # Embargo: calendar days after test fold's latest event_date
        all_event_dates = pd.DatetimeIndex(event_dates)
        total_span      = (all_event_dates.max() - all_event_dates.min()).days
        embargo_days    = int(total_span * self.pct_embargo)

        for fold_test_sorted in folds:
            test_idx = indices[fold_test_sorted]

            test_event_dates = pd.DatetimeIndex(event_dates[test_idx])
            test_start       = test_event_dates.min()
            test_end         = test_event_dates.max()
            embargo_cutoff   = test_end + pd.Timedelta(days=embargo_days)

            # Training candidates: everything NOT in test
            train_candidates = np.setdiff1d(indices, test_idx)

            if t1_vals is not None:
                # Purge: remove training samples whose label window overlaps test period
                t1_train = t1_vals.iloc[train_candidates]
                ed_train = pd.DatetimeIndex(event_dates[train_candidates])
                # Keep if label ends BEFORE test_start AND event_date is BEFORE test_start
                keep = (
                    (t1_train.values < test_start) &
                    (ed_train < test_start)
                )
                # Also allow training samples that come AFTER the embargo cutoff
                after_embargo = ed_train >= embargo_cutoff
                train_idx = train_candidates[keep | after_embargo.values]
            else:
                # No t1: use simple embargo on event dates
                ed_train  = pd.DatetimeIndex(event_dates[train_candidates])
                keep = (ed_train < test_start) | (ed_train >= embargo_cutoff)
                train_idx = train_candidates[keep.values]

            yield train_idx, test_idx


# ─────────────────────────────────────────────────────────────────────────────
#  Feature builder: one row per (ticker, event_date) in the label set
# ─────────────────────────────────────────────────────────────────────────────

def build_feature_matrix(
    bins:   pd.DataFrame,
    prices: pd.DataFrame,
    cfg:    dict,
) -> pd.DataFrame:
    """Build a feature matrix for all (ticker, event_date) entries in `bins`.

    Features per candidate long:
      resid_mom, naive_mom   — primary signals at entry
      ret1m                  — 1-month reversal (negative is good)
      ret3m                  — 3-month momentum
      idio_vol               — idiosyncratic vol
      dist_52wk              — distance from 52-week high (George–Hwang)
      beta                   — CAPM beta
      spy_ma200              — SPY trend (above/below MA)
      spy_vol                — SPY realised vol
    """
    from csm.signals import build_features as _build_features

    panels, spy_feat = _build_features(prices, cfg)

    rows = []
    for (ticker, event_date) in bins.index:
        if ticker not in prices.columns:
            continue
        if event_date not in prices.index:
            continue
        row = {"ticker": ticker, "date": event_date}
        for feat_name, df in panels.items():
            if ticker in df.columns and event_date in df.index:
                row[feat_name] = df.at[event_date, ticker]
            else:
                row[feat_name] = np.nan
        if event_date in spy_feat.index:
            for col in spy_feat.columns:
                row[col] = spy_feat.at[event_date, col]
        else:
            for col in spy_feat.columns:
                row[col] = np.nan
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index(["ticker", "date"])
    df.index.names = ["ticker", "date"]
    return df.dropna(how="all")


# ─────────────────────────────────────────────────────────────────────────────
#  Train and evaluate the meta-model
# ─────────────────────────────────────────────────────────────────────────────

def train_meta_model(
    X:       pd.DataFrame,
    y:       pd.Series,
    weights: pd.Series,
    bins:    pd.DataFrame,
    cfg:     dict,
) -> tuple[RandomForestClassifier, np.ndarray, np.ndarray]:
    """Train meta-model with PurgedKFoldPanel and return OOS probabilities.

    Returns
    -------
    clf      : fitted RandomForestClassifier (full-sample fit, for live scoring)
    oos_prob : OOS P(take) for each sample (len = len(X))
    cv_acc   : per-fold accuracy scores
    """
    ml_cfg = cfg.get("meta_labeling", {})
    n_est  = int(ml_cfg.get("n_estimators",      300))
    depth  = int(ml_cfg.get("max_depth",          4))
    leaf   = int(ml_cfg.get("min_samples_leaf",  20))
    n_spl  = int(ml_cfg.get("n_splits",           5))
    emb    = float(ml_cfg.get("pct_embargo",      0.02))

    clf = RandomForestClassifier(
        n_estimators    = n_est,
        max_depth       = depth,
        min_samples_leaf= leaf,
        class_weight    = "balanced_subsample",
        random_state    = 7,
        n_jobs          = -1,
    )

    # t1 indexed by (ticker, event_date)
    t1 = bins.reindex(X.index)["t1"]

    cv       = PurgedKFoldPanel(n_splits=n_spl, t1=t1, pct_embargo=emb)
    oos_prob = np.full(len(X), np.nan)
    cv_acc   = []

    for train_idx, test_idx in cv.split(X):
        if len(train_idx) < 50 or len(test_idx) < 5:
            continue
        X_tr = X.iloc[train_idx]
        y_tr = y.iloc[train_idx]
        w_tr = weights.iloc[train_idx]

        X_te = X.iloc[test_idx]
        y_te = y.iloc[test_idx]
        w_te = weights.iloc[test_idx]

        fit  = clf.fit(X_tr, y_tr, sample_weight=w_tr.values)
        col1 = list(fit.classes_).index(1) if 1 in fit.classes_ else -1
        if col1 < 0:
            continue
        proba = fit.predict_proba(X_te)[:, col1]
        pred  = (proba >= 0.5).astype(int)
        oos_prob[test_idx] = proba

        # Weighted accuracy
        correct = (pred == y_te.values).astype(float)
        acc = float((correct * w_te.values).sum() / w_te.values.sum()) if w_te.sum() > 0 else 0.5
        cv_acc.append(acc)

    # Full-sample fit for live use
    clf.fit(X, y, sample_weight=weights.values)
    return clf, oos_prob, np.array(cv_acc)


def apply_meta_filter(
    positions:  pd.DataFrame,
    prices:     pd.DataFrame,
    bins:       pd.DataFrame,
    clf:        RandomForestClassifier,
    X_all:      pd.DataFrame,
    oos_prob:   np.ndarray,
    cfg:        dict,
) -> pd.DataFrame:
    """Replace raw position weights with meta-filtered, sized positions.

    For each (ticker, entry_date) in the label set:
      - if OOS P(take) > threshold: keep position, sized ∝ P(take)
      - else: zero the position for this holding period
    For dates not in the label set (gaps in coverage), fall back to raw weights.
    """
    ml_cfg    = cfg.get("meta_labeling", {})
    min_prob  = float(ml_cfg.get("min_prob_take", 0.55))

    meta_pos  = positions.copy()
    prob_ser  = pd.Series(oos_prob, index=X_all.index)   # (ticker, date) → P(take)

    for (ticker, entry_date), p in prob_ser.items():
        if ticker not in meta_pos.columns:
            continue
        if entry_date not in meta_pos.index:
            continue
        if np.isnan(p):
            continue

        # Find the barrier end time for this entry
        try:
            t1_date = bins.loc[(ticker, entry_date), "t1"]
        except KeyError:
            continue
        if pd.isnull(t1_date):
            continue

        if p < min_prob:
            # Skip: zero out the holding period
            mask = (meta_pos.index >= entry_date) & (meta_pos.index <= t1_date)
            meta_pos.loc[mask, ticker] = 0.0
        else:
            # Size by conviction: position scaled by bet_size(P)
            pred_ser = pd.Series([1], index=[entry_date])
            prob_s   = pd.Series([p], index=[entry_date])
            size     = float(bet_size_from_prob(prob_s, pred_ser).iloc[0])
            size     = max(0.0, min(1.0, size))
            mask     = (meta_pos.index >= entry_date) & (meta_pos.index <= t1_date)
            meta_pos.loc[mask, ticker] *= size

    return meta_pos


# ─────────────────────────────────────────────────────────────────────────────
#  Persistence: save / load / score for the `ideas` command
# ─────────────────────────────────────────────────────────────────────────────

def save_meta_model(
    clf:           RandomForestClassifier,
    feature_names: list[str],
    is_end:        pd.Timestamp,
    out_dir:       Path,
) -> None:
    """Persist the trained meta-model so `ideas` can load and apply it."""
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "clf":           clf,
        "feature_names": feature_names,
        "is_end":        str(is_end.date()),
        "trained_at":    datetime.now().isoformat(),
    }
    path = out_dir / MODEL_FILE
    joblib.dump(bundle, path)
    print(f"  Meta-model saved → {path}")


def load_meta_model(out_dir: Path) -> dict | None:
    """Load a saved meta-model bundle, or return None if absent."""
    path = out_dir / MODEL_FILE
    if not path.exists():
        return None
    return joblib.load(path)


def score_current_candidates(
    tickers:       list[str],
    prices:        pd.DataFrame,
    clf:           RandomForestClassifier,
    feature_names: list[str],
    cfg:           dict,
    as_of:         pd.Timestamp,
) -> pd.Series:
    """Return P(take) for each ticker using the saved meta-model.

    Builds the same feature vector as training (panels + SPY regime features)
    at the `as_of` date, aligns to the saved feature names, median-imputes NaNs.
    """
    from csm.signals import build_features as _build_features

    panels, spy_feat = _build_features(prices, cfg)
    spy_row = spy_feat.loc[as_of] if as_of in spy_feat.index else pd.Series(dtype=float)

    rows: dict[str, dict] = {}
    for ticker in tickers:
        row: dict = {}
        for feat_name, df in panels.items():
            if ticker in df.columns and as_of in df.index:
                row[feat_name] = df.at[as_of, ticker]
            else:
                row[feat_name] = np.nan
        for col, val in spy_row.items():
            row[col] = val
        rows[ticker] = row

    X = pd.DataFrame(rows).T.reindex(columns=feature_names)
    X = X.fillna(X.median())

    col1_idx = list(clf.classes_).index(1) if 1 in clf.classes_ else -1
    if col1_idx < 0:
        return pd.Series(0.5, index=tickers)

    proba = clf.predict_proba(X.values)[:, col1_idx]
    return pd.Series(proba, index=tickers)
