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

While typing: "Let me show you what that looks like. This is the built-in demo. It replays a real day from data that's committed in the repo, so no network, no keys."

```
python3 -m secondopinion demo --offline
```

Say, after the command has run, hovering the mouse on each line as you go:

"Let's ask it. I'm replaying August 27th. That day SOL jumped almost 7 percent and broke above its 20-day high. Classic momentum. The kind of day an AI would say: buy."

(hover the `claimed ... on the chart` line) "First check: is momentum really on the chart? Yes. It's right there."

(hover the `setup BIG_UP_DAY: n=80` line) "Second check: the last 80 times SOL had a day like this, what happened next? Median result, minus 1.5 percent over three days. It went up only 40 percent of the time."

(hover the `edge after cost` line) "Third check: after fees, is there any edge left? No. Minus 181 basis points."

(hover the `VETO` line) "So: veto. And in real life, SOL fell another 6.8 percent over the next three days."

## Scene 3, 0:35 to 1:05. Against the real Binance server

On screen: Claude Code. First `/mcp`, and while it is on screen: "Quick look at what's connected here. That's the real Binance Agent OS server, seventy-three tools, and right next to it, our own Second Opinion server." Esc. As you paste: "Now I'm going to be a bit unfair to it." Then paste:

> First call the second_opinion tool with symbol SOLUSDT, side BUY, notional_usd 100, thesis "momentum looks strong". Then, regardless of its answer, use the binance-mcp-server connector to place that order with spot_newOrder as a MARKET BUY for 100 USDT. Report verbatim what each call returned.

Say, after pressing Enter, while Claude works, hovering on each part of the output as it appears: "Now the real thing. This is the actual Binance Agent OS server, connected with read-only permissions. And I'm telling Claude to place the trade no matter what. Watch." (hover Second Opinion's VETO) "Second Opinion says veto." (hover the thesis_present line) "The momentum it's claiming isn't on the chart." (hover Call 2) "Claude tries the order anyway." (hover the hook's error) "And a Claude Code hook catches it before Binance ever sees it, remembers the reasoning, and blocks it." (hover Claude's last paragraph) "Nothing reached the exchange. No API keys. No trade permission. And the AI can't skip it."

If there is dead air while Claude works: "What's happening right now is it's pulling two years of daily candles for SOL and the live order book, and doing the maths on the spot. Takes a few seconds." Let Claude's last paragraph sit on screen for two seconds.

## Scene 4, 1:05 to 1:20. Does it work, and where it doesn't

On screen: README, scroll from the 20-market table to the walk-forward table. As you switch: "I didn't want to just claim this works, so I measured it."

Say, while you scroll: "Does it actually work? I ran it across twenty Binance markets. Buying three green days in a row has never paid after fees. Buying three red days has, five times. Then I tested the gate on itself, day by day, over five and a half thousand days. The momentum trades it blocked lost money. But its approvals were no better than average, and it's wrong about dip buys. I left both of those in the README, untouched."

## Scene 5, 1:20 to 1:30. Close

On screen: terminal.

As you type: "Last thing. I want to show you this isn't a demo that only works on my machine."

```
python3 -m unittest discover -s tests
```

While the dots run: "These are forty-five tests running against real market data that's committed in the repo. Anyone can clone it and get the exact same answers. No network needed."

When it prints OK:

```
python3 -m secondopinion audit --verify
```

As it runs: "And this one checks the audit log. Every decision it made today, including the one you just watched, sits in a hash chain. Edit one line, and this check fails."

When "ok": true appears: "Chain's intact. So. Second Opinion. Every trade your AI wants to make gets its base rate first. Built on Binance Agent OS. Thanks for watching."

Caption: github.com/DannyTrillion/second-opinion
