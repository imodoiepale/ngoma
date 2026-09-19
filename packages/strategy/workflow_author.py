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

Fan-out. A step written `carousel@each` runs once per item that reaches its iterated input
(`node.data.each = true`), so fifty reference images become fifty carousels instead of one
carousel fed a list. The runner loops; the author and the canvas only mark the node. The
iterated port is `data.each_port` when set, otherwise the node's first required image or
video input (`iterated_port`).

Briefs. `parse_brief` reads a sentence clause by clause ("then" keeps the user's order),
maps swaps to `character-swap` or `wardrobe`, marks per-item steps `@each`, reads "10
slides" into `carousel.slides`, attaches a named reference collection and asks a question
when a name is unknown. `extend` appends steps to a saved workflow without renaming a node.

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
# A swap is a change to an existing image, never the making of a character: when a swap
# rule matches a clause, the `refmod` rule is suppressed for that clause (see parse_brief).
SWAP_RULES: list[tuple[str, list[str]]] = [
    (r"\b(?:change|swap|replace|switch)\b[^.,;]{0,40}?\b(?:character|face|head|person|model|subject)s?\b"
     r"|\bcharacter[- ]?(?:swap|changer?|change)\b|\b(?:face|head)[- ]?swap\b"
     r"|\bput\s+(?:our|my|the|a)\s+(?:persona|character)\b", ["character-swap"]),
    (r"\b(?:change|swap|replace|switch)\b[^.,;]{0,40}?\b(?:outfit|clothes|clothing|wardrobe|dress|look)s?\b"
     r"|\boutfit[- ]?(?:swap|change)\b|\bwardrobe[- ]?(?:swap|change)\b|\btry[- ]on\b", ["wardrobe"]),
]
BRIEF_RULES: list[tuple[str, list[str]]] = [
    (r"\b(dataset|character board)\b", ["dataset-aio"]),
    (r"\b(consistent character|refmod|same (face|person)|persona|influencer|spokes(person|model)|ugc)\b", ["refmod"]),
    (r"\b(product|packshot|sku)\b", ["klein-edit"]),
    (r"\b(carousels?|photosets?|slides?)\b", ["carousel"]),
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
# `<step>@each` in a pipeline or brief: the node runs once per upstream item (see module doc).
EACH_SUFFIX = "@each"
# Backends that can be looped per item. Inputs are provided, a person decides once, and
# publishing always goes through a person, so none of those fan out.
EACH_BACKENDS = frozenset({"comfy", "router", "python", "gap"})


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


# ---------------------------------------------------------------- the brief parser
#
# A brief is read clause by clause. "then", "after that", "and next" split clauses and the
# user's order wins over rule order. Inside a clause, "for each", "per image", "across all
# of them" or a plural quantity ("my 50 reference images") makes the clause's media steps
# fan out (`@each`). "N slides" sets carousel.slides. A named reference collection that
# exists in the workspace attaches; an unknown name becomes a question. A clause phrased
# as an option ("we could then...", "optionally") is a proposed continuation, not a step.

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "fifty": 50,
                "hundred": 100}
_NUM = r"(\d+|" + "|".join(NUMBER_WORDS) + r")"
SEQUENCE_SPLIT = re.compile(r"\s*(?:[,;.]\s*)?(?:\band\s+)?(?:\bthen\b|\bafter that\b|\band next\b|\bnext,|\bafterwards\b|\bfollowed by\b|\bfinally\b)\s*",
                            re.I)
EACH_PHRASE = re.compile(r"\b(?:for|per|across|on|of)\s+(?:each|every|all)\b(?:\s+(?:of\s+)?(?:them|those|these|the\s+\w+|\w+))?"
                         r"|\beach\s+(?:of\s+)?(?:them|those|these|one|image|photo|result|output|post)s?\b"
                         r"|\bper\s+(?:image|photo|picture|post|result|item|reference|output|shot|still)s?\b"
                         r"|\bone\s+per\b|\bacross all of them\b|\ball of them\b", re.I)
QUANTITY = re.compile(_NUM + r"\s+(?:owned\s+|licensed\s+|reference\s+|ref\s+|product\s+)?(?:images?|photos?|pictures?|references?|refs|shots?|stills?|files?|frames?)\b", re.I)
COLLECTION_HINT = re.compile(r"\b(?:from|in|out of|using|use|with)\s+(?:my|our|the)?\s*(?:reference\s+)?(?:folder|collection|set|library)\s+(?:called\s+|named\s+)?[`'\"]?([a-z0-9][a-z0-9_-]{1,60})"
                             r"|\b(?:folder|collection)\s+(?:called\s+|named\s+)[`'\"]?([a-z0-9][a-z0-9_-]{1,60})"
                             r"|\b(?:from|using)\s+[`'\"]?([a-z0-9]+(?:-[a-z0-9]+)+)[`'\"]?", re.I)
SLIDES = re.compile(_NUM + r"\s*(?:-\s*)?slides?\b|\bslides?\s*(?:of|:|=)\s*(\d+)\b", re.I)
OPTION_PHRASE = re.compile(r"\b(?:option(?:al|ally)?(?:\s+of)?|could (?:also|then)?|maybe|possibly|later|down the line|if (?:we|you) want|as an option)\b", re.I)
PLURAL_MEDIA = re.compile(r"\b(?:images|photos|pictures|references|refs|stills|frames)\b", re.I)
REFERENCE_MENTION = re.compile(r"\b(?:reference|ref)s?\b|\bmy (?:images|photos|pictures|folder|collection)\b|\bthese (?:images|photos|pictures)\b", re.I)
_STEP_TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*(?:@each)?$")
_KV_TOKEN = re.compile(r"^([a-z_][a-z0-9_]*)=(.+)$")


def _number(token: str) -> int:
    t = token.lower()
    return int(t) if t.isdigit() else NUMBER_WORDS[t]


def _coerce(value: str) -> Any:
    v = value.strip().strip("'\"")
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def known_collections(client: str | None) -> list[str]:
    """Reference collections on disk for a client: folders under brands/<client>/references/."""
    if not client:
        return []
    root = BRANDS / client / "references"
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith("."))


def collection_count(client: str, name: str) -> int:
    root = BRANDS / client / "references" / name
    if not root.is_dir():
        return 0
    return sum(1 for p in root.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".wav", ".mp3"))


def _find_known(text: str, known: list[str]) -> list[str]:
    """Known collection names appearing in the text, longest match first, in text order."""
    hits: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for name in sorted(known, key=len, reverse=True):
        for m in re.finditer(r"(?<![a-z0-9-])" + re.escape(name.lower()) + r"(?![a-z0-9-])", text.lower()):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            hits.append((m.start(), name))
    return [n for _, n in sorted(hits)]


def _fans_out(step: str, cat: dict[str, Any]) -> bool:
    spec = cat["by_step"].get(step)
    if not spec or spec["backend"]["kind"] not in EACH_BACKENDS:
        return False
    node = {"kind": spec["kind"], "data": {}}
    return iterated_port(node, cat) is not None


def _makes_media(step: str, cat: dict[str, Any]) -> bool:
    spec = cat["by_step"].get(step)
    return bool(spec) and spec.get("category") != "inputs" and any(o["type"] in ("image", "video") for o in spec["outputs"])


def _literal_steps(text: str, cat: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]]] | None:
    """`carousel@each slides=10` (what the canvas sends) is steps and params, not prose."""
    tokens = text.replace(",", " ").split()
    if not tokens:
        return None
    steps: list[str] = []
    params: dict[str, dict[str, Any]] = {}
    for tok in tokens:
        low = tok.lower()
        if _STEP_TOKEN.match(low) and split_each(low)[0] in cat["by_step"]:
            steps.append(low)
        elif (kv := _KV_TOKEN.match(low)) and steps:
            params.setdefault(split_each(steps[-1])[0], {})[kv.group(1)] = _coerce(tok.split("=", 1)[1])
        else:
            return None
    return (steps, params) if steps else None


def parse_brief(brief: str, known: list[str] | None = None, cat: dict[str, Any] | None = None,
                minimal: bool = False) -> dict[str, Any]:
    """Read a plain-language brief into steps, fan-out flags, parameters, collections,
    proposed continuations and open questions. Pure: touches no file.

    `known` are the workspace's reference collection names; `minimal` skips the default
    image step and the automatic compositor (used when extending an existing workflow)."""
    cat = cat or load_catalog()
    known = list(known or [])
    text = brief.strip()
    out: dict[str, Any] = {"steps": [], "params": {}, "collections": [], "unknown_collections": [],
                           "continuations": [], "questions": [], "clauses": [], "language": None,
                           "inferred": True}
    out["language"] = next((code for pat, code in LANGUAGE_RULES if re.search(pat, text.lower())), None)

    literal = _literal_steps(text, cat)
    if literal:
        out["steps"], out["params"] = literal
        out["clauses"] = [{"text": text, "steps": list(literal[0]), "each": any(split_each(s)[1] for s in literal[0])}]
        return out

    named = _find_known(text, known)
    talks_of_refs = bool(REFERENCE_MENTION.search(text) or re.search(r"\b(folder|collection|persona)\b", text, re.I))
    if talks_of_refs:
        for m in COLLECTION_HINT.finditer(text):
            name = next(g for g in m.groups() if g)
            if name.lower() not in [k.lower() for k in known] and name.lower() not in NUMBER_WORDS and not name.isdigit():
                if name.lower() not in out["unknown_collections"]:
                    out["unknown_collections"].append(name.lower())
    # "our persona" names the one persona collection the workspace has, when it has one
    persona = [k for k in known if "persona" in k.lower()]
    if re.search(r"\b(?:our|my|the)\s+persona\b", text, re.I) and len(persona) == 1 and persona[0] not in named:
        named.append(persona[0])

    clauses = [c for c in SEQUENCE_SPLIT.split(text) if c and c.strip(" ,.;")]
    steps: list[str] = []
    for raw in clauses:
        low = raw.lower()
        each = bool(EACH_PHRASE.search(low))
        option = bool(OPTION_PHRASE.search(low))
        count = None
        if qm := QUANTITY.search(low):
            count = _number(qm.group(1))
            if count > 1:
                each = True
        # a folder of photos is a batch: "the red-dress photos", "my references"
        if PLURAL_MEDIA.search(low) and count != 1:
            each = True
        # "per post" must not read as "make a post", and a collection called red-dress is
        # not a request to change a dress
        cleaned = EACH_PHRASE.sub(" ", low)
        for name in named + out["unknown_collections"]:
            cleaned = re.sub(r"(?<![a-z0-9-])" + re.escape(name.lower()) + r"(?![a-z0-9-])", " ", cleaned)
        clause_steps: list[str] = []
        swapped = False
        for pattern, add in SWAP_RULES:
            if re.search(pattern, cleaned):
                clause_steps += [s for s in add if s not in clause_steps]
                swapped = True
        for pattern, add in BRIEF_RULES:
            if re.search(pattern, cleaned):
                clause_steps += [s for s in add if s not in clause_steps and not (swapped and s == "refmod")]
        if sm := SLIDES.search(low):
            n = _number(sm.group(1) or sm.group(2))
            out["params"].setdefault("carousel", {})["slides"] = n
            if "carousel" not in clause_steps and not any(split_each(s)[0] == "carousel" for s in steps):
                clause_steps.append("carousel")
        if count is not None or (REFERENCE_MENTION.search(low) and not out["collections"]):
            role = "batch" if not out["collections"] else "face"
            out["collections"].append({"name": None, "count": count, "role": role})
        spelled = [f"{s}{EACH_SUFFIX}" if each and _fans_out(s, cat) else s for s in clause_steps]
        out["clauses"].append({"text": raw.strip(" ,.;"), "steps": spelled, "each": each, "option": option, "count": count})
        if option and steps:
            for s in spelled:
                base, e = split_each(s)
                out["continuations"].append({"step": base, "each": e, "params": dict(out["params"].get(base, {}))})
            continue
        steps += [s for s in spelled if split_each(s)[0] not in [split_each(x)[0] for x in steps]]

    # the named collections fill the mentioned slots in order; extra names add slots. A
    # collection named for its purpose (wardrobe-..., persona-...) is the thing put in, not
    # the batch it goes into, following the director's `<purpose>-<name>` convention.
    for name in named:
        role = "clothes" if re.match(r"(wardrobe|clothes|outfit)[-_]", name.lower()) else \
               "face" if re.match(r"(persona|face|character|identity)[-_]", name.lower()) else None
        slot = next((c for c in out["collections"] if c["name"] is None and (role is None or c["role"] != "batch")), None)
        if slot is None:
            slot = {"name": None, "count": None, "role": role or ("batch" if not out["collections"] else "face")}
            out["collections"].append(slot)
        slot["name"] = name
        if role:
            slot["role"] = role
    if out["collections"] and not any(s == "reference-images" for s in steps):
        steps.insert(0, "reference-images")

    media = [s for s in steps if _makes_media(split_each(s)[0], cat)]
    if not media and not minimal:
        out["inferred"] = bool([s for s in steps if s != "reference-images"])
        steps.insert(0, "nano-banana-2")
    bases = [split_each(s)[0] for s in steps]
    if not minimal and "compositor" not in bases and any(s in bases for s in ("nano-banana-2", "carousel", "klein-edit")):
        steps.append("compositor")
    out["steps"] = steps
    if out["unknown_collections"]:
        out["questions"].append({"key": "collection",
                                 "prompt": f"Which reference collection did you mean by '{out['unknown_collections'][0]}'?",
                                 "options": known})
    if not out["inferred"]:
        out["questions"].append({"key": "kind", "prompt": "What should this make?",
                                 "options": ["nano-banana-2", "carousel", "klein-edit", "wan-i2v", "h3-ref2va", "tts"]})
    return out


def apply_answers(plan: dict[str, Any], answers: dict[str, Any] | None, known: list[str] | None = None) -> dict[str, Any]:
    """Answers to the plan's questions change the plan in place and clear the question."""
    if not answers:
        return plan
    known = list(known or [])
    for key, value in answers.items():
        if key in ("collection", "batch") and value:
            slot = next((c for c in plan["collections"] if c["role"] == "batch"), None)
            if slot is None:
                slot = {"name": None, "count": None, "role": "batch"}
                plan["collections"].insert(0, slot)
            slot["name"] = str(value)
            if "reference-images" not in plan["steps"]:
                plan["steps"].insert(0, "reference-images")
            plan["unknown_collections"] = []
        elif key in ("persona", "face", "clothes") and value:
            slot = next((c for c in plan["collections"] if c["role"] in ("face", "clothes")), None)
            if slot is None:
                slot = {"name": None, "count": None, "role": "face"}
                plan["collections"].append(slot)
            slot["name"] = str(value)
        elif key == "slides":
            plan["params"].setdefault("carousel", {})["slides"] = int(value)
        elif key in ("kind", "step") and value:
            step = str(value)
            if split_each(step)[0] not in [split_each(s)[0] for s in plan["steps"]]:
                plan["steps"] = [s for s in plan["steps"] if s != "nano-banana-2"] if step != "nano-banana-2" else plan["steps"]
                plan["steps"].insert(1 if plan["steps"][:1] == ["reference-images"] else 0, step)
            plan["inferred"] = True
        elif key == "each" and value:
            for s in str(value).split(","):
                s = s.strip()
                plan["steps"] = [f"{x}{EACH_SUFFIX}" if x == s else x for x in plan["steps"]]
    plan["questions"] = [q for q in plan["questions"] if q["key"] not in answers
                         and not (q["key"] == "collection" and not plan["unknown_collections"])
                         and not (q["key"] == "kind" and plan["inferred"])]
    return plan


def steps_from_brief(brief: str, known: list[str] | None = None) -> list[str]:
    """The step list a brief asks for, `@each` included. See parse_brief for the rest."""
    return parse_brief(brief, known)["steps"]


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "workflow"


RUN_MODES = ("dry-run", "stage-approval", "auto")


def split_each(step: str) -> tuple[str, bool]:
    """`carousel@each` -> ("carousel", True); `carousel` -> ("carousel", False)."""
    s = str(step)
    if s.endswith(EACH_SUFFIX):
        return s[: -len(EACH_SUFFIX)], True
    return s, False


def is_each(node: dict[str, Any]) -> bool:
    return bool((node.get("data") or {}).get("each"))


def iterated_port(node: dict[str, Any], cat: dict[str, Any]) -> str | None:
    """The input port a fan-out node loops over: `data.each_port`, else the first required
    image or video input. None when the node has no such port."""
    spec = cat["by_kind"].get(node.get("kind"))
    if not spec:
        return None
    want = (node.get("data") or {}).get("each_port")
    if want:
        return want if any(p["id"] == want for p in spec["inputs"]) else None
    for p in spec["inputs"]:
        if p.get("optional"):
            continue
        if p["type"] in ("image", "video") or p["id"] == "media":
            return p["id"]
    return None


def _node_key(node: dict[str, Any]) -> tuple[Any, ...]:
    """What makes two nodes of one kind distinct: the scene, shot, variant and role they serve.

    A brief or an idea never sets these, so those workflows keep one node per kind. The
    director engine sets them, so a workflow can hold twenty angle nodes of one generator."""
    d = node.get("data") or {}
    return (node["kind"], d.get("scene"), d.get("shot"), d.get("variant"), d.get("role"))


class _Graph:
    """The wiring shared by `author` (a fresh graph) and `extend` (more steps on a saved one).

    Nodes are `n1, n2, ...`, edges `e1, e2, ...`; on an existing graph numbering continues
    after the highest id already used, so nothing saved is renamed."""

    def __init__(self, cat: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]],
                 gaps: list[dict[str, str]], language: str | None = None,
                 params: dict[str, dict[str, Any]] | None = None) -> None:
        self.cat, self.nodes, self.edges, self.gaps = cat, nodes, edges, gaps
        self.language = language
        self.params = {cat["by_step"][s]["kind"] if s in cat["by_step"] else s: dict(v) for s, v in (params or {}).items()}
        self.next_node = 1 + max([int(m.group(1)) for n in nodes if (m := re.fullmatch(r"n(\d+)", n["id"]))] or [0])
        self.next_edge = 1 + max([int(m.group(1)) for e in edges if (m := re.fullmatch(r"e(\d+)", e["id"]))] or [0])
        self.added: list[str] = []

    def _node_id(self) -> str:
        ids = {n["id"] for n in self.nodes}
        while f"n{self.next_node}" in ids:
            self.next_node += 1
        nid = f"n{self.next_node}"
        self.next_node += 1
        return nid

    def _edge_id(self) -> str:
        ids = {e["id"] for e in self.edges}
        while f"e{self.next_edge}" in ids:
            self.next_edge += 1
        eid = f"e{self.next_edge}"
        self.next_edge += 1
        return eid

    def add(self, kind: str, each: bool = False) -> dict[str, Any]:
        spec = self.cat["by_kind"][kind]
        params = {p["key"]: p["default"] for p in spec.get("params", []) if "default" in p}
        if self.language and any(p["key"] == "language" for p in spec.get("params", [])):
            params["language"] = self.language
        known_keys = {p["key"] for p in spec.get("params", [])}
        for key, value in self.params.get(kind, {}).items():
            if key in known_keys or not spec.get("params"):
                params[key] = value
        node = {"id": self._node_id(), "kind": kind, "position": {"x": 0, "y": 0}, "data": {"params": params}}
        if each:
            node["data"]["each"] = True
        self.nodes.append(node)
        self.added.append(node["id"])
        if spec["backend"]["kind"] == "gap":
            self.gaps.append({"node": node["id"], "step": kind, "reason": spec["backend"]["reason"]})
        return node

    def unmapped(self, step: str) -> dict[str, Any]:
        node = {"id": self._node_id(), "kind": "unmapped", "position": {"x": 0, "y": 0}, "data": {"step": step, "params": {}}}
        self.nodes.append(node)
        self.added.append(node["id"])
        self.gaps.append({"node": node["id"], "step": step, "reason": f"no catalogue node runs '{step}' yet"})
        return node

    def outputs_of(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        spec = self.cat["by_kind"].get(node["kind"])
        return spec["outputs"] if spec else []

    def link(self, src: dict[str, Any], out: dict[str, Any], target: dict[str, Any], port: str) -> None:
        self.edges.append({"id": self._edge_id(), "source": src["id"], "sourceHandle": out["id"],
                           "target": target["id"], "targetHandle": port, "type": out["type"]})

    def connect(self, target: dict[str, Any]) -> None:
        cat, nodes = self.cat, self.nodes
        for port in cat["by_kind"][target["kind"]]["inputs"]:
            src = None
            for cand in reversed(nodes[:nodes.index(target)]):
                out = next((o for o in self.outputs_of(cand) if _accepts(port, o["type"], cat)), None)
                if out:
                    src = (cand, out)
                    break
            if src is None:
                if port.get("optional"):
                    continue
                want = cat["media_ports"]["accepts"][0] if port["id"] == "media" else port["type"]
                if want in PRODUCER_FOR_TYPE:
                    # a character is made, not uploaded: insert the step that makes one
                    prod = self.add(PRODUCER_FOR_TYPE[want])
                    nodes.remove(prod)
                    nodes.insert(nodes.index(target), prod)
                    self.connect(prod)
                    self.link(prod, cat["by_kind"][prod["kind"]]["outputs"][0], target, port["id"])
                    continue
                if want not in INPUT_FOR_TYPE:
                    self.gaps.append({"node": target["id"], "step": target["kind"],
                                      "reason": f"needs a {want} input that no earlier step produces"})
                    continue
                inp = self.add(INPUT_FOR_TYPE[want])
                nodes.remove(inp)
                nodes.insert(nodes.index(target), inp)
                src = (inp, cat["by_kind"][inp["kind"]]["outputs"][0])
            self.link(src[0], src[1], target, port["id"])

    def add_steps(self, steps: list[str]) -> list[str]:
        """Steps become wired nodes; a kind already present (with no scene, shot, variant or
        role) is not added twice. Returns the steps that were skipped for that reason."""
        skipped: list[str] = []
        for raw in steps:
            step, each = split_each(raw)
            spec = self.cat["by_step"].get(step)
            if spec is None:
                self.unmapped(step)
                continue
            if any(_node_key(n) == (spec["kind"], None, None, None, None) for n in self.nodes):
                skipped.append(raw)
                continue
            node = self.add(spec["kind"], each=each)
            if step != spec["kind"]:
                node["data"]["alias"] = step   # the step name the brief used (character-swap on klein-headswap)
            self.connect(node)
        return skipped

    def has_publisher(self) -> bool:
        return any(self.cat["by_kind"].get(n["kind"], {}).get("category") == "publish" for n in self.nodes)

    def makes_media(self) -> bool:
        return any(o["type"] in ("image", "video") for n in self.nodes for o in self.outputs_of(n))


def author(steps: list[str], title: str, client: str, source: dict[str, Any],
           language: str | None = None, cat: dict[str, Any] | None = None,
           params: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Steps become a wired graph. `params` are per-step overrides, `{"carousel": {"slides": 10}}`,
    applied only to keys the catalogue declares for that node."""
    cat = cat or load_catalog()
    g = _Graph(cat, [], [], [], language=language, params=params)
    g.add_steps(steps)
    if not g.has_publisher() and g.makes_media():
        g.connect(g.add("export"))
    layout(g.nodes, g.edges)
    return {"version": 1, "id": _slug(title), "title": title, "client": client, "source": source,
            "created": date.today().isoformat(),
            "consent_required": any(cat["by_kind"].get(n["kind"], {}).get("consent") for n in g.nodes),
            "nodes": g.nodes, "edges": g.edges, "gaps": g.gaps}


def _ancestors(node_id: str, edges: list[dict[str, Any]]) -> set[str]:
    seen: set[str] = set()
    frontier = [node_id]
    while frontier:
        cur = frontier.pop()
        for e in edges:
            if e["target"] == cur and e["source"] not in seen:
                seen.add(e["source"])
                frontier.append(e["source"])
    return seen


def extend(wf: dict[str, Any], steps: list[str], cat: dict[str, Any] | None = None,
           params: dict[str, dict[str, Any]] | None = None, language: str | None = None,
           label: str | None = None) -> dict[str, Any]:
    """Append steps to a saved workflow: the "Continue with" action.

    Existing node ids, edges, `each` flags, picks and results are untouched. New steps take
    their inputs from the latest earlier node that produces the right type, exactly as
    `author` wires a fresh brief; missing inputs become placeholder input nodes. If the new
    steps produce media that no publisher consumes, the workflow's export is re-pointed
    at it when the new media descends from what it exported before, otherwise a new export
    ends the new branch. A workflow with stages gets one more stage for the new nodes.
    Returns a new workflow dict; `source.extended` lists what each extension added."""
    cat = cat or load_catalog()
    out = copy.deepcopy(wf)
    nodes, edges, gaps = out["nodes"], out["edges"], out.setdefault("gaps", [])
    g = _Graph(cat, nodes, edges, gaps, language=language, params=params)
    skipped = g.add_steps(steps)
    added = list(g.added)
    new_nodes = [n for n in nodes if n["id"] in added]

    final = _final_media(new_nodes, edges, cat)
    if final:
        by_id = {n["id"]: n for n in nodes}
        fed = {e["source"] for e in edges
               if e["target"] in by_id and cat["by_kind"].get(by_id[e["target"]]["kind"], {}).get("category") == "publish"}
        if final[0]["id"] not in fed:
            publishers = [n for n in nodes if n["id"] not in added
                          and cat["by_kind"].get(n["kind"], {}).get("category") == "publish"]
            repointed = False
            lineage = _ancestors(final[0]["id"], edges)
            for pub in publishers:
                port = next((p for p in cat["by_kind"][pub["kind"]]["inputs"] if p["id"] == "media" or p["type"] in ("image", "video")), None)
                if not port or not _accepts(port, final[1]["type"], cat):
                    continue
                incoming = [e for e in edges if e["target"] == pub["id"] and e["targetHandle"] == port["id"]]
                if incoming and all(e["source"] in lineage for e in incoming):
                    for e in incoming:
                        e["source"], e["sourceHandle"], e["type"] = final[0]["id"], final[1]["id"], final[1]["type"]
                    repointed = True
                    break
            if not repointed:
                exp = g.add("export")
                g.link(final[0], final[1], exp, "media")
                added.append(exp["id"])
                new_nodes.append(exp)

    if out.get("stages"):
        order = max((s.get("order", 0) for s in out["stages"]), default=0) + 1
        sid = f"extend{order}"
        out["stages"].append({"id": sid, "label": label or ", ".join(split_each(s)[0] for s in steps), "order": order})
        for n in new_nodes:
            n["data"]["stage"] = sid
        layout_lanes(nodes, edges, out["stages"])
    else:
        layout(nodes, edges)
    out["consent_required"] = any(cat["by_kind"].get(n["kind"], {}).get("consent") for n in nodes)
    out.setdefault("source", {}).setdefault("extended", []).append(
        {"steps": list(steps), "added": added, "skipped": skipped, "on": date.today().isoformat()})
    out["updated"] = date.today().isoformat()
    return out


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
        # a depth column with many siblings (twenty angles) becomes a grid, ROWS deep, and the
        # columns to its right move over so nothing overlaps
        ROWS = 4
        per_col: dict[int, int] = {}
        for n in lanes[lane]:
            per_col[depth[n["id"]]] = per_col.get(depth[n["id"]], 0) + 1
        x_of: dict[int, int] = {}
        x = 80
        for col in sorted(per_col):
            x_of[col] = x
            x += 320 * max(1, -(-per_col[col] // ROWS))
        seen: dict[int, int] = {}
        tallest = 1
        for n in lanes[lane]:
            col = depth[n["id"]]
            i = seen.get(col, 0)
            seen[col] = i + 1
            n["position"] = {"x": x_of[col] + (i // ROWS) * 320, "y": y + (i % ROWS) * 210}
            tallest = max(tallest, min(per_col[col], ROWS))
        y += 260 + (tallest - 1) * 210


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
        d = n.get("data") or {}
        if "each" in d and not isinstance(d["each"], bool):
            problems.append(f"{n['id']}: each must be true or false")
        elif is_each(n):
            if be["kind"] not in EACH_BACKENDS:
                problems.append(f"{n['id']}: a {be['kind']} step cannot fan out per item")
            port = iterated_port(n, cat)
            if port is None:
                problems.append(f"{n['id']}: fans out per item but has no image or video input to iterate"
                                + (f" (each_port {d['each_port']!r} is not an input)" if d.get("each_port") else ""))
            elif not any(e["target"] == n["id"] and e["targetHandle"] == port for e in wf.get("edges", [])):
                problems.append(f"{n['id']}: fans out per item but nothing feeds its {port} port")
        if spec.get("category") == "decide":
            k = d.get("params", {}).get("k")
            feeders = [ids[e["source"]] for e in wf.get("edges", []) if e["target"] == n["id"] and e["source"] in ids]
            offered = sum(int((f.get("data") or {}).get("variant_count") or 1) for f in feeders)
            # a fan-out feeder offers one set per item, and the item count is known only at run time
            if feeders and isinstance(k, (int, float)) and k > offered and not any(is_each(f) for f in feeders):
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


def _split_shared_inputs(wf: dict[str, Any], cat: dict[str, Any], collections: list[dict[str, Any]]) -> None:
    """A swap needs the images to change and the face to put in; a wardrobe step needs the
    image and the clothes. When two required image ports of one node were wired to the same
    input folder, the second gets its own placeholder input (named after the port), filled
    from the brief's second collection when one was named."""
    by_id = {n["id"]: n for n in wf["nodes"]}
    spare = [c for c in collections if c["role"] in ("face", "clothes")]
    for node in list(wf["nodes"]):
        spec = cat["by_kind"].get(node["kind"])
        if not spec:
            continue
        seen: dict[str, str] = {}
        for port in spec["inputs"]:
            if port.get("optional") or port["type"] not in ("image", "video"):
                continue
            edge = next((e for e in wf["edges"] if e["target"] == node["id"] and e["targetHandle"] == port["id"]), None)
            if not edge:
                continue
            src = by_id.get(edge["source"])
            if not src or cat["by_kind"].get(src["kind"], {}).get("category") != "inputs":
                continue
            if edge["source"] in seen.values():
                kind = INPUT_FOR_TYPE[port["type"]]
                nid = f"n{1 + max([int(m.group(1)) for n in wf['nodes'] if (m := re.fullmatch(r'n(\d+)', n['id']))] or [0])}"
                params = {p["key"]: p["default"] for p in cat["by_kind"][kind].get("params", []) if "default" in p}
                extra = {"id": nid, "kind": kind, "position": {"x": 0, "y": 0},
                         "data": {"params": params, "role": port["id"]}}
                if spare:
                    c = spare.pop(0)
                    if c.get("name"):
                        params["folder"] = f"brands/{wf['client']}/references/{c['name']}"
                        extra["data"]["collection"] = c["name"]
                wf["nodes"].insert(wf["nodes"].index(src) + 1, extra)
                by_id[nid] = extra
                edge["source"] = nid
                edge["sourceHandle"] = cat["by_kind"][kind]["outputs"][0]["id"]
            seen[port["id"]] = edge["source"]


def from_brief(brief: str, client: str, title: str | None = None, plan: dict[str, Any] | None = None,
               answers: dict[str, Any] | None = None, cat: dict[str, Any] | None = None) -> dict[str, Any]:
    """A plain-language brief becomes a workflow. `plan` is a `parse_brief` result to reuse;
    `answers` fill the plan's questions (collection, persona, slides, kind)."""
    cat = cat or load_catalog()
    known = known_collections(client)
    plan = plan or parse_brief(brief, known, cat)
    apply_answers(plan, answers, known)
    wf = author(plan["steps"], title or brief[:60], client, {"brief": brief}, language=plan.get("language"),
                cat=cat, params=plan.get("params"))
    brief_node = next((n for n in wf["nodes"] if n["kind"] == "brief"), None)
    if brief_node:
        brief_node["data"]["params"]["text"] = brief
    batch = next((c for c in plan.get("collections", []) if c["role"] == "batch"), None)
    refs = [n for n in wf["nodes"] if n["kind"] == "reference-images"]
    if batch and refs:
        node = refs[0]
        if batch.get("name"):
            node["data"]["params"]["folder"] = f"brands/{client}/references/{batch['name']}"
            node["data"]["collection"] = batch["name"]
        if batch.get("count"):
            node["data"]["expected_count"] = int(batch["count"])
    _split_shared_inputs(wf, cat, plan.get("collections", []))
    layout(wf["nodes"], wf["edges"])
    if plan.get("continuations"):
        wf["source"]["continuations"] = plan["continuations"]
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
