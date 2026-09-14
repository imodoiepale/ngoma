#!/usr/bin/env python3
"""Plan every model the repo's workflows need, for download on the pod.

Reads workflows/manifest.json, extracts each model file together with the loader that
names it (audit_models.extract), and resolves where to fetch it, strongest evidence first:

1. an exact Hugging Face URL already in the repo: workflow notes, bought lesson notes, docs;
2. an entry already resolved in download-plan.json;
3. with --online, a filename match in the public file listings of known repos.

A creator's own trained LoRA has no public source and is `creator_private`: never swap in a
lookalike. A file whose only lead is a Civitai / ModelScope / OpenModelDB / Drive page from
the lesson it came with goes in `manual`, with those pages. Everything else is `unresolved`.

Writes infra/runpod/download-plan.json. download_planned.py (on the pod) reads `resolved`.

Usage:
    python infra/runpod/plan_models.py            # offline: repo evidence + earlier plan
    python infra/runpod/plan_models.py --online   # also match against Hugging Face listings
    python infra/runpod/plan_models.py --dry-run  # print counts, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import audit_models as am  # noqa: E402

PLAN = HERE / "download-plan.json"
MANIFEST = REPO / "workflows" / "manifest.json"
LESSONS = REPO / "workflows" / "icekiub" / "skool" / "lessons.json"
EVIDENCE_GLOBS = ("workflows/**/*.json", "docs/**/*.md", "infra/runpod/*.py",
                  "packages/library/corpus/youtube/**/*.description",
                  "packages/library/corpus/youtube/links.jsonl")
EXT = r"(?:safetensors|ckpt|pt|pth|bin|onnx|gguf|sft)"
HF_URL = re.compile(r"https://huggingface\.co/([\w.\-]+/[\w.\-]+)/(?:resolve|blob)/([\w.\-]+)/([^\s\"'<>)\]\\]+?\." + EXT + r")(?![\w])")
MANUAL_HOST = re.compile(r"https?://(?:civitai\.(?:com|red)|modelscope\.cn|openmodeldb\.info|drive\.google\.com)/")
# Names shaped like a training checkpoint from someone's own run: no public source exists.
PRIVATE_NAME = re.compile(r"^Lora_lora_|^my_first_lora|lourta|^loratest|_0{3,}\d+(?:_[a-z_]+)?\.safetensors$|merged\d", re.I)
AUTO_DOWNLOAD = {"dw-ll_ucoco_384_bs5.torchscript.pt", "yolox_l.torchscript.pt", "rife47.pth", "rife47.pt", "model.onnx"}
CREATOR_PRIVATE = {"my_first_lora_v1_000000600_low_noise.safetensors", "Lora_lora_000000600.safetensors",
                   "slop_twerk_LowNoise_merged3_7_v2.safetensors", "wan2.1_SCAIL_2_DPO_lora_bf16(1).safetensors"}
# Repos the bought and free workflows draw from, beyond resolve_models.REPOS.
EXTRA_REPOS = [
    "Comfy-Org/Krea-2", "Comfy-Org/z_image_turbo", "Comfy-Org/z_image", "Comfy-Org/Qwen-Image_ComfyUI",
    "Comfy-Org/Qwen-Image-Edit_ComfyUI", "Comfy-Org/HunyuanVideo_1.5_repackaged", "Comfy-Org/Wan_2.2_ComfyUI_Repackaged",
    "lightx2v/Qwen-Image-Lightning", "lightx2v/Wan2.2-Lightning", "lightx2v/Minimax-h3-Turbo",
    "Phr00t/Qwen-Image-Edit-Rapid-AIO", "alibaba-pai/Z-Image-Fun-Lora-Distill", "alibaba-pai/Z-Image-Fun-Controlnet-Union-2.1",
    "Owen777/UltraFlux-v1", "lodestones/Chroma1-HD", "icekiub/WAN-2.2-T2V-FP8-NON-SCALED",
    "smhfacct/Minimax-H3-fl2va-ref2va-hybrid-models", "Mamad8/MiniMax-H3-Image-VAE", "Alissonerdx/CharacterSheet",
    "Danrisi/Lenovo_Qwen", "Kaoru8/T5XXL-Unchained", "Osrivers/Qwen-Image-Lightning-8steps-V2.0-bf16.safetensors",
    "Lightricks/LTX-2.3", "Kijai/LTX2.3_comfy", "Kijai/MiniMax-H3_comfy", "lightx2v/Wan2.2-Distill-Loras",
    "depth-anything/Depth-Anything-V2-Large", "facebook/sam3", "Bingsu/adetailer", "comfyanonymous/flux_text_encoders",
    "Comfy-Org/Chroma1-HD_ComfyUI", "lodestones/chroma-debug-development-only", "Kim2091/UltraSharpV2",
    "Comfy-Org/Qwen3-VL", "Bryan32/Adetailer", "jellybox/u2net-human-seg", "Metal3d/deeplabv3p-resnet50-human",
]


def required() -> dict[str, dict[str, set[str]]]:
    """basename -> folders, loaders, workflows and Skool lessons that ask for it."""
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    models: dict[str, dict[str, set[str]]] = {}
    for w in man["workflows"]:
        graph = json.loads((REPO / w["canonical"]).read_text(encoding="utf-8", errors="replace"))
        if not isinstance(graph, dict):
            continue
        for node_type, filename in am.extract(graph):
            base = Path(filename.replace("\\", "/")).name
            rec = models.setdefault(base, {"folders": set(), "loaders": set(), "used_by": set(), "lessons": set()})
            rec["folders"].add(am.folder_for(node_type, base))
            rec["loaders"].add(node_type or "?")
            rec["used_by"].add(w["canonical"])
            rec["lessons"].update(s.removeprefix("skool:") for s in w.get("sources", []) if s.startswith("skool:"))
    return models


def harvest() -> tuple[dict[str, dict[str, str]], dict[str, list[str]]]:
    """Exact HF URLs found anywhere in the repo, and each Skool lesson's non-HF model pages."""
    exact: dict[str, dict[str, str]] = {}
    for pattern in EVIDENCE_GLOBS:
        for p in sorted(REPO.glob(pattern)):
            if p == PLAN:
                continue
            text = p.read_text(encoding="utf-8", errors="replace").replace("\\/", "/")
            for repo, rev, path in HF_URL.findall(text):
                exact.setdefault(Path(path).name, {"repo": repo, "repo_path": path,
                                                   "evidence": p.relative_to(REPO).as_posix()})
    pages: dict[str, list[str]] = {}
    if LESSONS.exists():
        for les in json.loads(LESSONS.read_text(encoding="utf-8"))["lessons"]:
            if les.get("lesson_url"):
                pages[les["lesson_url"]] = [u for u in les.get("links", []) if MANUAL_HOST.match(u)]
    return exact, pages


def listings(extra: list[str]) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    import resolve_models as rm
    token = rm.hf_token()
    index: dict[str, tuple[str, str]] = {}
    errors: dict[str, str] = {}
    for repo in dict.fromkeys(rm.REPOS + EXTRA_REPOS + extra):
        files = rm.list_repo(repo, token)
        if files and files[0].startswith("__ERROR__"):
            errors[repo] = files[0].removeprefix("__ERROR__ ")
            continue
        for path in files:
            index.setdefault(Path(path).name, (repo, path))
    return index, errors


def build(online: bool = False) -> dict[str, Any]:
    need = required()
    exact, pages = harvest()
    old = json.loads(PLAN.read_text(encoding="utf-8")) if PLAN.exists() else {}
    earlier = {r["file"]: r for r in old.get("resolved", []) if r.get("repo")}
    index, errors = listings(sorted({e["repo"] for e in exact.values()})) if online else ({}, {})
    buckets: dict[str, list[dict[str, Any]]] = {k: [] for k in
                                               ("resolved", "auto_download", "creator_private", "manual", "unresolved")}
    for name, rec in sorted(need.items()):
        folders = sorted(rec["folders"])
        entry: dict[str, Any] = {"file": name, "folder": next((f for f in folders if f != "unknown"), folders[0]),
                                 "loaders": sorted(rec["loaders"]), "workflow_count": len(rec["used_by"]),
                                 "used_by": sorted(rec["used_by"])}
        if name in CREATOR_PRIVATE or (PRIVATE_NAME.search(name) and name not in exact):
            buckets["creator_private"].append(entry)
        elif name in exact:
            buckets["resolved"].append({**entry, **exact[name]})
        elif name in earlier:
            e = earlier[name]
            buckets["resolved"].append({**entry, "repo": e["repo"], "repo_path": e["repo_path"],
                                        "evidence": "download-plan.json (earlier resolution)"})
        elif name in index:
            repo, path = index[name]
            buckets["resolved"].append({**entry, "repo": repo, "repo_path": path,
                                        "evidence": "filename match in the repo's public listing"})
        elif name in AUTO_DOWNLOAD:
            buckets["auto_download"].append(entry)
        else:
            look_at = sorted({u for lesson in rec["lessons"] for u in pages.get(lesson, [])})
            if look_at:
                buckets["manual"].append({**entry, "look_at": look_at})
            else:
                buckets["unresolved"].append(entry)
    # Keep what an earlier plan resolved for workflows that live outside the manifest.
    for name, e in earlier.items():
        if name not in need:
            buckets["resolved"].append({**e, "evidence": e.get("evidence", "download-plan.json (earlier resolution)")})
    for k in buckets:
        buckets[k].sort(key=lambda r: (-r["workflow_count"], r["file"]))
    return {"generated_by": "infra/runpod/plan_models.py", "online": online,
            "counts": {k: len(v) for k, v in buckets.items()}, **buckets, "repo_errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--online", action="store_true", help="also match filenames against Hugging Face repo listings")
    ap.add_argument("--dry-run", action="store_true", help="print counts without writing download-plan.json")
    args = ap.parse_args()
    plan = build(args.online)
    for k, n in plan["counts"].items():
        print(f"{k:<16} {n}")
    for r in plan["unresolved"]:
        print(f"  unresolved: {r['file']}  ({r['workflow_count']} wf)")
    if plan["repo_errors"]:
        print(f"repo listings that failed: {len(plan['repo_errors'])} (gated repos need HF_TOKEN)")
    if not args.dry_run:
        PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {PLAN.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
