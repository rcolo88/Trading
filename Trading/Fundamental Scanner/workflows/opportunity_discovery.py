"""
Opportunity Discovery Workflow — yfinance-only, two-phase, resumable.

Phase 1 (gather): fetches yfinance current fundamentals + multi-year history,
respecting a 1 req/sec rate limit with exponential backoff. Persists to
`merged_opportunity_cache.pkl` after every ticker, so the process can be
interrupted (Ctrl-C) and resumed later without refetching.

Phase 2 (score): reads only from the cache and runs the cross-sectional
OpportunityScorer. No network calls.

This replaces the earlier SimFin + yfinance hybrid design so there is a single
free data source and predictable rate behaviour.

Usage from CLI:
    python main_quality_analysis.py --discover --index sp500
    # → runs gather-then-score, reusing anything already cached
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.financial_data_fetcher import FinancialData
from data.parallel_fetcher import ParallelFetcher
from data.watchlist_config import WatchlistConfig
from quality.opportunity_scorer import OpportunityReport, OpportunityScorer

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

logger = logging.getLogger(__name__)

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
MERGED_CACHE_FILE = Path(__file__).parent.parent / "merged_opportunity_cache.pkl"
MERGED_CACHE_TTL = timedelta(days=7)


# ---------------------------------------------------------------------------
# Persistent merged cache — resumable across sessions
# ---------------------------------------------------------------------------

class MergedCache:
    """Pickle-backed store of {ticker: (merged_dict, fetched_at)}."""

    def __init__(self, path: Path = MERGED_CACHE_FILE, ttl: timedelta = MERGED_CACHE_TTL):
        self.path = Path(path)
        self.ttl = ttl
        self._lock = Lock()
        self._data: Dict[str, Tuple[Dict[str, Any], datetime]] = self._load()

    def _load(self) -> Dict[str, Tuple[Dict[str, Any], datetime]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("rb") as f:
                return pickle.load(f)
        except Exception as exc:
            logger.warning(f"merged cache load failed: {exc}")
            return {}

    def _save(self) -> None:
        tmp = self.path.with_suffix(".pkl.tmp")
        with tmp.open("wb") as f:
            pickle.dump(self._data, f)
        os.replace(tmp, self.path)

    def get(self, ticker: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._data.get(ticker)
        if entry is None:
            return None
        data, fetched_at = entry
        if datetime.now() - fetched_at > self.ttl:
            return None
        return data

    def set(self, ticker: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._data[ticker] = (data, datetime.now())
            self._save()

    def has_fresh(self, ticker: str) -> bool:
        return self.get(ticker) is not None

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._data.keys())

    def get_many(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for t in tickers:
            d = self.get(t)
            if d is not None:
                out[t] = d
        return out


# ---------------------------------------------------------------------------
# yfinance → scorer-shape adapter
# ---------------------------------------------------------------------------

def _safe_col(df: pd.DataFrame, key: str, col) -> Optional[float]:
    try:
        if df is None or df.empty or key not in df.index or col not in df.columns:
            return None
        v = df.loc[key, col]
        if pd.notna(v) and not np.isinf(v):
            return float(v)
    except Exception:
        return None
    return None


def _first_present(df: pd.DataFrame, keys: List[str], col) -> Optional[float]:
    for k in keys:
        v = _safe_col(df, k, col)
        if v is not None:
            return v
    return None


def _build_merged_dict(
    ticker: str,
    current: FinancialData,
    stock: yf.Ticker,
) -> Dict[str, Any]:
    """Adapt yfinance data into the dict shape `OpportunityScorer` expects.

    The scorer reads keys like `gross_profitability`, `altman_z_score`,
    `accrual_ratio`, and a `simfin_historical` sub-dict with `income`,
    `balance`, and `cash_flow` arrays. We populate those from yfinance's
    raw statements so the scorer's logic is unchanged.
    """
    merged: Dict[str, Any] = current.to_dict()
    merged["ticker"] = ticker

    # Raw statements from this ticker (shared across historical + accrual calcs)
    try:
        financials = stock.financials
    except Exception:
        financials = pd.DataFrame()
    try:
        balance = stock.balance_sheet
    except Exception:
        balance = pd.DataFrame()
    try:
        cashflow = stock.cashflow
    except Exception:
        cashflow = pd.DataFrame()

    # Most-recent column (yfinance orders newest-first)
    def latest_col(df: pd.DataFrame):
        return df.columns[0] if isinstance(df, pd.DataFrame) and not df.empty else None

    lc_inc = latest_col(financials)
    lc_bal = latest_col(balance)
    lc_cf = latest_col(cashflow)

    # Current-year OCF (missing from FinancialData)
    ocf = _first_present(
        cashflow,
        ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
         "Total Cash From Operating Activities"],
        lc_cf,
    ) if lc_cf is not None else None
    if ocf is not None:
        merged["operating_cash_flow"] = ocf

    # Current assets / liabilities (for F-Score current ratio + Beneish)
    ca = _first_present(balance, ["Current Assets", "Total Current Assets"], lc_bal) if lc_bal is not None else None
    cl = _first_present(balance, ["Current Liabilities", "Total Current Liabilities"], lc_bal) if lc_bal is not None else None
    if ca is not None:
        merged["current_assets"] = ca
    if cl is not None:
        merged["current_liabilities"] = cl

    # EBITDA (fallback when FinancialData didn't capture it)
    if not merged.get("ebitda"):
        ebitda = _first_present(financials, ["EBITDA", "Normalized EBITDA"], lc_inc) if lc_inc is not None else None
        if ebitda is not None:
            merged["ebitda"] = ebitda

    # Shares outstanding (for shareholder yield + F-Score equity issuance)
    try:
        info = stock.fast_info if hasattr(stock, "fast_info") else {}
        shares = getattr(info, "shares", None) if info else None
        if shares:
            merged["shares_outstanding"] = float(shares)
    except Exception:
        pass

    # Buybacks + dividends (for shareholder yield)
    if lc_cf is not None:
        buybacks = _first_present(
            cashflow,
            ["Repurchase Of Capital Stock", "Common Stock Repurchased", "Repurchase of Stock"],
            lc_cf,
        )
        dividends = _first_present(
            cashflow,
            ["Cash Dividends Paid", "Common Stock Dividend Paid", "Dividends Paid"],
            lc_cf,
        )
        if buybacks is not None:
            merged["net_buybacks"] = abs(buybacks)
        if dividends is not None:
            merged["dividends_paid"] = abs(dividends)

    # Derived ratios expected by the scorer
    if merged.get("revenue") and merged.get("cogs") is not None and merged.get("total_assets"):
        merged["gross_profitability"] = (merged["revenue"] - merged["cogs"]) / merged["total_assets"]
    if merged.get("net_income") is not None and merged.get("shareholder_equity"):
        merged["roe"] = merged["net_income"] / merged["shareholder_equity"]
    if ocf is not None and merged.get("net_income") and merged.get("total_assets"):
        merged["accrual_ratio"] = (merged["net_income"] - ocf) / merged["total_assets"]
    if merged.get("total_debt") is not None and merged.get("ebitda"):
        try:
            merged["debt_to_ebitda"] = merged["total_debt"] / merged["ebitda"]
        except ZeroDivisionError:
            pass
    if merged.get("operating_income") and merged.get("interest_expense"):
        try:
            merged["interest_coverage"] = merged["operating_income"] / abs(merged["interest_expense"])
        except ZeroDivisionError:
            pass

    # Altman Z (original 1968 formula, mirrors data/ratio_calculator.py)
    try:
        ta = merged.get("total_assets")
        if ta and merged.get("working_capital") is not None and merged.get("retained_earnings") is not None \
                and merged.get("ebit") is not None and merged.get("revenue") is not None:
            x1 = merged["working_capital"] / ta
            x2 = merged["retained_earnings"] / ta
            x3 = merged["ebit"] / ta
            x5 = merged["revenue"] / ta
            td = merged.get("total_debt") or 0
            x4 = (merged.get("shareholder_equity") or 0) / td if td else 0
            merged["altman_z_score"] = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    except Exception:
        pass

    # ---- Historical (simfin_historical-shape so scorer logic is untouched)
    simfin_historical = _build_historical(financials, balance, cashflow)
    if simfin_historical:
        merged["simfin_historical"] = simfin_historical

    # ROE history for persistence scoring
    roe_history: List[float] = []
    for inc, bal in zip(
        simfin_historical.get("income", []),
        simfin_historical.get("balance", []),
    ):
        ni = inc.get("net_income")
        eq = bal.get("shareholder_equity")
        if ni is not None and eq and eq > 0:
            roe_history.append(ni / eq)
    if roe_history:
        merged["roe_history"] = roe_history

    merged["data_sources"] = ["yfinance"]
    merged["fetch_timestamp"] = datetime.now().isoformat()
    return merged


def _build_historical(
    financials: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame
) -> Dict[str, List[Dict[str, Any]]]:
    """Extract multi-year history as {income, balance, cash_flow} arrays ordered oldest → newest."""
    all_cols = set()
    for df in (financials, balance, cashflow):
        if isinstance(df, pd.DataFrame) and not df.empty:
            all_cols.update(df.columns)
    if not all_cols:
        return {}

    # yfinance columns are datetimes — sort ascending (oldest first)
    cols_sorted = sorted(all_cols)

    income_rows: List[Dict[str, Any]] = []
    balance_rows: List[Dict[str, Any]] = []
    cashflow_rows: List[Dict[str, Any]] = []

    for col in cols_sorted:
        fy = getattr(col, "year", None)

        income_rows.append({
            "fiscal_year": fy,
            "revenue": _first_present(financials, ["Total Revenue", "Revenue"], col),
            "cogs": _first_present(financials, ["Cost Of Revenue", "Cost Of Goods Sold"], col),
            "net_income": _first_present(financials, ["Net Income", "Net Income Common Stockholders"], col),
            "operating_income": _first_present(financials, ["Operating Income", "EBIT"], col),
            "operating_expense": _first_present(financials, ["Operating Expense"], col),
            "accounts_receivable": None,
        })
        balance_rows.append({
            "fiscal_year": fy,
            "total_assets": _first_present(balance, ["Total Assets"], col),
            "shareholder_equity": _first_present(
                balance, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"], col
            ),
            "total_debt": _first_present(balance, ["Total Debt", "Long Term Debt"], col),
            "current_assets": _first_present(balance, ["Current Assets", "Total Current Assets"], col),
            "current_liabilities": _first_present(balance, ["Current Liabilities", "Total Current Liabilities"], col),
            "retained_earnings": _first_present(balance, ["Retained Earnings"], col),
            "accounts_receivable": _first_present(balance, ["Accounts Receivable", "Receivables"], col),
        })
        cashflow_rows.append({
            "fiscal_year": fy,
            "operating_cash_flow": _first_present(
                cashflow,
                ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
                 "Total Cash From Operating Activities"],
                col,
            ),
            "free_cash_flow": _first_present(cashflow, ["Free Cash Flow"], col),
            "dividends_paid": _first_present(
                cashflow, ["Cash Dividends Paid", "Common Stock Dividend Paid"], col
            ),
            "stock_repurchased": _first_present(
                cashflow, ["Repurchase Of Capital Stock", "Common Stock Repurchased"], col
            ),
        })

    # Attach receivables to income rows too (for Beneish DSRI lookups)
    for inc, bal in zip(income_rows, balance_rows):
        inc["accounts_receivable"] = bal.get("accounts_receivable")

    return {"income": income_rows, "balance": balance_rows, "cash_flow": cashflow_rows}


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

class OpportunityDiscoveryWorkflow:
    """yfinance-only, two-phase, resumable cross-sectional screen."""

    def __init__(
        self,
        watchlist_config: WatchlistConfig,
        max_workers: int = 10,
        requests_per_second: float = 1.0,
        top_n: int = 25,
        write_outputs: bool = True,
        cache: Optional[MergedCache] = None,
        scorer: Optional[OpportunityScorer] = None,
    ) -> None:
        self.watchlist_config = watchlist_config
        self.max_workers = max_workers
        self.requests_per_second = requests_per_second
        self.top_n = top_n
        self.write_outputs = write_outputs
        self.cache = cache or MergedCache()
        self.scorer = scorer or OpportunityScorer()

        self._parallel_fetcher = ParallelFetcher(
            max_workers=max_workers,
            requests_per_second=requests_per_second,
            enable_cache=True,
            max_retries=3,
        )

    # ---- public API --------------------------------------------------------

    def run(self, limit: Optional[int] = None) -> List[OpportunityReport]:
        tickers = self.watchlist_config.get_tickers()
        if limit:
            tickers = tickers[:limit]
        print(f"\n[opportunity-discovery] Universe: {len(tickers)} tickers")

        if not tickers:
            print("[opportunity-discovery] No tickers resolved; aborting.")
            return []

        self.gather(tickers)
        return self.score(tickers)

    def gather(self, tickers: List[str]) -> None:
        """Phase 1: fetch + cache any tickers not already in the merged cache."""
        missing = [t for t in tickers if not self.cache.has_fresh(t)]
        cached = len(tickers) - len(missing)
        print(f"[opportunity-discovery] Cache: {cached} hit, {len(missing)} to fetch")

        if not missing:
            return

        # Step 1: batch-fetch current fundamentals via ParallelFetcher
        #         (rate-limited, retries on 429, reuses financial_cache.pkl)
        current_map = self._parallel_fetcher.batch_fetch_with_progress(
            missing, desc="Fetching current", suppress_logging=True,
        )

        # Step 2: fetch historical + adapt to scorer shape, persisting after each
        print(f"[opportunity-discovery] Fetching {len(missing)} histories (rate-limited)...")
        self._fetch_and_cache_histories(missing, current_map)

    def score(self, tickers: List[str]) -> List[OpportunityReport]:
        """Phase 2: read from cache, run scorer, write outputs."""
        merged = self.cache.get_many(tickers)
        if not merged:
            print("[opportunity-discovery] No cached data to score.")
            return []
        print(f"[opportunity-discovery] Scoring {len(merged)} tickers from cache")
        reports = self.scorer.score_universe(merged)
        if self.write_outputs:
            self._write_outputs(reports)
        return reports

    # ---- history fetch (adds OCF, current assets/liabs, accruals fields) ---

    def _fetch_and_cache_histories(
        self, tickers: List[str], current_map: Dict[str, Optional[FinancialData]]
    ) -> None:
        rate = self._parallel_fetcher.rate_limiter

        def fetch_one(ticker: str) -> None:
            current = current_map.get(ticker)
            if current is None or current.data_quality == "insufficient":
                logger.debug(f"{ticker}: skipping history (insufficient current data)")
                return
            try:
                rate.acquire()
                stock = yf.Ticker(ticker)
                merged = _build_merged_dict(ticker, current, stock)
                self.cache.set(ticker, merged)
            except Exception as exc:
                err = str(exc).lower()
                if "429" in err or "too many requests" in err:
                    # backoff and retry once
                    time.sleep(8)
                    try:
                        rate.acquire()
                        stock = yf.Ticker(ticker)
                        merged = _build_merged_dict(ticker, current, stock)
                        self.cache.set(ticker, merged)
                    except Exception as exc2:
                        logger.warning(f"{ticker}: history retry failed: {exc2}")
                else:
                    logger.warning(f"{ticker}: history fetch failed: {exc}")

        iterator_desc = "Fetching history"
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [pool.submit(fetch_one, t) for t in tickers]
            if HAS_TQDM:
                for _ in tqdm(as_completed(futures), total=len(futures), desc=iterator_desc,
                              unit="ticker", file=sys.stdout):
                    pass
            else:
                for fut in as_completed(futures):
                    fut.result()

    # ---- output writers ----------------------------------------------------

    def _write_outputs(self, reports: List[OpportunityReport]) -> None:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d")

        json_path = OUTPUTS_DIR / f"opportunities_{stamp}.json"
        top_path = OUTPUTS_DIR / f"opportunities_{stamp}_top.txt"
        red_path = OUTPUTS_DIR / f"opportunities_{stamp}_red.txt"

        with json_path.open("w") as f:
            json.dump([r.to_dict() for r in reports], f, indent=2, default=str)

        passers = [r for r in reports if r.gates_passed]
        flagged = [r for r in reports if not r.gates_passed]

        with top_path.open("w") as f:
            f.write(self._format_top(passers[: self.top_n]))
        with red_path.open("w") as f:
            f.write(self._format_red(flagged))

        print(f"[opportunity-discovery] Wrote {json_path}")
        print(f"[opportunity-discovery] Wrote {top_path}")
        print(f"[opportunity-discovery] Wrote {red_path}")

    @staticmethod
    def _format_top(reports: List[OpportunityReport]) -> str:
        lines = [
            "=" * 90,
            f"OPPORTUNITY DISCOVERY — TOP {len(reports)}  ({datetime.now().isoformat(timespec='seconds')})",
            "=" * 90,
            "",
            f"{'Rank':>4}  {'Ticker':<8}  {'Tier':<20}  {'Opp':>6}  {'QARP':>6}  {'GPOA':>6}  {'F':>3}  {'Sector':<24}",
            "-" * 90,
        ]
        for i, r in enumerate(reports, 1):
            gp = r.signals.get("gross_profitability")
            fscore = r.signals.get("f_score")
            lines.append(
                f"{i:>4}  {r.ticker:<8}  {r.tier:<20}  "
                f"{r.opportunity_score:>6.1f}  "
                f"{(r.qarp_score or 0):>6.1f}  "
                f"{(gp * 100 if gp is not None else 0):>5.1f}%  "
                f"{(fscore if fscore is not None else 0):>3}  "
                f"{(r.sector or ''):<24}"
            )
        lines.extend([
            "",
            "Tiers:",
            "  Compounder          — top 10% quality, all gates pass",
            "  Discount Compounder — top 20% QARP (quality + value), all gates pass",
            "  Rising Quality      — positive quality acceleration + quality > median",
            "  Cash Return         — shareholder yield > 5% + GPOA > 30%",
            "",
            "Methodology: Novy-Marx & Medhat (2025) — profitability anchors the",
            "composite. Hard gates applied for F-Score, asset growth, accruals,",
            "Beneish M, Altman Z, and interest coverage.",
            "",
        ])
        return "\n".join(lines)

    @staticmethod
    def _format_red(reports: List[OpportunityReport]) -> str:
        lines = [
            "=" * 90,
            f"OPPORTUNITY DISCOVERY — GATE FAILURES ({len(reports)} tickers)",
            "=" * 90,
            "",
            f"{'Ticker':<8}  {'Failures':<60}  {'Opp':>6}",
            "-" * 90,
        ]
        for r in sorted(reports, key=lambda x: x.opportunity_score, reverse=True):
            lines.append(
                f"{r.ticker:<8}  {', '.join(r.gate_failures)[:58]:<60}  {r.opportunity_score:>6.1f}"
            )
        return "\n".join(lines) + "\n"


__all__ = ["OpportunityDiscoveryWorkflow", "MergedCache"]
