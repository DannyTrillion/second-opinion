import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="so_test_")
ENV = dict(os.environ, SECOND_OPINION_OFFLINE="1", SECOND_OPINION_CACHE=os.path.join(TMP, "cache"),
           SECOND_OPINION_AUDIT=os.path.join(TMP, "audit.jsonl"), PYTHONPATH=str(ROOT))
os.environ.update({k: ENV[k] for k in ("SECOND_OPINION_OFFLINE", "SECOND_OPINION_CACHE", "SECOND_OPINION_AUDIT")})

from secondopinion import audit  # noqa: E402
from secondopinion.hook import pretooluse as hook  # noqa: E402
from secondopinion.service import normalize_symbol  # noqa: E402


class TestHookClassifyParse(unittest.TestCase):
    def test_classify(self):
        c = hook.classify
        self.assertEqual(c("mcp__binance-mcp-server__get_ticker"), "read")
        self.assertEqual(c("mcp__binance-mcp-server__get_klines"), "read")
        self.assertEqual(c("mcp__binance-mcp-server__create_spot_order"), "order")
        self.assertEqual(c("mcp__binance-mcp-server__spot_buy"), "order")
        self.assertEqual(c("mcp__binance-mcp-server__convert_accept_quote"), "order")
        self.assertEqual(c("mcp__binance-mcp-server__cancel_order"), "cancel")
        self.assertEqual(c("mcp__binance-mcp-server__universal_transfer"), "transfer")
        self.assertEqual(c("mcp__binance-mcp-server__frobnicate"), "unknown")
        self.assertEqual(c("mcp__binance-mcp-server__get_open_orders"), "read")

    def test_parse_shapes(self):
        p = hook.parse_order
        o, _ = p("x__create_spot_order", {"symbol": "SOLUSDT", "side": "BUY", "quoteOrderQty": 100})
        self.assertEqual((o["symbol"], o["side"], o["notional_usd"]), ("SOLUSDT", "BUY", 100.0))
        o, _ = p("x__place_order", {"symbol": "BTC/USDT", "side": "sell", "quantity": 0.001, "price": 80000})
        self.assertEqual((o["symbol"], o["side"], o["notional_usd"]), ("BTCUSDT", "SELL", 80.0))
        o, _ = p("x__convert", {"fromAsset": "USDT", "toAsset": "BNB", "fromAmount": 50})
        self.assertEqual((o["symbol"], o["side"], o["notional_usd"]), ("BNBUSDT", "BUY", 50.0))
        o, _ = p("x__convert", {"fromAsset": "BNB", "toAsset": "USDT", "fromAmount": 2}, price_lookup=lambda s: 700.0)
        self.assertEqual((o["symbol"], o["side"], o["notional_usd"]), ("BNBUSDT", "SELL", 1400.0))
        o, _ = p("x__spot_buy", {"symbol": "eth", "quantity": 1}, price_lookup=lambda s: 4000.0)
        self.assertEqual((o["symbol"], o["side"], o["notional_usd"]), ("ETHUSDT", "BUY", 4000.0))
        o, note = p("x__futures_new_order", {"foo": "bar"})
        self.assertIsNone(o)
        self.assertIn("symbol/side", note)
        o, _ = p("x__order", {"order": {"symbol": "BNBUSDT", "side": "BUY", "quoteOrderQty": "25"}})
        self.assertEqual(o["notional_usd"], 25.0)

    def test_normalize_symbol(self):
        self.assertEqual(normalize_symbol("btc"), "BTCUSDT")
        self.assertEqual(normalize_symbol("ETH-USDT"), "ETHUSDT")
        self.assertEqual(normalize_symbol("sol/usdc"), "SOLUSDC")


class TestHookDecide(unittest.TestCase):
    def out(self, payload):
        return hook.decide(payload)["hookSpecificOutput"]

    def test_read_allows_silently(self):
        h = self.out({"tool_name": "mcp__binance-mcp-server__get_ticker", "tool_input": {"symbol": "BTCUSDT"}})
        self.assertEqual(h["permissionDecision"], "allow")
        self.assertNotIn("additionalContext", h)

    def test_unknown_asks(self):
        h = self.out({"tool_name": "mcp__binance-mcp-server__zzz", "tool_input": {}})
        self.assertEqual(h["permissionDecision"], "ask")

    def test_unparseable_order_asks(self):
        h = self.out({"tool_name": "mcp__binance-mcp-server__new_order", "tool_input": {"foo": 1}})
        self.assertEqual(h["permissionDecision"], "ask")

    def test_cancel_allows_with_context(self):
        h = self.out({"tool_name": "mcp__binance-mcp-server__cancel_order", "tool_input": {"orderId": 5}})
        self.assertEqual(h["permissionDecision"], "allow")
        self.assertIn("logged", h["additionalContext"])

    def test_order_over_cap_is_denied_with_numbers(self):
        h = self.out({"tool_name": "mcp__binance-mcp-server__create_spot_order",
                      "tool_input": {"symbol": "ETHUSDT", "side": "BUY", "quoteOrderQty": 5000}})
        self.assertEqual(h["permissionDecision"], "deny")
        self.assertIn("max_notional", h["permissionDecisionReason"])
        self.assertIn("5000", h["permissionDecisionReason"])

    def test_caution_denies_by_default_and_asks_when_configured(self):
        payload = {"tool_name": "mcp__binance-mcp-server__create_spot_order",
                   "tool_input": {"symbol": "BTCUSDT", "side": "BUY", "quoteOrderQty": 100}}
        # BTC on the fixture's last completed bar is a plain day: CAUTION
        h = self.out(payload)
        self.assertEqual(h["permissionDecision"], "deny")
        self.assertIn("CAUTION", h["permissionDecisionReason"])
        with mock.patch.dict(os.environ, {"SECOND_OPINION_CAUTION": "ask"}):
            h = self.out(payload)
        self.assertEqual(h["permissionDecision"], "ask")

    def test_advisory_mode_never_denies(self):
        with mock.patch.dict(os.environ, {"SECOND_OPINION_MODE": "advisory"}):
            h = self.out({"tool_name": "mcp__binance-mcp-server__create_spot_order",
                          "tool_input": {"symbol": "ETHUSDT", "side": "BUY", "quoteOrderQty": 5000}})
        self.assertEqual(h["permissionDecision"], "ask")

    def test_empty_stdin_does_not_crash(self):
        r = subprocess.run([sys.executable, "-m", "secondopinion", "hook"], input="", capture_output=True, text=True, env=ENV, cwd=str(ROOT))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")


class TestMCPServer(unittest.TestCase):
    def rpc(self, msgs):
        inp = "\n".join(json.dumps(m) for m in msgs) + "\n"
        r = subprocess.run([sys.executable, "-m", "secondopinion", "serve"], input=inp, capture_output=True, text=True, env=ENV, cwd=str(ROOT), timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [json.loads(l) for l in r.stdout.strip().splitlines()]

    def test_protocol_and_tools(self):
        out = self.rpc([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "second_opinion", "arguments": {"symbol": "SOLUSDT", "side": "BUY", "notional_usd": 100, "thesis": "momentum", "as_of": "2026-08-27"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 5, "method": "ping"},
        ])
        self.assertEqual(out[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(out[0]["result"]["serverInfo"]["name"], "second-opinion")
        names = [t["name"] for t in out[1]["result"]["tools"]]
        self.assertEqual(names, ["second_opinion", "base_rates", "cost_estimate", "list_setups", "audit_log"])
        for t in out[1]["result"]["tools"]:
            self.assertIn("inputSchema", t)
        sc = out[2]["result"]["structuredContent"]
        self.assertEqual(sc["verdict"], "VETO")
        self.assertEqual(sc["primary_setup"], "BIG_UP_DAY")
        self.assertTrue(out[3]["result"]["isError"])
        self.assertEqual(out[4]["result"], {})


class TestAudit(unittest.TestCase):
    def test_chain_and_tamper(self):
        p = Path(TMP) / "chain.jsonl"
        audit.append({"a": 1}, p)
        audit.append({"b": 2}, p)
        self.assertTrue(audit.verify(p)["ok"])
        lines = p.read_text().splitlines()
        rec = json.loads(lines[0])
        rec["entry"]["a"] = 999
        lines[0] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
        p.write_text("\n".join(lines) + "\n")
        self.assertFalse(audit.verify(p)["ok"])


if __name__ == "__main__":
    unittest.main()


class TestRealBinanceCatalog(unittest.TestCase):
    """Against the 75-tool catalog observed on the real Agent OS server on 8 Sep 2026."""

    def out(self, payload):
        return hook.decide(payload)["hookSpecificOutput"]

    def test_exact_categories(self):
        c = hook.classify
        P = "mcp__binance-mcp-server__"
        self.assertEqual(c(P + "spot_newOrder"), "order")
        self.assertEqual(c(P + "margin_marginAccountNewOrder"), "order")
        self.assertEqual(c(P + "convert_sendQuoteRequest"), "order")
        self.assertEqual(c(P + "convert_placeLimitOrder"), "order")
        self.assertEqual(c(P + "convert_acceptQuote"), "order_accept")
        self.assertEqual(c(P + "spot_deleteOpenOrders"), "cancel")
        self.assertEqual(c(P + "wallet_userUniversalTransfer"), "transfer")
        self.assertEqual(c(P + "tool_execute"), "proxy")
        self.assertEqual(c("mcp__claude_ai_binance-mcp-server__spot_newOrder"), "order")
        import re
        from secondopinion.__main__ import hook_settings
        m = hook_settings("python3", "binance-mcp-server")["hooks"]["PreToolUse"][0]["matcher"]
        self.assertTrue(re.fullmatch(m, "mcp__binance-mcp-server__spot_newOrder"))
        self.assertTrue(re.fullmatch(m, "mcp__claude_ai_binance-mcp-server__spot_newOrder"))
        self.assertFalse(re.fullmatch(m, "mcp__other__spot_newOrder"))
        for t in ("spot_getAccount", "spot_myTrades", "wallet_depositAddress", "wallet_withdrawHistory",
                  "futures_usds_positionInformationV2", "analysis_getTokenAiReport", "tool_search"):
            self.assertEqual(c(P + t), "read", t)
        from secondopinion.hook.binance_tools import ALL
        self.assertEqual(len(ALL), 73)

    def test_spot_newOrder_over_cap_denied(self):
        h = self.out({"tool_name": "mcp__binance-mcp-server__spot_newOrder",
                      "tool_input": {"symbol": "ETHUSDT", "side": "BUY", "type": "MARKET", "quoteOrderQty": 5000}})
        self.assertEqual(h["permissionDecision"], "deny")
        self.assertIn("max_notional", h["permissionDecisionReason"])

    def test_tool_execute_proxy_is_unwrapped(self):
        h = self.out({"tool_name": "mcp__binance-mcp-server__tool_execute",
                      "tool_input": {"toolName": "spot_newOrder",
                                     "arguments": {"symbol": "ETHUSDT", "side": "BUY", "type": "MARKET", "quoteOrderQty": 5000}}})
        self.assertEqual(h["permissionDecision"], "deny")
        self.assertIn("max_notional", h["permissionDecisionReason"])
        h = self.out({"tool_name": "mcp__binance-mcp-server__tool_execute",
                      "tool_input": {"toolName": "spot_ticker24hr", "arguments": {"symbol": "BTCUSDT"}}})
        self.assertEqual(h["permissionDecision"], "allow")
        h = self.out({"tool_name": "mcp__binance-mcp-server__tool_execute", "tool_input": {}})
        self.assertEqual(h["permissionDecision"], "ask")

    def test_convert_quote_shapes(self):
        p = hook.parse_order
        o, _ = p("x__convert_sendQuoteRequest", {"fromAsset": "USDT", "toAsset": "BNB", "fromAmount": 50})
        self.assertEqual((o["symbol"], o["side"], o["notional_usd"]), ("BNBUSDT", "BUY", 50.0))
        o, _ = p("x__convert_sendQuoteRequest", {"fromAsset": "BNB", "toAsset": "USDT", "toAmount": 75})
        self.assertEqual((o["symbol"], o["side"], o["notional_usd"]), ("BNBUSDT", "SELL", 75.0))
        o, _ = p("x__convert_placeLimitOrder", {"baseAsset": "SOL", "quoteAsset": "USDT", "side": "BUY", "limitPrice": 100, "baseAmount": 2, "expiredType": "1_D"})
        self.assertEqual((o["symbol"], o["side"], o["notional_usd"]), ("SOLUSDT", "BUY", 200.0))

    def test_accept_quote_requires_a_recent_allowed_quote(self):
        h = self.out({"tool_name": "mcp__binance-mcp-server__convert_acceptQuote", "tool_input": {"quoteId": "q1"}})
        self.assertEqual(h["permissionDecision"], "deny")
        # a vetoed quote request (over cap) must not unlock acceptance
        self.out({"tool_name": "mcp__binance-mcp-server__convert_sendQuoteRequest",
                  "tool_input": {"fromAsset": "USDT", "toAsset": "ETH", "fromAmount": 5000}})
        h = self.out({"tool_name": "mcp__binance-mcp-server__convert_acceptQuote", "tool_input": {"quoteId": "q1"}})
        self.assertEqual(h["permissionDecision"], "deny")
        # an allowed quote request does
        audit.append({"origin": "hook", "tool": "mcp__binance-mcp-server__convert_sendQuoteRequest", "kind": "order", "decision": "allow"})
        h = self.out({"tool_name": "mcp__binance-mcp-server__convert_acceptQuote", "tool_input": {"quoteId": "q1"}})
        self.assertEqual(h["permissionDecision"], "allow")

    def test_thesis_is_recalled_from_a_prior_second_opinion_call(self):
        from secondopinion.service import second_opinion
        # the model asked second_opinion() with a thesis; the real order tool has no rationale field
        second_opinion("ETHUSDT", "BUY", 50, thesis="momentum breakout", origin="mcp")
        h = self.out({"tool_name": "mcp__binance-mcp-server__spot_newOrder",
                      "tool_input": {"symbol": "ETHUSDT", "side": "BUY", "type": "MARKET", "quoteOrderQty": 50}})
        self.assertIn("claimed: BIG_UP_DAY", h["permissionDecisionReason"])
