"""A conversation with the director. Each utterance is an intent; each intent changes the
brief; the workflow is rebuilt from the brief. Replaying the utterances rebuilds the same
workflow, so a session file is the whole history.

Session file: brands/<client>/workflows/<workflow-id>.session.json
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import mutate  # noqa: E402
import workflow_author as wa  # noqa: E402
import profiles  # noqa: E402
from presets import load_presets  # noqa: E402
from brief import EngineBrief  # noqa: E402

NUM = r"(\d+)"
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "twenty": 20}


@dataclass
class Intent:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    id: str
    client: str
    workflow_id: str
    brief: dict[str, Any]
    utterances: list[str] = field(default_factory=list)
    version: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)   # briefs before each change, for undo
    pending_picks: list[str] = field(default_factory=list)


def _n(text: str) -> int | None:
    m = re.search(NUM, text)
    if m:
        return int(m.group(1))
    for w, v in WORDS.items():
        if re.search(rf"\b{w}\b", text):
            return v
    return None


def intent(text: str) -> Intent:
    """Keyword rules, in the style of workflow_author.BRIEF_RULES. Unknown text is `note`."""
    t = text.strip()
    low = t.lower()
    presets = load_presets()["presets"]
    if re.search(r"\bundo\b", low):
        return Intent("undo")
    if m := re.search(r"\b(?:pick|keep|choose)\b.*?\b(?:at|on|for)\s+([a-z0-9.\-]+)\s*[:\s]\s*([\d,\s]+)$", low):
        return Intent("pick", {"node": m.group(1), "indices": [int(x) for x in re.findall(r"\d+", m.group(2))]})
    if re.search(r"\b(mode|switch to)\b.*\b(dry|approval|stage|auto)", low):
        word = re.search(r"\b(dry[- ]?run|dry|stage[- ]approval|approval|stage|auto(?:matic)?)\b", low).group(1)
        return Intent("mode", {"mode": word})
    if re.search(r"\brun\b", low) and re.search(r"\b(stage|next|all|everything|it)\b", low):
        m = re.search(r"\brun\s+(?:the\s+)?([a-z0-9\-]+)", low)
        target = m.group(1) if m else "next"
        return Intent("run", {"stage": "all" if target in ("all", "everything") else ("next" if target in ("next", "it", "stage", "the") else target)})
    if re.search(r"\b(add|another|new)\b.*\bscene\b", low) or re.search(r"\bscene\b.*\b(at|in|on|of)\b", low) and not re.search(r"\bangles?\b", low):
        hint = re.sub(r"^.*?\bscene\b\s*(?:\d+)?\s*(?:at|in|on|of|:)?\s*", "", t, flags=re.I).strip(" .")
        return Intent("add_scene", {"hint": hint})
    if m := re.search(r"\b(\d+|" + "|".join(WORDS) + r")\s+scenes\b", low):
        return Intent("set_scenes", {"n": _n(m.group(0))})
    if re.search(r"\bangles?\b|\bcameras?\b", low) and _n(low):
        return Intent("set_angles", {"k": _n(low)})
    if re.search(r"\b(takes?|seeds?|variants?)\b", low) and _n(low):
        return Intent("set_seeds", {"n": _n(low)})
    if re.search(r"\b(second|seconds|sec|s)\b", low) and re.search(r"\b(video|clip|clips|long)\b", low):
        return Intent("video", {"seconds": [int(x) for x in re.findall(r"(\d+)\s*(?:seconds|second|sec|s)\b", low)] or [_n(low)]})
    if m := re.search(r"\b(?:aesthetic|preset|style|look|like)\b\s*(?:of|:)?\s*([a-z][a-z \-]+)$", low):
        name = m.group(1).strip()
        key = name.replace(" ", "-")
        by_label = {p["label"].lower(): k for k, p in presets.items()}
        if key in presets or name in by_label:
            return Intent("preset", {"name": name})
    for key, p in presets.items():
        if key in low or p["label"].lower() in low:
            return Intent("preset", {"name": key})
    if prof := profiles.find(low):
        return Intent("profile", {"name": prof})
    if m := re.search(r"\b(wardrobe|clothes|outfit|location|room|set|jewell?ery|props?|motion clip|reference video)\b\s*(?:from|:|called|named)?\s*(?:my|the|our|own|owned|licensed)?\s*([a-z0-9][a-z0-9\-_ ]*)$", low):
        purpose = {"clothes": "wardrobe", "outfit": "wardrobe", "room": "location", "set": "location", "jewelry": "jewellery",
                   "prop": "jewellery", "props": "jewellery", "motion clip": "motion", "reference video": "motion"}.get(m.group(1), m.group(1))
        rights = "owned" if re.search(r"\b(my|mine|own|owned)\b", low) else ("licensed" if "licensed" in low else "unclear")
        use = "inspiration" if re.search(r"\b(inspiration|inspo|mood)\b", low) else "data"
        return Intent("attach_ref", {"purpose": purpose, "name": m.group(2).strip().replace(" ", "-"), "rights": rights, "use": use,
                                     "kind": "video" if purpose == "motion" else "image"})
    if m := re.search(r"\b(?:vfx|effect)\b\s*(?:called|:)?\s*([a-z][a-z\-]*)", low):
        return Intent("vfx", {"name": m.group(1)})
    if m := re.search(r"\b(?:add|new)\s+(?:a\s+)?role\s+([a-z][a-z0-9\-]*)(?:\s+from\s+([a-z0-9\-]+))?", low):
        return Intent("role", {"name": m.group(1), "ref_collection": m.group(2) or "", "consent": "consent" in low or "released" in low})
    return Intent("note", {"text": t})


def _path(client: str, workflow_id: str) -> Path:
    return wa.workflow_dir(client) / f"{workflow_id}.session.json"


def load(client: str, workflow_id: str) -> Session:
    p = _path(client, workflow_id)
    d = json.loads(p.read_text(encoding="utf-8"))
    return Session(**d)


def save(s: Session) -> Path:
    p = _path(s.client, s.workflow_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(s), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def start(client: str, session_id: str, title: str, first: str = "") -> Session:
    brief = EngineBrief(client=client, title=title, idea=first)
    wf = mutate.rebuild(brief)
    s = Session(id=session_id, client=client, workflow_id=wf["id"], brief=brief.to_dict())
    wa.save(wf)
    save(s)
    return s


def apply(s: Session, it: Intent, wf: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
    brief = EngineBrief.from_dict(s.brief)
    wf = wf or _read(s)
    if it.name == "undo":
        if not s.history:
            return wf, "Nothing to undo."
        s.brief = s.history.pop()
        wf = mutate.rebuild(EngineBrief.from_dict(s.brief), wf)
        s.version += 1
        return wf, "Undone."
    if it.name == "pick":
        reply = mutate.pick(wf, it.args["node"], it.args["indices"])
        s.version += 1
        return wf, reply
    if it.name == "run":
        return wf, f"Run requested for stage {it.args['stage']}. Use the Run button or `cli.py run`; the run mode decides what happens."
    if it.name == "note":
        brief.idea = (brief.idea + " " + it.args["text"]).strip() if brief.idea else it.args["text"]
        reply = "Noted in the brief."
    else:
        fn = {"add_scene": lambda: mutate.add_scene(brief, it.args.get("hint", "")),
              "set_scenes": lambda: mutate.set_scenes(brief, it.args["n"]),
              "set_angles": lambda: mutate.set_angles(brief, it.args["k"]),
              "set_seeds": lambda: mutate.set_seeds(brief, it.args["n"]),
              "video": lambda: mutate.set_video(brief, it.args["seconds"]),
              "preset": lambda: mutate.set_preset(brief, it.args["name"]),
              "profile": lambda: mutate.set_profile(brief, it.args["name"]),
              "vfx": lambda: mutate.add_vfx(brief, it.args["name"]),
              "attach_ref": lambda: mutate.attach_ref(brief, it.args["purpose"], it.args["name"], it.args.get("use", "data"),
                                                      it.args.get("rights", "unclear"), it.args.get("kind", "image")),
              "role": lambda: mutate.add_role(brief, it.args["name"], it.args.get("ref_collection", ""), it.args.get("consent", False)),
              "mode": lambda: mutate.set_mode(brief, it.args["mode"])}[it.name]
        reply = fn()
    s.history.append(s.brief)
    s.brief = brief.to_dict()
    wf = mutate.rebuild(brief, wf)
    s.version += 1
    return wf, reply


def _read(s: Session) -> dict[str, Any]:
    p = wa.workflow_dir(s.client) / f"{s.workflow_id}.studio.json"
    return json.loads(p.read_text(encoding="utf-8"))


def say(client: str, session_id: str, text: str, workflow_id: str | None = None) -> dict[str, Any]:
    """The one entry point the chat, the voice agent and the CLI all use."""
    existing = None
    if workflow_id and _path(client, workflow_id).exists():
        existing = load(client, workflow_id)
    else:
        for p in wa.workflow_dir(client).glob("*.session.json"):
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("id") == session_id:
                existing = Session(**d)
                break
    if existing is None:
        s = start(client, session_id, title=text[:60] or "Untitled", first=text)
        # "a stickman explainer about gravity, neon noir" starts as that kind of piece in that look
        if prof := profiles.find(text):
            wf, _ = apply(s, Intent("profile", {"name": prof}))
            wa.save(wf)
        low = text.lower()
        for key, p in load_presets()["presets"].items():
            if key in low or p["label"].lower() in low:
                wf, _ = apply(s, Intent("preset", {"name": key}))
                wa.save(wf)
                break
        wf = _read(s)
        reply = f"Started \"{s.workflow_id}\" with {len(wf['stages'])} stages. Tell me scenes, angles, wardrobe, an aesthetic, or say run."
    else:
        s = existing
        it = intent(text)
        wf, reply = apply(s, it)
        wa.save(wf)
    s.utterances.append(text)
    s.pending_picks = [n["id"] for n in wf["nodes"] if n["kind"] in ("pick", "pick-video") and not n["data"].get("picked")]
    save(s)
    return {"session": asdict(s), "workflow": wf, "reply": reply, "pending_picks": s.pending_picks}


def replay(client: str, session_id: str, utterances: list[str]) -> dict[str, Any]:
    """Rebuild a workflow from its history alone. Used by tests to prove determinism."""
    out = None
    for u in utterances:
        out = say(client, session_id, u)
    return out or {}
