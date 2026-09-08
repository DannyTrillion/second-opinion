---
name: second-opinion
description: Before placing any Binance order, get a deterministic second opinion - is the claimed setup on the chart, what happened the last N times it appeared on this symbol, and does the edge survive fees and order-book impact. Use whenever an agent is about to call a Binance MCP order, convert, or swap tool, or whenever a user asks "should I buy/sell X".
---

# Second Opinion

You are about to propose or place a trade on Binance. Do not call an order tool until you have a Second Opinion verdict for it.

## When to use

- Any call to a `binance-mcp-server` tool that places, submits, or accepts an order, convert, or swap.
- Any user question of the form "should I buy X", "is now a good time to sell Y", "X looks strong, buy?".

## Steps

1. State the trade as `symbol`, `side`, `notional_usd`, and your `thesis` in plain words (for example "momentum after today's breakout" or "buying the dip after three red days").
2. Call the `second_opinion` tool with exactly those four fields. It returns `APPROVE`, `CAUTION`, or `VETO` with every number behind it.
3. Read the `thesis_present` check first. If it failed, your rationale is not on the chart. Say so to the user in one sentence and do not place the trade.
4. Read `primary` (the setup and its base rate: n, median forward return, hit rate, 95% interval) and `edge_after_cost_bps`.
5. Act on the verdict:
   - `VETO`: do not place the order. Tell the user the setup, n, median, hit rate, and edge after cost, in one or two sentences.
   - `CAUTION`: present the numbers and ask the user to confirm explicitly. Placing the order still goes through Binance's own confirm-before-execute step.
   - `APPROVE`: proceed to the Binance order tool and quote the receipt line (setup, n, median, edge) in your confirmation message.
6. Never restate a base rate as a prediction. Say "the last 80 times" not "it will".

## Other tools

- `base_rates(symbol)`: which setups are active today and what each has paid on this symbol.
- `cost_estimate(symbol, notional_usd)`: fees plus order-book impact for a size.
- `list_setups()`: the setup definitions and the thesis words that map to each.
- `audit_log()`: recent decisions and whether the hash chain verifies.

## Install

MCP server: `claude mcp add second-opinion --env PYTHONPATH=/path/to/second-opinion -- python3 -m secondopinion serve`
Claude Code hook (cannot be skipped): `python3 -m secondopinion install-hook --apply`
