# Second Opinion

[![tests](https://github.com/DannyTrillion/second-opinion/actions/workflows/tests.yml/badge.svg)](https://github.com/DannyTrillion/second-opinion/actions/workflows/tests.yml)

**Every trade an AI proposes gets its base rate before Binance Agent OS executes it.**

Binance's own MCP documentation warns that an agent "can make mistakes, act on outdated or hallucinated information, or send incorrect parameters, always verify before execution." Every guardrail built so far verifies the *order*: size caps, slippage collars, symbol allowlists. Nothing verifies the *reasoning*. When an agent says "buy SOL, momentum is strong," nothing checks whether that setup has ever paid.

Second Opinion is a deterministic, zero-LLM adversary that sits between the AI and the Binance MCP server. For each proposed trade it answers three questions from real Binance history and the live order book:

1. **Is the claimed setup actually on the chart?** "Momentum" has to mean something measurable. If the rationale does not match the signal bar, that is a hallucinated thesis and a hard veto.
2. **What happened the last N times this setup appeared on this symbol?** Median forward return, hit rate, sample size, and a bootstrap 95% interval, computed from the symbol's own daily candles with no lookahead.
3. **Does the edge survive the round trip?** Taker fees both legs plus order-book impact both legs, walked against the live depth for the proposed size.

The answer is `APPROVE`, `CAUTION`, or `VETO`, and every veto prints the observed value, the limit, and the unit. Two runs on the same data produce a byte-identical decision and the same SHA-256.

Built in one day for the Binance Agent OS Mini Hackathon, Track A. Stock Python 3.9+, no dependencies.

## What it looks like

A momentum buy on SOL, replayed on 27 August 2026, the day SOL closed up 6.9% and broke out to a 20-day high:

```
$ python3 -m secondopinion check SOL buy 100 --thesis "strong momentum, SOL just broke out" --as-of 2026-08-27
VETO  BUY SOLUSDT  $100.00  horizon 3d
claimed: BIG_UP_DAY, THREE_UP, BREAKOUT_20D; on the chart: BIG_UP_DAY, BREAKOUT_20D, RSI_OVERBOUGHT, ABOVE_SMA50
setup BIG_UP_DAY: n=80, median -1.51%, hit 40%, CI95 median [-3.17%, +0.15%]
same setup by horizon (median/hit): 1d +0.21%/54%, 3d -1.51%/40%, 7d -1.23%/46%
all days: n=985, median +0.13%, hit 51%
round trip cost 30.0 bps (assumed)
edge after cost -181.2 bps (CI low -346.6 bps)
- edge_after_cost: observed -181.19, limit 0.0 (bps)
- edge_ci_low: observed -346.62, limit 0.0 (bps (lower 95% bound))
- hit_rate: observed 0.4, limit 0.5 (share of past occurrences that paid)
body sha256 b0c8b71a0b21799b
```

The chart really did show a big up day and a breakout. The problem is what followed the previous 80 of them: SOL lost a median 1.5% over the next three days and paid only 40% of the time. (What actually followed: SOL closed at $109.14 on 27 August and $101.75 three days later, -6.8%.)

A thesis that is not on the chart at all (live run on 8 September 2026):

```
$ python3 -m secondopinion check ETH buy 50 --thesis "momentum breakout"
VETO  BUY ETHUSDT  $50.00  horizon 3d
claimed: BIG_UP_DAY, THREE_UP, BREAKOUT_20D; on the chart: ABOVE_SMA50
- thesis_present: observed none of ['BIG_UP_DAY', 'THREE_UP', 'BREAKOUT_20D'], limit at least one claimed setup on the signal bar (setups) - the stated rationale does not match what the chart shows
```

And a dip buy after three red days on BTC. Three red days is the one setup with a positive median on all four majors, and it clears the cost bar with confidence on five of the twenty markets tested below:

```
$ python3 -m secondopinion check BTCUSDT buy 100 --thesis "buy the dip" --as-of 2026-08-12
CAUTION  BUY BTCUSDT  $100.00  horizon 3d
setup THREE_DOWN: n=109, median +0.96%, hit 62%, CI95 median [+0.15%, +1.80%]
same setup by horizon (median/hit): 1d +0.56%/60%, 3d +0.96%/62%, 7d +0.95%/58%
edge after cost +65.7 bps (CI low -14.8 bps)
- positive median edge but the 95% interval straddles zero; this is a coin flip with a small tilt
```

Honest output: the median edge is positive, but the lower bound of the interval is not, so Second Opinion asks rather than approves.

## What the data says, across 20 Binance markets

Running the same base rates over 20 USDT pairs (up to 1,000 daily bars each, through today) gives [docs/EVIDENCE.md](docs/EVIDENCE.md). Two findings carry the whole project:

| setup | markets where it paid after cost | markets where it reliably lost | markets tested |
| --- | --- | --- | --- |
| Three green days in a row (`THREE_UP`) | 0 | 8 | 20 |
| 20-day breakout (`BREAKOUT_20D`) | 0 | 4 | 20 |
| Big up day (`BIG_UP_DAY`) | 0 | 3 | 20 |
| Three red days in a row (`THREE_DOWN`) | 5 | 0 | 20 |

"Paid" means the lower 95% bound on the median 3-day return clears a 30 bps round trip; "lost" means the upper bound does not reach it. Chasing strength has not paid anywhere in this sample. Buying three red days has, on SOL, LINK, LTC, PEPE and TON. This is exactly the pattern an AI's language runs against: "momentum" sounds like a reason, and the record says it is the one setup to be most suspicious of.

Every receipt shows the primary setup at 1, 3 and 7 days, so a 3-day coin flip cannot hide a 7-day edge or loss:

```
setup BIG_UP_DAY: n=80, median -1.51%, hit 40%, CI95 median [-3.17%, +0.15%]
same setup by horizon (median/hit): 1d +0.21%/54%, 3d -1.51%/40%, 7d -1.23%/46%
```

## Does the gate itself work?

[docs/EVALUATION.md](docs/EVALUATION.md) is a walk-forward test: Second Opinion judged a $100 buy on every one of 5,568 days across eight symbols, using only the bars available on each day, and the realized 3-day return was recorded afterwards. No thresholds were tuned on this result. Here is what it found, including the parts that do not flatter the tool.

| days with a specific setup on the chart | days | median 3d | hit rate | mean net of 30 bps |
| --- | --- | --- | --- | --- |
| every such day, no gate | 2,440 | +0.08% | 51% | +0.05% |
| the days the gate did not veto | 1,480 | +0.33% | 53% | +0.13% |
| vetoes on strength setups (momentum, breakout, overbought) | 742 | -0.68% | 45% | -0.20% |
| vetoes on weakness setups (dips, oversold) | 218 | +0.47% | 55% | +0.37% |
| approvals | 109 | -0.04% | 50% | -0.62% |

**What works.** The gate's core job is stopping an AI from chasing strength, and out of sample that is where it is right: the 742 strength-chasing trades it vetoed lost a median 0.68% and paid 45% of the time. The 559 vetoes on big up days and three green days alone lost a median 1.13%. Filtering only by the gate's vetoes raised the median outcome of setup days from +0.08% to +0.33%.

**What does not.** `APPROVE` is not a buy signal. Only 109 of 5,568 days cleared the confidence bar, and they did no better than average, because a lower-CI-above-cost test on small samples selects flukes. Read `APPROVE` as "no objection found." And the gate is wrong when it vetoes dip buys: those 218 days went on to pay. The base-rate evidence that dips pay is stronger than the gate's per-day confidence test admits.

Both findings are left in the code and the tables rather than tuned away, because a gate that was fitted to its own evaluation would be worth nothing.

## How it plugs into Agent OS

```
   Claude Code / Claude Desktop / Cursor / Codex
        |                          |
        | tools/call               | PreToolUse hook (Claude Code)
        v                          v
   +-------------------+     +------------------------+
   | second-opinion    |     | secondopinion hook     |   deny / ask / allow
   | MCP server (stdio)|     | fires on every         |-------------------------+
   | second_opinion    |     | mcp__binance-mcp-      |                         |
   | base_rates        |     | server__* order call   |                         v
   | cost_estimate     |     +------------------------+     +------------------------------+
   +-------------------+                                    | Binance MCP Server           |
        ^                                                   | agent.binance.com/mcp/agentic|
        | public candles + live depth                       | confirm-before-execute,      |
        | data-api.binance.vision (no keys)                 | Agentic sub-account          |
                                                            +------------------------------+
```

**Two ways in, and they cannot disagree because they share one code path.**

- **As an MCP server.** Register it beside `binance-mcp-server`. Any client can call `second_opinion` before it calls an order tool. Five tools: `second_opinion`, `base_rates`, `cost_estimate`, `list_setups`, `audit_log`.
- **As a Claude Code hook.** A `PreToolUse` hook on `mcp__binance-mcp-server__.*` runs Second Opinion on every order the model tries to place: `spot_newOrder`, `margin_marginAccountNewOrder`, `convert_sendQuoteRequest`, `convert_placeLimitOrder`, and anything routed through the server's `tool_execute` proxy, which is unwrapped and judged as the inner call. A convert quote can only be accepted if the quote request was approved in the last 15 minutes. `VETO` denies the call and the model sees why. `CAUTION` also denies by default and tells the model to bring the numbers to you, because in a headless run (`claude -p`, cron, CI) a permission prompt cannot block and the order would go through; set `SECOND_OPINION_CAUTION=ask` in interactive sessions if you prefer a prompt. `APPROVE` allows it and attaches the receipt. Read-only tools pass silently. Anything the hook cannot parse asks; it never silently allows an unknown shape. Approved orders still go through Binance's own confirm-before-execute step.

Second Opinion holds no keys and no scopes. It reads public market data only. The Binance MCP server keeps the account.

## Quickstart

```bash
git clone https://github.com/DannyTrillion/second-opinion.git
cd second-opinion

# judge a trade (live candles + live order book, no keys)
python3 -m secondopinion check SOL buy 100 --thesis "momentum"

# replay a past decision on the committed fixtures, no network
python3 -m secondopinion check SOL buy 100 --thesis "momentum" --as-of 2026-08-27 --offline

# what has paid on this symbol, by setup
python3 -m secondopinion rates BNBUSDT

# round-trip cost for a size, from the live book
python3 -m secondopinion cost BTCUSDT 250

# play the three reference scenarios, then run the tests (45, offline)
python3 -m secondopinion demo --offline
python3 -m unittest discover -s tests -v
```

Exit codes: `0` approve, `1` caution, `2` veto, `3` error, so it drops straight into a shell pipeline or cron.

### Register the MCP server

Claude Code:

```bash
claude mcp add second-opinion --env PYTHONPATH=/ABSOLUTE/PATH/TO/second-opinion -- python3 -m secondopinion serve
```

Claude Desktop, Cursor, Codex: copy the `second-opinion` block from [mcp_config.json](mcp_config.json) and set the path.

### Install the Claude Code hook

```bash
python3 -m secondopinion install-hook            # prints the settings block
python3 -m secondopinion install-hook --apply    # merges it into ~/.claude/settings.json, keeps a .bak
```

Then, in a Claude Code session with the Binance MCP server connected, ask for a trade. If the model calls an order tool, the hook runs first. The real order tools have no rationale field, so the hook recalls the thesis the model gave `second_opinion` for the same symbol and side in the last 15 minutes; the two entry points work together. [docs/HOOK_TRANSCRIPT.md](docs/HOOK_TRANSCRIPT.md) is a verbatim transcript of the hook vetoing a momentum buy inside a real Claude Code session.

Set `SECOND_OPINION_MODE=advisory` to make the hook never deny, only ask with the receipt attached.

To watch the hook fire without a Binance account, run `scripts/try_hook.sh` from a normal terminal. It registers [examples/fake_binance_mcp.py](examples/fake_binance_mcp.py), a stand-in server that never places anything, under the name `binance-mcp-server` in a throwaway project, installs the hook there, and asks Claude Code for a momentum buy. The model's order call is intercepted before the server ever sees it, and the audit trail is printed at the end.

### As a skill

[skills/second-opinion/SKILL.md](skills/second-opinion/SKILL.md) packages the same workflow as an agent skill in the Binance Skills Hub format: when to call `second_opinion`, how to read `thesis_present` first, and how to act on each verdict. Copy the folder into any client that loads skills; for Claude Code that is `.claude/skills/second-opinion/` in your project.

## The setups

Thresholds come from the symbol's own trailing 250 days, so "big" means big for that coin, not a constant. Every flag on bar *i* is computed only from bars up to *i*. The test suite proves this by truncating the series and checking nothing changes.

| Setup | Definition | Thesis words that claim it |
| --- | --- | --- |
| `BIG_UP_DAY` | Signal-bar return at or above the trailing 90th percentile | momentum, strength, rally, surge, pump |
| `BIG_DOWN_DAY` | At or below the trailing 10th percentile | dip, pullback, bounce, reversion, cheap, crash, drop |
| `THREE_UP` / `THREE_DOWN` | Three consecutive green / red closes | momentum, trend / dip, pullback, bounce |
| `BREAKOUT_20D` / `BREAKDOWN_20D` | Close above the prior 20-bar high / below the low | breakout / breakdown, crash |
| `RSI_OVERBOUGHT` / `RSI_OVERSOLD` | 14-day RSI at or above 70 / at or below 30 | overbought / oversold, bounce |
| `ABOVE_SMA50` / `BELOW_SMA50` | Trend context; never a veto on its own | trend / downtrend |

Base rate for a setup at horizon *h*: enter at the signal close, exit *h* completed bars later, over every prior occurrence. Median, mean, hit rate, 10th and 90th percentile, and a 1,000-draw bootstrap interval on the median with a fixed seed.

## Verdict rules

| Check | Fails when | Effect |
| --- | --- | --- |
| `thesis_present` | none of the claimed setups is on the signal bar | VETO |
| `positive_notional`, `max_notional`, `symbol_allowlist`, `symbol_trading`, `min_notional` | size not positive, policy or exchange filter breached | VETO |
| `round_trip_cost`, `book_absorbs_size` | cost above policy cap, or visible depth cannot fill the size | VETO |
| `data_freshness` | last completed bar older than the policy allows | VETO |
| `evidence` | fewer than `min_sample` prior occurrences | CAUTION |
| `edge_after_cost`, `hit_rate` | median directional return minus cost is not positive, or the setup paid less than half the time | VETO for a specific setup, CAUTION if only trend context is active |
| `edge_ci_low` | lower 95% bound minus cost is not positive | CAUTION |

Policy lives in `second_opinion.policy.json` (see the [example](second_opinion.policy.example.json)); defaults are a $1,000 notional cap, 60 bps maximum round trip, 30-day sample minimum, 3-day horizon.

## Determinism and audit

The decision body contains no timestamps. It records the SHA-256 of the exact close series it used, the policy, every check with observed value and limit, and its own body hash. `tests/test_engine.py` pins the hash of the SOL 27 August replay on the committed fixture; if the maths changes, that test fails.

Every decision, whether from the CLI, the MCP server, or the hook, is appended to `~/.second_opinion/audit.jsonl` as a hash chain. `python3 -m secondopinion audit --verify` recomputes the chain and reports the first tampered line.

## What it does not do, on purpose

- It does not predict. A base rate is what happened, not what will happen. A 62% hit rate on 109 occurrences is a tilt, not a promise, and the output says so.
- Daily bars only, up to 1,000 of them. Intraday setups are out of scope; the MCP server's candle tool can be swapped in later.
- Spot pricing only. Futures funding is not modelled; a perp position's carry is a separate question.
- The hook matches the real server's 73 tools by exact name ([docs/BINANCE_MCP_TOOLS.md](docs/BINANCE_MCP_TOOLS.md), observed through an authenticated connector on 8 September 2026, since Binance has not published the list). Names outside that catalog fall back to heuristics and, if still unrecognised, ask rather than allow. `scripts/probe_binance_mcp.py` re-fetches the list when Binance changes it.
- Headless agents are the reason CAUTION denies. A hook decision of "ask" only holds when a human is at the keyboard; in `claude -p` the call proceeds. That was found by running `scripts/try_hook.sh`, and it is why the default is deny.
- No live trade is in this repository. The demo shows the veto and approve paths on live data and the hook firing inside Claude Code; the account was not funded during the hackathon window.

## Repository

```
secondopinion/
  data/binance.py      public market data, verified TLS only, on-disk cache, offline mode
  engine/indicators.py SMA, RSI, percentiles, no numpy
  engine/setups.py     setup taxonomy, no-lookahead thresholds
  engine/baserate.py   forward returns, bootstrap CI, fixed seed
  engine/cost.py       fees + order-book walk
  engine/verdict.py    checks, verdict, multi-horizon, body hash
  engine/evidence.py   cross-symbol base-rate tables
  engine/walkforward.py day-by-day out-of-sample test of the gate
  service.py           the one entry point the CLI, server and hook all use
  mcp/server.py        stdio JSON-RPC MCP server, 5 tools
  hook/pretooluse.py   Claude Code PreToolUse hook, fail closed
  hook/binance_tools.py the real server's tool catalog, matched exactly
  audit.py             hash-chained JSONL log
  __main__.py          CLI
fixtures/              up to 1,000 real daily bars for 20 USDT pairs; a depth snapshot; exchange filters
docs/                  EVIDENCE.md, EVALUATION.md, HOOK_TRANSCRIPT.md, BINANCE_MCP_TOOLS.md (the real server's 73 tools)
skills/                Skills Hub packaging
tests/                 45 tests, all offline
hooks/                 Claude Code settings example
examples/              stand-in Binance MCP server for demos
scripts/try_hook.sh    watch the hook fire in a real Claude Code session, no account needed
scripts/probe_binance_mcp.py  list the real Agent OS server's tools and input fields
```

## License

MIT.
