"""
Opportunity Scorer — Cross-Sectional Ranking for Quality Investing

Implements a profitability-anchored, cross-sectional z-score composite for
discovering lucrative investment opportunities from a pre-fetched universe of
financial data. Anchored on Novy-Marx & Medhat (2025), which shows gross
profits-to-assets subsumes all quality factors.

Signals used (from the enhanced hybrid fetcher output):

    Anchor (weight 0.40):
        - gross_profitability  = (revenue - cogs) / total_assets
            Novy-Marx (2013); Novy-Marx & Medhat (2025)

    Orthogonal quality (weight 0.60 total):
        - roe_persistence      = 5-yr median ROE                (0.15) FF5 / AQR QMJ
        - cash_flow_quality    = OCF / |NI|                     (0.10) Sloan (1996)
        - expected_growth      = z(CFOA) + z(dROE_2yr) + z(B/P) (0.10) Hou-Mo-Xue-Zhang (2021)
        - neg_accruals         = -(NI - OCF) / Assets           (0.10) Sloan (1996)
        - neg_asset_growth     = -ΔAssets / Assets              (0.05) Cooper-Gulen-Schill (2008)
        - shareholder_yield    = (dividends + |net buybacks|) / market_cap (0.05)
        - quality_acceleration = 2nd difference of quality score (0.05) Ma-Yang-Ye (2024)

Hard gates (exclude from opportunity list):
    F-Score  >= 5      (Piotroski 2000)
    Asset growth <= 40%  (Cooper 2008)
    Accrual ratio <= 10% (Sloan 1996)
    Beneish M  <= -1.78  (Beneish 1999)
    Altman Z   >= 1.80   (Altman 1968)
    Interest coverage >= 2x

The scorer consumes the merged dict already produced by
`data.enhanced_hybrid_fetcher.EnhancedHybridDataFetcher.fetch_complete_data`.
It does not fetch any data itself.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .earnings_quality import EarningsQualityAnalyzer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COMPOSITE_WEIGHTS: Dict[str, float] = {
    "gross_profitability": 0.40,
    "roe_persistence": 0.15,
    "cash_flow_quality": 0.10,
    "expected_growth": 0.10,
    "neg_accruals": 0.10,
    "neg_asset_growth": 0.05,
    "shareholder_yield": 0.05,
    "quality_acceleration": 0.05,
}

HARD_GATES: Dict[str, Tuple[str, float]] = {
    "f_score": ("min", 5),
    "asset_growth": ("max", 0.40),
    "accrual_ratio": ("max", 0.10),
    "beneish_m": ("max", -1.78),
    "altman_z": ("min", 1.80),
    "interest_coverage": ("min", 2.0),
}

VALUE_WEIGHTS: Dict[str, float] = {
    "fcf_yield": 0.50,
    "earnings_yield": 0.30,
    "neg_ev_ebitda": 0.20,
}

QARP_QUALITY_TILT = 0.60   # Quality vs. Value weight in QARP composite


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class OpportunitySignals:
    """Raw signal values computed per-ticker before z-scoring."""
    ticker: str
    gross_profitability: Optional[float] = None
    roe_persistence: Optional[float] = None
    cash_flow_quality: Optional[float] = None
    expected_growth: Optional[float] = None
    accrual_ratio: Optional[float] = None
    asset_growth: Optional[float] = None
    shareholder_yield: Optional[float] = None
    quality_acceleration: Optional[float] = None
    # Value overlay
    fcf_yield: Optional[float] = None
    earnings_yield: Optional[float] = None
    ev_ebitda: Optional[float] = None
    # Gate inputs
    f_score: Optional[int] = None
    beneish_m: Optional[float] = None
    altman_z: Optional[float] = None
    interest_coverage: Optional[float] = None
    # Metadata
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    data_quality: Optional[str] = None


@dataclass
class OpportunityReport:
    """Final per-ticker ranking output."""
    ticker: str
    opportunity_score: float        # 0-100, cross-sectional
    qarp_score: Optional[float]     # 0-100, quality+value blend
    gates_passed: bool
    gate_failures: List[str]
    tier: str                       # Compounder / Discount Compounder / Rising Quality / Cash Return / Flagged
    signals: Dict[str, Any]
    z_scores: Dict[str, float]
    market_cap: Optional[float]
    sector: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Core scorer
# ---------------------------------------------------------------------------

class OpportunityScorer:
    """
    Cross-sectional opportunity scorer.

    Usage:
        scorer = OpportunityScorer()
        reports = scorer.score_universe(merged_data_by_ticker)
        # reports: List[OpportunityReport] sorted by opportunity_score desc
    """

    def __init__(
        self,
        composite_weights: Optional[Dict[str, float]] = None,
        hard_gates: Optional[Dict[str, Tuple[str, float]]] = None,
        qarp_tilt: float = QARP_QUALITY_TILT,
    ) -> None:
        self.weights = composite_weights or dict(COMPOSITE_WEIGHTS)
        self.gates = hard_gates or dict(HARD_GATES)
        self.qarp_tilt = qarp_tilt
        self._fscore_analyzer = EarningsQualityAnalyzer()

        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.001:
            raise ValueError(
                f"Composite weights must sum to 1.0 (got {weight_sum:.3f})"
            )

    # ---- public API --------------------------------------------------------

    def score_universe(
        self,
        merged_by_ticker: Dict[str, Dict[str, Any]],
    ) -> List[OpportunityReport]:
        """
        Score every ticker in the universe and return ranked opportunities.

        Args:
            merged_by_ticker: Mapping ticker -> merged data dict from
                EnhancedHybridDataFetcher.fetch_complete_data

        Returns:
            List of OpportunityReport sorted by opportunity_score descending.
        """
        # Step 1: extract signals per ticker
        signals_list: List[OpportunitySignals] = []
        for ticker, data in merged_by_ticker.items():
            if not data:
                continue
            sig = self._extract_signals(ticker, data)
            if sig is not None:
                signals_list.append(sig)

        if not signals_list:
            logger.warning("No scorable tickers found in universe")
            return []

        # Step 2: cross-sectional z-scores for every composite signal
        z_by_ticker = self._cross_sectional_z(signals_list)

        # Step 3: value z-scores (for QARP overlay)
        value_z = self._value_z_scores(signals_list)

        # Step 4: build final reports
        reports: List[OpportunityReport] = []
        for sig in signals_list:
            composite_raw = self._weighted_sum(z_by_ticker.get(sig.ticker, {}), self.weights)
            value_raw = self._weighted_sum(value_z.get(sig.ticker, {}), VALUE_WEIGHTS)

            gates_ok, failures = self._evaluate_gates(sig)

            reports.append(
                OpportunityReport(
                    ticker=sig.ticker,
                    opportunity_score=self._to_centile(composite_raw, 50, 15),
                    qarp_score=self._qarp_score(composite_raw, value_raw),
                    gates_passed=gates_ok,
                    gate_failures=failures,
                    tier=self._classify_tier(sig, composite_raw, value_raw, gates_ok),
                    signals={k: v for k, v in asdict(sig).items() if k != "ticker"},
                    z_scores=z_by_ticker.get(sig.ticker, {}),
                    market_cap=sig.market_cap,
                    sector=sig.sector,
                )
            )

        reports.sort(key=lambda r: r.opportunity_score, reverse=True)
        return reports

    # ---- signal extraction -------------------------------------------------

    def _extract_signals(
        self, ticker: str, data: Dict[str, Any]
    ) -> Optional[OpportunitySignals]:
        """Pull every signal from one merged data dict.

        Prefers SimFin-tagged fields (more consistent) then falls back to
        yfinance-tagged fields on the same dict.
        """
        def pick(*keys: str) -> Optional[float]:
            for k in keys:
                v = data.get(k)
                if v is not None and not (isinstance(v, float) and math.isnan(v)):
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        continue
            return None

        gp = pick("simfin_gross_profitability", "gross_profitability")
        if gp is None:
            rev = pick("simfin_revenue", "revenue")
            cogs = pick("simfin_cogs", "cogs")
            ta = pick("simfin_total_assets", "total_assets")
            if rev is not None and cogs is not None and ta and ta > 0:
                gp = (rev - cogs) / ta

        historical = data.get("simfin_historical") or {}
        income_hist = historical.get("income") or []
        balance_hist = historical.get("balance") or []
        cashflow_hist = historical.get("cash_flow") or []

        roe_hist = data.get("roe_history") or []
        if roe_hist:
            valid = [x for x in roe_hist if x is not None]
            roe_persistence = _median(valid) if valid else None
        else:
            roe_persistence = pick("simfin_roe", "roe")

        ni = pick("simfin_net_income", "net_income")
        ocf = pick("simfin_operating_cash_flow", "operating_cash_flow")
        if ocf is None:
            fcf = pick("simfin_free_cash_flow", "free_cash_flow")
            ocf = fcf  # weak fallback; OCF ≈ FCF + capex but we treat as proxy
        cfq = None
        if ocf is not None and ni is not None and abs(ni) > 1e-6:
            cfq = ocf / abs(ni)

        accrual_ratio = pick("simfin_accrual_ratio", "accrual_ratio")
        if accrual_ratio is None and ni is not None and ocf is not None:
            ta = pick("simfin_total_assets", "total_assets")
            if ta and ta > 0:
                accrual_ratio = (ni - ocf) / ta

        asset_growth = _compute_asset_growth(balance_hist)

        shareholder_yield = _compute_shareholder_yield(data, cashflow_hist)

        expected_growth = _compute_expected_growth_proxy(
            income_hist, balance_hist, cashflow_hist, data
        )

        quality_acceleration = _compute_quality_acceleration(
            income_hist, balance_hist
        )

        # Value overlay
        mcap = pick("market_cap", "simfin_market_cap")
        fcf = pick("simfin_free_cash_flow", "free_cash_flow")
        fcf_yield = (fcf / mcap) if fcf is not None and mcap and mcap > 0 else None
        earnings_yield = (ni / mcap) if ni is not None and mcap and mcap > 0 else None
        ebitda = pick("simfin_ebitda", "ebitda")
        total_debt = pick("simfin_total_debt", "total_debt") or 0.0
        cash = pick("cash_and_equivalents", "cash") or 0.0
        ev_ebitda = None
        if ebitda and ebitda > 0 and mcap:
            ev = mcap + total_debt - cash
            ev_ebitda = ev / ebitda

        # Gate inputs
        f_score = _compute_f_score(self._fscore_analyzer, data, income_hist, balance_hist, cashflow_hist)
        beneish_m = _compute_beneish_m(income_hist, balance_hist, cashflow_hist)
        altman_z = pick("simfin_altman_z_score", "altman_z_score")
        interest_coverage = pick("simfin_interest_coverage", "interest_coverage")

        return OpportunitySignals(
            ticker=ticker,
            gross_profitability=gp,
            roe_persistence=roe_persistence,
            cash_flow_quality=cfq,
            expected_growth=expected_growth,
            accrual_ratio=accrual_ratio,
            asset_growth=asset_growth,
            shareholder_yield=shareholder_yield,
            quality_acceleration=quality_acceleration,
            fcf_yield=fcf_yield,
            earnings_yield=earnings_yield,
            ev_ebitda=ev_ebitda,
            f_score=f_score,
            beneish_m=beneish_m,
            altman_z=altman_z,
            interest_coverage=interest_coverage,
            market_cap=mcap,
            sector=data.get("sector"),
            data_quality=data.get("data_quality") or data.get("simfin_data_quality"),
        )

    # ---- cross-sectional normalization -------------------------------------

    def _cross_sectional_z(
        self, signals: List[OpportunitySignals]
    ) -> Dict[str, Dict[str, float]]:
        """Compute cross-sectional z-score for every composite signal."""
        field_map = {
            "gross_profitability": ("gross_profitability", 1),
            "roe_persistence": ("roe_persistence", 1),
            "cash_flow_quality": ("cash_flow_quality", 1),
            "expected_growth": ("expected_growth", 1),
            "neg_accruals": ("accrual_ratio", -1),
            "neg_asset_growth": ("asset_growth", -1),
            "shareholder_yield": ("shareholder_yield", 1),
            "quality_acceleration": ("quality_acceleration", 1),
        }

        z_by_ticker: Dict[str, Dict[str, float]] = {s.ticker: {} for s in signals}

        for comp_name, (attr, sign) in field_map.items():
            values = [(s.ticker, getattr(s, attr)) for s in signals]
            winsorized = _winsorize([v for _, v in values if v is not None], 0.01)
            mean, std = _mean_std(winsorized)
            for ticker, val in values:
                if val is None or std == 0:
                    z_by_ticker[ticker][comp_name] = 0.0
                else:
                    clipped = _clip(val, winsorized[0], winsorized[-1]) if winsorized else val
                    z_by_ticker[ticker][comp_name] = sign * (clipped - mean) / std

        return z_by_ticker

    def _value_z_scores(
        self, signals: List[OpportunitySignals]
    ) -> Dict[str, Dict[str, float]]:
        """Cross-sectional z-scores for value overlay."""
        field_map = {
            "fcf_yield": ("fcf_yield", 1),
            "earnings_yield": ("earnings_yield", 1),
            "neg_ev_ebitda": ("ev_ebitda", -1),
        }
        z_by_ticker: Dict[str, Dict[str, float]] = {s.ticker: {} for s in signals}
        for comp_name, (attr, sign) in field_map.items():
            values = [(s.ticker, getattr(s, attr)) for s in signals]
            winsorized = _winsorize([v for _, v in values if v is not None], 0.01)
            mean, std = _mean_std(winsorized)
            for ticker, val in values:
                if val is None or std == 0:
                    z_by_ticker[ticker][comp_name] = 0.0
                else:
                    clipped = _clip(val, winsorized[0], winsorized[-1]) if winsorized else val
                    z_by_ticker[ticker][comp_name] = sign * (clipped - mean) / std
        return z_by_ticker

    # ---- composite helpers -------------------------------------------------

    @staticmethod
    def _weighted_sum(z_map: Dict[str, float], weights: Dict[str, float]) -> float:
        return sum(z_map.get(k, 0.0) * w for k, w in weights.items())

    @staticmethod
    def _to_centile(raw_z: float, mean: float = 50.0, spread: float = 15.0) -> float:
        """Map composite z (approx. standard normal) to 0-100 centile-style score."""
        return max(0.0, min(100.0, mean + spread * raw_z))

    def _qarp_score(self, quality_z: float, value_z: float) -> float:
        q = self._to_centile(quality_z, 50.0, 15.0)
        v = self._to_centile(value_z, 50.0, 15.0)
        return self.qarp_tilt * q + (1 - self.qarp_tilt) * v

    # ---- gates / tier classification ---------------------------------------

    def _evaluate_gates(
        self, sig: OpportunitySignals
    ) -> Tuple[bool, List[str]]:
        failures: List[str] = []
        for key, (direction, threshold) in self.gates.items():
            value = getattr(sig, key, None)
            if value is None:
                continue  # missing data → skip gate (do not exclude)
            if direction == "min" and value < threshold:
                failures.append(f"{key}<{threshold}")
            elif direction == "max" and value > threshold:
                failures.append(f"{key}>{threshold}")
        return (len(failures) == 0, failures)

    def _classify_tier(
        self,
        sig: OpportunitySignals,
        quality_z: float,
        value_z: float,
        gates_ok: bool,
    ) -> str:
        if not gates_ok:
            return "Flagged"

        quality_centile = self._to_centile(quality_z)
        qarp_centile = self.qarp_tilt * quality_centile + (1 - self.qarp_tilt) * self._to_centile(value_z)
        accel_ok = sig.quality_acceleration is not None and sig.quality_acceleration > 0

        if (
            sig.shareholder_yield is not None
            and sig.shareholder_yield > 0.05
            and sig.gross_profitability is not None
            and sig.gross_profitability > 0.30
        ):
            return "Cash Return"

        if quality_centile >= 90:
            return "Compounder"

        if qarp_centile >= 80:
            return "Discount Compounder"

        if accel_ok and quality_centile >= 60:
            return "Rising Quality"

        return "Neutral"


# ---------------------------------------------------------------------------
# Signal helpers (module-level, stateless)
# ---------------------------------------------------------------------------

def _median(xs: Iterable[float]) -> Optional[float]:
    xs_sorted = sorted(xs)
    n = len(xs_sorted)
    if n == 0:
        return None
    mid = n // 2
    if n % 2 == 1:
        return xs_sorted[mid]
    return 0.5 * (xs_sorted[mid - 1] + xs_sorted[mid])


def _mean_std(xs: List[float]) -> Tuple[float, float]:
    if not xs:
        return 0.0, 0.0
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    return mean, math.sqrt(var)


def _winsorize(xs: List[float], p: float = 0.01) -> List[float]:
    """Clip extreme tail values to limit z-score distortion."""
    if not xs:
        return []
    xs_sorted = sorted(xs)
    n = len(xs_sorted)
    lo = xs_sorted[max(0, int(n * p))]
    hi = xs_sorted[min(n - 1, int(n * (1 - p)))]
    return [_clip(x, lo, hi) for x in xs_sorted]


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _compute_asset_growth(balance_hist: List[Dict[str, Any]]) -> Optional[float]:
    if not balance_hist or len(balance_hist) < 2:
        return None
    # SimFin historical is typically oldest -> newest; sort by fiscal year to be safe
    rows = [r for r in balance_hist if r.get("fiscal_year") and r.get("total_assets")]
    if len(rows) < 2:
        return None
    rows.sort(key=lambda r: r["fiscal_year"])
    prev = rows[-2]["total_assets"]
    curr = rows[-1]["total_assets"]
    if prev is None or curr is None or prev == 0:
        return None
    return (curr - prev) / prev


def _compute_shareholder_yield(
    data: Dict[str, Any], cashflow_hist: List[Dict[str, Any]]
) -> Optional[float]:
    mcap = data.get("market_cap") or data.get("simfin_market_cap")
    if not mcap or mcap <= 0:
        return None
    dividends = data.get("dividends_paid") or data.get("simfin_dividends_paid") or 0.0
    buybacks = data.get("net_buybacks") or data.get("simfin_net_buybacks") or 0.0
    # yfinance doesn't always expose these; use cashflow_hist fallback
    if dividends == 0 and cashflow_hist:
        last = cashflow_hist[-1] if cashflow_hist else {}
        dividends = abs(last.get("dividends_paid") or 0.0)
        buybacks = abs(last.get("stock_repurchased") or 0.0)
    total = abs(dividends) + abs(buybacks)
    if total == 0:
        return None
    return total / mcap


def _compute_expected_growth_proxy(
    income_hist: List[Dict[str, Any]],
    balance_hist: List[Dict[str, Any]],
    cashflow_hist: List[Dict[str, Any]],
    data: Dict[str, Any],
) -> Optional[float]:
    """Hou-Mo-Xue-Zhang (2021) expected-growth proxy.

    expected_growth = 0.4 * log(B/P)  +  0.4 * CFOA  +  0.2 * ΔROE_2yr

    log(B/P) approximated by log(book_equity / market_cap).
    """
    if not income_hist or not balance_hist:
        return None

    mcap = data.get("market_cap") or data.get("simfin_market_cap")
    book = None
    if balance_hist:
        book = balance_hist[-1].get("shareholder_equity")

    log_bp: Optional[float] = None
    if mcap and mcap > 0 and book and book > 0:
        log_bp = math.log(book / mcap)

    cfoa = None
    if cashflow_hist and balance_hist:
        ocf = cashflow_hist[-1].get("operating_cash_flow")
        ta = balance_hist[-1].get("total_assets")
        if ocf is not None and ta and ta > 0:
            cfoa = ocf / ta

    d_roe_2yr: Optional[float] = None
    roe_seq: List[float] = []
    for i in range(min(len(income_hist), len(balance_hist))):
        ni = income_hist[i].get("net_income")
        eq = balance_hist[i].get("shareholder_equity")
        if ni is not None and eq and eq > 0:
            roe_seq.append(ni / eq)
    if len(roe_seq) >= 3:
        d_roe_2yr = roe_seq[-1] - roe_seq[-3]

    parts = []
    if log_bp is not None:
        parts.append(0.4 * log_bp)
    if cfoa is not None:
        parts.append(0.4 * cfoa)
    if d_roe_2yr is not None:
        parts.append(0.2 * d_roe_2yr)
    if not parts:
        return None
    return sum(parts)


def _compute_quality_acceleration(
    income_hist: List[Dict[str, Any]],
    balance_hist: List[Dict[str, Any]],
) -> Optional[float]:
    """Second difference of a simple GPOA trajectory — Ma, Yang, Ye (2024)."""
    pairs = []
    for inc, bal in zip(income_hist, balance_hist):
        rev = inc.get("revenue")
        cogs = inc.get("cogs")
        ta = bal.get("total_assets")
        if rev is not None and cogs is not None and ta and ta > 0:
            pairs.append((inc.get("fiscal_year"), (rev - cogs) / ta))
    pairs = [p for p in pairs if p[0] is not None]
    pairs.sort(key=lambda p: p[0])
    if len(pairs) < 3:
        return None
    q = [v for _, v in pairs]
    # acceleration = (q[-1] - q[-2]) - (q[-2] - q[-3])
    return (q[-1] - q[-2]) - (q[-2] - q[-3])


def _compute_f_score(
    analyzer: EarningsQualityAnalyzer,
    data: Dict[str, Any],
    income_hist: List[Dict[str, Any]],
    balance_hist: List[Dict[str, Any]],
    cashflow_hist: List[Dict[str, Any]],
) -> Optional[int]:
    """Build the F-Score input dict from merged data + SimFin history."""
    if not income_hist or not balance_hist:
        return None

    # Use most-recent and prior fiscal year
    rows = list(zip(income_hist, balance_hist, cashflow_hist or [{}] * len(income_hist)))
    rows = [r for r in rows if r[0].get("fiscal_year") is not None]
    rows.sort(key=lambda r: r[0]["fiscal_year"])
    if len(rows) < 2:
        return None

    prev_inc, prev_bal, prev_cf = rows[-2]
    curr_inc, curr_bal, curr_cf = rows[-1]

    payload = {
        "net_income": curr_inc.get("net_income") or 0,
        "prior_net_income": prev_inc.get("net_income") or 0,
        "operating_cash_flow": curr_cf.get("operating_cash_flow") or 0,
        "prior_operating_cash_flow": prev_cf.get("operating_cash_flow") or 0,
        "total_assets": curr_bal.get("total_assets") or 1,
        "prior_total_assets": prev_bal.get("total_assets") or 1,
        "shareholder_equity": curr_bal.get("shareholder_equity") or 1,
        "prior_shareholder_equity": prev_bal.get("shareholder_equity") or 1,
        "current_assets": curr_bal.get("current_assets") or 0,
        "prior_current_assets": prev_bal.get("current_assets") or 0,
        "current_liabilities": curr_bal.get("current_liabilities") or 0,
        "prior_current_liabilities": prev_bal.get("current_liabilities") or 0,
        "total_debt": curr_bal.get("total_debt") or 0,
        "prior_total_debt": prev_bal.get("total_debt") or 0,
        "shares_outstanding": data.get("shares_outstanding") or 0,
        "prior_shares_outstanding": data.get("prior_shares_outstanding") or data.get("shares_outstanding") or 0,
        "revenue": curr_inc.get("revenue") or 0,
        "prior_revenue": prev_inc.get("revenue") or 0,
        "cogs": curr_inc.get("cogs") or 0,
        "prior_cogs": prev_inc.get("cogs") or 0,
    }

    try:
        total, _ = analyzer.calculate_piotroski_f_score(payload)
        return int(total)
    except Exception as exc:
        logger.debug(f"F-Score failed for {data.get('ticker')}: {exc}")
        return None


def _compute_beneish_m(
    income_hist: List[Dict[str, Any]],
    balance_hist: List[Dict[str, Any]],
    cashflow_hist: List[Dict[str, Any]],
) -> Optional[float]:
    """
    Simplified Beneish M-Score (1999) using SimFin historical fields.

    Requires two consecutive years. Falls back to None if any input missing.
    """
    if len(income_hist) < 2 or len(balance_hist) < 2 or len(cashflow_hist) < 2:
        return None

    inc_t = income_hist[-1]
    inc_p = income_hist[-2]
    bal_t = balance_hist[-1]
    bal_p = balance_hist[-2]
    cf_t = cashflow_hist[-1]

    rev_t = inc_t.get("revenue")
    rev_p = inc_p.get("revenue")
    if not rev_t or not rev_p or rev_t <= 0 or rev_p <= 0:
        return None

    receivables_t = bal_t.get("accounts_receivable")
    receivables_p = bal_p.get("accounts_receivable")

    cogs_t = inc_t.get("cogs")
    cogs_p = inc_p.get("cogs")
    gm_t = ((rev_t - cogs_t) / rev_t) if rev_t and cogs_t is not None else None
    gm_p = ((rev_p - cogs_p) / rev_p) if rev_p and cogs_p is not None else None

    ta_t = bal_t.get("total_assets")
    ta_p = bal_p.get("total_assets")

    sga_t = inc_t.get("operating_expense")
    sga_p = inc_p.get("operating_expense")

    debt_t = bal_t.get("total_debt") or 0
    debt_p = bal_p.get("total_debt") or 0

    ni_t = inc_t.get("net_income")
    ocf_t = cf_t.get("operating_cash_flow")

    # DSRI — Days Sales in Receivables Index
    dsri = 1.0
    if receivables_t and receivables_p and rev_t and rev_p:
        dsri = (receivables_t / rev_t) / (receivables_p / rev_p)

    # GMI — inverse gross margin index
    gmi = (gm_p / gm_t) if gm_t and gm_p else 1.0

    # AQI — Asset Quality Index (proxy: 1 - current_assets/total_assets)
    ca_t = bal_t.get("current_assets") or 0
    ca_p = bal_p.get("current_assets") or 0
    aqi = 1.0
    if ta_t and ta_p and ta_t > 0 and ta_p > 0:
        nca_t = 1 - ca_t / ta_t
        nca_p = 1 - ca_p / ta_p
        if nca_p:
            aqi = nca_t / nca_p

    # SGI — Sales Growth Index
    sgi = rev_t / rev_p

    # DEPI — depreciation index (use D&A / D&A + net PP&E proxy = 1)
    depi = 1.0

    # SGAI — SG&A Index (inverse)
    sgai = 1.0
    if sga_t is not None and sga_p and rev_t and rev_p:
        if sga_p / rev_p:
            sgai = (sga_t / rev_t) / (sga_p / rev_p)

    # TATA — Total Accruals to Total Assets
    tata = 0.0
    if ni_t is not None and ocf_t is not None and ta_t and ta_t > 0:
        tata = (ni_t - ocf_t) / ta_t

    # LVGI — Leverage Index
    lvgi = 1.0
    if ta_t and ta_p and ta_t > 0 and ta_p > 0:
        lt = debt_t / ta_t
        lp = debt_p / ta_p
        if lp:
            lvgi = lt / lp

    m = (
        -4.84
        + 0.920 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )
    return m
