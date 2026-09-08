"""One entry point used by the CLI, the MCP server and the hook, so they cannot disagree."""
import datetime
from typing import Any, Dict, Optional

from . import audit
from .config import fixtures_dir, load_policy
from .data.binance import BinancePublicData, DataError
from .engine.baserate import all_base_rates
from .engine.setups import SetupMatrix, SETUPS
from .engine.verdict import Verdict, evaluate

STABLES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI")


def normalize_symbol(sym: str) -> str:
    s = "".join(ch for ch in (sym or "").upper() if ch.isalnum())
    if not s:
        return s
    quotes = STABLES + ("BTC", "ETH", "BNB", "EUR", "TRY", "BRL")
    if not any(len(s) > len(q) and s.endswith(q) for q in quotes):
        s += "USDT"
    return s


def _as_of_ms(as_of: Optional[str]) -> Optional[int]:
    if not as_of:
        return None
    d = datetime.datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    # end of that UTC day: the bar for `as_of` is the last completed one
    return int((d + datetime.timedelta(days=1)).timestamp() * 1000) - 1


def make_data(offline: bool = False) -> BinancePublicData:
    import os
    offline = offline or os.environ.get("SECOND_OPINION_OFFLINE") == "1"
    return BinancePublicData(offline=offline, fixtures_dir=fixtures_dir())


def second_opinion(symbol: str, side: str, notional_usd: float, thesis: Optional[str] = None,
                   horizon_days: Optional[int] = None, as_of: Optional[str] = None, offline: bool = False,
                   policy_path: Optional[str] = None, setup: Optional[str] = None, log: bool = True,
                   origin: str = "cli") -> Verdict:
    policy, policy_src = load_policy(policy_path)
    if horizon_days:
        policy.horizon_days = int(horizon_days)
    data = make_data(offline)
    sym = normalize_symbol(symbol)
    klines = data.klines(sym)
    ksrc = data.last_source
    now_ms = _as_of_ms(as_of)
    book = None
    if now_ms is None:  # live decision: use the live book; replays never pretend to know the book
        try:
            book = data.depth(sym)
        except DataError:
            book = None
    info = None
    try:
        info = data.exchange_info(sym)
    except DataError:
        info = None
    if now_ms is not None:
        policy.max_data_age_hours = 1e9  # replay: freshness is not the question
    v = evaluate(sym, side, float(notional_usd), klines, book, policy, now_ms=now_ms,
                 symbol_info=info, data_source="%s:%s" % (ksrc, policy_src), thesis=thesis, setup=setup)
    if log:
        audit.append({"origin": origin, "verdict": v.verdict, "symbol": v.symbol, "side": v.side,
                      "notional_usd": v.notional_usd, "primary_setup": v.primary_setup,
                      "edge_after_cost_bps": v.edge_after_cost_bps, "as_of": as_of,
                      "body_sha256": v.body_sha256, "reasons": v.reasons})
    return v


def base_rates(symbol: str, horizon_days: int = 3, as_of: Optional[str] = None, offline: bool = False) -> Dict[str, Any]:
    data = make_data(offline)
    sym = normalize_symbol(symbol)
    klines = data.klines(sym)
    now_ms = _as_of_ms(as_of)
    if now_ms is not None:
        klines = [r for r in klines if int(r[6]) <= now_ms]
    else:
        import time
        klines = [r for r in klines if int(r[6]) <= int(time.time() * 1000)]
    closes = [float(r[4]) for r in klines]
    m = SetupMatrix(closes)
    rates = all_base_rates(m, horizon_days)
    last = len(closes) - 1
    return {
        "symbol": sym, "horizon_days": horizon_days, "bars": len(closes),
        "signal_bar_date": datetime.datetime.utcfromtimestamp(int(klines[-1][0]) / 1000).strftime("%Y-%m-%d"),
        "active_setups": m.active_at(last),
        "snapshot": m.snapshot(last),
        "rates": {k: r.to_dict() for k, r in rates.items()},
        "definitions": {s.key: s.description for s in SETUPS},
    }


def cost_estimate(symbol: str, notional_usd: float, offline: bool = False) -> Dict[str, Any]:
    from .engine.cost import estimate_cost
    data = make_data(offline)
    sym = normalize_symbol(symbol)
    try:
        book = data.depth(sym)
    except DataError:
        book = None
    c = estimate_cost(float(notional_usd), book)
    d = c.to_dict()
    d["symbol"] = sym
    return d
