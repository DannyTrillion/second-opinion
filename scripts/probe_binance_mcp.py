#!/usr/bin/env python3
"""
Ask the real Binance Agent OS MCP server what tools it exposes.

Speaks MCP over streamable HTTP with the standard library only. Market-data tools are
documented as public, so initialize + tools/list may work without a login. If the server
answers 401, pass a bearer token with --token (from an authenticated client's session).
Prints each tool's name and input fields, and writes the raw tools/list to a JSON file
so the hook matcher can be made exact. Run this on a network where binance.com resolves.
"""
import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://agent.binance.com/mcp/agentic"


def ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(p):
            return ssl.create_default_context(cafile=p)
    return ssl.create_default_context()


def rpc(url, body, token=None, session=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": "second-opinion-probe/0.1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20, context=ctx()) as r:
        raw = r.read().decode("utf-8", "replace")
        sid = r.headers.get("Mcp-Session-Id")
    # streamable HTTP may answer as JSON or as an SSE stream of JSON events
    if raw.lstrip().startswith("{"):
        return json.loads(raw), sid
    msgs = [json.loads(l[5:].strip()) for l in raw.splitlines() if l.startswith("data:")]
    return (msgs[-1] if msgs else {"raw": raw}), sid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=ENDPOINT)
    ap.add_argument("--token", default=os.environ.get("BINANCE_MCP_TOKEN"))
    ap.add_argument("--out", default="binance_mcp_tools.json")
    a = ap.parse_args()
    try:
        init, sid = rpc(a.url, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "second-opinion-probe", "version": "0.1"}}}, a.token)
    except urllib.error.HTTPError as e:
        print("initialize -> HTTP %d %s" % (e.code, e.reason))
        if e.code in (401, 403):
            print("The endpoint wants a login. Connect a client first (claude mcp add ...), then re-run with --token.")
        return 1
    except Exception as e:
        print("initialize failed: %s" % e)
        return 1
    print("server:", json.dumps(init.get("result", {}).get("serverInfo"), sort_keys=True))
    try:
        rpc(a.url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, a.token, sid)
    except Exception:
        pass
    try:
        tl, _ = rpc(a.url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, a.token, sid)
    except urllib.error.HTTPError as e:
        print("tools/list -> HTTP %d %s" % (e.code, e.reason))
        return 1
    tools = tl.get("result", {}).get("tools", [])
    if not tools:
        print("no tools returned:", json.dumps(tl)[:500])
        return 1
    for t in tools:
        props = (t.get("inputSchema") or {}).get("properties", {})
        req = (t.get("inputSchema") or {}).get("required", [])
        print("- %s(%s)" % (t["name"], ", ".join("%s%s" % (k, "*" if k in req else "") for k in props)))
        if t.get("description"):
            print("    " + t["description"].strip().splitlines()[0][:140])
    with open(a.out, "w") as f:
        json.dump(tl, f, indent=2, sort_keys=True)
    print("\n%d tools written to %s. Paste this file back to tighten the hook matcher." % (len(tools), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
