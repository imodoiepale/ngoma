"""ComfyUI execution client — one interface, four backends.

    local       127.0.0.1:8188                    dev, free, iterate
    pod         RunPod pod running ComfyUI        interactive, big models
    serverless   RunPod endpoint ugtmfoidpnh8pd   scheduled, scale-to-zero
    hosted      (not here — see packages/image-router)

The load-bearing part is not the HTTP: it is `validate()`. Submitting a graph whose node
packs or model files are missing on the target wastes a cold start and, on a pod, real
money. The graph built in Phase 3 already knows every dependency of every workflow, so
the check is cheap and happens before anything is spent.

Parameter injection targets `CR Prompt List` (Comfyroll) — the batch driver used by every
Icekiub dataset and carousel workflow, and therefore the natural programmatic seam.

Two rules inherited from the existing codebase and kept explicit:
  * queued is not success — only a COMPLETED history with outputs counts
  * dry-run by default; the allowlist is the template set, not arbitrary graphs
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

REPO = Path(__file__).resolve().parents[2]
GRAPH_JSON = REPO / "graph" / "graph.json"
MANIFEST = REPO / "workflows" / "manifest.json"

Backend = Literal["local", "pod", "serverless"]

DEFAULTS = {
    "local": "http://127.0.0.1:8188",
    "serverless_endpoint": "ugtmfoidpnh8pd",   # from infra/runpod/runpod-endpoint.json
}


def _secret(name: str) -> str | None:
    """Environment first, then the encrypted store. See packages/common/vault.py."""
    common = next(str(p / "packages" / "common") for p in Path(__file__).resolve().parents
                  if (p / "packages" / "common" / "vault.py").exists())
    if common not in sys.path:
        sys.path.insert(0, common)
    import vault
    return vault.get(name)


class ComfyError(RuntimeError):
    pass


class ValidationError(ComfyError):
    pass


# ---------------------------------------------------------------- validation

@dataclass
class Requirements:
    workflow: str
    node_packs: list[str] = field(default_factory=list)
    model_files: list[str] = field(default_factory=list)
    node_types: list[str] = field(default_factory=list)


def requirements(workflow_path: str) -> Requirements:
    """Read a workflow's dependencies out of the Phase 3 graph."""
    if not GRAPH_JSON.exists():
        raise ValidationError("graph/graph.json missing — run packages/library/graph_build.py")
    g = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in g["nodes"]}
    key = workflow_path.replace("\\", "/")
    wid = next((i for i in nodes
                if nodes[i]["kind"] == "workflow" and i.removeprefix("workflow:").endswith(key)), None)
    if wid is None:
        wid = next((i for i in nodes
                    if nodes[i]["kind"] == "workflow" and key.lower() in i.lower()), None)
    if wid is None:
        raise ValidationError(f"no workflow in the graph matching {workflow_path!r}")

    req = Requirements(workflow=wid.removeprefix("workflow:"))
    for e in g["edges"]:
        if e["src"] != wid:
            continue
        dst = nodes[e["dst"]]
        if e["rel"] == "requires" and dst["kind"] == "node_pack":
            req.node_packs.append(dst["label"])
        elif e["rel"] == "requires" and dst["kind"] == "model_file":
            req.model_files.append(dst["label"])
        elif e["rel"] == "uses":
            req.node_types.append(dst["label"])
    for lst in (req.node_packs, req.model_files, req.node_types):
        lst.sort()
    return req


@dataclass
class Validation:
    """Three-state, deliberately. `ok` alone would let an unreachable backend read as a
    pass — the same failure shape as treating a queued job as a completed one."""
    ok: bool
    workflow: str
    backend: str
    missing_node_types: list[str] = field(default_factory=list)
    missing_models: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def state(self) -> str:
        if self.unverified:
            return "UNVERIFIED"
        return "OK" if self.ok else "BLOCKED"

    def explain(self) -> str:
        L = [f"{self.state:<10} {self.workflow} on {self.backend}"]
        for t, items in (("node types not installed", self.missing_node_types),
                         ("model files not present", self.missing_models)):
            if items:
                L.append(f"  {t} ({len(items)}):")
                L += [f"    - {i}" for i in items[:12]]
                if len(items) > 12:
                    L.append(f"    ... and {len(items)-12} more")
        for n in self.unverified:
            L.append(f"  UNVERIFIED  {n}")
        for n in self.notes:
            L.append(f"  note: {n}")
        return "\n".join(L)


def _count_nodes(graph: dict[str, Any]) -> int:
    """A UI-format export has a `nodes` list; an API-format graph is keyed by node id.
    Counting top-level keys of the former counts `nodes`/`links`/`groups`, not nodes."""
    if isinstance(graph.get("nodes"), list):
        n = len(graph["nodes"])
        for sg in (graph.get("definitions", {}) or {}).get("subgraphs", []) or []:
            n += len(sg.get("nodes", []))
        return n
    return sum(1 for v in graph.values() if isinstance(v, dict) and "class_type" in v)


class ComfyClient:
    def __init__(self, backend: Backend = "local", base_url: str | None = None,
                 endpoint_id: str | None = None, api_key: str | None = None,
                 timeout: int = 30):
        self.backend = backend
        self.timeout = timeout
        self.endpoint_id = endpoint_id or os.environ.get(
            "RUNPOD_ENDPOINT_ID", DEFAULTS["serverless_endpoint"])
        self.api_key = api_key or _secret("RUNPOD_API_KEY")
        if backend == "local":
            self.base_url = base_url or os.environ.get("COMFY_URL", DEFAULTS["local"])
        elif backend == "pod":
            self.base_url = base_url or os.environ.get("COMFY_POD_URL", "")
            if not self.base_url:
                raise ComfyError("pod backend needs --url or COMFY_POD_URL "
                                 "(e.g. https://<podid>-8188.proxy.runpod.net)")
        else:
            self.base_url = f"https://api.runpod.ai/v2/{self.endpoint_id}"

    # ---- transport -------------------------------------------------------
    def _get(self, path: str) -> Any:
        headers = {"User-Agent": "epalle-studio/1.0"}
        if self.backend == "serverless" and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        r = urllib.request.Request(f"{self.base_url}{path}", headers=headers)
        with urllib.request.urlopen(r, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, body: dict[str, Any], timeout: int | None = None) -> Any:
        headers = {"Content-Type": "application/json", "User-Agent": "epalle-studio/1.0"}
        if self.backend == "serverless":
            if not self.api_key:
                raise ComfyError("RUNPOD_API_KEY is not set; refusing to call the endpoint")
            headers["Authorization"] = f"Bearer {self.api_key}"
        r = urllib.request.Request(f"{self.base_url}{path}",
                                   data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(r, timeout=timeout or self.timeout) as resp:
            return json.loads(resp.read())

    # ---- capability probe -------------------------------------------------
    def object_info(self) -> dict[str, Any] | None:
        """Installed node types, keyed by class_type. None when unreachable."""
        if self.backend == "serverless":
            return None          # the worker is asleep; nothing to probe
        try:
            return self._get("/object_info")
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def reachable(self) -> bool:
        if self.backend == "serverless":
            return bool(self.api_key)
        try:
            self._get("/system_stats")
            return True
        except Exception:  # noqa: BLE001 - any transport failure means unreachable
            return False

    # ---- validation -------------------------------------------------------
    def validate(self, workflow_path: str) -> Validation:
        req = requirements(workflow_path)
        v = Validation(ok=True, workflow=req.workflow, backend=self.backend)

        info = self.object_info()
        if info is None:
            v.unverified.append(
                "backend not reachable, so installed nodes and models could not be checked. "
                f"This workflow needs {len(req.node_packs)} packs and "
                f"{len(req.model_files)} model files — see `graph_query.py deps`.")
            v.notes.append(f"packs: {', '.join(req.node_packs)}")
            v.ok = False          # unknown is not OK
            return v

        installed = set(info)
        v.missing_node_types = [t for t in req.node_types
                                if t not in installed and not t.startswith(("Note", "MarkdownNote"))]

        # model filenames live in each loader's enum options
        available: set[str] = set()
        for spec in info.values():
            for group in ("required", "optional"):
                for opts in (spec.get("input", {}).get(group) or {}).values():
                    if isinstance(opts, list) and opts and isinstance(opts[0], list):
                        available.update(x for x in opts[0] if isinstance(x, str))
        v.missing_models = [m for m in req.model_files if m not in available]

        v.ok = not v.missing_node_types and not v.missing_models
        return v

    # ---- injection --------------------------------------------------------
    @staticmethod
    def inject(graph: dict[str, Any], prompts: list[str] | None = None,
               seed: int | None = None, images: dict[str, str] | None = None,
               loras: dict[str, str] | None = None) -> tuple[dict[str, Any], list[str]]:
        """Rewrite the parameters this studio drives. Returns (graph, change log)."""
        changes: list[str] = []
        api_form = all(isinstance(v, dict) and "class_type" in v for v in graph.values())
        items = graph.items() if api_form else (
            (str(n.get("id")), n) for n in graph.get("nodes", []))

        for nid, node in items:
            ctype = node.get("class_type") or node.get("type") or ""
            if api_form:
                inputs = node.setdefault("inputs", {})
                if prompts and ctype == "CR Prompt List":
                    inputs["prompt_list"] = "\n".join(prompts)
                    changes.append(f"{nid} CR Prompt List <- {len(prompts)} prompts")
                if seed is not None and "seed" in inputs:
                    inputs["seed"] = seed
                    changes.append(f"{nid} {ctype}.seed <- {seed}")
                if images and ctype == "LoadImage" and nid in images:
                    inputs["image"] = images[nid]
                    changes.append(f"{nid} LoadImage <- {images[nid]}")
                if loras and "lora_name" in inputs and ctype in loras:
                    inputs["lora_name"] = loras[ctype]
                    changes.append(f"{nid} {ctype}.lora_name <- {loras[ctype]}")
            else:
                wv = node.get("widgets_values")
                if prompts and ctype == "CR Prompt List" and isinstance(wv, list) and wv:
                    wv[0] = "\n".join(prompts)
                    changes.append(f"{nid} CR Prompt List <- {len(prompts)} prompts")
        if prompts and not any("CR Prompt List" in c for c in changes):
            changes.append("WARNING: no `CR Prompt List` node found — prompts were NOT injected")
        return graph, changes

    # ---- execution --------------------------------------------------------
    def submit(self, graph: dict[str, Any], workflow_name: str | None = None,
               dry_run: bool = True) -> dict[str, Any]:
        if dry_run:
            return {"status": "DRY_RUN", "backend": self.backend,
                    "node_count": _count_nodes(graph),
                    "would_submit_to": self.base_url}
        if self.backend == "serverless":
            # infra/runpod/handler.py takes a template NAME, not a graph: only
            # already-installed templates may run. Honour that contract.
            if not workflow_name:
                raise ComfyError("the serverless handler is allowlist-only and needs "
                                 "workflow_name, not a raw graph")
            return self._post("/runsync", {"input": {"workflow_name": workflow_name,
                                                     "dry_run": False}}, timeout=900)
        cid = str(uuid.uuid4())
        return self._post("/prompt", {"prompt": graph, "client_id": cid})

    def upload(self, path: Any, subfolder: str = "studio", overwrite: bool = True) -> str:
        """Put a local file in ComfyUI's input folder. Returns the name a loader widget expects
        (`studio/name.png`). ComfyUI's /upload/image accepts any file type, video included."""
        from pathlib import Path as _P
        if self.backend == "serverless":
            raise ComfyError("the serverless worker has no input folder; run engine stages on the pod")
        p = _P(path)
        boundary = uuid.uuid4().hex
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{p.name}"\r\n'
                f'Content-Type: application/octet-stream\r\n\r\n').encode()
        tail = (f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="subfolder"\r\n\r\n{subfolder}\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\n{"true" if overwrite else "false"}\r\n'
                f'--{boundary}--\r\n').encode()
        req = urllib.request.Request(f"{self.base_url}/upload/image", data=head + p.read_bytes() + tail,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                              "User-Agent": "epalle-studio/1.0"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            d = json.loads(resp.read())
        name, sub = d.get("name") or p.name, d.get("subfolder") or ""
        return f"{sub}/{name}" if sub else name

    def wait(self, prompt_id: str, poll_s: float = 2.0, max_s: int = 3600) -> dict[str, Any]:
        """Poll until the graph genuinely completes. Queued is not success."""
        t0 = time.time()
        while time.time() - t0 < max_s:
            try:
                hist = self._get(f"/history/{prompt_id}")
            except Exception:  # noqa: BLE001 - transient during a long run
                time.sleep(poll_s)
                continue
            entry = hist.get(prompt_id)
            if entry:
                status = (entry.get("status") or {})
                if status.get("status_str") == "error" or status.get("completed") is False:
                    return {"status": "ERROR", "detail": status, "elapsed_s": round(time.time()-t0, 1)}
                outputs = entry.get("outputs") or {}
                if outputs:
                    files = [f for o in outputs.values()
                             for k in ("images", "gifs", "videos", "audio")
                             for f in (o.get(k) or [])]
                    return {"status": "COMPLETED", "outputs": files,
                            "elapsed_s": round(time.time() - t0, 1)}
            time.sleep(poll_s)
        return {"status": "TIMEOUT", "elapsed_s": round(time.time() - t0, 1)}


def smoke(live: bool, max_s: int = 1200) -> int:
    """Prove the serverless endpoint completes a generation, not merely accepts one.

    Runs the allowlisted `smoke-test` template (infra/runpod/smoke-test.json: an empty
    256x256 image saved to disk). It must already be installed on the volume at
    $EPALLE_ROOT/workflow-api/smoke-test.json, or the handler refuses it.
    Passes only when the job reports COMPLETED *and* returns at least one file.
    """
    c = ComfyClient("serverless")
    body = {"input": {"workflow_name": "smoke-test", "dry_run": False}}
    if not live:
        print(f"dry run: would POST {c.base_url}/runsync {json.dumps(body)}")
        print("pass --live to spend one cold start and prove the endpoint")
        return 0
    res = c.submit({}, "smoke-test", dry_run=False)
    t0 = time.time()
    while res.get("status") in ("IN_QUEUE", "IN_PROGRESS") and res.get("id"):
        if time.time() - t0 > max_s:
            break
        time.sleep(5)
        res = c._get(f"/status/{res['id']}")
    status = res.get("status")
    output = res.get("output") if isinstance(res.get("output"), dict) else {}
    files = output.get("files") or []
    print(json.dumps({"status": status, "id": res.get("id"),
                      "error": output.get("error"), "files": files}, indent=2)[:1500])
    if status == "COMPLETED" and files and not output.get("error"):
        print(f"PASS: serverless completed and returned {len(files)} file(s)")
        return 0
    print(f"FAIL: status={status}, files={len(files)}. Queued is not success.")
    return 1


def _cli() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Validate and run ComfyUI workflows.")
    ap.add_argument("command", choices=["deps", "validate", "probe", "run", "smoke"])
    ap.add_argument("workflow", nargs="?", default="")
    ap.add_argument("--backend", choices=["local", "pod", "serverless"], default="local")
    ap.add_argument("--url")
    ap.add_argument("--prompt", action="append", default=[])
    ap.add_argument("--seed", type=int)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--all", action="store_true", help="validate every workflow")
    a = ap.parse_args()

    if a.command == "probe":
        c = ComfyClient(a.backend, a.url)
        up = c.reachable()
        print(f"{a.backend} @ {c.base_url}: {'reachable' if up else 'NOT reachable'}")
        if up and a.backend != "serverless":
            info = c.object_info() or {}
            print(f"  {len(info)} node types installed")
        raise SystemExit(0 if up else 1)

    if a.command == "deps":
        r = requirements(a.workflow)
        print(f"{r.workflow}\n  packs ({len(r.node_packs)}): {', '.join(r.node_packs)}")
        print(f"  models ({len(r.model_files)}):")
        for m in r.model_files:
            print(f"    - {m}")
        raise SystemExit(0)

    if a.command == "smoke":
        if a.backend != "serverless":
            raise SystemExit("smoke proves the serverless endpoint; pass --backend serverless")
        raise SystemExit(smoke(a.live))

    c = ComfyClient(a.backend, a.url)

    if a.command == "validate":
        if a.all:
            man = json.loads(MANIFEST.read_text(encoding="utf-8"))
            bad = 0
            for wf in man["workflows"]:
                v = c.validate(wf["canonical"])
                print(f"{v.state:<10} {Path(wf['canonical']).name}")
                bad += 1 if v.state == "BLOCKED" else 0
            print(f"\n{bad} workflow(s) cannot run on {a.backend} as configured")
            raise SystemExit(1 if bad else 0)
        v = c.validate(a.workflow)
        print(v.explain())
        raise SystemExit(0 if v.state != "BLOCKED" else 1)

    # run
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = next((w for w in man["workflows"]
                  if a.workflow.replace("\\", "/") in w["canonical"]), None)
    if not entry:
        raise SystemExit(f"no workflow matching {a.workflow!r} in workflows/manifest.json")
    v = c.validate(entry["canonical"])
    print(v.explain())
    if v.state == "BLOCKED":
        raise SystemExit("refusing to submit a graph the backend cannot run")
    if v.state == "UNVERIFIED" and a.live:
        raise SystemExit("refusing to spend a live run against an unverified backend; "
                         "probe it first, or re-run without --live")

    graph = json.loads((REPO / entry["canonical"]).read_text(encoding="utf-8"))
    graph, changes = ComfyClient.inject(graph, a.prompt or None, a.seed)
    for ch in changes:
        print(f"  inject: {ch}")
    res = c.submit(graph, Path(entry["canonical"]).stem, dry_run=not a.live)
    print(json.dumps(res, indent=2)[:1200])
    if res.get("status") == "DRY_RUN":
        print("\n(dry run — pass --live to actually submit)")


if __name__ == "__main__":
    _cli()
