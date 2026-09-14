"""Query the corpus graph.

The two questions the plan set as the Phase 3 gate:

    deps <workflow>        what node packs and models does it need, end to end?
    dependents <pack>      which workflows break if this pack is missing?

Plus `evidence <concept>` — where a creator actually talked about it, with the
timestamp, so a claim can be checked rather than trusted.

The studio layer adds three questions about references and steps:

    can-feed <type>        which steps accept an image / video / audio / text input?
    paths <from> <to>      how does one step reach another, by port type (BFS over `feeds`)?
    refs <brand>           the brand's reference collections with use, rights and count
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
GRAPH_JSON = REPO / "graph" / "graph.json"


def load() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if not GRAPH_JSON.exists():
        raise SystemExit("graph/graph.json missing — run packages/library/graph_build.py first")
    d = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    return {n["id"]: n for n in d["nodes"]}, d["edges"]


def _squash(s: str) -> str:
    # "sage attention", "sage-attention" and "SageAttention" are one concept; spoken facts
    # and workflow ids spell it differently, so match on letters and digits only.
    return re.sub(r"[\s_\-]+", "", s.lower().replace("\\", "/"))


def _find(nodes: dict[str, dict[str, Any]], needle: str, kinds: tuple[str, ...] = ()) -> list[str]:
    n = _squash(needle)
    exact = [i for i, v in nodes.items()
             if (not kinds or v["kind"] in kinds) and _squash(str(v.get("label", ""))) == n]
    if exact:
        return exact
    return [i for i, v in nodes.items()
            if (not kinds or v["kind"] in kinds)
            and (n in _squash(i) or n in _squash(str(v.get("label", ""))))]


def deps(target: str) -> int:
    nodes, edges = load()
    hits = _find(nodes, target, ("workflow",))
    if not hits:
        print(f"no workflow matching {target!r}")
        return 1
    out_edges = defaultdict(list)
    for e in edges:
        out_edges[e["src"]].append(e)

    for wid in hits[:3]:
        w = nodes[wid]
        print(f"\n=== {w['label']}  ({w['node_count']} nodes, collection={w['collection']})")
        print(f"    {wid.removeprefix('workflow:')}")
        packs = sorted(nodes[e['dst']]['label'] for e in out_edges[wid]
                       if e["rel"] == "requires" and nodes[e["dst"]]["kind"] == "node_pack")
        files = sorted(nodes[e['dst']]['label'] for e in out_edges[wid]
                       if e["rel"] == "requires" and nodes[e["dst"]]["kind"] == "model_file")
        types = sorted(nodes[e['dst']]['label'] for e in out_edges[wid] if e["rel"] == "uses")
        print(f"\n  node packs to install ({len(packs)}):")
        for p in packs:
            print(f"    - {p}")
        print(f"\n  model files to download ({len(files)}):")
        for f in files:
            print(f"    - {f}")
        print(f"\n  node types used: {len(types)}")
        print(f"    {', '.join(types[:14])}{' ...' if len(types) > 14 else ''}")
    return 0


def dependents(target: str) -> int:
    nodes, edges = load()
    hits = _find(nodes, target, ("node_pack", "model_file", "model", "node_type"))
    if not hits:
        print(f"nothing matching {target!r}")
        return 1
    nid = hits[0]
    print(f"=== dependents of {nodes[nid]['label']} ({nodes[nid]['kind']})")
    wfs = sorted({nodes[e["src"]]["label"] for e in edges
                  if e["dst"] == nid and e["rel"] in ("requires", "uses")
                  and nodes[e["src"]]["kind"] == "workflow"})
    print(f"{len(wfs)} workflow(s) break without it:")
    for w in wfs:
        print(f"  - {w}")
    if len(hits) > 1:
        print(f"\n(also matched {len(hits)-1} other node(s): "
              f"{', '.join(nodes[h]['label'] for h in hits[1:6])})")
    return 0


def evidence(target: str) -> int:
    nodes, edges = load()
    hits = _find(nodes, target)
    if not hits:
        print(f"nothing matching {target!r}")
        return 1
    found = 0
    for nid in hits[:5]:
        ev_edges = [e for e in edges if e["dst"] == nid and e.get("evidence")]
        if not ev_edges:
            continue
        print(f"\n=== {nodes[nid]['label']} ({nodes[nid]['kind']})")
        for e in ev_edges:
            v = nodes[e["src"]]
            for ev in e["evidence"][:3]:
                found += 1
                ts = ev["t"]
                secs = sum(int(x) * m for x, m in zip(reversed(ts.split(":")), (1, 60, 3600)))
                print(f"  [{ts}] {v.get('channel','?')}: {v['label'][:60]}")
                print(f"      \"{ev['quote'][:110]}\"")
                print(f"      {v.get('url','')}&t={secs}")
    if not found:
        print(f"no transcript evidence for {target!r} "
              f"(it may exist only as a workflow dependency — try `dependents`)")
    return 0


def stats() -> int:
    nodes, edges = load()
    from collections import Counter
    print(f"{len(nodes)} nodes, {len(edges)} edges")
    for k, v in Counter(n["kind"] for n in nodes.values()).most_common():
        print(f"  {k:<12} {v}")
    return 0


# ---------------------------------------------------------------- studio layer

def steps_accepting(nodes: dict[str, dict[str, Any]], port_type: str) -> dict[str, list[dict[str, Any]]]:
    """Steps with an input port that takes `port_type`, grouped by catalogue category."""
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in nodes.values():
        if n["kind"] == "step" and port_type in (n.get("accepts") or []):
            out[n.get("category") or "?"].append(n)
    return {k: sorted(v, key=lambda x: x["id"]) for k, v in sorted(out.items())}


def can_feed(port_type: str) -> int:
    nodes, _ = load()
    groups = steps_accepting(nodes, port_type)
    if not groups:
        print(f"no step accepts {port_type!r} (try image, video, audio, text, brand, character)")
        return 1
    total = sum(len(v) for v in groups.values())
    print(f"=== {total} step(s) accept {port_type}")
    for cat, steps in groups.items():
        print(f"\n  {cat}:")
        for s in steps:
            ports = ", ".join(p["id"] for p in s.get("inputs", [])
                              if p["type"] == port_type or (p["id"] == "media" and port_type in ("image", "video")))
            flag = " [consent]" if s.get("consent") else ""
            print(f"    - {s['id'].removeprefix('step:'):<20} {s['label']}  (port: {ports}){flag}")
    return 0


def find_paths(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]], src: str, dst: str,
               depth: int = 6, limit: int = 5) -> list[list[str]]:
    """Shortest simple paths over `feeds`, as step kinds. BFS, so shorter paths come first."""
    a, b = f"step:{src}", f"step:{dst}"
    if a not in nodes or b not in nodes:
        return []
    nxt: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e["rel"] == "feeds":
            nxt[e["src"]].append(e["dst"])
    for k in nxt:
        nxt[k].sort()
    found: list[list[str]] = []
    frontier: list[list[str]] = [[a]]
    while frontier and len(found) < limit:
        nxt_frontier: list[list[str]] = []
        for path in frontier:
            for n in nxt.get(path[-1], []):
                if n in path:
                    continue
                if n == b:
                    found.append(path + [n])
                    if len(found) >= limit:
                        break
                elif len(path) < depth:
                    nxt_frontier.append(path + [n])
            if len(found) >= limit:
                break
        frontier = nxt_frontier
    return [[p.removeprefix("step:") for p in path] for path in found]


def paths(src: str, dst: str) -> int:
    nodes, edges = load()
    for s in (src, dst):
        if f"step:{s}" not in nodes:
            print(f"no step {s!r} in the catalogue")
            return 1
    found = find_paths(nodes, edges, src, dst)
    if not found:
        print(f"no path from {src} to {dst} within 6 steps")
        return 1
    print(f"=== {len(found)} path(s) from {src} to {dst}")
    for p in found:
        print("  " + " -> ".join(p))
    return 0


def refs(brand: str) -> int:
    nodes, _ = load()
    cols = sorted((n for n in nodes.values()
                   if n["kind"] == "reference_collection" and n.get("brand") == brand), key=lambda n: n["id"])
    if not cols:
        print(f"no reference collections for {brand!r} (a folder needs collection.json or posts.jsonl)")
        return 1
    print(f"=== {len(cols)} reference collection(s) for {brand}")
    for c in cols:
        print(f"  - {c['label']:<28} {c.get('kind', '?'):<6} use={c.get('use', '?'):<12} "
              f"rights={c.get('rights', '?'):<9} consent={'yes' if c.get('consent') else 'no':<3} "
              f"{c.get('count', 0):>4} files")
    return 0


USAGE = "usage: graph_query.py {deps|dependents|evidence|stats|can-feed|paths|refs} [target] [target2]"


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print(USAGE)
        raise SystemExit(0)
    if len(sys.argv) < 2:
        print(__doc__)
        print(USAGE)
        raise SystemExit(2)
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    fns = {"deps": deps, "dependents": dependents, "evidence": evidence, "can-feed": can_feed, "refs": refs}
    if cmd == "stats":
        raise SystemExit(stats())
    if cmd == "paths":
        if len(sys.argv) < 4:
            raise SystemExit("paths needs <from-kind> <to-kind>")
        raise SystemExit(paths(sys.argv[2], sys.argv[3]))
    if cmd not in fns:
        raise SystemExit(f"unknown command {cmd!r}")
    if not arg:
        raise SystemExit(f"{cmd} needs a target")
    raise SystemExit(fns[cmd](arg))


if __name__ == "__main__":
    main()
