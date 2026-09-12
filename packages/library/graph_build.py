"""Typed knowledge graph over the ComfyUI corpus.

Generic text graphing (the `graphify` skill) is good at prose. It is *not* good at the
question this studio actually asks: "what is the minimum set of node packs and model
files needed to run carousel pose generation end to end, and where is that claimed?"

That answer lives in structure, not prose — so this builds typed nodes and edges directly
from `workflows/manifest.json`, then attaches the transcript facts mined by
`packages/ingest/yt_learn.py` as *evidence* edges carrying a video id and timestamp.

Node kinds:  workflow · node_type · node_pack · model_file · model · collection ·
             video · channel · technique · creative · style · brand
Edge kinds:  uses · provided_by · requires · belongs_to · mentions · evidence_for

Output: graph/graph.json + graph/GRAPH_REPORT.md, queryable via graph_query.py.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
GRAPH = REPO / "graph"
MANIFEST = REPO / "workflows" / "manifest.json"
YT_FACTS = REPO / "packages" / "library" / "corpus" / "youtube" / "facts.jsonl"
STYLES = REPO / "brands"

# Node types shipped with ComfyUI core carry no cnr_id, so absence of a pack is not
# absence of a dependency — it usually means "core". Recorded explicitly.
CORE_MARKER = "comfy-core"

# A workflow records a pack as either its ComfyUI-Manager registry id (`cnr_id`,
# lowercase) or its GitHub path (`aux_id`, Owner/Repo). Left unnormalised these split one
# pack into two nodes and halve its apparent dependency count, which is exactly the
# number a "what must I install" answer depends on.
def _norm_pack(p: str) -> str:
    if p == CORE_MARKER:
        return p
    tail = p.split("/")[-1].lower()
    tail = tail.removeprefix("comfyui-").removeprefix("comfyui_").removeprefix("comfy-")
    tail = tail.replace("_", "-")
    ALIAS = {
        "kjnodes": "comfyui-kjnodes",
        "videohelpersuite": "comfyui-videohelpersuite",
        "comfyroll-customnodes": "comfyui_comfyroll_customnodes",
        "rgthree-comfy": "rgthree-comfy",
        "rgthree": "rgthree-comfy",
        "impact-pack": "comfyui-impact-pack",
        "impact-subpack": "comfyui-impact-subpack",
        "inspire-pack": "comfyui-inspire-pack",
        "controlnet-aux": "comfyui_controlnet_aux",
        "easy-use": "comfyui-easy-use",
        "frame-interpolation": "comfyui-frame-interpolation",
        "wanvideowrapper": "comfyui-wanvideowrapper",
        "h3-motion-context": "comfyui-h3-motion-context",
        "h3-motion-context-multiref": "comfyui-h3-motion-context",
        "sam3": "comfyui-sam3",
        "essentials": "comfyui_essentials",
        "faceanalysis": "comfyui_faceanalysis",
        "ultimatesdupscale": "comfyui_ultimatesdupscale",
        "multigpu": "comfyui-multigpu",
        "custom-scripts": "comfyui-custom-scripts",
        "starnodes": "comfyui_starnodes",
        "painteri2v": "comfyui-painteri2v",
        "logic": "comfyui-logic",
        "scail-pose": "comfyui-scail-pose",
        "wananimatepreprocess": "comfyui-wananimatepreprocess",
        "ltxvideo": "comfyui-ltxvideo",
    }
    return ALIAS.get(tail, tail if tail.startswith(("comfyui", "rgthree")) else p.split("/")[-1].lower())


@dataclass
class Graph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[dict[str, Any]] = field(default_factory=list)
    _edge_keys: set[tuple[str, str, str]] = field(default_factory=set, repr=False)

    def node(self, nid: str, kind: str, **attrs: Any) -> str:
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "kind": kind, **attrs}
        else:
            for k, v in attrs.items():
                if v is not None and self.nodes[nid].get(k) in (None, "", [], 0):
                    self.nodes[nid][k] = v
        return nid

    def edge(self, src: str, rel: str, dst: str, **attrs: Any) -> None:
        key = (src, rel, dst)
        if key in self._edge_keys:
            # keep evidence stacking, but never duplicate a plain structural edge
            if attrs.get("evidence"):
                for e in self.edges:
                    if (e["src"], e["rel"], e["dst"]) == key:
                        e.setdefault("evidence", []).extend(attrs["evidence"])
                        return
            return
        self._edge_keys.add(key)
        self.edges.append({"src": src, "rel": rel, "dst": dst, **attrs})

    def neighbours(self, nid: str, rels: Iterable[str] | None = None,
                   direction: str = "both") -> list[tuple[str, str]]:
        out = []
        for e in self.edges:
            if rels and e["rel"] not in rels:
                continue
            if direction in ("out", "both") and e["src"] == nid:
                out.append((e["rel"], e["dst"]))
            if direction in ("in", "both") and e["dst"] == nid:
                out.append((e["rel"], e["src"]))
        return out


def _norm_model(name: str) -> str:
    """Canonical key for a model file so 'flux-2-klein-9b-fp8.safetensors' and the
    spoken form 'flux 2 klein' land on the same concept node."""
    s = name.lower()
    s = re.sub(r"\.(safetensors|ckpt|pt|pth|onnx|gguf|bin)$", "", s)
    s = re.sub(r"[_\s]+", "-", s)
    s = re.sub(r"-(fp8|fp16|bf16|int8|e4m3fn|scaled|mixed|kv|hq|pruned|convrot)\b", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def build() -> Graph:
    g = Graph()

    # ---- workflows, node types, packs, model files ------------------------
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for wf in man["workflows"]:
        coll = Path(wf["canonical"]).parent.name
        wid = f"workflow:{wf['canonical']}"
        g.node(wid, "workflow", label=Path(wf["canonical"]).stem,
               collection=coll, node_count=wf["node_count"], sha256=wf["sha256"],
               sources=len(wf["sources"]))
        g.node(f"collection:{coll}", "collection", label=coll)
        g.edge(wid, "belongs_to", f"collection:{coll}")

        packs = sorted({_norm_pack(p) for p in wf["node_packs"]}) or [CORE_MARKER]
        for p in packs:
            g.node(f"node_pack:{p}", "node_pack", label=p)
            g.edge(wid, "requires", f"node_pack:{p}")
        for t in wf["node_types"]:
            tid = f"node_type:{t}"
            g.node(tid, "node_type", label=t)
            g.edge(wid, "uses", tid)
            if len(packs) == 1:
                # unambiguous attribution only; never guess which pack owns a type
                g.edge(tid, "provided_by", f"node_pack:{packs[0]}")
        for m in wf["models"]:
            fid = f"model_file:{m}"
            g.node(fid, "model_file", label=m)
            g.edge(wid, "requires", fid)
            cid = f"model:{_norm_model(m)}"
            g.node(cid, "model", label=_norm_model(m))
            g.edge(fid, "belongs_to", cid)

    # ---- transcript evidence ---------------------------------------------
    if YT_FACTS.exists():
        for line in YT_FACTS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            vid = f"video:{rec['video_id']}"
            g.node(vid, "video", label=(rec.get("title") or rec["video_id"])[:90],
                   url=rec["url"], channel=rec.get("channel"))
            ch = f"channel:{rec.get('channel')}"
            g.node(ch, "channel", label=rec.get("channel"))
            g.edge(vid, "belongs_to", ch)

            for kind, items in rec.get("facts", {}).items():
                for it in items:
                    ev = [{"video": rec["video_id"], "t": it["t"], "quote": it["quote"]}]
                    if kind == "model":
                        tgt = g.node(f"model:{it['value']}", "model", label=it["value"])
                    elif kind == "model_file":
                        tgt = g.node(f"model_file:{it['value']}", "model_file", label=it["value"])
                    elif kind == "node_pack":
                        v = _norm_pack(it["value"].replace(" ", "-"))
                        tgt = g.node(f"node_pack:{v}", "node_pack", label=v)
                    elif kind in ("technique", "creative"):
                        tgt = g.node(f"{kind}:{it['value']}", kind, label=it["value"])
                    else:
                        tgt = g.node(f"{kind}:{it['value']}", kind, label=it["value"])
                    g.edge(vid, "mentions", tgt, evidence=ev)

    # ---- brand styles ------------------------------------------------------
    for brand_dir in sorted(STYLES.glob("*/styles")):
        brand = brand_dir.parent.name
        g.node(f"brand:{brand}", "brand", label=brand)
        for p in sorted(brand_dir.glob("*.yaml")):
            if p.stem == "index":
                continue
            sid = f"style:{brand}/{p.stem}"
            g.node(sid, "style", label=p.stem, brand=brand)
            g.edge(sid, "belongs_to", f"brand:{brand}")
    return g


def report(g: Graph) -> str:
    kinds = Counter(n["kind"] for n in g.nodes.values())
    rels = Counter(e["rel"] for e in g.edges)

    # god nodes: highest-degree, the things everything depends on
    deg: Counter[str] = Counter()
    for e in g.edges:
        deg[e["src"]] += 1
        deg[e["dst"]] += 1

    packs = [(g.nodes[n]["label"], d) for n, d in deg.most_common()
             if g.nodes[n]["kind"] == "node_pack"][:15]
    models = [(g.nodes[n]["label"], d) for n, d in deg.most_common()
              if g.nodes[n]["kind"] == "model"][:15]
    types = [(g.nodes[n]["label"], d) for n, d in deg.most_common()
             if g.nodes[n]["kind"] == "node_type"][:15]

    evidence_edges = sum(1 for e in g.edges if e.get("evidence"))
    corroborated = [
        g.nodes[e["dst"]]["label"] for e in g.edges
        if e["rel"] == "mentions" and g.nodes[e["dst"]]["kind"] in ("model", "node_pack")
        and any(x["src"] == e["dst"] or x["dst"] == e["dst"]
                for x in g.edges if x["rel"] == "requires")
    ]

    L = [
        f"# Graph Report — EPALLE Studio corpus ({date.today()})",
        "",
        "## Summary",
        f"- {len(g.nodes)} nodes · {len(g.edges)} edges",
        f"- node kinds: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()),
        f"- edge kinds: " + ", ".join(f"{k} {v}" for k, v in rels.most_common()),
        f"- {evidence_edges} edges carry transcript evidence (video id + timestamp + quote)",
        "",
        "## Extraction provenance",
        "- workflow structure: EXTRACTED from `workflows/manifest.json` (`class_type`,",
        "  `properties.cnr_id`/`aux_id`, widget model filenames). No inference.",
        "- transcript facts: EXTRACTED from subtitle cues; every one cites a video and",
        "  timestamp. A creator saying something is evidence of a claim, not proof it works.",
        f"- node types with no declared pack are attributed to `{CORE_MARKER}`; a type is only",
        "  linked to a pack when its workflow declares exactly one, so attribution is never guessed.",
        "",
        "## God nodes — node packs (what everything depends on)",
        *[f"- `{n}` — {d} connections" for n, d in packs],
        "",
        "## God nodes — models",
        *[f"- `{n}` — {d} connections" for n, d in models],
        "",
        "## Most-used node types",
        *[f"- `{n}` — {d} connections" for n, d in types],
        "",
        "## Corroboration",
        f"- {len(set(corroborated))} concepts appear BOTH as a workflow dependency and in a",
        "  creator transcript: " + ", ".join(f"`{x}`" for x in sorted(set(corroborated))[:20]),
        "",
        "## Queries",
        "```bash",
        "uv run packages/library/graph_query.py deps workflows/icekiub/Carousel_Pose_changer.json",
        "uv run packages/library/graph_query.py dependents comfyui-kjnodes",
        "uv run packages/library/graph_query.py evidence flux-2-klein",
        "```",
    ]
    return "\n".join(L)


def main() -> None:
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("usage: graph_build.py   (no arguments; rebuilds graph/ from the corpus)")
        raise SystemExit(0)
    g = build()
    GRAPH.mkdir(exist_ok=True)
    (GRAPH / "graph.json").write_text(
        json.dumps({"nodes": list(g.nodes.values()), "edges": g.edges},
                   indent=1, ensure_ascii=False), encoding="utf-8")
    (GRAPH / "GRAPH_REPORT.md").write_text(report(g), encoding="utf-8")
    print(f"graph/graph.json  {len(g.nodes)} nodes, {len(g.edges)} edges")
    print("graph/GRAPH_REPORT.md written")


if __name__ == "__main__":
    main()
