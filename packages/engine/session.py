"""A conversation with the director. Each utterance is an intent; each intent changes the
brief; the workflow is rebuilt from the brief. Replaying the utterances rebuilds the same
workflow, so a session file is the whole history.

Session file: brands/<client>/workflows/<workflow-id>.session.json

`describe` is the one entry point for the describe bar: a sentence becomes a workflow
(author route: named steps, wired) or a directed piece (director route: a profile or a
preset was named), and a second sentence on the same session extends it. The intent
rules live in `intents.py`; the brief rules in `workflow_author.parse_brief`.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "packages" / "strategy"))
import intents  # noqa: E402
import mutate  # noqa: E402
import workflow_author as wa  # noqa: E402
import profiles  # noqa: E402
from intents import NUM, WORDS, Intent, _n, intent  # noqa: E402,F401  (re-exported; tests and callers use session.intent)
from presets import load_presets  # noqa: E402
from brief import EngineBrief  # noqa: E402

ROUTES = ("director", "author")
MODES = ("plan", "create", "direct")


class DescribeError(ValueError):
    """A brief the studio refuses, or a request it cannot act on. The message is for the user."""


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
    route: str = "director"          # director: brief -> plan; author: steps wired by the author


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
    if existing is not None and existing.route == "author":
        # an authored workflow grows by extension, not by rebuilding a director brief
        out = describe(client, text, session_id=session_id, workflow_id=existing.workflow_id)
        return {"session": out["session"], "workflow": out["workflow"], "reply": out["reply"], "pending_picks": []}
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


# ---------------------------------------------------------------- describe: a sentence becomes a plan

def _find_session(client: str, session_id: str | None, workflow_id: str | None) -> Session | None:
    if workflow_id and _path(client, workflow_id).exists():
        return load(client, workflow_id)
    if session_id:
        for p in wa.workflow_dir(client).glob("*.session.json"):
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("id") == session_id:
                return Session(**d)
    return None


def _read_workflow(client: str, workflow_id: str) -> dict[str, Any] | None:
    p = wa.workflow_dir(client) / f"{workflow_id}.studio.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _local_steps() -> set[str]:
    try:
        import runner  # the engine's list of python steps it runs itself
        return set(runner.LOCAL_STEPS)
    except Exception:  # pragma: no cover - the runner is not needed to plan
        return {"voiceover", "cut", "captions", "export"}


def _has_port_map(spec: dict[str, Any]) -> bool:
    try:
        import ports
        return ports.port_map_path(spec["backend"]["workflow"]).exists()
    except Exception:
        return False


def _status(node: dict[str, Any], spec: dict[str, Any] | None, gap_nodes: set[str], local: set[str]) -> str:
    """ready | needs-setup | gap | input | decide, the three honest badges plus the two
    kinds of node a person fills or answers."""
    if node["kind"] == "unmapped" or node["id"] in gap_nodes or not spec:
        return "gap"
    be = spec["backend"]["kind"]
    if be == "gap":
        return "gap"
    if be == "input":
        return "input"
    if be == "human":
        return "decide"
    if be == "comfy":
        return "ready" if _has_port_map(spec) else "needs-setup"
    if be == "python":
        return "ready" if node["kind"] in local else "needs-setup"
    return "ready"


def _item_counts(wf: dict[str, Any], cat: dict[str, Any], client: str) -> tuple[dict[str, int], dict[str, int], bool]:
    """Items each node runs over and outputs it produces, walking the graph in order.
    A reference folder's size is read from disk when the folder is named, from the
    brief's expected count when not, else assumed to be one item (and said so)."""
    by_id = {n["id"]: n for n in wf["nodes"]}
    depths = wa._depths(wf["nodes"], wf["edges"])
    order = sorted(wf["nodes"], key=lambda n: depths[n["id"]])
    items: dict[str, int] = {}
    produced: dict[str, int] = {}
    sources: dict[str, str] = {}   # input node -> disk | brief | assumed
    for n in order:
        d = n.get("data") or {}
        spec = cat["by_kind"].get(n["kind"])
        incoming = {e["targetHandle"]: e["source"] for e in wf["edges"] if e["target"] == n["id"] and e["source"] in by_id}
        if spec and spec.get("category") == "inputs":
            count = 0
            folder = (d.get("params") or {}).get("folder") or d.get("collection")
            if n["kind"] == "reference-images" and folder:
                count = wa.collection_count(client, str(folder).rstrip("/").split("/")[-1])
                if count:
                    sources[n["id"]] = "disk"
            if not count and d.get("expected_count"):
                count = int(d["expected_count"])
                sources[n["id"]] = "brief"
            if not count:
                count = int(d.get("count") or 0) or (1 if n["kind"] != "reference-images" else 0)
                if count:
                    sources[n["id"]] = "disk"
            if not count:
                count = 1
                sources[n["id"]] = "assumed"
            items[n["id"]], produced[n["id"]] = count, count
            continue
        if wa.is_each(n):
            port = wa.iterated_port(n, cat)
            src = incoming.get(port or "")
            items[n["id"]] = produced.get(src, 1) if src else 1
        else:
            items[n["id"]] = 1
        per_run = int((d.get("params") or {}).get("slides") or 1) if n["kind"] == "carousel" else 1
        per_run *= int(d.get("variant_count") or 1)
        if wa.is_each(n):
            produced[n["id"]] = items[n["id"]] * per_run
        else:
            feed = max((produced.get(s, 1) for s in incoming.values()), default=1)
            produced[n["id"]] = per_run if per_run > 1 else feed
    return items, produced, sources


def estimate_workflow(wf: dict[str, Any], cat: dict[str, Any], client: str) -> dict[str, Any]:
    """USD and GPU seconds for the whole workflow, items included. A fan-out node costs its
    single-run estimate times its items; a carousel is priced per slide, as the spec says."""
    import cost
    items, _produced, sources = _item_counts(wf, cat, client)
    total_usd, total_gpu, bases, per_node = 0.0, 0.0, set(), []
    for n in wf["nodes"]:
        d = n.get("data") or {}
        e = cost.estimate(n["kind"], int(d.get("variant_count") or 1), (d.get("params") or {}).get("seconds"))
        mult = items.get(n["id"], 1)
        if n["kind"] == "carousel":
            mult *= int((d.get("params") or {}).get("slides") or 1)
        usd, gpu = round(e["usd"] * mult, 4), round(e.get("gpu_seconds", 0) * mult, 1)
        total_usd += usd
        total_gpu += gpu
        bases.add(e["basis"])
        if e["basis"] != "none":
            per_node.append({"node": n["id"], "kind": n["kind"], "items": mult, "usd": usd, "gpu_seconds": gpu, "basis": e["basis"]})
    basis = "measured" if bases <= {"measured", "none"} else "assumed"
    batch = max([v for k, v in items.items() if wa.is_each(next(n for n in wf["nodes"] if n["id"] == k))], default=1)
    # the batch is the biggest input folder; its count's origin is what the note should say
    biggest = max(sources, key=lambda k: items.get(k, 0), default=None)
    items_basis = sources.get(biggest, "assumed") if biggest else "disk"
    return {"usd": round(total_usd, 4), "gpu_seconds": round(total_gpu, 1), "basis": basis, "items": batch,
            "items_basis": items_basis, "budget_usd": cost.budget_usd(), "per_node": per_node,
            "note": {"disk": "item counts read from the reference folders on disk",
                     "brief": "item count taken from the brief; set the reference folder to confirm it",
                     "assumed": "a reference folder is not set yet; its items are assumed to be 1 until it is"}[items_basis]}


def plan_of(wf: dict[str, Any], client: str, cat: dict[str, Any] | None = None) -> dict[str, Any]:
    """The plan card: every step with its fan-out flag, params, backend and honest status,
    the gaps, the estimate, the consent flag and the inputs a person still has to fill."""
    cat = cat or wa.load_catalog()
    local = _local_steps()
    gap_nodes = {g["node"] for g in wf.get("gaps", [])}
    steps, inputs = [], []
    for n in wf["nodes"]:
        d = n.get("data") or {}
        spec = cat["by_kind"].get(n["kind"])
        step_name = d.get("step", n["kind"]) if n["kind"] == "unmapped" else (d.get("alias") or n["kind"])
        each = wa.is_each(n)
        steps.append({"id": n["id"], "kind": n["kind"], "step": f"{step_name}{wa.EACH_SUFFIX if each else ''}",
                      "label": (spec or {}).get("label", step_name), "each": each, "params": dict(d.get("params") or {}),
                      "backend": (spec or {}).get("backend", {}).get("kind", "gap"),
                      "status": _status(n, spec, gap_nodes, local), "consent": bool((spec or {}).get("consent")),
                      "category": (spec or {}).get("category"), "stage": d.get("stage"),
                      "expected_count": d.get("expected_count"), "role": d.get("role")})
        if spec and spec.get("category") == "inputs":
            params = d.get("params") or {}
            key = next((p["key"] for p in spec.get("params", [])), None)
            if key and not params.get(key):
                inputs.append({"node": n["id"], "kind": n["kind"], "param": key, "role": d.get("role"),
                               "expected_count": d.get("expected_count"),
                               "prompt": {"reference-images": "Which reference collection?", "product-photo": "Which product photo?",
                                          "video-clip": "Which clip?", "song": "Which song?", "brief": "What is the copy?"}.get(n["kind"], f"Fill {key}."),
                               "options": wa.known_collections(client) if n["kind"] == "reference-images" else []})
    return {"steps": steps, "gaps": list(wf.get("gaps", [])), "estimate": estimate_workflow(wf, cat, client),
            "consent_required": bool(wf.get("consent_required")), "inputs": inputs,
            "pending_picks": [n["id"] for n in wf["nodes"] if n["kind"] in ("pick", "pick-video") and not (n.get("data") or {}).get("picked")]}


def _continuations(items: list[dict[str, Any]], batch: int, cat: dict[str, Any]) -> list[dict[str, Any]]:
    """Proposed next stages ("we could then make a reel for each"), each with an estimate."""
    import cost
    out = []
    for c in items:
        spec = cat["by_step"].get(c["step"])
        kind = spec["kind"] if spec else c["step"]
        params = c.get("params") or {}
        e = cost.estimate(kind, 1, params.get("seconds"))
        mult = (batch if c.get("each") else 1) * (int(params.get("slides") or 1) if kind == "carousel" else 1)
        out.append({**c, "kind": kind, "estimate": {"usd": round(e["usd"] * mult, 4), "basis": e["basis"], "items": mult}})
    return out


def _director_preview(client: str, text: str) -> dict[str, Any]:
    """What `say` would start, without writing anything (plan mode on the director route)."""
    import director
    brief = EngineBrief(client=client, title=text[:60] or "Untitled", idea=text)
    if prof := profiles.find(text):
        mutate.set_profile(brief, prof)
    if key := intents.matched_preset(text):
        mutate.set_preset(brief, key)
    return director.plan(brief)


def _reply(wf: dict[str, Any], plan: dict[str, Any], route: str, extended: bool, saved: bool,
           questions: list[dict[str, Any]], added: list[str] | None = None) -> str:
    if questions:
        return questions[0]["prompt"] + (" Nothing was created yet." if not saved else "")
    est = plan["estimate"]
    fan = [s for s in plan["steps"] if s["each"]]
    named = [s["step"] for s in plan["steps"] if s["category"] not in ("inputs", "brand", "publish")]
    if extended:
        named = [s["step"] for s in plan["steps"] if s["id"] in (added or [])] or ["nothing new"]
        head = f"Added {', '.join(named[:6])} to \"{wf['title']}\""
        body = ""
    else:
        head = ("Planned " if not saved else "Created ") + f"\"{wf['title']}\""
        body = ": " + ", ".join(named[:6]) if named else ""
    batch = f"; {est['items']} items per fan-out step" if fan and est["items"] > 1 else ""
    money = f"; est ${est['usd']} ({est['basis']})" if est["usd"] else "; no GPU time in this plan"
    gaps = f"; {len(plan['gaps'])} gap(s)" if plan["gaps"] else ""
    consent = "; consent notice applies" if plan["consent_required"] else ""
    tail = " Nothing runs until you press Run." if saved else " Say create to save it."
    return head + body + batch + money + gaps + consent + "." + tail


def describe(client: str, text: str, session_id: str | None = None, workflow_id: str | None = None,
             mode: str = "create", answers: dict[str, Any] | None = None) -> dict[str, Any]:
    """The describe bar's contract. A sentence becomes an authored workflow (or a directed
    piece when a profile or preset is named); a later sentence on the same session or
    workflow extends it. `plan` mode writes nothing; `create` saves; `direct` forces the
    director route. Refuses a brief that names a person before any node exists."""
    text = (text or "").strip()
    if not text:
        raise DescribeError("Say what to make first.")
    if mode not in MODES:
        raise DescribeError(f"mode must be one of {', '.join(MODES)}")
    if why := intents.refusal(text):
        raise DescribeError(why)
    cat = wa.load_catalog()
    wa.workflow_dir(client)   # refuses an unknown client with a clear message
    existing = _find_session(client, session_id, workflow_id)
    wf_existing = _read_workflow(client, workflow_id) if workflow_id else (_read_workflow(client, existing.workflow_id) if existing else None)
    route = "director" if mode == "direct" else (existing.route if existing else ("author" if wf_existing else intents.route(text)))
    if wf_existing and not existing and wf_existing.get("stages"):
        route = "director"
    save_it = mode != "plan"
    questions: list[dict[str, Any]] = []
    continuations: list[dict[str, Any]] = []
    extended = bool(wf_existing)
    sess: Session | None = existing
    added: list[str] = []

    if route == "director":
        sid = session_id or (existing.id if existing else wa._slug(text[:40]))
        if not save_it and not wf_existing:
            wf = _director_preview(client, text)
        else:
            out = say(client, sid, text, workflow_id=(wf_existing or {}).get("id"))
            wf, sess = out["workflow"], Session(**out["session"])
    else:
        known = wa.known_collections(client)
        if wf_existing:
            rest = intents.continuation(text) or text
            parsed = wa.parse_brief(rest, known, cat, minimal=True)
            wa.apply_answers(parsed, answers, known)
            questions = list(parsed["questions"])
            continuations = parsed["continuations"]
            if not parsed["steps"]:
                raise DescribeError(f"Nothing in \"{text}\" names a step to add. Try a capability, like 'add captions' or 'carousel@each slides=10'.")
            wf = wa.extend(wf_existing, parsed["steps"], cat, params=parsed["params"], language=parsed.get("language"), label=rest[:40])
            added = wf["source"]["extended"][-1]["added"]
            if not added:
                skipped = ", ".join(wf["source"]["extended"][-1]["skipped"]) or rest
                raise DescribeError(f"{skipped} is already in the workflow; nothing was added. "
                                    "Pick another step, or open the canvas to change its settings.")
            if sess is None:
                sess = Session(id=session_id or wf["id"], client=client, workflow_id=wf["id"], brief={}, route="author")
        else:
            parsed = wa.parse_brief(text, known, cat)
            wa.apply_answers(parsed, answers, known)
            questions = list(parsed["questions"])
            wf = wa.from_brief(text, client, plan=parsed, cat=cat)
            continuations = parsed["continuations"]
            sess = Session(id=session_id or wf["id"], client=client, workflow_id=wf["id"], brief={}, route="author")
        if questions:
            save_it = False
        if save_it:
            wa.save(wf)
            sess.utterances.append(text)
            sess.version += 1
            save(sess)

    plan = plan_of(wf, client, cat)
    reply = _reply(wf, plan, route, extended, save_it, questions, added)
    return {"id": wf["id"] if save_it else None,
            "workflow": wf,
            "plan": plan,
            "steps": [s["step"] for s in plan["steps"]],
            "added": added,
            "continuations": _continuations(continuations or (wf.get("source") or {}).get("continuations", []), plan["estimate"]["items"], cat),
            "questions": questions[:2],
            "route": route,
            "mode": mode,
            "extended": extended,
            "saved": save_it,
            "session": asdict(sess) if sess and save_it else ({"id": session_id} if session_id else None),
            "reply": reply}
