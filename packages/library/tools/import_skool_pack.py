"""Import the Icekiub Skool classroom we bought into the repo.

Input is what a person downloaded, not a scrape: the lesson capture
(`icekiub-skool-lessons.json`) and each lesson's files, staged one folder per lesson under
Documents/COMFY/Icekiub-Skool. Re-running is safe; identical bytes are recognised by hash.

- Workflows go to workflows/icekiub/ and are registered with their Skool lesson as source.
- Icekiub's custom node packs go to workflows/icekiub/nodes/.
- Model files (.pt, .safetensors, ...) never enter git. They stay where they were downloaded.
- comfyui-unsafe-torch is never imported: it forces torch.load(weights_only=False) for the
  whole ComfyUI process, so any model file could run code.
- docs/business/ICEKIUB-SKOOL.md is regenerated from the capture and the import.

Paid material, internal production only: never resold, bundled or published.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import register_workflow as rw  # noqa: E402

REPO = rw.REPO
DEST = REPO / "workflows" / "icekiub"
NODES = DEST / "nodes"
LESSONS_OUT = DEST / "skool" / "lessons.json"
DOC = REPO / "docs" / "business" / "ICEKIUB-SKOOL.md"
DEFAULT_SOURCE = Path.home() / "Documents" / "COMFY" / "Icekiub-Skool"
CAPTURE = "icekiub-skool-lessons.json"

LESSON_DIR = {
    "NEW - Icy realism H3 Loras Checkpoints": "h3-realism-loras-checkpoints",
    "Updated Icy-Hider for subs": "custom-nodes/icy-hider",
    "(BEST) SCAIL 2 Motion Control": "video-related/scail-2-motion-control",
    "ICY ANIMATE WORKFLOW": "video-related/icy-animate",
    "WAN 2.2 Lora Based Faceswap": "video-related/wan22-lora-faceswap",
    "WAN 2.2 IMAGE TO VIDEO": "video-related/wan22-image-to-video",
    "NEW - Minimax reference based Image generation": "content-generation/minimax-reference-image-generation",
    "NEW - Reference based character sheet": "content-generation/reference-character-sheet",
    "Icy reference motion control pack (SFW)": "content-generation/reference-motion-control-pack-sfw",
    "NEW BEST - Icy Krea2": "content-generation/icy-krea2",
    "Consistent Background Klein workflow": "content-generation/consistent-background-klein",
    "ZIB + ZIT with controlnet workflow": "content-generation/zib-zit-controlnet",
    "Unc. I2I workflow (Klein) UPDATED": "content-generation/unc-i2i-klein",
    "Infinite wardrobe for your character (Multi Ref)": "content-generation/infinite-wardrobe-multi-ref",
    "IG Carousel pose generator": "content-generation/ig-carousel-pose-generator",
    "NSFW Surgery WF (SDXL Inpaint)": "content-generation/nsfw-surgery-sdxl-inpaint",
    "NEW - AI influencer dataset AIO (Klein)": "dataset-related/ai-influencer-dataset-aio-klein-v2",
    # renamed on Skool 2026-09-16 when the Krea 2 version above replaced them
    "OLD- -AI influencer dataset AIO (Klein)": "dataset-related/ai-influencer-dataset-aio-klein",
    "Old - AI influencer dataset AIO (Qwen)": "dataset-related/ai-influencer-dataset-aio-qwen",
    "Change faces with QWEN IMAGE EDIT": "dataset-related/qwen-image-edit-faceswap",
    "Uncensored captioning for datasets": "dataset-related/uncensored-captioning",
    "Klein Watermark removal": "dataset-related/klein-watermark-removal",
    "Edit ANYTHING (Phr00t Qwen image edit)": "dataset-related/edit-anything-phr00t-qwen",
}
# 18+ material: fictional adults only, separate entity, never on the Ongea Pesa or EPALLE brands.
ADULT = {"NSFW Surgery WF (SDXL Inpaint)", "Unc. I2I workflow (Klein) UPDATED",
         "Edit ANYTHING (Phr00t Qwen image edit)"}
# Steps that put a face or a character into an image or video.
CONSENT = {"ICY ANIMATE WORKFLOW", "WAN 2.2 Lora Based Faceswap", "Change faces with QWEN IMAGE EDIT",
           "Unc. I2I workflow (Klein) UPDATED", "NEW - Minimax reference based Image generation",
           "NEW - Reference based character sheet", "NEW - AI influencer dataset AIO (Klein)",
           "OLD- -AI influencer dataset AIO (Klein)", "Old - AI influencer dataset AIO (Qwen)",
           "(BEST) SCAIL 2 Motion Control"}
NEVER_IMPORT = {"comfyui-unsafe-torch": "patches torch.load so any model file can run code"}
SKIP_DIRS = {"__pycache__", ".git", ".zcode"}
MODEL_EXT = {".pt", ".pth", ".safetensors", ".ckpt", ".gguf", ".bin", ".onnx"}


class SkoolImportError(RuntimeError):
    pass


def safe_name(name: str) -> str:
    """'Motion Control Icy -SUBS.json' -> 'Motion_Control_Icy_-SUBS.json', matching existing files."""
    stem, _, ext = name.rpartition(".")
    stem = re.sub(r"\s*\(\d+\)$", "", stem.strip())
    stem = re.sub(r"\s+", "_", stem)
    stem = re.sub(r"[^A-Za-z0-9._+\-]", "", stem)
    return f"{stem}.{ext}"


def _skipped(p: Path, root: Path) -> bool:
    return any(part in SKIP_DIRS for part in p.relative_to(root).parts)


def workflow_files(d: Path) -> list[Path]:
    out = []
    for p in sorted(d.rglob("*.json")):
        if _skipped(p, d):
            continue
        try:
            rw.analyse(p.read_bytes())
        except (rw.NotAWorkflow, json.JSONDecodeError, UnicodeDecodeError):
            continue
        out.append(p)
    return out


def node_packs(d: Path) -> list[Path]:
    packs: list[Path] = []
    for init in sorted(d.rglob("__init__.py"), key=lambda p: len(p.parts)):
        pack = init.parent
        if _skipped(pack, d) or any(pack.is_relative_to(q) for q in packs):
            continue
        packs.append(pack)
    return packs


def copy_pack(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=lambda _dir, names: [
        n for n in names if n in SKIP_DIRS or Path(n).suffix.lower() in MODEL_EXT])


def run(source: Path = DEFAULT_SOURCE, dry_run: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    capture = source / CAPTURE
    if not capture.exists():
        raise SkoolImportError(f"no lesson capture at {capture}")
    doc = json.loads(capture.read_text(encoding="utf-8"))
    man = json.loads(rw.MANIFEST.read_text(encoding="utf-8"))
    by_sha = {w["sha256"]: w for w in man["workflows"]}
    report: list[dict[str, Any]] = []
    for lesson in doc["lessons"]:
        if lesson.get("section"):
            continue
        title = lesson["title"]
        if title not in LESSON_DIR:
            raise SkoolImportError(f"no staging folder mapped for lesson {title!r}")
        entry: dict[str, Any] = {"lesson": lesson, "workflows": [], "packs": [], "held_back": []}
        report.append(entry)
        d = source / LESSON_DIR[title]
        expected = [r["file_name"] for r in lesson.get("resources", []) if r.get("file_name")]
        if expected and not (d.exists() and any(d.iterdir())):
            entry["held_back"].append("not downloaded yet: " + ", ".join(expected))
            continue
        if not d.exists():
            continue
        for p in workflow_files(d):
            raw = p.read_bytes()
            info = rw.analyse(raw)
            known = by_sha.get(info["sha256"])
            if known:
                entry["workflows"].append({**known, "status": "already held"})
                continue
            target = DEST / safe_name(p.name)
            if target.exists() and target.read_bytes() != raw:
                raise SkoolImportError(f"{target.name} already exists with different bytes; rename one")
            if dry_run:
                reg = {**info, "canonical": f"workflows/icekiub/{target.name}"}
            else:
                target.write_bytes(raw)
                reg = rw.register(target, [f"skool:{lesson['lesson_url']}", f"skool-file:{p.name}"])
            by_sha[info["sha256"]] = reg
            entry["workflows"].append({**reg, "status": "imported"})
        for pack in node_packs(d):
            if pack.name in NEVER_IMPORT:
                entry["held_back"].append(f"{pack.name} ({NEVER_IMPORT[pack.name]})")
                continue
            if not dry_run:
                copy_pack(pack, NODES / pack.name)
            entry["packs"].append(pack.name)
        models = sorted({f.name for f in d.rglob("*") if f.suffix.lower() in MODEL_EXT})
        if models:
            entry["held_back"].append("model files kept out of git: " + ", ".join(models))
    if not dry_run:
        LESSONS_OUT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(capture, LESSONS_OUT)
        DOC.write_text(render(doc, report), encoding="utf-8")
    return doc, report


def _gate(title: str) -> list[str]:
    g = []
    if title in ADULT:
        g.append("**18+ gated.** Fictional adults only, separate entity, never on Ongea Pesa or EPALLE.")
    if title in CONSENT:
        g.append("**Consent required.** Owned, consented or fictional likenesses only.")
    return g


def render(doc: dict[str, Any], report: list[dict[str, Any]]) -> str:
    imported = sum(1 for e in report for w in e["workflows"] if w["status"] == "imported")
    held = sum(1 for e in report for w in e["workflows"] if w["status"] == "already held")
    packs = sorted({p for e in report for p in e["packs"]})
    L = ["# Icekiub Skool classroom", "",
         f"Generated by `packages/library/tools/import_skool_pack.py` from the lesson capture of "
         f"{doc['captured_at'][:10]}. Do not edit by hand.", "",
         "Bought material for internal production only: never resold, bundled into our own packs, "
         "or published (`docs/LICENSING.md`). Model files are not in git; the links below say where "
         "each one comes from.", "",
         f"**{len(report)} lessons, {imported + held} workflows ({imported} new, {held} we already "
         f"held), {len(packs)} node packs:** {', '.join(f'`{p}`' for p in packs)}.", "",
         "Re-import after downloading more:", "", "```bash",
         "uv run python packages/library/tools/import_skool_pack.py", "```", ""]
    section = None
    for e in report:
        les = e["lesson"]
        sec = les["path"][0] if len(les["path"]) > 1 else "Top of the classroom"
        if sec != section:
            section = sec
            L += [f"## {sec}", ""]
        L += [f"### {les['title']}", ""]
        L += [f"- {g}" for g in _gate(les["title"])]
        if les.get("video_link"):
            L.append(f"- Video: {les['video_link']}" + (f" ({les['video_minutes']} min)" if les.get("video_minutes") else ""))
        elif les.get("hosted_video"):
            L.append("- Video: hosted on Skool" + (f" ({les['video_minutes']} min)" if les.get("video_minutes") else ""))
        for w in e["workflows"]:
            L.append(f"- Workflow `{w['canonical']}`: {w['node_count']} nodes, {w['status']}")
            L.append(f"  - Node packs: {', '.join(w['node_packs'])}")
            if w.get("unattributed_node_types"):
                L.append(f"  - Node types with no known pack: {', '.join(w['unattributed_node_types'])}")
            if w.get("models"):
                L.append(f"  - Models: {', '.join(w['models'])}")
        if e["packs"]:
            L.append(f"- Custom nodes added: {', '.join(f'`workflows/icekiub/nodes/{p}`' for p in e['packs'])}")
        if les.get("links"):
            L.append("- Links:")
            L += [f"  - {u}" for u in les["links"]]
        L += [f"- Held back: {h}" for h in e["held_back"]]
        if les.get("description"):
            L += ["", "Lesson notes:", ""]
            L += [f"> {line}" if line.strip() else ">" for line in les["description"].splitlines()]
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                    help="folder with icekiub-skool-lessons.json and one folder per lesson")
    ap.add_argument("--dry-run", action="store_true", help="report without writing anything")
    args = ap.parse_args()
    try:
        _, report = run(args.source, args.dry_run)
    except SkoolImportError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for e in report:
        new = [w for w in e["workflows"] if w["status"] == "imported"]
        print(f"{e['lesson']['title']}: {len(new)} new, {len(e['workflows']) - len(new)} held, "
              f"{len(e['packs'])} packs, {len(e['held_back'])} held back")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
