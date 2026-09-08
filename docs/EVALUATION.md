# Does the gate work? A walk-forward evaluation

Every day from bar 300 onward, for each symbol, Second Opinion judged a $100 BUY at that day's close using only the bars available on that day. The realized return over the next 3 completed bars is then recorded. This is out of sample by construction: the base rates that drove each verdict were computed from bars strictly before the signal bar, and the outcome was not known when the verdict was made. No order book exists for the past, so every day carries the same assumed 30 bps round-trip cost. The same `evaluate` function used by the CLI, the MCP server and the hook produced every verdict. Regenerate with `python3 -m secondopinion evaluate`.

Fixtures: daily bars through 2026-09-04.

Symbols: AVAXUSDT, BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, LINKUSDT, SOLUSDT, XRPUSDT. Days judged: 5568.

## All days, pooled

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 109 | -0.04% | -0.32% | 50% | -0.62% |
| CAUTION | 4499 | +0.07% | +0.25% | 50% | -0.05% |
| VETO | 960 | -0.35% | +0.23% | 47% | -0.07% |
| every day (no gate) | 5568 | +0.00% | +0.24% | 50% | -0.06% |

## Days with a specific setup on the chart

Plain trend-context days are excluded here. These are the days an AI would point at and say 'momentum' or 'dip', and where the gate makes a real call.

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 109 | -0.04% | -0.32% | 50% | -0.62% |
| CAUTION | 1371 | +0.38% | +0.49% | 53% | +0.19% |
| VETO | 960 | -0.35% | +0.23% | 47% | -0.07% |

## What the gate changed

Strength setups: BIG_UP_DAY, THREE_UP, BREAKOUT_20D, RSI_OVERBOUGHT. Weakness setups: BIG_DOWN_DAY, THREE_DOWN, BREAKDOWN_20D, RSI_OVERSOLD.

| slice | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| every specific-setup day, no gate | 2440 | +0.08% | +0.35% | 51% | +0.05% |
| specific-setup days the gate did not veto | 1480 | +0.33% | +0.43% | 53% | +0.13% |
| vetoes on strength setups (chasing) | 742 | -0.68% | +0.10% | 45% | -0.20% |
| vetoes on weakness setups (dip buys) | 218 | +0.47% | +0.67% | 55% | +0.37% |
| all strength days | 1242 | -0.56% | +0.18% | 46% | -0.12% |
| all weakness days | 1198 | +0.54% | +0.53% | 55% | +0.23% |

## By primary setup and verdict

| setup | verdict | days | median gross | mean gross | hit rate | mean net |
|---|---|---|---|---|---|---|
| ABOVE_SMA50 | CAUTION | 1395 | +0.10% | +0.70% | 51% | +0.40% |
| BELOW_SMA50 | CAUTION | 1733 | -0.17% | -0.30% | 48% | -0.60% |
| BIG_DOWN_DAY | APPROVE | 10 | -2.06% | -3.64% | 40% | -3.94% |
| BIG_DOWN_DAY | CAUTION | 180 | +0.82% | +0.23% | 57% | -0.07% |
| BIG_DOWN_DAY | VETO | 149 | +0.42% | +0.72% | 54% | +0.42% |
| BIG_UP_DAY | CAUTION | 40 | -2.51% | -1.29% | 40% | -1.59% |
| BIG_UP_DAY | VETO | 351 | -0.85% | +0.06% | 46% | -0.24% |
| BREAKDOWN_20D | APPROVE | 42 | -0.03% | -0.59% | 50% | -0.89% |
| BREAKDOWN_20D | CAUTION | 315 | +0.54% | +0.56% | 55% | +0.26% |
| BREAKDOWN_20D | VETO | 62 | +0.29% | +0.16% | 53% | -0.14% |
| BREAKOUT_20D | APPROVE | 8 | -0.15% | +0.65% | 50% | +0.35% |
| BREAKOUT_20D | CAUTION | 111 | -1.48% | +0.24% | 41% | -0.06% |
| BREAKOUT_20D | VETO | 155 | +0.00% | +1.02% | 50% | +0.72% |
| RSI_OVERBOUGHT | APPROVE | 31 | +0.83% | +0.56% | 55% | +0.26% |
| RSI_OVERBOUGHT | CAUTION | 163 | -0.13% | +0.95% | 50% | +0.65% |
| RSI_OVERBOUGHT | VETO | 28 | +1.05% | +2.52% | 64% | +2.22% |
| RSI_OVERSOLD | CAUTION | 24 | +1.32% | -0.05% | 58% | -0.35% |
| THREE_DOWN | APPROVE | 18 | -0.50% | +0.21% | 44% | -0.09% |
| THREE_DOWN | CAUTION | 391 | +0.56% | +0.84% | 57% | +0.54% |
| THREE_DOWN | VETO | 7 | +5.07% | +4.15% | 86% | +3.85% |
| THREE_UP | CAUTION | 147 | +0.11% | +0.01% | 52% | -0.29% |
| THREE_UP | VETO | 208 | -1.41% | -0.84% | 39% | -1.14% |

## Per symbol

### AVAXUSDT (696 days)

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 0 | | | | |
| CAUTION | 515 | -0.45% | -0.35% | 46% | -0.65% |
| VETO | 181 | -0.11% | +0.14% | 48% | -0.16% |

### BNBUSDT (696 days)

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 1 | -1.32% | -1.32% | 0% | -1.62% |
| CAUTION | 589 | +0.39% | +0.24% | 55% | -0.06% |
| VETO | 106 | +0.10% | +0.10% | 53% | -0.20% |

### BTCUSDT (696 days)

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 12 | -1.99% | -1.60% | 42% | -1.90% |
| CAUTION | 571 | +0.44% | +0.38% | 55% | +0.08% |
| VETO | 113 | -0.35% | -0.55% | 48% | -0.85% |

### DOGEUSDT (696 days)

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 0 | | | | |
| CAUTION | 590 | -0.59% | +0.12% | 46% | -0.18% |
| VETO | 106 | -0.30% | +1.21% | 49% | +0.91% |

### ETHUSDT (696 days)

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 29 | +1.02% | +1.27% | 59% | +0.97% |
| CAUTION | 548 | +0.22% | +0.45% | 52% | +0.15% |
| VETO | 119 | -1.65% | -1.12% | 43% | -1.42% |

### LINKUSDT (696 days)

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 15 | -0.96% | -0.86% | 40% | -1.16% |
| CAUTION | 484 | +0.22% | +0.43% | 51% | +0.13% |
| VETO | 197 | -0.64% | +0.33% | 48% | +0.03% |

### SOLUSDT (696 days)

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 19 | +0.02% | -0.62% | 53% | -0.92% |
| CAUTION | 619 | +0.16% | +0.14% | 51% | -0.16% |
| VETO | 58 | -0.85% | -0.11% | 45% | -0.41% |

### XRPUSDT (696 days)

| verdict | days | median gross | mean gross | hit rate | mean net of 30 bps |
|---|---|---|---|---|---|
| APPROVE | 33 | -0.11% | -0.81% | 48% | -1.11% |
| CAUTION | 583 | -0.47% | +0.59% | 47% | +0.29% |
| VETO | 80 | -1.01% | +2.44% | 44% | +2.14% |

## How to read this

- A gate is useful if vetoed days did worse than approved days out of sample. Compare the VETO and APPROVE rows on the specific-setup table; that is the whole test.
- Base rates are not predictions. The numbers above are what happened over this window on these symbols, and a different window can look different.
- BUY only. The gate judges sells with the sign flipped, but an AI proposing longs is the common case and the one this table measures.
