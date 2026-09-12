"""Fixture generator shared by the analytics tests.

Wraps packages/analytics/collect.py's fixture mode so a test can ask for "a plan of N days"
without writing files. The planted structure is what the tests assert on: kenyan_meme and
accessibility over-perform on saves, data_magazine under-performs.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
for p in ("brandkit", "strategy", "analytics"):
    sys.path.insert(0, str(REPO / "packages" / p))


def fixture_posts(days: int, seed: int = 11) -> list[dict[str, Any]]:
    from brandkit import load_brand
    from plan import build
    from collect import collect_fixture

    b = load_brand("ongea-pesa")
    briefs = build(b, days, date(2026, 3, 1))
    tmp = REPO / "out" / "analytics" / f"_test-plan-{days}.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps([asdict(x) for x in briefs]), encoding="utf-8")
    posts = collect_fixture("ongea-pesa", tmp, seed)
    out = []
    for p in posts:
        d = asdict(p)
        d["engagement_rate"] = p.engagement_rate
        out.append(d)
    return out
