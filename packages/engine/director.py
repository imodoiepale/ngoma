"""The director: a brief becomes stages, scenes, angles, picks, videos and an ending.

Deterministic. The same brief always gives the same workflow, so a session can be replayed
and a test can pin the result. An LLM may enrich scene descriptions later (session.py,
`--llm`), and that enrichment is cached in the session so replay still holds.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "strategy"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import workflow_author as wa  # noqa: E402
from presets import FORBIDDEN, cameras, compose_motion_prompt, compose_prompt, negatives, node_params, preset, scene_fragments  # noqa: E402
from profiles import aspect_note, beat, lock_fragments, profile  # noqa: E402
from brief import EngineBrief, RefCollection, Role, Scene, ShotSpec, check_brief  # noqa: E402

# How a still becomes motion, by what the scene asks for.
ROUTE_FOR = {"still": "image-to-video", "reference-clip": "motion-control", "talking": "lipsync",
             "character": "character-video", "long": "long-video"}
# What reaches the canvas as VFX. Anything not here is recorded as a gap by name.
VFX_NODE = {"upscale": "upscale-video", "relight": "relight"}
INPUT_KINDS = {"image": "reference-images", "video": "video-clip", "audio": "song"}


class DirectorError(ValueError):
    pass


class Builder:
    """Builds one studio workflow from parts. Ids are `<stage>.<kind>.<suffix>`, so a node
    says where it lives and what it is."""

    def __init__(self, brief: EngineBrief, cat: dict[str, Any] | None = None):
        self.brief = brief
        self.cat = cat or wa.load_catalog()
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.gaps: list[dict[str, str]] = []
        self.stages: list[dict[str, Any]] = []
        self.ids: set[str] = set()

    # ---- primitives ------------------------------------------------------
    def stage(self, sid: str, label: str, **extra: Any) -> str:
        if not any(s["id"] == sid for s in self.stages):
            self.stages.append({"id": sid, "label": label, "order": len(self.stages) + 1, **extra})
        return sid

    def node(self, stage: str, kind: str, suffix: str = "", params: dict[str, Any] | None = None,
             **data: Any) -> dict[str, Any]:
        spec = self.cat["by_kind"][kind]
        nid = ".".join(x for x in (stage, kind, suffix) if x)
        if nid in self.ids:
            raise DirectorError(f"node id {nid} already exists")
        p = {q["key"]: q["default"] for q in spec.get("params", []) if "default" in q}
        p.update({k: v for k, v in (params or {}).items() if any(q["key"] == k for q in spec.get("params", []))})
        n = {"id": nid, "kind": kind, "position": {"x": 0, "y": 0}, "data": {"params": p, "stage": stage, **data}}
        self.nodes.append(n)
        self.ids.add(nid)
        if spec["backend"]["kind"] == "gap":
            self.gaps.append({"node": nid, "step": kind, "reason": spec["backend"]["reason"]})
        return n

    def link(self, src: dict[str, Any], out: str, dst: dict[str, Any], port: str) -> None:
        typ = next(o["type"] for o in self.cat["by_kind"][src["kind"]]["outputs"] if o["id"] == out)
        self.edges.append({"id": f"e{len(self.edges) + 1}", "source": src["id"], "sourceHandle": out,
                           "target": dst["id"], "targetHandle": port, "type": typ})

    def gap(self, stage: str, step: str, reason: str) -> dict[str, Any]:
        nid = f"{stage}.unmapped.{step}"
        n = {"id": nid, "kind": "unmapped", "position": {"x": 0, "y": 0}, "data": {"step": step, "params": {}, "stage": stage}}
        self.nodes.append(n)
        self.ids.add(nid)
        self.gaps.append({"node": nid, "step": step, "reason": reason})
        return n

    def finish(self, title: str, source: dict[str, Any]) -> dict[str, Any]:
        wa.layout_lanes(self.nodes, self.edges, self.stages)
        wf = {"version": 2, "id": wa._slug(title), "title": title, "client": self.brief.client, "source": source,
              "created": "engine", "run_mode": self.brief.run_mode, "preset": self.brief.preset,
              "stages": self.stages, "nodes": self.nodes, "edges": self.edges, "gaps": self.gaps,
              "consent_required": any(self.cat["by_kind"].get(n["kind"], {}).get("consent") for n in self.nodes)}
        problems = wa.validate(wf, self.cat)
        if problems:
            raise DirectorError("; ".join(problems))
        return wf


# ---------------------------------------------------------------- storyboard

def storyboard(brief: EngineBrief) -> list[Scene]:
    p = preset(brief.preset)
    prof = profile(brief.profile)
    hints = brief.scene_hints or []
    lead = [r.name for r in brief.roles[:1]]
    scenes = []
    for i in range(brief.scenes):
        hint = hints[i] if i < len(hints) else (hints[-1] if hints else "")
        setting = hint or f"{beat(prof, i)} beat of: {brief.idea or brief.title}"
        framing, blocking = p["framing"][i % len(p["framing"])], p["blocking"][i % len(p["blocking"])]
        seconds = brief.video_seconds[i % len(brief.video_seconds)]
        scenes.append(Scene(n=i + 1, title=f"Scene {i + 1} ({beat(prof, i)})", setting=setting,
                            action=blocking, framing=framing, blocking=blocking, duration_s=seconds, roles=lead,
                            wardrobe=_first(brief, "wardrobe"), location=_first(brief, "location"),
                            jewellery=_first(brief, "jewellery")))
    return scenes


def _first(brief: EngineBrief, purpose: str) -> str:
    for r in brief.by_purpose(purpose):
        if r.may_feed():
            return r.name
    return ""


def expand_angles(scene: Scene, k: int, preset_name: str) -> list[ShotSpec]:
    p = preset(preset_name)
    frags = scene_fragments(p, scene.n - 1)
    return [ShotSpec(scene=scene.n, angle=i + 1, camera=c["id"], lens=p["lens"], fragments=[c["prompt"], *frags])
            for i, c in enumerate(cameras(k))]


# ---------------------------------------------------------------- the plan

def plan(brief: EngineBrief, cat: dict[str, Any] | None = None) -> dict[str, Any]:
    problems = check_brief(brief)
    # A pasted guide prompt ("in the style of <director>", "shot by <cinematographer>") is refused
    # here, before any node exists, for the same reason presets are: the look, never the name.
    for field_name, value in (("idea", brief.idea), ("title", brief.title), *((f"scene_hints[{i}]", h) for i, h in enumerate(brief.scene_hints or []))):
        m = FORBIDDEN.search(value or "")
        if m:
            problems.append(f"{field_name} names a person or a likeness ({m.group(0)!r}); describe the look instead")
    if problems:
        raise DirectorError("; ".join(problems))
    b = Builder(brief, cat)
    p = preset(brief.preset)
    prof = profile(brief.profile)
    locks = lock_fragments(prof, brief.theme) + [aspect_note(prof, brief.ratio)]
    neg = ", ".join([negatives(p)] + [f"no {n}" for n in prof["negatives"]])

    # 1. references: one input node per collection; a character per consented role
    refs = b.stage("refs", "References")
    ref_nodes: dict[str, dict[str, Any]] = {}
    for r in brief.refs:
        ref_nodes[r.name] = b.node(refs, INPUT_KINDS.get(r.kind, "reference-images"), r.name,
                                   params={"folder": r.path or f"brands/{brief.client}/references/{r.name}",
                                           "file": r.path}, ref=r.__dict__.copy())
    # the character sheet is the identity: H3 reads it as Picture 1 of its reference list
    characters: dict[str, dict[str, Any]] = {}
    for role in brief.roles:
        src = ref_nodes.get(role.ref_collection)
        if not src:
            continue
        rc = next((x for x in brief.refs if x.name == role.ref_collection), None)
        if role.consent or (role.fictional and rc and rc.may_feed()):
            sheet = b.node(refs, "character-sheet", role.name, role=role.name)
            b.link(src, "images", sheet, "image")
            characters[role.name] = sheet
        else:
            b.gap(refs, f"character-{role.name}", f"role {role.name}: no consent release and not a fictional persona "
                                                    "built from owned references, so no likeness step runs")

    # 2. storyboard as one brief per scene, then angles, a pick, dressing and motion per scene
    sb = b.stage("storyboard", "Storyboard")
    scenes = storyboard(brief)
    finals: list[dict[str, Any]] = []
    for sc in scenes:
        text = f"{sc.title}: {sc.setting}. {sc.action}"
        brief_node = b.node(sb, "brief", f"s{sc.n}", params={"text": text}, scene=sc.n)
        st = b.stage(f"scene{sc.n}", f"{sc.title} stills", scene=sc.n)
        lead = characters.get(sc.roles[0]) if sc.roles and prof["generator"] == "character" else None
        gen_nodes = []
        for shot in expand_angles(sc, brief.angles_per_scene, brief.preset):
            prompt = compose_prompt(text, shot.fragments[0], shot.fragments[1:], locks)
            data = dict(scene=sc.n, shot=shot.angle, camera=shot.camera, prompt=prompt, negative=neg,
                        variant_count=brief.seeds_per_angle, why=f"{shot.camera} angle of {sc.title} in the {p['label']} grammar")
            if lead:
                g = b.node(st, "h3-reference-image", f"a{shot.angle}", role=sc.roles[0], **data)
                b.link(lead, "sheet", g, "identity")
                b.link(brief_node, "text", g, "prompt")
            else:
                g = b.node(st, "krea2-t2i", f"a{shot.angle}", **data)
                b.link(brief_node, "text", g, "prompt")
            gen_nodes.append(g)
        keep = min(3, brief.angles_per_scene * brief.seeds_per_angle)
        pick = b.node(st, "pick", "keep", params={"k": keep}, scene=sc.n)
        for g in gen_nodes:
            b.link(g, "image", pick, "candidates")
        current, port = pick, "chosen"

        # dressing: only owned or licensed data references may feed a node
        dress = b.stage(f"scene{sc.n}-dress", f"{sc.title} dressing", scene=sc.n) if (sc.wardrobe or sc.location or sc.jewellery) else None
        if sc.wardrobe:
            w = b.node(dress, "wardrobe", "", scene=sc.n)
            b.link(current, port, w, "image"); b.link(ref_nodes[sc.wardrobe], "images", w, "clothes")
            current, port = w, "image"
        if sc.location:
            # Consistent Room carries the character as a trained LoRA, not an image
            lead_role = next((r for r in brief.roles if sc.roles and r.name == sc.roles[0]), None)
            if lead_role and lead_role.lora:
                room = b.node(dress, "consistent-room", "", scene=sc.n, role=lead_role.name,
                              params={"character_lora": lead_role.lora},
                              why=f"{lead_role.name} re-rendered from their LoRA inside {sc.location}")
                b.link(ref_nodes[sc.location], "images", room, "room"); b.link(brief_node, "text", room, "prompt")
                current, port = room, "image"
            else:
                b.gap(dress, f"room-{sc.location}", f"location {sc.location}: Consistent Room needs a trained character "
                                                   "LoRA for the lead; the setting stays in the prompt until one exists")
        if sc.jewellery:
            j = b.node(dress, "image-edit", "jewellery", scene=sc.n, params={"instruction": f"add the jewellery from {sc.jewellery}"})
            b.link(current, port, j, "image"); b.link(brief_node, "text", j, "prompt")
            current, port = j, "image"

        # motion
        mo = b.stage(f"scene{sc.n}-motion", f"{sc.title} motion", scene=sc.n)
        clip = next((ref_nodes[r.name] for r in brief.by_purpose("motion") if r.may_feed()), None)
        # the beat is built from the setting; the blocking is passed once, as its own part
        motion_prompt = compose_motion_prompt(f"{sc.title}: {sc.setting}", p, sc.duration_s, locks, neg,
                                              framing=sc.framing, blocking=sc.blocking)
        if clip:
            v = b.node(mo, "motion-control", "", scene=sc.n, prompt=motion_prompt,
                       why="a reference clip drives the motion; the prompt holds style, counts and excludes")
            b.link(current, port, v, "character"); b.link(clip, "video", v, "video")
        else:
            v = b.node(mo, "image-to-video", "", scene=sc.n, params=node_params(p, "image-to-video", sc.duration_s),
                       prompt=motion_prompt, why=f"still to {sc.duration_s}s video in the {p['label']} pacing")
            b.link(current, port, v, "image"); b.link(brief_node, "text", v, "prompt")
        vcur, vport = v, "video"
        for fx in brief.vfx:
            kind = VFX_NODE.get(fx)
            if kind is None:
                b.gap(mo, f"vfx-{fx}", f"no step in the studio does '{fx}' yet")
                continue
            fxn = b.node(mo, kind, fx, scene=sc.n)
            b.link(vcur, vport, fxn, "video")
            vcur, vport = fxn, "video"
        finals.append(vcur)

    # 3. edit and ending
    ed = b.stage("edit", "Edit")
    cut = b.node(ed, "cut", "", params=node_params(p, "cut"))
    for f in finals:
        b.link(f, "video", cut, "video")
    caps = b.node(ed, "captions", "")
    b.link(cut, "video", caps, "video")
    briefs = [n for n in b.nodes if n["kind"] == "brief"]
    if prof["narration"] != "none":
        vo = b.node(ed, "voiceover", "", why=prof["narration"], params={"language": brief.language or "en", "provider": "elevenlabs"})
        for bn in briefs:
            b.link(bn, "text", vo, "script")
        b.link(vo, "audio", caps, "audio")
    for bn in briefs:
        b.link(bn, "text", caps, "script")
    out = b.stage("publish", "Publish")
    for o in brief.outputs or ["export"]:
        if o == "export":
            ex = b.node(out, "export", "")
            b.link(caps, "video", ex, "media")
        elif o in ("postiz", "whatsapp-status"):
            pub = b.node(out, o, "")
            b.link(caps, "video", pub, "media")
    return b.finish(brief.title, {"engine": brief.to_dict()})


def branch_from_picks(wf: dict[str, Any], pick_id: str, cat: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record which candidates survive a pick. Downstream nodes already hang off the pick's
    `chosen` port; the runner feeds them only the picked results."""
    cat = cat or wa.load_catalog()
    node = next((n for n in wf["nodes"] if n["id"] == pick_id), None)
    if not node or cat["by_kind"].get(node["kind"], {}).get("category") != "decide":
        raise DirectorError(f"{pick_id} is not a decide step")
    picked = node["data"].get("picked") or []
    k = int(node["data"]["params"].get("k") or 0)
    if len(picked) > k:
        raise DirectorError(f"{pick_id}: keeps {len(picked)} but was told to keep {k}")
    return wf


__all__ = ["plan", "storyboard", "expand_angles", "branch_from_picks", "Builder", "DirectorError",
           "EngineBrief", "RefCollection", "Role", "ROUTE_FOR"]
