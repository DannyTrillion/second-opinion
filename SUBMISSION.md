# Track A submission

Quote-repost https://x.com/binance/status/2094810011557838988 with the video attached and this text:

---

Track A submission: Second Opinion, a deterministic adversary for AI trading agents on @Binance Agent OS.

The problem: every guardrail verifies the order. None verifies the reasoning. When an agent says "buy SOL, momentum is strong," nothing checks whether that setup has ever paid.

Second Opinion does, before the Binance MCP server executes:

• Is the claimed setup actually on the chart? If not, hallucinated thesis, hard veto.
• What happened the last N times this setup appeared on this symbol? Median, hit rate, sample size, 95% CI, no lookahead.
• Does the edge survive fees plus live order-book impact, both legs?

Real example, replayed on 27 Aug: SOL +6.9%, 20-day breakout, agent says momentum. Last 80 times: median 3-day return −1.5%, paid 40% of the time. Veto, with the numbers.

Agent OS both ways: an MCP server any client can call, and a Claude Code hook that fires on every binance-mcp-server order tool so the check cannot be skipped. Fail closed. Approved orders still hit Binance's confirm-before-execute.

Measured, not predicted. 35 offline tests on committed real data, byte-identical decisions with a pinned hash, hash-chained audit log. No keys, no scopes, public data only.

Code: https://github.com/DannyTrillion/second-opinion

#BinanceAgentOS #AgentOS #MCP

---

Then complete the survey: https://www.binance.com/en/survey/2913aa200aac462c89a737779393f3d4
Choose Track A, paste the quote-post link, use your main-account UID.
