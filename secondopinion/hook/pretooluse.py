"""
Claude Code PreToolUse hook. Sits in front of the Binance MCP server so every order an
AI proposes gets a Second Opinion before Binance's own confirm-before-execute step.

Decisions:
  read-only tool           -> allow (silent)
  cancel / transfer        -> allow, logged
  order we can parse       -> APPROVE=allow(+receipt)  CAUTION=ask  VETO=deny
  order we cannot parse    -> ask   (fail closed: never a silent allow on unknown shapes)
  SECOND_OPINION_MODE=advisory -> never deny; verdict attached as context instead
  SECOND_OPINION_CAUTION=ask   -> CAUTION prompts the user instead of denying. Default is deny,
                                  because in headless runs (claude -p, cron, CI) "ask" cannot
                                  block and the order would go through.
"""
import json
import os
import re
import sys
from typing import Any, Dict, Optional, Tuple

from .. import audit
from ..service import make_data, normalize_symbol, second_opinion

READ_WORDS = ("get", "list", "query", "fetch", "read", "show", "search", "describe", "history", "status",
              "balance", "ticker", "kline", "candle", "depth", "book", "price", "funding", "position", "info", "time")
ORDER_WORDS = ("order", "trade", "buy", "sell", "convert", "swap", "execute", "submit", "place")
CANCEL_WORDS = ("cancel",)
TRANSFER_WORDS = ("transfer",)

SYMBOL_KEYS = ("symbol", "pair", "instrument", "market", "ticker")
SIDE_KEYS = ("side", "direction", "action")
QUOTE_QTY_KEYS = ("quoteorderqty", "quote_order_qty", "quoteqty", "quote_qty", "notional", "notional_usd", "usd", "usdt_amount", "quote_amount", "amount_usd")
BASE_QTY_KEYS = ("quantity", "qty", "amount", "size", "base_qty", "fromamount", "from_amount")
PRICE_KEYS = ("price", "limit_price")


def classify(tool_name: str) -> str:
    n = tool_name.lower().split("__")[-1]
    if any(w in n for w in CANCEL_WORDS):
        return "cancel"
    if any(w in n for w in TRANSFER_WORDS):
        return "transfer"
    if any(w in n for w in ORDER_WORDS) and not n.startswith(("get_", "list_", "query_")):
        return "order"
    if any(w in n for w in READ_WORDS):
        return "read"
    return "unknown"


def _flat(d: Any, out: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    if isinstance(d, dict):
        for k, v in d.items():
            key = (k if not prefix else prefix + "." + k).lower()
            if isinstance(v, (dict, list)):
                _flat(v, out, key)
            else:
                out[key] = v
                out.setdefault(k.lower(), v)
    elif isinstance(d, list):
        for i, v in enumerate(d):
            _flat(v, out, "%s[%d]" % (prefix, i))
    return out


def _pick(flat: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[Any]:
    for k in keys:
        for fk, v in flat.items():
            if fk == k or fk.endswith("." + k) or fk.replace("_", "") == k.replace("_", ""):
                if v not in (None, ""):
                    return v
    return None


def parse_order(tool_name: str, tool_input: Dict[str, Any], price_lookup=None) -> Tuple[Optional[Dict[str, Any]], str]:
    """Returns (order, note). order = {symbol, side, notional_usd, how}. None when unparseable."""
    flat = _flat(tool_input, {})
    n = tool_name.lower()
    symbol = _pick(flat, SYMBOL_KEYS)
    side = _pick(flat, SIDE_KEYS)
    from_asset, to_asset = _pick(flat, ("fromasset", "from_asset", "from")), _pick(flat, ("toasset", "to_asset", "to"))
    stables = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD")
    convert_from_amount = None
    if not symbol and from_asset and to_asset:
        fa, ta = str(from_asset).upper(), str(to_asset).upper()
        amt = _pick(flat, ("fromamount", "from_amount", "amount"))
        if fa in stables:
            symbol, side = ta + fa, "BUY"
            if amt is not None:
                try:
                    return {"symbol": normalize_symbol(symbol), "side": side, "notional_usd": float(amt), "how": "convert: %s amount is the quote notional" % fa}, ""
                except (TypeError, ValueError) as e:
                    return None, "could not read convert amount: %s" % e
        elif ta in stables:
            symbol, side = fa + ta, "SELL"
            convert_from_amount = amt
        else:
            symbol, side = ta + fa, "BUY"
            convert_from_amount = amt
    if not side:
        if "buy" in n:
            side = "BUY"
        elif "sell" in n:
            side = "SELL"
    if not symbol or not side:
        return None, "could not identify symbol/side in tool input keys %s" % sorted(tool_input.keys())
    side = str(side).upper()
    if side not in ("BUY", "SELL"):
        side = "BUY" if side.startswith("B") or side == "LONG" else "SELL"
    sym = normalize_symbol(str(symbol))
    quote = _pick(flat, QUOTE_QTY_KEYS)
    base = convert_from_amount if convert_from_amount is not None else _pick(flat, BASE_QTY_KEYS)
    price = _pick(flat, PRICE_KEYS)
    try:
        if quote is not None:
            return {"symbol": sym, "side": side, "notional_usd": float(quote), "how": "quote quantity from input"}, ""
        if base is not None:
            if price is not None:
                return {"symbol": sym, "side": side, "notional_usd": float(base) * float(price), "how": "quantity x limit price"}, ""
            if price_lookup:
                px = float(price_lookup(sym))
                return {"symbol": sym, "side": side, "notional_usd": float(base) * px, "how": "quantity x last close %.6g" % px}, ""
    except (TypeError, ValueError) as e:
        return None, "could not read quantity: %s" % e
    return None, "no quantity or notional in tool input keys %s" % sorted(tool_input.keys())


def decide(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    kind = classify(tool)
    advisory = os.environ.get("SECOND_OPINION_MODE", "").lower() == "advisory"

    def out(decision: str, reason: str = "", context: str = "") -> Dict[str, Any]:
        h = {"hookEventName": "PreToolUse", "permissionDecision": decision}
        if reason:
            h["permissionDecisionReason"] = reason
        if context:
            h["additionalContext"] = context
        return {"hookSpecificOutput": h}

    if kind == "read":
        return out("allow")
    if kind in ("cancel", "transfer"):
        audit.append({"origin": "hook", "tool": tool, "kind": kind, "decision": "allow", "input": tool_input})
        return out("allow", context="Second Opinion: %s passed through (not a market bet); logged." % kind)
    if kind == "unknown":
        audit.append({"origin": "hook", "tool": tool, "kind": kind, "decision": "ask", "input": tool_input})
        return out("ask", "Second Opinion does not recognise tool '%s'; confirm manually." % tool)

    data = make_data()
    order, note = parse_order(tool, tool_input, price_lookup=lambda s: data.last_price(s))
    if not order:
        audit.append({"origin": "hook", "tool": tool, "kind": "order", "decision": "ask", "note": note, "input": tool_input})
        return out("ask", "Second Opinion could not parse this order (%s). Confirm manually or call the second_opinion tool first." % note)

    thesis = os.environ.get("SECOND_OPINION_THESIS") or _pick(_flat(tool_input, {}), ("thesis", "reason", "rationale", "note", "comment"))
    try:
        v = second_opinion(order["symbol"], order["side"], order["notional_usd"], thesis=thesis, origin="hook:" + tool)
    except Exception as e:
        audit.append({"origin": "hook", "tool": tool, "kind": "order", "decision": "ask", "error": str(e), "input": tool_input})
        return out("ask", "Second Opinion could not evaluate (%s). Confirm manually." % e)

    receipt = "Second Opinion (%s, notional %s):\n%s" % (order["how"], "$%.2f" % order["notional_usd"], v.summary())
    caution_mode = os.environ.get("SECOND_OPINION_CAUTION", "deny").lower()
    if v.verdict == "APPROVE":
        return out("allow", context=receipt)
    if advisory:
        return out("ask", receipt, context=receipt)
    if v.verdict == "CAUTION":
        if caution_mode == "ask":
            return out("ask", receipt, context=receipt)
        return out("deny", receipt + "\n\nCAUTION is not an approval. Show the user these numbers and let them decide; "
                   "do not retry this order on your own.", context=receipt)
    return out("deny", receipt, context=receipt)


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    result = decide(payload)
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
