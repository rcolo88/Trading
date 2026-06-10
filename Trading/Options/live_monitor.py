#!/usr/bin/env python3
"""Monitor open calendar positions against today's real chain and fire the backtest's exit rules.

This is the live counterpart to the backtester. It loads your open positions, pulls the current SPY
chain (yfinance, or the latest logged snapshot), marks each spread with the *same* fill model
(`execution.net_close`), and runs the *same* `CallCalendarSpread.generate_exit_signal` the backtest
uses — so an alert here means the backtest would have exited too. It directly addresses the original
problem behind `stop_slippage_percent`: "I'm not alerted in time when a multi-leg stop is breached."

Positions live in `data/open_positions.json` (a template is written on first run):
    [{"strategy":"call_calendar","option_type":"call","strike":740,
      "near_expiration":"2026-06-18","far_expiration":"2026-07-17",
      "entry_debit":3.20,"contracts":2,"entry_date":"2026-06-09"}]

Every check is appended to `data/paper_trades.csv`.

    opt_venv/bin/python live_monitor.py                 # pull a fresh chain
    opt_venv/bin/python live_monitor.py --from-logged   # use the latest logged snapshot instead
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from src.strategies.calendar_spreads import CallCalendarSpread  # noqa: E402
from src.strategies.base_strategy import Position  # noqa: E402

POSITIONS_FILE = _ROOT / "data" / "open_positions.json"
PAPER_LOG = _ROOT / "data" / "paper_trades.csv"
RAW_CHAINS = _ROOT / "data" / "raw" / "chains"

_TEMPLATE = [{
    "strategy": "call_calendar", "option_type": "call", "strike": 740,
    "near_expiration": "2026-06-18", "far_expiration": "2026-07-17",
    "entry_debit": 3.20, "contracts": 2, "entry_date": "2026-06-09",
}]


def _load_config() -> dict:
    with open(_ROOT / "config" / "config.yaml") as f:
        return yaml.safe_load(f)


def _current_chain(from_logged: bool) -> tuple[pd.DataFrame, float]:
    """Return (chain_df, underlying_price). Prefer a fresh yfinance pull; fall back to logged."""
    if not from_logged:
        try:
            from data_collection.chain_logger import from_yfinance
            df = from_yfinance(max_dte=90)
            if not df.empty:
                df["expiration"] = pd.to_datetime(df["expiration"]).dt.normalize()
                return df, float(df["underlying_price"].iloc[0])
        except Exception as exc:
            print(f"  (live pull failed: {exc}; falling back to latest logged snapshot)")

    files = sorted(RAW_CHAINS.glob("SPY_chain_*.csv"))
    if not files:
        raise FileNotFoundError("No live chain and no logged snapshots in data/raw/chains/.")
    df = pd.read_csv(files[-1])
    df["expiration"] = pd.to_datetime(df["expiration"]).dt.normalize()
    print(f"  using logged snapshot: {files[-1].name}")
    return df, float(df["underlying_price"].iloc[0])


def _evaluate(position_spec: dict, chain: pd.DataFrame, underlying_price: float,
              strategy: CallCalendarSpread, costs: dict) -> dict:
    """Mark one position and run the backtest exit rules; return a status row."""
    ot = position_spec["option_type"]
    strike = float(position_spec["strike"])
    near_exp = pd.Timestamp(position_spec["near_expiration"]).normalize()
    far_exp = pd.Timestamp(position_spec["far_expiration"]).normalize()
    entry_debit = float(position_spec["entry_debit"])

    # Same leg-dict shape the backtester builds (legs[0]=short near, legs[1]=long far).
    legs = [
        {"strike": strike, "option_type": ot, "position": "short", "expiration": near_exp},
        {"strike": strike, "option_type": ot, "position": "long", "expiration": far_exp},
    ]
    position = Position(
        strategy_name=strategy.name,
        entry_date=pd.Timestamp(position_spec.get("entry_date", datetime.now())),
        entry_price=entry_debit,
        contracts=int(position_spec.get("contracts", 1)),
        legs=legs,
    )
    position.near_expiration = near_exp
    position.far_expiration = far_exp

    signal = strategy.generate_exit_signal(
        date=pd.Timestamp.now().normalize(),
        position=position,
        options_data=chain,
        underlying_price=underlying_price,
        limit_fraction=costs.get("limit_fill_fraction", 0.5),
        market_fraction=costs.get("market_fill_fraction", 1.0),
        extra_slippage=costs.get("extra_slippage_percent", 0.0),
        stop_slippage=costs.get("stop_slippage_percent", 0.0),
    )
    mark = position.current_price
    profit_pct = (mark - entry_debit) / entry_debit if mark is not None and entry_debit else float("nan")
    return {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": position_spec["strategy"], "option_type": ot, "strike": strike,
        "near_expiration": near_exp.date(), "far_expiration": far_exp.date(),
        "entry_debit": entry_debit, "contracts": position.contracts,
        "mark": None if mark is None else round(float(mark), 4),
        "profit_pct": None if pd.isna(profit_pct) else round(float(profit_pct), 4),
        "exit_signal": signal is not None,
        "exit_reason": signal.exit_reason if signal is not None else "",
    }


def main() -> int:
    if not POSITIONS_FILE.exists():
        POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        POSITIONS_FILE.write_text(json.dumps(_TEMPLATE, indent=2))
        print(f"Wrote a positions template to {POSITIONS_FILE} — edit it with your open trades, rerun.")
        return 0

    positions = json.loads(POSITIONS_FILE.read_text())
    if not positions:
        print("No open positions listed in data/open_positions.json.")
        return 0

    config = _load_config()
    costs = config.get("costs", {})
    strategy = CallCalendarSpread(config["strategies"]["call_calendar"])
    chain, underlying_price = _current_chain("--from-logged" in sys.argv)

    print(f"\n{'='*78}\nLIVE MONITOR  {datetime.now():%Y-%m-%d %H:%M}  | SPY ~ ${underlying_price:.2f}\n{'='*78}")
    rows = []
    for spec in positions:
        r = _evaluate(spec, chain, underlying_price, strategy, costs)
        rows.append(r)
        flag = "🚨 EXIT" if r["exit_signal"] else "  hold"
        mark = "n/a" if r["mark"] is None else f"${r['mark']:.2f}"
        pp = "n/a" if r["profit_pct"] is None else f"{r['profit_pct']:+.1%}"
        print(f"{flag}  {r['option_type']} {r['strike']:.0f} "
              f"{r['near_expiration']}/{r['far_expiration']}  mark {mark} (entry ${r['entry_debit']:.2f}, {pp})"
              + (f"  -> {r['exit_reason']}" if r["exit_signal"] else ""))
    print("=" * 78)

    # Append every check to the paper-trade log (record + later compare to real fills).
    log_df = pd.DataFrame(rows)
    PAPER_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_df.to_csv(PAPER_LOG, mode="a", header=not PAPER_LOG.exists(), index=False)
    print(f"Logged {len(rows)} check(s) -> {PAPER_LOG.relative_to(_ROOT)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
