"""CLI: python3 -m secondopinion <command>"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__, audit


def cmd_check(a: argparse.Namespace) -> int:
    from .service import second_opinion
    v = second_opinion(a.symbol, a.side, a.notional, thesis=a.thesis, horizon_days=a.horizon, as_of=a.as_of,
                       offline=a.offline, policy_path=a.policy, setup=a.setup)
    if a.json:
        print(json.dumps(v.to_dict(), indent=2, sort_keys=True))
    else:
        print(v.summary())
    return 0 if v.verdict == "APPROVE" else (2 if v.verdict == "VETO" else 1)


def cmd_rates(a: argparse.Namespace) -> int:
    from .service import base_rates
    r = base_rates(a.symbol, a.horizon, a.as_of, offline=a.offline)
    if a.json:
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    print("%s  signal bar %s  bars=%d  horizon %dd" % (r["symbol"], r["signal_bar_date"], r["bars"], r["horizon_days"]))
    print("active now: %s" % (", ".join(r["active_setups"]) or "nothing distinctive"))
    print("%-16s %5s %8s %5s %18s" % ("setup", "n", "median", "hit", "CI95 median"))
    for k, x in sorted(r["rates"].items(), key=lambda kv: -(kv[1]["n"] or 0)):
        if not x["n"]:
            continue
        print("%-16s %5d %+7.2f%% %4.0f%% [%+6.2f%%, %+6.2f%%]%s" % (
            k, x["n"], 100 * x["median_fwd"], 100 * x["hit_rate"], 100 * x["ci95_median_low"], 100 * x["ci95_median_high"],
            "  <- active" if k in r["active_setups"] else ""))
    return 0


def cmd_cost(a: argparse.Namespace) -> int:
    from .service import cost_estimate
    print(json.dumps(cost_estimate(a.symbol, a.notional, offline=a.offline), indent=2, sort_keys=True))
    return 0


DEMO = [
    ("A momentum buy on SOL, replayed on 27 Aug 2026 (SOL +6.9%, 20-day breakout)",
     dict(symbol="SOL", side="BUY", notional=100, thesis="strong momentum, SOL just broke out", as_of="2026-08-27")),
    ("The same thesis on ETH today, where no breakout exists on the chart",
     dict(symbol="ETH", side="BUY", notional=50, thesis="momentum breakout", as_of=None)),
    ("A dip buy on BTC after three red days, replayed on 12 Aug 2026",
     dict(symbol="BTCUSDT", side="BUY", notional=100, thesis="buy the dip", as_of="2026-08-12")),
]


def cmd_demo(a: argparse.Namespace) -> int:
    from .service import second_opinion
    for i, (title, kw) in enumerate(DEMO, 1):
        print("\n[%d/%d] %s" % (i, len(DEMO), title))
        print("-" * 72)
        v = second_opinion(kw["symbol"], kw["side"], kw["notional"], thesis=kw["thesis"], as_of=kw["as_of"], offline=a.offline)
        print(v.summary())
    print("\naudit chain:", json.dumps(audit.verify()))
    return 0


def cmd_serve(a: argparse.Namespace) -> int:
    from .mcp.server import serve
    serve()
    return 0


def cmd_hook(a: argparse.Namespace) -> int:
    from .hook.pretooluse import main
    return main()


def cmd_audit(a: argparse.Namespace) -> int:
    if a.verify:
        print(json.dumps(audit.verify(), indent=2))
        return 0
    for rec in audit.read(a.limit):
        e = rec["entry"]
        print("%s  %-8s %-6s %-9s %s  %s" % (rec["ts"], e.get("verdict", e.get("decision", "")), e.get("side", ""),
                                             e.get("symbol", e.get("tool", "")), e.get("primary_setup", ""), rec["line_sha256"][:12]))
    return 0


def hook_settings(python: str, server_name: str) -> dict:
    return {"hooks": {"PreToolUse": [{"matcher": "mcp__%s__.*" % server_name,
                                      "hooks": [{"type": "command", "command": "%s -m secondopinion hook" % python, "timeout": 60}]}]}}


def cmd_install_hook(a: argparse.Namespace) -> int:
    py = a.python or sys.executable
    env_line = 'PYTHONPATH="%s" ' % str(Path(__file__).resolve().parent.parent)
    snippet = hook_settings(env_line + py, a.server)
    if not a.apply:
        print(json.dumps(snippet, indent=2))
        print("\nMerge the block above into ~/.claude/settings.json, or re-run with --apply.", file=sys.stderr)
        return 0
    target = Path(a.settings or (Path.home() / ".claude" / "settings.json"))
    target.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(target.read_text()) if target.exists() else {}
    if target.exists():
        shutil.copy(target, str(target) + ".bak")
    hooks = current.setdefault("hooks", {}).setdefault("PreToolUse", [])
    hooks = [h for h in hooks if "secondopinion hook" not in json.dumps(h)]
    hooks.extend(snippet["hooks"]["PreToolUse"])
    current["hooks"]["PreToolUse"] = hooks
    target.write_text(json.dumps(current, indent=2))
    print("hook installed in %s (backup at %s.bak)" % (target, target))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="secondopinion", description="Second Opinion %s: base-rate and cost check for AI-proposed Binance trades" % __version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="judge one proposed trade")
    c.add_argument("symbol"); c.add_argument("side", choices=["buy", "sell", "BUY", "SELL"]); c.add_argument("notional", type=float, help="USD notional")
    c.add_argument("--thesis", help="the proposer's rationale in words")
    c.add_argument("--setup", help="force a setup key instead of a thesis")
    c.add_argument("--horizon", type=int, default=None); c.add_argument("--as-of", dest="as_of", help="YYYY-MM-DD replay")
    c.add_argument("--offline", action="store_true"); c.add_argument("--policy"); c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_check)

    r = sub.add_parser("rates", help="base rates for every setup on a symbol")
    r.add_argument("symbol"); r.add_argument("--horizon", type=int, default=3); r.add_argument("--as-of", dest="as_of")
    r.add_argument("--offline", action="store_true"); r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_rates)

    k = sub.add_parser("cost", help="round-trip cost from the live order book")
    k.add_argument("symbol"); k.add_argument("notional", type=float); k.add_argument("--offline", action="store_true")
    k.set_defaults(fn=cmd_cost)

    d = sub.add_parser("demo", help="play the three reference scenarios")
    d.add_argument("--offline", action="store_true"); d.set_defaults(fn=cmd_demo)
    sub.add_parser("serve", help="run the MCP server on stdio").set_defaults(fn=cmd_serve)
    sub.add_parser("hook", help="Claude Code PreToolUse hook (reads stdin)").set_defaults(fn=cmd_hook)

    au = sub.add_parser("audit", help="show or verify the hash-chained audit log")
    au.add_argument("--limit", type=int, default=20); au.add_argument("--verify", action="store_true")
    au.set_defaults(fn=cmd_audit)

    ih = sub.add_parser("install-hook", help="print or apply the Claude Code hook settings")
    ih.add_argument("--apply", action="store_true"); ih.add_argument("--settings"); ih.add_argument("--python")
    ih.add_argument("--server", default="binance-mcp-server", help="MCP server name the hook guards")
    ih.set_defaults(fn=cmd_install_hook)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
