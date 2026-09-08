# Track A submission

Quote-repost this: https://x.com/binance/status/2094810011557838988

Attach the video to the first post. Put the poster on the second. Everything is under 280 characters so it works on a standard account. Post the lead, then reply to yourself with each of the following in order.

---

**1. Lead (attach the video)**

I built a fact-checker for AI trading agents on @binance Agent OS.

Every guardrail out there checks the order. None of them check the reasoning. When an agent says "buy SOL, momentum's strong," nothing asks: has that ever worked?

Second Opinion does. Track A entry, 90 seconds:

---

**2. The idea (attach the poster)**

It asks three questions before the exchange sees the order:

Is the setup the AI is claiming actually on the chart?
The last 80 times this coin looked like this, what happened next?
Does whatever's left survive fees and the order book?

Then: yes, maybe, or no. With every number.

---

**3. The real server**

Today I connected it to the real Binance Agent OS server, read-only, and told Claude to place the order no matter what.

Claude tried. A Claude Code hook ran Second Opinion first, found no momentum on the chart, and blocked it before Binance saw it.

Transcript's in the repo.

---

**4. The evidence**

I didn't want to just claim it works.

Across 20 Binance markets, buying three green days in a row has never paid after fees. Three red days has, five times.

Then I ran the gate over 5,568 days. The momentum trades it blocked lost. Its approvals were average. Both are in the README.

---

**5. What it's made of**

Stock Python, no dependencies, no API keys, no LLM inside. 45 tests on real data committed in the repo, so anyone gets the same answers. Every decision hash-chained.

Code: github.com/DannyTrillion/second-opinion
Site: dannytrillion.github.io/second-opinion

#BinanceAgentOS

---

Then the survey: https://www.binance.com/en/survey/2913aa200aac462c89a737779393f3d4
Track A, your main-account UID, the link to post 1.
