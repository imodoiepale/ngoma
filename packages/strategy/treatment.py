"""Song -> treatment -> shot list, with a generation route per shot.

Implements the process in lesson 04-02, which is explicit that the ASALI pilot is the
example and the *process* is the transferable part. So this takes any audio master, reads
its real duration and energy, maps the brand's narrative arc onto the timeline, and emits a
shot list where every row already knows which pipeline produces it.

Two things are locked before anything is generated, because lesson 04-03 says changing
either one invalidates every timing decision downstream:

    the audio master (final mix, final length) and the frame rate.

Shots are deliberately NOT distributed evenly. Hero moments get length and stillness;
connective moments get cut short. Even distribution is what makes a music video feel like a
slideshow.

    uv run --with pyyaml packages/strategy/treatment.py --brand epalle \\
        --audio "~/Downloads/Ancestral Pulse.wav" --title "Ancestral Pulse"
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]

# Which pipeline makes which kind of shot. Straight from lesson 04-02's generation routes,
# resolved to the actual profiles in packages/image-router/router.py.
ROUTES = {
    "still_push":   dict(profile="klein_t2i", then="i2v_infinite",
                         why="static or near-static hero image, then a slow synthetic push"),
    "performance":  dict(profile="h3_music_video", then=None,
                         why="performance or lip-sync -> reference-conditioned video with audio",
                         workflow="workflows/h3/NEW_-_Music_Video.json"),
    "motion_xfer":  dict(profile="scail_motion", then=None,
                         why="motion inherited from a real performance"),
    "replacement":  dict(profile="scail_motion", then=None,
                         why="existing footage, different subject"),
    "segmented":    dict(profile="i2v_infinite", then=None,
                         why="anything longer than a single pass -> segmented with motion context"),
    "texture":      dict(profile="klein_t2i", then=None,
                         why="texture plate; a still is enough"),
}

# Hero shots are held; connective shots are cut short. Ratio, not an absolute.
HERO_WEIGHT = 2.6
MIN_SHOT_S = 1.6
MAX_SHOT_S = 9.0
# A longer song needs MORE shots, not longer ones. Shot count per stage is derived from
# the stage's length against this target, so the clamp above is a guard rail rather than
# the thing that decides the edit. Fixing shots-per-stage instead silently truncated a
# 177s master to 131s of shots.
TARGET_CONNECTIVE_S = 3.2


@dataclass
class Shot:
    n: int
    stage: str
    style_key: str
    kind: str                 # hero | connective
    start_s: float
    duration_s: float
    framing: str
    subject_action: str
    palette_note: str
    motion: str
    route: str
    route_why: str
    workflow_or_profile: str
    notes: list[str] = field(default_factory=list)


@dataclass
class Treatment:
    brand: str
    title: str
    audio: str
    duration_s: float
    fps: int
    arc: str
    premise: str
    what_this_is_not: list[str]
    shots: list[Shot]
    locked: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def audio_duration(p: Path) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(p)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return round(float(r.stdout.strip()), 2)
    except Exception:  # noqa: BLE001 - ffprobe optional; caller handles None
        return None


def audio_energy(p: Path, bands: int) -> list[float] | None:
    """Per-section loudness, used to decide which stage ranges carry hero shots.

    Uses ffmpeg's volumedetect over slices. Crude next to real onset detection, but it
    needs no extra dependency and it only has to rank sections against each other.
    """
    dur = audio_duration(p)
    if not dur:
        return None
    out = []
    step = dur / bands
    for i in range(bands):
        try:
            r = subprocess.run(
                ["ffmpeg", "-v", "error", "-ss", f"{i*step:.2f}", "-t", f"{step:.2f}",
                 "-i", str(p), "-af", "volumedetect", "-f", "null", "-"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            mean = next((float(l.split(":")[1].replace("dB", "").strip())
                         for l in (r.stderr or "").splitlines() if "mean_volume" in l), -60.0)
            out.append(mean)
        except Exception:  # noqa: BLE001
            out.append(-60.0)
    return out


def build(brand_spec: dict[str, Any], styles: dict[str, dict[str, Any]], title: str,
          audio: Path | None, duration_s: float, fps: int,
          shots_per_stage: int | None = None) -> Treatment:
    arc = brand_spec.get("arc") or {}
    stages = arc.get("stages") or []
    warnings: list[str] = []
    if not stages:
        raise SystemExit(f"brand {brand_spec['brand']} declares no narrative arc to map")

    # Map stage -> its style grammar by the order encoded in styles/index.yaml
    stage_styles: dict[str, str] = {}
    for key, s in styles.items():
        if s.get("stage"):
            stage_styles[s["stage"]] = key
    missing = [s["key"] for s in stages if s["key"] not in stage_styles]
    if missing:
        warnings.append(f"no style grammar for stage(s): {', '.join(missing)}")

    energy = audio_energy(audio, len(stages)) if audio and audio.exists() else None
    if energy is None and audio:
        warnings.append("could not read audio energy (is ffmpeg on PATH?); stage lengths are "
                        "distributed evenly, which is a worse default — check them by ear")

    # Stage length: even split, then nudged by relative loudness so louder sections get more
    # screen time. Never distribute shots evenly *within* a stage.
    n = len(stages)
    base = duration_s / n
    if energy:
        lo, hi = min(energy), max(energy)
        span = max(1e-6, hi - lo)
        weights = [0.75 + 0.5 * ((e - lo) / span) for e in energy]
        total_w = sum(weights)
        lengths = [duration_s * w / total_w for w in weights]
    else:
        lengths = [base] * n

    shots: list[Shot] = []
    t = 0.0
    num = 1
    for i, st in enumerate(stages):
        span = lengths[i]
        skey = stage_styles.get(st["key"], "")
        style = styles.get(skey, {})
        # one hero + (shots_per_stage - 1) connective, hero weighted longer
        # How many shots does THIS stage need so that durations land inside the clamp?
        # Solve span = hero + c*connective with hero = HERO_WEIGHT * connective.
        if shots_per_stage:
            n_conn = max(1, shots_per_stage - 1)
        else:
            n_conn = max(1, round((span / TARGET_CONNECTIVE_S) - HERO_WEIGHT))
        # grow the shot count until the hero fits under the clamp
        while span * HERO_WEIGHT / (HERO_WEIGHT + n_conn) > MAX_SHOT_S:
            n_conn += 1
        kinds = ["hero"] + ["connective"] * n_conn
        w = [HERO_WEIGHT if k == "hero" else 1.0 for k in kinds]
        tw = sum(w)
        for k, wi in zip(kinds, w):
            d = max(MIN_SHOT_S, min(MAX_SHOT_S, span * wi / tw))
            route = ("performance" if k == "hero" and st["key"] in ("prayer", "gratitude")
                     else "still_push" if k == "hero"
                     else "texture" if st["key"] in ("labour", "doubt")
                     else "segmented")
            r = ROUTES[route]
            shots.append(Shot(
                n=num, stage=st["key"], style_key=skey, kind=k,
                start_s=round(t, 2), duration_s=round(d, 2),
                framing=style.get("composition", st.get("visual_state", "")),
                subject_action=style.get("subject", st.get("visual_state", "")),
                palette_note=st.get("palette_weight", ""),
                motion=st.get("motion", ""),
                route=route, route_why=r["why"],
                workflow_or_profile=r.get("workflow") or r["profile"],
                notes=(["flower state: " + st["flower"]] if st.get("flower") else []),
            ))
            t += d
            num += 1

    drift = round(t - duration_s, 2)
    if abs(drift) > 1.0:
        warnings.append(f"shot durations total {t:.1f}s against a {duration_s:.1f}s master "
                        f"({drift:+.1f}s). Clamping at {MIN_SHOT_S}-{MAX_SHOT_S}s per shot did "
                        f"this — adjust shots_per_stage or trim by hand before generating.")

    return Treatment(
        brand=brand_spec["brand"], title=title,
        audio=str(audio) if audio else "(none supplied)",
        duration_s=duration_s, fps=fps, arc=arc.get("name", "arc"),
        premise=brand_spec.get("positioning", {}).get("premise", ""),
        what_this_is_not=list(brand_spec.get("forbidden_looks", [])),
        shots=shots,
        locked={"audio_master": str(audio) if audio else None, "fps": fps,
                "duration_s": duration_s,
                "rule": "changing either locked value invalidates every timing decision below"},
        warnings=warnings,
    )


def render(t: Treatment) -> str:
    L = [f"# {t.title} — treatment", "",
         f"**Brand** {t.brand} · **Arc** {t.arc} · **Master** {t.duration_s:.1f}s @ {t.fps}fps",
         "", "## Locked before generation",
         f"- audio master: `{t.locked['audio_master']}`",
         f"- frame rate: {t.fps}",
         f"- {t.locked['rule']}", ""]
    if t.premise:
        L += ["## Premise", t.premise, ""]
    L += ["## What this is not", *[f"- {x}" for x in t.what_this_is_not], "",
          "## Shot list", "",
          "| # | stage | kind | in | dur | route | produced by |",
          "|---|---|---|---|---|---|---|"]
    for s in t.shots:
        L.append(f"| {s.n} | {s.stage} | {s.kind} | {s.start_s:.1f}s | {s.duration_s:.1f}s "
                 f"| {s.route} | `{Path(s.workflow_or_profile).name}` |")
    L += ["", "## Shot detail", ""]
    for s in t.shots:
        L += [f"### {s.n}. {s.stage} — {s.kind} ({s.duration_s:.1f}s from {s.start_s:.1f}s)",
              f"- **subject** {s.subject_action}",
              f"- **framing** {s.framing}",
              f"- **palette** {s.palette_note}",
              f"- **motion** {s.motion}",
              f"- **route** {s.route} — {s.route_why}",
              f"- **style grammar** `{s.style_key}`",
              *[f"- {n}" for n in s.notes], ""]
    if t.warnings:
        L += ["## Warnings", *[f"- {w}" for w in t.warnings]]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="Turn a song into a treatment and shot list.")
    ap.add_argument("--brand", default="epalle")
    ap.add_argument("--audio", type=Path)
    ap.add_argument("--title")
    ap.add_argument("--duration", type=float, help="override, when no audio file is to hand")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--shots-per-stage", type=int, default=None,
                    help="override; by default derived from each stage's length")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    sys.path.insert(0, str(REPO / "packages" / "brandkit"))
    from brandkit import load_brand  # noqa: E402,PLC0415
    b = load_brand(a.brand)

    audio = Path(str(a.audio).replace("~", str(Path.home()))) if a.audio else None
    dur = a.duration or (audio_duration(audio) if audio and audio.exists() else None)
    if not dur:
        raise SystemExit("need --duration, or an --audio file ffprobe can read "
                         "(queued is not success; a guessed length is not a master)")

    title = a.title or (audio.stem if audio else "untitled")
    t = build(b.spec, b.styles, title, audio if audio and audio.exists() else None,
              dur, a.fps, a.shots_per_stage)
    md = render(t)
    print(md)

    out = a.out or REPO / "brands" / a.brand / "calendar" / f"treatment-{title.lower().replace(' ', '-')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    out.with_suffix(".json").write_text(
        json.dumps(asdict(t), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
