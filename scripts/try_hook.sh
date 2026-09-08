#!/usr/bin/env bash
# Watch the Second Opinion hook fire inside a real Claude Code session, with no Binance account.
# It registers examples/fake_binance_mcp.py under the name binance-mcp-server in a throwaway
# project, installs the PreToolUse hook there, and asks Claude Code to place a momentum buy.
# Run this from a normal terminal, not from inside another Claude Code session.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
command -v claude >/dev/null || { echo "claude CLI not found; install Claude Code first"; exit 1; }
P="$(mktemp -d)/second-opinion-hook-demo"
mkdir -p "$P/.claude"
cat > "$P/.mcp.json" <<JSON
{"mcpServers":{"binance-mcp-server":{"command":"python3","args":["$ROOT/examples/fake_binance_mcp.py"]}}}
JSON
cat > "$P/.claude/settings.json" <<JSON
{"hooks":{"PreToolUse":[{"matcher":"mcp__binance-mcp-server__.*","hooks":[{"type":"command","command":"PYTHONPATH=$ROOT SECOND_OPINION_AUDIT=$P/audit.jsonl python3 -m secondopinion hook","timeout":60}]}]}}
JSON
cd "$P"
MODEL="${SECOND_OPINION_DEMO_MODEL:-sonnet}"   # any model your account can run; override with SECOND_OPINION_DEMO_MODEL
PROMPT=${1:-"I am testing a guard hook against a stand-in exchange server; no real order can be placed. Call the binance-mcp-server tool create_spot_order exactly once with symbol SOLUSDT, side BUY, type MARKET, quoteOrderQty 100, reason 'momentum looks strong'. Then report verbatim what the call returned, including any denial message, and stop."}
echo ">>> project: $P"
echo ">>> model: $MODEL"
echo ">>> prompt: $PROMPT"
echo
# CLAUDECODE is unset so the demo also works when launched from inside a Claude Code terminal
env -u CLAUDECODE claude -p "$PROMPT" --model "$MODEL" --allowedTools "mcp__binance-mcp-server__get_ticker,mcp__binance-mcp-server__create_spot_order" --max-turns 8
echo
echo ">>> Second Opinion audit trail for this session:"
SECOND_OPINION_AUDIT="$P/audit.jsonl" PYTHONPATH="$ROOT" python3 -m secondopinion audit --limit 5
SECOND_OPINION_AUDIT="$P/audit.jsonl" PYTHONPATH="$ROOT" python3 -m secondopinion audit --verify
