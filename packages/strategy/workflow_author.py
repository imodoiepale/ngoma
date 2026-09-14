"""Workflow author: turn ideas and briefs into studio canvas workflows, and combine workflows.

    uv run --with pyyaml packages/strategy/workflow_author.py --all-ideas            # one template per idea
    uv run --with pyyaml packages/strategy/workflow_author.py --idea V02 --client ongea-pesa
    uv run --with pyyaml packages/strategy/workflow_author.py --brief "Sheng WhatsApp ad" --client ongea-pesa
    uv run --with pyyaml packages/strategy/workflow_author.py --combine M01 M04 --client epalle
    uv run --with pyyaml packages/strategy/workflow_author.py --seed                 # starter workflows per client
    uv run --with pyyaml packages/strategy/workflow_author.py --check                # validate every saved workflow
    uv run --with pyyaml packages/strategy/workflow_author.py --list

A workflow is a small graph (`*.studio.json`) of nodes from the shared catalogue
`packages/studio-ui/catalog/nodes.json`, and the canvas edits the same file.
- Client workflows live in `brands/<client>/workflows/`.
- Idea templates live in `brands/_templates/workflows/`.

Every node names what really runs it. A step with no working backend becomes a declared
gap. It is never dropped silently and never shown as runnable.

`--combine` marries workflows. Shared inputs such as the brand kit merge into one node.
Each workflow's finished media then feeds the next workflow in place of the placeholder
input it would otherwise need. A music video can flow straight into a rollout kit.

Authoring only plans. Nothing here calls a model, spends money or publishes.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "packages" / "studio-ui" / "catalog" / "nodes.json"
IDEAS = REPO / "brands" / "_business" / "ideas.yaml"
MANIFEST = REPO / "workflows" / "manifest.json"
BRANDS = REPO / "brands"
TEMPLATES = "_templates"

INPUT_FOR_TYPE = {"text": "brief", "image": "reference-images", "video": "video-clip",
                  "audio": "song", "brand": "brand-kit"}
INPUT_KINDS = set(INPUT_FOR_TYPE.values()) | {"product-photo"}
PRODUCER_FOR_TYPE = {"character": "refmod-create"}
# Brief keywords -> steps. Ordered: earlier entries come earlier in the graph.
BRIEF_RULES: list[tuple[str, list[str]]] = [
    (r"\b(dataset|character board)\b", ["dataset-aio"]),
    (r"\b(consistent character|refmod|same (face|person)|persona|influencer|spokes(person|model)|ugc)\b", ["refmod"]),
    (r"\b(product|packshot|sku)\b", ["klein-edit"]),
    (r"\b(carousel|photoset|slides?)\b", ["carousel"]),
    (r"\b(thumbnail|poster|flyer|banner|cover art|post)\b", ["nano-banana-2"]),
    (r"\b(music video|performance|dance|motion|choreograph)\b", ["scail-motion"]),
    (r"\b(song|lip ?sync|sing)\b", ["lipsync"]),
    (r"\b(listing|real estate|property|animate|reel)\b", ["wan-i2v"]),
    (r"\b(ugc|ad|advert|testimonial|spokes(person|model))\b", ["h3-ref2va"]),
    (r"\b(long|full[- ]length|3 ?min|4 ?min)\b", ["h3-infinite"]),
    (r"\b(upscale|4k|sharpen)\b", ["upscale"]),
    (r"\b(restore|old photo|colou?ri[sz]e)\b", ["restore"]),
    (r"\b(hook|variants?|a/b)\b", ["hook-variants"]),
    (r"\b(claim|fintech|loan|m-?pesa|bank|sacco)\b", ["claim-check"]),
    (r"\b(voice ?over|narrat|swahili|kiswahili|sheng|french|dub)\b", ["tts"]),
    (r"\b(captions?|subtitles?)\b", ["captions"]),
    (r"\b(logo|brand(ed)?|compos)\b", ["compositor"]),
    (r"\b(whatsapp|status)\b", ["openwa"]),
    (r"\b(instagram|tiktok|schedule|publish|reels)\b", ["postiz"]),
]
LANGUAGE_RULES = [(r"\bsheng\b", "sheng"), (r"\b(swahili|kiswahili)\b", "sw"), (r"\bfrench\b", "fr")]
MEDIA_STEPS = ("nano-banana-2", "carousel", "klein-edit", "wan-i2v", "h3-ref2va", "h3-infinite",
               "scail-motion", "lipsync", "dataset-aio", "restore")


class AuthorError(ValueError):
    pass


# ---------------------------------------------------------------- catalogue and clients

def load_catalog(path: Path = CATALOG) -> dict[str, Any]:
    cat = json.loads(path.read_text(encoding="utf-8"))
    cat["by_kind"] = {n["kind"]: n for n in cat["nodes"]}
    cat["by_step"] = {s: n for n in cat["nodes"] for s in n.get("steps", [])}
    return cat


def _accepts(port: dict[str, Any], out_type: str, cat: dict[str, Any]) -> bool:
    if port["id"] == "media":
        return out_type in cat["media_ports"]["accepts"]
    return port["type"] == out_type


def _brand_name(folder: Path) -> str:
    doc = yaml.safe_load((folder / "brand.yaml").read_text(encoding="utf-8")) or {}
    for key in ("name", "display_name", "brand_name"):
        if isinstance(doc.get(key), str):
            return doc[key]
    if isinstance(doc.get("brand"), dict) and isinstance(doc["brand"].get("name"), str):
        return doc["brand"]["name"]
    return folder.name.replace("-", " ").title()


def clients() -> list[dict[str, Any]]:
    out = []
    for d in sorted(BRANDS.iterdir()):
        if d.name.startswith("_") or not (d / "brand.yaml").exists():
            continue
        out.append({"id": d.name, "name": _brand_name(d),
                    "workflows": sorted(p.name for p in (d / "workflows").glob("*.studio.json"))})
    return out


# ---------------------------------------------------------------- authoring

def _ideas() -> list[dict[str, Any]]:
    return yaml.safe_load(IDEAS.read_text(encoding="utf-8"))["ideas"]


def _idea(idea_id: str) -> dict[str, Any]:
    for i in _ideas():
        if i["id"] == idea_id:
            return i
    raise AuthorError(f"no idea {idea_id!r} in {IDEAS.relative_to(REPO)}")


def expand_steps(steps: list[str], seen: set[str] | None = None) -> list[str]:
    """Idea references inside a pipeline (M07 = M02 + M03 + M04) expand to their steps."""
    seen = seen if seen is not None else set()
    out: list[str] = []
    for s in steps:
        if re.fullmatch(r"[A-Z]\d{2}", str(s)):
            if s in seen:
                continue
            seen.add(s)
            out += expand_steps(_idea(s)["pipeline"], seen)
        else:
            out.append(str(s))
    return out


def steps_from_brief(brief: str) -> list[str]:
    text = brief.lower()
    steps: list[str] = []
    for pattern, add in BRIEF_RULES:
        if re.search(pattern, text):
            steps += [s for s in add if s not in steps]
    if not any(s in steps for s in MEDIA_STEPS):
        steps.insert(0, "nano-banana-2")
    if "compositor" not in steps and any(s in steps for s in ("nano-banana-2", "carousel", "klein-edit")):
        steps.append("compositor")
    return steps


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "workflow"


RUN_MODES = ("dry-run", "stage-approval", "auto")


def _node_key(node: dict[str, Any]) -> tuple[Any, ...]:
    """What makes two nodes of one kind distinct: the scene, shot, variant and role they serve.

    A brief or an idea never sets these, so those workflows keep one node per kind. The
    director engine sets them, so a workflow can hold twenty angle nodes of one generator."""
    d = node.get("data") or {}
    return (node["kind"], d.get("scene"), d.get("shot"), d.get("variant"), d.get("role"))


def author(steps: list[str], title: str, client: str, source: dict[str, Any],
           language: str | None = None, cat: dict[str, Any] | None = None) -> dict[str, Any]:
    cat = cat or load_catalog()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []

    def add(kind: str) -> dict[str, Any]:
        spec = cat["by_kind"][kind]
        params = {p["key"]: p["default"] for p in spec.get("params", []) if "default" in p}
        if language and any(p["key"] == "language" for p in spec.get("params", [])):
            params["language"] = language
        node = {"id": f"n{len(nodes) + 1}", "kind": kind, "position": {"x": 0, "y": 0},
                "data": {"params": params}}
        nodes.append(node)
        if spec["backend"]["kind"] == "gap":
            gaps.append({"node": node["id"], "step": kind, "reason": spec["backend"]["reason"]})
        return node

    def outputs_of(node: dict[str, Any]) -> list[dict[str, Any]]:
        return [] if node["kind"] == "unmapped" else cat["by_kind"][node["kind"]]["outputs"]

    def connect(target: dict[str, Any]) -> None:
        for port in cat["by_kind"][target["kind"]]["inputs"]:
            src = None
            for cand in reversed(nodes[:nodes.index(target)]):
                out = next((o for o in outputs_of(cand) if _accepts(port, o["type"], cat)), None)
                if out:
                    src = (cand, out)
                    break
            if src is None:
                if port.get("optional"):
                    continue
                want = cat["media_ports"]["accepts"][0] if port["id"] == "media" else port["type"]
                if want in PRODUCER_FOR_TYPE:
                    # a character is made, not uploaded: insert the step that makes one
                    prod = add(PRODUCER_FOR_TYPE[want])
                    nodes.remove(prod)
                    nodes.insert(nodes.index(target), prod)
                    connect(prod)
                    src = (prod, cat["by_kind"][prod["kind"]]["outputs"][0])
                    edges.append({"id": f"e{len(edges) + 1}", "source": src[0]["id"], "sourceHandle": src[1]["id"],
                                  "target": target["id"], "targetHandle": port["id"], "type": src[1]["type"]})
                    continue
                if want not in INPUT_FOR_TYPE:
                    gaps.append({"node": target["id"], "step": target["kind"],
                                 "reason": f"needs a {want} input that no earlier step produces"})
                    continue
                inp = add(INPUT_FOR_TYPE[want])
                nodes.remove(inp)
                nodes.insert(nodes.index(target), inp)
                src = (inp, cat["by_kind"][inp["kind"]]["outputs"][0])
            edges.append({"id": f"e{len(edges) + 1}", "source": src[0]["id"], "sourceHandle": src[1]["id"],
                          "target": target["id"], "targetHandle": port["id"], "type": src[1]["type"]})

    for step in steps:
        spec = cat["by_step"].get(step)
        if spec is None:
            node = {"id": f"n{len(nodes) + 1}", "kind": "unmapped", "position": {"x": 0, "y": 0},
                    "data": {"step": step, "params": {}}}
            nodes.append(node)
            gaps.append({"node": node["id"], "step": step, "reason": f"no catalogue node runs '{step}' yet"})
            continue
        if any(_node_key(n) == (spec["kind"], None, None, None, None) for n in nodes):
            continue
        connect(add(spec["kind"]))

    if not any(cat["by_kind"].get(n["kind"], {}).get("category") == "publish" for n in nodes):
        if any(o["type"] in ("image", "video") for n in nodes for o in outputs_of(n)):
            connect(add("export"))

    layout(nodes, edges)
    return {"version": 1, "id": _slug(title), "title": title, "client": client, "source": source,
            "created": date.today().isoformat(),
            "consent_required": any(cat["by_kind"].get(n["kind"], {}).get("consent") for n in nodes),
            "nodes": nodes, "edges": edges, "gaps": gaps}


def layout(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], y0: int = 80) -> None:
    """Left to right by depth; inputs in column 0."""
    depth = {n["id"]: 0 for n in nodes}
    for _ in range(len(nodes)):
        changed = False
        for e in edges:
            if e["source"] in depth and e["target"] in depth and depth[e["source"]] + 1 > depth[e["target"]]:
                depth[e["target"]] = depth[e["source"]] + 1
                changed = True
        if not changed:
            break
    rows: dict[int, int] = {}
    for n in nodes:
        col = depth[n["id"]]
        rows[col] = rows.get(col, 0) + 1
        n["position"] = {"x": 80 + col * 320, "y": y0 + (rows[col] - 1) * 210}


def _depths(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    depth = {n["id"]: 0 for n in nodes}
    for _ in range(len(nodes)):
        changed = False
        for e in edges:
            if e["source"] in depth and e["target"] in depth and depth[e["source"]] + 1 > depth[e["target"]]:
                depth[e["target"]] = depth[e["source"]] + 1
                changed = True
        if not changed:
            break
    return depth


def layout_lanes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]],
                 stages: list[dict[str, Any]], y0: int = 80) -> None:
    """One horizontal lane per stage, in stage order; inside a lane, left to right by depth.

    Nodes with no stage go in a lane of their own at the bottom. Rows within a lane are
    210 px apart, lanes 260 px apart plus whatever the tallest lane needs."""
    order = {s["id"]: i for i, s in enumerate(sorted(stages, key=lambda s: s.get("order", 0)))}
    depth = _depths(nodes, edges)
    lanes: dict[int, list[dict[str, Any]]] = {}
    for n in nodes:
        lanes.setdefault(order.get((n.get("data") or {}).get("stage"), len(order)), []).append(n)
    y = y0
    for lane in sorted(lanes):
        rows: dict[int, int] = {}
        for n in lanes[lane]:
            col = depth[n["id"]]
            rows[col] = rows.get(col, 0) + 1
            n["position"] = {"x": 80 + col * 320, "y": y + (rows[col] - 1) * 210}
        y += 260 + (max(rows.values()) - 1) * 210


def _cycle(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str] | None:
    out: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        if e["source"] in out and e["target"] in out:
            out[e["source"]].append(e["target"])
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(v: str) -> list[str] | None:
        state[v] = 1
        path.append(v)
        for w in out[v]:
            if state.get(w) == 1:
                return path[path.index(w):] + [w]
            if w not in state:
                found = visit(w)
                if found:
                    return found
        path.pop()
        state[v] = 2
        return None

    for v in out:
        if v not in state:
            found = visit(v)
            if found:
                return found
    return None


# ---------------------------------------------------------------- combining

def combine(workflows: list[dict[str, Any]], title: str, client: str,
            cat: dict[str, Any] | None = None) -> dict[str, Any]:
    """Marry workflows into one graph.

    1. Every node id is prefixed with its part letter, so parts never collide.
    2. Identical shared inputs merge into one node: the brand kit always, and a brief when
       its text matches.
    3. For each later part, its first empty placeholder input (a reference image, clip or
       song with nothing set) is replaced by the previous part's finished media. That makes
       one workflow's result the next workflow's material.
    4. Each part's publish or export ending is kept only on the last part, so the combined
       workflow ends once.
    """
    if len(workflows) < 2:
        raise AuthorError("combining needs at least two workflows")
    cat = cat or load_catalog()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []
    parts = []

    for idx, wf in enumerate(workflows):
        tag = chr(ord("a") + idx)
        idmap = {n["id"]: f"{tag}{n['id']}" for n in wf["nodes"]}
        part_nodes = []
        for n in copy.deepcopy(wf["nodes"]):
            n["id"] = idmap[n["id"]]
            n["data"]["part"] = wf["title"]
            part_nodes.append(n)
        part_edges = []
        for e in copy.deepcopy(wf["edges"]):
            e["id"], e["source"], e["target"] = f"{tag}{e['id']}", idmap[e["source"]], idmap[e["target"]]
            part_edges.append(e)
        gaps += [{**g, "node": idmap.get(g["node"], g["node"])} for g in wf.get("gaps", [])]
        parts.append({"title": wf["title"], "nodes": part_nodes, "edges": part_edges})

    def repoint(old: str, new: str) -> None:
        for e in edges:
            if e["source"] == old:
                e["source"] = new

    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        if not is_last:
            # drop this part's endings so the chain continues into the next part
            enders = {n["id"] for n in part["nodes"]
                      if cat["by_kind"].get(n["kind"], {}).get("category") == "publish"}
            part["nodes"] = [n for n in part["nodes"] if n["id"] not in enders]
            part["edges"] = [e for e in part["edges"] if e["target"] not in enders and e["source"] not in enders]
        nodes_before = list(nodes)
        for n in part["nodes"]:
            if n["kind"] in ("brand-kit",):
                twin = next((m for m in nodes_before if m["kind"] == n["kind"]), None)
                if twin:
                    for e in part["edges"]:
                        if e["source"] == n["id"]:
                            e["source"] = twin["id"]
                    continue
            if n["kind"] == "brief":
                twin = next((m for m in nodes_before if m["kind"] == "brief"
                             and m["data"]["params"].get("text") == n["data"]["params"].get("text")), None)
                if twin:
                    for e in part["edges"]:
                        if e["source"] == n["id"]:
                            e["source"] = twin["id"]
                    continue
            nodes.append(n)
        edges += part["edges"]

        if i > 0:
            prev = parts[i - 1]
            produced = _final_media(prev["nodes"], prev["edges"], cat)
            placeholder = next((n for n in part["nodes"] if n in nodes and n["kind"] in ("reference-images", "video-clip", "product-photo")
                                and not any(v for v in n["data"]["params"].values())), None)
            if produced and placeholder:
                out_type = produced[1]["type"]
                consumers = [e for e in edges if e["source"] == placeholder["id"]]
                fits = []
                for e in consumers:
                    t = next(m for m in nodes if m["id"] == e["target"])
                    port = next(p for p in cat["by_kind"][t["kind"]]["inputs"] if p["id"] == e["targetHandle"])
                    fits.append(_accepts(port, out_type, cat))
                if consumers and all(fits):
                    for e in consumers:
                        e["source"], e["sourceHandle"], e["type"] = produced[0]["id"], produced[1]["id"], out_type
                        e["married"] = True
                    nodes.remove(placeholder)

    # every combined edge id unique
    for k, e in enumerate(edges, 1):
        e["id"] = f"e{k}"
    y = 80
    for part in parts:
        members = [n for n in nodes if n["data"].get("part") == part["title"]]
        layout(members, [e for e in edges if any(m["id"] == e["target"] for m in members)], y0=y)
        y = max((n["position"]["y"] for n in members), default=y) + 280
    live = {n["id"] for n in nodes}
    gaps = [g for g in gaps if g["node"] in live]
    return {"version": 1, "id": _slug(title), "title": title, "client": client,
            "source": {"combined": [p["title"] for p in parts]}, "created": date.today().isoformat(),
            "consent_required": any(cat["by_kind"].get(n["kind"], {}).get("consent") for n in nodes),
            "nodes": nodes, "edges": edges, "gaps": gaps}


def _final_media(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], cat: dict[str, Any]):
    """The last node (by graph order) that outputs image or video, with that output port."""
    for n in reversed(nodes):
        spec = cat["by_kind"].get(n["kind"])
        if not spec or spec["category"] == "inputs":
            continue
        out = next((o for o in spec["outputs"] if o["type"] in ("video", "image")), None)
        if out:
            return n, out
    return None


# ---------------------------------------------------------------- validation and storage

def validate(wf: dict[str, Any], cat: dict[str, Any] | None = None) -> list[str]:
    """Structural problems only. Declared gaps are not problems."""
    cat = cat or load_catalog()
    problems: list[str] = []
    manifest = {w["canonical"].removeprefix("workflows/")
                for w in json.loads(MANIFEST.read_text(encoding="utf-8"))["workflows"]}
    ids = {n["id"]: n for n in wf.get("nodes", [])}
    if len(ids) != len(wf.get("nodes", [])):
        problems.append("duplicate node ids")
    declared_gaps = {g["node"] for g in wf.get("gaps", [])}
    for n in wf.get("nodes", []):
        if n["kind"] == "unmapped":
            if n["id"] not in declared_gaps:
                problems.append(f"{n['id']}: unmapped step not declared as a gap")
            continue
        spec = cat["by_kind"].get(n["kind"])
        if spec is None:
            problems.append(f"{n['id']}: unknown node kind {n['kind']!r}")
            continue
        be = spec["backend"]
        if be["kind"] == "comfy" and be["workflow"] not in manifest:
            problems.append(f"{n['id']}: ComfyUI workflow {be['workflow']} is not in workflows/manifest.json")
        if be["kind"] == "gap" and n["id"] not in declared_gaps:
            problems.append(f"{n['id']}: {n['kind']} has no backend but is not declared as a gap")
        if be["kind"] == "human" and spec.get("category") != "decide":
            problems.append(f"{n['id']}: only a decide step may have a human backend")
        if spec.get("category") == "decide":
            k = (n.get("data") or {}).get("params", {}).get("k")
            feeders = [ids[e["source"]] for e in wf.get("edges", []) if e["target"] == n["id"] and e["source"] in ids]
            offered = sum(int((f.get("data") or {}).get("variant_count") or 1) for f in feeders)
            if feeders and isinstance(k, (int, float)) and k > offered:
                problems.append(f"{n['id']}: asks to keep {int(k)} but only {offered} candidate(s) feed it")
    if wf.get("run_mode") is not None and wf["run_mode"] not in RUN_MODES:
        problems.append(f"run_mode must be one of {', '.join(RUN_MODES)}")
    loop = _cycle(wf.get("nodes", []), wf.get("edges", []))
    if loop:
        problems.append("steps feed back into themselves: " + " -> ".join(loop))
    for e in wf.get("edges", []):
        s, t = ids.get(e["source"]), ids.get(e["target"])
        if not s or not t:
            problems.append(f"{e['id']}: dangling edge")
            continue
        s_spec, t_spec = cat["by_kind"].get(s["kind"]), cat["by_kind"].get(t["kind"])
        if not s_spec or not t_spec:
            continue
        out = next((o for o in s_spec["outputs"] if o["id"] == e["sourceHandle"]), None)
        port = next((p for p in t_spec["inputs"] if p["id"] == e["targetHandle"]), None)
        if not out or not port:
            problems.append(f"{e['id']}: unknown handle")
        elif not _accepts(port, out["type"], cat):
            problems.append(f"{e['id']}: {out['type']} cannot feed {t['kind']}.{port['id']} ({port['type']})")
    return problems


def workflow_dir(client: str) -> Path:
    if client != TEMPLATES and not (BRANDS / client / "brand.yaml").exists():
        raise AuthorError(f"unknown client {client!r}; expected brands/{client}/brand.yaml")
    return BRANDS / client / "workflows"


def save(wf: dict[str, Any]) -> Path:
    problems = validate(wf)
    if problems:
        raise AuthorError("; ".join(problems))
    dest = workflow_dir(wf["client"]) / f"{wf['id']}.studio.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(wf, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def from_idea(idea_id: str, client: str, title: str | None = None) -> dict[str, Any]:
    i = _idea(idea_id)
    wf = author(expand_steps(i["pipeline"]), title or i["name"], client,
                {"idea": idea_id, "offer": i["offer"]})
    if client == TEMPLATES:
        wf["id"] = f"{idea_id.lower()}-{wf['id']}"
    wf["family"] = i["family"]
    wf["compliance"] = i["compliance"]
    return wf


def from_brief(brief: str, client: str, title: str | None = None) -> dict[str, Any]:
    lang = next((code for pat, code in LANGUAGE_RULES if re.search(pat, brief.lower())), None)
    wf = author(steps_from_brief(brief), title or brief[:60], client, {"brief": brief}, language=lang)
    brief_node = next((n for n in wf["nodes"] if n["kind"] == "brief"), None)
    if brief_node:
        brief_node["data"]["params"]["text"] = brief
    return wf


def load_ref(ref: str, client: str) -> dict[str, Any]:
    """An idea id (V02), a saved workflow id for the client, or a path to a .studio.json."""
    if re.fullmatch(r"[A-Z]\d{2}", ref):
        return from_idea(ref, client)
    p = Path(ref)
    if not p.exists():
        p = workflow_dir(client) / f"{ref.removesuffix('.studio.json')}.studio.json"
    if not p.exists():
        raise AuthorError(f"no idea or workflow named {ref!r}")
    return json.loads(p.read_text(encoding="utf-8"))


SEED = {"ongea-pesa": ["V02", "U04", "V06"], "epalle": ["M01", "M03", "M04"]}
SEED_COMBINED = {"epalle": (["M01", "M04"], "Music video to release rollout"),
                 "ongea-pesa": (["U04", "V06"], "Sheng ad to WhatsApp Status")}


def main() -> int:
    ap = argparse.ArgumentParser(description="Author studio workflows from ideas or briefs, and combine them.")
    ap.add_argument("--idea", help="idea id from brands/_business/ideas.yaml, e.g. V02")
    ap.add_argument("--brief", help="plain-language description of what to make")
    ap.add_argument("--combine", nargs="+", metavar="REF", help="idea ids, workflow ids or files to marry, in order")
    ap.add_argument("--client", help="client id (a folder in brands/ with brand.yaml), or _templates")
    ap.add_argument("--title", help="workflow title")
    ap.add_argument("--all-ideas", action="store_true", help="write a template workflow for every idea")
    ap.add_argument("--seed", action="store_true", help="write starter workflows for each client")
    ap.add_argument("--check", action="store_true", help="validate every saved workflow")
    ap.add_argument("--list", action="store_true", help="list clients and their workflows")
    ap.add_argument("--json", action="store_true", help="print the workflow instead of saving it")
    a = ap.parse_args()

    if a.list:
        for c in clients():
            print(f"{c['id']:<14} {c['name']:<20} {len(c['workflows'])} workflow(s)")
        print(f"{TEMPLATES:<14} {'Idea templates':<20} {len(list((BRANDS / TEMPLATES / 'workflows').glob('*.studio.json')))} workflow(s)")
        return 0
    if a.check:
        bad = 0
        for p in sorted(BRANDS.glob("*/workflows/*.studio.json")):
            probs = validate(json.loads(p.read_text(encoding="utf-8")))
            bad += bool(probs)
            if probs:
                print(f"BAD {p.relative_to(REPO)}: {probs}")
        print(f"{len(list(BRANDS.glob('*/workflows/*.studio.json')))} workflows checked, {bad} with problems")
        return 1 if bad else 0
    if a.all_ideas:
        for i in _ideas():
            save(from_idea(i["id"], TEMPLATES))
        print(f"wrote {len(_ideas())} idea templates to brands/{TEMPLATES}/workflows/")
        return 0
    if a.seed:
        for client, idea_ids in SEED.items():
            for iid in idea_ids:
                print(f"wrote {save(from_idea(iid, client)).relative_to(REPO)}")
        for client, (refs, title) in SEED_COMBINED.items():
            print(f"wrote {save(combine([from_idea(r, client) for r in refs], title, client)).relative_to(REPO)}")
        return 0
    if not a.client or not (a.idea or a.brief or a.combine):
        ap.error("give --client and one of --idea, --brief or --combine (or use --all-ideas / --seed / --check / --list)")
    if a.combine:
        parts = [load_ref(r, a.client) for r in a.combine]
        wf = combine(parts, a.title or " + ".join(p["title"] for p in parts), a.client)
    elif a.idea:
        wf = from_idea(a.idea, a.client, a.title)
    else:
        wf = from_brief(a.brief, a.client, a.title)
    if a.json:
        print(json.dumps(wf, indent=2, ensure_ascii=False))
        return 0
    dest = save(wf)
    print(f"wrote {dest.relative_to(REPO)}: {len(wf['nodes'])} nodes, {len(wf['edges'])} links, "
          f"{len(wf['gaps'])} gap(s){', consent required' if wf['consent_required'] else ''}")
    for g in wf["gaps"]:
        print(f"  gap {g['node']} {g['step']}: {g['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
