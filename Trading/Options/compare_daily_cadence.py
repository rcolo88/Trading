#!/usr/bin/env python3
"""Model the user's ACTUAL live practice: 1 new spread every trading day (no risk-budget gate),
closest-to-30-DTE selection, fixed contract count per entry (not %-of-equity sizing), exit at
profit_target ~45% OR forced close at 22 DTE. Compares 20d/$5, 20d/$10, 20d/10d-long, 30d/10d-long
under this cadence, on $600k capital, 2018-2026."""
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import numpy as np
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.optimization.walk_forward import split_window
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

WINDOW = ("2018-01-02", "2026-07-09")
FIXED_CONTRACTS = 1


class FixedContractsBullPut(BullPutSpread):
    """Always trades FIXED_CONTRACTS per entry -- no %-of-equity / risk-budget sizing."""
    def calculate_position_size(self, signal, account_value, **kwargs):
        return FIXED_CONTRACTS


def base_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)


def slice_metrics(eq, lo, hi):
    seg = eq[(eq["date"] >= lo) & (eq["date"] < hi)].reset_index(drop=True)
    if len(seg) < 3:
        return {"sharpe": float("nan"), "return_pct": float("nan"), "max_dd_pct": float("nan")}
    rets = seg["total_value"].pct_change().dropna()
    excess = rets - 0.02 / 252.0
    sharpe = float(np.sqrt(252) * excess.mean() / excess.std()) if excess.std() > 0 else float("nan")
    sv, ev = float(seg["total_value"].iloc[0]), float(seg["total_value"].iloc[-1])
    ret = (ev - sv) / sv * 100.0 if sv else float("nan")
    cm = seg["total_value"].cummax()
    dd = float(((seg["total_value"] - cm) / cm).min() * 100.0)
    return {"sharpe": sharpe, "return_pct": ret, "max_dd_pct": dd}


STRUCTURES = [
    ("20d_$5wide",  {"short_delta": 0.20, "strike_width": 5}),
    ("20d_$10wide", {"short_delta": 0.20, "strike_width": 10}),
    ("20d_10dlong", {"short_delta": 0.20, "long_delta": 0.10}),
    ("30d_10dlong", {"short_delta": 0.30, "long_delta": 0.10}),
]


def main():
    cfg = base_config()
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    cfg["backtest"]["initial_capital"] = 150000  # ~2x the largest structure's peak exposure
    cfg["position_sizing"]["max_risk_percent"] = 1_000_000  # never gate entry -- pure daily cadence
    print("Loading 2018-2026 data ...")
    options_data = load_sample_spy_options_data(config=cfg)
    underlying = fetch_spy_data(*WINDOW)
    is_window, oos_window = split_window(*WINDOW, oos_fraction=0.30)
    cut = pd.to_datetime(oos_window[0])
    print(f"IS: {is_window}  OOS: {oos_window}\n")

    rows = []
    for label, wing in STRUCTURES:
        c = copy.deepcopy(cfg)
        strat_cfg = c["strategies"]["bull_put_spread"]
        strat_cfg["entry"]["dte_target"] = 30
        strat_cfg["entry"]["dte_tolerance"] = 5
        strat_cfg["entry"]["vix_min"] = 10
        strat_cfg["entry"]["vix_max"] = 999  # proven inert; daily cadence anyway
        strat_cfg["entry"].pop("strike_width", None)
        strat_cfg["entry"].pop("long_delta", None)
        strat_cfg["entry"]["short_delta"] = wing["short_delta"]
        if "strike_width" in wing:
            strat_cfg["entry"]["strike_width"] = wing["strike_width"]
        else:
            strat_cfg["entry"]["long_delta"] = wing["long_delta"]
        strat_cfg["exit"]["profit_target"] = 0.45
        strat_cfg["exit"]["stop_loss"] = 0.50
        strat_cfg["exit"]["dte_min"] = 22

        bt = OptopsyBacktester(c)
        strategy = FixedContractsBullPut(strat_cfg)
        res = bt.run_backtest(strategy=strategy, options_data=options_data, underlying_data=underlying, verbose=False)

        eq = res["equity_curve"].copy()
        eq["date"] = pd.to_datetime(eq["date"])
        full = slice_metrics(eq, eq["date"].min(), eq["date"].max() + pd.Timedelta(days=1))
        is_m = slice_metrics(eq, eq["date"].min(), cut)
        oos_m = slice_metrics(eq, cut, eq["date"].max() + pd.Timedelta(days=1))
        years = (eq["date"].max() - eq["date"].min()).days / 365.25
        sv, ev = float(eq["total_value"].iloc[0]), float(eq["total_value"].iloc[-1])
        cagr = ((ev / sv) ** (1 / years) - 1) * 100.0 if sv and years > 0 else float("nan")
        max_conc = int(eq["open_positions"].max())
        mean_conc = float(eq["open_positions"].mean())

        trades = res["trades"].copy()
        trades["width"] = (trades["leg1_strike"] - trades["leg2_strike"]).abs()
        trades["credit"] = -trades["entry_price"]
        trades["max_loss_per_contract"] = trades["width"] * 100 - trades["credit"] * 100
        trades["entry_date"] = pd.to_datetime(trades["entry_date"])
        trades["exit_date"] = pd.to_datetime(trades["exit_date"])

        # peak simultaneous dollar exposure: day with max open_positions, sum max_loss across them
        peak_day = eq.loc[eq["open_positions"].idxmax(), "date"]
        open_at_peak = trades[(trades["entry_date"] <= peak_day) & (trades["exit_date"] > peak_day)]
        peak_exposure = open_at_peak["max_loss_per_contract"].sum()  # contracts=1 fixed

        total_pnl = trades["net_pnl"].sum()
        avg_deployed = (trades["max_loss_per_contract"] * mean_conc / max(mean_conc, 1e-9)).mean()  # placeholder unused
        capital_efficient_return = 100 * total_pnl / peak_exposure if peak_exposure else float("nan")

        row = {"structure": label, "max_concurrent": max_conc, "mean_concurrent": mean_conc,
               "cagr_pct": cagr, "full_sharpe": full["sharpe"], "full_return_pct": full["return_pct"],
               "full_max_dd_pct": full["max_dd_pct"], "is_sharpe": is_m["sharpe"], "oos_sharpe": oos_m["sharpe"],
               "trades": len(trades), "avg_width": trades["width"].mean(),
               "avg_max_loss_per_contract": trades["max_loss_per_contract"].mean(),
               "total_pnl": total_pnl, "peak_exposure_dollars": peak_exposure,
               "return_on_peak_exposure_pct": capital_efficient_return}
        rows.append(row)
        eq.to_csv(f"backtest_results/daily_cadence_equity_{label}.csv", index=False)
        trades.to_csv(f"backtest_results/daily_cadence_trades_{label}.csv", index=False)
        print(f"[{label}] trades={len(trades)} max_conc={max_conc} mean_conc={mean_conc:.2f} "
              f"CAGR={cagr:.2f}% Sharpe={full['sharpe']:.3f} IS={is_m['sharpe']:.3f} OOS={oos_m['sharpe']:.3f} "
              f"MaxDD={full['max_dd_pct']:.2f}% avg_width=${trades['width'].mean():.1f} "
              f"total_pnl=${total_pnl:,.0f} peak_exposure=${peak_exposure:,.0f} "
              f"return_on_peak_exposure={capital_efficient_return:.1f}%", flush=True)

    df = pd.DataFrame(rows)
    out = "backtest_results/daily_cadence_comparison.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
