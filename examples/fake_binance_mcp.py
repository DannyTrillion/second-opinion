"""A stand-in for the Binance MCP server, for demonstrating the hook without an account.
It exposes get_ticker and create_spot_order over stdio and never places anything. The tool
names are illustrative; the real server's names are not published, which is why the hook
classifies by name and asks on anything it does not recognise."""
import json, sys
TOOLS=[{"name":"get_ticker","description":"24h ticker","inputSchema":{"type":"object","properties":{"symbol":{"type":"string"}},"required":["symbol"]}},
       {"name":"create_spot_order","description":"Place a spot order. side BUY/SELL, quoteOrderQty in USDT.","inputSchema":{"type":"object","properties":{"symbol":{"type":"string"},"side":{"type":"string"},"type":{"type":"string"},"quoteOrderQty":{"type":"number"}},"required":["symbol","side","quoteOrderQty"]}}]
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    r=json.loads(line); m=r.get("method"); i=r.get("id")
    if i is None: continue
    if m=="initialize": res={"protocolVersion":r["params"].get("protocolVersion","2024-11-05"),"capabilities":{"tools":{}},"serverInfo":{"name":"binance-mcp-server","version":"0"}}
    elif m=="tools/list": res={"tools":TOOLS}
    elif m=="tools/call":
        n=r["params"]["name"]; a=r["params"].get("arguments",{})
        if n=="get_ticker": res={"content":[{"type":"text","text":json.dumps({"symbol":a.get("symbol"),"lastPrice":"103.30","priceChangePercent":"-1.6"})}]}
        else: res={"content":[{"type":"text","text":json.dumps({"orderId":123456,"status":"FILLED","note":"FAKE SERVER - no real order"})}]}
    else: res={}
    sys.stdout.write(json.dumps({"jsonrpc":"2.0","id":i,"result":res})+"\n"); sys.stdout.flush()
