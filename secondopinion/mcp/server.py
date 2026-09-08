"""
Second Opinion as an MCP server (stdio, newline-delimited JSON-RPC 2.0).
Any MCP client (Claude Code, Claude Desktop, Cursor, Codex) can call it next to the
Binance MCP server: read the market with Binance, ask Second Opinion before trading.
"""
import json
import sys
import traceback
from typing import Any, Dict

from .. import __version__, audit
from ..engine.setups import SETUPS
from ..engine.verdict import THESIS_MAP
from ..service import base_rates, cost_estimate, second_opinion

PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "second_opinion",
        "description": ("Deterministic pre-trade check for an AI-proposed Binance trade. Classifies the current chart into "
                        "measurable setups, computes the historical base rate of the proposed trade on this symbol "
                        "(median forward return, hit rate, sample size, 95% CI), the round-trip cost from the live order "
                        "book and fees, and returns APPROVE / CAUTION / VETO with every number that drove it. "
                        "Call this before any order tool."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "e.g. BTCUSDT (BTC, BTC/USDT also accepted)"},
                "side": {"type": "string", "enum": ["BUY", "SELL"]},
                "notional_usd": {"type": "number", "description": "order size in quote currency (USD-equivalent)"},
                "thesis": {"type": "string", "description": "the rationale in plain words, e.g. 'momentum after today's breakout'. Second Opinion checks whether the claimed setup is actually present."},
                "horizon_days": {"type": "integer", "default": 3, "description": "holding horizon the trade is judged on"},
                "as_of": {"type": "string", "description": "YYYY-MM-DD to replay a past decision (no live order book)"},
            },
            "required": ["symbol", "side", "notional_usd"],
        },
    },
    {
        "name": "base_rates",
        "description": "Historical forward-return statistics for every setup on a symbol, plus which setups are active on the latest completed daily bar.",
        "inputSchema": {"type": "object", "properties": {
            "symbol": {"type": "string"}, "horizon_days": {"type": "integer", "default": 3}, "as_of": {"type": "string"}},
            "required": ["symbol"]},
    },
    {
        "name": "cost_estimate",
        "description": "Round-trip cost in basis points for a given notional: taker fees both legs plus order-book impact both legs, measured against mid from the live Binance depth.",
        "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "notional_usd": {"type": "number"}},
                        "required": ["symbol", "notional_usd"]},
    },
    {
        "name": "list_setups",
        "description": "The setup taxonomy Second Opinion can test, and the thesis words that map to each.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "audit_log",
        "description": "Recent Second Opinion decisions from the hash-chained audit log, and whether the chain verifies.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}},
    },
]


def _text(obj: Any) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(obj, indent=2, sort_keys=True)}]}


def call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "second_opinion":
        v = second_opinion(args["symbol"], args["side"], float(args["notional_usd"]), thesis=args.get("thesis"),
                           horizon_days=args.get("horizon_days"), as_of=args.get("as_of"), origin="mcp")
        body = v.to_dict()
        body["summary"] = v.summary()
        return {"content": [{"type": "text", "text": v.summary() + "\n\n" + json.dumps(body, indent=2, sort_keys=True)}],
                "structuredContent": body}
    if name == "base_rates":
        return _text(base_rates(args["symbol"], int(args.get("horizon_days", 3)), args.get("as_of")))
    if name == "cost_estimate":
        return _text(cost_estimate(args["symbol"], float(args["notional_usd"])))
    if name == "list_setups":
        return _text({"setups": [{"key": s.key, "label": s.label, "description": s.description} for s in SETUPS],
                      "thesis_words": THESIS_MAP})
    if name == "audit_log":
        return _text({"verify": audit.verify(), "recent": audit.read(int(args.get("limit", 10)))})
    raise KeyError("unknown tool %s" % name)


def handle(req: Dict[str, Any]) -> Dict[str, Any]:
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "second-opinion", "version": __version__}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method in ("prompts/list", "resources/list"):
        return {"jsonrpc": "2.0", "id": rid, "result": {method.split("/")[0]: []}}
    if method == "tools/call":
        try:
            return {"jsonrpc": "2.0", "id": rid, "result": call_tool(params.get("name", ""), params.get("arguments") or {})}
        except Exception as e:
            sys.stderr.write(traceback.format_exc())
            return {"jsonrpc": "2.0", "id": rid, "result": {"isError": True, "content": [{"type": "text", "text": "%s: %s" % (type(e).__name__, e)}]}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found: %s" % method}}


def serve() -> None:
    sys.stderr.write("second-opinion MCP server %s ready (stdio)\n" % __version__)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" not in req:      # notification
            continue
        resp = handle(req)
        sys.stdout.write(json.dumps(resp, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    serve()
