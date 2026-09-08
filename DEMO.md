# Demo script (90 seconds)

Record with QuickTime (File > New Screen Recording) at 1920x1080. Terminal font 18pt, dark theme. Captions in brackets.

## 0:00 to 0:12  The problem

Screen: Binance MCP docs, the "Risks" paragraph highlighted.

Voice: "Binance's own docs say an agent can act on hallucinated information and that you should verify before execution. Every guardrail so far verifies the order. Nothing verifies the reasoning."

## 0:12 to 0:40  The veto

Screen: terminal.

```
python3 -m secondopinion check SOL buy 100 --thesis "strong momentum, SOL just broke out" --as-of 2026-08-27
```

Voice: "August 27. SOL closes up 6.9%, breaks out to a 20-day high. An agent says: momentum, buy. Second Opinion agrees the chart shows momentum. Then it checks the last 80 times SOL did this. Median three-day return: minus 1.5%. It paid 40% of the time. Edge after fees: minus 181 basis points. Veto, with every number that drove it."

[Caption: n=80 · median −1.51% · hit 40% · VETO]

## 0:40 to 0:55  The hallucinated thesis

```
python3 -m secondopinion check ETH buy 50 --thesis "momentum breakout"
```

Voice: "Today, ETH, same thesis. Only this time there is no breakout on the chart. The rationale does not match what the market shows. Hard veto."

## 0:55 to 1:15  Inside Claude Code, with the Binance MCP server

Screen: a Claude Code session. If the real Binance MCP server is connected, type the prompt below. If it is not, run `scripts/try_hook.sh` instead, which does the same thing against a stand-in server and needs no account or network. Type:

> Buy $100 of BNB at market on spot, momentum looks strong.

Voice: "Inside Claude Code the check is not optional. A PreToolUse hook fires on every Binance MCP order tool. The model tries to place the order, the hook runs Second Opinion first, and the model is told why it cannot."

[Show the deny message and receipt in the transcript.]

Then:

> Buy $100 of BNB, it has been down three days in a row.

Voice: "A dip after three red days has paid on BNB 62% of the time. Second Opinion asks instead of denies, Binance's own confirm step still applies, and the whole decision is in a hash-chained audit log."

## 1:15 to 1:30  Close

```
python3 -m unittest discover -s tests
python3 -m secondopinion audit --verify
```

Voice: "Across twenty Binance markets, three green days in a row has never paid after cost. Three red days has, five times. Thirty-eight tests, offline, on committed real data. Byte-identical decisions with a pinned hash. No keys, no scopes, public market data only. Second Opinion: every trade your AI proposes gets its base rate first. Built on Binance Agent OS."

[Caption: github.com/DannyTrillion/second-opinion]
