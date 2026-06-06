# Real SPY option-chain logger

`chain_logger.py` writes the current SPY chain to `data/raw/chains/SPY_chain_YYYY-MM-DD_HHMM.csv` in the
same schema the backtester already reads. The bundled launchd job runs it **twice every weekday — 10:00
and 15:00** — so each day captures a morning and an afternoon snapshot (the `_HHMM` stamp keeps both).
In a few weeks you have a **real point-in-time history** — the honest replacement for the synthetic
Black-Scholes data.

## Sources

| Source | Account | Greeks/IV | Quality |
|---|---|---|---|
| **Schwab** (schwab-py) | your Schwab login | real, from Schwab | best |
| **yfinance** (default) | none | greeks filled from IV via our Black-Scholes | decent EOD |

> Reminder (verified June 2026): the **Schwab API has no *historical* option data** — only the *current*
> chain. That's exactly why we log it ourselves daily. To get *past* chains without waiting, also grab a
> free bulk set: **DoltHub** (post-no-preference/options, 2019–mid-2024), **OptionsDX**, **OptionData.org**.

### One-time Schwab setup (optional, for real greeks)
1. Create an app at developer.schwab.com → get an **App Key** and **Secret** (approval takes ~1–3 days).
2. `opt_venv/bin/pip install schwab-py`
3. First-run OAuth (opens a browser, writes a token file):
   ```python
   from schwab.auth import client_from_login_flow
   client_from_login_flow(api_key=..., app_secret=..., callback_url="https://127.0.0.1:8182",
                          token_path="data_collection/schwab_token.json")
   ```
4. Export the env vars before running the logger (or put them in the launchd plist):
   ```bash
   export SCHWAB_APP_KEY=... SCHWAB_APP_SECRET=... SCHWAB_TOKEN_PATH=$PWD/data_collection/schwab_token.json
   ```
> Schwab **refresh tokens expire ~7 days**, so you must re-run the login flow weekly. That weekly manual
> step is why a *local* job (where you can re-auth) beats a headless cloud job for the Schwab source.

## Scheduling on macOS — how it actually works

You asked whether free **n8n** is best. Short answer: **no, not for one daily script** — use the native
**launchd**. Here's the full picture.

### 1. launchd  — recommended ✅
macOS's own service manager (it runs everything at boot). A per-user *LaunchAgent* is a `.plist` in
`~/Library/LaunchAgents/`. We ship one: `com.robert.spychainlogger.plist`.
```bash
cp data_collection/com.robert.spychainlogger.plist ~/Library/LaunchAgents/
launchctl load  ~/Library/LaunchAgents/com.robert.spychainlogger.plist   # enable
launchctl start com.robert.spychainlogger                                # test-run now
tail -f data_collection/logger.log                                       # watch output
launchctl unload ~/Library/LaunchAgents/com.robert.spychainlogger.plist  # disable
```
- **Pros:** native (no extra software), starts at login, and **catches up a missed run** — if the Mac
  was asleep at 10:00 or 15:00 it fires the job when you next wake it. Edit the `Hour`s for your timezone.
- **Cons:** XML is fiddly; one job per plist. Note the catch-up captures the chain *at wake time*, not at
  10:00/15:00 — fine as "a morning/afternoon snapshot," but see the sleep gotcha for hitting exact times.

### 2. cron — works, but weakest on macOS
One line: `crontab -e` → `0 10,15 * * 1-5 /…/opt_venv/bin/python /…/chain_logger.py`.
- **Cons on macOS:** **no catch-up** (a job whose time passed while asleep is simply skipped), modern
  macOS needs to grant cron *Full Disk Access*, and Apple officially steers you to launchd. Fine on an
  always-on machine; poor on a laptop that sleeps.

### 3. n8n — overkill here, but nice for pipelines
Open-source workflow automation. **Free if self-hosted** (`npx n8n` or Docker); **n8n Cloud is paid**.
- **Use it if** you want a visual multi-step flow — fetch chain → validate → write file → email/Slack
  on failure → retry — or you'll add more integrations later.
- **Against it here:** it's a Node/Docker service that must be **running** to fire its schedule, so on a
  sleeping laptop it has the same problem as cron *plus* a heavyweight daemon. For a single `python`
  script, launchd does the same job with zero extra moving parts.

### 4. GitHub Actions (free) — best for the *yfinance* source
A free `schedule:` cron in a repo runs **always** (their servers, never asleep). Great for the
no-auth yfinance path; commit the CSV back or push to storage. **Not** ideal for Schwab, because the
~7-day refresh-token expiry needs interactive re-auth that a headless runner can't do.

### The laptop-sleep gotcha (read this)
We now capture **intraday** snapshots (10:00 and 15:00), so timing matters more than for an EOD grab —
a catch-up after you open the lid logs the chain *then*, not at 10:00/15:00 (the `_HHMM` filename records
the real time, so it's honest, just not the target minute). Options, best first:
- **Keep the Mac awake during market hours** (lid open, or clamshell on external power). If it's awake at
  10:00 and 15:00 the runs fire on time — the common case if you use the laptop during the day.
- **Wake it for the morning run:** `sudo pmset repeat wake MTWRF 09:59:00` (a single repeating wake); the
  15:00 run then fires while you're already using it. `pmset schedule` can add one-off wakes.
- **launchd catch-up** (default): if it was asleep at a target time you still get one snapshot when you
  next open it — labelled with the actual capture time.
- **Always-on:** run on a small always-on box / Raspberry Pi / cloud VM, or use GitHub Actions (yfinance).

## Recommendation
- **You have Schwab + a laptop →** local **launchd** job with the Schwab source (re-auth weekly), relying
  on catch-up or a `pmset` wake. Real greeks, free.
- **Want zero maintenance →** **GitHub Actions** with the yfinance source (always runs, no token upkeep).
- **Reach for n8n only** if you're building a larger visual pipeline with notifications/retries.
