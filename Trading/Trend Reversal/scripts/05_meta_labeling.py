"""Meta-labeling the Trend Reversal signal (AFML Ch. 3).

Primary model  : Trend Reversal picks the *side* (long/short) — this is your indicator.
Secondary model: a RandomForest decides whether to *take* each bet, trained on triple-barrier
                 meta-labels with sample-uniqueness weights and evaluated with a PurgedKFold so
                 overlapping labels cannot leak. Out-of-sample meta-predictions filter (and size)
                 the trades; we compare primary-only vs meta-filtered performance.

    python scripts/05_meta_labeling.py [TICKER]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402

from trendrev import data, indicators as ind, strategies, backtest, metrics, afml, plotting  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "meta")


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"]
    e9, e21 = ind.ema(c, 9), ind.ema(c, 21)
    feat = pd.DataFrame(index=df.index)
    feat["ret5"] = c.pct_change(5)
    feat["ret20"] = c.pct_change(20)
    feat["rsi2"] = ind.rsi(c, 2)
    feat["rsi14"] = ind.rsi(c, 14)
    feat["atr_pct"] = ind.atr(df, 14) / c
    feat["ema_spread"] = (e9 - e21) / c
    feat["dist_ema21"] = (c - e21) / c
    feat["vol"] = afml.get_daily_vol(c, 50)
    feat["mom60"] = c.pct_change(60)
    return feat


def main(ticker: str = "SPY") -> None:
    os.makedirs(OUT, exist_ok=True)
    df = data.get_ohlcv(ticker, start="2005-01-01")
    close = df["close"]

    # --- Primary model: Trend Reversal side at each entry (position changes to non-zero).
    primary = strategies.trend_reversal(df, long_short=True)
    entries = primary[(primary != 0) & (primary.shift(1) != primary)]
    t_events = entries.index
    side = primary.loc[t_events]

    # --- Triple-barrier meta-labels (take the side, or skip).
    target = afml.get_daily_vol(close, 50).reindex(df.index).ffill()
    vbar = afml.add_vertical_barrier(t_events, close, num_days=15)
    events = afml.get_events(close, t_events, pt_sl=[1.0, 1.0], target=target,
                             min_ret=0.0, vertical=vbar, side=side)
    bins = afml.get_bins(events, close)
    bins = bins.dropna(subset=["bin"])
    print(f"{ticker}: {len(bins)} primary signals | take-rate (meta=1) = {(bins['bin'] == 1).mean():.1%}")

    # --- Features, labels, sample weights.
    feat = build_features(df)
    X = feat.loc[bins.index].dropna()
    y = bins.loc[X.index, "bin"].astype(int)
    t1 = bins.loc[X.index, "t1"]
    co = afml.num_co_events(df.index, t1)
    w = afml.return_attribution_weights(t1, co, close).reindex(X.index).fillna(0.0)
    w = (w / w.mean()).clip(upper=10)

    clf = RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=20,
                                 class_weight="balanced_subsample", random_state=7, n_jobs=-1)

    # --- Purged-CV score (honest skill estimate).
    acc = afml.cv_score(clf, X, y, sample_weight=w, scoring="accuracy", t1=t1,
                        n_splits=5, pct_embargo=0.02)
    print(f"PurgedKFold accuracy: {acc.mean():.3f} +/- {acc.std():.3f} "
          f"(base rate {max(y.mean(), 1 - y.mean()):.3f})")

    # --- Out-of-sample meta predictions (per purged fold) -> filtered & sized positions.
    cv = afml.PurgedKFold(n_splits=5, t1=t1, pct_embargo=0.02)
    proba = pd.Series(index=X.index, dtype=float)
    for train, test in cv.split(X):
        fit = clf.fit(X.iloc[train], y.iloc[train], sample_weight=w.iloc[train].values)
        col = list(fit.classes_).index(1)
        proba.iloc[test] = fit.predict_proba(X.iloc[test])[:, col]

    # Bet size in [0,1] from P(take); hold side from event to its barrier.
    meta_pos = pd.Series(0.0, index=df.index)
    for loc in X.index:
        p = proba.loc[loc]
        if p > 0.5:
            size = float(2 * (afml.norm.cdf((p - 0.5) / np.sqrt(p * (1 - p))) - 0.5)) if 0 < p < 1 else 1.0
            t1_loc = events.at[loc, "t1"]
            meta_pos.loc[loc:t1_loc] = side.loc[loc] * size

    primary_res = backtest.run_backtest(df, primary, commission_bps=1.0, slippage_bps=5.0)
    meta_res = backtest.run_backtest(df, meta_pos, commission_bps=1.0, slippage_bps=5.0)

    table = metrics.metrics_table({"primary (Trend Reversal)": primary_res,
                                   "meta-labeled (filtered+sized)": meta_res})
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    pd.set_option("display.width", 160)
    print(f"\n=== {ticker}: primary vs meta-labeled ===")
    print(table.T.to_string())

    imp = pd.Series(clf.fit(X, y, sample_weight=w.values).feature_importances_, index=X.columns)
    print("\nFeature importances (full-sample fit):")
    print(imp.sort_values(ascending=False).to_string())

    plotting.plot_equity({"primary": primary_res, "meta-labeled": meta_res},
                         os.path.join(OUT, f"{ticker}_meta_equity.png"),
                         title=f"{ticker} — primary vs meta-labeled",
                         benchmark=primary_res.benchmark_equity)
    print(f"\nPlot written to {OUT}/")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "SPY")
