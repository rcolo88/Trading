"""Four ways to combine quality + Trend Reversal, side by side on one engine (your exact question).

  Fundamental scanner               — buy the top-N quality names now, hold (no timing).
  Fundamental scanner + entry timing — enter a top-N name only when 'buy' paints, then HOLD.
                                       (Live: hold while it stays top-N. Backtest: the 'leaves top-N'
                                        exit can't fire without point-in-time membership, so it holds
                                        to the end — a clean read on the value of ENTRY timing.)
  Fundamental scanner + full timing  — top-N names, buy when 'buy' paints, sell when 'sell' paints.
  S&P 500 + full timing              — across S&P 500 names, buy when 'buy' paints, sell on 'sell'.

All long-only, equal-weight 1/N sleeves, same costs and window. (scanner -> +entry timing) isolates
ENTRY timing, (+entry -> +full timing) isolates EXIT timing; judge on max drawdown, not just CAGR.

    python scripts/11_four_way.py                       # scanner top-10 & top-20, top-60 S&P 500
    python scripts/11_four_way.py --top-ns 10 20 30 --sp500-n 100 --months 36
"""
import argparse
import io
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, backtest, metrics, scanner, plotting  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "four_way")
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
    """Download once; return {ticker: df}. Skips names with no data."""
    frames = {}
    for t in tickers:
        try:
            frames[t] = data.get_ohlcv(t, start=start)
        except Exception as exc:
            print(f"  ! skip {t}: {exc}")
    return frames


def window(ret, months):
    if not months:
        return ret
    return ret[ret.index >= ret.index[-1] - pd.DateOffset(months=months)]


def overlay_returns(frames, profit_target, exit_signal, months):
    """Equal-weight portfolio returns for a (target, exit) rule across the given frames."""
    rmap = {}
    for t, df in frames.items():
        pos = strategies.trend_reversal_long_target(
            df, profit_target=profit_target, exit_signal=exit_signal, **EMA)
        res = backtest.run_backtest(df, pos, commission_bps=1.0, slippage_bps=5.0)
        rmap[t] = window(res.returns, months)
    port, _ = backtest.equal_weight_returns(rmap)
    return port


def bh_returns(frames, months):
    rmap = {}
    for t, df in frames.items():
        res = backtest.run_backtest(df, strategies.buy_and_hold(df), 0.0, 0.0)
        rmap[t] = window(res.returns, months)
    port, _ = backtest.equal_weight_returns(rmap)
    return port


def summarize(returns) -> dict:
    eq = (1 + returns.fillna(0)).cumprod()
    return {"CAGR": metrics.cagr(eq), "Sharpe": metrics.sharpe_ratio(returns),
            "max_DD": metrics.max_drawdown(eq), "exposure": float((returns != 0).mean())}


def green_now(frames) -> list[str]:
    out = []
    for t, df in frames.items():
        f = strategies.trend_reversal_frame(df, **EMA)
        if f["buysignal"].iloc[-1] == 1:
            just = len(f) > 1 and f["buysignal"].iloc[-2] == 0
            out.append(f"{t}{'*' if just else ''}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top-ns", type=int, nargs="+", default=[10, 20],
                    help="scanner basket sizes to compare (default: 10 20)")
    ap.add_argument("--sp500-n", type=int, default=60,
                    help="how many S&P 500 names (largest by cap) to use for the S&P 500 approach")
    ap.add_argument("--sp500-full", action="store_true", help="use all ~500 members (slow first run)")
    ap.add_argument("--months", type=int, default=None)
    ap.add_argument("--no-gate", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    start = "2005-01-01"
    span = f"last {args.months}m" if args.months else "2005-present"

    # Universes -------------------------------------------------------------------------------------
    top_ns = sorted(set(args.top_ns))
    scan_frames_by_n = {}                         # n -> {ticker: df}
    for n in top_ns:
        tickers = [c.ticker for c in scanner.top_candidates(n, require_gates=not args.no_gate)]
        scan_frames_by_n[n] = (tickers, None)     # frames filled below

    members = sp500_members()
    caps = {c.ticker: c.market_cap for c in scanner.load_candidates()}
    sp500_ranked = sorted((t for t in members if t in caps), key=lambda t: caps[t], reverse=True)
    sp_tickers = sp500_ranked if args.sp500_full else sp500_ranked[:args.sp500_n]

    print(f"\nFour-way comparison  |  {span}  |  costs 6bps round-trip  |  equal-weight 1/N sleeves")
    for n in top_ns:
        print(f"  scanner top-{n}: {', '.join(scan_frames_by_n[n][0])}")
    print(f"  S&P 500 universe: {len(sp_tickers)} largest by cap"
          f"{' (FULL)' if args.sp500_full else ''}\n  downloading data ...")

    for n in top_ns:
        tickers = scan_frames_by_n[n][0]
        scan_frames_by_n[n] = (tickers, load_frames(tickers, start))
    sp_frames = load_frames(sp_tickers, start)
    spy = data.get_ohlcv("SPY", start=start)
    spy_ret = window(backtest.run_backtest(spy, strategies.buy_and_hold(spy), 0.0, 0.0).returns,
                     args.months)

    # Approaches ------------------------------------------------------------------------------------
    rows = {"SPY buy & hold (baseline)": summarize(spy_ret)}
    for n in top_ns:
        frames = scan_frames_by_n[n][1]
        rows[f"Fundamental scanner (top {n})"] = summarize(bh_returns(frames, args.months))
        rows[f"Fundamental scanner + entry timing (top {n})"] = \
            summarize(overlay_returns(frames, None, "hold", args.months))
        rows[f"Fundamental scanner + full timing (top {n})"] = \
            summarize(overlay_returns(frames, None, "sell_signal", args.months))
    rows["S&P 500 + full timing"] = summarize(overlay_returns(sp_frames, None, "sell_signal", args.months))

    tbl = pd.DataFrame(rows).T[["CAGR", "Sharpe", "max_DD", "exposure"]]
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    pd.set_option("display.max_colwidth", 45)
    print("\n" + "=" * 86)
    print(tbl.to_string())
    print("=" * 86)
    print("Read it: (scanner -> +entry timing) = value of ENTRY timing; (+entry -> +full timing) = "
          "value of EXIT timing. Compare top-10 vs top-20 rows to see what spreading the money does: "
          "more names usually trims return a touch and shaves drawdown (diversification).")

    # Live: what's a 'buy' right now ----------------------------------------------------------------
    print(f"\nGreen RIGHT NOW (buy painted; * = just turned on today):")
    big_n = top_ns[-1]
    print(f"  scanner top-{big_n}: {', '.join(green_now(scan_frames_by_n[big_n][1])) or '(none)'}")
    gn = green_now(sp_frames)
    print(f"  S&P 500 (of {len(sp_frames)} scanned): {', '.join(gn) or '(none)'}")

    csv_path = os.path.join(OUT, "four_way_comparison.csv")
    png_path = os.path.join(OUT, "four_way_comparison.png")
    tbl.to_csv(csv_path)
    plotting.plot_table(tbl, png_path, index_label="approach",
                        title=f"Four-way comparison ({span}) — CAGR / Sharpe / max DD / exposure")
    print(f"\nSaved table -> {csv_path}\n            -> {png_path}")
    print("\nHonesty: the scanner rows use TODAY's top-N, so their *selection* is hindsight; the "
          "timing columns (drawdown especially) are the causal, trustworthy part. S&P 500 + full "
          "timing has no fundamental selection bias but still cherry-picks the current roster.")


if __name__ == "__main__":
    main()
