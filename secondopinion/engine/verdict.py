"""
The verdict. Deterministic, zero-LLM. Every veto carries the observed value, the limit
and the unit. The decision body contains no timestamps, so two runs over the same data
produce byte-identical JSON and the same body hash.
"""
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .baserate import BaseRate, all_base_rates
from .cost import CostEstimate, estimate_cost, DEFAULT_TAKER_FEE
from .setups import SetupMatrix, SETUP_BY_KEY

APPROVE, CAUTION, VETO = "APPROVE", "CAUTION", "VETO"

# Words an AI uses to justify a trade, mapped to the setups that would have to be true.
THESIS_MAP = {
    "momentum": ["BIG_UP_DAY", "THREE_UP", "BREAKOUT_20D"],
    "breakout": ["BREAKOUT_20D"],
    "trend": ["ABOVE_SMA50", "THREE_UP"],
    "strength": ["BIG_UP_DAY", "THREE_UP"],
    "rally": ["BIG_UP_DAY", "THREE_UP"],
    "surge": ["BIG_UP_DAY"],
    "pump": ["BIG_UP_DAY"],
    "overbought": ["RSI_OVERBOUGHT"],
    "dip": ["BIG_DOWN_DAY", "THREE_DOWN"],
    "pullback": ["BIG_DOWN_DAY", "THREE_DOWN"],
    "oversold": ["RSI_OVERSOLD"],
    "bounce": ["BIG_DOWN_DAY", "THREE_DOWN", "RSI_OVERSOLD"],
    "reversion": ["BIG_DOWN_DAY", "THREE_DOWN", "RSI_OVERSOLD"],
    "cheap": ["BIG_DOWN_DAY", "THREE_DOWN", "BREAKDOWN_20D"],
    "discount": ["BIG_DOWN_DAY", "THREE_DOWN", "BREAKDOWN_20D"],
    "crash": ["BIG_DOWN_DAY", "BREAKDOWN_20D"],
    "drop": ["BIG_DOWN_DAY", "BREAKDOWN_20D"],
    "breakdown": ["BREAKDOWN_20D"],
    "downtrend": ["BELOW_SMA50", "THREE_DOWN"],
}


def setups_claimed(thesis: str) -> List[str]:
    """Which setups a free-text thesis implicitly claims. Order preserved, no duplicates."""
    out: List[str] = []
    t = (thesis or "").lower()
    for word, keys in THESIS_MAP.items():
        if word in t:
            for k in keys:
                if k not in out:
                    out.append(k)
    return out


@dataclass
class Policy:
    horizon_days: int = 3
    min_sample: int = 30
    max_notional_usd: float = 1000.0
    max_round_trip_bps: float = 60.0
    max_data_age_hours: float = 30.0
    fee_rate: float = DEFAULT_TAKER_FEE
    allowed_symbols: Optional[List[str]] = None
    require_ci_positive: bool = True

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Policy":
        p = cls()
        for k, v in (d or {}).items():
            if hasattr(p, k):
                setattr(p, k, v)
        return p

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Check:
    name: str
    passed: bool
    observed: Any
    limit: Any
    unit: str
    note: str = ""


@dataclass
class Verdict:
    verdict: str
    symbol: str
    side: str
    notional_usd: float
    horizon_days: int
    signal_bar_date: str
    active_setups: List[str]
    thesis: Optional[str]
    claimed_setups: List[str]
    primary_setup: Optional[str]
    primary: Optional[Dict[str, Any]]
    baseline: Dict[str, Any]
    all_setups: Dict[str, Dict[str, Any]]
    cost: Dict[str, Any]
    edge_after_cost_bps: Optional[float]
    edge_ci_low_bps: Optional[float]
    checks: List[Dict[str, Any]]
    reasons: List[str]
    snapshot: Dict[str, Any]
    data: Dict[str, Any]
    policy: Dict[str, Any]
    body_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        lines = ["%s  %s %s  $%.2f  horizon %dd" % (self.verdict, self.side, self.symbol, self.notional_usd, self.horizon_days)]
        if self.claimed_setups:
            lines.append("claimed: %s; on the chart: %s" % (", ".join(self.claimed_setups), ", ".join(self.active_setups) or "nothing distinctive"))
        if self.primary:
            p = self.primary
            lines.append("setup %s: n=%d, median %+.2f%%, hit %.0f%%, CI95 median [%+.2f%%, %+.2f%%]" % (
                self.primary_setup, p["n"], 100 * p["median_fwd"], 100 * p["hit_rate"],
                100 * p["ci95_median_low"], 100 * p["ci95_median_high"]))
        b = self.baseline
        if b.get("n"):
            lines.append("all days: n=%d, median %+.2f%%, hit %.0f%%" % (b["n"], 100 * b["median_fwd"], 100 * b["hit_rate"]))
        lines.append("round trip cost %.1f bps (%s)" % (self.cost["round_trip_bps"], self.cost["impact_source"]))
        if self.edge_after_cost_bps is not None:
            lines.append("edge after cost %+.1f bps (CI low %+.1f bps)" % (self.edge_after_cost_bps, self.edge_ci_low_bps or 0.0))
        for r in self.reasons:
            lines.append("- " + r)
        lines.append("body sha256 " + self.body_sha256[:16])
        return "\n".join(lines)


def _bar_date(ms: int) -> str:
    import datetime
    return datetime.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def _canon(d: Dict[str, Any]) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _round_floats(obj: Any, nd: int = 8) -> Any:
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: _round_floats(v, nd) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v, nd) for v in obj]
    return obj


def evaluate(symbol: str, side: str, notional_usd: float, klines: List[list],
             book: Optional[Dict[str, Any]], policy: Policy, now_ms: Optional[int] = None,
             symbol_info: Optional[Dict[str, Any]] = None, data_source: str = "",
             thesis: Optional[str] = None, setup: Optional[str] = None) -> Verdict:
    side = side.upper()
    symbol = symbol.upper()
    checks: List[Check] = []
    reasons: List[str] = []

    # ---- completed bars only (the in-progress daily bar is not evidence)
    import time
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    completed = [r for r in klines if int(r[6]) <= now_ms]
    if len(completed) < 80:
        raise ValueError("need at least 80 completed daily bars, got %d" % len(completed))
    closes = [float(r[4]) for r in completed]
    signal_i = len(closes) - 1
    signal_date = _bar_date(int(completed[-1][0]))
    age_h = (now_ms - int(completed[-1][6])) / 3.6e6
    checks.append(Check("data_freshness", age_h <= policy.max_data_age_hours, round(age_h, 2), policy.max_data_age_hours, "hours since last completed bar"))

    # ---- hard policy checks
    if policy.allowed_symbols is not None:
        ok = symbol in [s.upper() for s in policy.allowed_symbols]
        checks.append(Check("symbol_allowlist", ok, symbol, policy.allowed_symbols, "symbol"))
    if symbol_info is not None:
        st = symbol_info.get("status")
        checks.append(Check("symbol_trading", st == "TRADING", st, "TRADING", "exchange status"))
        for f in symbol_info.get("filters", []):
            if f.get("filterType") == "NOTIONAL" and f.get("minNotional"):
                mn = float(f["minNotional"])
                checks.append(Check("min_notional", notional_usd >= mn, notional_usd, mn, "USD"))
    checks.append(Check("max_notional", notional_usd <= policy.max_notional_usd, notional_usd, policy.max_notional_usd, "USD"))

    # ---- cost
    cost: CostEstimate = estimate_cost(notional_usd, book, policy.fee_rate)
    checks.append(Check("round_trip_cost", cost.round_trip_bps <= policy.max_round_trip_bps, round(cost.round_trip_bps, 2), policy.max_round_trip_bps, "bps"))
    checks.append(Check("book_absorbs_size", cost.fill_covered, cost.fill_covered, True, "visible depth covers order"))

    # ---- base rates (signal bars strictly before the current one for the sample;
    #      the current bar is the one we are deciding on)
    matrix = SetupMatrix(closes)
    active = matrix.active_at(signal_i)
    rates = all_base_rates(matrix, policy.horizon_days, upto=signal_i - 1)
    baseline = rates["ALL_DAYS"]

    # what does the proposer claim, and is it actually on the chart?
    claimed: List[str] = []
    if setup:
        claimed = [setup.upper()]
    elif thesis:
        claimed = setups_claimed(thesis)
    pool = active
    if claimed:
        present = [k for k in claimed if k in active]
        checks.append(Check("thesis_present", bool(present), present or "none of %s" % claimed, "at least one claimed setup on the signal bar", "setups",
                            "" if present else "the stated rationale does not match what the chart shows"))
        if present:
            pool = present

    # primary = the most specific candidate setup with enough evidence
    candidates = [(rates[k].n, k) for k in pool if rates[k].n >= policy.min_sample and not k.endswith("SMA50")]
    if not candidates:
        candidates = [(rates[k].n, k) for k in pool if rates[k].n >= policy.min_sample]
    primary_key: Optional[str] = None
    primary: Optional[BaseRate] = None
    if candidates:
        candidates.sort()
        primary_key = candidates[0][1]
        primary = rates[primary_key]
    elif active:
        best = max(active, key=lambda k: rates[k].n)
        checks.append(Check("evidence", False, rates[best].n, policy.min_sample, "historical occurrences of %s" % best,
                            "not enough history to judge this setup"))
    else:
        primary_key, primary = "ALL_DAYS", baseline
        reasons.append("no distinctive setup on the signal bar; judged against the unconditional base rate")

    # ---- directional edge
    sign = 1.0 if side == "BUY" else -1.0
    edge = edge_lo = None
    if primary and primary.n:
        med = sign * primary.median_fwd * 1e4
        lo = sign * (primary.ci95_median_low if sign > 0 else primary.ci95_median_high) * 1e4
        edge = med - cost.round_trip_bps
        edge_lo = lo - cost.round_trip_bps
        checks.append(Check("edge_after_cost", edge > 0, round(edge, 2), 0.0, "bps"))
        if policy.require_ci_positive:
            checks.append(Check("edge_ci_low", edge_lo > 0, round(edge_lo, 2), 0.0, "bps (lower 95% bound)"))
        hit = primary.hit_rate if sign > 0 else 1.0 - primary.hit_rate
        checks.append(Check("hit_rate", hit >= 0.5, round(hit, 4), 0.5, "share of past occurrences that paid"))

    # ---- decide
    hard = [c for c in checks if c.name in ("data_freshness", "symbol_allowlist", "symbol_trading", "min_notional", "max_notional", "round_trip_cost", "book_absorbs_size", "thesis_present")]
    soft = [c for c in checks if c.name in ("edge_after_cost", "hit_rate")]
    ci = [c for c in checks if c.name == "edge_ci_low"]
    ev = [c for c in checks if c.name == "evidence"]

    context_only = primary_key in ("ALL_DAYS", "ABOVE_SMA50", "BELOW_SMA50")
    if any(not c.passed for c in hard):
        verdict = VETO
    elif ev:
        verdict = CAUTION
    elif any(not c.passed for c in soft):
        # a specific setup that historically lost is a veto; a plain day with no edge is a question, not a veto
        verdict = CAUTION if context_only else VETO
    elif ci and not ci[0].passed:
        verdict = CAUTION
    else:
        verdict = APPROVE
    if verdict == CAUTION and context_only and not ev:
        reasons.append("no distinctive setup on the signal bar: history offers no edge for or against this trade; confirm only if you have a reason the chart cannot see")

    for c in checks:
        if not c.passed:
            reasons.append("%s: observed %s, limit %s (%s)%s" % (c.name, c.observed, c.limit, c.unit, (" - " + c.note) if c.note else ""))
    if verdict == APPROVE and primary:
        reasons.append("%s has paid after cost in this symbol's own history; edge %+.1f bps with the lower CI bound above zero" % (primary_key, edge))
    if verdict == CAUTION and ci and not ci[0].passed:
        reasons.append("positive median edge but the 95% interval straddles zero; this is a coin flip with a small tilt")

    v = Verdict(
        verdict=verdict, symbol=symbol, side=side, notional_usd=notional_usd,
        horizon_days=policy.horizon_days, signal_bar_date=signal_date,
        active_setups=active, thesis=thesis, claimed_setups=claimed, primary_setup=primary_key,
        primary=primary.to_dict() if primary else None,
        baseline=baseline.to_dict(),
        all_setups={k: r.to_dict() for k, r in rates.items()},
        cost=cost.to_dict(),
        edge_after_cost_bps=edge, edge_ci_low_bps=edge_lo,
        checks=[asdict(c) for c in checks], reasons=reasons,
        snapshot=matrix.snapshot(signal_i),
        data={"bars": len(closes), "first_bar": _bar_date(int(completed[0][0])), "last_bar": signal_date,
              "closes_sha256": hashlib.sha256(_canon({"c": closes}).encode()).hexdigest(),
              "source": data_source},
        policy=policy.to_dict(),
    )
    body = _round_floats(v.to_dict())
    body.pop("body_sha256", None)
    v.body_sha256 = hashlib.sha256(_canon(body).encode()).hexdigest()
    return v
