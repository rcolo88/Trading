"""S&P 500 'bubble' candidates + Trend Reversal overlay (Idea #2, the honest, salvageable version).

The thesis: price-insensitive flows (passive funds, 401k auto-contributions) mechanically buy index
members, so a stock *about to be added* to the S&P 500 has a structural demand tailwind, and one
*about to be dropped* has forced selling. We use that as a **universe filter**, not an event trade —
because the classic 'buy on announcement' pop has largely been arbitraged away (Greenwood & Sammon,
*The Disappearing Index Effect*, J. Finance 2025: the S&P 500 addition abnormal return fell from
~7.3% in the 1990s to a statistically-insignificant ~0.8% in the 2010s).

What still has legs is *candidacy* + *quality* + *trend timing*:

  * ADD candidates — large names NOT yet in the S&P 500 that clear S&P's own inclusion bar
    (≈ market-cap threshold, positive GAAP earnings, quality gates). S&P's profitability rule is
    itself a quality gate, so these are quality large-caps with a forced-buying tailwind ahead.
  * DROP watch — names already in the index that have shrunk well below the threshold or failed the
    quality gates. We treat these as **avoid / exit**, never as shorts (the deletion effect is also
    dead, and shorting fights the low-drawdown goal).

Then the same non-repainting Trend Reversal overlay times entries/exits on the ADD candidates.

    python scripts/10_index_candidates.py                     # default cap band, full history
    python scripts/10_index_candidates.py --min-cap 18 --max-n 12 --months 36
"""
import argparse
import io
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, backtest, metrics, scanner  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "index_candidates")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
EMA = dict(superfast=9, fast=14, slow=21, use_low_filter=True)
WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def sp500_members(refresh: bool = False) -> set[str]:
    """Current S&P 500 tickers (cached to data/sp500_members.csv; Wikipedia needs a UA header)."""
    cache = os.path.join(DATA, "sp500_members.csv")
    if os.path.exists(cache) and not refresh:
        return set(pd.read_csv(cache)["symbol"].astype(str))
    try:
        req = urllib.request.Request(WIKI, headers={"User-Agent": "Mozilla/5.0 (research script)"})
        html = urllib.request.urlopen(req, timeout=20).read().decode()
        df = pd.read_html(io.StringIO(html))[0]
        syms = df["Symbol"].astype(str).str.replace(".", "-", regex=False).str.strip().tolist()
        os.makedirs(DATA, exist_ok=True)
        pd.DataFrame({"symbol": syms}).to_csv(cache, index=False)
        return set(syms)
    except Exception as exc:
        if os.path.exists(cache):
            print(f"  ! membership fetch failed ({exc}); using cached list")
            return set(pd.read_csv(cache)["symbol"].astype(str))
        raise RuntimeError(f"Could not fetch S&P 500 membership and no cache exists: {exc}") from exc


def summarize(returns: pd.Series) -> dict:
    eq = (1 + returns.fillna(0)).cumprod()
    return {"cagr": metrics.cagr(eq), "sharpe": metrics.sharpe_ratio(returns),
            "max_dd": metrics.max_drawdown(eq)}


def overlay_and_bh(ticker, start):
    try:
        df = data.get_ohlcv(ticker, start=start)
    except Exception as exc:
        print(f"  ! {ticker}: {exc}")
        return None, None
    pos = strategies.trend_reversal_long_target(df, profit_target=None, exit_signal="buy_end", **EMA)
    ov = backtest.run_backtest(df, pos, commission_bps=1.0, slippage_bps=5.0)
    bh = backtest.run_backtest(df, strategies.buy_and_hold(df), commission_bps=0.0, slippage_bps=0.0)
    return ov.returns, bh.returns


def live_state(df, frame) -> str:
    buy, sell = frame["buysignal"], frame["sellsignal"]
    if buy.iloc[-1] == 1:
        just = len(buy) > 1 and buy.iloc[-2] == 0
        return "BUY-NOW (green just turned on)" if just else "HOLD (green)"
    if sell.iloc[-1] == 1:
        return "AVOID (red downtrend)"
    return "NEUTRAL (no position)"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-cap", type=float, default=15.0,
                    help="min market cap ($B) for an ADD candidate (default 15)")
    ap.add_argument("--max-cap", type=float, default=60.0,
                    help="max market cap ($B) — above this it's likely already in or a mega-cap (default 60)")
    ap.add_argument("--drop-cap", type=float, default=9.0,
                    help="S&P members below this cap ($B) go on the DROP watch (default 9)")
    ap.add_argument("--max-n", type=int, default=12, help="how many ADD candidates to trade")
    ap.add_argument("--months", type=int, default=None)
    ap.add_argument("--no-gate", action="store_true")
    ap.add_argument("--refresh-members", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    members = sp500_members(refresh=args.refresh_members)
    cands = scanner.load_candidates()
    if not args.no_gate:
        cands = [c for c in cands if c.gates_passed]

    # ---- ADD candidates: quality names just below the index, with a forced-buying tailwind ahead --
    add = [c for c in cands
           if c.ticker not in members
           and args.min_cap * 1e9 <= c.market_cap <= args.max_cap * 1e9
           and (c.earnings_yield or 0) > 0]            # S&P requires positive GAAP earnings
    add.sort(key=lambda c: c.market_cap, reverse=True)  # closest to the threshold first
    add = add[:args.max_n]

    # ---- DROP watch: current members that have shrunk or lost quality (avoid / exit, never short) --
    by_ticker = {c.ticker: c for c in scanner.load_candidates()}
    drop = [c for c in by_ticker.values()
            if c.ticker in members
            and (c.market_cap < args.drop_cap * 1e9 or not c.gates_passed)]
    drop.sort(key=lambda c: c.market_cap)

    span = f"last {args.months}m" if args.months else "max history"
    print(f"\nS&P 500 inclusion-candidate overlay  |  {len(members)} current members  |  {span}")
    print("=" * 80)
    print(f"ADD candidates (NOT in S&P 500, cap ${args.min_cap:.0f}-{args.max_cap:.0f}B, "
          f"positive earnings, gates pass) — ranked by cap:\n")
    if not add:
        print("  (none in band — widen --min-cap/--max-cap)\n")

    start = "2005-01-01"
    ov_map, bh_map = {}, {}
    for c in add:
        ov, bh = overlay_and_bh(c.ticker, start)
        if ov is None:
            continue
        if args.months:
            cut = ov.index[-1] - pd.DateOffset(months=args.months)
            ov, bh = ov[ov.index >= cut], bh[bh.index >= cut]
        ov_map[c.ticker], bh_map[c.ticker] = ov, bh
        df = data.get_ohlcv(c.ticker, start=start)
        frame = strategies.trend_reversal_frame(df, **EMA)
        fscore = c.f_score if c.f_score is not None else "-"
        print(f"  {c.ticker:6s} ${c.market_cap/1e9:5.1f}B  score {c.score:4.1f}  F{fscore:<2}  "
              f"{c.sector:22s} | {live_state(df, frame)}")

    if ov_map:
        ov_port, ov_eq = backtest.equal_weight_returns(ov_map)
        bh_port, bh_eq = backtest.equal_weight_returns(bh_map)
        rows = {"Candidate basket buy&hold": summarize(bh_port),
                "Candidate basket + overlay": summarize(ov_port)}
        tbl = pd.DataFrame(rows).T
        pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
        print("\nEqual-weight candidate basket (long-only, 1/N sleeves):\n")
        print(tbl.to_string())
        ab = metrics.alpha_beta(ov_port, bh_port)
        print(f"\nTiming contribution: ann_alpha {ab['ann_alpha']:+.1%}  t={ab['alpha_tstat']:.2f}  "
              f"| drawdown {rows['Candidate basket buy&hold']['max_dd']:.1%} -> "
              f"{rows['Candidate basket + overlay']['max_dd']:.1%}")

    print(f"\nDROP watch — current members under ${args.drop_cap:.0f}B or failing gates "
          f"(avoid / don't hold; exit on red):\n")
    for c in drop[:15]:
        why = "below cap" if c.market_cap < args.drop_cap * 1e9 else "failed gates"
        print(f"  {c.ticker:6s} ${c.market_cap/1e9:5.1f}B  {why:12s}  {c.sector}")
    if len(drop) > 15:
        print(f"  ... and {len(drop)-15} more")

    print("\nHonesty: the *announcement pop* is largely gone (Greenwood-Sammon 2025); the durable part "
          "is holding quality, flow-supported large-caps and timing them for low drawdown. Backtest "
          "uses TODAY's membership/caps, so candidate identity is forward-looking — treat the basket "
          "result as the timing-overlay behaviour, not a tradeable historical edge.")


if __name__ == "__main__":
    main()
