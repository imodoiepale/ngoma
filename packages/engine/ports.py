"""Port maps: where studio inputs land inside a ComfyUI workflow, and which node saves the output.

A port map is a hand-written JSON file next to its workflow (same stem, `.ports.json`). It names,
for every studio port of the catalogue node that runs the workflow, the ComfyUI node and widget that
holds the value, plus the prompt, negative, seed and batch-count widgets and the save node(s). The
runner uses `bind()` to inject values; `validate_port_maps()` proves every map still matches the
workflow bytes it was written against (docs/engine/PORT-MAPS.md).

Pure module: no network, no GPU, no ComfyUI import.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / "workflows"
MANIFEST = WORKFLOWS / "manifest.json"

ENGINE_KINDS = [
    "krea2-t2i",
    "h3-reference-image",
    "character-sheet",
    "refmod-create",
    "wardrobe",
    "consistent-room",
    "image-edit",
    "image-to-video",
    "motion-control",
    "upscale-video",
    "klein-t2i",
    "carousel",
    "lipsync",
    "character-video",
]

# the single-value slots a map may carry besides the studio `inputs`
SLOTS = ("prompt", "negative", "seed", "count")
# file conversions the runner applies before a value is bound (see runner._prepare_file)
TRANSFORMS = ("audio_to_video",)
REQUIRED_KEYS = ("workflow", "sha256", "format", "inputs", "outputs", "unknown", "notes")


class PortMapError(ValueError):
    pass


# ---------------------------------------------------------------- loading

def port_map_path(workflow_rel: str) -> Path:
    """workflows/<rel>.json -> workflows/<rel>.ports.json (next to the workflow)."""
    rel = workflow_rel.replace("\\", "/")
    if rel.startswith("workflows/"):
        rel = rel[len("workflows/"):]
    if not rel.endswith(".json"):
        raise PortMapError(f"not a workflow json path: {workflow_rel}")
    return WORKFLOWS / (rel[:-5] + ".ports.json")


def _check_ref(name: str, ref: Any, fmt: str) -> None:
    if not isinstance(ref, dict):
        raise PortMapError(f"{name}: must be an object")
    for key in ("node", "class", "field"):
        if not isinstance(ref.get(key), str) or not ref[key]:
            raise PortMapError(f"{name}: missing string '{key}'")
    if fmt == "ui" and "widget_index" in ref and not isinstance(ref["widget_index"], int):
        raise PortMapError(f"{name}: widget_index must be an int")
    for key in ("line", "line_from"):
        if key in ref and (not isinstance(ref[key], int) or ref[key] < 0):
            raise PortMapError(f"{name}: {key} must be a non-negative int")
    if "transform" in ref and ref["transform"] not in TRANSFORMS:
        raise PortMapError(f"{name}: transform must be one of {TRANSFORMS}")
    if "set" in ref and not isinstance(ref["set"], dict):
        raise PortMapError(f"{name}: set must be an object of extra widget values")
    if "enable_nodes" in ref and not (isinstance(ref["enable_nodes"], list) and all(isinstance(x, str) for x in ref["enable_nodes"])):
        raise PortMapError(f"{name}: enable_nodes must be a list of node id strings")


def load_port_map(workflow_rel: str) -> dict[str, Any]:
    """Read and shape-check a port map. Raises PortMapError if missing or malformed."""
    path = port_map_path(workflow_rel)
    if not path.exists():
        raise PortMapError(f"no port map at {path.relative_to(REPO).as_posix()}")
    try:
        pm = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PortMapError(f"{path.name}: invalid json: {e}") from e
    if not isinstance(pm, dict):
        raise PortMapError(f"{path.name}: top level must be an object")
    for key in REQUIRED_KEYS:
        if key not in pm:
            raise PortMapError(f"{path.name}: missing key '{key}'")
    if pm["format"] not in ("ui", "api"):
        raise PortMapError(f"{path.name}: format must be 'ui' or 'api'")
    if not isinstance(pm["inputs"], dict) or not isinstance(pm["outputs"], dict):
        raise PortMapError(f"{path.name}: inputs and outputs must be objects")
    if not isinstance(pm["unknown"], list) or not isinstance(pm["notes"], list):
        raise PortMapError(f"{path.name}: unknown and notes must be lists")
    for port, ref in pm["inputs"].items():
        _check_ref(f"{path.name} inputs.{port}", ref, pm["format"])
    for slot in SLOTS:
        if slot in pm:
            _check_ref(f"{path.name} {slot}", pm[slot], pm["format"])
    if not isinstance(pm.get("params", {}), dict):
        raise PortMapError(f"{path.name}: params must be an object")
    for key, ref in pm.get("params", {}).items():
        _check_ref(f"{path.name} params.{key}", ref, pm["format"])
    for port, ref in pm["outputs"].items():
        if not isinstance(ref, dict) or not isinstance(ref.get("node"), str) or not ref.get("class"):
            raise PortMapError(f"{path.name} outputs.{port}: needs string 'node' and 'class'")
    return pm


# ---------------------------------------------------------------- workflow introspection

def _load_manifest() -> dict[str, dict[str, Any]]:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {w["canonical"]: w for w in m["workflows"]}


def workflow_node_ids(graph: dict[str, Any]) -> set[str]:
    """Every node id in a workflow, as strings. UI format includes subgraph nodes; API format is the keys."""
    if "nodes" in graph and isinstance(graph["nodes"], list):
        ids = {str(n["id"]) for n in graph["nodes"] if isinstance(n, dict) and "id" in n}
        for sg in (graph.get("definitions") or {}).get("subgraphs") or []:
            ids |= {str(n["id"]) for n in sg.get("nodes") or [] if isinstance(n, dict) and "id" in n}
        return ids
    return {str(k) for k, v in graph.items() if isinstance(v, dict) and "class_type" in v}


def _find_node(graph: dict[str, Any], node_id: str) -> tuple[dict[str, Any] | None, str]:
    """(node, format). UI: searches top-level then subgraphs. API: dict lookup."""
    if "nodes" in graph and isinstance(graph["nodes"], list):
        for n in graph["nodes"]:
            if str(n.get("id")) == node_id:
                return n, "ui"
        for sg in (graph.get("definitions") or {}).get("subgraphs") or []:
            for n in sg.get("nodes") or []:
                if str(n.get("id")) == node_id:
                    return n, "ui"
        return None, "ui"
    n = graph.get(node_id)
    return (n if isinstance(n, dict) else None), "api"


def _refs(pm: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    out += [(f"inputs.{k}", v) for k, v in pm["inputs"].items()]
    out += [(slot, pm[slot]) for slot in SLOTS if slot in pm]
    out += [(f"params.{k}", v) for k, v in pm.get("params", {}).items()]
    out += [(f"outputs.{k}", v) for k, v in pm["outputs"].items()]
    return out


# ---------------------------------------------------------------- validation

def validate_port_maps(catalog: dict[str, Any]) -> list[str]:
    """Every engine kind with a comfy backend has a map that matches its workflow. Returns problems."""
    problems: list[str] = []
    by_kind = catalog.get("by_kind") or {n["kind"]: n for n in catalog["nodes"]}
    try:
        manifest = _load_manifest()
    except (OSError, KeyError, json.JSONDecodeError) as e:
        return [f"cannot read {MANIFEST.relative_to(REPO).as_posix()}: {e}"]

    for kind in ENGINE_KINDS:
        spec = by_kind.get(kind)
        if spec is None:
            problems.append(f"{kind}: not in catalogue")
            continue
        backend = spec.get("backend") or {}
        if backend.get("kind") != "comfy" or not backend.get("workflow"):
            problems.append(f"{kind}: catalogue backend is not a comfy workflow")
            continue
        rel = backend["workflow"]
        tag = f"{kind} ({rel})"
        try:
            pm = load_port_map(rel)
        except PortMapError as e:
            problems.append(f"{tag}: {e}")
            continue

        if pm["workflow"] != rel:
            problems.append(f"{tag}: map says workflow '{pm['workflow']}'")
        entry = manifest.get("workflows/" + rel)
        if entry is None:
            problems.append(f"{tag}: workflow not in manifest")
        elif entry.get("sha256") != pm["sha256"]:
            problems.append(f"{tag}: sha256 {pm['sha256'][:12]} does not match manifest {entry.get('sha256', '')[:12]}")

        wf_path = WORKFLOWS / rel
        if not wf_path.exists():
            problems.append(f"{tag}: workflow file missing")
            continue
        graph = json.loads(wf_path.read_text(encoding="utf-8"))
        fmt = "ui" if "nodes" in graph and isinstance(graph["nodes"], list) else "api"
        if fmt != pm["format"]:
            problems.append(f"{tag}: map format '{pm['format']}' but workflow is '{fmt}'")
        ids = workflow_node_ids(graph)
        for name, ref in _refs(pm):
            if ref["node"] not in ids:
                problems.append(f"{tag}: {name} points at node {ref['node']} which does not exist")
                continue
            node, _ = _find_node(graph, ref["node"])
            cls = node.get("type") if fmt == "ui" else node.get("class_type")
            if cls != ref["class"]:
                problems.append(f"{tag}: {name} node {ref['node']} is {cls!r}, map says {ref['class']!r}")
            if fmt == "ui" and "widget_index" in ref and not name.startswith("outputs."):
                wv = node.get("widgets_values")
                if not isinstance(wv, list) or ref["widget_index"] >= len(wv):
                    problems.append(f"{tag}: {name} widget_index {ref['widget_index']} out of range for node {ref['node']}")
            if fmt == "api" and not name.startswith("outputs.") and ref["field"] not in (node.get("inputs") or {}):
                problems.append(f"{tag}: {name} field '{ref['field']}' not in node {ref['node']} inputs")
            for extra in ref.get("enable_nodes", []):
                if extra not in ids:
                    problems.append(f"{tag}: {name} enable_nodes names node {extra} which does not exist")
            if ref.get("set") and fmt == "ui" and not isinstance(node.get("widgets_values"), dict):
                problems.append(f"{tag}: {name} uses `set` but node {ref['node']} widgets are not keyed by name")
        for key in pm.get("params", {}):
            if key not in {p["key"] for p in spec.get("params", [])}:
                problems.append(f"{tag}: params.{key} is not a parameter of this kind")

        unknown_text = " ".join(pm["unknown"])
        for port in spec.get("inputs", []):
            pid = port["id"]
            if pid == "prompt":
                covered = "prompt" in pm or pid in pm["inputs"]
            else:
                covered = pid in pm["inputs"]
            if not covered and not port.get("optional"):
                if not any(u.split(":", 1)[0].strip() == pid for u in pm["unknown"]) and pid not in unknown_text:
                    problems.append(f"{tag}: required studio port '{pid}' is neither in inputs nor in unknown")
        for pid in pm["inputs"]:
            if pid not in {p["id"] for p in spec.get("inputs", [])}:
                problems.append(f"{tag}: inputs.{pid} is not a studio port of this kind")
        if not pm["outputs"]:
            problems.append(f"{tag}: outputs is empty")
    return problems


# ---------------------------------------------------------------- binding

def _set_value(node: dict[str, Any], ref: dict[str, Any], fmt: str, value: Any, name: str, log: list[str]) -> bool:
    if fmt == "api":
        node.setdefault("inputs", {})[ref["field"]] = value
        log.append(f"set {name}: node {ref['node']} ({ref['class']}) inputs.{ref['field']} = {value!r}")
        return True
    wv = node.get("widgets_values")
    if isinstance(wv, dict):
        wv[ref["field"]] = value
        log.append(f"set {name}: node {ref['node']} ({ref['class']}) widgets_values[{ref['field']!r}] = {value!r}")
        return True
    idx = ref.get("widget_index")
    if not isinstance(wv, list) or idx is None or idx >= len(wv):
        log.append(f"skipped {name}: node {ref['node']} has no widget at index {idx}")
        return False
    wv[idx] = value
    log.append(f"set {name}: node {ref['node']} ({ref['class']}) widgets_values[{idx}] ({ref['field']}) = {value!r}")
    return True


def bind(graph: dict[str, Any], pm: dict[str, Any], bindings: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Inject studio values into a workflow copy. Keys: studio port ids plus prompt/negative/seed/count.

    Returns (new graph, change log). Keys the map does not cover are logged as skipped, never dropped
    silently. Pure: the input graph is not mutated.
    """
    g = copy.deepcopy(graph)
    fmt = "ui" if "nodes" in g and isinstance(g["nodes"], list) else "api"
    log: list[str] = []
    # several studio ports can share one multi-line widget (identity on line 0, references after)
    lines: dict[tuple[str, str, Any], dict[str, Any]] = {}
    for key, value in bindings.items():
        if key in SLOTS and key in pm:
            ref = pm[key]
        elif key in pm["inputs"]:
            ref = pm["inputs"][key]
        elif key in pm.get("params", {}):
            ref = pm["params"][key]
            if value in (None, ""):
                log.append(f"skipped {key}: empty parameter keeps the workflow's own value")
                continue
        else:
            why = "listed as unknown in the port map" if any(
                u.split(":", 1)[0].strip() == key for u in pm.get("unknown", [])) else "not in the port map"
            log.append(f"skipped {key}: {why}")
            continue
        node, _ = _find_node(g, ref["node"])
        if node is None:
            log.append(f"skipped {key}: node {ref['node']} not found in workflow")
            continue
        if "line" in ref or "line_from" in ref:
            group = lines.setdefault((ref["node"], ref["field"], ref.get("widget_index")), {"ref": ref, "node": node, "by_line": {}})
            values = value if isinstance(value, list) else [value]
            if "line" in ref:
                group["by_line"][ref["line"]] = str(values[0])
            else:
                for i, v in enumerate(values):
                    group["by_line"][ref["line_from"] + i] = str(v)
            continue
        if _set_value(node, ref, fmt, value, key, log):
            for field, extra in (ref.get("set") or {}).items():
                _set_value(node, {**ref, "field": field, "widget_index": None}, fmt, extra, f"{key}.{field}", log)
            for nid in ref.get("enable_nodes", []):
                other, _ = _find_node(g, nid)
                if other is not None and fmt == "ui":
                    other["mode"] = 0
                    log.append(f"enabled node {nid} for {key}")
    for (nid, _field, _idx), group in lines.items():
        by_line = group["by_line"]
        text = "\n".join(by_line[i] for i in sorted(by_line))
        _set_value(group["node"], group["ref"], fmt, text, f"lines@{nid}", log)
    return g, log
