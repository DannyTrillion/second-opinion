"""Cross-symbol evidence: which setups have paid where, from the committed fixtures."""
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from .baserate import all_base_rates
from .setups import SetupMatrix, SETUPS

COST_BPS = 30.0


def build(fixtures: Path, horizon: int = 3, min_n: int = 30) -> Dict[str, Any]:
    now = int(time.time() * 1000)
    table: Dict[str, Dict[str, Any]] = {}
    pairs: List[Dict[str, Any]] = []
    symbols = sorted(p.name.split("_")[0] for p in fixtures.glob("*_1d.json"))
    for sym in symbols:
        rows = [r for r in json.loads((fixtures / ("%s_1d.json" % sym)).read_text()) if int(r[6]) <= now]
        closes = [float(r[4]) for r in rows]
        m = SetupMatrix(closes)
        rates = all_base_rates(m, horizon)
        table[sym] = {k: r.to_dict() for k, r in rates.items()}
        for k, r in rates.items():
            if k == "ALL_DAYS" or r.n < min_n:
                continue
            edge = r.median_fwd * 1e4 - COST_BPS
            lo = r.ci95_median_low * 1e4 - COST_BPS
            pairs.append({"symbol": sym, "setup": k, "n": r.n, "median": r.median_fwd, "hit": r.hit_rate,
                          "edge_bps": edge, "edge_lo_bps": lo, "pays": lo > 0, "loses": (r.ci95_median_high * 1e4 - COST_BPS) < 0})
    pairs.sort(key=lambda x: -x["edge_lo_bps"])
    return {"horizon": horizon, "cost_bps": COST_BPS, "min_n": min_n, "symbols": symbols, "table": table, "pairs": pairs,
            "last_bar": time.strftime("%Y-%m-%d", time.gmtime(int(rows[-1][0]) / 1000))}


def render_markdown(ev: Dict[str, Any]) -> str:
    syms = ev["symbols"]
    L = ["# What has actually paid, by setup and symbol", ""]
    L.append("Base rates for a BUY at the signal close, held %d completed daily bars, over every prior occurrence in %d symbols' daily history "
             "(up to 1,000 bars each, through %s). Cell: median forward return / hit rate (n). Bold cells: the lower 95%% bound on the median "
             "beats a %.0f bps round trip, so the setup has paid after cost with some confidence. Struck cells: the upper bound is below cost, so it has reliably lost. "
             "Regenerate with `python3 -m secondopinion evidence`." % (ev["horizon"], len(syms), ev["last_bar"], ev["cost_bps"]))
    L.append("")
    short = [s.replace("USDT", "") for s in syms]
    L.append("| setup | " + " | ".join(short) + " |")
    L.append("|---|" + "---|" * len(syms))
    for s in [x.key for x in SETUPS] + ["ALL_DAYS"]:
        cells = []
        for sym in syms:
            r = ev["table"][sym][s]
            if not r["n"]:
                cells.append("")
                continue
            txt = "%+.1f%% / %.0f%% (%d)" % (100 * r["median_fwd"], 100 * r["hit_rate"], r["n"])
            if s != "ALL_DAYS" and r["n"] >= ev["min_n"]:
                if r["ci95_median_low"] * 1e4 - ev["cost_bps"] > 0:
                    txt = "**%s**" % txt
                elif r["ci95_median_high"] * 1e4 - ev["cost_bps"] < 0:
                    txt = "~~%s~~" % txt
            cells.append(txt)
        L.append("| %s | %s |" % (s, " | ".join(cells)))
    L.append("")
    pays = [p for p in ev["pairs"] if p["pays"]]
    loses = [p for p in ev["pairs"] if p["loses"]]
    L.append("## Setups that have paid after cost (lower CI bound above %.0f bps, n >= %d)" % (ev["cost_bps"], ev["min_n"]))
    L.append("")
    L.append("| symbol | setup | n | median | hit | edge after cost | lower bound |\n|---|---|---|---|---|---|---|")
    for p in pays:
        L.append("| %s | %s | %d | %+.2f%% | %.0f%% | %+.0f bps | %+.0f bps |" % (p["symbol"], p["setup"], p["n"], 100 * p["median"], 100 * p["hit"], p["edge_bps"], p["edge_lo_bps"]))
    L.append("")
    L.append("## Setups that have reliably lost after cost (upper CI bound below cost)")
    L.append("")
    L.append("| symbol | setup | n | median | hit | edge after cost |\n|---|---|---|---|---|---|")
    for p in sorted(loses, key=lambda x: x["edge_bps"]):
        L.append("| %s | %s | %d | %+.2f%% | %.0f%% | %+.0f bps |" % (p["symbol"], p["setup"], p["n"], 100 * p["median"], 100 * p["hit"], p["edge_bps"]))
    L.append("")
    # counts by setup
    L.append("## Tally by setup across symbols")
    L.append("")
    L.append("| setup | symbols where it paid | symbols where it lost | symbols with enough history |\n|---|---|---|---|")
    for s in [x.key for x in SETUPS]:
        ps = [p for p in ev["pairs"] if p["setup"] == s]
        L.append("| %s | %d | %d | %d |" % (s, sum(p["pays"] for p in ps), sum(p["loses"] for p in ps), len(ps)))
    L.append("")
    L.append("These are base rates, not forecasts. They are the numbers Second Opinion puts in front of an AI before it trades, so that 'momentum' or 'dip' is judged by what followed the last time, on this coin, rather than by how the word sounds.")
    return "\n".join(L) + "\n"
