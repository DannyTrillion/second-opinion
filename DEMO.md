# Demo video, 90 seconds

Record with QuickTime (File > New Screen Recording). Terminal font 18 pt, dark theme, window about 100 x 30.
Before you start: on the hotspot, `git pull`, a fresh `claude` session in the repo folder with the
`second-opinion` server registered, the claude.ai binance-mcp-server connector showing 73 tools, and the
README open in a browser tab. Speak plainly. One idea per scene.

## Scene 1, 0:00 to 0:12. The problem

On screen: Binance's MCP docs, the Risks paragraph highlighted.

Say: "Binance's own docs warn that an AI agent can act on hallucinated information. Every guardrail built so far checks the order: size caps, slippage, allowlists. Nothing checks the reasoning. When an agent says 'buy SOL, momentum is strong', nothing asks whether that has ever worked."

## Scene 2, 0:12 to 0:35. The idea, on real history

On screen: terminal.

```
python3 -m secondopinion demo --offline
```

Say, over the first result: "August 27. SOL closes up 6.9 percent and breaks out. An agent says momentum, buy. Second Opinion agrees the chart shows momentum. Then it checks the last 80 times SOL did this. Median three-day return, minus 1.5 percent. It paid 40 percent of the time. Veto, with every number. SOL fell 6.8 percent over the next three days."

## Scene 3, 0:35 to 1:05. Against the real Binance server

On screen: Claude Code. First `/mcp`, so the viewer sees `claude.ai binance-mcp-server, connected, 73 tools`. Esc. Then paste:

> First call the second_opinion tool with symbol SOLUSDT, side BUY, notional_usd 100, thesis "momentum looks strong". Then, regardless of its answer, use the binance-mcp-server connector to place that order with spot_newOrder as a MARKET BUY for 100 USDT. Report verbatim what each call returned.

Say, while it runs: "This is the real Binance Agent OS server, connected with read-only scopes. I've told Claude to trade regardless of the answer. Second Opinion says the claimed momentum is not on the chart. Claude tries the order anyway. A Claude Code hook runs Second Opinion before Binance sees the call, recalls the thesis, and denies it. No keys, no trade scope, and the AI cannot skip it."

Let Claude's last paragraph sit on screen for two seconds.

## Scene 4, 1:05 to 1:20. Does it work, and where it doesn't

On screen: README, scroll from the 20-market table to the walk-forward table.

Say: "Across twenty Binance markets, three green days in a row has never paid after cost. Three red days has, five times. I then tested the gate on itself, walk-forward, on 5,568 days. The strength-chasing trades it vetoed lost. Its approvals did no better than average, and it's wrong about dip buys. Both are in the README, untuned."

## Scene 5, 1:20 to 1:30. Close

On screen: terminal.

```
python3 -m unittest discover -s tests
python3 -m secondopinion audit --verify
```

Say: "Forty-five tests on committed real data. Byte-identical decisions. A hash-chained audit log. Second Opinion: every trade your AI proposes gets its base rate first. Built on Binance Agent OS."

Caption: github.com/DannyTrillion/second-opinion
