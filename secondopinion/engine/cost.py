"""
Round-trip cost: what it really costs to get in and back out.
fee (both legs) + order-book impact (both legs), measured against mid.
"""
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

DEFAULT_TAKER_FEE = 0.001       # 0.10% Binance spot default
BNB_DISCOUNT_FEE = 0.00075      # 25% discount when paying fees in BNB
ASSUMED_IMPACT_BPS = 5.0        # used only when no order book is available


@dataclass
class CostEstimate:
    notional_usd: float
    mid: Optional[float]
    spread_bps: Optional[float]
    buy_impact_bps: Optional[float]
    sell_impact_bps: Optional[float]
    fee_bps_per_leg: float
    round_trip_bps: float
    book_depth_usd_within_50bps: Optional[float]
    impact_source: str            # "orderbook" | "assumed"
    fill_covered: bool            # False if the visible book could not absorb the size

    def to_dict(self) -> Dict:
        return asdict(self)


def _walk(levels: List[List[str]], notional: float) -> Tuple[Optional[float], bool]:
    """Average fill price for `notional` quote units walking price levels [[price, qty], ...]."""
    remaining = notional
    cost = 0.0
    qty_total = 0.0
    for p_s, q_s in levels:
        p, q = float(p_s), float(q_s)
        level_notional = p * q
        take = min(level_notional, remaining)
        qty = take / p
        cost += take
        qty_total += qty
        remaining -= take
        if remaining <= 1e-9:
            break
    if qty_total == 0:
        return None, False
    return cost / qty_total, remaining <= 1e-9


def depth_within(levels: List[List[str]], mid: float, bps: float, side: str) -> float:
    lim = mid * (1 + bps / 1e4) if side == "ask" else mid * (1 - bps / 1e4)
    total = 0.0
    for p_s, q_s in levels:
        p, q = float(p_s), float(q_s)
        if (side == "ask" and p <= lim) or (side == "bid" and p >= lim):
            total += p * q
        else:
            break
    return total


def estimate_cost(notional_usd: float, book: Optional[Dict], fee_rate: float = DEFAULT_TAKER_FEE) -> CostEstimate:
    fee_bps = fee_rate * 1e4
    if not book or not book.get("bids") or not book.get("asks"):
        return CostEstimate(notional_usd, None, None, None, None, fee_bps,
                            2 * fee_bps + 2 * ASSUMED_IMPACT_BPS, None, "assumed", True)
    best_bid = float(book["bids"][0][0])
    best_ask = float(book["asks"][0][0])
    mid = (best_bid + best_ask) / 2.0
    spread_bps = (best_ask - best_bid) / mid * 1e4
    buy_avg, buy_ok = _walk(book["asks"], notional_usd)
    sell_avg, sell_ok = _walk(book["bids"], notional_usd)
    buy_imp = (buy_avg / mid - 1.0) * 1e4 if buy_avg else None
    sell_imp = (1.0 - sell_avg / mid) * 1e4 if sell_avg else None
    covered = bool(buy_ok and sell_ok)
    imp_total = (buy_imp or ASSUMED_IMPACT_BPS) + (sell_imp or ASSUMED_IMPACT_BPS)
    depth50 = depth_within(book["asks"], mid, 50.0, "ask") + depth_within(book["bids"], mid, 50.0, "bid")
    return CostEstimate(notional_usd, mid, spread_bps, buy_imp, sell_imp, fee_bps,
                        2 * fee_bps + imp_total, depth50, "orderbook", covered)
