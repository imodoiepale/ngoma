"""Turn measured performance into facts memory can hold.

This is where the planner's "vary exactly one dimension" rule pays off. Because an adjacent
brief differs from a named proven parent in one declared factor, a difference in outcome is
*attributable*. Without that discipline you get a pile of posts and correlations you cannot
act on.

What it computes, and what it deliberately refuses to compute:

  * **Lift** of a style against the brand's own baseline on a primary metric. Baseline is
    the median of every other style, not the mean — one viral post should not move it.
  * **Factor effects** for adjacent briefs: variant vs its parent, one factor at a time.
  * **Fatigue**: a style whose performance declines across repeated uses in a window.

It does NOT compute p-values or confidence intervals. With 10-30 organic posts, unequal
exposure and no randomisation, a significance test would be decoration on a number that is
not significant — and dressing a weak signal in statistical language is worse than stating
it is weak. Confidence here is derived from sample size and effect size, and it is capped.

Every fact written carries its source. Facts derived from `source: fixture` data are
written with `kind: learning_fixture` and a note, so the skill curator can be told to
ignore them and a human reading the vault cannot be misled.
"""
from __future__ import annotations

import argparse
import json
import statistics as stats
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "memory"))

PRIMARY = "saves"        # the metric this brand optimises; override with --metric
CONF_CAP = 0.85          # observational data never earns more than this
MIN_EFFECT_PCT = 8.0     # smaller than this is not worth naming
MIN_SEPARATION = 1.15    # |effect| must exceed this multiple of the group's own spread

# THE IMPORTANT NUMBER. Below this many posts, a per-grammar claim is not underpowered,
# it is meaningless, and no statistic rescues it.
#
# This was discovered rather than chosen. At 3 posts per grammar the analysis confidently
# reported a grammar as +28% when it had been deliberately seeded to UNDER-perform, and
# suppressed the strongest true signal in the same run. Adding a within-group spread test
# swapped which one was wrong without making either right - because with n=3 the spread
# estimate is itself the median of three deviations, so it is as noisy as the thing it is
# meant to police.
#
# The fix is not a cleverer statistic. It is to refuse the question until there is enough
# data to answer it, and to say exactly how much more is needed.
MIN_POSTS_PER_STYLE = 6
MIN_FACTOR_PAIRS = 3     # matched pairs needed before a factor effect is named


@dataclass
class Finding:
    subject: str
    predicate: str
    object: str | None
    value: float | None
    unit: str | None
    sample_size: int
    confidence: float
    note: str
    audience: str | None = None
    fixture: bool = False


def load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"no analytics at {path} — run packages/analytics/collect.py first")
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _rate(p: dict[str, Any], metric: str) -> float | None:
    """Per-reach rate, so a post that simply reached more people does not look better."""
    m = p.get("metrics", {})
    reach = m.get("reach") or m.get("impressions")
    if not reach:
        return None
    if metric == "engagement_rate":
        return p.get("engagement_rate")
    v = m.get(metric)
    return None if v is None else v / reach


def _spread_pct(vals: list[float], base: float) -> float:
    """The group's own variability, as a percentage of the comparison baseline.

    Median absolute deviation rather than standard deviation: with 3-5 observations a
    single outlier dominates an SD, and outliers are exactly what small organic samples
    are made of.
    """
    if len(vals) < 2 or base <= 0:
        return 0.0
    med = stats.median(vals)
    mad = stats.median([abs(v - med) for v in vals]) or 0.0
    return mad / base * 100


def _confidence(n: int, effect_pct: float, separation: float = 2.0) -> float:
    """Sample size and effect size, capped. Observational data does not earn certainty."""
    size = min(1.0, n / 12)
    effect = min(1.0, abs(effect_pct) / 30)
    sep = min(1.0, max(0.0, (separation - 1.0) / 2.0))
    return round(min(CONF_CAP, 0.20 + 0.25 * size + 0.25 * effect + 0.30 * sep), 2)


def power_report(posts: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    """Can this dataset support per-grammar claims at all? Answer that before answering
    anything else, because an underpowered study does not produce weak findings - it
    produces confident wrong ones."""
    by_style: dict[str, list[float]] = defaultdict(list)
    for p in posts:
        r = _rate(p, metric)
        if r is not None and p.get("style_key"):
            by_style[p["style_key"]].append(r)
    counts = {k: len(v) for k, v in sorted(by_style.items(), key=lambda kv: -len(kv[1]))}
    usable = [k for k, n in counts.items() if n >= MIN_POSTS_PER_STYLE]
    need = sum(max(0, MIN_POSTS_PER_STYLE - n) for n in counts.values())
    return {
        "posts": len(posts),
        "grammars_used": len(counts),
        "posts_per_grammar": counts,
        "usable_grammars": usable,
        "min_required": MIN_POSTS_PER_STYLE,
        "additional_posts_needed": need,
        "can_support_claims": len(usable) >= 2,
    }


def style_effects(posts: list[dict[str, Any]], metric: str) -> list[Finding]:
    by_style: dict[str, list[float]] = defaultdict(list)
    for p in posts:
        r = _rate(p, metric)
        if r is not None and p.get("style_key"):
            by_style[p["style_key"]].append(r)

    usable = {k: v for k, v in by_style.items() if len(v) >= MIN_POSTS_PER_STYLE}
    out: list[Finding] = []
    if len(usable) < 2:
        return out
    fixture = any(p.get("source") == "fixture" for p in posts)

    for style, vals in usable.items():
        others = [x for k, v in usable.items() if k != style for x in v]
        if not others:
            continue
        base = stats.median(others)
        mine = stats.median(vals)
        if base <= 0:
            continue
        lift = (mine - base) / base * 100
        if abs(lift) < MIN_EFFECT_PCT:
            continue                     # below this it is noise, not a finding

        # Does the gap survive the group's own scatter?
        spread = _spread_pct(vals, base)
        separation = abs(lift) / spread if spread > 0 else 99.0
        if separation < MIN_SEPARATION:
            continue

        out.append(Finding(
            subject=style,
            predicate="performed_well_for" if lift > 0 else "underperformed_for",
            object=metric, value=round(lift, 1), unit="% vs median",
            sample_size=len(vals),
            confidence=_confidence(len(vals), lift, separation),
            fixture=fixture,
            note=(f"median {metric}/reach {mine:.4f} against a baseline of {base:.4f} "
                  f"from {len(others)} post(s) in other grammars; the effect is "
                  f"{separation:.1f}x this grammar's own spread")))
    suppressed = len([k for k, v in usable.items()]) - len(out)
    if suppressed > 0:
        out.append(Finding(
            subject="__suppressed__", predicate="note", object=None, value=None, unit=None,
            sample_size=suppressed, confidence=0.0, fixture=fixture,
            note=(f"{suppressed} grammar(s) showed a gap but it did not clear their own "
                  f"scatter, or fell under {MIN_EFFECT_PCT}%. Reported as nothing rather "
                  f"than as a weak finding.")))
    return sorted(out, key=lambda f: -abs(f.value or 0))


def factor_effects(posts: list[dict[str, Any]], metric: str) -> list[Finding]:
    """Adjacent briefs vs their parent. One factor differs, so the delta is attributable."""
    by_day = {p["brief_day"]: p for p in posts if p.get("brief_day")}
    by_idea = defaultdict(list)
    for p in posts:
        if p.get("campaign_id"):
            by_idea[p["campaign_id"]].append(p)

    out: list[Finding] = []
    fixture = any(p.get("source") == "fixture" for p in posts)
    grouped: dict[str, list[float]] = defaultdict(list)
    for p in posts:
        if p.get("lane") != "adjacent" or not p.get("varies") or not p.get("parent_id"):
            continue
        parent = next((q for q in posts
                       if q.get("campaign_id", "").endswith(f"idea{p['parent_id']:02d}")), None)
        if not parent:
            continue
        a, b = _rate(p, metric), _rate(parent, metric)
        if a is None or b is None or b <= 0:
            continue
        grouped[p["varies"]].append((a - b) / b * 100)

    for factor, deltas in grouped.items():
        if len(deltas) < MIN_FACTOR_PAIRS:
            continue                      # one or two comparisons is an anecdote
        med = stats.median(deltas)
        if abs(med) < 8:
            continue
        out.append(Finding(
            subject=f"factor:{factor}", predicate="changes",
            object=metric, value=round(med, 1), unit="% median delta",
            sample_size=len(deltas), confidence=_confidence(len(deltas), med),
            fixture=fixture,
            note=(f"varying `{factor}` alone moved {metric}/reach by a median of {med:+.1f}% "
                  f"across {len(deltas)} matched pair(s)")))
    return out


def fatigue(posts: list[dict[str, Any]], metric: str) -> list[Finding]:
    """A style used repeatedly whose later uses do worse than its earlier ones."""
    by_style: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for p in posts:
        r = _rate(p, metric)
        if r is not None and p.get("style_key") and p.get("published_at"):
            by_style[p["style_key"]].append((p["published_at"], r))

    out: list[Finding] = []
    fixture = any(p.get("source") == "fixture" for p in posts)
    for style, seq in by_style.items():
        if len(seq) < 4:
            continue                      # need enough uses to see a trend at all
        seq.sort()
        half = len(seq) // 2
        early = stats.median([v for _, v in seq[:half]])
        late = stats.median([v for _, v in seq[half:]])
        if early <= 0:
            continue
        drop = (late - early) / early * 100
        if drop > -15:
            continue
        out.append(Finding(
            subject=style, predicate="fatigued_for", object=metric,
            value=round(drop, 1), unit="% decline", sample_size=len(seq),
            confidence=_confidence(len(seq), drop), fixture=fixture,
            note=(f"later uses median {late:.4f} against {early:.4f} earlier across "
                  f"{len(seq)} uses — rest the grammar rather than retire it")))
    return out


def write_to_memory(brand: str, findings: list[Finding], source: str,
                    audience: str | None = None) -> tuple[int, int]:
    from store import Fact, connect, record, believed  # noqa: PLC0415

    con = connect()
    live = {(r["subject"], r["predicate"]): r for r in believed(con, brand)}
    added = superseded = 0
    for f in findings:
        if f.subject == "__suppressed__":
            continue                     # housekeeping, not a claim
        kind = "learning_fixture" if f.fixture else "learning"
        note = f.note
        if f.fixture:
            note = ("SYNTHETIC — derived from fixture data, not measurement. "
                    "Do not act on this. ") + note
        prev = live.get((f.subject, f.predicate))
        fact = Fact(brand=brand, kind=kind, subject=f.subject, predicate=f.predicate,
                    object=f.object, value=f.value, unit=f.unit,
                    audience=audience or f.audience, platform="instagram",
                    confidence=f.confidence, sample_size=f.sample_size,
                    source=source, note=note)
        if prev:
            from store import supersede  # noqa: PLC0415
            supersede(con, int(prev["id"]), fact)
            superseded += 1
        else:
            record(con, fact)
            added += 1
    return added, superseded


def main() -> None:
    ap = argparse.ArgumentParser(description="Derive learnings from collected analytics.")
    ap.add_argument("--brand", default="ongea-pesa")
    ap.add_argument("--data", type=Path, required=True, help="the .jsonl from collect.py")
    ap.add_argument("--metric", default=PRIMARY,
                    help=f"primary metric (default {PRIMARY}); or engagement_rate")
    ap.add_argument("--audience", help="who these posts reached, if you know")
    ap.add_argument("--write", action="store_true", help="write findings into memory")
    a = ap.parse_args()

    posts = load(a.data)
    fixture = any(p.get("source") == "fixture" for p in posts)
    findings = (style_effects(posts, a.metric) + factor_effects(posts, a.metric)
                + fatigue(posts, a.metric))

    print(f"=== {a.brand} — {len(posts)} post(s), primary metric `{a.metric}`")
    if fixture:
        print("!!  SYNTHETIC DATA. Findings below are shaped like real ones and are not real.")

    pw = power_report(posts, a.metric)
    print(f"\npower: {pw['grammars_used']} grammar(s) across {pw['posts']} post(s); "
          f"{len(pw['usable_grammars'])} have the {pw['min_required']}+ posts a per-grammar "
          f"claim needs")
    if not pw["can_support_claims"]:
        print(f"  spread too thin: {pw['posts_per_grammar']}")
        print(f"  NO per-grammar findings will be reported. This dataset cannot support "
              f"them.")
        print(f"  You need roughly {pw['additional_posts_needed']} more post(s), or fewer "
              f"grammars in rotation.")
        print(f"  An underpowered study does not give weak answers - it gives confident "
              f"wrong ones.")
    real = [f for f in findings if f.subject != "__suppressed__"]
    if not real:
        print("no finding cleared the noise floor (8% effect, 2+ posts per group).")
        print("That is a legitimate outcome, not a failure — most weeks say nothing.")
        return

    for f in findings:
        if f.subject == "__suppressed__":
            continue
        print(f"  {f.subject:<28} {f.predicate:<22} {f.value:+.1f}{f.unit or ''}"
              f"  n={f.sample_size} conf={f.confidence}")
        print(f"      {f.note}")
    for f in findings:
        if f.subject == "__suppressed__":
            print(f"\n  suppressed: {f.note}")

    if a.write:
        src = "fixture" if fixture else str(a.data.name)
        added, sup = write_to_memory(a.brand, findings, src, a.audience)
        print(f"\nmemory: {added} new fact(s), {sup} superseded")
        print("  run: uv run packages/memory/store.py believed")
    else:
        print("\n(pass --write to record these in memory)")


if __name__ == "__main__":
    main()
