"""Content plan — briefs a generator can actually execute.

Takes a brand, its calendar, its style grammars and (when present) a derived grammar from
studied references, and emits dated briefs. Each brief already carries its style, format,
language mix, generation route and claim verdict, so nothing downstream has to guess.

Three things it does that a list of ideas does not:

  * **Portfolio discipline.** 60% proven / 25% adjacent / 15% exploratory, from brand.yaml.
    Repeating only what worked is how an account goes stale; the exploratory lane is a
    budget for being wrong on purpose.
  * **One factor at a time.** Adjacent items vary exactly one dimension from a proven
    parent — hook, language, style family, CTA, format. Changing three at once produces a
    result you cannot attribute, which means you learn nothing from it.
  * **Approval gates.** claim_class sensitive/pitch items are marked blocked, and a
    generating agent may not clear its own.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, asdict, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

VARY_DIMENSIONS = ["hook", "language", "sheng_intensity", "style_family",
                   "format", "cta", "first_slide"]


@dataclass
class Brief:
    day: int
    date: str
    lane: str                  # proven | adjacent | exploratory
    idea_id: int | None
    title: str
    style_key: str
    format: str
    ratio: str
    language_mix: list[str]
    claim_class: str
    status: str                # ready | blocked_pending_approval
    varies: str | None = None
    parent_id: int | None = None
    route_hint: str = ""
    grammar_constraints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# What each format actually ACCEPTS on platform, in preference order. Instagram takes
# 1:1, 4:5 and 3:4 for a feed post — 4:5 is the taller of those and wins more screen, so
# it leads. Reels and stories are 9:16 and nothing else. Modelling this as a single
# required ratio flagged perfectly publishable 4:5 singles as broken.
FORMAT_RATIOS = {
    "reel":     ["9:16"],
    "story":    ["9:16"],
    "carousel": ["4:5", "1:1", "3:4"],
    "single":   ["4:5", "1:1", "3:4"],
}


def _ratio_for(style: dict[str, Any], fmt: str) -> tuple[str, str | None]:
    """Returns (ratio, warning). Falling back silently produced a 4:5 'reel' — the kind of
    wrong answer that looks like a right one — so a genuine mismatch is now reported."""
    ratios = style.get("ratios") or ["4:5"]
    accepted = FORMAT_RATIOS.get(fmt)
    if not accepted:
        return ratios[0], None
    for want in accepted:
        if want in ratios:
            return want, None
    return ratios[0], (
        f"format `{fmt}` accepts {', '.join(accepted)} but this style grammar declares only "
        f"{', '.join(ratios)}. Using {ratios[0]}, which will not publish as a {fmt}. "
        f"Add an accepted ratio to the grammar, or change the format.")


def load_grammar(brand_root: Path) -> dict[str, Any]:
    """Merge every derived grammar under references/ into a constraint list."""
    out: dict[str, Any] = {"sources": [], "constraints": []}
    for gj in sorted((brand_root / "references").rglob("grammar.json")):
        try:
            g = json.loads(gj.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if g.get("confidence") in ("insufficient", "low"):
            out.setdefault("skipped", []).append(
                f"{g['source']} ({g['confidence']}, {g['samples']} samples)")
            continue
        out["sources"].append(g["source"])
        out["constraints"].extend(g.get("conventions", []))
    return out


def build(brand: Any, days: int, start: date, seed: int = 7,
          grammar: dict[str, Any] | None = None) -> list[Brief]:
    rng = random.Random(seed)
    items = list(brand.calendar.get("items", []))
    if not items:
        raise SystemExit(f"brand {brand.key} has no calendar items to plan from")

    policy = brand.spec.get("portfolio_policy", {"proven": .6, "adjacent": .25, "exploratory": .15})
    n_proven = round(days * policy.get("proven", .6))
    n_adj = round(days * policy.get("adjacent", .25))
    n_exp = max(0, days - n_proven - n_adj)

    constraints = (grammar or {}).get("constraints", [])
    briefs: list[Brief] = []
    pool = items[:]
    rng.shuffle(pool)

    def mk(day: int, lane: str, it: dict[str, Any], varies: str | None = None,
           parent: int | None = None, style_override: str | None = None) -> Brief:
        skey = style_override or it["style_family"]
        style = brand.styles.get(skey, {})
        fmt = it.get("format", "carousel")
        cc = it.get("claim_class", "standard")
        ratio, ratio_warn = _ratio_for(style, fmt)
        b = Brief(
            day=day, date=(start + timedelta(days=day - 1)).isoformat(), lane=lane,
            idea_id=it.get("id"), title=it.get("idea", it.get("title", "untitled")),
            style_key=skey, format=fmt, ratio=ratio,
            language_mix=it.get("language_mix", [brand.spec["languages"]["primary"]])
            if "languages" in brand.spec else it.get("language_mix", ["en"]),
            claim_class=cc,
            status="blocked_pending_approval" if cc in ("sensitive", "pitch") else "ready",
            varies=varies, parent_id=parent,
            route_hint=("comfy (edit/identity/motion)" if fmt in ("carousel", "reel")
                        else "hosted (single still)"),
            grammar_constraints=constraints[:4],
            notes=(["a generating agent may not clear its own approval"] if cc != "standard" else []),
        )
        if ratio_warn:
            b.notes.append(ratio_warn)
            b.status = "blocked_format_mismatch"
        return b

    day = 1
    # proven: straight from the calendar
    for it in pool[:n_proven]:
        briefs.append(mk(day, "proven", it))
        day += 1
    # adjacent: one dimension varied from a proven parent
    parents = briefs[:] or [mk(0, "proven", pool[0])]
    for i in range(n_adj):
        par = parents[i % len(parents)]
        src = next((x for x in items if x["id"] == par.idea_id), items[0])
        dim = VARY_DIMENSIONS[i % len(VARY_DIMENSIONS)]
        override = None
        if dim == "style_family":
            others = [k for k, s in brand.styles.items()
                      if s.get("mode") == brand.styles.get(par.style_key, {}).get("mode")
                      and k != par.style_key]
            override = rng.choice(others) if others else None
            if override is None:
                dim = "hook"
        b = mk(day, "adjacent", src, varies=dim, parent=par.idea_id, style_override=override)
        b.notes.append(f"vary ONLY `{dim}` against day {par.day}; "
                       f"changing more than one makes the result unattributable")
        briefs.append(b)
        day += 1
    # exploratory: a style the calendar has not used yet
    used = {b.style_key for b in briefs}
    unused = [k for k in brand.styles if k not in used and k != "index"]
    for i in range(n_exp):
        src = rng.choice(items)
        override = unused[i % len(unused)] if unused else None
        b = mk(day, "exploratory", src, style_override=override)
        b.notes.append("exploratory lane — budgeted to be wrong; do not judge it on the "
                       "same metric as the proven lane")
        briefs.append(b)
        day += 1
    return briefs


def render(brand_key: str, briefs: list[Brief], grammar: dict[str, Any]) -> str:
    from collections import Counter
    L = [f"# {brand_key} — {len(briefs)}-day content plan", "",
         f"lanes: {dict(Counter(b.lane for b in briefs))} · "
         f"blocked pending approval: {sum(1 for b in briefs if b.status == 'blocked_pending_approval')} · "
         f"format mismatches: {sum(1 for b in briefs if b.status == 'blocked_format_mismatch')}", ""]
    if grammar.get("sources"):
        L += ["## Grammar applied", f"derived from: {', '.join(grammar['sources'])}",
              *[f"- {c}" for c in grammar["constraints"][:8]], ""]
    if grammar.get("skipped"):
        L += ["## Grammar NOT applied",
              *[f"- {s} — below the confidence floor" for s in grammar["skipped"]], ""]
    L += ["| day | date | lane | title | style | format | ratio | status | varies |",
          "|---|---|---|---|---|---|---|---|---|"]
    for b in briefs:
        L.append(f"| {b.day} | {b.date} | {b.lane} | {b.title} | `{b.style_key}` | "
                 f"{b.format} | {b.ratio} | "
                 f"{'' if b.status=='ready' else '**APPROVAL**' if b.status=='blocked_pending_approval' else '**RATIO**'} | "
                 f"{b.varies or ''} |")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a dated content plan for a brand.")
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--start", default=date.today().isoformat())
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    sys.path.insert(0, str(REPO / "packages" / "brandkit"))
    from brandkit import load_brand  # noqa: E402,PLC0415
    b = load_brand(a.brand)

    grammar = load_grammar(b.root)
    briefs = build(b, a.days, date.fromisoformat(a.start), a.seed, grammar)
    md = render(a.brand, briefs, grammar)
    print(md)

    out = a.out or b.root / "calendar" / f"plan-{a.start}-{a.days}d.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    out.with_suffix(".json").write_text(
        json.dumps([asdict(x) for x in briefs], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {out}")
    approve = [x for x in briefs if x.status == "blocked_pending_approval"]
    mismatch = [x for x in briefs if x.status == "blocked_format_mismatch"]
    if approve:
        print()
        print(f"{len(approve)} brief(s) need your approval before generation: "
              f"days {', '.join(str(x.day) for x in approve)}")
    if mismatch:
        print()
        print(f"{len(mismatch)} brief(s) have a format/ratio mismatch and would not "
              f"publish as the stated format: days {', '.join(str(x.day) for x in mismatch)}")
        print(f"  e.g. day {mismatch[0].day}: {mismatch[0].notes[-1]}")


if __name__ == "__main__":
    main()
