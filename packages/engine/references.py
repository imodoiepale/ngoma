"""References: what a folder of images or clips lets the engine do, and under what rights.

A reference collection is a folder `brands/<brand>/references/<name>/` holding media plus
a `collection.json` that says how it may be used:

    use     inspiration   shapes prompts only (mood boards, harvested pins)
            data          fed straight into a node port (a face, an outfit, a room)
    rights  owned | licensed | unclear   -- unclear rights can only inspire
    consent a real person's likeness, released in writing

Three questions this module answers, offline:

    possibilities   every node port a reference can drive, with the gate it must pass
    gate            may THIS collection feed THIS port?
    fragments       what a mood board says, as prompt fragments (from vision.jsonl)

`pull` harvests search terms or URLs into a collection through the existing Pinterest
and Instagram harvesters. It is dry-run unless asked otherwise, and nothing here ever
uploads, publishes or calls a model.

    uv run --with pyyaml packages/engine/references.py possibilities
    uv run --with pyyaml packages/engine/references.py list --brand epalle
    uv run --with pyyaml packages/engine/references.py pull --brand epalle --name mood-neon "neon street portrait"
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


from brief import RIGHTS, USES, RefCollection  # noqa: E402  (the engine's brief module, not ingest's schema)

REPO = HERE.parents[1]
BRANDS = REPO / "brands"
CATALOG = REPO / "packages" / "studio-ui" / "catalog" / "nodes.json"
POSSIBILITIES_DOC = REPO / "docs" / "engine" / "POSSIBILITIES.md"
COLLECTION_FILE = "collection.json"
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"}
VIDEO_EXT = {".mp4", ".mov"}
REF_TYPES = ("image", "video", "audio")

GATE_DATA = "owned or licensed data"
GATE_CONSENT = "consent"
GATE_INSPIRATION = "inspiration only (mood boards)"


class ReferenceError(ValueError):
    pass


# ---------------------------------------------------------------- collections on disk

def collection_dir(brand: str, name: str) -> Path:
    return BRANDS / brand / "references" / name


def write_collection(brand: str, name: str, *, use: str, rights: str, kind: str = "image",
                     consent: bool = False, source: str = "manual", notes: Iterable[str] = ()) -> dict[str, Any]:
    if use not in USES or rights not in RIGHTS:
        raise ReferenceError(f"use must be one of {USES} and rights one of {RIGHTS}")
    if kind not in REF_TYPES:
        raise ReferenceError(f"kind must be one of {REF_TYPES}")
    folder = collection_dir(brand, name)
    folder.mkdir(parents=True, exist_ok=True)
    doc = {"name": name, "use": use, "rights": rights, "kind": kind, "consent": bool(consent),
           "source": source, "created": date.today().isoformat(), "notes": list(notes)}
    (folder / COLLECTION_FILE).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def _media_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXT)


def _rel(p: Path) -> str:
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def read_collection(brand: str, name: str) -> RefCollection:
    """A folder without collection.json is still a collection, on the most cautious terms:
    inspiration only, rights unclear, no consent."""
    folder = collection_dir(brand, name)
    if not folder.is_dir():
        raise ReferenceError(f"no reference collection at {_rel(folder)}")
    meta: dict[str, Any] = {}
    f = folder / COLLECTION_FILE
    if f.exists():
        meta = json.loads(f.read_text(encoding="utf-8"))
    files = _media_files(folder)
    kind = meta.get("kind") or ("video" if files and all(p.suffix.lower() in VIDEO_EXT for p in files) else "image")
    return RefCollection(name=name, kind=kind, use=meta.get("use", "inspiration"),
                         rights=meta.get("rights", "unclear"), consent=bool(meta.get("consent", False)),
                         path=_rel(folder), count=len(files))


def list_collections(brand: str) -> list[RefCollection]:
    root = BRANDS / brand / "references"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and ((d / COLLECTION_FILE).exists() or (d / "posts.jsonl").exists() or _media_files(d)):
            out.append(read_collection(brand, d.name))
    return out


# ---------------------------------------------------------------- pulling references in

def search_url(term_or_url: str, source: str = "pinterest") -> str:
    t = term_or_url.strip()
    if "http" in t:
        return t
    if source == "pinterest":
        return f"https://www.pinterest.com/search/pins/?q={quote_plus(t)}"
    return t


def _load_harvester(name: str) -> Any:
    """packages/ingest and packages/engine both ship a `schema` module. Load the harvester by
    path with the ingest schema in place, then put the engine's back."""
    import importlib.util
    ingest = REPO / "packages" / "ingest"
    saved = sys.modules.get("schema")

    def _load(modname: str, path: Path) -> Any:
        spec = importlib.util.spec_from_file_location(modname, path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[modname] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    try:
        sys.modules["schema"] = _load("ingest_schema", ingest / "schema.py")
        return _load(f"ingest_{name}", ingest / f"{name}.py")
    finally:
        if saved is not None:
            sys.modules["schema"] = saved
        else:
            sys.modules.pop("schema", None)


def pull(brand: str, name: str, terms_or_urls: list[str], *, source: str = "pinterest",
         use: str = "inspiration", rights: str = "unclear", cookies_from: str | None = None,
         dry_run: bool = True) -> dict[str, Any]:
    """Harvest into brands/<brand>/references/<name>. Dry-run by default: the harvesters'
    own dry-run path, which downloads nothing."""
    if not terms_or_urls:
        raise ReferenceError("give at least one search term, URL or handle")
    notes = [f"source: {source}", f"terms: {', '.join(terms_or_urls)}"]
    if source == "pinterest":
        pin_harvest = _load_harvester("pin_harvest")
        urls = [search_url(t, "pinterest") for t in terms_or_urls]
        report = pin_harvest.harvest(urls, brand, name, cookies_from=cookies_from, dry_run=dry_run)
    elif source == "instagram":
        ig_harvest = _load_harvester("ig_harvest")
        report = None
        for handle in terms_or_urls:
            handle = handle.lstrip("@")
            r = ig_harvest.harvest(handle, brand, download=not dry_run, dry_run=dry_run)
            report = report or r
            notes.append(f"instagram posts for @{handle} land in brands/{brand}/references/{handle}")
    else:
        raise ReferenceError(f"unknown source {source!r}; use pinterest or instagram")
    if dry_run:
        notes.append("dry run: nothing downloaded and no collection.json written")
        col = RefCollection(name=name, use=use, rights=rights, path=_rel(collection_dir(brand, name)))
    else:
        write_collection(brand, name, use=use, rights=rights, source=source, notes=notes)
        col = read_collection(brand, name)
    return {"report": asdict(report), "collection": asdict(col), "notes": notes}


# ---------------------------------------------------------------- the gate

def gate(col: RefCollection, port_type: str, needs_consent: bool) -> tuple[bool, str]:
    """May this collection feed a port of this type? `media` ports take image or video."""
    if col.rights not in ("owned", "licensed"):
        return False, f"{col.name}: rights are {col.rights}, so it can only inspire (mood board, prompt fragments)"
    if col.use != "data":
        return False, f"{col.name}: marked as inspiration, not data; set use: data to feed a node"
    if port_type == "media":
        if col.kind not in ("image", "video"):
            return False, f"{col.name}: a media port takes images or video, not {col.kind}"
    elif port_type in REF_TYPES and col.kind != port_type:
        return False, f"{col.name}: holds {col.kind}, the port wants {port_type}"
    if needs_consent and not col.consent:
        return False, f"{col.name}: a face or character port needs a written consent release"
    return True, f"{col.name}: {col.rights} data" + (", consent on file" if needs_consent else "")


# ---------------------------------------------------------------- mood boards to prompt fragments

def _colour_name(hex_: str) -> str:
    """A plain English name for a colour, so a fragment reads as direction, not as a code."""
    import colorsys
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, sat, val = colorsys.rgb_to_hsv(r, g, b)
    if val < 0.15:
        return "near-black"
    if sat < 0.12:
        return "white" if val > 0.85 else "light grey" if val > 0.55 else "grey"
    hues = [(0.04, "red"), (0.10, "orange"), (0.17, "yellow"), (0.42, "green"),
            (0.55, "teal"), (0.72, "blue"), (0.83, "violet"), (0.95, "pink"), (1.01, "red")]
    base = next(n for lim, n in hues if hue < lim)
    if base in ("orange", "yellow") and val < 0.55:
        base = "brown"
    tone = "deep " if val < 0.4 else "muted " if sat < 0.35 else "pale " if val > 0.85 and sat < 0.5 else ""
    return tone + base


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def features_to_fragments(vision_jsonl: Path, min_samples: int = 1) -> list[str]:
    """Aggregate a vision.jsonl into short, deterministic prompt fragments."""
    recs: list[dict[str, Any]] = []
    if Path(vision_jsonl).exists():
        for line in Path(vision_jsonl).read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if len(recs) < max(1, min_samples):
        return []

    palette: Counter[str] = Counter()
    for r in recs:
        for c in (r.get("palette") or [])[:3]:
            if c.get("hex"):
                palette[c["hex"].upper()] += float(c.get("share", 0) or 0)
    top = [h for h, _ in sorted(palette.items(), key=lambda kv: (-round(kv[1], 4), kv[0]))[:3]]

    luma = _mean([float(r.get("mean_luma") or 0) for r in recs])
    contrast = _mean([float(r.get("contrast") or 0) for r in recs])
    warm = _mean([float(r.get("warm_ratio") or 0) for r in recs])
    quadrants = Counter(r["subject_quadrant"] for r in recs if r.get("subject_quadrant"))
    copy_zones = Counter(r["copy_zone"] for r in recs if r.get("copy_zone"))
    shots = [float(r["avg_shot_s"]) for r in recs if r.get("avg_shot_s")]

    frags: list[str] = []
    if top:
        frags.append("palette led by " + ", ".join(f"{_colour_name(h)} ({h})" for h in top))
    frags.append("low-key, dark frames" if luma < 85 else "high-key, bright airy frames" if luma > 170
                 else "mid-toned, balanced exposure")
    frags.append("punchy contrast" if contrast >= 50 else "soft contrast")
    frags.append("warm cast" if warm >= 0.5 else "cool cast")
    if quadrants:
        q = sorted(quadrants.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        frags.append(f"subject placed {q}")
    if copy_zones:
        z = sorted(copy_zones.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        frags.append(f"keep the {z} quiet for copy")
    if shots:
        s = _mean(shots)
        frags.append(f"fast cut rhythm, about {s:.1f}s per shot" if s < 2.0
                     else f"slow, held shots, about {s:.1f}s each")
    return frags


# ---------------------------------------------------------------- possibilities

# Where the catalogue's port names do not explain themselves: (kind, port) -> reference, drives.
CURATED: dict[tuple[str, str], tuple[str, str]] = {
    ("carousel", "image"): ("one photo of the avatar or product",
                            "bulk pose change: a whole consistent photoset from that one photo"),
    ("wardrobe", "image"): ("one photo of the person to dress", "the body that keeps its face, pose and room"),
    ("wardrobe", "clothes"): ("photos of the garments", "clothes-only change; nothing else in the frame moves"),
    ("consistent-room", "room"): ("one photo of the room or background",
                                  "the same room across every angle and scene"),
    ("image-edit", "image"): ("one image to change", "add jewellery, props, a new light or a new outfit by instruction"),
    ("klein-headswap", "face"): ("one face photo", "identity onto a body; the person must have signed a release"),
    ("klein-headswap", "image"): ("the target body shot", "the pose, outfit and room that keep their place"),
    ("faceswap", "face"): ("one face photo", "identity swap; consented faces only"),
    ("faceswap", "image"): ("the target image", "everything but the face stays"),
    ("refmod-create", "images"): ("12 or more photos of one person", "a reusable character file, no training"),
    ("dataset", "images"): ("a handful of photos of one character", "a 40-image training set and character board"),
    ("character-sheet", "image"): ("one photo", "four views of the character, ready for H3 references"),
    ("h3-reference-image", "identity"): ("a character sheet or one clear photo", "Picture 1: who the still is of"),
    ("h3-reference-image", "references"): ("outfit, pose and room photos", "Pictures 2 to 5: what the still keeps around them"),
    ("motion-control", "character"): ("one still of the character", "who performs the motion"),
    ("motion-control", "video"): ("a reference clip of the motion", "motion lifted from the clip onto the character"),
    ("motion-transfer", "image"): ("one still of the character", "who performs the motion"),
    ("motion-transfer", "motion"): ("a reference clip of the motion", "the character moves like the clip"),
    ("wan-animate", "character"): ("one still of the character", "full-body or face-only swap onto the driving clip"),
    ("wan-animate", "video"): ("a driving video", "the motion and timing the character follows"),
    ("wan-lora-faceswap", "video"): ("a source clip", "the performance that keeps its motion under a new face"),
    ("lipsync", "image"): ("one photo of the performer", "the face that sings or speaks"),
    ("lipsync", "audio"): ("the song or voice track", "audio drives a whole performance, mouth and timing"),
    ("caption-dataset", "media"): ("a folder of training images or frames", "captions for LoRA training"),
    ("image-to-video", "image"): ("one still", "a moving shot that starts from it"),
    ("long-video", "image"): ("one still", "a long, extended clip that starts from it"),
    ("character-video", "character"): ("a RefMod character", "a clip of that character"),
    ("image-hosted", "reference"): ("one reference image", "a hosted-model image that echoes it"),
    ("krea2-t2i", "pose"): ("a pose or depth reference", "composition control for the generation"),
    ("zimage-controlnet", "control"): ("a pose or edge map", "ControlNet composition for the generation"),
    ("klein-i2i", "image"): ("one reference image", "the same image recreated with the character as subject"),
    ("restore", "image"): ("an old or damaged photo", "repair, colourise and sharpen"),
    ("watermark-remove", "image"): ("an image we own or licensed", "the same image without the mark"),
    ("upscale-video", "video"): ("a finished clip", "a sharper, larger master"),
    ("compositor", "media"): ("a finished image", "exact copy, logo and palette laid on top"),
    ("transcribe", "media"): ("a clip with speech", "timed text to cut, caption or translate from"),
    ("captions", "video"): ("a finished clip", "burned-in subtitles from the script"),
    ("captions", "audio"): ("a voiceover or music track", "the soundtrack the subtitles are timed to"),
    ("cut", "video"): ("raw clips", "trimmed, looped and picked"),
}
MOOD_BOARD_ROW = {"reference_kind": "a mood board of harvested pins or clips", "node": "", "label": "(no node)",
                  "port": "", "drives": "prompt fragments only: palette, exposure, contrast, subject placement, "
                                        "copy zone, cut rhythm (features_to_fragments)",
                  "gate": GATE_INSPIRATION}

GENERIC_KIND = {"image": "one or more images", "video": "a video clip", "audio": "an audio track",
                "media": "an image or a video"}


def _load_catalog(catalog: dict[str, Any] | None) -> dict[str, Any]:
    if catalog is not None:
        return catalog
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    cat.setdefault("by_kind", {n["kind"]: n for n in cat["nodes"]})
    return cat


def is_reference_port(port: dict[str, Any]) -> bool:
    return port.get("id") == "media" or port.get("type") in REF_TYPES


def possibilities(catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every catalogue port a reference can drive, in catalogue order, plus the mood board."""
    cat = _load_catalog(catalog)
    rows = [dict(MOOD_BOARD_ROW)]
    for n in cat["nodes"]:
        for p in n.get("inputs", []):
            if not is_reference_port(p):
                continue
            ptype = "media" if p["id"] == "media" else p["type"]
            ref, drives = CURATED.get((n["kind"], p["id"]),
                                      (GENERIC_KIND[ptype] + f" for `{p['id']}`", n.get("blurb") or n["label"]))
            g = GATE_CONSENT if n.get("consent") and ptype == "image" else GATE_DATA
            rows.append({"reference_kind": ref, "node": n["kind"], "label": n["label"], "port": p["id"],
                         "drives": drives, "gate": g})
    return rows


def render_possibilities(catalog: dict[str, Any] | None = None) -> str:
    rows = possibilities(catalog)
    L = ["<!-- generated by packages/engine/references.py possibilities; edit the catalogue or CURATED, not this file -->",
         "# What a reference makes possible",
         "",
         "Every node port in `packages/studio-ui/catalog/nodes.json` that takes an image, a clip or a",
         "track, and the gate a reference collection must pass to feed it. `owned or licensed data`",
         "means `use: data` with `rights: owned|licensed`; `consent` adds a written release for the",
         "person shown; anything with unclear rights is `inspiration only` and reaches a prompt as",
         "fragments, never a port.",
         "",
         "| Reference | Node | Port | Makes possible | Gate |",
         "|---|---|---|---|---|"]
    for r in rows:
        node = f"`{r['node']}` {r['label']}" if r["node"] else r["label"]
        port = f"`{r['port']}`" if r["port"] else "—"
        L.append(f"| {r['reference_kind']} | {node} | {port} | {r['drives']} | {r['gate']} |")
    L += ["", f"{len(rows)} rows: {sum(1 for r in rows if r['gate'] == GATE_CONSENT)} need consent, "
              f"{sum(1 for r in rows if r['gate'] == GATE_DATA)} need owned or licensed data, "
              f"{sum(1 for r in rows if r['gate'] == GATE_INSPIRATION)} inspiration only.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("possibilities", help="write docs/engine/POSSIBILITIES.md")
    p = sub.add_parser("pull", help="harvest terms, URLs or handles into a collection (dry-run unless --live)")
    p.add_argument("--brand", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--source", default="pinterest", choices=("pinterest", "instagram"))
    p.add_argument("--use", default="inspiration", choices=USES)
    p.add_argument("--rights", default="unclear", choices=RIGHTS)
    p.add_argument("--cookies-from", default=None)
    p.add_argument("--live", action="store_true", help="actually download; default is a dry run")
    p.add_argument("terms", nargs="+")
    ls = sub.add_parser("list", help="collections of a brand with use, rights and count")
    ls.add_argument("--brand", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "possibilities":
        POSSIBILITIES_DOC.parent.mkdir(parents=True, exist_ok=True)
        POSSIBILITIES_DOC.write_text(render_possibilities(), encoding="utf-8")
        print(f"{_rel(POSSIBILITIES_DOC)} written ({len(possibilities())} rows)")
        return 0
    if a.cmd == "pull":
        out = pull(a.brand, a.name, a.terms, source=a.source, use=a.use, rights=a.rights,
                   cookies_from=a.cookies_from, dry_run=not a.live)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if out["report"]["status"] in ("ok", "partial") else 1
    if a.cmd == "list":
        cols = list_collections(a.brand)
        if not cols:
            print(f"no reference collections for {a.brand}")
            return 0
        for c in cols:
            print(f"{c.name:<28} {c.kind:<6} use={c.use:<12} rights={c.rights:<9} "
                  f"consent={'yes' if c.consent else 'no':<3} {c.count:>4} files")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
