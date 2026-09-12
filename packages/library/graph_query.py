"""Query the corpus graph.

The two questions the plan set as the Phase 3 gate:

    deps <workflow>        what node packs and models does it need, end to end?
    dependents <pack>      which workflows break if this pack is missing?

Plus `evidence <concept>` — where a creator actually talked about it, with the
timestamp, so a claim can be checked rather than trusted.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
GRAPH_JSON = REPO / "graph" / "graph.json"


def load() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if not GRAPH_JSON.exists():
        raise SystemExit("graph/graph.json missing — run packages/library/graph_build.py first")
    d = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    return {n["id"]: n for n in d["nodes"]}, d["edges"]


def _find(nodes: dict[str, dict[str, Any]], needle: str, kinds: tuple[str, ...] = ()) -> list[str]:
    n = needle.lower().replace("\\", "/")
    exact = [i for i, v in nodes.items()
             if (not kinds or v["kind"] in kinds) and v.get("label", "").lower() == n]
    if exact:
        return exact
    return [i for i, v in nodes.items()
            if (not kinds or v["kind"] in kinds)
            and (n in i.lower() or n in str(v.get("label", "")).lower())]


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


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        print("usage: graph_query.py {deps|dependents|evidence|stats} [target]")
        raise SystemExit(2)
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    fns = {"deps": deps, "dependents": dependents, "evidence": evidence}
    if cmd == "stats":
        raise SystemExit(stats())
    if cmd not in fns:
        raise SystemExit(f"unknown command {cmd!r}")
    if not arg:
        raise SystemExit(f"{cmd} needs a target")
    raise SystemExit(fns[cmd](arg))


if __name__ == "__main__":
    main()
