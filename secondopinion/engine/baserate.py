"""
Base rates: what actually happened after this setup, on this symbol, over its history.

Forward return for horizon h at signal bar i = close[i+h] / close[i] - 1 (enter at the
signal close, hold h completed bars). Bootstrap confidence intervals use a fixed seed so
the same data always yields the same numbers.
"""
import random
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from .indicators import median, percentile
from .setups import SetupMatrix, SETUPS

BOOT_N = 1000
SEED = 42


@dataclass
class BaseRate:
    setup: str
    horizon_days: int
    n: int
    median_fwd: Optional[float]
    mean_fwd: Optional[float]
    hit_rate: Optional[float]          # share of forward returns > 0
    p10_fwd: Optional[float]
    p90_fwd: Optional[float]
    ci95_median_low: Optional[float]
    ci95_median_high: Optional[float]
    last_seen_index: Optional[int]

    def to_dict(self) -> Dict:
        return asdict(self)


def _bootstrap_median_ci(vals: List[float], seed: int = SEED, b: int = BOOT_N) -> (float, float):
    rng = random.Random(seed)
    n = len(vals)
    meds = []
    for _ in range(b):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        meds.append(median(sample))
    meds.sort()
    return percentile(meds, 0.025), percentile(meds, 0.975)


def forward_returns(closes: List[float], idx: List[int], h: int) -> List[float]:
    out = []
    last = len(closes) - 1
    for i in idx:
        if i + h <= last:
            out.append(closes[i + h] / closes[i] - 1.0)
    return out


def base_rate_for(closes: List[float], idx: List[int], setup: str, h: int) -> BaseRate:
    fr = forward_returns(closes, idx, h)
    n = len(fr)
    if n == 0:
        return BaseRate(setup, h, 0, None, None, None, None, None, None, None, idx[-1] if idx else None)
    s = sorted(fr)
    lo, hi = _bootstrap_median_ci(fr) if n >= 5 else (s[0], s[-1])
    return BaseRate(
        setup=setup, horizon_days=h, n=n,
        median_fwd=median(fr), mean_fwd=sum(fr) / n,
        hit_rate=sum(1 for x in fr if x > 0) / n,
        p10_fwd=percentile(s, 0.10), p90_fwd=percentile(s, 0.90),
        ci95_median_low=lo, ci95_median_high=hi,
        last_seen_index=idx[-1],
    )


def all_base_rates(matrix: SetupMatrix, h: int, upto: Optional[int] = None) -> Dict[str, BaseRate]:
    """Base rate for every setup, using signal bars <= upto (default: all completed bars)."""
    closes = matrix.closes
    upto = len(closes) - 1 if upto is None else upto
    out: Dict[str, BaseRate] = {}
    # unconditional baseline: every bar that has a forward window
    out["ALL_DAYS"] = base_rate_for(closes, list(range(0, upto + 1)), "ALL_DAYS", h)
    for s in SETUPS:
        idx = [i for i in range(0, upto + 1) if matrix.flags[s.key][i]]
        out[s.key] = base_rate_for(closes, idx, s.key, h)
    return out
