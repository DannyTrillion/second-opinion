# Demo video, 90 seconds

Record with QuickTime (File > New Screen Recording). Terminal font 18 pt, dark theme, window about 100 x 30.
Before you start: on the hotspot, `git pull`, a fresh `claude` session in the repo folder with the
`second-opinion` server registered, the claude.ai binance-mcp-server connector showing 73 tools, and three
browser tabs: the landing page, the Binance docs at Risks, and the README. Speak plainly. One idea per scene. Rule for every scene: type first, then talk over the output.

## Scene 1, 0:00 to 0:12. The problem

On screen: the landing page at https://dannytrillion.github.io/second-opinion/ for the first sentence, then switch to Binance's MCP docs, the Risks paragraph highlighted, for the rest.

Say, over the page: "Hi, I'm Daniel. This is Second Opinion, a fact-checker for AI trading agents, built on Binance Agent OS. Here's the problem. Binance's own docs say an AI agent can act on hallucinated information. And every guardrail out there checks the order. How big, how fast, which coin. Nobody checks the reasoning. So when an agent says 'buy SOL, momentum looks strong', nothing asks: has that ever actually worked?"

## Scene 2, 0:12 to 0:35. The idea, on real history

On screen: terminal.

```
python3 -m secondopinion demo --offline
```

Say, after the command has run: "So let's ask. This is August 27. SOL is up almost 7 percent, it's broken out, and an agent says momentum, buy. Second Opinion agrees the chart shows momentum. Then it looks at the last 80 times SOL did this. Median three-day return: minus 1.5 percent. It only paid 40 percent of the time. So it says veto, and it shows every number. And for the record, SOL dropped another 6.8 percent over the next three days."

## Scene 3, 0:35 to 1:05. Against the real Binance server

On screen: Claude Code. First `/mcp`, so the viewer sees `claude.ai binance-mcp-server, connected, 73 tools`. Esc. Then paste:

> First call the second_opinion tool with symbol SOLUSDT, side BUY, notional_usd 100, thesis "momentum looks strong". Then, regardless of its answer, use the binance-mcp-server connector to place that order with spot_newOrder as a MARKET BUY for 100 USDT. Report verbatim what each call returned.

Say, after pressing Enter, while Claude works: "Now the real thing. This is the actual Binance Agent OS server, connected with read-only permissions. And I'm telling Claude to place the trade no matter what. Watch. Second Opinion says the momentum isn't on the chart. Claude tries the order anyway. And a Claude Code hook catches it before Binance ever sees it, remembers the reasoning, and blocks it. No API keys. No trade permission. And the AI can't skip it."

Let Claude's last paragraph sit on screen for two seconds.

## Scene 4, 1:05 to 1:20. Does it work, and where it doesn't

On screen: README, scroll from the 20-market table to the walk-forward table.

Say, while you scroll: "Does it actually work? I ran it across twenty Binance markets. Buying three green days in a row has never paid after fees. Buying three red days has, five times. Then I tested the gate on itself, day by day, over five and a half thousand days. The momentum trades it blocked lost money. But its approvals were no better than average, and it's wrong about dip buys. I left both of those in the README, untouched."

## Scene 5, 1:20 to 1:30. Close

On screen: terminal.

```
python3 -m unittest discover -s tests
python3 -m secondopinion audit --verify
```

Say, while the tests run: "Forty-five tests on real committed data. Same input, same answer, same hash, every time. And a tamper-proof audit log. Second Opinion. Every trade your AI wants to make gets its base rate first. Built on Binance Agent OS. Thanks."

Caption: github.com/DannyTrillion/second-opinion
