"""Study a reference body of work and derive its GRAMMAR — never its images.

This is the "clone someone's approach" capability, built the only way it can be built
responsibly. From the EPALLE visual-language lesson:

    What you take from a director is the *grammar*: how an artefact is framed to read as
    significant, how repetition accumulates rather than bores, how restraint creates
    weight. What you do not take is their shots, their scripts, their locations or their
    specific images. You compose original scenes in the grammar you learned.

So this module reads `vision.jsonl` (measurements, not pixels) and emits a **grammar**: the
recurring structural decisions behind a body of work — aspect discipline, palette
behaviour, where subjects sit, how much air is left, how tightly it is cropped, how fast it
cuts. A grammar is a set of constraints you can compose original work inside.

Three things it deliberately will not do, enforced in code rather than documented as advice:

  * It never copies caption text. Captions are read only for structural shape — length,
    hook position, question/CTA presence, emoji and hashtag density.
  * It never emits a subject, location or object lifted from a reference.
  * It refuses to produce a grammar from too few samples, because a "pattern" from four
    posts is noise wearing a suit.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as stats
from collections import Counter
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

MIN_SAMPLES = 12          # below this, refuse rather than invent a pattern
STRONG_SIGNAL = 0.55      # a convention must hold in >55% of samples to be called one


@dataclass
class Grammar:
    source: str
    samples: int
    # structural conventions
    aspect_discipline: dict[str, Any] = field(default_factory=dict)
    palette_behaviour: dict[str, Any] = field(default_factory=dict)
    composition: dict[str, Any] = field(default_factory=dict)
    density: dict[str, Any] = field(default_factory=dict)
    motion: dict[str, Any] = field(default_factory=dict)
    caption_shape: dict[str, Any] = field(default_factory=dict)
    # what to do with it
    conventions: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    confidence: str = "low"
    notes: list[str] = field(default_factory=list)


def _load(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        path = path / "vision.jsonl"
    if not path.exists():
        raise SystemExit(f"no vision.jsonl at {path} — run packages/vision/analyze.py first")
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _captions(ref_dir: Path) -> list[str]:
    """Captions are read for SHAPE only. The text itself never leaves this function."""
    p = ref_dir / "posts.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            c = json.loads(line).get("caption")
        except json.JSONDecodeError:
            continue
        if c:
            out.append(c)
    return out


def _caption_shape(caps: list[str]) -> dict[str, Any]:
    if not caps:
        return {}
    lens = [len(c) for c in caps]
    first_lines = [c.split("\n")[0] for c in caps]
    return {
        "median_chars": int(stats.median(lens)),
        "range_chars": [min(lens), max(lens)],
        "median_first_line_chars": int(stats.median([len(f) for f in first_lines])),
        "opens_with_question": round(sum(1 for f in first_lines if f.strip().endswith("?")) / len(caps), 2),
        "uses_line_breaks": round(sum(1 for c in caps if "\n" in c) / len(caps), 2),
        "median_hashtags": int(stats.median([len(re.findall(r"#\w+", c)) for c in caps])),
        "median_emoji": int(stats.median([len(re.findall(r"[\U0001F300-\U0001FAFF]", c)) for c in caps])),
        "note": "shape only — no caption text is retained or reused",
    }


def derive(records: list[dict[str, Any]], source: str,
           captions: list[str] | None = None) -> Grammar:
    vids = [r for r in records if r.get("kind") == "video"]
    g = Grammar(source=source, samples=len(records))

    if len(records) < MIN_SAMPLES:
        g.confidence = "insufficient"
        g.notes.append(
            f"only {len(records)} samples; {MIN_SAMPLES} is the floor for calling anything a "
            f"convention. What follows would be noise, so no grammar was derived.")
        return g

    def frac(pred, pool) -> float:
        return round(sum(1 for r in pool if pred(r)) / max(1, len(pool)), 2)

    # --- aspect ---------------------------------------------------------
    asp = Counter(r["aspect"] for r in records)
    top_asp, top_n = asp.most_common(1)[0]
    g.aspect_discipline = {"distribution": dict(asp.most_common()),
                           "dominant": top_asp, "share": round(top_n / len(records), 2)}
    if top_n / len(records) > STRONG_SIGNAL:
        g.conventions.append(f"commits to {top_asp} ({top_n/len(records):.0%} of posts) — "
                             f"format discipline, not opportunism")

    # --- palette --------------------------------------------------------
    lumas = [r["mean_luma"] for r in records]
    sats = [r["saturation"] for r in records]
    crushed = [r.get("crushed_blacks", 0) for r in records]
    warms = [r.get("warm_ratio", 0) for r in records]
    g.palette_behaviour = {
        "median_luma": round(stats.median(lumas), 1),
        "luma_spread": round(stats.pstdev(lumas), 1),
        "median_saturation": round(stats.median(sats), 1),
        "median_warm_ratio": round(stats.median(warms), 3),
        "median_crushed_blacks": round(stats.median(crushed), 3),
        "recurring_hues": [h for h, _ in Counter(
            c["hex"][:3] for r in records for c in r.get("palette", [])[:3]).most_common(5)],
    }
    if stats.median(lumas) < 70:
        g.conventions.append(f"works dark (median luma {stats.median(lumas):.0f}/255) — "
                             f"the mood is carried by exposure, not by colour")
    elif stats.median(lumas) > 170:
        g.conventions.append(f"works high-key (median luma {stats.median(lumas):.0f}/255)")
    if stats.median(sats) < 60:
        g.conventions.append(f"desaturated throughout (median sat {stats.median(sats):.0f}/255) — "
                             f"restraint is a stated choice")
    if stats.pstdev(lumas) < 25:
        g.conventions.append(f"exposure is held tight across the set (sd {stats.pstdev(lumas):.0f}) — "
                             f"the body of work reads as one piece")

    # --- composition ----------------------------------------------------
    quad = Counter(r["subject_quadrant"] for r in records if r.get("subject_quadrant"))
    bias = Counter(r.get("rule_of_thirds_bias") for r in records if r.get("rule_of_thirds_bias"))
    copyz = Counter(r.get("copy_zone") for r in records if r.get("copy_zone"))
    g.composition = {
        "subject_placement": dict(quad.most_common(4)),
        "thirds_bias": dict(bias.most_common()),
        "habitual_copy_zone": copyz.most_common(1)[0][0] if copyz else None,
        "median_symmetry": round(stats.median([r.get("symmetry", 0) for r in records]), 3),
        "share_with_quiet_zone": frac(lambda r: bool(r.get("copy_zone")), records),
    }
    if quad:
        top_q, qn = quad.most_common(1)[0]
        if qn / len(records) > STRONG_SIGNAL:
            g.conventions.append(f"habitually places the subject {top_q} ({qn/len(records):.0%})")
    if g.composition["share_with_quiet_zone"] > 0.7:
        g.conventions.append("almost always leaves a quiet zone — built for text overlay")
    if g.composition["median_symmetry"] > 0.9:
        g.conventions.append("strongly symmetrical framing")

    # --- density --------------------------------------------------------
    edges = [r["edge_density"] for r in records]
    g.density = {"median_edge_density": round(stats.median(edges), 4),
                 "spread": round(stats.pstdev(edges), 4)}
    if stats.median(edges) < 0.07:
        g.conventions.append(f"sparse frames (edge density {stats.median(edges):.3f}) — "
                             f"one idea per image, negative space allowed to sit")
    elif stats.median(edges) > 0.16:
        g.conventions.append(f"dense, information-rich frames (edge density {stats.median(edges):.3f})")

    # --- motion ---------------------------------------------------------
    if vids:
        durs = [v["duration_s"] for v in vids if v.get("duration_s")]
        shots = [v["avg_shot_s"] for v in vids if v.get("avg_shot_s")]
        g.motion = {
            "video_share": round(len(vids) / len(records), 2),
            "median_duration_s": round(stats.median(durs), 1) if durs else None,
            "median_shot_length_s": round(stats.median(shots), 2) if shots else None,
        }
        if shots and stats.median(shots) < 2.0:
            g.conventions.append(f"cuts fast (median shot {stats.median(shots):.1f}s) — "
                                 f"retention is engineered, not incidental")
        elif shots and stats.median(shots) > 4.0:
            g.conventions.append(f"holds shots long (median {stats.median(shots):.1f}s) — "
                                 f"composed stillness over motion")
        fpss = [v["fps"] for v in vids if v.get("fps")]
        if fpss:
            uniq = sorted(set(round(f, 2) for f in fpss))
            g.motion["frame_rates"] = uniq
            if len(uniq) == 1:
                g.conventions.append(f"single frame rate throughout ({uniq[0]}fps) — "
                                     f"frame-rate discipline is already in place")
            else:
                g.notes.append(f"MIXED frame rates {uniq}. Lesson 04-03 says lock ONE rate "
                               f"before generating; mixing them invalidates timing downstream.")
        g.notes.append("shot lengths are estimated from sampled frames; treat as pacing, "
                       "not an exact edit list")

    if captions:
        g.caption_shape = _caption_shape(captions)
        cs = g.caption_shape
        if cs.get("median_chars", 0) < 90:
            g.conventions.append(f"short captions (median {cs['median_chars']} chars) — "
                                 f"the image carries the message")
        if cs.get("opens_with_question", 0) > 0.4:
            g.conventions.append(f"opens with a question {cs['opens_with_question']:.0%} of the time")

    g.refusals = [
        "No subject, object, location or specific image from the reference is carried forward.",
        "No caption text is reused; only its structural shape was measured.",
        "This grammar is a set of constraints to compose original work inside — not a template to refill.",
    ]
    strong = len(g.conventions)
    g.confidence = "high" if len(records) >= 40 and strong >= 5 else \
                   "medium" if len(records) >= 20 and strong >= 3 else "low"
    if g.confidence == "low":
        g.notes.append("low confidence — either few samples or few conventions held above "
                       f"{STRONG_SIGNAL:.0%}. Treat these as hypotheses to test, not rules.")
    return g


def render(g: Grammar) -> str:
    L = [f"# Derived grammar — {g.source}", "",
         f"{g.samples} samples · confidence **{g.confidence}**", ""]
    if g.confidence == "insufficient":
        L += ["## Not derived", *[f"- {n}" for n in g.notes]]
        return "\n".join(L)
    conv = [f"- {c}" for c in g.conventions] or ["- none held strongly enough to name"]
    L += ["## Conventions observed", *conv, ""]
    L += ["## Measurements", "```json",
          json.dumps({"aspect": g.aspect_discipline, "palette": g.palette_behaviour,
                      "composition": g.composition, "density": g.density,
                      "motion": g.motion, "caption_shape": g.caption_shape},
                     indent=1)[:2400], "```", ""]
    L += ["## What this grammar does not contain", *[f"- {r}" for r in g.refusals], ""]
    if g.notes:
        L += ["## Caveats", *[f"- {n}" for n in g.notes]]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="Derive a compositional grammar from references.")
    ap.add_argument("--path", type=Path, required=True,
                    help="a reference dir containing vision.jsonl (and optionally posts.jsonl)")
    ap.add_argument("--name", help="label for the source; defaults to the directory name")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    recs = _load(a.path)
    ref_dir = a.path if a.path.is_dir() else a.path.parent
    g = derive(recs, a.name or ref_dir.name, _captions(ref_dir))
    md = render(g)
    print(md)

    out = a.out or ref_dir / "grammar.md"
    out.write_text(md, encoding="utf-8")
    (out.with_suffix(".json")).write_text(
        json.dumps(asdict(g), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
