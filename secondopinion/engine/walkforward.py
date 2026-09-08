"""
Walk-forward evaluation of the gate itself.

For every day t in a symbol's history (after a warm-up), ask Second Opinion to judge a
BUY at the close of t using only bars <= t, exactly as it would have on that day, then
record what actually happened over the next h bars. No order book is available for the
past, so cost is the same assumed 30 bps for every day; realized returns are shown gross
and net of that cost. The same `evaluate` function used in production makes every call.
"""
import json
from typing import Any, Dict, List, Optional

from .verdict import Policy, evaluate

WARMUP = 300


def walk_forward(symbol: str, klines: List[list], horizon: int = 3, notional: float = 100.0,
                 start: Optional[int] = None, every: int = 1, cost_bps: float = 30.0) -> Dict[str, Any]:
    completed = klines
    n = len(completed)
    start = WARMUP if start is None else start
    rows: List[Dict[str, Any]] = []
    policy = Policy(horizon_days=horizon, max_data_age_hours=1e9)
    for t in range(start, n - horizon, every):
        window = completed[: t + 1]
        now_ms = int(completed[t][6])
        v = evaluate(symbol, "BUY", notional, window, None, policy, now_ms=now_ms)
        c0, c1 = float(completed[t][4]), float(completed[t + horizon][4])
        gross = c1 / c0 - 1.0
        rows.append({
            "t": t, "date": v.signal_bar_date, "verdict": v.verdict, "primary": v.primary_setup,
            "specific": v.primary_setup not in (None, "ALL_DAYS", "ABOVE_SMA50", "BELOW_SMA50"),
            "edge_bps": v.edge_after_cost_bps, "gross": gross, "net": gross - cost_bps / 1e4,
        })
    return {"symbol": symbol, "horizon": horizon, "cost_bps": cost_bps, "days": len(rows), "rows": rows}


def _stats(rs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rs:
        return {"n": 0}
    g = sorted(r["gross"] for r in rs)
    net = [r["net"] for r in rs]
    mid = g[len(g) // 2] if len(g) % 2 else (g[len(g) // 2 - 1] + g[len(g) // 2]) / 2
    return {
        "n": len(rs),
        "median_gross": mid,
        "mean_gross": sum(g) / len(g),
        "hit_gross": sum(1 for x in g if x > 0) / len(g),
        "mean_net": sum(net) / len(net),
        "sum_net": sum(net),
    }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pool rows across symbols and split by verdict, for all days and for specific-setup days only."""
    pooled: List[Dict[str, Any]] = []
    per_symbol: Dict[str, Any] = {}
    for res in results:
        rows = res["rows"]
        pooled.extend(rows)
        per_symbol[res["symbol"]] = {
            "days": len(rows),
            "by_verdict": {v: _stats([r for r in rows if r["verdict"] == v]) for v in ("APPROVE", "CAUTION", "VETO")},
            "specific_by_verdict": {v: _stats([r for r in rows if r["verdict"] == v and r["specific"]]) for v in ("APPROVE", "CAUTION", "VETO")},
        }
    out = {
        "symbols": [r["symbol"] for r in results],
        "horizon": results[0]["horizon"] if results else None,
        "cost_bps": results[0]["cost_bps"] if results else None,
        "days_total": len(pooled),
        "all_days": _stats(pooled),
        "by_verdict": {v: _stats([r for r in pooled if r["verdict"] == v]) for v in ("APPROVE", "CAUTION", "VETO")},
        "specific_by_verdict": {v: _stats([r for r in pooled if r["verdict"] == v and r["specific"]]) for v in ("APPROVE", "CAUTION", "VETO")},
        "by_setup_and_verdict": {},
        "per_symbol": per_symbol,
    }
    setups = sorted({r["primary"] for r in pooled if r["primary"]})
    for s in setups:
        out["by_setup_and_verdict"][s] = {v: _stats([r for r in pooled if r["primary"] == s and r["verdict"] == v]) for v in ("APPROVE", "CAUTION", "VETO")}
    return out


def render_markdown(summary: Dict[str, Any], generated_note: str = "") -> str:
    def pct(x):
        return "%+.2f%%" % (100 * x)

    def row(label, s):
        if not s or not s.get("n"):
            return "| %s | 0 | | | | |" % label
        return "| %s | %d | %s | %s | %.0f%% | %s |" % (label, s["n"], pct(s["median_gross"]), pct(s["mean_gross"]), 100 * s["hit_gross"], pct(s["mean_net"]))

    hdr = "| verdict | days | median gross | mean gross | hit rate | mean net of %.0f bps |\n|---|---|---|---|---|---|" % summary["cost_bps"]
    L = ["# Does the gate work? A walk-forward evaluation", ""]
    L.append("Every day from bar 300 onward, for each symbol, Second Opinion judged a $100 BUY at that day's close using only the bars available on that day. "
             "The realized return over the next %d completed bars is then recorded. This is out of sample by construction: the base rates that drove each verdict "
             "were computed from bars strictly before the signal bar, and the outcome was not known when the verdict was made. "
             "No order book exists for the past, so every day carries the same assumed %.0f bps round-trip cost. The same `evaluate` function used by the CLI, "
             "the MCP server and the hook produced every verdict. Regenerate with `python3 -m secondopinion evaluate`." % (summary["horizon"], summary["cost_bps"]))
    L.append("")
    if generated_note:
        L.append(generated_note)
        L.append("")
    L.append("Symbols: %s. Days judged: %d." % (", ".join(summary["symbols"]), summary["days_total"]))
    L.append("")
    L.append("## All days, pooled")
    L.append("")
    L.append(hdr)
    for v in ("APPROVE", "CAUTION", "VETO"):
        L.append(row(v, summary["by_verdict"][v]))
    L.append(row("every day (no gate)", summary["all_days"]))
    L.append("")
    L.append("## Days with a specific setup on the chart")
    L.append("")
    L.append("Plain trend-context days are excluded here. These are the days an AI would point at and say 'momentum' or 'dip', and where the gate makes a real call.")
    L.append("")
    L.append(hdr)
    for v in ("APPROVE", "CAUTION", "VETO"):
        L.append(row(v, summary["specific_by_verdict"][v]))
    L.append("")
    L.append("## By primary setup and verdict")
    L.append("")
    L.append("| setup | verdict | days | median gross | mean gross | hit rate | mean net |\n|---|---|---|---|---|---|---|")
    for s, d in summary["by_setup_and_verdict"].items():
        for v in ("APPROVE", "CAUTION", "VETO"):
            st = d[v]
            if st.get("n"):
                L.append("| %s | %s | %d | %s | %s | %.0f%% | %s |" % (s, v, st["n"], pct(st["median_gross"]), pct(st["mean_gross"]), 100 * st["hit_gross"], pct(st["mean_net"])))
    L.append("")
    L.append("## Per symbol")
    L.append("")
    for sym, d in summary["per_symbol"].items():
        L.append("### %s (%d days)" % (sym, d["days"]))
        L.append("")
        L.append(hdr)
        for v in ("APPROVE", "CAUTION", "VETO"):
            L.append(row(v, d["by_verdict"][v]))
        L.append("")
    L.append("## How to read this")
    L.append("")
    L.append("- A gate is useful if vetoed days did worse than approved days out of sample. Compare the VETO and APPROVE rows on the specific-setup table; that is the whole test.")
    L.append("- Base rates are not predictions. The numbers above are what happened over this window on these symbols, and a different window can look different.")
    L.append("- BUY only. The gate judges sells with the sign flipped, but an AI proposing longs is the common case and the one this table measures.")
    return "\n".join(L) + "\n"
