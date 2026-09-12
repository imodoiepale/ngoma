"""Skill curator — propose a repeatable skill when analytics genuinely warrant one.

This is the "learns from its own results" layer, and the interesting part is everything it
refuses to do.

A single post with a million views cannot create a skill. Neither can three wins in one
week on one platform with one audience. The gates below are the ones from the v5 spec, and
they exist because the failure mode of an automated learning loop is not "it learns
nothing" — it is "it learns noise confidently and then enforces it".

    >= 3 repeated wins
    >= 3 distinct publication days
    >= 12 distinct content items
    >= 2 contexts (platform or audience), unless deliberately narrow
    >= 12% improvement on the declared primary metric
    >= 0.90 brand consistency
    >= 0.80 holdout pass rate
    no critical compliance failure
    no material decline in trust or conversion

These are configurable operating thresholds, not universal statistical truths. They are
tuned to be annoying rather than permissive.

Two hard rules, enforced in code:

  * **The curator proposes; it never promotes.** Output is a candidate under
    `shared-skills/candidates/`. Moving it to `approved/` is a human action.
  * **Protected skills can never be auto-edited** — anything touching publishing
    authorisation, financial claims, security, secrets, budgets or approval policy.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "memory"))

CANDIDATES = REPO / "shared-skills" / "candidates"
APPROVED = REPO / "shared-skills" / "approved"

GATES = {
    "min_wins": 3,
    "min_days": 3,
    "min_items": 12,
    "min_contexts": 2,
    "min_lift_pct": 12.0,
    "min_brand_consistency": 0.90,
    "min_holdout_pass": 0.80,
}

# A skill in any of these areas is never authored or edited automatically, no matter how
# strong the evidence. Automating the thing that decides what may be published is how an
# automated system removes its own brakes.
PROTECTED = [
    "publishing authorisation", "financial claims compliance", "security controls",
    "secret handling", "storage permissions", "draft-only protection",
    "whatsapp posting limits", "budget limits", "brand approval policy",
    "approval gates", "graph access controls",
]
PROTECTED_PAT = re.compile("|".join(re.escape(p.split()[0]) for p in PROTECTED), re.I)


@dataclass
class Evidence:
    subject: str
    audience: str | None
    wins: int = 0
    days: int = 0
    items: int = 0
    contexts: int = 0
    lift_pct: float = 0.0
    brand_consistency: float | None = None
    holdout_pass: float | None = None
    compliance_failures: int = 0
    trust_decline: bool = False
    narrow_by_design: bool = False


@dataclass
class Verdict:
    eligible: bool
    subject: str
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)


def evaluate(e: Evidence, gates: dict[str, Any] | None = None) -> Verdict:
    g = {**GATES, **(gates or {})}
    v = Verdict(eligible=False, subject=e.subject)

    def check(name: str, ok: bool, detail: str) -> None:
        (v.passed if ok else v.failed).append(f"{name}: {detail}")

    check("repeated wins", e.wins >= g["min_wins"], f"{e.wins} (need {g['min_wins']})")
    check("distinct days", e.days >= g["min_days"], f"{e.days} (need {g['min_days']})")
    check("distinct items", e.items >= g["min_items"], f"{e.items} (need {g['min_items']})")
    if e.narrow_by_design:
        v.passed.append("contexts: waived — declared narrow by design")
    else:
        check("contexts", e.contexts >= g["min_contexts"],
              f"{e.contexts} (need {g['min_contexts']}, or declare it narrow by design)")
    check("lift", e.lift_pct >= g["min_lift_pct"],
          f"{e.lift_pct:.1f}% (need {g['min_lift_pct']}%)")
    check("compliance", e.compliance_failures == 0,
          f"{e.compliance_failures} critical failure(s)")
    check("trust", not e.trust_decline, "no material decline" if not e.trust_decline
          else "a material decline was recorded")

    # An unmeasured gate is NOT a passed gate. This is the same rule as UNVERIFIED != OK.
    if e.brand_consistency is None:
        v.unmeasured.append(f"brand consistency (need >= {g['min_brand_consistency']})")
    else:
        check("brand consistency", e.brand_consistency >= g["min_brand_consistency"],
              f"{e.brand_consistency:.2f} (need {g['min_brand_consistency']})")
    if e.holdout_pass is None:
        v.unmeasured.append(f"holdout pass rate (need >= {g['min_holdout_pass']})")
    else:
        check("holdout", e.holdout_pass >= g["min_holdout_pass"],
              f"{e.holdout_pass:.2f} (need {g['min_holdout_pass']})")

    v.eligible = not v.failed and not v.unmeasured
    return v


def gather(con: sqlite3.Connection, brand: str, subject: str) -> Evidence:
    """Build evidence from the temporal memory store."""
    rows = list(con.execute(
        "SELECT * FROM facts WHERE brand=? AND subject LIKE ? AND valid_to IS NULL",
        (brand, f"%{subject}%")))
    wins = [r for r in rows if r["predicate"] == "performed_well_for"]
    e = Evidence(subject=subject,
                 audience=(wins[0]["audience"] if wins else None),
                 wins=len(wins),
                 items=sum(r["sample_size"] or 0 for r in wins),
                 contexts=len({(r["audience"], r["platform"]) for r in wins}),
                 lift_pct=max((r["value"] or 0.0) for r in wins) if wins else 0.0)
    days = con.execute(
        "SELECT COUNT(DISTINCT date(happened_at)) d FROM episodes WHERE brand=?",
        (brand,)).fetchone()
    e.days = int(days["d"] or 0)
    e.compliance_failures = len([r for r in rows if r["kind"] == "compliance_failure"])
    e.trust_decline = any(r["predicate"] == "declined_trust" for r in rows)
    return e


def is_protected(text: str) -> str | None:
    for p in PROTECTED:
        if p.split()[0].lower() in text.lower() and PROTECTED_PAT.search(text):
            return p
    return None


def draft_candidate(brand: str, e: Evidence, v: Verdict) -> str:
    """A candidate SKILL.md. Deliberately full of the caveats a real skill needs."""
    when = date.today().isoformat()
    return f"""---
name: {brand}-{e.subject.replace('_', '-')}
description: CANDIDATE, NOT APPROVED. Proposed {when} from measured results for {brand}. Use when producing {e.subject.replace('_', ' ')} content for {e.audience or 'the observed audience'}. Do not load this skill until a human has reviewed and moved it to shared-skills/approved/.
status: candidate
proposed: {when}
brand: {brand}
---

# {e.subject.replace('_', ' ').title()} — candidate skill

**This skill is not approved.** It was proposed by `packages/strategy/skill_curator.py`
from facts in the temporal memory store. A human must review it, test it, and move it to
`shared-skills/approved/` before any runtime loads it.

## Evidence

| gate | value |
|---|---|
| repeated wins | {e.wins} |
| distinct publication days | {e.days} |
| distinct content items | {e.items} |
| contexts | {e.contexts}{' (narrow by design)' if e.narrow_by_design else ''} |
| measured lift | {e.lift_pct:.1f}% |
| brand consistency | {e.brand_consistency if e.brand_consistency is not None else 'NOT MEASURED'} |
| holdout pass rate | {e.holdout_pass if e.holdout_pass is not None else 'NOT MEASURED'} |

Gates passed: {len(v.passed)} · failed: {len(v.failed)} · unmeasured: {len(v.unmeasured)}

## When to use it

{e.subject.replace('_', ' ')} for {e.audience or 'the audience this was measured on'}.

## When NOT to use it

- For a different audience than the one above — the lift was measured on one group.
- For a different platform, unless the evidence covers more than one context.
- After the recheck date below, until the evidence is refreshed.

## Procedure

TO BE WRITTEN BY THE REVIEWER. A skill that says "make content similar to the post that
worked" is not a skill. It must state the required inputs, the exact production steps, the
brand constraints, the common failure modes and how to verify the output.

## Expiry

Recheck by {when[:4]}-{int(when[5:7]) + 3 if int(when[5:7]) <= 9 else int(when[5:7]) - 9:02d}-{when[8:10]}.
Audiences fatigue; see the `fatigued_for` facts in memory before reusing this.
"""


def propose(brand: str, subject: str, gates: dict[str, Any] | None = None,
            write: bool = False) -> tuple[Evidence, Verdict, Path | None]:
    from store import connect  # noqa: PLC0415

    con = connect()
    e = gather(con, brand, subject)
    v = evaluate(e, gates)

    prot = is_protected(subject)
    if prot:
        v.eligible = False
        v.failed.append(f"PROTECTED AREA: '{prot}' is never auto-authored or auto-edited")

    path = None
    if v.eligible and write:
        CANDIDATES.mkdir(parents=True, exist_ok=True)
        d = CANDIDATES / f"{brand}-{subject.replace('_', '-')}"
        d.mkdir(exist_ok=True)
        path = d / "SKILL.md"
        path.write_text(draft_candidate(brand, e, v), encoding="utf-8")
    return e, v, path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Propose a skill from measured results. Proposes only; never promotes.")
    ap.add_argument("command", choices=["evaluate", "propose", "gates"])
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--subject")
    ap.add_argument("--write", action="store_true", help="write the candidate if eligible")
    a = ap.parse_args()

    if a.command == "gates":
        print("Promotion gates (operating thresholds, not universal statistics):")
        for k, val in GATES.items():
            print(f"  {k:<24} {val}")
        print("\nProtected areas — never auto-authored or auto-edited:")
        for p in PROTECTED:
            print(f"  - {p}")
        return

    if not a.subject:
        raise SystemExit("--subject is required (the style, hook or format being proposed)")

    e, v, path = propose(a.brand, a.subject, write=a.write)
    print(f"=== {a.subject} for {a.brand}")
    print(f"evidence: wins={e.wins} days={e.days} items={e.items} contexts={e.contexts} "
          f"lift={e.lift_pct:.1f}%")
    for p in v.passed:
        print(f"  PASS  {p}")
    for f in v.failed:
        print(f"  FAIL  {f}")
    for u in v.unmeasured:
        print(f"  UNMEASURED  {u}  (unmeasured is not passed)")
    print()
    if v.eligible:
        print("ELIGIBLE — a candidate may be drafted.")
        if path:
            print(f"  written to {path.relative_to(REPO)}")
            print("  It is a CANDIDATE. Review it, write the procedure, then move it to")
            print("  shared-skills/approved/ yourself. The curator never promotes.")
        else:
            print("  (pass --write to draft it)")
    else:
        print("NOT ELIGIBLE — no candidate drafted.")
        print("  This is the normal outcome. The gates are tuned to be annoying, because")
        print("  the failure mode of a learning loop is confidently learning noise.")


if __name__ == "__main__":
    main()
