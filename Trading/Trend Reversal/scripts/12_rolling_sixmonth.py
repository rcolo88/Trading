"""Rolling 6-month analysis of the four approaches (+ SPY) on daily close.

Same four approaches as ``11_four_way.py``, but instead of one full-history number this asks the more
honest question: *how do they behave over a typical 6 months?* It reports

  * the **latest 6 months** (what's happening right now), and
  * the **distribution across all rolling 6-month windows** in history (median annualised Sharpe,
    how often the window is profitable, median and worst 6-month return, median drawdown) — so you
    see the spread, not a single lucky/unlucky slice.

IMPORTANT — the Trend Reversal indicator is computed on the **full price history** and only the
resulting daily returns are sliced into each window. The EMA 9/14/21 ribbon + state machine are
therefore always warmed up; we never recompute the signal on a cold 6-month stub (which would mis-
fire for the first ~1 month). That is what makes a 6-month evaluation valid for this indicator.

    python scripts/12_rolling_sixmonth.py                 # 6-month windows, monthly step
    python scripts/12_rolling_sixmonth.py --sp500-full --window-months 6 --step-months 1
"""
import argparse
import io
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from trendrev import data, strategies, backtest, metrics, scanner  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "rolling")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
EMA = dict(superfast=9, fast=14, slow=21, use_low_filter=True)
WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def sp500_members(refresh=False) -> set[str]:
    cache = os.path.join(DATA, "sp500_members.csv")
    if os.path.exists(cache) and not refresh:
        return set(pd.read_csv(cache)["symbol"].astype(str))
    req = urllib.request.Request(WIKI, headers={"User-Agent": "Mozilla/5.0 (research script)"})
    html = urllib.request.urlopen(req, timeout=20).read().decode()
    syms = (pd.read_html(io.StringIO(html))[0]["Symbol"].astype(str)
            .str.replace(".", "-", regex=False).str.strip().tolist())
    os.makedirs(DATA, exist_ok=True)
    pd.DataFrame({"symbol": syms}).to_csv(cache, index=False)
    return set(syms)


def load_frames(tickers, start):
    frames = {}
    for t in tickers:
        try:
            frames[t] = data.get_ohlcv(t, start=start)
        except Exception as exc:
            print(f"  ! skip {t}: {exc}")
    return frames


def overlay_daily(frames, profit_target, exit_signal):
    """Full-history equal-weight daily return series for a (target, exit) rule."""
    rmap = {}
    for t, df in frames.items():
        pos = strategies.trend_reversal_long_target(
            df, profit_target=profit_target, exit_signal=exit_signal, **EMA)
        rmap[t] = backtest.run_backtest(df, pos, 1.0, 5.0).returns
    port, _ = backtest.equal_weight_returns(rmap)
    return port


def bh_daily(frames):
    rmap = {t: backtest.run_backtest(df, strategies.buy_and_hold(df), 0.0, 0.0).returns
            for t, df in frames.items()}
    port, _ = backtest.equal_weight_returns(rmap)
    return port


def window_stats(r: pd.Series) -> dict:
    """Annualised Sharpe, total return, and max drawdown over one window of daily returns."""
    r = r.dropna()
    sd = r.std(ddof=1)
    eq = (1 + r).cumprod()
    return {
        "sharpe": float(np.sqrt(252) * r.mean() / sd) if sd > 0 else 0.0,
        "ret": float(eq.iloc[-1] - 1.0) if len(eq) else 0.0,
        "max_dd": float((eq / eq.cummax() - 1).min()) if len(eq) else 0.0,
    }


def rolling_summary(series_map, window_months, step_months, min_obs):
    rows = []
    for name, s in series_map.items():
        s = s.dropna()
        if s.empty:
            continue
        anchors = pd.date_range(s.index.min() + pd.DateOffset(months=window_months),
                                s.index.max(), freq=f"{step_months}MS")
        sh, rr, dd = [], [], []
        for a in anchors:
            w = s[(s.index > a - pd.DateOffset(months=window_months)) & (s.index <= a)]
            if len(w) < min_obs:
                continue
            st = window_stats(w)
            sh.append(st["sharpe"]); rr.append(st["ret"]); dd.append(st["max_dd"])
        if not rr:
            continue
        rr = np.array(rr)
        rows.append({
            "approach": name,
            "n_windows": len(rr),
            "med_sharpe": float(np.median(sh)),
            "pct_profitable": float((rr > 0).mean()),
            "med_6mo_ret": float(np.median(rr)),
            "worst_6mo_ret": float(rr.min()),
            "med_maxDD": float(np.median(dd)),
        })
    return pd.DataFrame(rows).set_index("approach")


def latest_table(series_map, window_months):
    rows = {}
    for name, s in series_map.items():
        s = s.dropna()
        cut = s.index[-1] - pd.DateOffset(months=window_months)
        rows[name] = window_stats(s[s.index > cut])
    return pd.DataFrame(rows).T[["ret", "sharpe", "max_dd"]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top-ns", type=int, nargs="+", default=[10, 20],
                    help="scanner basket sizes to compare (default: 10 20)")
    ap.add_argument("--sp500-n", type=int, default=60)
    ap.add_argument("--sp500-full", action="store_true")
    ap.add_argument("--window-months", type=int, default=6)
    ap.add_argument("--step-months", type=int, default=1)
    ap.add_argument("--no-gate", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    start = "2005-01-01"
    min_obs = int(args.window_months * 21 * 0.6)  # ~60% of expected trading days present

    top_ns = sorted(set(args.top_ns))
    scan_tickers_by_n = {n: [c.ticker for c in
                             scanner.top_candidates(n, require_gates=not args.no_gate)]
                         for n in top_ns}
    members = sp500_members()
    caps = {c.ticker: c.market_cap for c in scanner.load_candidates()}
    ranked = sorted((t for t in members if t in caps), key=lambda t: caps[t], reverse=True)
    sp_tickers = ranked if args.sp500_full else ranked[:args.sp500_n]

    print(f"\nRolling {args.window_months}-month analysis (daily close) | signals on full history, "
          f"returns sliced per window")
    for n in top_ns:
        print(f"  scanner top-{n}: {', '.join(scan_tickers_by_n[n])}")
    print(f"  S&P 500 universe: {len(sp_tickers)} largest by cap"
          f"{' (FULL)' if args.sp500_full else ''}\n  building return series ...")

    scan_frames_by_n = {n: load_frames(scan_tickers_by_n[n], start) for n in top_ns}
    sp_frames = load_frames(sp_tickers, start)
    spy = data.get_ohlcv("SPY", start=start)

    series_map = {
        "SPY buy & hold (baseline)": backtest.run_backtest(spy, strategies.buy_and_hold(spy), 0, 0).returns,
    }
    for n in top_ns:
        frames = scan_frames_by_n[n]
        series_map[f"Fundamental scanner (top {n})"] = bh_daily(frames)
        series_map[f"Fundamental scanner + entry timing (top {n})"] = overlay_daily(frames, None, "hold")
        series_map[f"Fundamental scanner + full timing (top {n})"] = overlay_daily(frames, None, "sell_signal")
    series_map["S&P 500 + full timing"] = overlay_daily(sp_frames, None, "sell_signal")

    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    pd.set_option("display.width", 200)

    print(f"\n=== LATEST {args.window_months} MONTHS (ret = total, sharpe = annualised) ===")
    print(latest_table(series_map, args.window_months).to_string())

    roll = rolling_summary(series_map, args.window_months, args.step_months, min_obs)
    print(f"\n=== ACROSS ALL ROLLING {args.window_months}-MONTH WINDOWS "
          f"(step {args.step_months}m) ===")
    print(roll.to_string())
    print("\nColumns: med_sharpe = median annualised Sharpe per window; pct_profitable = share of "
          "6-month windows that made money; worst_6mo_ret = the ugliest 6-month stretch; "
          "med_maxDD = typical intra-window drawdown.")
    print("Read it: a strategy good for low drawdowns shows a high pct_profitable, a shallow "
          "med_maxDD, and a less-negative worst_6mo_ret — even if its median Sharpe is similar.")

    roll.to_csv(os.path.join(OUT, "rolling_sixmonth.csv"))
    print(f"\nSaved -> {os.path.join(OUT, 'rolling_sixmonth.csv')}")


if __name__ == "__main__":
    main()
