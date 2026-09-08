"""Append-only, hash-chained audit log. Each line: {ts, prev, body_sha256, entry}."""
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = Path(os.environ.get("SECOND_OPINION_AUDIT", Path.home() / ".second_opinion" / "audit.jsonl"))


def _canon(d: Any) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def append(entry: Dict[str, Any], path: Path = DEFAULT_PATH) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = "0" * 64
    if path.exists():
        with open(path, "rb") as f:
            try:
                f.seek(-min(65536, path.stat().st_size), 2)
            except OSError:
                pass
            tail = f.read().decode("utf-8", "ignore").strip().splitlines()
            if tail:
                try:
                    prev = json.loads(tail[-1])["line_sha256"]
                except Exception:
                    pass
    body_hash = hashlib.sha256(_canon(entry).encode()).hexdigest()
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "prev": prev, "body_sha256": body_hash, "entry": entry}
    rec["line_sha256"] = hashlib.sha256(_canon({k: rec[k] for k in ("ts", "prev", "body_sha256", "entry")}).encode()).hexdigest()
    with open(path, "a", encoding="utf-8") as f:
        f.write(_canon(rec) + "\n")
    return rec


def read(limit: int = 20, path: Path = DEFAULT_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(l) for l in lines[-limit:]]


def verify(path: Path = DEFAULT_PATH) -> Dict[str, Any]:
    """Recompute the chain. Returns {ok, entries, first_bad}."""
    if not path.exists():
        return {"ok": True, "entries": 0, "first_bad": None}
    prev = "0" * 64
    for n, line in enumerate(path.read_text(encoding="utf-8").strip().splitlines(), 1):
        rec = json.loads(line)
        if rec["prev"] != prev:
            return {"ok": False, "entries": n, "first_bad": n}
        body = hashlib.sha256(_canon(rec["entry"]).encode()).hexdigest()
        if body != rec["body_sha256"]:
            return {"ok": False, "entries": n, "first_bad": n}
        ls = hashlib.sha256(_canon({k: rec[k] for k in ("ts", "prev", "body_sha256", "entry")}).encode()).hexdigest()
        if ls != rec["line_sha256"]:
            return {"ok": False, "entries": n, "first_bad": n}
        prev = rec["line_sha256"]
    return {"ok": True, "entries": n, "first_bad": None}
