"""Small, named changes to an engine workflow. Each one rebuilds from the brief, so the graph
never drifts from what the session says was asked for; the brief is the source of truth and
the workflow is derived. Picks and results are carried across a rebuild by node id."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import director  # noqa: E402
from presets import PresetError, load_presets  # noqa: E402
from brief import ANGLE_CHOICES, EngineBrief, RefCollection, Role  # noqa: E402


class MutateError(ValueError):
    pass


def rebuild(brief: EngineBrief, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    wf = director.plan(brief)
    if previous:
        keep = {n["id"]: n["data"] for n in previous.get("nodes", [])}
        for n in wf["nodes"]:
            old = keep.get(n["id"])
            if old:
                for key in ("results", "picked"):
                    if old.get(key):
                        n["data"][key] = old[key]
        wf["id"] = previous.get("id", wf["id"])
        wf["title"] = previous.get("title", wf["title"])
    return wf


def add_scene(brief: EngineBrief, hint: str = "") -> str:
    brief.scenes += 1
    if hint:
        while len(brief.scene_hints) < brief.scenes - 1:
            brief.scene_hints.append(brief.scene_hints[-1] if brief.scene_hints else "")
        brief.scene_hints.append(hint)
    return f"Added scene {brief.scenes}" + (f": {hint}" if hint else "") + "."


def set_scenes(brief: EngineBrief, n: int) -> str:
    if not 1 <= n <= 40:
        raise MutateError("between 1 and 40 scenes")
    brief.scenes = n
    return f"Now {n} scenes."


def set_angles(brief: EngineBrief, k: int) -> str:
    if k not in ANGLE_CHOICES:
        raise MutateError(f"angles per scene must be one of {', '.join(map(str, ANGLE_CHOICES))}")
    brief.angles_per_scene = k
    return f"{k} angles per scene."


def set_seeds(brief: EngineBrief, n: int) -> str:
    if not 1 <= n <= 8:
        raise MutateError("1 to 8 takes per angle")
    brief.seeds_per_angle = n
    return f"{n} take(s) per angle."


def set_preset(brief: EngineBrief, name: str) -> str:
    presets = load_presets()["presets"]
    key = name.strip().lower().replace(" ", "-")
    if key not in presets:
        by_label = {p["label"].lower(): k for k, p in presets.items()}
        key = by_label.get(name.strip().lower(), key)
    if key not in presets:
        raise PresetError(f"no preset called {name!r}; try {', '.join(sorted(presets))}")
    brief.preset = key
    return f"Aesthetic: {presets[key]['label']}."


def set_video(brief: EngineBrief, seconds: list[int]) -> str:
    if not seconds or any(s < 3 or s > 30 for s in seconds):
        raise MutateError("clips are 3 to 30 seconds")
    brief.video_seconds = seconds
    return "Clips of " + ", ".join(f"{s}s" for s in seconds) + "."


def add_vfx(brief: EngineBrief, name: str) -> str:
    name = name.strip().lower()
    if name not in brief.vfx:
        brief.vfx.append(name)
    known = name in director.VFX_NODE
    return f"VFX: {name}." + ("" if known else f" No step does '{name}' yet; it is shown as a gap.")


def attach_ref(brief: EngineBrief, purpose: str, name: str, use: str = "data", rights: str = "owned",
               kind: str = "image", consent: bool = False) -> str:
    full = f"{purpose}-{name}" if not name.startswith(purpose) else name
    if any(r.name == full for r in brief.refs):
        return f"{full} is already attached."
    brief.refs.append(RefCollection(name=full, kind=kind, use=use, rights=rights, consent=consent))
    return f"Attached {full} as {use} ({rights})."


def add_role(brief: EngineBrief, name: str, ref_collection: str = "", consent: bool = False, fictional: bool = True) -> str:
    if any(r.name == name for r in brief.roles):
        return f"Role {name} already exists."
    brief.roles.append(Role(name=name, consent=consent, fictional=fictional, ref_collection=ref_collection))
    return f"Role {name} added" + (f" from {ref_collection}" if ref_collection else "") + "."


def set_profile(brief: EngineBrief, name: str) -> str:
    from profiles import load_profiles, profile
    docs = load_profiles()["profiles"]
    key = name.strip().lower().replace(" ", "-")
    by_label = {p["label"].lower(): k for k, p in docs.items()}
    key = by_label.get(name.strip().lower(), key)
    p = profile(key)
    brief.profile = key
    brief.preset = p["default_preset"]
    brief.scenes = int(p["default_scenes"])
    brief.video_seconds = list(p["seconds"])
    return f"Directing it as a {p['label'].lower()}: {len(p['beats'])} beats, {p['label']} pacing, look {p['default_preset']}."


def set_mode(brief: EngineBrief, mode: str) -> str:
    m = mode.strip().lower().replace(" ", "-")
    aliases = {"dry": "dry-run", "dryrun": "dry-run", "approval": "stage-approval", "stage": "stage-approval",
               "per-stage": "stage-approval", "automatic": "auto"}
    m = aliases.get(m, m)
    if m not in ("dry-run", "stage-approval", "auto"):
        raise MutateError("mode is dry-run, stage-approval or auto")
    brief.run_mode = m
    return {"dry-run": "Dry run: nothing spends.", "stage-approval": "Each stage waits for your approval.",
            "auto": "Auto: runs every stage, pauses at your picks and before publishing."}[m]


def pick(wf: dict[str, Any], node_id: str, indices: list[int]) -> str:
    node = next((n for n in wf["nodes"] if n["id"] == node_id), None)
    if not node or node["kind"] not in ("pick", "pick-video"):
        raise MutateError(f"{node_id} is not a pick step")
    feeders = [e["source"] for e in wf["edges"] if e["target"] == node_id]
    candidates = []
    for f in feeders:
        src = next(n for n in wf["nodes"] if n["id"] == f)
        results = [r for r in (src["data"].get("results") or []) if r.get("status") == "completed"]
        for r in results:
            for i, _f in enumerate(r.get("files", [])):
                candidates.append(f"{f}#{r['run_id']}#{i}")
    if not candidates:
        candidates = [f"{f}#pending#{i}" for f in feeders for i in range(int(next(n for n in wf["nodes"] if n["id"] == f)["data"].get("variant_count") or 1))]
    chosen = []
    for i in indices:
        if not 1 <= i <= len(candidates):
            raise MutateError(f"candidate {i} does not exist; there are {len(candidates)}")
        chosen.append(candidates[i - 1])
    k = int(node["data"]["params"].get("k") or len(chosen))
    if len(chosen) > k:
        raise MutateError(f"{node_id} keeps at most {k}")
    node["data"]["picked"] = chosen
    return f"Kept {len(chosen)} at {node_id}."
