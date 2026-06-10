# Real Data, Daily Collection & Trustworthy Analysis — Runbook

A step-by-step process for: getting **real** SPY option-chain data into the backtester,
**collecting** it automatically every day, and running **overfitting-aware** analysis you can
actually trust.

> **Why this exists.** The synthetic data prices every strike and expiration at one flat IV — no
> volatility skew, no term structure. That made the call-calendar a free lunch: an **8.2 Sharpe**
> with a **58-way tie** at the top and a `stop_loss` that never bound. On **real** data the same
> strategy prints a believable **~2.0 Sharpe** with a real **−19% drawdown**, and the Deflated
> Sharpe Ratio shows the synthetic 8.2 was *below* the no-skill selection benchmark — i.e. pure
> overfit. Real data is the source of truth; synthetic is now only fast plumbing/CI data.

All commands assume you're in the `Options/` directory and using the project venv,
`opt_venv/bin/python`.

---

## 0. TL;DR

```bash
# 1. Use real data (already set): config.yaml -> data_source.mode: real
# 2. (one-time / periodic) pull real history from DoltHub:
opt_venv/bin/python -m src.data_fetchers.real_chain_loader --start 2025-10-01 --end 2026-06-08
opt_venv/bin/python -m src.data_fetchers.validate_chain SPY_real_options_2025-10-01_2026-06-08.csv
# 3. Daily collection runs itself (launchd job, already installed) -> data/raw/chains/
# 4. Roll the collected snapshots into a dataset when you want to backtest them:
opt_venv/bin/python data_collection/compile_chains.py
# 5. Trustworthy optimization (long; see section 6):
caffeinate -i opt_venv/bin/python optimize_call_calendar_spread.py --wf
```

---

## 1. Data modes (synthetic vs. real)

The loader serves one of two datasets, chosen in `config/config.yaml`:

```yaml
data_source:
  mode: "real"          # "synthetic" | "real"
real_data:
  symbol: SPY
  start_date: "2025-10-01"
  end_date:   "2026-06-08"
```

- **`synthetic`** → Black-Scholes model data (flat IV). Fast, deterministic, good for smoke-testing
  the plumbing. **Results are not tradeable.**
- **`real`** → real chains with true skew + term structure. **Use this for any conclusion.** The
  loader reads `data/processed/SPY_real_options_<start>_<end>.csv` named from the `real_data` block.

---

## 2. Get real historical data (DoltHub)

`real_chain_loader.py` pulls real SPY chains from the public DoltHub database
`post-no-preference/options` (SQL-over-HTTP, no account), merges the SPY close + VIX from yfinance,
and writes the canonical CSV.

```bash
# Pull a date range (each trading day ~200 contracts; ~1-2 s/day):
opt_venv/bin/python -m src.data_fetchers.real_chain_loader --start 2024-01-01 --end 2026-06-08

# Gate it before trusting it (asserts real skew + term structure; synthetic fails both):
opt_venv/bin/python -m src.data_fetchers.validate_chain SPY_real_options_2024-01-01_2026-06-08.csv
```

After pulling, point the config at the new file by editing `real_data.start_date/end_date`.

> **Known limitation.** DoltHub quotes only ~35 strikes/day at irregular spacing, and a given strike
> persists only a few days. A calendar's exact strike often isn't quoted on a later day, so the
> strategy **re-marks held legs at the nearest quoted strike** within `strike_snap_pct` (default
> `0.01` ≈ $7 on SPY; see `config.yaml` → `call_calendar.exit`). DoltHub is excellent for
> skew/term/IV studies and quick verticals; for faithful **multi-day calendars**, prefer the
> **daily-logged full chains** (sections 3–5), which carry the complete strike grid.

---

## 3. Collect real data automatically (the scheduler)

`data_collection/chain_logger.py` writes the **full** current SPY chain (~4,500 contracts incl.
VIX) to `data/raw/chains/SPY_chain_YYYY-MM-DD_HHMM.csv`. A macOS **launchd** job runs it **twice
every weekday — 10:00 and 15:00 local** — so you accumulate a real, point-in-time history.

**It is already installed and loaded.** Lifecycle:

| Goal | Command |
|---|---|
| Check it's registered | `launchctl list \| grep spychainlogger` |
| Detailed status | `launchctl print gui/$(id -u)/com.robert.spychainlogger \| grep -iE "state\|last exit"` |
| Run once now (test) | `launchctl kickstart -k gui/$(id -u)/com.robert.spychainlogger` |
| Watch output / errors | `tail -f data_collection/logger.log` (errors → `logger.err`) |
| **Pause / stop** | `launchctl bootout gui/$(id -u)/com.robert.spychainlogger` |
| **Resume** | `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.robert.spychainlogger.plist` |
| **Remove for good** | bootout (above), then `rm ~/Library/LaunchAgents/com.robert.spychainlogger.plist` |

**Install from scratch** (only needed on a new machine — it's already done here):
```bash
cp data_collection/com.robert.spychainlogger.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.robert.spychainlogger.plist
```
The agent lives in `~/Library/LaunchAgents/`, so it **auto-loads at every login** and keeps running
long-term with no further action.

- Free **yfinance** source needs no account. For real Greeks via **Schwab**, add the env vars to the
  plist (`SCHWAB_APP_KEY` / `SCHWAB_APP_SECRET` / `SCHWAB_TOKEN_PATH`) — see
  `data_collection/README.md`. (Schwab refresh tokens expire ~weekly, so re-auth is manual.)

---

## 4. Make the Mac awake at capture time (scheduling a wake)

**The problem.** launchd only fires on time if the Mac is **awake** at 10:00 / 15:00. If it's
asleep, launchd "catches up" the run on the next wake — you still get a snapshot, but stamped at
wake time, not the target minute. To hit the actual times, schedule a wake a minute *before* each
run with `pmset` (requires `sudo`).

```bash
# Wake every weekday at 09:59 so the 10:00 capture fires on time:
sudo pmset repeat wake MTWRF 09:59:00

# Inspect scheduled power events:
pmset -g sched

# Cancel the repeating wake:
sudo pmset repeat cancel
```

Day codes: `M T W R F S U` (R = Thursday, U = Sunday). **The wake must be a minute or two BEFORE the
launchd Hour/Minute** so the system is fully up when the job runs.

### The one-repeating-wake limitation (the "different window" gotcha)

`pmset repeat` allows **only one repeating wake event**. You **cannot** set both 09:59 *and* 14:59
as repeating wakes. So the second daily capture (15:00) needs one of these:

1. **You're using the Mac at 15:00** → it's already awake, nothing to do. (Common case.)
2. **Keep it awake from the morning wake through the close** → set Energy/Battery to never sleep on
   power during the day, or after the 09:59 wake run `caffeinate -t 21600` (stay awake 6 h).
3. **One-off wake for a specific date** (not repeating), e.g. the afternoon:
   ```bash
   sudo pmset schedule wake "06/10/2026 14:59:00"
   ```
4. **Simplest if your laptop sleeps a lot — collect once near the close.** Edit the plist down to a
   single daily run (e.g. 15:45) and set one matching wake:
   ```bash
   sudo pmset repeat wake MTWRF 15:44:00
   ```
   An end-of-day snapshot is the most useful input for backtests anyway.

### Other caveats

- **Stay logged in.** A scheduled wake powers the machine on, but a *per-user* LaunchAgent only runs
  inside your logged-in GUI session. A **locked screen is fine**; being **fully logged out** (or
  switched to another user via Fast User Switching) means the job won't fire.
- **Power.** Scheduled wake generally works on battery, but keep the Mac on AC to be safe, and
  confirm in **System Settings → Battery/Energy** that scheduled/network wake is allowed.
- **Admin.** `pmset` scheduling needs `sudo`.

### Changing the times / timezone (different window)

The plist `Hour` values are **local time**; the US market is 09:30–16:00 **ET**.

- **Not on Eastern?** Convert. Pacific example: 10:00/15:00 ET → **07:00/12:00 PT**. Update *both*
  the plist `Hour`s and the `pmset` wake time.
- **Want to capture nearer the open/close?** Change the plist `Hour`/`Minute` (e.g. `09:35` just
  after the open, `15:55` near the close) and move the wake to ~1 minute before.
- After editing the plist, reload it:
  ```bash
  launchctl bootout gui/$(id -u)/com.robert.spychainlogger
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.robert.spychainlogger.plist
  ```

---

## 5. Turn collected snapshots into a backtestable dataset

```bash
opt_venv/bin/python data_collection/compile_chains.py
```

This rolls every `data/raw/chains/SPY_chain_*.csv` into one
`data/processed/SPY_real_options_<min>_<max>.csv` (keeps the latest intraday snapshot per day,
backfills VIX where missing). It prints the date range — set `real_data.start_date/end_date` to that
range and you can backtest the logged data exactly like the DoltHub data. Because the log captures
the **full strike grid** (~4,500 contracts/day vs DoltHub's ~200), it persists day-to-day and is the
better dataset for multi-day calendars as it accumulates.

---

## 6. What's left for you — the long runs (descriptive)

These are the deliberately-not-automated, time-consuming steps. Run them yourself when ready.

### 6a. Trustworthy optimization with an out-of-sample check

```bash
caffeinate -i opt_venv/bin/python optimize_call_calendar_spread.py --wf
```

- **What it does.** `--wf` (walk-forward) splits the backtest window into an **in-sample (IS)** part
  (the first ~70%) and a **held-out out-of-sample (OOS)** part (the last ~30%). It optimizes the
  parameters on IS only, then scores that *single* winning parameter set on the OOS window the
  search never saw. A real edge keeps most of its Sharpe out-of-sample; an overfit one collapses.
  Add `--oos-frac=0.25` to change the split.
- **Runtime.** This is the slow one — up to ~1,000 Optuna trials. Budget **a few hours** on the full
  window. `caffeinate -i` keeps the Mac awake for the duration. To do a fast first pass, lower
  `N_TRIALS` in `optimize_call_calendar_spread.py` (`run_optimization`) from `1000` to ~`150`.
- **How to read the output** (printed at the end, and saved to `optimization_results/`):
  - **IS vs OOS Sharpe** — the headline honesty check. Healthy ≈ OOS > 1.0 *and* OOS > 0.5 × IS. A
    large drop means the IS optimum is fit to noise.
  - **Deflated Sharpe Ratio (DSR)** — the probability the best Sharpe beats what pure selection over
    N trials would produce by luck. **Want DSR > 0.95.** Below that, the number is likely a search
    artifact (this is exactly what flagged the synthetic 8.2).
  - **`stability_score`** column — each row's metric averaged over its grid neighbors. The top row's
    stability should be close to its own Sharpe (a robust *plateau*, not a lone spike).
  - **"Best parameters" == top row of "TOP 5"** — guaranteed now by a stable tie-break (the old
    discrepancy is fixed).

### 6b. Pull more history (more data = more robust)

```bash
opt_venv/bin/python -m src.data_fetchers.real_chain_loader --start 2024-01-01 --end 2026-06-08
opt_venv/bin/python -m src.data_fetchers.validate_chain SPY_real_options_2024-01-01_2026-06-08.csv
```

~10–15 minutes for ~600 trading days. Then update `real_data.start_date` to `2024-01-01` so the
optimizer and walk-forward run over the longer history. More days → a more trustworthy IS/OOS split
and a less inflated selection benchmark.

### 6c. Regenerate the (now non-degenerate) synthetic data — optional

```bash
opt_venv/bin/python generate_synthetic_data.py
```

Only if you want `mode: synthetic` to use the upgraded generator (real skew + term structure) for
fast plumbing runs. Not needed for real-data analysis.

### 6d. Position-sizing realism — a caveat before you "tame" returns

The eye-popping backtest returns come from `position_sizing.max_risk_percent: 50` compounding. **Do
not simply lower it** — dropping it to 10% makes the calendar take **zero trades**, because
`call_calendar.entry.max_debit: 28` lets one spread cost up to $2,800, more than a 10%-of-$10k
($1,000) budget allows. Tune them **together** (e.g. `max_debit: ~10` *and* `max_risk_percent: ~15`)
or switch `position_sizing.method: kelly`, then re-run and judge by **Sharpe, drawdown, and OOS** —
not the headline return.

---

## 7. Live monitoring & paper trading

```bash
opt_venv/bin/python live_monitor.py                 # pull a fresh chain
opt_venv/bin/python live_monitor.py --from-logged   # use the latest logged snapshot instead
```

List your open trades in `data/open_positions.json` (a template is written on first run). The
monitor marks each position with the **same fill model and exit rules as the backtester**, so a
🚨 EXIT alert here means the backtest would have exited too — directly addressing the "I wasn't
alerted in time to close a multi-leg stop" problem. Every check is appended to `data/paper_trades.csv`
so you can later compare modeled fills to real ones.

---

## 8. File reference

| Path | Purpose |
|---|---|
| `src/data_fetchers/real_chain_loader.py` | Pull real SPY chains from DoltHub → canonical CSV |
| `src/data_fetchers/validate_chain.py` | Assert real skew + term structure before trusting a dataset |
| `src/data_fetchers/synthetic_generator.py` | Synthetic data (now with an IV surface) + the loader |
| `data_collection/chain_logger.py` | Log the live full SPY chain (yfinance/Schwab) + VIX |
| `data_collection/com.robert.spychainlogger.plist` | launchd schedule (10:00 & 15:00 weekdays) |
| `data_collection/compile_chains.py` | Roll logged snapshots → one backtestable dataset |
| `src/analysis/overfitting.py` | Deflated Sharpe / selection-benchmark math |
| `src/optimization/walk_forward.py` | In-sample/out-of-sample evaluation |
| `src/optimization/parameter_optimizer.py` | Optimizer + stable tie-break + stability scores |
| `live_monitor.py` | Mark open positions live and fire the backtest's exit rules |
| `config/config.yaml` | `data_source.mode`, `real_data`, costs, strategy params, sizing |
