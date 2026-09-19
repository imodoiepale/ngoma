"""One Archify workflow diagram per business idea, generated from data, never drawn by hand.

Inputs (read only):
  brands/_business/ideas.yaml                          the 50 ideas and their numbers
  brands/_templates/workflows/<id>-<slug>.studio.json  the studio pipeline for each idea
  packages/studio-ui/catalog/nodes.json                what actually runs each node

Outputs:
  docs/diagrams/ideas/<id>.workflow.json   Archify IR (schema v2)
  docs/diagrams/ideas/<id>.workflow.html   delivered HTML (--deliver only)
  docs/diagrams/ideas/README.md            index with the delivery receipt per diagram

    uv run --quiet --with pyyaml python packages/strategy/idea_diagrams.py
    uv run --quiet --with pyyaml python packages/strategy/idea_diagrams.py --deliver
    uv run --quiet --with pyyaml python packages/strategy/idea_diagrams.py --idea V01 --deliver

--deliver validates each source with Archify (node) at its recorded profile, delivers the
HTML and rewrites README.md; any failure exits non-zero and leaves README.md untouched.
Archify is found at $ARCHIFY_HOME or the default skill path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import business_os  # noqa: E402

TEMPLATES = REPO / "brands" / "_templates" / "workflows"
CATALOG = REPO / "packages" / "studio-ui" / "catalog" / "nodes.json"
OUT = REPO / "docs" / "diagrams" / "ideas"
DEFAULT_ARCHIFY = Path(r"C:\Users\inkno\.claude\skills\archify")

MAX_COL = 5
MAX_LABEL = 22
MAX_SUBLABEL = 20

# lane id, label, backend kinds it holds, variant
LANES = [
    ("you", "You provide", ("input", "brand"), None),
    ("studio", "Studio code", ("python",), None),
    ("gpu", "ComfyUI on the pod", ("comfy",), None),
    ("hosted", "Hosted model", ("router",), None),
    ("publish", "Publish (draft first)", ("publish",), None),
    ("gaps", "Not runnable yet", ("gap", "unmapped"), "exception"),
]
LANE_OF = {kind: lane for lane, _, kinds, _ in LANES for kind in kinds}
NODE_TYPE = {"input": "frontend", "brand": "frontend", "python": "backend", "comfy": "cloud",
             "router": "external", "publish": "external", "gap": "security",
             "unmapped": "security"}

# Ideas that could not pass the showcase profile after focused generator repairs, with why.
# Empty means every idea is delivered at showcase.
STANDARD_FALLBACK: dict[str, str] = {
    "M01": "one proper crossing (reference images -> lipsync crosses brief -> long video) under "
           "all four column variants and every route preset on either edge",
    "M07": "one proper crossing and one shared corridor (video -> compositor vs cut -> WhatsApp) "
           "under all column variants and route presets on the diagnosed edges",
    "P01": "three dataset branches in one ComfyUI lane share a 278px corridor under all column "
           "variants and every route preset on the diagnosed edges",
    "P03": "one proper crossing (reference images -> carousel crosses brief -> character video) "
           "under all column variants and every route preset on either edge",
}

# Column placement per idea. "rank" (default): longest-path rank, next free column.
# "compact": earliest column the predecessors allow. "late": inputs slide right next to
# their first consumer, so a shared input does not sit between another input and its step.
# "late-compact": both. Set only where Archify's showcase gate reported a crossing or
# shared corridor under the default.
LAYOUT_VARIANT: dict[str, str] = {
    "A01": "late", "P09": "late", "S08": "late", "U04": "late", "U06": "late", "V04": "late",
    "M05": "compact", "M07": "compact",
}
VARIANTS = ("rank", "late", "compact", "late-compact")

# Archify route presets for edges that the showcase gate reported crossing or sharing a
# corridor under every column variant: {idea: {"source>target": "preset" | "preset@bias"}}.
EDGE_ROUTE: dict[str, dict[str, str]] = {}
ROUTES = ("drop", "bottom-channel", "up-channel", "outside-right", "straight", "return-left")

NOISE = re.compile(r"(?i)\b(subs?|icekiub|icy|new|wf|aio)\b|\bv\d+(\.\d+)*\b")


# ---- inputs -------------------------------------------------------------------------

def load_catalog() -> dict[str, dict[str, Any]]:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {n["kind"]: n for n in doc["nodes"]}


def template_path(idea_id: str) -> Path:
    matches = sorted(TEMPLATES.glob(f"{idea_id.lower()}-*.studio.json"))
    if len(matches) != 1:
        raise SystemExit(f"{idea_id}: expected one studio template, found {len(matches)}")
    return matches[0]


def load_template(idea_id: str) -> dict[str, Any]:
    return json.loads(template_path(idea_id).read_text(encoding="utf-8"))


# ---- text ---------------------------------------------------------------------------

def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" -,(")
    return cut + "…"


def _label(label: str) -> tuple[str, str | None]:
    """Short label; a parenthetical that does not fit moves to the sublabel."""
    if len(label) > MAX_LABEL:
        label = label.replace(" and ", " + ")
    m = re.match(r"^(.*?)\s*\((.+)\)$", label)
    if len(label) > MAX_LABEL and m:
        return _clip(m.group(1), MAX_LABEL), m.group(2)
    return _clip(label, MAX_LABEL), None


def _workflow_hint(workflow: str) -> str:
    stem = Path(workflow).stem.replace("_", " ").replace("-", " ")
    stem = NOISE.sub(" ", stem)
    return _clip(stem, MAX_SUBLABEL)


def node_backend(tnode: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> str:
    if tnode["kind"] == "unmapped" or tnode["kind"] not in catalog:
        return "unmapped"
    return catalog[tnode["kind"]]["backend"]["kind"]


def describe(tnode: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> tuple[str, str | None]:
    backend = node_backend(tnode, catalog)
    if backend == "unmapped":
        step = (tnode.get("data") or {}).get("step") or tnode["kind"]
        return _clip(step.replace("-", " ").capitalize(), MAX_LABEL), "no node yet"
    entry = catalog[tnode["kind"]]
    label, paren = _label(entry["label"])
    b = entry["backend"]
    if paren:
        hint = paren
    elif backend == "comfy" and b.get("workflow"):
        hint = _workflow_hint(b["workflow"])
    elif b.get("module"):
        hint = Path(b["module"]).name
    elif backend == "router":
        hint = b.get("profile", "router")
    elif backend == "gap":
        hint = "not built yet"
    else:
        hint = None
    return label, (_clip(hint, MAX_SUBLABEL) if hint else None)


# ---- layout -------------------------------------------------------------------------

# Archify's default node is 92px and it rejects a label wider than its node; its estimate
# is about 6.8px per label character. Widen only nodes that need it, in 4px steps.
DEFAULT_NODE_WIDTH = 92
LABEL_PX, SUBLABEL_PX, NODE_PAD = 7.0, 6.0, 20


def node_width(label: str, sub: str | None, tag: str | None) -> int:
    need = max(len(label) * LABEL_PX, len(sub or "") * SUBLABEL_PX, len(tag or "") * SUBLABEL_PX)
    width = int(-(-(need + NODE_PAD) // 4) * 4)
    return max(DEFAULT_NODE_WIDTH, width)


def _edges(template: dict[str, Any]) -> list[tuple[str, str, str]]:
    """De-duplicated (source, target, label) per node pair, in template order."""
    pairs: dict[tuple[str, str], list[str]] = {}
    for e in template.get("edges", []):
        key = (e["source"], e["target"])
        label = e.get("type") or e.get("sourceHandle") or ""
        pairs.setdefault(key, [])
        if label and label not in pairs[key]:
            pairs[key].append(label)
    return [(s, t, " + ".join(v)) for (s, t), v in pairs.items()]


def _topo(ids: list[str], edges: list[tuple[str, str, str]]) -> list[str]:
    preds = {i: {s for s, t, _ in edges if t == i} for i in ids}
    order, done = [], set()
    while len(order) < len(ids):
        ready = [i for i in ids if i not in done and preds[i] <= done]
        if not ready:
            raise SystemExit("template edge graph has a cycle")
        order.append(ready[0])
        done.add(ready[0])
    return order


def ranks(ids: list[str], edges: list[tuple[str, str, str]]) -> dict[str, int]:
    rank = {i: 0 for i in ids}
    for i in _topo(ids, edges):
        for s, t, _ in edges:
            if s == i:
                rank[t] = max(rank[t], rank[i] + 1)
    top = max(rank.values(), default=0)
    if top > MAX_COL:  # compress into 0..5 preserving order
        rank = {i: round(r * MAX_COL / top) for i, r in rank.items()}
    return rank


def place(ids: list[str], lanes: dict[str, str], edges: list[tuple[str, str, str]]) -> dict[str, int]:
    """Columns: longest-path rank, then the next free column in the lane.

    An edge never points left; inside one lane it always moves at least one column right.
    When a lane runs out of columns (a long chain inside one lane), the layout is redone
    compactly: each node takes the earliest column its predecessors allow, so a
    cross-lane handoff may drop straight down in the same column.
    """
    return place_variant(ids, lanes, edges, "rank")


def place_variant(ids: list[str], lanes: dict[str, str], edges: list[tuple[str, str, str]],
                  variant: str) -> dict[str, int]:
    compact = variant.endswith("compact")
    late = variant.startswith("late")
    # each variant degrades deterministically when a lane runs out of columns
    attempts = [(compact, late), (True, late), (compact, False), (True, False)]
    for i, (c, s) in enumerate(attempts):
        try:
            return _place(ids, lanes, edges, compact=c, late_sources=s)
        except SystemExit:
            if i == len(attempts) - 1:
                raise
    raise AssertionError("unreachable")


def _place(ids: list[str], lanes: dict[str, str], edges: list[tuple[str, str, str]],
           compact: bool, late_sources: bool = False) -> dict[str, int]:
    rank = ranks(ids, edges)
    order = sorted(_topo(ids, edges), key=lambda i: (rank[i], ids.index(i)))
    col: dict[str, int] = {}
    taken: set[tuple[str, int]] = set()
    sources = [i for i in ids if not any(t == i for _, t, _ in edges)]
    consumers = {i: [t for s, t, _ in edges if s == i] for i in ids}
    if late_sources and any(consumers[i] for i in sources):
        # place every step first as if its inputs sat at column 0 in another lane, then
        # slide each input right, next to its earliest consumer
        inner = [i for i in order if i not in sources]
        for i in inner:
            preds = [s for s, t, _ in edges if t == i and s not in sources]
            lb = max((col[p] + (1 if lanes[p] == lanes[i] else 0) for p in preds), default=0)
            want = lb if compact else max(rank[i], lb)
            options = list(range(want, MAX_COL + 1)) + list(range(want - 1, lb - 1, -1))
            free = [c for c in options if (lanes[i], c) not in taken]
            if not free:
                raise SystemExit(f"no free column for node {i} in lane {lanes[i]}")
            col[i] = free[0]
            taken.add((lanes[i], free[0]))
        for i in sorted(sources, key=lambda s: (min((col[t] for t in consumers[s]), default=0),
                                                ids.index(s))):
            ub = min((col[t] - (1 if lanes[t] == lanes[i] else 0) for t in consumers[i]),
                     default=0)
            free = [c for c in range(ub, -1, -1) if (lanes[i], c) not in taken]
            if not free:
                raise SystemExit(f"no free column for input {i} in lane {lanes[i]}")
            col[i] = free[0]
            taken.add((lanes[i], free[0]))
        return col
    for i in order:
        preds = [s for s, t, _ in edges if t == i]
        lb = max((col[p] + (1 if lanes[p] == lanes[i] else 0) for p in preds), default=0)
        want = lb if compact else max(rank[i], lb)
        options = list(range(want, MAX_COL + 1)) + list(range(want - 1, lb - 1, -1))
        free = [c for c in options if (lanes[i], c) not in taken]
        if not free:
            raise SystemExit(f"no free column for node {i} in lane {lanes[i]}")
        col[i] = free[0]
        taken.add((lanes[i], free[0]))
    return col


def main_path(ids: list[str], edges: list[tuple[str, str, str]], col: dict[str, int]) -> list[str]:
    best: dict[str, list[str]] = {}
    for i in reversed(_topo(ids, edges)):
        tails = [best[t] for s, t, _ in edges if s == i and col[t] >= col[i]]
        best[i] = [i] + max(tails, key=len, default=[])
    path = max((best[i] for i in ids), key=len, default=[])
    return path if len(path) >= 2 else []


# ---- IR -----------------------------------------------------------------------------

def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def cards(idea: dict[str, Any], costed: business_os.Costed, flags: dict[str, Any]) -> list[dict]:
    per_unit = "units =" in idea.get("buyer", "") + idea.get("offer", "")
    base = costed.base
    price = business_os._money(idea["price_usd"]) + (" per unit" if per_unit else "/mo")
    numbers = [f"Price {price}",
               f"Base revenue {business_os._money(base['mrr'])}/mo",
               f"Margin {_pct(base['margin'])}",
               f"First cash {idea['first_cash_days']} days"]
    rules = []
    if flags["adult"]:
        rules.append("18+: fictional adults only")
    if flags["consent"]:
        rules.append("Consent on file before any likeness")
    for label in flags["gaps"]:
        rules.append(_clip(f"Gap: {label} not built", 34))
    rules.append("Dry-run until approved")
    if flags["brand"] or len(rules) < 3:
        rules.append("Logo composited, never generated")
    return [{"dot": "emerald", "title": "Numbers (base)", "items": numbers},
            {"dot": "rose" if (flags["gaps"] or flags["adult"]) else "amber",
             "title": "Rules", "items": rules}]


def build(idea: dict[str, Any], costed: business_os.Costed, template: dict[str, Any],
          catalog: dict[str, dict[str, Any]], variant: str | None = None,
          routes: dict[str, str] | None = None) -> dict[str, Any]:
    routes = EDGE_ROUTE.get(idea["id"], {}) if routes is None else routes
    tnodes = template["nodes"]
    gap_ids = {g["node"] for g in template.get("gaps", [])}
    ids = [n["id"] for n in tnodes]
    edges = _edges(template)
    backend = {}
    for n in tnodes:
        b = node_backend(n, catalog)
        # a template-declared gap is not runnable, whatever the catalogue says
        backend[n["id"]] = "gap" if (n["id"] in gap_ids and b != "unmapped") else b
    lanes = {i: LANE_OF[backend[i]] for i in ids}
    col = place_variant(ids, lanes, edges, variant or LAYOUT_VARIANT.get(idea["id"], "rank"))

    nodes, flags = [], {"adult": False, "consent": False, "gaps": [], "brand": False}
    for n in tnodes:
        i = n["id"]
        entry = catalog.get(n["kind"], {})
        label, sub = describe(n, catalog)
        tags = []
        if lanes[i] == "gaps":
            tags.append("gap")
            flags["gaps"].append(label)
        if entry.get("consent"):
            tags.append("consent")
            flags["consent"] = True
        if entry.get("adult"):
            tags.append("18+")
            flags["adult"] = True
        if entry.get("needs_setup") and lanes[i] != "gaps":
            # bound, but a gated model or missing server (docs/BLOCKERS.md item) must be cleared first
            tags.append("setup")
        if n["kind"] in ("brand-kit", "compositor"):
            flags["brand"] = True
        node = {"id": i, "lane": lanes[i], "col": col[i], "type": NODE_TYPE[backend[i]],
                "label": label}
        if sub:
            node["sublabel"] = sub
        if tags:
            node["tag"] = ", ".join(tags)
        width = node_width(label, sub, node.get("tag"))
        if width > DEFAULT_NODE_WIDTH:
            node["width"] = width
        nodes.append(node)
    if idea["family"] == "adult":
        flags["adult"] = True

    nodes.sort(key=lambda n: (col[n["id"]], [l[0] for l in LANES].index(n["lane"]), n["id"]))
    path = main_path(ids, edges, col)
    on_path = set(zip(path, path[1:]))
    ir_edges = []
    for s, t, label in edges:
        e: dict[str, Any] = {"from": s, "to": t}
        if label:
            e["label"] = label
        if (s, t) in on_path:
            e["variant"] = "emphasis"
        elif lanes[t] == "gaps" or lanes[s] == "gaps":
            e["variant"] = "dashed"
        if f"{s}>{t}" in routes:
            preset, _, bias = routes[f"{s}>{t}"].partition("@")
            e["route"] = preset
            if bias:
                e["bias"] = float(bias)
        ir_edges.append(e)

    profile = "standard" if idea["id"] in STANDARD_FALLBACK else "showcase"
    used = {lanes[i] for i in ids}
    ir: dict[str, Any] = {
        "schema_version": 2,
        "diagram_type": "workflow",
        "meta": {"title": f"{idea['id']} {idea['name']}", "locale": "en",
                 "quality_profile": profile},
        "lanes": [{"id": lid, "label": lab, **({"variant": var} if var else {})}
                  for lid, lab, _, var in LANES if lid in used],
    }
    if path:
        ir["mainPath"] = path
    ir["nodes"] = nodes
    ir["edges"] = ir_edges
    ir["cards"] = cards(idea, costed, flags)
    return ir


def dumps(ir: dict[str, Any]) -> str:
    return json.dumps(ir, indent=2, ensure_ascii=False) + "\n"


def generate(only: str | None = None) -> list[tuple[dict[str, Any], Path]]:
    doc = business_os.load()
    catalog = load_catalog()
    rows = business_os.costed_all(doc)
    if only:
        rows = [r for r in rows if r.idea["id"].upper() == only.upper()]
        if not rows:
            raise SystemExit(f"unknown idea {only}")
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for r in rows:
        ir = build(r.idea, r, load_template(r.idea["id"]), catalog)
        path = OUT / f"{r.idea['id'].lower()}.workflow.json"
        data = dumps(ir).encode("utf-8")
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
        written.append((r.idea, path))
    return written


# ---- delivery -----------------------------------------------------------------------

def archify_home() -> Path:
    return Path(os.environ.get("ARCHIFY_HOME") or DEFAULT_ARCHIFY)


def _archify(*args: str) -> tuple[int, dict[str, Any] | None, str]:
    home = archify_home()
    env = {**os.environ, "ARCHIFY_UPDATE_CHECK_DISABLED": "1"}
    proc = subprocess.run(["node", str(home / "bin" / "archify.mjs"), *args], cwd=home, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        receipt = json.loads(proc.stdout)
    except json.JSONDecodeError:
        receipt = None
    return proc.returncode, receipt, proc.stdout + proc.stderr


def _issues(receipt: dict[str, Any] | None) -> str:
    if not receipt:
        return "no JSON receipt"
    comp = receipt.get("composition") or {}
    msgs = [f"{i.get('code')}: {i.get('message')}" for i in comp.get("issues", [])]
    msgs += [f"{c['name']}: {c['details']}" for c in receipt.get("checks", []) if not c.get("ok")]
    return "; ".join(msgs) or json.dumps(receipt)[:400]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deliver(written: list[tuple[dict[str, Any], Path]]) -> int:
    if shutil.which("node") is None:
        print("error: node is not on PATH; install Node.js to validate and deliver", file=sys.stderr)
        return 2
    if not (archify_home() / "bin" / "archify.mjs").exists():
        print(f"error: Archify not found at {archify_home()} (set ARCHIFY_HOME)", file=sys.stderr)
        return 2
    results, failed = [], 0
    for idea, src in written:
        profile = json.loads(src.read_text(encoding="utf-8"))["meta"]["quality_profile"]
        code, receipt, raw = _archify("validate", "workflow", str(src), "--quality", profile, "--json")
        if code != 0:
            print(f"FAIL validate {idea['id']} ({profile}): {_issues(receipt) if receipt else raw[-800:]}")
            failed += 1
            continue
        html = src.with_suffix(".html")
        code, receipt, raw = _archify("deliver", "workflow", str(src), str(html), "--quality", profile,
                                      "--json")
        if code != 0 or not receipt:
            print(f"FAIL deliver {idea['id']} ({profile}): {_issues(receipt) if receipt else raw[-800:]}")
            failed += 1
            continue
        v = receipt.get("validation") or {}
        spec_sha = (receipt.get("specification") or {}).get("sha256", "")
        html_sha = (receipt.get("artifact") or {}).get("sha256", "")
        if spec_sha != _sha(src) or html_sha != _sha(html):
            print(f"FAIL deliver {idea['id']}: receipt sha256 does not match the files on disk")
            failed += 1
            continue
        results.append({"id": idea["id"], "name": idea["name"], "profile": profile,
                        "checks": v.get("checksPassed", 0), "total": v.get("checkCount", 0),
                        "errors": v.get("errors", 0), "warnings": v.get("warnings", 0),
                        "src": src, "html": html, "src_sha": spec_sha, "html_sha": html_sha})
        print(f"ok {idea['id']} {profile} checks {results[-1]['checks']}/{results[-1]['total']}")
    if failed:
        print(f"{failed} idea(s) failed; README.md not rewritten", file=sys.stderr)
        return 1
    write_readme(results)
    return 0


def write_readme(results: list[dict[str, Any]]) -> None:
    if len(results) != len(business_os.load()["ideas"]):
        # a single-idea run refreshes that row only
        old = _read_rows()
        for r in results:
            old[r["id"]] = _row(r)
        rows = [old[k] for k in sorted(old)]
    else:
        rows = [_row(r) for r in sorted(results, key=lambda r: r["id"])]
    showcase = sum(1 for r in rows if "| showcase |" in r)
    fallback = [f"- **{k}**: {v}" for k, v in sorted(STANDARD_FALLBACK.items())] or \
               ["- None. Every idea passes the showcase profile."]
    text = "\n".join([
        "# Idea workflow diagrams",
        "",
        "One Archify workflow diagram per business idea, generated by",
        "`packages/strategy/idea_diagrams.py` from `brands/_business/ideas.yaml`, the studio",
        "templates in `brands/_templates/workflows/` and `packages/studio-ui/catalog/nodes.json`.",
        "Do not edit these files by hand; regenerate them:",
        "",
        "```bash",
        "uv run --quiet --with pyyaml python packages/strategy/idea_diagrams.py            # JSON sources",
        "uv run --quiet --with pyyaml python packages/strategy/idea_diagrams.py --deliver  # + validate, HTML, this file",
        "```",
        "",
        "Lanes say what runs a step: you, studio code, ComfyUI on the pod, a hosted model, a",
        "publisher, or nothing yet (the exception lane). Numbers are planning estimates from",
        "`business_os.py`.",
        "",
        f"{len(rows)} diagrams; {showcase} at showcase, {len(rows) - showcase} at standard.",
        "",
        "## Standard fallbacks",
        "",
        *fallback,
        "",
        "## Receipts",
        "",
        "Checks = passing artifact checks from `archify deliver`; Errors / Warnings = composition",
        "summary; Source / HTML = first 12 hex of the SHA-256 recorded at delivery.",
        "",
        "| ID | Idea | Profile | Checks | Errors | Warnings | Source | HTML |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
        "",
    ])
    (OUT / "README.md").write_text(text, encoding="utf-8", newline="\n")


def _row(r: dict[str, Any]) -> str:
    return (f"| {r['id']} | {r['name']} | {r['profile']} | {r['checks']}/{r['total']} | {r['errors']} | "
            f"{r['warnings']} | [`{r['src_sha'][:12]}`]({r['src'].name}) | "
            f"[`{r['html_sha'][:12]}`]({r['html'].name}) |")


def _read_rows() -> dict[str, str]:
    readme = OUT / "README.md"
    rows = {}
    if readme.exists():
        for line in readme.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\| ([A-Z]\d\d) \|", line)
            if m:
                rows[m.group(1)] = line
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate one Archify workflow diagram per business idea.")
    ap.add_argument("--deliver", action="store_true",
                    help="also validate with Archify, deliver HTML and rewrite README.md (needs node)")
    ap.add_argument("--idea", help="limit to one idea id, e.g. V01")
    args = ap.parse_args(argv)
    written = generate(args.idea)
    print(f"wrote {len(written)} source(s) to {OUT.relative_to(REPO)}")
    return deliver(written) if args.deliver else 0


if __name__ == "__main__":
    sys.exit(main())
