"""Trend-time the Fundamental Scanner's top-N (Idea #1: quality 'what' + trend 'when').

Reads the latest ``opportunities_*.json`` from the sibling Fundamental Scanner, takes the top-N
quality names, and applies the non-repainting Trend Reversal System-A as a *timing overlay*:

  * **Live signal**  — what to do right now on each name (BUY-NOW / HOLD-green / AVOID-red / neutral).
  * **Equal-weight all-green portfolio** — each name a fixed 1/N sleeve, long only when green, else
    cash. This is the low-drawdown book you'd actually run.
  * **Honest decomposition** — the basket is chosen by *today's* fundamentals, so its raw return is
    hindsight-tainted. We therefore separate the **selection** effect (basket buy & hold) from the
    **timing** effect (overlay vs that same basket B&H), and validate the timing on a *non-hindsight*
    universe (the QUAL quality ETF) where there is no name-selection bias at all.

    python scripts/09_scanner_overlay.py                 # top 10, full history
    python scripts/09_scanner_overlay.py --top-n 15 --months 24
    python scripts/09_scanner_overlay.py --no-proxy AAPL MSFT NVDA   # explicit names, skip QUAL test
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, backtest, metrics, scanner, plotting  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "scanner_overlay")
EMA = dict(superfast=9, fast=14, slow=21, use_low_filter=True)
PROXY = "QUAL"  # iShares MSCI USA Quality Factor ETF — a non-hindsight stand-in for the basket


def live_state(df, frame) -> str:
    buy, sell = frame["buysignal"], frame["sellsignal"]
    last, px = df.index[-1], df["close"].iloc[-1]
    if buy.iloc[-1] == 1:
        just = buy.iloc[-2] == 0 if len(buy) > 1 else True
        # find run start
        start = last
        for ts in reversed(buy.index):
            if buy.loc[ts] == 1:
                start = ts
            else:
                break
        chg = px / df["close"].loc[start] - 1
        tag = "BUY-NOW " if just else "HOLD    "
        return f"{tag} green since {start.date()} ({chg:+.1%})"
    if sell.iloc[-1] == 1:
        return "AVOID    red (downtrend) — stay out"
    return "NEUTRAL  no position"


def overlay_and_bh(ticker, start):
    """Return (signal-only long overlay returns, buy&hold returns) for one ticker, or (None, None)."""
    try:
        df = data.get_ohlcv(ticker, start=start)
    except Exception as exc:  # delisted / no data
        print(f"  ! {ticker}: {exc}")
        return None, None, None
    pos = strategies.trend_reversal_long_target(df, profit_target=None, exit_signal="buy_end", **EMA)
    ov = backtest.run_backtest(df, pos, commission_bps=1.0, slippage_bps=5.0)
    bh = backtest.run_backtest(df, strategies.buy_and_hold(df), commission_bps=0.0, slippage_bps=0.0)
    return ov.returns, bh.returns, df


def windowed(ret, months):
    if not months or ret is None:
        return ret
    cutoff = ret.index[-1] - pd.DateOffset(months=months)
    return ret[ret.index >= cutoff]


def summarize(returns: pd.Series) -> dict:
    eq = (1 + returns.fillna(0)).cumprod()
    return {
        "cagr": metrics.cagr(eq),
        "sharpe": metrics.sharpe_ratio(returns),
        "max_dd": metrics.max_drawdown(eq),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tickers", nargs="*", help="explicit tickers (default: scanner top-N)")
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument("--months", type=int, default=None, help="restrict evaluation to last N months")
    ap.add_argument("--no-gate", action="store_true", help="don't require scanner hard gates")
    ap.add_argument("--no-proxy", action="store_true", help="skip the QUAL non-hindsight validation")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    # ---- universe: scanner top-N (or explicit tickers) --------------------------------------------
    if args.tickers:
        names = [t.upper() for t in args.tickers]
        meta = {t: "(manual)" for t in names}
        src = "manual list"
    else:
        cands = scanner.top_candidates(args.top_n, require_gates=not args.no_gate)
        names = [c.ticker for c in cands]
        meta = {c.ticker: f"{c.tier:<13s} score {c.score:4.1f}  {c.sector}" for c in cands}
        src = f"scanner {os.path.basename(scanner.latest_scan())} top-{args.top_n}"

    start = "2005-01-01"
    span = f"last {args.months}m" if args.months else "max history"

    # ---- per-name live signal + return streams ----------------------------------------------------
    print(f"\nTrend Reversal overlay on {src}  |  {span}\n" + "=" * 78)
    print("WHAT TO DO NOW (non-repainting System-A):\n")
    ov_map, bh_map = {}, {}
    for t in names:
        ov, bh, df = overlay_and_bh(t, start)
        if ov is None:
            continue
        ov_map[t] = windowed(ov, args.months)
        bh_map[t] = windowed(bh, args.months)
        frame = strategies.trend_reversal_frame(df, **EMA)
        print(f"  {t:6s} {live_state(df, frame):42s} | {meta.get(t,'')}")

    if not ov_map:
        print("\nNo tradeable names — aborting.")
        return

    # ---- equal-weight all-green portfolio vs equal-weight basket buy & hold ------------------------
    ov_port, ov_eq = backtest.equal_weight_returns(ov_map)
    bh_port, bh_eq = backtest.equal_weight_returns(bh_map)
    spy_bh = backtest.run_backtest(data.get_ohlcv("SPY", start=start),
                                   strategies.buy_and_hold(data.get_ohlcv("SPY", start=start)),
                                   commission_bps=0.0, slippage_bps=0.0)
    spy_ret = windowed(spy_bh.returns, args.months)

    rows = {
        "SPY buy&hold (baseline)": summarize(spy_ret),
        "Basket buy&hold (SELECTION)": summarize(bh_port),
        "Overlay: green-only (SEL+TIMING)": summarize(ov_port),
    }
    tbl = pd.DataFrame(rows).T
    tbl["exposure"] = [float("nan"), 1.0, float((ov_port != 0).mean())]
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    print("\n" + "=" * 78 + "\nPORTFOLIO (equal-weight, 1/N sleeves, long-only) — "
          "selection is hindsight, timing is causal:\n")
    print(tbl.to_string())

    # Timing contribution: does the overlay add return *beyond* just holding the basket?
    ab = metrics.alpha_beta(ov_port, bh_port)
    dd_cut = rows["Overlay: green-only (SEL+TIMING)"]["max_dd"] - rows["Basket buy&hold (SELECTION)"]["max_dd"]
    print(f"\nTIMING contribution (overlay vs same basket B&H): "
          f"ann_alpha {ab['ann_alpha']:+.1%}  t={ab['alpha_tstat']:.2f}  beta {ab['beta']:.2f}")
    print(f"  drawdown: basket {rows['Basket buy&hold (SELECTION)']['max_dd']:.1%} "
          f"-> overlay {rows['Overlay: green-only (SEL+TIMING)']['max_dd']:.1%} "
          f"(cuts {abs(dd_cut):.1%} of drawdown)")

    # ---- QUAL proxy: same overlay on a non-hindsight quality universe ------------------------------
    if not args.no_proxy and not args.tickers:
        ov, bh, _ = overlay_and_bh(PROXY, start)
        if ov is not None:
            q_ov, q_bh = summarize(windowed(ov, args.months)), summarize(windowed(bh, args.months))
            print(f"\nNON-HINDSIGHT CHECK — overlay on {PROXY} (quality ETF, no name selection):")
            print(f"  {PROXY} buy&hold : CAGR {q_bh['cagr']:+.1%}  Sharpe {q_bh['sharpe']:.2f}  "
                  f"maxDD {q_bh['max_dd']:.1%}")
            print(f"  {PROXY} + overlay : CAGR {q_ov['cagr']:+.1%}  Sharpe {q_ov['sharpe']:.2f}  "
                  f"maxDD {q_ov['max_dd']:.1%}")

    # ---- equity plot ------------------------------------------------------------------------------
    plot_path = os.path.join(OUT, "scanner_overlay_equity.png")
    plotting.plot_equity({"overlay green-only": backtest.BacktestResult(
        ov_port, ov_eq, (ov_port != 0).astype(float), pd.DataFrame(), bh_eq)},
        plot_path, title="Scanner top-N: Trend Reversal overlay vs basket buy & hold",
        benchmark=bh_eq)
    print(f"\nEquity curve: {plot_path}")
    print("\nReading it: 'SELECTION' return leans on hindsight (names chosen by today's fundamentals); "
          "the TIMING row and the QUAL check are the honest, causal parts. The overlay's job is "
          "drawdown reduction — judge it on the maxDD cut, not the headline CAGR.")


if __name__ == "__main__":
    main()
