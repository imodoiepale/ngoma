"""Run a stage of an engine workflow, one node at a time, under its run mode.

Modes:
  dry-run          nothing is submitted; every node gets a manifest that says so.
  stage-approval   each stage is a control-plane task a human must approve first.
  auto             one `engine_run` approval covers every stage; the runner stops at a pick
                   nobody has made and before anything that publishes.

Queued is not success: a node is `completed` only when ComfyUI's history shows outputs and
those files were fetched. Results live in brands/<client>/runs/<workflow>/<node>/<run>/.

Fan-out (`data.each`, docs/engine/BATCHES.md): the node runs once per item that reaches its
iterated port. Item i, variant v gets seed `base_seed + i * variants + v`; its files land in
`items/<i>/`; the manifest records `items[]` with a `group` (the source item it descends
from) and the node is `completed`, `partial` or `error` by how many items finished. Export
lays grouped files out as `posts/<group>/slide-<n>` so one folder is one post.

Rights gate: a consent-flagged step (head swap, face swap, recreate) runs only when every
reference collection feeding it has a collection.json that says the references are owned,
licensed or fictional, is a data collection (not a study), and records a written release
(`consent: true`) when the subject is a real person. Otherwise the node blocks and says why.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in ("strategy", "comfy-client", "orchestrator"):
    sys.path.insert(0, str(REPO / "packages" / p))
sys.path.insert(0, str(HERE))
import cost  # noqa: E402
import ports  # noqa: E402
import workflow_author as wa  # noqa: E402

BRANDS = REPO / "brands"        # tests point this at a scratch tree; workflows stay under REPO
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm", ".wav", ".mp3"}
PUBLISH_KINDS = {"postiz", "whatsapp-status", "course"}
# a fan-out stops submitting after this many items fail in a row (a broken pod, not a bad item)
EACH_STOP_AFTER = 3
# collection.json values that let a reference feed a step
RIGHTS_OK = ("owned", "licensed", "fictional")
# poses the carousel falls back on when the prompt has fewer lines than `slides`
CAROUSEL_POSES = [
    "standing, facing camera, relaxed, hands at sides",
    "three-quarter turn to the left, looking at camera",
    "seated, leaning forward, elbows on knees",
    "walking towards camera, mid-stride",
    "profile view, looking off frame",
    "close-up, head and shoulders, soft smile",
    "back to camera, looking over the shoulder",
    "leaning against a wall, arms crossed",
    "hands in pockets, weight on one leg",
    "sitting on the floor, legs to one side",
    "full body, arms raised, laughing",
    "crouching, one knee down, looking up at camera",
]


class RunError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(client: str, workflow_id: str) -> dict[str, Any]:
    p = wa.workflow_dir(client) / f"{workflow_id}.studio.json"
    if not p.exists():
        raise RunError(f"no workflow {workflow_id} for {client}")
    return json.loads(p.read_text(encoding="utf-8"))


def run_dir(client: str, workflow_id: str, node_id: str, run_id: str) -> Path:
    return BRANDS / client / "runs" / workflow_id / node_id.replace("/", "_") / run_id


def _order(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    depth = wa._depths(nodes, edges)
    return sorted(nodes, key=lambda n: (depth[n["id"]], n["id"]))


def _stage_of(wf: dict[str, Any], node: dict[str, Any]) -> str:
    """A workflow without stages (an authored template) is one stage called `all`."""
    return node["data"].get("stage") or ("" if wf.get("stages") else "all")


def _stages(wf: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(wf.get("stages") or [{"id": "all", "order": 1}], key=lambda s: s["order"])


# A node is finished for `--stage next` when a live run completed (fully or partially), a
# dry-run wrote its manifest, or the step is a declared gap. `blocked` / `error` stay unfinished.
_STAGE_DONE = frozenset({"completed", "partial", "dry-run", "gap", "provided"})


def next_stage(wf: dict[str, Any], cat: dict[str, Any]) -> str | None:
    """The first stage with a node that has not finished and is not waiting on a person."""
    for s in _stages(wf):
        for n in wf["nodes"]:
            if _stage_of(wf, n) != s["id"]:
                continue
            spec = cat["by_kind"].get(n["kind"], {})
            if spec.get("backend", {}).get("kind") in ("input", "brand", "human"):
                continue
            if _behind_pick(wf, n["id"]):
                continue
            if not any(r.get("status") in _STAGE_DONE for r in n["data"].get("results", [])):
                return s["id"]
    return None


# ---------------------------------------------------------------- what flows between nodes

def _result_items(src: dict[str, Any], r: dict[str, Any]) -> list[dict[str, Any]]:
    """The files one finished result contributes, each with the group it belongs to.

    A fan-out result lists `items`; only completed items count (a partial node passes on what
    finished). A plain result may carry `groups` parallel to `files` (the compositor keeps
    the group of every image it dresses); otherwise the files carry no group."""
    out: list[dict[str, Any]] = []
    if r.get("items"):
        for it in r["items"]:
            if it.get("status") != "completed":
                continue
            for f in it.get("files", []):
                out.append({"file": f, "group": it.get("group"), "src": src["id"]})
        return out
    files = r.get("files", [])
    groups = r.get("groups") if isinstance(r.get("groups"), list) and len(r["groups"]) == len(files) else None
    for i, f in enumerate(files):
        out.append({"file": f, "group": groups[i] if groups else None, "src": src["id"]})
    return out


def _placeholders(src: dict[str, Any], r: dict[str, Any]) -> list[dict[str, Any]]:
    """What a dry-run result would have produced: one placeholder per item or per group, so a
    dry run downstream can count items and name posts before anything has run."""
    if r.get("items"):
        return [{"file": None, "group": it.get("group"), "src": src["id"], "placeholder": f"<{src['id']}#{it['index']}>"}
                for it in r["items"]]
    groups = (r.get("expected") or {}).get("groups") or []
    if groups:
        return [{"file": None, "group": g, "src": src["id"], "placeholder": f"<{src['id']}#{g}>"} for g in groups]
    return [{"file": None, "group": None, "src": src["id"], "placeholder": f"<{src['id']}>"}]


def upstream_items(wf: dict[str, Any], node: dict[str, Any], placeholders: bool = False) -> dict[str, list[dict[str, Any]]]:
    """Per input port, the items that reach it: `{file, group, src}`. A pick passes only what
    was picked. With `placeholders` (dry runs), an upstream that has only dry-run results
    contributes placeholders instead, so the item count is known before anything runs."""
    by_id = {n["id"]: n for n in wf["nodes"]}
    out: dict[str, list[dict[str, Any]]] = {}
    for e in wf["edges"]:
        if e["target"] != node["id"]:
            continue
        src = by_id[e["source"]]
        items: list[dict[str, Any]] = []
        if src["kind"] in ("pick", "pick-video"):
            for ref in src["data"].get("picked") or []:
                sid, run_id, idx = (ref.split("#") + ["", ""])[:3]
                s = by_id.get(sid)
                if not s:
                    continue
                for r in s["data"].get("results", []):
                    if r.get("run_id") == run_id and idx.isdigit():
                        got = _result_items(s, r)
                        if int(idx) < len(got):
                            items.append(got[int(idx)])
        else:
            results = src["data"].get("results", [])
            for r in results:
                if r.get("status") in ("completed", "provided", "partial"):
                    items += _result_items(src, r)
            if not items and placeholders:
                dry = [r for r in results if r.get("status") == "dry-run"]
                if dry:
                    items = _placeholders(src, dry[-1])
        out.setdefault(e["targetHandle"], []).extend(items)
    return out


def upstream_files(wf: dict[str, Any], node: dict[str, Any]) -> dict[str, list[str]]:
    """Files each input port receives: a pick passes only what was picked."""
    return {port: [it["file"] for it in items if it.get("file")] for port, items in upstream_items(wf, node).items()}


def _provided(node: dict[str, Any]) -> dict[str, Any]:
    params = node["data"].get("params", {})
    folder = params.get("folder") or params.get("file") or ""
    files: list[str] = []
    p = BRANDS.parent / folder if folder else None
    if p and p.is_dir():
        files = sorted(str(f.relative_to(BRANDS.parent)).replace("\\", "/") for f in p.rglob("*") if f.suffix.lower() in MEDIA_EXT)
    elif p and p.is_file():
        files = [folder]
    if not files and not folder and str(params.get("text") or "").strip():
        # a text input (brief) is provided by its text, not by files
        return {"run_id": "provided", "status": "provided", "files": [], "text": params["text"], "finished": _now(), "note": ""}
    if not files and not folder and node["kind"] == "brand-kit":
        return {"run_id": "provided", "status": "provided", "files": [], "finished": _now(), "note": "brand.yaml"}
    return {"run_id": "provided", "status": "provided" if files else "missing", "files": files, "finished": _now(),
            "note": "" if files else f"nothing at {folder or '(no folder set)'}"}


def _manifest(client: str, wf: dict[str, Any], node: dict[str, Any], run_id: str, payload: dict[str, Any]) -> Path:
    d = run_dir(client, wf["id"], node["id"], run_id)
    d.mkdir(parents=True, exist_ok=True)
    m = {"run_id": run_id, "workflow": wf["id"], "node": node["id"], "kind": node["kind"], "each": wa.is_each(node), **payload}
    (d / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return d


def _record(node: dict[str, Any], result: dict[str, Any]) -> None:
    results = node["data"].setdefault("results", [])
    results[:] = [r for r in results if r.get("run_id") != result["run_id"]]
    results.append(result)


def _fetch(client_obj: Any, out: dict[str, Any], dest: Path) -> tuple[str, str]:
    """Download one ComfyUI output through /view. Returns (relative path, sha256)."""
    import urllib.parse
    import urllib.request
    q = urllib.parse.urlencode({"filename": out["filename"], "subfolder": out.get("subfolder", ""), "type": out.get("type", "output")})
    req = urllib.request.Request(f"{client_obj.base_url}/view?{q}", headers={"User-Agent": "epalle-studio/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = resp.read()
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / Path(out["filename"]).name
    target.write_bytes(data)
    return str(target.relative_to(BRANDS.parent)).replace("\\", "/"), hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- rights gate

MISSING_RIGHTS = "missing"


def declared_rights(name: str, c: dict[str, Any]) -> str:
    """Why a collection record (collection.json, or the `ref` the director attached to the input
    node) may not feed a consent step; empty when it may.

    It must be a data collection (`use: data`; a study or inspiration collection only informs the
    grammar), say `rights: owned | licensed | fictional` (or `fictional: true`), and for a real
    person (`real_person: true`, or `subject`/`likeness` naming a real person) record a written
    release as `consent: true`, ideally with `release: <path>`."""
    if not isinstance(c, dict):
        return f"collection {name}: collection.json must be an object"
    if str(c.get("use") or "data") != "data":
        return f"collection {name} is a {c.get('use')} collection; it may inform the grammar but never feed a model"
    rights = str(c.get("rights") or "").lower()
    if rights not in RIGHTS_OK and not c.get("fictional") is True:
        return (f"collection {name} has rights: {rights or 'unset'}; a swap step needs rights: owned, licensed or fictional "
                "recorded in collection.json (a real person also needs a written release: consent: true)")
    real = bool(c.get("real_person")) or str(c.get("subject") or "").replace("_", "-").lower() in ("real-person", "real person", "real") \
        or str(c.get("likeness") or "").lower() == "real"
    if real and c.get("consent") is not True:
        return (f"collection {name} is a real person without a written release; swapping a real face is refused until "
                "collection.json records consent: true and release: <path to the signed release>")
    return ""


def collection_rights(folder: Path, fallback: dict[str, Any] | None = None) -> str:
    """`declared_rights` for the collection.json in `folder`. Without one, the director's `ref`
    record is used when given; otherwise MISSING_RIGHTS, which blocks a live run and warns a dry run."""
    cj = folder / "collection.json"
    name = folder.name
    if not cj.exists():
        return declared_rights(name, fallback) if fallback else MISSING_RIGHTS
    try:
        c = json.loads(cj.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        return f"collection {name}: collection.json is not valid JSON ({e})"
    return declared_rights(name, c)


def _collections_feeding(wf: dict[str, Any], node: dict[str, Any]) -> list[tuple[str, Path, dict[str, Any] | None]]:
    """Every reference-images node upstream of this one (at any distance) with a folder set:
    (node id, folder, the `ref` record the director attached, if any)."""
    by_id = {n["id"]: n for n in wf["nodes"]}
    seen, todo, out = set(), [node["id"]], []
    while todo:
        cur = todo.pop()
        for e in wf["edges"]:
            if e["target"] == cur and e["source"] not in seen:
                seen.add(e["source"])
                src = by_id.get(e["source"])
                if src is None:
                    continue
                folder = (src["data"].get("params") or {}).get("folder")
                if src["kind"] == "reference-images" and folder:
                    ref = src["data"].get("ref")
                    out.append((src["id"], BRANDS.parent / folder, ref if isinstance(ref, dict) else None))
                todo.append(e["source"])
    return out


def rights_gate(wf: dict[str, Any], node: dict[str, Any], spec: dict[str, Any], mode: str) -> tuple[str, str]:
    """(block reason, warning). Only consent-flagged kinds are gated. A collection whose record
    says it may not feed a model blocks in every mode; a collection with no record at all blocks a
    live run and only warns a dry run, so planning can proceed while the paperwork is written."""
    if not spec.get("consent"):
        return "", ""
    problems, missing = [], []
    for _sid, folder, ref in _collections_feeding(wf, node):
        p = collection_rights(folder, ref)
        if p == MISSING_RIGHTS:
            missing.append(folder.name)
        elif p:
            problems.append(p)
    head = f"rights gate: {node['kind']} consumes a face or character reference and "
    if problems:
        return head + "; ".join(problems), ""
    if missing:
        msg = (head + f"collection(s) {', '.join(missing)} have no collection.json; write one with use: data and rights: "
               "owned, licensed or fictional (and consent: true plus release: <path> for a real person) before it runs live")
        return ("", msg) if mode == "dry-run" else (msg, "")
    return "", ""


# ---------------------------------------------------------------- running one node

def _item_count(wf: dict[str, Any], node: dict[str, Any], cat: dict[str, Any]) -> int:
    """How many times a node will run: the items on its iterated port, or 1."""
    if not wa.is_each(node):
        return 1
    port = wa.iterated_port(node, cat)
    return max(1, len(upstream_items(wf, node, placeholders=True).get(port or "", []))) if port else 1


def _carousel_prompt(d: dict[str, Any]) -> str | None:
    """The carousel makes one image per prompt line: `slides` lines, padding with neutral poses
    when the prompt has fewer and trimming when it has more."""
    slides = (d.get("params") or {}).get("slides")
    lines = [ln.strip() for ln in str(d.get("prompt") or "").splitlines() if ln.strip()]
    if not slides:
        return "\n".join(lines) if lines else None
    slides = max(1, int(slides))
    if len(lines) < slides:
        lines += [CAROUSEL_POSES[i % len(CAROUSEL_POSES)] for i in range(len(lines), slides)]
    return "\n".join(lines[:slides])


def _bindings_common(spec: dict[str, Any], pm: dict[str, Any], d: dict[str, Any], ups: dict[str, list[dict[str, Any]]],
                     feeders: dict[str, str], mode: str, skip: str | None) -> tuple[dict[str, Any], str]:
    """Bind every input port but `skip`. Returns (bindings, problem)."""
    bindings: dict[str, Any] = {}
    for port in spec["inputs"]:
        if port["id"] == skip:
            continue
        files = [it["file"] or it.get("placeholder") for it in ups.get(port["id"], [])]
        if files:
            bindings[port["id"]] = files[0] if len(files) == 1 or port["type"] != "image" else files
        elif not port.get("optional"):
            if mode == "dry-run" and port["id"] in feeders:
                # nothing has run yet; a dry run records where the input would come from
                bindings[port["id"]] = f"<{feeders[port['id']]}>"
                continue
            return bindings, (f"input {port['id']} has nothing to feed it yet"
                              + (f"; run the stage that makes {feeders[port['id']]} first" if port["id"] in feeders else ""))
    prompt = _carousel_prompt(d) if spec["kind"] == "carousel" else d.get("prompt")
    if prompt:
        bindings["prompt"] = prompt
    if d.get("negative"):
        bindings["negative"] = d["negative"]
    for key, value in (d.get("params") or {}).items():
        if key in pm.get("params", {}) and value not in (None, ""):
            bindings[key] = value
    return bindings, ""


def _base_seed(node: dict[str, Any]) -> int:
    return int(node["data"].get("seed") or (int(hashlib.sha256(node["id"].encode()).hexdigest(), 16) % 10_000_000))


def run_node(client: str, wf: dict[str, Any], node: dict[str, Any], mode: str, backend: str,
             cat: dict[str, Any], comfy_factory: Callable[..., Any] | None = None) -> dict[str, Any]:
    spec = cat["by_kind"].get(node["kind"])
    if not spec:
        return {"status": "gap", "note": "unmapped step"}
    be = spec["backend"]
    run_id = f"r-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{node['id'][-12:].replace('.', '-')}"
    d = node["data"]
    variants = int(d.get("variant_count") or 1)
    est = cost.estimate_node(node, items=_item_count(wf, node, cat))

    def finish(res: dict[str, Any]) -> dict[str, Any]:
        res = {"run_id": run_id, **res, "finished": _now()}
        _manifest(client, wf, node, run_id, res)
        _record(node, res)
        return res

    if be["kind"] in ("input", "brand"):
        res = _provided(node)
        _record(node, res)
        return res
    if be["kind"] == "human":
        return {"status": "waiting" if not d.get("picked") else "picked", "run_id": None}
    if be["kind"] == "gap":
        return finish({"status": "gap", "note": be.get("reason")})
    if be["kind"] in ("python", "publish"):
        if be["kind"] == "python" and node["kind"] in LOCAL_STEPS:
            return finish({**_run_local(client, wf, node, mode, run_id), "cost_estimate": est})
        return finish({"status": "dry-run" if mode == "dry-run" else "skipped",
                       "note": f"{be['kind']} step {be.get('module')} is not run by the engine; publishing goes through a person",
                       "cost_estimate": est})

    # ComfyUI
    try:
        pm = ports.load_port_map(be["workflow"])
    except ports.PortMapError as e:
        return finish({"status": "blocked", "note": f"no usable port map for {be['workflow']}: {e}", "cost_estimate": est})
    why, warning = rights_gate(wf, node, spec, mode)
    if why:
        return finish({"status": "blocked", "reason": "rights", "note": why, "cost_estimate": est})
    extra = {"rights_warning": warning} if warning else {}
    if wa.is_each(node):
        return finish({**_run_each(client, wf, node, mode, backend, cat, spec, be, pm, run_id, comfy_factory), **extra})

    ups = upstream_items(wf, node, placeholders=(mode == "dry-run"))
    feeders = {e["targetHandle"]: e["source"] for e in wf["edges"] if e["target"] == node["id"]}
    bindings, problem = _bindings_common(spec, pm, d, ups, feeders, mode, skip=None)
    if problem:
        return finish({"status": "blocked", "note": problem, "cost_estimate": est})
    base_seed = _base_seed(node)
    payload = {"backend": backend, "comfy_workflow": be["workflow"], "bindings": bindings,
               "seeds": [base_seed + i for i in range(variants)], "cost_estimate": est, "started": _now(), **extra}
    if mode == "dry-run":
        return finish({"status": "dry-run", "files": [], **payload})

    graph = json.loads((REPO / "workflows" / be["workflow"]).read_text(encoding="utf-8"))
    comfy = (comfy_factory or _default_factory)(backend)
    files, shas, log, prompt_ids, status, detail = [], [], [], [], "completed", ""
    t0 = time.time()
    try:
        bindings = {**bindings, **_stage_inputs(comfy, pm, bindings, run_dir(client, wf["id"], node["id"], run_id) / "inputs")}
    except Exception as e:  # noqa: BLE001 - an upload or conversion failure is the node's error, not a crash
        return finish({"status": "error", "detail": f"could not put inputs on the pod: {e}", **payload})
    payload["uploaded"] = {k: bindings[k] for k in pm["inputs"] if k in bindings}
    for seed in payload["seeds"]:
        outcome = _submit_one(comfy, graph, pm, {**bindings, "seed": seed, "count": 1}, be["workflow"],
                              run_dir(client, wf["id"], node["id"], run_id), log)
        prompt_ids += outcome["prompt_ids"]
        files += outcome["files"]
        shas += outcome["sha256"]
        if outcome["status"] != "completed":
            status, detail = outcome["status"], outcome["detail"]
            break
    return finish({"status": status, "detail": detail, "files": files, "sha256": shas, "prompt_ids": prompt_ids,
                   "log": log[:40], "gpu_seconds_actual": round(time.time() - t0, 1), **payload})


def _submit_one(comfy: Any, graph: dict[str, Any], pm: dict[str, Any], bindings: dict[str, Any], workflow_rel: str,
                dest: Path, log: list[str]) -> dict[str, Any]:
    """Bind, submit, wait, fetch: one ComfyUI job. Queued is not success."""
    g, changes = ports.bind(json.loads(json.dumps(graph)), pm, bindings)
    log += changes
    sub = comfy.submit(g, workflow_name=Path(workflow_rel).stem, dry_run=False)
    pid = sub.get("prompt_id") or (sub.get("output") or {}).get("prompt_id")
    if not pid:
        return {"status": "error", "detail": f"no prompt_id in {json.dumps(sub)[:200]}", "prompt_ids": [], "files": [], "sha256": []}
    done = comfy.wait(pid)
    if done.get("status") != "COMPLETED":
        return {"status": done.get("status", "error").lower(), "detail": json.dumps(done.get("detail", ""))[:300],
                "prompt_ids": [pid], "files": [], "sha256": []}
    files, shas = [], []
    for o in done.get("outputs", []):
        rel, sha = _fetch(comfy, o, dest)
        files.append(rel)
        shas.append(sha)
    return {"status": "completed", "detail": "", "prompt_ids": [pid], "files": files, "sha256": shas}


def _run_each(client: str, wf: dict[str, Any], node: dict[str, Any], mode: str, backend: str, cat: dict[str, Any],
              spec: dict[str, Any], be: dict[str, Any], pm: dict[str, Any], run_id: str,
              comfy_factory: Callable[..., Any] | None) -> dict[str, Any]:
    """One ComfyUI submission per item per variant over the iterated port (module doc)."""
    d = node["data"]
    variants = int(d.get("variant_count") or 1)
    dry = mode == "dry-run"
    port = wa.iterated_port(node, cat)
    if not port:
        return {"status": "blocked", "note": "fans out per item but has no image or video input to iterate"}
    ups = upstream_items(wf, node, placeholders=dry)
    feeders = {e["targetHandle"]: e["source"] for e in wf["edges"] if e["target"] == node["id"]}
    items_in = ups.get(port, [])
    if not items_in:
        return {"status": "blocked", "each_port": port, "items": [], "item_count": 0,
                "note": f"input {port} has nothing to feed it yet"
                + (f"; run the stage that makes {feeders[port]} first" if port in feeders else "")}
    cap = cost.max_items()
    if len(items_in) > cap:
        return {"status": "blocked", "each_port": port, "items": [], "item_count": len(items_in),
                "note": f"{len(items_in)} items reach {port} but max_items is {cap} in brands/_presets/engine.yaml; "
                        "split the collection or raise the cap on purpose"}
    retry = d.get("retry_items")
    indices = [i for i in range(len(items_in)) if not retry or i in retry]
    common, problem = _bindings_common(spec, pm, d, ups, feeders, mode, skip=port)
    if problem:
        return {"status": "blocked", "each_port": port, "items": [], "item_count": len(items_in), "note": problem}
    est = cost.estimate_node(node, items=len(indices))
    base_seed = _base_seed(node)
    items_out: list[dict[str, Any]] = []
    for i in indices:
        it = items_in[i]
        items_out.append({"index": i, "group": it["group"] if it["group"] is not None else str(i),
                          "input": it["file"] or it.get("placeholder"), "from": it["src"],
                          "seeds": [base_seed + i * variants + v for v in range(variants)],
                          "status": "dry-run" if dry else "pending", "files": [], "sha256": [], "prompt_ids": []})
    payload = {"backend": backend, "comfy_workflow": be["workflow"], "each_port": port, "bindings": common,
               "item_count": len(items_in), "items": items_out, "layout": "items/<index>/",
               "seeds": [s for it in items_out for s in it["seeds"]], "cost_estimate": est, "started": _now()}
    groups = sorted({it["group"] for it in items_out}, key=lambda g: (len(g), g))
    if dry:
        return {"status": "dry-run", "files": [], "groups": groups, **payload,
                "note": f"would run {node['kind']} once per item: {len(indices)} item(s) x {variants} variant(s), "
                        f"about {est['gpu_seconds']} GPU s ({est['basis']})"}

    graph = json.loads((REPO / "workflows" / be["workflow"]).read_text(encoding="utf-8"))
    comfy = (comfy_factory or _default_factory)(backend)
    base = run_dir(client, wf["id"], node["id"], run_id)
    cache: dict[str, str] = {}
    log: list[str] = []
    t_all = time.time()
    try:
        shared = _stage_inputs(comfy, pm, common, base / "inputs", cache)
    except Exception as e:  # noqa: BLE001 - an upload failure is the node's error, not a crash
        return {"status": "error", "detail": f"could not put inputs on the pod: {e}", **payload}
    payload["uploaded"] = shared
    consecutive = 0
    for k, it in enumerate(items_out):
        t0 = time.time()
        src = items_in[it["index"]]
        try:
            mine = _stage_inputs(comfy, pm, {port: src["file"]}, base / "inputs", cache)
        except Exception as e:  # noqa: BLE001
            it["status"], it["detail"] = "error", f"could not put {src['file']} on the pod: {e}"
        else:
            it["uploaded"] = mine.get(port)
            for seed in it["seeds"]:
                outcome = _submit_one(comfy, graph, pm, {**common, **shared, **mine, "seed": seed, "count": 1},
                                      be["workflow"], base / "items" / str(it["index"]), log)
                it["prompt_ids"] += outcome["prompt_ids"]
                it["files"] += outcome["files"]
                it["sha256"] += outcome["sha256"]
                if outcome["status"] != "completed":
                    it["status"], it["detail"] = outcome["status"], outcome["detail"]
                    break
            if it["status"] == "pending":
                it["status"] = "completed"
        it["gpu_seconds_actual"] = round(time.time() - t0, 1)
        consecutive = 0 if it["status"] == "completed" else consecutive + 1
        if consecutive >= EACH_STOP_AFTER and k + 1 < len(items_out):
            for rest in items_out[k + 1:]:
                rest["status"], rest["detail"] = "skipped", f"{EACH_STOP_AFTER} items failed in a row; stopped before spending more"
            break
    done = [it for it in items_out if it["status"] == "completed"]
    failed = [it["index"] for it in items_out if it["status"] != "completed"]
    status = "completed" if not failed else ("partial" if done else "error")
    return {"status": status, "files": [f for it in done for f in it["files"]], "sha256": [s for it in done for s in it["sha256"]],
            "groups": [it["group"] for it in done for _f in it["files"]], "prompt_ids": [p for it in items_out for p in it["prompt_ids"]],
            "failed": failed, "detail": "; ".join(f"item {it['index']}: {it.get('detail', it['status'])}" for it in items_out if it["status"] != "completed")[:600],
            "log": log[:40], "gpu_seconds_actual": round(time.time() - t_all, 1), **payload,
            "note": f"{len(done)} of {len(items_out)} item(s) completed" + (f"; failed: {failed}" if failed else "")}


def _stage_inputs(comfy: Any, pm: dict[str, Any], bindings: dict[str, Any], scratch: Path,
                  cache: dict[str, str] | None = None) -> dict[str, Any]:
    """Upload every file an input port binds into ComfyUI's input folder, converting first where
    the port map says so. Returns the bindings rewritten to the names ComfyUI loaders expect.
    `cache` (relative path -> uploaded name) lets a batch upload a shared reference once."""
    import edit
    out: dict[str, Any] = {}
    cache = cache if cache is not None else {}
    for key, ref in pm["inputs"].items():
        if key not in bindings:
            continue
        value = bindings[key]
        names = []
        for rel in (value if isinstance(value, list) else [value]):
            if rel in cache:
                names.append(cache[rel])
                continue
            src = BRANDS.parent / rel
            if not src.is_file():
                raise RunError(f"{key}: {rel} is not a file")
            if ref.get("transform") == "audio_to_video":
                src = edit.audio_to_video(src, scratch / f"{src.stem}.mp4")
            cache[rel] = comfy.upload(src)
            names.append(cache[rel])
        out[key] = names if isinstance(value, list) else names[0]
    return out


# ---------------------------------------------------------------- local steps

# steps this machine runs itself (packages/engine/edit.py, packages/video/motion_graphics.py,
# packages/voice/translate.py, packages/engine/lora_train.py); publishing never runs here
LOCAL_STEPS = {"voiceover", "cut", "captions", "export", "compositor", "claim-check", "hooks", "transcribe",
               "motion-graphics", "translate", "lora-train"}
# which input a local step cannot do without
_LOCAL_NEED = {"cut": "video", "captions": "video", "export": "media", "compositor": "media", "transcribe": "media",
               "lora-train": "images"}
_LOCAL_TEXT = {"claim-check": "text", "hooks": "text", "motion-graphics": "script", "translate": "text"}
# why a live lora-train never trains from here (docs/BLOCKERS.md item 3; infra/runpod/README.md "Training")
LORA_TRAIN_BLOCKED = ("training never runs from the engine: the plan (config.yaml + launch.sh) is written and a "
                      "person starts it on the pod once FLUX.2 Klein 9B's licence is accepted on Hugging Face "
                      "(docs/BLOCKERS.md item 3) and ostris/ai-toolkit is on the pod (infra/runpod/setup-pod.sh)")


def _feeder_text(wf: dict[str, Any], node: dict[str, Any], port: str) -> str:
    """Text arriving on a port: an input node's `params.text`, or the latest completed result's
    `text` of a step that makes text (claim-check, hooks, transcribe)."""
    by_id = {n["id"]: n for n in wf["nodes"]}
    parts = []
    for e in wf["edges"]:
        if e["target"] != node["id"] or e["targetHandle"] != port or e["source"] not in by_id:
            continue
        src = by_id[e["source"]]
        text = (src["data"].get("params") or {}).get("text") or ""
        if not text:
            done = [r for r in src["data"].get("results", []) if r.get("status") == "completed" and r.get("text")]
            text = done[-1]["text"] if done else ""
        parts.append(text)
    return "\n\n".join(p.strip() for p in parts if p.strip())


def _feeder_folder(wf: dict[str, Any], node: dict[str, Any], port: str, files: list[str]) -> Path | None:
    """The reference folder feeding a port: the input node's `params.folder`, else the common
    parent of the files that reached it. Relative to the repo root (BRANDS.parent)."""
    by_id = {n["id"]: n for n in wf["nodes"]}
    for e in wf["edges"]:
        if e["target"] == node["id"] and e["targetHandle"] == port and e["source"] in by_id:
            folder = (by_id[e["source"]]["data"].get("params") or {}).get("folder")
            if folder:
                return Path(folder)
    if files:
        parents = {Path(f).parent for f in files}
        return parents.pop() if len(parents) == 1 else None
    return None


def _motion_spec(text: str, params: dict[str, Any], client: str | None, background: str | None) -> dict[str, Any]:
    """One motion-graphics line per non-empty line of the script, spread evenly over the
    duration with a short overlap, in the style the node asks for. Deterministic."""
    lines = [l.strip() for l in text.splitlines() if l.strip()] or [text.strip()]
    duration = float(params.get("duration") or 6)
    style = str(params.get("style") or "headline")
    slot = duration / len(lines)
    spec: dict[str, Any] = {
        "aspect": str(params.get("aspect") or "9:16"), "fps": 24, "duration": duration, "client": client,
        "lines": [{"text": t, "in": round(i * slot, 3), "out": round(min(duration, (i + 1) * slot + 0.2), 3), "style": style}
                  for i, t in enumerate(lines)],
    }
    if background:
        spec["background"] = {"video": background}
    return spec


def _run_local(client: str, wf: dict[str, Any], node: dict[str, Any], mode: str, run_id: str) -> dict[str, Any]:
    import edit
    dry = mode == "dry-run"
    items = upstream_items(wf, node, placeholders=dry)
    ups = {port: [it["file"] for it in its if it.get("file")] for port, its in items.items()}
    dest = run_dir(client, wf["id"], node["id"], run_id)
    params = node["data"].get("params") or {}
    feeders = {e["targetHandle"] for e in wf["edges"] if e["target"] == node["id"]}
    kind = node["kind"]
    need = _LOCAL_NEED.get(kind)
    if need and not ups.get(need):
        if dry and need in feeders:
            expected = items.get(need, [])
            groups = sorted({str(it["group"]) for it in expected if it.get("group") is not None}, key=lambda g: (len(g), g))
            if kind == "export" and groups:
                names = ", ".join(groups)
                return {"status": "dry-run", "files": [], "layout": "posts/<group>/slide-<n>", "expected": {"groups": groups},
                        "note": f"would export what the upstream steps make as {len(groups)} post folder(s) posts/<group>/slide-<n> for groups {names}"}
            note = f"would {kind} what the upstream {need} steps make"
            if kind == "compositor":
                _spec, problem = edit.brand_kit(BRANDS / client)
                note = f"would composite what the upstream media steps make with the {client} kit (logo + exact copy), ratio {params.get('ratio') or '4:5'}"
                if groups:
                    note += f" across {len(groups)} post(s)"
                if problem:
                    note += f"; blocked until fixed: {problem}"
            return {"status": "dry-run", "files": [], "expected": {"groups": groups}, "note": note}
        return {"status": "blocked", "files": [], "note": f"input {need} has nothing to feed it yet"}
    text_port = _LOCAL_TEXT.get(kind)
    text = _feeder_text(wf, node, text_port) if text_port else ""
    if text_port and not text:
        if dry and text_port in feeders:
            return {"status": "dry-run", "files": [], "note": f"would {kind} the text the upstream step makes"}
        return {"status": "blocked", "files": [], "note": f"input {text_port} has no text yet"}
    absolute = lambda rels: [BRANDS.parent / r for r in rels]  # noqa: E731
    groups_of = lambda port: [it.get("group") for it in items.get(port, []) if it.get("file")]  # noqa: E731
    try:
        if kind == "voiceover":
            lang = params.get("language") or (wf.get("source", {}).get("engine") or {}).get("language") or "en"
            out = edit.voiceover(_feeder_text(wf, node, "script"), lang, dest / "voiceover.mp3", params.get("provider"), dry_run=dry)
        elif kind == "cut":
            out = edit.concat(absolute(ups["video"]), dest / "cut.mp4", params.get("seconds"), dry_run=dry)
        elif kind == "captions":
            audio = absolute(ups.get("audio", []))[:1]
            if not audio and "audio" in feeders and not dry:
                return {"status": "blocked", "files": [], "note": "the voiceover has not been made yet"}
            out = edit.captions(absolute(ups["video"])[-1], audio[0] if audio else None,
                                _feeder_text(wf, node, "script") or None, dest / "captioned.mp4", dry_run=dry)
        elif kind == "compositor":
            out = edit.composite_batch(absolute(ups["media"]), groups_of("media"), BRANDS / client,
                                       _feeder_text(wf, node, "copy"), str(params.get("ratio") or "4:5"),
                                       dest, wf["id"][:40], dry_run=dry)
        elif kind == "claim-check":
            out = edit.claim_check(text, BRANDS / client, dry_run=dry)
            if not dry:
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "claim-check.json").write_text(json.dumps({k: out.get(k) for k in ("verdict", "flags")}, indent=2), encoding="utf-8")
        elif kind == "hooks":
            out = edit.hooks(text, int(params.get("count") or 10), seed=_base_seed(node), dry_run=dry)
            if not dry and out.get("hooks"):
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "hooks.txt").write_text(out["text"] + "\n", encoding="utf-8")
                out["files"] = [str(dest / "hooks.txt")]
        elif kind == "transcribe":
            out = edit.transcribe(absolute(ups["media"])[-1], dest / "transcript.txt", params.get("language"), dry_run=dry)
        elif kind == "motion-graphics":
            out = _motion_graphics(client, text, params, absolute(ups.get("background", []))[-1:], dest, dry)
        elif kind == "translate":
            out = _translate(text, params, dest, dry)
        elif kind == "lora-train":
            out = _lora_train(client, wf, node, ups, params, dest, dry)
        else:
            out = edit.export(absolute(ups["media"]), dest / "export", dry_run=dry, groups=groups_of("media"))
    except (edit.EditError, OSError) as e:
        return {"status": "error", "files": [], "note": str(e)}
    out["files"] = [str(Path(f).resolve().relative_to(BRANDS.parent.resolve())).replace("\\", "/") for f in out.get("files", [])]
    return out


def _under_brands(mod: Any, fn: Callable[[], Any]) -> Any:
    """Run `fn` with the module's BRANDS pointed at the runner's (tests point the runner at a
    scratch tree); restored afterwards so nothing else sees the swap."""
    prev = mod.BRANDS
    mod.BRANDS = BRANDS
    try:
        return fn()
    finally:
        mod.BRANDS = prev


def _motion_graphics(client: str, text: str, params: dict[str, Any], background: list[Path], dest: Path, dry: bool) -> dict[str, Any]:
    """packages/video/motion_graphics.py: Pillow frames piped into ffmpeg, no GPU. Dry-run writes
    the frame plan (`<out>.plan.json`) and nothing else."""
    sys.path.insert(0, str(REPO / "packages" / "video"))
    import motion_graphics as mg
    kit = client if (BRANDS / client / "brand.yaml").exists() else None
    spec = _motion_spec(text, params, kit, background[0].as_posix() if background else None)
    try:
        p = _under_brands(mg, lambda: mg.render(spec, dest / "motion.mp4", dry_run=dry))
    except mg.MotionGraphicsError as e:
        return {"status": "error", "files": [], "note": str(e)}
    out = {"status": p["status"], "note": p["note"], "plan": p["plan_path"], "spec": spec,
           "frame_count": p["frame_count"], "size": [p["width"], p["height"]], "fonts": p["fonts"]}
    out["files"] = [p["file"]] if p.get("file") else []
    return out


def _translate(text: str, params: dict[str, Any], dest: Path, dry: bool) -> dict[str, Any]:
    """packages/voice/translate.py over OpenRouter. Dry-run writes the exact request and sends
    nothing; live needs OPENROUTER_API_KEY in the vault and otherwise blocks, never errors."""
    sys.path.insert(0, str(REPO / "packages" / "voice"))
    import translate as tr
    src, dst = str(params.get("source") or "en"), str(params.get("language") or "sw")
    glossary = params.get("glossary") or None
    glossary_path = (BRANDS.parent / glossary) if glossary and not Path(glossary).is_absolute() else (Path(glossary) if glossary else None)
    if not dry and not tr._secret("OPENROUTER_API_KEY"):
        return {"status": "blocked", "files": [], "reason": "secret",
                "note": "OPENROUTER_API_KEY is not in the vault; translation is a paid call. Store it with "
                        "python infra/runpod/set_secret.py openrouter, or run the stage in dry-run"}
    dest.mkdir(parents=True, exist_ok=True)
    source = dest / f"source.{src}.txt"
    source.write_text(text.strip() + "\n", encoding="utf-8")
    target = dest / f"translated.{dst}.txt"
    try:
        r = tr.translate_file(source, target, src, dst, glossary_path, dry_run=dry)
    except tr.TranslateError as e:
        return {"status": "error", "files": [], "note": str(e)}
    if dry:
        req = dest / "request.json"
        req.write_text(json.dumps(r["request"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"status": "dry-run", "files": [], "request": _rel_repo(req), "units": r["units"],
                "glossary": r["glossary"], "note": r["note"] + f"; request written to {_rel_repo(req)}"}
    return {"status": "completed", "files": [target], "text": target.read_text(encoding="utf-8").strip(),
            "model": r["model"], "problems": r["problems"], "units": r["units"], "note": r["note"]}


def _lora_train(client: str, wf: dict[str, Any], node: dict[str, Any], ups: dict[str, list[str]],
                params: dict[str, Any], dest: Path, dry: bool) -> dict[str, Any]:
    """packages/engine/lora_train.py: the rights gate, config.yaml and launch.sh. Always a plan;
    live mode stages the dataset too and then blocks with why training is a person's job."""
    import lora_train as lt
    folder = _feeder_folder(wf, node, "images", ups.get("images", []))
    if folder is None:
        return {"status": "blocked", "files": [], "note": "input images must come from one reference folder"}
    if folder.parts[:3] != ("brands", client, "references"):
        return {"status": "blocked", "files": [], "reason": "rights",
                "note": f"{folder.as_posix()} is not a reference collection of {client}; a LoRA trains only on "
                        f"brands/{client}/references/<collection> with its collection.json"}
    collection = folder.name
    trigger = str(params.get("trigger") or "").strip().lower()
    if not trigger:
        trigger = re.sub(r"[^a-z0-9_]", "", collection.lower().replace("-", "_"))[:24]
        trigger = trigger if re.fullmatch(r"[a-z][a-z0-9_]{2,23}", trigger) else f"chr_{trigger}"[:24]
    captions = ups.get("captions", [])
    cap_path: Path | None = None
    if captions:
        first = BRANDS.parent / captions[0]
        cap_path = first if first.suffix.lower() in (".json", ".jsonl") else first.parent
    try:
        plan = _under_brands(lt, lambda: lt.plan_job(client, collection, trigger, base=params.get("base") or None,
                                                     steps=int(params.get("steps") or 3000), rank=int(params.get("rank") or 16),
                                                     captions=cap_path, out=dest, dry_run=dry))
    except lt.LoraTrainError as e:
        msg = str(e)
        if msg.startswith("refused"):
            return {"status": "blocked", "files": [], "reason": "rights", "note": msg}
        return {"status": "error", "files": [], "note": msg}
    files = [BRANDS.parent / plan["config"], BRANDS.parent / plan["launch"]]
    out = {k: plan[k] for k in ("rights", "base", "steps", "rank", "images", "captions", "config", "launch",
                                "pod_dir", "output", "command", "needs_setup", "gpu_estimate")}
    if dry:
        return {**out, "status": "dry-run", "files": [], "note": plan["note"]}
    if plan.get("manifest"):
        files.append(BRANDS.parent / plan["manifest"])
    return {**out, "status": "blocked", "reason": "training", "dataset": plan.get("dataset"),
            "files": [str(f) for f in files if Path(f).exists()], "note": f"{plan['note']}. {LORA_TRAIN_BLOCKED}"}


def _rel_repo(p: Path) -> str:
    return str(Path(p).resolve().relative_to(BRANDS.parent.resolve())).replace("\\", "/")


def _default_factory(backend: str) -> Any:
    from client import ComfyClient
    return ComfyClient(backend=backend)


# ---------------------------------------------------------------- stages and the gate

def _gate(client: str, wf: dict[str, Any], stage: str, mode: str, nodes: list[dict[str, Any]],
          approve_as: str | None, db: Path | None, items: dict[str, int] | None = None) -> dict[str, Any]:
    """Control-plane gate for anything that spends. Returns {"ok": bool, "task": id, "why": str}."""
    import control
    con = control.connect(db) if db else control.connect()
    name = cost.worker_name()
    try:
        control.worker(con, name)
    except control.ControlError:
        control.add_worker(con, name, "local", "director engine", cost.budget_usd(), actor="system")
    est = cost.estimate_nodes(nodes, items)
    kind = "engine_stage" if mode == "stage-approval" else "generate_draft"
    if mode == "auto":
        # one engine_run approval for the whole workflow must exist and be approved
        ok = con.execute("SELECT id FROM tasks WHERE kind='engine_run' AND status IN ('ready','running','done') AND spec LIKE ?",
                         (f'%"workflow": "{wf["id"]}"%',)).fetchone()
        if not ok:
            tid = control.propose(con, control.Task(client, "engine_run", f"Run {wf['title']} end to end",
                                                    {"workflow": wf["id"], "estimate": est}, assigned_to=name,
                                                    estimate_usd=est["usd"], created_by="engine"))
            if approve_as:
                control.approve(con, tid, approve_as)
            else:
                return {"ok": False, "task": tid, "why": f"auto mode needs one approval of task {tid} (engine_run) first"}
    label = f"{wf['title']}: stage {stage}" + (f" ({est['items']} items)" if est.get("items", 0) > 1 else "")
    tid = control.propose(con, control.Task(client, kind, label,
                                            {"workflow": wf["id"], "stage": stage, "estimate": est, "items": items or {}},
                                            assigned_to=name, estimate_usd=est["usd"], created_by="engine"))
    if kind == "engine_stage":
        if not approve_as:
            return {"ok": False, "task": tid, "why": f"stage {stage} waits for a human to approve task {tid} "
                                                  f"(est ${est['usd']}, {est['items']} item(s), {est['basis']})"}
        control.approve(con, tid, approve_as)
    try:
        control.start(con, tid)
    except control.ControlError as e:
        return {"ok": False, "task": tid, "why": str(e)}
    return {"ok": True, "task": tid, "con": con, "control": control, "estimate": est}


def _provide_inputs(wf: dict[str, Any], cat: dict[str, Any]) -> None:
    """Inputs and the brand kit are on disk, so they are resolved before any stage runs (free,
    nothing is submitted). A folder that has since gained files is picked up on the next run."""
    for n in wf["nodes"]:
        if cat["by_kind"].get(n["kind"], {}).get("backend", {}).get("kind") in ("input", "brand"):
            if not any(r.get("status") == "provided" and (r.get("files") or r.get("text") or n["kind"] == "brand-kit")
                       for r in n["data"].get("results", [])):
                _record(n, _provided(n))


def _total_estimate(results: list[dict[str, Any]]) -> dict[str, Any]:
    ests = [r.get("cost_estimate") or {} for r in results]
    basis = {e.get("basis", "none") for e in ests}
    return {"usd": round(sum(e.get("usd", 0) for e in ests), 4),
            "gpu_seconds": round(sum(e.get("gpu_seconds", 0) for e in ests), 1),
            "items": sum(e.get("items", 1) for e in ests if e.get("basis", "none") != "none"),
            "basis": "measured" if basis <= {"measured", "none"} else "assumed"}


def run_stage(client: str, workflow_id: str, stage: str, mode: str | None = None, backend: str = "pod",
              approve_as: str | None = None, db: Path | None = None,
              comfy_factory: Callable[..., Any] | None = None, wf: dict[str, Any] | None = None,
              save: bool = True) -> dict[str, Any]:
    cat = wa.load_catalog()
    wf = wf or _read(client, workflow_id)
    mode = mode or wf.get("run_mode") or "dry-run"
    if mode not in wa.RUN_MODES:
        raise RunError(f"unknown mode {mode}")
    if stage == "next":
        stage = next_stage(wf, cat) or ""
        if not stage:
            return {"ok": True, "stage": None, "mode": mode, "note": "every stage has completed", "results": [],
                    "cost_estimate": _total_estimate([])}
    nodes = [n for n in _order(wf["nodes"], wf["edges"]) if _stage_of(wf, n) == stage]
    if not nodes:
        raise RunError(f"no stage {stage!r} in {workflow_id}")
    _provide_inputs(wf, cat)

    # GPU steps, and narration from a paid voice (ElevenLabs bills per character)
    spends = [n for n in nodes if cat["by_kind"].get(n["kind"], {}).get("backend", {}).get("kind") == "comfy"
              or (n["kind"] == "voiceover" and (n["data"].get("params") or {}).get("provider", "elevenlabs") in ("elevenlabs", "openai"))]
    publishes = [n for n in nodes if n["kind"] in PUBLISH_KINDS]
    gate: dict[str, Any] = {"ok": True}
    if mode != "dry-run" and spends:
        gate = _gate(client, wf, stage, mode, spends, approve_as, db, {n["id"]: _item_count(wf, n, cat) for n in spends})
        if not gate["ok"]:
            return {"ok": False, "stage": stage, "mode": mode, "task": gate["task"], "note": gate["why"], "results": []}
    if mode != "dry-run" and publishes:
        return {"ok": False, "stage": stage, "mode": mode, "note": "publishing always needs a human; use the publisher after approval", "results": []}

    results, waiting = [], []
    for n in nodes:
        # anything downstream of an unmade pick, however far, waits
        if _behind_pick(wf, n["id"]):
            waiting.append(n["id"])
            continue
        r = run_node(client, wf, n, mode, backend, cat, comfy_factory)
        row = {"node": n["id"], "kind": n["kind"], **{k: r.get(k) for k in ("status", "note", "files", "cost_estimate", "run_id")}}
        if wa.is_each(n):
            row["each"] = True
            row["items"] = len(r.get("items") or [])
            row["item_count"] = r.get("item_count", 0)
            row["failed"] = r.get("failed", [])
            row["groups"] = r.get("groups", [])
        results.append(row)
        if r.get("status") in ("error", "timeout") and mode != "dry-run":
            break
    if gate.get("con") is not None:
        spent = sum((r.get("cost_estimate") or {}).get("usd", 0) for r in results if r.get("status") in ("completed", "partial"))
        gate["control"].finish(gate["con"], gate["task"], all(r["status"] in ("completed", "provided", "dry-run", "picked") for r in results),
                               actual_usd=round(spent, 4), result={"results": results})
    wf["run_mode"] = mode
    if save:
        wa.save(wf)
    return {"ok": all(r["status"] not in ("error", "timeout", "blocked", "partial") for r in results), "stage": stage, "mode": mode,
            "cost_estimate": _total_estimate(results), "results": results, "waiting_on_pick": waiting,
            "pending_picks": [n["id"] for n in wf["nodes"] if _unpicked(wf, n["id"])]}


def _behind_pick(wf: dict[str, Any], node_id: str) -> bool:
    """True when any step upstream of this one, at any distance, is a pick nobody has made."""
    seen, todo = set(), [node_id]
    while todo:
        cur = todo.pop()
        for e in wf["edges"]:
            if e["target"] == cur and e["source"] not in seen:
                seen.add(e["source"])
                if _unpicked(wf, e["source"]):
                    return True
                todo.append(e["source"])
    return False


def _unpicked(wf: dict[str, Any], node_id: str) -> bool:
    n = next((x for x in wf["nodes"] if x["id"] == node_id), None)
    return bool(n and n["kind"] in ("pick", "pick-video") and not n["data"].get("picked"))
