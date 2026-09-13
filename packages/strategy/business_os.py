"""Business OS: turn brands/_business/ideas.yaml into costed ideas, offers and MRR.

Inputs are prices, client counts and resource use per client. Everything else — monthly
cost, MRR, margin, payback — is computed here with packages/strategy/unit_economics.py, so
docs/business/IDEAS-50.md, OFFERS.md and the Notion rows can never disagree.

    uv run --with pyyaml packages/strategy/business_os.py          # write docs
    uv run --with pyyaml packages/strategy/business_os.py --json   # rows for Notion

Every figure is a planning estimate. The docs say so at the top, and each GPU rate carries
its basis (measured / contract / assumed).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from unit_economics import GPU_RATES  # noqa: E402

IDEAS = REPO / "brands" / "_business" / "ideas.yaml"
DOCS = REPO / "docs" / "business"
REQUIRED = ("id", "family", "name", "buyer", "offer", "pipeline", "backend", "price_usd",
            "clients", "gpu_hours", "api_usd", "setup_usd", "fixed_usd", "first_cash_days",
            "risk", "compliance", "evidence")
EXPECTED_COUNT = 50


class IdeaError(ValueError):
    pass


@dataclass
class Costed:
    idea: dict[str, Any]
    cost_per_client: float
    scenarios: dict[str, dict[str, float]]

    @property
    def base(self) -> dict[str, float]:
        return self.scenarios["base"]


def load(path: Path = IDEAS) -> dict[str, Any]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    ideas = doc.get("ideas") or []
    problems = []
    if len(ideas) != EXPECTED_COUNT:
        problems.append(f"expected {EXPECTED_COUNT} ideas, found {len(ideas)}")
    ids = [i.get("id") for i in ideas]
    if len(set(ids)) != len(ids):
        problems.append("duplicate idea ids")
    for i in ideas:
        missing = [k for k in REQUIRED if k not in i]
        if missing:
            problems.append(f"{i.get('id')}: missing {missing}")
            continue
        if i["family"] not in doc["families"]:
            problems.append(f"{i['id']}: unknown family {i['family']!r}")
        c = i["clients"]
        if not (isinstance(c, list) and len(c) == 3 and 0 <= c[0] <= c[1] <= c[2]):
            problems.append(f"{i['id']}: clients must be [low <= base <= high]")
        for k in ("price_usd", "gpu_hours", "api_usd", "setup_usd", "fixed_usd", "first_cash_days"):
            if not isinstance(i[k], (int, float)) or i[k] < 0:
                problems.append(f"{i['id']}: {k} must be a non-negative number")
        if i["family"] == "adult" and "HARD GATES" not in i["compliance"] and "hard gates" not in i["compliance"]:
            problems.append(f"{i['id']}: adult ideas must state their hard compliance gates")
    if problems:
        raise IdeaError("; ".join(problems))
    return doc


# GPU and API spend alone made every service look 95%+ margin. People's time is the real
# cost of a creative service, so it is priced in. ASSUMED: a Nairobi-based operator at
# $15/h, and 5% for payment processing and platform fees.
LABOR_USD_PER_HOUR = 15.0
FEE_RATE = 0.05
# Hours of human work per client-month by family (briefing, QA, revisions, reporting).
# Ideas sold per unit ("units = ...") use UNIT_LABOR_HOURS instead.
LABOR_HOURS = {"volume": 6, "ugc": 10, "persona": 12, "music": 20, "service": 6,
               "education": 3, "saas": 0.25, "adult": 6}
UNIT_LABOR_HOURS = 0.25


def labor_hours(idea: dict[str, Any]) -> float:
    if "labor_hours" in idea:
        return float(idea["labor_hours"])
    if "units =" in idea.get("buyer", "") + idea.get("offer", ""):
        return UNIT_LABOR_HOURS
    return float(LABOR_HOURS[idea["family"]])


def cost(idea: dict[str, Any], gpu: str = "a100-80gb") -> Costed:
    rate = GPU_RATES[idea.get("gpu", gpu)].usd_per_hour
    per_client = round(idea["gpu_hours"] * rate + idea["api_usd"]
                       + labor_hours(idea) * LABOR_USD_PER_HOUR
                       + idea["price_usd"] * FEE_RATE, 2)
    scenarios = {}
    for name, n in zip(("low", "base", "high"), idea["clients"]):
        mrr = round(n * idea["price_usd"], 2)
        variable = round(n * per_client, 2)
        total_cost = round(variable + idea["fixed_usd"], 2)
        profit = round(mrr - total_cost, 2)
        scenarios[name] = {
            "clients": n, "mrr": mrr, "monthly_cost": total_cost, "profit": profit,
            "margin": round(profit / mrr, 3) if mrr else 0.0,
            "payback_months": round(idea["setup_usd"] / profit, 1) if profit > 0 else None,
        }
    return Costed(idea, per_client, scenarios)


def costed_all(doc: dict[str, Any]) -> list[Costed]:
    return [cost(i) for i in doc["ideas"]]


def _money(x: float | None) -> str:
    return "—" if x is None else f"${x:,.0f}"


def render_ideas(doc: dict[str, Any], rows: list[Costed]) -> str:
    rate = GPU_RATES["a100-80gb"]
    out = [
        "# 50 ideas, costed",
        "",
        f"Generated from `brands/_business/ideas.yaml` by `packages/strategy/business_os.py` "
        f"(as of {doc['as_of']}). Do not edit by hand.",
        "",
        "> **Planning estimates, not forecasts.** Client counts are scenarios. GPU cost uses "
        f"{rate.name} at ${rate.usd_per_hour}/h ({rate.basis}: {rate.source}). Image throughput "
        "is measured on our pod (444/GPU-hour); video throughput is assumed until measured.",
        "",
    ]
    totals = {k: sum(r.scenarios[k]["mrr"] for r in rows) for k in ("low", "base", "high")}
    out += ["| Scenario | Combined MRR if every idea hit it |", "|---|---|"]
    out += [f"| {k} | {_money(v)} |" for k, v in totals.items()]
    out += ["", "Nobody runs 50 ideas at once. Use the table to pick 3-5 with fast first cash, "
            "high margin and low setup, then prove them.", ""]
    for fam, title in doc["families"].items():
        fam_rows = [r for r in rows if r.idea["family"] == fam]
        if not fam_rows:
            continue
        out += [f"## {title}", "",
                "| ID | Idea | Buyer | Price | Cost / client | MRR low · base · high | Base profit | Margin | Setup | Payback | First cash |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in fam_rows:
            i, s = r.idea, r.scenarios
            out.append(
                f"| {i['id']} | **{i['name']}** | {i['buyer']} | {_money(i['price_usd'])} | "
                f"{_money(r.cost_per_client)} | {_money(s['low']['mrr'])} · {_money(s['base']['mrr'])} · "
                f"{_money(s['high']['mrr'])} | {_money(s['base']['profit'])} | {s['base']['margin']:.0%} | "
                f"{_money(i['setup_usd'])} | "
                f"{'—' if s['base']['payback_months'] is None else str(s['base']['payback_months']) + ' mo'} | "
                f"{i['first_cash_days']} d |")
        out.append("")
        for r in fam_rows:
            i = r.idea
            out += [f"**{i['id']} {i['name']}.** {i['offer']}. Pipeline: `{' → '.join(map(str, i['pipeline']))}` "
                    f"on **{i['backend']}**. Evidence: {i['evidence']}. Risk: {i['risk']}. "
                    f"Compliance: {i['compliance']}.", ""]
    return "\n".join(out)


def render_offers(doc: dict[str, Any], rows: list[Costed]) -> str:
    pick = sorted(rows, key=lambda r: (r.idea["first_cash_days"], -r.base["margin"], r.idea["setup_usd"]))
    out = ["# Offers to sell first", "",
           "Ranked by days to first cash, then base margin, then setup budget. Generated; do not edit.", "",
           "| Rank | Offer | Who buys | Price | What they get | Base margin | Setup |",
           "|---|---|---|---|---|---|---|"]
    for n, r in enumerate(pick[:15], 1):
        i = r.idea
        out.append(f"| {n} | **{i['name']}** ({i['id']}) | {i['buyer']} | {_money(i['price_usd'])} | "
                   f"{i['offer']} | {r.base['margin']:.0%} | {_money(i['setup_usd'])} |")
    return "\n".join(out) + "\n"


def notion_rows(rows: list[Costed], families: dict[str, str]) -> list[dict[str, Any]]:
    return [{
        "Key": r.idea["id"], "Idea": r.idea["name"], "Family": families[r.idea["family"]],
        "Buyer": r.idea["buyer"], "Offer": r.idea["offer"], "Backend": r.idea["backend"],
        "Price USD": r.idea["price_usd"], "Cost per client USD": r.cost_per_client,
        "MRR low": r.scenarios["low"]["mrr"], "MRR base": r.base["mrr"], "MRR high": r.scenarios["high"]["mrr"],
        "Base margin": r.base["margin"], "Setup budget USD": r.idea["setup_usd"],
        "Monthly fixed USD": r.idea["fixed_usd"], "First cash days": r.idea["first_cash_days"],
        "Risk": r.idea["risk"], "Compliance": r.idea["compliance"], "Evidence": r.idea["evidence"],
    } for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description="Cost the 50 ideas and write docs/business/.")
    ap.add_argument("--json", action="store_true", help="print Notion-ready rows instead of writing docs")
    a = ap.parse_args()
    doc = load()
    rows = costed_all(doc)
    if a.json:
        print(json.dumps(notion_rows(rows, doc["families"]), indent=2, ensure_ascii=False))
        return 0
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "IDEAS-50.md").write_text(render_ideas(doc, rows), encoding="utf-8")
    (DOCS / "OFFERS.md").write_text(render_offers(doc, rows), encoding="utf-8")
    base = sum(r.base["mrr"] for r in rows)
    print(f"{len(rows)} ideas costed; combined base MRR {_money(base)} -> docs/business/IDEAS-50.md, OFFERS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
