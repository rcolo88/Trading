"""Run the Fundamental Scanner fresh, then paint a Trend Reversal chart for each of its top-20 names.

End to end, in one command:
  1. re-runs the sibling Fundamental Scanner so the top-20 is *fresh* (``--score-only`` by default:
     instant re-score of cached fundamentals; pass ``--fetch`` for a full, slow data refresh),
  2. reads the freshly-written top-20 shortlist,
  3. downloads fresh prices, resamples to **3-day bars** (the tuning study's low-noise sweet spot),
     and writes **ONE tall, scrollable PNG** that stacks a painted candle panel per ticker — the last
     14 three-day bars with full candles, a date under every bar, candles coloured by the
     non-repainting Trend Reversal state (green=buy, red=sell, grey=neutral), the EMA 9/14/21 ribbon,
     and BUY ▲ / SELL ▼ arrows — so you can read exactly where each buy/sell paint lands.

It also prints a one-line live status per name (BUY-NOW / HOLD-green / AVOID-red / neutral) and a
final list of which top-20 names are flashing a buy right now.

    python scripts/13_scanner_charts.py                 # fresh re-score + one combined chart, top 20
    python scripts/13_scanner_charts.py --top-n 25 --lookback 45
    python scripts/13_scanner_charts.py --fetch          # full fundamental refetch first (slow)
    python scripts/13_scanner_charts.py --no-scan        # skip re-running the scanner, use latest file
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, plotting, scanner  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
COMBINED = os.path.join(OUT, "scanner_top20_painted.png")
OLD_DIR = os.path.join(OUT, "scanner_charts")
EMA = dict(superfast=9, fast=14, slow=21, use_low_filter=True)
TIMEFRAME = "3D"  # 3-day bars — the tuning study's lowest-noise / best-Sharpe sweet spot


def _scan_date(path: str) -> str:
    """Extract the YYYY-MM-DD date stamped in an opportunities_YYYYMMDD.json filename."""
    digits = "".join(ch for ch in os.path.basename(path) if ch.isdigit())[:8]
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}" if len(digits) == 8 else "unknown"


def run_scanner_fresh(top_n: int, full_fetch: bool) -> None:
    """Invoke the sibling Fundamental Scanner so it writes a fresh dated opportunities file."""
    scanner_dir = scanner.DEFAULT_SCANNER_DIR
    script = os.path.join(scanner_dir, "main_quality_analysis.py")
    if not os.path.exists(script):
        print(f"  ! scanner not found at {script}; using the latest existing output instead.")
        return
    cmd = [sys.executable, "main_quality_analysis.py", "--top-n", str(top_n)]
    # Default: re-score cached fundamentals (instant). --fetch: full fetch + score (the bare command).
    if not full_fetch:
        cmd += ["--score-only"]
    mode = "full fetch + score (slow)" if full_fetch else "score-only (fast)"
    print(f"  running Fundamental Scanner [{mode}] in {scanner_dir} ...\n")
    try:
        subprocess.run(cmd, cwd=scanner_dir, check=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"\n  ! scanner run failed ({exc}); falling back to the latest existing output.")


def live_state(df: pd.DataFrame, frame: pd.DataFrame) -> tuple[str, bool]:
    buy, sell = frame["buysignal"], frame["sellsignal"]
    last, px = df.index[-1], df["close"].iloc[-1]
    is_buy = buy.iloc[-1] == 1
    if is_buy:
        start = last
        for ts in reversed(buy.index):
            if buy.loc[ts] == 1:
                start = ts
            else:
                break
        chg = px / df["close"].loc[start] - 1
        just = len(buy) > 1 and buy.iloc[-2] == 0
        tag = "BUY-NOW " if just else "HOLD    "
        return f"{tag} green since {start.date()} ({chg:+.1%}) | {px:.2f} as of {last.date()}", True
    if sell.iloc[-1] == 1:
        return f"AVOID    red downtrend | {px:.2f} as of {last.date()}", False
    return f"NEUTRAL  no position | {px:.2f} as of {last.date()}", False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--lookback", type=int, default=14,
                    help="number of 3-day bars drawn per ticker panel (default 14)")
    ap.add_argument("--fetch", action="store_true",
                    help="full fundamental refetch before scoring (slow); default is a fast re-score")
    ap.add_argument("--no-scan", action="store_true",
                    help="don't re-run the scanner; chart the latest existing top-N")
    ap.add_argument("--no-gate", action="store_true",
                    help="don't require the scanner's hard quality gates")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    # Clean up the old one-PNG-per-ticker folder from earlier versions.
    if os.path.isdir(OLD_DIR):
        for f in os.listdir(OLD_DIR):
            os.remove(os.path.join(OLD_DIR, f))
        os.rmdir(OLD_DIR)
        print(f"  cleaned up old per-ticker charts in {OLD_DIR}/")

    print(f"\nFresh Fundamental Scanner -> Trend Reversal charts (top {args.top_n})")
    if args.no_scan:
        print("  --no-scan: using the latest existing scanner output.")
    else:
        run_scanner_fresh(args.top_n, args.fetch)

    path = scanner.latest_scan()
    scan_date = _scan_date(path)
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    if scan_date == today:
        print(f"  scan is current (dated {scan_date}).")
    else:
        print(f"\n  ! Latest scan is dated {scan_date}, not today ({today}) — the scanner's "
              f"fundamental\n    cache is empty/expired (entries expire after 7 days), so it could "
              f"not re-score.\n    Charting the latest available top-{args.top_n}; run --fetch for a "
              f"genuinely fresh pass.")
    top = scanner.top_candidates(args.top_n, require_gates=not args.no_gate, path=path)
    print(f"\nTop {len(top)} from {os.path.basename(path)}:\n")

    # Pull enough daily history to warm the EMAs on 3-day bars, then draw only the last `lookback`.
    start = (pd.Timestamp.today() - pd.DateOffset(days=args.lookback * 3 + 320)).strftime("%Y-%m-%d")
    buys, panels = [], []
    # SPY market-context panel, always pinned to the very top — same TR indicator / 3-day bars.
    try:
        spy_df = data.resample_ohlcv(data.get_ohlcv("SPY", start=start, refresh=True), TIMEFRAME)
        spy_frame = strategies.trend_reversal_frame(spy_df, **EMA)
        spy_state, _ = live_state(spy_df, spy_frame)
        flag = "● BUY" if spy_frame["buysignal"].iloc[-1] == 1 else "  ·"
        panels.append({"df": spy_df, "frame": spy_frame, "title": f"SPY  {flag}  | market context"})
        print(f"  {'SPY':6s} {spy_state}   [market context]")
    except Exception as exc:
        print(f"  SPY    ! price download failed: {exc}")

    # Charts (and the status list) alphabetical by ticker; the footer table keeps the scanner's rank order.
    for c in sorted(top, key=lambda c: c.ticker):
        try:
            df_daily = data.get_ohlcv(c.ticker, start=start, refresh=True)
        except Exception as exc:
            print(f"  {c.ticker:6s} ! price download failed: {exc}")
            continue
        df = data.resample_ohlcv(df_daily, TIMEFRAME)   # -> 3-day bars
        frame = strategies.trend_reversal_frame(df, **EMA)
        state, is_buy = live_state(df, frame)
        if is_buy:
            buys.append(c.ticker)
        flag = "● BUY" if is_buy else "  ·"
        panels.append({"df": df, "frame": frame,
                       "title": f"{c.ticker}  {flag}  | {c.tier} (score {c.score:.1f})"})
        print(f"  {c.ticker:6s} {state}   [{c.tier}]")

    # The scanner's own top-N shortlist, embedded verbatim beneath the charts.
    top_txt_path = path.replace(".json", "_top.txt")
    footer = ""
    if os.path.exists(top_txt_path):
        with open(top_txt_path) as fh:
            footer = fh.read().rstrip("\n")

    if panels:
        plotting.plot_multi_painted(
            panels, COMBINED, lookback=args.lookback, footer_text=footer,
            title=f"SPY + Fundamental Scanner top {len(panels) - 1} — Trend Reversal on 3-day bars, "
                  f"last {args.lookback} bars ({_scan_date(path)})")
    print(f"\nOne scrollable chart written: {COMBINED}")
    print("  (green ▲ = BUY, red ▼ = SELL, candle colour = signal state; scroll top-to-bottom.)")
    print(f"\nBUY painted right now ({len(buys)}/{len(panels)}): "
          f"{', '.join(buys) if buys else '(none — no top-20 name is green today)'}")


if __name__ == "__main__":
    main()
