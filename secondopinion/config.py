"""Policy discovery: env var, then ./second_opinion.policy.json, then ~/.second_opinion/policy.json, else defaults."""
import json
import os
from pathlib import Path
from typing import Optional, Tuple

from .engine.verdict import Policy


def load_policy(explicit: Optional[str] = None) -> Tuple[Policy, str]:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("SECOND_OPINION_POLICY"):
        candidates.append(Path(os.environ["SECOND_OPINION_POLICY"]))
    candidates.append(Path.cwd() / "second_opinion.policy.json")
    candidates.append(Path.home() / ".second_opinion" / "policy.json")
    for c in candidates:
        if c.exists():
            return Policy.from_dict(json.loads(c.read_text(encoding="utf-8"))), str(c)
    return Policy(), "defaults"


def fixtures_dir() -> Optional[Path]:
    p = Path(__file__).resolve().parent.parent / "fixtures"
    return p if p.exists() else None
