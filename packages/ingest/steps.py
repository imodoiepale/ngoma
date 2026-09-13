"""Turn a mined video into a timestamped step outline, without copying the transcript.

A step here is `[timestamp] action — the tools, models, packs and settings named at that
moment`. The action is a canonical verb (install, load, connect, set, run, ...) detected in
the cue; the tools come from the facts `yt_learn.mine()` already extracted. No sentence
from the video is reproduced: the outline points you to the right minute, and the video
remains the source.

    uv run --with pyyaml packages/ingest/steps.py            # every mined video
    uv run --with pyyaml packages/ingest/steps.py --video ID
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import REPO  # noqa: E402
from yt_learn import CORPUS, vtt_to_cues  # noqa: E402

# spoken verb -> canonical action (first match in a cue wins)
ACTIONS: list[tuple[str, str]] = [
    (r"\b(git clone|clone)\b", "clone"), (r"\binstall(ing|ed)?\b", "install"),
    (r"\bdownload(ing|ed)?\b", "download"), (r"\bupload(ing|ed)?\b", "upload"),
    (r"\b(load|loader)\b", "load"), (r"\bconnect(ing|ed)?\b", "connect"),
    (r"\b(set|change|adjust|increase|decrease|lower|raise)\b", "set"),
    (r"\b(add|place|double[- ]click|search for)\b", "add"), (r"\b(select|choose|pick)\b", "select"),
    (r"\b(run|queue|generate|render)\b", "run"), (r"\b(train|training)\b", "train"),
    (r"\b(upscale|upscaling)\b", "upscale"), (r"\b(save|export)\b", "save"),
    (r"\b(compare|comparison)\b", "compare"), (r"\b(prompt|caption)\b", "prompt"),
]
_ACTIONS = [(re.compile(p, re.I), a) for p, a in ACTIONS]
MAX_STEPS = 40


def _facts_by_time(rec: dict[str, Any]) -> dict[str, list[str]]:
    by_t: dict[str, list[str]] = {}
    for kind, items in rec.get("facts", {}).items():
        for it in items:
            by_t.setdefault(it["t"], []).append(it["value"])
    return by_t


def outline(rec: dict[str, Any], cues: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Steps where an action verb and at least one named fact meet within ~20 seconds."""
    by_t = _facts_by_time(rec)
    fact_times = sorted(by_t)

    def secs(ts: str) -> int:
        return sum(int(x) * m for x, m in zip(reversed(ts.split(":")), (1, 60, 3600)))

    steps, last_key = [], None
    for ts, text in cues:
        action = next((a for pat, a in _ACTIONS if pat.search(text)), None)
        if not action:
            continue
        near = [v for t in fact_times if abs(secs(t) - secs(ts)) <= 20 for v in by_t[t]]
        if not near:
            continue
        things = sorted(set(near))[:4]
        key = (action, tuple(things))
        if key == last_key:
            continue
        last_key = key
        steps.append({"t": ts, "seconds": secs(ts), "action": action, "things": things})
        if len(steps) >= MAX_STEPS:
            break
    return steps


def render(rec: dict[str, Any], steps: list[dict[str, Any]]) -> str:
    url = rec.get("url") or f"https://www.youtube.com/watch?v={rec['video_id']}"
    lines = [f"# {rec.get('title') or rec['video_id']}", "",
             f"Source: {url} · channel `{rec.get('channel')}` · generated outline, not a transcript.", ""]
    if not steps:
        lines += ["No actionable steps detected. Watch the video; the facts file lists what it mentions.", ""]
    for n, s in enumerate(steps, 1):
        lines.append(f"{n}. [{s['t']}]({url}&t={s['seconds']}) **{s['action']}** — {', '.join(s['things'])}")
    return "\n".join(lines) + "\n"


def run(video: str | None = None) -> int:
    idx = CORPUS / "facts.jsonl"
    if not idx.exists():
        print("facts.jsonl missing — run yt_learn first")
        return 2
    written = 0
    for line in idx.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if video and rec["video_id"] != video:
            continue
        sub = rec.get("subtitle_file")
        vtt = REPO / sub if sub else None
        if not vtt or not vtt.exists():
            cand = sorted((CORPUS / str(rec.get("channel"))).glob(f"subs/{rec['video_id']}*.vtt"))
            vtt = cand[0] if cand else None
        if not vtt:
            continue
        steps = outline(rec, vtt_to_cues(vtt))
        dest = CORPUS / str(rec.get("channel")) / "steps" / f"{rec['video_id']}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(rec, steps), encoding="utf-8")
        written += 1
    print(f"wrote {written} step outline(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Timestamped step outlines from mined videos.")
    ap.add_argument("--video", help="only this video id")
    return run(ap.parse_args().video)


if __name__ == "__main__":
    raise SystemExit(main())
