"""Run a stage of an engine workflow, one node at a time, under its run mode.

Modes:
  dry-run          nothing is submitted; every node gets a manifest that says so.
  stage-approval   each stage is a control-plane task a human must approve first.
  auto             one `engine_run` approval covers every stage; the runner stops at a pick
                   nobody has made and before anything that publishes.

Queued is not success: a node is `completed` only when ComfyUI's history shows outputs and
those files were fetched. Results live in brands/<client>/runs/<workflow>/<node>/<run>/.
"""
from __future__ import annotations

import hashlib
import json
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


def next_stage(wf: dict[str, Any], cat: dict[str, Any]) -> str | None:
    """The first stage with a node that has not completed and is not waiting on a person."""
    for s in sorted(wf.get("stages", []), key=lambda s: s["order"]):
        for n in wf["nodes"]:
            if n["data"].get("stage") != s["id"]:
                continue
            spec = cat["by_kind"].get(n["kind"], {})
            if spec.get("backend", {}).get("kind") in ("input", "brand", "human"):
                continue
            if not any(r.get("status") == "completed" for r in n["data"].get("results", [])):
                return s["id"]
    return None


def upstream_files(wf: dict[str, Any], node: dict[str, Any]) -> dict[str, list[str]]:
    """Files each input port receives: a pick passes only what was picked."""
    by_id = {n["id"]: n for n in wf["nodes"]}
    out: dict[str, list[str]] = {}
    for e in wf["edges"]:
        if e["target"] != node["id"]:
            continue
        src = by_id[e["source"]]
        files: list[str] = []
        if src["kind"] in ("pick", "pick-video"):
            for ref in src["data"].get("picked") or []:
                sid, run_id, idx = (ref.split("#") + ["", ""])[:3]
                s = by_id.get(sid)
                if s:
                    for r in s["data"].get("results", []):
                        if r.get("run_id") == run_id and idx.isdigit() and int(idx) < len(r.get("files", [])):
                            files.append(r["files"][int(idx)])
        else:
            for r in src["data"].get("results", []):
                if r.get("status") in ("completed", "provided"):
                    files += r.get("files", [])
        out.setdefault(e["targetHandle"], []).extend(files)
    return out


def _provided(node: dict[str, Any]) -> dict[str, Any]:
    folder = node["data"].get("params", {}).get("folder") or node["data"].get("params", {}).get("file") or ""
    files: list[str] = []
    p = BRANDS.parent / folder if folder else None
    if p and p.is_dir():
        files = sorted(str(f.relative_to(BRANDS.parent)).replace("\\", "/") for f in p.rglob("*") if f.suffix.lower() in MEDIA_EXT)
    elif p and p.is_file():
        files = [folder]
    return {"run_id": "provided", "status": "provided" if files else "missing", "files": files, "finished": _now(),
            "note": "" if files else f"nothing at {folder or '(no folder set)'}"}


def _manifest(client: str, wf: dict[str, Any], node: dict[str, Any], run_id: str, payload: dict[str, Any]) -> Path:
    d = run_dir(client, wf["id"], node["id"], run_id)
    d.mkdir(parents=True, exist_ok=True)
    m = {"run_id": run_id, "workflow": wf["id"], "node": node["id"], "kind": node["kind"], **payload}
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


def run_node(client: str, wf: dict[str, Any], node: dict[str, Any], mode: str, backend: str,
             cat: dict[str, Any], comfy_factory: Callable[..., Any] | None = None) -> dict[str, Any]:
    spec = cat["by_kind"].get(node["kind"])
    if not spec:
        return {"status": "gap", "note": "unmapped step"}
    be = spec["backend"]
    run_id = f"r-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{node['id'][-12:].replace('.', '-')}"
    d = node["data"]
    variants = int(d.get("variant_count") or 1)
    seconds = d.get("params", {}).get("seconds")
    est = cost.estimate(node["kind"], variants, seconds)

    if be["kind"] in ("input", "brand"):
        res = _provided(node)
        _record(node, res)
        return res
    if be["kind"] == "human":
        return {"status": "waiting" if not d.get("picked") else "picked", "run_id": None}
    if be["kind"] == "gap":
        res = {"run_id": run_id, "status": "gap", "note": be.get("reason"), "finished": _now()}
        _record(node, res)
        return res
    if be["kind"] in ("python", "publish"):
        res = {"run_id": run_id, "status": "dry-run" if mode == "dry-run" else "skipped",
               "note": f"{be['kind']} step {be.get('module')} is not run by the engine yet; run it from the studio CLI",
               "cost_estimate": est, "finished": _now()}
        _manifest(client, wf, node, run_id, res)
        _record(node, res)
        return res

    # ComfyUI
    pm = ports.load_port_map(be["workflow"])
    ups = upstream_files(wf, node)
    bindings: dict[str, Any] = {}
    feeders = {e["targetHandle"]: e["source"] for e in wf["edges"] if e["target"] == node["id"]}
    for port in spec["inputs"]:
        files = ups.get(port["id"], [])
        if files:
            bindings[port["id"]] = files[0] if len(files) == 1 or port["type"] != "image" else files
        elif not port.get("optional"):
            if mode == "dry-run" and port["id"] in feeders:
                # nothing has run yet; a dry run records where the input would come from
                bindings[port["id"]] = f"<{feeders[port['id']]}>"
                continue
            res = {"run_id": run_id, "status": "blocked", "note": f"input {port['id']} has nothing to feed it yet"
                   + (f"; run the stage that makes {feeders[port['id']]} first" if port["id"] in feeders else ""),
                   "cost_estimate": est, "finished": _now()}
            _manifest(client, wf, node, run_id, res)
            _record(node, res)
            return res
    if d.get("prompt"):
        bindings["prompt"] = d["prompt"]
    if d.get("negative"):
        bindings["negative"] = d["negative"]
    base_seed = int(d.get("seed") or (int(hashlib.sha256(node["id"].encode()).hexdigest(), 16) % 10_000_000))
    payload = {"backend": backend, "workflow": be["workflow"], "bindings": bindings, "seeds": [base_seed + i for i in range(variants)],
               "cost_estimate": est, "started": _now()}
    if mode == "dry-run":
        res = {"run_id": run_id, "status": "dry-run", "files": [], **payload, "finished": _now()}
        _manifest(client, wf, node, run_id, res)
        _record(node, res)
        return res

    graph = json.loads((REPO / "workflows" / be["workflow"]).read_text(encoding="utf-8"))
    factory = comfy_factory or _default_factory
    comfy = factory(backend)
    files, shas, log, prompt_ids, status, detail = [], [], [], [], "completed", ""
    t0 = time.time()
    for seed in payload["seeds"]:
        g, changes = ports.bind(json.loads(json.dumps(graph)), pm, {**bindings, "seed": seed, "count": 1})
        log += changes
        sub = comfy.submit(g, workflow_name=Path(be["workflow"]).stem, dry_run=False)
        pid = sub.get("prompt_id") or (sub.get("output") or {}).get("prompt_id")
        if not pid:
            status, detail = "error", f"no prompt_id in {json.dumps(sub)[:200]}"
            break
        prompt_ids.append(pid)
        done = comfy.wait(pid)
        if done.get("status") != "COMPLETED":
            status, detail = done.get("status", "error").lower(), json.dumps(done.get("detail", ""))[:300]
            break
        dest = run_dir(client, wf["id"], node["id"], run_id)
        for o in done.get("outputs", []):
            rel, sha = _fetch(comfy, o, dest)
            files.append(rel)
            shas.append(sha)
    res = {"run_id": run_id, "status": status, "detail": detail, "files": files, "sha256": shas, "prompt_ids": prompt_ids,
           "log": log[:40], "gpu_seconds_actual": round(time.time() - t0, 1), **payload, "finished": _now()}
    _manifest(client, wf, node, run_id, res)
    _record(node, res)
    return res


def _default_factory(backend: str) -> Any:
    from client import ComfyClient
    return ComfyClient(backend=backend)


def _gate(client: str, wf: dict[str, Any], stage: str, mode: str, nodes: list[dict[str, Any]],
          approve_as: str | None, db: Path | None) -> dict[str, Any]:
    """Control-plane gate for anything that spends. Returns {"ok": bool, "task": id, "why": str}."""
    import control
    con = control.connect(db) if db else control.connect()
    name = cost.worker_name()
    try:
        control.worker(con, name)
    except control.ControlError:
        control.add_worker(con, name, "local", "director engine", cost.budget_usd(), actor="system")
    est = cost.estimate_nodes(nodes)
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
    tid = control.propose(con, control.Task(client, kind, f"{wf['title']}: stage {stage}",
                                            {"workflow": wf["id"], "stage": stage, "estimate": est},
                                            assigned_to=name, estimate_usd=est["usd"], created_by="engine"))
    if kind == "engine_stage":
        if not approve_as:
            return {"ok": False, "task": tid, "why": f"stage {stage} waits for a human to approve task {tid} (est ${est['usd']})"}
        control.approve(con, tid, approve_as)
    try:
        control.start(con, tid)
    except control.ControlError as e:
        return {"ok": False, "task": tid, "why": str(e)}
    return {"ok": True, "task": tid, "con": con, "control": control}


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
            return {"ok": True, "stage": None, "mode": mode, "note": "every stage has completed", "results": []}
    nodes = [n for n in _order(wf["nodes"], wf["edges"]) if n["data"].get("stage") == stage]
    if not nodes:
        raise RunError(f"no stage {stage!r} in {workflow_id}")

    spends = [n for n in nodes if cat["by_kind"].get(n["kind"], {}).get("backend", {}).get("kind") == "comfy"]
    publishes = [n for n in nodes if n["kind"] in PUBLISH_KINDS]
    gate: dict[str, Any] = {"ok": True}
    if mode != "dry-run" and spends:
        gate = _gate(client, wf, stage, mode, spends, approve_as, db)
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
        results.append({"node": n["id"], "kind": n["kind"], **{k: r.get(k) for k in ("status", "note", "files", "cost_estimate", "run_id")}})
        if r.get("status") in ("error", "timeout") and mode != "dry-run":
            break
    if gate.get("con") is not None:
        spent = sum((r.get("cost_estimate") or {}).get("usd", 0) for r in results if r.get("status") == "completed")
        gate["control"].finish(gate["con"], gate["task"], all(r["status"] in ("completed", "provided", "dry-run", "picked") for r in results),
                               actual_usd=round(spent, 4), result={"results": results})
    wf["run_mode"] = mode
    if save:
        wa.save(wf)
    return {"ok": all(r["status"] not in ("error", "timeout", "blocked") for r in results), "stage": stage, "mode": mode,
            "results": results, "waiting_on_pick": waiting, "pending_picks": [n["id"] for n in wf["nodes"] if _unpicked(wf, n["id"])]}


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
