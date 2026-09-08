"""
Setup taxonomy. A "setup" is a mechanically testable description of what the market
looked like on the signal bar. Thresholds are measured from the symbol's OWN trailing
history (no fixed "+5% is big" constants), and only from bars strictly before the
signal bar, so there is no lookahead.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from .indicators import percentile, returns, rsi, sma

TRAIL = 250   # bars used to measure a symbol's own percentiles
MIN_TRAIL = 60


@dataclass(frozen=True)
class SetupDef:
    key: str
    label: str
    description: str


SETUPS: List[SetupDef] = [
    SetupDef("BIG_UP_DAY", "Big up day", "Signal-bar return at or above the symbol's own trailing 90th percentile of daily returns."),
    SetupDef("BIG_DOWN_DAY", "Big down day", "Signal-bar return at or below the symbol's own trailing 10th percentile."),
    SetupDef("THREE_UP", "Three green days", "Three consecutive positive daily closes ending on the signal bar."),
    SetupDef("THREE_DOWN", "Three red days", "Three consecutive negative daily closes ending on the signal bar."),
    SetupDef("BREAKOUT_20D", "20-day breakout", "Close above the highest close of the prior 20 bars."),
    SetupDef("BREAKDOWN_20D", "20-day breakdown", "Close below the lowest close of the prior 20 bars."),
    SetupDef("RSI_OVERBOUGHT", "RSI overbought", "14-day RSI at or above 70."),
    SetupDef("RSI_OVERSOLD", "RSI oversold", "14-day RSI at or below 30."),
    SetupDef("ABOVE_SMA50", "Above 50-day average", "Close above the 50-day simple moving average (trend context)."),
    SetupDef("BELOW_SMA50", "Below 50-day average", "Close below the 50-day simple moving average (trend context)."),
]
SETUP_BY_KEY: Dict[str, SetupDef] = {s.key: s for s in SETUPS}


class SetupMatrix:
    """Precomputes, for every bar, which setups were true. Pure function of closes."""

    def __init__(self, closes: List[float]):
        self.closes = closes
        n = len(closes)
        self.ret = returns(closes)
        self.rsi14 = rsi(closes, 14)
        self.sma50 = sma(closes, 50)
        self.flags: Dict[str, List[bool]] = {s.key: [False] * n for s in SETUPS}
        self.thresholds: Dict[str, List[Optional[float]]] = {"p90": [None] * n, "p10": [None] * n}
        self._build()

    def _build(self) -> None:
        c, r, n = self.closes, self.ret, len(self.closes)
        window: List[float] = []
        for i in range(n):
            # thresholds from bars strictly before i
            if i - 1 >= 1:
                lo = max(1, i - TRAIL)
                window = sorted(x for x in r[lo:i] if x is not None)
            if len(window) >= MIN_TRAIL and r[i] is not None:
                p90 = percentile(window, 0.90)
                p10 = percentile(window, 0.10)
                self.thresholds["p90"][i] = p90
                self.thresholds["p10"][i] = p10
                self.flags["BIG_UP_DAY"][i] = r[i] >= p90
                self.flags["BIG_DOWN_DAY"][i] = r[i] <= p10
            if i >= 3 and all(r[j] is not None for j in (i, i - 1, i - 2)):
                self.flags["THREE_UP"][i] = all(r[j] > 0 for j in (i, i - 1, i - 2))
                self.flags["THREE_DOWN"][i] = all(r[j] < 0 for j in (i, i - 1, i - 2))
            if i >= 20:
                prior = c[i - 20:i]
                self.flags["BREAKOUT_20D"][i] = c[i] > max(prior)
                self.flags["BREAKDOWN_20D"][i] = c[i] < min(prior)
            v = self.rsi14[i]
            if v is not None:
                self.flags["RSI_OVERBOUGHT"][i] = v >= 70.0
                self.flags["RSI_OVERSOLD"][i] = v <= 30.0
            m = self.sma50[i]
            if m is not None:
                self.flags["ABOVE_SMA50"][i] = c[i] > m
                self.flags["BELOW_SMA50"][i] = c[i] < m

    def active_at(self, i: int) -> List[str]:
        return [s.key for s in SETUPS if self.flags[s.key][i]]

    def snapshot(self, i: int) -> Dict[str, Optional[float]]:
        return {
            "close": self.closes[i],
            "ret_1d": self.ret[i],
            "rsi14": self.rsi14[i],
            "sma50": self.sma50[i],
            "p90_daily_ret": self.thresholds["p90"][i],
            "p10_daily_ret": self.thresholds["p10"][i],
        }
