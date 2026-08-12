# ADR 0001: The 3-way blend replaces the equity engine as the primary strategy

**Status:** Adopted, 2026-08-05 (commit `46a4f0d`)

## Context

The original equity cross-sectional momentum engine (S&P 1500, composite momentum signal, weekly
rebalance) was the project's founding strategy. Repeated attempts to isolate genuine stock-picking
alpha in it — sector-neutralizing, beta-capping, inverse-vol weighting, and hedging with a real
inverse ETF (SH/SDS) — never produced an alpha t-stat above 1.5; every variant sat at 0.4-1.1
(`README.md:395-407`). The inverse-ETF hedge made results progressively *worse* as hedge intensity
rose (Sharpe 0.671 → 0.401 → −0.166), which is itself evidence there was no isolable alpha to
protect by hedging beta away — if there were, hedging beta should have revealed it, not destroyed it.

## Decision

Build a 3-way fixed-weight ETF blend (growth / macro regime tilt / defensive rotation) and promote
it to the primary `backtest`/`ideas`/`verify-book` commands. The equity engine is preserved,
unchanged, under `equity-*` commands rather than deleted — its infrastructure (PIT universe,
composite signal, DSR/MCPT wiring) remains useful, and demoting rather than removing it keeps the
option to revisit if a future signal genuinely clears the alpha bar.

The blend uses **SPY as a substitute for the equity book's beta exposure**, since testing found the
equity book's returns are not significantly different from a ~0.5-0.7-beta SPY position anyway — SPY
is a fair, simpler stand-in for the same exposure, freeing the remaining two sleeves to add
genuinely diversifying return streams (macro regime tilt, multi-asset rotation) on top.

## Consequences

- The equity engine's infrastructure (universe, signal, validation, DSR/MCPT/PBO wiring) is more
  fully built out than the blend's — see [`GAPS.md` #3](../GAPS.md) (the blend has no MCPT/PBO
  wired) and [`GAPS.md` #8](../GAPS.md) (dead AFML surface original to the equity engine).
- The blend's claimed edge is diversification, not stock-picking skill — see
  [`METHODOLOGY.md`](../METHODOLOGY.md#what-this-result-actually-is).
- Two parallel strategies now exist in one codebase (`csm/backtest.py`+`csm/portfolio.py` for
  equity, `csm/blend.py` for the blend), sharing `csm/data.py`/`csm/costs.py`/`csm/report.py`.
- The equity engine's own numbers should still be periodically re-validated if the project keeps it
  around — see the equity-engine correction row in [`VALIDATION.md`](../VALIDATION.md).
